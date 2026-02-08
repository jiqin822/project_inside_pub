"""
STT (Speech-to-Text) API routes and WebSocket stream handler.

This module provides:
- REST: create STT session (POST /session), which registers a session with voice embeddings
  for candidate users and returns a session_id for the WebSocket stream.
- WebSocket: stream STT (WS /stream/{session_id}?token=...), which accepts binary audio chunks,
  runs Google Cloud StreamingRecognize (and optional NeMo diarization fallback), and sends
  transcript and speaker_resolved messages back to the client.

Speaker attribution uses voice embeddings (ECAPA-TDNN), optional Google diarization,
and/or a sample-indexed speaker timeline from NeMo Sortformer. Business logic is
delegated to service classes (SttSessionService, SttStreamHandler, etc.).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.stt.session_registry import SttSessionContext, stt_registry
from app.domain.stt.speaker_matching import AudioRingBuffer
from app.settings import settings

from google.cloud import speech_v2 as speech

from app.api.stt.constants import (
    DEFAULT_STT_EXECUTOR_WORKERS,
    STT_SAMPLE_RATE_HZ,
)
from app.api.stt.stt_models import CreateSttSessionRequest, CreateSttSessionResponse
from app.api.stt.speaker_matcher import SpeakerMatcher
from app.api.stt.audio_processor import AudioProcessor
from app.api.stt.message_builder import MessageBuilder
from app.api.stt.segment_builder import SegmentBuilder
from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt.diarization_workers import (
    NeMoLabeler,
    SortformerStreamingWorker,
)
from app.api.stt.stt_session_service import SttSessionService
from app.api.stt.stt_stream_handler import SttStreamHandler

import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared dependencies and service instances
# ---------------------------------------------------------------------------

@dataclass
class StreamSttDeps:
    """
    Shared dependencies for the STT stream handler and its workers.

    Passed into the Google recognition thread callback, NeMo workers, and
    response handlers so they can access websocket, session context, executor,
    and queues without closure capture issues.
    """

    websocket: WebSocket
    ctx: SttSessionContext
    loop: asyncio.AbstractEventLoop
    executor: concurrent.futures.ThreadPoolExecutor
    ring_buffer: AudioRingBuffer
    audio_queue: queue.Queue[Optional[bytes]]
    sortformer_queue: queue.Queue[Optional[tuple[bytes, int, int]]]
    nemo_worker_stop: asyncio.Event
    enable_nemo_fallback: bool
    request_generator_sync: Callable[[bool], Any]
    client: speech.SpeechClient


def _get_services() -> tuple[
    GoogleSttClient,
    SttSessionService,
    SpeakerMatcher,
    AudioProcessor,
    MessageBuilder,
    SegmentBuilder,
    NeMoLabeler,
    SttStreamHandler,
]:
    """Build and return service instances (lazy singleton pattern for router)."""
    google_stt_client = GoogleSttClient()
    stt_session_service = SttSessionService(google_stt_client)
    speaker_matcher = SpeakerMatcher()
    audio_processor = AudioProcessor()
    message_builder = MessageBuilder()
    segment_builder = SegmentBuilder()
    nemo_labeler = NeMoLabeler(speaker_matcher, message_builder, audio_processor)
    stt_stream_handler = SttStreamHandler(
        segment_builder, audio_processor, message_builder, nemo_labeler
    )
    return (
        google_stt_client,
        stt_session_service,
        speaker_matcher,
        audio_processor,
        message_builder,
        segment_builder,
        nemo_labeler,
        stt_stream_handler,
    )


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------

@router.post("/session", response_model=CreateSttSessionResponse)
async def create_stt_session(
    request: CreateSttSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateSttSessionResponse:
    """
    Create an STT session: load voice embeddings for candidates, register context in stt_registry,
    optionally assemble combined voice sample for Gemini. Returns session_id for WebSocket stream.
    """
    _, stt_session_service, *_ = _get_services()
    return await stt_session_service.create_session(request, current_user, db)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/stream/{session_id}")
async def stream_stt(
    websocket: WebSocket,
    session_id: str,
    token: str | None = None,
):
    """WebSocket endpoint for streaming speech-to-text with optional speaker attribution.

    Expects session created via POST /session and token in query or path. Accepts
    binary audio chunks, runs Google StreamingRecognize (and optional NeMo/Sortformer
    workers), sends stt.transcript and stt.speaker_resolved messages. On disconnect
    or error, shuts down workers and may update voice centroids from session embeddings.
    """
    # --- Resolve service instances (STT client, session service, matcher, stream handler) ---
    (
        google_stt_client,
        stt_session_service,
        speaker_matcher,
        _audio_processor,
        _message_builder,
        _segment_builder,
        _nemo_labeler,
        stt_stream_handler,
    ) = _get_services()

    # --- Accept WebSocket and validate session/token; resolve session context ---
    await websocket.accept()
    validated = await stt_session_service.validate_stream_request(
        websocket, session_id, token
    )
    if validated is None:
        return
    _user_id, ctx = validated

    # --- Create queues and ring buffer for audio flow to Google STT and NeMo workers ---
    audio_queue: queue.Queue[Optional[bytes]] = queue.Queue()
    sortformer_queue: queue.Queue[Optional[tuple[bytes, int, int]]] = queue.Queue()
    ring_buffer = AudioRingBuffer(
        sample_rate=STT_SAMPLE_RATE_HZ,
        max_seconds=settings.stt_audio_buffer_seconds,
    )

    # --- Build Google STT language config and synchronous request generator ---
    language_codes, model_id, enable_diarization_for_request = (
        google_stt_client.get_language_config(ctx)
    )
    request_generator_sync = google_stt_client.build_request_generator(
        audio_queue, ctx, language_codes, model_id, enable_diarization_for_request
    )

    # --- Ensure Google credentials and Speech client; bail if unavailable ---
    client, _endpoint = await google_stt_client.ensure_credentials_and_client(
        websocket
    )
    if client is None:
        return

    # --- Event loop and thread pool for running blocking Google recognition ---
    loop = asyncio.get_running_loop()
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=DEFAULT_STT_EXECUTOR_WORKERS
    )

    # --- NeMo diarization fallback: flags, stop event, and shared deps for workers ---
    enable_nemo_fallback = bool(
        getattr(settings, "stt_enable_nemo_diarization_fallback", False)
    )
    nemo_worker_stop = asyncio.Event()
    nemo_worker_task: asyncio.Task | None = None

    deps = StreamSttDeps(
        websocket=websocket,
        ctx=ctx,
        loop=loop,
        executor=executor,
        ring_buffer=ring_buffer,
        audio_queue=audio_queue,
        sortformer_queue=sortformer_queue,
        nemo_worker_stop=nemo_worker_stop,
        enable_nemo_fallback=enable_nemo_fallback,
        request_generator_sync=request_generator_sync,
        client=client,
    )
    last_escalation_at_ref: list[float] = [0.0]

    # --- Wire response handler and start Google streaming recognition in a daemon thread ---
    def handle_response_message(response: Any, stream_base: int, d: StreamSttDeps) -> Any:
        return stt_stream_handler.handle_response_message(
            response, stream_base, d, last_escalation_at_ref, speaker_matcher
        )

    stop_event = threading.Event()
    response_thread = threading.Thread(
        target=google_stt_client.run_streaming_recognize,
        args=(deps, stop_event, handle_response_message),
        daemon=True,
    )
    response_thread.start()

    # --- Start NeMo streaming diarization worker when fallback is enabled ---
    nemo_available = getattr(
        websocket.app.state, "nemo_diarization_available", False
    )
    sortformer_timeline_task: asyncio.Task | None = None
    flush_loop_task: asyncio.Task | None = None
    if enable_nemo_fallback and nemo_available:
        # Use new streaming worker instead of old windowed workers
        streaming_worker = SortformerStreamingWorker(deps)
        nemo_worker_task = asyncio.create_task(streaming_worker.run(deps))
        flush_loop_task = asyncio.create_task(
            stt_stream_handler.run_pending_flush_loop(deps, speaker_matcher)
        )

    # --- Main loop: receive binary audio, append to ring buffer, feed queues until disconnect ---
    try:
        while True:
            chunk = await websocket.receive_bytes()
            start_sample = ring_buffer.total_samples
            ring_buffer.append(chunk)
            end_sample = ring_buffer.total_samples
            audio_queue.put(chunk)
            sortformer_queue.put((chunk, start_sample, end_sample))
    except WebSocketDisconnect:
        pass
    # --- Cleanup: stop workers, drain pending final segments, update centroids, release session ---
    finally:
        await stt_session_service.shutdown(
            stop_event,
            nemo_worker_stop,
            nemo_worker_task,
            sortformer_timeline_task,
            flush_loop_task,
            audio_queue,
            sortformer_queue,
            ctx,
        )
        # Drain pending final segments so user sees all transcripts
        for item in getattr(ctx, "pending_final_segments", []):
            payload = item.get("payload") if isinstance(item, dict) else None
            if payload:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    pass
        await stt_session_service.update_voice_centroids_after_session(ctx)
        executor.shutdown(wait=False)
        await stt_registry.delete(session_id)
