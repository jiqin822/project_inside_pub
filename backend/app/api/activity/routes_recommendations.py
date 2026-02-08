"""Compass recommendations API."""
import json
import logging
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
from pydantic import BaseModel
from typing import Optional, List

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from app.services.llm_service import LLMService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class SuggestedInvitee(BaseModel):
    """Suggested invitee (relationship member other than current user)."""
    id: str
    name: str


def _card_snapshot_from_recommendation(item: "ActivityRecommendationItem") -> dict:
    """Build card_snapshot dict for discover_feed_items from an ActivityRecommendationItem."""
    return {
        "id": item.id,
        "title": item.title,
        "description": item.steps_markdown_template or "",
        "vibe_tags": item.vibe_tags or [],
        "relationship_types": item.relationship_types or [],
        "constraints": item.constraints or {},
        "explanation": item.explanation,
        "recommended_invitee": item.recommended_invitee.model_dump() if item.recommended_invitee else None,
        "recommended_location": item.recommended_location,
        "suggested_invitees": [s.model_dump() for s in item.suggested_invitees] if item.suggested_invitees else [],
        "debug_source": item.debug_source,
        "debug_prompt": item.debug_prompt,
        "debug_response": item.debug_response,
    }


class ActivityRecommendationItem(BaseModel):
    """Single activity recommendation with explanation."""
    id: str
    title: str
    relationship_types: list
    vibe_tags: list
    risk_tags: Optional[list] = None
    constraints: Optional[dict] = None
    steps_markdown_template: Optional[str] = None
    variants: Optional[dict] = None
    safety_rules: Optional[dict] = None
    explanation: Optional[str] = None
    suggested_invitees: List[SuggestedInvitee] = []
    recommended_invitee: Optional[SuggestedInvitee] = None
    recommended_location: Optional[str] = None
    debug_prompt: Optional[str] = None
    debug_response: Optional[str] = None
    debug_source: Optional[str] = None  # "llm" | "seed_fallback" — where this activity came from (for debug UI)


