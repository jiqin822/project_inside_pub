"""Assemble multiple voice WAVs and beeps into a single WAV for Gemini speaker identification."""
from __future__ import annotations

import base64
import io
import wave

import numpy as np

TARGET_SAMPLE_RATE = 16000
BEEP_DURATION_SEC = 0.2
BEEP_FREQUENCY_HZ = 880.0
BEEP_AMPLITUDE = 0.5


def wav_bytes_to_pcm_16k(wav_bytes: bytes) -> bytes:
    """Read WAV bytes and return raw PCM 16-bit mono at 16 kHz."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        nchannels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        framerate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if not frames:
        return b""

    # Convert to int16 array
    if sampwidth == 2:  # 16-bit
        pcm = np.frombuffer(frames, dtype=np.int16)
    elif sampwidth == 1:  # 8-bit, scale up
        pcm = (np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128) * 256
    else:
        return b""

    # Mono: mix down if stereo
    if nchannels == 2:
        pcm = pcm.reshape(-1, 2).mean(axis=1).astype(np.int16)
    elif nchannels != 1:
        return b""

    # Resample to 16 kHz if needed
    if framerate != TARGET_SAMPLE_RATE:
        duration_sec = len(pcm) / framerate
        num_out = int(duration_sec * TARGET_SAMPLE_RATE)
        indices = np.linspace(0, len(pcm) - 1, num_out, endpoint=True)
        pcm = np.interp(indices, np.arange(len(pcm)), pcm.astype(np.float32)).astype(np.int16)

    return pcm.tobytes()


def generate_beep_16k(
    duration_sec: float = BEEP_DURATION_SEC,
    frequency_hz: float = BEEP_FREQUENCY_HZ,
    amplitude: float = BEEP_AMPLITUDE,
) -> bytes:
    """Generate a short sine beep as PCM 16-bit mono at 16 kHz."""
    num_samples = int(TARGET_SAMPLE_RATE * duration_sec)
    t = np.arange(num_samples, dtype=np.float32) / TARGET_SAMPLE_RATE
    sine = np.sin(2 * np.pi * frequency_hz * t) * amplitude
    # Scale to int16: clamp to [-1, 1] then * 32767
    sine = np.clip(sine, -1.0, 1.0)
    pcm = (sine * 32767).astype(np.int16)
    return pcm.tobytes()


def assemble_voice_sample_with_beeps(
    ordered_user_id_and_wav_base64: list[tuple[str, str]],
) -> tuple[str | None, list[str]]:
    """
    Concatenate voice WAVs with a beep between each, in order.
    Returns (combined_wav_base64, speaker_user_ids_in_order).
    If no samples, returns (None, []).
    """
    if not ordered_user_id_and_wav_base64:
        return None, []

    pcm_chunks: list[bytes] = []
    speaker_user_ids_in_order: list[str] = []

    for user_id, wav_b64 in ordered_user_id_and_wav_base64:
        raw = wav_b64.strip()
        if "base64," in raw:
            raw = raw.split("base64,", 1)[1]
        try:
            wav_bytes = base64.b64decode(raw)
        except Exception:
            continue
        pcm = wav_bytes_to_pcm_16k(wav_bytes)
        if not pcm:
            continue
        pcm_chunks.append(pcm)
        speaker_user_ids_in_order.append(user_id)

    if not pcm_chunks:
        return None, []

    # Leading beep, then voice samples with beep between each (no beep after the last)
    combined_parts: list[bytes] = [generate_beep_16k()]
    for i, pcm in enumerate(pcm_chunks):
        combined_parts.append(pcm)
        if i < len(pcm_chunks) - 1:
            combined_parts.append(generate_beep_16k())
    combined_pcm = b"".join(combined_parts)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(TARGET_SAMPLE_RATE)
        wav_file.writeframes(combined_pcm)

    combined_b64 = base64.b64encode(wav_buffer.getvalue()).decode("ascii")
    return combined_b64, speaker_user_ids_in_order
