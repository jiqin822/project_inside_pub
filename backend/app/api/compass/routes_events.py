"""Compass event ingest API."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class EventIngestRequest(BaseModel):
    """Event ingest request."""
    type: str
    payload: dict = {}
    source: str
    relationship_id: Optional[str] = None
    privacy_scope: Optional[str] = "private"


class EventIngestResponse(BaseModel):
    """Event ingest response."""
    event_id: str
    created_at: str


@router.post("", response_model=EventIngestResponse)
async def ingest_event(
    request: EventIngestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest an event into Insider Compass (then consolidate and update portraits/summaries)."""
    from app.domain.compass.services import EventIngestService, ConsolidationService
    from app.infra.db.repositories.event_repo import EventRepository
    from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
    from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
    from app.infra.db.repositories.memory_repo import MemoryRepository

    event_repo = EventRepository(db)
    person_portrait_repo = PersonPortraitRepository(db)
    dyad_portrait_repo = DyadPortraitRepository(db)
    context_summary_repo = ContextSummaryRepository(db)
    memory_repo = MemoryRepository(db)
    consolidation = ConsolidationService(
        event_repo=event_repo,
        person_portrait_repo=person_portrait_repo,
        dyad_portrait_repo=dyad_portrait_repo,
        context_summary_repo=context_summary_repo,
        memory_repo=memory_repo,
    )
    from app.settings import settings
    event_ingest = EventIngestService(
        event_repo=event_repo,
        consolidation_service=consolidation,
        consolidation_threshold=settings.compass_consolidation_threshold,
    )

    if request.relationship_id:
        from app.infra.db.models.relationship import relationship_members
        from sqlalchemy import select
        result = await db.execute(
            select(relationship_members.c.user_id).where(
                relationship_members.c.relationship_id == request.relationship_id,
            )
        )
        member_ids = [row[0] for row in result.all()]
        if current_user.id not in member_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this relationship",
            )

    event = await event_ingest.ingest(
        type=request.type,
        actor_user_id=current_user.id,
        payload=request.payload,
        source=request.source,
        relationship_id=request.relationship_id,
        privacy_scope=request.privacy_scope or "private",
        db=db,
    )

    # When type is activity_completed, also append to dyad_activity_history for recommendations.
    if request.type == "activity_completed" and request.relationship_id:
        activity_template_id = request.payload.get("activity_template_id") or request.payload.get("activity_id")
        if activity_template_id:
            from datetime import datetime
            from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
            now = datetime.utcnow()
            payload = request.payload
            note = payload.get("note")
            outcome_tags = payload.get("outcome_tags")
            if note and outcome_tags is None:
                outcome_tags = [note]
            dyad_repo = DyadActivityHistoryRepository(db)
            await dyad_repo.append(
                relationship_id=request.relationship_id,
                activity_template_id=activity_template_id,
                actor_user_id=current_user.id,
                started_at=now,
                completed_at=now,
                rating=payload.get("rating"),
                outcome_tags=outcome_tags,
                notes_text=note,
            )

    from datetime import datetime
    created_at_str = event.created_at.isoformat() + "Z" if isinstance(event.created_at, datetime) else str(event.created_at)
    return EventIngestResponse(event_id=event.event_id, created_at=created_at_str)
