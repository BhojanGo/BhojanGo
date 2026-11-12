"""G1, the Phase 1 gate: an order goes all the way through with no admin action.

Customer pays (fake provider) → restaurant accepts through the API → dispatch
offers it to the nearest rider → rider accepts → pickup → delivered →
restaurant and rider are in the weekly payout run → messages were sent.

Run twice: the Hyderabad worked example (₹638.22, restaurant nets ₹486.00)
and a Boise order with Idaho sales tax from the tax provider.
"""
import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from e2e.conftest import CORE, MAIL, Api, idem, wait_for

pytestmark = pytest.mark.skipif(not CORE, reason="needs a running stack (set E2E_CORE_API)")

SPICE = "spice-route-kitchen-madhapur"
SPICE_AT = (17.4486, 78.3908)
JUBILEE_HILLS = (17.43, 78.41)  # the worked example's drop-off, ~3.8 km by road
BOISE_BOWL_AT = (43.6295, -116.2008)
IST = ZoneInfo("Asia/Kolkata")


def run(coro):  # type: ignore[no-untyped-def]
    """Run a database step in its own event loop and drop the pool afterwards."""
    from shared.db import engine

    async def go():  # type: ignore[no-untyped-def]
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(go())


async def sql(query: str, **params: object) -> list:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return list((await db.execute(text(query), params)).mappings().all())


async def sql_commit(query: str, **params: object) -> None:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text(query), params)
        await db.commit()


def next_thursday_8pm_ist() -> datetime:
    now = datetime.now(IST)
    days = (3 - now.weekday()) % 7 or 7
    return datetime.combine(now.date() + timedelta(days=days), time(20, 0), IST).astimezone(UTC)


def menu_ids(api: Api, rid: str) -> dict[str, str]:
    menu = api.core("GET", f"/restaurants/{rid}/menu").json()
    return {i["name"]: i["id"] for c in menu["categories"] for i in c["items"]}


def weekly_payout_job(delivered_on: date, tz: str) -> None:
    """The scheduler's weekly job, run on the payout day after the delivery's week."""
    from core_api.modules.finance.service.schedule import ensure_weekly_drafts
    from shared.db import AsyncSessionLocal

    week_start = delivered_on - timedelta(days=delivered_on.weekday())
    pay_day = datetime.combine(week_start + timedelta(days=9), time(12, 0), ZoneInfo(tz))  # Wednesday after

    async def go() -> None:
        # A rerun on the same stack: drop an earlier draft for that week so the job makes it again.
        overlapping = "period_start < :e AND period_end > :s AND status = 'draft'"
        await sql_commit(f"DELETE FROM payout_statements WHERE run_id IN (SELECT id FROM payout_runs WHERE {overlapping})",
                         s=week_start, e=week_start + timedelta(days=7))
        await sql_commit(f"DELETE FROM payout_runs WHERE {overlapping}", s=week_start, e=week_start + timedelta(days=7))
        async with AsyncSessionLocal() as db:
            await ensure_weekly_drafts(db, now=pay_day)
            await db.commit()

    run(go())


def deliver_through_dispatch(order: dict, customer: Api, partner: Api, rider: Api, near: tuple[float, float]) -> None:
    """Pay → accept → dispatch → rider accepts → pickup → delivered, all over HTTP."""
    oid = order["id"]
    r = customer.core("POST", "/payments/initiate", json={"order_id": oid, "payment_method_type": "card"})
    assert r.status_code == 201, r.text
    # The fake provider completes checkout on its own and sends the webhook.
    assert wait_for(lambda: customer.core("GET", f"/orders/{oid}").json()["status"] == "placed"), "payment never placed the order"

    assert rider.rt("POST", "/riders/me/online", json={"lat": near[0] + 0.004, "lng": near[1]}).status_code == 200
    for s in ("accepted", "preparing", "almost_ready"):
        r = partner.core("PUT", f"/orders/{oid}/status", json={"status": s})
        assert r.status_code == 200, (s, r.text)
    offer = wait_for(lambda: (rider.rt("GET", "/riders/me").json().get("offer") or {}).get("order_id") == oid)
    assert offer, "dispatch never offered the order to the rider"
    r = rider.rt("POST", f"/offers/{oid}/accept")
    assert r.status_code == 200 and r.json()["status"] == "assigned", r.text
    assert partner.core("PUT", f"/orders/{oid}/status", json={"status": "ready"}).status_code == 200
    for s in ("picked_up", "delivered"):
        r = rider.core("PUT", f"/orders/{oid}/status", json={"status": s})
        assert r.status_code == 200, (s, r.text)
    rider.rt("POST", "/riders/me/offline")


