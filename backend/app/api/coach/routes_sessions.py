"""Session routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.coach.services import (
    SessionService, SessionRepository, SessionReportService,
    SessionReportRepository, NudgeEventRepository
)
from app.domain.admin.services import RelationshipRepository
from app.infra.db.repositories.session_repo import (
    SessionRepositoryImpl, SessionReportRepositoryImpl, NudgeEventRepositoryImpl
)
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.jobs.queue import job_queue

router = APIRouter()


class CreateSessionRequest(BaseModel):
    """Create session request model."""
    relationship_id: str
    participants: list[str] = []


class SessionResponse(BaseModel):
    """Session response model."""
    id: str
    status: str


class FinalizeResponse(BaseModel):
    """Finalize response model."""
    ok: bool


class SessionReportResponse(BaseModel):
    """Session report response model."""
    sid: str
    summary: str
    moments: list[dict]
    action_items: list[str]


@router.post("", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new session."""
    session_repo: SessionRepository = SessionRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    session_service = SessionService(session_repo, relationship_repo)

    session = await session_service.create_session(
        relationship_id=request.relationship_id,
        participants=request.participants,
        creator_id=current_user.id,
    )

    return SessionResponse(id=session.id, status=session.status)


@router.post("/{session_id}/finalize", response_model=FinalizeResponse)
async def finalize_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a session (enqueue review job)."""
    session_repo: SessionRepository = SessionRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    session_service = SessionService(session_repo, relationship_repo)
    
    # Verify user has access to session
    session = await session_service.get_session(session_id)
    participants = await session_service.get_session_participants(session_id)
    if current_user.id not in participants:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Finalize session
    await session_service.finalize_session(session_id)

    # Create pending report
    report_repo: SessionReportRepository = SessionReportRepositoryImpl(db)
    nudge_repo: NudgeEventRepository = NudgeEventRepositoryImpl(db)
    report_service = SessionReportService(report_repo, nudge_repo)
    await report_service.get_or_create_report(session_id)

    # Enqueue review job
    await job_queue.enqueue("generate_session_report", {"session_id": session_id})

    return FinalizeResponse(ok=True)


@router.get("/{session_id}/report", response_model=SessionReportResponse)
async def get_session_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get session report."""
    session_repo: SessionRepository = SessionRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    session_service = SessionService(session_repo, relationship_repo)
    
    # Verify user has access to session
    session = await session_service.get_session(session_id)
    participants = await session_service.get_session_participants(session_id)
    if current_user.id not in participants:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Get or create report
    report_repo: SessionReportRepository = SessionReportRepositoryImpl(db)
    nudge_repo: NudgeEventRepository = NudgeEventRepositoryImpl(db)
    report_service = SessionReportService(report_repo, nudge_repo)
    
    report = await report_service.get_or_create_report(session_id)
    
    # Convert moments from dict to list format expected by API
    moments = report.moments if isinstance(report.moments, list) else []
    
    return SessionReportResponse(
        sid=report.session_id,
        summary=report.summary or "Report pending...",
        moments=moments,
        action_items=report.action_items if isinstance(report.action_items, list) else [],
    )
