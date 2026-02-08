"""Activity invite repository."""
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import ActivityInviteModel
from app.domain.common.types import generate_id


class ActivityInviteRepository:
    """Activity invite repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        relationship_id: str,
        activity_template_id: str,
        from_user_id: str,
        to_user_id: str,
        card_snapshot: Optional[dict] = None,
    ) -> ActivityInviteModel:
        """Create a pending activity invite. Optionally store full ActivityCard JSON for UI."""
        invite_id = generate_id()
        model = ActivityInviteModel(
            id=invite_id,
            relationship_id=relationship_id,
            activity_template_id=activity_template_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            status="pending",
            card_snapshot=card_snapshot,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_id(self, invite_id: str) -> Optional[ActivityInviteModel]:
        """Get invite by id."""
        result = await self.session.execute(
            select(ActivityInviteModel).where(ActivityInviteModel.id == invite_id)
        )
        return result.scalars().first()

    async def get_pending_for_user(self, to_user_id: str, limit: int = 50) -> List[ActivityInviteModel]:
        """List pending invites for a user, newest first."""
        q = (
            select(ActivityInviteModel)
            .where(
                ActivityInviteModel.to_user_id == to_user_id,
                ActivityInviteModel.status == "pending",
            )
            .order_by(ActivityInviteModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_sent_for_user(self, from_user_id: str, limit: int = 50) -> List[ActivityInviteModel]:
        """List invites sent by a user that are still pending, newest first."""
        q = (
            select(ActivityInviteModel)
            .where(
                ActivityInviteModel.from_user_id == from_user_id,
                ActivityInviteModel.status == "pending",
            )
            .order_by(ActivityInviteModel.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_declined_for_user(self, to_user_id: str, limit: int = 50) -> List[ActivityInviteModel]:
        """List declined invites for a user (invites they declined), newest first."""
        q = (
            select(ActivityInviteModel)
            .where(
                ActivityInviteModel.to_user_id == to_user_id,
                ActivityInviteModel.status == "declined",
            )
            .order_by(ActivityInviteModel.responded_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update_status(
        self,
        invite_id: str,
        status: str,
        responded_at: Optional[datetime] = None,
    ) -> Optional[ActivityInviteModel]:
        """Update invite status (accepted | declined)."""
        invite = await self.get_by_id(invite_id)
        if not invite:
            return None
        invite.status = status
        invite.responded_at = responded_at or datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(invite)
        return invite
