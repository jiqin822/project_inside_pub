"""Onboarding database models."""
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.infra.db.base import Base


class OnboardingProgressModel(Base):
    """Onboarding progress database model."""

    __tablename__ = "onboarding_progress"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    profile_completed = Column(Boolean, default=False, nullable=False)
    voiceprint_completed = Column(Boolean, default=False, nullable=False)
    relationships_completed = Column(Boolean, default=False, nullable=False)
    consent_completed = Column(Boolean, default=False, nullable=False)
    device_setup_completed = Column(Boolean, default=False, nullable=False)
    done_completed = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