def assert_messages_sent(order_id: str, customer: Api, partner_id: str, customer_email: str) -> None:
    want = {"order_placed", "order_accepted", "order_preparing", "driver_assigned", "order_picked_up", "order_delivered"}

    def inbox() -> set[str]:
        items = customer.wk("GET", "/notifications", params={"limit": 50}).json()["items"]
        return {n["type"] for n in items if (n.get("data") or {}).get("order_id") == order_id}

    got = wait_for(lambda: want <= inbox() and inbox())
    assert got and want <= got, f"customer inbox: {inbox()}"
    partner_rows = run(sql("SELECT channel, status FROM notifications WHERE user_id = :u AND type = 'partner_new_order' "
                           "AND data->>'order_id' = :o", u=partner_id, o=order_id))
    assert {(r["channel"], r["status"]) for r in partner_rows} >= {("in_app", "sent"), ("sms", "sent")}, partner_rows
    import httpx

    def mails() -> list[str]:
        msgs = httpx.get(f"{MAIL}/api/v1/messages", params={"limit": 200}).json().get("messages", [])
        return [m["Subject"] for m in msgs if any(t["Address"] == customer_email for t in m["To"])]

    code = "#" + order_id.replace("-", "")[:6].upper()
    assert wait_for(lambda: [s for s in mails() if code in s and "Delivered" in s]), mails()
    assert any(code in s and "Order placed" in s for s in mails()), mails()


def statement_line(payee_type: str, payee_id: str, order_id: str, week_start: date) -> dict:
    rows = run(sql("SELECT s.lines, s.amount FROM payout_statements s JOIN payout_runs r ON r.id = s.run_id "
                   "WHERE r.period_start = :w AND s.payee_type = :t AND s.payee_id = :p",
                   w=week_start, t=payee_type, p=payee_id))
    assert rows, f"no {payee_type} statement in the weekly run for {week_start}"
    line = next((ln for ln in rows[0]["lines"] if ln["order_id"] == order_id), None)
    assert line, f"order {order_id} missing from the {payee_type} statement"
    return line


