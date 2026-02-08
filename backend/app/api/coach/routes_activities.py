"""Activity routes. Uses PersonalizationService for suggestions (Insider Compass)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from app.services.llm_service import LLMService
from app.infra.db.models.relationship import relationship_members

router = APIRouter()


class ActivitySuggestionResponse(BaseModel):
    """Activity suggestion response model."""
    id: str
    title: str
    description: str
    debug_prompt: Optional[str] = None
    debug_response: Optional[str] = None
    debug_source: Optional[str] = None  # "llm" | "seed_fallback" — where this activity came from (for debug UI)


async def _ensure_member(db: AsyncSession, relationship_id: str, user_id: str) -> None:
    """Raise 403 if user is not a member of the relationship."""
    result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == relationship_id,
        )
    )
    member_ids = [row[0] for row in result.all()]
    if user_id not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this relationship",
        )


@router.get("/suggestions", response_model=list[ActivitySuggestionResponse])
async def get_suggestions(
    rid: str,
    debug: bool = Query(False, description="Include LLM prompt/response (for debug UI)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Get personalized activity suggestions for a relationship (Insider Compass)."""
    await _ensure_member(db, rid, current_user.id)

    from app.domain.compass.services import PersonalizationService
    from app.domain.activity.services import ActivitySuggestionService
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
    activity_suggestion = ActivitySuggestionService(
        activity_template_repo=activity_template_repo,
        context_provider=personalization,
    )

    from app.settings import settings
    from app.domain.common.types import generate_id
    from app.domain.activity.seed_examples import SEED_EXAMPLE_ACTIVITIES

    result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == rid,
        )
    )
    member_ids = [row[0] for row in result.all()]
    other_member_ids = [uid for uid in member_ids if uid != current_user.id]
    member_list = []
    if other_member_ids:
        from app.infra.db.repositories.user_repo import UserRepositoryImpl
        user_repo = UserRepositoryImpl(db)
        for uid in other_member_ids:
            user = await user_repo.get_by_id(uid)
            name = (user.display_name or (user.email.split("@")[0] if user and user.email else "Someone")) if user else "Someone"
            member_list.append({"id": uid, "name": name})

    gemini_key = (settings.gemini_api_key or "").strip()
    if gemini_key:
        partner_portrait = await person_portrait_repo.get_by_owner(other_member_ids[0], rid) if other_member_ids else None
        llm_activities = await activity_suggestion.generate_activities_llm(
            actor_user_id=current_user.id,
            relationship_id=rid,
            limit=10,
            duration_max_minutes=None,
            partner_portrait=partner_portrait,
            member_list=member_list,
            gemini_api_key=settings.gemini_api_key,
            include_debug=debug,
            llm_service=llm_service,
        )
        if llm_activities:
            return [
                ActivitySuggestionResponse(
                    id=a["id"],
                    title=a.get("title") or "Activity",
                    description=a.get("description") or a.get("title") or "Activity",
                    debug_prompt=a.get("llm_prompt"),
                    debug_response=a.get("llm_response"),
                    debug_source="llm",
                )
                for a in llm_activities
            ]

    # Persist each seed item so invite works (activity_template_id must exist)
    out = []
    for ex in SEED_EXAMPLE_ACTIVITIES[:10]:
        activity_id = generate_id()
        title = ex.get("title") or "Activity"
        description = ex.get("description") or ex.get("title") or "Activity"
        estimated_min = ex.get("estimated_minutes", 30)
        location = ex.get("recommended_location") or "any"
        rationale = ex.get("recommendation_rationale") or "Recommended for your relationship."
        rec_name = (ex.get("recommended_invitee_name") or "").strip()
        await activity_template_repo.create(
            activity_id=activity_id,
            title=title,
            relationship_types=["partner"],
            vibe_tags=["fun"],
            constraints={"duration_min": estimated_min, "location": location},
            steps_markdown_template=description,
            personalization_slots={
                "source": "seed_fallback",
                "recommended_for_relationship_id": rid,
                "recommended_for_actor_user_id": current_user.id,
                "recommended_invitee_name": rec_name or "Partner",
                "recommendation_rationale": rationale,
            },
            is_active=True,
        )
        out.append(
            ActivitySuggestionResponse(
                id=activity_id,
                title=title,
                description=description,
                debug_source="seed_fallback",
            )
        )
    return out
