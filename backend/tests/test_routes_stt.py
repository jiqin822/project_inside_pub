"""Unit tests for app.api.stt helpers (constants, SpeakerMatcher, SegmentBuilder, MessageBuilder, etc.)."""
from __future__ import annotations

import base64
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.api.stt.constants import (
    LABEL_ANON_PREFIX,
    LABEL_UNKNOWN_PREFIX,
    MSG_STT_ESCALATION,
    MSG_STT_SPEAKER_RESOLVED,
    MSG_STT_TRANSCRIPT,
    SESSION_END_SLEEP_BEFORE_CENTROID_S,
    SPEAKER_SOURCE_NEMO,
    SPEAKER_SOURCE_NONE,
)
from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt.speaker_matcher import SpeakerMatcher
from app.api.stt.segment_builder import SegmentBuilder, SttSegment
from app.api.stt.message_builder import MessageBuilder
from app.api.stt.audio_processor import AudioProcessor
from app.api.stt.stt_session_service import SttSessionService
from app.api.stt.stt_stream_handler import SttStreamHandler
from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt.speaker_matching import AudioRingBuffer
from app.domain.stt.speaker_timeline_attribution import OVERLAP_LABEL, UNCERTAIN_LABEL
from app.domain.voice.embeddings import ECAPA_EMBEDDING_DIM

# Service instances for tests
_google_stt_client = GoogleSttClient()
_speaker_matcher = SpeakerMatcher()
_segment_builder = SegmentBuilder()
_message_builder = MessageBuilder()
_audio_processor = AudioProcessor()
_stt_session_service = SttSessionService(_google_stt_client)
_stt_stream_handler = SttStreamHandler(
    _segment_builder, _audio_processor, _message_builder, MagicMock()
)


# ---------------------------------------------------------------------------
# Tier 1: Pure / sync (no or minimal mocks)
# ---------------------------------------------------------------------------

def test_is_placeholder_recognizer_empty_returns_true() -> None:
    assert _google_stt_client.is_placeholder_recognizer("") is True


def test_is_placeholder_recognizer_your_project_returns_true() -> None:
    assert _google_stt_client.is_placeholder_recognizer("projects/your-project/locations/eu/recognizers/_") is True


def test_is_placeholder_recognizer_default_returns_true() -> None:
    assert _google_stt_client.is_placeholder_recognizer("recognizers/default") is True


def test_is_placeholder_recognizer_valid_returns_false() -> None:
    assert _google_stt_client.is_placeholder_recognizer("projects/my-real-project/locations/eu/recognizers/my-rec") is False


def test_duration_to_seconds_none_returns_zero() -> None:
    assert _segment_builder._duration_to_seconds(None) == 0.0


def test_duration_to_seconds_seconds_and_nanos() -> None:
    d = SimpleNamespace(seconds=1, nanos=500_000_000)
    assert _segment_builder._duration_to_seconds(d) == 1.5


def test_duration_to_seconds_seconds_only() -> None:
    d = SimpleNamespace(seconds=3, nanos=0)
    assert _segment_builder._duration_to_seconds(d) == 3.0


def test_duration_to_seconds_missing_attrs_returns_zero() -> None:
    d = object()
    assert _segment_builder._duration_to_seconds(d) == 0.0


def test_resolve_speaker_tag_empty_returns_none() -> None:
    assert _segment_builder._resolve_speaker_tag([]) is None


def test_resolve_speaker_tag_no_speaker_tag_returns_none() -> None:
    w = SimpleNamespace()
    assert _segment_builder._resolve_speaker_tag([w, w]) is None


def test_resolve_speaker_tag_single_tag_returns_that_tag() -> None:
    w = SimpleNamespace(speaker_tag=1)
    assert _segment_builder._resolve_speaker_tag([w, w]) == 1


def test_resolve_speaker_tag_majority_tag_wins() -> None:
    w1 = SimpleNamespace(speaker_tag=1)
    w2 = SimpleNamespace(speaker_tag=2)
    assert _segment_builder._resolve_speaker_tag([w1, w2, w1, w1]) == 1


