"""User database model."""
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.infra.db.base import Base
from app.domain.admin.models import User as UserEntity


class UserModel(Base):
    """User database model."""

    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    pronouns = Column(String, nullable=True)
    personality_type = Column(JSONB, nullable=True)  # MBTI data: {"type": "INTJ", "values": {"ei": 25, "sn": 75, "tf": 50, "jp": 50}} or {"type": "Prefer not to say"}
    communication_style = Column(Float, nullable=True)  # 0.0 = Gentle, 1.0 = Direct
    goals = Column(JSONB, nullable=True)  # Array of strings
    personal_description = Column(Text, nullable=True)  # Short bio / about me
    hobbies = Column(JSONB, nullable=True)  # Array of strings, e.g. ["Running", "Reading"]
    birthday = Column(Date, nullable=True)  # Optional date of birth
    occupation = Column(String, nullable=True)  # Optional job/role
    privacy_tier = Column(String, nullable=True)  # PRIVATE|STANDARD|ENHANCED
    profile_picture_url = Column(String, nullable=True)  # URL or base64 data URL for profile picture
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_entity(self) -> UserEntity:
        """Convert to domain entity."""
        return UserEntity(
            id=self.id,
            email=self.email,
            password_hash=self.password_hash,
            display_name=self.display_name,
            pronouns=self.pronouns,
            personality_type=dict(self.personality_type) if self.personality_type is not None else None,
            communication_style=self.communication_style,
            goals=self.goals if self.goals else None,
            personal_description=getattr(self, "personal_description", None),
            hobbies=self.hobbies if getattr(self, "hobbies", None) is not None else None,
            birthday=getattr(self, "birthday", None),
            occupation=getattr(self, "occupation", None),
            privacy_tier=self.privacy_tier,
            profile_picture_url=getattr(self, 'profile_picture_url', None),
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: UserEntity) -> "UserModel":
        """Create from domain entity."""
        return cls(
            id=entity.id,
            email=entity.email,
            password_hash=entity.password_hash,
            display_name=entity.display_name,
            pronouns=getattr(entity, 'pronouns', None),
            personality_type=getattr(entity, 'personality_type', None),
            communication_style=getattr(entity, 'communication_style', None),
            goals=getattr(entity, "goals", None),
            personal_description=getattr(entity, "personal_description", None),
            hobbies=getattr(entity, "hobbies", None),
            birthday=getattr(entity, "birthday", None),
            occupation=getattr(entity, "occupation", None),
            privacy_tier=getattr(entity, "privacy_tier", None),
            profile_picture_url=getattr(entity, 'profile_picture_url', None),
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
