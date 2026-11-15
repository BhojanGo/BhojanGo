""""Almost there" (realtime): once per order, when the rider carrying it comes within
ALMOST_THERE_METERS of the door, the tracker hears it on the order's channel and the
worker gets a driver.almost_there event to message the customer."""
import json

import pytest

from app.services import dispatch
from tests.test_dispatch import CUSTOMER, ORDER, RIDER_NEAR, core, drain, r, three_riders  # noqa: F401

# CUSTOMER is the drop-off ([17.4600, 78.3800]); ~0.0009 deg lat is ~100 m.
FAR = (17.4500, 78.3920)        # ~1.7 km out
NEAR = (17.4600 - 0.0027, 78.3800)  # ~300 m out
CLOSER = (17.4600 - 0.0009, 78.3800)  # ~100 m out


@pytest.fixture
def events(monkeypatch):  # type: ignore[no-untyped-def]
    sent: list[tuple[str, dict]] = []

    async def publish_event(event_type: str, payload: dict) -> bool:
        sent.append((event_type, payload))
        return True

    from shared import notify

    monkeypatch.setattr(notify, "publish_event", publish_event)
    return sent


async def on_the_way(r) -> object:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    await dispatch.on_order_event({"event_type": "order.status_changed",
                                   "payload": {"order_id": ORDER, "new_status": "picked_up", "driver_id": RIDER_NEAR}})
    pubsub = r.pubsub()
    await pubsub.subscribe(f"tracking:{ORDER}")
    return pubsub


def test_threshold() -> None:
    info = {"status": "picked_up", "dropoff": CUSTOMER}
    assert dispatch.is_almost_there(info, NEAR) and dispatch.is_almost_there(info, CLOSER)
    assert not dispatch.is_almost_there(info, FAR)
    assert not dispatch.is_almost_there({**info, "status": "ready"}, NEAR), "only with the food on board"
    assert not dispatch.is_almost_there({"status": "picked_up", "dropoff": None}, NEAR)
    assert not dispatch.is_almost_there(None, NEAR)


async def test_once_per_order(r, core, events) -> None:  # type: ignore[no-untyped-def]
    pubsub = await on_the_way(r)
    await dispatch.update_location(RIDER_NEAR, *FAR)
    assert [m["type"] for m in await drain(pubsub)] == ["location_update"] and not events
    await dispatch.update_location(RIDER_NEAR, *NEAR)
    msgs = await drain(pubsub)
    assert [m["type"] for m in msgs] == ["location_update", "almost_there"]
    near = msgs[1]["payload"]
    assert near["order_id"] == ORDER and 200 <= near["distance_m"] <= 400 and near["eta_minutes"] >= 1
    [(kind, payload)] = events
    assert kind == "driver.almost_there" and payload["driver_id"] == RIDER_NEAR and payload["customer_id"]
    for at in (CLOSER, NEAR, CLOSER):  # more fixes near the door: nothing again
        await dispatch.update_location(RIDER_NEAR, *at)
    assert [m["type"] for m in await drain(pubsub)] == ["location_update"] * 3
    assert len(events) == 1
    assert await r.get(dispatch.almost_there_key(ORDER)) == "1"


async def test_not_before_pickup(r, core, events) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    await dispatch.update_location(RIDER_NEAR, *NEAR)  # still almost_ready: on the way to the kitchen
    assert not events and not await r.exists(dispatch.almost_there_key(ORDER))


async def test_its_own_event_is_ignored(r, core) -> None:  # type: ignore[no-untyped-def]
    await dispatch.on_order_event({"event_type": "driver.almost_there", "payload": {"order_id": ORDER}})
    assert not await r.keys("*")


async def test_publish_event_reaches_the_worker_queue(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared import bus, notify

    sent: list = []
    monkeypatch.setattr(bus, "is_redis", lambda: True)
    monkeypatch.setattr(bus, "publish", lambda env: sent.append(env) or "1-0")
    assert await notify.publish_event("driver.almost_there", {"order_id": ORDER})
    assert sent[0]["event_type"] == "driver.almost_there" and sent[0]["payload"] == {"order_id": ORDER}
    assert json.dumps(sent[0])  # serialisable as it goes on the stream
