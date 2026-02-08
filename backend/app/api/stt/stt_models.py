"""
Pydantic models for STT API (session create request/response).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CreateSttSessionRequest(BaseModel):
    """Request body for POST /session: candidates for voice matching and optional language/diarization hints."""
    candidate_user_ids: list[str] = []
    language_code: Optional[str] = None
    min_speaker_count: Optional[int] = 1
    max_speaker_count: Optional[int] = 2
    debug: Optional[bool] = None
    skip_diarization: Optional[bool] = None
    disable_speaker_union_join: Optional[bool] = None


class CreateSttSessionResponse(BaseModel):
    """Response for POST /session: session_id for WebSocket, optional combined sample and speaker order."""
    session_id: str
    combined_voice_sample_base64: str | None = None
    speaker_user_ids_in_order: list[str] = []
