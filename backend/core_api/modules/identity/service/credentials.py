"""A signed-in person's ways in (Profile > Sign-in and security): one account per
person, with a phone and/or an email linked to it, each verified by a code, and
a password they can set or change.

An email or phone already on another account can't be linked: the answer says
so, never whose it is (per-account limits stop this being used to test many
addresses). Changing the password signs every other device out.
"""
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.user import User
from core_api.modules.identity.repository.user import UserRepository
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    ChangePasswordRequest,
    LinkEmailStart,
    LinkEmailVerify,
    LinkPhoneStart,
    LinkPhoneVerify,
    SecurityOverview,
)
from core_api.modules.identity.service import background, email_codes, events, guard, mailer, mfa, passwords
from core_api.modules.identity.service.email_auth import code_invalid, forgot_link, rejected
from core_api.modules.identity.service.otp import send_otp, verify_otp
from core_api.modules.identity.service.sessions import (
    blacklist_access_token,
    issue_tokens,
    requires_mfa,
    revoke_all_sessions,
    token_has_mfa,
)
from core_api.modules.markets.service import countries

LINKS_PER_WINDOW = 5
LINK_WINDOW_SECONDS = 15 * 60


def _error(code: int, kind: str, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": kind, "message": message})


class CredentialsService:
    def __init__(self, db: AsyncSession, user: User) -> None:
        self.db = db
        self.user = user
        self.repo = UserRepository(db)

    async def overview(self) -> SecurityOverview:
        u = self.user
        return SecurityOverview(
            email=u.email, email_verified=bool(u.email and u.is_verified), phone=u.phone,
            phone_verified=bool(u.phone and u.is_phone_verified), has_password=bool(u.hashed_password),
            password_changed_at=u.password_changed_at, google_linked=bool(u.google_id), apple_linked=bool(u.apple_id),
            mfa_enabled=bool(u.totp_secret), mfa_required=await requires_mfa(self.db, u),
            recovery_codes_left=await mfa.recovery_codes_left(self.db, u.id) if u.totp_secret else 0,
        )

    async def _limit(self, action: str) -> None:
        if not await guard.hit(action, str(self.user.id), limit=LINKS_PER_WINDOW, window_seconds=LINK_WINDOW_SECONDS):
            raise _error(status.HTTP_429_TOO_MANY_REQUESTS, "TOO_MANY_REQUESTS", "Too many tries. Try again in 15 minutes.")

    # ── password ─────────────────────────────────────────────────────────────
    async def change_password(self, data: ChangePasswordRequest, access_token: str) -> AuthTokensResponse:
        u = self.user
        if not u.email:
            raise _error(status.HTTP_409_CONFLICT, "EMAIL_REQUIRED", "Add an email first: you sign in with it and your password.")
        had = bool(u.hashed_password)
        if had:
            left = await guard.locked_for(u.email)
            if left:
                raise mfa.locked_error(left)
            if not passwords.verify_password(data.current_password or "", u.hashed_password):
                events.record_later(u.id, "auth.sign_in_failed", method="password_change")
                locked = await guard.failure(u.email)
                if locked:
                    events.record_later(u.id, "auth.locked", minutes=locked // 60)
                    raise mfa.locked_error(locked)
                raise _error(status.HTTP_400_BAD_REQUEST, "WRONG_PASSWORD", "Your current password isn't right.")
        try:
            await passwords.validate_new_password(data.new_password, email=u.email)
        except passwords.PasswordRejected as e:
            raise rejected(e) from e
        await self.repo.update(u.id, hashed_password=passwords.hash_password(data.new_password),
                               password_changed_at=datetime.now(UTC))
        await guard.clear(u.email)
        # Everyone else out; this device gets a fresh session (an admin keeps their second step).
        await revoke_all_sessions(str(u.id))
        await blacklist_access_token(access_token)
        await events.record(self.db, u.id, "auth.password_changed" if had else "auth.password_set")
        if had:
            lang = mailer.language(None, u.preferred_locale)
            background.spawn(mailer.send(u.email, "changed", lang, link=forgot_link()), name="mail:changed")
        fresh = await self.repo.get_by_id(u.id) or u
        return await issue_tokens(self.db, fresh, mfa=token_has_mfa(access_token))

    # ── email ────────────────────────────────────────────────────────────────
    async def start_email(self, data: LinkEmailStart) -> None:
        email = data.email.strip().lower()
        await self._limit("link_email")  # checking many addresses from one account
        wait = await guard.code_send_wait("email_send", email, exempt=bool(email_codes.fixed_code_for(email)))
        if self.user.email == email and self.user.is_verified:
            raise _error(status.HTTP_409_CONFLICT, "ALREADY_LINKED", "This email is already on your account.")
        other = await self.repo.get_by_email(email)
        if other is not None and other.id != self.user.id:
            raise _error(status.HTTP_409_CONFLICT, "EMAIL_IN_USE",
                         "This email is already used by another BhojanGo account. Use a different one.")
        if wait:
            raise guard.too_many_codes(wait, "email address")
        code = await email_codes.issue(f"link:{self.user.id}", email)
        lang = mailer.language(data.language, self.user.preferred_locale)
        background.spawn(mailer.send_code(email, code, lang, email_codes.ttl_minutes()), name="mail:link")

    async def verify_email(self, data: LinkEmailVerify) -> User:
        email = data.email.strip().lower()
        if not await email_codes.check(f"link:{self.user.id}", email, data.code):
            raise code_invalid()
        other = await self.repo.get_by_email(email)
        if other is not None and other.id != self.user.id:
            raise _error(status.HTTP_409_CONFLICT, "EMAIL_IN_USE",
                         "This email is already used by another BhojanGo account. Use a different one.")
        old = self.user.email
        user = await self.repo.update(self.user.id, email=email, is_verified=True) or self.user
        await events.record(self.db, user.id, "auth.email_linked", replaced=bool(old and old != email))
        if old and old != email:
            lang = mailer.language(None, user.preferred_locale)
            background.spawn(mailer.send(old, "email_replaced", lang), name="mail:email_replaced")
        return user

    # ── phone ────────────────────────────────────────────────────────────────
    async def start_phone(self, data: LinkPhoneStart) -> None:
        country = await countries.require_open(self.db, data.country)
        data.phone = countries.require_phone_in(country, data.phone) or data.phone  # R38: E.164
        await self._limit("link_phone")
        if self.user.phone == data.phone and self.user.is_phone_verified:
            raise _error(status.HTTP_409_CONFLICT, "ALREADY_LINKED", "This number is already on your account.")
        other = await self.repo.get_by_phone(data.phone)
        if other is not None and other.id != self.user.id:
            raise _error(status.HTTP_409_CONFLICT, "PHONE_IN_USE",
                         "This number is already used by another BhojanGo account. Use a different one.")
        lang = mailer.language(data.language, self.user.preferred_locale)
        if not await send_otp(data.phone, country.code, lang):  # 429 TOO_MANY_CODES is raised inside
            raise _error(status.HTTP_503_SERVICE_UNAVAILABLE, "SEND_FAILED", "We couldn't send the code. Try again in a moment.")

    async def verify_phone(self, data: LinkPhoneVerify) -> User:
        from shared.phone import normalize

        data.phone = normalize(data.phone) or data.phone  # R38: E.164, as start_phone sent the code to
        other = await self.repo.get_by_phone(data.phone)
        if other is not None and other.id != self.user.id:
            raise _error(status.HTTP_409_CONFLICT, "PHONE_IN_USE",
                         "This number is already used by another BhojanGo account. Use a different one.")
        if not await verify_otp(data.phone, data.code):
            raise code_invalid()
        user = await self.repo.update(self.user.id, phone=data.phone, is_phone_verified=True) or self.user
        await events.record(self.db, user.id, "auth.phone_linked")
        return user
