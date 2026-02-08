"""Coach domain models."""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

from app.domain.common.types import generate_id


class Session(BaseModel):
    """Session domain model."""

    id: str
    relationship_id: str
    status: str  # ACTIVE, ENDED, FINALIZED
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, relationship_id: str, creator_id: str, status: str = "ACTIVE") -> "Session":
        """Create a new session."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            relationship_id=relationship_id,
            status=status,
            started_at=now,
            ended_at=None,
            created_by_user_id=creator_id,
            created_at=now,
            updated_at=now,
        )


class SessionParticipant(BaseModel):
    """Session participant domain model."""

    session_id: str
    user_id: str

    @classmethod
    def create(cls, session_id: str, user_id: str) -> "SessionParticipant":
        """Create a new session participant."""
        return cls(session_id=session_id, user_id=user_id)


class NudgeEvent(BaseModel):
    """Nudge event domain model."""

    id: str
    session_id: str
    user_id: str
    nudge_type: str
    payload: dict[str, Any]
    created_at: datetime

    @classmethod
    def create(
        cls, session_id: str, user_id: str, nudge_type: str, payload: dict[str, Any]
    ) -> "NudgeEvent":
        """Create a new nudge event."""
        return cls(
            id=generate_id(),
            session_id=session_id,
            user_id=user_id,
            nudge_type=nudge_type,
            payload=payload,
            created_at=datetime.utcnow(),
        )


class SessionReport(BaseModel):
    """Session report domain model."""

    session_id: str
    summary: str
    moments: list[dict[str, Any]]
    action_items: list[str]  # Changed to list of strings per API contract
    status: str  # PENDING, READY
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        session_id: str,
        summary: str = "",
        moments: Optional[list[dict[str, Any]]] = None,
        action_items: Optional[list[str]] = None,
        status: str = "PENDING",
    ) -> "SessionReport":
        """Create a new session report."""
        now = datetime.utcnow()
        return cls(
            session_id=session_id,
            summary=summary or "Session report pending...",
            moments=moments or [],
            action_items=action_items or [],
            status=status,
            created_at=now,
            updated_at=now,
        )


class ActivitySuggestion(BaseModel):
    """Activity suggestion domain model."""

    id: str
    title: str
    description: str

    @classmethod
    def create(cls, title: str, description: str) -> "ActivitySuggestion":
        """Create a new activity suggestion."""
        return cls(
            id=generate_id(),
            title=title,
            description=description,
        )
