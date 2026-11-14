"""Payment fees in the order split, and contribution per order (item 1), on the
migrated, seeded database: a card order pays Razorpay's 2%, a UPI order nothing; the
contribution report adds up (platform - payment fees - refunds = platform keeps)."""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import assign, login, move

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


async def order_paid_with(client: AsyncClient, h: dict, method: str) -> dict:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                if r["name"] == "Spice Route Kitchen")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rest["id"], "items": cart,
                                                                    "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": method, "quote_token": q.json()["token"],
        "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}})
    assert r.status_code == 201, r.text
    return r.json()


async def split_of(client: AsyncClient, admin: dict, order_id: str) -> dict:
    return (await client.get(f"/api/v1/pricing/orders/{order_id}/snapshot", headers=admin)).json()["split"]


async def test_payment_fees_in_the_split_by_method(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    fin = await login(client, "finance.in@example.com", "BhojanGoAdmin1")
    card = await order_paid_with(client, cust, "card")
    upi = await order_paid_with(client, cust, "upi")
    s_card, s_upi = await split_of(client, fin, card["id"]), await split_of(client, fin, upi["id"])
    total = Decimal(str(card["total"]))
    assert Decimal(s_card["payment_fees"]) == (total * 2 / 100).quantize(Decimal("0.01"))  # Razorpay cards: 2%
    assert Decimal(s_card["platform_keeps"]) == Decimal(s_card["platform"]) - Decimal(s_card["payment_fees"])
    assert s_card["detail"]["payment_fees"]["method"] == "card"
    assert Decimal(s_upi["payment_fees"]) == 0 and s_upi["platform_keeps"] == s_upi["platform"]  # UPI: free


async def test_contribution_adds_up(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    partner = await login(client, "partner.hyd@example.com")
    rider = await login(client, "rider3.hyd@example.com")
    fin = await login(client, "finance.in@example.com", "BhojanGoAdmin1")
    o = await order_paid_with(client, cust, "card")
    from core_api.integration.test_orders_flow import pay

    await pay(client, cust, o)
    for s in ("accepted", "preparing", "almost_ready"):
        await move(client, partner, o["id"], s)
    assert (await assign(client, o["id"], rider)).status_code == 200
    await move(client, partner, o["id"], "ready")
    await move(client, rider, o["id"], "picked_up")
    pin = (await client.get(f"/api/v1/orders/{o['id']}", headers=cust)).json()["pin"]
    r = await client.put(f"/api/v1/orders/{o['id']}/status", headers=rider, json={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    assert r.status_code == 200, r.text

    today = date.today()
    rep = (await client.get("/api/v1/finance/contribution", headers=fin, params={
        "scope": "IN-TG-HYD", "start": str(today - timedelta(days=1)), "end": str(today + timedelta(days=1))})).json()
    city = next(c for c in rep["cities"] if c["city"] == "IN-TG-HYD")
    t = {k: Decimal(v) for k, v in city["totals"].items()}
    assert city["orders"] >= 1 and t["payment_fees"] > 0
    assert t["keeps"] == t["platform"] - t["payment_fees"] - t["refunds"]
    # the platform line is the snapshot's: commission + customer fees - our offers - rider pay (tips excluded)
    assert t["platform"] == t["commission"] + t["customer_fees"] - t["platform_promos"] - t["rider_pay"]
    assert Decimal(city["per_order"]["keeps"]) == (t["keeps"] / city["orders"]).quantize(Decimal("0.01"))
    # the reconciliation shows payment fees too
    rec = (await client.get("/api/v1/finance/reconciliation", headers=fin, params={
        "country": "IN", "start": str(today - timedelta(days=1)), "end": str(today + timedelta(days=1))})).json()
    assert rec["money"]["payment_fees"] >= 0 and "platform_after_payment_fees" in rec["money"]
