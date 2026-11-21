"""R27 on Postgres: a kitchen takes orders only while its tablet is live. The tablet's board
polls are its heartbeat; 60 s without one and the kitchen is paused for customers ("Not
taking orders right now"): no quote, no order, no payment, and a payment that lands anyway is
refunded at once. The next heartbeat brings it back, and the tablet is told what happened."""
import os
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import get, login
from core_api.integration.test_partner import order_from, quote, spice

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client(monkeypatch):  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.config import get_settings
    from shared.db import engine
    from shared.redis import close_redis

    monkeypatch.setattr(get_settings().catalog, "KITCHEN_TABLET_REQUIRED", "1")  # as on QA and in production
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def silent_for(rid: str, seconds: float) -> None:
    """The tablet's last heartbeat was this long ago."""
    from shared import kitchen_live as K
    from shared.redis import get_redis

    r = await get_redis()
    await r.delete(K.tablet_key(rid), K.sim_key(rid), K.gap_key(rid))
    await K.beat(rid, "poll", r, now=time.time() - seconds)


async def test_no_tablet_heartbeat_pauses_the_kitchen_and_the_next_one_resumes_it(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid, item = await spice(client)

    # The tablet polls its board: a heartbeat. The kitchen takes orders.
    await silent_for(rid, 120)
    assert (await client.get(f"/api/v1/orders/restaurant/{rid}", headers=partner, params={"limit": 5})).status_code == 200
    a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
    assert a["open_now"] is True and a["not_taking_orders"] is False, a
    waiting = await order_from(client, cust, rid, item, await quote(client, cust, rid, item))  # pending payment
    late = await order_from(client, cust, rid, item, await quote(client, cust, rid, item))
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": late["id"], "payment_method_type": "upi"})
    assert r.status_code == 201, r.text
    started = r.json()
    unused_quote = await quote(client, cust, rid, item)

    # 61 s without a heartbeat: paused for customers.
    await silent_for(rid, 61)
    a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
    assert (a["open_now"], a["reason"], a["not_taking_orders"]) == (False, "Not taking orders right now", True), a
    r = await client.post("/api/v1/pricing/quote", headers=cust, json={
        "restaurant_id": rid, "items": [{"menu_item_id": item, "quantity": 2}], "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    assert r.status_code in (409, 422) and "Not taking orders right now" in r.text, r.text
    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": [{"menu_item_id": item, "quantity": 2}], "payment_method": "upi",
        "quote_token": unused_quote["token"],
        "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "KITCHEN_OFFLINE", r.text
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": waiting["id"], "payment_method_type": "upi"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "KITCHEN_OFFLINE", r.text
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": late["id"], "payment_method_type": "upi"})
    assert r.status_code == 409, "an open checkout isn't handed back either"
    # A payment started before the pause that completes now: cancelled and refunded at once.
    r = await client.post(f"/api/v1/payments/fake/{started['payment_intent_id']}/complete", headers=cust, json={"outcome": "succeeded"})
    assert r.status_code == 200, r.text
    o = await get(client, cust, late["id"])
    assert o["status"] == "cancelled" and o["cancellation_reason"] == "restaurant_no_response", o
    assert (await get(client, cust, waiting["id"]))["status"] == "pending_payment"

    # An admin looking at the board is no heartbeat.
    ops = await login(client, "ops.hyd@example.com", "BhojanGoAdmin1")
    await client.get(f"/api/v1/orders/restaurant/{rid}", headers=ops, params={"limit": 5})
    assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["not_taking_orders"] is True

    # The tablet is back (its header poll): open again, and it is told customers couldn't order.
    today = (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()
    assert today["not_taking_orders"] is False and today["open_now"] is True, today
    assert today["offline_from"] and today["offline_to"], today
    a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
    assert a["open_now"] is True and a["not_taking_orders"] is False
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": waiting["id"], "payment_method_type": "upi"})
    assert r.status_code == 201, r.text
    await order_from(client, cust, rid, item, await quote(client, cust, rid, item))


async def test_the_demo_simulator_keeps_a_kitchen_open_only_until_a_tablet_runs_it(client: AsyncClient) -> None:
    from shared import kitchen_live as K
    from shared.redis import get_redis

    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid, item = await spice(client)
    r = await get_redis()
    await r.delete(K.tablet_key(rid), K.sim_key(rid), K.gap_key(rid))
    await K.sim_beat([rid], r)  # QA's demo simulator plays this kitchen; no tablet has run it
    assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["open_now"] is True
    await quote(client, cust, rid, item)
    # A tablet opens it, then goes quiet: the simulator no longer keeps it open.
    await silent_for(rid, 120)
    await K.sim_beat([rid], r)
    assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["not_taking_orders"] is True
    await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)  # leave it open for the other tests
