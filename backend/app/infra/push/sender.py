"""Push notification sender via FCM (Firebase Cloud Messaging)."""
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.repositories.device_repo import DeviceRepository
from app.settings import settings

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_firebase_app():
    """Lazy-init Firebase default app. Returns None if push disabled or no credentials."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    if not getattr(settings, "push_enabled", False):
        return None
    import os
    cred_path = getattr(settings, "google_application_credentials", "") or ""
    if not cred_path:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not cred_path:
        logger.debug("Push disabled: no GOOGLE_APPLICATION_CREDENTIALS or push_enabled=False")
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        _firebase_app = firebase_admin.initialize_app(credentials.Certificate(cred_path))
        return _firebase_app
    except Exception as e:
        logger.warning("Firebase init failed (push disabled): %s", e)
        return None


async def send_push_to_user(
    session: AsyncSession,
    user_id: str,
    title: str,
    body: str,
    data: dict[str, Any],
) -> None:
    """Send push notification to all devices for the user. data must include notificationId (and optionally type); values are stringified for FCM."""
    app = _get_firebase_app()
    if app is None:
        return
    repo = DeviceRepository(session)
    tokens_rows = await repo.list_tokens_by_user(user_id)
    if not tokens_rows:
        logger.debug("No push tokens for user %s", user_id)
        return
    # FCM data payload: all values must be strings
    data_str = {k: str(v) for k, v in data.items()}
    try:
        from firebase_admin import messaging
        for (push_token, platform) in tokens_rows:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data_str,
                    token=push_token,
                )
                messaging.send(message)
                logger.debug("Push sent to user %s token %s...", user_id, push_token[:20])
            except Exception as e:
                logger.warning("Push send failed for token %s...: %s", push_token[:20], e)
    except Exception as e:
        logger.warning("Push send failed for user %s: %s", user_id, e)
