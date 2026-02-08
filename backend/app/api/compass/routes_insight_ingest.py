"""Compass Kai insight ingestion API."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User

router = APIRouter()


class IngestInsightRequest(BaseModel):
    """Request body for ingesting a Kai insight."""
    insight_text: str
    relationship_id: Optional[str] = None
    source: str = "kai_insight"


class IngestInsightResponse(BaseModel):
    """Response after ingesting an insight."""
    ok: bool
    memory_id: Optional[str] = None


@router.post("", response_model=IngestInsightResponse)
async def ingest_insight(
    request: IngestInsightRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a Kai-generated insight into Compass (stored as unstructured memory)."""
    if not (request.insight_text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="insight_text is required and must be non-empty",
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

    from app.domain.compass.services import PersonalizationService
    from app.infra.db.repositories.event_repo import EventRepository
    from app.infra.db.repositories.memory_repo import MemoryRepository
    from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
    from app.infra.db.repositories.loop_repo import LoopRepository
    from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
    from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
    from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
    from app.infra.db.repositories.unstructured_memory_repo import UnstructuredMemoryRepository

    event_repo = EventRepository(db)
    memory_repo = MemoryRepository(db)
    person_portrait_repo = PersonPortraitRepository(db)
    dyad_portrait_repo = DyadPortraitRepository(db)
    loop_repo = LoopRepository(db)
    activity_template_repo = ActivityTemplateRepository(db)
    dyad_activity_repo = DyadActivityHistoryRepository(db)
    context_summary_repo = ContextSummaryRepository(db)
    unstructured_memory_repo = UnstructuredMemoryRepository(db)

    personalization = PersonalizationService(
        event_repo=event_repo,
        memory_repo=memory_repo,
        person_portrait_repo=person_portrait_repo,
        dyad_portrait_repo=dyad_portrait_repo,
        loop_repo=loop_repo,
        activity_template_repo=activity_template_repo,
        dyad_activity_repo=dyad_activity_repo,
        context_summary_repo=context_summary_repo,
        unstructured_memory_repo=unstructured_memory_repo,
    )

    memory_id = await personalization.ingest_kai_insight(
        actor_user_id=current_user.id,
        insight_text=request.insight_text,
        relationship_id=request.relationship_id,
        source=request.source or "kai_insight",
    )
    return IngestInsightResponse(ok=True, memory_id=memory_id)
