"""Unstructured memory repository (Compass Kai insights)."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import UnstructuredMemoryModel
from app.domain.common.types import generate_id


class UnstructuredMemoryRepository:
    """Repository for unstructured memories (e.g. Kai insights)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        owner_user_id: str,
        content_text: str,
        source: str = "kai_insight",
        relationship_id: Optional[str] = None,
    ) -> UnstructuredMemoryModel:
        """Create an unstructured memory."""
        id_ = generate_id()
        now = datetime.utcnow()
        model = UnstructuredMemoryModel(
            id=id_,
            owner_user_id=owner_user_id,
            relationship_id=relationship_id,
            content_text=content_text,
            source=source,
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
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[UnstructuredMemoryModel]:
        """List unstructured memories by owner, newest first."""
        q = (
            select(UnstructuredMemoryModel)
            .where(UnstructuredMemoryModel.owner_user_id == owner_user_id)
            .order_by(UnstructuredMemoryModel.created_at.desc())
            .limit(limit)
        )
        if relationship_id is not None:
            q = q.where(UnstructuredMemoryModel.relationship_id == relationship_id)
        if source is not None:
            q = q.where(UnstructuredMemoryModel.source == source)
        result = await self.session.execute(q)
        return list(result.scalars().all())
