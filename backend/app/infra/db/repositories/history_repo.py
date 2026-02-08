"""History repository implementation."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.session import SessionModel


class HistoryRepository:
    """History repository for session history."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_sessions(self, user_id: str, limit: int = 100) -> list[dict]:
        """List sessions for a user (history)."""
        from app.infra.db.models.session import session_participants

        result = await self.session.execute(
            select(SessionModel)
            .join(session_participants)
            .where(session_participants.c.user_id == user_id)
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [
            {
                "id": m.id,
                "relationship_id": m.relationship_id,
                "status": m.status,
                "created_at": m.created_at.isoformat(),
            }
            for m in models
        ]
