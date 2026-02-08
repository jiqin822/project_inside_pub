"""Poke endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.entities import User
from app.domain.interaction.services import PokeService
from app.domain.interaction.repositories import NotificationRepository
from app.infra.messaging.notify import NotificationRepositoryImpl
from app.infra.realtime.websocket import ws_manager

router = APIRouter()


class SendPokeRequest(BaseModel):
    """Send poke request."""

    to_user_id: str
    message: str | None = None


class PokeResponse(BaseModel):
    """Poke response."""

    success: bool
    message: str


@router.post("", response_model=PokeResponse, status_code=status.HTTP_201_CREATED)
async def send_poke(
    request: SendPokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a poke to another user."""
    notification_repo: NotificationRepository = NotificationRepositoryImpl()
    poke_service = PokeService(ws_manager, notification_repo)

    await poke_service.send_poke(
        from_user_id=current_user.id, to_user_id=request.to_user_id, message=request.message
    )

    return PokeResponse(success=True, message="Poke sent successfully")
