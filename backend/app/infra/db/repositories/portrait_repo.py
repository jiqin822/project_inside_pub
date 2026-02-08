"""Person and dyad portrait repositories."""
from datetime import datetime
from typing import Optional, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import PersonPortraitModel, DyadPortraitModel
from app.domain.common.types import generate_id


class PersonPortraitRepository:
    """Person portrait repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        owner_user_id: str,
        portrait_text: Optional[str] = None,
        portrait_facets_json: Optional[dict] = None,
        relationship_id: Optional[str] = None,
        visibility: str = "private",
        evidence_event_ids: Optional[list] = None,
        confidence: float = 0.5,
    ) -> PersonPortraitModel:
        """Create or update person portrait for owner + relationship. If multiple exist, updates the most recent."""
        q = (
            select(PersonPortraitModel)
            .where(
                PersonPortraitModel.owner_user_id == owner_user_id,
                PersonPortraitModel.relationship_id == relationship_id,
            )
            .order_by(PersonPortraitModel.updated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(q)
        existing = result.scalars().first()
        now = datetime.utcnow()
        if existing:
            if portrait_text is not None:
                existing.portrait_text = portrait_text
            if portrait_facets_json is not None:
                existing.portrait_facets_json = portrait_facets_json
            if evidence_event_ids is not None:
                existing.evidence_event_ids = evidence_event_ids
            existing.confidence = confidence
            existing.visibility = visibility
            existing.updated_at = now
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        portrait_id = generate_id()
        model = PersonPortraitModel(
            portrait_id=portrait_id,
            owner_user_id=owner_user_id,
            relationship_id=relationship_id,
            visibility=visibility,
            portrait_text=portrait_text or "",
            portrait_facets_json=portrait_facets_json or {},
            evidence_event_ids=evidence_event_ids,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_owner(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
    ) -> Optional[PersonPortraitModel]:
        """Get person portrait by owner and optional relationship. If multiple exist, return the most recently updated."""
        q = select(PersonPortraitModel).where(
            PersonPortraitModel.owner_user_id == owner_user_id,
        )
        if relationship_id is not None:
            q = q.where(PersonPortraitModel.relationship_id == relationship_id)
        else:
            q = q.where(PersonPortraitModel.relationship_id.is_(None))
        q = q.order_by(PersonPortraitModel.updated_at.desc()).limit(1)
        result = await self.session.execute(q)
        return result.scalars().first()


class DyadPortraitRepository:
    """Dyad portrait repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        relationship_id: str,
        portrait_text: Optional[str] = None,
        facets_json: Optional[dict] = None,
        evidence_event_ids: Optional[list] = None,
        confidence: float = 0.5,
    ) -> DyadPortraitModel:
        """Create or update dyad portrait. If multiple rows exist for the relationship, updates the most recent."""
        result = await self.session.execute(
            select(DyadPortraitModel)
            .where(DyadPortraitModel.relationship_id == relationship_id)
            .order_by(DyadPortraitModel.updated_at.desc())
            .limit(1)
        )
        existing = result.scalars().first()
        now = datetime.utcnow()
        if existing:
            if portrait_text is not None:
                existing.portrait_text = portrait_text
            if facets_json is not None:
                existing.facets_json = facets_json
            if evidence_event_ids is not None:
                existing.evidence_event_ids = evidence_event_ids
            existing.confidence = confidence
            existing.updated_at = now
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        dyad_portrait_id = generate_id()
        model = DyadPortraitModel(
            dyad_portrait_id=dyad_portrait_id,
            relationship_id=relationship_id,
            portrait_text=portrait_text or "",
            facets_json=facets_json or {},
            evidence_event_ids=evidence_event_ids,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_by_relationship(self, relationship_id: str) -> Optional[DyadPortraitModel]:
        """Get dyad portrait by relationship. If multiple exist, returns the most recently updated."""
        result = await self.session.execute(
            select(DyadPortraitModel)
            .where(DyadPortraitModel.relationship_id == relationship_id)
            .order_by(DyadPortraitModel.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()
