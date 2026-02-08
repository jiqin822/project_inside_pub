"""Session database models."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, JSON, BigInteger, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.infra.db.base import Base
from app.domain.coach.models import (
    Session as SessionEntity,
    SessionParticipant as SessionParticipantEntity,
    SessionReport as SessionReportEntity,
)


class SessionStatus(str, enum.Enum):
    """Session status enum."""
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    FINALIZED = "FINALIZED"


class ReportStatus(str, enum.Enum):
    """Report status enum."""
    PENDING = "PENDING"
    READY = "READY"


# Association table for session participants
session_participants = Table(
    "session_participants",
    Base.metadata,
    Column("session_id", String, ForeignKey("sessions.id"), primary_key=True),
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
)


class SessionModel(Base):
    """Session database model."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.ACTIVE)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_entity(self) -> SessionEntity:
        """Convert to domain entity."""
        return SessionEntity(
            id=self.id,
            relationship_id=self.relationship_id,
            status=self.status.value if isinstance(self.status, SessionStatus) else self.status,
            started_at=self.started_at,
            ended_at=self.ended_at,
            created_by_user_id=self.created_by_user_id,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: SessionEntity) -> "SessionModel":
        """Create from domain entity."""
        status_enum = SessionStatus.ACTIVE
        if isinstance(entity.status, str):
            status_enum = SessionStatus(entity.status) if entity.status in [s.value for s in SessionStatus] else SessionStatus.ACTIVE
        elif isinstance(entity.status, SessionStatus):
            status_enum = entity.status
        
        return cls(
            id=entity.id,
            relationship_id=entity.relationship_id,
            status=status_enum,
            started_at=entity.started_at,
            ended_at=entity.ended_at,
            created_by_user_id=entity.created_by_user_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class NudgeEventModel(Base):
    """Nudge event database model."""

    __tablename__ = "nudge_events"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    nudge_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "nudge_type": self.nudge_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }


class SessionReportModel(Base):
    """Session report database model."""

    __tablename__ = "session_reports"

    session_id = Column(String, ForeignKey("sessions.id"), primary_key=True)
    summary = Column(String, nullable=True)
    moments = Column(JSON, nullable=False, default=[])
    action_items = Column(JSON, nullable=False, default=[])
    status = Column(SQLEnum(ReportStatus), nullable=False, default=ReportStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SessionFeatureFrameModel(Base):
    """Session feature frame database model."""

    __tablename__ = "session_feature_frames"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    timestamp_ms = Column(BigInteger, nullable=False)
    speaking_rate = Column(Float, nullable=False)
    overlap_ratio = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
