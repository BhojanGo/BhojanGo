import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    country: str,
) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expire_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    expire = datetime.now(UTC) + timedelta(seconds=expire_seconds)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "country": country,
        "type": "access",
        "iat": datetime.now(UTC),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expire_seconds


def create_refresh_token(user_id: str) -> tuple[str, int]:
    """Returns (token, expires_in_seconds)."""
    expire_seconds = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    expire = datetime.now(UTC) + timedelta(seconds=expire_seconds)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(UTC),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expire_seconds


def decode_token(token: str) -> dict:
    """Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)
