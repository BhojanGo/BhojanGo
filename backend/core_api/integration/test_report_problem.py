"""B5 on Postgres: the customer reports a problem with a delivered order. Up to
the city's automatic refund limit (Hyderabad ₹100 per order) it's refunded at
once, charged by the reason's fault rule; above it, support gets a ticket with
the items, the reason and the photo."""
import os
import uuid

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import PNG, client, login, pay  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def chai_order(client: AsyncClient, h: dict, cups: int) -> tuple[dict, str]:  # noqa: F811
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Charminar Chai House")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    chai = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Irani Chai")
    cart = [{"menu_item_id": chai["id"], "quantity": cups}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": cart,
                                                                    "deliver_to": {"lat": 17.3650, "lng": 78.4700}})
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
        "delivery_address": {"street": "Lane 4", "city": "Hyderabad", "state": "Telangana", "zip": "500002", "country": "IN"}})
    assert r.status_code == 201, r.text
    return r.json(), chai["id"]


async def delivered(order_id: str) -> None:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE orders SET status = 'delivered', actual_delivery_time = now() WHERE id = :i"), {"i": order_id})
        await db.commit()


async def test_report_a_problem(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order, chai = await chai_order(client, cust, 6)
    await pay(client, cust, order)
    url = f"/api/v1/orders/{order['id']}/problems"
    one = {"items": [{"menu_item_id": chai, "quantity": 1}], "reason": "missing_item"}
    r = await client.post(url, headers=cust, json=one)
    assert r.status_code == 409 and "delivered" in r.text  # not yet
    await delivered(order["id"])
    other = await login(client, "customer2.hyd@example.com")
    assert (await client.post(url, headers=other, json=one)).status_code == 404

    # One missing chai: well under ₹100, refunded at once and charged to the kitchen.
    r = await client.post(url, headers=cust, json={**one, "note": "Only five came"})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["outcome"] == "refunded" and first["limit"] == "100" and 0 < float(first["amount"]) < 100
    refunds = (await client.get(f"/api/v1/payments/orders/{order['id']}/refunds", headers=cust)).json()
    assert [(x["reason"], x["fault"]) for x in refunds] == [("missing_item", "restaurant")]

    # Four more, with a photo: over the limit (with the first), so support gets a ticket.
    up = await client.post("/api/v1/uploads", headers=cust, data={"purpose": "problem_photo"}, files={"file": ("cups.png", PNG, "image/png")})
    assert up.status_code == 201, up.text
    # A customer uploads problem photos only, never delivery proof or documents.
    bad = await client.post("/api/v1/uploads", headers=cust, data={"purpose": "delivery_proof"}, files={"file": ("x.png", PNG, "image/png")})
    assert bad.status_code == 403
    r = await client.post(url, headers=cust, json={"items": [{"menu_item_id": chai, "quantity": 4}], "reason": "quality",
                                                   "note": "Cold and watery", "photo_key": up.json()["key"]})
    assert r.status_code == 201 and r.json()["outcome"] == "ticket" and r.json()["ticket_id"], r.text
    tid = r.json()["ticket_id"]
    assert len((await client.get(f"/api/v1/payments/orders/{order['id']}/refunds", headers=cust)).json()) == 1  # nothing more yet
    # More than are left to refund: refused.
    r = await client.post(url, headers=cust, json={"items": [{"menu_item_id": chai, "quantity": 6}], "reason": "quality"})
    assert r.status_code == 409
    # Someone else's photo key: refused.
    r = await client.post(url, headers=cust, json={**one, "photo_key": "problem_photo/" + str(uuid.uuid4()) + "/x.png"})
    assert r.status_code == 422

    support = await login(client, "support.hyd@example.com", "BhojanGoAdmin1")
    t = next(x for x in (await client.get("/api/v1/ops/tickets", headers=support, params={"scope": "IN-TG-HYD"})).json() if x["id"] == tid)
    assert t["kind"] == "problem" and t["topic"] == "quality" and t["order_id"] == order["id"] and t["note"] == "Cold and watery"
    assert t["details"]["items"][0]["quantity"] == 4 and t["details"]["reason_words"] == "Not good"
    key = t["details"]["photo_key"]
    assert (await client.get("/api/v1/uploads/view", headers=support, params={"key": key})).status_code == 200
    boise = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")
    assert (await client.get("/api/v1/uploads/view", headers=boise, params={"key": key})).status_code == 404
    r = await client.post(f"/api/v1/ops/tickets/{tid}/resolve", headers=support, json={"resolution": "Refunded 4 chai by item"})
    assert r.status_code == 200
