"""Consent management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.entities import User
from app.domain.admin.services import ConsentService
from app.domain.admin.repositories import ConsentRepository, RelationshipRepository
from app.infra.db.repositories import (
    ConsentRepositoryImpl,
    RelationshipRepositoryImpl,
)

router = APIRouter()


class GrantConsentRequest(BaseModel):
    """Grant consent request."""

    relationship_id: str
    consent_type: str


class ConsentResponse(BaseModel):
    """Consent response."""

    id: str
    user_id: str
    relationship_id: str
    consent_type: str
    granted: bool


@router.post("", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def grant_consent(
    request: GrantConsentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant consent."""
    consent_repo: ConsentRepository = ConsentRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    consent_service = ConsentService(consent_repo, relationship_repo)

    try:
        consent = await consent_service.grant_consent(
            user_id=current_user.id,
            relationship_id=request.relationship_id,
            consent_type=request.consent_type,
        )
        return ConsentResponse(
            id=consent.id,
            user_id=consent.user_id,
            relationship_id=consent.relationship_id,
            consent_type=consent.consent_type,
            granted=consent.granted,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{consent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_consent(
    consent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke consent."""
    consent_repo: ConsentRepository = ConsentRepositoryImpl(db)
    relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
    consent_service = ConsentService(consent_repo, relationship_repo)

    try:
        await consent_service.revoke_consent(consent_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
