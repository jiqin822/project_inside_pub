"""Relationship routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.admin.services import (
    RelationshipService,
    RelationshipRepository,
)
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl

logger = logging.getLogger(__name__)

router = APIRouter()


# Public invite validation - must be declared before /{relationship_id}/... so path /invites/validate is not matched as relationship_id="invites"
@router.get("/invites/validate", response_model=dict)
async def validate_invite_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Validate an invite token and return invite info (public endpoint)."""
    from app.infra.db.repositories.invite_repo import InviteRepository
    from app.infra.db.models.relationship import RelationshipModel
    from app.infra.db.models.user import UserModel
    from sqlalchemy import select

    invite_repo = InviteRepository(db)
    invite = await invite_repo.get_invite_by_token(token)

    if not invite:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired invitation token"
        )

    # Get relationship info
    relationship_result = await db.execute(
        select(RelationshipModel).where(RelationshipModel.id == invite.relationship_id)
    )
    relationship = relationship_result.scalar_one_or_none()

    # Get inviter info
    inviter_result = await db.execute(
        select(UserModel).where(UserModel.id == invite.inviter_user_id)
    )
    inviter = inviter_result.scalar_one_or_none()

    # Map relationship type to frontend-friendly format
    relationship_type = "Partner"  # Default
    if relationship:
        type_value = relationship.type.value if hasattr(relationship.type, 'value') else str(relationship.type)
        type_map = {
            'COUPLE': 'Partner',
            'DATE': 'Date',
            'FAMILY': 'Family',
            'FRIEND_1_1': 'Friend',
            'FRIEND_GROUP': 'Friend',
            'OTHER': 'Other',
        }
        relationship_type = type_map.get(type_value, 'Partner')

    return {
        "email": invite.invitee_email,
        "valid": True,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "relationship_type": relationship_type,
        "inviter_name": inviter.display_name if inviter and inviter.display_name else (inviter.email if inviter else "Someone"),
    }


class CreateRelationshipRequest(BaseModel):
    """Create relationship request model."""
    type: str
    member_ids: list[str]


class RelationshipResponse(BaseModel):
    """Relationship response model."""
    id: str
    type: str
    status: str


class CreateInviteRequest(BaseModel):
    """Create invite request."""
    email: str
    role: str | None = None
    message: str | None = None


class CreateInviteResponse(BaseModel):
    """Create invite response."""
    invite_id: str
    status: str
    expires_at: str
    invite_url: str | None = None  # Invitation link for sharing


class InviteInfo(BaseModel):
    """Invite info."""
    invite_id: str
    email: str
    role: str | None = None
    status: str
    expires_at: str
    created_at: str
    inviter_user_id: str | None = None  # ID of the user who sent the invite




