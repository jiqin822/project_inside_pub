"""Compass dyad insights API."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/{relationship_id}/insights")
async def get_dyad_insights(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dyad insights: person portraits, dyad portrait, loops, memories summary."""
    from app.infra.db.models.relationship import relationship_members
    from sqlalchemy import select
    result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == relationship_id,
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

    event_repo = EventRepository(db)
    memory_repo = MemoryRepository(db)
    person_portrait_repo = PersonPortraitRepository(db)
    dyad_portrait_repo = DyadPortraitRepository(db)
    loop_repo = LoopRepository(db)
    activity_template_repo = ActivityTemplateRepository(db)
    dyad_activity_repo = DyadActivityHistoryRepository(db)
    context_summary_repo = ContextSummaryRepository(db)

    personalization = PersonalizationService(
        event_repo=event_repo,
        memory_repo=memory_repo,
        person_portrait_repo=person_portrait_repo,
        dyad_portrait_repo=dyad_portrait_repo,
        loop_repo=loop_repo,
        activity_template_repo=activity_template_repo,
        dyad_activity_repo=dyad_activity_repo,
        context_summary_repo=context_summary_repo,
    )

    data = await personalization.get_dyad_insights(
        relationship_id=relationship_id,
        actor_user_id=current_user.id,
    )

    def portrait_to_dict(p):
        if p is None:
            return None
        return {
            "portrait_id": getattr(p, "portrait_id", getattr(p, "dyad_portrait_id", None)),
            "portrait_text": getattr(p, "portrait_text", None),
            "portrait_facets_json": getattr(p, "portrait_facets_json", None) or getattr(p, "facets_json", None),
            "confidence": getattr(p, "confidence", None),
            "evidence_event_ids": getattr(p, "evidence_event_ids", None),
        }

    def loop_to_dict(lo):
        return {
            "loop_id": lo.loop_id,
            "name": lo.name,
            "status": lo.status,
            "trigger_signals_json": lo.trigger_signals_json,
            "meanings_json": lo.meanings_json,
            "repair_attempts_json": lo.repair_attempts_json,
        }

    return {
        "person_portraits": [portrait_to_dict(p) for p in data["person_portraits"] if p],
        "dyad_portrait": portrait_to_dict(data["dyad_portrait"]),
        "loops": [loop_to_dict(lo) for lo in data["loops"]],
        "memories_summary": data["memories_summary"],
    }
