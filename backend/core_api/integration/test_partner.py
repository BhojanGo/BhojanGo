"""P19 on Postgres: the partner tablet. Pause (and its end), busy +10 min on
new orders, prep time chosen at accept, offers the restaurant funds with a
weekly cap, the application steps, and the customer's first name on the board."""
import os
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login, move, pay

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


async def spice(client: AsyncClient) -> tuple[str, str]:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
    return rest["id"], item["id"]


async def quote(client: AsyncClient, h: dict, rid: str, item: str) -> dict:
    r = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": [{"menu_item_id": item, "quantity": 2}], "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    assert r.status_code == 200, r.text
    return r.json()


async def order_from(client: AsyncClient, h: dict, rid: str, item: str, q: dict) -> dict:
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": [{"menu_item_id": item, "quantity": 2}], "payment_method": "upi", "quote_token": q["token"],
        "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}})
    assert r.status_code == 201, r.text
    return r.json()


async def test_pause_ends_by_itself_and_busy_adds_prep(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid, item = await spice(client)
    mine = (await client.get("/api/v1/restaurants/mine", headers=partner)).json()
    assert {r["name"] for r in mine} >= {"Spice Route Kitchen"} and all(r["status"] == "active" for r in mine)
    assert (await client.get("/api/v1/restaurants/mine", headers=cust)).json() == []
    base = (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()
    assert base["paused"] is False and base["name"] == "Spice Route Kitchen" and base["currency"] == "INR"

    r = await client.put(f"/api/v1/restaurants/{rid}/pause", headers=partner, json={"paused": True, "minutes": 15})
    assert r.status_code == 200 and r.json()["paused"] and r.json()["paused_until"], r.text
    a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
    assert a["open_now"] is False and a["reason"] == "Paused by the restaurant"
    # Fifteen minutes later it takes orders again without anyone touching it.
    from sqlalchemy import update

    from core_api.modules.catalog.models.restaurant import Restaurant
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(update(Restaurant).where(Restaurant.id == uuid.UUID(rid)).values(
            paused_until=datetime.now(UTC) - timedelta(minutes=1)))
        await db.commit()
    assert (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()["paused"] is False
    assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["reason"] != "Paused by the restaurant"
    await client.put(f"/api/v1/restaurants/{rid}/pause", headers=partner, json={"paused": False})

    r = await client.put(f"/api/v1/restaurants/{rid}/busy", headers=partner, json={"extra_minutes": 10})
    assert r.json()["busy_extra_minutes"] == 10 and r.json()["prep_minutes"] == base["prep_minutes"] + 10
    try:
        o = await order_from(client, cust, rid, item, await quote(client, cust, rid, item))
        assert o["estimated_prep_minutes"] == base["prep_minutes"] + 10
    finally:
        await client.put(f"/api/v1/restaurants/{rid}/busy", headers=partner, json={"extra_minutes": 0})

    # The kitchen says how long it'll take when it accepts; the board shows the customer's first name.
    await pay(client, cust, o)
    r = await client.put(f"/api/v1/orders/{o['id']}/status", headers=partner, json={"status": "accepted", "prep_minutes": 30})
    assert r.status_code == 200 and r.json()["estimated_prep_minutes"] == 30, r.text
    board = (await client.get(f"/api/v1/orders/restaurant/{rid}", headers=partner, params={"limit": 20})).json()["items"]
    mine = next(x for x in board if x["id"] == o["id"])
    assert mine["customer"] == {"name": "Srini"}
    await move(client, partner, o["id"], "preparing")


async def test_offer_the_restaurant_funds_stops_at_the_weekly_cap(client: AsyncClient) -> None:
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid, item = await spice(client)
    r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
        "template": "flat_off", "name": "₹50 off biryani", "amount": "50", "weekly_cap": "100"})
    assert r.status_code == 201, r.text
    offer = next(x for x in r.json() if x["name"] == "₹50 off biryani")
    assert offer["live"] and float(offer["weekly_cap"]) == 100
    try:
        def promo(q: dict) -> list[dict]:
            return [ln for ln in q["lines"] if ln["code"] == "promotion"]

        # ₹50 off beats the city's platform launch offer (10% of ₹480 = ₹48) until this week's ₹100 is used.
        for _ in range(2):
            q = await quote(client, cust, rid, item)
            assert [(float(p["amount"]), p["funded_by"]) for p in promo(q)] == [(-50, "restaurant")]
            await order_from(client, cust, rid, item, q)
        assert [p["funded_by"] for p in promo(await quote(client, cust, rid, item))] == ["platform"]  # cap reached
        listed = next(x for x in (await client.get(f"/api/v1/restaurants/{rid}/offers", headers=partner)).json()
                      if x["id"] == offer["id"])
        assert float(listed["used_this_week"]) == 100 and listed["orders_this_week"] == 2 and listed["live"] is False
    finally:
        r = await client.post(f"/api/v1/restaurants/{rid}/offers/{offer['id']}/end", headers=partner)
        assert r.status_code == 200, r.text
    assert all(x["id"] != offer["id"] for x in r.json())
    # Someone else's offer id can't be ended through this restaurant.
    other = await login(client, "partner.boi@example.com")
    assert (await client.post(f"/api/v1/restaurants/{rid}/offers/{offer['id']}/end", headers=other)).status_code == 403


async def test_application_steps(client: AsyncClient) -> None:
    h = await login(client, "applicant.hyd@example.com")
    from sqlalchemy import select

    from core_api.modules.catalog.models.restaurant import Restaurant
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rid = str((await db.execute(select(Restaurant.id).where(Restaurant.slug == "kesar-kitchen-kondapur"))).scalar())
    a = (await client.get(f"/api/v1/restaurants/{rid}/application", headers=h)).json()
    assert (a["done"], a["total"], a["current"], a["status"]) == (1, 5, "fssai", "pending_approval")
    assert a["commission_percent"] == "15.0" and [s["title"] for s in a["steps"]][1] == "FSSAI licence"
    from core_api.integration.test_orders_flow import upload

    assert (await upload(client, h, "rider_document")).status_code == 403  # partners upload partner documents only
    key = (await upload(client, h, "partner_document")).json()["key"]
    r = await client.put(f"/api/v1/restaurants/{rid}/licence", headers=h, json={
        "fssai_number": "13623012000487", "fssai_expires_on": (date.today() + timedelta(days=500)).isoformat(), "document_key": key})
    assert r.status_code == 200 and r.json()["document_key"] == key, r.text
    assert (await client.put(f"/api/v1/restaurants/{rid}/gst", headers=h, json={"gstin": "nope"})).status_code == 422
    a = (await client.put(f"/api/v1/restaurants/{rid}/gst", headers=h, json={"gstin": "36AABCU9603R1ZM"})).json()
    assert a["done"] == 2 and a["current"] == "gst_bank" and a["fssai_document"] and a["gstin"] == "36AABCU9603R1ZM"
    assert a["payout_account"] is None  # still needs the bank
    # The pending kitchen isn't listed for customers.
    assert all(x["id"] != rid for x in (await client.get("/api/v1/restaurants", params={"limit": 100})).json()["items"])


async def test_admin_pauses_a_kitchens_offer(client: AsyncClient) -> None:
    """B4: a kitchen's own offer goes live without approval; city ops can pause it
    (the kitchen sees why, customers stop getting it) and resume it, all audited."""
    partner, cust = await login(client, "partner.hyd@example.com"), await login(client, "customer1.hyd@example.com")
    rid, item = await spice(client)
    r = await client.post(f"/api/v1/restaurants/{rid}/offers", headers=partner, json={
        "template": "flat_off", "name": "₹60 off, pause test", "amount": "60", "weekly_cap": "100000"})
    offer = next(x for x in r.json() if x["name"] == "₹60 off, pause test")
    assert r.status_code == 201 and offer["live"] and not offer["paused"]  # live at once, no approval

    def kitchen_promo(q: dict) -> list[float]:
        return [float(ln["amount"]) for ln in q["lines"] if ln["code"] == "promotion" and ln.get("funded_by") == "restaurant"]

    try:
        assert kitchen_promo(await quote(client, cust, rid, item)) == [-60]
        pw = "BhojanGoAdmin1"
        for who in ("ops.boi@example.com", "support.hyd@example.com", "viewer@example.com"):
            h = await login(client, who, pw)
            assert (await client.post(f"/api/v1/rules/{offer['id']}/pause", headers=h, json={"reason": "Checking it"})).status_code in (403, 404)
        ops = await login(client, "ops.hyd@example.com", pw)
        r = await client.post(f"/api/v1/rules/{offer['id']}/pause", headers=ops, json={"reason": "Price looks wrong, please check"})
        assert r.status_code == 200 and r.json()["paused_reason"] == "Price looks wrong, please check", r.text
        assert (await client.post(f"/api/v1/rules/{offer['id']}/pause", headers=ops, json={"reason": "again"})).status_code == 409
        assert kitchen_promo(await quote(client, cust, rid, item)) == []
        listed = next(x for x in (await client.get(f"/api/v1/restaurants/{rid}/offers", headers=partner)).json() if x["id"] == offer["id"])
        assert listed["paused"] and not listed["live"] and listed["paused_reason"] == "Price looks wrong, please check"

        r = await client.post(f"/api/v1/rules/{offer['id']}/resume", headers=ops)
        assert r.status_code == 200 and r.json()["paused_at"] is None
        assert kitchen_promo(await quote(client, cust, rid, item)) == [-60]

        # Only kitchens' own offers pause; platform rules are ended instead.
        rules = (await client.get("/api/v1/rules", headers=ops, params={"family": "delivery_fee"})).json()
        hyd = next(x for x in rules if x["status"] == "published" and x["market_scope"].startswith("IN"))
        cm = await login(client, "cm.in@example.com", pw)
        assert (await client.post(f"/api/v1/rules/{hyd['id']}/pause", headers=cm, json={"reason": "nope"})).status_code == 409

        from sqlalchemy import select

        from core_api.modules.audit.models import AuditLog
        from shared.db import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            acts = [a.action for a in (await db.execute(select(AuditLog).where(AuditLog.entity_id == r.json()["rule_key"])
                                                         .order_by(AuditLog.at))).scalars()]
        assert acts[-2:] == ["offer.paused", "offer.resumed"] and "partner_offer_started" in acts
    finally:
        await client.post(f"/api/v1/restaurants/{rid}/offers/{offer['id']}/end", headers=partner)


async def test_today_when_open_all_day(client: AsyncClient) -> None:
    """Regression: with an "open all day" override (00:00–00:00, which conftest
    gives every seeded restaurant) there's no closing time; the tablet's /today
    fell back to the legacy closes_at string and crashed."""
    partner = await login(client, "partner.hyd@example.com")
    rid, _ = await spice(client)
    r = await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)
    assert r.status_code == 200, r.text
