"""R32 pickup orders on a migrated, seeded Postgres: the quote has no delivery fee and the pickup platform fee (5% of
food, at least $0.99); the order needs no delivery address and never gets a delivery partner; the restaurant marks
it ready, the customer (only) sees the 4-digit code, the restaurant enters it to complete the order; a wrong code is
refused and 5 wrong codes lock the order until support helps. A restaurant with pickup off can't be quoted for it."""
import os
from decimal import ROUND_HALF_UP, Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login, move, outbox_types, pay
from core_api.integration.test_tax import client, menu  # noqa: F401 - fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
C = Decimal("0.01")


async def boise_pickup(client: AsyncClient, cust: dict) -> tuple[str, list[dict], dict]:  # noqa: F811
    rid, items = await menu(client, "boise-bowl-co-hyde-park")
    cart = [{"menu_item_id": items["Teriyaki Chicken Bowl"], "quantity": 2}]
    r = await client.post("/api/v1/pricing/quote", headers=cust, json={
        "restaurant_id": rid, "items": cart, "fulfillment": "pickup", "tip": "3"})
    assert r.status_code == 200, r.text
    return rid, cart, r.json()


async def place_pickup(client: AsyncClient, cust: dict, rid: str, cart: list[dict], q: dict) -> dict:  # noqa: F811
    import uuid

    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "card", "quote_token": q["token"]})
    assert r.status_code == 201, r.text
    return r.json()


async def ready_order(client: AsyncClient, cust: dict, partner: dict) -> dict:  # noqa: F811
    rid, cart, q = await boise_pickup(client, cust)
    order = await place_pickup(client, cust, rid, cart, q)
    await pay(client, cust, order)
    for s in ("accepted", "preparing", "ready"):
        r = await move(client, partner, order["id"], s)
        assert r.status_code == 200, (s, r.text)
    return order


