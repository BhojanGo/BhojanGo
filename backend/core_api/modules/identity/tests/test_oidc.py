"""Google / Apple ID token verification, against a locally generated RSA key
and a fake JWKS (no network)."""
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from jwt.algorithms import RSAAlgorithm

from core_api.modules.identity.service import oidc

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
WEB = "1234-web.apps.googleusercontent.com"


def jwk(key, kid: str) -> dict:  # type: ignore[no-untyped-def]
    return {**json.loads(RSAAlgorithm.to_jwk(key.public_key())), "kid": kid, "alg": "RS256", "use": "sig"}


def token(*, key=KEY, kid="k1", iss="https://accounts.google.com", aud=WEB, exp_in=600, **extra) -> str:  # type: ignore[no-untyped-def]
    now = int(time.time())
    claims = {"iss": iss, "aud": aud, "sub": "1100220033", "iat": now, "exp": now + exp_in,
              "email": "priya@example.com", "email_verified": True, "name": "Priya Rao", **extra}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def jwks(monkeypatch):  # type: ignore[no-untyped-def]
    """The providers' keys endpoints, faked: serve `doc`, count fetches."""
    state = {"doc": {"keys": [jwk(KEY, "k1")]}, "fetches": 0, "fail": False}

    async def fetch(url: str) -> dict:
        assert url in (oidc.GOOGLE.jwks_url, oidc.APPLE.jwks_url)
        state["fetches"] += 1
        if state["fail"]:
            raise httpx.ConnectError("offline")
        return state["doc"]

    monkeypatch.setattr(oidc, "_fetch_jwks", fetch)
    oidc._cache.clear()
    yield state
    oidc._cache.clear()


async def test_valid_google_token(jwks) -> None:  # type: ignore[no-untyped-def]
    ident = await oidc.verify("google", token(), [WEB])
    assert (ident.subject, ident.email, ident.email_verified, ident.name) == (
        "1100220033", "priya@example.com", True, "Priya Rao")
    await oidc.verify("google", token(iss="accounts.google.com"), [WEB])  # the issuer without https://
    assert jwks["fetches"] == 1  # keys are cached


async def test_any_configured_audience(jwks) -> None:  # type: ignore[no-untyped-def]
    assert (await oidc.verify("google", token(aud="android-id"), [WEB, "android-id"])).subject == "1100220033"


@pytest.mark.parametrize("bad", [
    {"aud": "someone-elses-client"},
    {"iss": "https://evil.example.com"},
    {"exp_in": -60},
    {"key": OTHER},  # signed by someone else, claiming the provider's key id
    {"kid": "unknown"},
], ids=["audience", "issuer", "expired", "forged", "unknown-key"])
async def test_rejected(jwks, bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(oidc.OidcError):
        await oidc.verify("google", token(**bad), [WEB])


async def test_unconfigured_provider_is_off(jwks) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(oidc.OidcError, match="not configured"):
        await oidc.verify("google", token(), [])
    with pytest.raises(oidc.OidcError, match="not configured"):
        await oidc.verify("apple", token(iss="https://appleid.apple.com"), [])
    assert jwks["fetches"] == 0


async def test_key_rotation_refetches(jwks) -> None:  # type: ignore[no-untyped-def]
    await oidc.verify("google", token(), [WEB])
    jwks["doc"] = {"keys": [jwk(KEY, "k1"), jwk(OTHER, "k2")]}
    assert (await oidc.verify("google", token(key=OTHER, kid="k2"), [WEB])).subject == "1100220033"
    assert jwks["fetches"] == 2


async def test_keys_unreachable(jwks) -> None:  # type: ignore[no-untyped-def]
    jwks["fail"] = True
    with pytest.raises(oidc.OidcError, match="signing keys"):
        await oidc.verify("google", token(), [WEB])


async def test_malformed_token(jwks) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(oidc.OidcError):
        await oidc.verify("google", "not-a-jwt", [WEB])


def test_audiences_from_config() -> None:
    from shared.config import IdentitySettings

    s = IdentitySettings(GOOGLE_WEB_CLIENT_ID=WEB, GOOGLE_CLIENT_ID="legacy", GOOGLE_CLIENT_IDS=["ios", WEB])
    assert s.google_audiences == [WEB, "legacy", "ios"]
    assert s.google_web_client_id == WEB
    assert IdentitySettings(GOOGLE_CLIENT_ID="only").google_web_client_id == "only"
    assert IdentitySettings().apple_audiences == []  # Apple is off unless configured


async def test_providers_endpoint(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.config import get_settings

    ident = get_settings().identity
    for k in ("GOOGLE_WEB_CLIENT_ID", "GOOGLE_CLIENT_ID", "APPLE_CLIENT_ID"):
        monkeypatch.setattr(ident, k, "")
    assert (await client.get("/api/v1/auth/providers")).json() == {"google": None, "apple": None}
    monkeypatch.setattr(ident, "GOOGLE_WEB_CLIENT_ID", WEB)
    assert (await client.get("/api/v1/auth/providers")).json() == {"google": {"client_id": WEB}, "apple": None}


async def test_website_google_sign_in_end_to_end(client: AsyncClient, jwks, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The website's client id is accepted; a verified email creates a customer; signing in again finds them."""
    from shared.config import get_settings

    ident = get_settings().identity
    monkeypatch.setattr(ident, "GOOGLE_WEB_CLIENT_ID", WEB)
    t = token(sub="g-web-1", email="web.signin@example.com")
    r = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": t, "country": "IN"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_new_user"] is True and body["user"]["email"] == "web.signin@example.com"
    assert body["user"]["role"] == "customer"
    again = await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": t, "country": "IN"})
    assert again.json()["user"]["id"] == body["user"]["id"] and again.json()["is_new_user"] is False
    wrong = token(sub="g-web-2", aud="not-ours")
    assert (await client.post("/api/v1/auth/social-login", json={"provider": "google", "token": wrong})).status_code == 401
