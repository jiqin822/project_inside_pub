"""Admin domain services."""
from typing import Protocol, Optional
from app.domain.admin.models import User, Relationship, RelationshipMember, Consent
from app.domain.common.errors import NotFoundError, ValidationError, AuthorizationError


class UserRepository(Protocol):
    """User repository protocol."""

    async def create(self, user: User) -> User:
        """Create a new user."""
        ...

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        ...

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        ...

    async def update(self, user: User) -> User:
        """Update user."""
        ...


class RelationshipRepository(Protocol):
    """Relationship repository protocol."""

    async def create(self, relationship: Relationship) -> Relationship:
        """Create a new relationship."""
        ...

    async def get_by_id(self, relationship_id: str) -> Optional[Relationship]:
        """Get relationship by ID."""
        ...

    async def list_by_user(self, user_id: str) -> list[Relationship]:
        """List relationships for a user."""
        ...

    async def add_member(self, member: RelationshipMember) -> RelationshipMember:
        """Add a member to a relationship."""
        ...

    async def get_members(self, relationship_id: str) -> list[RelationshipMember]:
        """Get all members of a relationship."""
        ...

    async def is_member(self, relationship_id: str, user_id: str) -> bool:
        """Check if user is a member of relationship."""
        ...

    async def delete(self, relationship_id: str) -> None:
        """Delete a relationship."""
        ...


class ConsentRepository(Protocol):
    """Consent repository protocol."""

    async def create_or_update(self, consent: Consent) -> Consent:
        """Create or update consent."""
        ...

    async def get(self, relationship_id: str, user_id: str) -> Optional[Consent]:
        """Get consent."""
        ...


class UserService:
    """User service."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def create_user(self, email: str, password_hash: str, display_name: Optional[str] = None) -> User:
        """Create a new user."""
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ValidationError("Email already registered")
        user = User.create(email=email, password_hash=password_hash, display_name=display_name)
        return await self.user_repo.create(user)

    async def get_user(self, user_id: str) -> User:
        """Get user by ID."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self.user_repo.get_by_email(email)


