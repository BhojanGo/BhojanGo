"""P13 on Postgres: payout runs with maker-checker, restaurant and rider
statements (refunds, hourly floor), payee accounts, retry, reconciliation,
and the weekly draft."""
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from core_api.integration.test_orders_flow import login
from core_api.integration.test_payments_refunds import delivered_order

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


@pytest.fixture(autouse=True)
async def _no_earlier_runs():
    """Runs from an earlier test session would overlap this one's periods."""
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM payout_statements"))
        await db.execute(text("DELETE FROM payout_runs"))
        await db.execute(text("DELETE FROM payout_accounts"))
        await db.commit()
    yield


def ist_today() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def ist_last_week() -> tuple[date, date]:
    """Last week, Monday to the next Monday in India: a run covers a week that has ended (R12)."""
    monday = ist_today() - timedelta(days=ist_today().weekday() + 7)
    return monday, monday + timedelta(days=7)


async def deliver_last_week(order_id: str) -> None:
    """The test's order was delivered today; a run pays only ended weeks, so move it to last Wednesday noon IST."""
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    wednesday = datetime.combine(ist_last_week()[0] + timedelta(days=2), datetime.min.time().replace(hour=12),
                                 tzinfo=ZoneInfo("Asia/Kolkata"))
    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE orders SET actual_delivery_time = CAST(:t AS timestamptz), "
                              "created_at = CAST(:t AS timestamptz) - interval '40 minutes', "
                              "rider_assigned_at = CAST(:t AS timestamptz) - interval '30 minutes', "
                              "picked_up_at = CAST(:t AS timestamptz) - interval '15 minutes' "
                              "WHERE id = CAST(:id AS uuid)"), {"t": wednesday, "id": order_id})
        await db.commit()


