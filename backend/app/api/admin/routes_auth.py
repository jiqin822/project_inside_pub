"""Authentication routes."""
import logging
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.domain.admin.models import User
from app.domain.admin.services import UserService, UserRepository
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.infra.security.password import verify_password, get_password_hash
from app.infra.security.jwt import create_access_token, create_refresh_token, decode_token
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/signup")
async def signup_page_redirect(token: Optional[str] = None):
    """Redirect GET /auth/signup?token=... to the app's signup page. Invite links use the app URL (/signup?token=...);
    if a request hits the API (e.g. GET /v1/auth/signup?token=...), redirect to the frontend so the SPA can load."""
    base = (settings.app_public_url or "").rstrip("/") or "http://localhost:3000"
    url = f"{base}/signup"
    if token:
        url += f"?token={quote(token)}"
    return RedirectResponse(url=url, status_code=302)


class SignupRequest(BaseModel):
    """Signup request model."""
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    invite_token: Optional[str] = None  # Optional invite token for automatic relationship creation


class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str


@router.post("/signup", response_model=TokenResponse)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sign up a new user."""
    logger.info(f"🔵 [SERVER] Signup request received for email: {request.email}, display_name: {request.display_name}")
    
    user_repo: UserRepository = UserRepositoryImpl(db)
    user_service = UserService(user_repo)

    # Check if user exists
    existing = await user_service.get_user_by_email(request.email)
    if existing:
        logger.warning(f"❌ [SERVER] Signup failed: Email already registered: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    password_hash = get_password_hash(request.password)
    user = await user_service.create_user(
        email=request.email,
        password_hash=password_hash,
        display_name=request.display_name,
    )

    # Handle invite token if provided
    if request.invite_token:
        try:
            from app.infra.db.repositories.invite_repo import InviteRepository
            from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
            from app.domain.admin.services import RelationshipRepository
            
            invite_repo = InviteRepository(db)
            relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
            
            # Validate invite token
            invite = await invite_repo.get_invite_by_token(request.invite_token)
            if not invite:
                logger.warning(f"⚠️ [SERVER] Invalid or expired invite token for signup: {request.email}")
            elif invite.invitee_email.lower() != request.email.lower():
                logger.warning(f"⚠️ [SERVER] Invite email mismatch: invite expects {invite.invitee_email}, got {request.email}")
            else:
                # Add user to relationship
                from sqlalchemy import insert
                from app.infra.db.models.relationship import relationship_members, MemberStatus, MemberRole
                
                # Check if user is already a member
                is_member = await relationship_repo.is_member(invite.relationship_id, user.id)
                if not is_member:
                    await db.execute(
                        insert(relationship_members).values(
                            relationship_id=invite.relationship_id,
                            user_id=user.id,
                            role=MemberRole.MEMBER,
                            member_status=MemberStatus.ACCEPTED,
                        )
                    )
                    await db.commit()
                    logger.info(f"✅ [SERVER] Added user {user.id} to relationship {invite.relationship_id} via invite")
                
                # Mark invite as accepted
                await invite_repo.mark_accepted(invite.id, user.id)
                logger.info(f"✅ [SERVER] Marked invite {invite.id} as accepted")
        except Exception as e:
            logger.error(f"❌ [SERVER] Error processing invite token during signup: {str(e)}")
            # Don't fail signup if invite processing fails

    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    logger.info(f"✅ [SERVER] Signup successful for user: {user.id} (email: {request.email})")
    logger.debug(f"   [SERVER] Generated tokens (access_token length: {len(access_token)}, refresh_token length: {len(refresh_token)})")

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login user."""
    logger.info(f"🔵 [SERVER] Login request received for email: {request.email}")
    
    user_repo: UserRepository = UserRepositoryImpl(db)
    user_service = UserService(user_repo)

    user = await user_service.get_user_by_email(request.email)
    if not user:
        logger.warning(f"❌ [SERVER] Login failed: User not found for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    password_valid = verify_password(request.password, user.password_hash)
    if not password_valid:
        logger.warning(f"❌ [SERVER] Login failed: Invalid password for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        logger.warning(f"❌ [SERVER] Login failed: Inactive account for email: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    logger.info(f"✅ [SERVER] Login successful for user: {user.id} (email: {request.email})")
    logger.debug(f"   [SERVER] Generated tokens (access_token length: {len(access_token)}, refresh_token length: {len(refresh_token)})")

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """Refresh access token."""
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Generate new tokens
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)
