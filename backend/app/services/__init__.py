"""Application services (cross-cutting)."""
from app.services.notification_service import deliver_notification

__all__ = ["deliver_notification"]
