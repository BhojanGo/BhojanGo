import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_admin
from app.db.base import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import MessageResponse, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])
logger = structlog.get_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update the current user's profile."""
    repo = UserRepository(db)

    update_data = data.model_dump(exclude_none=True)
    if not update_data:
        return UserResponse.model_validate(current_user)

    # Phone uniqueness check
    if "phone" in update_data:
        existing = await repo.get_by_phone(update_data["phone"])
        if existing and existing.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PHONE_ALREADY_EXISTS", "message": "Phone number is already in use"},
            )

    updated = await repo.update(current_user.id, **update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(updated)


@router.delete("/me", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Delete (anonymize) the current user's account per GDPR/PDPA.

    Anonymizes PII, revokes all tokens, and deactivates the account.
    Data retention: anonymized record kept for order history integrity.
    SLA: immediate anonymization (within GDPR 30-day requirement).
    """
    from datetime import UTC, datetime
    from app.core.redis import get_redis, refresh_token_key

    repo = UserRepository(db)
    user_id = str(current_user.id)

    # Anonymize PII
    await repo.update(
        current_user.id,
        email=f"deleted_{user_id}@deleted.bhojango.com",
        phone=None,
        full_name="Deleted User",
        avatar_url=None,
        google_id=None,
        apple_id=None,
        fcm_token=None,
        is_active=False,
        is_verified=False,
        is_phone_verified=False,
    )

    # Revoke all refresh tokens
    try:
        redis = await get_redis()
        pattern = refresh_token_key(user_id, "*")
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass  # Best effort — account is already deactivated

    logger.info("user_account_anonymized", user_id=user_id)
    return MessageResponse(message="Account deleted and data anonymized successfully")


@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_admin)])
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Admin: Get any user by ID."""
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete(
    "/{user_id}/anonymize",
    response_model=MessageResponse,
    dependencies=[Depends(require_admin)],
    status_code=status.HTTP_200_OK,
)
async def admin_anonymize_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Admin: Anonymize a user's data per GDPR right-to-erasure request."""
    from datetime import UTC, datetime
    from app.core.redis import get_redis, refresh_token_key

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    uid = str(user_id)
    await repo.update(
        user_id,
        email=f"deleted_{uid}@deleted.bhojango.com",
        phone=None,
        full_name="Deleted User",
        avatar_url=None,
        google_id=None,
        apple_id=None,
        fcm_token=None,
        is_active=False,
        is_verified=False,
        is_phone_verified=False,
    )

    try:
        redis = await get_redis()
        pattern = refresh_token_key(uid, "*")
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass

    logger.info("admin_user_anonymized", user_id=uid)
    return MessageResponse(message="User data anonymized successfully")
