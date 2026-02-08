"""Context summary repository (per-use-case personalization context)."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import ContextSummaryModel
from app.domain.common.types import generate_id


class ContextSummaryRepository:
    """Context summary repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        relationship_id: Optional[str],
        actor_user_id: str,
        use_case: str,
        scenario: Optional[str],
        summary_text: str,
        evidence_event_ids: Optional[list] = None,
    ) -> ContextSummaryModel:
        """Create or update context summary for (relationship_id or actor_user_id, use_case, scenario)."""
        q = select(ContextSummaryModel).where(
            ContextSummaryModel.actor_user_id == actor_user_id,
            ContextSummaryModel.use_case == use_case,
        )
        if relationship_id is not None:
            q = q.where(ContextSummaryModel.relationship_id == relationship_id)
        else:
            q = q.where(ContextSummaryModel.relationship_id.is_(None))
        if scenario is not None:
            q = q.where(ContextSummaryModel.scenario == scenario)
        else:
            q = q.where(ContextSummaryModel.scenario.is_(None))
        q = q.order_by(ContextSummaryModel.updated_at.desc()).limit(1)
        result = await self.session.execute(q)
        existing = result.scalars().first()
        now = datetime.utcnow()
        if existing:
            existing.summary_text = summary_text
            existing.evidence_event_ids = evidence_event_ids
            existing.updated_at = now
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        summary_id = generate_id()
        model = ContextSummaryModel(
            id=summary_id,
            relationship_id=relationship_id,
            actor_user_id=actor_user_id,
            use_case=use_case,
            scenario=scenario,
            summary_text=summary_text,
            evidence_event_ids=evidence_event_ids,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get(
        self,
        relationship_id: str,
        use_case: str,
        scenario: Optional[str] = None,
    ) -> Optional[ContextSummaryModel]:
        """Get context summary by relationship, use_case, and optional scenario."""
        q = select(ContextSummaryModel).where(
            ContextSummaryModel.relationship_id == relationship_id,
            ContextSummaryModel.use_case == use_case,
        )
        if scenario is not None:
            q = q.where(ContextSummaryModel.scenario == scenario)
        else:
            q = q.where(ContextSummaryModel.scenario.is_(None))
        q = q.order_by(ContextSummaryModel.updated_at.desc()).limit(1)
        result = await self.session.execute(q)
        return result.scalars().first()

    async def get_by_actor(
        self,
        actor_user_id: str,
        use_case: str,
        scenario: Optional[str] = None,
    ) -> Optional[ContextSummaryModel]:
        """Get context summary by actor, use_case, and optional scenario (actor-only, no relationship)."""
        q = select(ContextSummaryModel).where(
            ContextSummaryModel.actor_user_id == actor_user_id,
            ContextSummaryModel.relationship_id.is_(None),
            ContextSummaryModel.use_case == use_case,
        )
        if scenario is not None:
            q = q.where(ContextSummaryModel.scenario == scenario)
        else:
            q = q.where(ContextSummaryModel.scenario.is_(None))
        q = q.order_by(ContextSummaryModel.updated_at.desc()).limit(1)
        result = await self.session.execute(q)
        return result.scalars().first()
