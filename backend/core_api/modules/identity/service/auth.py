"""Sign-in, tokens and account deletion.

Sessions and tokens: service/sessions.py (re-exported here for older imports).
Every sign-in ends in mfa.finish_sign_in: tokens, or an admin's second step.
Email sign-up, email codes and password reset: service/email_auth.py.
"""
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.recovery_code import RecoveryCode
from core_api.modules.identity.models.rider import RiderProfile
from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.admin_role import AdminRoleRepository
from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    LoginRequest,
    MfaChallengeResponse,
    OtpSendRequest,
    OtpVerifyRequest,
    PhoneSignInRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
)
from core_api.modules.identity.service import events, guard, oidc, passwords
from core_api.modules.identity.service.email_auth import rejected
from core_api.modules.identity.service.mfa import finish_sign_in, locked_error
from core_api.modules.legal import service as legal
from core_api.modules.identity.service.otp import send_otp, verify_otp
from core_api.modules.identity.service.redis_keys import refresh_families_key, refresh_family_key
from core_api.modules.identity.service.security import decode_token
from core_api.modules.identity.service.sessions import (  # noqa: F401 - re-exported
    blacklist_access_token,
    issue_tokens,
    requires_mfa,
    revoke_all_sessions,
)
from core_api.modules.markets.service import countries
from shared.auth import InvalidTokenError
from shared.config import get_settings
from shared.redis import get_redis
from shared.texts import language_for

logger = structlog.get_logger(__name__)
settings = get_settings()

# A new account's currency and language come from its country in Markets
# (markets.service.countries), not from a list here.

