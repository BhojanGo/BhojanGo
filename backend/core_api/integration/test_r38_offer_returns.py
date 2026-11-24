"""R38: a cancelled, unpaid or refunded order gives its BhojanGo-funded offer cost back to its budget
(pricing/service/offer_budget.py give_back)."""
import os
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login  # noqa: F401
from core_api.integration.test_r37_offer_budget import BOISE, DOWNTOWN, scalar
from core_api.integration.test_web_v3 import sql

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"


async def offer(client: AsyncClient, maker: dict, checker: dict, scope: str, key: str, amount: int) -> dict:  # noqa: F811
    r = await client.post("/api/v1/rules", headers=maker, json={
        "family": "promotion", "template": "flat_off", "key": key, "name": f"{amount} off ({key})",
        "params": {"amount": amount, "funded_by": "platform"}, "scope_level": "city", "scope_id": scope})
    assert r.status_code == 201, r.text
    rule = r.json()
    await client.post(f"/api/v1/rules/{rule['id']}/submit", headers=maker)
    assert (await client.post(f"/api/v1/rules/{rule['id']}/approve", headers=checker, json={})).status_code == 200
    return rule


async def test_budget_10_offer_3_three_orders_one_cancelled_then_a_fourth_gets_it(client: AsyncClient) -> None:  # noqa: F811
    maker, checker = await login(client, "cm.us@example.com", ADMIN), await login(client, "finance.us@example.com", ADMIN)
    cust = await login(client, "customer1.boi@example.com")
    await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")
    assert (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": "10"})).status_code == 200
    rule = await offer(client, maker, checker, BOISE, "r38_return", 3)
    try:
        rest = next(x for x in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if x["name"] == "Boise Bowl Co.")
        menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
        tofu = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")
        items = [{"menu_item_id": tofu["id"], "quantity": 2}]

        async def order() -> dict:
            q = (await client.post("/api/v1/pricing/quote", headers=cust, json={"restaurant_id": rest["id"], "items": items,
                                                                                "deliver_to": DOWNTOWN})).json()
            assert [ln["amount"] for ln in q["lines"] if ln["code"] == "promotion"] == ["-3.00"], q["lines"]
            r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
                "restaurant_id": rest["id"], "items": items, "payment_method": "card", "quote_token": q["token"],
                "delivery_address": {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}})
            assert r.status_code == 201, r.text
            return r.json()

        placed = [await order() for _ in range(3)]
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("9.00")
        r = await client.post(f"/api/v1/orders/{placed[1]['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
        assert r.status_code == 200, r.text
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("6.00")
        assert await scalar("SELECT orders FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == 2
        # cancelling again gives nothing back twice
        await client.post(f"/api/v1/orders/{placed[1]['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("6.00")
        await order()  # the fourth order gets the offer again
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'") == Decimal("9.00")
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=checker, json={})
        await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": None})
        await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")


async def test_a_partial_refund_gives_back_its_share(client: AsyncClient) -> None:  # noqa: F811
    """Hyderabad: ₹30 off, paid and delivered; one of the two biryanis refunded gives back that share of the ₹30."""
    from core_api.integration.test_payments_refunds import delivered_order

    maker, checker = await login(client, "cm.in@example.com", ADMIN), await login(client, "finance.in@example.com", ADMIN)
    await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:IN-TG-HYD'")
    assert (await client.put("/api/v1/rules/offers/budgets/city/IN-TG-HYD", headers=maker, json={"monthly": "1000"})).status_code == 200
    rule = await offer(client, maker, checker, "IN-TG-HYD", "r38_partial", 30)
    try:
        cust = await login(client, "customer2.hyd@example.com")
        order = await delivered_order(client, cust)
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:IN-TG-HYD'") == Decimal("30.00")
        ops = await login(client, "ops.hyd@example.com", ADMIN)
        r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=ops, json={
            "items": [{"menu_item_id": order["items"][0]["menu_item_id"], "quantity": 1}], "reason": "missing_item"})
        assert r.status_code == 201, r.text
        refund = r.json()["amount"] if isinstance(r.json().get("amount"), int) else int(Decimal(str(r.json()["amount"])) * 100)
        paid = await scalar("SELECT amount FROM payment_intents WHERE order_id = CAST(:o AS uuid) ORDER BY created_at DESC LIMIT 1", o=order["id"])
        share = (Decimal(30) * Decimal(refund) / Decimal(paid)).quantize(Decimal("0.01"))
        assert 0 < share < 30
        assert await scalar("SELECT returned FROM platform_offer_returns WHERE order_id = CAST(:o AS uuid)", o=order["id"]) == share
        assert await scalar("SELECT spent FROM platform_offer_spend WHERE pool = 'city:IN-TG-HYD'") == Decimal("30.00") - share
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=checker, json={})
        await client.put("/api/v1/rules/offers/budgets/city/IN-TG-HYD", headers=maker, json={"monthly": None})
        await sql("DELETE FROM platform_offer_spend WHERE pool = 'city:IN-TG-HYD'")