async def test_pickup_quote_order_code_and_lock(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.boi@example.com")
    partner = await login(client, "partner.boi@example.com")

    # The quote: no delivery fee, no tip, 5% platform fee (at least $0.99); priced at the restaurant's address.
    rid, cart, q = await boise_pickup(client, cust)
    codes = {ln["code"] for ln in q["lines"]}
    assert "delivery_fee" not in codes and "tip" not in codes
    food = sum(Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] == "food")
    fee = sum(Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] == "platform_fee")
    assert fee == max(Decimal("0.99"), (food * Decimal("0.05")).quantize(C, rounding=ROUND_HALF_UP))
    assert q["fulfillment"] == "pickup" and q["pickup_address"]["street"] == "1520 N 13th St"
    # R33: Idaho taxes the food and the platform fee (6%), through the tax provider and the state's rule
    tax = next(ln for ln in q["lines"] if ln["code"] == "tax")
    assert Decimal(tax["amount"]) == ((food + fee) * Decimal("0.06")).quantize(C, rounding=ROUND_HALF_UP), tax
    assert tax["detail"]["targets"] == "food,platform_fee", tax["detail"]

    # A restaurant that hasn't turned pickup on can't be quoted for it.
    other = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                 if r["currency"] == "USD" and not r["pickup_enabled"])
    _, their = await menu(client, other["slug"])
    r = await client.post("/api/v1/pricing/quote", headers=cust, json={
        "restaurant_id": other["id"], "items": [{"menu_item_id": next(iter(their.values())), "quantity": 1}],
        "fulfillment": "pickup"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "PICKUP_OFF", r.text

    # The order: no delivery address needed; the restaurant marks it ready; only the customer sees the code.
    order = await ready_order(client, cust, partner)
    mine = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()
    assert mine["fulfillment"] == "pickup" and mine["status"] == "ready" and mine["driver_id"] is None
    assert len(mine["pickup_code"]) == 4 and mine["pin"] is None
    assert mine["pickup_address"]["street"] == "1520 N 13th St" and mine["pickup_locked"] is False
    theirs = (await client.get(f"/api/v1/orders/{order['id']}", headers=partner)).json()
    assert theirs["pickup_code"] is None

    # No delivery partner, and no completing it without the code.
    assert (await move(client, partner, order["id"], "picked_up")).status_code == 409
    r = await move(client, partner, order["id"], "delivered", proof={"method": "photo", "photo_key": "x"})
    assert r.status_code == 409, r.text
    # The customer can't enter it for the restaurant.
    assert (await client.post(f"/api/v1/orders/{order['id']}/pickup", headers=cust,
                              json={"code": mine["pickup_code"]})).status_code == 404

    # The right code completes it; the snapshot pays no delivery partner.
    r = await client.post(f"/api/v1/orders/{order['id']}/pickup", headers=partner, json={"code": mine["pickup_code"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "delivered"
    ops = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")
    snap = (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=ops)).json()
    assert Decimal(snap["split"]["rider"]) == 0 and snap["context"]["fulfillment"] == "pickup"
    assert snap["context"]["routing"] == "none"
    assert "order.status_changed" in await outbox_types(order["id"])

    # Wrong codes: refused with the tries left; the 5th locks it (the restaurant calls support).
    order = await ready_order(client, cust, partner)
    code = (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["pickup_code"]
    wrong = f"{(int(code) + 1) % 10000:04d}"
    for left in (4, 3, 2, 1):
        r = await client.post(f"/api/v1/orders/{order['id']}/pickup", headers=partner, json={"code": wrong})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "PICKUP_CODE_WRONG", r.text
        assert f"{left} tr" in r.json()["detail"]["message"]
    r = await client.post(f"/api/v1/orders/{order['id']}/pickup", headers=partner, json={"code": wrong})
    assert r.status_code == 423 and r.json()["detail"]["code"] == "PICKUP_LOCKED", r.text
    assert "support" in r.json()["detail"]["message"].lower()
    # locked: even the right code is refused now
    r = await client.post(f"/api/v1/orders/{order['id']}/pickup", headers=partner, json={"code": code})
    assert r.status_code == 423, r.text
    locked = (await client.get(f"/api/v1/orders/{order['id']}", headers=partner)).json()
    assert locked["pickup_locked"] is True and locked["status"] == "ready"


async def test_routing_fallback_alert_and_the_admin_tile(client: AsyncClient) -> None:  # noqa: F811
    """R32: over 5% of an hour's delivery prices (at least 20) on the fallback raises one Operations alert for
    the hour; a later healthy hour resolves it. The tile counts placed orders by road vs fallback (24 h)."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete, select

    from core_api.modules.pricing.service import routing_stats as rs
    from core_api.modules.support.models import OpsAlert
    from shared.db import AsyncSessionLocal
    from shared.redis import get_redis

    hour = datetime(2031, 1, 2, 3, 15, tzinfo=UTC)  # an hour no real traffic uses
    later = hour + timedelta(hours=1)
    redis = await get_redis()
    await redis.delete(f"routing:{rs._hour(hour)}", f"routing:{rs._hour(later)}")
    async with AsyncSessionLocal() as db:
        await db.execute(delete(OpsAlert).where(OpsAlert.name == rs.ALERT_NAME))
        await db.commit()
        for _ in range(19):
            await rs.record_routing(db, "road", hour)
        await rs.record_routing(db, "fallback", hour)  # 1 of 20 = 5%: not over
        assert (await db.execute(select(OpsAlert).where(OpsAlert.name == rs.ALERT_NAME))).scalars().all() == []
        await rs.record_routing(db, "fallback", hour)  # 2 of 21 = 9.5%
        alert = (await db.execute(select(OpsAlert).where(OpsAlert.name == rs.ALERT_NAME))).scalar_one()
        assert alert.status == "firing" and alert.fingerprint == rs.fingerprint(hour) and "9.5%" in alert.summary
        for _ in range(20):  # the next hour is healthy: the alert ends
            await rs.record_routing(db, "road", later)
        await db.refresh(alert)
        assert alert.status == "resolved"
        await db.execute(delete(OpsAlert).where(OpsAlert.name == rs.ALERT_NAME))
        await db.commit()
    await redis.delete(f"routing:{rs._hour(hour)}", f"routing:{rs._hour(later)}")

    ops = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")
    tile = (await client.get("/api/v1/ops/routing", headers=ops)).json()
    assert tile["hours"] == 24 and tile["alert_pct"] == 5.0
    assert tile["pickup"] >= 1  # the pickup orders above have no distance
    measured = tile["road"] + tile["fallback"]
    assert tile["road_pct"] is None if measured == 0 else tile["road_pct"] + tile["fallback_pct"] == 100.0
