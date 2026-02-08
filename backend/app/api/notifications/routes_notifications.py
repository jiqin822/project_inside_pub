"""Notification API routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.infra.db.repositories.notification_repo import NotificationRepository
from app.infra.db.models.relationship import relationship_members
from app.services.notification_service import deliver_notification

router = APIRouter()


class NotificationCreateRequest(BaseModel):
    """Create notification request."""
    type: str  # message, alert, reward, system, etc.
    title: str
    message: str


class NotificationResponse(BaseModel):
    """Notification response."""
    id: str
    type: str
    title: str
    message: str
    read: bool
    timestamp: int  # ms since epoch for client compatibility

    class Config:
        from_attributes = True


@router.post("", response_model=NotificationResponse)
async def create_notification(
    request: NotificationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a notification for the current user (e.g. from market/therapy events)."""
    model = await deliver_notification(
        db,
        current_user.id,
        request.type,
        request.title,
        request.message,
    )
    ts_ms = int(model.created_at.timestamp() * 1000) if model.created_at else 0
    return NotificationResponse(
        id=model.id,
        type=model.type,
        title=model.title,
        message=model.message,
        read=model.read,
        timestamp=ts_ms,
    )


@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    limit: Optional[int] = 50,
    type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user, newest first. Optional filter by type (message, alert, reward, system)."""
    if limit is not None and (limit < 1 or limit > 100):
        limit = 50
    repo = NotificationRepository(db)
    models = await repo.list_by_user(current_user.id, limit=limit or 50, type=type)
    return [
        NotificationResponse(
            id=m.id,
            type=m.type,
            title=m.title,
            message=m.message,
            read=m.read,
            timestamp=int(m.created_at.timestamp() * 1000) if m.created_at else 0,
        )
        for m in models
    ]


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return unread notification count for the current user."""
    repo = NotificationRepository(db)
    count = await repo.count_unread(current_user.id)
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    repo = NotificationRepository(db)
    updated = await repo.mark_read(notification_id, current_user.id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"ok": True}


@router.post("/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    repo = NotificationRepository(db)
    count = await repo.mark_all_read(current_user.id)
    return {"ok": True, "updated": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification for the current user (e.g. after swipe-to-dismiss)."""
    repo = NotificationRepository(db)
    deleted = await repo.delete_for_user(notification_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"ok": True}


class SendHeartRequest(BaseModel):
    """Send heart to a loved one (creates in-app notification for them)."""
    target_user_id: str


class SendEmotionRequest(BaseModel):
    """Send emotion to a loved one (creates emotion notification; shown on watch full-screen or as tag on icon)."""
    target_user_id: str
    emotion_kind: Optional[str] = None  # e.g. "love", "hug"


@router.post("/send-emotion")
async def send_emotion(
    request: SendEmotionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an emotion notification for a loved one. Target must be in a relationship with current user."""
    target_user_id = request.target_user_id
    emotion_kind = request.emotion_kind or "love"
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send emotion to yourself",
        )

    current_user_relationships = await db.execute(
        select(relationship_members.c.relationship_id).where(
            relationship_members.c.user_id == current_user.id
        )
    )
    relationship_ids = [row[0] for row in current_user_relationships.all()]

    if not relationship_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send emotions to users in relationships with you",
        )

    target_in_relationship = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id.in_(relationship_ids),
            relationship_members.c.user_id == target_user_id,
        )
    )
    if not target_in_relationship.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send emotions to users in relationships with you",
        )

    sender_name = current_user.display_name or "Someone"
    await deliver_notification(
        db,
        target_user_id,
        "emotion",
        emotion_kind.capitalize(),
        f"{sender_name} sent you {emotion_kind}",
        extra_payload={
            "sender_id": current_user.id,
            "sender_name": sender_name,
            "emotion_kind": emotion_kind,
        },
    )
    return {"ok": True}


@router.post("/send-heart")
async def send_heart(
    request: SendHeartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a heart notification for a loved one. Target must be in a relationship with current user."""
    target_user_id = request.target_user_id
    if target_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send heart to yourself",
        )

    # Get all relationships where current user is a member
    current_user_relationships = await db.execute(
        select(relationship_members.c.relationship_id).where(
            relationship_members.c.user_id == current_user.id
        )
    )
    relationship_ids = [row[0] for row in current_user_relationships.all()]

    if not relationship_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send hearts to users in relationships with you",
        )

    # Check if target user is in any of these relationships
    target_in_relationship = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id.in_(relationship_ids),
            relationship_members.c.user_id == target_user_id,
        )
    )
    if not target_in_relationship.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only send hearts to users in relationships with you",
        )

    sender_name = current_user.display_name or "Someone"
    await deliver_notification(
        db,
        target_user_id,
        "message",
        "Heart",
        f"{sender_name} sent you a heart",
    )
    return {"ok": True}
