"""P8 quotes and the simulator on a migrated, seeded database."""
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from core_api.modules.identity.tests.signin import login_response

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

SPICE_ROUTE = "spice-route-kitchen-madhapur"
THU_8PM_IST = datetime(2026, 11, 12, 14, 30, tzinfo=UTC)
JUBILEE_HILLS = (17.43, 78.41)  # ~3.8 km by road from Spice Route Kitchen


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def login(client: AsyncClient, email: str, pw: str = "BhojanGo123") -> tuple[dict, dict]:
    r = await login_response(client, email, pw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


async def spice_route_cart(client: AsyncClient) -> tuple[str, list[dict]]:
    rest = next(r for r in (await client.get("/api/v1/restaurants")).json()["items"] if r["slug"] == SPICE_ROUTE)
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    items = {i["name"]: i["id"] for c in menu["categories"] for i in c["items"]}
    cart = [
        {"menu_item_id": items["Chicken Dum Biryani"], "quantity": 1, "options": [
            {"group": "Size", "option": "Regular · serves 1"}, {"group": "Spice", "option": "Medium"},
            {"group": "Add-ons", "option": "Extra raita"}]},
        {"menu_item_id": items["Paneer Tikka"], "quantity": 1},
    ]
    return rest["id"], cart


async def test_hyderabad_quote_from_the_database(client: AsyncClient) -> None:
    """The worked example's bill, priced from seeded menu, markets and rules."""
    from core_api.modules.pricing.schemas import QuoteRequest
    from core_api.modules.pricing.service.quotes import QuoteService
    from shared.db import AsyncSessionLocal

    rid, cart = await spice_route_cart(client)
    req = QuoteRequest(restaurant_id=rid, items=cart, deliver_to={"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]}, tip=20)
    async with AsyncSessionLocal() as db:
        q = await QuoteService(db).quote(uuid.uuid4(), req, now=THU_8PM_IST)
    lines = {ln.label: ln.amount for ln in q.lines}
    assert lines["Food"] == 560  # biryani 300 + extra raita 40 + paneer tikka 220
    # R16: the platform's 10% off doesn't lower the GST base in India: 5% of 570, not 520 (+2.50)
    # R31: platform fee 10% of 560 = 56 (above the ₹15 minimum); delivery fee from the bands: 3.77 km is in >3-5 km, ₹40;
    # GST on fees 18% of 40 + 56 = 17.28. 560 − 50 + 10 + 40 + 56 + 28.50 + 17.28 + 20 tip = 681.78
    # (R33: the busy-hour fee is 0 in every seed, so no line, even at 8 PM)
    assert q.distance == Decimal("3.77")
    assert q.total == Decimal("681.78"), q.lines
    assert lines["Platform fee"] == 56 and "Service fee" not in lines
    assert lines["Delivery fee"] == 40 and "Busy-hour fee" not in lines and lines["GST on platform fees"] == Decimal("17.28")
    assert q.zone == "Jubilee Hills" and q.city == "Hyderabad" and 3 < q.distance < 6


async def test_quote_order_snapshot_and_single_use(client: AsyncClient) -> None:
    h, user = await login(client, "customer2.hyd@example.com")
    addresses = (await client.get("/api/v1/me/addresses", headers=h)).json()
    rid, cart = await spice_route_cart(client)
    r = await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": cart, "deliver_to": {"address_id": addresses[0]["id"]}, "tip": "20"})
    assert r.status_code == 200, r.text
    q = r.json()
    assert q["currency"] == "INR" and Decimal(q["total"]) > 560 and q["zone"] == "Jubilee Hills"
    assert [ln["code"] for ln in q["lines"]][:3] == ["food", "promotion", "delivery_fee"]

    order_body = {
        "restaurant_id": rid,
        "items": [{"menu_item_id": i["menu_item_id"], "quantity": i["quantity"],
                   "customizations": [{"customization_id": o["group"], "option_id": o["option"]} for o in i.get("options", [])]}
                  for i in cart],
        "delivery_address": {"street": "12-2-41, Road No. 36", "city": "Hyderabad", "state": "Telangana", "zip": "500033",
                             "country": "IN", "lat": 17.4307, "lng": 78.4072},
        "payment_method": "upi", "quote_token": q["token"],
    }
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json=order_body)
    assert r.status_code == 201, r.text
    order = r.json()
    assert Decimal(str(order["total"])) == Decimal(q["total"])

    # Single use.
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json=order_body)
    assert r.status_code == 409

    admin, _ = await login(client, "ops.hyd@example.com", "BhojanGoAdmin1")
    snap = (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=admin)).json()
    assert snap["total"] == q["total"] and snap["context"]["zone"] == "Jubilee Hills"
    assert {r["slot"] for r in snap["rule_versions"]} >= {"delivery_fee", "fee:platform_fee_pct", "tax:rate_on_lines:gst_food"}
    split = snap["split"]
    assert (Decimal(split["restaurant"]) + Decimal(split["rider"]) + Decimal(split["tax"]) + Decimal(split["platform"])
            + Decimal(split["card_fee"]) == Decimal(q["total"]))  # R29: the card fee goes to the payment provider
    boise_ops, _ = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")
    assert (await client.get(f"/api/v1/pricing/orders/{order['id']}/snapshot", headers=boise_ops)).status_code == 403