def test_group_words_by_speaker_empty_returns_empty() -> None:
    assert _segment_builder._group_words_by_speaker([]) == []


def test_group_words_by_speaker_same_tag_one_group() -> None:
    w = SimpleNamespace(speaker_tag=1)
    groups = _segment_builder._group_words_by_speaker([w, w, w])
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_group_words_by_speaker_tag_change_new_group() -> None:
    w1 = SimpleNamespace(speaker_tag=1)
    w2 = SimpleNamespace(speaker_tag=2)
    groups = _segment_builder._group_words_by_speaker([w1, w1, w2, w2])
    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 2


def test_group_words_by_speaker_two_groups_then_one() -> None:
    w1 = SimpleNamespace(speaker_tag=1)
    w2 = SimpleNamespace(speaker_tag=2)
    groups = _segment_builder._group_words_by_speaker([w1, w2, w1])
    assert len(groups) == 3
    assert len(groups[0]) == 1
    assert len(groups[1]) == 1
    assert len(groups[2]) == 1


@patch("app.api.stt.message_builder.speaker_display_name")
def test_build_transcript_payload_shape_and_type(mock_display: MagicMock) -> None:
    mock_display.return_value = "Display"
    payload = _message_builder.build_transcript_payload(
        "sess1",
        seg_text="Hello",
        speaker_label="user1",
        seg_tag=0,
        is_final=True,
        segment_id=1,
    )
    assert payload["type"] == MSG_STT_TRANSCRIPT
    assert payload["text"] == "Hello"
    assert payload["speaker_label"] == "Display"
    assert payload["is_final"] is True
    assert payload["segment_id"] == 1
    assert payload["bubble_id"] == "1"
    mock_display.assert_called_once_with(
        "sess1", "user1", nemo_speaker_id=None
    )


@patch("app.api.stt.message_builder.speaker_display_name")
def test_build_transcript_payload_overlap_label_unchanged(mock_display: MagicMock) -> None:
    payload = _message_builder.build_transcript_payload(
        "sess1",
        seg_text="x",
        speaker_label=OVERLAP_LABEL,
        seg_tag=None,
        is_final=True,
        segment_id=0,
    )
    assert payload["speaker_label"] == OVERLAP_LABEL
    mock_display.assert_not_called()


@patch("app.api.stt.message_builder.speaker_display_name")
def test_build_transcript_payload_uncertain_label_unchanged(mock_display: MagicMock) -> None:
    payload = _message_builder.build_transcript_payload(
        "sess1",
        seg_text="x",
        speaker_label=UNCERTAIN_LABEL,
        seg_tag=None,
        is_final=True,
        segment_id=0,
    )
    assert payload["speaker_label"] == UNCERTAIN_LABEL
    mock_display.assert_not_called()


@patch("app.api.stt.message_builder.speaker_display_name")
def test_build_speaker_resolved_payload_shape_and_confidence(mock_display: MagicMock) -> None:
    mock_display.return_value = "Resolved"
    payload = _message_builder.build_speaker_resolved_payload(
        "sess1",
        segment_id=2,
        speaker_label="user1",
        speaker_source="voice_id",
        confidence=0.8765,
    )
    assert payload["type"] == MSG_STT_SPEAKER_RESOLVED
    assert payload["segment_id"] == 2
    assert payload["bubble_id"] == "2"
    assert payload["speaker_label"] == "Resolved"
    assert payload["confidence"] == 0.876  # round(0.8765, 3) -> 0.876 (round half to even)
    assert payload["speaker_source"] == "voice_id"


@patch("app.api.stt.message_builder.speaker_display_name")
def test_build_speaker_resolved_payload_overlap_unchanged(mock_display: MagicMock) -> None:
    payload = _message_builder.build_speaker_resolved_payload(
        "sess1",
        segment_id=0,
        speaker_label=OVERLAP_LABEL,
        speaker_source="voice_id",
    )
    assert payload["speaker_label"] == OVERLAP_LABEL
    mock_display.assert_not_called()


def test_samples_to_wav_base64_none_returns_none() -> None:
    assert _audio_processor.samples_to_wav_base64(None) is None


