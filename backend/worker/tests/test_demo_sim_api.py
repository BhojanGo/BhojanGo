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
RIDER = SimpleNamespace(id="rider-1", email="rider.demo.hyd@example.com", phone="+919000000250", country="IN")
CUSTOMER = SimpleNamespace(id="cust-1", email="demo1.hyd@example.com", phone="+919000000301", country="IN")
OWNER = SimpleNamespace(id="owner-1", email="partner.demo.hyd@example.com", phone="+919000000910", country="IN")
PHONES = {RIDER.phone: "rider", CUSTOMER.phone: "customer", OWNER.phone: "owner"}


class Services:
    """core_api and realtime, as far as the simulator uses them; records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict | None]] = []  # (who, method, path, body)
        self.tokens: dict[str, str] = {}
        self.offer: str | None = None
        self.state = "offline"
        self.closed_kitchens: set[str] = set()

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
        if path == "/api/v1/auth/refresh":
            return self._tokens(body["refresh_token"].split(":")[1], path, body)
        who = self.who(request)
        if not who:
            return httpx.Response(401, json={"detail": "Invalid credentials"})
        self.calls.append((who, method, path, body))
        if path == "/api/v1/riders/me" and method == "GET":
            return httpx.Response(200, json={"state": {"status": self.state},
                                             "offer": {"order_id": self.offer} if self.offer else None})
        if path == "/api/v1/riders/me/online":
            self.state = "available"
        if path.startswith("/api/v1/offers/") and path.endswith("/accept"):
            self.state, self.offer = "busy", None
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
    city = runner.City(api, "hyd", RIDER)
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
    city = runner.City(api, "hyd", RIDER)
    for step, status in (("accept", "accepted"), ("prepare", "preparing"), ("almost_ready", "almost_ready"), ("ready", "ready")):
        await city.do(step, order(), CUSTOMER, OWNER, NOW)
        assert services.of("owner")[-1] == ("PUT", "/api/v1/orders/o1/status", {"status": status})
    assert any(p == "/api/v1/riders/me/online" for _, p, _ in services.of("rider")), "the rider is about before dispatch"


async def test_riding_sends_gps_and_delivers_with_the_customers_pin(services: Services) -> None:
    api = api_for(services)
    city = runner.City(api, "hyd", RIDER)
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
    assert city.go_offline, "off duty once realtime has seen the delivery (City.tick)"


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
    city = runner.City(api, "hyd", RIDER)
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
    city = runner.City(api_for(services), "hyd", RIDER)
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
