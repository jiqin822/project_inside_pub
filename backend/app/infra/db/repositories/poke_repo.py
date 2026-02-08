"""Poke repository implementation."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.interaction.models import PokeEvent
from app.domain.interaction.services import PokeRepository
from app.infra.db.models.events import PokeEventModel


class PokeRepositoryImpl(PokeRepository):
    """Poke repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, poke: PokeEvent) -> PokeEvent:
        """Create a new poke."""
        model = PokeEventModel.from_entity(poke)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def list_by_relationship(self, relationship_id: str, limit: int = 100) -> list[PokeEvent]:
        """List pokes for a relationship."""
        result = await self.session.execute(
            select(PokeEventModel)
            .where(PokeEventModel.relationship_id == relationship_id)
            .order_by(PokeEventModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]
