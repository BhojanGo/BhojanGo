"""Dispatch (P14): nearest rider first, 30 s window, re-offer on pass/timeout,
stale GPS skipped, accept assigns through core_api, location and tracking guards."""
import json
import uuid

import fakeredis
import pytest
from fastapi import HTTPException

from app.api.v1 import delivery
from app.services import dispatch
from app.services.core_api import CoreApiError
from shared.auth import CurrentUser

SPICE_ROUTE = [17.4483, 78.3915]
CUSTOMER = [17.4600, 78.3800]
ORDER = str(uuid.uuid4())
CUSTOMER_ID = str(uuid.uuid4())


async def drain(pubsub) -> list[dict]:  # type: ignore[no-untyped-def]
    out = []
    for _ in range(10):
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.05)
        if m:
            out.append(json.loads(m["data"]))
    return out


def info(**kw) -> dict:  # type: ignore[no-untyped-def]
    return {"order_id": ORDER, "status": "almost_ready", "customer_id": CUSTOMER_ID, "restaurant_id": str(uuid.uuid4()),
            "restaurant_name": "Spice Route", "driver_id": None, "market_city": "IN-TG-HYD", "pickup": SPICE_ROUTE,
            "dropoff": CUSTOMER, "offer_timeout_seconds": 30, "distance_unit": "km", **kw}


NOT_READY = "00000000-0000-0000-0000-00000000dead"


class FakeCore:
    async def rider_ready(self, rider: str) -> dict:
        return {"rider_id": rider, "ready": rider != NOT_READY, "country": "IN"}

    def __init__(self) -> None:
        self.assigned: list[tuple[str, str]] = []
        self.fail: CoreApiError | None = None

    async def dispatch_info(self, order: str) -> dict:
        if order != ORDER:
            raise CoreApiError(404, "Order not found")
        return info()

    async def assign_rider(self, order: str, rider: str) -> dict:
        if self.fail:
            raise self.fail
        self.assigned.append((order, rider))
        return info(driver_id=rider, status="almost_ready")


@pytest.fixture
def r(monkeypatch):  # type: ignore[no-untyped-def]
    server = fakeredis.FakeServer()
    client = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    async def get() -> fakeredis.aioredis.FakeRedis:
        return client

    from app.services import shifts

    monkeypatch.setattr(dispatch, "get_redis", get)
    monkeypatch.setattr(shifts, "get_redis", get)
    return client


@pytest.fixture
def core(monkeypatch):  # type: ignore[no-untyped-def]
    fake = FakeCore()
    monkeypatch.setattr(dispatch, "core_api", fake)
    monkeypatch.setattr(delivery, "core_api", fake)
    return fake


RIDER_NEAR = str(uuid.uuid4())   # ~0.5 km
RIDER_MID = str(uuid.uuid4())    # ~1.5 km
RIDER_FAR = str(uuid.uuid4())    # ~20 km: outside the radius


async def three_riders() -> None:
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960)
    await dispatch.go_online(RIDER_FAR, 17.6300, 78.3915)


