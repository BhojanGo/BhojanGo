"""Access-control sweep for realtime: every endpoint without a token, with the
wrong role, and against someone else's order or offer. Every route needs a
policy; a new one without it fails."""
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import delivery
from app.services import dispatch, shifts
from app.services.core_api import CoreApiError
from shared.auth import encode_jwt

REFUSED = {401, 403, 404}
ORDER = str(uuid.uuid4())
OTHER_ORDER = str(uuid.uuid4())
IDS = {name: str(uuid.uuid4()) for name in ("customer", "other_customer", "partner", "rider", "other_rider", "ops_hyd",
                                            "ops_boi", "viewer")}
ROLES = {"customer": ("customer", []), "other_customer": ("customer", []), "partner": ("restaurant_owner", []),
         "rider": ("driver", []), "other_rider": ("driver", []), "ops_hyd": ("customer", ["city_ops@IN-TG-HYD"]),
         "ops_boi": ("customer", ["city_ops@US-ID-BOI"]), "viewer": ("customer", ["viewer@*"])}


def token(actor: str) -> dict:
    role, adm = ROLES[actor]
    now = int(time.time())
    t = encode_jwt({"sub": IDS[actor], "type": "access", "role": role, "country": "IN", "adm": adm,
                    "iat": now, "exp": now + 900})
    return {"Authorization": f"Bearer {t}"}


def info(order: str = ORDER, **kw: Any) -> dict:
    return {"order_id": order, "status": "picked_up", "customer_id": IDS["customer"], "restaurant_id": str(uuid.uuid4()),
            "restaurant_name": "Spice Route", "driver_id": IDS["rider"], "market_city": "IN-TG-HYD",
            "pickup": [17.4486, 78.3908], "dropoff": [17.43, 78.41], "offer_timeout_seconds": 30, "distance_unit": "km", **kw}


class FakeCore:
    async def dispatch_info(self, order: str) -> dict:
        if order not in (ORDER, OTHER_ORDER):
            raise CoreApiError(404, "Order not found")
        return info(order, driver_id=None, status="almost_ready") if order == OTHER_ORDER else info(order)

    async def assign_rider(self, order: str, rider: str) -> dict:
        return info(order, driver_id=rider)


@dataclass
class Policy:
    kind: str  # public | user | admin
    refused: list[str] = field(default_factory=list)
    body: Any = None
    why: str = ""


NOT_ADMINS = ["customer", "partner", "rider"]
POLICY: dict[tuple[str, str], Policy] = {
    ("GET", "/health"): Policy("public", why="probe"), ("GET", "/health/live"): Policy("public", why="probe"),
    ("GET", "/health/ready"): Policy("public", why="probe"), ("GET", "/metrics"): Policy("public", why="scraped in the VPC"),
    # riders: their own state, offers made to them, deliveries assigned to them
    ("POST", "/api/v1/riders/me/online"): Policy("user", ["customer", "partner"], {"lat": 17.45, "lng": 78.39}),
    ("POST", "/api/v1/riders/me/offline"): Policy("user", ["customer", "partner"]),
    ("GET", "/api/v1/riders/me"): Policy("user", ["customer", "partner"]),
    # OTHER_ORDER is on offer to other_rider: the rider (busy with ORDER) can't take or pass it
    ("POST", "/api/v1/offers/{order_id}/accept"): Policy("user", ["customer", "partner", "rider"]),
    ("POST", "/api/v1/offers/{order_id}/pass"): Policy("user", ["customer", "partner", "rider"]),
    ("POST", "/api/v1/delivery/driver/location"): Policy("user", ["customer", "partner", "other_rider"],
                                                         {"lat": 17.45, "lng": 78.39, "order_id": ORDER}),
    ("GET", "/api/v1/delivery/driver/active-order"): Policy("user", ["customer", "partner"]),
    ("GET", "/api/v1/delivery/{order_id}/eta"): Policy("user", ["other_customer", "other_rider", "partner", "ops_boi"]),
    ("POST", "/api/v1/drivers/me/shift/start"): Policy("user", ["customer", "partner", "ops_hyd"]),
    ("POST", "/api/v1/drivers/me/shift/activity"): Policy("user", ["customer", "partner", "ops_hyd"], {"status": "waiting"}),
    ("GET", "/api/v1/drivers/me/shift"): Policy("user", ["customer", "partner", "ops_hyd"]),
    ("POST", "/api/v1/drivers/me/shift/end"): Policy("user", ["customer", "partner", "ops_hyd"]),
    ("POST", "/api/v1/drivers/me/earnings/estimate"): Policy("user", ["customer", "partner", "ops_hyd"], {
        "available_minutes": 60, "active_minutes": 30, "waiting_minutes": 0}),
    # admins
    ("POST", "/api/v1/delivery/assign"): Policy("admin", NOT_ADMINS + ["ops_boi", "viewer"],
                                                {"order_id": OTHER_ORDER, "driver_id": IDS["other_rider"]}),
    ("GET", "/api/v1/dispatch/shadow-batches"): Policy("admin", NOT_ADMINS + ["viewer"]),
}


