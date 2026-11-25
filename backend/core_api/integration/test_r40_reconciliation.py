"""R40 item 2: the finance model, to the cent and the paisa, on a fixed set of orders.

    Customer pays: food + packaging + delivery fee + platform fee + tax + tip.
    Restaurant receives: food + packaging - commission (and GST on it, TDS) - offers it funds - card fee for the
    whole charge - refunds for its own mistakes.
    Delivery partner receives: delivery fee + tip.
    BhojanGo receives: platform fee (+ any commission) - offers it funds - the refunds it bears. No card fees.

    captured - refunded = restaurants + card fees + delivery partners + tax + BhojanGo

Each order's share is worked out here from its own bill lines (independently of the finance code), then the
Reconciliation, the payout run, the restaurant statements and the contribution report must show exactly the same
totals. The orders are moved into a week of their own (long ago), so those screens hold only them.

US (Boise): a delivery with a tip, a delivery with a BhojanGo-funded $3 offer and a chargeback still open (food
quality: the restaurant's share is held), a pickup with a tip, and a cancelled order (refunded in full: outside the
week's money). India (Hyderabad): a delivery at Spice Route (its own 15% commission deal, GST on it) with a refund
for the restaurant's mistake and one for the delivery's.
"""
import os
import random
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login, new_order, pay  # noqa: F401
from core_api.integration.test_r38_offer_returns import offer
from core_api.integration.test_r39_disputes import dispute_event

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"
BOISE = "US-ID-BOI"
DOWNTOWN = {"lat": 43.6150, "lng": -116.2023}
US_ADDRESS = {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}
FEES = ("platform_fee", "service_fee", "small_order_fee", "late_night_fee")


async def rows(q: str, **p):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(text(q), p)
        out = res.all() if res.returns_rows else []
        await db.commit()
        return out


def minor(v) -> int:  # type: ignore[no-untyped-def]
    return int((Decimal(str(v)) * 100).to_integral_value())


async def boise_menu(client: AsyncClient) -> tuple[str, dict[str, str]]:
    rest = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 100})).json()["items"]
                if r["name"] == "Boise Bowl Co.")
    menu = (await client.get(f"/api/v1/restaurants/{rest['id']}/menu")).json()
    return rest["id"], {i["name"]: i["id"] for c in menu["categories"] for i in c["items"]}


async def us_order(client: AsyncClient, cust: dict, rid: str, cart: list[dict], *, tip: str = "0", pickup: bool = False) -> dict:
    body: dict = {"restaurant_id": rid, "items": cart, "tip": tip}
    body.update({"fulfillment": "pickup"} if pickup else {"deliver_to": DOWNTOWN})
    q = await client.post("/api/v1/pricing/quote", headers=cust, json=body)
    assert q.status_code == 200, q.text
    r = await client.post("/api/v1/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": rid, "items": cart, "payment_method": "card", "quote_token": q.json()["token"],
        **({} if pickup else {"delivery_address": US_ADDRESS})})
    assert r.status_code == 201, r.text
    order = r.json()
    init = await client.post("/api/v1/payments/initiate", headers=cust, json={"order_id": order["id"], "payment_method_type": "card"})
    assert init.status_code == 201, init.text
    done = await client.post(f"/api/v1/payments/fake/{init.json()['payment_intent_id']}/complete", headers=cust, json={"outcome": "succeeded"})
    assert done.status_code == 200, done.text
    return order


async def delivered_in(order_id: str, rider_email: str | None, at: datetime) -> None:
    """The money doesn't depend on how the order got there: delivered (or collected) at ``at``, by ``rider_email``."""
    await rows("UPDATE orders SET status = 'delivered', actual_delivery_time = CAST(:t AS timestamptz), "
               "created_at = CAST(:t AS timestamptz) - interval '40 minutes', "
               "rider_assigned_at = CASE WHEN CAST(:r AS text) IS NULL THEN NULL ELSE CAST(:t AS timestamptz) - interval '30 minutes' END, "
               "picked_up_at = CAST(:t AS timestamptz) - interval '15 minutes', "
               "driver_id = (SELECT id FROM users WHERE email = CAST(:r AS text)) WHERE id = CAST(:o AS uuid)",
               t=at, r=rider_email, o=order_id)


