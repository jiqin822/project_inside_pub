"""Interaction domain models."""
from datetime import datetime
from pydantic import BaseModel

from app.domain.common.types import generate_id


class PokeEvent(BaseModel):
    """Poke event domain model."""

    id: str
    relationship_id: str
    sender_id: str
    receiver_id: str
    type: str  # Keep for backward compatibility
    emoji: str | None = None  # Emoji character (e.g., "❤️", "👍", "😊")
    created_at: datetime

    @classmethod
    def create(
        cls, relationship_id: str, sender_id: str, receiver_id: str, type: str, emoji: str | None = None
    ) -> "PokeEvent":
        """Create a new poke event."""
        return cls(
            id=generate_id(),
            relationship_id=relationship_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            type=type,
            emoji=emoji,
            created_at=datetime.utcnow(),
        )
