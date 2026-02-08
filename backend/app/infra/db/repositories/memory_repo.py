"""Memory repository (Insider Compass structured memories)."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.infra.db.models.compass import MemoryModel
from app.domain.common.types import generate_id


class MemoryRepository:
    """Structured memory repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        owner_user_id: str,
        memory_type: str,
        canonical_key: str,
        value_json: dict,
        relationship_id: Optional[str] = None,
        visibility: str = "private",
        confidence: float = 0.5,
        status: str = "hypothesis",
        evidence_event_ids: Optional[list] = None,
    ) -> MemoryModel:
        """Create a memory."""
        memory_id = generate_id()
        now = datetime.utcnow()
        model = MemoryModel(
            memory_id=memory_id,
            owner_user_id=owner_user_id,
            relationship_id=relationship_id,
            visibility=visibility,
            memory_type=memory_type,
            canonical_key=canonical_key,
            value_json=value_json,
            confidence=confidence,
            status=status,
            evidence_event_ids=evidence_event_ids,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get(self, memory_id: str) -> Optional[MemoryModel]:
        """Get a memory by ID."""
        result = await self.session.execute(
            select(MemoryModel).where(MemoryModel.memory_id == memory_id)
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[MemoryModel]:
        """List memories by owner with optional filters."""
        q = (
            select(MemoryModel)
            .where(MemoryModel.owner_user_id == owner_user_id)
            .order_by(MemoryModel.updated_at.desc())
            .limit(limit)
        )
        if relationship_id is not None:
            q = q.where(MemoryModel.relationship_id == relationship_id)
        if memory_type is not None:
            q = q.where(MemoryModel.memory_type == memory_type)
        if status is not None:
            q = q.where(MemoryModel.status == status)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update_status(self, memory_id: str, status: str) -> bool:
        """Update memory status (e.g. hypothesis -> confirmed)."""
        result = await self.session.execute(
            update(MemoryModel)
            .where(MemoryModel.memory_id == memory_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_visibility(self, memory_id: str, visibility: str) -> bool:
        """Update memory visibility."""
        result = await self.session.execute(
            update(MemoryModel)
            .where(MemoryModel.memory_id == memory_id)
            .values(visibility=visibility, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
