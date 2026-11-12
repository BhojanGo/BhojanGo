import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.security import HTTPAuthorizationCredentials

from core_api.modules.identity.api.dependencies import (
    AdminContext,
    get_current_active_user,
    require_permission,
    security,
)
from core_api.modules.identity.service.auth import AuthService
from shared.db import get_db
from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.user import MessageResponse, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["Users"])
logger = structlog.get_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserResponse:
    """Get the current authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def patch_me(
    data: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> UserResponse:
    """Update the current user's profile (PATCH)."""
    return await update_me(data, current_user, db)


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
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

    if "phone" in update_data and update_data["phone"] != current_user.phone:
        update_data["is_phone_verified"] = False  # a new number must be verified by OTP

    updated = await repo.update(current_user.id, **update_data)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.model_validate(updated)


@router.delete("/me", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def delete_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Delete my account (GDPR / India DPDP / app store rules).

    Removes personal data (name, email, phone, social ids, addresses, admin
    roles), ends every session at once and deactivates the account. Orders
    keep the anonymous user id so restaurant and tax records stay intact.
    """
    await AuthService(db).delete_account(current_user, credentials.credentials)
    return MessageResponse(message="Account deleted and data anonymized successfully")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(require_permission("customers.view"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> UserResponse:
    """Admin: get any user in a country you cover."""
    user = await UserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    admin.require("customers.view", user.country, within=True)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}/anonymize", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def admin_anonymize_user(
    user_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(require_permission("customers.edit"))],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Admin: erase a user's personal data on request (right to erasure)."""
    user = await UserRepository(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    admin.require("customers.edit", user.country, within=True)
    await AuthService(db).delete_account(user)
    logger.info("admin_user_anonymized", user_id=str(user_id), by=str(admin.user.id))
    return MessageResponse(message="User data anonymized successfully")
