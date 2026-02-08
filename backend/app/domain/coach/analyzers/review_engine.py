"""Review engine for generating session reports."""
from typing import Any
from app.domain.coach.models import SessionReport


class ReviewEngine:
    """Review engine for generating session reports."""

    def generate_report(self, session_id: str, nudge_events: list[dict[str, Any]]) -> SessionReport:
        """
        Generate a session report from nudge events.
        This is a stub implementation for MVP.
        """
        # Count nudge types
        slow_down_count = sum(1 for e in nudge_events if e.get("nudge_type") == "SLOW_DOWN")
        pause_count = sum(1 for e in nudge_events if e.get("nudge_type") == "PAUSE")

        summary = f"{len(nudge_events)} nudges delivered. Try more pauses."
        if slow_down_count > 0:
            summary = f"{len(nudge_events)} nudges delivered. {slow_down_count} slow-down suggestions, {pause_count} pause suggestions."

        moments = []  # Empty for MVP as per requirements

        action_items = []
        if slow_down_count > 3:
            action_items.append("Practice slower speech in future sessions")
        if pause_count > 3:
            action_items.append("Try to pause more and allow the other person to speak")
        if len(nudge_events) > 0 and len(action_items) == 0:
            action_items.append("Continue practicing active listening")

        return SessionReport.create(
            session_id=session_id,
            summary=summary,
            moments=moments,
            action_items=action_items,
            status="READY",
        )
