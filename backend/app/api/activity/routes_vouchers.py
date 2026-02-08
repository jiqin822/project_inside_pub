"""Activity vouchers API: repair/amendment promises one partner can offer the other."""
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from app.domain.compass.models import USE_CASE_ACTIVITIES
from app.domain.kai import generate_repair_vouchers
from app.infra.db.models.relationship import relationship_members
from app.services.llm_service import LLMService
from app.settings import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class VoucherItem(BaseModel):
    """Single repair/amendment voucher (promise one partner can offer the other)."""
    title: str
    description: str


@router.get("", response_model=List[VoucherItem])
async def get_vouchers(
    relationship_id: str = Query(..., description="Relationship for which to generate vouchers"),
    limit: int = Query(5, ge=1, le=15, description="Max number of vouchers to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Get personalized repair/amendment vouchers (simple promises one partner can offer the other)."""
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

    other_member_ids = [uid for uid in member_ids if uid != current_user.id]
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
            member_list.append({"id": uid, "name": name})
    if not member_list:
        member_list.append({"id": "other", "name": "Partner"})

    bundle = await personalization.build_context_bundle(
        current_user.id, relationship_id, USE_CASE_ACTIVITIES
    )
    partner_portrait = None
    if other_member_ids:
        partner_portrait = await person_portrait_repo.get_by_owner(other_member_ids[0], relationship_id)
    context_text = personalization._build_llm_context_text(
        bundle,
        partner_portrait,
        member_list,
        None,
        [],
        actor_profile=None,
        partner_profiles=None,
        exclude_activity_titles=None,
    )

    gemini_key = (settings.gemini_api_key or "").strip()
    items = generate_repair_vouchers(
        compass_context_text=context_text,
        member_list=member_list,
        limit=limit,
        gemini_api_key=gemini_key or None,
        llm_service=llm_service,
    )
    return [VoucherItem(title=item["title"], description=item["description"]) for item in items]
