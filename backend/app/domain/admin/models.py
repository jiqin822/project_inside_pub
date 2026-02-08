"""Admin domain models."""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr

from app.domain.common.types import generate_id


class User(BaseModel):
    """User domain model."""

    id: str
    email: EmailStr
    password_hash: str
    display_name: Optional[str] = None
    pronouns: Optional[str] = None
    personality_type: Optional[dict] = None  # MBTI data: {"type": "INTJ", "values": {"ei": 25, "sn": 75, "tf": 50, "jp": 50}} or {"type": "Prefer not to say"}
    communication_style: Optional[float] = None
    goals: Optional[list[str]] = None
    personal_description: Optional[str] = None
    hobbies: Optional[list[str]] = None
    birthday: Optional[date] = None
    occupation: Optional[str] = None
    privacy_tier: Optional[str] = None
    profile_picture_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, email: EmailStr, password_hash: str, display_name: Optional[str] = None) -> "User":
        """Create a new user."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            is_active=True,
            created_at=now,
            updated_at=now,
        )


class Relationship(BaseModel):
    """Relationship domain model."""

    id: str
    rel_type: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, rel_type: str, status: str = "active") -> "Relationship":
        """Create a new relationship."""
        now = datetime.utcnow()
        return cls(
            id=generate_id(),
            rel_type=rel_type,
            status=status,
            created_at=now,
            updated_at=now,
        )


class RelationshipMember(BaseModel):
    """Relationship member domain model."""

    relationship_id: str
    user_id: str
    role: Optional[str] = None

    @classmethod
    def create(cls, relationship_id: str, user_id: str, role: Optional[str] = None) -> "RelationshipMember":
        """Create a new relationship member."""
        return cls(
            relationship_id=relationship_id,
            user_id=user_id,
            role=role,
        )


class Consent(BaseModel):
    """Consent domain model."""

    relationship_id: str
    user_id: str
    scopes: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, relationship_id: str, user_id: str, scopes: list[str]) -> "Consent":
        """Create a new consent."""
        now = datetime.utcnow()
        return cls(
            relationship_id=relationship_id,
            user_id=user_id,
            scopes=scopes,
            created_at=now,
            updated_at=now,
        )
