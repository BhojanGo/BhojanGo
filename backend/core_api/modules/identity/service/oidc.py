"""Verify Sign in with Apple and Google identity tokens (OpenID Connect).

Both are RS256 JWTs signed by the provider. We check the signature against
the provider's published keys (JWKS), the issuer, our client id as audience,
and expiry. No provider account is needed to verify; the client ids
(GOOGLE_CLIENT_IDS / APPLE_CLIENT_IDS) come from the app configuration.
"""
import json
import time
from dataclasses import dataclass

import httpx
import jwt
import structlog
from jwt.algorithms import RSAAlgorithm

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Provider:
    name: str
    jwks_url: str
    issuers: tuple[str, ...]


GOOGLE = Provider("google", "https://www.googleapis.com/oauth2/v3/certs", ("https://accounts.google.com", "accounts.google.com"))
APPLE = Provider("apple", "https://appleid.apple.com/auth/keys", ("https://appleid.apple.com",))
PROVIDERS = {"google": GOOGLE, "apple": APPLE}


class OidcError(ValueError):
    pass


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None
    email_verified: bool
    name: str | None


_cache: dict[str, tuple[float, dict[str, object]]] = {}
CACHE_SECONDS = 3600


async def _keys(provider: Provider, *, refresh: bool = False) -> dict[str, object]:
    cached = _cache.get(provider.name)
    if cached and not refresh and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    async with httpx.AsyncClient(timeout=5) as client:
        data = (await client.get(provider.jwks_url)).json()
    keys = {k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k)) for k in data.get("keys", [])}
    _cache[provider.name] = (time.monotonic(), keys)
    return keys


async def verify(provider_name: str, token: str, audiences: list[str]) -> Identity:
    provider = PROVIDERS[provider_name]
    if not audiences:
        raise OidcError(f"{provider_name} sign-in is not configured (no client ids)")
    try:
        kid = jwt.get_unverified_header(token).get("kid", "")
    except jwt.PyJWTError as e:
        raise OidcError("malformed token") from e
    keys = await _keys(provider)
    if kid not in keys:  # provider rotated its keys
        keys = await _keys(provider, refresh=True)
    key = keys.get(kid)
    if key is None:
        raise OidcError("unknown signing key")
    try:
        claims = jwt.decode(
            token, key, algorithms=["RS256"], audience=audiences, issuer=list(provider.issuers),  # type: ignore[arg-type]
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as e:
        raise OidcError(str(e)) from e
    verified = claims.get("email_verified")
    return Identity(
        subject=str(claims["sub"]),
        email=(claims.get("email") or None),
        # Apple sends "true"/"false" strings; Google sends booleans.
        email_verified=verified is True or verified == "true",
        name=claims.get("name"),
    )
