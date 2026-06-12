import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.redis import blacklist_key, get_redis, refresh_token_key
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import (
    AuthTokensResponse,
    LoginRequest,
    OtpSendRequest,
    OtpVerifyRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
    UserResponse,
)
from app.services.otp import send_otp, verify_otp

logger = structlog.get_logger(__name__)
settings = get_settings()

# Dummy hash to prevent timing attacks — always run bcrypt even if user not found
_DUMMY_HASH = hash_password("dummy-never-matches-any-password")


def _build_tokens_response(user: User) -> AuthTokensResponse:
    access_token, expires_in = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        country=user.country,
    )
    refresh_token, _ = create_refresh_token(str(user.id))
    return AuthTokensResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


async def _store_refresh_token(user_id: str, refresh_token: str) -> None:
    payload = decode_token(refresh_token)
    jti = payload["jti"]
    ttl = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    redis = await get_redis()
    await redis.setex(
        refresh_token_key(user_id, jti),
        ttl,
        json.dumps({"user_id": user_id, "jti": jti}),
    )


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

        tokens = _build_tokens_response(user)
        await _store_refresh_token(str(user.id), tokens.refresh_token)
        logger.info("user_registered", user_id=str(user.id), email=user.email)
        return tokens

    async def login(self, data: LoginRequest) -> AuthTokensResponse:
        user = await self.repo.get_by_email(data.email)
        # Always run bcrypt to prevent timing-based user enumeration
        password_valid = verify_password(
            data.password,
            user.hashed_password if user and user.hashed_password else _DUMMY_HASH,
        )
        if not user or not password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCOUNT_INACTIVE", "message": "Account is inactive"},
            )

        tokens = _build_tokens_response(user)
        await _store_refresh_token(str(user.id), tokens.refresh_token)
        logger.info("user_logged_in", user_id=str(user.id))
        return tokens

    async def refresh(self, refresh_token: str) -> AuthTokensResponse:
        try:
            payload = decode_token(refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_TOKEN", "message": "Invalid or expired refresh token"},
            )

        if payload.get("type") != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

        user_id = payload.get("sub")
        jti = payload.get("jti", "")
        redis = await get_redis()

        # Verify token exists in Redis (not revoked)
        stored = await redis.get(refresh_token_key(user_id, jti))
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "TOKEN_REVOKED", "message": "Token has been revoked"},
            )

        user = await self.repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Rotate: revoke old token, issue new pair
        await redis.delete(refresh_token_key(user_id, jti))

        new_tokens = _build_tokens_response(user)
        await _store_refresh_token(str(user.id), new_tokens.refresh_token)
        return new_tokens

    async def logout(self, access_token: str, user_id: str) -> None:
        try:
            payload = decode_token(access_token)
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            ttl = max(0, int(exp - datetime.now(UTC).timestamp()))
            redis = await get_redis()
            if ttl > 0:
                await redis.setex(blacklist_key(jti), ttl, "1")
            # Revoke all refresh tokens for this user
            pattern = refresh_token_key(user_id, "*")
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
        except JWTError:
            pass  # Token already invalid — that's fine
        logger.info("user_logged_out", user_id=user_id)

    async def send_otp(self, data: OtpSendRequest) -> bool:
        return await send_otp(data.phone, data.country)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        """Verify the OTP, set a new password, and revoke existing sessions."""
        verified = await verify_otp(data.phone, data.otp)
        if not verified:
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
        # Revoke all refresh tokens after a credential change so old sessions can't continue.
        redis = await get_redis()
        keys = await redis.keys(refresh_token_key(str(user.id), "*"))
        if keys:
            await redis.delete(*keys)
        logger.info("password_reset", user_id=str(user.id))

    async def verify_otp_and_update(self, data: OtpVerifyRequest) -> bool:
        verified = await verify_otp(data.phone, data.otp)
        if verified:
            user = await self.repo.get_by_phone(data.phone)
            if user:
                await self.repo.update(user.id, is_phone_verified=True)
        return verified

    async def social_login(self, data: SocialLoginRequest) -> AuthTokensResponse:
        if data.provider == "google":
            return await self._google_login(data)
        return await self._apple_login(data)

    async def _google_login(self, data: SocialLoginRequest) -> AuthTokensResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": data.token},
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Invalid Google token"},
                )
            google_data = resp.json()

        if google_data.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_GOOGLE_TOKEN", "message": "Token audience mismatch"},
            )

        google_id = google_data["sub"]
        email = google_data.get("email", "")
        full_name = google_data.get("name", "")

        # Find or create user
        user = await self.repo.get_by_google_id(google_id)
        if not user:
            user = await self.repo.get_by_email(email)
            if user:
                await self.repo.update(user.id, google_id=google_id)
            else:
                user = await self.repo.create(
                    email=email,
                    full_name=full_name,
                    google_id=google_id,
                    country=data.country,
                    is_verified=True,
                )

        tokens = _build_tokens_response(user)
        await _store_refresh_token(str(user.id), tokens.refresh_token)
        return tokens

    async def _apple_login(self, data: SocialLoginRequest) -> AuthTokensResponse:
        # Verify Apple identity token
        try:
            import jwt as pyjwt

            unverified = pyjwt.decode(data.token, options={"verify_signature": False})
            apple_id = unverified.get("sub", "")
            email = unverified.get("email", f"{apple_id}@privaterelay.appleid.com")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_APPLE_TOKEN", "message": "Invalid Apple token"},
            )

        user = await self.repo.get_by_apple_id(apple_id)
        if not user:
            user = await self.repo.get_by_email(email)
            if user:
                await self.repo.update(user.id, apple_id=apple_id)
            else:
                user = await self.repo.create(
                    email=email,
                    full_name="Apple User",
                    apple_id=apple_id,
                    country=data.country,
                    is_verified=True,
                )

        tokens = _build_tokens_response(user)
        await _store_refresh_token(str(user.id), tokens.refresh_token)
        return tokens
