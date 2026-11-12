"""Service-to-service calls (P14): realtime -> core_api internal endpoints.

Requests carry ``X-Internal-Timestamp`` and ``X-Internal-Signature``: an
HMAC-SHA256, with INTERNAL_SERVICE_SECRET, of "timestamp\\nMETHOD\\npath\\nbody".
Signatures older than five minutes are refused (replays). Production refuses
the local default secret.
"""
import hashlib
import hmac
import time

from shared.config import get_settings

LOCAL_DEFAULT = "local-internal-secret"  # placeholder for docker compose and tests
MAX_SKEW_SECONDS = 300


class InternalAuthError(Exception):
    pass


def _secret() -> bytes:
    s = get_settings()
    secret = s.INTERNAL_SERVICE_SECRET
    if s.is_production and (not secret or secret == LOCAL_DEFAULT):
        raise InternalAuthError("INTERNAL_SERVICE_SECRET must be set in production")
    return secret.encode()


def sign(method: str, path: str, body: bytes, ts: int | None = None) -> dict[str, str]:
    ts = ts or int(time.time())
    msg = f"{ts}\n{method.upper()}\n{path}\n".encode() + body
    return {"X-Internal-Timestamp": str(ts), "X-Internal-Signature": hmac.new(_secret(), msg, hashlib.sha256).hexdigest()}


def verify(method: str, path: str, body: bytes, timestamp: str | None, signature: str | None) -> None:
    if not timestamp or not signature:
        raise InternalAuthError("missing signature")
    try:
        ts = int(timestamp)
    except ValueError:
        raise InternalAuthError("bad timestamp")
    if abs(time.time() - ts) > MAX_SKEW_SECONDS:
        raise InternalAuthError("stale signature")
    expected = sign(method, path, body, ts)["X-Internal-Signature"]
    if not hmac.compare_digest(expected, signature):
        raise InternalAuthError("bad signature")
