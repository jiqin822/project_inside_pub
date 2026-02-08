"""Dyad activity history repository."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import DyadActivityHistoryModel
from app.domain.common.types import generate_id


class DyadActivityHistoryRepository:
    """Dyad activity history repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append(
        self,
        relationship_id: str,
        activity_template_id: str,
        actor_user_id: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        rating: Optional[float] = None,
        outcome_tags: Optional[list] = None,
        notes_text: Optional[str] = None,
        memory_urls: Optional[list] = None,
        memory_entries: Optional[list] = None,
        planned_id: Optional[str] = None,
    ) -> DyadActivityHistoryModel:
        """Append a dyad activity record."""
        record_id = generate_id()
        now = datetime.utcnow()
        model = DyadActivityHistoryModel(
            id=record_id,
            relationship_id=relationship_id,
            activity_template_id=activity_template_id,
            actor_user_id=actor_user_id,
            planned_id=planned_id,
            started_at=started_at,
            completed_at=completed_at,
            rating=rating,
            outcome_tags=outcome_tags,
            notes_text=notes_text,
            memory_urls=memory_urls,
            memory_entries=memory_entries,
            created_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_id(self, record_id: str) -> Optional[DyadActivityHistoryModel]:
        """Get a dyad activity history record by id."""
        result = await self.session.execute(
            select(DyadActivityHistoryModel).where(DyadActivityHistoryModel.id == record_id)
        )
        return result.scalar_one_or_none()

    async def update_scrapbook_layout(
        self,
        record_id: str,
        scrapbook_layout: Optional[dict] = None,
    ) -> Optional[DyadActivityHistoryModel]:
        """Save AI-generated scrapbook layout for a standalone memory (dyad history record)."""
        record = await self.get_by_id(record_id)
        if not record:
            return None
        record.scrapbook_layout = scrapbook_layout
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list_by_relationship(
        self,
        relationship_id: str,
        limit: int = 100,
    ) -> List[DyadActivityHistoryModel]:
        """List activity history for a relationship, newest first."""
        q = (
            select(DyadActivityHistoryModel)
            .where(DyadActivityHistoryModel.relationship_id == relationship_id)
            .order_by(DyadActivityHistoryModel.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all())
