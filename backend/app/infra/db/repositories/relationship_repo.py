"""Relationship repository implementation."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload

from app.domain.admin.models import Relationship, RelationshipMember
from app.domain.admin.services import RelationshipRepository
from app.infra.db.models.relationship import RelationshipModel, relationship_members
from app.infra.db.models.user import UserModel


class RelationshipRepositoryImpl(RelationshipRepository):
    """Relationship repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, relationship: Relationship) -> Relationship:
        """Create a new relationship."""
        model = RelationshipModel.from_entity(relationship)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def get_by_id(self, relationship_id: str) -> Optional[Relationship]:
        """Get relationship by ID."""
        result = await self.session.execute(
            select(RelationshipModel).where(RelationshipModel.id == relationship_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def list_by_user(self, user_id: str) -> list[Relationship]:
        """List relationships for a user."""
        result = await self.session.execute(
            select(RelationshipModel)
            .join(relationship_members)
            .where(relationship_members.c.user_id == user_id)
        )
        models = result.scalars().all()
        return [m.to_entity() for m in models]

    async def add_member(
        self,
        member: RelationshipMember,
        member_status: str = "INVITED",
        role: str = "MEMBER",
    ) -> RelationshipMember:
        """Add a member to a relationship."""
        from app.infra.db.models.relationship import MemberStatus, MemberRole
        from datetime import datetime
        
        # Map string to enum
        status_enum = MemberStatus[member_status] if member_status in MemberStatus.__members__ else MemberStatus.INVITED
        role_enum = MemberRole[role] if role in MemberRole.__members__ else MemberRole.MEMBER
        
        stmt = relationship_members.insert().values(
            relationship_id=member.relationship_id,
            user_id=member.user_id,
            role=role_enum,
            member_status=status_enum,
            added_at=datetime.utcnow(),
        )
        await self.session.execute(stmt)
        await self.session.commit()
        return member

    async def get_members(self, relationship_id: str) -> list[RelationshipMember]:
        """Get all members of a relationship."""
        result = await self.session.execute(
            select(relationship_members).where(
                relationship_members.c.relationship_id == relationship_id
            )
        )
        rows = result.all()
        return [
            RelationshipMember(
                relationship_id=row.relationship_id,
                user_id=row.user_id,
                role=row.role.value if hasattr(row.role, 'value') else str(row.role) if row.role else None,
            )
            for row in rows
        ]

    async def is_member(self, relationship_id: str, user_id: str) -> bool:
        """Check if user is a member of relationship."""
        result = await self.session.execute(
            select(relationship_members).where(
                and_(
                    relationship_members.c.relationship_id == relationship_id,
                    relationship_members.c.user_id == user_id,
                )
            )
        )
        return result.first() is not None

    async def delete(self, relationship_id: str) -> None:
        """Delete a relationship and its members."""
        from app.infra.db.models.invite import RelationshipInviteModel
        from app.infra.db.models.relationship import ConsentModel
        from app.infra.db.models.session import SessionModel
        from app.infra.db.models.events import PokeEventModel
        
        # Delete related records first (foreign key constraints)
        # Order matters: delete child records before parent
        
        # 1. Delete poke events
        await self.session.execute(
            delete(PokeEventModel).where(
                PokeEventModel.relationship_id == relationship_id
            )
        )
        
        # 2. Delete invites
        await self.session.execute(
            delete(RelationshipInviteModel).where(
                RelationshipInviteModel.relationship_id == relationship_id
            )
        )
        
        # 3. Delete consent records
        await self.session.execute(
            delete(ConsentModel).where(
                ConsentModel.relationship_id == relationship_id
            )
        )
        
        # 4. Delete sessions (if any exist)
        await self.session.execute(
            delete(SessionModel).where(
                SessionModel.relationship_id == relationship_id
            )
        )
        
        # 5. Delete relationship members
        await self.session.execute(
            delete(relationship_members).where(
                relationship_members.c.relationship_id == relationship_id
            )
        )
        
        # 6. Delete the relationship
        await self.session.execute(
            delete(RelationshipModel).where(RelationshipModel.id == relationship_id)
        )
        await self.session.commit()
