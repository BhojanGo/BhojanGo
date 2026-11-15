"""The demo rider simulator talks to core_api and realtime like the apps do
(app/demo_sim/runner.py), checked against stand-in services: phone-code sign-in
and token refresh, ordering again, the offer, GPS fixes, and delivery with the PIN."""
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import fakeredis.aioredis
import httpx
import pytest

from app.demo_sim import rules, runner
from app.demo_sim.path import haversine_km

KITCHEN, HOME = (17.4400, 78.3550), (17.4560, 78.3870)
NOW = datetime(2026, 11, 15, 13, 0, tzinfo=UTC)
RIDER = SimpleNamespace(id="rider-1", email="rider.sim.hyd.1@example.com", phone="+919000000261", country="IN")
RIDER2 = SimpleNamespace(id="rider-2", email="rider.sim.hyd.2@example.com", phone="+919000000262", country="IN")
CUSTOMER = SimpleNamespace(id="cust-1", email="demo1.hyd@example.com", phone="+919000000301", country="IN")
OWNER = SimpleNamespace(id="owner-1", email="partner.demo.hyd@example.com", phone="+919000000910", country="IN")
PHONES = {RIDER.phone: "rider", RIDER2.phone: "rider2", CUSTOMER.phone: "customer", OWNER.phone: "owner"}


