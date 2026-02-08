"""Tests for app.domain.voice.assembly (combined voice sample + beeps)."""
import base64
import io
import wave

import pytest

from app.domain.voice.assembly import (
    assemble_voice_sample_with_beeps,
    generate_beep_16k,
    wav_bytes_to_pcm_16k,
)


def test_generate_beep_16k():
    beep = generate_beep_16k(duration_sec=0.2)
    assert len(beep) == 6400  # 16000 * 0.2 * 2 bytes
    assert isinstance(beep, bytes)


def test_wav_bytes_to_pcm_16k():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 8000)
    wav_bytes = buf.getvalue()
    pcm = wav_bytes_to_pcm_16k(wav_bytes)
    assert len(pcm) == 16000
    assert isinstance(pcm, bytes)


def test_assemble_empty():
    b64, ids = assemble_voice_sample_with_beeps([])
    assert b64 is None
    assert ids == []


def test_assemble_one_wav():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 8000)
    fake_b64 = base64.b64encode(buf.getvalue()).decode()
    b64, ids = assemble_voice_sample_with_beeps([("user1", fake_b64)])
    assert b64 is not None
    assert ids == ["user1"]
    decoded = base64.b64decode(b64)
    assert len(decoded) > 100
    with wave.open(io.BytesIO(decoded), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000


def test_assemble_two_wavs_has_beep_between():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 8000)
    fake_b64 = base64.b64encode(buf.getvalue()).decode()
    b64, ids = assemble_voice_sample_with_beeps([("a", fake_b64), ("b", fake_b64)])
    assert b64 is not None
    assert ids == ["a", "b"]
    decoded = base64.b64decode(b64)
    # Leading beep (0.2s) + two 0.5s segments + one 0.2s beep between = 1.4s PCM
    assert len(decoded) > 30000
