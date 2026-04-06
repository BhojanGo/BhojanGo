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


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Soft-delete the current user's account."""
    repo = UserRepository(db)
    # Soft delete: deactivate rather than hard delete
    await repo.update(current_user.id, is_active=False)
    logger.info("user_account_deleted", user_id=str(current_user.id))
    return MessageResponse(message="Account deactivated successfully")


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
