"""Relationship management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.models import User
from app.domain.admin.services import RelationshipService, RelationshipRepository, UserRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.db.repositories.user_repo import UserRepositoryImpl

router = APIRouter()


class CreateRelationshipRequest(BaseModel):
    """Create relationship request."""

    user2_id: str
    relationship_type: str


class RelationshipResponse(BaseModel):
    """Relationship response."""

    id: str
    user1_id: str
    user2_id: str
    relationship_type: str
    status: str


@router.post("", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    request: CreateRelationshipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new relationship."""
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    user_repo: UserRepository = UserRepositoryImpl(db)
    relationship_service = RelationshipService(relationship_repo, user_repo)

    try:
        relationship = await relationship_service.create_relationship(
            user1_id=current_user.id,
            user2_id=request.user2_id,
            relationship_type=request.relationship_type,
        )
        return RelationshipResponse(
            id=relationship.id,
            user1_id=relationship.user1_id,
            user2_id=relationship.user2_id,
            relationship_type=relationship.relationship_type,
            status=relationship.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[RelationshipResponse])
async def list_relationships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's relationships."""
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    user_repo: UserRepository = UserRepositoryImpl(db)
    relationship_service = RelationshipService(relationship_repo, user_repo)

    relationships = await relationship_service.list_user_relationships(current_user.id)
    return [
        RelationshipResponse(
            id=r.id,
            user1_id=r.user1_id,
            user2_id=r.user2_id,
            relationship_type=r.relationship_type,
            status=r.status,
        )
        for r in relationships
    ]


@router.get("/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get relationship by ID."""
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    user_repo: UserRepository = UserRepositoryImpl(db)
    relationship_service = RelationshipService(relationship_repo, user_repo)

    relationship = await relationship_service.get_relationship(relationship_id)
    if not relationship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")

    # Check access
    if relationship.user1_id != current_user.id and relationship.user2_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return RelationshipResponse(
        id=relationship.id,
        user1_id=relationship.user1_id,
        user2_id=relationship.user2_id,
        relationship_type=relationship.relationship_type,
        status=relationship.status,
    )
