"""Interaction domain services."""
from typing import Protocol
from app.domain.interaction.models import PokeEvent
from app.domain.common.errors import NotFoundError, AuthorizationError
from app.domain.interaction.repositories import NotificationRepository


class PokeRepository(Protocol):
    """Poke repository protocol."""

    async def create(self, poke: PokeEvent) -> PokeEvent:
        """Create a new poke."""
        ...

    async def list_by_relationship(self, relationship_id: str, limit: int = 100) -> list[PokeEvent]:
        """List pokes for a relationship."""
        ...


class PokeService:
    """Poke service."""

    def __init__(
        self,
        poke_repo: PokeRepository,
        relationship_repo,  # RelationshipRepository protocol
        notification_repo: NotificationRepository | None = None,
        ws_manager=None,  # WebSocket manager (optional)
    ):
        self.poke_repo = poke_repo
        self.relationship_repo = relationship_repo
        self.notification_repo = notification_repo
        self.ws_manager = ws_manager

    async def send_poke(
        self, relationship_id: str, sender_id: str, receiver_id: str, type: str, emoji: str | None = None
    ) -> PokeEvent:
        """Send a poke."""
        # Verify relationship exists
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)

        # Verify sender is a member
        is_sender_member = await self.relationship_repo.is_member(relationship_id, sender_id)
        if not is_sender_member:
            raise AuthorizationError("Sender is not a member of this relationship")

        # Verify receiver is a member
        is_receiver_member = await self.relationship_repo.is_member(relationship_id, receiver_id)
        if not is_receiver_member:
            raise AuthorizationError("Receiver is not a member of this relationship")

        poke = PokeEvent.create(
            relationship_id=relationship_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            type=type,
            emoji=emoji,
        )
        created_poke = await self.poke_repo.create(poke)
        
        # Send notification
        if self.notification_repo:
            await self.notification_repo.send(
                user_id=receiver_id,
                notification_type="emoji_poke",
                payload={
                    "poke_id": created_poke.id,
                    "sender_id": sender_id,
                    "emoji": emoji or type,
                    "relationship_id": relationship_id,
                }
            )
        
        # Send via WebSocket if available
        if self.ws_manager:
            import logging
            logger = logging.getLogger(__name__)
            emoji_message = {
                "type": "emoji_poke",
                "poke_id": created_poke.id,
                "sender_id": sender_id,
                "emoji": emoji or type,
                "relationship_id": relationship_id,
                "created_at": created_poke.created_at.isoformat(),
            }
            logger.info(f"🔵 [WEBSOCKET] Sending emoji_poke to user {receiver_id}: {emoji_message}")
            await self.ws_manager.send_to_user(receiver_id, emoji_message)
            logger.info(f"✅ [WEBSOCKET] Emoji message sent to user {receiver_id}")
        
        return created_poke

    async def list_pokes(self, relationship_id: str, limit: int = 100) -> list[PokeEvent]:
        """List pokes for a relationship."""
        return await self.poke_repo.list_by_relationship(relationship_id, limit=limit)
