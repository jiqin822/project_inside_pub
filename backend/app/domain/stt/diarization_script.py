"""
Programmatic diarization scripts for unit testing.

Segment format: list[tuple[float, float, str]] i.e. (start_s, end_s, speaker_id).
Compatible with diarization_utils and nemo_sortformer_diarizer.DiarSegment.
"""
from __future__ import annotations

import math
import random
import struct
from typing import Optional

# Segment list: (start_s, end_s, speaker_id)
DiarScript = list[tuple[float, float, str]]


def make_script(segments: DiarScript) -> DiarScript:
    """
    Normalize a segment list: sort by start_s, drop invalid (start >= end).
    Overlaps and gaps are preserved as-is.
    """
    out: DiarScript = []
    for start_s, end_s, speaker_id in segments:
        if start_s >= end_s:
            continue
        out.append((float(start_s), float(end_s), str(speaker_id)))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def make_script_alternating(
    duration_s: float,
    turn_duration_s: float,
    speaker_ids: list[str],
) -> DiarScript:
    """
    Build a script with speakers taking turns (no overlap, no gap).
    Fills [0, duration_s) with turns of turn_duration_s; cycles through speaker_ids.
    """
    if duration_s <= 0 or turn_duration_s <= 0 or not speaker_ids:
        return []
    segments: DiarScript = []
    t = 0.0
    i = 0
    while t < duration_s:
        end = min(t + turn_duration_s, duration_s)
        segments.append((t, end, speaker_ids[i % len(speaker_ids)]))
        t = end
        i += 1
    return segments


def make_script_random(
    duration_s: float,
    num_turns: int,
    speaker_ids: list[str],
    seed: Optional[int] = None,
) -> DiarScript:
    """
    Build a script with num_turns segments and random boundaries in [0, duration_s).
    Segments may overlap or have gaps; speaker cycles through speaker_ids.
    """
    if duration_s <= 0 or num_turns <= 0 or not speaker_ids:
        return []
    rng = random.Random(seed)
    # Random starts and ends; we sort and assign speakers
    points: list[float] = [0.0, duration_s]
    for _ in range(num_turns - 1):
        points.append(rng.uniform(0.0, duration_s))
    points.sort()
    segments: DiarScript = []
    for k in range(len(points) - 1):
        start_s, end_s = points[k], points[k + 1]
        if start_s >= end_s:
            continue
        speaker_id = speaker_ids[k % len(speaker_ids)]
        segments.append((start_s, end_s, speaker_id))
    return segments


def script_to_readable(segments: DiarScript) -> str:
    """Human-readable string e.g. '0.0-1.0 spk_0, 1.0-2.5 spk_1'."""
    return ", ".join(f"{s[0]}-{s[1]} {s[2]}" for s in segments)


def script_to_nemo_raw(segments: DiarScript) -> list[tuple[float, float, int]]:
    """
    Convert (start_s, end_s, speaker_id) to NeMo raw format (start_s, end_s, speaker_index).
    speaker_id must be 'spk_0', 'spk_1', ...; index is parsed from it.
    """
    raw: list[tuple[float, float, int]] = []
    for start_s, end_s, speaker_id in segments:
        if not speaker_id.startswith("spk_"):
            continue
        try:
            idx = int(speaker_id[4:])
        except ValueError:
            continue
        raw.append((start_s, end_s, idx))
    return raw


def script_to_pcm16(
    segments: DiarScript,
    duration_s: float,
    sample_rate: int = 16000,
) -> bytes:
    """
    Generate 16-bit mono PCM matching the script: each segment gets a distinct
    sine tone (by speaker_id) so boundaries are known. Used for integration-style
    tests; NeMo may not assign speakers by frequency, so assert only high-level.
    """
    if duration_s <= 0 or sample_rate <= 0:
        return b""
    num_samples = int(math.ceil(duration_s * sample_rate))
    # Build speaker_id -> frequency (Hz) for distinct tones
    seen: dict[str, int] = {}
    freqs = [300, 500, 700, 900]
    for _, _, spk in segments:
        if spk not in seen:
            seen[spk] = freqs[len(seen) % len(freqs)]
    # Amplitude for 16-bit (avoid clipping)
    amp = 0.3 * 32767
    samples: list[int] = [0] * num_samples
    for start_s, end_s, speaker_id in segments:
        freq = seen.get(speaker_id, 440)
        i0 = max(0, int(start_s * sample_rate))
        i1 = min(num_samples, int(end_s * sample_rate))
        for i in range(i0, i1):
            t = i / sample_rate
            val = amp * math.sin(2 * math.pi * freq * t)
            samples[i] = int(max(-32768, min(32767, val)))
    return struct.pack(f"<{num_samples}h", *samples)
