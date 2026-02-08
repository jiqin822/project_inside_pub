import numpy as np

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
from app.domain.stt_v2.contracts import AudioWindow, DiarFrame, DiarPatch, SttSegment, TimeRangeMs, TimeRangeSamples


class FakeDiarService:
    def start(self, stream_id, sr):
        self.sr = sr

    def process_window(self, window: AudioWindow):
        return [
            DiarFrame(
                range_samples=window.range_samples,
                label="spk0",
                conf=0.8,
                is_patch=False,
            )
        ]


class FakeSttService:
    def __init__(self):
        self.emitted = False

    def start(self, stream_id, sr, ctx=None, client=None):
        pass

    def stop(self, stream_id):
        pass

    def process_audio_chunk(self, chunk):
        if self.emitted:
            return []
        self.emitted = True
        return [
            SttSegment(
                range_ms=TimeRangeMs(start_ms=0, end_ms=1000),
                text="Hello world.",
                stt_conf=0.9,
                is_final=True,
            )
        ]


class FakeDiarPatchService:
    def __init__(self):
        self.count = 0

    def start(self, stream_id, sr):
        self.sr = sr

    def process_window(self, window: AudioWindow):
        self.count += 1
        if self.count < 2:
            return [DiarFrame(range_samples=window.range_samples, label="spk0", conf=0.8, is_patch=False)]
        patch = DiarPatch(
            range_samples=window.range_samples,
            frames=[
                DiarFrame(range_samples=window.range_samples, label="spk1", conf=0.9, is_patch=True)
            ],
            version=1,
        )
        return [patch]


def _pcm_bytes(duration_ms: int, sample_rate: int = 16000) -> bytes:
    samples = int(sample_rate * duration_ms / 1000)
    signal = (np.ones(samples) * 1000).astype(np.int16)
    return signal.tobytes()


def test_v2_pipeline_produces_sentence():
    # Scenario: end-to-end pipeline emits at least one speaker sentence.
    sample_rate = 16000
    ring = AudioRingBuffer(sample_rate=sample_rate, max_seconds=60)
    ingestor = AudioIngestor(ring_buffer=ring, sample_rate=sample_rate)
    chunker = AudioChunker(sample_rate=sample_rate)
    pause_vad = PauseVADService(sample_rate=sample_rate)
    diar = FakeDiarService()
    timeline = SpeakerTimelineStore(sample_rate=sample_rate, min_turn_ms=0, switch_confirm_ms=0, cooldown_ms=0, switch_margin=0.0, max_minutes=1)
    stt = FakeSttService()
    assembler = SentenceAssembler(sample_rate=sample_rate)
    attributor = SentenceSpeakerAttributor(timeline_store=timeline, sample_rate=sample_rate)
    voice_id_matcher = VoiceIdMatcher(sample_rate=sample_rate)
    stitcher = SentenceStitcher()
    coach = CoachEngine()
    orchestrator = SessionOrchestrator(
        ingestor=ingestor,
        chunker=chunker,
        pause_vad=pause_vad,
        diar_service=diar,
        timeline_store=timeline,
        stt_service=stt,
        sentence_assembler=assembler,
        attributor=attributor,
        voice_id_matcher=voice_id_matcher,
        stitcher=stitcher,
        coach_engine=coach,
    )
    orchestrator.start_session("s1", sample_rate, ctx=None, client=None)

    output1 = orchestrator.process_audio_chunk("s1", _pcm_bytes(200), sample_rate)
    output2 = orchestrator.process_audio_chunk("s1", _pcm_bytes(200), sample_rate)
    total_sentences = len(output1.speaker_sentences) + len(output2.speaker_sentences)
    assert total_sentences >= 1


def test_v2_pipeline_emits_patch_updates():
    # Scenario: diarization patch results in ui.sentence.patch updates.
    sample_rate = 16000
    ring = AudioRingBuffer(sample_rate=sample_rate, max_seconds=60)
    ingestor = AudioIngestor(ring_buffer=ring, sample_rate=sample_rate)
    chunker = AudioChunker(sample_rate=sample_rate, window_s=0.2, hop_s=0.2)
    pause_vad = PauseVADService(sample_rate=sample_rate)
    diar = FakeDiarPatchService()
    timeline = SpeakerTimelineStore(sample_rate=sample_rate, min_turn_ms=0, switch_confirm_ms=0, cooldown_ms=0, switch_margin=0.0, max_minutes=1)
    stt = FakeSttService()
    assembler = SentenceAssembler(sample_rate=sample_rate)
    attributor = SentenceSpeakerAttributor(timeline_store=timeline, sample_rate=sample_rate)
    voice_id_matcher = VoiceIdMatcher(sample_rate=sample_rate)
    stitcher = SentenceStitcher()
    coach = CoachEngine()
    orchestrator = SessionOrchestrator(
        ingestor=ingestor,
        chunker=chunker,
        pause_vad=pause_vad,
        diar_service=diar,
        timeline_store=timeline,
        stt_service=stt,
        sentence_assembler=assembler,
        attributor=attributor,
        voice_id_matcher=voice_id_matcher,
        stitcher=stitcher,
        coach_engine=coach,
    )
    orchestrator.start_session("s1", sample_rate, ctx=None, client=None)

    orchestrator.process_audio_chunk("s1", _pcm_bytes(200), sample_rate)
    output = orchestrator.process_audio_chunk("s1", _pcm_bytes(200), sample_rate)
    assert output.ui_sentence_patches