async def expected(order_id: str) -> dict[str, int]:
    """One order's shares from its own bill lines, split, card fee and refunds (minor units): the model."""
    (lines, split, card_fee, total), = await rows(
        "SELECT s.lines, s.split, o.card_fee, o.total FROM order_pricing_snapshots s JOIN orders o ON o.id = s.order_id "
        "WHERE o.id = CAST(:o AS uuid)", o=order_id)
    amt = lambda *codes: sum(minor(ln["amount"]) for ln in lines if ln["code"] in codes)  # noqa: E731
    funded = lambda who: -sum(minor(ln["amount"]) for ln in lines if ln["code"] == "promotion" and ln.get("funded_by") == who)  # noqa: E731
    detail = split.get("detail", {})
    commission = minor(detail.get("commission", 0))
    commission_tax = round(commission * Decimal(18) / 100) if commission else 0  # India: GST 18% on our commission
    refunds = await rows("SELECT amount, fault, lines FROM refunds WHERE order_id = CAST(:o AS uuid) AND status NOT IN ('failed', 'rejected')",
                         o=order_id)
    refunded = sum(a for a, _, _ in refunds)
    food = amt("food")
    keep = 1 - Decimal(commission) / food if food else Decimal(1)
    restaurant_charged = sum(int((Decimal(minor(ln["food"])) * keep).quantize(Decimal(1)))
                             for _, fault, lns in refunds if (fault or "restaurant") == "restaurant"
                             for ln in lns if ln.get("menu_item_id"))
    restaurant = food + amt("packaging") - commission - commission_tax - funded("restaurant") - minor(card_fee) - restaurant_charged
    partner = amt("delivery_fee", "surge") + amt("tip")
    tax = amt("tax") + commission_tax
    bhojango = amt(*FEES) - funded("platform") + commission - (refunded - restaurant_charged)
    out = {"captured": minor(total), "refunded": refunded, "restaurant": restaurant, "card_fee": minor(card_fee),
           "partner": partner, "tax": tax, "bhojango": bhojango}
    # The model, order by order: every cent the customer paid goes to exactly one of them
    assert out["captured"] - refunded == restaurant + out["card_fee"] + partner + tax + bhojango, (order_id, out, lines)
    return out


def isolated_week() -> date:
    """A Monday long ago that no other test's payout run covers."""
    return date(2002, 1, 7) + timedelta(weeks=random.randint(0, 700))


async def check_screens(client: AsyncClient, finance: dict, country: str, start: date, mine: list[dict[str, int]],
                        held: int = 0) -> dict:
    """Reconciliation, the payout run, the restaurant statements and the contribution report agree with the model."""
    end = start + timedelta(days=7)
    want = {k: sum(o[k] for o in mine) for k in mine[0]}
    rec = (await client.get("/api/v1/finance/reconciliation", headers=finance, params={
        "country": country, "start": start.isoformat(), "end": end.isoformat()})).json()["money"]
    got = {"captured": rec["captured"], "refunded": rec["refunded"], "restaurant": rec["restaurant_payable"], "card_fee": rec["card_fees"],
           "partner": rec["rider_payable"], "tax": rec["tax_owed"], "bhojango": rec["platform_revenue"]}
    assert got == want, (country, got, want)
    assert rec["captured"] - rec["refunded"] == (rec["restaurant_payable"] + rec["card_fees"] + rec["rider_payable"]
                                                 + rec["tax_owed"] + rec["platform_revenue"])
    run = await client.post("/api/v1/finance/payout-runs", headers=finance, json={
        "country": country, "period_start": start.isoformat(), "period_end": end.isoformat()})
    assert run.status_code == 201, run.text
    run = (await client.get(f"/api/v1/finance/payout-runs/{run.json()['id']}", headers=finance)).json()
    assert minor(run["totals"]["restaurants"]) == want["restaurant"] and minor(run["totals"]["riders"]) == want["partner"], run["totals"]
    kitchens = [s for s in run["statements"] if s["payee_type"] == "restaurant"]
    assert sum(minor(s["summary"].get("card_fee", 0)) for s in kitchens) == want["card_fee"]  # on the restaurants' statements
    assert sum(s["amount"] for s in kitchens) == want["restaurant"] - held  # an open chargeback holds the share
    rec2 = (await client.get("/api/v1/finance/reconciliation", headers=finance, params={
        "country": country, "start": start.isoformat(), "end": end.isoformat()})).json()
    assert rec2["money"]["platform_revenue"] == want["bhojango"]  # the run changes nothing BhojanGo keeps
    assert (rec2["not_in_run"] or {}).get("chargeback_holds", 0) == held and not (rec2["not_in_run"] or {}).get("orders")
    con = (await client.get("/api/v1/finance/contribution", headers=finance, params={
        "scope": country, "start": start.isoformat(), "end": end.isoformat()})).json()["all"]["totals"]
    assert minor(con["keeps"]) == want["bhojango"] and minor(con["card_fees"]) == want["card_fee"], con
    assert minor(con["gmv"]) == want["captured"]
    return rec2


