"""Session orchestrator for STT V2 pipeline (audio -> diarization + STT -> UI)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple
from concurrent.futures import Future, ThreadPoolExecutor

import logging
import base64
import numpy as np
from app.api.stt_v2.audio_chunker import AudioChunker
from app.api.stt_v2.audio_ingestor import AudioIngestor
from app.api.stt_v2.chirp3_stt_service import Chirp3SttService
from app.api.stt_v2.coach_engine import CoachEngine, NudgeEvent
from app.api.stt_v2.pause_vad_service import PauseVADService
from app.api.stt_v2.sentence_assembler import SentenceAssembler
from app.api.stt_v2.sentence_attributor import SentenceSpeakerAttributor
from app.api.stt_v2.sentence_stitcher import SentenceStitcher
from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.api.stt_v2.diarization_service import DiarizationService
from app.api.stt_v2.diarization_stabilizer import DiarizationStabilizer
from app.api.stt_v2.event_bus import EventBus, EventQueue
from app.api.stt_v2.metrics import MetricsCollector
from app.api.stt_v2.voice_id_matcher import VoiceIdMatcher
from app.api.stt.audio_processor import AudioProcessor
from app.settings import settings
from app.domain.stt_v2.contracts import (
    AudioFrame,
    AudioWindow,
    DiarFrame,
    DiarPatch,
    PauseEvent,
    SpeakerSentence,
    StreamId,
    TimeRangeSamples,
    UiSentence,
    UNCERTAIN_LABEL,
    OVERLAP_LABEL,
)


@dataclass
class OrchestratorOutput:
    provisional_sentences: List
    speaker_sentences: List
    ui_sentence_patches: List
    nudges: List[NudgeEvent]


@dataclass
class _StreamState:
    recent_sentences: List[UiSentence] = field(default_factory=list)
    event_bus: EventBus | None = None
    metrics: MetricsCollector | None = None
    stt_segments: List = field(default_factory=list)
    speaker_sentences: List = field(default_factory=list)
    debug_enabled: bool = False
    ctx: any = None
    patch_timeline_diffs: List[dict] = field(default_factory=list)
    diar_stabilizer: DiarizationStabilizer | None = None
    diar_futures: List[Tuple[Future, int]] = field(default_factory=list)


class SessionOrchestrator:
    def __init__(
        self,
        ingestor: AudioIngestor,
        chunker: AudioChunker,
        pause_vad: PauseVADService,
        diar_service: DiarizationService,
        timeline_store: SpeakerTimelineStore,
        stt_service: Chirp3SttService,
        sentence_assembler: SentenceAssembler,
        attributor: SentenceSpeakerAttributor,
        voice_id_matcher: VoiceIdMatcher,
        stitcher: SentenceStitcher,
        coach_engine: CoachEngine,
        patch_window_ms: int = 20000,
        audio_queue_max: int = 50,
        frame_queue_max: int = 200,
        window_queue_max: int = 50,
        diar_queue_max: int = 200,
        stt_queue_max: int = 200,
    ) -> None:
        self.ingestor = ingestor
        self.chunker = chunker
        self.pause_vad = pause_vad
        self.diar_service = diar_service
        self.timeline_store = timeline_store
        self.stt_service = stt_service
        self.sentence_assembler = sentence_assembler
        self.attributor = attributor
        self.voice_id_matcher = voice_id_matcher
        self.stitcher = stitcher
        self.coach_engine = coach_engine
        self.audio_processor = AudioProcessor(sample_rate_hz=ingestor.sample_rate)
        self.patch_window_ms = patch_window_ms
        self.audio_queue_max = audio_queue_max
        self.frame_queue_max = frame_queue_max
        self.window_queue_max = window_queue_max
        self.diar_queue_max = diar_queue_max
        self.stt_queue_max = stt_queue_max
        self._streams: Dict[StreamId, _StreamState] = {}
        self._logger = logging.getLogger(__name__)
        self._max_patch_diffs = 5
        self._use_diar_stabilizer = bool(
            getattr(diar_service, "is_nemo_backend", False)
        )
        self._use_diar_async = bool(
            getattr(diar_service, "is_nemo_backend", False)
        )
        self._diar_executor = ThreadPoolExecutor(max_workers=1)

    def _state(self, stream_id: StreamId) -> _StreamState:
        if stream_id not in self._streams:
            state = _StreamState(
                event_bus=EventBus(
                    audio_queue=EventQueue(self.audio_queue_max),
                    frame_queue=EventQueue(self.frame_queue_max),
                    window_queue=EventQueue(self.window_queue_max),
                    diar_queue=EventQueue(self.diar_queue_max),
                    stt_queue=EventQueue(self.stt_queue_max),
                ),
                metrics=None,
            )
            if self._use_diar_stabilizer:
                state.diar_stabilizer = DiarizationStabilizer(
                    sample_rate=self.ingestor.sample_rate,
                    live_zone_ms=settings.stt_v2_diar_live_zone_ms,
                    refine_zone_ms=settings.stt_v2_diar_refine_zone_ms,
                    commit_zone_ms=settings.stt_v2_diar_commit_zone_ms,
                    min_segment_ms=settings.stt_v2_diar_min_segment_ms,
                    commit_conf_th=settings.stt_v2_diar_commit_conf_th,
                    switch_confirm_ms=settings.stt_v2_switch_confirm_ms,
                    switch_margin=settings.stt_v2_switch_margin,
                )
            self._streams[stream_id] = state
        return self._streams[stream_id]

    def start_session(self, stream_id: StreamId, sr: int, ctx: any, client: any) -> None:
        self.diar_service.start(stream_id, sr)
        self.stt_service.start(stream_id, sr, ctx, client)
        state = self._state(stream_id)
        state.debug_enabled = bool(getattr(ctx, "debug", False))
        state.metrics = MetricsCollector() if state.debug_enabled else None
        state.ctx = ctx
        self.sentence_assembler.set_debug(stream_id, state.debug_enabled)

    def stop_session(self, stream_id: StreamId) -> None:
        self.stt_service.stop(stream_id)
        self.voice_id_matcher.reset(stream_id)
        state = self._streams.get(stream_id)
        if state is not None:
            state.metrics = None

    def process_audio_chunk(self, stream_id: StreamId, pcm16_bytes: bytes, sr: int) -> OrchestratorOutput:
        output = OrchestratorOutput(
            provisional_sentences=[],
            speaker_sentences=[],
            ui_sentence_patches=[],
            nudges=[],
        )
        chunk = self.ingestor.push_pcm16(stream_id, pcm16_bytes, sr)
        state = self._state(stream_id)
        if state.event_bus is None:
            return output
        bus = state.event_bus
        bus.audio_queue.push(chunk)

        if self._use_diar_async:
            self._drain_diar_futures(state, bus, stream_id)

        # Audio -> frames/windows
        for audio_chunk in bus.audio_queue.pop_all():
            events = self.chunker.on_audio_chunk(audio_chunk)
            for event in events:
                if isinstance(event, AudioFrame):
                    bus.frame_queue.push(event)
                elif isinstance(event, AudioWindow):
                    bus.window_queue.push(event)

        # VAD over frames (pause events define sentence boundaries)
        for frame in bus.frame_queue.pop_all():
            pause_events = self.pause_vad.process_frame(frame)
            for pause_event in pause_events:
                if isinstance(pause_event, PauseEvent):
                    ui_sentences = self.sentence_assembler.on_pause_event(
                        stream_id, pause_event
                    )
                    for ui_sentence in ui_sentences:
                        output.provisional_sentences.append(
                            self._build_provisional_sentence(ui_sentence, state.ctx)
                        )
                    patches, new_sentences, nudges = self._handle_ui_sentences(
                        stream_id, ui_sentences
                    )
                    output.ui_sentence_patches.extend(patches)
                    output.speaker_sentences.extend(new_sentences)
                    output.nudges.extend(nudges)

        # Diarization over windows (speaker labels in sample-time). Skip when session requests sentence boundary + embedding only.
        skip_diar = state.ctx is not None and getattr(state.ctx, "skip_diarization", False)
        windows = bus.window_queue.pop_all()
        for window in windows:
            if skip_diar:
                continue
            if self._use_diar_async:
                future = self._diar_executor.submit(
                    self.diar_service.process_window, window
                )
                state.diar_futures.append((future, window.range_samples.end))
            else:
                diar_outputs = self.diar_service.process_window(window)
                if state.diar_stabilizer is not None:
                    diar_outputs = state.diar_stabilizer.stabilize_outputs(
                        diar_outputs, window.range_samples.end
                    )
                for diar_output in diar_outputs:
                    if isinstance(diar_output, DiarFrame):
                        bus.diar_queue.push(diar_output, drop_preview_first=True)
                    elif isinstance(diar_output, DiarPatch):
                        bus.diar_queue.push(diar_output, drop_preview_first=True)

        # Apply diar outputs in order, prioritizing patches if queue is full (drop preview first).
        # This updates the timeline used for all subsequent sentence attribution.
        for diar_output in bus.diar_queue.pop_all():
            if isinstance(diar_output, DiarFrame):
                self.timeline_store.apply_frames(stream_id, [diar_output])
            elif isinstance(diar_output, DiarPatch):
                pre_patch = self._snapshot_timeline_range(
                    stream_id, diar_output.range_samples
                )
                self.timeline_store.apply_patch(stream_id, diar_output)
                post_patch = self._snapshot_timeline_range(
                    stream_id, diar_output.range_samples
                )
                self._record_patch_diff(
                    state,
                    diar_output,
                    pre_patch,
                    post_patch,
                )
                output.ui_sentence_patches.extend(
                    self._reattribute_patch(stream_id, diar_output.range_samples.start, diar_output.range_samples.end)
                )

        # STT path (text segments -> UI sentences -> speaker attribution)
        stt_segments = self.stt_service.process_audio_chunk(chunk)
        for seg in stt_segments:
            state.stt_segments.append(seg)
            if len(state.stt_segments) > 200:
                state.stt_segments = state.stt_segments[-200:]
            ui_sentences = self.sentence_assembler.on_stt_segment(stream_id, seg)
            for ui_sentence in ui_sentences:
                output.provisional_sentences.append(
                    self._build_provisional_sentence(ui_sentence, state.ctx)
                )
            patches, new_sentences, nudges = self._handle_ui_sentences(
                stream_id, ui_sentences
            )
            output.ui_sentence_patches.extend(patches)
            output.speaker_sentences.extend(new_sentences)
            output.nudges.extend(nudges)

        # Flush any buffered sentence to avoid UI starvation.
        flushed = self.stitcher.flush(stream_id)
        for ss in flushed:
            ss_with_audio = self._attach_audio_segment(stream_id, ss)
            patches, new_sentences = self._prepare_updates(ss_with_audio, state.ctx)
            output.ui_sentence_patches.extend(patches)
            output.speaker_sentences.extend(new_sentences)
            output.nudges.extend(self.coach_engine.on_speaker_sentence(ss_with_audio))
            state.speaker_sentences.append(ss_with_audio)
            if len(state.speaker_sentences) > 200:
                state.speaker_sentences = state.speaker_sentences[-200:]
            if state.metrics:
                state.metrics.record_sentence(ss_with_audio)

        # Emit metrics snapshot occasionally.
        if state.metrics and state.metrics.sentence_count and state.metrics.sentence_count % 20 == 0:
            self._logger.info(
                "STT V2 metrics (%s): %s",
                stream_id,
                state.metrics.snapshot(),
            )


        return output

    def _drain_diar_futures(
        self, state: _StreamState, bus: EventBus, stream_id: StreamId
    ) -> None:
        if not state.diar_futures:
            return
        processed = 0
        pending: List[Tuple[Future, int]] = []
        for idx, (future, window_end) in enumerate(state.diar_futures):
            if not future.done():
                pending = state.diar_futures[idx:]
                break
            try:
                diar_outputs = future.result()
            except Exception:
                continue
            processed += 1
            if state.diar_stabilizer is not None:
                diar_outputs = state.diar_stabilizer.stabilize_outputs(
                    diar_outputs, window_end
                )
            for diar_output in diar_outputs:
                if isinstance(diar_output, (DiarFrame, DiarPatch)):
                    bus.diar_queue.push(diar_output, drop_preview_first=True)
        state.diar_futures = pending

    def _handle_ui_sentences(
        self, stream_id: StreamId, sentences: List[UiSentence]
    ) -> tuple[List, List, List[NudgeEvent]]:
        patches: List = []
        new_sentences: List = []
        nudges: List[NudgeEvent] = []
        state = self._state(stream_id)
        for sentence in sentences:
            state.recent_sentences.append(sentence)
            skip_diar = state.ctx is not None and getattr(state.ctx, "skip_diarization", False)
            if skip_diar:
                # Embedding-only mode: no diarization labels, use per-sentence voice ID.
                speaker_sentences = [
                    SpeakerSentence(
                        ui_sentence=sentence,
                        label=f"spk_embed_{sentence.id}",
                        label_conf=0.0,
                        coverage=0.0,
                        flags={"embedding_only": True},
                        debug={
                            "decision": "embedding_only",
                            "skip_diarization": True,
                        }
                        if state.debug_enabled
                        else None,
                    )
                ]
            else:
                # Attribute UI sentence to a single diarization label (spkX / overlap / uncertain).
                speaker_sentences = self.attributor.attribute_with_speaker_change(
                    stream_id,
                    sentence,
                    self.ingestor.ring_buffer,
                    self.audio_processor,
                    debug_enabled=state.debug_enabled,
                )
            for speaker_sentence in speaker_sentences:
                if state.ctx is not None:
                    # Map diarization label (spkX) to a stable user_id using voiceprints + cache.
                    speaker_sentence = self.voice_id_matcher.map_label(
                        stream_id,
                        speaker_sentence,
                        state.ctx,
                        self.ingestor.ring_buffer,
                        self.audio_processor,
                        debug_enabled=state.debug_enabled,
                    )
                # Reduce fragmentation by stitching adjacent same-speaker sentences.
                stitched = self.stitcher.on_speaker_sentence(
                    stream_id, speaker_sentence
                )
                for ss in stitched:
                    ss_with_audio = self._attach_audio_segment(stream_id, ss)
                    patch_items, new_items = self._prepare_updates(
                        ss_with_audio, state.ctx
                    )
                    patches.extend(patch_items)
                    new_sentences.extend(new_items)
                    nudges.extend(self.coach_engine.on_speaker_sentence(ss))
                    state.speaker_sentences.append(ss_with_audio)
                    if len(state.speaker_sentences) > 200:
                        state.speaker_sentences = state.speaker_sentences[-200:]
                    if state.metrics:
                        state.metrics.record_sentence(ss_with_audio)
        return patches, new_sentences, nudges

    def _reattribute_patch(self, stream_id: StreamId, start_sample: int, end_sample: int) -> List:
        state = self._state(stream_id)
        patch_start_ms = int((start_sample * 1000) / self.timeline_store.sample_rate)
        patch_end_ms = int((end_sample * 1000) / self.timeline_store.sample_rate)
        updated = []
        recent = []
        for sentence in state.recent_sentences:
            if sentence.range_ms.end_ms < patch_start_ms - self.patch_window_ms:
                continue
            recent.append(sentence)
            if sentence.range_ms.start_ms <= patch_end_ms and sentence.range_ms.end_ms >= patch_start_ms:
                # Re-attribute any UI sentences that overlap the patched diarization window.
                speaker_sentences = self.attributor.attribute_with_speaker_change(
                    stream_id,
                    sentence,
                    self.ingestor.ring_buffer,
                    self.audio_processor,
                    debug_enabled=state.debug_enabled,
                )
                for speaker_sentence in speaker_sentences:
                    if state.ctx is not None:
                        speaker_sentence = self.voice_id_matcher.map_label(
                            stream_id,
                            speaker_sentence,
                            state.ctx,
                            self.ingestor.ring_buffer,
                            self.audio_processor,
                            debug_enabled=state.debug_enabled,
                        )
                    patch_items, _ = self._prepare_updates(
                        speaker_sentence, state.ctx, emit_split_new=False
                    )
                    updated.extend(patch_items)
        state.recent_sentences = recent
        if state.metrics:
            state.metrics.record_patch(len(updated))
        return updated

    def _build_provisional_sentence(
        self, sentence: UiSentence, ctx: any
    ) -> SpeakerSentence:
        ui_sentence = replace(sentence, ui_context={"provisional": True})
        flags = {"provisional": True, "uncertain": True}
        return SpeakerSentence(
            ui_sentence=ui_sentence,
            label=UNCERTAIN_LABEL,
            label_conf=0.0,
            coverage=0.0,
            flags=flags,
            speaker_color=self._speaker_color(UNCERTAIN_LABEL, ctx),
        )

    def _prepare_updates(
        self, ss: SpeakerSentence, ctx: any, emit_split_new: bool = True
    ) -> tuple[List[SpeakerSentence], List[SpeakerSentence]]:
        flags = dict(ss.flags or {})
        flags["provisional"] = False
        speaker_color = self._speaker_color(ss.label, ctx)
        ui_sentence = replace(ss.ui_sentence, ui_context={"provisional": False})
        updated = replace(
            ss,
            flags=flags,
            speaker_color=speaker_color,
            ui_sentence=ui_sentence,
        )
        base_id = self._split_base_id(updated.ui_sentence.id)
        if base_id:
            if updated.ui_sentence.id.endswith("_a"):
                return [self._patch_base_sentence(updated, base_id)], []
            if updated.ui_sentence.id.endswith("_b"):
                if emit_split_new:
                    split_ui = replace(updated.ui_sentence, split_from=base_id)
                    split_ss = replace(updated, ui_sentence=split_ui)
                    return [], [split_ss]
                return [updated], []
        return [updated], []

    @staticmethod
    def _split_base_id(sentence_id: str) -> Optional[str]:
        if sentence_id.endswith("_a") or sentence_id.endswith("_b"):
            return sentence_id[:-2]
        return None

    @staticmethod
    def _patch_base_sentence(
        ss: SpeakerSentence, base_id: str
    ) -> SpeakerSentence:
        patched_ui = replace(ss.ui_sentence, id=base_id, split_from=None)
        return replace(ss, ui_sentence=patched_ui)

    @staticmethod
    def _speaker_color(label: str, ctx: any) -> Optional[str]:
        if not label:
            return None
        lower = str(label).lower()
        if label in (UNCERTAIN_LABEL, OVERLAP_LABEL) or lower.startswith("unknown"):
            return "unknown"
        if ctx is not None:
            if label == getattr(ctx, "user_id", None):
                return "self"
            if label in (getattr(ctx, "candidate_user_ids", None) or []):
                return "partner"
        return "other"

    def _attach_audio_segment(self, stream_id: StreamId, ss: any):
        try:
            start_ms = ss.ui_sentence.range_ms.start_ms
            end_ms = ss.ui_sentence.range_ms.end_ms
        except Exception:
            return ss
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            return ss
        sample_rate = self.ingestor.sample_rate
        start_sample = int((start_ms * sample_rate) / 1000)
        end_sample = int((end_ms * sample_rate) / 1000)
        range_samples = TimeRangeSamples(start=start_sample, end=end_sample, sr=sample_rate)
        samples = self.ingestor.ring_buffer.read(stream_id, range_samples)
        if samples is None or len(samples) == 0:
            return ss
        audio_b64 = self.audio_processor.samples_to_wav_base64(samples)
        if not audio_b64:
            return ss
        return replace(ss, audio_segment_base64=audio_b64)

    def _snapshot_timeline_range(
        self, stream_id: StreamId, range_samples: TimeRangeSamples
    ) -> List[dict]:
        intervals = self.timeline_store.query(stream_id, range_samples)
        snapshot = []
        for span, label, conf, is_patch in intervals:
            snapshot.append(
                {
                    "start_sample": span.start,
                    "end_sample": span.end,
                    "label": label,
                    "conf": float(conf),
                    "is_patch": bool(is_patch),
                }
            )
        return snapshot

    def _record_patch_diff(
        self,
        state: _StreamState,
        patch: DiarPatch,
        pre_patch: List[dict],
        post_patch: List[dict],
    ) -> None:
        entry = {
            "version": patch.version,
            "range_start_sample": patch.range_samples.start,
            "range_end_sample": patch.range_samples.end,
            "pre": pre_patch,
            "post": post_patch,
        }
        state.patch_timeline_diffs.append(entry)
        if len(state.patch_timeline_diffs) > self._max_patch_diffs:
            state.patch_timeline_diffs = state.patch_timeline_diffs[-self._max_patch_diffs :]

    def build_debug_bundle(self, stream_id: StreamId) -> dict:
        state = self._state(stream_id)
        pcm = self.ingestor.ring_buffer.read_last_seconds(stream_id, 30)
        pcm_trimmed = self._trim_silence(pcm)
        pcm_b64 = (
            base64.b64encode(pcm_trimmed.tobytes()).decode("utf-8")
            if pcm_trimmed is not None
            else None
        )
        timeline = self.timeline_store.export_intervals(stream_id)
        metrics = state.metrics.snapshot() if state.metrics else {}
        return {
            "stream_id": stream_id,
            "pcm16_base64": pcm_b64,
            "timeline_intervals": timeline,
            "stt_segments": [
                {
                    "start_ms": seg.range_ms.start_ms,
                    "end_ms": seg.range_ms.end_ms,
                    "text": seg.text,
                    "conf": seg.stt_conf,
                    "is_final": seg.is_final,
                }
                for seg in state.stt_segments
            ],
            "speaker_sentences": [
                {
                    "id": ss.ui_sentence.id,
                    "start_ms": ss.ui_sentence.range_ms.start_ms,
                    "end_ms": ss.ui_sentence.range_ms.end_ms,
                    "text": ss.ui_sentence.text,
                    "label": ss.label,
                    "label_conf": ss.label_conf,
                    "coverage": ss.coverage,
                    "flags": ss.flags,
                }
                for ss in state.speaker_sentences
            ],
            "patch_timeline_diffs": list(state.patch_timeline_diffs),
            "metrics": metrics,
        }

    def _trim_silence(self, samples: np.ndarray | None) -> np.ndarray | None:
        if samples is None or len(samples) == 0:
            return None
        energy_th = float(getattr(self.pause_vad, "energy_threshold", 0.01))
        threshold = int(max(1.0, energy_th * 32768.0))
        abs_samples = np.abs(samples)
        indices = np.where(abs_samples > threshold)[0]
        if indices.size == 0:
            return None
        start = int(indices[0])
        end = int(indices[-1]) + 1
        return samples[start:end]
