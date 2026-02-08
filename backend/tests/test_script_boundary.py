"""Unit tests for script_boundary: derive script span and length-heuristic segmentation."""
from __future__ import annotations

import pytest

from app.domain.stt.session_registry import DiarInterval
from app.domain.stt.script_boundary import (
    assign_text_to_sub_spans,
    derive_script_span_from_nemo,
    derive_script_span_from_timeline,
    derive_and_segment,
    intervals_in_sub_span,
    sub_spans_from_length_heuristic,
)


def test_derive_script_span_from_timeline_empty_returns_none() -> None:
    assert derive_script_span_from_timeline([], 0, 16000) is None


def test_derive_script_span_from_timeline_single_interval() -> None:
    # (start_sample, end_sample, spk_id, conf, flag); 0-1s at 16kHz
    timeline: list[DiarInterval] = [(0, 16000, "0", 0.9, "NONE")]
    out = derive_script_span_from_timeline(timeline, 0, 16000, lag_ms=0)
    assert out is not None
    assert out[0] == 0.0
    assert out[1] == 1.0


def test_derive_script_span_from_nemo_empty_returns_none() -> None:
    assert derive_script_span_from_nemo([], 0, 10.0) is None


def test_derive_script_span_from_nemo_converts_to_stream_relative() -> None:
    # nemo (start_s_abs, end_s_abs, speaker_id); stream_base = 16000 (1s)
    segments = [(2.0, 4.0, "spk_0")]  # abs 2-4s -> stream 1-3s
    out = derive_script_span_from_nemo(segments, 16000, 10.0)
    assert out is not None
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(3.0)


def test_sub_spans_single_interval_one_span() -> None:
    intervals = [(0.0, 5.0)]
    sub = sub_spans_from_length_heuristic(0.0, 5.0, intervals)
    assert sub == [(0.0, 5.0)]


def test_sub_spans_long_pause_splits() -> None:
    # Gaps: 0.5s, 1.0s (>= 0.8), 0.3s. Second gap should trigger cut when seg_len >= 1.2
    intervals = [(0.0, 2.0), (2.5, 4.0), (5.0, 7.0)]  # gap 0.5s, then 1.0s
    sub = sub_spans_from_length_heuristic(0.0, 7.0, intervals)
    assert len(sub) >= 2
    assert sub[0][0] == 0.0
    assert sub[-1][1] == 7.0


def test_assign_text_to_sub_spans_single_returns_full_text() -> None:
    result = assign_text_to_sub_spans("Hello world", [(0.0, 1.0)])
    assert len(result) == 1
    assert result[0][0] == "Hello world"
    assert result[0][1] == 0.0
    assert result[0][2] == 1.0


def test_assign_text_to_sub_spans_proportional() -> None:
    sub_spans = [(0.0, 2.0), (2.0, 5.0)]  # 2s and 3s
    result = assign_text_to_sub_spans("abcdefgh", sub_spans)
    assert len(result) == 2
    total_chars = len(result[0][0]) + len(result[1][0])
    assert total_chars == 8
    assert result[0][1] == 0.0 and result[0][2] == 2.0
    assert result[1][1] == 2.0 and result[1][2] == 5.0


def test_derive_and_segment_no_data_returns_none_none() -> None:
    assert derive_and_segment(0, 16000, 1.0, None, None) == (None, None)
    assert derive_and_segment(0, 16000, 1.0, [], None) == (None, None)
    assert derive_and_segment(0, 16000, 1.0, None, []) == (None, None)


def test_derive_and_segment_nemo_returns_sub_spans_and_intervals() -> None:
    # nemo (start_s_abs, end_s_abs, speaker_id); stream_base = 16000 (1s), one segment 2-4s -> stream 1-3s
    sub_spans, intervals = derive_and_segment(16000, 16000 * 10, 10.0, None, [(2.0, 4.0, "spk_0")])
    assert sub_spans is not None
    assert intervals is not None
    assert len(sub_spans) >= 1
    assert sub_spans[0][0] == pytest.approx(1.0)
    assert sub_spans[0][1] == pytest.approx(3.0)
    assert len(intervals) == 1
    assert intervals[0] == (1.0, 3.0)


def test_intervals_in_sub_span_empty() -> None:
    assert intervals_in_sub_span((0.0, 1.0), []) == []
    assert intervals_in_sub_span((5.0, 6.0), [(0.0, 1.0), (2.0, 3.0)]) == []


def test_intervals_in_sub_span_clips_to_sub_span() -> None:
    intervals = [(0.0, 2.0), (2.5, 5.0), (5.0, 7.0)]
    out = intervals_in_sub_span((1.0, 4.0), intervals)
    assert out == [(1.0, 2.0), (2.5, 4.0)]


def test_intervals_in_sub_span_full_overlap() -> None:
    intervals = [(0.5, 1.5), (2.0, 3.0)]
    out = intervals_in_sub_span((0.0, 4.0), intervals)
    assert out == [(0.5, 1.5), (2.0, 3.0)]
