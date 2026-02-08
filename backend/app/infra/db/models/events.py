"""Event database models."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey

from app.infra.db.base import Base
from app.domain.interaction.models import PokeEvent as PokeEventEntity


class PokeEventModel(Base):
    """Poke event database model."""

    __tablename__ = "poke_events"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False)
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    emoji = Column(String, nullable=True)  # Emoji character
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_entity(self) -> PokeEventEntity:
        """Convert to domain entity."""
        return PokeEventEntity(
            id=self.id,
            relationship_id=self.relationship_id,
            sender_id=self.sender_id,
            receiver_id=self.receiver_id,
            type=self.type,
            emoji=getattr(self, 'emoji', None),
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: PokeEventEntity) -> "PokeEventModel":
        """Create from domain entity."""
        return cls(
            id=entity.id,
            relationship_id=entity.relationship_id,
            sender_id=entity.sender_id,
            receiver_id=entity.receiver_id,
            type=entity.type,
            emoji=entity.emoji,
            created_at=entity.created_at,
        )
