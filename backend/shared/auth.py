"""JWT signing and verification shared by every module and deployable.

Tokens are RS256 (ADR-011): core_api signs with its private key and publishes
the public keys as a JWKS; realtime and worker verify with that JWKS
(shared/jwt_keys.py). Each module keeps its own FastAPI dependency
(``api/dependencies.py``) that turns :class:`InvalidTokenError` into the same
401 it always returned.
"""
import uuid

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import HTTPConnection

from shared import jwt_keys
from shared.config import get_settings

settings = get_settings()

ISSUER = "bhojango"
AUDIENCE = "bhojango"


class InvalidTokenError(Exception):
    """The token is missing, malformed, badly signed, expired or the wrong type."""


def encode_jwt(claims: dict) -> str:
    """Sign claims (core_api only). Adds iss and aud."""
    key, kid = jwt_keys.signing_key()
    return jwt.encode({**claims, "iss": ISSUER, "aud": AUDIENCE}, key, algorithm=jwt_keys.ALGORITHM, headers={"kid": kid})


def decode_jwt(token: str) -> dict:
    """Verify signature, expiry, issuer and audience. Raises InvalidTokenError."""
    try:
        kid = jwt.get_unverified_header(token).get("kid", "")
        key = jwt_keys.verification_key(kid)
        if key is None:
            raise InvalidTokenError(f"unknown key id {kid!r}")
        return jwt.decode(token, key, algorithms=[jwt_keys.ALGORITHM], audience=AUDIENCE, issuer=ISSUER)
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


def decode_access_token(token: str) -> dict:
    """Return the claims of a valid access token, or raise InvalidTokenError."""
    payload = decode_jwt(token)
    if not payload.get("sub", "") or payload.get("type") != "access":
        raise InvalidTokenError("not an access token")
    return payload


class CurrentUser:
    """The caller, as described by their access-token claims."""

    def __init__(self, user_id: str, role: str, country: str, email: str = "", admin: list[str] | None = None) -> None:
        self.user_id = user_id
        # Admin role assignments as "role@scope" (e.g. "city_ops@IN-TG-HYD"); see shared/authz.py.
        self.admin = admin or []
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
            admin=payload.get("adm", []),
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
