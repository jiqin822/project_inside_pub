"""Onboarding domain services."""
from typing import Optional
from app.domain.common.errors import NotFoundError
from app.infra.db.repositories.onboarding_repo import OnboardingRepository
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.db.repositories.invite_repo import InviteRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from sqlalchemy.ext.asyncio import AsyncSession


class OnboardingService:
    """Onboarding service."""

    def __init__(
        self,
        onboarding_repo: OnboardingRepository,
        user_repo: UserRepositoryImpl,
        voice_repo: VoiceRepository,
        invite_repo: InviteRepository,
        relationship_repo: RelationshipRepositoryImpl,
        session: AsyncSession,
    ):
        self.onboarding_repo = onboarding_repo
        self.user_repo = user_repo
        self.voice_repo = voice_repo
        self.invite_repo = invite_repo
        self.relationship_repo = relationship_repo
        self.session = session

    async def get_status(self, user_id: str) -> dict:
        """Get onboarding status."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)

        progress = await self.onboarding_repo.get_progress(user_id)
        
        # has_profile
        has_profile = bool(
            user.display_name or 
            (progress and getattr(progress, 'profile_completed', False))
        )
        
        # has_voiceprint
        voice_profile = await self.voice_repo.get_profile(user_id)
        has_voiceprint = bool(
            voice_profile is not None or 
            (progress and getattr(progress, 'voiceprint_completed', False))
        )
        
        # pending_invites
        pending_invites = await self.invite_repo.get_pending_invites_by_email(user.email)
        pending_count = len(pending_invites)
        
        # active_relationships
        relationships = await self.relationship_repo.list_by_user(user_id)
        from app.infra.db.models.relationship import RelationshipStatus
        active_count = 0
        for r in relationships:
            # Handle both enum and string status
            if isinstance(r.status, RelationshipStatus):
                if r.status == RelationshipStatus.ACTIVE:
                    active_count += 1
            elif isinstance(r.status, str):
                if r.status.upper() == "ACTIVE" or r.status.lower() == "active":
                    active_count += 1
            else:
                # Fallback: convert to string and check
                status_str = str(r.status).upper()
                if status_str == "ACTIVE":
                    active_count += 1
        
        # next_step
        next_step = None
        if not (progress and progress.profile_completed):
            next_step = "PROFILE"
        elif not (progress and progress.voiceprint_completed):
            next_step = "VOICEPRINT"
        elif not (progress and progress.relationships_completed):
            next_step = "RELATIONSHIPS"
        elif not (progress and progress.consent_completed):
            next_step = "CONSENT"
        elif not (progress and progress.device_setup_completed):
            next_step = "DEVICE_SETUP"
        elif not (progress and progress.done_completed):
            next_step = "DONE"
        
        return {
            "has_profile": has_profile,
            "has_voiceprint": has_voiceprint,
            "pending_invites": pending_count,
            "active_relationships": active_count,
            "next_step": next_step,
        }

    async def complete_step(self, user_id: str, step: str) -> None:
        """Complete an onboarding step."""
        step_upper = step.upper()
        
        if step_upper == "PROFILE":
            await self.onboarding_repo.create_or_update_progress(
                user_id, profile_completed=True
            )
        elif step_upper in ["VOICEPRINT", "VOICEPRINT_SKIPPED"]:
            await self.onboarding_repo.create_or_update_progress(
                user_id, voiceprint_completed=True
            )
        elif step_upper == "RELATIONSHIPS":
            await self.onboarding_repo.create_or_update_progress(
                user_id, relationships_completed=True
            )
        elif step_upper == "CONSENT":
            await self.onboarding_repo.create_or_update_progress(
                user_id, consent_completed=True
            )
        elif step_upper == "DEVICE_SETUP":
            await self.onboarding_repo.create_or_update_progress(
                user_id, device_setup_completed=True
            )
        elif step_upper == "DONE":
            await self.onboarding_repo.create_or_update_progress(
                user_id, done_completed=True
            )
