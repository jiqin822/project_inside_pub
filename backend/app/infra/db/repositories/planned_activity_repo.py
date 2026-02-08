"""Planned activity repository."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.infra.db.models.compass import PlannedActivityModel
from app.domain.common.types import generate_id


class PlannedActivityRepository:
    """Planned activity repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        relationship_id: str,
        activity_template_id: str,
        initiator_user_id: str,
        invitee_user_id: str,
        invite_id: Optional[str] = None,
        card_snapshot: Optional[dict] = None,
    ) -> PlannedActivityModel:
        """Create a planned activity (after invite accepted). Optionally store full ActivityCard JSON for UI."""
        planned_id = generate_id()
        now = datetime.utcnow()
        model = PlannedActivityModel(
            id=planned_id,
            relationship_id=relationship_id,
            activity_template_id=activity_template_id,
            initiator_user_id=initiator_user_id,
            invitee_user_id=invitee_user_id,
            invite_id=invite_id,
            status="planned",
            agreed_at=now,
            card_snapshot=card_snapshot,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_id(self, planned_id: str) -> Optional[PlannedActivityModel]:
        """Get planned activity by id."""
        result = await self.session.execute(
            select(PlannedActivityModel).where(PlannedActivityModel.id == planned_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        relationship_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PlannedActivityModel]:
        """List planned activities where user is initiator or invitee, newest first."""
        q = (
            select(PlannedActivityModel)
            .where(
                or_(
                    PlannedActivityModel.initiator_user_id == user_id,
                    PlannedActivityModel.invitee_user_id == user_id,
                )
            )
            .order_by(PlannedActivityModel.agreed_at.desc())
            .limit(limit)
        )
        if relationship_id:
            q = q.where(PlannedActivityModel.relationship_id == relationship_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update_completion(
        self,
        planned_id: str,
        completed_at: datetime,
        notes_text: Optional[str] = None,
        memory_urls: Optional[list] = None,
    ) -> Optional[PlannedActivityModel]:
        """Mark planned activity as completed with notes and memory URLs."""
        planned = await self.get_by_id(planned_id)
        if not planned:
            return None
        planned.status = "completed"
        planned.completed_at = completed_at
        if notes_text is not None:
            planned.notes_text = notes_text
        if memory_urls is not None:
            planned.memory_urls = memory_urls
        await self.session.commit()
        await self.session.refresh(planned)
        return planned

    async def update_scrapbook_layout(
        self,
        planned_id: str,
        scrapbook_layout: Optional[dict] = None,
    ) -> Optional[PlannedActivityModel]:
        """Save AI-generated scrapbook layout for a completed planned activity."""
        planned = await self.get_by_id(planned_id)
        if not planned:
            return None
        planned.scrapbook_layout = scrapbook_layout
        await self.session.commit()
        await self.session.refresh(planned)
        return planned
