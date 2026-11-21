"""R27 on Postgres: refunds on the receipt (bill API and PDF), a cancelled and refunded order's
receipt, and the kitchen's "today" net of the refunds charged to it."""
import os
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login, new_order, pay
from core_api.integration.test_payments_refunds import ADMIN, client, delivered_order  # noqa: F401 - fixture
from core_api.modules.orders.tests.test_receipt import pdf_text
from shared.money import format_money

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_a_partial_refund_is_on_the_receipt_and_off_the_kitchens_today(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    partner = await login(client, "partner.hyd@example.com")
    order = await delivered_order(client, cust)  # 2 x Veg Dum Biryani at Spice Route Kitchen
    rid = order["restaurant_id"]
    before = (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()

    support = await login(client, "support.hyd@example.com", ADMIN)
    biryani = order["items"][0]["menu_item_id"]
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "missing_item"})
    assert r.status_code == 201, r.text
    refund = r.json()
    back = Decimal(refund["amount"]) / 100
    food = Decimal(refund["lines"][0]["food"])

    # The kitchen's today: the refund it pays comes off today's sales (R26 showed the sales without it).
    after = (await client.get(f"/api/v1/restaurants/{rid}/today", headers=partner)).json()
    assert after["today_orders"] == before["today_orders"]
    assert Decimal(after["today_sales"]) == Decimal(before["today_sales"]) - food
    assert Decimal(after["today_refunds"]) == Decimal(before["today_refunds"]) + food

    # The receipt's bill: the refund, its reason and items, and what was paid after it.
    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=cust)).json()
    assert [(x["reason"], x["kind"], x["items"]) for x in bill["refunds"]] == [("missing_item", "items", ["Veg Dum Biryani"])]
    assert Decimal(bill["refunds"][0]["amount"]) == back
    assert Decimal(bill["refunded"]) == back and Decimal(bill["paid"]) == Decimal(bill["total"]) - back

    # The PDF says it too.
    pdf = await client.get(f"/api/v1/orders/{order['id']}/receipt.pdf", headers=cust)
    assert pdf.status_code == 200, pdf.text
    text = pdf_text(pdf.content)
    for want in (f"Refunded {format_money(back, 'INR')} · missing item (Veg Dum Biryani)", "Total paid",
                 format_money(Decimal(bill["paid"]), "INR")):
        assert want in text, want


async def test_a_cancelled_order_refunded_in_full_has_a_receipt_with_the_full_refund(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer2.hyd@example.com")
    order = await new_order(client, cust)
    await pay(client, cust, order)
    r = await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"

    bill = (await client.get(f"/api/v1/pricing/orders/{order['id']}/bill", headers=cust)).json()
    assert [(x["kind"], x["reason"]) for x in bill["refunds"]] == [("full", "full")]
    assert Decimal(bill["refunded"]) == Decimal(bill["total"]) and Decimal(bill["paid"]) == 0

    pdf = await client.get(f"/api/v1/orders/{order['id']}/receipt.pdf", headers=cust)
    assert pdf.status_code == 200, pdf.text
    text = pdf_text(pdf.content)
    assert f"Refunded {format_money(Decimal(bill['total']), 'INR')} · order cancelled" in text
    assert "Total paid" in text and format_money(0, "INR") in text


async def test_a_cancelled_order_never_paid_has_no_receipt(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer2.hyd@example.com")
    order = await new_order(client, cust)
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
    assert (await client.get(f"/api/v1/orders/{order['id']}/receipt.pdf", headers=cust)).status_code == 409
