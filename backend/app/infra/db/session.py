"""Database session management."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
