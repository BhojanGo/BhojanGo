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
    async def city_centre(self, code: str):  # type: ignore[no-untyped-def]
        return {"IN-TG-HYD": (17.4486, 78.3908), "US-ID-BOI": (43.615, -116.2023)}.get(code)

    async def rider_ready(self, rider: str) -> dict:
        return {"rider_id": rider, "ready": rider != NOT_READY, "country": "IN"}

    def __init__(self) -> None:
        self.assigned: list[tuple[str, str]] = []
        self.fail: CoreApiError | None = None
        self.others: set[str] = set()  # more orders at the same kitchen (fairness tests)
        self.live = False  # the city's business:batching rule (task 43)
        self.batch_positions: dict[str, tuple] = {}

    async def dispatch_info(self, order: str) -> dict:
        if order != ORDER and order not in self.others:
            raise CoreApiError(404, "Order not found")
        return info(order_id=order, batching_live=self.live, rider_pay="60.00", rider_pay_batched="45.00")

    async def assign_rider(self, order: str, rider: str, batch_id: str | None = None, position: int | None = None) -> dict:
        if self.fail:
            raise self.fail
        self.assigned.append((order, rider))
        self.batch_positions[order] = (batch_id, position)
        return info(order_id=order, driver_id=rider, status="almost_ready", batching_live=self.live)


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


async def test_shadow_suggestions_are_stored_not_offered(r, core) -> None:  # type: ignore[no-untyped-def]
    await three_riders()
    await dispatch.record_shadow({"orders": [ORDER, "o2"], "score": 61, "savings_percent": 38.0, "city": "IN-TG-HYD"})
    [s] = await dispatch.shadow_suggestions()
    assert s["mode"] == "shadow" and s["orders"] == [ORDER, "o2"] and s["score"] == 61
    assert await dispatch.current_offer(RIDER_NEAR) is None


# ── live batching (task 43) ──────────────────────────────────────────────────

async def _pair(core, live: bool = True) -> list[str]:  # type: ignore[no-untyped-def]
    """Two waiting orders from Spice Route; nobody online yet."""
    core.live = live
    second = str(uuid.uuid4())
    core.others.add(second)
    for i, o in enumerate((ORDER, second)):
        await dispatch.start_dispatch(o)
        await (await dispatch.get_redis()).zadd(dispatch.WAITING, {o: 1000.0 + i}, xx=True)  # ORDER is the older one
    return [ORDER, second]


async def test_live_city_holds_a_new_order_for_a_partner(r, core) -> None:  # type: ignore[no-untyped-def]
    core.live = True
    await three_riders()
    assert await dispatch.start_dispatch(ORDER) is None  # held, not offered alone yet
    assert await dispatch.current_offer(RIDER_NEAR) is None
    assert (await dispatch.tick(now=dispatch._now() + 5))["retried"] == 0
    await r.zadd(dispatch.HOLD, {ORDER: dispatch._now() - 1}, xx=True)  # the hold runs out
    await r.zadd(dispatch.RETRY, {ORDER: dispatch._now() - 1})
    await dispatch.tick()
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == ORDER  # then it goes alone


async def test_a_city_that_is_off_never_gets_a_batch_offer(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core, live=False)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)  # takes the oldest order alone
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == ORDER
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960)
    assert await dispatch.offer_batch(orders) is None


async def test_batch_offer_shows_both_drop_offs_and_total_pay(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    assert await dispatch.current_offer(RIDER_NEAR) is None  # both still held for batching
    assert await dispatch.offer_batch(orders, {"total_distance_km": 4.2, "total_time_min": 21}) == RIDER_NEAR
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert offer["order_id"] == ORDER and [b["order_id"] for b in offer["batch"]] == orders
    assert all(b["dropoff"] for b in offer["batch"])  # both drop-offs
    pays = [b["rider_pay"] for b in offer["batch"]]
    from decimal import Decimal
    assert offer["rider_pay"] == (str(sum(Decimal(x) for x in pays)) if all(pays) else None)  # the total
    assert offer["trip_km"] == 4.2 and offer["batch_minutes"] == 21
    # the second order isn't offered to anyone else while the batch offer is open
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960)
    await r.zrem(dispatch.HOLD, orders[1])
    assert await dispatch.offer_next(orders[1]) is None
    assert await dispatch.offer_batch(orders) is None  # not twice


