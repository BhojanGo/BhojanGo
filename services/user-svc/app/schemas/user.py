import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Enums as Literals ─────────────────────────────────────────────────────────
UserRole = Literal["customer", "driver", "restaurant_owner", "admin", "super_admin"]
Country = Literal["US", "IN"]
Currency = Literal["USD", "INR"]
Locale = Literal["en-US", "en-IN", "hi-IN"]


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    phone: str | None = None
    country: Country
    preferred_currency: Currency = "USD"
    preferred_locale: Locale = "en-US"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        cleaned = re.sub(r"[\s\-\(\)]", "", v)
        if not re.match(r"^\+?[1-9]\d{7,14}$", cleaned):
            raise ValueError("Invalid phone number format. Must be E.164 format e.g. +14155552671")
        return cleaned


class RegisterRequest(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class OtpSendRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    country: Country


class OtpVerifyRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class SocialLoginRequest(BaseModel):
    provider: Literal["google", "apple"]
    token: str = Field(min_length=10)
    country: Country = "US"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = None
    avatar_url: str | None = None
    preferred_currency: Currency | None = None
    preferred_locale: Locale | None = None
    fcm_token: str | None = None


# ── Response Schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str
    phone: str | None
    full_name: str
    avatar_url: str | None
    role: str
    is_active: bool
    is_verified: bool
    is_phone_verified: bool
    loyalty_points: int
    preferred_currency: str
    preferred_locale: str
    country: str
    fcm_token: str | None
    created_at: datetime
    updated_at: datetime


class AuthTokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MessageResponse(BaseModel):
    message: str
    success: bool = True
