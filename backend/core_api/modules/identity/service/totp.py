"""Time-based one-time codes (RFC 6238) and recovery codes for admin two-step sign-in.

- Secrets: 160 random bits, base32 (what authenticator apps expect), stored
  encrypted (Fernet; keys in IDENTITY_DATA_KEYS, the first one encrypts, all
  decrypt, so keys can be rotated).
- Codes: HMAC-SHA1, 6 digits, 30-second steps; one step of clock drift either
  way is accepted, and a step is never accepted twice (the caller stores the last
  accepted step: RFC 6238 section 5.2).
- Recovery codes: 10 random codes of 10 characters, shown once, stored as SHA-256
  (they carry 50 random bits, so a fast hash is enough), each usable once.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from shared.config import get_settings

STEP_SECONDS = 30
DIGITS = 6
DRIFT_STEPS = 1
ISSUER = "BhojanGo"
RECOVERY_CODES = 10
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_SECONDS)


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10 ** DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, *, last_step: int | None = None, now: float | None = None) -> int | None:
    """The step ``code`` belongs to (within the drift window and after ``last_step``), else None."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    step = current_step(now)
    found = None
    for candidate in range(step - DRIFT_STEPS, step + DRIFT_STEPS + 1):
        # Compare every candidate (constant work whichever one matches).
        if hmac.compare_digest(code_at(secret, candidate), code) and found is None:
            found = candidate
    if found is None or (last_step is not None and found <= last_step):
        return None
    return found


def otpauth_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    query = urlencode({"secret": secret, "issuer": ISSUER, "algorithm": "SHA1", "digits": DIGITS, "period": STEP_SECONDS})
    return f"otpauth://totp/{label}?{query}"


def qr_svg_data_uri(text: str) -> str:
    """The otpauth URI as a QR code (SVG data URI) for the enrolment screen."""
    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0B1F24", light="#FFFFFF",
                                     xmldecl=False, svgns=True)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


# ── secrets at rest ──────────────────────────────────────────────────────────

_DEV_KEY_SEED = b"bhojango-local-identity-data-key (never used in production)"


def _fernet() -> MultiFernet:
    settings = get_settings()
    keys = [k for k in settings.identity.IDENTITY_DATA_KEYS if k]
    if not keys:
        if settings.production_named:
            raise RuntimeError("IDENTITY_DATA_KEYS is not set: two-step secrets can't be stored in production")
        keys = [base64.urlsafe_b64encode(hashlib.sha256(_DEV_KEY_SEED).digest()).decode("ascii")]
    return MultiFernet([Fernet(k.encode("ascii")) for k in keys])


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError):
        return None


# ── recovery codes ───────────────────────────────────────────────────────────

def generate_recovery_codes(n: int = RECOVERY_CODES) -> list[str]:
    codes = []
    for _ in range(n):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalise_recovery_code(code: str) -> str:
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(normalise_recovery_code(code).encode("ascii", "ignore")).hexdigest()