async def test_accepting_a_batch_assigns_both_and_drops_them_in_order(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.offer_batch(orders)
    res = await dispatch.accept(RIDER_NEAR, ORDER)
    assert res["batch"] == orders and core.assigned == [(o, RIDER_NEAR) for o in orders]
    state = await dispatch.rider_state(RIDER_NEAR)
    assert state["status"] == "busy" and state["order_id"] == ORDER and state["batch"] == orders
    for o in orders:
        assert await r.zscore(dispatch.WAITING, o) is None and not await r.sismember(dispatch.ACTIVE, o)
    # GPS may name either order being carried
    req = delivery.DriverLocationUpdateRequest(lat=17.45, lng=78.39, order_id=orders[1])
    assert (await delivery.update_driver_location(req, user(RIDER_NEAR, "driver"))).order_id == ORDER
    # first drop-off done: on to the second
    await dispatch.on_order_event({"event_type": "order.status_changed",
                                   "payload": {"order_id": ORDER, "new_status": "delivered", "driver_id": RIDER_NEAR}})
    state = await dispatch.rider_state(RIDER_NEAR)
    assert state["status"] == "busy" and state["order_id"] == orders[1] and state["batch"] == [orders[1]]
    await dispatch.on_order_event({"event_type": "order.status_changed",
                                   "payload": {"order_id": orders[1], "new_status": "delivered", "driver_id": RIDER_NEAR}})
    state = await dispatch.rider_state(RIDER_NEAR)
    assert state["status"] == "available" and "batch" not in state


async def test_a_passed_batch_goes_back_to_solo_dispatch(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.offer_batch(orders)
    await dispatch.go_online(RIDER_MID, 17.4610, 78.3960)
    await dispatch.decline(RIDER_NEAR, ORDER, "passed")
    for o in orders:
        assert RIDER_NEAR in await r.smembers(dispatch.declined_key(o))
        assert await r.zscore(dispatch.HOLD, o) is None and not await r.exists(dispatch.in_batch_offer_key(o))
    offer = await dispatch.current_offer(RIDER_MID)  # the oldest goes to the other rider, alone
    assert offer and offer["order_id"] == ORDER and "batch" not in offer


async def test_cancelling_one_order_withdraws_the_batch_offer(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = await _pair(core)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.offer_batch(orders)
    await dispatch.on_order_event({"event_type": "order.cancelled", "payload": {"order_id": orders[1], "status": "cancelled"}})
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert offer and offer["order_id"] == ORDER and "batch" not in offer  # the other one, alone


async def test_a_batch_can_take_an_order_still_cooking_at_the_same_kitchen(r, core) -> None:  # type: ignore[no-untyped-def]
    """The pool includes orders still being cooked: one looking for a rider pairs with
    one from the same kitchen that'll be ready soon. If the pair is turned down, the
    cooking one goes back to waiting for its own turn (no offer while still cooking)."""
    core.live = True
    cooking = str(uuid.uuid4())
    core.others.add(cooking)
    statuses = {cooking: "preparing"}
    real = core.dispatch_info

    async def dispatch_info(order: str) -> dict:
        return {**await real(order), "status": statuses.get(order, "almost_ready"), "restaurant_id": "spice-route"}

    core.dispatch_info = dispatch_info
    await dispatch.start_dispatch(ORDER)  # almost ready: held for a partner
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    assert await dispatch.offer_batch([ORDER, cooking]) == RIDER_NEAR
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert offer["early"] == [cooking] and await r.sismember(dispatch.ACTIVE, cooking)
    # it reaches "almost ready" while on the batch offer: no separate dispatch starts
    await dispatch.on_order_event({"event_type": "order.status_changed", "payload": {"order_id": cooking, "new_status": "almost_ready"}})
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == ORDER
    statuses[cooking] = "preparing"
    await dispatch.decline(RIDER_NEAR, ORDER, "passed")
    assert not await r.sismember(dispatch.ACTIVE, cooking) and await r.zscore(dispatch.WAITING, cooking) is None


async def test_two_orders_still_cooking_are_never_offered(r, core) -> None:  # type: ignore[no-untyped-def]
    core.live = True
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    core.others.update([a, b])
    real = core.dispatch_info

    async def dispatch_info(order: str) -> dict:
        return {**await real(order), "status": "preparing"}

    core.dispatch_info = dispatch_info
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    assert await dispatch.offer_batch([a, b]) is None


async def test_batches_endpoint_is_signed(r, core) -> None:  # type: ignore[no-untyped-def]
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from shared import internal_auth

    body = json.dumps({"mode": "shadow", "city": "IN-TG-HYD", "batches": [{"orders": [ORDER, "o2"], "score": 50,
                       "savings_percent": 30, "total_distance_km": 3, "total_time_min": 20, "max_detour_min": 1}]}).encode()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        no = await c.post("/internal/dispatch/batches", content=body, headers={"content-type": "application/json"})
        ok = await c.post("/internal/dispatch/batches", content=body, headers={
            "content-type": "application/json", **internal_auth.sign("POST", "/internal/dispatch/batches", body)})
    assert no.status_code == 401
    assert ok.status_code == 200 and ok.json() == {"received": 1, "offered": 0}
    assert (await dispatch.shadow_suggestions())[0]["orders"] == [ORDER, "o2"]


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


async def test_dispatch_map_shows_riders_and_sos_to_the_citys_admins(r, core) -> None:  # type: ignore[no-untyped-def]
    from app.api.v1 import riders

    await three_riders()
    await dispatch.start_dispatch(ORDER)
    await riders.sos(riders.SosIn(note="Flat tyre"), CurrentUser(RIDER_MID, "driver", "IN"))
    hyd = CurrentUser(str(uuid.uuid4()), "customer", "IN", admin=["city_ops@IN-TG-HYD"])
    m = await riders.dispatch_riders(hyd, city="IN-TG-HYD")
    got = {x["rider_id"]: x for x in m["riders"]}
    assert set(got) == {RIDER_NEAR, RIDER_MID, RIDER_FAR}  # all within 30 km of the centre
    assert got[RIDER_NEAR]["status"] == "offered" and got[RIDER_NEAR]["order_id"] == ORDER
    assert [a["rider_id"] for a in m["sos"]] == [RIDER_MID]
    boi = CurrentUser(str(uuid.uuid4()), "customer", "US", admin=["city_ops@US-ID-BOI"])
    with pytest.raises(HTTPException) as e:
        await riders.dispatch_riders(boi, city="IN-TG-HYD")
    assert e.value.status_code == 403


async def test_a_free_rider_gets_the_oldest_waiting_order(r, core) -> None:  # type: ignore[no-untyped-def]
    """Pilot dress rehearsal: with every rider busy, orders queue; the next free
    rider must get the one that has waited longest, not whichever retries first."""
    orders = [str(uuid.uuid4()) for _ in range(3)]
    core.others.update(orders)
    for i, o in enumerate(orders):  # nobody online: all three wait, oldest first
        await dispatch.start_dispatch(o)
        await r.zadd(dispatch.WAITING, {o: 1000.0 + i}, xx=True)
    # The newest order's retry timer comes up first.
    for i, o in enumerate(reversed(orders)):
        await r.zadd(dispatch.RETRY, {o: 1.0 + i})
    await dispatch.go_online(RIDER_NEAR, SPICE_ROUTE[0] + 0.004, SPICE_ROUTE[1])
    offer = await dispatch.current_offer(RIDER_NEAR)
    assert offer and offer["order_id"] == orders[0]  # the oldest, at once, not after a retry

    await dispatch.accept(RIDER_NEAR, orders[0])
    assert await r.zscore(dispatch.WAITING, orders[0]) is None
    await dispatch.go_online(RIDER_MID, SPICE_ROUTE[0] + 0.012, SPICE_ROUTE[1])
    assert (await dispatch.current_offer(RIDER_MID))["order_id"] == orders[1]


async def test_retries_run_oldest_first(r, core) -> None:  # type: ignore[no-untyped-def]
    orders = [str(uuid.uuid4()) for _ in range(2)]
    core.others.update(orders)
    for i, o in enumerate(orders):
        await dispatch.start_dispatch(o)
        await r.zadd(dispatch.WAITING, {o: 1000.0 + i}, xx=True)
        await r.zadd(dispatch.RETRY, {o: 5.0 - i})  # the newer one is due first
    # A rider whose GPS arrives without go_online's hand-off (e.g. after a restart).
    await r.sadd(dispatch.ONLINE, RIDER_NEAR)
    await r.hset(dispatch.state_key(RIDER_NEAR), mapping={"status": "available", "order_id": ""})
    await dispatch.update_location(RIDER_NEAR, SPICE_ROUTE[0] + 0.004, SPICE_ROUTE[1])
    await dispatch.tick(now=10.0)
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == orders[0]


async def test_a_pass_frees_the_rider_for_the_oldest_other_order(r, core) -> None:  # type: ignore[no-untyped-def]
    old, new = str(uuid.uuid4()), str(uuid.uuid4())
    core.others.update([old, new])
    await dispatch.go_online(RIDER_NEAR, SPICE_ROUTE[0] + 0.004, SPICE_ROUTE[1])
    await dispatch.start_dispatch(new)  # offered to the only rider
    await r.zadd(dispatch.WAITING, {new: 2000.0}, xx=True)
    await dispatch.start_dispatch(old)  # nobody free: waits
    await r.zadd(dispatch.WAITING, {old: 1000.0}, xx=True)
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == new
    await dispatch.decline(RIDER_NEAR, new, "passed")
    assert (await dispatch.current_offer(RIDER_NEAR))["order_id"] == old


async def test_second_drop_off_shows_the_batch_rate_and_is_recorded_as_second(r, core) -> None:  # type: ignore[no-untyped-def]
    """Item 2: on the offer card the second drop-off pays the batch rate (no base, + the batch
    bonus); the total is the first's full pay plus it; core_api records each order's place."""
    orders = await _pair(core)
    await dispatch.go_online(RIDER_NEAR, 17.4520, 78.3940)
    await dispatch.offer_batch(orders)
    offer = await dispatch.current_offer(RIDER_NEAR)
    first, second = offer["batch"]
    assert first["rider_pay"] == "60.00" and first["batch_rate"] is False
    assert second["rider_pay"] == "45.00" and second["batch_rate"] is True
    assert offer["rider_pay"] == "105.00"
    await dispatch.accept(RIDER_NEAR, ORDER)
    (b1, p1), (b2, p2) = core.batch_positions[orders[0]], core.batch_positions[orders[1]]
    assert b1 and b1 == b2 and (p1, p2) == (1, 2)
