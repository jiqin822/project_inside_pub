"""Contact lookup routes."""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.admin.services import ContactService
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ContactLookupRequest(BaseModel):
    """Contact lookup request."""
    email: str


class UserInfo(BaseModel):
    """User info in contact lookup."""
    id: str
    display_name: str


class ContactLookupResponse(BaseModel):
    """Contact lookup response."""
    status: str  # EXISTS, NOT_FOUND, BLOCKED
    user: UserInfo | None = None


@router.post("/lookup", response_model=ContactLookupResponse)
async def lookup_contact(
    request: ContactLookupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lookup contact by email."""
    user_repo = UserRepositoryImpl(db)
    contact_service = ContactService(user_repo)
    
    blocked_domains = settings.email_blocked_domains_list
    result = await contact_service.lookup_contact(request.email, blocked_domains)
    
    if result["status"] == "EXISTS" and result.get("user"):
        return ContactLookupResponse(
            status=result["status"],
            user=UserInfo(**result["user"]),
        )
    
    return ContactLookupResponse(
        status=result["status"],
        user=None,
    )
