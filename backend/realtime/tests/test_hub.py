"""P24: the WebSocket hub shares one Redis pub/sub connection per process; each
socket gets each message exactly once, and a channel is dropped when its last
socket leaves."""
import asyncio

import fakeredis
import pytest

from app.core import hub as H


@pytest.fixture
def redis(monkeypatch):  # type: ignore[no-untyped-def]
    r = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)

    async def get() -> fakeredis.aioredis.FakeRedis:
        return r

    monkeypatch.setattr(H, "get_redis", get)
    return r


async def test_sockets_share_one_subscription_and_each_gets_a_message_once(redis) -> None:  # type: ignore[no-untyped-def]
    hub = H.Hub()
    try:
        async with hub.subscribe("tracking:a") as q1, hub.subscribe("tracking:a") as q2, hub.subscribe("tracking:b") as q3:
            assert hub.channels() == 2
            await asyncio.sleep(0.05)
            await redis.publish("tracking:a", "x")
            assert await asyncio.wait_for(q1.get(), 3) == "x"
            assert await asyncio.wait_for(q2.get(), 3) == "x"
            await asyncio.sleep(0.2)
            assert q1.empty() and q2.empty() and q3.empty()  # once each; b's socket got nothing
            await redis.publish("tracking:b", "y")
            assert await asyncio.wait_for(q3.get(), 3) == "y"
        assert hub.channels() == 0  # the last socket left: unsubscribed
        # One pub/sub connection for all of them (plus the hub's own keep-alive channel).
        assert (await redis.pubsub_numsub("tracking:a"))[0][1] == 0
    finally:
        if hub._reader:  # noqa: SLF001
            hub._reader.cancel()  # noqa: SLF001
