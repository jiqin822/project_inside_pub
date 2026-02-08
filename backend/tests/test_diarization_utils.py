from app.domain.stt.diarization_script import (
    make_script,
    make_script_alternating,
    make_script_random,
    script_to_nemo_raw,
    script_to_pcm16,
    script_to_readable,
)
from app.domain.stt.diarization_utils import best_overlap_speaker_id, overlap_s


def test_best_overlap_speaker_id_none_when_empty() -> None:
    assert best_overlap_speaker_id([], 0.0, 1.0) is None


def test_best_overlap_speaker_id_picks_max_overlap() -> None:
    segments = [
        (0.0, 1.0, "spk_0"),
        (1.0, 3.0, "spk_1"),
        (3.0, 4.0, "spk_0"),
    ]
    # Overlaps spk_1 for 1.5s, spk_0 for 0.5s
    assert best_overlap_speaker_id(segments, 1.5, 3.5) == "spk_1"


def test_best_overlap_speaker_id_sums_multiple_turns() -> None:
    segments = [
        (0.0, 1.0, "spk_0"),
        (1.0, 2.0, "spk_1"),
        (2.0, 3.0, "spk_0"),
    ]
    # Overlap with spk_0 is 1.0s total, spk_1 is 0.5s
    assert best_overlap_speaker_id(segments, 0.5, 2.5) == "spk_0"


def test_best_overlap_speaker_id_alternating_script() -> None:
    """Use make_script_alternating to get segments; query range overlaps one speaker."""
    segments = make_script_alternating(4.0, 1.0, ["spk_0", "spk_1"])
    assert len(segments) == 4
    # [0,1) spk_0, [1,2) spk_1, [2,3) spk_0, [3,4) spk_1
    # Query [1.5, 2.5]: only spk_1
    assert best_overlap_speaker_id(segments, 1.5, 2.5) == "spk_1"
    # Query [0.5, 1.5]: spk_0 0.5s, spk_1 0.5s -> first max wins
    assert best_overlap_speaker_id(segments, 0.5, 1.5) in ("spk_0", "spk_1")


def test_overlap_s_with_script_segments() -> None:
    """overlap_s with segment boundaries from a script."""
    segments = make_script([(0.0, 1.0, "spk_0"), (1.0, 2.0, "spk_1"), (2.0, 3.0, "spk_0")])
    # Query [0.5, 1.5] vs [0, 1] -> 0.5s
    assert overlap_s(0.5, 1.5, 0.0, 1.0) == 0.5
    # Query [0.5, 1.5] vs [1, 2] -> 0.5s
    assert overlap_s(0.5, 1.5, 1.0, 2.0) == 0.5
    # No overlap
    assert overlap_s(0.0, 1.0, 1.0, 2.0) == 0.0


def test_script_to_readable() -> None:
    """Human-readable script for debugging."""
    segments = make_script_alternating(2.0, 1.0, ["spk_0", "spk_1"])
    s = script_to_readable(segments)
    assert "0.0-1.0 spk_0" in s
    assert "1.0-2.0 spk_1" in s


def test_make_script_normalizes_and_sorts() -> None:
    """make_script drops invalid segments and sorts by start_s."""
    raw = [(2.0, 3.0, "spk_1"), (0.0, 1.0, "spk_0"), (1.5, 1.5, "drop")]
    out = make_script(raw)
    assert len(out) == 2
    assert out[0] == (0.0, 1.0, "spk_0")
    assert out[1] == (2.0, 3.0, "spk_1")


def test_make_script_random_deterministic_with_seed() -> None:
    """make_script_random with seed produces same script for best_overlap_speaker_id."""
    segs1 = make_script_random(5.0, 4, ["spk_0", "spk_1"], seed=42)
    segs2 = make_script_random(5.0, 4, ["spk_0", "spk_1"], seed=42)
    assert segs1 == segs2
    assert len(segs1) <= 4
    # Query a range; result should be one of the speakers
    got = best_overlap_speaker_id(segs1, 1.0, 3.0)
    assert got is None or got in ("spk_0", "spk_1")


def test_script_to_nemo_raw() -> None:
    """script_to_nemo_raw converts spk_N to (start_s, end_s, index)."""
    script = make_script_alternating(1.0, 0.5, ["spk_0", "spk_1"])
    raw = script_to_nemo_raw(script)
    assert raw == [(0.0, 0.5, 0), (0.5, 1.0, 1)]


def test_script_to_pcm16_length_and_nonzero() -> None:
    """script_to_pcm16 produces 16-bit mono PCM of expected length."""
    script = make_script_alternating(1.0, 0.5, ["spk_0", "spk_1"])
    pcm = script_to_pcm16(script, 1.0, 16000)
    assert len(pcm) == 32000  # 1 s * 16000 Hz * 2 bytes
    # Non-silent (sine tones)
    assert pcm != b"\x00" * 32000

