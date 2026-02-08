"""
STT session creation, validation, shutdown, and post-session voice centroid updates.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import queue
import uuid
from typing import Any, Optional

from fastapi import WebSocket, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.admin.models import User
from app.domain.stt.session_registry import SttSessionContext, stt_registry
from app.domain.voice.assembly import assemble_voice_sample_with_beeps
from app.domain.voice.embeddings import (
    ECAPA_EMBEDDING_DIM,
    compute_embedding_centroid,
    compute_embedding_from_wav_bytes,
    cosine_similarity,
    l2_normalize,
    parse_voice_embedding_json,
)
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.security.jwt import decode_token

from app.api.stt.constants import MSG_STT_ERROR, SESSION_END_SLEEP_BEFORE_CENTROID_S
from app.api.stt.stt_models import CreateSttSessionRequest, CreateSttSessionResponse

logger = logging.getLogger(__name__)


class SttSessionService:
    """Handles STT session lifecycle: create, validate stream request, shutdown, and centroid update."""

    def __init__(self, google_stt_client: Any):
        self.google_stt_client = google_stt_client

    async def load_voice_embeddings(
        self,
        voice_repo: VoiceRepository,
        candidate_user_ids: list[str],
    ) -> tuple[dict[str, list[float]], dict[str, tuple[list[list[float]], list[dict]]]]:
        """
        Load voice embeddings for candidate users from DB. Returns (centroids, multi).
        """
        profiles = await voice_repo.get_profiles_by_user_ids(candidate_user_ids)
        embeddings: dict[str, list[float]] = {}
        embeddings_multi: dict[str, tuple[list[list[float]], list[dict]]] = {}
        embedding_user_ids = set()
        for profile in profiles:
            if profile.voice_embedding_json:
                try:
                    embs_list, meta_list = parse_voice_embedding_json(
                        profile.voice_embedding_json,
                        expected_dim=ECAPA_EMBEDDING_DIM,
                    )
                    if embs_list:
                        embeddings_multi[profile.user_id] = (embs_list, meta_list)
                        centroid = compute_embedding_centroid(
                            embs_list, normalize=True
                        )
                        if centroid:
                            embeddings[profile.user_id] = centroid
                            embedding_user_ids.add(profile.user_id)
                except (json.JSONDecodeError, TypeError):
                    continue
            if (
                profile.user_id not in embedding_user_ids
                and getattr(profile, "voice_sample_base64", None)
            ):
                try:
                    sample = profile.voice_sample_base64 or ""
                    if "base64," in sample:
                        sample = sample.split("base64,", 1)[1]
                    audio_bytes = base64.b64decode(sample)
                    computed = compute_embedding_from_wav_bytes(audio_bytes)
                    if computed:
                        embeddings[profile.user_id] = computed
                        embeddings_multi[profile.user_id] = ([computed], [{}])
                        embedding_user_ids.add(profile.user_id)
                        await voice_repo.update_profile(
                            profile.user_id,
                            voice_embedding_json=json.dumps(computed),
                        )
                except Exception:
                    pass
        return embeddings, embeddings_multi

    async def get_user_from_token(self, token: str) -> Optional[str]:
        """Decode JWT and return subject (user_id) if type is 'access'; otherwise None."""
        payload = decode_token(token)
        if not payload:
            return None
        if payload.get("type") != "access":
            return None
        return payload.get("sub")

    async def create_session(
        self,
        request: CreateSttSessionRequest,
        current_user: User,
        db: AsyncSession,
    ) -> CreateSttSessionResponse:
        """Create an STT session: load voice embeddings, register context, optionally assemble combined voice sample."""
        from fastapi import HTTPException

        from app.settings import settings

        if self.google_stt_client.is_placeholder_recognizer(settings.stt_recognizer):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STT_RECOGNIZER is not configured. Set a valid recognizer resource.",
            )
        session_id = str(uuid.uuid4())
        voice_repo = VoiceRepository(db)
        embeddings, embeddings_multi = await self.load_voice_embeddings(
            voice_repo, request.candidate_user_ids
        )
        if len(embeddings) >= 2:
            try:
                embed_items = list(embeddings.items())
                cosine_similarity(embed_items[0][1], embed_items[1][1])
            except Exception:
                pass
        if len(embeddings) == 0:
            logger.info(
                "Voice matching: no embeddings loaded for this session. "
                "Send candidate_user_ids when creating the STT session and ensure those users have completed voice enrollment."
            )
        ctx = SttSessionContext(
            session_id=session_id,
            user_id=current_user.id,
            candidate_user_ids=request.candidate_user_ids,
            language_code=request.language_code or "auto",
            min_speaker_count=request.min_speaker_count or 1,
            max_speaker_count=request.max_speaker_count or 2,
            disable_speaker_union_join=bool(request.disable_speaker_union_join)
            if request.disable_speaker_union_join is not None
            else False,
            debug=bool(request.debug) if request.debug is not None else False,
            skip_diarization=bool(request.skip_diarization) if request.skip_diarization is not None else True,
            voice_embeddings=embeddings,
            voice_embeddings_multi=embeddings_multi,
        )
        await stt_registry.create(ctx)

        combined_b64: str | None = None
        speaker_ids_in_order: list[str] = []
        profiles = await voice_repo.get_profiles_by_user_ids(
            request.candidate_user_ids
        )
        profile_by_id = {p.user_id: p for p in profiles}
        ordered_samples: list[tuple[str, str]] = []
        for uid in request.candidate_user_ids:
            profile = profile_by_id.get(uid)
            sample = (
                getattr(profile, "voice_sample_base64", None) if profile else None
            )
            if sample:
                ordered_samples.append((uid, sample))
        if ordered_samples:
            combined_b64, speaker_ids_in_order = assemble_voice_sample_with_beeps(
                ordered_samples
            )

        return CreateSttSessionResponse(
            session_id=session_id,
            combined_voice_sample_base64=combined_b64,
            speaker_user_ids_in_order=speaker_ids_in_order,
        )

    async def validate_stream_request(
        self,
        websocket: WebSocket,
        session_id: str,
        token: str | None,
    ) -> Optional[tuple[str, SttSessionContext]]:
        """Validate STT stream request: recognizer config, token, and session ownership. On failure sends error and returns None."""
        from app.settings import settings

        if self.google_stt_client.is_placeholder_recognizer(settings.stt_recognizer):
            await websocket.send_json(
                {
                    "type": MSG_STT_ERROR,
                    "message": "STT_RECOGNIZER is not configured. Set a valid recognizer resource.",
                }
            )
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="STT recognizer not configured",
            )
            return None
        query_params = dict(websocket.query_params)
        resolved_token = token or query_params.get("token")
        if not resolved_token:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication required",
            )
            return None
        user_id = await self.get_user_from_token(resolved_token)
        if not user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
            )
            return None
        ctx = await stt_registry.get(session_id)
        if not ctx or ctx.user_id != user_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid session"
            )
            return None
        return (user_id, ctx)

    async def shutdown(
        self,
        stop_event: Any,
        nemo_worker_stop: asyncio.Event,
        nemo_worker_task: Optional[asyncio.Task],
        sortformer_timeline_task: Optional[asyncio.Task],
        flush_loop_task: Optional[asyncio.Task],
        audio_queue: queue.Queue,
        sortformer_queue: queue.Queue,
        ctx: SttSessionContext,
    ) -> None:
        """Tear down STT stream: signal workers, cancel tasks, drain queues."""
        stop_event.set()
        nemo_worker_stop.set()
        if nemo_worker_task:
            nemo_worker_task.cancel()
        if sortformer_timeline_task:
            sortformer_timeline_task.cancel()
        if flush_loop_task:
            flush_loop_task.cancel()
            try:
                await flush_loop_task
            except asyncio.CancelledError:
                pass
        audio_queue.put(None)
        sortformer_queue.put(None)
        for task in list(ctx.pending_voice_id_tasks):
            task.cancel()
        for task in list(ctx.pending_nemo_label_tasks):
            task.cancel()
        try:
            await asyncio.gather(
                *ctx.pending_voice_id_tasks, return_exceptions=True
            )
        except Exception:
            pass
        try:
            await asyncio.gather(
                *ctx.pending_nemo_label_tasks, return_exceptions=True
            )
        except Exception:
            pass
        # Clean up streaming diarizer state
        if ctx.streaming_diarizer is not None:
            ctx.streaming_diarizer = None
            ctx.diar_abs_cursor_sample = None
            ctx.diar_last_end_sample = None
            ctx.diar_open_segment = None
        await asyncio.sleep(SESSION_END_SLEEP_BEFORE_CENTROID_S)

    async def update_voice_centroids_after_session(
        self, ctx: SttSessionContext
    ) -> None:
        """Blend session segment embeddings into user voice profiles and persist."""
        from app.settings import settings

        if not getattr(
            settings, "stt_update_voice_centroid_after_session", True
        ) or not ctx.user_segment_embeddings:
            return
        try:
            from app.infra.db.base import AsyncSessionLocal
        except ImportError:
            return
        if not AsyncSessionLocal:
            return
        try:
            async with AsyncSessionLocal() as db:
                voice_repo = VoiceRepository(db)
                min_seg = getattr(
                    settings, "stt_voice_centroid_min_segments", 2
                )
                alpha = getattr(
                    settings, "stt_voice_centroid_blend_alpha", 0.3
                )
                for user_id, embeddings in ctx.user_segment_embeddings.items():
                    try:
                        if len(embeddings) < min_seg:
                            continue
                        centroid = compute_embedding_centroid(
                            embeddings, normalize=True
                        )
                        if centroid is None:
                            continue
                        profile = await voice_repo.get_profile(user_id)
                        if profile and getattr(
                            profile, "voice_embedding_json", None
                        ):
                            try:
                                old = json.loads(
                                    profile.voice_embedding_json
                                )
                                if (
                                    isinstance(old, list)
                                    and len(old) == ECAPA_EMBEDDING_DIM
                                ):
                                    blended = [
                                        (1 - alpha) * old[i] + alpha * centroid[i]
                                        for i in range(len(old))
                                    ]
                                    new_embedding = l2_normalize(
                                        blended
                                    ).tolist()
                                else:
                                    new_embedding = centroid
                            except (json.JSONDecodeError, TypeError):
                                new_embedding = centroid
                        else:
                            new_embedding = centroid
                        updated = await voice_repo.update_profile(
                            user_id,
                            voice_embedding_json=json.dumps(new_embedding),
                        )
                        if updated:
                            logger.info(
                                "STT session end: updated voice profile centroid for user_id=%s segments=%s",
                                user_id[-6:] if len(user_id) >= 6 else user_id,
                                len(embeddings),
                            )
                        else:
                            logger.debug(
                                "STT session end: no voice profile for user_id=%s",
                                user_id[-6:] if len(user_id) >= 6 else user_id,
                            )
                    except Exception as e:
                        logger.warning(
                            "STT session end: failed to update voice profile for user_id=%s: %s",
                            user_id[-6:] if len(user_id) >= 6 else user_id,
                            str(e)[:120],
                        )
        except Exception as e:
            logger.warning(
                "STT session end: voice centroid update failed: %s",
                str(e)[:120],
            )
