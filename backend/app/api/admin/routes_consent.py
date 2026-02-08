"""Consent routes."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.consent.services import ConsentService
from app.infra.db.repositories.consent_repo import ConsentRepositoryImpl
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl

logger = logging.getLogger(__name__)

router = APIRouter()


class ConsentTemplate(BaseModel):
    """Consent template."""
    template_id: str
    title: str
    description: str
    scopes: list[str]


class UpdateConsentRequest(BaseModel):
    """Update consent request."""
    scopes: list[str]
    status: str = "ACTIVE"


class UpdateConsentResponse(BaseModel):
    """Update consent response."""
    ok: bool = True
    version: int


class ConsentMember(BaseModel):
    """Consent member."""
    user_id: str
    member_status: str
    consent_status: str
    scopes: list[str]


class ConsentInfoResponse(BaseModel):
    """Consent info response."""
    relationship_status: str
    members: list[ConsentMember]


@router.get("/{relationship_id}/consent/templates", response_model=list[ConsentTemplate])
async def get_consent_templates(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get consent templates for relationship."""
    consent_repo = ConsentRepositoryImpl(db)
    relationship_repo = RelationshipRepositoryImpl(db)
    
    service = ConsentService(
        consent_repo=consent_repo,
        relationship_repo=relationship_repo,
        session=db,
    )
    
    templates = await service.get_templates(relationship_id)
    return [ConsentTemplate(**t) for t in templates]


@router.put("/{relationship_id}/consent/me", response_model=UpdateConsentResponse)
async def update_my_consent(
    relationship_id: str,
    request: UpdateConsentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update consent for current user."""
    consent_repo = ConsentRepositoryImpl(db)
    relationship_repo = RelationshipRepositoryImpl(db)
    
    service = ConsentService(
        consent_repo=consent_repo,
        relationship_repo=relationship_repo,
        session=db,
    )
    
    result = await service.set_my_consent(
        relationship_id=relationship_id,
        user_id=current_user.id,
        scopes=request.scopes,
        status=request.status,
    )
    
    return UpdateConsentResponse(**result)


@router.get("/{relationship_id}/consent", response_model=ConsentInfoResponse)
async def get_consent(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get consent info for relationship."""
    consent_repo = ConsentRepositoryImpl(db)
    relationship_repo = RelationshipRepositoryImpl(db)
    
    service = ConsentService(
        consent_repo=consent_repo,
        relationship_repo=relationship_repo,
        session=db,
    )
    
    result = await service.get_consent_state(relationship_id)
    return ConsentInfoResponse(**result)
