from app.api.stt_v2.audio_chunker import AudioChunker
from app.api.stt_v2.audio_ingestor import AudioIngestor
from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.api.stt_v2.coach_engine import CoachEngine
from app.api.stt_v2.pause_vad_service import PauseVADService
from app.api.stt_v2.sentence_assembler import SentenceAssembler
from app.api.stt_v2.sentence_attributor import SentenceSpeakerAttributor
from app.api.stt_v2.sentence_stitcher import SentenceStitcher
from app.api.stt_v2.session_orchestrator import SessionOrchestrator
from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.api.stt_v2.voice_id_matcher import VoiceIdMatcher
from app.domain.stt_v2.contracts import DiarFrame, DiarPatch, TimeRangeMs, TimeRangeSamples, UiSentence


class DummyDiar:
    def start(self, *_args, **_kwargs):
        return None

    def process_window(self, _window):
        return []


class DummyStt:
    def start(self, *_args, **_kwargs):
        return None

    def stop(self, *_args, **_kwargs):
        return None

    def process_audio_chunk(self, _chunk):
        return []


def test_patch_reattribute_marks_patched():
    # Scenario: patch re-attribution should mark updated sentences as patched.
    sample_rate = 16000
    ring = AudioRingBuffer(sample_rate=sample_rate, max_seconds=60)
    timeline_store = SpeakerTimelineStore(
        sample_rate=sample_rate,
        min_turn_ms=0,
        switch_confirm_ms=0,
        cooldown_ms=0,
        switch_margin=0.0,
        max_minutes=1,
    )
    orchestrator = SessionOrchestrator(
        ingestor=AudioIngestor(ring, sample_rate),
        chunker=AudioChunker(sample_rate=sample_rate),
        pause_vad=PauseVADService(sample_rate=sample_rate),
        diar_service=DummyDiar(),
        timeline_store=timeline_store,
        stt_service=DummyStt(),
        sentence_assembler=SentenceAssembler(sample_rate=sample_rate),
        attributor=SentenceSpeakerAttributor(timeline_store, sample_rate=sample_rate),
        voice_id_matcher=VoiceIdMatcher(sample_rate=sample_rate),
        stitcher=SentenceStitcher(),
        coach_engine=CoachEngine(),
    )
    stream_id = "s1"
    orchestrator.start_session(stream_id, sample_rate, ctx=None, client=None)
    state = orchestrator._state(stream_id)
    state.recent_sentences.append(
        UiSentence(id="sent_1", range_ms=TimeRangeMs(start_ms=0, end_ms=1000), text="hello", is_final=True)
    )
    patch = DiarPatch(
        range_samples=TimeRangeSamples(start=0, end=16000, sr=sample_rate),
        frames=[DiarFrame(TimeRangeSamples(0, 16000, sample_rate), "spk1", 0.9, is_patch=True)],
        version=1,
    )
    orchestrator.timeline_store.apply_patch(stream_id, patch)
    updated = orchestrator._reattribute_patch(stream_id, 0, 16000)
    assert updated
    assert updated[0].flags.get("patched") is True
