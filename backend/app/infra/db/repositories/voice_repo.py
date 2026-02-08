"""Voice repository implementation."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.infra.db.models.voice import (
    VoiceEnrollmentModel,
    VoiceProfileModel,
    VoiceEnrollmentStatus,
)
from app.domain.common.types import generate_id


class VoiceRepository:
    """Voice repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_enrollment(self, user_id: str) -> VoiceEnrollmentModel:
        """Create a new voice enrollment."""
        enrollment = VoiceEnrollmentModel(
            id=generate_id(),
            user_id=user_id,
            status=VoiceEnrollmentStatus.STARTED,
        )
        self.session.add(enrollment)
        await self.session.commit()
        await self.session.refresh(enrollment)
        return enrollment

    async def get_enrollment(self, enrollment_id: str) -> Optional[VoiceEnrollmentModel]:
        """Get enrollment by ID."""
        result = await self.session.execute(
            select(VoiceEnrollmentModel).where(
                VoiceEnrollmentModel.id == enrollment_id
            )
        )
        return result.scalar_one_or_none()

    async def update_enrollment(
        self,
        enrollment_id: str,
        status: Optional[VoiceEnrollmentStatus] = None,
        audio_path: Optional[str] = None,
    ) -> VoiceEnrollmentModel:
        """Update enrollment."""
        enrollment = await self.get_enrollment(enrollment_id)
        if not enrollment:
            raise ValueError(f"Enrollment {enrollment_id} not found")
        
        if status is not None:
            enrollment.status = status
        if audio_path is not None:
            enrollment.audio_path = audio_path
        enrollment.updated_at = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(enrollment)
        return enrollment

    async def create_profile(
        self,
        user_id: str,
        quality_score: float,
        voice_sample_base64: str | None = None,
        voice_embedding_json: str | None = None,
    ) -> VoiceProfileModel:
        """Create a voice profile."""
        profile = VoiceProfileModel(
            id=generate_id(),
            user_id=user_id,
            quality_score=quality_score,
            voice_sample_base64=voice_sample_base64,
            voice_embedding_json=voice_embedding_json,
        )
        self.session.add(profile)
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def update_profile(
        self,
        user_id: str,
        quality_score: float | None = None,
        voice_sample_base64: str | None = None,
        voice_embedding_json: str | None = None,
    ) -> VoiceProfileModel | None:
        """Update voice profile for user. Returns profile or None if not found."""
        profile = await self.get_profile(user_id)
        if not profile:
            return None
        if quality_score is not None:
            profile.quality_score = quality_score
        if voice_sample_base64 is not None:
            profile.voice_sample_base64 = voice_sample_base64
        if voice_embedding_json is not None:
            profile.voice_embedding_json = voice_embedding_json
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def get_profile(self, user_id: str) -> Optional[VoiceProfileModel]:
        """Get voice profile for user."""
        result = await self.session.execute(
            select(VoiceProfileModel).where(
                VoiceProfileModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_profiles_by_user_ids(self, user_ids: list[str]) -> list[VoiceProfileModel]:
        if not user_ids:
            return []
        result = await self.session.execute(
            select(VoiceProfileModel).where(VoiceProfileModel.user_id.in_(user_ids))
        )
        return list(result.scalars().all())

    async def delete_profile(self, user_id: str) -> bool:
        """Delete voice profile for user. Returns True if a profile was deleted."""
        profile = await self.get_profile(user_id)
        if not profile:
            return False
        await self.session.delete(profile)
        await self.session.commit()
        return True
