"""R37: offers BhojanGo pays for spend from a monthly budget (pricing/service/offer_budget.py); India's
bill in exact paise adds up to the total charged."""
import os
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login  # noqa: F401
from core_api.integration.test_web_v3 import sql

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

BOISE = "US-ID-BOI"
DOWNTOWN = {"lat": 43.6150, "lng": -116.2023}


async def scalar(statement: str, **params):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return (await db.execute(text(statement), params)).scalar()


async def test_seed_has_no_active_bhojango_funded_offer(client: AsyncClient) -> None:  # noqa: F811
    """Every seeded offer BhojanGo pays for is paused, and no place has an offer budget: the home
    screens (discover) show only offers restaurants pay for."""
    live = await scalar("""SELECT count(*) FROM rules WHERE family = 'promotion' AND params->>'funded_by' = 'platform'
                           AND status = 'published' AND paused_at IS NULL AND (effective_to IS NULL OR effective_to > now())""")
    assert live == 0
    assert await scalar("SELECT count(*) FROM rules WHERE family = 'promotion' AND params->>'funded_by' = 'platform'") >= 1
    for place in ({"lat": 17.4483, "lng": 78.3915}, DOWNTOWN, {"city": "IN-TG-HYD"}, {"city": BOISE}):
        d = (await client.get("/api/v1/discover", params=place)).json()
        assert all(o["funded_by"] == "restaurant" for o in d["offers"]), d["offers"]
        assert all(k["offer"] is None or k["offer"]["funded_by"] == "restaurant" for k in d["restaurants"])


async def test_budget_10_offer_3_three_orders_then_it_stops_with_alerts(client: AsyncClient) -> None:  # noqa: F811
    """Boise: a $10 monthly budget and a $3-off offer BhojanGo pays for. Three orders get it ($9: the 80%
    alert, and too little left for a fourth: the 100% alert); the fourth quote has no offer."""
    maker, checker = await login(client, "cm.us@example.com", "BhojanGoAdmin1"), await login(client, "finance.us@example.com", "BhojanGoAdmin1")
    cust = await login(client, "customer1.boi@example.com")
    await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")
    await sql("DELETE FROM ops_alerts WHERE fingerprint LIKE 'offer-budget:city:US-ID-BOI:%'")

    budgets = (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": "10"}))
    assert budgets.status_code == 200, budgets.text
    row = next(r for r in budgets.json()["rows"] if r["code"] == BOISE)
    assert (Decimal(row["own"]), row["pool"], Decimal(row["monthly"]), Decimal(row["spent"])) == (10, "city:US-ID-BOI", 10, 0)
    r = await client.post("/api/v1/rules", headers=maker, json={
        "family": "promotion", "template": "flat_off", "key": "r37_budget", "name": "$3 off (R37 budget test)",
        "params": {"amount": 3, "funded_by": "platform"}, "scope_level": "city", "scope_id": BOISE})
    assert r.status_code == 201, r.text
    rule = r.json()
    assert (await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=maker)).status_code == 200
    r = await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=checker, json={})
    assert r.status_code == 200, r.text
    try:
        econ = (await client.get(f"/api/v1/rules/offers/{rule['id']}/economics", headers=maker)).json()
        assert econ["funded_by"] == "platform" and Decimal(econ["max_cost"]) == 3 and econ["running"] is True
        assert econ["warning"] is True and Decimal(econ["cost_per_order"]) > Decimal(econ["platform_fee"]), econ
        assert (econ["pool"], Decimal(econ["monthly"]), Decimal(econ["left"])) == ("city:US-ID-BOI", 10, 10)

        rest = next(x for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                    if x["name"] == "Boise Bowl Co.")
        menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
        tofu = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")
        items = [{"menu_item_id": tofu["id"], "quantity": 2}]

        async def quote() -> dict:
            q = await client.post("/api/v1/pricing/quote", headers=cust, json={"restaurant_id": rest["id"], "items": items,
                                                                               "deliver_to": DOWNTOWN})
            assert q.status_code == 200, q.text
            return q.json()

        def offer(q: dict) -> list:
            return [(ln["amount"], ln["funded_by"]) for ln in q["lines"] if ln["code"] == "promotion"]

        async def place(q: dict):  # type: ignore[no-untyped-def]
            return await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
                "restaurant_id": rest["id"], "items": items, "payment_method": "card", "quote_token": q["token"],
                "delivery_address": {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}})

        for n in range(3):
            q = await quote()
            assert offer(q) == [("-3.00", "platform")], (n, q["lines"])
            placed = await place(q)
            assert placed.status_code == 201, placed.text
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("9.00")
        q4 = await quote()
        assert offer(q4) == [], q4["lines"]  # $1 left can't pay for $3: the fourth order doesn't get it

        ops = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")  # Operations sees the alerts
        alerts = (await client.get("/api/v1/ops/alerts", headers=ops, params={"scope": BOISE})).json()
        ours = {a["severity"]: a for a in alerts if a["name"] == "PlatformOfferBudget" and a["city"] == BOISE}
        assert set(ours) == {"warning", "critical"}, alerts  # 80% and 100%
        assert "80%" in ours["warning"]["summary"] and "$9.00 of $10.00" in ours["warning"]["description"]
        assert "stopped" in ours["critical"]["summary"]
        econ = (await client.get(f"/api/v1/rules/offers/{rule['id']}/economics", headers=maker)).json()
        assert econ["running"] is False and Decimal(econ["left"]) == 1
        # the home screen stops showing it too
        d = (await client.get("/api/v1/discover", params=DOWNTOWN)).json()
        assert all(o["funded_by"] == "restaurant" for o in d["offers"])
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=checker, json={})
        await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": None})


