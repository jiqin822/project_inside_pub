"""Unit tests for NeMo Sortformer diarization (nemo_sortformer_diarizer)."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.domain.stt.diarization_script import (
    make_script_alternating,
    script_to_nemo_raw,
    script_to_pcm16,
)
from app.domain.stt.nemo_sortformer_diarizer import (
    DiarSegment,
    _parse_diarize_result,
    create_streaming_diarizer,
    diarize_pcm16,
    get_chunk_bytes,
    get_frame_bytes,
    nemo_diarization_available,
)


# --- DiarSegment ---


def test_diar_segment_dataclass() -> None:
    seg = DiarSegment(start_s=0.0, end_s=1.5, speaker_id="spk_0")
    assert seg.start_s == 0.0
    assert seg.end_s == 1.5
    assert seg.speaker_id == "spk_0"


# --- _parse_diarize_result ---


def test_parse_diarize_result_empty_raw() -> None:
    assert _parse_diarize_result([], 10.0, None) == []
    assert _parse_diarize_result(None, 10.0, None) == []
    assert _parse_diarize_result("not a list", 10.0, None) == []


def test_parse_diarize_result_list_of_tuples() -> None:
    raw = [(0.0, 1.0, 0), (1.0, 2.5, 1)]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 2
    assert out[0] == DiarSegment(0.0, 1.0, "spk_0")
    assert out[1] == DiarSegment(1.0, 2.5, "spk_1")


def test_parse_diarize_result_list_of_lists() -> None:
    raw = [[0.0, 1.0, 0], [1.0, 2.0, 1]]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 2
    assert out[0] == DiarSegment(0.0, 1.0, "spk_0")
    assert out[1] == DiarSegment(1.0, 2.0, "spk_1")


def test_parse_diarize_result_per_file_nested() -> None:
    """Single file: NeMo may return [[(0, 1, 0), (1, 2, 1)]]."""
    raw = [[(0.0, 1.0, 0), (1.0, 2.0, 1)]]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 2
    assert out[0] == DiarSegment(0.0, 1.0, "spk_0")
    assert out[1] == DiarSegment(1.0, 2.0, "spk_1")


def test_parse_diarize_result_dict_items() -> None:
    raw = [
        {"start": 0.0, "end": 1.0, "speaker": 0},
        {"begin": 1.0, "end": 2.0, "speaker_index": 1},
    ]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 2
    assert out[0] == DiarSegment(0.0, 1.0, "spk_0")
    assert out[1] == DiarSegment(1.0, 2.0, "spk_1")


def test_parse_diarize_result_clamps_to_duration() -> None:
    raw = [(0.0, 100.0, 0)]  # end beyond duration_s
    out = _parse_diarize_result(raw, 5.0, None)
    assert len(out) == 1
    assert out[0].start_s == 0.0
    assert out[0].end_s == 5.0


def test_parse_diarize_result_clamps_negative_start() -> None:
    raw = [(-1.0, 2.0, 0)]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 1
    assert out[0].start_s == 0.0
    assert out[0].end_s == 2.0


def test_parse_diarize_result_clamps_speaker_index() -> None:
    raw = [(0.0, 1.0, 99)]  # 4spk model: 0..3
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 1
    assert out[0].speaker_id == "spk_3"


def test_parse_diarize_result_max_speakers_filter() -> None:
    raw = [(0.0, 1.0, 0), (1.0, 2.0, 1), (2.0, 3.0, 2)]
    out = _parse_diarize_result(raw, 10.0, max_speakers=2)
    assert len(out) == 2
    assert out[0].speaker_id == "spk_0"
    assert out[1].speaker_id == "spk_1"


def test_parse_diarize_result_skips_invalid_item() -> None:
    raw = [(0.0, 1.0, 0), "invalid", (1.0, 2.0, 1)]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 2
    assert out[0] == DiarSegment(0.0, 1.0, "spk_0")
    assert out[1] == DiarSegment(1.0, 2.0, "spk_1")


def test_parse_diarize_result_skips_start_ge_end_after_clamp() -> None:
    raw = [(2.0, 2.0, 0), (3.0, 2.0, 0)]
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 0


def test_parse_diarize_result_skips_dict_missing_keys() -> None:
    raw = [{"start": 0.0}]  # missing end, speaker
    out = _parse_diarize_result(raw, 10.0, None)
    assert len(out) == 0


# --- nemo_diarization_available ---


def test_nemo_diarization_available_returns_tuple() -> None:
    ok, err = nemo_diarization_available()
    assert isinstance(ok, bool)
    assert err is None or isinstance(err, str)


def test_nemo_diarization_available_false_when_load_error_set() -> None:
    with patch("app.domain.stt.nemo_sortformer_diarizer._LOAD_ERROR", "test error"):
        ok, err = nemo_diarization_available()
        assert ok is False
        assert err == "test error"


# --- diarize_pcm16 ---


def test_diarize_pcm16_empty_audio_returns_empty() -> None:
    assert diarize_pcm16(b"", 16000) == []


def test_diarize_pcm16_wrong_sample_rate_returns_empty() -> None:
    # 32000 bytes = 1 s at 16 kHz 16-bit
    pcm = b"\x00" * 32000
    assert diarize_pcm16(pcm, 8000) == []
    assert diarize_pcm16(pcm, 44100) == []


def test_diarize_pcm16_too_short_audio_returns_empty() -> None:
    # Less than 1 s: 32000 bytes minimum
    pcm = b"\x00" * 31999
    assert diarize_pcm16(pcm, 16000) == []


def test_diarize_pcm16_returns_empty_when_nemo_unavailable() -> None:
    """When NeMo is not installed (or _LOAD_ERROR set), diarize_pcm16 returns [] after checks."""
    pcm = b"\x00" * 32000  # 1 s at 16 kHz 16-bit
    result = diarize_pcm16(pcm, 16000)
    # Either NeMo is unavailable (returns []) or we'd get segments; we only assert no crash
    assert isinstance(result, list)
    assert all(isinstance(s, DiarSegment) for s in result)


def test_diarize_pcm16_with_mocked_model_returns_parsed_segments() -> None:
    """With NeMo "available" and a mock model returning raw segments from script, we get DiarSegment list."""
    script = make_script_alternating(1.0, 0.5, ["spk_0", "spk_1"])
    mock_raw = script_to_nemo_raw(script)
    expected = [DiarSegment(s[0], s[1], s[2]) for s in script]
    pcm = script_to_pcm16(script, 1.0, 16000)
    mock_model = MagicMock()
    mock_model.diarize.return_value = mock_raw

    with patch(
        "app.domain.stt.nemo_sortformer_diarizer.nemo_diarization_available",
        return_value=(True, None),
    ), patch(
        "app.domain.stt.nemo_sortformer_diarizer._ensure_model_loaded",
        return_value=mock_model,
    ):
        result = diarize_pcm16(pcm, 16000, timeout_s=5.0)
    assert len(result) == len(expected)
    assert result == expected
    mock_model.diarize.assert_called_once()
    call_kw = mock_model.diarize.call_args[1]
    assert call_kw.get("batch_size") == 1
    # diarize_pcm16 writes to tempfile, so audio is a list of file paths, not sample_rate kwarg
    assert "audio" in call_kw
    assert isinstance(call_kw["audio"], list)
    assert len(call_kw["audio"]) == 1


def test_diarize_pcm16_with_mocked_model_nested_return() -> None:
    """Mock returns nested per-file list from script; parser unwraps correctly."""
    script = make_script_alternating(1.0, 0.5, ["spk_0", "spk_1"])
    mock_raw = [script_to_nemo_raw(script)]
    expected = [DiarSegment(s[0], s[1], s[2]) for s in script]
    pcm = script_to_pcm16(script, 1.0, 16000)
    mock_model = MagicMock()
    mock_model.diarize.return_value = mock_raw

    with patch(
        "app.domain.stt.nemo_sortformer_diarizer.nemo_diarization_available",
        return_value=(True, None),
    ), patch(
        "app.domain.stt.nemo_sortformer_diarizer._ensure_model_loaded",
        return_value=mock_model,
    ):
        result = diarize_pcm16(pcm, 16000, timeout_s=5.0)
    assert len(result) == len(expected)
    assert result == expected
    mock_model.diarize.assert_called_once()
    call_kw = mock_model.diarize.call_args[1]
    # diarize_pcm16 writes to tempfile, so audio is a list of file paths
    assert "audio" in call_kw
    assert isinstance(call_kw["audio"], list)
    assert len(call_kw["audio"]) == 1


def test_diarize_pcm16_synthetic_audio_returns_list() -> None:
    """script_to_pcm16 + diarize_pcm16: high-level smoke test (no strict segment equality)."""
    script = make_script_alternating(2.0, 0.5, ["spk_0", "spk_1"])
    pcm = script_to_pcm16(script, 2.0, 16000)
    assert len(pcm) >= 32000  # at least 1 s at 16 kHz 16-bit
    result = diarize_pcm16(pcm, 16000)
    assert isinstance(result, list)
    assert all(isinstance(s, DiarSegment) for s in result)


# --- NeMo helper functions: get_frame_bytes, get_chunk_bytes ---


def test_get_frame_bytes() -> None:
    """get_frame_bytes returns expected size: 16kHz * 0.08s * 2 bytes."""
    frame_bytes = get_frame_bytes()
    expected = int(16000 * 0.08 * 2)  # 2560 bytes
    assert frame_bytes == expected
    assert frame_bytes > 0


def test_get_chunk_bytes() -> None:
    """get_chunk_bytes returns chunk_len * frame_bytes."""
    frame_bytes = get_frame_bytes()
    chunk_bytes = get_chunk_bytes()
    # chunk_len = 6 frames (from _NEMO_STREAMING_CHUNK_LEN)
    expected = frame_bytes * 6
    assert chunk_bytes == expected
    assert chunk_bytes > frame_bytes


# --- Streaming diarizer: step_chunk and step ---


def test_streaming_diarizer_step_chunk_unavailable() -> None:
    """When NeMo unavailable, create_streaming_diarizer returns None."""
    ok, _ = nemo_diarization_available()
    if not ok:
        diarizer = create_streaming_diarizer()
        assert diarizer is None


def test_streaming_diarizer_step_chunk_available() -> None:
    """Test step_chunk with full chunk input (light integration)."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    chunk_bytes = get_chunk_bytes()
    # Create a full chunk of zeros (silence)
    pcm_chunk = b"\x00" * chunk_bytes

    # Reset state before test
    diarizer.reset_state()

    # Process chunk
    frame_probs = diarizer.step_chunk(pcm_chunk)

    # Should return one frame probability array per frame in chunk (6 frames)
    assert isinstance(frame_probs, list)
    assert len(frame_probs) == 6  # chunk_len = 6
    for frame_prob in frame_probs:
        assert isinstance(frame_prob, np.ndarray)
        # Shape should be (max_num_speakers,) - typically 4 for 4spk model
        assert len(frame_prob.shape) == 1
        assert frame_prob.shape[0] >= 1


