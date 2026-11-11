"""Sign-in, tokens and account deletion.

Tokens (P5): RS256 access tokens for 15 minutes and rotating refresh tokens.
Every sign-in starts a refresh-token *family*; each refresh returns a new
token in that family and retires the old one. Presenting a retired token
means it leaked, so the whole family is revoked (the thief and the user both
have to sign in again).

Redis keys (service/redis_keys.py):
  refresh_family:{user}:{family} -> current jti   (TTL = refresh lifetime)
  refresh_families:{user}        -> set of family ids (for sign-out everywhere)
"""
import html
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.admin_role import AdminRoleRepository
from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    LoginRequest,
    OtpSendRequest,
    OtpVerifyRequest,
    PhoneSignInRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
    UserResponse,
)
from core_api.modules.identity.service import oidc
from core_api.modules.identity.service.otp import send_otp, verify_otp
from core_api.modules.identity.service.redis_keys import blacklist_key, refresh_families_key, refresh_family_key
from core_api.modules.identity.service.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from shared import notify
from shared.auth import InvalidTokenError
from shared.config import get_settings
from shared.redis import get_redis

logger = structlog.get_logger(__name__)
settings = get_settings()

# Dummy hash to prevent timing attacks — always run bcrypt even if user not found
_DUMMY_HASH = hash_password("dummy-never-matches-any-password")

CURRENCY = {"US": "USD", "IN": "INR"}
LOCALE = {"US": "en-US", "IN": "en-IN"}


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": code, "message": message})


def _welcome_html(name: str) -> str:
    safe = html.escape(name or "there")
    return (
        f"<p>Hi {safe},</p><p>Welcome to BhojanGo. Your account is ready: "
        "pick a restaurant near you and we'll bring the food over.</p><p>The BhojanGo team</p>"
    )


async def issue_tokens(db: AsyncSession, user: User, *, family: str | None = None, is_new_user: bool = False) -> AuthTokensResponse:
    """Access + refresh token pair; starts a new refresh family unless one is given."""
    admin = [f"{a.role}@{a.scope}" for a in await AdminRoleRepository(db).for_user(user.id)]
    access_token, expires_in = create_access_token(str(user.id), user.email, user.role, user.country, admin)
    refresh_token, jti, family, ttl = create_refresh_token(str(user.id), family)
    redis = await get_redis()
    uid = str(user.id)
    pipe = redis.pipeline()
    pipe.setex(refresh_family_key(uid, family), ttl, jti)
    pipe.sadd(refresh_families_key(uid), family)
    pipe.expire(refresh_families_key(uid), ttl)
    await pipe.execute()
    return AuthTokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
        is_new_user=is_new_user,
        admin_roles=admin,
    )


async def revoke_all_sessions(user_id: str) -> None:
    """Sign out everywhere: drop every refresh family of the user."""
    redis = await get_redis()
    families = await redis.smembers(refresh_families_key(user_id))
    keys = [refresh_family_key(user_id, f) for f in families] + [refresh_families_key(user_id)]
    await redis.delete(*keys)


