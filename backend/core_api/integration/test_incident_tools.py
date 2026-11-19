"""R17: the incident tools on Postgres (docs/launch/incident-plan.md). Each needs its permission in
the scope, a reason and a confirmation, and leaves an audit entry; orders already placed carry on.
Everything a test pauses it resumes (finally), so the suites after it see Hyderabad open."""
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login, move, new_order, pay, user_id
from core_api.integration.test_payments_refunds import client, delivered_order  # noqa: F401 - fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"
BASE = "/api/v1/incidents"
WHY = "R17 test: the kitchen's gas is off"


async def spice(client: AsyncClient) -> str:
    return next(r["id"] for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")


async def quote(client: AsyncClient, h: dict, rid: str):  # type: ignore[no-untyped-def]
    menu = (await client.get(f"/api/v1/restaurants/{rid}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
    return await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": [{"menu_item_id": item["id"], "quantity": 1}], "deliver_to": {"lat": 17.4483, "lng": 78.3915}})


async def log_actions(client: AsyncClient, h: dict) -> list[str]:
    r = await client.get(f"{BASE}/log", headers=h)
    assert r.status_code == 200, r.text
    return [e["action"] for e in r.json()]


async def test_an_admin_pauses_and_resumes_a_kitchen(client: AsyncClient) -> None:  # noqa: F811
    ops, ops_boi = await login(client, "ops.hyd@example.com", ADMIN), await login(client, "ops.boi@example.com", ADMIN)
    support = await login(client, "support.hyd@example.com", ADMIN)
    cust, partner = await login(client, "customer1.hyd@example.com"), await login(client, "partner.hyd@example.com")
    rid = await spice(client)
    before = await new_order(client, cust)  # placed before the pause: it carries on
    body = {"reason": WHY, "confirm": True}

    assert (await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops, json={"reason": WHY})).status_code == 422  # no confirmation
    assert (await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops, json={"reason": "gas", "confirm": True})).status_code == 422
    assert (await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops_boi, json=body)).status_code == 403  # another city
    assert (await client.post(f"{BASE}/kitchens/{rid}/pause", headers=support, json=body)).status_code == 403  # no permission
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    assert (await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops, json={**body, "back_at": past})).status_code == 409
    try:
        r = await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops, json=body)
        assert r.status_code == 200 and r.json()["closed_for_now"] is True, r.text
        a = (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()
        assert (a["open_now"], a["reason"], a["closed_for_now"], a["listed"]) == (False, "Closed for now", True, True)
        listed = next(x for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if x["id"] == rid)
        assert listed["closed_for_now"] is True and "admin_pause_reason" not in listed  # the reason stays with admins
        q = await quote(client, cust, rid)
        assert q.status_code == 422 and "Closed for now" in q.text
        # the kitchen can't undo it from its tablet
        await client.put(f"/api/v1/restaurants/{rid}/pause", headers=partner, json={"paused": False})
        assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["closed_for_now"] is True
        # the order placed before carries on: paid, accepted, cooked
        await pay(client, cust, before)
        await move(client, partner, before["id"], "accepted")
        paused = (await client.get(f"{BASE}/kitchens/paused", headers=ops)).json()
        assert any(k["id"] == rid and k["reason"] == WHY for k in paused)
    finally:
        r = await client.post(f"{BASE}/kitchens/{rid}/resume", headers=ops, json=body)
    assert r.status_code == 200 and r.json()["closed_for_now"] is False, r.text
    assert (await client.post(f"{BASE}/kitchens/{rid}/resume", headers=ops, json=body)).status_code == 409  # not paused now
    assert (await quote(client, cust, rid)).status_code == 200
    actions = await log_actions(client, ops)
    assert actions.index("kitchen.resumed") < actions.index("kitchen.paused")  # newest first


async def test_back_at_reopens_by_itself(client: AsyncClient) -> None:  # noqa: F811
    from core_api.modules.catalog.models.restaurant import Restaurant
    from shared.db import AsyncSessionLocal

    ops = await login(client, "ops.hyd@example.com", ADMIN)
    rid = await spice(client)
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    r = await client.post(f"{BASE}/kitchens/{rid}/pause", headers=ops, json={"reason": WHY, "confirm": True, "back_at": soon})
    assert r.status_code == 200 and r.json()["back_at"], r.text
    try:
        assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["back_at"]
        async with AsyncSessionLocal() as db:  # as if the hour had passed
            k = await db.get(Restaurant, uuid.UUID(rid))
            k.admin_paused_until = datetime.now(UTC) - timedelta(seconds=1)  # type: ignore[union-attr]
            await db.commit()
        assert (await client.get(f"/api/v1/restaurants/{rid}/availability")).json()["closed_for_now"] is False
    finally:
        await client.post(f"{BASE}/kitchens/{rid}/resume", headers=ops, json={"reason": WHY, "confirm": True})


async def test_ordering_pauses_for_a_city_a_country_or_everywhere(client: AsyncClient) -> None:  # noqa: F811
    ops, cm = await login(client, "ops.hyd@example.com", ADMIN), await login(client, "cm.in@example.com", ADMIN)
    root = await login(client, "admin@example.com", ADMIN)
    cust, partner = await login(client, "customer2.hyd@example.com"), await login(client, "partner.hyd@example.com")
    rid = await spice(client)
    placed = await new_order(client, cust)
    await pay(client, cust, placed)
    q = await quote(client, cust, rid)  # a quote taken before the pause: good for 10 minutes, but not to order now
    assert q.status_code == 200
    body = {"reason": "R17 test: the payment provider is down", "note": "Back by 9 pm", "confirm": True}

    assert (await client.post(f"{BASE}/ordering-pauses", headers=ops, json={**body, "scope": "IN"})).status_code == 403
    assert (await client.post(f"{BASE}/ordering-pauses", headers=cm, json={**body, "scope": "*"})).status_code == 403
    assert (await client.post(f"{BASE}/ordering-pauses", headers=cm, json={**body, "scope": "US"})).status_code == 403
    r = await client.post(f"{BASE}/ordering-pauses", headers=ops, json={**body, "scope": "IN-TG-HYD"})
    assert r.status_code == 200 and r.json()["area"] == "Hyderabad", r.text
    pause_id = r.json()["id"]
    try:
        assert (await client.post(f"{BASE}/ordering-pauses", headers=cm, json={**body, "scope": "IN-TG-HYD"})).status_code == 409
        public = (await client.get(f"{BASE}/ordering-pauses/active")).json()
        mine = next(p for p in public if p["id"] == pause_id)
        assert (mine["scope"], mine["note"]) == ("IN-TG-HYD", "Back by 9 pm") and "reason" not in mine
        refused = await quote(client, cust, rid)
        assert refused.status_code == 422 and "paused" in refused.text and "Back by 9 pm" in refused.text
        menu = (await client.get(f"/api/v1/restaurants/{rid}/menu")).json()
        item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
        o = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
            "restaurant_id": rid, "items": [{"menu_item_id": item["id"], "quantity": 1}], "payment_method": "upi",
            "quote_token": q.json()["token"],
            "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}})
        assert o.status_code == 409 and o.json()["detail"]["code"] == "ORDERING_PAUSED", o.text
        await move(client, partner, placed["id"], "accepted")  # the order in progress carries on
    finally:
        end = await client.post(f"{BASE}/ordering-pauses/{pause_id}/end", headers=ops, json={"reason": "R17 test: fixed", "confirm": True})
    assert end.status_code == 200, end.text
    assert all(p["id"] != pause_id for p in (await client.get(f"{BASE}/ordering-pauses/active")).json())
    assert (await quote(client, cust, rid)).status_code == 200

    # everywhere: only a super admin
    r = await client.post(f"{BASE}/ordering-pauses", headers=root, json={**body, "scope": "*"})
    assert r.status_code == 200, r.text
    try:
        assert "paused" in (await quote(client, cust, rid)).text
    finally:
        await client.post(f"{BASE}/ordering-pauses/{r.json()['id']}/end", headers=root, json={"reason": "R17 test: fixed", "confirm": True})
    history = (await client.get(f"{BASE}/ordering-pauses", headers=cm)).json()
    assert any(p["id"] == pause_id and p["ended_at"] and p["reason"] == body["reason"] for p in history)
    actions = await log_actions(client, cm)
    assert "ordering.paused" in actions and "ordering.resumed" in actions


async def test_bulk_refunds_and_the_second_admin(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy import select

    from core_api.modules.payments.models.payment import PaymentIntent, Refund
    from shared.db import AsyncSessionLocal

    ops, cm = await login(client, "ops.hyd@example.com", ADMIN), await login(client, "cm.in@example.com", ADMIN)
    viewer = await login(client, "viewer@example.com", ADMIN)
    cust = await login(client, "customer3.hyd@example.com")
    rid = await spice(client)
    start = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    orders = [await delivered_order(client, cust), await delivered_order(client, cust)]
    end = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    pick = {"city": "IN-TG-HYD", "restaurant_id": rid, "placed_from": start, "placed_to": end}

    assert (await client.post(f"{BASE}/refunds/preview", headers=viewer, json={**pick, "mode": "full"})).status_code == 403
    week = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    assert (await client.post(f"{BASE}/refunds/preview", headers=ops, json={**pick, "placed_from": week, "mode": "full"})).status_code == 409
    p = (await client.post(f"{BASE}/refunds/preview", headers=ops, json={**pick, "mode": "percent", "percent": "50"})).json()
    assert p["count"] == 2 and {o["order_id"] for o in p["orders"]} == {o["id"] for o in orders}
    paid = [int(Decimal(str(o["total"])) * 100) for o in orders]
    half = sum(int((Decimal(x) / 2).quantize(Decimal(1), rounding=ROUND_HALF_UP)) for x in paid)
    assert p["total"] == half and p["needs_approval"] is True  # above Hyderabad's ₹100 limit

    # half of each: above the limit, so it waits for a second admin
    r = await client.post(f"{BASE}/refunds", headers=ops, json={**pick, "mode": "percent", "percent": "50", "reason": WHY})
    assert r.status_code == 422  # no confirmation
    r = await client.post(f"{BASE}/refunds", headers=ops, json={**pick, "mode": "percent", "percent": "50", "reason": WHY, "confirm": True})
    assert r.status_code == 200 and r.json()["status"] == "pending_approval", r.text
    bulk = r.json()["id"]
    decide = {"note": "R17 test: checked the orders", "confirm": True}
    assert (await client.post(f"{BASE}/refunds/{bulk}/approve", headers=ops, json=decide)).status_code == 403  # no approval right
    r = await client.post(f"{BASE}/refunds/{bulk}/approve", headers=cm, json=decide)
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["refunded"] == p["total"], r.text
    assert (await client.post(f"{BASE}/refunds/{bulk}/approve", headers=cm, json=decide)).status_code == 409  # once
    async with AsyncSessionLocal() as db:
        intents = (await db.execute(select(PaymentIntent).where(PaymentIntent.order_id.in_([uuid.UUID(o["id"]) for o in orders])))).scalars().all()
        assert {i.status for i in intents} == {"partially_refunded"}
        refunds = (await db.execute(select(Refund).where(Refund.order_id.in_([uuid.UUID(o["id"]) for o in orders])))).scalars().all()
        assert {(r.kind, r.fault) for r in refunds} == {("amount", "goodwill")}  # the platform pays: kitchens' payouts unchanged

    # the rest in full, by the one who asks: every order above the limit again, so a second admin; this time rejected
    r = await client.post(f"{BASE}/refunds", headers=cm, json={**pick, "mode": "full", "reason": WHY, "confirm": True})
    assert r.json()["status"] == "pending_approval" and r.json()["total"] == sum(paid) - p["total"]
    assert (await client.post(f"{BASE}/refunds/{r.json()['id']}/approve", headers=cm, json=decide)).status_code == 409  # not their own
    finance = await login(client, "finance.in@example.com", ADMIN)
    assert (await client.post(f"{BASE}/refunds/{r.json()['id']}/reject", headers=finance, json=decide)).json()["status"] == "rejected"

    # small enough for the city's limit: runs at once, no approval
    r = await client.post(f"{BASE}/refunds", headers=ops, json={**pick, "mode": "percent", "percent": "1", "reason": WHY, "confirm": True})
    assert r.json()["status"] == "done", r.text
    listed = (await client.get(f"{BASE}/refunds", headers=ops)).json()
    assert {x["status"] for x in listed if x["id"] in (bulk, r.json()["id"])} == {"done"}
    actions = await log_actions(client, cm)
    for a in ("bulk_refund.requested", "bulk_refund.approved", "bulk_refund.rejected", "bulk_refund.done"):
        assert a in actions


async def test_bulk_messages_reach_test_accounts_in_their_language(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy import select

    from core_api.modules.identity.models.user import User
    from shared.db import AsyncSessionLocal
    from shared.outbox import OutboxEvent

    ops = await login(client, "ops.hyd@example.com", ADMIN)
    support = await login(client, "support.hyd@example.com", ADMIN)
    cust = await login(client, "customer4.hyd@example.com")
    rid = await spice(client)
    start = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    order = await delivered_order(client, cust)
    pick = {"city": "IN-TG-HYD", "restaurant_id": rid, "placed_from": start,
            "placed_to": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()}
    bulk = (await client.post(f"{BASE}/refunds", headers=ops, json={**pick, "mode": "percent", "percent": "1", "reason": WHY,
                                                                     "confirm": True})).json()
    assert bulk["status"] == "done", bulk

    templates = {t["key"]: t for t in (await client.get(f"{BASE}/messages/templates", headers=ops)).json()}
    assert templates["refund_sent"]["per_order"] and templates["delay"]["needs"] == ["time"]
    assert (await client.get(f"{BASE}/messages/templates", headers=support)).status_code == 403
    # a per-order message needs a bulk refund's customers; a city message needs what the admin fills in
    r = await client.post(f"{BASE}/messages/preview", headers=ops, json={"city": "IN-TG-HYD", "template": "refund_sent"})
    assert r.status_code == 409
    r = await client.post(f"{BASE}/messages/preview", headers=ops, json={"city": "IN-TG-HYD", "template": "area_paused"})
    assert r.status_code == 409 and "area" in r.text

    p = (await client.post(f"{BASE}/messages/preview", headers=ops, json={"bulk_refund_id": bulk["id"], "template": "refund_sent"})).json()
    assert p["recipients"] == 1 and p["only_test_accounts"] is True and "Spice Route Kitchen" in p["sample"]["body"]
    r = await client.post(f"{BASE}/messages", headers=ops, json={"bulk_refund_id": bulk["id"], "template": "refund_sent",
                                                                 "reason": WHY, "confirm": True})
    assert r.status_code == 200 and r.json()["recipients"] == 1, r.text
    async with AsyncSessionLocal() as db:
        ev = (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "incident.message",
                                                          OutboxEvent.aggregate_id == r.json()["id"]))).scalars().all()
        assert len(ev) == 1
        payload = ev[0].envelope["payload"]
        assert (payload["user_id"], payload["order_id"], payload["template"]) == (user_id(cust), order["id"], "refund_sent")
        assert payload["params"]["restaurant"] == "Spice Route Kitchen" and payload["params"]["amount"].startswith("₹")

    # outside production only test accounts: a real-looking customer is skipped
    async with AsyncSessionLocal() as db:
        u = await db.get(User, uuid.UUID(user_id(cust)))
        saved = (u.email, u.phone)  # type: ignore[union-attr]
        u.email, u.phone = f"someone.{uuid.uuid4().hex[:6]}@gmail.com", None  # type: ignore[union-attr]
        await db.commit()
    try:
        p = (await client.post(f"{BASE}/messages/preview", headers=ops, json={
            "city": "IN-TG-HYD", "template": "area_paused", "params": {"area": "Hyderabad"}})).json()
        assert p["skipped"] >= 1 and p["recipients"] >= 1, p
        before = p["recipients"]
        r = await client.post(f"{BASE}/messages", headers=ops, json={"city": "IN-TG-HYD", "template": "area_paused",
                                                                     "params": {"area": "Hyderabad"}, "reason": WHY, "confirm": True})
        assert r.json()["recipients"] == before and r.json()["skipped"] == p["skipped"]
        async with AsyncSessionLocal() as db:
            ev = (await db.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == r.json()["id"]))).scalars().all()
            assert user_id(cust) not in {e.envelope["payload"]["user_id"] for e in ev}
    finally:
        async with AsyncSessionLocal() as db:
            u = await db.get(User, uuid.UUID(user_id(cust)))
            u.email, u.phone = saved  # type: ignore[union-attr]
            await db.commit()
    assert "customers.messaged" in await log_actions(client, ops)
    assert (await client.get(f"{BASE}/messages", headers=ops)).json()[0]["template"] == "area_paused"


def test_test_accounts_are_the_fixed_code_ones() -> None:
    from core_api.modules.incidents.service import covers, is_test_account

    assert is_test_account("customer1.hyd@example.com", None) and is_test_account(None, "+919000012345")
    assert not is_test_account("someone@gmail.com", "+919876543210")
    assert covers("*", "IN-TG-HYD") and covers("IN", "IN-TG-HYD") and covers("IN-TG-HYD", "IN-TG-HYD")
    assert not covers("US", "IN-TG-HYD") and not covers("IN-TG-HY", "IN-TG-HYD")
