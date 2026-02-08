import numpy as np

from app.api.stt.audio_processor import AudioProcessor
from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.api.stt_v2.sentence_attributor import SentenceSpeakerAttributor
from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.domain.stt_v2.contracts import (
    DiarFrame,
    TimeRangeMs,
    TimeRangeSamples,
    UiSentence,
    UiSentenceSegment,
)
from app.domain.voice.embeddings import ECAPA_EMBEDDING_DIM


def test_attributor_thresholds_overlap():
    # Scenario: overlap coverage above threshold should label sentence as OVERLAP.
    store = SpeakerTimelineStore(sample_rate=16000, min_turn_ms=0, switch_confirm_ms=0, cooldown_ms=0, switch_margin=0.0, max_minutes=1)
    stream_id = "s1"
    store.apply_frames(
        stream_id,
        [
            DiarFrame(TimeRangeSamples(0, 800, 16000), "OVERLAP", 0.9),
            DiarFrame(TimeRangeSamples(800, 1000, 16000), "spk0", 0.9),
        ],
    )
    attributor = SentenceSpeakerAttributor(store, sample_rate=16000, overlap_sentence_th=0.2)
    sentence = UiSentence(id="sent_1", range_ms=TimeRangeMs(start_ms=0, end_ms=62), text="hi", is_final=True)
    ss = attributor.attribute(stream_id, sentence)
    assert ss.label == "OVERLAP"


def _unit_vector(index: int) -> list[float]:
    vec = [0.0] * ECAPA_EMBEDDING_DIM
    vec[index] = 1.0
    return vec


def _make_segments():
    return [
        UiSentenceSegment(
            range_ms=TimeRangeMs(start_ms=0, end_ms=800),
            text="hello",
            stt_conf=0.9,
            is_final=True,
        ),
        UiSentenceSegment(
            range_ms=TimeRangeMs(start_ms=800, end_ms=1600),
            text="there",
            stt_conf=0.9,
            is_final=True,
        ),
    ]


def _ring_with_two_halves(sample_rate: int, stream_id: str) -> AudioRingBuffer:
    ring = AudioRingBuffer(sample_rate=sample_rate, max_seconds=60)
    half_samples = int(sample_rate * 0.8)
    left = np.zeros(half_samples, dtype=np.int16)
    right = (np.ones(half_samples) * 1000).astype(np.int16)
    signal = np.concatenate([left, right])
    ring.write(
        stream_id,
        TimeRangeSamples(start=0, end=len(signal), sr=sample_rate),
        signal.tobytes(),
    )
    return ring


def test_attributor_splits_on_speaker_change_when_embeddings_differ():
    # Scenario: boundary + dissimilar embeddings -> split into two speaker sentences.
    sample_rate = 16000
    store = SpeakerTimelineStore(
        sample_rate=sample_rate,
        min_turn_ms=0,
        switch_confirm_ms=0,
        cooldown_ms=0,
        switch_margin=0.0,
        max_minutes=1,
    )
    stream_id = "s1"
    store.apply_frames(
        stream_id,
        [
            DiarFrame(TimeRangeSamples(0, 12800, sample_rate), "spk0", 0.9),
            DiarFrame(TimeRangeSamples(12800, 25600, sample_rate), "spk1", 0.9),
        ],
    )
    attributor = SentenceSpeakerAttributor(store, sample_rate=sample_rate)
    sentence = UiSentence(
        id="sent_1",
        range_ms=TimeRangeMs(start_ms=0, end_ms=1600),
        text="hello there",
        is_final=True,
        segments=_make_segments(),
    )
    ring = _ring_with_two_halves(sample_rate, stream_id)

    def _provider(pcm_bytes: bytes) -> list[float]:
        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        return _unit_vector(0) if pcm.mean() <= 0 else _unit_vector(1)

    results = attributor.attribute_with_speaker_change(
        stream_id,
        sentence,
        ring,
        AudioProcessor(sample_rate_hz=sample_rate),
        similarity_th=0.5,
        embedding_provider=_provider,
    )
    assert len(results) == 2
    assert results[0].label == "spk0"
    assert results[1].label == "spk1"


def test_attributor_no_split_when_embeddings_similar():
    # Scenario: boundary + similar embeddings -> keep single sentence.
    sample_rate = 16000
    store = SpeakerTimelineStore(
        sample_rate=sample_rate,
        min_turn_ms=0,
        switch_confirm_ms=0,
        cooldown_ms=0,
        switch_margin=0.0,
        max_minutes=1,
    )
    stream_id = "s1"
    store.apply_frames(
        stream_id,
        [
            DiarFrame(TimeRangeSamples(0, 12800, sample_rate), "spk0", 0.9),
            DiarFrame(TimeRangeSamples(12800, 25600, sample_rate), "spk1", 0.9),
        ],
    )
    attributor = SentenceSpeakerAttributor(store, sample_rate=sample_rate)
    sentence = UiSentence(
        id="sent_1",
        range_ms=TimeRangeMs(start_ms=0, end_ms=1600),
        text="hello there",
        is_final=True,
        segments=_make_segments(),
    )
    ring = _ring_with_two_halves(sample_rate, stream_id)

    results = attributor.attribute_with_speaker_change(
        stream_id,
        sentence,
        ring,
        AudioProcessor(sample_rate_hz=sample_rate),
        similarity_th=0.5,
        embedding_provider=lambda _pcm: _unit_vector(0),
    )
    assert len(results) == 1
