"""Delivery PINs on the migrated database (R27): every order gets its own random PIN, the
seed customers too (no fixed 1234 for seed phones any more); the customer gets it from the
API only once the rider has picked the order up; the rider hands over with it."""
import os
import re

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from core_api.integration.test_orders_flow import assign, client, login, move, new_order, pay  # noqa: F401  (client: fixture)
from core_api.modules.orders.service.pin import is_weak

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def pin_of(order_id: str) -> str:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return (await db.execute(text("SELECT delivery_pin FROM orders WHERE id = :i"), {"i": order_id})).scalar()


async def test_seed_customers_get_random_pins(client: AsyncClient) -> None:  # noqa: F811
    pins = []
    for email in ("customer1.hyd@example.com", "customer2.hyd@example.com"):
        h = await login(client, email)
        pins += [await pin_of((await new_order(client, h))["id"]) for _ in range(3)]
    assert all(re.fullmatch(r"\d{4}", p) and not is_weak(p) for p in pins), pins
    assert len(set(pins)) > 1, pins  # six equal random PINs: 1 in 10^20
    assert "1234" not in pins


async def test_pin_reaches_the_customer_only_after_pickup(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    oid = order["id"]
    url = f"/api/v1/orders/{oid}"

    async def shown() -> tuple[str | None, str | None]:
        one = (await client.get(url, headers=cust)).json()["pin"]
        page = (await client.get("/api/v1/orders", headers=cust, params={"limit": 100})).json()["items"]
        return one, next((o["pin"] for o in page if o["id"] == oid), None)  # the website's active-order bar

    assert await shown() == (None, None)  # waiting for payment
    await pay(client, cust, order)
    assert await shown() == (None, None)  # placed
    partner = await login(client, "partner.hyd@example.com")
    for s in ("accepted", "preparing", "ready"):
        await move(client, partner, oid, s)
        assert await shown() == (None, None), s
    rider = await login(client, "rider1.hyd@example.com")
    await assign(client, oid, rider)
    assert await shown() == (None, None)  # a rider is on the way to the kitchen: still not yet

    await move(client, rider, oid, "picked_up")
    pin = await pin_of(oid)
    assert await shown() == (pin, pin)
    assert (await client.get(url, headers=rider)).json()["pin"] is None  # the rider asks for it at the door

    r = await move(client, rider, oid, "delivered", {"method": "pin", "pin": pin})
    assert r.status_code == 200 and r.json()["status"] == "delivered", r.text
    assert (await client.get(url, headers=cust)).json()["pin"] is None  # done with it
