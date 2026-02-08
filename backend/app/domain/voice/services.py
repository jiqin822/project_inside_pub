"""Voice domain services."""
import base64
import json
import logging
from pathlib import Path
from typing import Optional
from app.domain.common.errors import NotFoundError
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.db.models.voice import VoiceEnrollmentStatus
from app.domain.common.types import generate_id
from app.infra.vendors.voiceprint_client import VoiceprintClient
from app.domain.voice.embeddings import compute_embedding_from_wav_bytes

logger = logging.getLogger(__name__)


class VoiceService:
    """Voice service. Enrollment stores voice sample in DB for Live Coach; optional voiceprint-api for identify_speaker."""

    def __init__(
        self,
        voice_repo: VoiceRepository,
        voiceprint_client: Optional[VoiceprintClient] = None,
        audio_storage_path: str = "storage/audio",
    ):
        self.voice_repo = voice_repo
        self.voiceprint_client = voiceprint_client or VoiceprintClient()
        self.audio_storage_path = Path(audio_storage_path)
        self.audio_storage_path.mkdir(parents=True, exist_ok=True)

    async def start_enrollment(self, user_id: str) -> dict:
        """Start voice enrollment."""
        enrollment = await self.voice_repo.create_enrollment(user_id)
        return {
            "enrollment_id": enrollment.id,
            "upload_url": None,  # MVP: direct PUT to API
        }

    async def upload_audio(
        self,
        enrollment_id: str,
        audio_bytes: bytes,
    ) -> None:
        """Upload audio for enrollment."""
        if not audio_bytes or len(audio_bytes) == 0:
            raise ValueError("No audio data: recording is empty. Please record again and speak for a few seconds.")
        enrollment = await self.voice_repo.get_enrollment(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment", enrollment_id)

        # Store audio file
        audio_file = self.audio_storage_path / f"{enrollment_id}.wav"
        audio_file.write_bytes(audio_bytes)
        
        # Update enrollment
        await self.voice_repo.update_enrollment(
            enrollment_id,
            status=VoiceEnrollmentStatus.UPLOADED,
            audio_path=str(audio_file),
        )

    async def complete_enrollment(
        self,
        enrollment_id: str,
        user_id: str,
    ) -> dict:
        """Complete voice enrollment."""
        enrollment = await self.voice_repo.get_enrollment(enrollment_id)
        if not enrollment:
            raise NotFoundError("Enrollment", enrollment_id)
        
        if enrollment.user_id != user_id:
            raise ValueError("Enrollment does not belong to user")
        
        if not enrollment.audio_path:
            raise ValueError("No audio uploaded for enrollment")
        
        # Read audio file and store as base64 in DB (for Live Coach identification on login)
        audio_file = Path(enrollment.audio_path)
        if not audio_file.exists():
            raise ValueError("Audio file not found")

        audio_bytes = audio_file.read_bytes()
        voice_sample_base64 = base64.b64encode(audio_bytes).decode("ascii")

        # Compute voice embedding (if encoder available)
        embedding = compute_embedding_from_wav_bytes(audio_bytes)
        voice_embedding_json = json.dumps(embedding) if embedding else None

        # Quality score from audio length (rough estimate)
        audio_duration_estimate = len(audio_bytes) / 16000 / 2
        quality_score = min(0.95, 0.7 + (audio_duration_estimate / 10.0) * 0.25)

        existing_profile = await self.voice_repo.get_profile(user_id)
        if existing_profile:
            await self.voice_repo.update_profile(
                user_id,
                quality_score=quality_score,
                voice_sample_base64=voice_sample_base64,
                voice_embedding_json=voice_embedding_json,
            )
            profile = await self.voice_repo.get_profile(user_id)
        else:
            profile = await self.voice_repo.create_profile(
                user_id,
                quality_score,
                voice_sample_base64=voice_sample_base64,
                voice_embedding_json=voice_embedding_json,
            )
        
        # Update enrollment
        await self.voice_repo.update_enrollment(
            enrollment_id,
            status=VoiceEnrollmentStatus.COMPLETED,
        )
        
        return {
            "voice_profile_id": profile.id,
            "quality_score": quality_score,
        }

    async def delete_profile(self, user_id: str) -> bool:
        """Delete the current user's voice profile (voice print). Returns True if deleted."""
        return await self.voice_repo.delete_profile(user_id)

    async def identify_speaker(
        self,
        candidate_user_ids: list[str],
        audio_bytes: bytes,
    ) -> tuple[Optional[str], float]:
        """
        Identify speaker from audio.
        
        Args:
            candidate_user_ids: List of user IDs to match against
            audio_bytes: Audio file bytes
            
        Returns:
            Tuple of (user_id if match found, similarity score)
        """
        if not candidate_user_ids:
            return None, 0.0
        
        try:
            speaker_id, score = await self.voiceprint_client.identify_voiceprint(
                speaker_ids=candidate_user_ids,
                audio_bytes=audio_bytes,
            )
            return speaker_id, score
        except Exception as e:
            logger.error(f"Voiceprint identification failed: {e}")
            return None, 0.0