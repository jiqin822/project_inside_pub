"""Notification infrastructure."""
from app.domain.interaction.repositories import NotificationRepository


class NotificationRepositoryImpl(NotificationRepository):
    """Notification repository implementation."""

    async def send(self, user_id: str, notification_type: str, payload: dict) -> None:
        """Send a notification."""
        # Skeleton implementation - would integrate with push notification service
        # For now, just log or store in database
        print(f"Notification to {user_id}: {notification_type} - {payload}")
