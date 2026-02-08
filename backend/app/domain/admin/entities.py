"""Admin domain entities."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.domain.common.types import generate_id


class User(BaseModel):
    """User entity."""

    id: str
    email: EmailStr
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, email: EmailStr, hashed_password: str, full_name: Optional[str] = None) -> "User":
        """Create a new user."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            is_active=True,
            created_at=now,
            updated_at=now,
        )


class Relationship(BaseModel):
    """Relationship entity."""

    id: str
    user1_id: str
    user2_id: str
    relationship_type: str  # e.g., "partner", "friend", "family"
    status: str  # e.g., "active", "paused", "ended"
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls, user1_id: str, user2_id: str, relationship_type: str, status: str = "active"
    ) -> "Relationship":
        """Create a new relationship."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            user1_id=user1_id,
            user2_id=user2_id,
            relationship_type=relationship_type,
            status=status,
            created_at=now,
            updated_at=now,
        )


class Consent(BaseModel):
    """Consent/ACL entity."""

    id: str
    user_id: str
    relationship_id: str
    consent_type: str  # e.g., "data_sharing", "coaching", "analysis"
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls, user_id: str, relationship_id: str, consent_type: str, granted: bool = True
    ) -> "Consent":
        """Create a new consent."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            user_id=user_id,
            relationship_id=relationship_id,
            consent_type=consent_type,
            granted=granted,
            granted_at=now if granted else None,
            revoked_at=None,
            created_at=now,
            updated_at=now,
        )
