import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field


# ── Enums as Literals ─────────────────────────────────────────────────────────
UserRole = Literal["customer", "driver", "restaurant_owner", "admin", "super_admin"]
# Countries and currencies are rows in Markets (the countries table), not a list
# here: the shape is checked by these patterns, and whether we operate there by
# markets.service.countries (sign-up: exists and isn't draft; phone: its code).
Country = Annotated[str, Field(pattern=r"^[A-Z]{2}$", examples=["IN"])]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$", examples=["INR"])]
# The web's languages; every backend message is written in each of them
# (shared/texts.py LANGUAGES, language_for; tools/i18n/check_locales.py).
Locale = Literal["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN", "en-US", "es-US"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class OtpSendRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    country: Country
    # The app's language ("hi"): the code's SMS is written in it when the country offers it.
    language: str | None = Field(default=None, pattern=r"^[a-z]{2}$", examples=["hi"])


class OtpVerifyRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    """Reset a forgotten password by proving phone ownership via OTP."""

    phone: str = Field(pattern=r"^\+?[1-9]\d{7,14}$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    # The rules (10+ characters, not breached) are checked by service/passwords.py,
    # which answers with a code the apps translate.
    new_password: str = Field(min_length=1, max_length=256)


class PhoneSignInRequest(BaseModel):
    """Sign in (or sign up) with the code from /auth/send-otp."""

    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    country: Country
    full_name: str | None = Field(default=None, min_length=2, max_length=255)


class SocialLoginRequest(BaseModel):
    provider: Literal["google", "apple"]
    token: str = Field(min_length=10)
    country: Country = "US"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserUpdateRequest(BaseModel):
    """Name and preferences. Phone and email change through /me/phone and /me/email (verified by a code)."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    avatar_url: str | None = None
    preferred_currency: Currency | None = None
    preferred_locale: Locale | None = None
    fcm_token: str | None = None


# ── Response Schemas ──────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    email: str | None
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
    is_new_user: bool = False
    # Always false here; a sign-in that needs the second step answers MfaChallengeResponse instead.
    mfa_required: bool = False
    # Admin role assignments, "role@scope" (empty for customers, riders, partners)
    admin_roles: list[str] = []


class MessageResponse(BaseModel):
    message: str
    success: bool = True


# ── email + password sign-in, two-step sign-in, account security (Round 8, D5) ─
Language = Annotated[str, Field(pattern=r"^[a-z]{2}$", examples=["hi"])]
Code6 = Annotated[str, Field(pattern=r"^\d{6}$", examples=["123456"])]
# New passwords: the rules are checked by service/passwords.py (PasswordRejected codes).
NewPassword = Annotated[str, Field(min_length=1, max_length=256)]


class EmailSignUpRequest(BaseModel):
    """Create an account: a 6-digit code goes to the email; the account exists once it's entered."""

    email: EmailStr
    password: NewPassword
    country: Country
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    language: Language | None = None


class EmailCodeRequest(BaseModel):
    email: EmailStr
    language: Language | None = None


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: Code6


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    language: Language | None = None


class ResetTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetTokenStatus(BaseModel):
    valid: bool


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: NewPassword


class MfaChallengeResponse(BaseModel):
    """The password (or code) was right; an admin account needs its second step.
    Send ``mfa_token`` with a code from the authenticator app to /auth/mfa/verify
    (or a recovery code to /auth/mfa/recovery). ``enrolment_required``: no
    authenticator yet: a code went to the account's email; start at /auth/mfa/enrol/start."""

    mfa_required: Literal[True] = True
    mfa_token: str
    enrolment_required: bool
    email_code_sent: bool = False
    expires_in: int


class MfaCodeRequest(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=200)
    code: Code6


class MfaRecoveryRequest(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=200)
    recovery_code: str = Field(min_length=8, max_length=24)


class MfaEnrolStartRequest(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=200)
    email_code: Code6


class MfaEnrolStartResponse(BaseModel):
    """Add this to an authenticator app (scan the QR code or type the key)."""

    account: str
    secret: str
    otpauth_uri: str
    qr_svg: str  # data:image/svg+xml;base64,...


class MfaEnrolledResponse(AuthTokensResponse):
    """Signed in. Show the recovery codes once: they are not shown again."""

    recovery_codes: list[str]


class RecoveryCodesRenewRequest(BaseModel):
    code: Code6


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class ChangePasswordRequest(BaseModel):
    """Required when the account has a password; leave out to set a first one."""

    current_password: str | None = Field(default=None, max_length=256)
    new_password: NewPassword


class LinkEmailStart(BaseModel):
    email: EmailStr
    language: Language | None = None


class LinkEmailVerify(BaseModel):
    email: EmailStr
    code: Code6


class LinkPhoneStart(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    country: Country
    language: Language | None = None


class LinkPhoneVerify(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    code: Code6


class SecurityOverview(BaseModel):
    """How this account signs in (Profile > Sign-in and security)."""

    email: str | None
    email_verified: bool
    phone: str | None
    phone_verified: bool
    has_password: bool
    password_changed_at: datetime | None
    google_linked: bool
    apple_linked: bool
    mfa_enabled: bool
    mfa_required: bool  # admins must use two-step sign-in
    recovery_codes_left: int
