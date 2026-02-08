"""Coach domain repository protocols."""
from typing import Protocol

from app.domain.coach.entities import Activity, ReviewJob


class ActivityRepository(Protocol):
    """Activity repository protocol."""

    async def create(self, activity: Activity) -> Activity:
        """Create a new activity."""
        ...

    async def get_by_id(self, activity_id: str) -> Activity | None:
        """Get activity by ID."""
        ...

    async def list_by_relationship(self, relationship_id: str, limit: int = 100) -> list[Activity]:
        """List activities for a relationship."""
        ...


class ReviewJobRepository(Protocol):
    """Review job repository protocol."""

    async def create(self, job: ReviewJob) -> ReviewJob:
        """Create a new review job."""
        ...

    async def get_by_id(self, job_id: str) -> ReviewJob | None:
        """Get review job by ID."""
        ...

    async def list_pending(self, limit: int = 100) -> list[ReviewJob]:
        """List pending review jobs."""
        ...

    async def update(self, job: ReviewJob) -> ReviewJob:
        """Update review job."""
        ...
