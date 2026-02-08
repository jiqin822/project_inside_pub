"""
Attribution of transcript segments to speakers using the sample-indexed speaker timeline.
Plan: only resolve for segments ending before now_sample - L; overlap policy (dominant < 20% -> dominant, > 50% -> OVERLAP).
Map track embeddings to known users (two-tier labels, commit rules, collision check).
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.domain.stt.session_registry import DiarInterval, SttSessionContext
from app.domain.voice.embeddings import (
    cosine_similarity,
    score_user_multi_embedding,
)

# Labels for attribution when timeline is ambiguous or overlapping
OVERLAP_LABEL = "OVERLAP"
UNCERTAIN_LABEL = "UNCERTAIN"

# Attribution source for client/debug
WORD_LEVEL = "word_level"
SEGMENT_LEVEL = "segment_level"
FALLBACK_ENDPOINTING = "fallback_endpointing"


def _overlap_samples(a0: int, a1: int, b0: int, b1: int) -> int:
    """Overlap in samples of [a0, a1) with [b0, b1)."""
    lo = max(a0, b0)
    hi = min(a1, b1)
    return max(0, hi - lo)


def extract_clean_pcm_for_segment(
    timeline: List[DiarInterval],
    start_sample: int,
    end_sample: int,
    segment_pcm: bytes,
    *,
    sample_rate: int = 16000,
    min_clean_seconds: float = 1.0,
) -> Optional[bytes]:
    """
    Extract PCM for single-speaker (clean) sub-intervals of the segment and concatenate.

    A span is "clean" when exactly one distinct speaker is active (overlapping intervals
    from the same speaker count as one). The per-interval overlap_flag is not used;
    overlap is derived from multiple distinct speakers covering the same sample range.

    Precondition: len(segment_pcm) must equal (end_sample - start_sample) * 2 (16-bit).
    Returns None if precondition fails, timeline is empty, or total clean duration < min_clean_seconds.
    """
    expected_bytes = (end_sample - start_sample) * 2
    if end_sample <= start_sample or len(segment_pcm) != expected_bytes:
        return None
    if not timeline:
        return None

    # Restrict to intervals intersecting [start_sample, end_sample]; clip to segment.
    events: List[Tuple[int, int, str]] = []  # (position, delta, spk_id); delta +1 or -1
    for t in timeline:
        ts_start, ts_end, spk_id, _conf, _overlap_flag = t
        clip_lo = max(ts_start, start_sample)
        clip_hi = min(ts_end, end_sample)
        if clip_hi <= clip_lo:
            continue
        events.append((clip_lo, 1, spk_id))
        events.append((clip_hi, -1, spk_id))

    if not events:
        return None

    # Sort by position; at same position process -1 before +1 so span [prev, pos] uses state before update.
    events.sort(key=lambda e: (e[0], 0 if e[1] == -1 else 1))

    # Sweep: per-speaker count; span [prev, pos] is clean iff exactly one distinct speaker active.
    active: dict[str, int] = {}
    clean_spans: List[Tuple[int, int]] = []
    prev_pos = start_sample
    for pos, delta, spk_id in events:
        if pos > prev_pos:
            if len([s for s, c in active.items() if c > 0]) == 1:
                clean_spans.append((prev_pos, pos))
        if delta == -1:
            active[spk_id] = active.get(spk_id, 0) - 1
            if active[spk_id] <= 0:
                del active[spk_id]
        else:
            active[spk_id] = active.get(spk_id, 0) + 1
        prev_pos = pos

    # Check final span from last event to end_sample
    if end_sample > prev_pos and len([s for s, c in active.items() if c > 0]) == 1:
        clean_spans.append((prev_pos, end_sample))

    total_clean_samples = sum(hi - lo for lo, hi in clean_spans)
    min_clean_samples = int(min_clean_seconds * sample_rate)
    if total_clean_samples < min_clean_samples:
        return None

    # Extract byte ranges from segment_pcm (segment covers [start_sample, end_sample]).
    parts: List[bytes] = []
    for clean_start, clean_end in clean_spans:
        byte_off = (clean_start - start_sample) * 2
        byte_len = (clean_end - clean_start) * 2
        parts.append(segment_pcm[byte_off : byte_off + byte_len])
    return b"".join(parts)


def query_speaker_timeline(
    ctx: SttSessionContext,
    start_sample: int,
    end_sample: int,
    *,
    dominant_threshold: float = 0.5,
    overlap_threshold: float = 0.5,
    min_dominant_ratio: float = 0.2,
    attribution_source: str = SEGMENT_LEVEL,
) -> tuple[str, float, bool, str]:
    """
    Query speaker_timeline for interval [start_sample, end_sample].
    Returns (speaker_label, confidence, is_overlap, attribution_source).
    speaker_label: spk_id (from track's stable_label if available), OVERLAP_LABEL, or UNCERTAIN_LABEL.
    """
    def _log_decision(
        reason: str,
        label: str,
        *,
        best_spk_id: Optional[str] = None,
        best_ratio: Optional[float] = None,
        overlap_ratio: Optional[float] = None,
        totals_count: Optional[int] = None,
        interval_samples: Optional[int] = None,
    ) -> None:
        return None

    if end_sample <= start_sample:
        _log_decision("invalid_bounds", UNCERTAIN_LABEL, interval_samples=0)
        return UNCERTAIN_LABEL, 0.0, True, attribution_source
    interval_samples = end_sample - start_sample
    totals: dict[str, int] = {}
    for t in ctx.speaker_timeline:
        ts_start, ts_end, spk_id, _conf, _overlap_flag = t
        ov = _overlap_samples(start_sample, end_sample, ts_start, ts_end)
        if ov <= 0:
            continue
        totals[spk_id] = totals.get(spk_id, 0) + ov
    if not totals:
        _log_decision("no_overlap", UNCERTAIN_LABEL, totals_count=0, interval_samples=interval_samples)
        return UNCERTAIN_LABEL, 0.0, False, attribution_source
    total_attributed = sum(totals.values())
    overlap_ratio = 1.0 - (total_attributed / interval_samples) if interval_samples else 0.0
    # Dominant speaker: one spk has > dominant_threshold of attributed time
    best_spk = max(totals.items(), key=lambda kv: kv[1])
    best_ratio = best_spk[1] / total_attributed if total_attributed else 0.0
    if overlap_ratio >= overlap_threshold:
        _log_decision(
            "overlap_ratio",
            OVERLAP_LABEL,
            best_spk_id=best_spk[0],
            best_ratio=best_ratio,
            overlap_ratio=overlap_ratio,
            totals_count=len(totals),
            interval_samples=interval_samples,
        )
        return OVERLAP_LABEL, float(1.0 - overlap_ratio), True, attribution_source
    if best_ratio >= dominant_threshold:
        # Resolve to track's stable_label if we have it
        track = ctx.spk_tracks.get(best_spk[0])
        label = track.stable_label if track else best_spk[0]
        _log_decision(
            "dominant_ratio",
            label,
            best_spk_id=best_spk[0],
            best_ratio=best_ratio,
            overlap_ratio=overlap_ratio,
            totals_count=len(totals),
            interval_samples=interval_samples,
        )
        return label, best_ratio, False, attribution_source
    if best_ratio >= min_dominant_ratio:
        track = ctx.spk_tracks.get(best_spk[0])
        label = track.stable_label if track else best_spk[0]
        _log_decision(
            "min_dominant_ratio",
            label,
            best_spk_id=best_spk[0],
            best_ratio=best_ratio,
            overlap_ratio=overlap_ratio,
            totals_count=len(totals),
            interval_samples=interval_samples,
        )
        return label, best_ratio, False, attribution_source
    _log_decision(
        "uncertain_ratio",
        UNCERTAIN_LABEL,
        best_spk_id=best_spk[0],
        best_ratio=best_ratio,
        overlap_ratio=overlap_ratio,
        totals_count=len(totals),
        interval_samples=interval_samples,
    )
    return UNCERTAIN_LABEL, best_ratio, False, attribution_source


def score_track_against_users(
    ctx: SttSessionContext,
    track_embedding: list[float],
    *,
    device_filter: Optional[str] = None,
) -> list[tuple[str, float]]:
    """
    Score track embedding against all known users. Uses voice_embeddings_multi (percentile_90)
    when set, else voice_embeddings (single centroid). Returns list of (user_id, score) sorted by score desc.
    """
    scores: list[tuple[str, float]] = []
    if ctx.voice_embeddings_multi:
        for user_id, (embs_list, meta_list) in ctx.voice_embeddings_multi.items():
            s = score_user_multi_embedding(
                track_embedding,
                embs_list,
                percentile=90.0,
                device_filter=device_filter,
                embeddings_meta=meta_list if meta_list else None,
            )
            scores.append((user_id, s))
    else:
        for user_id, emb in ctx.voice_embeddings.items():
            s = cosine_similarity(track_embedding, emb)
            scores.append((user_id, s))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


def update_track_label_from_embedding(
    ctx: SttSessionContext,
    spk_id: str,
    *,
    commit_threshold: float = 0.85,
    commit_margin: float = 0.25,
    temperature: float = 0.1,
    min_embedding_count: int = 2,
) -> None:
    """
    Score track against users, update label_posterior (softmax + EMA), and optionally commit stable_label.
    Commit only if P(best) >= commit_threshold, (P(best)-P(second)) >= commit_margin,
    and track has at least min_embedding_count embeddings. Collision: if user already assigned to another track, do not commit.
    """
    track = ctx.spk_tracks.get(spk_id)
    if not track or not track.track_embedding:
        return
    if track.embedding_count < min_embedding_count:
        return
    scores = score_track_against_users(ctx, track.track_embedding)
    if not scores:
        return
    # Softmax over scores (temperature)
    best_user, best_score = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0.0
    exp_scores = [math.exp(s / max(temperature, 1e-8)) for _, s in scores]
    z = sum(exp_scores)
    probs = [e / z for e in exp_scores]
    # EMA into label_posterior
    new_posterior = {user_id: probs[i] for i, (user_id, _) in enumerate(scores)}
    alpha_ema = 0.3
    if track.label_posterior:
        for uid, p in new_posterior.items():
            track.label_posterior[uid] = (1 - alpha_ema) * track.label_posterior.get(uid, 0.0) + alpha_ema * p
    else:
        track.label_posterior = dict(new_posterior)
    track.current_best_label = best_user
    p_best = track.label_posterior.get(best_user, 0.0)
    p_second = max(
        (track.label_posterior.get(uid, 0.0) for uid, _ in scores[1:]),
        default=0.0,
    )
    if p_best >= commit_threshold and (p_best - p_second) >= commit_margin:
        # Collision check: is best_user already stable_label of another active track?
        for other_spk, other_track in ctx.spk_tracks.items():
            if other_spk == spk_id:
                continue
            if other_track.stable_label == best_user:
                return  # do not commit; keep Unknown
        track.stable_label = best_user
