"""Session repository implementation."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.domain.coach.models import Session, SessionParticipant, SessionReport
from app.domain.coach.services import (
    SessionRepository,
    SessionReportRepository,
    NudgeEventRepository,
)
from app.infra.db.models.session import (
    SessionModel,
    SessionReportModel,
    NudgeEventModel,
    session_participants,
)


class SessionRepositoryImpl(SessionRepository):
    """Session repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, session: Session) -> Session:
        """Create a new session."""
        model = SessionModel.from_entity(session)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        result = await self.session.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def add_participant(self, participant: SessionParticipant) -> SessionParticipant:
        """Add participant to session."""
        stmt = session_participants.insert().values(
            session_id=participant.session_id,
            user_id=participant.user_id,
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return participant

    async def get_participants(self, session_id: str) -> list[str]:
        """Get participant user IDs for session."""
        result = await self.session.execute(
            select(session_participants.c.user_id).where(
                session_participants.c.session_id == session_id
            )
        )
        return [row[0] for row in result.all()]

    async def finalize(self, session_id: str) -> Session:
        """Finalize a session."""
        from datetime import datetime
        from app.infra.db.models.session import SessionStatus
        
        await self.session.execute(
            update(SessionModel)
            .where(SessionModel.id == session_id)
            .values(
                status=SessionStatus.ENDED,
                ended_at=datetime.utcnow()
            )
        )
        await self.session.commit()
        return await self.get_by_id(session_id)
    
    async def list_by_user(self, user_id: str, limit: int = 20) -> list[Session]:
        """List sessions where user is a participant."""
        from sqlalchemy import select
        from app.infra.db.models.session import SessionModel, session_participants
        
        result = await self.session.execute(
            select(SessionModel)
            .join(session_participants, SessionModel.id == session_participants.c.session_id)
            .where(session_participants.c.user_id == user_id)
            .order_by(SessionModel.created_at.desc())
            .limit(limit)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]


class SessionReportRepositoryImpl(SessionReportRepository):
    """Session report repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, report: SessionReport) -> SessionReport:
        """Create a session report."""
        model = SessionReportModel.from_entity(report)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def get_by_session_id(self, session_id: str) -> Optional[SessionReport]:
        """Get report by session ID."""
        result = await self.session.execute(
            select(SessionReportModel).where(SessionReportModel.session_id == session_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None


class NudgeEventRepositoryImpl(NudgeEventRepository):
    """Nudge event repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: dict) -> dict:
        """Create a nudge event."""
        model = NudgeEventModel(
            id=event.get("id"),
            session_id=event["session_id"],
            user_id=event["user_id"],
            nudge_type=event["nudge_type"],
            payload=event["payload"],
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_dict()

    async def list_by_session(self, session_id: str) -> list[dict]:
        """List nudge events for a session."""
        result = await self.session.execute(
            select(NudgeEventModel)
            .where(NudgeEventModel.session_id == session_id)
            .order_by(NudgeEventModel.created_at.desc())
        )
        models = result.scalars().all()
        return [m.to_dict() for m in models]
