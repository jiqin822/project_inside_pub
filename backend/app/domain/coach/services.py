"""Coach domain services."""
from typing import Protocol, Optional
from app.domain.coach.models import Session, SessionParticipant, SessionReport, ActivitySuggestion
from app.domain.common.errors import NotFoundError, AuthorizationError


class SessionRepository(Protocol):
    """Session repository protocol."""

    async def create(self, session: Session) -> Session:
        """Create a new session."""
        ...

    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        ...

    async def add_participant(self, participant: SessionParticipant) -> SessionParticipant:
        """Add participant to session."""
        ...

    async def get_participants(self, session_id: str) -> list[str]:
        """Get participant user IDs for session."""
        ...

    async def finalize(self, session_id: str) -> Session:
        """Finalize a session."""
        ...


class SessionReportRepository(Protocol):
    """Session report repository protocol."""

    async def create(self, report: SessionReport) -> SessionReport:
        """Create a session report."""
        ...

    async def get_by_session_id(self, session_id: str) -> Optional[SessionReport]:
        """Get report by session ID."""
        ...


class NudgeEventRepository(Protocol):
    """Nudge event repository protocol."""

    async def create(self, event: dict) -> dict:
        """Create a nudge event."""
        ...

    async def list_by_session(self, session_id: str) -> list[dict]:
        """List nudge events for a session."""
        ...


class SessionService:
    """Session service."""

    def __init__(
        self,
        session_repo: SessionRepository,
        relationship_repo,  # RelationshipRepository protocol
    ):
        self.session_repo = session_repo
        self.relationship_repo = relationship_repo

    async def create_session(
        self, relationship_id: str, participants: list[str], creator_id: str
    ) -> Session:
        """Create a new session."""
        # Verify relationship exists
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)

        # Verify all participants are members
        for user_id in participants:
            is_member = await self.relationship_repo.is_member(relationship_id, user_id)
            if not is_member:
                raise AuthorizationError(f"User {user_id} is not a member of this relationship")

        # Ensure creator is in participants
        if creator_id not in participants:
            participants.append(creator_id)

        session = Session.create(relationship_id=relationship_id, creator_id=creator_id, status="ACTIVE")
        created = await self.session_repo.create(session)

        # Add participants
        for user_id in participants:
            participant = SessionParticipant.create(
                session_id=created.id, user_id=user_id
            )
            await self.session_repo.add_participant(participant)

        return created

    async def get_session(self, session_id: str) -> Session:
        """Get session by ID."""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError("Session", session_id)
        return session

    async def finalize_session(self, session_id: str) -> Session:
        """Finalize a session."""
        session = await self.get_session(session_id)
        if session.status == "FINALIZED":
            return session
        return await self.session_repo.finalize(session_id)

    async def get_session_participants(self, session_id: str) -> list[str]:
        """Get session participants."""
        return await self.session_repo.get_participants(session_id)


class SessionReportService:
    """Session report service."""

    def __init__(
        self,
        report_repo: SessionReportRepository,
        nudge_repo: NudgeEventRepository,
    ):
        self.report_repo = report_repo
        self.nudge_repo = nudge_repo

    async def get_or_create_report(self, session_id: str) -> SessionReport:
        """Get report by session ID, or create pending one if missing."""
        report = await self.report_repo.get_by_session_id(session_id)
        if not report:
            # Create pending report
            report = SessionReport.create(
                session_id=session_id,
                summary="Report pending...",
                status="PENDING",
            )
            report = await self.report_repo.create(report)
        return report

    async def generate_report(self, session_id: str) -> SessionReport:
        """Generate a report for a session."""
        from app.domain.coach.analyzers.review_engine import ReviewEngine
        
        # Get nudge events
        nudge_events = await self.nudge_repo.list_by_session(session_id)
        
        # Generate report using review engine
        review_engine = ReviewEngine()
        report = review_engine.generate_report(session_id, nudge_events)
        report.status = "READY"
        
        # Upsert report
        existing = await self.report_repo.get_by_session_id(session_id)
        if existing:
            # Update existing
            from datetime import datetime
            report.updated_at = datetime.utcnow()
            # Note: Repository should handle update - for now we'll create new
            # In production, add update method to repository
        
        return await self.report_repo.create(report)


class ActivitySuggestionService:
    """Activity suggestion service."""

    def get_suggestions(self, relationship_id: str) -> list[ActivitySuggestion]:
        """
        Get activity suggestions for a relationship.
        Returns static list for MVP.
        """
        return [
            ActivitySuggestion.create(
                title="Daily Check-in",
                description="Set aside 10 minutes each day to check in with each other.",
            ),
            ActivitySuggestion.create(
                title="Gratitude Exercise",
                description="Share three things you're grateful for about your relationship.",
            ),
            ActivitySuggestion.create(
                title="Active Listening Practice",
                description="Practice active listening by summarizing what the other person said.",
            ),
            ActivitySuggestion.create(
                title="Conflict Resolution Workshop",
                description="Work through a small disagreement using structured communication.",
            ),
            ActivitySuggestion.create(
                title="Shared Goal Setting",
                description="Set and work towards a shared goal together.",
            ),
        ]
