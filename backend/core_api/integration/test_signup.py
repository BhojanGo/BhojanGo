"""B1 on Postgres: a new number signs up as a rider (onboarding checklist) or
applies with a kitchen (partner application); both reach the admin queues."""
import os
import random

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def new_number(client: AsyncClient) -> dict:
    """A brand-new phone signs in (fixed seed code for the +919000000… range)."""
    phone = f"+9190000{random.randint(10000, 99999)}"
    assert (await client.post("/api/v1/auth/send-otp", json={"phone": phone, "country": "IN"})).status_code == 200
    r = await client.post("/api/v1/auth/phone", json={"phone": phone, "otp": "123456", "country": "IN"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "customer", r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_rider_signs_up_and_lands_in_onboarding(client: AsyncClient) -> None:
    h = await new_number(client)
    r = await client.post("/api/v1/riders/apply", headers=h, json={"full_name": "Kiran Rao", "city_code": "IN-TG-HYD"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "driver", r.text
    rider = {"Authorization": f"Bearer {r.json()['access_token']}"}
    o = (await client.get("/api/v1/riders/me/onboarding", headers=rider)).json()
    assert o["first_name"] == "Kiran" and o["ready"] is False and o["steps"][0]["status"] == "done"
    assert (await client.post("/api/v1/riders/apply", headers=rider, json={"full_name": "Kiran Rao", "city_code": "IN-TG-HYD"})).status_code == 200
    # A number with orders, a city we're not in, and an admin's account are refused.
    cust = await login(client, "customer1.hyd@example.com")
    assert (await client.post("/api/v1/riders/apply", headers=cust, json={"full_name": "X Y", "city_code": "IN-TG-HYD"})).json()["detail"]["code"] == "HAS_ORDERS"
    assert (await client.post("/api/v1/riders/apply", headers=await new_number(client), json={"full_name": "X Y", "city_code": "IN-TG-WGL"})).status_code == 422


async def test_kitchen_applies_and_waits_for_approval(client: AsyncClient) -> None:
    h = await new_number(client)
    r = await client.post("/api/v1/restaurants/apply", headers=h, json={
        "full_name": "Lata Menon", "kitchen_name": "Lata's Kitchen", "city_code": "IN-TG-HYD", "street": "Plot 9, Road 12",
        "area": "Banjara Hills", "zip": "500034", "lat": 17.4126, "lng": 78.4400, "cuisines": ["Kerala"]})
    assert r.status_code == 201 and r.json()["user"]["role"] == "restaurant_owner", r.text
    partner = {"Authorization": f"Bearer {r.json()['access_token']}"}
    rid = r.json()["restaurant_id"]
    mine = (await client.get("/api/v1/restaurants/mine", headers=partner)).json()
    assert [(k["id"], k["status"]) for k in mine] == [(rid, "pending_approval")]
    a = (await client.get(f"/api/v1/restaurants/{rid}/application", headers=partner)).json()
    assert a["done"] == 1 and a["current"] == "fssai"
    ops = await login(client, "ops.hyd@example.com", "BhojanGoAdmin1")
    assert rid in [k["id"] for k in (await client.get("/api/v1/restaurants/admin/pending", headers=ops)).json()]
