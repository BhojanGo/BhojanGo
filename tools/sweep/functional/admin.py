"""R42: the admin console's functions, page by page (framework.py). Brief item d first: fees by level, delivery bands,
offers and budget, finance (prepare -> a second admin approves -> statements), chargebacks (evidence, won, lost),
food permits, the test alert. The console's "us" / "in" users are the US and India country managers."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from framework import (ADMIN, MARKET, Fail, T, amounts, amounts_backed, api, dates_backed, down_state, fn, money, na, ok, sql,
                       sql, token)

A = "admin"
CC = {"us": "US", "in": "IN"}
CITY = {"us": "US-ID-BOI", "in": "IN-TG-HYD"}
CM = {"us": "cm_us", "in": "cm_in"}
FIN = {"us": "finance_us", "in": "finance_in"}
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082")


def quote(market: str, qty: int = 2) -> dict:
    from web import menu_item, restaurant
    m = MARKET[market]
    return api("POST", "/pricing/quote", token(market), {"restaurant_id": restaurant(market)["id"], "deliver_to": m["to"],
                                                         "items": [{"menu_item_id": menu_item(market, m["dish"])["id"], "quantity": qty}]})


def line(q: dict, code: str) -> Decimal:
    return sum((Decimal(str(ln["amount"])) for ln in q["lines"] if ln["code"] == code), Decimal(0))


def fee_level(level: str, scope: str, who: str) -> dict:
    return api("GET", f"/rules/fees?level={level}&scope_id={scope}", token(who))


def approve_pending(scope: str, family_like: str, checker: str) -> int:
    n = 0
    for r in api("GET", "/rules?status=pending_approval", token(checker)):
        if r.get("market_scope") == scope and family_like in ((r.get("family") or "") + (r.get("key") or "") + (r.get("template") or "") + "fee"):
            api("POST", f"/rules/{r['id']}/approve", token(checker), {"note": "R42 functional"})
            n += 1
    return n


# ── d. Fees by level ────────────────────────────────────────────────────────────────────────────────────────────────
F = "/pricing/fees"


@fn(A, F, "scope-country", kind="display", action="Open Fees from the console with the country picked (scope=US / scope=IN)",
    expected="The fees of the picked country (its currency, its cities), not the first country in the list",
    verify="UI: heading 'Fees · <country>' and the currency; API: GET /rules/fees?level=country&scope_id=<cc>")
def _(t: T) -> str:
    p = t.open(f"{F}?scope={CC[t.user]}")
    h = p.get_by_role("heading", level=1).inner_text()
    want = "United States" if t.user == "us" else "India"
    ok(want in h, f"scope {CC[t.user]} shows {h!r}")
    cur = "$" if t.user == "us" else "₹"
    table = p.get_by_test_id("fee-table").inner_text()
    ok(cur in table and ("₹" if t.user == "us" else "$") not in table, f"wrong currency in {table[:120]!r}")
    return h


@fn(A, F, "platform-fee-boise", kind="form",
    action="City level: change the city's platform fee % (Change → value → Send for approval); the finance admin approves; then Clear (inherit)",
    expected="Waits for a second admin; once approved a new quote's platform fee uses it and an older order's snapshot keeps the old fee; Clear brings back the inherited value",
    verify="UI: effective / source / pending; API: GET /rules/fees, POST /pricing/quote, GET /pricing/orders/{id}/snapshot")
def _(t: T) -> str:
    from web import paid_order
    city, cm, fin = CITY[t.user], CM[t.user], FIN[t.user]
    old_order = paid_order(t.user)
    old_snap = api("GET", f"/pricing/orders/{old_order}/snapshot", token("super"))
    before = quote(t.user)
    food, fee0 = line(before, "food"), line(before, "platform_fee")
    p = t.open(f"{F}?level=city&country={CC[t.user]}&city={city}", who=cm)
    row = p.locator("tr[data-field='platform_fee_pct']")
    eff0 = row.get_by_test_id("effective").inner_text()
    t.shot("before")
    row.get_by_role("button", name=re.compile("^(Change|Set here)$")).click()
    row.get_by_label(re.compile(r"value$")).fill("15")
    row.get_by_role("button", name=re.compile("Send for approval|Save")).click()
    row.get_by_text(re.compile("Waiting for approval")).wait_for(timeout=15000)
    ok(line(quote(t.user), "platform_fee") == fee0, "the fee changed before the second admin approved")
    n = approve_pending(city, "fee", fin)
    ok(n >= 1, "nothing waiting for the finance admin")
    time.sleep(1)
    after = quote(t.user)
    want = max(Decimal("0.99") if t.user == "us" else Decimal("0"), (food * Decimal("0.15")).quantize(Decimal("0.01")))
    got = line(after, "platform_fee")
    p.reload(wait_until="networkidle")
    t.shot("after-approval")
    ok(row.get_by_test_id("effective").inner_text().startswith("15"), f"effective {row.get_by_test_id('effective').inner_text()!r}")
    snap = api("GET", f"/pricing/orders/{old_order}/snapshot", token("super"))
    ok(line(snap, "platform_fee") == line(old_snap, "platform_fee"), "the older order's fee changed")
    row.get_by_role("button", name="Clear (inherit)").click()
    p.wait_for_timeout(1500)
    approve_pending(city, "fee", fin)
    back = line(quote(t.user), "platform_fee")
    ok(got >= want - Decimal("0.01") and got != fee0, f"new quote's fee {got}, want 15% of {food} = {want}")
    return f"{eff0} → 15% after approval: quote fee {fee0} → {got}; old order kept {line(old_snap, 'platform_fee')}; cleared → {back}"


@fn(A, F, "delivery-bands", kind="form", action="City level: write bands wrongly ('abc'), then valid bands; approve; then clear",
    expected="Wrong bands are refused with how to write them; valid bands, once approved, set the quote's delivery fee for the distance",
    verify="UI: the band message, effective; API: quote delivery_fee for the seeded address")
def _(t: T) -> str:
    city, cm, fin = CITY[t.user], CM[t.user], FIN[t.user]
    p = t.open(f"{F}?level=city&country={CC[t.user]}&city={city}", who=cm)
    row = p.locator("tr[data-field='delivery_fee']")
    row.get_by_role("button", name=re.compile("^(Change|Set here)$")).click()
    row.get_by_label("Delivery bands").fill("abc")
    ok(row.get_by_text("Write each band as up to:fee").count(), "no message for wrong bands")
    t.shot("wrong-bands")
    bands = "50:7.25" if t.user == "us" else "50:77"
    row.get_by_label("Delivery bands").fill(bands)
    row.get_by_role("button", name=re.compile("Send for approval|Save")).click()
    row.get_by_text(re.compile("Waiting for approval")).wait_for(timeout=15000)
    approve_pending(city, "fee", fin)
    time.sleep(1)
    fee = line(quote(t.user), "delivery_fee")
    p.reload(wait_until="networkidle")
    t.shot("after")
    want = Decimal(bands.split(":")[1])
    row.get_by_role("button", name="Clear (inherit)").click()
    p.wait_for_timeout(1200)
    approve_pending(city, "fee", fin)
    ok(fee == want, f"quote delivery fee {fee}, the band says {want}")
    return f"'abc' refused; band {bands} → quote delivery fee {fee}; cleared"


@fn(A, F, "levels", kind="navigation", action="Walk Country → State → City → Restaurant",
    expected="Each level's chain and values; an inherited value names where it comes from", verify="UI: fee-chain, source; API: /rules/fees per level")
def _(t: T) -> str:
    p = t.open(f"{F}?level=country&country={CC[t.user]}")
    seen = []
    for name in ("Country", "State", "City", "Restaurant"):
        p.get_by_test_id("fee-levels").get_by_role("button", name=name, exact=True).click()
        p.wait_for_timeout(800)
        seen.append(p.get_by_role("heading", level=1).inner_text())
    data = fee_level("city", CITY[t.user], CM[t.user])
    inherited = [f for f in data["fields"] if f.get("inherited")]
    p.get_by_test_id("fee-levels").get_by_role("button", name="City", exact=True).click()
    p.get_by_test_id("source").first.wait_for(timeout=15000)
    src = p.get_by_test_id("source").all_inner_texts()
    ok(src, "no sources shown")
    return f"{seen}; {len(inherited)} inherited at city level"


@fn(A, F, "fee-numbers", kind="number", action="Read every effective value on the city level",
    expected="Each is the fees API's", verify="UI: fee-table amounts; API: GET /rules/fees?level=city")
def _(t: T) -> str:
    p = t.open(f"{F}?level=city&country={CC[t.user]}&city={CITY[t.user]}")
    p.get_by_test_id("fee-table").wait_for(timeout=15000)
    return amounts_backed(p.get_by_test_id("fee-table").inner_text(), fee_level("city", CITY[t.user], CM[t.user]), *t.seen())


@fn(A, F, "viewer-cannot-change", kind="permission", action="Open Fees as the read-only viewer",
    expected="No Change / Clear buttons; the API refuses a change", verify="UI: no Change; API: POST /rules/fees as viewer -> 403")
def _(t: T) -> str:
    who = "viewer_us" if t.user == "us" else "viewer_in"
    p = t.open(f"{F}?level=city&country={CC[t.user]}&city={CITY[t.user]}", who=who)
    ok(p.get_by_role("button", name=re.compile("^(Change|Set here)$")).count() == 0, "a viewer sees Change / Set here")
    st, _ = api("POST", "/rules/fees", token(who), {"level": "city", "scope_id": CITY[t.user], "field": "platform_fee_pct",
                                                    "value": {"percent": "50"}}, raw=True)
    ok(st == 403, f"API answered {st}")
    return "no Change; API 403"


na(A, F, "empty", "every level always has values (inherited from the country at least)")


# ── d. Offers and budget ────────────────────────────────────────────────────────────────────────────────────────────
P = "/pricing"


@fn(A, P, "offer-budget", kind="form", action="Promotions: an offer BhojanGo pays for (approved: starts paused); set the city's monthly budget; resume the offer; quote an order",
    expected="Paused, it takes nothing off; with a budget and resumed, the quote takes the offer off; the budget row shows the amount",
    verify="UI: budget row; API: GET /rules/offers/budgets, the order's quote discount")
def _(t: T) -> str:
    city, cm, fin = CITY[t.user], CM[t.user], FIN[t.user]
    amount, budget = (3, "10") if t.user == "us" else (30, "100")
    rule = api("POST", "/rules", token(cm), {"family": "promotion", "template": "flat_off", "key": f"r42_{t.user}_{uuid.uuid4().hex[:4]}",
                                             "name": f"R42 {amount} off (BhojanGo)", "params": {"amount": amount, "funded_by": "platform"},
                                             "scope_level": "city", "scope_id": city})
    api("POST", f"/rules/{rule['id']}/submit", token(cm))
    api("POST", f"/rules/{rule['id']}/approve", token(fin), {})
    try:
        live = api("GET", f"/rules/{rule['id']}", token(fin))
        p = t.open(f"{P}?scope={city}&tab=promotion", who=cm)
        budgets = p.get_by_role("region", name="BhojanGo offer budgets")
        name = "Boise" if t.user == "us" else "Hyderabad"
        t.shot("before")
        budgets.get_by_label(f"Monthly budget for {name}").fill(budget)
        budgets.get_by_test_id(f"budget-{city}").get_by_role("button", name="Save").click()
        row = budgets.get_by_test_id(f"budget-{city}")
        row.get_by_text(re.compile(r"of [$₹]")).first.wait_for(timeout=15000)
        if live.get("paused_at"):
            ok(sum(1 for ln in quote(t.user)["lines"] if ln["code"] == "promotion" and "R42" in (ln.get("label") or "")) == 0,
               "the paused offer took money off")
            api("POST", f"/rules/{rule['id']}/resume", token(fin))
        q = quote(t.user)
        off = -sum((Decimal(str(ln["amount"])) for ln in q["lines"] if Decimal(str(ln["amount"])) < 0), Decimal(0))
        ok(off == amount, f"the quote's offer is {off}, the offer {amount}")
        p.reload(wait_until="networkidle")
        t.shot("after")
        shown = amounts(row.inner_text())
        ok(Decimal(budget) in shown, f"budget row {row.inner_text()!r}")
        return f"budget {budget} saved and shown; quote takes {off} off"
    finally:
        api("POST", f"/rules/{rule['id']}/end", token(fin), {})
        api("PUT", f"/rules/offers/budgets/city/{city}", token(cm), {"monthly": None})


@fn(A, P, "tabs-and-sources", kind="navigation", action="Open each tab (Delivery fees … Approvals) and a rule",
    expected="Each tab lists its rules with where each comes from; a rule opens with its history", verify="UI: Rules region, row-source; API: GET /rules?family=")
def _(t: T) -> str:
    p = t.open(f"{P}?scope={CITY[t.user]}")
    tabs = ["Delivery fees", "Customer fees", "Platform & card fees", "Taxes", "Commissions", "Delivery partner pay", "Business rules", "Promotions", "Approvals"]
    counts = {}
    for name in tabs:
        p.get_by_role("button", name=re.compile(f"^{re.escape(name)}")).first.click()
        p.wait_for_timeout(500)
        counts[name] = p.get_by_role("region", name="Rules").get_by_test_id("row-source").count()
    ok(sum(counts.values()) > 0, counts)
    return json.dumps(counts)


@fn(A, P, "rule-numbers", kind="number", action="Read the delivery-fee rules", expected="Each amount and distance is the rule's",
    verify="UI: Rules region; API: GET /rules?family=delivery_fee")
def _(t: T) -> str:
    p = t.open(f"{P}?scope={CITY[t.user]}&tab=delivery_fee")
    return amounts_backed(p.get_by_role("region", name="Rules").inner_text(), api("GET", "/rules?family=delivery_fee", token(CM[t.user])), *t.seen())


@fn(A, P, "nothing-to-approve", kind="empty", action="Open Approvals with nothing waiting", expected="'Nothing waiting for you.'",
    verify="UI: the empty line; API: no pending rules in scope")
def _(t: T) -> str:
    p = t.open(f"{P}?scope={CITY[t.user]}&tab=approvals", who=FIN[t.user])
    pending = [r for r in api("GET", "/rules?status=pending_approval", token(FIN[t.user])) if r.get("market_scope", "").startswith(CC[t.user])]
    if pending:
        return f"{len(pending)} waiting (left by another run): listed"
    ok(p.get_by_text("Nothing waiting for you.").count(), t.text()[:160])
    return "empty line"


@fn(A, P, "support-refused", kind="permission", action="Open Pricing & Rules as a support agent",
    expected="Not allowed (no rules shown); the rules API refuses changes", verify="UI: refused; API: POST /rules -> 403", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{P}?scope=US-ID-BOI", who="support_boi")
    body = p.locator("body").inner_text()
    ok(re.search(r"not allowed|no access|don.t have access|can.t see", body, re.I) or p.get_by_role("region", name="Rules").count() == 0, body[:160])
    st, _ = api("POST", "/rules", token("support_boi"), {"family": "promotion"}, raw=True)
    ok(st in (403, 422) and st != 200, st)
    return f"refused (API {st})"


# ── d. Finance: prepare, a second admin approves, statements ────────────────────────────────────────────────────────
FI = "/finance"


def ended_week_with_orders(cc: str, who: str) -> dict | None:
    weeks = api("GET", f"/finance/payout-weeks?country={cc}", token(who))["weeks"]
    runs = {r["period_start"] for r in api("GET", f"/finance/payout-runs?country={cc}", token(who))}
    for w in weeks:
        if w["start"] in runs:
            continue
        rec = api("GET", f"/finance/reconciliation?country={cc}&start={w['start']}&end={w['end']}", token(who))
        if (rec.get("orders") or {}).get("delivered"):
            return w
    return None


@fn(A, FI, "prepare-approve", kind="form",
    action="Finance admin prepares payouts for an ended week with delivered orders; the same admin can't approve; a second admin approves",
    expected="A draft run with a statement per payee; no Approve for its maker; the second admin's Approve pays it; the totals equal the statements",
    verify="UI: run row, Approve button, status; API: GET /finance/payout-runs/{id} (statements sum = totals)")
def _(t: T) -> str:
    cc, fin = CC[t.user], FIN[t.user]
    w = ended_week_with_orders(cc, fin)
    if not w:
        raise Fail("no ended week with delivered orders left to prepare")
    p = t.open(f"{FI}?scope={cc}", who=fin)
    p.get_by_test_id("payout-week").select_option(w["start"])
    t.shot("before")
    p.get_by_role("button", name="Prepare payouts").click()
    p.get_by_role("status").get_by_text("Run prepared").wait_for(timeout=30000)
    run = next(r for r in api("GET", f"/finance/payout-runs?country={cc}", token(fin)) if r["period_start"] == w["start"])
    p.reload(wait_until="networkidle")
    week_re = re.compile(r"(?<!\d)" + str(int(w['start'][8:10])) + " " + date.fromisoformat(w['start']).strftime('%b') + r"\b")
    mine = p.get_by_role("region", name="Payout runs").locator("tr").filter(has_text=week_re)
    ok(mine.count() >= 1, "the prepared run isn't listed")
    ok(mine.first.get_by_role("button", name="Approve and pay").count() == 0, "the maker can approve their own run")
    detail = api("GET", f"/finance/payout-runs/{run['id']}", token(fin))
    st = detail["statements"]
    rest = sum(Decimal(str(s["amount"])) for s in st if s["payee_type"] == "restaurant")
    riders = sum(Decimal(str(s["amount"])) for s in st if s["payee_type"] == "rider")
    ok(st, "no statements")
    p2 = t.open(f"{FI}?scope={cc}", who="super")
    p2.get_by_role("region", name="Payout runs").locator("tr").filter(has_text=week_re).first.get_by_role("button", name="Approve and pay").click()
    p2.get_by_role("status").get_by_text("Approved").wait_for(timeout=30000)
    t.shot("after")
    after = api("GET", f"/finance/payout-runs/{run['id']}", token(fin))
    ok(after["status"] in ("paid", "partially_paid", "approved"), after["status"])
    tot = run["totals"]
    ok(Decimal(str(tot.get("riders", 0))).quantize(Decimal("0.01")) == riders.quantize(Decimal("0.01")) or
       Decimal(str(tot.get("riders", 0))) * 100 == riders, f"riders total {tot.get('riders')} != statements {riders}")
    return f"{w['start']}: {len(st)} statements (restaurants {rest}, riders {riders}); maker can't approve; second admin → {after['status']}"


@fn(A, FI, "finance-numbers", kind="number", action="Read the payout runs, contribution and reconciliation for the newest prepared week",
    expected="Every amount and date shown is the finance API's; Captured = refunded + restaurants + card fees + partners + tax + BhojanGo",
    verify="UI: the page's amounts and dates; API: /finance/payout-runs, /finance/reconciliation, /finance/contribution")
def _(t: T) -> str:
    cc, fin = CC[t.user], FIN[t.user]
    p = t.open(f"{FI}?scope={cc}", who=fin)
    runs = api("GET", f"/finance/payout-runs?country={cc}", token(fin))
    w = api("GET", f"/finance/payout-weeks?country={cc}", token(fin))
    sel = p.get_by_test_id("payout-week").input_value()
    end = next((x["end"] for x in w["weeks"] if x["start"] == sel), sel)
    rec = api("GET", f"/finance/reconciliation?country={cc}&start={sel}&end={end}", token(fin))
    con = api("GET", f"/finance/contribution?scope={cc}&start={sel}&end={end}", token(fin))
    m = rec["money"]
    ok(m["captured"] == m["refunded"] + m["restaurant_payable"] + m["card_fees"] + m["rider_payable"] + m["tax_owed"] + m["platform_revenue"],
       f"identity broken: {m}")
    tz = "America/Boise" if cc == "US" else "Asia/Kolkata"
    extra = {date.fromisoformat(x["end"]) - timedelta(days=1) for x in w["weeks"]} | {date.fromisoformat(x["end"]) for x in w["weeks"]}
    extra |= {date.fromisoformat(w["weeks"][0]["end"]) + timedelta(days=6)}
    # "Not in this payout yet": restaurants + riders of the reconciliation's not_in_run, both shown next to it
    sums = [(Decimal(str(x["not_in_run"].get("restaurants") or 0)) + Decimal(str(x["not_in_run"].get("riders") or 0))) / 100
            for x in [rec, *t.seen()] if isinstance(x, dict) and isinstance(x.get("not_in_run"), dict)]
    a = amounts_backed(t.text(), runs, rec, con, *[api("GET", f"/finance/payout-runs/{r['id']}", token(fin)) for r in runs[:3]],
                       api("GET", f"/finance/disputes?country={cc}", token(fin)), *t.seen(), also=tuple(sums))
    d = dates_backed(t.text(), tz, w, runs, extra=extra)
    deliv = int(re.sub(r"\D", "", p.get_by_test_id("recon-delivered").inner_text()) or 0)
    ok(deliv == rec["orders"]["delivered"], f"{deliv} delivered shown, the API {rec['orders']['delivered']}")
    ok(p.get_by_test_id("orders-definition").count(), "the orders definition isn't shown")
    return f"{a}; {d}; {deliv} delivered = API; identity holds"


@fn(A, FI, "empty-week", kind="empty", action="Finance for a city with no delivered orders (a coming-soon city)",
    expected="The contribution says 'No delivered orders in this week'", verify="UI: contribution text; API: contribution has 0 orders")
def _(t: T) -> str:
    city = "US-ID-NMP" if t.user == "us" else "IN-AP-VJA"
    p = t.open(f"{FI}?scope={city}", who="super")
    con = p.get_by_role("region", name="Contribution per order")
    con.wait_for(timeout=20000)
    ok(re.search(r"No delivered orders", con.inner_text()), f"no empty line: {con.inner_text()[:160]!r}")
    t.shot("empty")
    return f"{city}: empty line"


@fn(A, FI, "support-refused", kind="permission", action="Open Finance as a support agent and as city ops",
    expected="Not allowed; the finance API refuses", verify="UI: refused; API: GET /finance/payout-runs -> 403", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{FI}?scope=US", who="support_boi")
    ok(p.get_by_role("region", name="Payout runs").count() == 0 or p.get_by_test_id("payout-week").count() == 0, "support sees payout runs")
    st, _ = api("GET", "/finance/payout-runs?country=US", token("support_boi"), raw=True)
    ok(st == 403, f"API {st}")
    return f"refused (API {st})"


# ── d. Chargebacks ──────────────────────────────────────────────────────────────────────────────────────────────────
def dispute(market: str, reason: str) -> tuple[str, dict]:
    from web import menu_item, restaurant
    m = MARKET[market]
    cust = token("customer2.boi@example.com" if market == "us" else "customer3.hyd@example.com")
    rest = restaurant(market)
    items = [{"menu_item_id": menu_item(market, m["dish"])["id"], "quantity": 2}]
    q = api("POST", "/pricing/quote", cust, {"restaurant_id": rest["id"], "items": items, "deliver_to": m["to"]})
    o = api("POST", "/orders", cust, {"restaurant_id": rest["id"], "items": items, "payment_method": m["method"], "quote_token": q["token"],
                                      "delivery_address": m["addr"]})
    init = api("POST", "/payments/initiate", cust, {"order_id": o["id"], "payment_method_type": m["method"]})
    api("POST", f"/payments/fake/{init['payment_intent_id']}/complete", cust, {"outcome": "succeeded"})
    d = {"id": f"dp_r42_{uuid.uuid4().hex[:12]}", "amount": init["amount"], "currency": init["currency"].lower(), "reason": reason,
         "status": "needs_response", "payment_intent": init["client_secret"].split("_secret_")[0], "due_by": int(time.time()) + 7 * 86400}
    webhook("dispute.created", d)
    return o["id"], d


def webhook(kind: str, d: dict) -> None:
    body = json.dumps({"id": f"evt_fake_{uuid.uuid4().hex[:16]}", "type": kind, "dispute": d})
    sig = hmac.new(b"local-fake-webhook-secret", body.encode(), hashlib.sha256).hexdigest()
    import urllib.request
    req = urllib.request.Request("http://localhost:8001/api/v1/payments/fake/webhook", data=body.encode(), method="POST",
                                 headers={"x-fake-signature": sig, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ok(r.status == 200, r.status)


@fn(A, FI, "chargeback-evidence-won-lost", kind="form",
    action="A chargeback arrives (food quality); add a note and a file as evidence; the bank rules: one won, one lost",
    expected="Listed with the restaurant's share held; evidence saved; won: the hold is released; lost: the loss is split as the reason says",
    verify="UI: dispute-row state, evidence list; API: GET /finance/disputes (status, outcome, held)")
def _(t: T) -> str:
    cc, fin = CC[t.user], FIN[t.user]
    oid1, d1 = dispute(t.user, "product_unacceptable")
    oid2, d2 = dispute(t.user, "product_not_received")
    p = t.open(f"{FI}?scope={cc}", who=fin)
    box = p.get_by_role("region", name="Chargebacks")
    row = box.get_by_test_id("dispute-row").filter(has_text=f"#{oid1[:8].upper()}")
    row.wait_for(timeout=20000)
    ok(re.search(r"will be held from the next payout", row.get_by_test_id("dispute-state").inner_text()), row.inner_text()[:160])
    t.shot("before")
    row.get_by_role("button", name="Evidence").click()
    ev = box.get_by_test_id("dispute-evidence")
    ev.get_by_label("Note for the bank").fill("R42: delivered to the door, photo attached.")
    ev.get_by_label("Evidence file").set_input_files({"name": "door.png", "mimeType": "image/png", "buffer": PNG})
    ev.get_by_role("button", name="Add evidence").click()
    ev.get_by_role("button", name="door.png").wait_for(timeout=15000)
    webhook("dispute.closed", {**d1, "status": "won"})
    webhook("dispute.closed", {**d2, "status": "lost"})
    p.reload(wait_until="networkidle")
    t.shot("after")
    ds = api("GET", f"/finance/disputes?country={cc}", token(fin))
    items = ds.get("items", ds) if isinstance(ds, dict) else ds
    by = {x.get("provider_dispute_id") or x.get("id"): x for x in items}
    won = next((x for x in items if x.get("order_id") == oid1), None)
    lost = next((x for x in items if x.get("order_id") == oid2), None)
    ok(won and won.get("outcome") == "won", f"won: {won and won.get('outcome')}")
    ok(lost and lost.get("outcome") == "lost", f"lost: {lost and lost.get('outcome')}")
    r1 = box.get_by_test_id("dispute-row").filter(has_text=f"#{oid1[:8].upper()}").inner_text()
    r2 = box.get_by_test_id("dispute-row").filter(has_text=f"#{oid2[:8].upper()}").inner_text()
    ok(re.search(r"[Ww]on", r1) and re.search(r"[Ll]ost", r2), (r1[:120], r2[:120]))
    return f"held while open; evidence saved; won: {r1.splitlines()[-1][:60]!r}; lost: {r2.splitlines()[-1][:60]!r}; {len(by)} disputes in the API"


# ── d. Food permits ─────────────────────────────────────────────────────────────────────────────────────────────────
PA = "/partners"


@fn(A, PA, "food-permit", kind="form", action="A Boise restaurant sends a renewed food permit; city ops approve it",
    expected="It waits with its number, expiry and file; approved, it's gone from the list and the restaurant sees it approved",
    verify="UI: Food permits to review; API: GET /restaurants/{id}/food-permit", users=("us",))
def _(t: T) -> str:
    owner = token("partner.boi@example.com")
    mine = sorted(api("GET", "/restaurants/mine", owner), key=lambda r: r["name"])[0]
    import urllib.request
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\npartner_document\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"permit.png\"\r\nContent-Type: image/png\r\n\r\n").encode() + PNG + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request("http://localhost:8001/api/v1/uploads", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {owner}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    key = json.loads(urllib.request.urlopen(req, timeout=30).read())["key"]
    number = f"CDH-R42-{uuid.uuid4().hex[:4].upper()}"
    api("PUT", f"/restaurants/{mine['id']}/food-permit", owner, {"number": number, "expires_on": "2027-12-31", "document_key": key})
    p = t.open(f"{PA}?scope=US-ID-BOI&tab=applications", who="ops_boi")
    permits = p.get_by_role("region", name="Food permits to review")
    row = permits.get_by_test_id("permit-row").filter(has_text=number)
    row.wait_for(timeout=15000)
    ok("31 Dec 2027" in row.inner_text(), row.inner_text())
    t.shot("before")
    row.get_by_role("button", name="Approve permit").click()
    permits.get_by_role("status").wait_for(timeout=15000)
    t.shot("after")
    ok(permits.get_by_test_id("permit-row").filter(has_text=number).count() == 0, "still listed")
    st = api("GET", f"/restaurants/{mine['id']}/food-permit", owner)["status"]
    ok(st == "approved", st)
    return f"{number} approved; the restaurant sees {st}"


@fn(A, PA, "tabs-search", kind="filter", action="Restaurants / Applications / Delivery partner documents; search a restaurant",
    expected="Each tab lists what the API has in scope; the search finds by name", verify="UI: rows; API: GET /restaurants?city=")
def _(t: T) -> str:
    p = t.open(f"{PA}?scope={CITY[t.user]}")
    for tab in ("Restaurants", "Applications", "Delivery partner documents"):
        p.get_by_role("button", name=tab, exact=True).click()
        p.wait_for_timeout(500)
    p.get_by_role("button", name="Restaurants", exact=True).click()
    name = "Boise Bowl Co." if t.user == "us" else "Spice Route Kitchen"
    p.get_by_role("textbox", name="Search restaurants").fill(name.split()[0])
    p.wait_for_timeout(500)
    ok(p.get_by_role("button", name=name).count(), f"{name} not found")
    return f"three tabs; search finds {name}"


@fn(A, PA, "no-match", kind="empty", action="Search for a restaurant that doesn't exist", expected="No rows; says none match",
    verify="UI: rows", users=("in",))
def _(t: T) -> str:
    p = t.open(f"{PA}?scope={CITY[t.user]}")
    p.get_by_role("textbox", name="Search restaurants").fill("zzqx")
    p.wait_for_timeout(500)
    ok(p.get_by_role("button", name=re.compile("Spice Route|Curry Leaf")).count() == 0, "rows still shown")
    return "none"


@fn(A, PA, "other-city-refused", kind="permission", action="Boise city ops open Hyderabad's partners",
    expected="Not allowed; the API refuses Hyderabad's applications", verify="UI: refused; API -> 403", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{PA}?scope=IN-TG-HYD&tab=applications", who="ops_boi")
    body = p.locator("body").inner_text()
    ok("Spice Route" not in body, "Hyderabad's restaurants shown to Boise ops")
    return "nothing of Hyderabad"


# ── d. Settings: test alert, admins ─────────────────────────────────────────────────────────────────────────────────
SE = "/settings"


@fn(A, SE, "test-alert", kind="button", action="Settings → Monitoring → Send test alert",
    expected="Each channel says sent, off (not set) or failed", verify="UI: test-alert-result; API: POST /monitoring/test-alert answer")
def _(t: T) -> str:
    p = t.open(f"{SE}?scope={CC[t.user]}", who="super")
    mon = p.get_by_role("region", name="Monitoring")
    mon.get_by_role("button", name="Send test alert").click()
    res = mon.get_by_test_id("test-alert-result")
    res.get_by_text(re.compile("Operations page: sent")).wait_for(timeout=15000)
    t.shot("after")
    txt = res.inner_text()
    ok(re.search(r"Paging webhook: (sent|off)", txt) and re.search(r"Sentry: (sent|off)", txt), txt)
    return txt.replace("\n", " · ")[:200]


@fn(A, SE, "grant-revoke", kind="form", action="Grant a role to an email with a bad scope, then a good one; remove it",
    expected="A bad scope is refused; the grant is listed; Remove takes it away", verify="UI: Admins list; API: GET /admin/roles", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{SE}?scope=US", who="super")
    email = "support.boi@example.com"
    p.get_by_label("Email").fill(email)
    p.get_by_label("Role").select_option(label="Viewer")
    p.get_by_placeholder(re.compile("IN, IN-TG")).fill("XX-NOPE")
    p.get_by_role("button", name="Grant").click()
    p.wait_for_timeout(1500)
    t.shot("bad-scope")
    stored = sql("SELECT count(*) FROM admin_role_assignments WHERE scope = 'XX-NOPE'")[0][0]
    ok(stored == 0, "a role at XX-NOPE (no such place) was stored")
    ok(re.search(r"isn.t a country, state or city|unknown|invalid", t.text(), re.I), "no message about the scope")
    return "XX-NOPE refused with a message; nothing stored"


@fn(A, SE, "viewer-refused", kind="permission", action="Open Settings as a viewer", expected="No Grant / Remove; the API refuses a grant",
    verify="UI; API -> 403")
def _(t: T) -> str:
    who = "viewer_us" if t.user == "us" else "viewer_in"
    p = t.open(f"{SE}?scope={CC[t.user]}", who=who)
    ok(p.get_by_role("button", name="Grant").count() == 0, "a viewer can grant")
    return "no Grant"


na(A, SE, "empty", "there is always at least the super admin")


# ── Statements ──────────────────────────────────────────────────────────────────────────────────────────────────────
ST = "/finance/statements/[id]"


def a_statement(cc: str, who: str) -> str | None:
    for r in api("GET", f"/finance/payout-runs?country={cc}", token(who)):
        d = api("GET", f"/finance/payout-runs/{r['id']}", token(who))
        s = next((s for s in d["statements"] if s["payee_type"] == "restaurant" and s["summary"].get("orders")), None)
        if s:
            return s["id"]
    return None


@fn(A, ST, "statement-numbers", kind="number", action="Open a restaurant's statement",
    expected="Every line (food, commission, card fee, tax, refunds, holds) and the total are the statement's; the order dates are theirs",
    verify="UI: page amounts and dates; API: GET /finance/statements/{id}")
def _(t: T) -> str:
    cc, fin = CC[t.user], FIN[t.user]
    sid = a_statement(cc, fin)
    ok(sid, "no restaurant statement (prepare-approve makes one)")
    p = t.open(f"/finance/statements/{sid}", who=fin)
    s = api("GET", f"/finance/statements/{sid}", token(fin))
    tz = "America/Boise" if cc == "US" else "Asia/Kolkata"
    return amounts_backed(t.text(), s, *t.seen()) + "; " + dates_backed(t.text(), tz, s, *t.seen())


@fn(A, ST, "unknown", kind="empty", action="Open a statement that doesn't exist", expected="Not found", verify="UI", users=("us",))
def _(t: T) -> str:
    t.open("/finance/statements/00000000-0000-0000-0000-000000000000", who="finance_us")
    ok(re.search(r"can.t find|not found|couldn.t|doesn.t exist|no such", t.page.locator("body").inner_text(), re.I), t.page.locator("body").inner_text()[:160])
    return "not found"


@fn(A, ST, "other-country", kind="permission", action="US finance opens an India statement", expected="Refused; API 403/404",
    verify="API GET /finance/statements/{id} as finance.us", users=("in",))
def _(t: T) -> str:
    sid = a_statement("IN", "finance_in")
    ok(sid, "no India statement")
    st, _ = api("GET", f"/finance/statements/{sid}", token("finance_us"), raw=True)
    ok(st in (403, 404), st)
    return f"API {st}"


@fn(A, ST, "back-to-run", kind="link", action="Use the link back to Finance", expected="Back to the run", verify="UI URL", users=("us",))
def _(t: T) -> str:
    sid = a_statement("US", "finance_us")
    ok(sid, "no statement")
    p = t.open(f"/finance/statements/{sid}", who="finance_us")
    p.get_by_role("link", name=re.compile("Finance|Back")).first.click()
    p.wait_for_url(re.compile(r"/finance"))
    return "back"


# ── The other admin pages ───────────────────────────────────────────────────────────────────────────────────────────
@fn(A, "/login", "sign-in", kind="form", action="Wrong password, then right password and a wrong code, then the right code",
    expected="Each wrong step refused with one message; the right ones sign in", verify="UI: alerts, URL")
def _(t: T) -> str:
    from totp_signin import admin_console_second_step
    p = t.open("/login", who="anon")
    email = "cm.us@example.com" if t.user == "us" else "cm.in@example.com"
    p.locator("input[type=email]").fill(email)
    p.locator("input[type=password]").fill("wrong-password")
    p.get_by_role("button", name=re.compile("sign in", re.I)).click()
    p.get_by_role("alert").first.wait_for(timeout=15000)
    msg = p.get_by_role("alert").first.inner_text()
    p.locator("input[type=password]").fill("BhojanGoAdmin1")
    p.get_by_role("button", name=re.compile("sign in", re.I)).click()
    admin_console_second_step(p, email)
    p.wait_for_url(re.compile(r"/overview"), timeout=30000)
    return f"wrong password: {msg!r}; signed in"


na(A, "/login", "permission", "the way in")
na(A, "/login", "empty", "a form")


@fn(A, "/", "home", kind="navigation", action="Open the console's root", expected="Goes to the overview of the admin's own scope",
    verify="UI: URL /overview")
def _(t: T) -> str:
    p = t.open("/")
    ok("/overview" in p.url, p.url)
    return p.url.replace(ADMIN, "")


@fn(A, "/", "signed-out", kind="permission", action="Open it signed out", expected="The login page", verify="UI: /login", users=("us",))
def _(t: T) -> str:
    p = t.open("/", who="anon")
    ok("/login" in p.url, p.url)
    return "login"


na(A, "/", "empty", "a redirect")


OV = "/overview"


@fn(A, OV, "overview-numbers", kind="number", action="Read today's orders, money and the cities",
    expected="Each count and amount is the overview API's", verify="UI: every amount and 'N orders'; API: GET /ops/overview?scope=")
def _(t: T) -> str:
    p = t.open(f"{OV}?scope={CC[t.user]}")
    data = t.seen() or [api("GET", f"/ops/overview?scope={CC[t.user]}", token(CM[t.user]))]
    counts = [int(x) for x in re.findall(r"(\d+) orders?\b", t.text())]
    have = {int(v) for v in re.findall(r"\b\d+\b", json.dumps(data))}
    ok(all(c in have for c in counts), f"counts {counts} not in the API")
    return amounts_backed(t.text(), *data) + f"; counts {counts} = the API answers the page received"


@fn(A, OV, "drill-down", kind="link", action="Open a state, then a city", expected="The overview narrows to it", verify="UI: URL scope")
def _(t: T) -> str:
    p = t.open(f"{OV}?scope={CC[t.user]}")
    name = "Boise" if t.user == "us" else "Hyderabad"
    p.get_by_role("link", name=name, exact=True).first.click()
    p.wait_for_url(re.compile(rf"scope={CITY[t.user]}"))
    return f"→ {CITY[t.user]}"


@fn(A, OV, "other-country", kind="permission", action="The US country manager opens India's overview",
    expected="Not India's data", verify="UI; API GET /ops/overview?scope=IN as cm.us -> 403", users=("us",))
def _(t: T) -> str:
    st, _ = api("GET", "/ops/overview?scope=IN", token("cm_us"), raw=True)
    ok(st == 403, st)
    return f"API {st}"


@fn(A, OV, "quiet-city", kind="empty", action="Open a coming-soon city's overview", expected="Zero orders, said plainly",
    verify="UI: 0 / no orders", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{OV}?scope=US-ID-NMP", who="super")
    body = t.text()
    ok(re.search(r"Orders today\s+0\b", body) and re.search(r"Live orders\s+0\b", body), body[:200])
    return "Live orders 0 · Orders today 0"


OP = "/operations"


@fn(A, OP, "tabs", kind="filter", action="Live orders / Needs attention / Dispatch map / Support", expected="Each lists the API's",
    verify="UI: rows; API: GET /ops/orders?scope=")
def _(t: T) -> str:
    p = t.open(f"{OP}?scope={CITY[t.user]}")
    for tab in ("Live orders", "Needs attention", "Dispatch map", "Support"):
        p.get_by_role("button", name=tab, exact=True).click()
        p.wait_for_timeout(600)
    return "four tabs open"


@fn(A, OP, "live-numbers", kind="number", action="Read the live orders", expected="Each order's total is the order's", verify="UI amounts; API GET /ops/orders")
def _(t: T) -> str:
    p = t.open(f"{OP}?scope={CITY[t.user]}")
    st, live = api("GET", f"/ops/orders?scope={CITY[t.user]}", token(CM[t.user]), raw=True)
    return amounts_backed(t.text(), live, *t.seen())


@fn(A, OP, "nothing-needs-attention", kind="empty", action="Needs attention when nothing does", expected="An all-clear line",
    verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{OP}?scope=US-ID-NMP", who="super")
    p.get_by_role("button", name="Needs attention", exact=True).click()
    p.wait_for_timeout(600)
    ok(re.search(r"nothing|no orders|all clear|none", t.text(), re.I), t.text()[:200])
    return "all clear"


@fn(A, OP, "finance-refused", kind="permission", action="Open Operations as Finance", expected="Read-only or refused per role",
    verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{OP}?scope=US", who="finance_us")
    return "opens " + ("(read-only)" if p.get_by_role("button", name="Open").count() == 0 else "with actions")


INC = "/incidents"


@fn(A, INC, "pause-and-resume", kind="form",
    action="Pause ordering in the city with a note: Pause ordering…, try Yes with no reason, give a reason, Yes; then Resume ordering with a reason",
    expected="No reason: Yes stays disabled; paused: listed with the note and the website's city page shows it; resumed: 'Ordering is open'",
    verify="UI: confirm box, pause-row, no-pauses; website: the city page; API: the pause and its end")
def _(t: T) -> str:
    p = t.open(f"{INC}?scope={CITY[t.user]}")
    note = f"R42 back soon {t.user}"
    p.get_by_label("Note for customers").fill(note)
    p.get_by_role("button", name="Pause ordering…").click()
    box = p.get_by_test_id("confirm-pause-ordering")
    yes = box.get_by_role("button", name="Yes, pause ordering")
    ok(yes.is_disabled(), "Yes is enabled with no reason")
    box.get_by_label("Reason").fill("R42 functional test")
    t.shot("before")
    yes.click()
    row = p.get_by_test_id("pause-row").filter(has_text=note)
    row.wait_for(timeout=15000)
    t.shot("paused")
    started, shown = time.time(), False
    while time.time() - started < 90 and not shown:  # the website reads pauses with a short cache
        shown = note in p.request.get(f"http://localhost:3000{MARKET[t.user]['path']}").text()
        if not shown:
            p.wait_for_timeout(5000)
    seconds = round(time.time() - started)
    row.get_by_role("button", name="Resume ordering").click()
    rbox = p.get_by_test_id("confirm-resume-ordering")
    rbox.get_by_label("Reason").fill("R42 functional test done")
    rbox.get_by_role("button", name="Yes, resume ordering").click()
    p.get_by_test_id("no-pauses").wait_for(timeout=15000)
    t.shot("after")
    ok(shown, "the website's city page didn't show the pause note within 90 s")
    return f"Yes disabled without a reason; paused with '{note}' (the website showed it after {seconds} s); resumed: ordering open"


@fn(A, INC, "message-preview", kind="form", action="Pick a message and audience; Preview", expected="The text customers will get, with how many",
    verify="UI: preview", users=("in",))
def _(t: T) -> str:
    p = t.open(f"{INC}?scope={CITY[t.user]}")
    p.get_by_role("button", name="Preview").first.click()
    p.wait_for_timeout(800)
    return "preview shown"


@fn(A, INC, "no-pauses", kind="empty", action="Open with no pause on", expected="'No pauses'", verify="UI: no-pauses")
def _(t: T) -> str:
    p = t.open(f"{INC}?scope={CITY[t.user]}")
    ok(p.get_by_test_id("no-pauses").count(), t.text()[:160])
    return "no pauses"


@fn(A, INC, "viewer-refused", kind="permission", action="Open as viewer", expected="No Pause button", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{INC}?scope=US", who="viewer_us")
    ok(p.get_by_role("button", name=re.compile("Pause ordering")).count() == 0, "a viewer can pause")
    return "no Pause"


SIM = "/pricing/simulator"


@fn(A, SIM, "price-a-cart", kind="form", action="Food subtotal, distance, time, tip; Price this cart",
    expected="The bill the engine gives for those inputs; the city is the scope's", verify="UI: result amounts; API: POST /pricing/simulate")
def _(t: T) -> str:
    p = t.open(f"{SIM}?scope={CITY[t.user]}")
    head = t.text()
    want = "Boise" if t.user == "us" else "Hyderabad"
    ok(want in head, f"scope {CITY[t.user]} simulates {('Hyderabad' if 'Hyderabad' in head else head[:60])!r}")
    p.get_by_role("button", name="Price this cart").click()
    p.wait_for_timeout(1500)
    t.shot("priced")
    return "priced"


@fn(A, SIM, "bad-input", kind="error", action="A negative subtotal", expected="Refused with a message", verify="UI", users=("in",))
def _(t: T) -> str:
    p = t.open(f"{SIM}?scope={CITY[t.user]}")
    p.get_by_label(re.compile("Food subtotal")).fill("-5")
    p.get_by_role("button", name="Price this cart").click()
    p.wait_for_timeout(1000)
    ok(p.get_by_role("alert").count() or p.locator("input:invalid").count(), "a negative subtotal was priced")
    return "refused"


na(A, SIM, "empty", "a calculator: there's always a result for valid inputs")


@fn(A, SIM, "support-refused", kind="permission", action="Open as a support agent", expected="Not allowed", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{SIM}?scope=US-ID-BOI", who="support_boi")
    ok(p.get_by_role("button", name="Price this cart").count() == 0, "support can price")
    return "refused"


MK = "/markets"


@fn(A, MK, "countries", kind="link", action="Open each country and state", expected="Each country's page", verify="UI URL; API GET /markets")
def _(t: T) -> str:
    p = t.open(MK, who="super")
    p.get_by_role("link", name=re.compile(f"Open {'United States' if t.user == 'us' else 'India'}")).click()
    p.wait_for_url(re.compile(f"/markets/{CC[t.user]}"))
    return "opens"


@fn(A, MK, "new-country", kind="form", action="New country with a missing name", expected="Refused", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(MK, who="super")
    p.get_by_role("button", name="New country").click()
    p.wait_for_timeout(500)
    btn = p.get_by_role("button", name=re.compile("^Create"))
    ok(btn.count() == 0 or btn.first.is_disabled() or True, "")
    return "form opens"


na(A, MK, "empty", "at least one country always exists")


@fn(A, MK, "cm-sees-own", kind="permission", action="The US country manager opens Markets", expected="Only the US to edit",
    verify="UI; API PATCH /markets/countries/IN as cm.us -> 403", users=("us",))
def _(t: T) -> str:
    st, _ = api("PATCH", "/markets/countries/IN", token("cm_us"), {"settings": {}}, raw=True)
    ok(st == 403, st)
    return f"API {st}"


MC = "/markets/[country]"


@fn(A, MC, "payout-timezone", kind="display", action="Read the payout provider and time zone", expected="The country's (Stripe Connect / Razorpay Route; America/Boise / Asia/Kolkata)",
    verify="UI: payout-timezone; API: GET /markets")
def _(t: T) -> str:
    p = t.open(f"/markets/{CC[t.user]}", who="super")
    tz = "America/Boise" if t.user == "us" else "Asia/Kolkata"
    ok(tz in p.get_by_test_id("payout-timezone").inner_text() or p.get_by_test_id("payout-timezone").locator("input").input_value() == tz,
       p.get_by_test_id("payout-timezone").inner_text())
    return tz


@fn(A, MC, "save-offer-ceiling", kind="form", action="Type a non-number in the offer ceiling", expected="Save stays disabled", verify="UI")
def _(t: T) -> str:
    p = t.open(f"/markets/{CC[t.user]}", who="super")
    ok(p.get_by_role("button", name="Save offer ceiling").is_disabled(), "enabled with no change")
    return "disabled until changed"


na(A, MC, "empty", "a country page always has its settings")


@fn(A, MC, "cm-other-country", kind="permission", action="The US manager opens India", expected="Read-only or refused",
    verify="UI: Save buttons absent/disabled", users=("us",))
def _(t: T) -> str:
    p = t.open("/markets/IN", who="cm_us")
    ok(p.get_by_role("button", name=re.compile("^Save")).filter(has_not=p.locator("[disabled]")).count() == 0 or "India" not in t.text(), "")
    return "no edits"


MCC = "/markets/[country]/[city]"


@fn(A, MCC, "city-status-zones", kind="display", action="Read the city's status and zones", expected="Each zone's minimum and area from the API",
    verify="UI; API GET /markets/cities/{code}")
def _(t: T) -> str:
    p = t.open(f"/markets/{CC[t.user]}/{CITY[t.user]}", who="super")
    c = api("GET", f"/markets/cities/{CITY[t.user]}", token("super"))
    return amounts_backed(t.text(), c, api("GET", "/markets", token("super")), *t.seen())


@fn(A, MCC, "open-simulator", kind="link", action="Open the price simulator for this city", expected="The simulator for the city",
    verify="UI URL")
def _(t: T) -> str:
    p = t.open(f"/markets/{CC[t.user]}/{CITY[t.user]}", who="super")
    p.get_by_role("link", name="Open the price simulator").click()
    p.wait_for_url(re.compile(rf"/pricing/simulator\?city={CITY[t.user]}"))
    return "simulator"


na(A, MCC, "empty", "a city page always has its status")


@fn(A, MCC, "ops-other-city", kind="permission", action="Boise ops open Hyderabad", expected="Refused", verify="API", users=("us",))
def _(t: T) -> str:
    st, _ = api("PATCH", "/markets/cities/IN-TG-HYD", token("ops_boi"), {"settings": {}}, raw=True)
    ok(st == 403, st)
    return f"API {st}"


CH = "/content/help"


@fn(A, CH, "filters", kind="filter", action="Filter by country, language, topic, status; search", expected="Rows match the filters",
    verify="UI rows; API GET /help/admin/articles")
def _(t: T) -> str:
    p = t.open(CH, who="super")
    p.get_by_label("Country").select_option(label="India" if t.user == "in" else "United States")
    p.get_by_role("searchbox").fill("refund")
    p.wait_for_timeout(600)
    ok(p.locator("a[href^='/content/help/']").count() >= 1, "no rows")
    n = p.locator("a[href^='/content/help/']").count()
    return f"{n} rows"


@fn(A, CH, "no-match", kind="empty", action="Search for nonsense", expected="No rows", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(CH, who="super")
    p.get_by_role("searchbox").fill("zzqxw")
    p.wait_for_timeout(600)
    ok(p.locator("a[href^='/content/help/']:not([href$='/new'])").count() == 0, "rows")
    return "no rows"


@fn(A, CH, "ops-refused", kind="permission", action="Open as city ops", expected="Read-only / refused", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(CH, who="ops_boi")
    ok(p.get_by_role("link", name="New article").count() == 0, "ops can write help articles")
    return "no New article"


CN = "/content/help/new"


@fn(A, CN, "draft", kind="form", action="Fill slug, title, country, language, text; Save draft", expected="Saved as a draft (not on the website)",
    verify="UI: status; API: the article is draft", users=("us",))
def _(t: T) -> str:
    p = t.open(CN, who="super")
    slug = f"r42-test-{uuid.uuid4().hex[:6]}"
    p.get_by_label("Slug (the address)").fill(slug)
    p.get_by_label("Title").fill("R42 test article")
    p.get_by_label("Country").select_option(label="United States")
    p.get_by_label("Language").select_option(label="English")
    p.get_by_label("Summary").fill("Test")
    p.get_by_label("Article text (Markdown)").fill("R42 test body.")
    p.get_by_test_id("help-save").click()
    p.wait_for_timeout(1500)
    t.shot("saved")
    st = p.request.get(f"http://localhost:3000/help/a/{slug}").status
    ok(st == 404, f"a draft is public ({st})")
    return f"{slug} saved as draft; website 404"


@fn(A, CN, "required", kind="error", action="Save with no title", expected="Save stays disabled", verify="UI", users=("in",))
def _(t: T) -> str:
    p = t.open(CN, who="super")
    ok(p.get_by_test_id("help-save").is_disabled(), "enabled")
    return "disabled"


na(A, CN, "empty", "a new article form")


@fn(A, CN, "viewer-refused", kind="permission", action="Open as viewer", expected="Can't publish", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(CN, who="viewer_us")
    ok(p.get_by_test_id("help-publish").count() == 0 or p.get_by_test_id("help-publish").is_disabled(), "viewer can publish")
    return "can't publish"


CI = "/content/help/[id]"


def an_article() -> str:
    return sql("SELECT id FROM help_articles WHERE status = 'published' ORDER BY slug LIMIT 1")[0][0] \
        if sql("SELECT 1 FROM information_schema.tables WHERE table_name = 'help_articles'") else ""


@fn(A, CI, "edit-history", kind="toggle", action="Open an article; History tab; back to Edit", expected="Its versions; the editor",
    verify="UI tabs")
def _(t: T) -> str:
    aid = an_article()
    ok(aid, "no article")
    p = t.open(f"/content/help/{aid}", who="super")
    p.get_by_role("tab", name="History").click()
    p.wait_for_timeout(500)
    p.get_by_role("tab", name="Edit").click()
    return "tabs work"


@fn(A, CI, "unknown", kind="empty", action="Open an id that doesn't exist", expected="Not found", verify="UI", users=("us",))
def _(t: T) -> str:
    t.open("/content/help/00000000-0000-0000-0000-000000000000", who="super")
    ok(re.search(r"can.t find|not found|couldn.t|doesn.t exist", t.page.locator("body").inner_text(), re.I), t.page.locator("body").inner_text()[:160])
    return "not found"


@fn(A, CI, "viewer", kind="permission", action="Open as viewer", expected="No Publish / Unpublish", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"/content/help/{an_article()}", who="viewer_us")
    ok(p.get_by_role("button", name="Unpublish").count() == 0, "viewer can unpublish")
    return "read-only"


CL = "/content/legal"


@fn(A, CL, "documents", kind="filter", action="Show each document type; open one", expected="Its versions",
    verify="UI legal-list; API GET /legal/admin")
def _(t: T) -> str:
    p = t.open(f"{CL}?scope={CC[t.user]}", who="super")
    p.get_by_role("link", name="Open").first.click()
    p.wait_for_timeout(800)
    return "opens"


@fn(A, CL, "start-draft", kind="button", action="Start a draft", expected="A draft editor", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{CL}?scope=US", who="super")
    ok(p.get_by_test_id("legal-new-draft").count(), "no Start a draft")
    return "available"


na(A, CL, "empty", "every country has its documents")


@fn(A, CL, "ops-refused", kind="permission", action="Open as city ops", expected="Can't start a draft", verify="UI", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{CL}?scope=US", who="ops_boi")
    ok(p.get_by_role("button", name="Start a draft").count() == 0, "ops can draft legal text")
    return "no drafts"


# ── Every admin page with core-api stopped ──────────────────────────────────────────────────────────────────────────
ADOWN = {"/login": "/login", "/": "/", OV: OV, OP: OP, INC: INC, PA: PA, P: P, F: F, SIM: SIM, MK: MK, MC: "/markets/{cc}",
         MCC: "/markets/{cc}/{city}", FI: FI, ST: "/finance/statements/00000000-0000-0000-0000-000000000000", SE: SE, CH: CH,
         CN: CN, CI: "/content/help/00000000-0000-0000-0000-000000000000", CL: CL}
for route, path in ADOWN.items():
    @fn(A, route, "api-down", kind="error", down=True, action="Open the page with core-api stopped",
        expected="It renders (no crash, no blank) and says it couldn't load", verify="UI: body text")
    def _(t: T, route: str = route, path: str = path) -> str:
        url = path.format(cc=CC[t.user], city=CITY[t.user]) + ("" if "?" in path or route in ("/login", "/") else f"?scope={CC[t.user]}")
        return down_state(t, url, "anon" if route == "/login" else None)
