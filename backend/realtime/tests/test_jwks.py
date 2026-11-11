"""realtime verifies core_api's RS256 tokens with the published JWKS."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from shared import jwt_keys
from shared.auth import InvalidTokenError, decode_access_token
from shared.config import get_settings

CORE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = jwt_keys.public_jwk(CORE_KEY.public_key())


def token(key=CORE_KEY, kid=JWK["kid"], **extra) -> str:
    now = int(time.time())
    claims = {"sub": "5b0c8a3e-0000-4000-8000-000000000001", "type": "access", "role": "driver", "country": "IN",
              "iss": "bhojango", "aud": "bhojango", "iat": now, "exp": now + 900, **extra}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def jwks_url(monkeypatch):
    calls = []

    class Resp:
        def json(self):
            return {"keys": [JWK]}

    def fake_get(url, timeout):
        calls.append(url)
        return Resp()

    monkeypatch.setattr(get_settings(), "JWKS_URL", "http://core-api:8001/.well-known/jwks.json")
    monkeypatch.setattr(jwt_keys.httpx, "get", fake_get)
    monkeypatch.setattr(jwt_keys, "_remote", jwt_keys._RemoteJwks())
    jwt_keys._static_public_keys.cache_clear()
    yield calls
    jwt_keys._static_public_keys.cache_clear()


def test_token_verified_via_jwks_and_cached(jwks_url) -> None:
    assert decode_access_token(token())["role"] == "driver"
    decode_access_token(token())
    assert jwks_url == ["http://core-api:8001/.well-known/jwks.json"]  # fetched once


def test_wrong_key_or_unknown_kid_rejected(jwks_url) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidTokenError):
        decode_access_token(token(key=other))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token(kid="nope"))


def test_expired_or_wrong_audience_rejected(jwks_url) -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token(token(exp=int(time.time()) - 10))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token(aud="someone-else"))


def test_realtime_never_signs_when_using_jwks(jwks_url) -> None:
    # With JWKS_URL and no private key, this process trusts only published keys.
    assert jwt_keys._has_signing_key() is False