@router.post("", response_model=RelationshipResponse)
async def create_relationship(
    request: CreateRelationshipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new relationship."""
    logger.info(f"🔵 [SERVER] Create relationship request: type={request.type}, member_ids={request.member_ids}, creator_id={current_user.id}")
    
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    from app.domain.admin.services import UserRepository
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    user_repo: UserRepository = UserRepositoryImpl(db)
    relationship_service = RelationshipService(relationship_repo, user_repo)

    relationship = await relationship_service.create_relationship(
        rel_type=request.type,  # Map type to rel_type for service
        member_ids=request.member_ids,
        creator_id=current_user.id,
        session=db,
    )

    logger.info(f"✅ [SERVER] Relationship created: id={relationship.id}, type={relationship.rel_type}, status={relationship.status}")
    
    response = RelationshipResponse(
        id=relationship.id,
        type=relationship.rel_type,  # Return as type
        status=relationship.status,
    )
    
    logger.debug(f"   [SERVER] Response data: id={response.id}, type={response.type}, status={response.status}")
    
    return response


@router.get("", response_model=list[RelationshipResponse])
async def list_relationships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List relationships for current user."""
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    relationships = await relationship_repo.list_by_user(current_user.id)
    
    logger.info(f"🔵 [SERVER] Listing relationships for user {current_user.id} (email: {current_user.email})")
    logger.info(f"   Found {len(relationships)} relationships")
    for r in relationships:
        logger.info(f"   - Relationship {r.id}: type={r.rel_type}, status={r.status}")

    return [
        RelationshipResponse(
            id=r.id,
            type=r.rel_type,  # Map rel_type to type
            status=r.status,
        )
        for r in relationships
    ]


@router.post("/{relationship_id}/invites", response_model=CreateInviteResponse)
async def create_invite(
    http_request: Request,
    relationship_id: str,
    request: CreateInviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an invite for a relationship."""
    from app.domain.admin.services import InviteService
    from app.infra.db.repositories.invite_repo import InviteRepository
    from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    from app.infra.messaging.email_base import get_email_service
    from app.domain.admin.services import UserRepository, RelationshipRepository
    
    app_base_url = http_request.headers.get("X-App-Base-URL")
    
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    user_repo: UserRepository = UserRepositoryImpl(db)
    invite_repo = InviteRepository(db)
    email_service = get_email_service()
    
    invite_service = InviteService(
        invite_repo=invite_repo,
        relationship_repo=relationship_repo,
        user_repo=user_repo,
        email_service=email_service,
        session=db,
    )
    
    result = await invite_service.create_invite(
        relationship_id=relationship_id,
        inviter_user_id=current_user.id,
        invitee_email=request.email,
        invitee_role=request.role,
        message=request.message,
        app_base_url=app_base_url,
    )
    
    return CreateInviteResponse(**result)


class InviteLinkResponse(BaseModel):
    """Invite link response (regenerates token and returns URL)."""
    invite_url: str


@router.get("/{relationship_id}/invites/{invite_id}/link", response_model=InviteLinkResponse)
async def get_invite_link(
    relationship_id: str,
    invite_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a fresh invite link for a pending invite (regenerates token). Caller must be a member of the relationship."""
    from app.infra.db.repositories.invite_repo import InviteRepository
    from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
    from app.domain.admin.services import RelationshipRepository
    from app.settings import settings

    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    is_member = await relationship_repo.is_member(relationship_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this relationship",
        )
    invite_repo = InviteRepository(db)
    invite = await invite_repo.get_invite(invite_id)
    if not invite or invite.relationship_id != relationship_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    try:
        _, raw_token = await invite_repo.regenerate_token(invite_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    base_for_invite = settings.app_public_url
    invite_url = f"{base_for_invite.rstrip('/')}/signup?token={raw_token}"
    return InviteLinkResponse(invite_url=invite_url)


@router.get("/{relationship_id}/invites", response_model=list[InviteInfo])
async def get_invites(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get invites for a relationship."""
    from app.infra.db.repositories.invite_repo import InviteRepository
    from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
    from app.domain.admin.services import RelationshipRepository
    
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    
    # Verify user is a member
    is_member = await relationship_repo.is_member(relationship_id, current_user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this relationship",
        )
    
    invite_repo = InviteRepository(db)
    invites = await invite_repo.get_invites_by_relationship(relationship_id)
    
    return [
        InviteInfo(
            invite_id=invite.id,
            email=invite.invitee_email,
            role=invite.invitee_role.value if invite.invitee_role else None,
            status=invite.status.value,
            expires_at=invite.expires_at.isoformat() if invite.expires_at else "",
            created_at=invite.created_at.isoformat() if invite.created_at else "",
            inviter_user_id=invite.inviter_user_id,
        )
        for invite in invites
    ]


@router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a relationship."""
    logger.info(f"🔵 [SERVER] Delete relationship request: relationship_id={relationship_id}, user_id={current_user.id}")
    
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    
    # Get user repo for service
    from app.domain.admin.services import UserRepository
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    user_repo: UserRepository = UserRepositoryImpl(db)
    relationship_service = RelationshipService(relationship_repo, user_repo)

    try:
        await relationship_service.delete_relationship(
            relationship_id=relationship_id,
            user_id=current_user.id,
        )
        logger.info(f"✅ [SERVER] Relationship deleted: id={relationship_id}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ [SERVER] Failed to delete relationship: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


