"""Device repository for push tokens."""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.device import DeviceModel
from app.domain.common.types import generate_id


class DeviceRepository:
    """Device repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_by_token(
        self, user_id: str, push_token: str, platform: str
    ) -> DeviceModel:
        """Insert or update device by push_token. Same token overwrites (one token per device)."""
        existing = await self.session.execute(
            select(DeviceModel).where(DeviceModel.push_token == push_token)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.user_id = user_id
            row.platform = platform
            await self.session.commit()
            await self.session.refresh(row)
            return row
        model = DeviceModel(
            id=generate_id(),
            user_id=user_id,
            push_token=push_token,
            platform=platform,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def list_tokens_by_user(self, user_id: str) -> List[tuple]:
        """List (push_token, platform) for a user. Used by push sender."""
        result = await self.session.execute(
            select(DeviceModel.push_token, DeviceModel.platform).where(
                DeviceModel.user_id == user_id
            )
        )
        return list(result.all())
