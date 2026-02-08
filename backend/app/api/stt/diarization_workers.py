"""
Diarization background workers and NeMo speaker labeling for STT stream.

BaseDiarizationWorker, NeMoDiarizationWorker, SortformerTimelineWorker, and NeMoLabeler.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, NamedTuple, Optional

import numpy as np

from app.domain.stt.nemo_sortformer_diarizer import (
    create_streaming_diarizer,
    diarize_pcm16,
    get_chunk_bytes,
    get_frame_bytes,
    nemo_diarization_available,
    streaming_context_window_s,
    streaming_latency_s,
)
from app.domain.stt.session_registry import (
    DiarInterval,
    DEFINITE_OVERLAP,
    OVERLAP_NONE,
    POSSIBLE_OVERLAP,
    diarization_reliable_end_sample,
    TrackState,
)
from app.domain.stt.speaker_timeline_attribution import (
    SEGMENT_LEVEL,
    update_track_label_from_embedding,
)
from app.domain.stt.anonymous_name import speaker_display_name
from app.domain.voice.embeddings import (
    ECAPA_EMBEDDING_DIM,
    cosine_similarity,
    compute_embedding_from_pcm_bytes,
    l2_normalize,
)

from app.api.stt.constants import (
    LABEL_ANON_PREFIX,
    LABEL_UNKNOWN,
    LABEL_UNKNOWN_PREFIX,
    MSG_STT_NEMO_DIAR_SEGMENTS,
    SPEAKER_SOURCE_NEMO,
    SPEAKER_SOURCE_VOICE_ID,
    SPEAKER_SOURCE_GOOGLE,
    STT_MIN_PCM_BYTES_2S,
    STT_SAMPLE_RATE_HZ,
    STT_SPEAKER_TIMELINE_MAX_SAMPLES_DEFAULT,
)
from app.settings import settings

logger = logging.getLogger(__name__)


class BaseDiarizationWorker(ABC):
    """Abstract base for diarization background workers."""

    @abstractmethod
    async def run(self, deps: Any) -> None:
        """Run the worker until stop or queue end. Implementations consume from deps."""
        pass


class NeMoDiarizationWorker(BaseDiarizationWorker):
    """
    Legacy/compat: periodic NeMo diarization over the tail of the ring buffer.
    This exists for older windowed fallback behavior and debug scenarios.
    Not the main live path; streaming worker should be preferred.
    """

    async def run(self, deps: Any) -> None:
        ok, err = nemo_diarization_available()
        if not ok:
            logger.warning("NeMo diarization fallback disabled: %s", err)
            return
        window_s = float(getattr(settings, "stt_nemo_diarization_window_s", 1.6))
        hop_s = float(getattr(settings, "stt_nemo_diarization_hop_s", 0.4))
        timeout_s = float(getattr(settings, "stt_nemo_diarization_timeout_s", 3.0))
        max_speakers = getattr(settings, "stt_nemo_diarization_max_speakers", 4)
        latency_s = streaming_latency_s()
        context_s = streaming_context_window_s()
        # Align diarization window with streaming model context/latency so we don't ask for more
        # (or less) audio than the NeMo streaming model expects. This keeps windowed fallback
        # behavior consistent with the streaming diarizer's receptive field and latency.
        effective_window_s = min(window_s, context_s)
        effective_window_s = max(effective_window_s, latency_s)
        while not deps.nemo_worker_stop.is_set():
            try:
                # --- Wait until we have enough audio for one diarization window ---
                abs_end_sample = deps.ring_buffer.total_samples
                window_samples = max(0, int(effective_window_s * STT_SAMPLE_RATE_HZ))
                if abs_end_sample < window_samples:
                    # We do not have enough audio yet to fill a window for diarization,
                    # so we wait for either (A) the stop event (deps.nemo_worker_stop)
                    # or (B) a short timeout (up to max(0.1, hop_s) seconds) to allow new audio to accumulate.
                    # If the stop event is set during the wait, we will exit the loop soon.
                    # If a TimeoutError occurs, it simply means more audio has not yet arrived.
                    # In either case, after waiting, we 'continue' to the next loop iteration
                    # so we can check again if more audio has arrived (i.e., if abs_end_sample is now sufficient).
                    try:
                        # The stop event is set when an external controller (such as session cleanup logic) signals
                        # the worker to shut down.
                        await asyncio.wait_for(
                            deps.nemo_worker_stop.wait(), timeout=max(0.1, hop_s)
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue  # Loop back and check if there is now enough audio for diarization
                # --- Slice ring buffer for the trailing window and run NeMo diarization (blocking) ---
                # We always read the most recent window so the fallback aligns with the latest audio
                # and produces absolute timestamps anchored to the stream.
                abs_start_sample = max(0, abs_end_sample - window_samples)
                samples = deps.ring_buffer.slice(abs_start_sample, abs_end_sample)
                pcm = (
                    bytes(samples.tobytes())
                    if samples is not None and len(samples) > 0
                    else b""
                )
                if pcm:
                    # Run in executor so we don't block the event loop; no lambda args needed
                    # here because we're in the same scope and pcm/timeout_s/max_speakers are
                    # read at call time.
                    diar_segments = await deps.loop.run_in_executor(
                        deps.executor,
                        lambda: diarize_pcm16(
                            pcm,
                            STT_SAMPLE_RATE_HZ,
                            timeout_s=timeout_s,
                            max_speakers=max_speakers,
                        ),
                    )
                    # Convert segment times to absolute stream seconds (same base as STT seg_abs_*
                    # in segment_builder) so downstream code can align with transcript segments.
                    base_s = abs_start_sample / float(STT_SAMPLE_RATE_HZ)
                    new_segments = [
                        (base_s + s.start_s, base_s + s.end_s, s.speaker_id)
                        for s in diar_segments
                    ]
                    deps.ctx.nemo_latest_segments = new_segments
                    # Append to rolling history and prune by retention so we don't grow unbounded.
                    # This history is used for overlap resolution and diagnostics downstream.
                    retention_s = getattr(
                        deps.ctx, "nemo_history_retention_s", 60.0
                    )
                    async with deps.ctx.nemo_history_lock:
                        deps.ctx.nemo_segments_history.extend(new_segments)
                        if deps.ctx.nemo_segments_history:
                            latest_end_s = max(
                                s[1] for s in deps.ctx.nemo_segments_history
                            )
                            cutoff_s = latest_end_s - retention_s
                            deps.ctx.nemo_segments_history = [
                                t
                                for t in deps.ctx.nemo_segments_history
                                if t[1] >= cutoff_s
                            ]
                    nemo_updated = getattr(deps.ctx, "nemo_updated_event", None)
                    if nemo_updated is not None:
                        nemo_updated.set()
                    for i, (start_s, end_s, speaker_id) in enumerate(deps.ctx.nemo_latest_segments):
                        logger.info(f"nemo_diar_segments: {i} {start_s} {end_s} {speaker_id} segments")
                    # --- Notify client with latest diarization segments (best-effort) ---
                    try:
                        await deps.websocket.send_json(
                            {
                                "type": MSG_STT_NEMO_DIAR_SEGMENTS,
                                "segments": [
                                    {
                                        "start_s": base_s + s.start_s,
                                        "end_s": base_s + s.end_s,
                                        "speaker_id": s.speaker_id,
                                    }
                                    for s in diar_segments
                                ],
                            }
                        )
                    except Exception as send_err:
                        logger.info(
                            "nemo_diar_segments send skipped: %s", send_err
                        )
            except Exception as e:
                if isinstance(e, TimeoutError):
                    continue
                logger.info(
                    "NeMo diarization worker error (ignored): %r", e
                )
            # Throttle: wait for stop signal or hop_s before next diarization run.
            try:
                await asyncio.wait_for(
                    deps.nemo_worker_stop.wait(), timeout=max(0.1, hop_s)
                )
            except asyncio.TimeoutError:
                continue


class SortformerTimelineWorker(BaseDiarizationWorker):
    """
    Legacy/compat: windowed timeline builder.
    Consumes sortformer_queue, runs NeMo diarization per window, updates
    speaker_timeline and spk_tracks. Retained for compatibility, but not main.
    """

    async def run(self, deps: Any) -> None:
        ok, _ = nemo_diarization_available()
        if not ok:
            return
        window_s = float(getattr(settings, "stt_nemo_diarization_window_s", 1.6))
        timeout_s = float(getattr(settings, "stt_nemo_diarization_timeout_s", 0.4))
        max_speakers = getattr(settings, "stt_nemo_diarization_max_speakers", 4)
        window_samples = max(1, int(window_s * STT_SAMPLE_RATE_HZ))
        buffer_chunks: list[tuple[bytes, int, int]] = []
        buffer_sample_count = 0  # 16-bit PCM: 2 bytes per sample, so len(chunk) // 2

        while not deps.nemo_worker_stop.is_set():
            # --- Drain queue: collect (chunk, start_sample, end_sample) until we have a full window ---
            # We buffer raw PCM chunks until we reach the configured window size, then diarize
            # that window as a batch to build a coarse timeline.
            try:
                item = deps.sortformer_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.05)
                continue
            if item is None:
                break
            chunk, start_sample, end_sample = item
            buffer_chunks.append((chunk, start_sample, end_sample))
            buffer_sample_count += len(chunk) // 2
            if buffer_sample_count < window_samples:
                continue

            window_start_sample = buffer_chunks[0][1]
            pcm = b"".join(c for c, _, _ in buffer_chunks)
            buffer_chunks.clear()
            buffer_sample_count = 0
            # Skip very short buffers; NeMo needs at least ~1s (32000 bytes at 16 kHz) for stable diarization.
            if len(pcm) < 32000:
                continue

            # --- Run NeMo diarization on the window (lambda default args capture current pcm/timeout/max_speakers) ---
            try:
                diar_segments = await deps.loop.run_in_executor(
                    deps.executor,
                    lambda p=pcm, to=timeout_s, ms=max_speakers: diarize_pcm16(
                        p, 16000, timeout_s=to, max_speakers=ms
                    ),
                )
            except Exception:
                continue

            # --- Convert NeMo segments (relative seconds) to DiarInterval (absolute sample indices) ---
            # NeMo returns relative time offsets; we translate to absolute samples so the timeline
            # aligns with the session's global sample index.
            intervals: list[DiarInterval] = []
            for s in diar_segments:
                start_samp = window_start_sample + int(s.start_s * 16000)
                end_samp = window_start_sample + int(s.end_s * 16000)
                # spk_conf could later hold per-segment model confidence; we default to 0.8 for now.
                spk_conf = 0.8
                intervals.append(
                    (start_samp, end_samp, s.speaker_id, spk_conf, OVERLAP_NONE)
                )

            # --- Under timeline_lock: extend speaker_timeline, update spk_tracks with clean speech, prune timeline ---
            # All timeline and track mutations happen under the same lock to keep speaker state consistent.
            async with deps.ctx.timeline_lock:
                deps.ctx.speaker_timeline.extend(intervals)
                for s in diar_segments:
                    if s.start_s >= s.end_s:
                        continue
                    start_byte = int(s.start_s * 16000 * 2)
                    end_byte = int(s.end_s * 16000 * 2)
                    if start_byte >= len(pcm) or end_byte > len(pcm):
                        continue
                    chunk = pcm[start_byte:end_byte]
                    # Skip segments shorter than 0.1s (3200 bytes); too little for a reliable embedding.
                    if len(chunk) < 3200:
                        continue
                    if deps.ctx.spk_tracks.get(s.speaker_id) is None:
                        deps.ctx.spk_tracks[s.speaker_id] = TrackState(
                            stable_label=f"{LABEL_UNKNOWN_PREFIX}{s.speaker_id}"
                        )
                    deps.ctx.spk_tracks[s.speaker_id].last_seen_sample = (
                        window_start_sample
                        + int(s.end_s * STT_SAMPLE_RATE_HZ)
                    )
                    deps.ctx.spk_tracks[s.speaker_id].append_clean_speech(chunk)

                # Prune timeline to a bounded length (by sample count) to avoid unbounded growth.
                max_samp = getattr(
                    deps.ctx,
                    "speaker_timeline_max_samples",
                    STT_SPEAKER_TIMELINE_MAX_SAMPLES_DEFAULT,
                )
                if deps.ctx.speaker_timeline:
                    min_start = max(
                        0, deps.ctx.speaker_timeline[-1][1] - max_samp
                    )
                    deps.ctx.speaker_timeline = [
                        t for t in deps.ctx.speaker_timeline if t[1] > min_start
                    ]

                # Collect tracks that still need embedding updates (not yet 3+, and have enough clean audio).
                # Built inside lock; embedding computation done outside lock to avoid blocking.
                to_compute = []
                for spk_id, track in list(deps.ctx.spk_tracks.items()):
                    if track.embedding_count >= 3:
                        continue
                    if len(track.clean_buffer) < STT_MIN_PCM_BYTES_2S:
                        continue
                    slice_start = len(track.clean_buffer) - STT_MIN_PCM_BYTES_2S
                    to_compute.append(
                        (spk_id, bytes(track.clean_buffer[slice_start:]))
                    )

            # --- Compute embeddings and update track embeddings (EMA); then resolve labels from embeddings ---
            # We compute embeddings outside the lock, then update EMA inside to reduce contention.
            for spk_id, pcm_slice in to_compute:
                try:
                    emb = await deps.loop.run_in_executor(
                        deps.executor,
                        lambda p=pcm_slice: compute_embedding_from_pcm_bytes(
                            p, STT_SAMPLE_RATE_HZ
                        ),
                    )
                except Exception:
                    continue
                if not emb or len(emb) != ECAPA_EMBEDDING_DIM:
                    continue
                async with deps.ctx.timeline_lock:
                    track = deps.ctx.spk_tracks.get(spk_id)
                    if not track:
                        continue
                    # Exponential moving average: blend new embedding with existing (alpha = weight for new).
                    alpha = 0.3
                    if track.track_embedding is None:
                        track.track_embedding = list(emb)
                        track.embedding_count = 1
                    else:
                        for i in range(len(track.track_embedding)):
                            track.track_embedding[i] = (
                                (1 - alpha) * track.track_embedding[i]
                                + alpha * emb[i]
                            )
                        track.track_embedding = l2_normalize(
                            track.track_embedding
                        ).tolist()
                        track.embedding_count = min(
                            track.embedding_count + 1, 10
                        )
                # Resolve anonymous speaker to a known user label using voice embeddings.
                update_track_label_from_embedding(deps.ctx, spk_id)

        logger.debug("Sortformer timeline worker exited")


@dataclass
class _FrameDecision:
    spk_id: str
    conf: float
    overlap_flag: str


class _NemoSegment(NamedTuple):
    start_sample: int
    end_sample: int
    speaker_id: str


class SortformerStreamingWorker(BaseDiarizationWorker):
    """
    Main live path: incremental streaming diarization driven by sortformer_queue.
    Consumes (chunk_bytes, start_sample, end_sample), accumulates to chunk_bytes,
    processes incrementally with per-session streaming diarizer, and updates
    speaker_timeline and nemo_latest_segments with continuity preservation.
    """

    def __init__(self, deps: Any) -> None:
        self.deps = deps
        self.ready = False
        self.init_error: Optional[str] = None

        ok, err = nemo_diarization_available()
        if not ok:
            self.init_error = err
            return

        # Initialize per-session streaming diarizer early (before first audio chunk).
        if deps.ctx.streaming_diarizer is None:
            streaming_diarizer = create_streaming_diarizer()
            if streaming_diarizer is None:
                self.init_error = "failed to create streaming diarizer"
                return
            deps.ctx.streaming_diarizer = streaming_diarizer
            deps.ctx.diar_abs_cursor_sample = None
            deps.ctx.diar_last_end_sample = None
            deps.ctx.diar_open_segment = None

        # Settings (resolved once at init)
        self.timeout_s = float(
            getattr(settings, "stt_nemo_diarization_timeout_s", 4.0)
        )
        self.max_speakers = getattr(
            settings, "stt_nemo_diarization_max_speakers", 4
        )
        self.max_backlog_s = float(
            getattr(settings, "stt_diarization_max_backlog_s", 3.5)
        )
        self.gap_reset_s = float(
            getattr(settings, "stt_diarization_gap_reset_s", 1.5)
        )
        self.hysteresis_k = int(
            getattr(settings, "stt_diarization_hysteresis_k", 2)
        )

        # Derived constants (from model config)
        # Keep these aligned to the model so frame/chunk boundaries match NeMo expectations.
        self.frame_bytes = get_frame_bytes()
        chunk_frames = getattr(deps.ctx.streaming_diarizer, "chunk_size", None)
        if not chunk_frames:
            chunk_frames = max(1, int(get_chunk_bytes() / self.frame_bytes))
        self.chunk_bytes = self.frame_bytes * int(chunk_frames)
        self.max_backlog_bytes = int(self.max_backlog_s * STT_SAMPLE_RATE_HZ * 2)
        self.gap_reset_samples = int(self.gap_reset_s * STT_SAMPLE_RATE_HZ)

        self.ready = True

    async def run(self, deps: Any) -> None:
        if not self.ready:
            logger.warning(
                "NeMo diarization unavailable: %s", self.init_error or "unknown"
            )
            return

        logger.info(
            "SortformerStreamingWorker start: chunk_bytes=%d (~%.2fs), max_backlog_s=%.1f, gap_reset_s=%.1f, hysteresis_k=%d",
            self.chunk_bytes,
            self.chunk_bytes / (2.0 * STT_SAMPLE_RATE_HZ),
            self.max_backlog_s,
            self.gap_reset_s,
            self.hysteresis_k,
        )

        # Buffer that holds raw PCM bytes not yet processed into a chunk.
        # diar_pending_base_sample tracks the absolute sample index of pending_pcm[0].
        pending_pcm = bytearray()
        in_flight_task: Optional[asyncio.Task] = None
        last_log_time = time.monotonic()
        reset_count = 0
        frames_processed = 0

        while not deps.nemo_worker_stop.is_set():
            # Pull next chunk tuple
            try:
                item = deps.sortformer_queue.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue

            if item is None:
                break

            pcm_chunk, start_sample, end_sample = item
            if not pcm_chunk:
                logger.warning("!!!!!!!!!!!!SortformerStreamingWorker: pcm_chunk is None")
                continue

            # Gap detection against last received chunk:
            # We need this to handle audio stream discontinuities, such as network pauses, dropped audio, or gaps in incoming chunks.
            # If there is an unexpected gap between the end sample of the previous chunk and the start sample of the current chunk
            # (i.e. if audio samples are missing in the sequence), then the diarization model's internal recurrent state
            # will be misaligned with the real audio timeline. To avoid this, we detect such gaps and reset both the audio
            # buffering and the diarization state, ensuring subsequent processing is correct and stable.
            if deps.ctx.diar_last_end_sample is not None:
                gap_samples = start_sample - deps.ctx.diar_last_end_sample
                if gap_samples > self.gap_reset_samples:
                    logger.warning(
                        "Diarization discontinuity: gap detected (%.2fs). Reset streaming state.",
                        gap_samples / STT_SAMPLE_RATE_HZ
                    )
                    await self._reset_session_streaming_state(deps, pending_pcm)
                    reset_count += 1

            deps.ctx.diar_last_end_sample = end_sample

            # Initialize pending base sample when buffer is empty
            if deps.ctx.diar_pending_base_sample is None or len(pending_pcm) == 0:
                deps.ctx.diar_pending_base_sample = start_sample

            # Enforce strict byte↔sample alignment for out-of-order or overlapping packets.
            # This keeps diarization sample indices consistent with the actual audio timebase,
            # even when chunks arrive late or overlap previously buffered data.
            expected_next = deps.ctx.diar_pending_base_sample + (len(pending_pcm) // 2)
            if start_sample > expected_next:
                # Gap inside pending buffer: reset and realign
                gap_samples = start_sample - expected_next
                if gap_samples > self.gap_reset_samples:
                    logger.warning(
                        "Pending base gap detected (%.2fs). Reset streaming state.",
                        gap_samples / STT_SAMPLE_RATE_HZ
                    )
                await self._reset_session_streaming_state(deps, pending_pcm)
                reset_count += 1
                deps.ctx.diar_pending_base_sample = start_sample
                expected_next = start_sample
            elif start_sample < expected_next:
                # Overlap or out-of-order: trim overlapping prefix
                overlap_samples = expected_next - start_sample
                overlap_bytes = overlap_samples * 2
                if overlap_bytes >= len(pcm_chunk):
                    # Entire chunk overlaps buffered data; skip
                    continue
                pcm_chunk = pcm_chunk[overlap_bytes:]
                start_sample = expected_next

            # Initialize cursor from pending base
            if deps.ctx.diar_abs_cursor_sample is None:
                deps.ctx.diar_abs_cursor_sample = deps.ctx.diar_pending_base_sample

            # Append bytes to pending buffer
            pending_pcm.extend(pcm_chunk)

            # Backlog policy: trim if exceeds max_backlog_bytes.
            # We drop old audio, reset streaming state, and realign the cursor to prevent drift.
            # This prevents the streaming diarizer from accumulating excessive latency.
            if len(pending_pcm) > self.max_backlog_bytes:
                keep_bytes = int(1.5 * STT_SAMPLE_RATE_HZ * 2)  # Keep last 1.5s
                # Align to frame boundary
                keep_bytes = (keep_bytes // self.frame_bytes) * self.frame_bytes
                if keep_bytes < len(pending_pcm):
                    dropped_bytes = len(pending_pcm) - keep_bytes
                    kept_samples = keep_bytes // 2
                    del pending_pcm[:dropped_bytes]
                    logger.warning(
                        "Backlog overflow: dropped %d bytes (%.2fs). Reset streaming state.",
                        dropped_bytes, (dropped_bytes / 2) / STT_SAMPLE_RATE_HZ
                    )
                    await self._reset_session_streaming_state(deps, pending_pcm)
                    # Realign cursor and pending base
                    if deps.ctx.diar_last_end_sample is not None:
                        deps.ctx.diar_abs_cursor_sample = (
                            deps.ctx.diar_last_end_sample - kept_samples
                        )
                        deps.ctx.diar_pending_base_sample = (
                            deps.ctx.diar_last_end_sample - kept_samples
                        )
                    elif deps.ctx.diar_pending_base_sample is not None:
                        deps.ctx.diar_pending_base_sample += kept_samples
                    reset_count += 1

            # Process chunks while enough bytes are buffered.
            # We only run one in-flight step to avoid piling up executor work
            # and to keep diarizer state updates serialized.
            while len(pending_pcm) >= self.chunk_bytes:
                # Don't start another step if one is in flight
                if in_flight_task is not None and not in_flight_task.done():
                    break

                # Consume exactly chunk_bytes
                # We're consuming exactly chunk_bytes for this diarization step.
                # chunk_bytes is typically (chunk_len * frame_bytes), i.e., (6 * 320) = 1920 bytes (or 0.48s).
                # This slice DOES NOT include left/right context; any context
                # handling is performed inside the diarizer model or its bufferer.
                # If you want to include left/right context, you'd need to adjust indices
                # here or rely on the model's buffer.
                step_pcm = bytes(pending_pcm[: self.chunk_bytes])
                del pending_pcm[: self.chunk_bytes]

                step_start_sample = deps.ctx.diar_pending_base_sample
                step_end_sample = step_start_sample + (self.chunk_bytes // 2)
                deps.ctx.diar_abs_cursor_sample = step_end_sample
                deps.ctx.diar_pending_base_sample = step_end_sample

                # Launch streaming step (off event loop).
                # This keeps the event loop responsive while model inference runs in the executor,
                # and ensures we maintain a single ordered stream of updates.
                in_flight_task = asyncio.create_task(
                    self._run_one_streaming_step(
                        deps=deps,
                        pcm=step_pcm,
                        step_start_sample=step_start_sample,
                        step_end_sample=step_end_sample,
                        timeout_s=self.timeout_s,
                        max_speakers=self.max_speakers,
                        hysteresis_k=self.hysteresis_k,
                    )
                )
                frames_processed += (self.chunk_bytes // self.frame_bytes)

            # Rate-limited logging
            now = time.monotonic()
            if now - last_log_time >= 5.0:
                backlog_s = len(pending_pcm) / (2.0 * STT_SAMPLE_RATE_HZ)
                logger.debug(
                    "Streaming worker: backlog=%.2fs, frames_processed=%d, resets=%d",
                    backlog_s, frames_processed, reset_count
                )
                last_log_time = now

            # Small yield to keep loop responsive
            await asyncio.sleep(0)

        # Ensure last in-flight step is flushed (best-effort).
        # This reduces the chance of dropping the last diarization update on shutdown.
        if in_flight_task is not None and not in_flight_task.done():
            try:
                await asyncio.wait_for(in_flight_task, timeout=1.0)
            except asyncio.TimeoutError:
                in_flight_task.cancel()
            except asyncio.CancelledError:
                pass

        # Flush any open segment at shutdown so the tail is not lost.
        # We close the last open segment at the most recent cursor/end sample.
        await self._flush_open_segment_on_shutdown(deps)

        logger.info("SortformerStreamingWorker exited")

    async def _reset_session_streaming_state(self, deps: Any, pending_pcm: bytearray) -> None:
        """Reset session streaming state on discontinuity or backlog trim."""
        pending_pcm.clear()
        deps.ctx.diar_abs_cursor_sample = None
        deps.ctx.diar_pending_base_sample = None
        deps.ctx.diar_open_segment = None
        # Reset diarization speaker state: spk ids can be re-used after a reset.
        deps.ctx.speaker_timeline.clear()
        deps.ctx.spk_tracks.clear()
        deps.ctx.nemo_speaker_id_to_label.clear()
        deps.ctx.nemo_speaker_id_to_tag.clear()
        deps.ctx.nemo_label_attempted.clear()
        deps.ctx.nemo_next_tag = 1

        if deps.ctx.streaming_diarizer is not None:
            try:
                async with deps.ctx.streaming_diar_lock:
                    deps.ctx.streaming_diarizer.reset_state()
            except Exception as e:
                logger.debug("Error resetting streaming diarizer state: %s", e)

    async def _run_one_streaming_step(
        self,
        deps: Any,
        pcm: bytes,
        step_start_sample: int,
        step_end_sample: int,
        timeout_s: float,
        max_speakers: int,
        hysteresis_k: int,
    ) -> None:
        """One diarization step for exactly chunk_bytes of audio."""
        t0 = time.monotonic()

        # Run streaming step (with per-session lock) to protect per-session state.
        # The diarizer maintains internal state across steps, so access must be serialized.
        try:
            async with deps.ctx.streaming_diar_lock:
                # Choose efficient stepping method if the diarizer has "step_chunk" (chunk-at-a-time) for exact chunk input;
                # otherwise fallback to the default "step" method (general, supports arbitrary-length audio).
                if hasattr(deps.ctx.streaming_diarizer, "step_chunk"):
                    frame_probs = await deps.loop.run_in_executor(
                        deps.executor,
                        lambda: deps.ctx.streaming_diarizer.step_chunk(pcm),
                    )
                else:
                    frame_probs = await deps.loop.run_in_executor(
                        deps.executor,
                        lambda: deps.ctx.streaming_diarizer.step(pcm),
                    )
        except Exception as e:
            logger.warning("stream step failed: %r", e)
            return

        elapsed = time.monotonic() - t0
        if timeout_s > 0 and elapsed > timeout_s:
            logger.warning("nemo streaming step slow %.2fs (timeout %.2fs)", elapsed, timeout_s)

        if not frame_probs:
            return

        # Convert frame probabilities to speaker labels with hysteresis to reduce churn.
        # This smooths short-lived speaker flips and reduces false transitions.
        frame_labels = self._apply_hysteresis_to_frames(
            frame_probs, max_speakers, hysteresis_k, deps.ctx
        )

        # Build intervals preserving continuity across steps.
        # Open segments are carried forward via ctx.diar_open_segment to keep speaker runs intact.
        intervals, nemo_segments = self._build_intervals_from_frames(
            frame_labels,
            step_start_sample,
            step_end_sample,
            deps.ctx,
        )

        if not intervals:
            return

        # Update speaker_timeline and spk_tracks
        # Timeline mutations and track updates happen under a lock to keep state consistent.
        async with deps.ctx.timeline_lock:
            deps.ctx.speaker_timeline.extend(intervals)

            # Update spk_tracks conservatively (only stable segments >= 0.3s).
            # We also gate on reliable horizon and avoid overlap segments for clean embeddings.
            reliable_end_sample = diarization_reliable_end_sample(
                deps.ring_buffer.total_samples,
                getattr(settings, "stt_diarization_reliable_lag_ms", 1200),
            )
            track_update_stats = {
                "total": 0,
                "too_short": 0,
                "past_reliable": 0,
                "overlap": 0,
                "updated": 0,
            }
            duration_min: Optional[float] = None
            duration_max: Optional[float] = None
            end_sample_min: Optional[int] = None
            end_sample_max: Optional[int] = None
            for start_samp, end_samp, spk_id, conf, overlap_flag in intervals:
                track_update_stats["total"] += 1
                duration_s = (end_samp - start_samp) / STT_SAMPLE_RATE_HZ
                if duration_min is None or duration_s < duration_min:
                    duration_min = duration_s
                if duration_max is None or duration_s > duration_max:
                    duration_max = duration_s
                if end_sample_min is None or end_samp < end_sample_min:
                    end_sample_min = end_samp
                if end_sample_max is None or end_samp > end_sample_max:
                    end_sample_max = end_samp
                if duration_s < 0.6:  # Skip short segments
                    track_update_stats["too_short"] += 1
                    continue
                if end_samp > reliable_end_sample:
                    track_update_stats["past_reliable"] += 1
                    continue
                if overlap_flag != OVERLAP_NONE:
                    track_update_stats["overlap"] += 1
                    continue

                # Extract PCM for this interval
                start_byte = (start_samp - step_start_sample) * 2
                end_byte = (end_samp - step_start_sample) * 2
                if start_byte < 0 or end_byte > len(pcm):
                    continue
                chunk = pcm[start_byte:end_byte]
                if len(chunk) < 3200:  # Skip very short chunks
                    continue

                if deps.ctx.spk_tracks.get(spk_id) is None:
                    deps.ctx.spk_tracks[spk_id] = TrackState(
                        stable_label=f"{LABEL_UNKNOWN_PREFIX}{spk_id}"
                    )
                deps.ctx.spk_tracks[spk_id].last_seen_sample = end_samp
                deps.ctx.spk_tracks[spk_id].append_clean_speech(chunk)
                track_update_stats["updated"] += 1

            # Prune timeline
            max_samp = getattr(
                deps.ctx,
                "speaker_timeline_max_samples",
                STT_SPEAKER_TIMELINE_MAX_SAMPLES_DEFAULT,
            )
            if deps.ctx.speaker_timeline:
                min_start = max(
                    0, deps.ctx.speaker_timeline[-1][1] - max_samp
                )
                deps.ctx.speaker_timeline = [
                    t for t in deps.ctx.speaker_timeline if t[1] > min_start
                ]

            # Collect tracks needing embedding updates
            to_compute = []
            for spk_id, track in list(deps.ctx.spk_tracks.items()):
                if track.embedding_count >= 3:
                    continue
                if len(track.clean_buffer) < STT_MIN_PCM_BYTES_2S:
                    continue
                slice_start = len(track.clean_buffer) - STT_MIN_PCM_BYTES_2S
                to_compute.append(
                    (spk_id, bytes(track.clean_buffer[slice_start:]))
                )

        # Compute embeddings outside lock
        # Embedding inference is CPU-heavy; we keep lock scope minimal.
        for spk_id, pcm_slice in to_compute:
            try:
                emb = await deps.loop.run_in_executor(
                    deps.executor,
                    lambda p=pcm_slice: compute_embedding_from_pcm_bytes(
                        p, STT_SAMPLE_RATE_HZ
                    ),
                )
            except Exception:
                continue
            if not emb or len(emb) != ECAPA_EMBEDDING_DIM:
                continue
            async with deps.ctx.timeline_lock:
                track = deps.ctx.spk_tracks.get(spk_id)
                if not track:
                    continue
                alpha = 0.3
                if track.track_embedding is None:
                    track.track_embedding = list(emb)
                    track.embedding_count = 1
                else:
                    for i in range(len(track.track_embedding)):
                        track.track_embedding[i] = (
                            (1 - alpha) * track.track_embedding[i]
                            + alpha * emb[i]
                        )
                    track.track_embedding = l2_normalize(
                        track.track_embedding
                    ).tolist()
                    track.embedding_count = min(
                        track.embedding_count + 1, 10
                    )
            update_track_label_from_embedding(deps.ctx, spk_id)

        # Update nemo_latest_segments (absolute seconds) for downstream overlap resolution.
        # These segments drive overlap logic and UI previews.
        frame_len_s = 0.08
        nemo_segments_abs = [
            (start_samp / STT_SAMPLE_RATE_HZ, end_samp / STT_SAMPLE_RATE_HZ, spk_id)
            for start_samp, end_samp, spk_id in nemo_segments
        ]
        deps.ctx.nemo_latest_segments = nemo_segments_abs

        # Append to history and prune
        # History is bounded to avoid unbounded memory growth.
        retention_s = getattr(deps.ctx, "nemo_history_retention_s", 60.0)
        async with deps.ctx.nemo_history_lock:
            deps.ctx.nemo_segments_history.extend(nemo_segments_abs)
            if deps.ctx.nemo_segments_history:
                latest_end_s = max(s[1] for s in deps.ctx.nemo_segments_history)
                cutoff_s = latest_end_s - retention_s
                deps.ctx.nemo_segments_history = [
                    t for t in deps.ctx.nemo_segments_history if t[1] >= cutoff_s
                ]

        # Notify listeners
        nemo_updated = getattr(deps.ctx, "nemo_updated_event", None)
        if nemo_updated is not None:
            nemo_updated.set()

        # Send to client (best effort)
        try:
            await deps.websocket.send_json(
                {
                    "type": MSG_STT_NEMO_DIAR_SEGMENTS,
                    "segments": [
                        {"start_s": s0, "end_s": s1, "speaker_id": spk}
                        for (s0, s1, spk) in nemo_segments_abs
                    ],
                    "meta": {
                        "step_elapsed_s": round(elapsed, 3),
                    },
                }
            )
        except Exception:
            pass

    def _apply_hysteresis_to_frames(
        self,
        frame_probs: list,
        max_speakers: int,
        hysteresis_k: int,
        ctx: Any,
    ) -> list[_FrameDecision]:
        """Apply hysteresis to frame probabilities, returning list of frame decisions."""
        if not frame_probs:
            return []

        # Get or initialize hysteresis state (per-session) to stabilize speaker switching.
        # We keep a stable speaker and a candidate speaker that must persist for K frames.
        if not hasattr(ctx, "_hysteresis_state"):
            ctx._hysteresis_state = {
                "stable_spk": None,
                "candidate_spk": None,
                "candidate_count": 0,
            }

        state = ctx._hysteresis_state
        decisions: list[_FrameDecision] = []

        min_conf = float(getattr(settings, "stt_diarization_overlap_min_conf", 0.55))
        min_margin = float(getattr(settings, "stt_diarization_overlap_margin", 0.15))

        total_frames = 0
        margin_below = 0
        conf_below = 0
        candidate_rejects = 0
        switch_count = 0
        unique_spk: set[str] = set()
        max_prob_min: Optional[float] = None
        max_prob_max: Optional[float] = None
        margin_min: Optional[float] = None
        margin_max: Optional[float] = None

        for frame_prob in frame_probs:
            if isinstance(frame_prob, np.ndarray):
                probs = frame_prob[:max_speakers]
                spk_idx = int(np.argmax(probs))
                max_prob = float(probs[spk_idx]) if len(probs) else 0.0
                if len(probs) > 1:
                    sorted_probs = np.partition(probs, -2)
                    second_prob = float(sorted_probs[-2])
                else:
                    second_prob = 0.0
                margin = max_prob - second_prob
            else:
                spk_idx = 0
                max_prob = 0.0
                margin = 0.0
            spk_id = f"spk_{spk_idx}"
            total_frames += 1
            unique_spk.add(spk_id)
            if max_prob_min is None or max_prob < max_prob_min:
                max_prob_min = max_prob
            if max_prob_max is None or max_prob > max_prob_max:
                max_prob_max = max_prob
            if margin_min is None or margin < margin_min:
                margin_min = margin
            if margin_max is None or margin > margin_max:
                margin_max = margin
            if max_prob < min_conf:
                conf_below += 1
            if margin < min_margin:
                margin_below += 1

            # Overlap/uncertainty detection from frame probabilities.
            # This flags low-confidence or low-margin frames for downstream handling.
            overlap_flag = OVERLAP_NONE
            if max_prob < min_conf or margin < min_margin:
                overlap_flag = POSSIBLE_OVERLAP
            # 0.75 here acts as a stricter threshold for 'definite' speaker overlap—frames with even lower max confidence
            # than the usual minimum (min_conf) are more aggressively flagged as definitely overlapped.
            if max_prob < (min_conf * 0.75):
                overlap_flag = DEFINITE_OVERLAP

            if state["stable_spk"] is None:
                state["stable_spk"] = spk_id
                state["candidate_spk"] = None
                state["candidate_count"] = 0
                decisions.append(
                    _FrameDecision(
                        spk_id=spk_id, conf=max_prob, overlap_flag=overlap_flag
                    )
                )
                continue

            if spk_id == state["stable_spk"]:
                state["candidate_spk"] = None
                state["candidate_count"] = 0
                decisions.append(
                    _FrameDecision(
                        spk_id=state["stable_spk"],
                        conf=max_prob,
                        overlap_flag=overlap_flag,
                    )
                )
                continue

            # New candidate: require K consecutive frames to switch speakers.
            # This hysteresis prevents rapid toggling when probabilities are noisy.
            if margin < min_margin:
                # Don't consider a new speaker when the model is unsure (low margin).
                state["candidate_spk"] = None
                state["candidate_count"] = 0
                candidate_rejects += 1
                decisions.append(
                    _FrameDecision(
                        spk_id=state["stable_spk"],
                        conf=max_prob,
                        overlap_flag=overlap_flag,
                    )
                )
                continue

            if state["candidate_spk"] != spk_id:
                state["candidate_spk"] = spk_id
                state["candidate_count"] = 1
                decisions.append(
                    _FrameDecision(
                        spk_id=state["stable_spk"],
                        conf=max_prob,
                        overlap_flag=overlap_flag,
                    )
                )  # Keep current until confirmed
                continue

            state["candidate_count"] += 1
            if state["candidate_count"] >= max(1, hysteresis_k):
                prev_stable = state["stable_spk"]
                state["stable_spk"] = spk_id
                state["candidate_spk"] = None
                state["candidate_count"] = 0
                if prev_stable != state["stable_spk"]:
                    switch_count += 1
            decisions.append(
                _FrameDecision(
                    spk_id=state["stable_spk"],
                    conf=max_prob,
                    overlap_flag=overlap_flag,
                )
            )

        return decisions

    def _build_intervals_from_frames(
        self,
        frame_labels: list[_FrameDecision],
        step_start_sample: int,
        step_end_sample: int,
        ctx: Any,
    ) -> tuple[list[DiarInterval], list[_NemoSegment]]:
        """
        Build DiarInterval entries and nemo_segments from frame labels.
        Preserves continuity across steps by merging with open segment.
        """
        frame_bytes = get_frame_bytes()
        frame_samples = frame_bytes // 2
        intervals: list[DiarInterval] = []
        nemo_segments: list[_NemoSegment] = []

        if not frame_labels:
            # Close open segment if any. This ensures we don't leave a dangling segment
            # when no frames arrive for a step.
            if ctx.diar_open_segment is not None:
                open_start, open_spk, open_flag, open_conf_sum, open_frames = (
                    ctx.diar_open_segment
                )
                conf = open_conf_sum / max(1, open_frames)
                intervals.append(
                    DiarInterval(
                        # open_start: sample index where the open segment started (from previous chunk)
                        # step_start_sample: sample index where this step (current chunk) starts; close segment at this sample
                        # open_spk: speaker id of the open segment
                        # conf: average confidence over the open segment
                        # open_flag: overlap flag ("NONE", "POSSIBLE_OVERLAP", or "DEFINITE_OVERLAP")
                        open_start, step_start_sample, open_spk, conf, open_flag
                    )
                )
                nemo_segments.append(
                    # _NemoSegment(start_s, end_s, speaker_id)
                    # start_s: sample index where the open segment started
                    # end_s: sample index where this step (current chunk) ends (segment closed here)
                    # speaker_id: speaker id of the open segment
                    _NemoSegment(open_start, step_start_sample, open_spk)
                )
                ctx.diar_open_segment = None
            return intervals, nemo_segments

        current_spk = None
        current_start = None
        current_flag = OVERLAP_NONE
        current_conf_sum = 0.0
        current_frames = 0

        # Handle open segment from previous step (continuity across chunks).
        # If the first frame matches the open segment, we continue it; otherwise we close it.
        if ctx.diar_open_segment is not None:
            open_start, open_spk, open_flag, open_conf_sum, open_frames = (
                ctx.diar_open_segment
            )
            if (
                frame_labels[0].spk_id == open_spk
                and frame_labels[0].overlap_flag == open_flag
            ):
                # Continue open segment
                current_spk = open_spk
                current_start = open_start
                current_flag = open_flag
                current_conf_sum = open_conf_sum
                current_frames = open_frames
            else:
                # Close open segment and start new one
                # Append a finalized diarization interval representing the open segment.
                # DiarInterval captures the segment's sample indices (open_start to step_start_sample),
                # the speaker ID (open_spk), the average confidence over the segment, and the overlap flag.
                intervals.append(
                    DiarInterval(
                        open_start,                     # Absolute index where the open segment began.
                        step_start_sample,              # Absolute index where this step (current chunk) begins; marks end of the segment.
                        open_spk,                       # ID of the speaker for this segment.
                        (open_conf_sum / max(1, open_frames)),  # Average confidence over the segment's frames.
                        open_flag,                      # Type of overlap, if any (e.g., NONE, POSSIBLE_OVERLAP, DEFINITE_OVERLAP).
                    )
                )
                # Add a _NemoSegment so downstream code can access simple start/end indices and spk_id.
                # _NemoSegment encapsulates the low-level segment boundaries and speaker ID in a compact, internal format.
                nemo_segments.append(
                    _NemoSegment(open_start, step_start_sample, open_spk)
                )
                current_spk = frame_labels[0].spk_id
                current_start = step_start_sample
                current_flag = frame_labels[0].overlap_flag
                current_conf_sum = frame_labels[0].conf
                current_frames = 1
            ctx.diar_open_segment = None
        # Process frames and close segments on speaker/overlap flag changes.
        # Each time the speaker or overlap flag changes, we finalize the previous segment.
        for i, decision in enumerate(frame_labels):
            frame_start = step_start_sample + i * frame_samples
            frame_end = frame_start + frame_samples

            if current_spk is None:
                current_spk = decision.spk_id
                current_start = frame_start
                current_flag = decision.overlap_flag
                current_conf_sum = decision.conf
                current_frames = 1
                continue

            if (
                decision.spk_id != current_spk
                or decision.overlap_flag != current_flag
            ):
                # Close current segment
                intervals.append(
                    DiarInterval(
                        current_start,
                        frame_start,
                        current_spk,
                        (current_conf_sum / max(1, current_frames)),
                        current_flag,
                    )
                )
                nemo_segments.append(
                    _NemoSegment(current_start, frame_start, current_spk)
                )
                current_spk = decision.spk_id
                current_start = frame_start
                current_flag = decision.overlap_flag
                current_conf_sum = decision.conf
                current_frames = 1
                logger.info(f"!!!!!!!!CLOSING SEGMENT: {current_spk} {current_start} {current_flag} {current_conf_sum} {current_frames}")
            else:
                current_conf_sum += decision.conf
                current_frames += 1

        # Leave last segment open so the next step can extend it.
        # This keeps speaker runs continuous across chunk boundaries.
        if current_spk is not None and current_start is not None:
            # Keep last segment open for continuity across steps
            ctx.diar_open_segment = (
                current_start,
                current_spk,
                current_flag,
                current_conf_sum,
                current_frames,
            )

        return intervals, nemo_segments

    async def _flush_open_segment_on_shutdown(self, deps: Any) -> None:
        """Close any open segment at shutdown to avoid losing the tail."""
        if deps.ctx.diar_open_segment is None:
            return
        open_start, open_spk, open_flag, open_conf_sum, open_frames = (
            deps.ctx.diar_open_segment
        )
        if deps.ctx.diar_abs_cursor_sample is not None:
            end_sample = deps.ctx.diar_abs_cursor_sample
        elif deps.ctx.diar_last_end_sample is not None:
            end_sample = deps.ctx.diar_last_end_sample
        else:
            end_sample = deps.ring_buffer.total_samples
        if end_sample <= open_start:
            deps.ctx.diar_open_segment = None
            return

        conf = open_conf_sum / max(1, open_frames)
        interval = (open_start, end_sample, open_spk, conf, open_flag)
        nemo_seg = (open_start / STT_SAMPLE_RATE_HZ, end_sample / STT_SAMPLE_RATE_HZ, open_spk)

        async with deps.ctx.timeline_lock:
            deps.ctx.speaker_timeline.append(interval)
        async with deps.ctx.nemo_history_lock:
            deps.ctx.nemo_segments_history.append(nemo_seg)
            retention_s = getattr(deps.ctx, "nemo_history_retention_s", 60.0)
            if deps.ctx.nemo_segments_history:
                latest_end_s = max(s[1] for s in deps.ctx.nemo_segments_history)
                cutoff_s = latest_end_s - retention_s
                deps.ctx.nemo_segments_history = [
                    t for t in deps.ctx.nemo_segments_history if t[1] >= cutoff_s
                ]
        deps.ctx.nemo_latest_segments = [nemo_seg]
        nemo_updated = getattr(deps.ctx, "nemo_updated_event", None)
        if nemo_updated is not None:
            nemo_updated.set()
        deps.ctx.diar_open_segment = None


class NeMoLabeler:
    """Resolves NeMo anonymous speakers and voice-id segments; sends speaker_resolved messages."""

    def __init__(
        self,
        speaker_matcher: Any,
        message_builder: Any,
        audio_processor: Any,
    ):
        self.speaker_matcher = speaker_matcher
        self.message_builder = message_builder
        self.audio_processor = audio_processor

    async def label_then_send(
        self,
        deps: Any,
        pcm_copy: bytes,
        segment_id: int,
        nemo_speaker_id: str,
        segment_start_ms: Optional[int] = None,
    ) -> bool:
        """Resolve an anonymous NeMo speaker to a known user via voice embedding; send speaker_resolved if matched."""
        task = asyncio.current_task()
        deps.ctx.pending_nemo_label_tasks.add(task)
        matched_user_id: Optional[str] = None
        try:
            # Compute segment embedding off the event loop (CPU-heavy).
            segment_embedding = await deps.loop.run_in_executor(
                deps.executor,
                self.audio_processor.compute_embedding_sync,
                pcm_copy,
            )
            speaker_label_before: Optional[str] = None
            best_score_pct: Optional[float] = None
            second_score_pct: Optional[float] = None
            score_margin_pct: Optional[float] = None
            best_user_suffix: Optional[str] = None
            second_user_suffix: Optional[str] = None
            all_scores: list[dict] = []
            # Under lock: match to known user and persist nemo_speaker_id -> user_id for this session.
            # The lock protects shared label maps to avoid races between concurrent label tasks.
            async with deps.ctx.nemo_label_lock:
                speaker_label_before = deps.ctx.nemo_speaker_id_to_label.get(
                    nemo_speaker_id
                )
                best_label = None
                best_score = 0.0
                second_score = 0.0
                if segment_embedding and len(segment_embedding) == ECAPA_EMBEDDING_DIM:
                    best_label, best_score, _, second_score = (
                        self.speaker_matcher.score_known_voice_embeddings(
                            deps.ctx, segment_embedding
                        )
                    )
                    scores_list = []
                    for uid, emb in deps.ctx.voice_embeddings.items():
                        if len(emb) != len(segment_embedding):
                            continue
                        score = cosine_similarity(segment_embedding, emb)
                        scores_list.append(
                            (
                                f"user:{uid[-6:]}" if len(uid) >= 6 else uid,
                                score,
                            )
                        )
                    scores_list.sort(key=lambda x: x[1], reverse=True)
                    all_scores = [
                        {
                            "label": speaker_display_name(deps.ctx.session_id, label),
                            "score_pct": round(max(0.0, s) * 100, 1),
                        }
                        for label, s in scores_list
                    ]
                    if len(scores_list) >= 1:
                        first_label = scores_list[0][0]
                        best_user_suffix = (
                            first_label[5:]
                            if first_label.startswith("user:")
                            else None
                        )
                        best_score_pct = round(max(0.0, scores_list[0][1]) * 100, 1)
                    if len(scores_list) >= 2:
                        second_label = scores_list[1][0]
                        second_user_suffix = (
                            second_label[5:]
                            if second_label.startswith("user:")
                            else None
                        )
                        second_score_pct = round(
                            max(0.0, scores_list[1][1]) * 100, 1
                        )
                        score_margin_pct = round(
                            (scores_list[0][1] - scores_list[1][1]) * 100, 1
                        )
                matched_user_id = self.speaker_matcher.match_known_user_only(
                    deps.ctx, segment_embedding
                )
                if matched_user_id:
                    deps.ctx.nemo_speaker_id_to_label[
                        nemo_speaker_id
                    ] = matched_user_id
            # If we matched, send speaker_resolved to client and drop segment audio from backing store.
            # We free backing audio once resolved to avoid retaining large PCM buffers.
            if matched_user_id:
                try:
                    payload = self.message_builder.build_speaker_resolved_payload(
                        deps.ctx.session_id,
                        segment_id=segment_id,
                        speaker_label=matched_user_id,
                        speaker_source=SPEAKER_SOURCE_NEMO,
                        best_score_pct=best_score_pct,
                        second_score_pct=second_score_pct,
                        score_margin_pct=score_margin_pct,
                        best_user_suffix=best_user_suffix,
                        second_user_suffix=second_user_suffix,
                        all_scores=all_scores,
                        nemo_speaker_id=nemo_speaker_id,
                        speaker_label_before=speaker_display_name(
                            deps.ctx.session_id,
                            speaker_label_before,
                            nemo_speaker_id=nemo_speaker_id,
                        )
                        if speaker_label_before
                        else None,
                        speaker_label_after=matched_user_id,
                        speaker_change_at_ms=segment_start_ms,
                    )
                    await deps.websocket.send_json(payload)
                    deps.ctx.segment_audio_backing.pop(segment_id, None)
                    deps.ctx.segments_resolved_count += 1
                except Exception as send_err:
                    logger.debug(
                        "speaker_resolved send skipped (websocket closed?): %s",
                        send_err,
                    )
        finally:
            deps.ctx.pending_nemo_label_tasks.discard(task)
        return bool(matched_user_id)

    async def voice_id_then_send(
        self,
        deps: Any,
        pcm_copy: bytes,
        segment_id: int,
        seg_tag: Optional[int],
        nemo_speaker_id: Optional[str] = None,
        start_ms: Optional[int] = None,
    ) -> None:
        """Compute segment embedding, match to speaker (voice-id or Google tag), send stt.speaker_resolved."""
        task = asyncio.current_task()
        deps.ctx.pending_voice_id_tasks.add(task)
        try:
            segment_embedding = await deps.loop.run_in_executor(
                deps.executor,
                self.audio_processor.compute_embedding_sync,
                pcm_copy,
            )
            # Match segment to a speaker label (voice-id or Google diarization tag); optionally
            # append to user_segment_embeddings for centroid updates, capped per user.
            # This enables online centroid refinement without unbounded growth.
            async with deps.ctx.voice_id_lock:
                seg_speaker_label = self.speaker_matcher.match_speaker_label(
                    seg_tag, deps.ctx, segment_embedding
                )
                if (
                    seg_speaker_label in deps.ctx.voice_embeddings
                    and segment_embedding is not None
                    and len(segment_embedding) == ECAPA_EMBEDDING_DIM
                ):
                    deps.ctx.user_segment_embeddings.setdefault(
                        seg_speaker_label, []
                    ).append(list(segment_embedding))
                    lst = deps.ctx.user_segment_embeddings[seg_speaker_label]
                    max_seg = getattr(
                        settings,
                        "stt_voice_centroid_max_segments_per_user",
                        50,
                    )
                    while len(lst) > max_seg:
                        lst.pop(0)

            # --- Build confidence/margin and all_scores for payload (best, second, margin, full list) ---
            # We compute full similarity scores to display top candidates and margins in the UI.
            best_score_pct = None
            second_score_pct = None
            score_margin_pct = None
            best_user_suffix = None
            second_user_suffix = None
            all_scores: list[dict] = []
            if (
                segment_embedding
                and len(segment_embedding) == ECAPA_EMBEDDING_DIM
            ):
                scores_list = []
                for uid, emb in deps.ctx.voice_embeddings.items():
                    if len(emb) != len(segment_embedding):
                        continue
                    score = cosine_similarity(segment_embedding, emb)
                    scores_list.append(
                        (
                            f"user:{uid[-6:]}" if len(uid) >= 6 else uid,
                            score,
                        )
                    )
                for label, emb in deps.ctx.unknown_voice_embeddings.items():
                    if len(emb) != len(segment_embedding):
                        continue
                    score = cosine_similarity(segment_embedding, emb)
                    scores_list.append((label, score))
                scores_list.sort(key=lambda x: x[1], reverse=True)
                all_scores = [
                    {
                        "label": speaker_display_name(deps.ctx.session_id, label),
                        "score_pct": round(max(0.0, s) * 100, 1),
                    }
                    for label, s in scores_list
                ]
                if len(scores_list) >= 1:
                    first_label = scores_list[0][0]
                    best_user_suffix = (
                        first_label[5:]
                        if first_label.startswith("user:")
                        else None
                    )
                    raw_best = scores_list[0][1]
                    best_score_pct = round(max(0.0, raw_best) * 100, 1)
                if len(scores_list) >= 2:
                    second_label = scores_list[1][0]
                    second_user_suffix = (
                        second_label[5:]
                        if second_label.startswith("user:")
                        else None
                    )
                    second_score_pct = round(
                        max(0.0, scores_list[1][1]) * 100, 1
                    )
                    score_margin_pct = round(
                        (scores_list[0][1] - scores_list[1][1]) * 100, 1
                    )

            # Send speaker_resolved with voice-id source and optional confidence/scores for UI.
            try:
                _resolved_source = SPEAKER_SOURCE_VOICE_ID
                confidence = (
                    (best_score_pct / 100.0) if best_score_pct is not None else 0.0
                )
                payload = self.message_builder.build_speaker_resolved_payload(
                    deps.ctx.session_id,
                    segment_id=segment_id,
                    speaker_label=seg_speaker_label,
                    speaker_source=_resolved_source,
                    confidence=confidence,
                    is_overlap=False,
                    attribution_source=SEGMENT_LEVEL,
                    best_score_pct=best_score_pct,
                    second_score_pct=second_score_pct,
                    score_margin_pct=score_margin_pct,
                    best_user_suffix=best_user_suffix,
                    second_user_suffix=second_user_suffix,
                    all_scores=all_scores,
                    speaker_label_before=LABEL_UNKNOWN,
                    speaker_label_after=speaker_display_name(
                        deps.ctx.session_id, seg_speaker_label
                    ),
                )
                await deps.websocket.send_json(payload)
                deps.ctx.segment_audio_backing.pop(segment_id, None)
                deps.ctx.segments_resolved_count += 1
            except Exception as send_err:
                logger.debug(
                    "speaker_resolved send skipped (websocket closed?): %s",
                    send_err,
                )
        finally:
            deps.ctx.pending_voice_id_tasks.discard(task)
