"""Voice enrollment routes."""
import logging
from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.voice.services import VoiceService
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.vendors.voiceprint_client import VoiceprintClient

logger = logging.getLogger(__name__)

router = APIRouter()


class VoiceEnrollmentStartResponse(BaseModel):
    """Voice enrollment start response."""
    enrollment_id: str
    upload_url: str | None = None


class VoiceEnrollmentCompleteResponse(BaseModel):
    """Voice enrollment complete response."""
    voice_profile_id: str
    quality_score: float


@router.post("/enrollment/start", response_model=VoiceEnrollmentStartResponse)
async def start_voice_enrollment(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start voice enrollment."""
    voice_repo = VoiceRepository(db)
    voiceprint_client = VoiceprintClient()
    voice_service = VoiceService(voice_repo, voiceprint_client)
    
    result = await voice_service.start_enrollment(current_user.id)
    return VoiceEnrollmentStartResponse(**result)


@router.put("/enrollment/{enrollment_id}/audio")
async def upload_enrollment_audio(
    enrollment_id: str,
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload audio for enrollment."""
    try:
        logger.info(f"Uploading audio for enrollment {enrollment_id} by user {current_user.id}")
        voice_repo = VoiceRepository(db)
        voiceprint_client = VoiceprintClient()
        voice_service = VoiceService(voice_repo, voiceprint_client)
        
        # Verify enrollment belongs to user
        enrollment = await voice_repo.get_enrollment(enrollment_id)
        if not enrollment:
            logger.warning(f"Enrollment {enrollment_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enrollment not found",
            )
        if enrollment.user_id != current_user.id:
            logger.warning(f"Enrollment {enrollment_id} does not belong to user {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Enrollment does not belong to user",
            )
        
        # Read audio bytes
        audio_bytes = await audio.read()
        logger.info(f"Received {len(audio_bytes)} bytes of audio data")
        if not audio_bytes or len(audio_bytes) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recording is empty. Please record again and speak for a few seconds.",
            )

        await voice_service.upload_audio(enrollment_id, audio_bytes)
        logger.info(f"Successfully uploaded audio for enrollment {enrollment_id}")
        return {"ok": True}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error uploading audio for enrollment {enrollment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload audio: {str(e)}",
        )


@router.post("/enrollment/{enrollment_id}/complete", response_model=VoiceEnrollmentCompleteResponse)
async def complete_voice_enrollment(
    enrollment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete voice enrollment."""
    voice_repo = VoiceRepository(db)
    voiceprint_client = VoiceprintClient()
    voice_service = VoiceService(voice_repo, voiceprint_client)
    
    result = await voice_service.complete_enrollment(enrollment_id, current_user.id)
    return VoiceEnrollmentCompleteResponse(**result)


@router.delete("/profile")
async def delete_voice_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete the current user's voice profile (voice print)."""
    voice_repo = VoiceRepository(db)
    voiceprint_client = VoiceprintClient()
    voice_service = VoiceService(voice_repo, voiceprint_client)
    deleted = await voice_service.delete_profile(current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No voice profile found",
        )
    return {"ok": True}


class VoiceFeedbackRequest(BaseModel):
    """Request body for POST /voice/feedback (Me / Not me in Live Coach)."""
    segment_id: int
    is_me: bool
    audio_segment_base64: str | None = None


class VoiceFeedbackResponse(BaseModel):
    """Response for POST /voice/feedback."""
    success: bool = True


@router.post("/feedback", response_model=VoiceFeedbackResponse)
async def submit_voice_feedback(
    body: VoiceFeedbackRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submit speaker feedback for an STT segment ("that was me" or "that wasn't me").
    Used by Live Coach so the user can correct misattribution. Accepts and returns success;
    future use: associate segment embedding with user when is_me and update centroid.
    """
    # Acknowledge feedback; optional: look up STT session by user and store feedback for centroid update
    logger.debug("Voice feedback: user_id=%s segment_id=%s is_me=%s", current_user.id[:8] if current_user.id else None, body.segment_id, body.is_me)
    return VoiceFeedbackResponse(success=True)


class IdentifySpeakerResponse(BaseModel):
    """Identify speaker response."""
    user_id: str | None
    similarity_score: float


@router.post("/identify", response_model=IdentifySpeakerResponse)
async def identify_speaker(
    candidate_user_ids: str = Form(..., description="Comma-separated list of user IDs to match against"),
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Identify speaker from audio.
    
    Requires authentication. The candidate_user_ids should be users
    the current user has relationships with.
    
    Args:
        candidate_user_ids: Comma-separated list of user IDs to match against
        audio: WAV audio file
    """
    voice_repo = VoiceRepository(db)
    voiceprint_client = VoiceprintClient()
    voice_service = VoiceService(voice_repo, voiceprint_client)
    
    # Parse candidate user IDs
    user_ids = [uid.strip() for uid in candidate_user_ids.split(",") if uid.strip()]
    
    # Read audio bytes
    audio_bytes = await audio.read()
    
    # Identify speaker
    user_id, score = await voice_service.identify_speaker(
        candidate_user_ids=user_ids,
        audio_bytes=audio_bytes,
    )
    
    return IdentifySpeakerResponse(
        user_id=user_id,
        similarity_score=score,
    )
