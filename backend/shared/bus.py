"""The event bus behind the outbox: AWS SNS/SQS, or Redis Streams.

``EVENT_BUS=aws`` (the default; AWS and LocalStack): the worker's outbox relay
publishes to SNS topics, which fan out to SQS queues for the worker
(notifications) and realtime (dispatch, tracking).

``EVENT_BUS=redis`` (Railway, or anywhere without SNS/SQS): one Redis stream
holds every event, and each consumer is a Redis consumer group with the same
behaviour the SQS queues had:

- at-least-once: an entry is acknowledged only after it was handled, and
  consumers dedupe by ``event_id`` as before;
- retries: an entry left unacknowledged for ``EVENT_BUS_RETRY_IDLE_MS`` is
  claimed again (``XAUTOCLAIM``); after ``EVENT_BUS_MAX_DELIVERIES`` it goes to
  the dead-letter stream (``<stream>:dlq``), like the SQS redrive policy;
- the same routing: the worker group gets everything, realtime gets every
  family but ``payment``, as the SNS subscriptions did.

The outbox table stays the source of truth: an event is in the stream only
after its change committed, and the stream is capped (``MAXLEN ~``) so Redis
memory stays bounded.
"""
import asyncio
import json
import socket
from collections.abc import Awaitable, Callable, Iterable

import redis
import redis.asyncio as aredis
import structlog

from shared.config import get_settings

logger = structlog.get_logger(__name__)

Handler = Callable[[dict], Awaitable[None]]

_sync: redis.Redis | None = None


def kind() -> str:
    return get_settings().EVENT_BUS


def is_redis() -> bool:
    return kind() == "redis"


def _url() -> str:
    s = get_settings()
    return s.EVENT_BUS_REDIS_URL or s.REDIS_URL


def stream() -> str:
    return get_settings().EVENT_BUS_STREAM


def dlq() -> str:
    return f"{stream()}:dlq"


def _client() -> redis.Redis:
    global _sync
    if _sync is None:
        _sync = redis.Redis.from_url(_url(), password=get_settings().REDIS_PASSWORD or None, decode_responses=True)
    return _sync


def _async_client() -> aredis.Redis:
    """A connection of its own for one consumer loop (it blocks on XREADGROUP)."""
    return aredis.Redis.from_url(_url(), password=get_settings().REDIS_PASSWORD or None, decode_responses=True)


def publish(envelope: dict) -> str:
    """Add one event to the stream (blocking; the relay runs it in a thread)."""
    return _client().xadd(stream(), {"event": json.dumps(envelope)},
                          maxlen=get_settings().EVENT_BUS_MAXLEN, approximate=True)


def configured() -> bool:
    """What the health checks report: is there somewhere for events to go?"""
    s = get_settings()
    if is_redis():
        return bool(_url())
    return bool(s.worker.SQS_QUEUE_URL_NOTIFICATION)


def family(event: dict) -> str:
    return str(event.get("event_type", "")).split(".", 1)[0]


async def consume(group: str, handle: Handler, *, skip_families: Iterable[str] = (),
                  running: Callable[[], bool] = lambda: True, block_ms: int = 5000) -> None:
    """Read the stream as consumer group ``group`` until ``running()`` is false.

    Each process is its own consumer in the group, so several replicas share
    the work. Entries this consumer was given but didn't acknowledge (a crash,
    a failed handler) are claimed again after the retry idle time."""
    s = get_settings()
    skip = set(skip_families)
    r = _async_client()
    name = f"{s.SERVICE_NAME}-{s.EVENT_BUS_CONSUMER or socket.gethostname()}"
    try:
        await r.xgroup_create(stream(), group, id="0", mkstream=True)
    except aredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
    logger.info("event_bus_consumer_started", stream=stream(), group=group, consumer=name)

    async def handle_entry(entry_id: str, fields: dict) -> None:
        try:
            event = json.loads(fields.get("event", "{}"))
        except ValueError:
            logger.error("event_bus_bad_entry", id=entry_id)
            await r.xack(stream(), group, entry_id)
            return
        if family(event) not in skip:
            await handle(event)  # raises -> not acknowledged -> retried
        await r.xack(stream(), group, entry_id)

    async def run_batch(entries: list) -> None:
        for entry_id, fields in entries:
            if fields is None:  # trimmed away while pending
                await r.xack(stream(), group, entry_id)
                continue
            try:
                await handle_entry(entry_id, fields)
            except Exception as e:  # noqa: BLE001 - left pending; claimed again later
                logger.error("event_bus_handler_failed", group=group, id=entry_id, error=str(e))

    while running():
        try:
            # 1. Retries: entries idle too long (ours or a dead replica's).
            _, claimed, *_ = await r.xautoclaim(stream(), group, name, min_idle_time=s.EVENT_BUS_RETRY_IDLE_MS,
                                                start_id="0-0", count=20)
            if claimed:
                dead = await _dead_letter(r, group, claimed)
                await run_batch([c for c in claimed if c[0] not in dead])
            # 2. New entries.
            resp = await r.xreadgroup(group, name, {stream(): ">"}, count=20, block=block_ms)
            for _, entries in resp or []:
                await run_batch(entries)
            await asyncio.sleep(0)  # let other tasks run even if Redis answers at once
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - Redis blips: try again shortly
            logger.error("event_bus_poll_error", group=group, error=str(e))
            await asyncio.sleep(2)
    await r.aclose()


async def _dead_letter(r: aredis.Redis, group: str, claimed: list) -> set[str]:
    """Entries delivered too many times go to the dead-letter stream; returns their ids."""
    s = get_settings()
    dead: set[str] = set()
    ids = [c[0] for c in claimed]
    info = await r.xpending_range(stream(), group, min=ids[0], max=ids[-1], count=len(ids) + 50)
    times = {p["message_id"]: p["times_delivered"] for p in info}
    for entry_id, fields in claimed:
        if times.get(entry_id, 0) > s.EVENT_BUS_MAX_DELIVERIES:
            await r.xadd(dlq(), {**(fields or {}), "group": group, "id": entry_id}, maxlen=10000, approximate=True)
            await r.xack(stream(), group, entry_id)
            dead.add(entry_id)
            logger.error("event_bus_dead_letter", group=group, id=entry_id)
    return dead
