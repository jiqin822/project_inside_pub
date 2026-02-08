"""Notification repository."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete

from app.infra.db.models.notification import NotificationModel
from app.domain.common.types import generate_id


class NotificationRepository:
    """Notification repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, type: str, title: str, message: str) -> NotificationModel:
        """Create a notification."""
        now = __import__("datetime").datetime.utcnow()
        model = NotificationModel(
            id=generate_id(),
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            read=False,
            created_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def list_by_user(
        self, user_id: str, limit: int = 50, type: Optional[str] = None
    ) -> List[NotificationModel]:
        """List notifications for a user, newest first. Optional filter by type."""
        q = (
            select(NotificationModel)
            .where(NotificationModel.user_id == user_id)
            .order_by(NotificationModel.created_at.desc())
            .limit(limit)
        )
        if type is not None:
            q = q.where(NotificationModel.type == type)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count_unread(self, user_id: str) -> int:
        """Count unread notifications for a user."""
        result = await self.session.execute(
            select(func.count()).select_from(NotificationModel).where(
                NotificationModel.user_id == user_id,
                NotificationModel.read.is_(False),
            )
        )
        return result.scalar() or 0

    async def get(self, notification_id: str, user_id: str) -> Optional[NotificationModel]:
        """Get a notification by ID if it belongs to the user."""
        result = await self.session.execute(
            select(NotificationModel).where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read. Returns True if found and updated."""
        result = await self.session.execute(
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
            .values(read=True)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        result = await self.session.execute(
            update(NotificationModel).where(NotificationModel.user_id == user_id).values(read=True)
        )
        await self.session.commit()
        return result.rowcount or 0

    async def delete_for_user(self, notification_id: str, user_id: str) -> bool:
        """Delete a notification if it belongs to the user. Returns True if deleted."""
        result = await self.session.execute(
            delete(NotificationModel).where(
                NotificationModel.id == notification_id,
                NotificationModel.user_id == user_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0
