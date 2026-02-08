import numpy as np
from typing import Optional

from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.api.stt_v2.voice_id_matcher import VoiceIdMatcher
from app.api.stt.audio_processor import AudioProcessor
from app.domain.stt.session_registry import SttSessionContext
from app.domain.stt.union_find import find as uf_find
from app.domain.stt_v2.contracts import (
    OVERLAP_LABEL,
    SpeakerSentence,
    TimeRangeMs,
    TimeRangeSamples,
    UiSentence,
)
from app.domain.voice.embeddings import ECAPA_EMBEDDING_DIM


def _unit_vector(index: int) -> list[float]:
    vec = [0.0] * ECAPA_EMBEDDING_DIM
    vec[index] = 1.0
    return vec


def _make_sentence(label: str, start_ms: int = 0, end_ms: int = 1000) -> SpeakerSentence:
    return SpeakerSentence(
        ui_sentence=UiSentence(
            id="sent_1",
            range_ms=TimeRangeMs(start_ms=start_ms, end_ms=end_ms),
            text="hello",
            is_final=True,
        ),
        label=label,
        label_conf=0.9,
        coverage=0.9,
        flags={"overlap": False, "uncertain": False, "patched": False},
    )


def _setup_ring(sample_rate: int, stream_id: str, duration_ms: int = 1000) -> AudioRingBuffer:
    ring = AudioRingBuffer(sample_rate=sample_rate, max_seconds=60)
    samples = int(sample_rate * duration_ms / 1000)
    signal = (np.ones(samples) * 1000).astype(np.int16)
    ring.write(
        stream_id,
        TimeRangeSamples(start=0, end=samples, sr=sample_rate),
        signal.tobytes(),
    )
    return ring


def test_voice_id_maps_known_user():
    # Scenario: known voiceprint maps spk label to user id with voice_id flag.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0)}

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate,
        min_audio_ms=0,
        embedding_provider=lambda _pcm: _unit_vector(0),
    )
    sentence = _make_sentence("spk0")
    mapped = matcher.map_label(
        "s1", sentence, ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert mapped.label == "user_a"
    assert mapped.flags.get("voice_id") is True


def test_voice_id_switch_requires_persistence():
    # Scenario: mapping switch requires persistence across N sentences.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0), "user_b": _unit_vector(1)}

    calls = {"count": 0}

    def _provider(_pcm: bytes) -> list[float]:
        calls["count"] += 1
        return _unit_vector(0) if calls["count"] == 1 else _unit_vector(1)

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate,
        min_audio_ms=0,
        persist_sentences=2,
        persist_ms=0,
        embedding_provider=_provider,
    )
    sentence = _make_sentence("spk0")

    first = matcher.map_label(
        "s1", sentence, ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )
    second = matcher.map_label(
        "s1", sentence, ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )
    third = matcher.map_label(
        "s1", sentence, ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert first.label == "user_a"
    assert second.label == "user_a"
    assert third.label == "user_b"


def test_voice_id_passes_through_overlap():
    # Scenario: overlap/uncertain labels bypass voice ID mapping.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0)}

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate, min_audio_ms=0, embedding_provider=lambda _pcm: _unit_vector(0)
    )
    sentence = _make_sentence(OVERLAP_LABEL)
    mapped = matcher.map_label(
        "s1", sentence, ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert mapped.label == OVERLAP_LABEL
    assert mapped.flags.get("voice_id") is None


def test_voice_id_union_canonicalizes_unknown_after_expiry():
    # Scenario: after mapping, unknown label canonicalizes to user when cache expires.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0)}

    calls = {"count": 0}

    def _provider(_pcm: bytes) -> Optional[list[float]]:
        calls["count"] += 1
        if calls["count"] == 1:
            return _unit_vector(0)
        return None

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate,
        ttl_ms=0,
        min_audio_ms=0,
        embedding_provider=_provider,
    )
    first = matcher.map_label(
        "s1", _make_sentence("spk0", end_ms=1000), ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )
    second = matcher.map_label(
        "s1", _make_sentence("spk0", start_ms=1000, end_ms=2000), ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert first.label == "user_a"
    assert second.label == "user_a"
    assert second.flags.get("voice_id") is None


def test_voice_id_union_keeps_unknowns_bound_to_user():
    # Scenario: two spk labels mapped to same user share canonical root.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0)}

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate,
        min_audio_ms=0,
        embedding_provider=lambda _pcm: _unit_vector(0),
    )
    matcher.map_label(
        "s1", _make_sentence("spk0", end_ms=1000), ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )
    matcher.map_label(
        "s1", _make_sentence("spk1", start_ms=1000, end_ms=2000), ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert uf_find(ctx.unknown_label_parent, "Unknown_spk0") == "user_a"
    assert uf_find(ctx.unknown_label_parent, "Unknown_spk1") == "user_a"


def test_voice_id_union_can_be_disabled():
    # Scenario: disable union-join so unknown labels are not merged to user.
    sample_rate = 16000
    ring = _setup_ring(sample_rate, "s1")
    ctx = SttSessionContext(
        session_id="s1",
        user_id="owner",
        candidate_user_ids=[],
        language_code="en",
        min_speaker_count=1,
        max_speaker_count=2,
        disable_speaker_union_join=True,
    )
    ctx.voice_embeddings = {"user_a": _unit_vector(0)}

    matcher = VoiceIdMatcher(
        sample_rate=sample_rate,
        min_audio_ms=0,
        embedding_provider=lambda _pcm: _unit_vector(0),
    )
    matcher.map_label(
        "s1", _make_sentence("spk0", end_ms=1000), ctx, ring, AudioProcessor(sample_rate_hz=sample_rate)
    )

    assert uf_find(ctx.unknown_label_parent, "Unknown_spk0") == "Unknown_spk0"
