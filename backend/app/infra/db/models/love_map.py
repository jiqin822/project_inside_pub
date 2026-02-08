"""Love Map database models."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.infra.db.base import Base


class MapPromptModel(Base):
    """Map prompt template model."""

    __tablename__ = "map_prompts"

    id = Column(String, primary_key=True)
    category = Column(String, nullable=False, index=True)  # e.g., "Dreams", "Stress", "History", "Sex", "Work"
    difficulty_tier = Column(Integer, nullable=False, index=True)  # 1-5 (Easy to Deep)
    question_template = Column(Text, nullable=False)  # "What is [NAME]'s favorite comfort food?"
    input_prompt = Column(Text, nullable=False)  # "What is your favorite comfort food?"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user_specs = relationship("UserSpecModel", back_populates="prompt")


class UserSpecModel(Base):
    """User specification (answer) model."""

    __tablename__ = "user_specs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    prompt_id = Column(String, ForeignKey("map_prompts.id"), nullable=False, index=True)
    answer_text = Column(Text, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    # Note: embedding column would be added via migration if vector extension is enabled
    # embedding = Column(Vector(768), nullable=True)

    # Relationships
    prompt = relationship("MapPromptModel", back_populates="user_specs")
    user = relationship("UserModel", foreign_keys=[user_id])

    # Unique constraint: one answer per user per prompt
    __table_args__ = (
        Index('idx_user_specs_user_prompt', 'user_id', 'prompt_id', unique=True),
    )


class RelationshipMapProgressModel(Base):
    """Relationship map progress model (directional)."""

    __tablename__ = "relationship_map_progress"

    id = Column(String, primary_key=True)
    observer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)  # The Player/Guesser
    subject_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)  # The Person being studied
    level_tier = Column(Integer, default=1, nullable=False)  # Current unlocked difficulty tier (1-6)
    current_xp = Column(Integer, default=0, nullable=False)  # Experience points
    stars = Column(JSONB, nullable=True)  # {'tier_1': 3, 'tier_2': 1} (Star ratings per level)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    observer = relationship("UserModel", foreign_keys=[observer_id])
    subject = relationship("UserModel", foreign_keys=[subject_id])

    # Unique constraint: one progress record per observer-subject pair
    __table_args__ = (
        Index('idx_map_progress_observer_subject', 'observer_id', 'subject_id', unique=True),
    )
