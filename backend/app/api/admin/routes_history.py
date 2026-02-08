"""History routes."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.coach.services import SessionRepository
from app.infra.db.repositories.session_repo import SessionRepositoryImpl

router = APIRouter()


class SessionHistoryItem(BaseModel):
    """Session history item response model."""
    id: str
    relationship_id: str
    status: str
    created_at: str


@router.get("/sessions", response_model=list[SessionHistoryItem])
async def get_session_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get session history for current user."""
    session_repo: SessionRepository = SessionRepositoryImpl(db)
    sessions = await session_repo.list_by_user(current_user.id, limit=limit)
    
    return [
        SessionHistoryItem(
            id=s.id,
            relationship_id=s.relationship_id,
            status=s.status,
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]
