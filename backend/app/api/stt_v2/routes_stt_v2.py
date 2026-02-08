"""
STT V2 WebSocket route using the STT V2 pipeline.

This route is parallel to the existing STT v1 stack and intentionally isolated.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.api.stt.constants import STT_SAMPLE_RATE_HZ
from app.api.stt.google_stt_client import GoogleSttClient
from app.api.stt.stt_session_service import SttSessionService
from app.settings import settings

from app.api.stt_v2.audio_chunker import AudioChunker
from app.api.stt_v2.audio_ingestor import AudioIngestor
from app.api.stt_v2.audio_ring_buffer import AudioRingBuffer
from app.api.stt_v2.chirp3_stt_service import Chirp3SttService
from app.api.stt_v2.coach_engine import CoachEngine
from app.api.stt_v2.diart_diarization_service import DiartDiarizationService
from app.api.stt_v2.nemo_diarization_service import NemoDiarizationService
from app.api.stt_v2.none_diarization_service import NoneDiarizationService
from app.api.stt_v2.pause_vad_service import PauseVADService
from app.api.stt_v2.sentence_assembler import SentenceAssembler
from app.api.stt_v2.sentence_attributor import SentenceSpeakerAttributor
from app.api.stt_v2.sentence_stitcher import SentenceStitcher
from app.api.stt_v2.session_orchestrator import SessionOrchestrator
from app.api.stt_v2.speaker_timeline_store import SpeakerTimelineStore
from app.api.stt_v2.voice_id_matcher import VoiceIdMatcher

logger = logging.getLogger(__name__)
router = APIRouter()


@dataclass
class _V2Services:
    stt_session_service: SttSessionService
    orchestrator: SessionOrchestrator


def _build_services() -> _V2Services:
    google_stt_client = GoogleSttClient()
    stt_session_service = SttSessionService(google_stt_client)

    sample_rate = STT_SAMPLE_RATE_HZ
    ring_buffer = AudioRingBuffer(
        sample_rate=sample_rate, max_seconds=settings.stt_v2_audio_buffer_seconds
    )
    ingestor = AudioIngestor(ring_buffer=ring_buffer, sample_rate=sample_rate)
    chunker = AudioChunker(
        sample_rate=sample_rate,
        frame_ms=settings.stt_v2_frame_ms,
        window_s=settings.stt_v2_diar_window_s,
        hop_s=settings.stt_v2_diar_hop_s,
    )
    pause_vad = PauseVADService(
        sample_rate=sample_rate,
        vad_frame_ms=settings.stt_v2_vad_frame_ms,
        vad_hangover_ms=settings.stt_v2_vad_hangover_ms,
        pause_split_ms=settings.stt_v2_pause_split_ms,
        pause_merge_ms=settings.stt_v2_pause_merge_ms,
    )
    diar_backend = (settings.stt_v2_diar_backend or "diart").strip().lower()
    if diar_backend not in {"diart", "nemo", "none"}:
        logger.warning(
            "Unknown stt_v2_diar_backend=%r; defaulting to diart",
            diar_backend,
        )
        diar_backend = "diart"
    if diar_backend == "none":
        diar_service = NoneDiarizationService()
        logger.info("STT v2 diarization backend: none (diarization disabled)")
    elif diar_backend == "nemo":
        diar_service = NemoDiarizationService(
            preview_mode=True,
            patch_window_s=settings.stt_v2_patch_window_ms / 1000,
            patch_emit_s=settings.stt_v2_patch_emit_s,
            max_speakers=settings.stt_nemo_diarization_max_speakers,
        )
        if not getattr(diar_service, "_available", False):
            logger.warning(
                "NeMo diarization unavailable (%s), falling back to Diart",
                getattr(diar_service, "_unavailable_reason", None),
            )
            diar_backend = "diart"
    if diar_backend == "diart":
        diar_service = DiartDiarizationService(
            preview_mode=True,
            patch_window_s=settings.stt_v2_patch_window_ms / 1000,
            patch_emit_s=settings.stt_v2_patch_emit_s,
            window_s=settings.stt_v2_diar_window_s,
            hop_s=settings.stt_v2_diar_hop_s,
        )
    timeline_store = SpeakerTimelineStore(
        sample_rate=sample_rate,
        min_turn_ms=settings.stt_v2_min_turn_ms,
        switch_confirm_ms=settings.stt_v2_switch_confirm_ms,
        cooldown_ms=settings.stt_v2_cooldown_ms,
        switch_margin=settings.stt_v2_switch_margin,
        max_minutes=settings.stt_v2_timeline_max_minutes,
    )
    stt_service = Chirp3SttService(google_stt_client)
    sentence_assembler = SentenceAssembler(
        sample_rate=sample_rate,
        pause_split_ms=settings.stt_v2_pause_split_ms,
        max_sentence_ms=settings.stt_v2_max_sentence_ms,
        max_chars=settings.stt_v2_max_chars,
        min_chars=settings.stt_v2_min_chars,
        stt_jitter_buffer_ms=settings.stt_v2_stt_jitter_buffer_ms,
    )
    attributor = SentenceSpeakerAttributor(
        timeline_store=timeline_store,
        sample_rate=sample_rate,
        dominant_sentence_th=settings.stt_v2_dominant_sentence_th,
        overlap_sentence_th=settings.stt_v2_overlap_sentence_th,
        uncertain_sentence_th=settings.stt_v2_uncertain_sentence_th,
    )
    voice_id_matcher = VoiceIdMatcher(sample_rate=sample_rate)
    stitcher = SentenceStitcher(
        stitch_gap_ms=settings.stt_v2_stitch_gap_ms,
        max_stitched_ms=settings.stt_v2_max_stitched_ms,
    )
    coach_engine = CoachEngine(
        dominant_sentence_th=settings.stt_v2_dominant_sentence_th,
        min_nudge_sentence_ms=settings.stt_v2_min_nudge_sentence_ms,
    )
    orchestrator = SessionOrchestrator(
        ingestor=ingestor,
        chunker=chunker,
        pause_vad=pause_vad,
        diar_service=diar_service,
        timeline_store=timeline_store,
        stt_service=stt_service,
        sentence_assembler=sentence_assembler,
        attributor=attributor,
        voice_id_matcher=voice_id_matcher,
        stitcher=stitcher,
        coach_engine=coach_engine,
        patch_window_ms=settings.stt_v2_patch_window_ms,
        audio_queue_max=settings.stt_v2_audio_queue_max,
        frame_queue_max=settings.stt_v2_frame_queue_max,
        window_queue_max=settings.stt_v2_window_queue_max,
        diar_queue_max=settings.stt_v2_diar_queue_max,
        stt_queue_max=settings.stt_v2_stt_queue_max,
    )
    return _V2Services(stt_session_service=stt_session_service, orchestrator=orchestrator)


def _speaker_sentence_payload(
    stream_id: str, ss: Any, message_type: str = "ui.sentence", debug_enabled: bool = False
) -> dict:
    payload = {
        "type": message_type,
        "id": ss.ui_sentence.id,
        "stream_id": stream_id,
        "start_ms": ss.ui_sentence.range_ms.start_ms,
        "end_ms": ss.ui_sentence.range_ms.end_ms,
        "label": ss.label,
        "label_conf": ss.label_conf,
        "coverage": ss.coverage,
        "text": ss.ui_sentence.text,
        "flags": ss.flags,
        "speaker_color": getattr(ss, "speaker_color", None),
        "ui_context": getattr(ss.ui_sentence, "ui_context", None),
        "split_from": getattr(ss.ui_sentence, "split_from", None),
    }
    audio_b64 = getattr(ss, "audio_segment_base64", None)
    if audio_b64:
        payload["audio_segment_base64"] = audio_b64
    if debug_enabled:
        segmentation_debug = getattr(getattr(ss, "ui_sentence", None), "debug", None)
        speaker_debug = getattr(ss, "debug", None)
        if segmentation_debug or speaker_debug:
            payload["debug"] = {
                "segmentation": segmentation_debug,
                "speaker": speaker_debug,
            }
    return payload


@router.get(
    "/stream/{session_id}",
    responses={426: {"description": "Use WebSocket to connect to this endpoint."}},
)
async def stream_stt_v2_get(session_id: str, token: Optional[str] = None) -> JSONResponse:
    """Plain GET is not allowed; this endpoint is WebSocket-only. Returns 426 so clients know to upgrade."""
    return JSONResponse(
        status_code=426,
        content={
            "detail": "This endpoint is WebSocket-only. Connect with a WebSocket client (e.g. new WebSocket(url)) instead of GET."
        },
        headers={"Upgrade": "websocket", "Connection": "Upgrade"},
    )


@router.websocket("/stream/{session_id}")
async def stream_stt_v2(websocket: WebSocket, session_id: str, token: Optional[str] = None) -> None:
    services = _build_services()
    await websocket.accept()
    validated = await services.stt_session_service.validate_stream_request(
        websocket, session_id, token
    )
    if validated is None:
        return
    _user_id, ctx = validated

    client, _endpoint = await services.stt_session_service.google_stt_client.ensure_credentials_and_client(
        websocket
    )
    if client is None:
        return

    stream_id = session_id
    services.orchestrator.start_session(stream_id, STT_SAMPLE_RATE_HZ, ctx, client)
    debug_enabled = bool(getattr(ctx, "debug", False))

    try:
        while True:
            # Raw PCM16 audio in, batched STT/diar outputs out.
            chunk = await websocket.receive_bytes()
            output = services.orchestrator.process_audio_chunk(
                stream_id, chunk, STT_SAMPLE_RATE_HZ
            )
            if not settings.stt_v2_shadow_mode:
                # Emit speaker sentences (mapped label), patches, then nudges.
                for ss in output.provisional_sentences:
                    if hasattr(ss, "ui_sentence"):
                        await websocket.send_json(
                            _speaker_sentence_payload(
                                stream_id, ss, "ui.sentence", debug_enabled=debug_enabled
                            )
                        )
                for patch in output.ui_sentence_patches:
                    await websocket.send_json(
                        _speaker_sentence_payload(
                            stream_id,
                            patch,
                            "ui.sentence.patch",
                            debug_enabled=debug_enabled,
                        )
                    )
                for ss in output.speaker_sentences:
                    if hasattr(ss, "ui_sentence"):
                        await websocket.send_json(
                            _speaker_sentence_payload(
                                stream_id, ss, "ui.sentence", debug_enabled=debug_enabled
                            )
                        )
                for nudge in output.nudges:
                    await websocket.send_json(
                        {"type": nudge.type, "label": nudge.label, "text": nudge.text}
                    )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("STT V2 stream error: %s", exc)
        try:
            await websocket.close(code=1011, reason="STT V2 error")
        except Exception:
            pass
    finally:
        if settings.stt_v2_debug_bundle_enabled:
            try:
                bundle = services.orchestrator.build_debug_bundle(stream_id)
                out_dir = Path(settings.stt_v2_debug_bundle_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"stt_v2_bundle_{stream_id}.json"
                out_path.write_text(json.dumps(bundle))
            except Exception:
                pass
        services.orchestrator.stop_session(stream_id)
