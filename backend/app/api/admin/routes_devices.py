"""Device management routes."""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.infra.db.repositories.device_repo import DeviceRepository

logger = logging.getLogger(__name__)

router = APIRouter()


class PushTokenRequest(BaseModel):
    """Push token request."""
    token: str
    platform: str  # 'ios' or 'android'


@router.post("/push-token")
async def register_push_token(
    request: PushTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register push token for device notifications. Upserts by token (one device per token)."""
    platform = "ios" if (request.platform or "").lower() == "ios" else "android"
    repo = DeviceRepository(db)
    await repo.upsert_by_token(
        user_id=current_user.id,
        push_token=request.token,
        platform=platform,
    )
    logger.info(
        f"📱 [DEVICE] Registered push token for user {current_user.id}: "
        f"platform={platform}, token={request.token[:20]}..."
    )
    return {"ok": True}
