"""Consent domain services."""
from typing import List, Optional
from app.domain.common.errors import NotFoundError, AuthorizationError
from app.infra.db.repositories.consent_repo import ConsentRepositoryImpl
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.db.models.relationship import ConsentStatus, RelationshipStatus, MemberStatus
from sqlalchemy.ext.asyncio import AsyncSession


class ConsentService:
    """Consent service."""

    def __init__(
        self,
        consent_repo: ConsentRepositoryImpl,
        relationship_repo: RelationshipRepositoryImpl,
        session: AsyncSession,
    ):
        self.consent_repo = consent_repo
        self.relationship_repo = relationship_repo
        self.session = session

    async def get_templates(self, relationship_id: str) -> List[dict]:
        """Get consent templates for relationship type."""
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)
        
        # Map rel_type to relationship type
        rel_type = relationship.rel_type.lower()
        
        templates = []
        if rel_type in ["romantic", "couple"]:
            templates = [
                {
                    "template_id": "COUPLE_DEFAULT",
                    "title": "Default Couple Settings",
                    "description": "Real-time features, summaries, and mediation",
                    "scopes": [
                        "REALTIME_FEATURES_ONLY",
                        "SUMMARY_SHARED",
                        "MEDIATION_ALLOWED",
                    ],
                },
                {
                    "template_id": "PRIVATE_COUPLE",
                    "title": "Private Couple",
                    "description": "Real-time features only",
                    "scopes": ["REALTIME_FEATURES_ONLY"],
                },
                {
                    "template_id": "ENHANCED_COUPLE",
                    "title": "Enhanced Couple",
                    "description": "All features including transcript storage",
                    "scopes": [
                        "REALTIME_FEATURES_ONLY",
                        "SUMMARY_SHARED",
                        "TRANSCRIPT_STORED",
                        "MEDIATION_ALLOWED",
                    ],
                },
            ]
        elif rel_type == "family":
            templates = [
                {
                    "template_id": "FAMILY_DEFAULT",
                    "title": "Default Family Settings",
                    "description": "Real-time features and summaries",
                    "scopes": [
                        "REALTIME_FEATURES_ONLY",
                        "SUMMARY_SHARED",
                    ],
                },
            ]
        elif rel_type == "friend":
            templates = [
                {
                    "template_id": "FRIEND_DEFAULT",
                    "title": "Default Friend Settings",
                    "description": "Real-time features only",
                    "scopes": ["REALTIME_FEATURES_ONLY"],
                },
            ]
        else:
            templates = [
                {
                    "template_id": "DEFAULT",
                    "title": "Default Settings",
                    "description": "Real-time features only",
                    "scopes": ["REALTIME_FEATURES_ONLY"],
                },
            ]
        
        return templates

    async def set_my_consent(
        self,
        relationship_id: str,
        user_id: str,
        scopes: List[str],
        status: str = "ACTIVE",
    ) -> dict:
        """Set consent for current user."""
        # Verify user is a member
        is_member = await self.relationship_repo.is_member(relationship_id, user_id)
        if not is_member:
            raise AuthorizationError("User is not a member of this relationship")
        
        consent_status = ConsentStatus[status] if status in ConsentStatus.__members__ else ConsentStatus.ACTIVE
        
        consent = await self.consent_repo.create_or_update(
            relationship_id=relationship_id,
            user_id=user_id,
            scopes=scopes,
            status=consent_status,
        )
        
        # Try to activate relationship
        await self._try_activate_relationship(relationship_id)
        
        return {
            "ok": True,
            "version": int(consent.version) if consent.version.isdigit() else 1,
        }

    async def get_consent_state(self, relationship_id: str) -> dict:
        """Get consent state for relationship."""
        from sqlalchemy import select
        from app.infra.db.models.relationship import relationship_members, MemberStatus
        
        relationship = await self.relationship_repo.get_by_id(relationship_id)
        if not relationship:
            raise NotFoundError("Relationship", relationship_id)
        
        # Get members with status from DB
        members_result = await self.session.execute(
            select(relationship_members).where(
                relationship_members.c.relationship_id == relationship_id
            )
        )
        member_rows = members_result.all()
        
        consents = await self.consent_repo.get_all_for_relationship(relationship_id)
        consent_map = {c.user_id: c for c in consents}
        
        members_list = []
        for row in member_rows:
            consent = consent_map.get(row.user_id)
            member_status = row.member_status.value if hasattr(row.member_status, 'value') else str(row.member_status) if row.member_status else "INVITED"
            members_list.append({
                "user_id": row.user_id,
                "member_status": member_status,
                "consent_status": consent.status.value if consent and hasattr(consent.status, 'value') else (str(consent.status) if consent else "DRAFT"),
                "scopes": consent.scopes if consent else [],
            })
        
        status_value = relationship.status.value if hasattr(relationship.status, 'value') else str(relationship.status)
        return {
            "relationship_status": status_value.lower() if isinstance(status_value, str) else status_value,
            "members": members_list,
        }

    async def _try_activate_relationship(self, relationship_id: str) -> None:
        """Try to activate relationship if all members have consent."""
        from sqlalchemy import select, and_
        from app.infra.db.models.relationship import (
            RelationshipModel,
            relationship_members,
            MemberStatus,
            RelationshipStatus,
        )
        
        # Get relationship
        result = await self.session.execute(
            select(RelationshipModel).where(RelationshipModel.id == relationship_id)
        )
        relationship = result.scalar_one_or_none()
        if not relationship:
            return
        
        # Get all members
        members_result = await self.session.execute(
            select(relationship_members).where(
                relationship_members.c.relationship_id == relationship_id
            )
        )
        members = members_result.all()
        
        # Get all consents
        consents = await self.consent_repo.get_all_for_relationship(relationship_id)
        consent_user_ids = {c.user_id for c in consents if c.status == ConsentStatus.ACTIVE}
        
        # Check if all members are ACCEPTED and have ACTIVE consent
        all_accepted = all(
            m.member_status == MemberStatus.ACCEPTED.value
            for m in members
        )
        all_have_consent = all(
            m.user_id in consent_user_ids
            for m in members
        )
        
        if all_accepted and all_have_consent and len(members) > 1:
            # Update relationship status to ACTIVE
            from sqlalchemy import update
            await self.session.execute(
                update(RelationshipModel)
                .where(RelationshipModel.id == relationship_id)
                .values(status=RelationshipStatus.ACTIVE)
            )
            await self.session.commit()
        elif relationship.status == RelationshipStatus.ACTIVE and not (all_accepted and all_have_consent):
            # Downgrade to PENDING_ACCEPTANCE if requirements no longer met
            from sqlalchemy import update
            await self.session.execute(
                update(RelationshipModel)
                .where(RelationshipModel.id == relationship_id)
                .values(status=RelationshipStatus.PENDING_ACCEPTANCE)
            )
            await self.session.commit()
