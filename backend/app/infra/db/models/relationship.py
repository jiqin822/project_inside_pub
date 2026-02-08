"""Relationship database models."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum

from app.infra.db.base import Base
from app.domain.admin.models import (
    Relationship as RelationshipEntity,
    RelationshipMember as RelationshipMemberEntity,
    Consent as ConsentEntity,
)


class RelationshipType(str, enum.Enum):
    """Relationship type enum."""
    COUPLE = "COUPLE"
    DATE = "DATE"
    FAMILY = "FAMILY"
    FRIEND_1_1 = "FRIEND_1_1"
    FRIEND_GROUP = "FRIEND_GROUP"
    OTHER = "OTHER"


class RelationshipStatus(str, enum.Enum):
    """Relationship status enum."""
    DRAFT = "DRAFT"
    PENDING_ACCEPTANCE = "PENDING_ACCEPTANCE"
    ACTIVE = "ACTIVE"
    DECLINED = "DECLINED"
    REVOKED = "REVOKED"


class MemberRole(str, enum.Enum):
    """Member role enum."""
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class MemberStatus(str, enum.Enum):
    """Member status enum."""
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    REMOVED = "REMOVED"


class ConsentStatus(str, enum.Enum):
    """Consent status enum."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


# Association table for many-to-many relationship
relationship_members = Table(
    "relationship_members",
    Base.metadata,
    Column("relationship_id", String, ForeignKey("relationships.id"), primary_key=True),
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("role", SQLEnum(MemberRole), nullable=True),
    Column("member_status", SQLEnum(MemberStatus), nullable=False, default=MemberStatus.INVITED),
    Column("added_at", DateTime, default=datetime.utcnow, nullable=False),
    Column("responded_at", DateTime, nullable=True),
)


class RelationshipModel(Base):
    """Relationship database model."""

    __tablename__ = "relationships"

    id = Column(String, primary_key=True)
    type = Column(SQLEnum(RelationshipType), nullable=False)
    status = Column(SQLEnum(RelationshipStatus), nullable=False, default=RelationshipStatus.DRAFT)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Keep rel_type for backward compatibility (computed property)
    @property
    def rel_type(self) -> str:
        """Backward compatibility property."""
        if self.type:
            type_value = self.type.value if hasattr(self.type, 'value') else str(self.type)
            # Map enum values to lowercase strings
            type_map = {
                'COUPLE': 'romantic',
                'DATE': 'date',
                'FAMILY': 'family',
                'FRIEND_1_1': 'friend',
                'FRIEND_GROUP': 'friend',
                'OTHER': 'other',
            }
            return type_map.get(type_value, type_value.lower())
        return "other"

    def to_entity(self) -> RelationshipEntity:
        """Convert to domain entity."""
        # Map type enum to rel_type string for backward compatibility
        rel_type_str = self.rel_type  # Use property
        status_str = self.status.value.lower() if isinstance(self.status, RelationshipStatus) else str(self.status)
        return RelationshipEntity(
            id=self.id,
            rel_type=rel_type_str,
            status=status_str,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: RelationshipEntity) -> "RelationshipModel":
        """Create from domain entity."""
        # Map rel_type string to type enum
        rel_type_str = entity.rel_type.lower() if entity.rel_type else "other"
        if rel_type_str in ["romantic", "couple"]:
            rel_type_enum = RelationshipType.COUPLE
        elif rel_type_str in ["date"]:
            rel_type_enum = RelationshipType.DATE
        elif rel_type_str in ["family"]:
            rel_type_enum = RelationshipType.FAMILY
        elif rel_type_str in ["friend"]:
            rel_type_enum = RelationshipType.FRIEND_1_1
        else:
            rel_type_enum = RelationshipType.OTHER
        
        status_str = entity.status.upper() if entity.status else "DRAFT"
        try:
            status_enum = RelationshipStatus[status_str]
        except KeyError:
            status_enum = RelationshipStatus.DRAFT
        
        return cls(
            id=entity.id,
            type=rel_type_enum,
            status=status_enum,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class ConsentModel(Base):
    """Consent database model."""

    __tablename__ = "relationship_consents"

    relationship_id = Column(String, ForeignKey("relationships.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    scopes = Column(JSONB, nullable=False)  # Array of strings
    version = Column(String, nullable=False, default="1")
    status = Column(SQLEnum(ConsentStatus), nullable=False, default=ConsentStatus.DRAFT)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_entity(self) -> ConsentEntity:
        """Convert to domain entity."""
        # scopes is already JSONB (list), no need to parse
        scopes_list = self.scopes if isinstance(self.scopes, list) else []
        return ConsentEntity(
            relationship_id=self.relationship_id,
            user_id=self.user_id,
            scopes=scopes_list,
            created_at=self.updated_at,  # Use updated_at as created_at fallback
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: ConsentEntity) -> "ConsentModel":
        """Create from domain entity."""
        return cls(
            relationship_id=entity.relationship_id,
            user_id=entity.user_id,
            scopes=entity.scopes,  # JSONB stores list directly
            version="1",
            status=ConsentStatus.ACTIVE,
            updated_at=entity.updated_at,
        )
