"""Relationship loop repository."""
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.infra.db.models.compass import RelationshipLoopModel
from app.domain.common.types import generate_id


class LoopRepository:
    """Relationship loop repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        relationship_id: str,
        name: str,
        trigger_signals_json: Optional[dict] = None,
        meanings_json: Optional[dict] = None,
        patterns_by_person_json: Optional[dict] = None,
        heat_signature_json: Optional[dict] = None,
        repair_attempts_json: Optional[dict] = None,
        recommended_interruptions_json: Optional[dict] = None,
        confidence: float = 0.5,
        status: str = "hypothesis",
        evidence_event_ids: Optional[list] = None,
    ) -> RelationshipLoopModel:
        """Create a relationship loop."""
        loop_id = generate_id()
        now = datetime.utcnow()
        model = RelationshipLoopModel(
            loop_id=loop_id,
            relationship_id=relationship_id,
            name=name,
            trigger_signals_json=trigger_signals_json or {},
            meanings_json=meanings_json or {},
            patterns_by_person_json=patterns_by_person_json or {},
            heat_signature_json=heat_signature_json or {},
            repair_attempts_json=repair_attempts_json or {},
            recommended_interruptions_json=recommended_interruptions_json or {},
            confidence=confidence,
            status=status,
            evidence_event_ids=evidence_event_ids,
            created_at=now,
            updated_at=now,
            last_seen_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get(self, loop_id: str) -> Optional[RelationshipLoopModel]:
        """Get a loop by ID."""
        result = await self.session.execute(
            select(RelationshipLoopModel).where(RelationshipLoopModel.loop_id == loop_id)
        )
        return result.scalar_one_or_none()

    async def list_by_relationship(
        self,
        relationship_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[RelationshipLoopModel]:
        """List loops by relationship."""
        q = (
            select(RelationshipLoopModel)
            .where(RelationshipLoopModel.relationship_id == relationship_id)
            .order_by(RelationshipLoopModel.last_seen_at.desc().nullslast())
            .limit(limit)
        )
        if status is not None:
            q = q.where(RelationshipLoopModel.status == status)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def update_status(self, loop_id: str, status: str) -> bool:
        """Update loop status (e.g. hypothesis -> confirmed)."""
        result = await self.session.execute(
            update(RelationshipLoopModel)
            .where(RelationshipLoopModel.loop_id == loop_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount > 0
