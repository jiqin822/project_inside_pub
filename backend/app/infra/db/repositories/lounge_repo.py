"""Lounge (group chat room) repository: rooms, members, messages, Kai context, events."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.types import generate_id
from app.infra.db.models.lounge import (
    LoungeRoomModel,
    LoungeMemberModel,
    LoungeMessageModel,
    LoungeKaiContextModel,
    LoungeEventModel,
    LoungeKaiUserPreferenceModel,
)


async def _next_sequence(session: AsyncSession, model_class: type, room_id: str, column_name: str = "sequence") -> int:
    """Return next per-room sequence (caller must use within same transaction)."""
    col = getattr(model_class, column_name)
    subq = select(func.coalesce(func.max(col), 0) + 1).where(model_class.room_id == room_id)
    result = await session.execute(subq)
    return result.scalar() or 1


class LoungeRepository:
    """Single repository for lounge rooms, members, messages, Kai context, and event log."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- Rooms ----
    async def create_room(
        self,
        owner_user_id: str,
        title: Optional[str] = None,
        conversation_goal: Optional[str] = None,
    ) -> LoungeRoomModel:
        room_id = generate_id()
        room = LoungeRoomModel(
            id=room_id,
            owner_user_id=owner_user_id,
            title=title,
            conversation_goal=conversation_goal,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.session.add(room)
        await self.session.flush()
        return room

    async def get_room(self, room_id: str) -> Optional[LoungeRoomModel]:
        result = await self.session.execute(select(LoungeRoomModel).where(LoungeRoomModel.id == room_id))
        return result.scalar_one_or_none()

    async def delete_room(self, room_id: str) -> None:
        """Delete a room and all related data (events, kai context, messages, members, kai user preferences). Caller must be owner."""
        await self.session.execute(delete(LoungeEventModel).where(LoungeEventModel.room_id == room_id))
        await self.session.execute(delete(LoungeKaiContextModel).where(LoungeKaiContextModel.room_id == room_id))
        await self.session.execute(delete(LoungeMessageModel).where(LoungeMessageModel.room_id == room_id))
        await self.session.execute(delete(LoungeMemberModel).where(LoungeMemberModel.room_id == room_id))
        await self.session.execute(delete(LoungeKaiUserPreferenceModel).where(LoungeKaiUserPreferenceModel.room_id == room_id))
        await self.session.execute(delete(LoungeRoomModel).where(LoungeRoomModel.id == room_id))
        await self.session.flush()

    async def list_rooms_for_user(self, user_id: str) -> list[LoungeRoomModel]:
        result = await self.session.execute(
            select(LoungeRoomModel)
            .join(LoungeMemberModel, LoungeRoomModel.id == LoungeMemberModel.room_id)
            .where(LoungeMemberModel.user_id == user_id)
            .order_by(LoungeRoomModel.updated_at.desc())
        )
        rooms = list(result.scalars().unique().all())
        return rooms

    # ---- Members ----
    async def add_member(
        self, room_id: str, user_id: str, invited_by_user_id: Optional[str] = None
    ) -> LoungeMemberModel:
        member = LoungeMemberModel(
            room_id=room_id,
            user_id=user_id,
            joined_at=datetime.utcnow(),
            invited_by_user_id=invited_by_user_id,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def list_members(self, room_id: str) -> list[LoungeMemberModel]:
        result = await self.session.execute(
            select(LoungeMemberModel).where(LoungeMemberModel.room_id == room_id)
        )
        return list(result.scalars().all())

    async def is_member(self, room_id: str, user_id: str) -> bool:
        result = await self.session.execute(
            select(LoungeMemberModel).where(
                LoungeMemberModel.room_id == room_id,
                LoungeMemberModel.user_id == user_id,
            )
        )
        return result.first() is not None

    # ---- Messages ----
    async def append_message(
        self,
        room_id: str,
        sender_user_id: Optional[str],
        content: str,
        visibility: str = "public",
    ) -> LoungeMessageModel:
        seq = await _next_sequence(self.session, LoungeMessageModel, room_id)
        msg = LoungeMessageModel(
            id=generate_id(),
            room_id=room_id,
            sender_user_id=sender_user_id,
            content=content,
            visibility=visibility,
            sequence=seq,
            created_at=datetime.utcnow(),
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def list_public_messages(
        self,
        room_id: str,
        limit: int = 100,
        before_sequence: Optional[int] = None,
        after_created_at: Optional[datetime] = None,
    ) -> list[LoungeMessageModel]:
        """List public messages. If after_created_at is set (e.g. viewer's joined_at), only messages created at or after that time are returned."""
        q = (
            select(LoungeMessageModel)
            .where(
                LoungeMessageModel.room_id == room_id,
                LoungeMessageModel.visibility == "public",
            )
            .order_by(LoungeMessageModel.sequence.desc())
            .limit(limit)
        )
        if before_sequence is not None:
            q = q.where(LoungeMessageModel.sequence < before_sequence)
        if after_created_at is not None:
            q = q.where(LoungeMessageModel.created_at >= after_created_at)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def list_private_messages_for_user(
        self, room_id: str, user_id: str, limit: int = 50
    ) -> list[LoungeMessageModel]:
        """Private thread: messages from this user and Kai replies (sender_user_id IS NULL)."""
        result = await self.session.execute(
            select(LoungeMessageModel)
            .where(
                LoungeMessageModel.room_id == room_id,
                LoungeMessageModel.visibility == "private_to_kai",
                or_(
                    LoungeMessageModel.sender_user_id == user_id,
                    LoungeMessageModel.sender_user_id.is_(None),
                ),
            )
            .order_by(LoungeMessageModel.sequence.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ---- Kai context ----
    async def get_or_create_kai_context(self, room_id: str) -> LoungeKaiContextModel:
        result = await self.session.execute(
            select(LoungeKaiContextModel).where(LoungeKaiContextModel.room_id == room_id)
        )
        ctx = result.scalar_one_or_none()
        if ctx is None:
            ctx = LoungeKaiContextModel(
                room_id=room_id,
                summary_text=None,
                extracted_facts={},
                updated_at=datetime.utcnow(),
            )
            self.session.add(ctx)
            await self.session.flush()
        return ctx

    async def update_kai_context(
        self, room_id: str, summary_text: Optional[str], extracted_facts: Optional[dict]
    ) -> LoungeKaiContextModel:
        ctx = await self.get_or_create_kai_context(room_id)
        if summary_text is not None:
            ctx.summary_text = summary_text
        if extracted_facts is not None:
            existing = ctx.extracted_facts or {}
            merged = {**existing, **extracted_facts}
            ctx.extracted_facts = merged
        ctx.updated_at = datetime.utcnow()
        await self.session.flush()
        return ctx

    # ---- Event log (append-only for replay) ----
    async def append_event(self, room_id: str, event_type: str, payload: dict) -> LoungeEventModel:
        seq = await _next_sequence(self.session, LoungeEventModel, room_id)
        event = LoungeEventModel(
            id=generate_id(),
            room_id=room_id,
            sequence=seq,
            event_type=event_type,
            payload=payload,
            created_at=datetime.utcnow(),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_events(
        self,
        room_id: str,
        limit: int = 200,
        from_sequence: Optional[int] = None,
    ) -> list[LoungeEventModel]:
        q = (
            select(LoungeEventModel)
            .where(LoungeEventModel.room_id == room_id)
            .order_by(LoungeEventModel.sequence.asc())
            .limit(limit)
        )
        if from_sequence is not None:
            q = q.where(LoungeEventModel.sequence >= from_sequence)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    # ---- Kai user preferences (feedback / preference / personal_info) ----
    async def add_preference(
        self,
        user_id: str,
        content: str,
        kind: str,
        source: str,
        room_id: Optional[str] = None,
    ) -> LoungeKaiUserPreferenceModel:
        pref = LoungeKaiUserPreferenceModel(
            id=generate_id(),
            user_id=user_id,
            content=content,
            text_=content,
            type_=kind,
            kind=kind,
            source=source,
            room_id=room_id,
            created_at=datetime.utcnow(),
        )
        self.session.add(pref)
        await self.session.flush()
        return pref

    async def list_preferences_for_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[LoungeKaiUserPreferenceModel]:
        result = await self.session.execute(
            select(LoungeKaiUserPreferenceModel)
            .where(LoungeKaiUserPreferenceModel.user_id == user_id)
            .order_by(LoungeKaiUserPreferenceModel.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
