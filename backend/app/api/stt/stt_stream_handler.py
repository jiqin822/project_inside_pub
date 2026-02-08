"""
STT stream handler: orchestrates response processing, final/interim segments, and speaker resolution.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from app.domain.stt.diarization_utils import best_overlap_speaker_id
from app.domain.stt.escalation import detect_escalation
from app.domain.stt.nemo_sortformer_diarizer import streaming_latency_s
from app.domain.stt.session_registry import diarization_reliable_end_sample
from app.domain.stt.speaker_timeline_attribution import (
    OVERLAP_LABEL,
    SEGMENT_LEVEL,
    UNCERTAIN_LABEL,
    query_speaker_timeline,
)
from app.domain.stt.anonymous_name import speaker_display_name
from app.domain.voice.embeddings import ECAPA_EMBEDDING_DIM, cosine_similarity

from app.api.stt.segment_builder import SttSegment
from app.api.stt.constants import (
    LABEL_ANON_PREFIX,
    LABEL_UNKNOWN_PREFIX,
    SPEAKER_SOURCE_NEMO,
    SPEAKER_SOURCE_VOICE_ID,
)
from app.settings import settings

logger = logging.getLogger(__name__)


class SttStreamHandler:
    """Main orchestrator for WebSocket stream: response handling, segment handling, timeline attribution, and speaker resolution scheduling."""

    def __init__(
        self,
        segment_builder: Any,
        audio_processor: Any,
        message_builder: Any,
        nemo_labeler: Any,
    ):
        self.segment_builder = segment_builder
        self.audio_processor = audio_processor
        self.message_builder = message_builder
        self.nemo_labeler = nemo_labeler

    async def resolve_interim_speaker_label(
        self, deps: Any, seg_tag: Optional[int]
    ) -> str:
        """Resolve display label for an interim (non-final) segment."""
        async with deps.ctx.voice_id_lock:
            raw = (
                deps.ctx.speaker_tag_to_label.get(
                    seg_tag, LABEL_UNKNOWN_PREFIX.rstrip("_")
                )
                if seg_tag is not None
                else LABEL_UNKNOWN_PREFIX.rstrip("_")
            )
            if (
                raw
                and not raw.startswith(LABEL_UNKNOWN_PREFIX)
                and raw not in deps.ctx.voice_embeddings
            ):
                deps.ctx.unknown_counter += 1
                seg_speaker_label = f"{LABEL_UNKNOWN_PREFIX}{deps.ctx.unknown_counter}"
                deps.ctx.unknown_label_parent[seg_speaker_label] = seg_speaker_label
                if seg_tag is not None:
                    deps.ctx.speaker_tag_to_label[seg_tag] = seg_speaker_label
            else:
                seg_speaker_label = raw or LABEL_UNKNOWN_PREFIX.rstrip("_")
        return seg_speaker_label

    async def query_timeline_attribution(
        self,
        deps: Any,
        start_sample: Optional[int],
        end_sample: Optional[int],
    ) -> Optional[tuple[str, float, bool, str]]:
        """Query speaker timeline for segment attribution when inside the reliable window."""
        if (
            not deps.ctx.speaker_timeline
            or start_sample is None
            or end_sample is None
        ):
            reason = "no_timeline" if not deps.ctx.speaker_timeline else "missing_bounds"
            return None
        lag_ms = getattr(settings, "stt_diarization_reliable_lag_ms", 1000)
        reliable_end = diarization_reliable_end_sample(
            deps.ring_buffer.total_samples, lag_ms
        )
        if end_sample > reliable_end:
            return None
        async with deps.ctx.timeline_lock:
            tl_label, timeline_confidence, timeline_is_overlap, timeline_attr_source = query_speaker_timeline(
                deps.ctx, start_sample, end_sample, attribution_source=SEGMENT_LEVEL
            )
        if not tl_label or tl_label == UNCERTAIN_LABEL:
            return None
        return (
            tl_label,
            timeline_confidence,
            timeline_is_overlap,
            timeline_attr_source,
        )

    async def schedule_speaker_resolution(
        self,
        deps: Any,
        pcm_for_embedding: bytes,
        segment_id: int,
        seg_tag: Optional[int],
        nemo_speaker_id: Optional[str],
        start_ms: Optional[int],
    ) -> None:
        """Schedule async speaker-resolution task (NeMo label or voice-id) for this segment."""
        if deps.enable_nemo_fallback and nemo_speaker_id:
            async with deps.ctx.nemo_label_lock:
                label = deps.ctx.nemo_speaker_id_to_label.get(nemo_speaker_id)
                should_attempt = (
                    (nemo_speaker_id not in deps.ctx.nemo_label_attempted)
                    and (label is not None)
                    and label.startswith(LABEL_ANON_PREFIX)
                )
                if should_attempt:
                    deps.ctx.nemo_label_attempted.add(nemo_speaker_id)
            if should_attempt:
                async def _label_then_fallback() -> None:
                    matched = await self.nemo_labeler.label_then_send(
                        deps,
                        pcm_for_embedding,
                        segment_id,
                        nemo_speaker_id,
                        segment_start_ms=start_ms,
                    )
                    if not matched:
                        await self.nemo_labeler.voice_id_then_send(
                            deps,
                            pcm_for_embedding,
                            segment_id,
                            seg_tag,
                            nemo_speaker_id=nemo_speaker_id,
                            start_ms=start_ms,
                        )

                task = asyncio.create_task(_label_then_fallback())
                deps.ctx.pending_nemo_label_tasks.add(task)
                task.add_done_callback(
                    lambda t: deps.ctx.pending_nemo_label_tasks.discard(t)
                )
            else:
                task = asyncio.create_task(
                    self.nemo_labeler.voice_id_then_send(
                        deps, pcm_for_embedding, segment_id, seg_tag
                    )
                )
                deps.ctx.pending_voice_id_tasks.add(task)
                task.add_done_callback(
                    lambda t: deps.ctx.pending_voice_id_tasks.discard(t)
                )
        else:
            task = asyncio.create_task(
                self.nemo_labeler.voice_id_then_send(
                    deps, pcm_for_embedding, segment_id, seg_tag
                )
            )
            deps.ctx.pending_voice_id_tasks.add(task)
            task.add_done_callback(
                lambda t: deps.ctx.pending_voice_id_tasks.discard(t)
            )

    async def handle_final_segment(
        self,
        deps: Any,
        segment: SttSegment,
        result: Any,
        alternative: Any,
        stream_base: int,
        timeline_snapshot: Optional[list],
        diarization_script_intervals: Optional[list],
        last_escalation_at_ref: list[float],
        speaker_matcher: Any,
    ) -> None:
        """Handle one final STT segment end-to-end."""
        start_ms = (
            int(segment.raw_start_s * 1000) if segment.raw_start_s is not None else None
        )
        end_ms = (
            int(segment.raw_end_s * 1000) if segment.raw_end_s is not None else None
        )
        samples, start_sample, end_sample, seg_abs_start_s, seg_abs_end_s = (
            self.segment_builder.extract_segment_audio(
                segment,
                deps.ring_buffer,
                stream_base,
                timeline_snapshot,
                diarization_script_intervals,
                True,
                bool(deps.ctx.voice_embeddings),
            )
        )
        segment_id = deps.ctx.segment_index
        deps.ctx.segment_index += 1
        pcm_copy = (
            bytes(samples.tobytes())
            if samples is not None and len(samples) > 0
            else None
        )
        if pcm_copy is not None:
            deps.ctx.segment_audio_backing[segment_id] = pcm_copy
            while len(deps.ctx.segment_audio_backing) > deps.ctx.segment_audio_backing_max:
                oldest = min(deps.ctx.segment_audio_backing.keys())
                del deps.ctx.segment_audio_backing[oldest]
        audio_segment_base64 = self.audio_processor.samples_to_wav_base64(samples)
        seg_speaker_label, speaker_source, nemo_speaker_id, seg_tag = (
            await self.audio_processor.resolve_final_segment_speaker_and_source(
                deps,
                seg_abs_start_s,
                seg_abs_end_s,
                segment.speaker_tag,
                segment.words,
                speaker_matcher,
            )
        )
        if start_sample is not None and end_sample is not None:
            earliest_retained = max(
                0,
                deps.ring_buffer.total_samples - deps.ring_buffer.max_samples,
            )
            if (
                start_sample < earliest_retained
                or end_sample > deps.ring_buffer.total_samples
            ):
                logger.warning(
                    "STT attribution query outside ring buffer: start=%s end=%s total=%s earliest=%s",
                    start_sample,
                    end_sample,
                    deps.ring_buffer.total_samples,
                    earliest_retained,
                )
        tl_result = await self.query_timeline_attribution(
            deps, start_sample, end_sample
        )
        use_timeline_resolved = False
        timeline_confidence = 0.0
        timeline_is_overlap = False
        timeline_attr_source = SEGMENT_LEVEL
        if tl_result:
            (
                tl_label,
                timeline_confidence,
                timeline_is_overlap,
                timeline_attr_source,
            ) = tl_result
            seg_speaker_label = tl_label
            use_timeline_resolved = True
        transcript_payload = self.message_builder.build_transcript_payload(
            deps.ctx.session_id,
            seg_text=segment.text,
            speaker_label=seg_speaker_label,
            seg_tag=seg_tag,
            is_final=True,
            start_ms=start_ms,
            end_ms=end_ms,
            confidence=getattr(alternative, "confidence", None),
            segment_id=segment_id,
            audio_segment_base64=audio_segment_base64,
            speaker_source=speaker_source,
            nemo_speaker_id=nemo_speaker_id,
        )
        # Bounded deferral: if NeMo overlap missing and fallback enabled, queue and let flush send later.
        ttl_s = streaming_latency_s() + 0.5
        pending_list = getattr(deps.ctx, "pending_final_segments", None)
        if (
            nemo_speaker_id is None
            and deps.enable_nemo_fallback
            and pending_list is not None
            and getattr(deps.ctx, "nemo_updated_event", None) is not None
        ):
            if pcm_copy and deps.ctx.voice_embeddings:
                pcm_for_embedding = await self.audio_processor.get_pcm_for_embedding(
                    deps, pcm_copy, start_sample, end_sample, segment_id
                )
                await self.schedule_speaker_resolution(
                    deps,
                    pcm_for_embedding,
                    segment_id,
                    seg_tag,
                    nemo_speaker_id,
                    start_ms,
                )
            pending_list.append(
                {
                    "segment_id": segment_id,
                    "seg_abs_start_s": seg_abs_start_s,
                    "seg_abs_end_s": seg_abs_end_s,
                    "payload": transcript_payload,
                    "created_ts": time.monotonic(),
                    "ttl_s": ttl_s,
                    "use_timeline_resolved": use_timeline_resolved,
                    "seg_speaker_label": seg_speaker_label,
                    "timeline_confidence": timeline_confidence,
                    "timeline_is_overlap": timeline_is_overlap,
                    "timeline_attr_source": timeline_attr_source,
                }
            )
            return
        await deps.websocket.send_json(transcript_payload)
        if use_timeline_resolved:
            did_schedule_voice_id = False
            try:
                _timeline_payload = self.message_builder.build_speaker_resolved_payload(
                    deps.ctx.session_id,
                    segment_id=segment_id,
                    speaker_label=seg_speaker_label,
                    speaker_source=SPEAKER_SOURCE_VOICE_ID,
                    confidence=timeline_confidence,
                    is_overlap=timeline_is_overlap,
                    attribution_source=timeline_attr_source,
                )
                if pcm_copy and deps.ctx.voice_embeddings:
                    segment_embedding = await deps.loop.run_in_executor(
                        deps.executor,
                        self.audio_processor.compute_embedding_sync,
                        pcm_copy,
                    )
                    if (
                        segment_embedding
                        and len(segment_embedding) == ECAPA_EMBEDDING_DIM
                    ):
                        scores_list = []
                        for uid, emb in deps.ctx.voice_embeddings.items():
                            if len(emb) != len(segment_embedding):
                                continue
                            score = cosine_similarity(segment_embedding, emb)
                            label = f"user:{uid[-6:]}" if len(uid) >= 6 else uid
                            scores_list.append((label, score))
                        scores_list.sort(key=lambda x: x[1], reverse=True)
                        if scores_list:
                            _timeline_payload["best_score_pct"] = round(
                                max(0.0, scores_list[0][1]) * 100, 1
                            )
                        if len(scores_list) >= 2:
                            _timeline_payload["second_score_pct"] = round(
                                max(0.0, scores_list[1][1]) * 100, 1
                            )
                            _timeline_payload["score_margin_pct"] = round(
                                (scores_list[0][1] - scores_list[1][1]) * 100, 1
                            )
                        _timeline_payload["all_scores"] = [
                            {
                                "label": speaker_display_name(
                                    deps.ctx.session_id, label
                                ),
                                "score_pct": round(max(0.0, s) * 100, 1),
                            }
                            for label, s in scores_list
                        ]
                await deps.websocket.send_json(_timeline_payload)
                # If we can run voice-id on this segment, schedule it so we get debug scores.
                # We only pop segment_audio_backing / increment counters when voice-id is not scheduled.
                if (
                    pcm_copy
                    and deps.ctx.voice_embeddings
                    and seg_speaker_label not in (OVERLAP_LABEL, UNCERTAIN_LABEL)
                ):
                    pcm_for_embedding = await self.audio_processor.get_pcm_for_embedding(
                        deps, pcm_copy, start_sample, end_sample, segment_id
                    )
                    await self.schedule_speaker_resolution(
                        deps,
                        pcm_for_embedding,
                        segment_id,
                        seg_tag,
                        nemo_speaker_id,
                        start_ms,
                    )
                    did_schedule_voice_id = True
                if not did_schedule_voice_id:
                    deps.ctx.segment_audio_backing.pop(segment_id, None)
                    deps.ctx.segments_resolved_count += 1
                if seg_speaker_label == OVERLAP_LABEL:
                    deps.ctx.overlap_resolved_count += 1
                    logger.debug(
                        "STT speaker_resolved OVERLAP session=%s segment_id=%s total_resolved=%s overlap_count=%s",
                        deps.ctx.session_id,
                        segment_id,
                        deps.ctx.segments_resolved_count,
                        deps.ctx.overlap_resolved_count,
                    )
                elif seg_speaker_label == UNCERTAIN_LABEL:
                    deps.ctx.uncertain_resolved_count += 1
                    logger.debug(
                        "STT speaker_resolved UNCERTAIN session=%s segment_id=%s total_resolved=%s uncertain_count=%s",
                        deps.ctx.session_id,
                        segment_id,
                        deps.ctx.segments_resolved_count,
                        deps.ctx.uncertain_resolved_count,
                    )
            except Exception as send_err:
                logger.debug(
                    "speaker_resolved (timeline) send skipped: %s", send_err
                )
        elif pcm_copy and deps.ctx.voice_embeddings:
            pcm_for_embedding = await self.audio_processor.get_pcm_for_embedding(
                deps, pcm_copy, start_sample, end_sample, segment_id
            )
            await self.schedule_speaker_resolution(
                deps,
                pcm_for_embedding,
                segment_id,
                seg_tag,
                nemo_speaker_id,
                start_ms,
            )

    async def _flush_pending_final_segments(
        self, deps: Any, speaker_matcher: Any
    ) -> None:
        """Re-resolve pending segments from NeMo history; send when resolved or TTL expired."""
        pending_list = getattr(deps.ctx, "pending_final_segments", None)
        if not pending_list:
            return
        now = time.monotonic()
        still_pending: list = []
        async with deps.ctx.nemo_history_lock:
            segments_for_overlap = list(
                getattr(deps.ctx, "nemo_segments_history", None) or []
            )
        for item in pending_list:
            seg_abs_start_s = item.get("seg_abs_start_s")
            seg_abs_end_s = item.get("seg_abs_end_s")
            payload = item.get("payload")
            created_ts = item.get("created_ts", 0)
            ttl_s = item.get("ttl_s", 3.0)
            segment_id = item.get("segment_id")
            if payload is None or segment_id is None:
                continue
            nemo_speaker_id = best_overlap_speaker_id(
                segments_for_overlap, seg_abs_start_s or 0, seg_abs_end_s or 0
            )
            if nemo_speaker_id:
                async with deps.ctx.nemo_label_lock:
                    seg_speaker_label = speaker_matcher.get_or_assign_nemo_label(
                        deps.ctx, nemo_speaker_id
                    )
                new_payload = self.message_builder.build_transcript_payload(
                    deps.ctx.session_id,
                    seg_text=payload.get("text", ""),
                    speaker_label=seg_speaker_label,
                    seg_tag=payload.get("speaker_tag"),
                    is_final=True,
                    start_ms=payload.get("start_ms"),
                    end_ms=payload.get("end_ms"),
                    confidence=payload.get("confidence"),
                    segment_id=segment_id,
                    audio_segment_base64=payload.get("audio_segment_base64"),
                    speaker_source=SPEAKER_SOURCE_NEMO,
                    nemo_speaker_id=nemo_speaker_id,
                )
                try:
                    await deps.websocket.send_json(new_payload)
                except Exception:
                    pass
                continue
            if (now - created_ts) >= ttl_s:
                try:
                    await deps.websocket.send_json(payload)
                except Exception:
                    pass
                continue
            still_pending.append(item)
        if pending_list is not None:
            pending_list.clear()
            pending_list.extend(still_pending)

    async def run_pending_flush_loop(
        self, deps: Any, speaker_matcher: Any
    ) -> None:
        """Loop: wait for NeMo update or TTL, then flush pending final segments. Run until nemo_worker_stop."""
        ttl_s = streaming_latency_s() + 0.5
        event = getattr(deps.ctx, "nemo_updated_event", None)
        while not deps.nemo_worker_stop.is_set():
            try:
                if event is not None:
                    await asyncio.wait_for(event.wait(), timeout=ttl_s)
                else:
                    await asyncio.sleep(ttl_s)
            except asyncio.TimeoutError:
                pass
            if deps.nemo_worker_stop.is_set():
                break
            await self._flush_pending_final_segments(deps, speaker_matcher)
            if event is not None:
                event.clear()

    async def handle_interim_segment(
        self, deps: Any, segment: SttSegment, alternative: Any
    ) -> None:
        """Handle one interim (non-final) STT segment."""
        start_ms = (
            int(segment.raw_start_s * 1000) if segment.raw_start_s is not None else None
        )
        end_ms = (
            int(segment.raw_end_s * 1000) if segment.raw_end_s is not None else None
        )
        seg_speaker_label = await self.resolve_interim_speaker_label(
            deps, segment.speaker_tag
        )
        await deps.websocket.send_json(
            self.message_builder.build_transcript_payload(
                deps.ctx.session_id,
                seg_text=segment.text,
                speaker_label=seg_speaker_label,
                seg_tag=segment.speaker_tag,
                is_final=False,
                start_ms=start_ms,
                end_ms=end_ms,
                confidence=getattr(alternative, "confidence", None),
            )
        )

    async def handle_response_message(
        self,
        response: Any,  # Google STT StreamingRecognizeResponse object containing transcription results
        stream_base: int,  # Absolute sample index marking the beginning of the current audio chunk (i.e., the starting sample index for this portion of streamed audio)
        deps: Any,  # Dependencies and context for the session (includes ctx, websocket, ring_buffer, etc.)
        last_escalation_at_ref: list[float],  # Singleton list tracking timestamp of last escalation sent (mutable for reference)
        speaker_matcher: Any,  # SpeakerMatcher instance to assign and resolve speaker tags/labels
    ) -> None:
        """Process a single Google StreamingRecognize response.

        StreamingRecognize response has a "results" attribute, which is a list of
        StreamingRecognitionResult objects. Each result may represent an interim or final
        portion of the transcript. Each result contains a list of "alternatives", with the
        first (highest confidence) alternative containing the transcript and word-level info.
        """
        alternative = None
        for result in response.results:
            # "alternatives" is a list of possible recognition results provided by the STT API,
            # typically ordered by confidence (best guess first). We pick the top (best) one.
            if not result.alternatives:
                continue
            alternative = result.alternatives[0]
            segments_to_send, diarization_script_intervals, timeline_snapshot = (
                await self.segment_builder.build_segments_from_result(
                    result, deps, stream_base
                )
            )
            if not segments_to_send:
                continue
            for segment in segments_to_send:
                escalation = detect_escalation(segment.text)
                if escalation:
                    await self.message_builder.send_escalation_if_allowed(
                        escalation, deps.websocket, last_escalation_at_ref
                    )
                if result.is_final:
                    await self.handle_final_segment(
                        deps,
                        segment,
                        result,
                        alternative,
                        stream_base,
                        timeline_snapshot,
                        diarization_script_intervals,
                        last_escalation_at_ref,
                        speaker_matcher,
                    )
                else:
                    await self.handle_interim_segment(
                        deps, segment, alternative
                    )
