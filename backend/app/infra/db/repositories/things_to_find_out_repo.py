"""Things to find out repository (Compass)."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import ThingToFindOutModel
from app.domain.common.types import generate_id


class ThingsToFindOutRepository:
    """Repository for things Kai wants to find out."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        owner_user_id: str,
        question_text: str,
        source: str = "kai",
        relationship_id: Optional[str] = None,
        priority: Optional[int] = None,
    ) -> ThingToFindOutModel:
        """Create a thing to find out."""
        id_ = generate_id()
        now = datetime.utcnow()
        model = ThingToFindOutModel(
            id=id_,
            owner_user_id=owner_user_id,
            relationship_id=relationship_id,
            question_text=question_text,
            source=source,
            priority=priority,
            created_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def list_by_owner(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[ThingToFindOutModel]:
        """List things to find out by owner, newest first."""
        q = (
            select(ThingToFindOutModel)
            .where(ThingToFindOutModel.owner_user_id == owner_user_id)
            .order_by(ThingToFindOutModel.created_at.desc())
            .limit(limit)
        )
        if relationship_id is not None:
            q = q.where(ThingToFindOutModel.relationship_id == relationship_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())
