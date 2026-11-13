"""The Redis Streams event bus (EVENT_BUS=redis, Railway): what SNS/SQS gave
us, kept. Every consumer group gets each event; a failed handler sees it again;
an event that keeps failing goes to the dead-letter stream; realtime skips
payment events as its SQS subscription did."""
import asyncio

import fakeredis
import pytest

from shared import bus
from shared.config import get_settings


@pytest.fixture
def redis(monkeypatch):  # type: ignore[no-untyped-def]
    server = fakeredis.FakeServer()
    sync = fakeredis.FakeRedis(server=server, decode_responses=True)
    s = get_settings()
    monkeypatch.setattr(s, "EVENT_BUS", "redis")
    monkeypatch.setattr(s, "EVENT_BUS_STREAM", "test:events")
    monkeypatch.setattr(s, "EVENT_BUS_RETRY_IDLE_MS", 50)
    monkeypatch.setattr(s, "EVENT_BUS_MAX_DELIVERIES", 3)
    monkeypatch.setattr(bus, "_sync", sync)
    monkeypatch.setattr(bus, "_async_client", lambda: fakeredis.aioredis.FakeRedis(server=server, decode_responses=True))
    return sync


async def run_until(group: str, handle, done, skip=()) -> None:  # type: ignore[no-untyped-def]
    stop = asyncio.Event()

    async def watch() -> None:
        for _ in range(200):
            if done():
                break
            await asyncio.sleep(0.05)
        stop.set()

    await asyncio.gather(watch(), bus.consume(group, handle, skip_families=skip, running=lambda: not stop.is_set(), block_ms=50))


def event(kind: str, n: int) -> dict:
    return {"event_id": f"e{n}", "event_type": kind, "payload": {"n": n}}


async def test_every_group_gets_every_event_and_realtime_skips_payments(redis) -> None:  # type: ignore[no-untyped-def]
    for i, kind in enumerate(["order.placed", "payment.succeeded", "driver.assigned"]):
        bus.publish(event(kind, i))
    worker: list[str] = []
    realtime: list[str] = []

    async def w(e: dict) -> None:
        worker.append(e["event_type"])

    async def r(e: dict) -> None:
        realtime.append(e["event_type"])

    await run_until("worker", w, lambda: len(worker) == 3)
    await run_until("realtime", r, lambda: len(realtime) == 2, skip={"payment"})
    assert worker == ["order.placed", "payment.succeeded", "driver.assigned"]
    assert realtime == ["order.placed", "driver.assigned"]
    for group in ("worker", "realtime"):  # everything acknowledged, payments included
        assert redis.xpending("test:events", group)["pending"] == 0


async def test_a_failed_handler_gets_the_event_again(redis) -> None:  # type: ignore[no-untyped-def]
    bus.publish(event("order.placed", 1))
    calls: list[int] = []

    async def flaky(e: dict) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database blip")

    await run_until("worker", flaky, lambda: len(calls) == 2)
    assert len(calls) == 2
    assert redis.xpending("test:events", "worker")["pending"] == 0
    assert redis.xlen("test:events:dlq") == 0


async def test_an_event_that_keeps_failing_goes_to_the_dead_letter_stream(redis) -> None:  # type: ignore[no-untyped-def]
    bus.publish(event("order.placed", 1))
    bus.publish(event("order.placed", 2))
    good: list[int] = []

    async def poison(e: dict) -> None:
        if e["payload"]["n"] == 1:
            raise RuntimeError("never works")
        good.append(e["payload"]["n"])

    await run_until("worker", poison, lambda: redis.exists("test:events:dlq") and redis.xlen("test:events:dlq") == 1)
    assert good == [2]  # the bad one didn't hold up the next
    dead = redis.xrange("test:events:dlq")
    assert len(dead) == 1 and dead[0][1]["group"] == "worker"
    assert redis.xpending("test:events", "worker")["pending"] == 0


def test_publish_caps_the_stream(redis, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Every XADD carries MAXLEN ~ so Redis memory stays bounded (Redis trims whole nodes)."""
    monkeypatch.setattr(get_settings(), "EVENT_BUS_MAXLEN", 1234)
    seen: dict = {}
    real = redis.xadd

    def spy(name, fields, **kw):  # type: ignore[no-untyped-def]
        seen.update(kw)
        return real(name, fields, **kw)

    monkeypatch.setattr(redis, "xadd", spy)
    bus.publish(event("order.placed", 1))
    assert seen == {"maxlen": 1234, "approximate": True}
