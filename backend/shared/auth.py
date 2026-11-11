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

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import JWTError, jwt
from starlette.requests import HTTPConnection

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


class BearerAuth(HTTPBearer):
    """HTTPBearer that keeps the API's original responses for a missing token.

    FastAPI 0.115+ answers a missing or non-Bearer Authorization header with 401
    + WWW-Authenticate; FastAPI 0.111 (what the API shipped with) answered 403.
    The upgrade in P3 must not change the API contract, so this keeps 403.
    """

    async def __call__(self, request: HTTPConnection) -> HTTPAuthorizationCredentials | None:  # type: ignore[override]
        authorization = request.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(authorization)
        if not (authorization and scheme and credentials):
            if self.auto_error:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated")
            return None
        if scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Invalid authentication credentials"
                )
            return None
        return HTTPAuthorizationCredentials(scheme=scheme, credentials=credentials)
