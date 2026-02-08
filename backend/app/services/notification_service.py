"""
Central notification delivery: one function for in-app inbox, WebSocket, and push.

Call this from any module (activities, notifications, market, etc.) instead of
creating notifications and sending WebSocket/push separately. Handles:
- DB notification (inbox, read/unread)
- WebSocket notification.new (real-time in-app)
- Push (FCM) when configured
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.repositories.notification_repo import NotificationRepository
from app.infra.realtime.ws_manager import ws_manager
from app.infra.push.sender import send_push_to_user

logger = logging.getLogger(__name__)


async def deliver_notification(
    session: AsyncSession,
    user_id: str,
    type: str,
    title: str,
    message: str,
    *,
    extra_payload: Optional[dict[str, Any]] = None,
):
    """
    Deliver a notification atomically: create in DB (inbox, unread), send WebSocket, send push.

    Args:
        session: DB session (for create + push token lookup).
        user_id: Recipient user id.
        type: Notification type (e.g. activity_invite, emotion, message).
        title: Title for inbox and push.
        message: Body for inbox and push.
        extra_payload: Optional dict merged into the WebSocket payload only (e.g. invite_id,
            activity_title, planned_id, sender_id, sender_name, emotion_kind). Use for
            client-specific fields; push always gets notificationId and type.

    Returns:
        The created NotificationModel (e.g. for id, created_at).
    """
    repo = NotificationRepository(session)
    notif = await repo.create(user_id=user_id, type=type, title=title, message=message)
    ts_ms = int(notif.created_at.timestamp() * 1000) if notif.created_at else 0
    payload = {
        "id": notif.id,
        "type": notif.type,
        "title": notif.title,
        "message": notif.message,
        "read": notif.read,
        "timestamp": ts_ms,
    }
    if extra_payload:
        payload.update(extra_payload)
    await ws_manager.send_to_user(user_id, {"type": "notification.new", "payload": payload})
    try:
        await send_push_to_user(
            session,
            user_id,
            notif.title,
            notif.message,
            {"notificationId": notif.id, "type": notif.type},
        )
    except Exception as e:
        logger.warning("Push send failed for user %s: %s", user_id, e)
    return notif
