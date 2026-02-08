"""Lounge (group chat room) database models."""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import JSONB

from app.infra.db.base import Base


class LoungeRoomModel(Base):
    """Lounge chat room."""

    __tablename__ = "lounge_rooms"

    id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    conversation_goal = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LoungeMemberModel(Base):
    """Lounge room member."""

    __tablename__ = "lounge_members"

    room_id = Column(String, ForeignKey("lounge_rooms.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    invited_by_user_id = Column(String, ForeignKey("users.id"), nullable=True)

    __table_args__ = (Index("ix_lounge_members_user_id", "user_id"),)


class LoungeMessageModel(Base):
    """Lounge message (public or private to Kai)."""

    __tablename__ = "lounge_messages"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("lounge_rooms.id"), nullable=False, index=True)
    sender_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)  # None = Kai/system
    content = Column(Text, nullable=False)
    visibility = Column(String, nullable=False, default="public", index=True)  # public | private_to_kai
    sequence = Column(Integer, nullable=False, index=True)  # per-room increment for ordering
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_lounge_messages_room_sequence", "room_id", "sequence"),)


class LoungeKaiContextModel(Base):
    """Kai's context for a room (summary + extracted facts). One row per room."""

    __tablename__ = "lounge_kai_context"

    room_id = Column(String, ForeignKey("lounge_rooms.id"), primary_key=True)
    summary_text = Column(Text, nullable=True)
    extracted_facts = Column(JSONB, nullable=True, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LoungeEventModel(Base):
    """Append-only event log for lounge (replay)."""

    __tablename__ = "lounge_events"

    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey("lounge_rooms.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False, index=True)  # per-room sequence for replay order
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_lounge_events_room_sequence", "room_id", "sequence"),)


class LoungeKaiUserPreferenceModel(Base):
    """Per-user unstructured preference/feedback/memory learned by Kai from lounge (public or private) messages."""

    __tablename__ = "kai_user_preferences"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    # DB column "text" (legacy): same as content; set so INSERT satisfies NOT NULL.
    text_ = Column("text", Text, nullable=False)
    # DB column "type" (legacy): same meaning as kind; set so INSERT satisfies NOT NULL.
    type_ = Column("type", String, nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)  # feedback | preference | personal_info
    source = Column(String, nullable=False, index=True)  # public | private
    room_id = Column(String, ForeignKey("lounge_rooms.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_kai_user_preferences_user_created", "user_id", "created_at"),)