class Services:
    """core_api and realtime, as far as the simulator uses them; records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict | None]] = []  # (who, method, path, body)
        self.tokens: dict[str, str] = {}
        self.riders: dict[str, dict] = {}  # who -> what realtime has: state, offer, busy_with (the order it's on)
        self.closed_kitchens: set[str] = set()
        self.refresh_revoked = False  # signed out on another device: refresh tokens revoked
        self.marked: list[str] = []  # orders marked for the simulator's pool (signed internal call)

    def rt(self, who: str) -> dict:
        return self.riders.setdefault(who, {"state": "offline", "offer": None, "busy_with": None})

    # The first rider's state, as most tests set it.
    state = property(lambda s: s.rt("rider")["state"], lambda s, v: s.rt("rider").__setitem__("state", v))
    offer = property(lambda s: s.rt("rider")["offer"], lambda s, v: s.rt("rider").__setitem__("offer", v))
    busy_with = property(lambda s: s.rt("rider")["busy_with"], lambda s, v: s.rt("rider").__setitem__("busy_with", v))

    def who(self, request: httpx.Request) -> str:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        return self.tokens.get(token, "")

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        body = json.loads(request.content) if request.content else None
        if path == "/api/v1/auth/send-otp":
            self.calls.append(("-", method, path, body))
            return httpx.Response(200, json={"message": "OTP sent successfully"})
        if path == "/api/v1/auth/phone":
            assert body["otp"] == "123456"
            return self._tokens(PHONES[body["phone"]], path, body)
        if path == runner.POOL_ORDERS_PATH:
            from shared import internal_auth

            internal_auth.verify(method, path, request.content, request.headers.get("x-internal-timestamp"),
                                 request.headers.get("x-internal-signature"))
            assert body["pool"] == "demo_sim"
            self.marked.append(body["order_id"])
            self.calls.append(("internal", method, path, body))
            return httpx.Response(200, json=body)
        if path == "/api/v1/auth/refresh":
            if self.refresh_revoked:
                return httpx.Response(401, json={"detail": {"code": "INVALID_TOKEN"}})
            return self._tokens(body["refresh_token"].split(":")[1], path, body)
        who = self.who(request)
        if not who:
            return httpx.Response(401, json={"detail": "Invalid credentials"})
        self.calls.append((who, method, path, body))
        me = self.rt(who)
        if path == "/api/v1/riders/me" and method == "GET":
            return httpx.Response(200, json={"state": {"status": me["state"], "order_id": me["busy_with"] or ""},
                                             "offer": {"order_id": me["offer"]} if me["offer"] else None})
        if path == "/api/v1/riders/me/online":  # realtime frees a rider stuck on an order that is over
            me["state"], me["busy_with"] = "available", None
        if path == "/api/v1/riders/me/offline":
            me["state"] = "offline"
        if path.startswith("/api/v1/offers/") and path.endswith("/accept"):
            me["state"], me["offer"], me["busy_with"] = "busy", None, path.split("/")[4]
        if path == "/api/v1/me/addresses":
            return httpx.Response(200, json=[{"id": "addr-1", "label": "Home", "street": "Flat 504, Cyber Residency",
                                              "city": "Hyderabad", "state": "Telangana", "postal_code": "500081",
                                              "country": "IN", "lat": HOME[0], "lng": HOME[1], "is_default": True}])
        if path.endswith("/reorder"):
            past = path.split("/")[4]
            return httpx.Response(200, json={"restaurant": {"id": f"kitchen-of-{past}", "slug": "k", "name": "K", "currency": "INR"},
                                             "items": [{"menu_item_id": "item-1", "name": "Paneer", "quantity": 2, "price": 10,
                                                        "options": [{"group": "Size", "option": "Full", "name": "Full"}]}],
                                             "unavailable": []})
        if path == "/api/v1/pricing/quote":
            if body["restaurant_id"] in self.closed_kitchens:
                return httpx.Response(422, json={"detail": "The kitchen is closed"})
            return httpx.Response(200, json={"token": "q" * 30, "total": "100.00"})
        if path == "/api/v1/orders" and method == "POST":
            assert request.headers["x-idempotency-key"]
            return httpx.Response(201, json={"id": "new-order", "status": "pending_payment"})
        if path.startswith("/api/v1/orders/") and method == "GET":
            return httpx.Response(200, json={"id": path.split("/")[-1], "pin": "4821" if who == "customer" else None})
        return httpx.Response(200, json={})

    def _tokens(self, who: str, path: str, body: dict) -> httpx.Response:
        self.calls.append(("-", "POST", path, body))
        n = len(self.tokens)
        self.tokens[f"access-{who}-{n}"] = who
        return httpx.Response(200, json={"access_token": f"access-{who}-{n}", "refresh_token": f"refresh:{who}:{n}",
                                         "expires_in": 900})

    def of(self, who: str) -> list[tuple[str, str, dict | None]]:
        return [(m, p, b) for w, m, p, b in self.calls if w == who]


@pytest.fixture
def services(monkeypatch):  # type: ignore[no-untyped-def]
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def get_redis():  # type: ignore[no-untyped-def]
        return redis

    monkeypatch.setattr(runner, "get_redis", get_redis)
    return Services()


def api_for(s: Services) -> runner.Api:
    transport = httpx.MockTransport(s.handle)
    return runner.Api(httpx.AsyncClient(transport=transport, base_url="http://core"),
                      httpx.AsyncClient(transport=transport, base_url="http://rt"))


def order(**kw) -> rules.DemoOrder:  # type: ignore[no-untyped-def]
    base = {"id": "o1", "status": "almost_ready", "customer_email": CUSTOMER.email, "driver_id": None,
            "restaurant_owner_id": OWNER.id, "pickup": KITCHEN, "dropoff": HOME, "created_at": NOW - timedelta(minutes=8)}
    return rules.DemoOrder(**{**base, **kw})


async def test_signs_in_with_the_phone_code_and_refreshes(services: Services) -> None:
    api = api_for(services)
    rider = api.person(RIDER)
    await rider.call("rt", "GET", "/riders/me")
    assert [p for _, _, p, _ in services.calls[:2]] == ["/api/v1/auth/send-otp", "/api/v1/auth/phone"]
    assert services.calls[0][3] == {"phone": RIDER.phone, "country": "IN"}
    services.tokens.clear()  # the access token expired
    await rider.call("rt", "GET", "/riders/me")
    assert any(p == "/api/v1/auth/refresh" for _, _, p, _ in services.calls), "refreshed, not signed in again"
    assert api.person(RIDER) is rider


async def test_sign_in_waits_out_the_code_limit(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    api = api_for(services)
    original = services.handle

    def limited(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/send-otp":
            services.calls.append(("-", "POST", request.url.path, None))
            return httpx.Response(429, json={"detail": "Too many"})
        return original(request)

    api.core._transport = httpx.MockTransport(limited)  # type: ignore[attr-defined]
    person = api.person(OWNER)
    for _ in range(3):
        with pytest.raises(runner.ApiError):
            await person.call("core", "GET", "/users/me")
    assert sum(p == "/api/v1/auth/send-otp" for _, _, p, _ in services.calls) == 1, "no hammering"


async def test_the_rider_takes_only_its_order(services: Services) -> None:
    api = api_for(services)
    city = runner.City(api, "hyd", [RIDER])
    services.offer = "someone-elses"
    await city.do("find_rider", order(), CUSTOMER, OWNER, NOW)
    rider = services.of("rider")
    online = next(b for m, p, b in rider if p == "/api/v1/riders/me/online")
    assert 0.9 <= haversine_km(KITCHEN, (online["lat"], online["lng"])) <= 1.9, "goes online near the kitchen"
    assert ("POST", "/api/v1/offers/someone-elses/pass", None) in rider
    services.offer = "o1"
    await city.do("find_rider", order(), CUSTOMER, OWNER, NOW)
    assert ("POST", "/api/v1/offers/o1/accept", None) in services.of("rider")


async def test_kitchen_steps_are_status_moves_by_the_owner(services: Services) -> None:
    api = api_for(services)
    city = runner.City(api, "hyd", [RIDER])
    for step, status in (("accept", "accepted"), ("prepare", "preparing"), ("almost_ready", "almost_ready"), ("ready", "ready")):
        await city.do(step, order(), CUSTOMER, OWNER, NOW)
        assert services.of("owner")[-1] == ("PUT", "/api/v1/orders/o1/status", {"status": status})
    assert any(p == "/api/v1/riders/me/online" for _, p, _ in services.of("rider")), "the rider is about before dispatch"


async def test_riding_sends_gps_and_delivers_with_the_customers_pin(services: Services) -> None:
    api = api_for(services)
    city = runner.City(api, "hyd", [RIDER])
    o = order(status="picked_up", driver_id=RIDER.id, picked_up_at=NOW - timedelta(minutes=2))
    for k in range(3):
        await city.do("to_home", o, CUSTOMER, OWNER, NOW + timedelta(seconds=4 * k))
    fixes = [b for _, p, b in services.of("rider") if p == "/api/v1/delivery/driver/location"]
    assert len(fixes) == 3 and all(18 / 3.6 <= f["speed"] <= 25 / 3.6 and f["accuracy"] == 8 for f in fixes)
    steps = [haversine_km((a["lat"], a["lng"]), (b["lat"], b["lng"])) for a, b in zip(fixes, fixes[1:])]
    assert all(0.015 <= d <= 0.03 for d in steps), steps  # 4 s apart at 18-25 km/h
    await city.do("pick_up", order(status="ready", driver_id=RIDER.id), CUSTOMER, OWNER, NOW)
    assert ("PUT", "/api/v1/orders/o1/status", {"status": "picked_up"}) in services.of("rider")
    await city.do("deliver", o, CUSTOMER, OWNER, NOW + timedelta(minutes=30))
    assert ("GET", "/api/v1/orders/o1", None) in services.of("customer"), "the customer reads out the PIN"
    assert ("PUT", "/api/v1/orders/o1/status", {"status": "delivered", "proof": {"method": "pin", "pin": "4821"}}) \
        in services.of("rider")
    assert city.off_duty == {RIDER.id}, "off duty once realtime has seen the delivery (City.tick)"


async def test_orders_again_from_an_open_kitchen(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class Db:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *a):  # type: ignore[no-untyped-def]
            return False

        async def execute(self, *_a, **_k):  # type: ignore[no-untyped-def]
            return SimpleNamespace(all=lambda: [SimpleNamespace(id="past-1"), SimpleNamespace(id="past-2")])

    monkeypatch.setattr(runner, "AsyncSessionLocal", Db)
    services.closed_kitchens = {"kitchen-of-past-1"}
    api = api_for(services)
    city = runner.City(api, "hyd", [RIDER])
    assert await city.place(CUSTOMER) == "new-order"
    calls = services.of("customer")
    quotes = [b for m, p, b in calls if p == "/api/v1/pricing/quote"]
    assert [q["restaurant_id"] for q in quotes] == ["kitchen-of-past-1", "kitchen-of-past-2"], "closed: the next kitchen"
    assert quotes[-1]["deliver_to"] == {"address_id": "addr-1"}
    assert quotes[-1]["items"] == [{"menu_item_id": "item-1", "quantity": 2, "options": [{"group": "Size", "option": "Full"}]}]
    placed = next(b for m, p, b in calls if p == "/api/v1/orders" and m == "POST")
    assert placed["quote_token"] == "q" * 30 and placed["payment_method"] == "card"
    assert placed["delivery_address"]["lat"] == HOME[0] and placed["delivery_address"]["zip"] == "500081"
    assert ("POST", "/api/v1/payments/initiate", {"order_id": "new-order", "payment_method_type": "card"}) in calls
    assert await (await runner.get_redis()).smembers(runner.OURS) == {"new-order"}, "marked as the simulator's"


def row(oid: str, status: str, *, seeded: bool = False, driver: str | None = None, picked: datetime | None = None):  # type: ignore[no-untyped-def]
    return SimpleNamespace(id=oid, status=status, customer_email=CUSTOMER.email, driver_id=driver, owner_id=OWNER.id,
                           pickup_lat=KITCHEN[0], pickup_lng=KITCHEN[1], delivery_lat=HOME[0], delivery_lng=HOME[1],
                           created_at=NOW - timedelta(minutes=30), placed_at=NOW - timedelta(minutes=29),
                           restaurant_accepted_at=NOW - timedelta(minutes=28), rider_assigned_at=NOW - timedelta(minutes=20),
                           picked_up_at=picked, market_city="IN-TG-HYD", seeded=seeded)


def fake_db(orders: list, last_delivered: datetime | None):  # type: ignore[no-untyped-def]
    class Result:
        def __init__(self, value) -> None:  # type: ignore[no-untyped-def]
            self.value = value

        def first(self):  # type: ignore[no-untyped-def]
            return self.value

        def all(self):  # type: ignore[no-untyped-def]
            return self.value

        def scalar(self):  # type: ignore[no-untyped-def]
            return self.value

    class Db:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *a):  # type: ignore[no-untyped-def]
            return False

        async def execute(self, sql, params=None):  # type: ignore[no-untyped-def]
            return Result({id(runner.USER_SQL): CUSTOMER, id(runner.ORDERS_SQL): orders,
                           id(runner.LAST_DELIVERED_SQL): last_delivered, id(runner.OWNER_SQL): OWNER}[id(sql)])

    return Db


async def test_a_tick_drives_only_its_own_orders(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seeded = row("seeded", "picked_up", seeded=True, driver=RIDER.id, picked=NOW - timedelta(minutes=2))
    persons = row("a-testers-order", "placed")  # a person testing with the demo account
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([seeded, persons], NOW - timedelta(hours=1)))
    city = runner.City(api_for(services), "hyd", [RIDER])
    placed: list = []

    async def place(customer):  # type: ignore[no-untyped-def]
        placed.append(customer)

    monkeypatch.setattr(city, "place", place)
    assert await city.tick(NOW) == ["to_home"]
    assert not services.of("owner"), "the tester's order is left alone"
    assert [p for _, p, _ in services.of("rider")] == ["/api/v1/delivery/driver/location"]
    assert not placed, "one on its way already"

    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([], NOW - timedelta(minutes=1)))
    assert await city.tick(NOW) == [] and not placed, "a short pause after a delivery"
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([], NOW - timedelta(minutes=5)))
    await city.tick(NOW)
    assert placed == [CUSTOMER]
    await city.tick(NOW + timedelta(minutes=1))
    assert placed == [CUSTOMER], "no kitchen took it: not again for a while"


# -- stalls and recovery (QA, 2026-11-15: a reset left the rider busy with a vanished order) --

async def test_a_rider_left_busy_with_another_order_goes_online_again(services: Services) -> None:
    services.state, services.busy_with = "busy", "an-order-the-reset-dropped"
    city = runner.City(api_for(services), "hyd", [RIDER])
    await city.do("find_rider", order(), CUSTOMER, OWNER, NOW)
    rider = [p for _, p, _ in services.of("rider")]
    assert rider == ["/api/v1/riders/me", "/api/v1/riders/me/online", "/api/v1/riders/me"]
    services.offer = "o1"
    await city.do("find_rider", order(), CUSTOMER, OWNER, NOW)
    assert ("POST", "/api/v1/offers/o1/accept", None) in services.of("rider")


async def test_waiting_for_an_offer_keeps_the_gps_fresh(services: Services) -> None:
    services.state = "available"
    city = runner.City(api_for(services), "hyd", [RIDER])
    for k in range(3):
        await city.do("find_rider", order(), CUSTOMER, OWNER, NOW + timedelta(seconds=4 * k))
    fixes = [b for _, p, b in services.of("rider") if p == "/api/v1/delivery/driver/location"]
    assert len(fixes) == 3, "dispatch skips riders whose last fix is over 30 s old"
    assert all(0.9 <= haversine_km(KITCHEN, (f["lat"], f["lng"])) <= 1.9 for f in fixes)


async def test_signed_out_on_another_device_signs_in_again(services: Services) -> None:
    api = api_for(services)
    rider = api.person(RIDER)
    await rider.call("rt", "GET", "/riders/me")
    services.tokens.clear()  # the access token stopped working
    services.refresh_revoked = True  # and the refresh token was revoked (signed out elsewhere)
    await rider.call("rt", "GET", "/riders/me")
    assert [p for _, _, p, _ in services.calls].count("/api/v1/auth/phone") == 2


async def test_watchdog_recovers_then_cancels_a_stalled_order(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    stuck = row("stuck", "almost_ready")  # nobody ever takes it: realtime keeps the rider busy
    stuck.restaurant_accepted_at = NOW - timedelta(minutes=10)
    await (await runner.get_redis()).sadd(runner.OURS, "stuck")
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([stuck], NOW - timedelta(hours=1)))
    services.state, services.busy_with = "busy", "gone"
    city = runner.City(api_for(services), "hyd", [RIDER])
    original = services.handle

    def never_offers(request: httpx.Request) -> httpx.Response:  # going online doesn't help this time
        response = original(request)
        if request.url.path == "/api/v1/riders/me/online":
            services.state, services.busy_with = "busy", "gone"
        return response

    city.api.core._transport = city.api.rt._transport = httpx.MockTransport(never_offers)  # type: ignore[attr-defined]
    placed: list = []

    async def place(customer):  # type: ignore[no-untyped-def]
        placed.append(customer)

    monkeypatch.setattr(city, "place", place)
    assert await city.tick(NOW) == ["find_rider"]
    assert city.watches["stuck"].step == "find_rider" and city.watches["stuck"].recoveries == 0
    await city.tick(NOW + timedelta(minutes=10))
    assert city.watches["stuck"].recoveries == 0, "not yet: 15 minutes"
    sign_ins = [p for _, _, p, _ in services.calls].count("/api/v1/auth/phone")
    await city.tick(NOW + timedelta(minutes=16))
    assert city.watches["stuck"].recoveries == 1
    assert [p for _, _, p, _ in services.calls].count("/api/v1/auth/phone") == sign_ins + 1, "the rider signs in afresh"
    assert not services.of("owner"), "not cancelled on the first stall"
    await city.tick(NOW + timedelta(minutes=32))
    assert ("POST", "/api/v1/orders/stuck/cancel",
            {"reason": "other", "note": "Demo order stalled; cancelled by the demo rider simulator"}) in services.of("owner")
    assert "stuck" in city.given_up and await city.tick(NOW + timedelta(minutes=33)) == [], "left alone after"
    assert placed == [CUSTOMER], "and the next order starts"


async def test_an_order_nobody_may_cancel_is_left_and_the_next_one_starts(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    ready = row("ready-one", "ready", driver="a-person")  # another rider took it and vanished
    ready.restaurant_accepted_at = NOW - timedelta(minutes=30)
    await (await runner.get_redis()).sadd(runner.OURS, "ready-one")
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([ready], NOW - timedelta(hours=1)))
    city = runner.City(api_for(services), "hyd", [RIDER])
    placed: list = []

    async def place(customer):  # type: ignore[no-untyped-def]
        placed.append(customer)

    monkeypatch.setattr(city, "place", place)
    for minutes in (0, 16, 32):
        await city.tick(NOW + timedelta(minutes=minutes))
    assert not [c for c in services.calls if c[2].endswith("/cancel")], "only an admin may cancel a ready order"
    assert "ready-one" in city.given_up
    await city.tick(NOW + timedelta(minutes=33))
    assert placed == [CUSTOMER], "the next order starts"


def test_watch_verdicts() -> None:
    w, v = rules.watch(None, "find_rider", NOW)
    assert v == "new"
    assert rules.watch(w, "find_rider", NOW + timedelta(minutes=14))[1] == "same"
    w, v = rules.watch(w, "find_rider", NOW + timedelta(minutes=15))
    assert v == "stalled" and w.recoveries == 1 and w.since == NOW + timedelta(minutes=15)
    assert rules.watch(w, "find_rider", NOW + timedelta(minutes=20))[1] == "same"
    assert rules.watch(w, "find_rider", NOW + timedelta(minutes=30))[1] == "give_up"
    assert rules.watch(w, "to_kitchen", NOW + timedelta(minutes=30))[1] == "new", "moving on resets it"
    ride, _ = rules.watch(None, "to_home", NOW)
    assert rules.watch(ride, "to_home", NOW + timedelta(minutes=30))[1] == "same", "a ride takes as long as it takes"
    assert rules.watch(ride, "to_home", NOW + timedelta(minutes=46))[1] == "stalled"
    assert [rules.cancel_as(x) for x in ("pending_payment", "placed", "almost_ready", "ready", "picked_up")] == \
        ["customer", "kitchen", "kitchen", None, None]


# -- the simulator's own riders (Round 5, item 3) ------------------------------------

async def test_an_order_is_marked_for_the_pool_before_it_is_almost_ready(services: Services) -> None:
    city = runner.City(api_for(services), "hyd", [RIDER])
    await city.do("almost_ready", order(status="preparing"), CUSTOMER, OWNER, NOW)
    order_of = [(w, p) for w, _, p, _ in services.calls if w != "-"]
    assert order_of == [("internal", runner.POOL_ORDERS_PATH), ("rider", "/api/v1/riders/me/online"),
                        ("owner", "/api/v1/orders/o1/status")], "marked, rider about, then dispatch starts"
    assert services.marked == ["o1"]
    await city.do("find_rider", order(), CUSTOMER, OWNER, NOW)
    assert services.marked == ["o1", "o1"], "again while it waits: a realtime restart can't lose it"


async def test_orders_in_flight_together_get_different_riders(services: Services) -> None:
    city = runner.City(api_for(services), "hyd", [RIDER, RIDER2])
    city.waiting = {"o1", "o2"}
    await city.do("almost_ready", order(id="o1", status="preparing"), CUSTOMER, OWNER, NOW)
    await city.do("almost_ready", order(id="o2", status="preparing"), CUSTOMER, OWNER, NOW)
    assert city.claims == {"o1": RIDER.id, "o2": RIDER2.id}
    assert any(p == "/api/v1/riders/me/online" for _, p, _ in services.of("rider2"))
    # Realtime offered o2 to the first rider (nearer): it takes it, and the two swap.
    services.rt("rider")["offer"] = "o2"
    await city.do("find_rider", order(id="o1"), CUSTOMER, OWNER, NOW)
    assert ("POST", "/api/v1/offers/o2/accept", None) in services.of("rider")
    assert not [p for _, p, _ in services.of("rider") if p.endswith("/pass")], "never passes one of ours"
    assert city.claims == {"o1": RIDER2.id, "o2": RIDER.id}
    services.rt("rider2")["offer"] = "o1"
    await city.do("find_rider", order(id="o1"), CUSTOMER, OWNER, NOW)
    assert ("POST", "/api/v1/offers/o1/accept", None) in services.of("rider2")


async def test_a_tick_gives_the_next_order_a_rider_who_is_free(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    on_its_way = row("seeded", "picked_up", seeded=True, driver=RIDER.id, picked=NOW - timedelta(minutes=2))
    waiting = row("next", "almost_ready")
    await (await runner.get_redis()).sadd(runner.OURS, "next")
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([on_its_way, waiting], NOW - timedelta(hours=1)))
    city = runner.City(api_for(services), "hyd", [RIDER, RIDER2])
    assert await city.tick(NOW) == ["to_home", "find_rider"]
    assert city.claims == {"next": RIDER2.id}, "the first rider is carrying the other one"
    assert [p for _, p, _ in services.of("rider")] == ["/api/v1/delivery/driver/location"]
    assert "/api/v1/riders/me" in [p for _, p, _ in services.of("rider2")]


async def test_with_every_rider_on_an_order_the_next_one_waits(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    on_its_way = row("seeded", "picked_up", seeded=True, driver=RIDER.id, picked=NOW - timedelta(minutes=2))
    cooking = row("next", "preparing")
    cooking.restaurant_accepted_at = NOW - timedelta(minutes=5)
    await (await runner.get_redis()).sadd(runner.OURS, "next")
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([on_its_way, cooking], NOW - timedelta(hours=1)))
    city = runner.City(api_for(services), "hyd", [RIDER])
    assert await city.tick(NOW) == ["to_home", "almost_ready"]
    assert not services.of("owner"), "not almost ready until a rider of its own is free"
    assert not services.marked and not city.claims


async def test_off_duty_after_the_delivery_one_rider_at_a_time(services: Services, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    still = row("other", "picked_up", seeded=True, driver=RIDER2.id, picked=NOW - timedelta(minutes=1))
    monkeypatch.setattr(runner, "AsyncSessionLocal", fake_db([still], NOW - timedelta(minutes=1)))
    city = runner.City(api_for(services), "hyd", [RIDER, RIDER2])
    city.off_duty = {RIDER.id}
    await city.tick(NOW)
    assert ("POST", "/api/v1/riders/me/offline", None) in services.of("rider")
    assert not [p for _, p, _ in services.of("rider2") if p.endswith("/offline")], "the other is still riding"
    assert city.off_duty == set()


async def test_cities_group_the_pool_by_city(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    boise = SimpleNamespace(id="b1", email="rider.sim.boi.1@example.com", phone="+12085550261", country="US")
    stray = SimpleNamespace(id="x", email="rider.demo.hyd@example.com", phone="+919000000250", country="IN")

    class Db:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *a):  # type: ignore[no-untyped-def]
            return False

        async def execute(self, *_a, **_k):  # type: ignore[no-untyped-def]
            return SimpleNamespace(all=lambda: [boise, RIDER, RIDER2, stray])

    monkeypatch.setattr(runner, "AsyncSessionLocal", Db)
    api = api_for(Services())
    found = {c.key: c for c in await runner.cities(api)}
    assert set(found) == {"hyd", "boi"}
    assert found["hyd"].pool == [RIDER.id, RIDER2.id] and found["boi"].pool == ["b1"]
    again = await runner.cities(api, list(found.values()))
    assert {c.key: c for c in again}["hyd"] is found["hyd"], "a running city keeps its state"
