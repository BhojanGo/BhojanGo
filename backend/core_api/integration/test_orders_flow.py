"""P11 order flow end to end on Postgres: happy path, each timeout, late
payment, cancel window, who may move an order, outbox and its relay."""
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def login(client: AsyncClient, email: str, pw: str = "BhojanGo123") -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def new_order(client: AsyncClient, h: dict) -> dict:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": cart,
                                                                    "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
        "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}})
    assert r.status_code == 201, r.text
    return r.json()


async def pay(client: AsyncClient, h: dict, order: dict, outcome: str = "succeeded") -> dict:
    r = await client.post("/api/v1/payments/initiate", headers=h, json={"order_id": order["id"], "payment_method_type": "upi"})
    assert r.status_code == 201, r.text
    intent = r.json()
    r = await client.post(f"/api/v1/payments/fake/{intent['payment_intent_id']}/complete", headers=h, json={"outcome": outcome})
    assert r.status_code == 200, r.text
    return intent


async def get(client: AsyncClient, h: dict, order_id: str) -> dict:
    r = await client.get(f"/api/v1/orders/{order_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def move(client: AsyncClient, h: dict, order_id: str, new: str):  # type: ignore[no-untyped-def]
    return await client.put(f"/api/v1/orders/{order_id}/status", headers=h, json={"status": new})


async def sweep(minutes: float) -> dict:
    from core_api.modules.orders.service.order import OrderService
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        counts = await OrderService(db).sweep(now=datetime.now(UTC) + timedelta(minutes=minutes))
        await db.commit()
    return counts


async def outbox_types(order_id: str) -> list[str]:
    from sqlalchemy import select

    from shared.db import AsyncSessionLocal
    from shared.outbox import OutboxEvent

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(OutboxEvent).where(OutboxEvent.aggregate_id == order_id)
                                 .order_by(OutboxEvent.created_at))).scalars().all()
    return [r.event_type for r in rows]


async def payment(order_id: str) -> dict:
    from sqlalchemy import select

    from core_api.modules.payments.models.payment import PaymentIntent
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(PaymentIntent).where(PaymentIntent.order_id == uuid.UUID(order_id))
                                 .order_by(PaymentIntent.created_at))).scalars().all()
    return {"status": rows[-1].status, "amount": rows[-1].amount, "refunded": rows[-1].refunded_amount} if rows else {}


async def test_happy_path(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)
    assert order["status"] == "pending_payment" and order["market_city"] == "IN-TG-HYD"
    due = datetime.fromisoformat(order["payment_due_at"])
    assert timedelta(minutes=9) < due - datetime.now(UTC) <= timedelta(minutes=10)

    # The amount comes from the order; a wrong one is refused.
    r = await client.post("/api/v1/payments/initiate", headers=cust,
                          json={"order_id": order["id"], "payment_method_type": "upi", "amount": 100, "currency": "INR"})
    assert r.status_code == 409 and "AMOUNT_MISMATCH" in r.text
    intent = await pay(client, cust, order)
    assert intent["amount"] == int(Decimal(str(order["total"])) * 100) and intent["provider"] == "fake"

    o = await get(client, cust, order["id"])
    assert o["status"] == "placed" and o["placed_at"] and o["accept_due_at"]
    assert timedelta(seconds=170) < datetime.fromisoformat(o["accept_due_at"]) - datetime.now(UTC) <= timedelta(seconds=180)

    partner = await login(client, "partner.hyd@example.com")
    other_partner = await login(client, "partner.boi@example.com")
    assert (await move(client, other_partner, order["id"], "accepted")).status_code == 404
    assert (await move(client, cust, order["id"], "accepted")).status_code == 403
    for s in ("accepted", "preparing", "almost_ready", "ready"):
        r = await move(client, partner, order["id"], s)
        assert r.status_code == 200 and r.json()["status"] == s, r.text

    rider, rider2 = await login(client, "rider1.hyd@example.com"), await login(client, "rider2.hyd@example.com")
    assert (await move(client, partner, order["id"], "picked_up")).status_code == 403
    r = await move(client, rider, order["id"], "picked_up")
    assert r.status_code == 200 and r.json()["driver_id"]
    assert (await move(client, rider2, order["id"], "delivered")).status_code == 404  # not their order
    r = await move(client, rider, order["id"], "delivered")
    assert r.json()["status"] == "delivered" and r.json()["actual_delivery_time"]

    assert await outbox_types(order["id"]) == [
        "order.created", "payment.succeeded", "order.placed",
        "order.status_changed", "order.status_changed", "order.status_changed", "order.status_changed",
        "order.status_changed", "order.status_changed",
    ]
    # Who can see it.
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=other_partner)).status_code == 404
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=await login(client, "customer2.hyd@example.com"))).status_code == 404
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=await login(client, "ops.hyd@example.com", "BhojanGoAdmin1"))).status_code == 200
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=await login(client, "ops.boi@example.com", "BhojanGoAdmin1"))).status_code == 404


