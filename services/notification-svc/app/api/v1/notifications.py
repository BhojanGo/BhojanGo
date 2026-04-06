import math
import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.db.base import get_db
from app.models.notification import DeviceToken, Notification
from app.schemas.notification import (
    DeviceTokenRequest,
    NotificationListResponse,
    NotificationResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = structlog.get_logger(__name__)


@router.post("/device-token", status_code=status.HTTP_201_CREATED)
async def register_device_token(
    data: DeviceTokenRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Register or update a device's FCM token."""
    # Upsert: if token exists, update user_id; otherwise create
    result = await db.execute(select(DeviceToken).where(DeviceToken.token == data.token))
    existing = result.scalar_one_or_none()

    if existing:
        await db.execute(
            update(DeviceToken).where(DeviceToken.token == data.token).values(user_id=current_user.id, platform=data.platform)
        )
    else:
        db.add(DeviceToken(user_id=current_user.id, token=data.token, platform=data.platform))
        await db.flush()

    return {"message": "Device token registered", "platform": data.platform}


@router.delete("/device-token")
async def remove_device_token(
    data: DeviceTokenRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Remove a device token (on logout / app uninstall)."""
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.token == data.token, DeviceToken.user_id == current_user.id)
    )
    token_obj = result.scalar_one_or_none()
    if token_obj:
        await db.delete(token_obj)
    return {"message": "Device token removed"}


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
) -> NotificationListResponse:
    """Get user's notification inbox."""
    from sqlalchemy import and_, func

    where_clause = Notification.user_id == current_user.id
    if unread_only:
        where_clause = and_(where_clause, Notification.is_read == False)  # noqa: E712

    total = (await db.execute(select(func.count(Notification.id)).where(where_clause))).scalar_one()
    result = await db.execute(
        select(Notification).where(where_clause).order_by(Notification.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    notifications = result.scalars().all()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
        unread_count=(await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == current_user.id, Notification.is_read == False  # noqa: E712
            )
        )).scalar_one(),
    )


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    await db.execute(
        update(Notification).where(Notification.id == notification_id).values(is_read=True, read_at=datetime.now(UTC))
    )
    return {"message": "Marked as read"}