async def test_quote_refuses_changed_bag_and_bad_places(client: AsyncClient) -> None:
    h, _ = await login(client, "customer3.hyd@example.com")
    rid, cart = await spice_route_cart(client)
    q = (await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": cart, "deliver_to": {"lat": 17.4483, "lng": 78.3915}})).json()
    body = {"restaurant_id": rid, "items": [{"menu_item_id": cart[1]["menu_item_id"], "quantity": 3}],
            "delivery_address": {"street": "x", "city": "Hyderabad", "state": "TG", "zip": "500081", "country": "IN"},
            "payment_method": "upi", "quote_token": q["token"]}
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json=body)
    assert r.status_code == 409 and "cart changed" in r.text

    cases = [
        ({"lat": 15.0, "lng": 65.0}, cart, "don't deliver here"),
        ({"lat": 17.400, "lng": 78.330}, cart, "not delivering"),  # Kokapet: draft zone
        ({"lat": 17.4483, "lng": 78.3915}, [{"menu_item_id": cart[0]["menu_item_id"], "quantity": 1}], "Choose size"),
        ({"lat": 17.4483, "lng": 78.3915}, [{"menu_item_id": cart[1]["menu_item_id"], "quantity": 1,
                                            "options": [{"group": "Size", "option": "XL"}]}], "has no option"),
    ]
    for where, items, words in cases:
        r = await client.post("/api/v1/pricing/quote", headers=h, json={"restaurant_id": rid, "items": items, "deliver_to": where})
        assert r.status_code == 422 and words.lower() in r.text.lower(), (where, r.text)


async def test_simulator_live_vs_draft(client: AsyncClient) -> None:
    maker, _ = await login(client, "cm.in@example.com", "BhojanGoAdmin1")
    resolved = (await client.get("/api/v1/rules/resolve", headers=maker,
                                 params={"country": "IN", "region": "IN-TG", "city": "IN-TG-HYD"})).json()
    fee = next(x for x in resolved if x["slot"] == "delivery_fee")
    r = await client.post(f"/api/v1/rules/{fee['rule_id']}/versions", headers=maker, json={"params": {
        "slabs": [{"up_to": 3, "fee": 30}, {"up_to": 5, "fee": 45}, {"up_to": 7, "fee": 50}]}})  # R31: >3-5 km ₹40 -> ₹45
    draft = r.json()
    try:
        body = {"city": "IN-TG-HYD", "cart": {"food_subtotal": "560"}, "distance": "4.2",
                "local_time": "2026-11-12T20:00:00", "tip": "20", "restaurant_tier": "B", "draft_rule_ids": [draft["id"]]}
        r = await client.post("/api/v1/pricing/simulate", headers=maker, json=body)
        assert r.status_code == 200, r.text
        sim = r.json()
        # No restaurant picked, so no ₹10 packaging: 560 − 50 + 40 delivery (4.2 km: the >3-5 km band) + 56 platform fee
        # + 28.00 GST on food (5% of 560; R16: the platform's discount doesn't lower the base)
        # + 17.28 GST on fees (18% of 40 + 56) + 20 tip (R33: no busy-hour fee)
        assert sim["live"]["total"] == "671.28"
    finally:
        await client.delete(f"/api/v1/rules/{draft['id']}", headers=maker)
    changes = {c["label"]: (c["live"], c["draft"]) for c in sim["changes"]}
    assert changes["Delivery fee"] == ("40.00", "45.00")
    assert changes["GST on platform fees"] == ("17.28", "18.18")
    # R30: the delivery fee goes to the delivery partner, so a dearer one never changes what the platform keeps
    assert "Platform keeps" not in changes or changes["Platform keeps"][0] == changes["Platform keeps"][1]

    viewer, _ = await login(client, "viewer@example.com", "BhojanGoAdmin1")
    assert (await client.post("/api/v1/pricing/simulate", headers=viewer, json=body)).status_code == 403


async def test_order_with_options_matches_its_quote(client: AsyncClient) -> None:
    """The bag at checkout carries the same option picks as the quote (found by the G1 gate)."""
    h, _ = await login(client, "customer3.hyd@example.com")
    rid, cart = await spice_route_cart(client)
    q = (await client.post("/api/v1/pricing/quote", headers=h, json={
        "restaurant_id": rid, "items": cart, "deliver_to": {"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]}})).json()
    r = await client.post("/api/v1/orders", headers={**h, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "upi", "quote_token": q["token"],
        "delivery_address": {"street": "12-2-41", "city": "Hyderabad", "state": "Telangana", "zip": "500033", "country": "IN"}})
    assert r.status_code == 201, r.text
    assert Decimal(str(r.json()["total"])) == Decimal(q["total"])
