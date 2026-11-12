"""P12 on Postgres: checkout payloads, "payment didn't go through", Razorpay
verify, refunds by item with tax, agent limits, and who may refund."""
import hashlib
import hmac
import os
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login, move, new_order, pay

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def delivered_order(client: AsyncClient, cust: dict) -> dict:
    order = await new_order(client, cust)  # 2 × Veg Dum Biryani at Spice Route
    await pay(client, cust, order)
    partner, rider = await login(client, "partner.hyd@example.com"), await login(client, "rider1.hyd@example.com")
    for s in ("accepted", "preparing", "ready"):
        await move(client, partner, order["id"], s)
    from core_api.integration.test_orders_flow import assign

    await assign(client, order["id"], rider)
    await move(client, rider, order["id"], "picked_up")
    await move(client, rider, order["id"], "delivered")
    return order


async def test_checkout_payload_and_failed_payment(client: AsyncClient) -> None:
    cust = await login(client, "customer2.hyd@example.com")
    order = await new_order(client, cust)
    r = await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)
    assert r.json()["payment_status"] == "not_started" and r.json()["can_retry"] is True

    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "upi",
                                                                         "payment_method_id": "upi_fail"})
    checkout = r.json()["checkout"]
    assert checkout["sdk"] == "fake" and checkout["mimics"] == "razorpay_checkout"
    assert checkout["methods"] == ["upi", "card", "wallet"]  # India's methods (markets settings)
    assert checkout["complete_path"].endswith(f"{r.json()['payment_intent_id']}/complete")
    held = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)).json()["price_held_until"]

    await client.post(f"/api/v1/payments/fake/{r.json()['payment_intent_id']}/complete", headers=cust, json={})
    st = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)).json()
    assert (st["payment_status"], st["order_status"], st["can_retry"]) == ("failed", "pending_payment", True)
    assert st["failure_reason"] and st["price_held_until"] >= held and st["amount"] == int(Decimal(str(order["total"])) * 100)

    await pay(client, cust, order)  # tries again with another method
    st = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)).json()
    assert (st["payment_status"], st["order_status"], st["attempts"]) == ("succeeded", "placed", 2)


async def test_razorpay_checkout_verify(client: AsyncClient, monkeypatch) -> None:
    from core_api.modules.payments.models.payment import PaymentIntent
    from shared.config import get_settings
    from shared.db import AsyncSessionLocal

    cust = await login(client, "customer3.hyd@example.com")
    order = await new_order(client, cust)
    rzp_order, rzp_pay = f"order_rzp_{uuid.uuid4().hex[:10]}", f"pay_{uuid.uuid4().hex[:10]}"
    async with AsyncSessionLocal() as db:  # as if Razorpay had created the order
        from sqlalchemy import select

        from core_api.modules.identity.models.user import User

        user = (await db.execute(select(User).where(User.email == "customer3.hyd@example.com"))).scalar_one()
        db.add(PaymentIntent(order_id=uuid.UUID(order["id"]), user_id=user.id, provider="razorpay",
                             provider_payment_id=rzp_order, amount=int(Decimal(str(order["total"])) * 100),
                             currency="INR", status="pending", idempotency_key=str(uuid.uuid4()), metadata_={}))
        await db.commit()
    monkeypatch.setattr(get_settings().payments, "RAZORPAY_KEY_SECRET", "rzp_test_secret")
    sig = hmac.new(b"rzp_test_secret", f"{rzp_order}|{rzp_pay}".encode(), hashlib.sha256).hexdigest()
    body = {"razorpay_order_id": rzp_order, "razorpay_payment_id": rzp_pay, "razorpay_signature": sig}
    bad = await client.post("/api/v1/payments/razorpay/verify", headers=cust, json={**body, "razorpay_signature": "x"})
    assert bad.status_code == 400
    r = await client.post("/api/v1/payments/razorpay/verify", headers=cust, json=body)
    assert r.status_code == 200 and r.json() == {"received": True}
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=cust)).json()["status"] == "placed"
    r = await client.post("/api/v1/payments/razorpay/verify", headers=cust, json=body)
    assert r.json()["duplicate"] is True  # the webhook or a retry later changes nothing


async def test_refund_by_item_with_tax_and_limits(client: AsyncClient) -> None:
    cust = await login(client, "customer4.hyd@example.com")
    order = await delivered_order(client, cust)
    biryani = order["items"][0]["menu_item_id"]
    support = await login(client, "support.hyd@example.com", ADMIN)

    # One biryani back: its price, its discount share and its GST.
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "missing_item"})
    assert r.status_code == 201, r.text
    first = r.json()
    assert first["reason"] == "missing_item" and first["fault"] == "restaurant"
    line = first["lines"][0]
    assert line["quantity"] == 1 and line["food"] == "240.00" and Decimal(line["tax"]) > 0
    assert first["amount"] == int(Decimal(line["amount"]) * 100)

    # Support picks a reason from the list; free text is refused.
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "cold food"})
    assert r.status_code == 422

    # Hyderabad lowers the support limit to ₹200 per order (a business rule):
    # the second biryani would take this order over it.
    cm = await login(client, "cm.in@example.com", ADMIN)
    rule = (await client.post("/api/v1/rules", headers=cm, json={
        "family": "business", "template": "support_refund_limit", "params": {"max_per_order": 200},
        "scope_level": "city", "scope_id": "IN-TG-HYD"})).json()
    await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=cm)
    try:
        r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support, json={
            "items": [{"menu_item_id": biryani, "quantity": 1}], "include_delivery_fee": True, "reason": "late"})
        assert r.status_code == 403 and "refund limit of INR 200" in r.text
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=await login(client, "finance.in@example.com", ADMIN), json={})
    ops = await login(client, "ops.hyd@example.com", ADMIN)
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=ops, json={
        "items": [{"menu_item_id": biryani, "quantity": 1}], "include_delivery_fee": True, "reason": "late"})
    assert r.status_code == 201, r.text
    assert r.json()["fault"] == "delivery"
    # Nothing left of that item, and the delivery fee is done.
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=ops,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "missing_item"})
    assert r.status_code == 409

    refunds = (await client.get(f"/api/v1/payments/orders/{order['id']}/refunds", headers=cust)).json()
    assert len(refunds) == 2 and all(x["status"] == "succeeded" for x in refunds)
    pay_status = (await client.get(f"/api/v1/payments/{order['id']}", headers=cust)).json()
    assert pay_status["status"] == "partially_refunded"


@pytest.mark.parametrize(("email", "status"), [
    ("ops.boi@example.com", 403),       # another city
    ("viewer@example.com", 403),        # no refunds.issue
    ("finance.in@example.com", 201),    # finance can
])
async def test_who_can_refund(client: AsyncClient, email, status) -> None:
    cust = await login(client, "customer5.hyd@example.com")
    order = await delivered_order(client, cust)
    h = await login(client, email, ADMIN)
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=h,
                          json={"items": [{"menu_item_id": order["items"][0]["menu_item_id"], "quantity": 1}], "reason": "quality"})
    assert r.status_code == status, r.text


async def test_customers_cannot_refund_themselves(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)
    r = await client.post(f"/api/v1/payments/{order['id']}/refund", headers=cust, json={"reason": "free money"})
    assert r.status_code in (404, 405)
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=cust,
                          json={"items": [{"menu_item_id": order["items"][0]["menu_item_id"], "quantity": 1}], "reason": "goodwill"})
    assert r.status_code == 403
    other = await login(client, "customer2.hyd@example.com")
    assert (await client.get(f"/api/v1/payments/orders/{order['id']}/refunds", headers=other)).status_code == 404
