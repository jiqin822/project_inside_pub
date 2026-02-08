"""Common domain types."""
from datetime import datetime
from uuid import UUID, uuid4
from typing import Protocol


def generate_id() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


class Timestamped:
    """Mixin for timestamped entities."""
    created_at: datetime
    updated_at: datetime