async def test_unpaid_order_cancels_after_ten_minutes(client: AsyncClient) -> None:
    cust = await login(client, "customer2.hyd@example.com")
    order = await new_order(client, cust)
    assert (await sweep(minutes=9))["payment_timeout"] == 0 or (await get(client, cust, order["id"]))["status"] == "pending_payment"
    assert (await get(client, cust, order["id"]))["status"] == "pending_payment"
    await sweep(minutes=11)
    o = await get(client, cust, order["id"])
    assert (o["status"], o["cancellation_reason"], o["cancelled_by"]) == ("cancelled", "payment_timeout", "system")
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "upi"})
    assert r.status_code == 409 and "ORDER_NOT_PAYABLE" in r.text


async def test_payment_arriving_after_the_timeout_is_refunded(client: AsyncClient) -> None:
    cust = await login(client, "customer3.hyd@example.com")
    order = await new_order(client, cust)
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "upi"})
    intent = r.json()
    await sweep(minutes=11)  # the customer took too long in the payment app
    assert (await get(client, cust, order["id"]))["status"] == "cancelled"
    r = await client.post(f"/api/v1/payments/fake/{intent['payment_intent_id']}/complete", headers=cust, json={"outcome": "succeeded"})
    assert r.status_code == 200
    assert (await get(client, cust, order["id"]))["status"] == "cancelled"
    p = await payment(order["id"])
    assert p["status"] == "refunded" and p["refunded"] == p["amount"]
    assert {"order.payment_after_cancel", "payment.refunded"} <= set(await outbox_types(order["id"]))


async def test_restaurant_that_does_not_accept_in_three_minutes(client: AsyncClient) -> None:
    cust = await login(client, "customer4.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order)
    await sweep(minutes=2)
    assert (await get(client, cust, order["id"]))["status"] == "placed"
    await sweep(minutes=4)
    o = await get(client, cust, order["id"])
    assert (o["status"], o["cancellation_reason"]) == ("cancelled", "restaurant_no_response")
    p = await payment(order["id"])
    assert p["status"] == "refunded" and p["refunded"] == p["amount"]
    # Too late for the restaurant now.
    assert (await move(client, await login(client, "partner.hyd@example.com"), order["id"], "accepted")).status_code == 409


async def test_failed_payment_keeps_the_order_waiting(client: AsyncClient) -> None:
    cust = await login(client, "customer5.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order, outcome="failed")
    assert (await get(client, cust, order["id"]))["status"] == "pending_payment"
    await pay(client, cust, order)  # the retry is a new payment attempt
    assert (await get(client, cust, order["id"]))["status"] == "placed"


async def test_customer_cancel_rules(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    partner = await login(client, "partner.hyd@example.com")

    placed = await new_order(client, cust)
    await pay(client, cust, placed)
    r = await client.post(f"/api/v1/orders/{placed['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (await payment(placed["id"]))["status"] == "refunded"

    accepted = await new_order(client, cust)
    await pay(client, cust, accepted)
    await move(client, partner, accepted["id"], "accepted")
    from sqlalchemy import update

    from core_api.modules.orders.models.order import Order
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:  # placed 5 minutes ago: past the 2-minute window
        await db.execute(update(Order).where(Order.id == uuid.UUID(accepted["id"]))
                         .values(placed_at=datetime.now(UTC) - timedelta(minutes=5)))
        await db.commit()
    r = await client.post(f"/api/v1/orders/{accepted['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
    assert r.status_code == 409 and "CANCEL_WINDOW_PASSED" in r.text
    r = await client.post(f"/api/v1/orders/{accepted['id']}/cancel", headers=partner, json={"reason": "item_unavailable"})
    assert r.status_code == 200 and r.json()["cancelled_by"] == "restaurant"


async def test_outbox_relay_publishes_each_event_once() -> None:
    from worker.app.services.outbox_relay import relay_once

    sent: list[dict] = []
    while await relay_once(publish=lambda row: sent.append(row.envelope)):
        pass
    assert sent and all({"event_id", "event_type", "payload", "timestamp"} <= set(e) for e in sent)
    assert any(e["event_type"] == "order.placed" for e in sent)
    assert await relay_once(publish=lambda row: sent.append(row.envelope)) == 0
