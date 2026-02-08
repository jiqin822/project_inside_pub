"""Compass context API: full bundle or LLM Q&A for Kai."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from app.services.llm_service import LLMService

router = APIRouter()


@router.get("", response_model=str)
async def get_context(
    query: Optional[str] = Query(None, description="Optional question; if set, returns LLM answer over context"),
    relationship_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Return Compass context for Kai. If query is empty, returns full profile text.
    If query is set, returns LLM-derived answer over profile + unstructured memories.
    """
    from app.domain.compass.services import PersonalizationService
    from app.infra.db.repositories.event_repo import EventRepository
    from app.infra.db.repositories.memory_repo import MemoryRepository
    from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
    from app.infra.db.repositories.loop_repo import LoopRepository
    from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
    from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
    from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
    from app.infra.db.repositories.unstructured_memory_repo import UnstructuredMemoryRepository
    from app.infra.db.repositories.user_repo import UserRepositoryImpl

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

    user_repo = UserRepositoryImpl(db)
    user = await user_repo.get_by_id(current_user.id)
    actor_profile = None
    if user:
        actor_profile = {
            "personal_description": getattr(user, "personal_description", None),
            "hobbies": getattr(user, "hobbies", None),
            "personality_type": getattr(user, "personality_type", None),
        }

    def llm_generate(prompt: str):
        return llm_service.generate_text(prompt)

    text = await personalization.get_context_for_query(
        user_id=current_user.id,
        question=query,
        relationship_id=relationship_id,
        actor_profile=actor_profile,
        llm_generate_text=llm_generate,
    )
    return text
