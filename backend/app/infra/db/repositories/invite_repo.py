"""Invite repository implementation."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta

from app.infra.db.models.invite import (
    RelationshipInviteModel,
    InviteStatus,
    InviteeRole,
)
from app.domain.common.types import generate_id
import hashlib
import secrets


class InviteRepository:
    """Invite repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _hash_token(self, token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    async def create_invite(
        self,
        relationship_id: str,
        inviter_user_id: str,
        invitee_email: str,
        invitee_role: Optional[InviteeRole] = None,
        message: Optional[str] = None,
        expires_in_days: int = 7,
    ) -> tuple[RelationshipInviteModel, str]:
        """Create an invite and return (model, raw_token)."""
        raw_token = self._generate_token()
        token_hash = self._hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        invite = RelationshipInviteModel(
            id=generate_id(),
            relationship_id=relationship_id,
            inviter_user_id=inviter_user_id,
            invitee_email=invitee_email,
            invitee_role=invitee_role,
            status=InviteStatus.CREATED,
            token_hash=token_hash,
            expires_at=expires_at,
            message=message,
        )
        self.session.add(invite)
        await self.session.commit()
        await self.session.refresh(invite)
        return invite, raw_token

    async def mark_sent(self, invite_id: str) -> RelationshipInviteModel:
        """Mark invite as sent."""
        invite = await self.get_invite(invite_id)
        if not invite:
            raise ValueError(f"Invite {invite_id} not found")
        
        invite.status = InviteStatus.SENT
        invite.sent_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(invite)
        return invite

    async def get_invite(self, invite_id: str) -> Optional[RelationshipInviteModel]:
        """Get invite by ID."""
        result = await self.session.execute(
            select(RelationshipInviteModel).where(
                RelationshipInviteModel.id == invite_id
            )
        )
        return result.scalar_one_or_none()

    async def get_invites_by_relationship(
        self,
        relationship_id: str,
    ) -> List[RelationshipInviteModel]:
        """Get all invites for a relationship."""
        result = await self.session.execute(
            select(RelationshipInviteModel).where(
                RelationshipInviteModel.relationship_id == relationship_id
            )
        )
        return list(result.scalars().all())

    async def get_pending_invites_by_email(
        self,
        email: str,
    ) -> List[RelationshipInviteModel]:
        """Get pending invites for an email."""
        result = await self.session.execute(
            select(RelationshipInviteModel).where(
                and_(
                    RelationshipInviteModel.invitee_email == email,
                    RelationshipInviteModel.status.in_([
                        InviteStatus.SENT,
                        InviteStatus.OPENED,
                    ]),
                )
            )
        )
        return list(result.scalars().all())

    async def update_invitee_user_id(
        self,
        invite_id: str,
        invitee_user_id: str,
    ) -> RelationshipInviteModel:
        """Update invitee_user_id when user is found."""
        invite = await self.get_invite(invite_id)
        if not invite:
            raise ValueError(f"Invite {invite_id} not found")
        
        invite.invitee_user_id = invitee_user_id
        await self.session.commit()
        await self.session.refresh(invite)
        return invite

    async def get_invite_by_token(self, token: str) -> Optional[RelationshipInviteModel]:
        """Get invite by token (validates token hash)."""
        token_hash = self._hash_token(token)
        result = await self.session.execute(
            select(RelationshipInviteModel).where(
                and_(
                    RelationshipInviteModel.token_hash == token_hash,
                    RelationshipInviteModel.expires_at > datetime.utcnow(),
                    RelationshipInviteModel.status != InviteStatus.DECLINED,
                )
            )
        )
        return result.scalar_one_or_none()

    async def regenerate_token(self, invite_id: str) -> tuple[RelationshipInviteModel, str]:
        """Regenerate invite token and return (invite, raw_token). Extends expiry by 7 days."""
        invite = await self.get_invite(invite_id)
        if not invite:
            raise ValueError(f"Invite {invite_id} not found")
        if invite.status not in (InviteStatus.CREATED, InviteStatus.SENT, InviteStatus.OPENED):
            raise ValueError(f"Invite {invite_id} is not pending")
        raw_token = self._generate_token()
        invite.token_hash = self._hash_token(raw_token)
        invite.expires_at = datetime.utcnow() + timedelta(days=7)
        await self.session.commit()
        await self.session.refresh(invite)
        return invite, raw_token

    async def mark_accepted(
        self,
        invite_id: str,
        invitee_user_id: str,
    ) -> RelationshipInviteModel:
        """Mark invite as accepted and set invitee_user_id."""
        invite = await self.get_invite(invite_id)
        if not invite:
            raise ValueError(f"Invite {invite_id} not found")
        
        invite.status = InviteStatus.ACCEPTED
        invite.invitee_user_id = invitee_user_id
        invite.accepted_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(invite)
        return invite