async def test_a_quoted_offer_the_budget_can_no_longer_pay_for_refuses_the_order(client: AsyncClient) -> None:  # noqa: F811
    """Two bags quoted with $3 off while $3 is left: the first order takes it; placing the second is
    refused (OFFER_ENDED) and prices again without the offer."""
    maker, checker = await login(client, "cm.us@example.com", "BhojanGoAdmin1"), await login(client, "finance.us@example.com", "BhojanGoAdmin1")
    cust = await login(client, "customer2.boi@example.com")
    await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")
    assert (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": "3"})).status_code == 200
    rule = (await client.post("/api/v1/rules", headers=maker, json={
        "family": "promotion", "template": "flat_off", "key": "r37_race", "name": "$3 off (R37 race test)",
        "params": {"amount": 3, "funded_by": "platform"}, "scope_level": "city", "scope_id": BOISE})).json()
    await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=maker)
    assert (await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=checker, json={})).status_code == 200
    try:
        rest = next(x for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"]
                    if x["name"] == "Boise Bowl Co.")
        menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
        tofu = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")
        items = [{"menu_item_id": tofu["id"], "quantity": 2}]
        qs = []
        for _ in range(2):
            q = await client.post("/api/v1/pricing/quote", headers=cust, json={"restaurant_id": rest["id"], "items": items,
                                                                               "deliver_to": DOWNTOWN})
            assert any(ln["code"] == "promotion" for ln in q.json()["lines"]), q.text
            qs.append(q.json())
        results = []
        for q in qs:
            results.append(await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
                "restaurant_id": rest["id"], "items": items, "payment_method": "card", "quote_token": q["token"],
                "delivery_address": {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}}))
        assert results[0].status_code == 201, results[0].text
        assert results[1].status_code == 409 and results[1].json()["detail"]["code"] == "OFFER_ENDED", results[1].text
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("3.00")
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=checker, json={})
        await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": None})
        await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")


async def test_budgets_need_an_approver_and_a_sane_amount(client: AsyncClient) -> None:  # noqa: F811
    ops = await login(client, "ops.boi@example.com", "BhojanGoAdmin1")
    maker = await login(client, "cm.us@example.com", "BhojanGoAdmin1")
    assert (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=ops, json={"monthly": "50"})).status_code == 403
    assert (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": "-1"})).status_code == 422
    rows = (await client.get("/api/v1/rules/offers/budgets", headers=maker, params={"country": "US"})).json()["rows"]
    assert {r["level"] for r in rows} == {"country", "region", "city"} and all(r["monthly"] == "0" or r["own"] for r in rows)


async def test_india_bill_in_exact_paise_adds_up(client: AsyncClient) -> None:  # noqa: F811
    """R37: ₹300 of food, 2.50 km, UPI in Hyderabad: ₹300.00 + ₹30.00 delivery + ₹30.00 platform fee + GST ₹25.80
    (5% of the food, 18% of the fees) = ₹385.80. The bill's lines, printed as customers read them on the bill,
    receipt and messages (exact paise), add up to the printed total."""
    from shared.money import format_money

    maker = await login(client, "cm.in@example.com", "BhojanGoAdmin1")
    r = await client.post("/api/v1/pricing/simulate", headers=maker, json={
        "city": "IN-TG-HYD", "cart": {"food_subtotal": "300"}, "distance": "2.50", "local_time": "2026-11-12T13:00:00",
        "tip": "0", "payment_method": "upi"})
    assert r.status_code == 200, r.text
    live = r.json()["live"]
    lines = {ln["label"]: Decimal(ln["amount"]) for ln in live["lines"]}
    assert lines["Food"] == Decimal("300.00") and lines["Delivery fee"] == Decimal("30.00") and lines["Platform fee"] == Decimal("30.00")
    gst = sum((Decimal(ln["amount"]) for ln in live["lines"] if ln["code"] == "tax"), Decimal(0))
    assert gst == Decimal("25.80") and Decimal(live["total"]) == Decimal("385.80")
    assert {ln["code"] for ln in live["lines"]} == {"food", "delivery_fee", "platform_fee", "tax"}
    shown = [format_money(ln["amount"], "INR", "en-IN") for ln in live["lines"]]
    assert shown[:3] == ["₹300.00", "₹30.00", "₹30.00"] and format_money(live["total"], "INR", "en-IN") == "₹385.80"
    assert sum(Decimal(s.replace("₹", "").replace(",", "")) for s in shown) == Decimal("385.80")
