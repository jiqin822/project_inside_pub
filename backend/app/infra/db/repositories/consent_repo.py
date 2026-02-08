"""Consent repository implementation."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from app.domain.admin.models import Consent
from app.domain.admin.services import ConsentRepository
from app.infra.db.models.relationship import ConsentModel, ConsentStatus


class ConsentRepositoryImpl(ConsentRepository):
    """Consent repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update(
        self,
        relationship_id: str,
        user_id: str,
        scopes: List[str],
        status: ConsentStatus = ConsentStatus.ACTIVE,
    ) -> ConsentModel:
        """Create or update consent."""
        existing = await self.get_model(relationship_id, user_id)
        
        if existing:
            # Increment version
            new_version = str(int(existing.version) + 1) if existing.version.isdigit() else "2"
            await self.session.execute(
                update(ConsentModel)
                .where(
                    ConsentModel.relationship_id == relationship_id,
                    ConsentModel.user_id == user_id,
                )
                .values(
                    scopes=scopes,
                    status=status,
                    version=new_version,
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            model = ConsentModel(
                relationship_id=relationship_id,
                user_id=user_id,
                scopes=scopes,
                status=status,
                version="1",
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return model

    async def get(self, relationship_id: str, user_id: str) -> Optional[Consent]:
        """Get consent."""
        model = await self.get_model(relationship_id, user_id)
        return model.to_entity() if model else None

    async def get_model(self, relationship_id: str, user_id: str) -> Optional[ConsentModel]:
        """Get consent model."""
        result = await self.session.execute(
            select(ConsentModel).where(
                ConsentModel.relationship_id == relationship_id,
                ConsentModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_for_relationship(
        self,
        relationship_id: str,
    ) -> List[ConsentModel]:
        """Get all consents for a relationship."""
        result = await self.session.execute(
            select(ConsentModel).where(
                ConsentModel.relationship_id == relationship_id
            )
        )
        return list(result.scalars().all())
