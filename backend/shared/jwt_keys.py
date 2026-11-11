"""RS256 keys for access and refresh tokens, and the JWKS that publishes them.

Signing (core_api only): ``JWT_PRIVATE_KEY`` (PEM; from Secrets Manager in
AWS). Outside production, when it is empty, a development key is created once
at ``JWT_DEV_KEY_PATH`` and reused, so tokens survive restarts (compose keeps
it on a volume). Production refuses to start without a configured key.

Verification (every deployable): the local signing key if this process has
one, any ``JWT_PUBLIC_KEYS`` (PEMs, e.g. the previous key during rotation),
and the keys published at ``JWKS_URL`` (realtime and worker point it at
core_api's ``/.well-known/jwks.json``), cached and refetched when an unknown
``kid`` shows up.
"""
import base64
import hashlib
import json
import os
import threading
import time
from functools import lru_cache
from pathlib import Path

import httpx
import structlog
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from shared.config import get_settings

logger = structlog.get_logger(__name__)

ALGORITHM = "RS256"
JWKS_CACHE_SECONDS = 600
JWKS_MIN_REFETCH_SECONDS = 30


class KeyConfigError(RuntimeError):
    pass


def _b64(n: int) -> str:
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def public_jwk(key: RSAPublicKey) -> dict:
    nums = key.public_numbers()
    jwk = {"kty": "RSA", "e": _b64(nums.e), "n": _b64(nums.n)}
    # RFC 7638 thumbprint as the key id: stable, no config needed.
    thumb = hashlib.sha256(json.dumps(jwk, separators=(",", ":"), sort_keys=True).encode()).digest()
    return {**jwk, "kid": base64.urlsafe_b64encode(thumb).rstrip(b"=").decode()[:16], "use": "sig", "alg": ALGORITHM}


def _load_private(pem: str) -> RSAPrivateKey:
    key = serialization.load_pem_private_key(pem.replace("\\n", "\n").encode(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise KeyConfigError("JWT_PRIVATE_KEY must be an RSA private key")
    return key


def _dev_key() -> RSAPrivateKey:
    path = Path(get_settings().JWT_DEV_KEY_PATH)
    if path.exists():
        return _load_private(path.read_text())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_bytes(pem)
    try:
        os.replace(tmp, path)  # atomic; if two processes race, one key wins
    except OSError:
        tmp.unlink(missing_ok=True)
    logger.warning("jwt_dev_key_created", path=str(path))
    return _load_private(path.read_text())


@lru_cache
def signing_key() -> tuple[RSAPrivateKey, str]:
    """(private key, kid). Raises KeyConfigError in production without a key."""
    s = get_settings()
    if s.JWT_PRIVATE_KEY:
        key = _load_private(s.JWT_PRIVATE_KEY)
    elif s.is_production:
        raise KeyConfigError("JWT_PRIVATE_KEY is required in production")
    else:
        key = _dev_key()
    return key, public_jwk(key.public_key())["kid"]


def _has_signing_key() -> bool:
    s = get_settings()
    return bool(s.JWT_PRIVATE_KEY) or (not s.is_production and not s.JWKS_URL)


@lru_cache
def _static_public_keys() -> dict[str, RSAPublicKey]:
    keys: dict[str, RSAPublicKey] = {}
    for pem in get_settings().JWT_PUBLIC_KEYS:
        k = serialization.load_pem_public_key(pem.replace("\\n", "\n").encode())
        if isinstance(k, RSAPublicKey):
            keys[public_jwk(k)["kid"]] = k
    if _has_signing_key():
        priv, kid = signing_key()
        keys[kid] = priv.public_key()
    return keys


def jwks() -> dict:
    """What core_api publishes at /.well-known/jwks.json."""
    return {"keys": [public_jwk(k) for k in _static_public_keys().values()]}


class _RemoteJwks:
    def __init__(self) -> None:
        self._keys: dict[str, RSAPublicKey] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def get(self, kid: str) -> RSAPublicKey | None:
        url = get_settings().JWKS_URL
        if not url:
            return None
        age = time.monotonic() - self._fetched_at
        if kid not in self._keys or age > JWKS_CACHE_SECONDS:
            if age > JWKS_MIN_REFETCH_SECONDS or not self._keys:
                self._refresh(url)
        return self._keys.get(kid)

    def _refresh(self, url: str) -> None:
        from jwt.algorithms import RSAAlgorithm

        with self._lock:
            try:
                data = httpx.get(url, timeout=5).json()
                self._keys = {k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k)) for k in data.get("keys", [])}  # type: ignore[misc]
                self._fetched_at = time.monotonic()
            except Exception as e:  # noqa: BLE001 - keep the old keys, try again later
                logger.error("jwks_fetch_failed", url=url, error=str(e))
                self._fetched_at = time.monotonic()


_remote = _RemoteJwks()


def verification_key(kid: str) -> RSAPublicKey | None:
    return _static_public_keys().get(kid) or _remote.get(kid)
