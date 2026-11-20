"""R21 security review (docs/launch/security-review.md): one test per HIGH finding,
each failing without its fix.

S2  A Razorpay webhook with no secret configured (production has no Razorpay keys)
    was checked against an empty HMAC key, which anyone can sign with; and a
    provider's event could settle another provider's payment. Either placed an
    order nobody paid for.
S3  POST /wallet/topup credited any amount without taking a payment, and the
    wallet then paid for real orders.
S4  A kitchen's owner could set its own status (go live without approval, undo a
    suspension) through PUT /restaurants/{id}.
S5  (access sweep extension) A kitchen can't reach another kitchen's dishes, option
    groups or offers by putting their ids under its own restaurant's path.
"""
import hashlib
import hmac
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login, new_order, payment

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


async def _order_status(client: AsyncClient, h: dict, order_id: str) -> str:
    r = await client.get(f"/api/v1/orders/{order_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["status"]


async def _open_payment(client: AsyncClient, h: dict) -> tuple[dict, str]:
    """An order waiting for payment and its (fake gateway) payment id at the provider."""
    order = await new_order(client, h)
    r = await client.post("/api/v1/payments/initiate", headers=h, json={"order_id": order["id"], "payment_method_type": "upi"})
    assert r.status_code == 201, r.text
    from core_api.modules.payments.models.payment import PaymentIntent
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        intent = await db.get(PaymentIntent, uuid.UUID(r.json()["payment_intent_id"]))
        assert intent is not None and intent.status == "pending"
        provider_id = intent.provider_payment_id
    return order, provider_id


def _razorpay_captured(provider_payment_id: str) -> bytes:
    return json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": f"pay_{uuid.uuid4().hex[:14]}", "order_id": provider_payment_id, "status": "captured"}}}}).encode()


# ── S2: webhooks ────────────────────────────────────────────────────────────

async def test_razorpay_webhook_without_a_secret_is_refused(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().payments, "RAZORPAY_WEBHOOK_SECRET", "")
    cust = await login(client, "customer3.hyd@example.com")
    order, provider_id = await _open_payment(client, cust)
    body = _razorpay_captured(provider_id)
    forged = hmac.new(b"", body, hashlib.sha256).hexdigest()  # what anyone can compute with no secret set
    r = await client.post("/api/v1/payments/razorpay/webhook", content=body,
                          headers={"x-razorpay-signature": forged, "content-type": "application/json"})
    assert r.status_code == 400, r.text
    assert await _order_status(client, cust, order["id"]) == "pending_payment"
    assert (await payment(order["id"]))["status"] == "pending"


async def test_one_providers_webhook_cant_settle_another_providers_payment(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.config import get_settings

    monkeypatch.setattr(get_settings().payments, "RAZORPAY_WEBHOOK_SECRET", "rzp_whsec_ci_only")
    cust = await login(client, "customer3.hyd@example.com")
    order, provider_id = await _open_payment(client, cust)  # a payment with the fake gateway, not Razorpay
    body = _razorpay_captured(provider_id)
    sig = hmac.new(b"rzp_whsec_ci_only", body, hashlib.sha256).hexdigest()
    r = await client.post("/api/v1/payments/razorpay/webhook", content=body,
                          headers={"x-razorpay-signature": sig, "content-type": "application/json"})
    assert r.status_code == 200, r.text
    assert await _order_status(client, cust, order["id"]) == "pending_payment"
    assert (await payment(order["id"]))["status"] == "pending"


# ── S3: wallet ──────────────────────────────────────────────────────────────

async def test_there_is_no_free_wallet_top_up(client: AsyncClient) -> None:
    cust = await login(client, "customer4.hyd@example.com")
    before = (await client.get("/api/v1/wallet/balance", headers=cust)).json()["balance"]
    r = await client.post("/api/v1/wallet/topup", headers=cust,
                          json={"amount": 100000, "currency": "INR", "payment_method_id": "pm_anything"})
    assert r.status_code in (404, 405), r.text
    after = (await client.get("/api/v1/wallet/balance", headers=cust)).json()["balance"]
    assert float(after) == float(before)


async def test_an_empty_wallet_cant_pay_for_an_order(client: AsyncClient) -> None:
    cust = await login(client, "customer4.hyd@example.com")
    await client.post("/api/v1/wallet/topup", headers=cust,
                      json={"amount": 100000, "currency": "INR", "payment_method_id": "pm_anything"})
    balance = float((await client.get("/api/v1/wallet/balance", headers=cust)).json()["balance"])
    order = await new_order(client, cust)
    assert balance < float(order["total"]), "the seed gives this customer no wallet money"
    r = await client.post("/api/v1/payments/initiate", headers=cust,
                          json={"order_id": order["id"], "payment_method_type": "wallet"})
    assert r.status_code == 400, r.text
    assert await _order_status(client, cust, order["id"]) == "pending_payment"


# ── S4: a kitchen's status ──────────────────────────────────────────────────

RESTAURANT = {
    "name": "Security Review Kitchen", "cuisine_types": ["Indian"], "currency": "INR", "country": "IN", "city": "Hyderabad",
    "address": {"street": "1 Review Rd", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"},
    "location": {"lat": 17.44, "lng": 78.39}, "delivery_time_min": 20, "delivery_time_max": 40,
    "minimum_order_amount": 0, "delivery_fee": 0,
}


async def test_an_owner_cant_approve_or_unsuspend_their_own_kitchen(client: AsyncClient) -> None:
    partner = await login(client, "partner.hyd@example.com")
    r = await client.post("/api/v1/restaurants", headers=partner, json=RESTAURANT)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    assert r.json()["status"] == "pending_approval"
    for status in ("active", "inactive", "suspended"):
        r = await client.put(f"/api/v1/restaurants/{rid}", headers=partner, json={"status": status})
        assert r.status_code == 403, (status, r.text)
    from core_api.modules.catalog.models.restaurant import Restaurant
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        assert (await db.get(Restaurant, uuid.UUID(rid))).status == "pending_approval"
    # The owner still edits everything else.
    r = await client.put(f"/api/v1/restaurants/{rid}", headers=partner, json={"description": "Still mine to edit"})
    assert r.status_code == 200, r.text


# ── S5: a kitchen can't reach another kitchen's things through its own path ─

async def test_a_kitchen_cant_reach_another_kitchens_menu_or_offers_through_its_own_path(client: AsyncClient) -> None:
    own = await login(client, "partner.hyd@example.com")
    other = await login(client, "partner.boi@example.com")
    mine = (await client.get("/api/v1/restaurants/mine", headers=own)).json()
    spice = next(r for r in mine if r["name"] == "Spice Route Kitchen")["id"]
    theirs = (await client.get("/api/v1/restaurants/mine", headers=other)).json()
    assert theirs, "partner.boi owns a kitchen in the seed"
    their_id = theirs[0]["id"]
    menu = (await client.get(f"/api/v1/restaurants/{spice}/menu")).json()
    first = next(i for c in menu["categories"] for i in c["items"])
    item, price = first["id"], float(first["price"])
    group = (await client.post(f"/api/v1/restaurants/{spice}/option-groups", headers=own, json={
        "name": "Security review extras", "min_picks": 0, "max_picks": 1, "options": [{"name": "Lemon", "price": 0}]})).json()["id"]
    offers = (await client.post(f"/api/v1/restaurants/{spice}/offers", headers=own, json={
        "template": "free_delivery", "name": "Security review", "weekly_cap": "1", "min_subtotal": "999999"})).json()
    offer = next(o for o in offers if o["name"] == "Security review")["id"]
    try:
        base = f"/api/v1/restaurants/{their_id}"
        attempts = [
            ("PUT", f"{base}/menu-items/{item}", {"price": 1}),
            ("PUT", f"{base}/menu-items/{item}/sold-out", {"sold_out": True}),
            ("PUT", f"{base}/menu-items/{item}/option-groups", {"group_ids": []}),
            ("PUT", f"{base}/option-groups/{group}", {"name": "Taken", "min_picks": 0, "max_picks": 1,
                                                      "options": [{"name": "x", "price": 0}]}),
            ("POST", f"{base}/offers/{offer}/end", None),
            ("DELETE", f"{base}/option-groups/{group}", None),
            ("DELETE", f"{base}/menu-items/{item}", None),
        ]
        for method, path, body in attempts:
            r = await client.request(method, path, headers=other, **({"json": body} if body is not None else {}))
            assert r.status_code in (403, 404), (method, path, r.status_code, r.text[:200])
        # Still Spice Route's, unchanged.
        menu2 = (await client.get(f"/api/v1/restaurants/{spice}/menu")).json()
        again = next(i for c in menu2["categories"] for i in c["items"] if i["id"] == item)
        assert float(again["price"]) == price
        live = (await client.get(f"/api/v1/restaurants/{spice}/offers", headers=own)).json()
        assert any(o["id"] == offer for o in live)
    finally:
        await client.post(f"/api/v1/restaurants/{spice}/offers/{offer}/end", headers=own)
        await client.delete(f"/api/v1/restaurants/{spice}/option-groups/{group}", headers=own)


# ── S7: price checks per person ─────────────────────────────────────────────

async def test_quotes_are_limited_per_person(client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.config import get_settings
    from shared.redis import get_redis

    cust = await login(client, "customer5.hyd@example.com")
    me = (await client.get("/api/v1/users/me", headers=cust)).json()["id"]
    redis = await get_redis()
    await redis.delete(f"rl:quote:60:{me}", f"rl:quote:86400:{me}")
    monkeypatch.setattr(get_settings(), "QUOTE_LIMIT_PER_MINUTE", 3)
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"])["id"]
    body = {"restaurant_id": rest["id"], "items": [{"menu_item_id": item, "quantity": 1}],
            "deliver_to": {"lat": 17.4483, "lng": 78.3915}}
    try:
        codes = [(await client.post("/api/v1/pricing/quote", headers=cust, json=body)).status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200], codes
        r = await client.post("/api/v1/pricing/quote", headers=cust, json=body)
        assert r.status_code == 429 and r.json()["detail"]["code"] == "TOO_MANY_QUOTES", r.text
        assert int(r.headers["retry-after"]) > 0
        # Someone else is unaffected.
        other = await login(client, "customer4.hyd@example.com")
        assert (await client.post("/api/v1/pricing/quote", headers=other, json=body)).status_code == 200
    finally:
        await redis.delete(f"rl:quote:60:{me}", f"rl:quote:86400:{me}")
