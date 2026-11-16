"""Admin two-step sign-in: the challenge after a right password, authenticator
codes, recovery codes and first-time enrolment.

After the first step (password, email code, phone code or Google) an admin gets
an ``mfa_token`` instead of tokens: 32 random bytes, kept in Redis as a SHA-256
hash for CHALLENGE_SECONDS, good for MAX_TRIES wrong codes. Wrong codes also
count towards the account's password lockout (service/guard.py).

Enrolment (an admin without an authenticator, e.g. the first sign-in after this
shipped): the password alone is not enough to attach a new authenticator, so a
code goes to the account's email first; then the key (QR code + text), then a
code from the app confirms it, and 10 recovery codes are shown once.

  mfa_challenge:{sha256(token)} -> {"uid", "enrol", "method", "tries", "email_ok", "pending"}
"""
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.recovery_code import RecoveryCode
from core_api.modules.identity.models.user import User
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    MfaChallengeResponse,
    MfaEnrolledResponse,
    MfaEnrolStartResponse,
)
from core_api.modules.identity.service import background, email_codes, events, guard, mailer, totp
from core_api.modules.identity.service.sessions import issue_tokens, requires_mfa
from shared.redis import get_redis

CHALLENGE_SECONDS = 600
MAX_TRIES = 5


def _key(token: str) -> str:
    return "mfa_challenge:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _error(code: int, kind: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=code, detail={"code": kind, "message": message, **extra})


def locked_error(seconds: int) -> HTTPException:
    minutes = max(1, (seconds + 59) // 60)
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "ACCOUNT_LOCKED", "message": f"Too many attempts. Try again in {minutes} minutes.",
                "retry_after": seconds},
        headers={"Retry-After": str(seconds)},
    )


async def finish_sign_in(db: AsyncSession, user: User, method: str, *,
                         is_new_user: bool = False) -> AuthTokensResponse | MfaChallengeResponse:
    """The first step passed: tokens, or (admins) the second step."""
    if await requires_mfa(db, user):
        return await start_challenge(user, method)
    await events.record(db, user.id, "auth.sign_in", method=method)
    return await issue_tokens(db, user, is_new_user=is_new_user)


async def start_challenge(user: User, method: str) -> MfaChallengeResponse:
    enrol = not user.totp_secret
    token = secrets.token_urlsafe(32)
    data = {"uid": str(user.id), "enrol": enrol, "method": method, "tries": 0, "email_ok": False, "pending": None}
    redis = await get_redis()
    await redis.setex(_key(token), CHALLENGE_SECONDS, json.dumps(data))
    sent = False
    if enrol and user.email:
        code = await email_codes.issue("mfa_enrol", user.email)
        background.spawn(mailer.send_code(user.email, code, mailer.language(None, user.preferred_locale),
                                          email_codes.ttl_minutes()), name="mail:mfa_enrol")
        sent = True
    return MfaChallengeResponse(mfa_token=token, enrolment_required=enrol, email_code_sent=sent,
                                expires_in=CHALLENGE_SECONDS)


async def _load(db: AsyncSession, token: str) -> tuple[dict, User]:
    redis = await get_redis()
    raw = await redis.get(_key(token))
    expired = _error(status.HTTP_401_UNAUTHORIZED, "MFA_EXPIRED", "Your sign-in timed out. Sign in again.")
    if raw is None:
        raise expired
    data = json.loads(raw)
    user = await db.get(User, uuid.UUID(data["uid"]))
    if user is None or not user.is_active:
        await redis.delete(_key(token))
        raise expired
    if user.email:
        left = await guard.locked_for(user.email)
        if left:
            raise locked_error(left)
    return data, user


async def _save(token: str, data: dict) -> None:
    redis = await get_redis()
    ttl = await redis.ttl(_key(token))
    if ttl and ttl > 0:
        await redis.setex(_key(token), ttl, json.dumps(data))


