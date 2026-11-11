import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeviceTokenRequest(BaseModel):
    token: str = Field(min_length=10)
    platform: Literal["ios", "android", "web"]


class NotificationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    channel: str
    title: str
    body: str
    data: dict[str, Any] | None
    is_read: bool
    sent_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    unread_count: int