def routes() -> list[tuple[str, str]]:
    from fastapi.routing import APIRoute

    from app.main import app

    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            out |= {(m, r.path) for m in r.methods}
        elif type(r).__name__ == "_IncludedRouter":
            out |= {(m, c.path) for c in r.effective_route_contexts() for m in (c.methods or ())}
    return sorted((m, p) for m, p in out if m != "HEAD")


@pytest.fixture
async def client(monkeypatch):  # type: ignore[no-untyped-def]
    redis = fakeredis.aioredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)

    async def get() -> fakeredis.aioredis.FakeRedis:
        return redis

    for mod in (dispatch, shifts):
        monkeypatch.setattr(mod, "get_redis", get)
    fake = FakeCore()
    monkeypatch.setattr(dispatch, "core_api", fake)
    monkeypatch.setattr(delivery, "core_api", fake)
    # The rider is delivering ORDER; OTHER_ORDER is on offer to the other rider.
    await dispatch.go_online(IDS["rider"], 17.45, 78.39)
    await redis.hset(dispatch.state_key(IDS["rider"]), mapping={"status": "busy", "order_id": ORDER})
    await dispatch.go_online(IDS["other_rider"], 17.45, 78.39)
    offer = {"order_id": OTHER_ORDER, "rider_id": IDS["other_rider"], "expires_in": 30}
    await redis.set(dispatch.offer_key(OTHER_ORDER), json.dumps(offer), ex=60)
    await redis.hset(dispatch.state_key(IDS["other_rider"]), mapping={"status": "offered", "order_id": OTHER_ORDER})
    await redis.zadd(dispatch.OFFER_EXPIRY, {OTHER_ORDER: time.time() + 30})
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def path_for(template: str, method: str) -> str:
    order = OTHER_ORDER if template.startswith("/api/v1/offers/") else ORDER
    return template.format(order_id=order)


async def call(client: AsyncClient, method: str, template: str, actor: str | None):  # type: ignore[no-untyped-def]
    p = POLICY[(method, template)]
    kw: dict[str, Any] = {"headers": token(actor) if actor else {}}
    if p.body is not None:
        kw["json"] = p.body
    return await client.request(method, path_for(template, method), **kw)


def test_every_route_has_a_policy() -> None:
    have = set(routes())
    assert not sorted(have - set(POLICY)), f"routes with no access policy: {sorted(have - set(POLICY))}"
    assert not sorted(set(POLICY) - have), f"stale policies: {sorted(set(POLICY) - have)}"


PROTECTED = [k for k, p in POLICY.items() if p.kind != "public"]


@pytest.mark.parametrize(("method", "path"), PROTECTED, ids=[f"{m} {p}" for m, p in PROTECTED])
async def test_no_token_is_refused(client: AsyncClient, method: str, path: str) -> None:
    r = await call(client, method, path, None)
    assert r.status_code in {401, 403}, f"{method} {path} without a token → {r.status_code} {r.text[:200]}"


CASES = [(m, p, a) for (m, p), pol in POLICY.items() for a in pol.refused]


@pytest.mark.parametrize(("method", "path", "actor"), CASES, ids=[f"{m} {p} as {a}" for m, p, a in CASES])
async def test_wrong_role_or_someone_elses_resource_is_refused(client: AsyncClient, method: str, path: str, actor: str) -> None:
    r = await call(client, method, path, actor)
    assert r.status_code in REFUSED, f"{method} {path} as {actor} → {r.status_code} {r.text[:300]}"


async def test_the_right_people_still_get_in(client: AsyncClient) -> None:
    """The sweep's own control: the same requests succeed for their owners."""
    assert (await client.get(f"/api/v1/delivery/{ORDER}/eta", headers=token("customer"))).status_code == 200
    assert (await client.get(f"/api/v1/delivery/{ORDER}/eta", headers=token("ops_hyd"))).status_code == 200
    r = await client.post("/api/v1/delivery/driver/location", headers=token("rider"),
                          json={"lat": 17.45, "lng": 78.39, "order_id": ORDER})
    assert r.status_code == 200
    assert (await client.post(f"/api/v1/offers/{OTHER_ORDER}/pass", headers=token("other_rider"))).status_code == 200
