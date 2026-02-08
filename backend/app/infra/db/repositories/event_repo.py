"""Compass event repository."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import CompassEventModel
from app.domain.common.types import generate_id


class EventRepository:
    """Insider Compass event repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def append(
        self,
        type: str,
        actor_user_id: str,
        payload: dict,
        source: str,
        relationship_id: Optional[str] = None,
        privacy_scope: str = "private",
    ) -> CompassEventModel:
        """Append an event to the stream."""
        event_id = generate_id()
        now = datetime.utcnow()
        model = CompassEventModel(
            event_id=event_id,
            type=type,
            actor_user_id=actor_user_id,
            relationship_id=relationship_id,
            payload_json=payload,
            created_at=now,
            privacy_scope=privacy_scope,
            source=source,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def list_by_actor(
        self,
        actor_user_id: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[CompassEventModel]:
        """List events by actor, newest first."""
        q = (
            select(CompassEventModel)
            .where(CompassEventModel.actor_user_id == actor_user_id)
            .order_by(CompassEventModel.created_at.desc())
            .limit(limit)
        )
        if since is not None:
            q = q.where(CompassEventModel.created_at >= since)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_by_relationship(
        self,
        relationship_id: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[CompassEventModel]:
        """List events by relationship, newest first."""
        q = (
            select(CompassEventModel)
            .where(CompassEventModel.relationship_id == relationship_id)
            .order_by(CompassEventModel.created_at.desc())
            .limit(limit)
        )
        if since is not None:
            q = q.where(CompassEventModel.created_at >= since)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count_unprocessed_by_actor(self, actor_user_id: str) -> int:
        """Count events for actor (schema has no processed_at; treat all as unprocessed)."""
        from sqlalchemy import func
        q = select(func.count()).select_from(CompassEventModel).where(
            CompassEventModel.actor_user_id == actor_user_id,
        )
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def count_unprocessed_by_relationship(self, relationship_id: str) -> int:
        """Count events for relationship (schema has no processed_at; treat all as unprocessed)."""
        from sqlalchemy import func
        q = select(func.count()).select_from(CompassEventModel).where(
            CompassEventModel.relationship_id == relationship_id,
        )
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def list_unprocessed_by_actor(
        self,
        actor_user_id: str,
        limit: int = 50,
    ) -> List[CompassEventModel]:
        """List events by actor, newest first (schema has no processed_at)."""
        return await self.list_by_actor(actor_user_id, limit=limit)

    async def list_unprocessed_by_relationship(
        self,
        relationship_id: str,
        limit: int = 50,
    ) -> List[CompassEventModel]:
        """List events by relationship, newest first (schema has no processed_at)."""
        return await self.list_by_relationship(relationship_id, limit=limit)

    async def mark_processed(self, event_ids: List[str]) -> None:
        """No-op when processed_at column does not exist."""
        pass
