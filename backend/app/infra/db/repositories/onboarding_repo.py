"""Onboarding repository implementation."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.infra.db.models.onboarding import OnboardingProgressModel


class OnboardingRepository:
    """Onboarding repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_progress(self, user_id: str) -> Optional[OnboardingProgressModel]:
        """Get onboarding progress for user."""
        result = await self.session.execute(
            select(OnboardingProgressModel).where(
                OnboardingProgressModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update_progress(
        self,
        user_id: str,
        profile_completed: Optional[bool] = None,
        voiceprint_completed: Optional[bool] = None,
        relationships_completed: Optional[bool] = None,
        consent_completed: Optional[bool] = None,
        device_setup_completed: Optional[bool] = None,
        done_completed: Optional[bool] = None,
    ) -> OnboardingProgressModel:
        """Create or update onboarding progress."""
        progress = await self.get_progress(user_id)
        
        if progress is None:
            progress = OnboardingProgressModel(
                user_id=user_id,
                profile_completed=profile_completed or False,
                voiceprint_completed=voiceprint_completed or False,
                relationships_completed=relationships_completed or False,
                consent_completed=consent_completed or False,
                device_setup_completed=device_setup_completed or False,
                done_completed=done_completed or False,
            )
            self.session.add(progress)
        else:
            if profile_completed is not None:
                progress.profile_completed = profile_completed
            if voiceprint_completed is not None:
                progress.voiceprint_completed = voiceprint_completed
            if relationships_completed is not None:
                progress.relationships_completed = relationships_completed
            if consent_completed is not None:
                progress.consent_completed = consent_completed
            if device_setup_completed is not None:
                progress.device_setup_completed = device_setup_completed
            if done_completed is not None:
                progress.done_completed = done_completed
            progress.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(progress)
        return progress
