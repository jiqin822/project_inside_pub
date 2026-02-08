"""Authorization policies."""
from typing import Protocol
from app.domain.admin.models import Consent


class ConsentChecker(Protocol):
    """Consent checker protocol."""

    async def has_scope(
        self, relationship_id: str, user_id: str, scope: str
    ) -> bool:
        """Check if user has scope for relationship."""
        ...


class SimpleConsentChecker:
    """Simple consent checker implementation."""

    def __init__(self, consent_repo):
        self.consent_repo = consent_repo

    async def has_scope(
        self, relationship_id: str, user_id: str, scope: str
    ) -> bool:
        """Check if user has scope."""
        consent = await self.consent_repo.get(relationship_id, user_id)
        if not consent:
            return False
        return scope in consent.scopes