@router.get("", response_model=List[ActivityRecommendationItem])
async def get_recommendations(
    request: Request,
    mode: str = Query(..., description="activities | economy | therapist | live_coach | dashboard"),
    relationship_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    vibe_tags: Optional[str] = Query(None),
    duration_max_minutes: Optional[int] = Query(None, description="Max duration in minutes (filter suggestions)"),
    relationship_type: str = Query("partner"),
    similar_to_activity_id: Optional[str] = Query(None, description="Generate more like this activity (by vibe_tags)"),
    use_llm: bool = Query(False, description="Use Gemini to generate personalized activities (requires gemini_api_key)"),
    stream: bool = Query(False, description="Stream activities as NDJSON as they are generated (requires use_llm=true)"),
    debug: bool = Query(False, description="Include LLM prompt/response in each item (for debug UI)"),
    exclude_titles: Optional[str] = Query(None, description="Comma-separated activity titles to exclude (e.g. previous set shown to user)"),
    query: Optional[str] = Query(None, description="e.g. 'something to do together', 'date ideas', 'reconnection' — focus suggestions on this theme"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Get personalized recommendations for the given mode and relationship."""
    raw_use_llm = request.query_params.get("use_llm")
    # Defensive: ensure use_llm is True when client sends use_llm=true (query string can be ambiguous)
    if raw_use_llm and str(raw_use_llm).lower() in ("true", "1", "yes"):
        use_llm = True
    if mode != "activities":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only mode=activities is supported in Phase 1",
        )
    if not relationship_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relationship_id is required for recommendations",
        )

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
    from app.domain.activity.services import ActivitySuggestionService
    from app.infra.db.repositories.event_repo import EventRepository
    from app.infra.db.repositories.memory_repo import MemoryRepository
    from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
    from app.infra.db.repositories.loop_repo import LoopRepository
    from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
    from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
    from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
    from app.infra.db.repositories.discover_feed_repo import DiscoverFeedRepository

    event_repo = EventRepository(db)
    memory_repo = MemoryRepository(db)
    person_portrait_repo = PersonPortraitRepository(db)
    dyad_portrait_repo = DyadPortraitRepository(db)
    loop_repo = LoopRepository(db)
    activity_template_repo = ActivityTemplateRepository(db)
    dyad_activity_repo = DyadActivityHistoryRepository(db)
    context_summary_repo = ContextSummaryRepository(db)
    discover_feed_repo = DiscoverFeedRepository(db)

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

    # Build suggested_invitees and member_list (id, name) for both DB and LLM paths
    other_member_ids = [uid for uid in member_ids if uid != current_user.id]
    suggested_invitees: List[SuggestedInvitee] = []
    member_list: List[dict] = []
    if other_member_ids:
        from app.infra.db.repositories.user_repo import UserRepositoryImpl
        user_repo = UserRepositoryImpl(db)
        for uid in other_member_ids:
            user = await user_repo.get_by_id(uid)
            raw = (user.display_name or (user.email.split("@")[0] if user and user.email else "Someone")) if user else "Someone"
            if raw and re.match(r"^User\s+[a-f0-9]{8}$", raw, re.I):
                raw = (user.email.split("@")[0] if user and user.email else None) or "Partner"
            name = raw or "Partner"
            suggested_invitees.append(SuggestedInvitee(id=uid, name=name))
            member_list.append({"id": uid, "name": name})

    from app.settings import settings
    from app.domain.common.types import generate_id
    from app.domain.activity.seed_examples import SEED_EXAMPLE_ACTIVITIES

    # LLM path: when gemini_api_key is set (and use_llm for opt-in if desired)
    gemini_key = (settings.gemini_api_key or "").strip()
    if not use_llm:
        logger.info("activity/recommendations: use_llm=false, using seed fallback")
    elif not gemini_key:
        logger.info("activity/recommendations: GEMINI_API_KEY not set or empty, using seed fallback")
    if gemini_key and use_llm:
        partner_portrait = None
        if other_member_ids:
            partner_portrait = await person_portrait_repo.get_by_owner(other_member_ids[0], relationship_id)
        # Load actor and partner profile context (interests, personal description, personality) for LLM prompt
        from app.infra.db.repositories.user_repo import UserRepositoryImpl as UserRepoImpl
        user_repo_llm = UserRepoImpl(db)
        actor_user = await user_repo_llm.get_by_id(current_user.id)
        actor_profile = None
        if actor_user:
            actor_profile = {
                "personal_description": getattr(actor_user, "personal_description", None),
                "hobbies": getattr(actor_user, "hobbies", None),
                "personality_type": getattr(actor_user, "personality_type", None),
            }
        partner_profiles = []
        for uid in other_member_ids:
            u = await user_repo_llm.get_by_id(uid)
            if u:
                partner_profiles.append({
                    "personal_description": getattr(u, "personal_description", None),
                    "hobbies": getattr(u, "hobbies", None),
                    "personality_type": getattr(u, "personality_type", None),
                })
        else:
            partner_profiles.append({})
        exclude_activity_titles: List[str] = []
        if exclude_titles and exclude_titles.strip():
            exclude_activity_titles = [t.strip() for t in exclude_titles.split(",") if t.strip()][:30]
        if stream:
            name_to_invitee = {inv.name: inv for inv in suggested_invitees}

            async def ndjson_stream():
                suggestion_ids = []
                async for item in activity_suggestion.generate_activities_llm_stream(
                    actor_user_id=current_user.id,
                    relationship_id=relationship_id,
                    limit=limit,
                    duration_max_minutes=duration_max_minutes,
                    partner_portrait=partner_portrait,
                    member_list=member_list,
                    gemini_api_key=settings.gemini_api_key,
                    include_debug=debug,
                    actor_profile=actor_profile,
                    partner_profiles=partner_profiles if partner_profiles else None,
                    exclude_activity_titles=exclude_activity_titles if exclude_activity_titles else None,
                    query=query,
                    llm_service=llm_service,
                ):
                    rec_name = (item.get("recommended_invitee_name") or "").strip()
                    recommended_invitee = name_to_invitee.get(rec_name) if rec_name else (suggested_invitees[0] if suggested_invitees else None)
                    out_item = ActivityRecommendationItem(
                        id=item["id"],
                        title=item["title"],
                        relationship_types=["partner"],
                        vibe_tags=item.get("vibe_tags") if isinstance(item.get("vibe_tags"), list) and item["vibe_tags"] else ["calm"],
                        risk_tags=[],
                        constraints={
                            "duration_min": item.get("estimated_minutes", 30),
                            "location": item.get("recommended_location") or "any",
                        },
                        steps_markdown_template=item.get("description") or "",
                        variants=None,
                        safety_rules=None,
                        explanation=item.get("recommendation_rationale") or "Recommended for your relationship.",
                        suggested_invitees=suggested_invitees,
                        recommended_invitee=recommended_invitee,
                        recommended_location=(item.get("recommended_location") or "").strip() or None,
                        debug_prompt=item.get("llm_prompt"),
                        debug_response=item.get("llm_response"),
                        debug_source="llm",
                    )
                    suggestion_ids.append(item["id"])
                    if out_item.recommended_invitee:
                        try:
                            await discover_feed_repo.create_feed_item(
                                relationship_id=relationship_id,
                                activity_template_id=out_item.id,
                                generated_by_user_id=current_user.id,
                                recommended_invitee_user_id=out_item.recommended_invitee.id,
                                card_snapshot=_card_snapshot_from_recommendation(out_item),
                            )
                        except Exception as e:
                            logger.warning("discover_feed create_feed_item (stream): %s", e)
                    yield json.dumps(out_item.model_dump()) + "\n"

            return StreamingResponse(ndjson_stream(), media_type="application/x-ndjson")
        llm_activities = await activity_suggestion.generate_activities_llm(
            actor_user_id=current_user.id,
            relationship_id=relationship_id,
            limit=limit,
            duration_max_minutes=duration_max_minutes,
            partner_portrait=partner_portrait,
            member_list=member_list,
            gemini_api_key=settings.gemini_api_key,
            include_debug=debug,
            actor_profile=actor_profile,
            partner_profiles=partner_profiles if partner_profiles else None,
            exclude_activity_titles=exclude_activity_titles if exclude_activity_titles else None,
            query=query,
            llm_service=llm_service,
        )
        if not llm_activities:
            logger.warning("activity/recommendations: Gemini returned no activities, using seed fallback")
        if llm_activities:
            out = []
            name_to_invitee = {inv.name: inv for inv in suggested_invitees}
            for item in llm_activities:
                rec_name = (item.get("recommended_invitee_name") or "").strip()
                recommended_invitee = name_to_invitee.get(rec_name) if rec_name else (suggested_invitees[0] if suggested_invitees else None)
                out.append(
                    ActivityRecommendationItem(
                        id=item["id"],
                        title=item["title"],
                        relationship_types=["partner"],
                        vibe_tags=item.get("vibe_tags") if isinstance(item.get("vibe_tags"), list) and item["vibe_tags"] else ["calm"],
                        risk_tags=[],
                        constraints={
                            "duration_min": item.get("estimated_minutes", 30),
                            "location": item.get("recommended_location") or "any",
                        },
                        steps_markdown_template=item.get("description") or "",
                        variants=None,
                        safety_rules=None,
                        explanation=item.get("recommendation_rationale") or "Recommended for your relationship.",
                        suggested_invitees=suggested_invitees,
                        recommended_invitee=recommended_invitee,
                        recommended_location=(item.get("recommended_location") or "").strip() or None,
                        debug_prompt=item.get("llm_prompt"),
                        debug_response=item.get("llm_response"),
                        debug_source="llm",
                    )
                )
            await event_repo.append(
                type="activity_suggestions_generated",
                actor_user_id=current_user.id,
                relationship_id=relationship_id,
                payload={
                    "suggestion_ids": [a["id"] for a in llm_activities],
                    "count": len(llm_activities),
                    "source": "llm",
                },
                source="activity",
            )
            for rec_item in out:
                if rec_item.recommended_invitee:
                    try:
                        await discover_feed_repo.create_feed_item(
                            relationship_id=relationship_id,
                            activity_template_id=rec_item.id,
                            generated_by_user_id=current_user.id,
                            recommended_invitee_user_id=rec_item.recommended_invitee.id,
                            card_snapshot=_card_snapshot_from_recommendation(rec_item),
                        )
                    except Exception as e:
                        logger.warning("discover_feed create_feed_item (llm): %s", e)
            return out

    # Seed fallback: when no key or LLM returned empty — persist each so invite works
    out = []
    name_to_invitee = {inv.name: inv for inv in suggested_invitees}
    for ex in SEED_EXAMPLE_ACTIVITIES[: min(limit, len(SEED_EXAMPLE_ACTIVITIES))]:
        activity_id = generate_id()
        title = ex.get("title") or "Activity"
        estimated_min = ex.get("estimated_minutes", 30)
        location = ex.get("recommended_location") or "any"
        description = ex.get("description") or ""
        rationale = ex.get("recommendation_rationale") or "Recommended for your relationship."
        rec_name = (ex.get("recommended_invitee_name") or "").strip()
        recommended_invitee = name_to_invitee.get(rec_name) if rec_name else (suggested_invitees[0] if suggested_invitees else None)
        loc = location.strip() or None

        await activity_template_repo.create(
            activity_id=activity_id,
            title=title,
            relationship_types=["partner"],
            vibe_tags=["fun"],
            constraints={"duration_min": estimated_min, "location": location},
            steps_markdown_template=description,
            personalization_slots={
                "source": "seed_fallback",
                "recommended_for_relationship_id": relationship_id,
                "recommended_for_actor_user_id": current_user.id,
                "recommended_invitee_name": rec_name or (suggested_invitees[0].name if suggested_invitees else "Partner"),
                "recommendation_rationale": rationale,
            },
            is_active=True,
        )

        out.append(
            ActivityRecommendationItem(
                id=activity_id,
                title=title,
                relationship_types=["partner"],
                vibe_tags=["fun"],
                risk_tags=[],
                constraints={"duration_min": estimated_min, "location": location},
                steps_markdown_template=description,
                variants=None,
                safety_rules=None,
                explanation=rationale,
                suggested_invitees=suggested_invitees,
                recommended_invitee=recommended_invitee,
                recommended_location=loc,
                debug_source="seed_fallback",
            )
        )
    await event_repo.append(
        type="activity_suggestions_generated",
        actor_user_id=current_user.id,
        relationship_id=relationship_id,
        payload={
            "suggestion_ids": [a.id for a in out],
            "count": len(out),
            "source": "seed_fallback",
        },
        source="activity",
    )
    for rec_item in out:
        if rec_item.recommended_invitee:
            try:
                await discover_feed_repo.create_feed_item(
                    relationship_id=relationship_id,
                    activity_template_id=rec_item.id,
                    generated_by_user_id=current_user.id,
                    recommended_invitee_user_id=rec_item.recommended_invitee.id,
                    card_snapshot=_card_snapshot_from_recommendation(rec_item),
                )
            except Exception as e:
                logger.warning("discover_feed create_feed_item (seed): %s", e)
    return out


class FeedbackRequest(BaseModel):
    """Activity feedback for recommendation loop (rating + tags)."""
    relationship_id: str
    activity_template_id: str
    rating: Optional[float] = None  # e.g. 1–5
    outcome_tags: Optional[List[str]] = None  # e.g. ["fun", "reconnect", "quick"]


class FeedbackResponse(BaseModel):
    """Feedback recorded."""
    record_id: str
    created_at: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit activity feedback (rating + tags) for the recommendation engine. Writes to dyad_activity_history and emits activity_completed event."""
    from app.infra.db.models.relationship import relationship_members
    from sqlalchemy import select
    from app.infra.db.repositories.event_repo import EventRepository
    from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository

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

    now = datetime.utcnow()
    dyad_repo = DyadActivityHistoryRepository(db)
    record = await dyad_repo.append(
        relationship_id=request.relationship_id,
        activity_template_id=request.activity_template_id,
        actor_user_id=current_user.id,
        started_at=now,
        completed_at=now,
        rating=request.rating,
        outcome_tags=request.outcome_tags,
    )

    event_repo = EventRepository(db)
    await event_repo.append(
        type="activity_completed",
        actor_user_id=current_user.id,
        relationship_id=request.relationship_id,
        payload={
            "activity_template_id": request.activity_template_id,
            "rating": request.rating,
            "outcome_tags": request.outcome_tags,
        },
        source="activity",
    )

    created_at_str = record.created_at.isoformat() + "Z" if record.created_at else ""
    return FeedbackResponse(record_id=record.id, created_at=created_at_str)
