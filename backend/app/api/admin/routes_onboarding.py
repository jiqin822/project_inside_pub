"""Onboarding routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.onboarding.services import OnboardingService
from app.infra.db.repositories.onboarding_repo import OnboardingRepository
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.db.repositories.invite_repo import InviteRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl

logger = logging.getLogger(__name__)

router = APIRouter()


class OnboardingStatusResponse(BaseModel):
    """Onboarding status response."""
    has_profile: bool
    has_voiceprint: bool
    pending_invites: int
    active_relationships: int
    next_step: str | None = None


class CompleteStepRequest(BaseModel):
    """Complete step request."""
    step: str


class CompleteStepResponse(BaseModel):
    """Complete step response."""
    ok: bool = True


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get onboarding status."""
    try:
        logger.info(f"Getting onboarding status for user {current_user.id}")
        onboarding_repo = OnboardingRepository(db)
        user_repo = UserRepositoryImpl(db)
        voice_repo = VoiceRepository(db)
        invite_repo = InviteRepository(db)
        relationship_repo = RelationshipRepositoryImpl(db)
        
        service = OnboardingService(
            onboarding_repo=onboarding_repo,
            user_repo=user_repo,
            voice_repo=voice_repo,
            invite_repo=invite_repo,
            relationship_repo=relationship_repo,
            session=db,
        )
        
        status_data = await service.get_status(current_user.id)
        logger.info(f"Onboarding status for user {current_user.id}: {status_data}")
        return OnboardingStatusResponse(**status_data)
    except Exception as e:
        logger.error(f"Error getting onboarding status for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get onboarding status: {str(e)}",
        )


@router.post("/complete", response_model=CompleteStepResponse)
async def complete_step(
    request: CompleteStepRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete an onboarding step."""
    onboarding_repo = OnboardingRepository(db)
    user_repo = UserRepositoryImpl(db)
    voice_repo = VoiceRepository(db)
    invite_repo = InviteRepository(db)
    relationship_repo = RelationshipRepositoryImpl(db)
    
    service = OnboardingService(
        onboarding_repo=onboarding_repo,
        user_repo=user_repo,
        voice_repo=voice_repo,
        invite_repo=invite_repo,
        relationship_repo=relationship_repo,
        session=db,
    )
    
    await service.complete_step(current_user.id, request.step)
    return CompleteStepResponse(ok=True)