async def _wrong(token: str, data: dict, user: User, method: str) -> HTTPException:
    """Count a wrong code: the challenge ends after MAX_TRIES, the account locks
    after LOCKOUT_ATTEMPTS (with wrong passwords)."""
    data["tries"] = int(data.get("tries", 0)) + 1
    if data["tries"] >= MAX_TRIES:
        redis = await get_redis()
        await redis.delete(_key(token))
    else:
        await _save(token, data)
    events.record_later(user.id, "auth.sign_in_failed", method=method)
    locked = await guard.failure(user.email) if user.email else 0
    if locked:
        events.record_later(user.id, "auth.locked", minutes=locked // 60)
        return locked_error(locked)
    if data["tries"] >= MAX_TRIES:
        return _error(status.HTTP_401_UNAUTHORIZED, "MFA_EXPIRED", "Too many wrong codes. Sign in again.")
    return _error(status.HTTP_400_BAD_REQUEST, "CODE_INVALID", "That code didn't work. Check it and try again.")


async def _done(db: AsyncSession, token: str, user: User, data: dict, method: str) -> AuthTokensResponse:
    redis = await get_redis()
    await redis.delete(_key(token))
    if user.email:
        await guard.clear(user.email)
    await events.record(db, user.id, "auth.mfa_recovery_used" if method == "recovery_code" else "auth.mfa_used")
    await events.record(db, user.id, "auth.sign_in", method=data.get("method", "password"), second_step=method)
    await db.refresh(user)  # the bulk update of totp_last_step expired its columns
    return await issue_tokens(db, user, mfa=True)


async def verify_code(db: AsyncSession, token: str, code: str) -> AuthTokensResponse:
    data, user = await _load(db, token)
    if data["enrol"]:
        raise _error(status.HTTP_409_CONFLICT, "ENROLMENT_REQUIRED", "Set up your authenticator app first.")
    secret = totp.decrypt_secret(user.totp_secret or "")
    step = totp.matching_step(secret, code, last_step=user.totp_last_step) if secret else None
    if step is not None:
        # Atomic: of two requests with the same code, only one moves the step on.
        moved = await db.execute(update(User).where(
            User.id == user.id, (User.totp_last_step.is_(None)) | (User.totp_last_step < step)
        ).values(totp_last_step=step))
        if moved.rowcount != 1:  # type: ignore[attr-defined]
            step = None
    if step is None:
        raise await _wrong(token, data, user, "totp")
    return await _done(db, token, user, data, "totp")


async def verify_recovery(db: AsyncSession, token: str, recovery_code: str) -> AuthTokensResponse:
    data, user = await _load(db, token)
    if data["enrol"]:
        raise _error(status.HTTP_409_CONFLICT, "ENROLMENT_REQUIRED", "Set up your authenticator app first.")
    used = await db.execute(update(RecoveryCode).where(
        RecoveryCode.user_id == user.id, RecoveryCode.code_hash == totp.hash_recovery_code(recovery_code),
        RecoveryCode.used_at.is_(None),
    ).values(used_at=datetime.now(UTC)))
    if used.rowcount != 1:  # type: ignore[attr-defined]
        raise await _wrong(token, data, user, "recovery_code")
    return await _done(db, token, user, data, "recovery_code")


async def enrol_start(db: AsyncSession, token: str, email_code: str) -> MfaEnrolStartResponse:
    data, user = await _load(db, token)
    if not data["enrol"]:
        raise _error(status.HTTP_409_CONFLICT, "ALREADY_ENROLLED", "Two-step sign-in is already set up.")
    if not user.email:
        raise _error(status.HTTP_409_CONFLICT, "EMAIL_REQUIRED", "This account has no email. Ask a super admin for help.")
    if not data.get("email_ok"):
        if not await email_codes.check("mfa_enrol", user.email, email_code):
            raise await _wrong(token, data, user, "email_code")
        data["email_ok"] = True
    secret = totp.decrypt_secret(data["pending"]) if data.get("pending") else None
    if not secret:
        secret = totp.generate_secret()
        data["pending"] = totp.encrypt_secret(secret)
    await _save(token, data)
    uri = totp.otpauth_uri(secret, user.email)
    return MfaEnrolStartResponse(account=user.email, secret=secret, otpauth_uri=uri, qr_svg=totp.qr_svg_data_uri(uri))


async def _new_recovery_codes(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    codes = totp.generate_recovery_codes()
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
    db.add_all([RecoveryCode(user_id=user_id, code_hash=totp.hash_recovery_code(c)) for c in codes])
    await db.flush()
    return codes


async def enrol_confirm(db: AsyncSession, token: str, code: str) -> MfaEnrolledResponse:
    data, user = await _load(db, token)
    if not data["enrol"] or not data.get("email_ok") or not data.get("pending"):
        raise _error(status.HTTP_409_CONFLICT, "ENROLMENT_NOT_STARTED", "Start setting up your authenticator first.")
    secret = totp.decrypt_secret(data["pending"])
    step = totp.matching_step(secret, code) if secret else None
    if step is None:
        raise await _wrong(token, data, user, "totp")
    await db.execute(update(User).where(User.id == user.id).values(
        totp_secret=data["pending"], totp_enabled_at=datetime.now(UTC), totp_last_step=step))
    await db.refresh(user)
    codes = await _new_recovery_codes(db, user.id)
    await events.record(db, user.id, "auth.mfa_enabled")
    tokens = await _done(db, token, user, data, "totp")
    return MfaEnrolledResponse(**tokens.model_dump(), recovery_codes=codes)


async def renew_recovery_codes(db: AsyncSession, user: User, code: str) -> list[str]:
    """New recovery codes for a signed-in admin (the old ones stop working)."""
    secret = totp.decrypt_secret(user.totp_secret or "")
    if not secret:
        raise _error(status.HTTP_409_CONFLICT, "MFA_NOT_ENABLED", "Two-step sign-in isn't set up on this account.")
    step = totp.matching_step(secret, code, last_step=user.totp_last_step)
    if step is None:
        raise _error(status.HTTP_400_BAD_REQUEST, "CODE_INVALID", "That code didn't work. Check it and try again.")
    await db.execute(update(User).where(User.id == user.id).values(totp_last_step=step))
    codes = await _new_recovery_codes(db, user.id)
    await events.record(db, user.id, "auth.mfa_codes_renewed")
    return codes


async def recovery_codes_left(db: AsyncSession, user_id: uuid.UUID) -> int:
    rows = await db.execute(select(RecoveryCode.id).where(RecoveryCode.user_id == user_id, RecoveryCode.used_at.is_(None)))
    return len(rows.all())
