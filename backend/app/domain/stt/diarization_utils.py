from __future__ import annotations

from typing import Optional


def overlap_s(a0: float, a1: float, b0: float, b1: float) -> float:
    lo = max(a0, b0)
    hi = min(a1, b1)
    return max(0.0, hi - lo)


def best_overlap_speaker_id(
    segments: list[tuple[float, float, str]],
    seg_start_s: float,
    seg_end_s: float,
) -> Optional[str]:
    """Return speaker_id with maximum overlap with [seg_start_s, seg_end_s]."""
    if not segments or seg_end_s <= seg_start_s:
        return None
    totals: dict[str, float] = {}
    for start_s, end_s, speaker_id in segments:
        ov = overlap_s(seg_start_s, seg_end_s, start_s, end_s)
        if ov <= 0:
            continue
        totals[speaker_id] = totals.get(speaker_id, 0.0) + ov
    if not totals:
        return None
    return max(totals.items(), key=lambda kv: kv[1])[0]