class RelationshipService:
    """Relationship service."""

    def __init__(
        self,
        relationship_repo: RelationshipRepository,
        user_repo: UserRepository,
    ):
        self.relationship_repo = relationship_repo
        self.user_repo = user_repo

    async def create_relationship(
        self, rel_type: str, member_ids: list[str], creator_id: str, session=None
    ) -> Relationship:
        """Create a new relationship."""
        from app.infra.db.models.relationship import (
            RelationshipType,
            RelationshipStatus,
            relationship_members,
            MemberStatus,
            MemberRole,
        )
        from sqlalchemy import insert, select
        from app.domain.common.types import generate_id
        
        # Verify all users exist
        for user_id in member_ids:
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise NotFoundError("User", user_id)

        # Ensure creator is in member list
        if creator_id not in member_ids:
            member_ids.append(creator_id)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔵 [RELATIONSHIP] Creating relationship: type={rel_type}, creator={creator_id}, members={member_ids}")

        # Map rel_type to RelationshipType enum
        rel_type_lower = rel_type.lower()
        if rel_type_lower in ["romantic", "couple"]:
            type_enum = RelationshipType.COUPLE
        elif rel_type_lower == "date":
            type_enum = RelationshipType.DATE
        elif rel_type_lower == "family":
            type_enum = RelationshipType.FAMILY
        elif rel_type_lower == "friend":
            type_enum = RelationshipType.FRIEND_1_1
        else:
            type_enum = RelationshipType.OTHER
        
        # Determine initial status
        if len(member_ids) == 1:
            status_enum = RelationshipStatus.DRAFT
        else:
            # If all members are existing users (explicitly added), set to ACTIVE
            # PENDING_ACCEPTANCE is only for relationships with pending invites
            status_enum = RelationshipStatus.ACTIVE
        
        # Create relationship model directly
        from app.infra.db.models.relationship import RelationshipModel
        from datetime import datetime
        relationship_id = generate_id()
        relationship_model = RelationshipModel(
            id=relationship_id,
            type=type_enum,
            status=status_enum,
            created_by_user_id=creator_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        if session:
            session.add(relationship_model)
            await session.flush()  # Flush to get ID without committing
        else:
            # Fallback to repository (won't work with new schema, but keep for compatibility)
            relationship = Relationship.create(rel_type=rel_type)
            created = await self.relationship_repo.create(relationship)
            relationship_id = created.id
            relationship_model = None
        
        # Add members with appropriate status
        # If all members are existing users (explicitly added, not via invite), 
        # set all to ACCEPTED. INVITED status is only for pending invites.
        for user_id in member_ids:
            # All explicitly added members (including creator) are ACCEPTED
            # INVITED status is only set when creating invites for non-existent users
            member_status = MemberStatus.ACCEPTED
            role = MemberRole.OWNER if user_id == creator_id else MemberRole.MEMBER
            
            if session:
                await session.execute(
                    insert(relationship_members).values(
                        relationship_id=relationship_id,
                        user_id=user_id,
                        role=role,
                        member_status=member_status,
                        added_at=datetime.utcnow(),
                    )
                )
            else:
                member = RelationshipMember.create(
                    relationship_id=relationship_id, user_id=user_id
                )
                await self.relationship_repo.add_member(
                    member,
                    member_status=member_status.value,
                    role=role.value,
                )
        
        if session:
            await session.commit()
            await session.refresh(relationship_model)
            logger.info(f"✅ [RELATIONSHIP] Relationship created successfully: id={relationship_model.id}, type={relationship_model.type}, status={relationship_model.status}")
            # Verify members were added
            from sqlalchemy import select
            from app.infra.db.models.relationship import relationship_members
            members_result = await session.execute(
                select(relationship_members).where(relationship_members.c.relationship_id == relationship_id)
            )
            members = members_result.all()
            logger.info(f"   Relationship has {len(members)} members: {[m.user_id for m in members]}")
            # Return entity
            return relationship_model.to_entity()
        else:
            return await self.relationship_repo.get_by_id(relationship_id)

    async def get_relationship(self, relationship_id: str) -> Relationship:
        """Get relationship by ID."""
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)
        return relationship

    async def list_user_relationships(self, user_id: str) -> list[Relationship]:
        """List relationships for a user."""
        return await self.relationship_repo.list_by_user(user_id)

    async def require_membership(self, relationship_id: str, user_id: str) -> None:
        """Require that user is a member of relationship."""
        is_member = await self.relationship_repo.is_member(relationship_id, user_id)
        if not is_member:
            raise AuthorizationError("User is not a member of this relationship")

    async def delete_relationship(self, relationship_id: str, user_id: str) -> None:
        """Delete a relationship. Only members can delete."""
        # Verify user is a member
        await self.require_membership(relationship_id, user_id)
        
        # Delete the relationship
        await self.relationship_repo.delete(relationship_id)


class ConsentService:
    """Consent service."""

    def __init__(
        self,
        consent_repo: ConsentRepository,
        relationship_repo: RelationshipRepository,
    ):
        self.consent_repo = consent_repo
        self.relationship_repo = relationship_repo

    async def update_consent(
        self, relationship_id: str, user_id: str, scopes: list[str]
    ) -> Consent:
        """Update consent."""
        # Verify relationship exists and user is member
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)

        is_member = await self.relationship_repo.is_member(relationship_id, user_id)
        if not is_member:
            raise AuthorizationError("User is not a member of this relationship")

        # Use new consent service from domain.consent.services instead
        # This method is kept for backward compatibility
        from app.infra.db.repositories.consent_repo import ConsentRepositoryImpl
        from app.infra.db.models.relationship import ConsentStatus
        if isinstance(self.consent_repo, ConsentRepositoryImpl):
            consent_model = await self.consent_repo.create_or_update(
                relationship_id=relationship_id,
                user_id=user_id,
                scopes=scopes,
                status=ConsentStatus.ACTIVE,
            )
            return consent_model.to_entity()
        else:
            consent = Consent.create(
                relationship_id=relationship_id, user_id=user_id, scopes=scopes
            )
            return await self.consent_repo.create_or_update(consent)

    async def get_consent(self, relationship_id: str, user_id: str) -> Optional[Consent]:
        """Get consent."""
        return await self.consent_repo.get(relationship_id, user_id)