async def test_us_week_to_the_cent(client: AsyncClient) -> None:  # noqa: F811
    await rows("DELETE FROM payment_disputes WHERE country = 'US'")
    maker, checker = await login(client, "cm.us@example.com", ADMIN), await login(client, "finance.us@example.com", ADMIN)
    cust = await login(client, "customer2.boi@example.com")
    rid, menu = await boise_menu(client)
    start = isolated_week()
    at = datetime.combine(start + timedelta(days=2), time(12), tzinfo=ZoneInfo("America/Boise"))
    rider = (await rows("SELECT email FROM users WHERE email LIKE 'rider%.boi@example.com' ORDER BY email LIMIT 1"))[0][0]
    tofu = [{"menu_item_id": menu["Crispy Tofu Bowl"], "quantity": 2}]
    teriyaki = [{"menu_item_id": menu["Teriyaki Chicken Bowl"], "quantity": 2}]  # above Boise Bowl's $15 minimum

    tipped = await us_order(client, cust, rid, tofu, tip="3")
    pickup = await us_order(client, cust, rid, teriyaki, tip="2", pickup=True)
    cancelled = await us_order(client, cust, rid, teriyaki)
    r = await client.post(f"/api/v1/orders/{cancelled['id']}/cancel", headers=cust, json={"reason": "customer_cancelled"})
    assert r.status_code == 200, r.text
    await rows("DELETE FROM platform_offer_spend WHERE pool = 'city:US-ID-BOI'")
    assert (await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": "50"})).status_code == 200
    rule = await offer(client, maker, checker, BOISE, f"r40_{uuid.uuid4().hex[:6]}", 3)
    try:
        offered = await us_order(client, cust, rid, tofu, tip="1")
    finally:
        await client.post(f"/api/v1/rules/{rule['id']}/end", headers=checker, json={})
        await client.put(f"/api/v1/rules/offers/budgets/city/{BOISE}", headers=maker, json={"monthly": None})
    (lines,), = await rows("SELECT lines FROM order_pricing_snapshots WHERE order_id = CAST(:o AS uuid)", o=offered["id"])
    assert any(ln["code"] == "promotion" and ln.get("funded_by") == "platform" for ln in lines), lines

    # The cancelled order was refunded in full and is outside the week's money
    (cap, ref), = await rows("SELECT coalesce(sum(amount), 0), coalesce(sum(refunded_amount), 0) FROM payment_intents "
                             "WHERE order_id = CAST(:o AS uuid) AND status IN ('succeeded', 'partially_refunded', 'refunded')",
                             o=cancelled["id"])
    assert cap > 0 and cap == ref, (cap, ref)

    for o, who in ((tipped, rider), (offered, rider), (pickup, None)):
        await delivered_in(o["id"], who, at)
    # A chargeback on the offer order, still open: food quality, so the restaurant's share is held
    (pi, amount), = await rows("SELECT provider_payment_id, amount FROM payment_intents WHERE order_id = CAST(:o AS uuid) "
                               "AND status = 'succeeded'", o=offered["id"])
    await dispute_event(client, "created", {"id": f"dp_r40_{uuid.uuid4().hex[:10]}", "amount": amount, "currency": "usd",
                                            "reason": "product_unacceptable", "status": "needs_response", "payment_intent": pi})
    (held,), = await rows("SELECT held FROM payment_disputes WHERE order_id = CAST(:o AS uuid)", o=offered["id"])
    assert held > 0

    mine = [await expected(o["id"]) for o in (tipped, offered, pickup)]
    assert mine[0]["partner"] == minor(Decimal(next(ln["amount"] for ln in (await rows(
        "SELECT lines FROM order_pricing_snapshots WHERE order_id = CAST(:o AS uuid)", o=tipped["id"]))[0][0]
        if ln["code"] == "delivery_fee"))) + 300  # the delivery fee and the whole $3 tip
    (plines,), = await rows("SELECT lines FROM order_pricing_snapshots WHERE order_id = CAST(:o AS uuid)", o=pickup["id"])
    assert not any(ln["code"] in ("delivery_fee", "tip") for ln in plines), plines  # pickup: no delivery fee, no tip (R32)
    assert mine[2]["partner"] == 0
    rec = await check_screens(client, checker, "US", start, mine, held)  # finance.us (one sign-in per code window)
    assert rec["money"]["card_fees"] == sum(o["card_fee"] for o in mine) > 0


async def test_india_week_to_the_paisa(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order = await new_order(client, cust)  # 2 x Veg Dum Biryani at Spice Route (its own 15% commission deal)
    await pay(client, cust, order)
    start = isolated_week()
    at = datetime.combine(start + timedelta(days=2), time(12), tzinfo=ZoneInfo("Asia/Kolkata"))
    await delivered_in(order["id"], "rider1.hyd@example.com", at)
    ops = await login(client, "ops.hyd@example.com", ADMIN)
    biryani = order["items"][0]["menu_item_id"]
    for reason in ("missing_item", "damaged_in_transit"):  # the restaurant's mistake, then the delivery's (BhojanGo's)
        r = await client.post(f"/api/v1/payments/orders/{order['id']}/refunds", headers=ops,
                              json={"items": [{"menu_item_id": biryani, "quantity": 1}], "reason": reason})
        assert r.status_code == 201, r.text
    mine = [await expected(order["id"])]
    assert mine[0]["refunded"] > 0 and mine[0]["card_fee"] == 0  # UPI: no card fee in India's estimate
    await check_screens(client, await login(client, "finance.in@example.com", ADMIN), "IN", start, mine)