def test_streaming_diarizer_step_chunk_wrong_size() -> None:
    """step_chunk raises ValueError if input size doesn't match chunk_bytes."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    chunk_bytes = get_chunk_bytes()
    wrong_size = chunk_bytes - 1
    pcm_chunk = b"\x00" * wrong_size

    with pytest.raises(ValueError, match="must equal chunk_bytes"):
        diarizer.step_chunk(pcm_chunk)


def test_streaming_diarizer_step_full_chunk() -> None:
    """step() delegates to step_chunk() when input equals chunk_bytes."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    chunk_bytes = get_chunk_bytes()
    pcm_chunk = b"\x00" * chunk_bytes

    diarizer.reset_state()
    frame_probs = diarizer.step(pcm_chunk)

    # Should return 6 frames (chunk_len)
    assert isinstance(frame_probs, list)
    assert len(frame_probs) == 6


def test_streaming_diarizer_step_multi_frame() -> None:
    """step() processes multi-frame input frame-by-frame."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    frame_bytes = get_frame_bytes()
    # Process 2 frames
    pcm_2frames = b"\x00" * (frame_bytes * 2)

    diarizer.reset_state()
    frame_probs = diarizer.step(pcm_2frames)

    # Should return 2 frame probability arrays
    assert isinstance(frame_probs, list)
    assert len(frame_probs) == 2
    for frame_prob in frame_probs:
        assert isinstance(frame_prob, np.ndarray)
        assert len(frame_prob.shape) == 1


def test_streaming_diarizer_step_not_multiple_of_frame() -> None:
    """step() raises ValueError if input is not a multiple of frame_bytes."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    frame_bytes = get_frame_bytes()
    wrong_size = frame_bytes * 2 + 1  # Not a multiple
    pcm_chunk = b"\x00" * wrong_size

    with pytest.raises(ValueError, match="must be a multiple of frame_bytes"):
        diarizer.step(pcm_chunk)


def test_streaming_diarizer_step_too_short() -> None:
    """step() returns empty list if input is shorter than frame_bytes."""
    if not nemo_diarization_available()[0]:
        pytest.skip("NeMo import not available")
    diarizer = create_streaming_diarizer()
    if diarizer is None:
        pytest.skip("NeMo available but create_streaming_diarizer() failed (model may not be loaded/downloaded)")

    frame_bytes = get_frame_bytes()
    too_short = frame_bytes - 1
    pcm_chunk = b"\x00" * too_short

    result = diarizer.step(pcm_chunk)
    assert result == []
