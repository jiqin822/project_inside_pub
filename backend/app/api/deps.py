"""API dependencies."""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.session import get_db
from app.infra.security.jwt import decode_token
from app.domain.admin.models import User
from app.domain.admin.services import UserRepository
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.settings import settings
from app.services.llm_service import LLMService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def get_llm_service() -> LLMService:
    """Build LLM service from settings (provider selection for sticker generation)."""
    return LLMService(
        openai_api_key=settings.openai_api_key or None,
        gemini_api_key=settings.gemini_api_key or None,
        default_text_model=settings.llm_default_text_model or None,
        backup_text_model=settings.llm_backup_text_model or None,
        default_image_model=settings.llm_default_image_model or None,
        default_image_size=settings.llm_default_image_size or None,
        default_image_quality=settings.llm_default_image_quality or None,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    token_type: str = payload.get("type")
    if user_id is None or token_type != "access":
        raise credentials_exception

    user_repo: UserRepository = UserRepositoryImpl(db)
    user = await user_repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user
