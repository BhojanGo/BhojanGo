"""P9 tax on a migrated, seeded database: Idaho sales tax from the tax provider
(local stand-in here; Stripe Tax with keys), GST from rules, and the fair bill."""
import os
import uuid
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


async def login(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "BhojanGo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def menu(client: AsyncClient, slug: str) -> tuple[str, dict[str, str]]:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if r["slug"] == slug)
    m = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    return rest["id"], {i["name"]: i["id"] for c in m["categories"] for i in c["items"]}


async def place(client: AsyncClient, h: dict, rid: str, cart: list[dict], q: dict, country: str) -> dict:
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": [{"menu_item_id": i["menu_item_id"], "quantity": i["quantity"]} for i in cart],
        "delivery_address": {"street": "x", "city": "x", "state": "x", "zip": "00000", "country": country},
        "payment_method": "card", "quote_token": q["token"]})
    assert r.status_code == 201, r.text
    return r.json()


async def test_boise_quote_has_idaho_sales_tax(client: AsyncClient) -> None:
    h = await login(client, "customer1.boi@example.com")
    address = (await client.get("/api/v1/me/addresses", headers=h)).json()[0]
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if r["name"] == "Boise Bowl Co.")
    rid, items = await menu(client, rest["slug"])
    cart = [{"menu_item_id": items["Teriyaki Chicken Bowl"], "quantity": 2}]
    r = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": cart, "deliver_to": {"address_id": address["id"]}, "tip": "3"})
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["currency"] == "USD" and q["tax_pending"] is False and q["distance_unit"] == "mi"
    lines = {ln["label"]: ln for ln in q["lines"]}
    tax = lines["Idaho sales tax"]
    taxable = sum(Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] in ("food", "promotion", "delivery_fee", "service_fee", "small_order_fee"))
    assert tax["detail"]["rate_percent"] == "6" and Decimal(tax["detail"]["base"]) == taxable
    assert Decimal(tax["amount"]) == (taxable * Decimal("0.06")).quantize(Decimal("0.01"))
    assert tax["detail"]["calculation_id"].startswith("taxcalc_local_")
    assert Decimal(q["total"]) == sum(Decimal(ln["amount"]) for ln in q["lines"])

    order = await place(client, h, rid, cart, q, "US")
    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
    assert [t["label"] for t in bill["taxes"]] == ["Idaho sales tax"] and bill["total"] == q["total"]
    other = await login(client, "customer2.boi@example.com")
    assert (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=other)).status_code == 404


async def test_hyderabad_bill_shows_each_gst_line(client: AsyncClient) -> None:
    h = await login(client, "customer4.hyd@example.com")
    address = (await client.get("/api/v1/me/addresses", headers=h)).json()[0]
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if r["name"] == "Curry Leaf")
    rid, items = await menu(client, rest["slug"])
    first = next(iter(items.values()))
    cart = [{"menu_item_id": first, "quantity": 2}]
    r = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rid, "items": cart,
                                                                    "deliver_to": {"address_id": address["id"]}})
    assert r.status_code == 200, r.text
    q = r.json()
    order = await place(client, h, rid, cart, q, "IN")
    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=h)).json()
    taxes = {t["label"]: t["detail"] for t in bill["taxes"]}
    assert taxes["GST on food"]["rate_percent"] == "5" and taxes["GST on platform fees"]["rate_percent"] == "18"
    food_base = sum(Decimal(ln["amount"]) for ln in bill["lines"] if ln["code"] in ("food", "packaging"))
    food_base += sum(Decimal(ln["amount"]) for ln in bill["lines"] if ln["code"] == "promotion" and ln["label"] != "Free delivery")
    assert Decimal(taxes["GST on food"]["base"]) == food_base
