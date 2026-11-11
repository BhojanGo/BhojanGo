import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from passlib.context import CryptContext

from shared.auth import decode_jwt, encode_jwt
from shared.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    email: str | None,
    role: str,
    country: str,
    admin: list[str] | None = None,
) -> tuple[str, int]:
    """Returns (token, expires_in_seconds). RS256, 15 minutes by default.

    ``admin`` holds the user's admin role assignments as "role@scope" so other
    deployables can authorise without a database call (shared/authz.py)."""
    expire_seconds = settings.identity.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email or "",
        "role": role,
        "country": country,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expire_seconds),
        "jti": str(uuid.uuid4()),
    }
    if admin:
        payload["adm"] = admin
    return encode_jwt(payload), expire_seconds


def create_refresh_token(user_id: str, family: str | None = None) -> tuple[str, str, str, int]:
    """Returns (token, jti, family, expires_in_seconds).

    Refresh tokens rotate: each use returns a new one in the same family, and
    reusing an old one revokes the whole family (service/auth.py)."""
    expire_seconds = settings.identity.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    family = family or str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "type": "refresh",
        "fam": family,
        "iat": now,
        "exp": now + timedelta(seconds=expire_seconds),
        "jti": jti,
    }
    return encode_jwt(payload), jti, family, expire_seconds


def decode_token(token: str) -> dict:
    """Decode any identity token (access or refresh). Raises InvalidTokenError."""
    return decode_jwt(token)


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)
