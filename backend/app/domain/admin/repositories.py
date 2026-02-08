"""Admin domain repository protocols."""
from typing import Protocol

from app.domain.admin.entities import User, Relationship, Consent


class UserRepository(Protocol):
    """User repository protocol."""

    async def create(self, user: User) -> User:
        """Create a new user."""
        ...

    async def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        ...

    async def update(self, user: User) -> User:
        """Update user."""
        ...

    async def delete(self, user_id: str) -> None:
        """Delete user."""
        ...


class RelationshipRepository(Protocol):
    """Relationship repository protocol."""

    async def create(self, relationship: Relationship) -> Relationship:
        """Create a new relationship."""
        ...

    async def get_by_id(self, relationship_id: str) -> Relationship | None:
        """Get relationship by ID."""
        ...

    async def list_by_user(self, user_id: str) -> list[Relationship]:
        """List relationships for a user."""
        ...

    async def update(self, relationship: Relationship) -> Relationship:
        """Update relationship."""
        ...


class ConsentRepository(Protocol):
    """Consent repository protocol."""

    async def create(self, consent: Consent) -> Consent:
        """Create a new consent."""
        ...

    async def get_by_id(self, consent_id: str) -> Consent | None:
        """Get consent by ID."""
        ...

    async def get_by_user_and_relationship(
        self, user_id: str, relationship_id: str
    ) -> Consent | None:
        """Get consent by user and relationship."""
        ...

    async def update(self, consent: Consent) -> Consent:
        """Update consent."""
        ...


class HistoryRepository(Protocol):
    """History repository protocol."""

    async def create(self, history_entry: dict) -> dict:
        """Create a history entry."""
        ...

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[dict]:
        """List history entries for a user."""
        ...
