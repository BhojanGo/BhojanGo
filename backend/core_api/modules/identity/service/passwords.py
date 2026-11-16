"""Passwords: Argon2id hashing and the rules for a new password (Round 8, D5).

Contract other modules use:

    hash_password(pw) -> str                 Argon2id (OWASP parameters)
    verify_password(pw, hashed) -> bool      Argon2id, or a legacy bcrypt hash
    needs_rehash(hashed) -> bool             True for bcrypt or weaker Argon2 parameters
    await validate_new_password(pw, *, email)  raises PasswordRejected(code, message)

Existing bcrypt hashes keep working; the next successful sign-in stores an
Argon2id hash instead (service/auth.py).

The breached-password check asks Pwned Passwords with k-anonymity: only the first
5 hex characters of the password's SHA-1 leave the server, padded responses, a
short timeout. If the service can't be reached the password is allowed and the
miss is logged: sign-up never fails because a third party is down. Tests replace
the checker with ``set_breach_checker`` (no network in tests).
"""
from __future__ import annotations

import hashlib
import unicodedata
from typing import Protocol

import bcrypt
import httpx
import structlog
from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from argon2 import low_level

logger = structlog.get_logger(__name__)

MIN_LENGTH = 10
MAX_LENGTH = 128  # Argon2 copes with more; this keeps request bodies and hashing time bounded

# OWASP Password Storage Cheat Sheet: Argon2id, m=19 MiB, t=2, p=1.
_hasher = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1, hash_len=32, salt_len=16,
                         type=low_level.Type.ID)


class PasswordRejected(ValueError):
    """A new password that breaks a rule. ``code`` is stable (the apps translate it)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _normalise(password: str) -> str:
    # The same password typed on two keyboards can differ in Unicode form.
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    return _hasher.hash(_normalise(password))


def verify_password(password: str, hashed: str | None) -> bool:
    """True if ``password`` matches ``hashed`` (Argon2id or legacy bcrypt). Never raises."""
    if not hashed or password is None:
        return False
    try:
        if hashed.startswith("$argon2"):
            return _hasher.verify(hashed, _normalise(password))
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            # bcrypt only looks at the first 72 bytes; passlib hashed the raw password.
            return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("ascii"))
    except (argon2_exceptions.VerificationError, argon2_exceptions.InvalidHashError, ValueError):
        return False
    return False


def needs_rehash(hashed: str | None) -> bool:
    """A stored hash that should be replaced after the next successful sign-in."""
    if not hashed:
        return False
    if not hashed.startswith("$argon2id$"):
        return True
    try:
        return _hasher.check_needs_rehash(hashed)
    except argon2_exceptions.InvalidHashError:
        return True


# A hash to verify against when there is no account, so a wrong email costs the
# same time as a wrong password (no account enumeration by timing).
DUMMY_HASH = hash_password("bhojango-dummy-password-never-matches")


# ── breached passwords ───────────────────────────────────────────────────────

class BreachChecker(Protocol):
    async def times_seen(self, password: str) -> int | None:
        """How often the password appears in known breaches; None = couldn't check."""
        ...


class PwnedPasswords:
    """https://haveibeenpwned.com/API/v3#PwnedPasswords (free, no key)."""

    URL = "https://api.pwnedpasswords.com/range/{prefix}"
    TIMEOUT_SECONDS = 2.0

    async def times_seen(self, password: str) -> int | None:
        digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()  # noqa: S324 - the API's format
        prefix, suffix = digest[:5], digest[5:]
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT_SECONDS) as client:
                r = await client.get(self.URL.format(prefix=prefix),
                                     headers={"Add-Padding": "true", "User-Agent": "bhojango-password-check"})
                r.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("breach_check_unavailable", error=type(e).__name__)
            return None
        for line in r.text.splitlines():
            head, _, count = line.strip().partition(":")
            if head == suffix:
                try:
                    return int(count)
                except ValueError:
                    return None
        return 0


_checker: BreachChecker = PwnedPasswords()


def set_breach_checker(checker: BreachChecker) -> BreachChecker:
    """Swap the checker (tests); returns the previous one."""
    global _checker
    previous, _checker = _checker, checker
    return previous


def get_breach_checker() -> BreachChecker:
    return _checker


# ── rules for a new password ─────────────────────────────────────────────────

TOO_SHORT = "PASSWORD_TOO_SHORT"
TOO_LONG = "PASSWORD_TOO_LONG"
LIKE_EMAIL = "PASSWORD_LIKE_EMAIL"
BREACHED = "PASSWORD_BREACHED"


async def validate_new_password(password: str, *, email: str | None) -> None:
    """Raise PasswordRejected unless ``password`` may be set. Length counts characters
    (so 10 Devanagari letters are fine); no composition rules (NIST SP 800-63B)."""
    pw = _normalise(password or "")
    if len(pw) < MIN_LENGTH:
        raise PasswordRejected(TOO_SHORT, f"Use at least {MIN_LENGTH} characters.")
    if len(pw) > MAX_LENGTH:
        raise PasswordRejected(TOO_LONG, f"Use at most {MAX_LENGTH} characters.")
    if email:
        address = email.strip().lower()
        lowered = pw.lower()
        if address in lowered or lowered == address.split("@", 1)[0]:
            raise PasswordRejected(LIKE_EMAIL, "Choose a password that isn't your email address.")
    seen = await _checker.times_seen(pw)
    if seen:
        logger.info("password_rejected_breached")
        raise PasswordRejected(BREACHED, "This password has appeared in a data breach. Choose a different one.")
