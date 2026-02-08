"""Relationship invite database models."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum
import enum

from app.infra.db.base import Base


class InviteeRole(str, enum.Enum):
    """Invitee role enum."""
    PARTNER = "PARTNER"
    CHILD = "CHILD"
    FRIEND = "FRIEND"
    FAMILY = "FAMILY"
    OTHER = "OTHER"


class InviteStatus(str, enum.Enum):
    """Invite status enum."""
    CREATED = "CREATED"
    SENT = "SENT"
    OPENED = "OPENED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELED = "CANCELED"


class RelationshipInviteModel(Base):
    """Relationship invite database model."""

    __tablename__ = "relationship_invites"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    inviter_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    invitee_email = Column(String, nullable=False, index=True)
    invitee_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    invitee_role = Column(SQLEnum(InviteeRole), nullable=True)
    status = Column(SQLEnum(InviteStatus), nullable=False, default=InviteStatus.CREATED)
    token_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)
