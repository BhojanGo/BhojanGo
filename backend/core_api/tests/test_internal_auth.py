"""Signed realtime -> core_api calls (P14)."""
import time

import pytest

from shared import internal_auth
from shared.internal_auth import InternalAuthError


def test_signed_request_verifies() -> None:
    h = internal_auth.sign("POST", "/api/v1/internal/orders/x/assign-rider", b'{"rider_id":"r"}')
    internal_auth.verify("POST", "/api/v1/internal/orders/x/assign-rider", b'{"rider_id":"r"}',
                         h["X-Internal-Timestamp"], h["X-Internal-Signature"])


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/v1/internal/orders/x/assign-rider", b'{"rider_id":"r"}'),   # other method
    ("POST", "/api/v1/internal/orders/y/assign-rider", b'{"rider_id":"r"}'),  # other order
    ("POST", "/api/v1/internal/orders/x/assign-rider", b'{"rider_id":"s"}'),  # other rider
])
def test_tampering_is_refused(method: str, path: str, body: bytes) -> None:
    h = internal_auth.sign("POST", "/api/v1/internal/orders/x/assign-rider", b'{"rider_id":"r"}')
    with pytest.raises(InternalAuthError):
        internal_auth.verify(method, path, body, h["X-Internal-Timestamp"], h["X-Internal-Signature"])


def test_missing_and_stale_signatures_are_refused() -> None:
    with pytest.raises(InternalAuthError):
        internal_auth.verify("GET", "/p", b"", None, None)
    old = int(time.time()) - 600
    h = internal_auth.sign("GET", "/p", b"", ts=old)
    with pytest.raises(InternalAuthError, match="stale"):
        internal_auth.verify("GET", "/p", b"", h["X-Internal-Timestamp"], h["X-Internal-Signature"])


def test_production_refuses_the_local_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import get_settings

    s = get_settings()
    monkeypatch.setattr(type(s), "is_production", property(lambda self: True))
    monkeypatch.setattr(s, "INTERNAL_SERVICE_SECRET", internal_auth.LOCAL_DEFAULT)
    with pytest.raises(InternalAuthError, match="production"):
        internal_auth.sign("GET", "/p", b"")
