"""Limits on the realtime WebSockets (R22 security review, S10).

* A socket lives only as long as the token it opened with: at the token's
  ``exp`` it is closed with code 4401, and the client reconnects with a fresh
  token (the apps) or a fresh socket ticket (the website). Before, a socket
  outlived its 15-minute token, a sign-out and a removed admin role.
* Each process holds at most ``WS_MAX_PER_USER`` sockets per account and
  ``WS_MAX_PER_IP`` per client address; one more is refused with 4429.

The counts are per process (one realtime process today). With more than one,
each process applies the caps to its own sockets.
"""
import asyncio
import time
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import WebSocket

from shared.client_ip import client_ip
from shared.config import get_settings

logger = structlog.get_logger(__name__)

TOKEN_EXPIRED = 4401  # the clients reconnect with a fresh token
NOT_ALLOWED = 4403    # e.g. the order's rider changed and this socket's rider isn't on it any more
TOO_MANY = 4429


class TooManySockets(Exception):
    pass


class Limits:
    def __init__(self) -> None:
        self.by_user: Counter[str] = Counter()
        self.by_ip: Counter[str] = Counter()

    @asynccontextmanager
    async def hold(self, user_id: str, ip: str) -> AsyncIterator[None]:
        s = get_settings().realtime
        if s.WS_MAX_PER_USER and self.by_user[user_id] >= s.WS_MAX_PER_USER:
            logger.warning("ws_refused_too_many", per="user", user_id=user_id)
            raise TooManySockets("user")
        if s.WS_MAX_PER_IP and self.by_ip[ip] >= s.WS_MAX_PER_IP:
            logger.warning("ws_refused_too_many", per="ip")
            raise TooManySockets("ip")
        self.by_user[user_id] += 1
        self.by_ip[ip] += 1
        try:
            yield
        finally:
            for c, k in ((self.by_user, user_id), (self.by_ip, ip)):
                c[k] -= 1
                if c[k] <= 0:
                    del c[k]


limits = Limits()


def address(websocket: WebSocket) -> str:
    return client_ip(websocket)  # type: ignore[arg-type]  # headers and client: all it reads


async def close_at(websocket: WebSocket, exp: int | None) -> None:
    """Close the socket with 4401 when its token expires (a task, cancelled when the socket ends)."""
    if exp is None:
        await websocket.close(code=TOKEN_EXPIRED, reason="Token expired")
        return
    await asyncio.sleep(max(0.0, exp - time.time()))
    logger.info("ws_token_expired")
    try:
        await websocket.close(code=TOKEN_EXPIRED, reason="Token expired")
    except RuntimeError:
        pass  # already closed
