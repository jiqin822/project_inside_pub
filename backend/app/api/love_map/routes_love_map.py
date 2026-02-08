"""Love Map API routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.compass.models import EventSource
from app.services.llm_service import LLMService
from app.services.notification_service import deliver_notification

logger = logging.getLogger(__name__)
from app.domain.admin.models import User
from app.domain.love_map.services import LoveMapService
from app.domain.love_map.models import QuizQuestion
from app.infra.db.repositories.love_map_repo import (
    MapPromptRepositoryImpl,
    UserSpecRepositoryImpl,
    RelationshipMapProgressRepositoryImpl,
)
from app.settings import settings

router = APIRouter()


# Request/Response Models
class MapPromptResponse(BaseModel):
    """Map prompt response."""
    id: str
    category: str
    difficulty_tier: int
    question_template: str
    input_prompt: str
    is_active: bool


class UserSpecRequest(BaseModel):
    """User spec request."""
    prompt_id: str
    answer_text: str


class UserSpecResponse(BaseModel):
    """User spec response."""
    id: str
    user_id: str
    prompt_id: str
    answer_text: str
    last_updated: str


class MapProgressResponse(BaseModel):
    """Map progress response."""
    level_tier: int
    current_xp: int
    stars: dict
    locked_levels: List[int]
    unlocked_levels: List[int]
    total_specs_count: int
    specs_by_tier: dict


class QuizGenerateRequest(BaseModel):
    """Quiz generation request."""
    subject_id: str
    tier: int


class QuizQuestionResponse(BaseModel):
    """Quiz question response."""
    question_id: str
    question_text: str
    options: List[str]
    correct_option_index: int
    prompt_id: str
    category: str
    difficulty_tier: int


class QuizCompleteRequest(BaseModel):
    """Quiz completion request."""
    subject_id: str
    tier: int
    score: int  # Number of correct answers
    total_questions: int


class QuizCompleteResponse(BaseModel):
    """Quiz completion response."""
    level_tier: int
    current_xp: int
    stars: dict
    xp_gained: int


class SuggestPromptItem(BaseModel):
    """Single suggested love map question from Kai (to confirm or fill Compass profile)."""
    question_template: str
    input_prompt: str
    category: str


class SuggestPromptsRequest(BaseModel):
    """Request for Kai to suggest love map questions for a subject's profile."""
    subject_id: str
    tier: int
    relationship_id: Optional[str] = None