def test_g1_hyderabad_worked_example() -> None:
    from core_api.modules.pricing.schemas import QuoteRequest
    from core_api.modules.pricing.service.quotes import QuoteService
    from shared.db import AsyncSessionLocal

    customer, partner, rider = Api("customer1.hyd@example.com"), Api("partner.hyd@example.com"), Api("rider1.hyd@example.com")
    rid = next(r for r in customer.core("GET", "/restaurants", params={"limit": 50}).json()["items"] if r["slug"] == SPICE)["id"]
    items = menu_ids(customer, rid)
    cart = [{"menu_item_id": items["Chicken Dum Biryani"], "quantity": 1, "options": [
                {"group": "Size", "option": "Regular · serves 1"}, {"group": "Spice", "option": "Medium"},
                {"group": "Add-ons", "option": "Extra raita"}]},
            {"menu_item_id": items["Paneer Tikka"], "quantity": 1}]

    # The worked example is priced on a Thursday at 8 PM (evening surge); the quote
    # service runs at that time, everything after it goes through the API.
    async def price():  # type: ignore[no-untyped-def]
        async with AsyncSessionLocal() as db:
            q = await QuoteService(db).quote(uuid.UUID(customer.user["id"]), QuoteRequest(
                restaurant_id=rid, items=cart, deliver_to={"lat": JUBILEE_HILLS[0], "lng": JUBILEE_HILLS[1]}, tip=20),
                now=next_thursday_8pm_ist())
            await db.commit()
            return q

    q = run(price())
    assert q.total == Decimal("638.22"), q.lines

    r = customer.core("POST", "/orders", headers=idem(), json={
        "restaurant_id": rid, "items": cart, "payment_method": "upi", "quote_token": q.token,
        "delivery_address": {"street": "12-2-41, Road No. 36", "city": "Hyderabad", "state": "Telangana",
                             "zip": "500033", "country": "IN"}})
    assert r.status_code == 201, r.text
    order = r.json()
    assert Decimal(str(order["total"])) == Decimal("638.22")

    deliver_through_dispatch(order, customer, partner, rider, SPICE_AT)
    pay = customer.core("GET", f"/payments/{order['id']}").json()
    assert pay["amount"] == 63822 and pay["status"] == "succeeded", pay
    bill = customer.core("GET", f"/pricing/orders/{order['id']}/bill").json()
    assert bill["total"] == "638.22"

    delivered_on = datetime.now(IST).date()
    weekly_payout_job(delivered_on, "Asia/Kolkata")
    week_start = delivered_on - timedelta(days=delivered_on.weekday())
    rest = statement_line("restaurant", rid, order["id"], week_start)
    assert rest["net"] == "486.00", rest  # 560 food + 10 packaging - 84 commission
    ride = statement_line("rider", rider.user["id"], order["id"], week_start)
    assert ride["base"] == "25.00" and ride["tip"] == "20.00", ride

    assert_messages_sent(order["id"], customer, partner.user["id"], "customer1.hyd@example.com")


def test_g1_boise_with_idaho_sales_tax() -> None:
    customer, partner, rider = Api("customer1.boi@example.com"), Api("partner.boi@example.com"), Api("rider1.boi@example.com")
    rest = next(r for r in customer.core("GET", "/restaurants", params={"limit": 50}).json()["items"] if r["name"] == "Boise Bowl Co.")
    items = menu_ids(customer, rest["id"])
    cart = [{"menu_item_id": items["Teriyaki Chicken Bowl"], "quantity": 2}]
    address = customer.core("GET", "/me/addresses").json()[0]
    r = customer.core("POST", "/pricing/quote", json={"restaurant_id": rest["id"], "items": cart,
                                                      "deliver_to": {"address_id": address["id"]}, "tip": "3"})
    assert r.status_code == 200, r.text
    q = r.json()
    tax = next(ln for ln in q["lines"] if ln["label"] == "Idaho sales tax")
    taxable = sum(Decimal(ln["amount"]) for ln in q["lines"]
                  if ln["code"] in ("food", "promotion", "delivery_fee", "service_fee", "small_order_fee"))
    assert tax["detail"]["rate_percent"] == "6" and Decimal(tax["amount"]) == (taxable * Decimal("0.06")).quantize(Decimal("0.01"))

    r = customer.core("POST", "/orders", headers=idem(), json={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "card", "quote_token": q["token"],
        "delivery_address": {"street": address.get("street", "1510 N 13th St"), "city": "Boise", "state": "ID",
                             "zip": address.get("postal_code") or "83702", "country": "US"}})
    assert r.status_code == 201, r.text
    order = r.json()

    deliver_through_dispatch(order, customer, partner, rider, BOISE_BOWL_AT)
    pay = customer.core("GET", f"/payments/{order['id']}").json()
    assert pay["amount"] == int(Decimal(q["total"]) * 100) and pay["currency"] == "USD", pay
    bill = customer.core("GET", f"/pricing/orders/{order['id']}/bill").json()
    assert [t["label"] for t in bill["taxes"]] == ["Idaho sales tax"] and bill["total"] == q["total"]

    delivered_on = datetime.now(ZoneInfo("America/Boise")).date()
    weekly_payout_job(delivered_on, "America/Boise")
    week_start = delivered_on - timedelta(days=delivered_on.weekday())
    statement_line("restaurant", rest["id"], order["id"], week_start)
    statement_line("rider", rider.user["id"], order["id"], week_start)

    assert_messages_sent(order["id"], customer, partner.user["id"], "customer1.boi@example.com")
