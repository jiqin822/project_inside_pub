"""Poke routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.interaction.services import PokeService, PokeRepository
from app.domain.admin.services import RelationshipRepository
from app.domain.interaction.repositories import NotificationRepository
from app.infra.db.repositories.poke_repo import PokeRepositoryImpl
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.messaging.notify import NotificationRepositoryImpl
from app.infra.realtime.ws_manager import ws_manager

router = APIRouter(prefix="/pokes", tags=["pokes"])


class SendPokeRequest(BaseModel):
    """Send poke request model."""
    relationship_id: str
    receiver_id: str
    type: str  # Keep for backward compatibility
    emoji: str | None = None  # Emoji character (e.g., "❤️", "👍", "😊")


class PokeResponse(BaseModel):
    """Poke response model."""
    id: str


class PokeListItem(BaseModel):
    """Poke list item model."""
    id: str
    type: str
    emoji: str | None = None
    sender_id: str
    receiver_id: str
    created_at: str


@router.post("", response_model=PokeResponse)
async def send_poke(
    request: SendPokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a poke."""
    poke_repo: PokeRepository = PokeRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    notification_repo: NotificationRepository = NotificationRepositoryImpl()
    poke_service = PokeService(poke_repo, relationship_repo, notification_repo, ws_manager)

    poke = await poke_service.send_poke(
        relationship_id=request.relationship_id,
        sender_id=current_user.id,
        receiver_id=request.receiver_id,
        type=request.type,
        emoji=request.emoji,
    )

    return PokeResponse(id=poke.id)


@router.get("", response_model=list[PokeListItem])
async def list_pokes(
    rid: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pokes for a relationship."""
    poke_repo: PokeRepository = PokeRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    poke_service = PokeService(poke_repo, relationship_repo)

    pokes = await poke_service.list_pokes(rid)

    return [
        PokeListItem(
            id=p.id,
            type=p.type,
            emoji=p.emoji,
            sender_id=p.sender_id,
            receiver_id=p.receiver_id,
            created_at=p.created_at.isoformat(),
        )
        for p in pokes
    ]
