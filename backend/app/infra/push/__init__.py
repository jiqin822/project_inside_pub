"""Push notification infrastructure (FCM)."""
from app.infra.push.sender import send_push_to_user

__all__ = ["send_push_to_user"]
