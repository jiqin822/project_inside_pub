"""Voice enrollment database models."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Text, Enum as SQLEnum
import enum

from app.infra.db.base import Base


class VoiceEnrollmentStatus(str, enum.Enum):
    """Voice enrollment status enum."""
    STARTED = "STARTED"
    UPLOADED = "UPLOADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VoiceEnrollmentModel(Base):
    """Voice enrollment database model."""

    __tablename__ = "voice_enrollments"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(SQLEnum(VoiceEnrollmentStatus), nullable=False, default=VoiceEnrollmentStatus.STARTED)
    audio_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class VoiceProfileModel(Base):
    """Voice profile database model."""

    __tablename__ = "voice_profiles"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    quality_score = Column(Float, nullable=False)
    voice_sample_base64 = Column(Text, nullable=True)  # Base64-encoded WAV for Live Coach identification
    voice_embedding_json = Column(Text, nullable=True)  # JSON-encoded embedding vector
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