async def blacklist_access_token(access_token: str) -> None:
    try:
        payload = decode_token(access_token)
    except InvalidTokenError:
        return
    ttl = max(0, int(payload.get("exp", 0) - datetime.now(UTC).timestamp()))
    if ttl > 0:
        redis = await get_redis()
        await redis.setex(blacklist_key(payload.get("jti", "")), ttl, "1")


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def register(self, data: RegisterRequest) -> AuthTokensResponse:
        if await self.repo.email_exists(data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "EMAIL_ALREADY_EXISTS", "message": "Email is already registered"},
            )
        if data.phone and await self.repo.phone_exists(data.phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "PHONE_ALREADY_EXISTS", "message": "Phone number is already registered"},
            )

        user = await self.repo.create(
            email=data.email.lower().strip(),
            phone=data.phone,
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role="customer",
            country=data.country,
            preferred_currency=data.preferred_currency,
            preferred_locale=data.preferred_locale,
        )
        logger.info("user_registered", user_id=str(user.id))
        await notify.send("email", user.email or "", _welcome_html(user.full_name), subject="Welcome to BhojanGo")
        return await issue_tokens(self.db, user, is_new_user=True)

    async def login(self, data: LoginRequest) -> AuthTokensResponse:
        user = await self.repo.get_by_email(data.email)
        # Always run bcrypt to prevent timing-based user enumeration
        password_valid = verify_password(
            data.password,
            user.hashed_password if user and user.hashed_password else _DUMMY_HASH,
        )
        if not user or not password_valid:
            raise _unauthorized("INVALID_CREDENTIALS", "Invalid email or password")
        self._require_active(user)
        logger.info("user_logged_in", user_id=str(user.id), method="password")
        return await issue_tokens(self.db, user)

    async def phone_sign_in(self, data: PhoneSignInRequest) -> AuthTokensResponse:
        """Sign in with an SMS code; creates a customer account for a new number."""
        if not await verify_otp(data.phone, data.otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "OTP_INVALID", "message": "Invalid or expired code"},
            )
        user = await self.repo.get_by_phone(data.phone)
        is_new = user is None
        if user is None:
            user = await self.repo.create(
                email=None,
                phone=data.phone,
                full_name=data.full_name or "BhojanGo customer",
                role="customer",
                country=data.country,
                preferred_currency=CURRENCY[data.country],
                preferred_locale=LOCALE[data.country],
                is_phone_verified=True,
            )
            logger.info("user_registered", user_id=str(user.id), method="phone")
        else:
            self._require_active(user)
            if not user.is_phone_verified:
                user = await self.repo.update(user.id, is_phone_verified=True) or user
        logger.info("user_logged_in", user_id=str(user.id), method="phone")
        return await issue_tokens(self.db, user, is_new_user=is_new)

    async def refresh(self, refresh_token: str) -> AuthTokensResponse:
        try:
            payload = decode_token(refresh_token)
        except InvalidTokenError:
            raise _unauthorized("INVALID_TOKEN", "Invalid or expired refresh token")
        if payload.get("type") != "refresh" or not payload.get("fam"):
            raise _unauthorized("INVALID_TOKEN", "Not a refresh token")

        user_id, family, jti = payload["sub"], payload["fam"], payload.get("jti", "")
        redis = await get_redis()
        current = await redis.get(refresh_family_key(user_id, family))
        if current is None:
            raise _unauthorized("TOKEN_REVOKED", "Session has ended; sign in again")
        if current != jti:
            # An already-used refresh token: someone else has a copy. End the session.
            await redis.delete(refresh_family_key(user_id, family))
            await redis.srem(refresh_families_key(user_id), family)
            logger.warning("refresh_token_reuse_detected", user_id=user_id, family=family)
            raise _unauthorized("TOKEN_REUSED", "Session ended for your security; sign in again")

        user = await self.repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise _unauthorized("USER_INACTIVE", "User not found or inactive")
        return await issue_tokens(self.db, user, family=family)

    async def logout(self, access_token: str, user_id: str) -> None:
        await blacklist_access_token(access_token)
        await revoke_all_sessions(user_id)
        logger.info("user_logged_out", user_id=user_id)

    async def send_otp(self, data: OtpSendRequest) -> bool:
        return await send_otp(data.phone, data.country)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        """Verify the OTP, set a new password, and revoke existing sessions."""
        if not await verify_otp(data.phone, data.otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "OTP_INVALID", "message": "Invalid or expired OTP"},
            )
        user = await self.repo.get_by_phone(data.phone)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "USER_NOT_FOUND", "message": "No account found for this phone number"},
            )
        await self.repo.update(user.id, hashed_password=hash_password(data.new_password))
        await revoke_all_sessions(str(user.id))
        logger.info("password_reset", user_id=str(user.id))

    async def verify_otp_and_update(self, data: OtpVerifyRequest) -> bool:
        verified = await verify_otp(data.phone, data.otp)
        if verified:
            user = await self.repo.get_by_phone(data.phone)
            if user:
                await self.repo.update(user.id, is_phone_verified=True)
        return verified

    async def social_login(self, data: SocialLoginRequest) -> AuthTokensResponse:
        """Sign in with Apple or Google: verify the provider's ID token, then
        find the account by provider id, or by a *verified* email, or create one."""
        audiences = (
            settings.identity.google_audiences if data.provider == "google" else settings.identity.APPLE_CLIENT_IDS
        )
        try:
            ident = await oidc.verify(data.provider, data.token, audiences)
        except oidc.OidcError as e:
            logger.info("social_login_rejected", provider=data.provider, reason=str(e))
            raise _unauthorized(f"INVALID_{data.provider.upper()}_TOKEN", f"Invalid {data.provider.title()} token")

        id_field = "google_id" if data.provider == "google" else "apple_id"
        user = await (self.repo.get_by_google_id if data.provider == "google" else self.repo.get_by_apple_id)(ident.subject)
        is_new = False
        if user is None and ident.email and ident.email_verified:
            # Link to an existing account only when the provider vouches for the email.
            user = await self.repo.get_by_email(ident.email)
            if user is not None:
                user = await self.repo.update(user.id, **{id_field: ident.subject}) or user
        if user is None:
            user = await self.repo.create(
                email=ident.email.lower() if ident.email and ident.email_verified else None,
                full_name=ident.name or ("Apple user" if data.provider == "apple" else "Google user"),
                role="customer",
                country=data.country,
                preferred_currency=CURRENCY[data.country],
                preferred_locale=LOCALE[data.country],
                is_verified=ident.email_verified,
                **{id_field: ident.subject},
            )
            is_new = True
        self._require_active(user)
        logger.info("user_logged_in", user_id=str(user.id), method=data.provider)
        return await issue_tokens(self.db, user, is_new_user=is_new)

    async def delete_account(self, user: User, access_token: str | None = None) -> None:
        """Account deletion (app store requirement, GDPR/DPDP): remove personal
        data, end every session, drop admin roles. Orders keep the anonymous id."""
        uid = str(user.id)
        await self.repo.update(
            user.id,
            email=None,
            phone=None,
            full_name="Deleted user",
            avatar_url=None,
            hashed_password=None,
            google_id=None,
            apple_id=None,
            fcm_token=None,
            is_active=False,
            is_verified=False,
            is_phone_verified=False,
        )
        await AdminRoleRepository(self.db).delete_for_user(user.id)
        await self.db.execute(delete(Address).where(Address.user_id == user.id))
        await revoke_all_sessions(uid)
        if access_token:
            await blacklist_access_token(access_token)
        logger.info("user_account_deleted", user_id=uid)

    @staticmethod
    def _require_active(user: User) -> None:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_INACTIVE", "message": "Account is inactive"},
            )