def test_samples_to_wav_base64_empty_array_returns_none() -> None:
    assert _audio_processor.samples_to_wav_base64(np.array([], dtype=np.int16)) is None


def test_samples_to_wav_base64_valid_returns_decodeable_wav() -> None:
    samples = np.array([0, 100, -100], dtype=np.int16)
    out = _audio_processor.samples_to_wav_base64(samples)
    assert out is not None
    raw = base64.b64decode(out)
    buf = io.BytesIO(raw)
    with wave.open(buf, "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        frames = wav.readframes(4)
        assert len(frames) == 6  # 3 samples * 2 bytes


# ---------------------------------------------------------------------------
# Tier 2: Sync with SttSessionContext (real dataclass)
# ---------------------------------------------------------------------------

def minimal_ctx(
    session_id: str = "test-session",
    user_id: str = "user1",
    language_code: str = "en-US",
) -> SttSessionContext:
    return SttSessionContext(
        session_id=session_id,
        user_id=user_id,
        candidate_user_ids=[],
        language_code=language_code,
        min_speaker_count=1,
        max_speaker_count=2,
    )


def test_get_or_assign_nemo_tag_first_call_returns_one_and_stores() -> None:
    ctx = minimal_ctx()
    tag = _speaker_matcher.get_or_assign_nemo_tag(ctx, "s1")
    assert tag == 1
    assert ctx.nemo_speaker_id_to_tag["s1"] == 1
    assert ctx.nemo_next_tag == 2


def test_get_or_assign_nemo_tag_second_call_same_speaker_returns_same() -> None:
    ctx = minimal_ctx()
    t1 = _speaker_matcher.get_or_assign_nemo_tag(ctx, "s1")
    t2 = _speaker_matcher.get_or_assign_nemo_tag(ctx, "s1")
    assert t1 == t2 == 1


def test_get_or_assign_nemo_tag_new_speaker_returns_next() -> None:
    ctx = minimal_ctx()
    _speaker_matcher.get_or_assign_nemo_tag(ctx, "s1")
    tag2 = _speaker_matcher.get_or_assign_nemo_tag(ctx, "s2")
    assert tag2 == 2
    assert ctx.nemo_speaker_id_to_tag["s2"] == 2


def test_get_or_assign_nemo_label_first_call_returns_anon_1() -> None:
    ctx = minimal_ctx()
    label = _speaker_matcher.get_or_assign_nemo_label(ctx, "spk_0")
    assert label == f"{LABEL_ANON_PREFIX}1"
    assert ctx.nemo_speaker_id_to_label["spk_0"] == label
    assert ctx.nemo_anon_counter == 1


def test_get_or_assign_nemo_label_second_call_same_id_returns_same() -> None:
    ctx = minimal_ctx()
    l1 = _speaker_matcher.get_or_assign_nemo_label(ctx, "spk_0")
    l2 = _speaker_matcher.get_or_assign_nemo_label(ctx, "spk_0")
    assert l1 == l2 == f"{LABEL_ANON_PREFIX}1"


def test_get_or_assign_nemo_label_new_id_returns_anon_2() -> None:
    ctx = minimal_ctx()
    _speaker_matcher.get_or_assign_nemo_label(ctx, "spk_0")
    label2 = _speaker_matcher.get_or_assign_nemo_label(ctx, "spk_1")
    assert label2 == f"{LABEL_ANON_PREFIX}2"


def test_session_context_has_nemo_history_and_pending_segments() -> None:
    """Session context has rolling NeMo history and pending_final_segments for bounded deferral."""
    ctx = minimal_ctx()
    assert hasattr(ctx, "nemo_segments_history")
    assert hasattr(ctx, "pending_final_segments")
    assert hasattr(ctx, "nemo_history_lock")
    assert hasattr(ctx, "nemo_updated_event")
    assert isinstance(ctx.nemo_segments_history, list)
    assert isinstance(ctx.pending_final_segments, list)
    # Drain iteration (as in session end) does not crash
    for item in ctx.pending_final_segments:
        payload = item.get("payload") if isinstance(item, dict) else None
        assert payload is None  # empty list


def test_get_stream_stt_language_config_auto_returns_chirp_no_diarization() -> None:
    ctx = minimal_ctx(language_code="auto")
    codes, model_id, enable_diar = _google_stt_client.get_language_config(ctx)
    assert codes == ["auto"]
    assert model_id == "chirp_3"
    assert enable_diar is False


def test_get_stream_stt_language_config_en_us_returns_latest_short_diarization() -> None:
    ctx = minimal_ctx(language_code="en-US")
    codes, model_id, enable_diar = _google_stt_client.get_language_config(ctx)
    assert codes == ["en-US"]
    assert model_id == "latest_short"
    assert enable_diar is True


def test_get_stream_stt_language_config_empty_language_returns_en_us() -> None:
    ctx = minimal_ctx(language_code="")
    codes, model_id, enable_diar = _google_stt_client.get_language_config(ctx)
    assert codes == ["en-US"]
    assert model_id == "latest_short"
    assert enable_diar is True


def test_canonical_unknown_union_find_returns_root() -> None:
    ctx = minimal_ctx()
    ctx.unknown_label_parent["A"] = "B"
    ctx.unknown_label_parent["B"] = "B"
    assert _speaker_matcher.canonical_unknown(ctx, "A") == "B"
    assert _speaker_matcher.canonical_unknown(ctx, "B") == "B"


def test_canonical_unknown_self_loop_returns_self() -> None:
    ctx = minimal_ctx()
    ctx.unknown_label_parent["C"] = "C"
    assert _speaker_matcher.canonical_unknown(ctx, "C") == "C"


@patch("app.api.stt.speaker_matcher.settings")
def test_match_known_user_only_no_embedding_returns_none(mock_settings: MagicMock) -> None:
    mock_settings.stt_speaker_match_threshold = 0.7
    ctx = minimal_ctx()
    ctx.voice_embeddings["u1"] = [0.1] * ECAPA_EMBEDDING_DIM
    assert _speaker_matcher.match_known_user_only(ctx, None) is None
    assert _speaker_matcher.match_known_user_only(ctx, []) is None


@patch("app.api.stt.speaker_matcher.settings")
def test_match_known_user_only_wrong_dim_returns_none(mock_settings: MagicMock) -> None:
    mock_settings.stt_speaker_match_threshold = 0.7
    ctx = minimal_ctx()
    ctx.voice_embeddings["u1"] = [0.1] * ECAPA_EMBEDDING_DIM
    assert _speaker_matcher.match_known_user_only(ctx, [0.0] * 10) is None


@patch("app.api.stt.speaker_matcher.settings")
@patch("app.api.stt.speaker_matcher.cosine_similarity")
def test_match_known_user_only_above_threshold_returns_user(mock_cosine: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.stt_speaker_match_threshold = 0.7
    mock_cosine.return_value = 0.9
    ctx = minimal_ctx()
    ctx.voice_embeddings["user_a"] = [0.1] * ECAPA_EMBEDDING_DIM
    emb = [0.2] * ECAPA_EMBEDDING_DIM
    assert _speaker_matcher.match_known_user_only(ctx, emb) == "user_a"


@patch("app.api.stt.speaker_matcher.settings")
@patch("app.api.stt.speaker_matcher.cosine_similarity")
def test_match_known_user_only_below_threshold_returns_none(mock_cosine: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.stt_speaker_match_threshold = 0.7
    mock_cosine.return_value = 0.5
    ctx = minimal_ctx()
    ctx.voice_embeddings["user_a"] = [0.1] * ECAPA_EMBEDDING_DIM
    emb = [0.2] * ECAPA_EMBEDDING_DIM
    assert _speaker_matcher.match_known_user_only(ctx, emb) is None


def test_match_speaker_label_no_tag_no_embeddings_creates_unknown_1() -> None:
    ctx = minimal_ctx()
    label = _speaker_matcher.match_speaker_label_no_tag(ctx, None)
    assert label == f"{LABEL_UNKNOWN_PREFIX}1"
    assert ctx.unknown_counter == 1
    assert ctx.unknown_label_parent[label] == label


def test_match_speaker_label_with_tag_cache_hit_returns_cached() -> None:
    ctx = minimal_ctx()
    ctx.speaker_tag_to_label[0] = "user_a"
    ctx.voice_embeddings["user_a"] = [0.1] * ECAPA_EMBEDDING_DIM
    label = _speaker_matcher.match_speaker_label_with_tag(0, ctx, None)
    assert label == "user_a"


def test_match_speaker_label_none_delegates_to_no_tag() -> None:
    ctx = minimal_ctx()
    label = _speaker_matcher.match_speaker_label(None, ctx, None)
    assert label.startswith(LABEL_UNKNOWN_PREFIX)


def test_match_speaker_label_with_tag_delegates_to_with_tag() -> None:
    ctx = minimal_ctx()
    ctx.speaker_tag_to_label[1] = "cached"
    ctx.voice_embeddings["cached"] = [0.1] * ECAPA_EMBEDDING_DIM
    assert _speaker_matcher.match_speaker_label(1, ctx, None) == "cached"


# ---------------------------------------------------------------------------
# Tier 3: Async helpers with mocked deps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("app.api.stt.message_builder.settings")
@patch("asyncio.get_event_loop")
async def test_send_escalation_if_allowed_sends_and_updates_ref(
    mock_loop: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.stt_escalation_cooldown_seconds = 10.0
    mock_loop.return_value.time.return_value = 1000.0
    websocket = AsyncMock()
    ref: list[float] = [0.0]
    escalation = SimpleNamespace(severity="high", reason="test", message="msg")
    await _message_builder.send_escalation_if_allowed(escalation, websocket, ref)
    assert ref[0] == 1000.0
    websocket.send_json.assert_called_once()
    call_arg = websocket.send_json.call_args[0][0]
    assert call_arg["type"] == MSG_STT_ESCALATION
    assert call_arg["severity"] == "high"
    assert call_arg["reason"] == "test"
    assert call_arg["message"] == "msg"


@pytest.mark.asyncio
@patch("app.api.stt.message_builder.settings")
@patch("asyncio.get_event_loop")
async def test_send_escalation_if_allowed_cooldown_exceeded_does_not_send(
    mock_loop: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.stt_escalation_cooldown_seconds = 10.0
    mock_loop.return_value.time.return_value = 1000.0
    websocket = AsyncMock()
    ref: list[float] = [999.0]  # last sent at 999, now 1000, cooldown 10 -> 1000 - 999 < 10
    escalation = SimpleNamespace(severity="high", reason="x", message="y")
    await _message_builder.send_escalation_if_allowed(escalation, websocket, ref)
    websocket.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_final_segment_speaker_and_source_nemo_off_returns_unknown_none() -> None:
    ctx = minimal_ctx()
    d = MagicMock()
    d.ctx = ctx
    d.enable_nemo_fallback = False
    label, source, nemo_id, tag = await _audio_processor.resolve_final_segment_speaker_and_source(
        d, 1.0, 2.0, None, [], _speaker_matcher
    )
    assert label == "UNKNOWN"
    assert source == SPEAKER_SOURCE_NONE
    assert nemo_id is None
    assert tag is None


@pytest.mark.asyncio
@patch("app.api.stt.audio_processor.best_overlap_speaker_id")
async def test_resolve_final_segment_speaker_and_source_nemo_overlap_returns_label(
    mock_best: MagicMock,
) -> None:
    mock_best.return_value = "nemo_0"
    ctx = minimal_ctx()
    d = MagicMock()
    d.ctx = ctx
    d.enable_nemo_fallback = True
    label, source, nemo_id, tag = await _audio_processor.resolve_final_segment_speaker_and_source(
        d, 1.0, 2.0, None, [MagicMock()], _speaker_matcher
    )
    assert label == f"{LABEL_ANON_PREFIX}1"
    assert source == SPEAKER_SOURCE_NEMO
    assert nemo_id == "nemo_0"
    assert tag == 1


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_query_timeline_attribution_no_timeline_returns_none() -> None:
    d = MagicMock()
    d.ctx.speaker_timeline = []
    d.ring_buffer = MagicMock(total_samples=16000)
    result = await _stt_stream_handler.query_timeline_attribution(d, 0, 1000)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_query_timeline_attribution_none_start_end_returns_none() -> None:
    d = MagicMock()
    d.ctx.speaker_timeline = [(0, 1000, "0", 0.9, "NONE")]
    d.ring_buffer = MagicMock(total_samples=16000)
    assert await _stt_stream_handler.query_timeline_attribution(d, None, 1000) is None
    assert await _stt_stream_handler.query_timeline_attribution(d, 0, None) is None


@pytest.mark.asyncio
@patch("app.api.stt.stt_stream_handler.query_speaker_timeline")
@patch("app.api.stt.stt_stream_handler.diarization_reliable_end_sample")
async def test_query_timeline_attribution_in_window_returns_tuple(
    mock_reliable: MagicMock,
    mock_query: MagicMock,
) -> None:
    mock_reliable.return_value = 16000
    mock_query.return_value = ("user_1", 0.95, False, "segment_level")
    d = MagicMock()
    d.ctx.speaker_timeline = [(0, 8000, "0", 0.9, "NONE")]
    d.ring_buffer = MagicMock(total_samples=16000)
    result = await _stt_stream_handler.query_timeline_attribution(d, 0, 8000)
    assert result is not None
    assert result[0] == "user_1"
    assert result[1] == 0.95
    assert result[2] is False
    assert result[3] == "segment_level"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_resolve_interim_speaker_label_cached_returns_label() -> None:
    ctx = minimal_ctx()
    ctx.speaker_tag_to_label[0] = "user_a"
    ctx.voice_embeddings["user_a"] = [0.1] * ECAPA_EMBEDDING_DIM
    d = MagicMock()
    d.ctx = ctx
    label = await _stt_stream_handler.resolve_interim_speaker_label(d, 0)
    assert label == "user_a"


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_resolve_interim_speaker_label_missing_creates_unknown() -> None:
    ctx = minimal_ctx()
    d = MagicMock()
    d.ctx = ctx
    label = await _stt_stream_handler.resolve_interim_speaker_label(d, None)
    assert label == f"{LABEL_UNKNOWN_PREFIX}1"
    assert ctx.unknown_counter == 1


@pytest.mark.asyncio
@patch("app.api.stt.stt_session_service.asyncio.sleep", new_callable=AsyncMock)
async def test_stream_stt_shutdown_sets_events_puts_none_gathers(mock_sleep: AsyncMock) -> None:
    stop_event = MagicMock()
    nemo_worker_stop = MagicMock()
    nemo_worker_task = MagicMock()
    sortformer_timeline_task = MagicMock()
    audio_queue = MagicMock()
    sortformer_queue = MagicMock()
    ctx = minimal_ctx()
    await _stt_session_service.shutdown(
        stop_event,
        nemo_worker_stop,
        nemo_worker_task,
        sortformer_timeline_task,
        None,  # flush_loop_task
        audio_queue,
        sortformer_queue,
        ctx,
    )
    stop_event.set.assert_called_once()
    nemo_worker_stop.set.assert_called_once()
    nemo_worker_task.cancel.assert_called_once()
    sortformer_timeline_task.cancel.assert_called_once()
    audio_queue.put.assert_called_once_with(None)
    # flush_loop_task was None so no cancel
    sortformer_queue.put.assert_called_once_with(None)
    mock_sleep.assert_called_once_with(SESSION_END_SLEEP_BEFORE_CENTROID_S)


@patch("app.api.stt.stt_session_service.asyncio.sleep", new_callable=AsyncMock)
async def test_stream_stt_shutdown_cancels_flush_loop_task(mock_sleep: AsyncMock) -> None:
    """Shutdown cancels flush_loop_task when provided (session-end cleanup)."""
    stop_event = MagicMock()
    nemo_worker_stop = MagicMock()
    nemo_worker_task = MagicMock()
    sortformer_timeline_task = MagicMock()
    flush_loop_task = AsyncMock()
    flush_loop_task.cancel = MagicMock()
    audio_queue = MagicMock()
    sortformer_queue = MagicMock()
    ctx = minimal_ctx()
    await _stt_session_service.shutdown(
        stop_event,
        nemo_worker_stop,
        nemo_worker_task,
        sortformer_timeline_task,
        flush_loop_task,
        audio_queue,
        sortformer_queue,
        ctx,
    )
    flush_loop_task.cancel.assert_called_once()


# ---------------------------------------------------------------------------
# Tier 4: Optional (more setup or integration-like)
# ---------------------------------------------------------------------------

def test_extract_segment_audio_final_with_times_returns_samples_and_bounds() -> None:
    ring = AudioRingBuffer(sample_rate=16000, max_seconds=10)
    # 4 seconds so min_window 3s fits (segment 0-1s gets expanded to 0-3s)
    ring.append(np.zeros(16000 * 4 * 2, dtype=np.int16).tobytes())
    stream_base = 0
    segment = SttSegment(
        text="hello",
        words=[],
        speaker_tag=None,
        raw_start_s=0.0,
        raw_end_s=1.0,
        from_diarization=False,
    )  # 0-1s
    samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s = _segment_builder.extract_segment_audio(
        segment, ring, stream_base, None, None, True, False
    )
    assert samples is not None
    assert start_sample is not None
    assert end_sample is not None
    assert seg_abs_start_s is not None
    assert seg_abs_end_s is not None
    assert start_sample == stream_base
    assert end_sample > start_sample
    assert seg_abs_start_s == start_sample / 16000.0
    assert seg_abs_end_s == end_sample / 16000.0


def test_extract_segment_audio_fallback_no_times_has_voice_embeddings() -> None:
    ring = AudioRingBuffer(sample_rate=16000, max_seconds=10)
    ring.append(np.zeros(16000 * 5, dtype=np.int16).tobytes())  # 5 s
    stream_base = 0
    segment = SttSegment(
        text="hello",
        words=[],
        speaker_tag=None,
        raw_start_s=None,
        raw_end_s=None,
        from_diarization=False,
    )
    samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s = _segment_builder.extract_segment_audio(
        segment, ring, stream_base, None, None, True, True
    )
    assert samples is not None
    assert start_sample is not None
    assert end_sample is not None
    assert seg_abs_start_s is not None
    assert seg_abs_end_s is not None


@pytest.mark.asyncio
@patch("app.api.stt.google_stt_client.GoogleSttClient.is_placeholder_recognizer")
async def test_validate_stream_stt_request_placeholder_recognizer_returns_none(
    mock_placeholder: MagicMock,
) -> None:
    mock_placeholder.return_value = True
    websocket = AsyncMock()
    websocket.query_params = {}
    result = await _stt_session_service.validate_stream_request(websocket, "sess1", None)
    assert result is None
    websocket.send_json.assert_called_once()
    websocket.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.stt.google_stt_client.GoogleSttClient.is_placeholder_recognizer")
async def test_validate_stream_stt_request_no_token_returns_none(mock_placeholder: MagicMock) -> None:
    mock_placeholder.return_value = False
    websocket = AsyncMock()
    websocket.query_params = {}
    result = await _stt_session_service.validate_stream_request(websocket, "sess1", None)
    assert result is None
    websocket.close.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.stt.stt_session_service.stt_registry")
@patch("app.api.stt.stt_session_service.SttSessionService.get_user_from_token")
@patch("app.api.stt.google_stt_client.GoogleSttClient.is_placeholder_recognizer")
async def test_validate_stream_stt_request_valid_token_and_session_returns_tuple(
    mock_placeholder: MagicMock,
    mock_get_user: MagicMock,
    mock_registry: MagicMock,
) -> None:
    mock_placeholder.return_value = False
    mock_get_user.return_value = "user1"
    ctx = minimal_ctx()
    mock_registry.get = AsyncMock(return_value=ctx)
    websocket = AsyncMock()
    websocket.query_params = {}
    result = await _stt_session_service.validate_stream_request(websocket, "test-session", "token123")
    assert result is not None
    assert result[0] == "user1"
    assert result[1] is ctx
