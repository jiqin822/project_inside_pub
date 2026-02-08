"""Coach domain entities."""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

from app.domain.common.types import generate_id


class Activity(BaseModel):
    """Activity entity."""

    id: str
    relationship_id: str
    activity_type: str  # e.g., "message", "call", "meeting"
    content: Optional[str] = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        relationship_id: str,
        activity_type: str,
        content: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "Activity":
        """Create a new activity."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            relationship_id=relationship_id,
            activity_type=activity_type,
            content=content,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )


class ReviewJob(BaseModel):
    """Review job entity."""

    id: str
    relationship_id: str
    job_type: str  # e.g., "daily_review", "weekly_summary"
    status: str  # e.g., "pending", "processing", "completed", "failed"
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    @classmethod
    def create(cls, relationship_id: str, job_type: str) -> "ReviewJob":
        """Create a new review job."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            relationship_id=relationship_id,
            job_type=job_type,
            status="pending",
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
