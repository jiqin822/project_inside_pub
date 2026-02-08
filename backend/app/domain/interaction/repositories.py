"""Interaction domain repository protocols."""
from typing import Protocol


class NotificationRepository(Protocol):
    """Notification repository protocol."""

    async def send(self, user_id: str, notification_type: str, payload: dict) -> None:
        """Send a notification."""
        ...
