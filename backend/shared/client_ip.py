"""The client's address, for rate limits and request logs.

Behind a platform proxy the socket's peer is the proxy, so every user would share
one address (and one sign-in or OTP rate limit). Railway's edge puts the client's
address in X-Real-IP and replaces whatever a client sent in it (verified on QA,
2026-11-14); its X-Forwarded-For ends in edge hops, not the client. Set
CLIENT_IP_HEADER=X-Real-IP there. Unset (local, tests): the socket's peer.
Only set it where the app is reachable through that proxy alone.
"""
from starlette.requests import Request

from shared.config import get_settings


def client_ip(request: Request) -> str:
    header = get_settings().CLIENT_IP_HEADER
    if header:
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    return request.client.host if request.client else "unknown"
