"""One Redis pub/sub connection per realtime process, shared by every WebSocket (P24).

Before, each tracking or rider socket opened its own pub/sub connection: 200
people watching orders meant 200 Redis connections, the pool ran out ("Too many
connections") and rider location pings failed with it. And each socket's
listener broadcast to every socket on the order, so with two watchers each
message went out twice.

Now the hub subscribes to a channel when its first socket arrives and
unsubscribes when the last one leaves; one reader task hands each message to
the queues of that channel's sockets, and each socket sends only to itself.
"""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog

from app.core.redis import get_redis

logger = structlog.get_logger(__name__)
QUEUE_SIZE = 256  # a socket this far behind skips newer updates until it catches up (logged)


class Hub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[str]]] = {}
        self._pubsub = None  # type: ignore[var-annotated]
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def _start(self) -> None:
        if self._pubsub is None:
            self._pubsub = (await get_redis()).pubsub()
            await self._pubsub.subscribe("hub:alive")  # get_message needs a subscription to wait on
            self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        while True:
            try:
                msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - keep serving; the next read retries
                logger.warning("hub_read_failed", error=str(e))
                await asyncio.sleep(1)
                continue
            if not msg or msg.get("type") != "message":
                continue
            for q in list(self._subs.get(msg["channel"], ())):
                try:
                    q.put_nowait(msg["data"])
                except asyncio.QueueFull:
                    logger.warning("hub_socket_behind", channel=msg["channel"])

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator["asyncio.Queue[str]"]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_SIZE)
        async with self._lock:
            await self._start()
            first = channel not in self._subs
            self._subs.setdefault(channel, set()).add(q)
            if first:
                await self._pubsub.subscribe(channel)
        try:
            yield q
        finally:
            async with self._lock:
                subs = self._subs.get(channel)
                if subs is not None:
                    subs.discard(q)
                    if not subs:
                        del self._subs[channel]
                        await self._pubsub.unsubscribe(channel)

    def channels(self) -> int:
        return len(self._subs)


hub = Hub()
