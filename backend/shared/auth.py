"""JWT access-token verification shared by every module and deployable.

Before P1 each service had its own copy of this check (restaurant, order,
payment, delivery and notification core/auth.py). The checks were identical:
decode with JWT_SECRET/JWT_ALGORITHM, require a ``sub`` claim and
``type == "access"``. What differed was the HTTP error each service returned,
which is part of the API contract, so modules keep their own FastAPI
dependency (``api/dependencies.py``) and turn :class:`InvalidTokenError` into
the same 401 they returned before.
"""
import uuid

from jose import JWTError, jwt

from shared.config import get_settings

settings = get_settings()


class InvalidTokenError(Exception):
    """The bearer token is missing, malformed, expired or not an access token."""


def decode_jwt(token: str) -> dict:
    """Decode and verify a token's signature and expiry. Raises JWTError."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def decode_access_token(token: str) -> dict:
    """Return the claims of a valid access token, or raise InvalidTokenError."""
    try:
        payload = decode_jwt(token)
    except JWTError as exc:
        raise InvalidTokenError from exc
    if not payload.get("sub", "") or payload.get("type") != "access":
        raise InvalidTokenError
    return payload


class CurrentUser:
    """The caller, as described by their access-token claims."""

    def __init__(self, user_id: str, role: str, country: str, email: str = "") -> None:
        self.user_id = user_id
        self.email = email
        self.role = role
        self.country = country
        self.id = uuid.UUID(user_id)

    @classmethod
    def from_claims(cls, payload: dict) -> "CurrentUser":
        return cls(
            user_id=payload["sub"],
            email=payload.get("email", ""),
            role=payload.get("role", "customer"),
            country=payload.get("country", "US"),
        )