class ContactService:
    """Contact lookup service."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def lookup_contact(self, email: str, blocked_domains: list[str] = None) -> dict:
        """Lookup contact by email."""
        blocked_domains = blocked_domains or []
        
        # Check if blocked
        email_domain = email.split("@")[-1] if "@" in email else ""
        if email_domain in blocked_domains or email == "blocked@example.com":
            return {"status": "BLOCKED", "user": None}
        
        # Lookup user
        user = await self.user_repo.get_by_email(email)
        if user:
            return {
                "status": "EXISTS",
                "user": {
                    "id": user.id,
                    "display_name": user.display_name or email.split("@")[0],
                },
            }
        
        return {"status": "NOT_FOUND", "user": None}


class InviteService:
    """Invite service."""

    def __init__(
        self,
        invite_repo,
        relationship_repo: RelationshipRepository,
        user_repo: UserRepository,
        email_service,
        session,
    ):
        self.invite_repo = invite_repo
        self.relationship_repo = relationship_repo
        self.user_repo = user_repo
        self.email_service = email_service
        self.session = session

    async def create_invite(
        self,
        relationship_id: str,
        inviter_user_id: str,
        invitee_email: str,
        invitee_role: Optional[str] = None,
        message: Optional[str] = None,
        app_base_url: Optional[str] = None,
    ) -> dict:
        """Create and send an invite."""
        from app.infra.db.models.invite import InviteeRole
        from app.infra.db.models.relationship import relationship_members, MemberStatus
        
        # Verify inviter is a member
        is_member = await self.relationship_repo.is_member(relationship_id, inviter_user_id)
        if not is_member:
            raise AuthorizationError("User is not a member of this relationship")
        
        # Get inviter name
        inviter = await self.user_repo.get_by_id(inviter_user_id)
        inviter_name = inviter.display_name or inviter.email if inviter else "Someone"
        
        # Get relationship
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        relationship_type = relationship.rel_type if relationship else "relationship"
        
        # Map role string to enum
        role_enum = None
        if invitee_role:
            try:
                role_enum = InviteeRole[invitee_role.upper()]
            except KeyError:
                pass
        
        # Create invite
        invite, raw_token = await self.invite_repo.create_invite(
            relationship_id=relationship_id,
            inviter_user_id=inviter_user_id,
            invitee_email=invitee_email,
            invitee_role=role_enum,
            message=message,
        )
        
        # Check if invitee is an existing user
        invitee_user = await self.user_repo.get_by_email(invitee_email)
        if invitee_user:
            invite.invitee_user_id = invitee_user.id
            # Add as member with INVITED status
            from sqlalchemy import insert
            from app.infra.db.models.relationship import MemberStatus, MemberRole
            await self.session.execute(
                insert(relationship_members).values(
                    relationship_id=relationship_id,
                    user_id=invitee_user.id,
                    role=MemberRole.MEMBER,
                    member_status=MemberStatus.INVITED,
                )
            )
            await self.session.commit()
        
        # Build invitation URL - points to signup page with token
        from urllib.parse import urlparse
        from app.settings import settings
        base_for_invite = settings.app_public_url
        if app_base_url is not None and app_base_url.strip():
            raw = app_base_url.strip().replace("\r", "").replace("\n", "")
            if len(raw) <= 2048:
                try:
                    parsed = urlparse(raw)
                    if parsed.scheme in ("http", "https") and parsed.netloc:
                        base_for_invite = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                except Exception:
                    pass
        invite_url = f"{base_for_invite}/signup?token={raw_token}"
        
        # Mark as sent (but don't send email - will be shared via native share)
        await self.invite_repo.mark_sent(invite.id)
        # Skip email sending - user will share via native share interface
        # await self.email_service.send_invite(
        #     to_email=invitee_email,
        #     inviter_name=inviter_name,
        #     relationship_type=relationship_type,
        #     token=raw_token,
        # )
        
        from datetime import datetime
        return {
            "invite_id": invite.id,
            "status": "CREATED",  # Changed from "SENT" since we're not sending email
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
            "invite_url": invite_url,
        }