SignInResult = AuthTokensResponse | MfaChallengeResponse


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": code, "message": message})


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def login(self, data: LoginRequest) -> SignInResult:
        """Email + password. Wrong answers are the same for an unknown email and a
        wrong password (and take as long: a hash is always checked); five in a row
        lock password sign-in for that email for 15 minutes, account or not."""
        email = data.email.strip().lower()
        left = await guard.locked_for(email)
        if left:
            raise locked_error(left)
        user = await self.repo.get_by_email(email)
        stored = user.hashed_password if user and user.hashed_password else passwords.DUMMY_HASH
        valid = passwords.verify_password(data.password, stored) and user is not None and bool(user.hashed_password)
        if not valid:
            locked = await guard.failure(email)
            if user is not None:
                events.record_later(user.id, "auth.sign_in_failed", method="password")
                if locked:
                    events.record_later(user.id, "auth.locked", minutes=locked // 60)
            if locked:
                raise locked_error(locked)
            raise _unauthorized("INVALID_CREDENTIALS",
                                "That email and password don't match. Try again, or sign in with an email code.")
        assert user is not None
        await guard.clear(email)
        self._require_active(user)
        if passwords.needs_rehash(user.hashed_password):
            # bcrypt (or older Argon2 settings) -> Argon2id, now that we have the password.
            user = await self.repo.update(user.id, hashed_password=passwords.hash_password(data.password)) or user
            logger.info("password_rehashed", user_id=str(user.id))
        logger.info("user_logged_in", user_id=str(user.id), method="password")
        return await finish_sign_in(self.db, user, "password")

    async def phone_sign_in(self, data: PhoneSignInRequest, client: legal.ClientInfo | None = None) -> SignInResult:
        """Sign in with an SMS code; creates a customer account for a new number."""
        country = await countries.require_open(self.db, data.country)
        countries.require_phone_in(country, data.phone)
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
                country=country.code,
                preferred_currency=country.currency,
                preferred_locale=country.default_locale,
                is_phone_verified=True,
            )
            await events.record(self.db, user.id, "auth.signed_up", method="phone")
            logger.info("user_registered", user_id=str(user.id), method="phone")
            # Signing in with a new number creates the account: "By continuing you agree to the Terms and Privacy".
            await legal.record_acceptance(self.db, user.id, user.country, language=user.preferred_locale, client=client)
        else:
            self._require_active(user)
            if not user.is_phone_verified:
                user = await self.repo.update(user.id, is_phone_verified=True) or user
        logger.info("user_logged_in", user_id=str(user.id), method="phone")
        return await finish_sign_in(self.db, user, "phone", is_new_user=is_new)

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
        mfa = payload.get("mfa") is True
        if not mfa and await requires_mfa(self.db, user):
            # A session from before two-step sign-in (or before admin roles were
            # granted): the second step is needed now.
            await redis.delete(refresh_family_key(user_id, family))
            await redis.srem(refresh_families_key(user_id), family)
            raise _unauthorized("MFA_REQUIRED", "Sign in again with your authenticator code")
        return await issue_tokens(self.db, user, family=family, mfa=mfa)

    async def logout(self, access_token: str, user_id: str) -> None:
        await blacklist_access_token(access_token)
        await revoke_all_sessions(user_id)
        logger.info("user_logged_out", user_id=user_id)

    async def send_otp(self, data: OtpSendRequest) -> bool:
        country = await countries.require_open(self.db, data.country)
        countries.require_phone_in(country, data.phone)
        return await send_otp(data.phone, country.code, await self._otp_language(data, country))

    async def _otp_language(self, data: OtpSendRequest, country: countries.CountryInfo) -> str:
        """The app's language when the country offers it, else the account's, else the country's default."""
        offered = {language_for(loc) for loc in country.locales}
        if data.language and data.language in offered and language_for(data.language) == data.language:
            return data.language
        user = await self.repo.get_by_phone(data.phone)
        if user is not None and user.preferred_locale:
            return language_for(user.preferred_locale)
        return language_for(country.default_locale)

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        """Choose a new password by proving the phone with its code; ends every session."""
        user = await self.repo.get_by_phone(data.phone)
        try:
            await passwords.validate_new_password(data.new_password, email=user.email if user else None)
        except passwords.PasswordRejected as e:
            raise rejected(e) from e
        if not await verify_otp(data.phone, data.otp) or user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "OTP_INVALID", "message": "Invalid or expired code"},
            )
        await self.repo.update(user.id, hashed_password=passwords.hash_password(data.new_password),
                               password_changed_at=datetime.now(UTC))
        await revoke_all_sessions(str(user.id))
        if user.email:
            await guard.clear(user.email)
        await events.record(self.db, user.id, "auth.password_reset", method="phone")
        logger.info("password_reset", user_id=str(user.id), method="phone")

    async def verify_otp_and_update(self, data: OtpVerifyRequest) -> bool:
        verified = await verify_otp(data.phone, data.otp)
        if verified:
            user = await self.repo.get_by_phone(data.phone)
            if user:
                await self.repo.update(user.id, is_phone_verified=True)
        return verified

    async def social_login(self, data: SocialLoginRequest, client: legal.ClientInfo | None = None) -> SignInResult:
        """Sign in with Apple or Google: verify the provider's ID token, then
        find the account by provider id, or by a *verified* email, or create one."""
        audiences = (
            settings.identity.google_audiences if data.provider == "google" else settings.identity.apple_audiences
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
                changes: dict = {id_field: ident.subject}
                if not user.is_verified:
                    # Nobody proved this mailbox before: a password set by whoever made the
                    # account (maybe not the mailbox's owner) must not survive the link.
                    changes.update(is_verified=True, hashed_password=None)
                    await revoke_all_sessions(str(user.id))
                    await events.record(self.db, user.id, "auth.email_verified", method=data.provider)
                user = await self.repo.update(user.id, **changes) or user
        if user is None:
            country = await countries.require_open(self.db, data.country)
            user = await self.repo.create(
                email=ident.email.lower() if ident.email and ident.email_verified else None,
                full_name=ident.name or ("Apple user" if data.provider == "apple" else "Google user"),
                role="customer",
                country=country.code,
                preferred_currency=country.currency,
                preferred_locale=country.default_locale,
                is_verified=ident.email_verified,
                **{id_field: ident.subject},
            )
            await events.record(self.db, user.id, "auth.signed_up", method=data.provider)
            is_new = True
            await legal.record_acceptance(self.db, user.id, user.country, language=user.preferred_locale, client=client)
        self._require_active(user)
        logger.info("user_logged_in", user_id=str(user.id), method=data.provider)
        return await finish_sign_in(self.db, user, data.provider, is_new_user=is_new)

    async def delete_account(self, user: User, access_token: str | None = None) -> None:
        """Account deletion (app store requirement, GDPR/DPDP): remove personal
        data, end every session, drop admin roles. Orders keep the anonymous id,
        with the street, map pin and notes removed (orders.service.lookup.forget_customer)."""
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
            totp_secret=None,
            totp_enabled_at=None,
            totp_last_step=None,
        )
        await self.db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
        await self.db.execute(delete(RiderProfile).where(RiderProfile.user_id == user.id))  # date of birth, vehicle
        await AdminRoleRepository(self.db).delete_for_user(user.id)
        await self.db.execute(delete(Address).where(Address.user_id == user.id))
        # Saved cards, favourites and preferences go; orders and reviews stay
        # (tax and restaurant records) without the personal details.
        from core_api.modules.catalog.service import lookup as catalog_lookup
        from core_api.modules.identity.service import account
        from core_api.modules.orders.service import lookup as order_lookup
        from core_api.modules.payments.service import methods

        await methods.forget_user(self.db, user.id)
        await account.forget(self.db, user.id)
        await order_lookup.forget_customer(self.db, user.id)
        await catalog_lookup.forget_reviewer(self.db, user.id)
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