async def test_payout_run_end_to_end(client: AsyncClient) -> None:
    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)  # 2 × Veg Dum Biryani, rider1.hyd, today
    support = await login(client, "support.hyd@example.com", ADMIN)
    biryani = order["items"][0]["menu_item_id"]
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "missing_item"})
    assert r.status_code == 201
    # The second biryani arrived crushed: delivery's fault, so the platform pays for it.
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=support,
                          json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": "damaged_in_transit"})
    assert r.status_code == 201

    await deliver_last_week(order["id"])

    finance = await login(client, "finance.in@example.com", ADMIN)
    # This week hasn't ended, and a run covers Monday to Sunday only (R12).
    this_monday = ist_last_week()[1]
    for start, end in ((this_monday, this_monday + timedelta(days=7)), (ist_last_week()[0] + timedelta(days=1), this_monday)):
        r = await client.post("/api/v1/finance/payout-runs", headers=finance,
                              json={"country": "IN", "period_start": start.isoformat(), "period_end": end.isoformat()})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "FINANCE_RULE", r.text
    weeks = (await client.get("/api/v1/finance/payout-weeks", headers=finance, params={"country": "IN"})).json()
    assert weeks["weeks"][0] == {"start": ist_last_week()[0].isoformat(), "end": ist_last_week()[1].isoformat()}

    period = {"country": "IN", "period_start": ist_last_week()[0].isoformat(), "period_end": ist_last_week()[1].isoformat()}
    r = await client.post("/api/v1/finance/payout-runs", headers=finance, json=period)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "draft" and run["totals"]["orders"] >= 1
    # R14: Reconciliation for the same week owes exactly what the run pays (top-ups included),
    # and captured is every part added up.
    rec = (await client.get("/api/v1/finance/reconciliation", headers=finance, params={
        "country": "IN", "start": period["period_start"], "end": period["period_end"]})).json()["money"]
    cents = lambda v: int((Decimal(v) * 100).to_integral_value())
    assert rec["restaurant_payable"] == cents(run["totals"]["restaurants"])
    assert rec["rider_payable"] == cents(run["totals"]["riders"]) and rec["min_pay_top_ups"] == cents(run["totals"]["min_pay_top_ups"])
    assert rec["captured"] == rec["refunded"] + rec["restaurant_payable"] + rec["rider_payable"] + rec["tax_owed"] + rec["platform_revenue"]
    assert (await client.post("/api/v1/finance/payout-runs", headers=finance, json=period)).status_code == 409  # overlap

    detail = (await client.get(f"/api/v1/finance/payout-runs/{run['id']}", headers=finance)).json()
    spice = next(s for s in detail["statements"] if s["payee_type"] == "restaurant" and s["payee_name"] == "Spice Route Kitchen")
    rider = next(s for s in detail["statements"] if s["payee_type"] == "rider" and s["payee_name"] == "Ravi Kumar")

    stmt = (await client.get(f"/api/v1/finance/statements/{spice['id']}", headers=finance)).json()
    line = next(ln for ln in stmt["lines"] if ln["order_id"] == order["id"])
    food, commission = Decimal(line["food"]), -Decimal(line["commission"])
    assert commission == (food * Decimal("0.15")).quantize(Decimal("0.01"))  # R29: Spice Route's own 15% deal
    # Only the restaurant's own mistake comes off its payout; both are listed with their reason.
    assert -Decimal(line["refunds"]) == (Decimal("240") * (1 - commission / food)).quantize(Decimal("0.01"))
    assert [(d["reason"], d["charged_to"]) for d in line["refund_details"]] == [
        ("missing_item", "restaurant"), ("damaged_in_transit", "platform")]
    # R16: GST on our commission (India 18%) and TDS (0% until a CA confirms) come off the kitchen's payout too
    assert Decimal(line["commission_tax"]) == -(commission * Decimal("0.18")).quantize(Decimal("0.01")) and Decimal(line["tds"]) == 0
    assert Decimal(line["card_fee"]) < 0  # R29: the card fee comes off the kitchen's payout
    assert Decimal(line["net"]) == (food + Decimal(line["packaging"]) - commission + Decimal(line["refunds"])
                                    + Decimal(line["commission_tax"]) + Decimal(line["tds"]) + Decimal(line["card_fee"]))

    rs = (await client.get(f"/api/v1/finance/statements/{rider['id']}", headers=finance)).json()
    rl = next(ln for ln in rs["lines"] if ln["order_id"] == order["id"])
    assert rl["base"] == "25.00" and Decimal(rl["distance"]) == (6 * Decimal(rl["distance_units"])).quantize(Decimal("0.01"))
    assert rs["summary"]["hourly_floor"] == "120" and Decimal(rs["summary"]["floor_top_up"]) >= 0

    # Maker-checker: the preparer can't approve; city ops can't at all.
    assert (await client.post(f"/api/v1/finance/payout-runs/{run['id']}/approve", headers=finance)).status_code == 409
    ops = await login(client, "ops.hyd@example.com", ADMIN)
    assert (await client.post(f"/api/v1/finance/payout-runs/{run['id']}/approve", headers=ops)).status_code == 403

    admin = await login(client, "admin@example.com", ADMIN)
    # R14: on QA nothing is approved while a payee owed money has no ready payout account.
    from shared.config import get_settings

    settings, was = get_settings(), get_settings().APP_ENV
    settings.APP_ENV = "qa"
    try:
        r = await client.post(f"/api/v1/finance/payout-runs/{run['id']}/approve", headers=admin)
        assert r.status_code == 409 and "every payee's payout account is ready" in r.json()["detail"]["message"], r.text
    finally:
        settings.APP_ENV = was
    r = await client.post(f"/api/v1/finance/payout-runs/{run['id']}/approve", headers=admin)
    assert r.status_code == 200, r.text
    approved = r.json()
    assert approved["status"] == "partially_paid"  # payees haven't set up payout accounts yet
    assert {s["status"] for s in approved["statements"]} == {"no_account"}

    # The partner and the rider set up payouts (fake provider: active at once), then finance retries.
    partner = await login(client, "partner.hyd@example.com")
    r = await client.post("/api/v1/finance/payout-accounts", headers=partner,
                          json={"payee_type": "restaurant", "restaurant_id": order["restaurant_id"]})
    assert r.status_code == 201 and r.json()["status"] == "active"
    rider_h = await login(client, "rider1.hyd@example.com")
    assert (await client.post("/api/v1/finance/payout-accounts", headers=rider_h, json={"payee_type": "rider"})).status_code == 201
    r = await client.post(f"/api/v1/finance/payout-runs/{run['id']}/retry", headers=admin)
    statuses = {(s["payee_name"], s["status"]) for s in r.json()["statements"]}
    assert ("Spice Route Kitchen", "paid") in statuses and ("Ravi Kumar", "paid") in statuses

    mine = (await client.get("/api/v1/finance/statements/me", headers=partner)).json()
    assert any(s["id"] == spice["id"] and s["status"] == "paid" and s["transfer_id"].startswith("fake_tr_") for s in mine)
    # R16: the commission tax invoice to the kitchen: as a PDF for its owner (and finance), and through
    # a one-hour link the Kitchen app opens in a browser; another partner can't get it.
    r = await client.get(f"/api/v1/finance/statements/{spice['id']}/commission-invoice", headers=partner)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF", r.text[:200]
    link = (await client.post(f"/api/v1/finance/statements/{spice['id']}/commission-invoice/link", headers=partner)).json()["url"]
    token = link.split("t=", 1)[1]
    r = await client.get("/api/v1/finance/commission-invoice", params={"t": token})
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert (await client.get("/api/v1/finance/commission-invoice", params={"t": token[:-2] + "xx"})).status_code == 404
    assert (await client.get(f"/api/v1/finance/statements/{spice['id']}/commission-invoice",
                             headers=await login(client, "partner.boi@example.com"))).status_code == 404
    other_partner = await login(client, "partner.boi@example.com")
    assert (await client.get(f"/api/v1/finance/statements/{spice['id']}", headers=other_partner)).status_code == 404

    # Sent back by the bank (a reversal): the partner is told the date it's paid again, the
    # country's next payout day (R12), and on that day the scheduler pays it with a new transfer.
    from sqlalchemy import text

    from core_api.modules.finance.service.payouts import next_payout_day
    from core_api.modules.finance.service.schedule import repay_unpaid
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("UPDATE payout_statements SET status = 'reversed', attempts = attempts + 1 WHERE id = :id"),
                         {"id": spice["id"]})
        await db.execute(text("UPDATE payout_runs SET status = 'partially_paid' WHERE id = :id"), {"id": run["id"]})
        await db.commit()
        pay_day = await next_payout_day(db, "IN")
    mine = (await client.get("/api/v1/finance/statements/me", headers=partner)).json()
    reversed_ = next(s for s in mine if s["id"] == spice["id"])
    assert reversed_["status"] == "reversed" and reversed_["repay_on"] == pay_day.isoformat()
    async with AsyncSessionLocal() as db:
        not_today = datetime.combine(pay_day + timedelta(days=1), datetime.min.time().replace(hour=12), tzinfo=ZoneInfo("Asia/Kolkata"))
        assert await repay_unpaid(db, now=not_today.astimezone(UTC)) == 0
        on_day = datetime.combine(pay_day, datetime.min.time().replace(hour=12), tzinfo=ZoneInfo("Asia/Kolkata"))
        assert await repay_unpaid(db, now=on_day.astimezone(UTC)) >= 1
        await db.commit()
    mine = (await client.get("/api/v1/finance/statements/me", headers=partner)).json()
    assert next(s for s in mine if s["id"] == spice["id"])["status"] == "paid"


