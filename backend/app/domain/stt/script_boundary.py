"""
Derive script time boundary from diarization and split into sub-spans using
length heuristic (800 ms pause + MIN/SOFT_MAX/HARD_MAX, best-available-pause scoring).
Used when word-level timing is missing for final STT results.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.domain.stt.session_registry import DiarInterval, diarization_reliable_end_sample

# Length heuristic parameters (plan defaults)
MIN_SEG_LEN_S = 1.2
TARGET_SEG_LEN_LO_S = 4.0
TARGET_SEG_LEN_HI_S = 12.0
SOFT_MAX_LEN_S = 12.0  # 12-15 s; use 14
HARD_MAX_LEN_S = 15.0
LONG_PAUSE_S = 0.8
SOFT_PAUSE_S = 0.5  # 350-500 ms; use 0.5
MIN_PAUSE_CANDIDATE_S = 0.35
FALLBACK_AFTER_SPEECH_S = 0.15  # 100-200 ms
FORCE_CUT_INSET_S = 0.2
MAX_SCRIPT_DURATION_S = 20.0
SAMPLE_RATE = 16000

# (start_s, end_s) stream-relative seconds
StreamInterval = Tuple[float, float]
# (start_s, end_s) sub-span in stream-relative seconds
SubSpan = Tuple[float, float]
# (cut_position_s, duration_s, score)
PauseCandidate = Tuple[float, float, float]


def _score_candidate(duration_s: float, seg_start_s: float, cut_position_s: float) -> float:
    """Score a pause candidate: +2 for >= 800ms, +1 for >= 500ms, +0.5 for >= 350ms; +1 if segment length in [4, 12]."""
    score = 0.0
    if duration_s >= 0.8:
        score += 2.0
    elif duration_s >= 0.5:
        score += 1.0
    elif duration_s >= MIN_PAUSE_CANDIDATE_S:
        score += 0.5
    seg_len = cut_position_s - seg_start_s
    if TARGET_SEG_LEN_LO_S <= seg_len <= TARGET_SEG_LEN_HI_S:
        score += 1.0
    return score


def derive_script_span_from_timeline(
    timeline: List[DiarInterval],
    stream_base: int,
    total_samples: int,
    lag_ms: int = 1000,
    max_script_duration_s: float = MAX_SCRIPT_DURATION_S,
) -> Optional[Tuple[float, float]]:
    """
    Compute script [start_s, end_s] in stream-relative seconds from speaker_timeline.
    Returns None if no valid span.
    """
    if not timeline:
        return None
    reliable_end = diarization_reliable_end_sample(total_samples, lag_ms)
    window_start = max(0, reliable_end - int(max_script_duration_s * SAMPLE_RATE))
    intervals_in_window = [
        (start, end, spk_id, conf, flag)
        for start, end, spk_id, conf, flag in timeline
        if end <= reliable_end and end > window_start and start < reliable_end
    ]
    if not intervals_in_window:
        return None
    script_start_sample = min(s for s, _, _, _, _ in intervals_in_window)
    script_end_sample = max(e for _, e, _, _, _ in intervals_in_window)
    if script_end_sample <= stream_base:
        return None
    stream_base_f = float(stream_base)
    script_start_s = (script_start_sample - stream_base_f) / SAMPLE_RATE
    script_end_s = (script_end_sample - stream_base_f) / SAMPLE_RATE
    if script_end_s <= script_start_s:
        return None
    return (script_start_s, script_end_s)


def derive_script_span_from_nemo(
    nemo_segments: List[Tuple[float, float, str]],
    stream_base: int,
    max_end_s: float,
) -> Optional[Tuple[float, float]]:
    """
    Compute script [start_s, end_s] in stream-relative seconds from nemo_latest_segments.
    nemo segments are (start_s_abs, end_s_abs, speaker_id) with abs = sample_index/16000.
    Returns None if no valid span.
    """
    if not nemo_segments:
        return None
    stream_base_s = stream_base / SAMPLE_RATE
    starts = [seg[0] - stream_base_s for seg in nemo_segments]
    ends = [seg[1] - stream_base_s for seg in nemo_segments]
    script_start_s = max(0.0, min(starts))
    script_end_s = min(max_end_s, max(ends))
    if script_end_s <= script_start_s:
        return None
    return (script_start_s, script_end_s)


def _timeline_to_stream_intervals(
    timeline: List[DiarInterval],
    script_start_sample: int,
    script_end_sample: int,
    stream_base: int,
) -> List[StreamInterval]:
    """Intervals intersecting [script_start_sample, script_end_sample], in stream-relative seconds, sorted by start."""
    stream_base_f = float(stream_base)
    out: List[StreamInterval] = []
    for start, end, _, _, _ in timeline:
        if end <= script_start_sample or start >= script_end_sample:
            continue
        clip_start = max(start, script_start_sample)
        clip_end = min(end, script_end_sample)
        if clip_end <= clip_start:
            continue
        start_s = (clip_start - stream_base_f) / SAMPLE_RATE
        end_s = (clip_end - stream_base_f) / SAMPLE_RATE
        out.append((start_s, end_s))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def _nemo_to_stream_intervals(
    nemo_segments: List[Tuple[float, float, str]],
    script_start_s: float,
    script_end_s: float,
    stream_base: int,
) -> List[StreamInterval]:
    """Segments overlapping [script_start_s, script_end_s] in stream-relative seconds, sorted by start."""
    stream_base_s = stream_base / SAMPLE_RATE
    out: List[StreamInterval] = []
    for start_abs, end_abs, _ in nemo_segments:
        start_s = start_abs - stream_base_s
        end_s = end_abs - stream_base_s
        if end_s <= script_start_s or start_s >= script_end_s:
            continue
        clip_start = max(start_s, script_start_s)
        clip_end = min(end_s, script_end_s)
        if clip_end <= clip_start:
            continue
        out.append((clip_start, clip_end))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def sub_spans_from_length_heuristic(
    script_start_s: float,
    script_end_s: float,
    intervals: List[StreamInterval],
) -> List[SubSpan]:
    """
    Single-pass: from ordered speech intervals in [script_start_s, script_end_s],
    compute sub-spans using MIN_SEG_LEN, LONG_PAUSE, SOFT_MAX, HARD_MAX and cooldown.
    Returns list of (start_s, end_s) in stream-relative seconds.
    """
    if not intervals:
        return [(script_start_s, script_end_s)]

    sub_spans: List[SubSpan] = []
    seg_start = script_start_s
    candidates: List[PauseCandidate] = []

    for i in range(len(intervals) - 1):
        intv_start, intv_end = intervals[i]
        next_start, next_end = intervals[i + 1]
        gap_start_s = intv_end  # end of current speech
        gap_end_s = next_start  # start of next speech
        gap_duration_s = gap_end_s - gap_start_s
        seg_len = gap_start_s - seg_start

        if gap_duration_s >= MIN_PAUSE_CANDIDATE_S:
            cut_position = gap_end_s
            score = _score_candidate(gap_duration_s, seg_start, cut_position)
            candidates.append((cut_position, gap_duration_s, score))

        # Primary: pause >= 800 ms and seg_len >= MIN_SEG_LEN
        if gap_duration_s >= LONG_PAUSE_S and seg_len >= MIN_SEG_LEN_S:
            sub_spans.append((seg_start, gap_end_s))
            seg_start = gap_end_s
            candidates = []
            continue

        # Hard max: force cut
        if seg_len >= HARD_MAX_LEN_S:
            if candidates:
                best = max(candidates, key=lambda c: c[2])
                cut_at = best[0]
            else:
                cut_at = min(seg_start + HARD_MAX_LEN_S, script_end_s - FORCE_CUT_INSET_S)
            if cut_at > seg_start:
                sub_spans.append((seg_start, cut_at))
                seg_start = cut_at
            candidates = []
            continue

        # Soft max: cut at best pause or last_speech_end + inset
        if seg_len >= SOFT_MAX_LEN_S:
            if candidates:
                best = max(candidates, key=lambda c: c[2])
                cut_at = best[0]
            else:
                cut_at = min(gap_start_s + FALLBACK_AFTER_SPEECH_S, script_end_s - FORCE_CUT_INSET_S)
            if cut_at > seg_start:
                sub_spans.append((seg_start, cut_at))
                seg_start = cut_at
            candidates = []
            continue

    sub_spans.append((seg_start, script_end_s))
    return sub_spans


def assign_text_to_sub_spans(
    text: str,
    sub_spans: List[SubSpan],
) -> List[Tuple[str, float, float]]:
    """
    Assign text chunks to sub-spans by duration proportion.
    Returns list of (text_chunk, start_s, end_s).
    """
    if not text or not sub_spans:
        return [(text or "", sub_spans[0][0], sub_spans[0][1])] if sub_spans else []
    if len(sub_spans) == 1:
        return [(text, sub_spans[0][0], sub_spans[0][1])]
    total_duration = sum(end_s - start_s for start_s, end_s in sub_spans)
    if total_duration <= 0:
        return [(text, sub_spans[0][0], sub_spans[0][1])]
    result: List[Tuple[str, float, float]] = []
    offset = 0
    sentence_end_chars = ".!?;:。！？"
    def _classify_char(ch: str) -> str:
        if not ch:
            return "none"
        if ch.isspace():
            return "space"
        if ch.isalpha():
            return "alpha"
        if ch.isdigit():
            return "digit"
        if ch in ".,!?;:":
            return "punct"
        return "other"
    def _nearest_sentence_boundary(text_val: str, start_offset: int, target_offset: int) -> Optional[int]:
        if not text_val:
            return None
        window = max(12, min(60, int(round(len(text_val) * 0.15))))
        min_i = max(start_offset + 1, target_offset - window)
        max_i = min(len(text_val), target_offset + window)
        best = None
        best_dist = None
        for i in range(min_i, max_i + 1):
            if i <= 0 or i > len(text_val):
                continue
            prev_char = text_val[i - 1]
            if prev_char not in sentence_end_chars:
                continue
            if i < len(text_val) and not text_val[i].isspace():
                continue
            dist = abs(i - target_offset)
            if best is None or dist < best_dist:
                best = i
                best_dist = dist
        return best
    for i, (start_s, end_s) in enumerate(sub_spans):
        dur = end_s - start_s
        if i == len(sub_spans) - 1:
            chunk = text[offset:]
        else:
            n_chars = max(0, int(round(len(text) * (dur / total_duration))))
            target_offset = min(offset + n_chars, len(text))
            end_offset = target_offset
            boundary_kind = "target"
            sentence_boundary = _nearest_sentence_boundary(text, offset, target_offset)
            if sentence_boundary is not None and sentence_boundary > offset:
                end_offset = sentence_boundary
                boundary_kind = "sentence"
            if 0 < target_offset < len(text):
                left = target_offset
                while left > offset and not text[left - 1].isspace():
                    left -= 1
                right = target_offset
                while right < len(text) and not text[right].isspace():
                    right += 1
                candidates: list[int] = []
                if left > offset and text[left - 1].isspace():
                    candidates.append(left)
                if right < len(text) and text[right].isspace():
                    candidates.append(right + 1)
                if candidates and boundary_kind != "sentence":
                    adjusted = min(candidates, key=lambda c: abs(c - target_offset))
                    if adjusted > offset:
                        end_offset = min(adjusted, len(text))
                        boundary_kind = "whitespace"
            if end_offset <= offset:
                end_offset = target_offset
                boundary_kind = "target"
            chunk = text[offset:end_offset]
            offset = end_offset
        result.append((chunk, start_s, end_s))
    return result


def intervals_in_sub_span(
    sub_span: SubSpan,
    intervals: List[StreamInterval],
) -> List[StreamInterval]:
    """
    Return intervals clipped to [sub_span[0], sub_span[1]], sorted by start.
    Used to get exact diarization bounds for audio extraction per segment.
    """
    start_s, end_s = sub_span
    out: List[StreamInterval] = []
    for a, b in intervals:
        if b <= start_s or a >= end_s:
            continue
        clip_start = max(a, start_s)
        clip_end = min(b, end_s)
        if clip_end <= clip_start:
            continue
        out.append((clip_start, clip_end))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def derive_and_segment(
    stream_base: int,
    total_samples: int,
    max_end_s: float,
    timeline: Optional[List[DiarInterval]],
    nemo_segments: Optional[List[Tuple[float, float, str]]],
    lag_ms: int = 1000,
) -> Tuple[Optional[List[SubSpan]], Optional[List[StreamInterval]]]:
    """
    Derive script boundary from timeline (prefer) or nemo; build stream intervals;
    run length heuristic. Returns (sub_spans, intervals) or (None, None).
    Caller uses assign_text_to_sub_spans(text, sub_spans) to get (text_chunk, start_s, end_s),
    and intervals_in_sub_span((start_s, end_s), intervals) for exact audio bounds per segment.
    """
    script_span = None
    intervals: List[StreamInterval] = []

    if timeline:
        script_span = derive_script_span_from_timeline(
            timeline, stream_base, total_samples, lag_ms=lag_ms
        )
        if script_span:
            script_start_s, script_end_s = script_span
            script_start_sample = stream_base + int(script_start_s * SAMPLE_RATE)
            script_end_sample = stream_base + int(script_end_s * SAMPLE_RATE)
            intervals = _timeline_to_stream_intervals(
                timeline, script_start_sample, script_end_sample, stream_base
            )

    if script_span is None and nemo_segments:
        script_span = derive_script_span_from_nemo(nemo_segments, stream_base, max_end_s)
        if script_span:
            script_start_s, script_end_s = script_span
            intervals = _nemo_to_stream_intervals(
                nemo_segments, script_start_s, script_end_s, stream_base
            )

    if script_span is None or not intervals:
        return (None, None)
    script_start_s, script_end_s = script_span
    sub_spans = sub_spans_from_length_heuristic(script_start_s, script_end_s, intervals)
    if not sub_spans:
        return (None, None)
    return (sub_spans, intervals)
