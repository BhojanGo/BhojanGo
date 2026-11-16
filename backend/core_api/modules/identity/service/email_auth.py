"""Email sign-in (Round 8, D5): create an account with email + password (the
address is verified by a 6-digit code before the account exists), sign in with
a code instead of the password, and choose a new password by a link.

No account enumeration: sign-up, "email me a code" and "forgot password" give
the same answer whether or not the email has an account, and do the same work
before answering (the password is always hashed; emails and audit rows are sent
after the answer, service/background.py). What differs is only the email that
arrives, which only the mailbox's owner sees:

  sign-up, new email       -> a code; the account is created when it's entered
  sign-up, existing email  -> "you already have an account" with a reset link
  email me a code          -> a sign-in code (nothing for an unknown email)
  forgot password          -> a reset link (nothing for an unknown email)

Redis:
  email_signup:{hash}            pending sign-up {email, password_hash, country, ...}  (code lifetime)
  pwreset:{sha256(token)}        user id                                                (30 minutes)
  pwreset_user:{user id}         the user's current reset token hash (a new link ends the old one)
"""
from typing import TYPE_CHECKING

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    EmailCodeRequest,
    EmailSignUpRequest,
    EmailVerifyRequest,
    ForgotPasswordRequest,
    MfaChallengeResponse,
    PasswordResetRequest,
)
from core_api.modules.identity.service import background, email_codes, events, guard, mailer, passwords
from core_api.modules.identity.service.mfa import finish_sign_in
from core_api.modules.identity.service.sessions import revoke_all_sessions
from core_api.modules.markets.service import countries
from shared.config import get_settings
from shared.redis import get_redis

if TYPE_CHECKING:
    from core_api.modules.legal.service import ClientInfo

logger = structlog.get_logger(__name__)


SENT = "If that email can be used, we've sent a message to it. Check your inbox and spam folder."


def rejected(e: passwords.PasswordRejected) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                         detail={"code": e.code, "message": e.message})


def code_invalid() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                         detail={"code": "CODE_INVALID", "message": "That code is wrong or has expired."})


def _norm(email: str) -> str:
    return email.strip().lower()


def _signup_key(email: str) -> str:
    return f"email_signup:{guard.ident_hash(email)}"


def _reset_key(token: str) -> str:
    return "pwreset:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def reset_link(token: str) -> str:
    return mailer.web_link(f"/signin/reset?token={token}")


def forgot_link() -> str:
    return mailer.web_link("/signin/forgot")


async def _same_work() -> None:
    """The Redis round trips a real account's branch makes, so both take as long."""
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.get("pwreset_user:none")
    pipe.exists("email_code:none")
    await pipe.execute()
    await redis.get("pwreset_user:none")


class EmailAuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def _send_allowed(self, action: str, email: str) -> None:
        """Per email address (any account or none, so the answer is the same): 1 per 30 s,
        5 per hour, 10 per day (guard.code_send_wait). The seed's @example.com is exempt
        outside production (it always gets the fixed code)."""
        wait = await guard.code_send_wait(action, email, exempt=bool(email_codes.fixed_code_for(email)))
        if wait:
            raise guard.too_many_codes(wait, "email address")

    # ── sign-up ──────────────────────────────────────────────────────────────
    async def sign_up(self, data: EmailSignUpRequest) -> str:
        email = _norm(data.email)
        try:
            await passwords.validate_new_password(data.password, email=email)
        except passwords.PasswordRejected as e:
            raise rejected(e) from e
        country = await countries.require_open(self.db, data.country)
        return await self.start_sign_up(email, data.password, country, full_name=data.full_name, language=data.language)

    async def start_sign_up(self, email: str, password: str, country: countries.CountryInfo, *, full_name: str | None,
                            language: str | None, locale: str | None = None, kitchen: dict | None = None) -> str:
        """The password was already checked. A code goes to a new email; the account is made
        when it's entered (_create). ``kitchen``: a kitchen partner's application
        (catalog /kitchens/apply): the account becomes theirs, with the kitchen pending."""
        email = _norm(email)
        await self._send_allowed("email_send", email)
        # Hash for every request (also for an existing email): the same work either way.
        password_hash = passwords.hash_password(password)
        existing = await self.repo.get_by_email(email)
        lang = mailer.language(language, locale or country.default_locale)
        if existing is not None:
            background.spawn(mailer.send(email, "exists", lang, link=forgot_link()), name="mail:exists")
            logger.info("email_sign_up_existing")
            return SENT
        pending = {"email": email, "password_hash": password_hash, "country": country.code,
                   "currency": country.currency, "locale": locale or country.default_locale,
                   "language": lang, "full_name": (full_name or "").strip() or None, "kitchen": kitchen}
        redis = await get_redis()
        await redis.setex(_signup_key(email), email_codes.ttl_minutes() * 60, json.dumps(pending))
        code = await email_codes.issue("signup", email)
        background.spawn(mailer.send_code(email, code, lang, email_codes.ttl_minutes()), name="mail:signup")
        return SENT

    # ── sign in with a code ──────────────────────────────────────────────────
    async def send_code(self, data: EmailCodeRequest) -> str:
        email = _norm(data.email)
        await self._send_allowed("email_send", email)
        user = await self.repo.get_by_email(email)
        if user is not None and user.is_active:
            code = await email_codes.issue("signin", email)
            lang = mailer.language(data.language, user.preferred_locale)
            background.spawn(mailer.send_code(email, code, lang, email_codes.ttl_minutes()), name="mail:signin")
        else:
            await _same_work()
        return SENT

    async def verify(self, data: EmailVerifyRequest, client: "ClientInfo | None" = None) -> AuthTokensResponse | MfaChallengeResponse:
        """The code from sign-up (creates the account) or from "email me a code"."""
        email = _norm(data.email)
        redis = await get_redis()
        raw = await redis.get(_signup_key(email))
        if raw is not None:
            if not await email_codes.check("signup", email, data.code):
                raise code_invalid()
            await redis.delete(_signup_key(email))
            return await self._create(json.loads(raw), client)
        if not await email_codes.check("signin", email, data.code):
            raise code_invalid()
        user = await self.repo.get_by_email(email)
        if user is None or not user.is_active:
            raise code_invalid()
        if not user.is_verified:
            user = await self.repo.update(user.id, is_verified=True) or user
            await events.record(self.db, user.id, "auth.email_verified")
        await guard.clear(email)
        return await finish_sign_in(self.db, user, "email_code")

    async def _create(self, pending: dict, client: "ClientInfo | None" = None) -> AuthTokensResponse | MfaChallengeResponse:
        email = pending["email"]
        if await self.repo.email_exists(email):  # taken while the code was on its way
            raise code_invalid()
        kitchen = pending.get("kitchen")
        user = await self.repo.create(
            email=email, phone=None, full_name=pending.get("full_name") or "BhojanGo customer",
            hashed_password=pending["password_hash"], password_changed_at=datetime.now(UTC),
            role="restaurant_owner" if kitchen else "customer", country=pending["country"],
            preferred_currency=pending["currency"], preferred_locale=pending["locale"], is_verified=True,
        )
        # Signing up is accepting the country's Terms and Privacy (and, for a kitchen, the kitchen partner terms).
        from core_api.modules.legal import service as legal

        await legal.record_acceptance(self.db, user.id, user.country,
                                      legal.ROLE_KINDS["restaurant_owner"] if kitchen else legal.SIGN_UP_KINDS,
                                      language=user.preferred_locale, client=client)
        if kitchen:
            # The kitchen pending approval, the accepted terms, the "application started" email.
            from core_api.modules.catalog.api.v1.kitchens import open_applied_kitchen

            await open_applied_kitchen(self.db, user, kitchen)
            await events.record(self.db, user.id, "auth.signed_up", method="email", kitchen=True)
            await events.record(self.db, user.id, "auth.email_verified")
            await events.record(self.db, user.id, "auth.password_set")
            logger.info("user_registered", user_id=str(user.id), method="email", role="restaurant_owner")
            return await finish_sign_in(self.db, user, "email_code", is_new_user=True)
        await events.record(self.db, user.id, "auth.signed_up", method="email")
        await events.record(self.db, user.id, "auth.email_verified")
        await events.record(self.db, user.id, "auth.password_set")
        logger.info("user_registered", user_id=str(user.id), method="email")
        background.spawn(mailer.send_welcome(email, pending.get("full_name") or "", pending.get("language") or "en"),
                         name="mail:welcome")
        return await finish_sign_in(self.db, user, "email_code", is_new_user=True)

    # ── forgot password ──────────────────────────────────────────────────────
    async def forgot(self, data: ForgotPasswordRequest) -> str:
        email = _norm(data.email)
        await self._send_allowed("pw_forgot", email)
        user = await self.repo.get_by_email(email)
        token = secrets.token_urlsafe(32)  # made either way: the same work
        if user is not None and user.is_active:
            redis = await get_redis()
            minutes = get_settings().identity.PASSWORD_RESET_MINUTES
            previous = await redis.get(f"pwreset_user:{user.id}")
            pipe = redis.pipeline()
            if previous:
                pipe.delete(f"pwreset:{previous}")
            digest = _reset_key(token).split(":", 1)[1]
            pipe.setex(_reset_key(token), minutes * 60, str(user.id))
            pipe.setex(f"pwreset_user:{user.id}", minutes * 60, digest)
            await pipe.execute()
            lang = mailer.language(data.language, user.preferred_locale)
            background.spawn(mailer.send(email, "reset", lang, link=reset_link(token), minutes=minutes), name="mail:reset")
        else:
            await _same_work()
        return SENT

    async def reset_valid(self, token: str) -> bool:
        redis = await get_redis()
        return bool(await redis.exists(_reset_key(token)))

    async def reset(self, data: PasswordResetRequest) -> None:
        expired = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "code": "RESET_LINK_INVALID", "message": "This link has expired or was already used. Ask for a new one."})
        redis = await get_redis()
        uid = await redis.get(_reset_key(data.token))
        if uid is None:
            raise expired
        user = await self.repo.get_by_id(uuid.UUID(uid))
        if user is None or not user.is_active:
            await redis.delete(_reset_key(data.token))
            raise expired
        try:
            await passwords.validate_new_password(data.new_password, email=user.email)
        except passwords.PasswordRejected as e:
            raise rejected(e) from e  # the link still works: try another password
        if await redis.getdel(_reset_key(data.token)) is None:  # used at the same moment by another request
            raise expired
        await redis.delete(f"pwreset_user:{user.id}")
        await self.repo.update(user.id, hashed_password=passwords.hash_password(data.new_password),
                               password_changed_at=datetime.now(UTC), is_verified=True)
        await revoke_all_sessions(str(user.id))
        if user.email:
            await guard.clear(user.email)
            lang = mailer.language(None, user.preferred_locale)
            background.spawn(mailer.send(user.email, "changed", lang, link=forgot_link()), name="mail:changed")
        await events.record(self.db, user.id, "auth.password_reset")
        logger.info("password_reset", user_id=str(user.id), method="email_link")

