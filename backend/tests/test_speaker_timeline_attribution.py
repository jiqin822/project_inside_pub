"""Unit tests for speaker_timeline_attribution, including extract_clean_pcm_for_segment."""
from __future__ import annotations

from app.domain.stt.session_registry import OVERLAP_NONE
from app.domain.stt.speaker_timeline_attribution import extract_clean_pcm_for_segment

# DiarInterval = (start_sample, end_sample, spk_id, spk_conf, overlap_flag)
# 16000 samples = 1 second at 16 kHz; 1 sample = 2 bytes -> 32000 bytes/sec


def _make_pcm(num_samples: int) -> bytes:
    """Dummy PCM bytes (zeros) for the given number of samples (16-bit)."""
    return b"\x00\x00" * num_samples


def test_extract_clean_pcm_no_overlap_full_segment_returned() -> None:
    """Timeline with no overlap in segment: full segment returned."""
    start_sample = 0
    end_sample = 16000  # 1 sec
    segment_pcm = _make_pcm(end_sample - start_sample)
    timeline = [
        (0, 16000, "spk_0", 0.8, OVERLAP_NONE),
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is not None
    assert len(result) == (end_sample - start_sample) * 2
    assert result == segment_pcm


def test_extract_clean_pcm_middle_overlap_two_clean_chunks() -> None:
    """Timeline with middle overlap (two different speakers): two clean chunks, concatenated length correct."""
    # Segment [0, 48000) = 3 sec. Timeline: [0, 16000) spk_0, [16000, 32000) both spk_0 and spk_1, [32000, 48000) spk_0.
    start_sample = 0
    end_sample = 48000
    segment_pcm = _make_pcm(end_sample - start_sample)
    timeline = [
        (0, 32000, "spk_0", 0.8, OVERLAP_NONE),   # 0-32k spk_0
        (16000, 32000, "spk_1", 0.8, OVERLAP_NONE),  # 16k-32k spk_1 (overlap 16k-32k)
        (32000, 48000, "spk_0", 0.8, OVERLAP_NONE),  # 32k-48k spk_0
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is not None
    # Clean spans: [0, 16000) spk_0 only, [32000, 48000) spk_0 only. Total 2 sec = 32000 samples = 64000 bytes.
    assert len(result) == 64000
    assert result == segment_pcm[0:32000] + segment_pcm[64000:96000]


def test_extract_clean_pcm_overlap_throughout_returns_none() -> None:
    """Timeline with overlap throughout or clean total < 1 s -> None."""
    start_sample = 0
    end_sample = 48000  # 3 sec
    segment_pcm = _make_pcm(end_sample - start_sample)
    # Entire segment has two speakers: spk_0 and spk_1 over [0, 48000)
    timeline = [
        (0, 48000, "spk_0", 0.8, OVERLAP_NONE),
        (0, 48000, "spk_1", 0.8, OVERLAP_NONE),
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is None


def test_extract_clean_pcm_clean_under_one_second_returns_none() -> None:
    """Total clean duration < 1 s -> None."""
    start_sample = 0
    end_sample = 32000  # 2 sec
    segment_pcm = _make_pcm(end_sample - start_sample)
    # Only [0, 8000) is single-speaker (0.5 sec), rest overlap
    timeline = [
        (0, 8000, "spk_0", 0.8, OVERLAP_NONE),
        (8000, 32000, "spk_0", 0.8, OVERLAP_NONE),
        (8000, 32000, "spk_1", 0.8, OVERLAP_NONE),
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is None


def test_extract_clean_pcm_same_speaker_overlapping_intervals_one_clean_span() -> None:
    """Two intervals from same speaker that overlap in time -> one clean span covering the overlap."""
    # Segment [0, 32000) = 2 sec. Timeline: [0, 16000) spk_0, [8000, 32000) spk_0 (overlap 8k-16k).
    start_sample = 0
    end_sample = 32000
    segment_pcm = _make_pcm(end_sample - start_sample)
    timeline = [
        (0, 16000, "spk_0", 0.8, OVERLAP_NONE),
        (8000, 32000, "spk_0", 0.8, OVERLAP_NONE),
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is not None
    # Entire [0, 32000) has exactly one distinct speaker -> full segment
    assert len(result) == (end_sample - start_sample) * 2
    assert result == segment_pcm


def test_extract_clean_pcm_invalid_segment_pcm_length_returns_none() -> None:
    """len(segment_pcm) != (end_sample - start_sample) * 2 -> None."""
    start_sample = 0
    end_sample = 16000
    segment_pcm = b"\x00" * 1000  # wrong length
    timeline = [(0, 16000, "spk_0", 0.8, OVERLAP_NONE)]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm
    )
    assert result is None


def test_extract_clean_pcm_empty_timeline_returns_none() -> None:
    """Empty timeline -> None."""
    start_sample = 0
    end_sample = 16000
    segment_pcm = _make_pcm(end_sample - start_sample)
    result = extract_clean_pcm_for_segment(
        [], start_sample, end_sample, segment_pcm
    )
    assert result is None


def test_extract_clean_pcm_segment_fully_in_overlap_returns_none() -> None:
    """Segment fully in overlap (two speakers, no single-speaker span >= 1 s) -> None."""
    start_sample = 0
    end_sample = 32000  # 2 sec
    segment_pcm = _make_pcm(end_sample - start_sample)
    # Two speakers over full segment; no span has only one speaker
    timeline = [
        (0, 32000, "spk_0", 0.8, OVERLAP_NONE),
        (0, 32000, "spk_1", 0.8, OVERLAP_NONE),
    ]
    result = extract_clean_pcm_for_segment(
        timeline, start_sample, end_sample, segment_pcm, min_clean_seconds=1.0
    )
    assert result is None


def test_extract_clean_pcm_invalid_end_before_start_returns_none() -> None:
    """end_sample <= start_sample -> None (precondition)."""
    segment_pcm = _make_pcm(16000)
    result = extract_clean_pcm_for_segment(
        [(0, 16000, "spk_0", 0.8, OVERLAP_NONE)], 100, 50, segment_pcm
    )
    assert result is None
