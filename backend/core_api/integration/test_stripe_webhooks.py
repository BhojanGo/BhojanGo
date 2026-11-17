"""Stripe's side of checkout on Postgres with Stripe mocked (GitHub CI never
holds Stripe keys; the real test-mode run is tools/stripe_e2e on the QA runner):
initiate hands out the PaymentSheet / Payment Element payload, signed webhooks
move the order pending_payment -> placed (once, however often Stripe retries),
a declined attempt keeps the order payable, refunds by item go to Stripe as a
Refund of the item's amount, and a refund that fails at Stripe is taken back."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login, new_order

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


@pytest.fixture
def stripe_mock(monkeypatch):  # type: ignore[no-untyped-def]
    """Stripe's API replaced by recorders; the order's gateway is Stripe."""
    import stripe

    from core_api.modules.payments.api.v1 import payments as api
    from core_api.modules.payments.service import gateways
    from shared.config import get_settings

    calls: dict[str, list] = {"pi": [], "refund": []}

    def pi_create(**kw):  # type: ignore[no-untyped-def]
        calls["pi"].append(kw)
        n = uuid.uuid4().hex[:12]
        return type("PI", (), {"id": f"pi_{n}", "client_secret": f"pi_{n}_secret_x"})()

    def refund_create(**kw):  # type: ignore[no-untyped-def]
        calls["refund"].append(kw)
        return type("R", (), {"id": f"re_{uuid.uuid4().hex[:12]}", "status": "succeeded", "amount": kw.get("amount")})()

    monkeypatch.setattr(stripe.PaymentIntent, "create", pi_create)
    monkeypatch.setattr(stripe.Refund, "create", refund_create)
    monkeypatch.setattr(stripe.Customer, "create", lambda **kw: type("C", (), {"id": f"cus_{uuid.uuid4().hex[:8]}"})())
    monkeypatch.setattr(stripe.EphemeralKey, "create", lambda **kw: type("K", (), {"secret": "ek_test_x"})())
    monkeypatch.setattr(stripe.Webhook, "construct_event",
                        lambda payload, sig, secret: __import__("json").loads(payload) if sig == "t=1,v1=ok" else
                        (_ for _ in ()).throw(stripe.SignatureVerificationError("bad", sig)))
    monkeypatch.setattr(api, "get_gateway", lambda country: gateways.StripeGateway())
    monkeypatch.setattr(get_settings().payments, "STRIPE_PUBLISHABLE_KEY", "pk_test_ci")
    return calls


async def hook(client: AsyncClient, event: dict, sig: str = "t=1,v1=ok"):  # type: ignore[no-untyped-def]
    import json

    return await client.post("/api/v1/payments/stripe/webhook", content=json.dumps(event).encode(),
                             headers={"stripe-signature": sig})


async def test_webhooks_drive_the_order_and_refunds(client: AsyncClient, stripe_mock) -> None:  # type: ignore[no-untyped-def]
    cust = await login(client, "customer5.hyd@example.com")
    order = await new_order(client, cust)
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "card"})
    assert r.status_code == 201, r.text
    c = r.json()["checkout"]
    assert c["sdk"] == "stripe_payment_sheet" and c["publishable_key"] == "pk_test_ci"
    assert c["customer_ephemeral_key"] == "ek_test_x" and c["payment_intent_client_secret"].startswith("pi_")
    pi1 = c["payment_intent_client_secret"].split("_secret_")[0]
    assert stripe_mock["pi"][0]["idempotency_key"] == f"{order['id']}:attempt-1"
    assert stripe_mock["pi"][0]["payment_method_types"] == ["card", "link"]

    # A forged webhook is refused; a declined attempt keeps the order payable.
    assert (await hook(client, {"id": "evt_x", "type": "payment_intent.succeeded", "data": {"object": {"id": pi1}}},
                       sig="t=1,v1=forged")).status_code == 400
    r = await hook(client, {"id": f"evt_{uuid.uuid4().hex}", "type": "payment_intent.payment_failed", "data": {"object": {
        "id": pi1, "last_payment_error": {"message": "Your card was declined."}}}})
    assert r.status_code == 200
    st = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)).json()
    assert (st["payment_status"], st["order_status"], st["can_retry"]) == ("failed", "pending_payment", True)
    assert st["failure_reason"] == "Your card was declined."

    # Second attempt: a new PaymentIntent; Stripe's success places the order, once.
    r = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "card"})
    pi2 = r.json()["checkout"]["payment_intent_client_secret"].split("_secret_")[0]
    assert pi2 != pi1 and stripe_mock["pi"][1]["idempotency_key"] == f"{order['id']}:attempt-2"
    ok = {"id": f"evt_{uuid.uuid4().hex}", "type": "payment_intent.succeeded", "data": {"object": {"id": pi2}}}
    assert (await hook(client, ok)).json() == {"received": True}
    assert (await hook(client, ok)).json().get("duplicate") is True  # Stripe retried the same event
    st = (await client.get(f"/api/v1/payments/orders/{order['id']}/status", headers=cust)).json()
    assert (st["payment_status"], st["order_status"]) == ("succeeded", "placed")

    # Refund one item through Stripe: a Refund of exactly that amount, keyed by our refund id.
    ops = await login(client, "ops.hyd@example.com", ADMIN)
    item = order["items"][0]["menu_item_id"]
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=ops,
                          json={"items": [{"menu_item_id": item, "quantity": 1}], "reason": "missing_item"})
    assert r.status_code == 201, r.text
    refund = r.json()
    sent = stripe_mock["refund"][0]
    assert sent["payment_intent"] == pi2 and sent["amount"] == refund["amount"]
    assert sent["idempotency_key"] == f"refund:{refund['id']}" and sent["metadata"]["order_id"] == order["id"]

    # Stripe later says that refund failed: it's taken back off the payment.
    r = await hook(client, {"id": f"evt_{uuid.uuid4().hex}", "type": "refund.failed", "data": {"object": {
        "id": refund["provider_refund_id"], "status": "failed", "amount": refund["amount"], "payment_intent": pi2}}})
    assert r.json() == {"received": True, "updated": 1}
    refunds = (await client.get(f"/api/v1/payments/orders/{order['id']}/refunds", headers=cust)).json()
    assert [x["status"] for x in refunds] == ["failed"]
    pay = (await client.get(f"/api/v1/payments/{order['id']}", headers=cust)).json()
    assert pay["status"] == "succeeded"
