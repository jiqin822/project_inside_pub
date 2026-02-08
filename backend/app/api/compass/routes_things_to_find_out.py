"""Compass things-to-find-out API (Kai questions)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User

router = APIRouter()


class AddThingToFindOutRequest(BaseModel):
    """Request body for adding a thing to find out."""
    question_text: str
    relationship_id: Optional[str] = None
    source: str = "kai"
    priority: Optional[int] = None


class AddThingToFindOutResponse(BaseModel):
    """Response after adding a thing to find out."""
    ok: bool
    id: Optional[str] = None


@router.post("", response_model=AddThingToFindOutResponse)
async def add_thing_to_find_out(
    request: AddThingToFindOutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a question Kai wants to find out (stored in Compass)."""
    if not (request.question_text or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question_text is required and must be non-empty",
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
    from app.infra.db.repositories.things_to_find_out_repo import ThingsToFindOutRepository

    event_repo = EventRepository(db)
    memory_repo = MemoryRepository(db)
    person_portrait_repo = PersonPortraitRepository(db)
    dyad_portrait_repo = DyadPortraitRepository(db)
    loop_repo = LoopRepository(db)
    activity_template_repo = ActivityTemplateRepository(db)
    dyad_activity_repo = DyadActivityHistoryRepository(db)
    context_summary_repo = ContextSummaryRepository(db)
    things_to_find_out_repo = ThingsToFindOutRepository(db)

    personalization = PersonalizationService(
        event_repo=event_repo,
        memory_repo=memory_repo,
        person_portrait_repo=person_portrait_repo,
        dyad_portrait_repo=dyad_portrait_repo,
        loop_repo=loop_repo,
        activity_template_repo=activity_template_repo,
        dyad_activity_repo=dyad_activity_repo,
        context_summary_repo=context_summary_repo,
        things_to_find_out_repo=things_to_find_out_repo,
    )

    id_ = await personalization.add_thing_to_find_out(
        owner_user_id=current_user.id,
        question_text=request.question_text,
        relationship_id=request.relationship_id,
        source=request.source or "kai",
        priority=request.priority,
    )
    return AddThingToFindOutResponse(ok=True, id=id_)
