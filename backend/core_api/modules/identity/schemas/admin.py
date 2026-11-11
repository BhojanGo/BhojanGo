import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RoleAssignmentCreate(BaseModel):
    """Grant a role at a scope. Identify the admin by user_id or email."""

    user_id: uuid.UUID | None = None
    email: EmailStr | None = None
    role: str = Field(examples=["city_ops"])
    scope: str = Field(examples=["IN-TG-HYD"], description='"*" (global), "IN", "IN-TG" or "IN-TG-HYD"')


class RoleAssignmentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    scope: str
    granted_by: uuid.UUID | None
    created_at: datetime


class AdminMeResponse(BaseModel):
    user_id: uuid.UUID
    email: str | None
    full_name: str
    assignments: list[RoleAssignmentResponse]
    # permission -> widest scopes where it holds (["*"] = everywhere)
    permissions: dict[str, list[str]]
