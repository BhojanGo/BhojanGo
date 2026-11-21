"""R25 on Postgres: the commission tax invoice, fetched through the API, is its own statement's: the
period of the statement's run, its orders, commission and GST (R24's review showed one week's period
over another week's numbers). Two consecutive weekly runs where the kitchen has orders only in the
earlier week: the earlier statement's invoice says that week and its order; the later statement (only a
balance carried in, no tax on commission) has no invoice (409 NO_COMMISSION_TAX).

The supplier is the country's legal entity from Markets; without a legal name the invoice is refused
(409 LEGAL_ENTITY_MISSING, before a link is made too) and admin Finance is told (payout-weeks
``legal_name_missing``). Nothing is ever printed in its place."""
import os
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login
from core_api.integration.test_payments_refunds import delivered_order
from core_api.integration.test_payouts import ADMIN, _no_earlier_runs, client, ist_last_week  # noqa: F401 - fixtures
from core_api.modules.orders.tests.test_receipt import pdf_text

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
# Weeks long ago, so no other test's orders (delivered today, or moved to last week) fall in them.
WEEKS_BACK = 12


def day(d) -> str:  # type: ignore[no-untyped-def]
    return f"{d:%d %b %Y}"


async def deliver_on(order_id: str, when: datetime) -> None:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE orders SET actual_delivery_time = CAST(:t AS timestamptz), "
                              "created_at = CAST(:t AS timestamptz) - interval '40 minutes', "
                              "rider_assigned_at = CAST(:t AS timestamptz) - interval '30 minutes', "
                              "picked_up_at = CAST(:t AS timestamptz) - interval '15 minutes' "
                              "WHERE id = CAST(:id AS uuid)"), {"t": when, "id": order_id})
        await db.commit()


async def kitchen_statement(client: AsyncClient, h: dict, run_id: str, restaurant_id: str) -> dict:  # noqa: F811
    run = (await client.get(f"/api/v1/finance/payout-runs/{run_id}", headers=h)).json()
    sid = next(s["id"] for s in run["statements"] if s["payee_id"] == restaurant_id)
    return (await client.get(f"/api/v1/finance/statements/{sid}", headers=h)).json()


async def set_legal_name(name: str | None) -> str | None:
    """India's legal name in Markets (None: removed); returns the one it replaces."""
    from sqlalchemy import select

    from core_api.modules.markets.models import Country
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        c = (await db.execute(select(Country).where(Country.code == "IN"))).scalar_one()
        legal = dict((c.settings or {}).get("legal") or {})
        was = legal.pop("name", None)
        if name:
            legal["name"] = name
        c.settings = {**(c.settings or {}), "legal": legal}
        await db.commit()
        return was


async def test_each_invoice_is_its_own_statements_week(client: AsyncClient) -> None:  # noqa: F811
    early = ist_last_week()[0] - timedelta(days=7 * WEEKS_BACK)
    late = early + timedelta(days=7)
    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)  # 2 x Veg Dum Biryani at Spice Route Kitchen
    spice = order["restaurant_id"]
    # Both biryanis were the kitchen's mistake: the week ends below zero, so the next week's statement
    # exists with no orders, only the balance carried in (as in R24's review).
    support = await login(client, "support.hyd@example.com", ADMIN)
    biryani = order["items"][0]["menu_item_id"]
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 2}], "reason": "missing_item"})
    assert r.status_code == 201, r.text
    await deliver_on(order["id"], datetime.combine(early + timedelta(days=2), datetime.min.time().replace(hour=12),
                                                   tzinfo=ZoneInfo("Asia/Kolkata")))

    finance = await login(client, "finance.in@example.com", ADMIN)
    admin = await login(client, "admin@example.com", ADMIN)
    partner = await login(client, "partner.hyd@example.com")
    runs = []
    for start in (early, late):
        r = await client.post("/api/v1/finance/payout-runs", headers=finance, json={
            "country": "IN", "period_start": start.isoformat(), "period_end": (start + timedelta(days=7)).isoformat()})
        assert r.status_code == 201, r.text
        runs.append(r.json())
        r = await client.post(f"/api/v1/finance/payout-runs/{runs[-1]['id']}/approve", headers=admin)
        assert r.status_code == 200, r.text
    first = await kitchen_statement(client, finance, runs[0]["id"], spice)
    second = await kitchen_statement(client, finance, runs[1]["id"], spice)
    assert [ln["order_id"] for ln in first["lines"]] == [order["id"]] and first["summary"]["orders"] == 1
    assert first["amount"] < 0 and Decimal(first["summary"]["commission_tax"]) > 0
    assert second["summary"]["orders"] == 0 and second["lines"] == [] and second["carried_in"] == first["amount"]

    # The earlier week's invoice: that week, its one order, its commission and GST.
    r = await client.get(f"/api/v1/finance/statements/{first['id']}/commission-invoice", headers=partner)
    assert r.status_code == 200 and r.content[:4] == b"%PDF", r.text[:300]
    text = " ".join(pdf_text(r.content).split())
    assert f"Period: {day(early)} – {day(early + timedelta(days=6))}" in text, text
    assert day(late) not in text  # never the next week's
    commission, tax = Decimal(first["summary"]["commission"]), Decimal(first["summary"]["commission_tax"])
    assert f"Commission on 1 delivered order ₹{commission:,.2f}" in text, text
    assert f"GST on commission @ {first['summary']['commission_tax_percent']}% ₹{tax:,.2f}" in text, text
    assert f"₹{commission + tax:,.2f}" in text
    assert "Supplier DeepTrics Software Solutions Pvt Ltd" in text and "Markets" not in text
    # The later week: no tax on commission, so no invoice, as before.
    for h in (partner, finance):
        r = await client.get(f"/api/v1/finance/statements/{second['id']}/commission-invoice", headers=h)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "NO_COMMISSION_TAX", r.text

    # No legal name in Markets: refused (the PDF and the app's link), and admin Finance is told.
    weeks = (await client.get("/api/v1/finance/payout-weeks", headers=finance, params={"country": "IN"})).json()
    assert weeks["legal_name_missing"] is False
    was = await set_legal_name(None)
    assert was == "DeepTrics Software Solutions Pvt Ltd"
    try:
        r = await client.get(f"/api/v1/finance/statements/{first['id']}/commission-invoice", headers=partner)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "LEGAL_ENTITY_MISSING", r.text
        assert "legal entity name for India is missing in Markets" in r.json()["detail"]["message"]
        r = await client.post(f"/api/v1/finance/statements/{first['id']}/commission-invoice/link", headers=partner)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "LEGAL_ENTITY_MISSING", r.text
        weeks = (await client.get("/api/v1/finance/payout-weeks", headers=finance, params={"country": "IN"})).json()
        assert weeks["legal_name_missing"] is True
    finally:
        await set_legal_name(was)
    r = await client.get(f"/api/v1/finance/statements/{first['id']}/commission-invoice", headers=partner)
    assert r.status_code == 200