async def test_reconciliation_report(client: AsyncClient) -> None:
    finance = await login(client, "finance.in@example.com", ADMIN)
    params = {"country": "IN", "start": (ist_today() - timedelta(days=1)).isoformat(),
              "end": (ist_today() + timedelta(days=1)).isoformat()}
    r = await client.get("/api/v1/finance/reconciliation", headers=finance, params=params)
    assert r.status_code == 200, r.text
    rep = r.json()
    money = rep["money"]
    assert money["captured"] > 0 and money["net_collected"] == money["captured"] - money["refunded"]
    assert "fake" in rep["by_provider"]
    assert money["delivered_gmv"] >= money["restaurant_payable"] + money["rider_payable"]
    csv = await client.get("/api/v1/finance/reconciliation", headers=finance, params={**params, "format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv") and "money,captured," in csv.text
    viewer_us = await login(client, "finance.us@example.com", ADMIN)
    assert (await client.get("/api/v1/finance/reconciliation", headers=viewer_us, params=params)).status_code == 403


async def test_weekly_draft_on_payout_day(client: AsyncClient) -> None:
    from core_api.modules.finance.service.schedule import ensure_weekly_drafts
    from shared.db import AsyncSessionLocal

    # A Boise order delivered this week, then "now" is next week's payout day (Monday, after the 2-day hold).
    cust = await login(client, "customer1.boi@example.com")
    from core_api.integration.test_orders_flow import move

    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 50})).json()["items"] if r["name"] == "Boise Bowl Co.")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == "Crispy Tofu Bowl")
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = (await client.post("/api/v1/pricing/quote", headers=cust, json={"restaurant_id": rest["id"], "items": cart,
                                                                         "deliver_to": {"lat": 43.6290, "lng": -116.2070}})).json()
    o = (await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "card", "quote_token": q["token"],
        "delivery_address": {"street": "1510 N 13th St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}})).json()
    from core_api.integration.test_orders_flow import pay

    await pay(client, cust, o)
    partner, rider = await login(client, "partner.boi@example.com"), await login(client, "rider1.boi@example.com")
    for s in ("accepted", "preparing", "ready"):
        await move(client, partner, o["id"], s)
    from core_api.integration.test_orders_flow import assign

    assert (await assign(client, o["id"], rider)).status_code == 200
    await move(client, rider, o["id"], "picked_up")
    await move(client, rider, o["id"], "delivered")

    boise_now = datetime.now(ZoneInfo("America/Boise"))
    next_monday = (boise_now + timedelta(days=7 - boise_now.weekday())).replace(hour=12)
    async with AsyncSessionLocal() as db:
        made = await ensure_weekly_drafts(db, now=(next_monday + timedelta(days=2)).astimezone(UTC))
        await db.commit()
    us = [r for r in made if r.country == "US"]
    assert us and us[0].status == "draft" and us[0].totals["orders"] >= 1
    async with AsyncSessionLocal() as db:  # idempotent
        assert [r for r in await ensure_weekly_drafts(db, now=(next_monday + timedelta(days=2)).astimezone(UTC)) if r.country == "US"] == []