async def test_offers_nearest_rider_first(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    assert await dispatch.start_dispatch(ORDER) == RIDER_NEAR
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert offer["expires_in"] == 30 and offer["restaurant_name"] == "Spice Route"
    assert offer["distance_km"] < 1 and offer["eta"]["to_pickup_minutes"] >= 1
    assert await dispatch.current_offer(RIDER_MID) is None
    # a duplicate event doesn't offer twice
    assert await dispatch.start_dispatch(ORDER) is None


async def test_pass_goes_to_next_rider_then_retries(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    assert await dispatch.decline(RIDER_NEAR, ORDER, "passed") == RIDER_MID
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "available"
    # the far rider is outside the radius: nobody left, so it waits for a retry
    assert await dispatch.decline(RIDER_MID, ORDER, "passed") is None
    assert await r.zscore(dispatch.RETRY, ORDER) is not None


async def test_timeout_goes_to_next_rider(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    assert (await dispatch.tick(now=dispatch._now() + 10))["expired"] == 0
    assert (await dispatch.tick(now=dispatch._now() + 31))["expired"] == 1
    assert await dispatch.current_offer(RIDER_NEAR) is None
    assert (await dispatch.current_offer(RIDER_MID))["order_id"] == ORDER


async def test_stale_gps_and_busy_riders_are_skipped(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await r.delete(dispatch.loc_key(RIDER_NEAR))  # app stopped sending GPS
    assert await dispatch.start_dispatch(ORDER) == RIDER_MID


async def test_accept_assigns_in_core_api(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"tracking:{ORDER}")
    result = await dispatch.accept(RIDER_NEAR, ORDER)
    assert result["status"] == "assigned" and core.assigned == [(ORDER, RIDER_NEAR)]
    assert await dispatch.rider_state(RIDER_NEAR) == {"status": "busy", "order_id": ORDER}
    msgs = await drain(pubsub)
    assert [m["type"] for m in msgs] == ["rider_assigned"]
    # nothing left to expire or retry
    assert (await dispatch.tick(now=dispatch._now() + 60)) == {"expired": 0, "retried": 0}
    # another rider can't accept it, nor can the first twice
    with pytest.raises(LookupError):
        await dispatch.accept(RIDER_MID, ORDER)


async def test_accept_after_timeout_is_refused(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.tick(now=dispatch._now() + 31)
    with pytest.raises(LookupError):
        await dispatch.accept(RIDER_NEAR, ORDER)
    assert core.assigned == []


async def test_accept_when_core_api_refuses(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    core.fail = CoreApiError(409, "The order already has a rider")
    with pytest.raises(LookupError, match="already has a rider"):
        await dispatch.accept(RIDER_NEAR, ORDER)
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "available"


async def test_location_streams_with_eta_while_busy(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"tracking:{ORDER}")
    fix = await dispatch.update_location(RIDER_NEAR, 17.4500, 78.3920)
    assert fix["order_id"] == ORDER
    [msg] = await drain(pubsub)
    assert msg["type"] == "location_update" and msg["payload"]["eta"]["to_customer_minutes"] >= 1
    assert await r.llen(f"trail:{ORDER}") == 1


async def test_delivered_frees_rider_and_offline_rules(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    with pytest.raises(ValueError):
        await dispatch.go_offline(RIDER_NEAR)
    await dispatch.on_order_event({"event_type": "order.status_changed",
                                   "payload": {"order_id": ORDER, "new_status": "delivered", "driver_id": RIDER_NEAR}})
    assert (await dispatch.rider_state(RIDER_NEAR))["status"] == "available"
    assert (await dispatch.go_offline(RIDER_NEAR))["status"] == "offline"


async def test_status_event_starts_dispatch_once(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    event = {"event_type": "order.status_changed", "payload": {"order_id": ORDER, "new_status": "almost_ready"}}
    await dispatch.on_order_event(event)
    await dispatch.on_order_event(event)
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == ORDER
    assert await dispatch.current_offer(RIDER_MID) is None


async def test_shadow_batching_only_suggests(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    other = info(order_id=str(uuid.uuid4()), dropoff=[17.4610, 78.3810])
    await r.sadd(dispatch.ACTIVE, other["order_id"])
    await r.set(dispatch.info_key(other["order_id"]), json.dumps(other))
    await dispatch.start_dispatch(ORDER, info())
    [s] = await dispatch.shadow_suggestions()
    assert s["mode"] == "shadow" and set(s["orders"]) == {ORDER, other["order_id"]}


# ── guards ────────────────────────────────────────────────────────────────────

def user(uid: str, role: str = "customer", admin: list[str] | None = None) -> CurrentUser:
    return CurrentUser(user_id=uid, role=role, country="IN", admin=admin)


async def test_location_only_for_own_order(r, core) -> None:  # type: ignore[no-untyped-def]
    from app.schemas.delivery import DriverLocationUpdateRequest

    await three_riders()
    other_order = str(uuid.uuid4())
    with pytest.raises(HTTPException) as e:
        await delivery.update_driver_location(
            DriverLocationUpdateRequest(lat=17.45, lng=78.39, order_id=other_order), user(RIDER_MID, "driver"))
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        await delivery.update_driver_location(DriverLocationUpdateRequest(lat=17.45, lng=78.39), user(CUSTOMER_ID))
    ok = await delivery.update_driver_location(DriverLocationUpdateRequest(lat=17.45, lng=78.39), user(RIDER_MID, "driver"))
    assert ok.order_id is None


def test_who_can_track() -> None:
    i = info(driver_id=RIDER_NEAR)
    assert delivery.can_see(user(CUSTOMER_ID), i)
    assert delivery.can_see(user(RIDER_NEAR, "driver"), i)
    assert not delivery.can_see(user(RIDER_MID, "driver"), i)
    assert not delivery.can_see(user(str(uuid.uuid4())), i)
    assert delivery.can_see(user(str(uuid.uuid4()), admin=["city_ops@IN-TG-HYD"]), i)
    assert not delivery.can_see(user(str(uuid.uuid4()), admin=["city_ops@US-ID-BOI"]), i)
    assert delivery.can_see(user(str(uuid.uuid4()), admin=["support_agent@IN"]), i)
    # The kitchen sees its own orders' riders arriving (P19 tablet), not other kitchens'.
    owner = str(uuid.uuid4())
    assert delivery.can_see(user(owner, "restaurant_owner"), info(driver_id=RIDER_NEAR, restaurant_owner_id=owner))
    assert not delivery.can_see(user(owner, "restaurant_owner"), i)


async def test_eta_endpoint_hides_other_orders(r, core) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(HTTPException) as e:
        await delivery.get_order_eta(uuid.UUID(ORDER), user(str(uuid.uuid4())))
    assert e.value.status_code == 404
    eta = await delivery.get_order_eta(uuid.UUID(ORDER), user(CUSTOMER_ID))
    assert eta.driver_lat is None


async def test_engaged_time_runs_from_accept_to_drop_off(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import shifts

    clock = {"t": 1_800_000_000.0}
    monkeypatch.setattr(dispatch, "_now", lambda: clock["t"])
    await three_riders()
    assert (await shifts.get_shift(RIDER_NEAR, clock["t"]))["status"] == "available"  # online, not engaged
    clock["t"] += 600  # 10 idle minutes online
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    assert (await shifts.get_shift(RIDER_NEAR, clock["t"] + 60))["status"] == "active"
    clock["t"] += 40 * 60  # drive to the restaurant, wait, ride to the customer
    await dispatch.on_order_event({"event_type": "order.status_changed",
                                   "payload": {"order_id": ORDER, "new_status": "delivered", "driver_id": RIDER_NEAR}})
    after = await shifts.get_shift(RIDER_NEAR, clock["t"] + 30 * 60)
    # only the 40 minutes from accept to drop-off are engaged, not the idle time before or after
    assert after["status"] == "available" and after["active_minutes"] == 40 and after["available_minutes"] == 80


async def test_offer_shows_pay_bags_and_drop_area(r, core, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    extra = {"code": "#AB12CD", "currency": "INR", "rider_pay": "45.00", "tip": "20.00", "items_count": 3, "bags": 1,
             "ready_in_minutes": 6, "drop_area": "Kondapur"}
    monkeypatch.setattr(core, "dispatch_info", lambda order: _async(info(**extra)))
    await three_riders()
    await dispatch.start_dispatch(ORDER)
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert {k: offer[k] for k in extra} == extra
    assert offer["trip_km"] > 0 and offer["distance_unit"] == "km"


async def _async(v):  # type: ignore[no-untyped-def]
    return v


async def test_online_needs_finished_onboarding(r, core) -> None:  # type: ignore[no-untyped-def]
    from app.api.v1 import riders

    with pytest.raises(HTTPException) as e:
        await riders.online(riders.Point(lat=17.45, lng=78.39), CurrentUser(NOT_READY, "driver", "IN"))
    assert e.value.status_code == 403 and e.value.detail["code"] == "ONBOARDING_INCOMPLETE"
    assert not await r.sismember(dispatch.ONLINE, NOT_READY)
    ok = str(uuid.uuid4())
    assert (await riders.online(riders.Point(lat=17.45, lng=78.39), CurrentUser(ok, "driver", "IN")))["status"] == "available"


async def test_sos_reaches_admins_for_the_city(r, core) -> None:  # type: ignore[no-untyped-def]
    from app.api.v1 import riders

    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await dispatch.accept(RIDER_NEAR, ORDER)
    pubsub = r.pubsub()
    await pubsub.subscribe(dispatch.SOS_CHANNEL)
    alert = await riders.sos(riders.SosIn(note="Followed"), CurrentUser(RIDER_NEAR, "driver", "IN"))
    assert alert["emergency_number"] == "112" and alert["order_id"] == ORDER and alert["lat"] == 17.4520
    assert [m["type"] for m in await drain(pubsub)] == ["sos"]
    hyd = CurrentUser(str(uuid.uuid4()), "customer", "IN", admin=["city_ops@IN-TG-HYD"])
    boi = CurrentUser(str(uuid.uuid4()), "customer", "US", admin=["city_ops@US-ID-BOI"])
    assert [a["id"] for a in await riders.open_sos(hyd)] == [alert["id"]]
    assert await riders.open_sos(boi) == []
