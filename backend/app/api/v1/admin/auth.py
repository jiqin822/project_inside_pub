"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.entities import User
from app.domain.admin.services import UserService
from app.domain.admin.repositories import UserRepository
from app.infra.db.repositories import UserRepositoryImpl
from app.infra.security.jwt import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    """Registration request."""

    email: EmailStr
    password: str
    full_name: str | None = None


class RegisterResponse(BaseModel):
    """Registration response."""

    user_id: str
    email: str
    access_token: str
    refresh_token: str


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User response."""

    id: str
    email: str
    full_name: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        """Create from user entity."""
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
        )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    user_repo: UserRepository = UserRepositoryImpl(db)
    user_service = UserService(user_repo)

    # Check if user exists
    existing = await user_service.get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user
    hashed_password = get_password_hash(request.password)
    user = await user_service.create_user(
        email=request.email, password=hashed_password, full_name=request.full_name
    )

    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)
):
    """Login and get access token."""
    user_repo: UserRepository = UserRepositoryImpl(db)
    user_service = UserService(user_repo)

    user = await user_service.get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    return LoginResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse.from_entity(current_user)