# Specification Management
@router.get("/prompts", response_model=List[MapPromptResponse])
async def get_prompts(
    status: Optional[str] = Query(None, description="Filter by status: 'unanswered'"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get prompts. If status=unanswered, returns prompts user hasn't answered."""
    prompt_repo = MapPromptRepositoryImpl(db)
    
    if status == "unanswered":
        prompts = await prompt_repo.get_unanswered_by_user(current_user.id)
    else:
        prompts = await prompt_repo.get_all_active()
    
    return [
        MapPromptResponse(
            id=p.id,
            category=p.category,
            difficulty_tier=p.difficulty_tier,
            question_template=p.question_template,
            input_prompt=p.input_prompt,
            is_active=p.is_active,
        )
        for p in prompts
    ]


@router.post("/specs", response_model=UserSpecResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_spec(
    request: UserSpecRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Create or update a user spec."""
    prompt_repo = MapPromptRepositoryImpl(db)
    spec_repo = UserSpecRepositoryImpl(db)
    progress_repo = RelationshipMapProgressRepositoryImpl(db)

    service = LoveMapService(
        prompt_repo, spec_repo, progress_repo,
        gemini_api_key=settings.gemini_api_key or None,
        llm_service=llm_service,
    )

    try:
        spec = await service.create_or_update_spec(
            current_user.id, request.prompt_id, request.answer_text
        )
        # Emit event to Insider Compass for portrait/context extraction (plan §7).
        try:
            from app.domain.compass.services import EventIngestService, ConsolidationService
            from app.infra.db.repositories.event_repo import EventRepository
            from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
            from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
            from app.infra.db.repositories.memory_repo import MemoryRepository

            event_repo = EventRepository(db)
            consolidation = ConsolidationService(
                event_repo=event_repo,
                person_portrait_repo=PersonPortraitRepository(db),
                dyad_portrait_repo=DyadPortraitRepository(db),
                context_summary_repo=ContextSummaryRepository(db),
                memory_repo=MemoryRepository(db),
            )
            event_ingest = EventIngestService(
                event_repo=event_repo,
                consolidation_service=consolidation,
                consolidation_threshold=settings.compass_consolidation_threshold,
            )
            await event_ingest.ingest(
                type="love_map_spec",
                actor_user_id=current_user.id,
                payload={"prompt_id": request.prompt_id, "answer_text": request.answer_text},
                source=EventSource.LOVE_MAP.value,
                relationship_id=None,
                privacy_scope="private",
                db=db,
            )
        except Exception as ingest_err:
            logger.warning("Compass event ingest after UserSpec save failed: %s", ingest_err, exc_info=True)
        return UserSpecResponse(
            id=spec.id,
            user_id=spec.user_id,
            prompt_id=spec.prompt_id,
            answer_text=spec.answer_text,
            last_updated=spec.last_updated.isoformat(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Gameplay
@router.get("/progress/{subject_id}", response_model=MapProgressResponse)
async def get_progress(
    subject_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get map progress for a relationship."""
    prompt_repo = MapPromptRepositoryImpl(db)
    spec_repo = UserSpecRepositoryImpl(db)
    progress_repo = RelationshipMapProgressRepositoryImpl(db)
    
    service = LoveMapService(prompt_repo, spec_repo, progress_repo)
    
    try:
        progress_status = await service.get_progress_status(
            current_user.id, subject_id
        )
        return MapProgressResponse(
            level_tier=progress_status.level_tier,
            current_xp=progress_status.current_xp,
            stars=progress_status.stars,
            locked_levels=progress_status.locked_levels,
            unlocked_levels=progress_status.unlocked_levels,
            total_specs_count=progress_status.total_specs_count,
            specs_by_tier=progress_status.specs_by_tier,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/quiz/generate", response_model=List[QuizQuestionResponse])
async def generate_quiz(
    request: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate quiz questions for a tier."""
    prompt_repo = MapPromptRepositoryImpl(db)
    spec_repo = UserSpecRepositoryImpl(db)
    progress_repo = RelationshipMapProgressRepositoryImpl(db)

    service = LoveMapService(
        prompt_repo, spec_repo, progress_repo,
        gemini_api_key=settings.gemini_api_key or None,
        llm_service=llm_service,
    )
    
    try:
        questions = await service.generate_quiz(
            current_user.id, request.subject_id, request.tier
        )
        return [
            QuizQuestionResponse(
                question_id=q.question_id,
                question_text=q.question_text,
                options=q.options,
                correct_option_index=q.correct_option_index,
                prompt_id=q.prompt_id,
                category=q.category,
                difficulty_tier=q.difficulty_tier,
            )
            for q in questions
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/quiz/complete", response_model=QuizCompleteResponse)
async def complete_quiz(
    request: QuizCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete a quiz and update progress."""
    prompt_repo = MapPromptRepositoryImpl(db)
    spec_repo = UserSpecRepositoryImpl(db)
    progress_repo = RelationshipMapProgressRepositoryImpl(db)
    
    service = LoveMapService(prompt_repo, spec_repo, progress_repo)
    
    try:
        progress = await service.complete_quiz(
            current_user.id,
            request.subject_id,
            request.tier,
            request.score,
            request.total_questions,
        )
        
        # Calculate XP gained
        xp_gained = request.score * 10
        await deliver_notification(
            db,
            current_user.id,
            "love_map",
            "Love Map",
            f"You advanced! +{xp_gained} XP. Level {progress.level_tier}.",
        )
        
        return QuizCompleteResponse(
            level_tier=progress.level_tier,
            current_xp=progress.current_xp,
            stars=progress.stars or {},
            xp_gained=xp_gained,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/suggest-prompts", response_model=List[SuggestPromptItem])
async def suggest_prompts_for_profile(
    request: SuggestPromptsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Suggest love map questions to confirm or fill gaps in the subject's Compass profile.
    Uses Compass get_user_profile_text_for_kai(subject_id) and Kai.generate_love_map_questions_for_profile.
    """
    if llm_service is None and not (settings.gemini_api_key and (settings.gemini_api_key or "").strip()):
        return []
    try:
        from app.domain.compass.services import PersonalizationService
        from app.domain.kai import generate_love_map_questions_for_profile
        from app.infra.db.repositories.event_repo import EventRepository
        from app.infra.db.repositories.memory_repo import MemoryRepository
        from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
        from app.infra.db.repositories.loop_repo import LoopRepository
        from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
        from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
        from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
        from app.infra.db.repositories.things_to_find_out_repo import ThingsToFindOutRepository
        from app.infra.db.repositories.user_repo import UserRepositoryImpl
        from app.infra.db.repositories.love_map_repo import MapPromptRepositoryImpl

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
        user_repo = UserRepositoryImpl(db)
        subject_user = await user_repo.get_by_id(request.subject_id)
        subject_profile = None
        if subject_user:
            subject_profile = {
                "personal_description": getattr(subject_user, "personal_description", None),
                "hobbies": getattr(subject_user, "hobbies", None),
                "personality_type": getattr(subject_user, "personality_type", None),
            }
        compass_profile_subject_text = await personalization.get_love_map_design_context(
            relationship_id=request.relationship_id,
            actor_user_id=current_user.id,
            subject_id=request.subject_id,
            subject_profile=subject_profile,
        )
        prompt_repo = MapPromptRepositoryImpl(db)
        existing = await prompt_repo.get_by_tier(request.tier)
        existing_prompt_ids = [p.id for p in existing[:30]] if existing else None
        subject_display_name = "your partner"
        if subject_user:
            subject_display_name = (getattr(subject_user, "display_name", None) or (getattr(subject_user, "email", "") or "").split("@")[0]) or subject_display_name
        suggestions = generate_love_map_questions_for_profile(
            observer_id=current_user.id,
            subject_id=request.subject_id,
            compass_profile_subject_text=compass_profile_subject_text,
            tier=request.tier,
            gemini_api_key=settings.gemini_api_key,
            existing_prompt_ids=existing_prompt_ids,
            subject_display_name=subject_display_name,
            llm_service=llm_service,
        )
        return [
            SuggestPromptItem(
                question_template=s["question_template"],
                input_prompt=s["input_prompt"],
                category=s["category"],
            )
            for s in (suggestions or [])
        ]
    except Exception as e:
        logger.warning("Love map suggest_prompts_for_profile failed: %s", e, exc_info=True)
        return []
