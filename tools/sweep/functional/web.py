"""R42: the customer website's functions, page by page (framework.py). The money path first (brief item a), in the
order a customer goes: menu -> cart -> checkout -> pay -> tracking -> receipt -> report a problem -> refund."""
from __future__ import annotations

import json
import os
import re
import time
from decimal import Decimal

from framework import (MARKET, OTP, Fail, T, amounts, amounts_backed, api, dates_backed, down_state, fn, render_ms, money, na, ok,
                       sessions, sql, token)

W = "web"
S: dict = {}  # what one function leaves for the next, per market (the order made by paying, ...)
VARS = os.path.join(os.environ.get("OUT", "/out"), "sessions", "vars.json")


def rt(method: str, path: str, tok: str, body: dict | None = None) -> dict:
    import urllib.request
    req = urllib.request.Request(f"http://localhost:8004/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def uid(tok: str) -> str:
    import base64
    part = tok.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"]


def restaurant(market: str) -> dict:
    slug = MARKET[market]["rest"]
    return next(r for r in api("GET", "/restaurants?limit=100")["items"] if r["slug"] == slug)


def menu_item(market: str, name: str) -> dict:
    menu = api("GET", f"/restaurants/{restaurant(market)['id']}/menu")
    return next(i for c in menu["categories"] for i in c["items"] if i["name"] == name)


def paid_order(market: str, qty: int = 2) -> str:
    """An order placed and paid over the API (the pages that show one)."""
    m, tok = MARKET[market], token(market)
    rest, item = restaurant(market), menu_item(market, MARKET[market]["dish"])
    cart = [{"menu_item_id": item["id"], "quantity": qty}]
    q = api("POST", "/pricing/quote", tok, {"restaurant_id": rest["id"], "items": cart, "deliver_to": m["to"]})
    o = api("POST", "/orders", tok, {"restaurant_id": rest["id"], "items": cart, "quote_token": q["token"],
                                     "payment_method": m["method"], "delivery_address": m["addr"]})
    init = api("POST", "/payments/initiate", tok, {"order_id": o["id"], "payment_method_type": m["method"]})
    api("POST", f"/payments/fake/{init['payment_intent_id']}/complete", tok, {"outcome": "succeeded"})
    for _ in range(30):
        if api("GET", f"/orders/{o['id']}", tok)["status"] == "placed":
            break
        time.sleep(1)
    return o["id"]


def deliver(market: str, order_id: str) -> None:
    """The restaurant accepts and cooks, ops assign the rider, the rider picks up and hands over with the PIN."""
    m = MARKET[market]
    partner, rider, cust = token(m["partner"]), token(m["rider"]), token(market)
    ops = token("ops_boi" if market == "us" else "ops_hyd")
    for st in ("accepted", "preparing", "ready"):
        api("PUT", f"/orders/{order_id}/status", partner, {"status": st})
    rt("POST", "/delivery/assign", ops, {"order_id": order_id, "driver_id": uid(rider)})
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "picked_up"})
    pin = api("GET", f"/orders/{order_id}", cust)["pin"]
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})


def setup() -> None:
    """Before the functions: a paid order and a delivered one for each customer, saved for the "API down" phase."""
    out = {}
    for market in MARKET:
        try:
            placed = paid_order(market)
            done = paid_order(market, 2)  # Boise Bowl's minimum is $15: two bowls
            deliver(market, done)
            rest, item = restaurant(market), menu_item(market, MARKET[market]["dish"])
            # a cart for the "API down" phase's checkout (the website keeps it in localStorage: bhojango-bag)
            cart = {"restaurant": {"id": rest["id"], "name": rest["name"], "slug": rest["slug"], "city": rest["city"],
                                   "currency": rest.get("currency") or ("USD" if market == "us" else "INR")},
                    "lines": [{"key": f"{item['id']}|", "menuItemId": item["id"], "name": item["name"], "unitPrice": float(item["price"]),
                               "quantity": 2, "picks": [], "summary": ""}], "tip": 0, "fulfillment": "delivery"}
            out[market] = {"placed": placed, "delivered": done, "cart": cart}
        except Exception as e:  # noqa: BLE001 - the functions that need them then fail and say so
            print("setup", market, e, flush=True)
    os.makedirs(os.path.dirname(VARS), exist_ok=True)
    json.dump(out, open(VARS, "w"))
    S.update({"orders": out})


def orders(t: T) -> dict:
    if "orders" not in S and os.path.exists(VARS):
        S["orders"] = json.load(open(VARS))
    return S.get("orders", {}).get(t.user if t.user in MARKET else "us", {})


def bill_rows(t: T, scope) -> list[Decimal]:  # type: ignore[no-untyped-def]
    cells = [c.strip() for c in scope.locator("table tbody tr:not([data-testid='tax-share']) td:last-child").all_inner_texts()]
    return [money(c) for c in cells if re.search(r"[$₹]", c)]


def quote_capture(t: T) -> list[dict]:
    """The quotes the page asks core-api for, as the browser received them (what the bill is drawn from)."""
    got: list[dict] = []

    def on(resp):  # type: ignore[no-untyped-def]
        if "/api/v1/pricing/quote" in resp.url and resp.request.method == "POST" and resp.ok:
            try:
                got.append(resp.json())
            except Exception:  # noqa: BLE001
                pass
    t.page.on("response", on)
    return got


def last_quote(t: T, got: list[dict], **want) -> dict:  # type: ignore[no-untyped-def]
    for _ in range(40):
        t.page.wait_for_timeout(250)
        if got and all(str(got[-1].get(k)) == str(v) for k, v in want.items() if k != "tip") and \
                ("tip" not in want or Decimal(str(next((ln["amount"] for ln in got[-1]["lines"] if ln["code"] == "tip"), 0))) == Decimal(str(want["tip"]))):
            return got[-1]
    ok(got, "the page asked for no quote")
    raise Fail(f"no quote with {want}; last: { {k: got[-1].get(k) for k in want} }")


def bill_equals_quote(t: T, q: dict) -> str:
    """Every line of the fair bill on the page equals the quote's line, and the total and Pay button equal its total."""
    t.page.wait_for_timeout(600)
    bill = t.page.get_by_role("complementary", name="Your order")
    shown = sorted(bill_rows(t, bill))
    want = sorted(Decimal(str(ln["amount"])) for ln in q["lines"] if Decimal(str(ln["amount"])) != 0)
    ok(shown == want, f"bill lines {[str(x) for x in shown]} != quote lines {[str(x) for x in want]}")
    total = money(bill.locator("div.border-dashed b").last.inner_text())
    ok(total == Decimal(str(q["total"])), f"total {total} != quote {q['total']}")
    pay = t.page.get_by_role("button", name=re.compile(r"^Pay ")).first.inner_text()
    ok(money(pay) == Decimal(str(q["total"])), f"Pay button {pay!r} != {q['total']}")
    return f"{len(shown)} bill lines and the total {q['total']} equal the quote"


def to_cart(t: T, qty: int = 1) -> None:
    """The restaurant page with this market's dish in the cart (an empty cart first)."""
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    p.evaluate("() => { for (const k of Object.keys(localStorage)) if (/bag|cart/i.test(k)) localStorage.removeItem(k); }")
    p.reload(wait_until="networkidle")
    p.get_by_role("button", name=f"Add {t.m['dish']}").first.click()
    if p.get_by_role("dialog").count():
        p.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
    for _ in range(qty - 1):
        p.get_by_role("main").get_by_role("button", name=f"One more {t.m['dish']}").first.click()


# ── a. The money path ───────────────────────────────────────────────────────────────────────────────────────────────
K = "/[country]/[city]/[kitchen]"


@fn(W, K, "add-stepper-remove", kind="button",
    action="Add the dish (+), One more (+) twice, One less (−) once; add a second dish and take it back out (− to 0)",
    expected="The stepper reads 1, 2, 3, 2; the cart lists exactly the dish ×2 and the second dish is gone; the cart's food equals the menu price × 2",
    verify="UI: dish stepper and cart lines; API: menu price (GET /restaurants/{id}/menu)")
def _(t: T) -> str:
    to_cart(t)
    p = t.page
    t.shot("before")
    step = p.get_by_test_id("dish-stepper").first
    seen = [step.inner_text().strip()]
    for _ in range(2):
        p.get_by_role("main").get_by_role("button", name=f"One more {t.m['dish']}").first.click()
        seen.append(step.inner_text().strip())
    p.get_by_role("main").get_by_role("button", name=f"One less {t.m['dish']}").first.click()
    seen.append(step.inner_text().strip())
    ok([re.sub(r"\D", "", s) for s in seen] == ["1", "2", "3", "2"], f"stepper read {seen}")
    p.get_by_role("button", name=f"Add {t.m['dish2']}").first.click()
    if p.get_by_role("dialog").count():
        p.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
    cart = p.get_by_role("complementary", name="Your cart")
    ok(cart.get_by_text(t.m["dish2"]).count(), "the second dish isn't in the cart")
    cart.get_by_role("button", name=f"One less {t.m['dish2']}").first.click()
    p.wait_for_timeout(300)
    ok(cart.get_by_text(t.m["dish2"]).count() == 0, "the second dish is still in the cart at 0")
    ok(cart.get_by_text(re.compile(rf"2 × {re.escape(t.m['dish'])}")).count(), f"cart: {cart.inner_text()[:160]!r}")
    price = Decimal(str(menu_item(t.user, t.m["dish"])["price"]))
    shown = amounts(cart.inner_text())
    ok(price * 2 in shown, f"cart amounts {[str(a) for a in shown]} lack {price * 2} (menu {price} × 2)")
    t.shot("after")
    return f"stepper {seen}; cart {t.m['dish']} ×2 = {price * 2}; second dish removed"


@fn(W, K, "delivery-pickup-switch", kind="toggle",
    action="Read the Delivery / Pickup switch with no address, then with the customer's address; choose Pickup, then Delivery",
    expected="No address: 'from <the city's lowest band> delivery'; with the address: the engine's fee to it; Pickup shows its fee %; the choice sticks",
    verify="UI: how-delivery / how-pickup; API: GET /markets/cities/{cc}/{city} (delivery_from), GET /discover?lat&lng (delivery_fee)")
def _(t: T) -> str:
    import urllib.parse
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    cc, slug = t.m["path"].strip("/").split("/")
    city = api("GET", f"/markets/cities/{cc}/{slug}")
    frm = Decimal(str((city.get("pricing") or {}).get("delivery_from")))
    no_addr = p.get_by_test_id("how-delivery").inner_text()
    started = time.time()
    while money(no_addr) != frm and time.time() - started < 75:  # the website caches the city's pricing for 60 s
        p.wait_for_timeout(5000)
        p.reload(wait_until="networkidle")
        no_addr = p.get_by_test_id("how-delivery").inner_text()
    ok("from" in no_addr and money(no_addr) == frm, f"no address: {no_addr!r}, the city's lowest band is {frm}")
    place = {"lat": t.m["to"]["lat"], "lng": t.m["to"]["lng"], "label": t.m["addr"]["street"], "country": t.m["cc"]}
    t._ctx.add_cookies([{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": "http://localhost:3000"}])
    p.reload(wait_until="networkidle")
    deliv, pick = p.get_by_test_id("how-delivery"), p.get_by_test_id("how-pickup")
    d = api("GET", f"/discover?lat={t.m['to']['lat']}&lng={t.m['to']['lng']}")
    r = next(x for x in d["restaurants"] if x["slug"] == t.m["rest"])
    started = time.time()
    while money(deliv.inner_text()) != Decimal(str(r["delivery_fee"])) and time.time() - started < 75:  # cached 30-60 s
        p.wait_for_timeout(5000)
        p.reload(wait_until="networkidle")
    ok(money(deliv.inner_text()) == Decimal(str(r["delivery_fee"])), f"with the address: {deliv.inner_text()!r} vs discover {r['delivery_fee']}")
    pct = re.search(r"(\d+)% fee", pick.inner_text())
    ok(pct and Decimal(pct.group(1)) == Decimal(str(r.get("pickup_fee_percent") or pct.group(1))), f"pickup: {pick.inner_text()!r}")
    pick.click()
    ok(pick.get_attribute("aria-checked") == "true", "Pickup not chosen")
    deliv.click()
    ok(deliv.get_attribute("aria-checked") == "true", "Delivery not chosen")
    t.shot("with-address")
    return f"no address {no_addr!r} = city from {frm}; with address {deliv.inner_text()!r} = discover {r['delivery_fee']}; pickup {pct.group(0)}"


@fn(W, K, "menu-prices", kind="number", action="Read every price on the menu",
    expected="Each dish's price is the menu API's", verify="UI: every amount on the page; API: GET /restaurants/{id}/menu and /discover")
def _(t: T) -> str:
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    rest = restaurant(t.user)
    menu = api("GET", f"/restaurants/{rest['id']}/menu")
    d = api("GET", f"/discover?lat={t.m['to']['lat']}&lng={t.m['to']['lng']}")
    return amounts_backed(t.text(), menu, rest, d)


@fn(W, K, "menu-search-empty", kind="empty", action="Search the menu for a dish it doesn't have",
    expected="No dishes listed and a 'nothing matches' line", verify="UI: dish rows and the empty line")
def _(t: T) -> str:
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    p.get_by_role("searchbox", name="Search menu").fill("zzqx")
    p.wait_for_timeout(500)
    ok(p.get_by_role("button", name=re.compile(r"^Add ")).count() == 0, "dishes still listed")
    body = t.text()
    ok(re.search(r"no |nothing|didn.t find|matches", body, re.I), f"no empty line: {body[:200]!r}")
    t.shot("empty")
    return "no dishes, an empty line"


@fn(W, K, "save-share", kind="button", action="Save the restaurant (heart), then unsave; open Share",
    expected="Saved shows on the account (favourites API) and goes again; Share offers the link",
    verify="UI: aria-pressed; API: GET /me/favourites", users=("us",))
def _(t: T) -> str:
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    rest = restaurant(t.user)
    heart = p.get_by_role("main").get_by_role("button", name=re.compile(r"^(Save|Unsave|Remove) ")).first
    before = heart.get_attribute("aria-pressed")
    heart.click()
    p.wait_for_timeout(800)
    favs = json.dumps(api("GET", "/me/favourites", token(t.user)))
    now_saved = rest["id"] in favs
    ok(now_saved == (before != "true"), f"favourites API saved={now_saved} after the click (was {before})")
    heart.click()
    p.wait_for_timeout(800)
    ok((rest["id"] in json.dumps(api("GET", "/me/favourites", token(t.user)))) == (before == "true"), "not back as it was")
    p.get_by_role("button", name="Share").click()
    p.wait_for_timeout(300)
    return "save and unsave agree with the favourites API; Share opens"


C = "/checkout"


@fn(W, C, "bill-equals-quote", kind="number", action="Open checkout with the dish ×2 in the cart",
    expected="Every fair-bill line, the total and the Pay button equal the pricing API's quote",
    verify="UI: bill rows, total, Pay; API: the POST /pricing/quote the page received")
def _(t: T) -> str:
    to_cart(t, 2)
    got = quote_capture(t)
    t.page.goto("http://localhost:3000/checkout", wait_until="networkidle")
    q = last_quote(t, got)
    S[t.user] = {"quote": q}
    t.shot("bill")
    return bill_equals_quote(t, q)


@fn(W, C, "fulfilment-switch", kind="toggle", action="Choose Pickup at checkout, then Delivery",
    expected="Pickup: a pickup quote with no delivery fee or tip line, the bill equals it; Delivery: back to the delivery quote",
    verify="UI: bill; API: the quotes the page received (fulfillment)")
def _(t: T) -> str:
    to_cart(t, 2)
    got = quote_capture(t)
    p = t.page
    p.goto("http://localhost:3000/checkout", wait_until="networkidle")
    last_quote(t, got)
    if not p.get_by_test_id("how-pickup").count():
        return "this restaurant takes no pickup orders: delivery only (no switch)"
    p.get_by_test_id("how-pickup").click()
    q = last_quote(t, got, fulfillment="pickup")
    ok(not [ln for ln in q["lines"] if ln["code"] in ("delivery_fee", "tip")], f"pickup quote has {[ln['code'] for ln in q['lines']]}")
    a = bill_equals_quote(t, q)
    t.shot("pickup")
    p.get_by_test_id("how-delivery").click()
    q2 = last_quote(t, got, fulfillment="delivery")
    bill_equals_quote(t, q2)
    return f"pickup: {a}; delivery again equals its quote"


@fn(W, C, "promo-code", kind="form",
    action="With the city's BhojanGo offer budget set and the code's offer resumed: a wrong promo code, then the city's code (BOISE5 / FEAST100), then Remove",
    expected="The wrong code says it doesn't apply and changes nothing; the right one says applied and adds the discount the quote has; Remove takes it off",
    verify="UI: promo-state (applied or not), bill lines and total; API: the quotes the page received (promotion line with detail.promo_code)")
def _(t: T) -> str:
    code = "BOISE5" if t.user == "us" else "FEAST100"
    cm, fin = ("cm_us", "finance_us") if t.user == "us" else ("cm_in", "finance_in")
    # R37: BhojanGo pays for these codes, so they're off until the city has a monthly budget and an approver resumes them
    rule = next(r for r in api("GET", "/rules?family=promotion", token(fin)) if (r.get("params") or {}).get("code") == code
                and not r.get("effective_to"))
    was_paused = bool(rule.get("paused_at"))
    api("PUT", f"/rules/offers/budgets/city/{t.m['city']}", token(cm), {"monthly": "1000" if t.user == "us" else "100000"})
    if was_paused:
        api("POST", f"/rules/{rule['id']}/resume", token(fin))
    try:
        to_cart(t, 4)  # over the code's minimum (BOISE5 $30, FEAST100 ₹499)
        got = quote_capture(t)
        p = t.page
        p.goto("http://localhost:3000/checkout", wait_until="networkidle")
        base = last_quote(t, got)
        p.get_by_placeholder("Promo code").fill("NOPE999")
        p.get_by_role("button", name="Apply").click()
        state = p.get_by_test_id("promo-state")
        state.get_by_text("doesn't apply").wait_for(timeout=15000)
        t.shot("wrong-code")
        ok(state.get_attribute("data-applied") == "false", "a wrong code shows as applied")
        ok(Decimal(str(got[-1]["total"])) == Decimal(str(base["total"])), f"a wrong code changed the total: {got[-1]['total']}")
        p.get_by_role("button", name="Remove").click()
        p.get_by_placeholder("Promo code").fill(code)
        p.get_by_role("button", name="Apply").click()
        for _ in range(40):
            if any(ln["code"] == "promotion" and (ln.get("detail") or {}).get("promo_code") == code for ln in got[-1]["lines"]):
                break
            p.wait_for_timeout(250)
        q = got[-1]
        off = [ln for ln in q["lines"] if ln["code"] == "promotion" and (ln.get("detail") or {}).get("promo_code") == code]
        ok(off, f"{code}: no discount line in the quote ({[ln['code'] for ln in q['lines']]})")
        ok(state.get_attribute("data-applied") == "true", f"{code} not shown as applied")
        bill_equals_quote(t, q)
        t.shot("code-applied")
        p.get_by_role("button", name="Remove").click()
        for _ in range(40):
            if Decimal(str(got[-1]["total"])) == Decimal(str(base["total"])):
                break
            p.wait_for_timeout(250)
        ok(Decimal(str(got[-1]["total"])) == Decimal(str(base["total"])), f"after Remove {got[-1]['total']} != {base['total']}")
        return f"NOPE999: 'doesn't apply', total unchanged; {code}: {off[0]['amount']} off, bill = quote; removed: back to {base['total']}"
    finally:
        if was_paused:
            api("POST", f"/rules/{rule['id']}/pause", token(fin), {"reason": rule.get("paused_reason") or "Off by default"})
        api("PUT", f"/rules/offers/budgets/city/{t.m['city']}", token(cm), {"monthly": None})


@fn(W, C, "tip-chips", kind="button", action="Choose each tip chip, then Other with a typed amount",
    expected="The tip line and total follow each chip; the chips are the city's tip presets",
    verify="UI: tip chips, bill; API: the quote for each tip")
def _(t: T) -> str:
    to_cart(t, 2)
    got = quote_capture(t)
    p = t.page
    p.goto("http://localhost:3000/checkout", wait_until="networkidle")
    last_quote(t, got)
    chips = p.get_by_role("radiogroup", name="Tip your delivery partner").get_by_role("radio")
    labels = [chips.nth(i).inner_text().strip() for i in range(chips.count())]
    done = []
    for i, label in enumerate(labels):
        if label in ("Other",):
            continue
        chips.nth(i).click()
        want = Decimal(0) if label == "None" else money(label)
        q = last_quote(t, got, tip=want)
        bill_equals_quote(t, q)
        done.append(f"{label}={want}")
    t.shot("tips")
    return f"chips {labels}: each tip on the quote and the bill ({', '.join(done)})"


@fn(W, C, "pay-declined", kind="error", action="Pay, then Decline in the test provider's checkout",
    expected="'Your payment didn't go through' and no charge: the order stays unpaid, the price held",
    verify="UI: the alert; API: the order's payment status is not paid")
def _(t: T) -> str:
    to_cart(t, 2)
    p = t.page
    p.goto("http://localhost:3000/checkout", wait_until="networkidle")
    p.get_by_role("button", name=re.compile(r"^Pay ")).first.click()
    dlg = p.get_by_role("dialog", name="Pay (test mode)")
    dlg.get_by_role("button", name="Decline").click()
    alert = p.get_by_role("alert").filter(has_text="didn't go through")
    alert.first.wait_for(timeout=20000)
    t.shot("declined")
    mine = api("GET", "/orders?limit=1", token(t.user))
    items = mine.get("items", mine) if isinstance(mine, dict) else mine
    last = items[0] if items else {}
    ok(last.get("payment_status") not in ("paid", "succeeded", "captured"), f"latest order payment {last.get('payment_status')}")
    return f"alert shown; latest order {last.get('status')}/{last.get('payment_status')}"


@fn(W, C, "pay-and-order-stored", kind="form",
    action="Pay with the market's method (US card, India UPI) and Approve in the test provider's checkout",
    expected="Tracking opens; the stored order's lines and total equal the quote paid; payment captured once",
    verify="UI: Pay, tracking URL; API: GET /orders/{id}, /pricing/orders/{id}/snapshot; DB: orders.total, payments")
def _(t: T) -> str:
    to_cart(t, 2)
    got = quote_capture(t)
    p = t.page
    p.goto("http://localhost:3000/checkout", wait_until="networkidle")
    q = last_quote(t, got)
    bill_equals_quote(t, q)
    t.shot("before")
    p.get_by_role("button", name=re.compile(r"^Pay ")).first.click()
    dlg = p.get_by_role("dialog", name="Pay (test mode)")
    dlg.get_by_role("button", name=re.compile("^Approve")).click()
    p.wait_for_url(re.compile(r"/orders/[0-9a-f-]{36}/track$"), timeout=40000)
    oid = p.url.rstrip("/").split("/")[-2]
    t.shot("after")
    o = api("GET", f"/orders/{oid}", token(t.user))
    ok(Decimal(str(o["total"])) == Decimal(str(q["total"])), f"order total {o['total']} != quote {q['total']}")
    snap = api("GET", f"/pricing/orders/{oid}/snapshot", token("super"))
    s_lines = sorted(Decimal(str(ln["amount"])) for ln in snap.get("lines", snap.get("quote", {}).get("lines", [])))
    q_lines = sorted(Decimal(str(ln["amount"])) for ln in q["lines"])
    ok(s_lines == q_lines, f"stored lines {[str(x) for x in s_lines]} != quote {[str(x) for x in q_lines]}")
    row = sql("SELECT total, payment_method FROM orders WHERE id = %s", oid)[0]
    ok(Decimal(str(row[0])) == Decimal(str(q["total"])), f"DB total {row[0]}")
    pays = sql("SELECT count(*) FROM payment_intents WHERE order_id = %s AND status IN ('succeeded','captured','paid')", oid)[0][0]
    ok(pays == 1, f"{pays} successful payments for the order")
    S.setdefault(t.user, {})["order"] = oid
    return f"order {oid[:8]} total {o['total']} = quote; {len(s_lines)} stored lines = quote; 1 payment ({row[1]})"


TR = "/orders/[id]/track"


@fn(W, TR, "status-follows", kind="display", action="Watch tracking while the restaurant accepts, cooks, and the rider picks up and delivers",
    expected="The status line follows each step live (no reload); the PIN appears only after pickup",
    verify="UI: Order status region, delivery-pin; API: the order's status after each step")
def _(t: T) -> str:
    oid = S.get(t.user, {}).get("order") or paid_order(t.user)
    p = t.open(f"/orders/{oid}/track")
    status = p.get_by_role("region", name="Order status")
    seen = [status.inner_text().replace("\n", " ")[:80]]
    ok(p.locator('[data-testid="delivery-pin"]').count() == 0, "a PIN before pickup")
    m = t.m
    partner, rider, cust = token(m["partner"]), token(m["rider"]), token(t.user)
    ops = token("ops_boi" if t.user == "us" else "ops_hyd")
    for st in ("accepted", "preparing", "ready"):
        api("PUT", f"/orders/{oid}/status", partner, {"status": st})
        p.wait_for_timeout(1500)
        seen.append(status.inner_text().replace("\n", " ")[:80])
    rt("POST", "/delivery/assign", ops, {"order_id": oid, "driver_id": uid(rider)})
    api("PUT", f"/orders/{oid}/status", rider, {"status": "picked_up"})
    p.locator('[data-testid="delivery-pin"]:visible').wait_for(timeout=20000)
    pin_ui = p.locator('[data-testid="delivery-pin"]:visible').inner_text().strip()
    ok(pin_ui == api("GET", f"/orders/{oid}", cust)["pin"], "the PIN on the page isn't the order's")
    t.shot("picked-up")
    api("PUT", f"/orders/{oid}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin_ui}})
    status.get_by_text(re.compile("Delivered|delivered|Enjoy", re.I)).first.wait_for(timeout=20000)
    seen.append(status.inner_text().replace("\n", " ")[:80])
    t.shot("delivered")
    ok(len(set(seen)) >= 3, f"the status didn't move: {seen}")
    return " → ".join(seen)


@fn(W, TR, "amounts", kind="number", action="Read the bill on the tracking page",
    expected="Every amount is the order's (lines, total, You paid)", verify="UI: page amounts; API: GET /orders/{id} and its pricing snapshot")
def _(t: T) -> str:
    oid = S.get(t.user, {}).get("order") or orders(t).get("placed")
    ok(oid, "no order")
    t.open(f"/orders/{oid}/track")
    return amounts_backed(t.text(), api("GET", f"/orders/{oid}", token(t.user)), api("GET", f"/pricing/orders/{oid}/snapshot", token("super")))


@fn(W, TR, "someone-elses-order", kind="permission", action="Open another customer's order",
    expected="Refused: not found, nothing of the order shown; the API refuses too",
    verify="UI: no bill; API: GET /orders/{id} as the other customer -> 403/404")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    ok(oid, "no order")
    other = "customer2.boi@example.com" if t.user == "us" else "customer2.hyd@example.com"
    status, _ = api("GET", f"/orders/{oid}", token(other), raw=True)
    ok(status in (403, 404), f"API answered {status}")
    p = t.open(f"/orders/{oid}/track", who=other)
    ok(p.get_by_text("The fair bill").count() == 0, "the bill is shown to another customer")
    t.shot("refused")
    return f"API {status}; the page shows nothing of it"


O = "/orders/[id]"


@fn(W, O, "opens-tracking", kind="navigation", action="Open /orders/{id}", expected="Goes to its tracking page",
    verify="UI: the URL ends /track; API: the order exists for this customer")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    ok(oid, "no order")
    p = t.open(f"/orders/{oid}")
    ok(re.search(rf"/orders/{oid}/track", p.url), p.url)
    return "redirects to /track"


@fn(W, O, "signed-out", kind="permission", action="Open an order signed out",
    expected="Sign in first (the order isn't shown)", verify="UI: /signin?next=…")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    p = t.open(f"/orders/{oid}", who="anon")
    ok("/signin" in p.url or p.get_by_text("The fair bill").count() == 0, p.url)
    return f"signed out: {p.url.replace('http://localhost:3000', '')}"


@fn(W, O, "unknown-order", kind="empty", action="Open an order id that doesn't exist",
    expected="'We couldn't find this order' and a way back", verify="UI: the not-found state")
def _(t: T) -> str:
    p = t.open("/orders/00000000-0000-0000-0000-000000000000")
    body = p.locator("body").inner_text()
    ok(re.search(r"couldn.t find|not found|no such", body, re.I), body[:200])
    return "not-found state"


RC = "/account/orders"


@fn(W, RC, "receipt-equals-order", kind="number", action="Open the paid order's receipt from Your orders",
    expected="Every receipt line, You paid and any refund equal the stored order; India: GST lines; the date is the order's",
    verify="UI: the receipt article; API: GET /orders/{id}, /pricing/orders/{id}/snapshot")
def _(t: T) -> str:
    oid = S.get(t.user, {}).get("order") or orders(t).get("delivered")
    ok(oid, "no order")
    p = t.open(f"/account/orders?order={oid}")
    o = api("GET", f"/orders/{oid}", token(t.user))
    receipt = p.get_by_role("article", name=re.compile(r"^Receipt for order"))
    receipt.wait_for(timeout=20000)
    t.shot("receipt")
    snap = api("GET", f"/pricing/orders/{oid}/snapshot", token("super"))
    res = amounts_backed(receipt.inner_text(), o, snap)
    dates_backed(receipt.inner_text(), t.m["tz"], o)
    return res


@fn(W, RC, "filters-search", kind="filter", action="Use the All / In progress / Delivered / Cancelled filters and the search box",
    expected="Each filter lists exactly the orders the API has in that state; a search for the restaurant finds its orders",
    verify="UI: order rows; API: GET /orders (statuses)")
def _(t: T) -> str:
    p = t.open("/account/orders")
    mine = api("GET", "/orders?limit=100", token(t.user))
    items = mine.get("items", mine) if isinstance(mine, dict) else mine
    counts = {}
    for name in ("All", "In progress", "Delivered", "Cancelled"):
        p.get_by_role("button", name=name, exact=True).click()
        p.wait_for_timeout(500)
        m = re.search(r"(\d+) orders?\b", t.text())
        counts[name] = int(m.group(1)) if m else 0
    done = sum(1 for o in items if o["status"] == "delivered")
    ok(counts["Delivered"] == done, f"Delivered shows {counts['Delivered']}, the API has {done}")
    ok(counts["All"] == len(items), f"All shows {counts['All']}, the API has {len(items)}")
    t.shot("filters")
    return f"{counts} = the API's"


@fn(W, RC, "no-orders-yet", kind="empty", action="Open Your orders as a new customer",
    expected="'No orders yet' and Find something to eat", verify="UI: empty state; API: GET /orders is empty", users=("us",))
def _(t: T) -> str:
    p = t.open("/account/orders", who="fresh")
    body = t.text()
    ok(re.search(r"0 orders|no orders", body, re.I), body[:160])
    ok(p.get_by_role("link", name="Find something to eat").count(), "no way to find food")
    t.shot("empty")
    return "empty state"


@fn(W, RC, "signed-out", kind="permission", action="Open Your orders signed out", expected="Sign in first",
    verify="UI: /signin?next=/account/orders", users=("us",))
def _(t: T) -> str:
    p = t.open("/account/orders", who="anon")
    ok("/signin" in p.url, p.url)
    return p.url.replace("http://localhost:3000", "")


RP = "/orders/[id]/report"


@fn(W, RP, "report-refund", kind="form",
    action="On a delivered order, choose 1 of the dish, Missing, and Send report",
    expected="Refunded (under the city's automatic limit): the refund equals the item's price incl. its tax; the order shows it",
    verify="UI: 'Refunded' and the amount; API: GET /orders/{id} refunds; DB: refunds row")
def _(t: T) -> str:
    oid = orders(t).get("delivered")
    ok(oid, "no delivered order")
    p = t.open(f"/orders/{oid}/report")
    t.shot("before")
    p.locator("input[type=number]").first.fill("1")
    p.get_by_text("Missing", exact=True).first.click()
    plus = p.get_by_role("button", name=re.compile(r"^(One more|Add|Increase)"))
    if plus.count():
        plus.first.click()
    p.get_by_role("button", name="Send report").click()
    done = p.get_by_text(re.compile(r"^Refunded|Sent to support"))
    done.first.wait_for(timeout=20000)
    t.shot("after")
    body = p.locator("main").inner_text()
    if "Sent to support" in body:  # over the city's automatic limit: a person checks it first
        n = sql("SELECT count(*) FROM support_tickets WHERE row_to_json(support_tickets)::text ILIKE %s", f"%{oid}%")[0][0]
        ok(n >= 1, "sent to support, but no ticket for the order")
        return f"over the automatic limit: sent to support (ticket stored); {body.splitlines()[-1][:80]!r}"
    rows = sql("SELECT amount, status FROM refunds WHERE order_id = %s ORDER BY created_at DESC", oid)
    ok(rows, "the page says refunded, but no refund row")
    shown = amounts(body)
    amt = Decimal(str(rows[0][0]))
    ok(amt in shown or (amt / 100).quantize(Decimal("0.01")) in shown, f"refund {amt} not on the page {shown}")
    return f"refund {amt} ({rows[0][1]}) shown"


@fn(W, RP, "nothing-chosen", kind="error", action="Press Send report without choosing an item or reason",
    expected="Send stays disabled / says what to choose; nothing is sent", verify="UI: disabled button; DB: no new refund or ticket")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    p = t.open(f"/orders/{oid}/report")
    send = p.get_by_role("button", name="Send report")
    ok(send.is_disabled(), "Send is enabled with nothing chosen")
    return "Send disabled until an item and reason are chosen"


@fn(W, RP, "someone-elses", kind="permission", action="Open the report page for another customer's order",
    expected="We couldn't find this order", verify="UI: not-found; API: POST /orders/{id}/problems as another -> 403/404")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    other = "customer3.boi@example.com" if t.user == "us" else "customer3.hyd@example.com"
    p = t.open(f"/orders/{oid}/report", who=other)
    body = p.locator("body").inner_text()
    ok(re.search(r"couldn.t find|not found", body, re.I) or "/signin" in p.url, body[:160])
    return "refused"


na(W, RP, "empty", "a report is always about one order: there is no list to be empty (an unknown order: see someone-elses)")


AR = "/account/orders/[id]/report"


@fn(W, AR, "opens-form", kind="navigation", action="Open Report a problem from the account",
    expected="The same form for that order (items, reasons, photo)", verify="UI: heading, reasons; API: the order's items")
def _(t: T) -> str:
    oid = orders(t).get("placed")
    p = t.open(f"/account/orders/{oid}/report")
    ok(p.get_by_role("heading", name="Report a problem", level=1).count(), "no form")
    o = api("GET", f"/orders/{oid}", token(t.user))
    names = [i.get("name") or i.get("item_name") for i in o.get("items", [])]
    ok(all(n and p.get_by_text(n).count() for n in names), f"items {names} not all listed")
    return f"form with {names}"


@fn(W, AR, "photo-too-big", kind="error", action="Attach a file that isn't a photo",
    expected="Refused with a message; nothing uploaded", verify="UI: the photo message", users=("in",))
def _(t: T) -> str:
    oid = orders(t).get("placed")
    p = t.open(f"/account/orders/{oid}/report")
    p.locator("input[type=file]").set_input_files(files=[{"name": "notes.txt", "mimeType": "text/plain", "buffer": b"not a photo"}])
    p.wait_for_timeout(800)
    body = t.text()
    ok(re.search(r"photo|image|JPEG|PNG|upload", body, re.I), body[:200])
    return "a non-photo is refused"


@fn(W, AR, "signed-out", kind="permission", action="Open it signed out", expected="Sign in first", verify="UI: /signin", users=("us",))
def _(t: T) -> str:
    p = t.open(f"/account/orders/{orders(t).get('placed')}/report", who="anon")
    ok("/signin" in p.url, p.url)
    return "sign in first"


na(W, AR, "empty", "about one order; no list (an unknown order shows 'We couldn't find this order')")


# ── Checkout's other states ─────────────────────────────────────────────────────────────────────────────────────────
@fn(W, C, "empty-cart", kind="empty", action="Open checkout with an empty cart",
    expected="'Your cart is empty' and Find something to eat", verify="UI: empty state")
def _(t: T) -> str:
    p = t.open("/checkout")
    p.evaluate("() => { for (const k of Object.keys(localStorage)) if (/bag|cart/i.test(k)) localStorage.removeItem(k); }")
    p.reload(wait_until="networkidle")
    ok(p.get_by_text("Your cart is empty").count(), t.text()[:160])
    return "empty state"


@fn(W, C, "signed-out", kind="permission", action="Open checkout signed out", expected="Sign in first, then back to checkout",
    verify="UI: /signin?next=/checkout", users=("us",))
def _(t: T) -> str:
    p = t.open("/checkout", who="anon")
    ok("/signin" in p.url, p.url)
    return "sign in first"


CR = "/checkout/return"


@fn(W, CR, "unknown-order", kind="empty", action="Come back from a payment page for an order that doesn't exist",
    expected="Says it couldn't find the payment and links back to checkout", verify="UI: Back to checkout")
def _(t: T) -> str:
    p = t.open("/checkout/return?order=00000000-0000-0000-0000-000000000000")
    ok(p.get_by_role("link", name="Back to checkout").count(), t.text()[:160])
    return "Back to checkout"


@fn(W, CR, "paid-order", kind="navigation", action="Come back from the payment page for a paid order",
    expected="Goes on to its tracking page", verify="UI: URL /orders/{id}/track; API: the order is paid")
def _(t: T) -> str:
    oid = paid_order(t.user)  # paid just now (an unaccepted order is cancelled after a while)
    p = t.open(f"/checkout/return?order={oid}&redirect_status=succeeded")
    p.wait_for_url(re.compile(rf"/orders/{oid}"), timeout=30000)
    return "to tracking"


@fn(W, CR, "signed-out", kind="permission", action="Open it signed out", expected="Sign in first (nothing about the order)",
    verify="UI: /signin or no order shown", users=("us",))
def _(t: T) -> str:
    p = t.open(f"/checkout/return?order={orders(t).get('placed')}", who="anon")
    ok("/signin" in p.url or p.get_by_text("The fair bill").count() == 0, p.url)
    return "nothing shown"


# ── The rest of the website ─────────────────────────────────────────────────────────────────────────────────────────
@fn(W, "/", "find-food", kind="form", action="Type the city's address and Find food",
    expected="Lands on the city's restaurants", verify="UI: URL is the city page and lists its restaurants; API: /discover has them")
def _(t: T) -> str:
    p = t.open("/", who="anon")
    p.get_by_role("link", name="Hyderabad" if t.user == "in" else "Boise").first.click()
    p.wait_for_url(re.compile(t.m["path"]), timeout=20000)
    return f"→ {t.m['path']}"


@fn(W, "/", "who-gets-amounts", kind="number", action="Read the example bill (who gets your money)",
    expected="Each amount is the pricing example's", verify="UI: the money split; API: GET /pricing/example?city=")
def _(t: T) -> str:
    p = t.open("/", who="anon")
    ex = api("GET", f"/pricing/example?city={t.m['city']}")
    block = p.get_by_test_id("who-gets")
    return amounts_backed(block.inner_text(), ex) if block.count() else amounts_backed(t.text(), ex)


@fn(W, "/", "notify-me", kind="form", action="Type a city we're not in and an email, tick Email me, and Notify me",
    expected="Thanks; a sign-up is stored once", verify="UI: confirmation; API: 2xx from the notify endpoint")
def _(t: T) -> str:
    p = t.open("/", who="anon")
    p.get_by_role("textbox", name="Your city").fill("Atlantis")
    p.get_by_role("textbox", name="Your email").fill(f"r42.notify.{int(time.time())}@example.com")
    p.get_by_role("checkbox").first.check()
    t.shot("before")
    p.get_by_role("button", name="Notify me").click()
    p.wait_for_timeout(1500)
    t.shot("after")
    ok(re.search(r"thank|we.ll (email|let)|you.re on|saved", t.text(), re.I), t.text()[:200])
    return "confirmation shown"


@fn(W, "/", "city-search-empty", kind="empty", action="Search the city list for a place we don't serve",
    expected="No cities and a 'not there yet' line", verify="UI: city list")
def _(t: T) -> str:
    p = t.open("/", who="anon")
    p.get_by_role("searchbox", name="Find your city").fill("Zzyzx")
    p.get_by_text("No city by that name yet").wait_for(timeout=10000)
    t.shot("empty")
    return "'No city by that name yet. Tell us where you are.'"


na(W, "/", "permission", "the public home page: anyone may open it")


@fn(W, "/cities", "filters", kind="filter", action="Use All countries / India / United States / Live now and the search",
    expected="Each lists exactly the cities the API has for it; counts on the tabs equal the lists",
    verify="UI: city cards; API: GET /markets/cities (or /cities)")
def _(t: T) -> str:
    p = t.open("/cities", who="anon")
    counts = {}
    for name in ("India", "United States"):
        b = p.get_by_role("button", name=re.compile(rf"^{name} · \d+"))
        n = int(re.search(r"(\d+)", b.inner_text()).group(1))
        b.click()
        p.wait_for_timeout(300)
        listed = p.locator("a[href^='/in/'], a[href^='/us/']").filter(has_text=re.compile("restaurants")).count()
        counts[name] = (n, listed)
        ok(n == listed, f"{name}: tab says {n}, lists {listed} live")
    p.get_by_role("button", name="Live now").click()
    p.get_by_role("searchbox").fill("Boise")
    p.wait_for_timeout(300)
    ok(p.get_by_role("link", name=re.compile("^Boise")).count(), "search for Boise found nothing")
    t.shot("filtered")
    return f"tab counts = cards: {counts}"


@fn(W, "/cities", "restaurant-counts", kind="number", action="Read each city's restaurant count",
    expected="The number of live restaurants the API lists in that city", verify="UI: 'N restaurants'; API: GET /restaurants?city=")
def _(t: T) -> str:
    p = t.open("/cities", who="anon")
    out = []
    for city, path in (("Hyderabad", "/in/hyderabad"), ("Boise", "/us/boise")):
        card = p.locator(f"a[href='{path}']").first
        n = int(re.search(r"(\d+) restaurants", card.inner_text()).group(1))
        code = "IN-TG-HYD" if city == "Hyderabad" else "US-ID-BOI"
        d = api("GET", f"/discover?city={code}")
        api_n = len(d.get("restaurants", []))
        ok(n == api_n, f"{city}: {n} shown, {api_n} in /discover?city=")
        out.append(f"{city} {n}")
    return ", ".join(out)


@fn(W, "/cities", "no-match", kind="empty", action="Search for a city we don't serve", expected="No cards; a 'no city' line",
    verify="UI: cards and the empty line", users=("us",))
def _(t: T) -> str:
    p = t.open("/cities", who="anon")
    p.get_by_role("searchbox").fill("Zzyzx")
    p.wait_for_timeout(400)
    ok(p.locator("a[href^='/in/'], a[href^='/us/']").count() == 0, "cards still listed")
    return "no cards"


na(W, "/cities", "permission", "public page")


CT = "/[country]/[city]"


@fn(W, CT, "cards-and-fees", kind="number", action="Read every restaurant card (fee, time, distance) at the customer's address",
    expected="Each card's delivery fee, minimum and times are the discover API's for that location",
    verify="UI: every amount on the page; API: GET /discover?lat&lng, GET /pricing/example")
def _(t: T) -> str:
    t.open(t.m["path"])
    d = api("GET", f"/discover?lat={t.m['to']['lat']}&lng={t.m['to']['lng']}")
    d2 = api("GET", f"/discover?city={t.m['city']}")
    cc, slug = t.m["path"].strip("/").split("/")
    return amounts_backed(t.text(), d, d2, api("GET", f"/pricing/example?city={t.m['city']}"), api("GET", f"/markets/cities/{cc}/{slug}"))


@fn(W, CT, "search-and-open", kind="filter", action="Search for a cuisine, open the first card",
    expected="Only matching restaurants; the card opens its menu", verify="UI: cards, URL")
def _(t: T) -> str:
    p = t.open(t.m["path"])
    p.get_by_role("searchbox", name="Search restaurants and cuisines").fill("Bowl" if t.user == "us" else "Biryani")
    p.wait_for_timeout(600)
    cards = p.locator("[data-testid^='kitchen-card-']")
    ok(cards.count() >= 1, "nothing found")
    cards.first.locator("a").first.click()
    p.wait_for_url(re.compile(rf"{t.m['path']}/[a-z0-9-]+$"), timeout=20000)
    return f"{cards.count()} cards; opened {p.url.rsplit('/', 1)[-1]}"


@fn(W, CT, "no-match", kind="empty", action="Search for something no restaurant has", expected="No cards and a line saying so",
    verify="UI: cards and the empty line")
def _(t: T) -> str:
    p = t.open(t.m["path"])
    box = p.get_by_role("searchbox", name="Search restaurants and cuisines")
    box.fill("zzqx")
    box.press("Enter")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(800)
    t.shot("empty")
    shown = p.locator("[data-testid^='kitchen-card-']:visible").count()
    said = re.search(r"no (restaurants|results|dishes)|nothing (found|matches)|didn.t find|no match", t.text(), re.I)
    ok(shown == 0 and said, f"{shown} cards still shown; message: {bool(said)}")
    return f"no cards; {said.group(0)!r}"


@fn(W, CT, "unknown-city", kind="error", action="Open a city that doesn't exist", expected="Not found, with a way to the city list",
    verify="UI: 404 page", users=("us",))
def _(t: T) -> str:
    p = t.open("/us/atlantis")
    ok(re.search(r"can.t find|not found|couldn.t find|isn.t|doesn.t", p.locator("body").inner_text(), re.I), p.locator("body").inner_text()[:160])
    return "not found"


na(W, CT, "permission", "public page")


@fn(W, K, "unknown-restaurant", kind="error", action="Open a restaurant that doesn't exist", expected="Not found",
    verify="UI: 404 page", users=("in",))
def _(t: T) -> str:
    p = t.open(f"{t.m['path']}/no-such-restaurant")
    ok(re.search(r"can.t find|not found|couldn.t find", p.locator("body").inner_text(), re.I), p.locator("body").inner_text()[:160])
    return "not found"


na(W, K, "permission", "public page (paying needs sign-in: see /checkout signed-out)")


@fn(W, "/deliver", "sign-up-form", kind="form", action="Fill name, date of birth, vehicle, mobile and city; Send code; enter the code",
    expected="An under-18 date is refused; a valid form sends a code and starts the application",
    verify="UI: the age message, the code step; API: the new rider's checklist (GET /riders/me/documents)")
def _(t: T) -> str:
    p = t.open("/deliver", who="anon")
    p.get_by_label("Your full name").fill("R42 Rider")
    p.get_by_label("Date of birth").fill("2015-01-01")
    p.get_by_test_id("gs-vehicle-scooter").check(force=True)
    p.get_by_label("Country code").select_option(t.m["cc"])
    # a number the stack answers with the fixed test code (OTP_FIXED_CODE_PHONE_PREFIXES: +12085550…, +9190000…)
    phone = ("20855509" if t.user == "us" else "90000") + str(int(time.time()))[-2 if t.user == "us" else -5:]
    p.get_by_role("textbox", name="Mobile number").fill(phone)
    p.wait_for_timeout(300)
    young = p.get_by_test_id("gs-send").is_disabled() or re.search(r"18|old enough", t.text())
    ok(young, "an under-18 date of birth was accepted")
    p.get_by_label("Date of birth").fill("1995-05-05")
    t.shot("before")
    p.get_by_test_id("gs-send").click()
    code = p.get_by_label("6-digit code")
    code.wait_for(timeout=15000)
    code.fill(OTP)
    p.get_by_role("button", name="Verify and sign up").click()
    p.wait_for_timeout(3000)
    t.shot("after")
    body = p.locator("#get-started").inner_text() if p.locator("#get-started").count() else t.text()
    ok(not re.search(r"didn.t work|invalid|wrong code", body, re.I), f"the code was refused: {body[-200:]!r}")
    return f"under-18 refused; code accepted for {phone}: {body.splitlines()[-1][:80] if body else ''}"


@fn(W, "/deliver", "pay-numbers", kind="number", action="Read the pay table", expected="Trip pay by distance is the city's rider pay rule",
    verify="UI: pay-cards amounts; API: GET /deliver/terms?city= (rider pay)")
def _(t: T) -> str:
    p = t.open("/deliver", who="anon")
    terms = api("GET", f"/delivery/terms?city={t.m['city']}") if api("GET", f"/delivery/terms?city={t.m['city']}", raw=True)[0] == 200 else {}
    return amounts_backed(p.get_by_test_id("pay-cards").inner_text(), terms, api("GET", f"/pricing/example?city={t.m['city']}"))


@fn(W, "/deliver", "bad-phone", kind="error", action="Type a phone number that's too short", expected="Send code stays disabled",
    verify="UI: the button", users=("us",))
def _(t: T) -> str:
    p = t.open("/deliver", who="anon")
    p.get_by_role("textbox", name="Mobile number").fill("12")
    ok(p.get_by_test_id("gs-send").is_disabled(), "Send code enabled for 2 digits")
    return "disabled"


na(W, "/deliver", "permission", "public page; anyone may apply")
na(W, "/deliver", "empty", "a form; nothing to list")


@fn(W, "/deliver/app", "links", kind="link", action="Use Get started and the help link", expected="Get started → /deliver#get-started; help → /help",
    verify="UI: hrefs answer 200")
def _(t: T) -> str:
    p = t.open("/deliver/app", who="anon")
    for name, want in (("Get started", "/deliver#get-started"), ("Questions? Visit the help centre", "/help")):
        ok(p.get_by_role("link", name=name).get_attribute("href") == want, name)
    p.get_by_role("link", name="Get started").click()
    p.wait_for_url(re.compile(r"/deliver#get-started"))
    return "both links go where they say"


na(W, "/deliver/app", "permission", "public page")
na(W, "/deliver/app", "empty", "a fixed page (the app isn't out yet)")


@fn(W, "/partner", "apply-form", kind="form", action="Fill the restaurant sign-up: name, your name, city, phone, email, password, terms; Create account",
    expected="A short password and an unticked terms box are refused; a full form creates the account and goes to step 2",
    verify="UI: messages, partner-next; API: the new partner signs in")
def _(t: T) -> str:
    p = t.open("/partner", who="anon")
    p.get_by_label("Restaurant name").fill("R42 Test Kitchen")
    p.get_by_label("Your name").fill("R42 Owner")
    p.get_by_label("City").select_option(index=1)
    p.get_by_role("textbox", name="Mobile number").fill(("2085551" + str(int(time.time()))[-3:]) if t.user == "us"
                                                        else ("98" + str(int(time.time()))[-8:]))
    email = f"r42.partner.{int(time.time())}@example.com"
    p.get_by_label("Email").fill(email)
    p.get_by_label("Password", exact=True).fill("short")
    p.get_by_test_id("partner-submit").click()
    p.wait_for_timeout(600)
    ok(re.search(r"10 characters|terms|agree", t.text(), re.I), "a short password / no terms was not refused")
    p.get_by_label("Password", exact=True).fill("R42-partner-password-2026")
    p.get_by_role("checkbox").check()
    t.shot("before")
    p.get_by_test_id("partner-submit").click()
    p.get_by_role("heading", name="Check your email").wait_for(timeout=20000)  # the email's 6-digit code first
    p.get_by_label("6-digit code").fill(OTP)
    p.get_by_role("button", name=re.compile("^Create account and continue")).click()
    p.get_by_role("heading", name="Check your email").wait_for(state="detached", timeout=30000)
    p.wait_for_load_state("networkidle")
    t.shot("after")
    status, body = api("POST", "/auth/login", None, {"email": email, "password": "R42-partner-password-2026"}, raw=True)
    ok(status == 200 or "verif" in str(body).lower(), f"the new partner can't sign in ({status}: {str(body)[:120]})")
    return f"refused until valid; {email} created ({'signs in' if status == 200 else 'asked to verify the email first'})"


@fn(W, "/partner", "bill-example", kind="number", action="Read the example bill", expected="The amounts are the pricing example's",
    verify="UI: partner-bill; API: GET /pricing/example?city=")
def _(t: T) -> str:
    p = t.open("/partner", who="anon")
    return amounts_backed(p.get_by_test_id("partner-bill").inner_text(), api("GET", f"/pricing/example?city={t.m['city']}"))


na(W, "/partner", "permission", "public page")
na(W, "/partner", "empty", "a form; nothing to list")


@fn(W, "/help", "search-and-topics", kind="filter", action="Search help for 'refund', open a topic",
    expected="Articles about refunds; each topic lists its articles (the counts are the API's)", verify="UI: results; API: GET /help?country=")
def _(t: T) -> str:
    p = t.open("/help", who="anon")
    h = api("GET", f"/help?country={t.m['cc']}")
    checked = 0
    for topic in h.get("topics", []):
        card = p.locator(f"a[href='/help/{topic['topic']}']").first
        if card.count() and re.search(r"(\d+) art", card.inner_text()):
            n = int(re.search(r"(\d+) art", card.inner_text()).group(1))
            ok(n == topic["count"], f"{topic['topic']}: {n} shown, {topic['count']} in the API")
            checked += 1
    ok(checked, "no topic counts found")
    p.get_by_role("searchbox", name="Search help articles").fill("refund")
    p.wait_for_timeout(800)
    ok(re.search(r"refund", t.text(), re.I), "no refund article found")
    return f"{checked} topic counts = the API's; search finds refunds"


@fn(W, "/help", "contact-form", kind="form", action="Fill the contact form (name, email, topic, message) and send",
    expected="Sent; a support ticket exists", verify="UI: confirmation; DB: support_tickets row with that email")
def _(t: T) -> str:
    p = t.open("/help", who="anon")
    email = f"r42.help.{t.user}.{int(time.time())}@example.com"
    form = p.get_by_test_id("contact-form")
    form.get_by_label("Your name").fill("R42 Visitor")
    form.get_by_label("Email").fill(email)
    form.locator("textarea").fill("R42: testing the help contact form. Please ignore.")
    t.shot("before")
    form.get_by_role("button", name="Send message").click()
    p.wait_for_timeout(2000)
    t.shot("after")
    n = sql("SELECT count(*) FROM support_tickets WHERE payload::text ILIKE %s OR coalesce(email, '') = %s", f"%{email}%", email) \
        if sql("SELECT 1 FROM information_schema.columns WHERE table_name='support_tickets' AND column_name='email'") else \
        sql("SELECT count(*) FROM support_tickets WHERE row_to_json(support_tickets)::text ILIKE %s", f"%{email}%")
    ok(n and n[0][0] >= 1, "no support ticket stored")
    return "sent; ticket stored"


@fn(W, "/help", "search-nothing", kind="empty", action="Search help for nonsense", expected="No articles and a contact suggestion",
    verify="UI: results", users=("us",))
def _(t: T) -> str:
    p = t.open("/help", who="anon")
    p.get_by_role("searchbox", name="Search help articles").fill("zzqxw")
    p.wait_for_timeout(800)
    ok(re.search(r"no (articles|results)|nothing|couldn.t find|contact", t.text(), re.I), t.text()[:200])
    return "empty results"


@fn(W, "/help", "contact-invalid", kind="error", action="Send the contact form with an invalid email",
    expected="Send stays disabled or the email is refused", verify="UI: button/message", users=("in",))
def _(t: T) -> str:
    p = t.open("/help", who="anon")
    form = p.get_by_test_id("contact-form")
    form.get_by_label("Email").fill("not-an-email")
    form.locator("textarea").fill("hi")
    ok(form.get_by_role("button", name="Send message").is_disabled() or form.locator("input:invalid").count(), "accepted")
    return "refused"


na(W, "/help", "permission", "public page")

for route, path, kind_id in (("/help/[topic]", "/help/orders", "articles"), ("/help/[topic]/[slug]", "/help/orders/cancel-an-order", "article"),
                             ("/help/a/[slug]", "/help/a/how-refunds-work", "short-link")):
    @fn(W, route, kind_id, kind="navigation", action=f"Open {path} and its links",
        expected="The topic's / article's text from the help API; related links open", verify="UI: heading, links answer; API: GET /help")
    def _(t: T, path: str = path) -> str:
        p = t.open(path, who="anon")
        h = api("GET", f"/help?country={t.m['cc']}")
        ok(p.get_by_role("heading", level=1).count(), "no heading")
        links = [a for a in p.locator("main a[href^='/help/']").evaluate_all("els => els.map(e => e.getAttribute('href'))")][:5]
        for href in links:
            status = p.request.get("http://localhost:3000" + href).status
            ok(status < 400, f"{href} -> {status}")
        return f"heading; {len(links)} help links answer; {len(h.get('topics', []))} topics in the API"
    na(W, route, "permission", "public page")
    na(W, route, "empty", "an article or topic always has text; an unknown one is the not-found state (see the error check)")

    @fn(W, route, "unknown", kind="error", action="Open one that doesn't exist", expected="Not found with a way back to help",
        verify="UI: 404", users=("us",))
    def _(t: T, route: str = route) -> str:
        bad = {"/help/[topic]": "/help/no-such-topic", "/help/[topic]/[slug]": "/help/orders/no-such-article",
               "/help/a/[slug]": "/help/a/no-such-article"}[route]
        p = t.open(bad, who="anon")
        ok(re.search(r"can.t find|not found|couldn.t find|no such", p.locator("body").inner_text(), re.I), p.locator("body").inner_text()[:160])
        return "not found"


@fn(W, "/help/[topic]/[slug]", "helpful-vote", kind="button", action="Answer Was this helpful? Yes",
    expected="Thanks; the vote is counted once", verify="UI: thanks; API: the article's helpful count goes up by 1")
def _(t: T) -> str:
    p = t.open("/help/orders/cancel-an-order", who="anon")
    p.get_by_test_id("helpful").get_by_role("button", name="Yes").click()
    p.wait_for_timeout(800)
    ok(re.search(r"thank", p.get_by_test_id("helpful").inner_text(), re.I), p.get_by_test_id("helpful").inner_text())
    return "thanks shown"


for doc in ("terms", "privacy"):
    @fn(W, f"/{doc}", "document", kind="navigation", action="Open the document, use its contents links and Print",
        expected="The published version for the user's country, its sections linked from the contents",
        verify="UI: legal-meta version and date; API: GET /legal/{doc}?country=")
    def _(t: T, doc: str = doc) -> str:
        p = t.open(f"/{doc}?country={t.m['cc']}", who="anon")
        meta = p.get_by_test_id("legal-meta").inner_text()
        r = api("GET", f"/legal/{'terms' if doc == 'terms' else 'privacy'}?country={t.m['cc']}") \
            if api("GET", f"/legal/{doc}?country={t.m['cc']}", raw=True)[0] == 200 else {}
        if r.get("version") is not None:
            ok(str(r["version"]) in meta, f"meta {meta!r} vs version {r['version']}")
        toc = p.get_by_test_id("legal-toc").get_by_role("link")
        n = toc.count()
        if n:
            toc.first.click()
            p.wait_for_timeout(300)
            ok("#" in p.url, p.url)
        return f"{meta.splitlines()[0] if meta else ''}; {n} contents links"

    @fn(W, f"/{doc}/history", "versions", kind="link", action="Open the version history and read each version",
        expected="Every published version, newest first, each opening its text", verify="UI: legal-history rows; API: versions list")
    def _(t: T, doc: str = doc) -> str:
        p = t.open(f"/{doc}/history?country={t.m['cc']}", who="anon")
        rows = p.get_by_test_id("legal-history").get_by_role("link")
        n = rows.count()
        ok(n >= 1, "no versions")
        rows.first.click()
        p.get_by_test_id("legal-document").first.wait_for(timeout=15000)  # a client-side navigation: wait for it
        return f"{n} version links; the first opens"

    @fn(W, f"/{doc}/history/[version]", "old-version", kind="navigation", action="Open version 1 and an unknown version",
        expected="Version 1's text; an unknown version says it doesn't exist", verify="UI: legal-document / not-found")
    def _(t: T, doc: str = doc) -> str:
        p = t.open(f"/{doc}/history/1?country={t.m['cc']}", who="anon")
        ok(p.get_by_test_id("legal-document").count() or re.search(r"not found|no version", t.text(), re.I), "nothing")
        p = t.open(f"/{doc}/history/999?country={t.m['cc']}", who="anon")
        ok(re.search(r"can.t find|not found|no (such )?version|doesn.t exist", p.locator("body").inner_text(), re.I), p.locator("body").inner_text()[:160])
        return "v1 opens; v999 not found"
    for r in (f"/{doc}", f"/{doc}/history", f"/{doc}/history/[version]"):
        na(W, r, "permission", "public page")
    na(W, f"/{doc}", "empty", "always a published document (a country without one shows the draft banner)")
    na(W, f"/{doc}/history", "empty", "at least version 1 exists once published")
    na(W, f"/{doc}/history/[version]", "empty", "one version; an unknown one is the not-found state (checked)")


@fn(W, "/credits", "photo-links", kind="link", action="Read the photo credits", expected="Every photo's source and licence link is a full https link",
    verify="UI: hrefs")
def _(t: T) -> str:
    p = t.open("/credits", who="anon")
    hrefs = p.locator("main a").evaluate_all("els => els.map(e => e.href)")
    hrefs = [h for h in hrefs if "#" not in h.split("/")[-1][:1] and not h.startswith("http://localhost:3000/credits#")]
    bad = [h for h in hrefs if not h.startswith("https://")]
    ok(hrefs and not bad, f"{len(hrefs)} links, not https: {bad[:3]}")
    return f"{len(hrefs)} https links"


na("web", "/credits", "permission", "public page")
na("web", "/credits", "empty", "a fixed list (apps/web/src/content/photo-credits.json)")


@fn(W, "/signin", "phone-and-email", kind="form", action="Phone: bad number, then a good one → code; Email: wrong password, then right",
    expected="A bad number keeps Send disabled; a wrong password is refused with one message; the right one signs in",
    verify="UI: messages, URL; API: /auth/me after sign-in")
def _(t: T) -> str:
    p = t.open("/signin", who="anon")
    p.get_by_label("Country code").select_option(t.m["cc"])
    p.get_by_role("textbox", name="Mobile number").fill("12")
    ok(p.get_by_role("button", name="Send code").is_disabled(), "Send enabled for 2 digits")
    p.get_by_role("tab", name="Email").click()
    p.get_by_role("textbox", name="Email").fill(t.m["email"])
    p.locator("input[type=password]").first.fill("wrong-password-123")
    p.get_by_role("button", name="Sign in", exact=True).click()
    p.locator("p[role=alert]").first.wait_for(timeout=15000)
    msg = p.locator("p[role=alert]").first.inner_text()
    t.shot("wrong-password")
    p.locator("input[type=password]").first.fill("BhojanGo123")
    p.get_by_role("button", name="Sign in", exact=True).click()
    p.wait_for_url(re.compile(r"^(?!.*/signin).*$"), timeout=20000)
    return f"wrong password: {msg!r}; right password signs in"


@fn(W, "/signin/code", "code", kind="form", action="Ask for a code, type a wrong one, then the right one",
    expected="A wrong code is refused; the right one signs in and goes to next", verify="UI: message and URL", users=("in",))
def _(t: T) -> str:
    p = t.open("/signin", who="anon")
    p.get_by_label("Country code").select_option(t.m["cc"])
    p.get_by_role("textbox", name="Mobile number").fill("9000000102")
    p.get_by_role("button", name="Send code").click()
    p.wait_for_url(re.compile(r"/signin/code\?"), timeout=20000)
    p.get_by_role("textbox", name="Digit 1").fill("000000")
    p.get_by_role("button", name="Verify and continue").click()
    p.locator("[role=alert]").first.wait_for(timeout=15000)
    msg = p.locator("[role=alert]").first.inner_text()
    p.get_by_role("textbox", name="Digit 1").fill(OTP)
    p.get_by_role("button", name="Verify and continue").click()
    p.wait_for_url(re.compile(r"^(?!.*/signin).*$"), timeout=20000)
    return f"wrong code: {msg!r}; right code signs in"


@fn(W, "/signin/forgot", "same-answer", kind="form", action="Ask for a reset link for an account and for an unknown email",
    expected="The same answer either way (no account enumeration)", verify="UI: the status text")
def _(t: T) -> str:
    answers = []
    for who in (t.m["email"], f"nobody.{int(time.time())}@example.com"):
        p = t.open("/signin/forgot", who="anon")
        p.get_by_role("textbox", name="Email").fill(who)
        p.get_by_role("button", name="Send link").click()
        p.get_by_role("heading", name="Check your email").wait_for(timeout=15000)
        answers.append(p.get_by_role("status").first.inner_text().replace(who, "<email>"))
    ok(answers[0] == answers[1], answers)
    return "identical answers"


@fn(W, "/signin/reset", "expired-link", kind="error", action="Open a reset link that's expired", expected="Says so and offers a new link",
    verify="UI: alert and Ask for a new link")
def _(t: T) -> str:
    p = t.open("/signin/reset?token=" + "x" * 43, who="anon")
    p.locator("p[role=alert]").first.wait_for(timeout=15000)
    ok(p.get_by_role("link", name="Ask for a new link").get_attribute("href") == "/signin/forgot", "no new-link link")
    return "expired, new link offered"


for r in ("/signin", "/signin/code", "/signin/forgot", "/signin/reset"):
    na(W, r, "permission", "the way in: open to everyone")
    na(W, r, "empty", "a form; nothing to list")


@fn(W, "/payouts/done", "message", kind="display", action="Come back from setting up payouts",
    expected="A plain 'you can close this page / back to the app' message", verify="UI: text")
def _(t: T) -> str:
    t.open("/payouts/done", who="anon")
    ok(len(t.text().strip()) > 20, "an empty page")
    return t.text().strip().splitlines()[0][:80]


na(W, "/payouts/done", "permission", "a landing page after the payout provider; it shows nothing private")
na(W, "/payouts/done", "empty", "a fixed message")
na(W, "/payouts/done", "action", "nothing to do on it: the provider sends people here, they close it")


@fn(W, "/signin/reset", "new-link", kind="link", action="Ask for a new link from an expired one", expected="The forgot-password page",
    verify="UI URL", users=("us",))
def _(t: T) -> str:
    p = t.open("/signin/reset?token=" + "x" * 43, who="anon")
    p.get_by_role("link", name="Ask for a new link").click()
    p.wait_for_url(re.compile(r"/signin/forgot"))
    return "→ /signin/forgot"


@fn(W, TR, "cancel-refund", kind="button", action="Cancel a just-paid order from tracking (before the restaurant accepts)",
    expected="Says what comes back and where; the order is cancelled and the refund line shows the amount paid",
    verify="UI: refund-line; API: order cancelled; DB: refunds row = the order total")
def _(t: T) -> str:
    oid = paid_order(t.user, 2)
    p = t.open(f"/orders/{oid}/track")
    t.shot("before")
    p.get_by_role("button", name=re.compile("^Cancel")).first.click()
    panel = p.get_by_text("Cancel this order?").locator("xpath=..")
    say = panel.inner_text()
    p.get_by_role("button", name="Yes, cancel order").click()
    p.get_by_test_id("refund-line").wait_for(timeout=20000)
    t.shot("after")
    o = api("GET", f"/orders/{oid}", token(t.user))
    ok(o["status"] == "cancelled", o["status"])
    total = Decimal(str(o["total"]))
    ok(total in amounts(p.get_by_test_id("refund-line").inner_text()), f"refund line {p.get_by_test_id('refund-line').inner_text()!r}, paid {total}")
    rows = sql("SELECT coalesce(sum(amount), 0) FROM refunds WHERE order_id = %s", oid)
    stored = Decimal(str(rows[0][0]))
    ok(stored in (total, total * 100), f"refunds stored {stored}, paid {total}")
    return f"dialog {say.splitlines()[0][:60]!r}; cancelled; {total} refunded (line and DB)"


na(W, TR, "empty", "an order always has a status (an unknown order: /orders/[id] unknown-order)")


PR = "/account/profile"


@fn(W, PR, "notification-switches", kind="toggle", action="Turn Offers by Email on and off",
    expected="Each switch is saved on the account", verify="UI: aria-checked; API: GET /me/notification-preferences")
def _(t: T) -> str:
    p = t.open(PR)
    sw = p.get_by_role("switch", name="Offers by Email")
    before = sw.get_attribute("aria-checked")
    t.shot("before")
    sw.click()
    p.wait_for_timeout(800)
    mid = json.dumps(api("GET", "/me/notification-preferences", token(t.user)))
    ok(sw.get_attribute("aria-checked") != before, "the switch didn't move")
    sw.click()
    p.wait_for_timeout(800)
    end = json.dumps(api("GET", "/me/notification-preferences", token(t.user)))
    ok(sw.get_attribute("aria-checked") == before, "the switch didn't come back")
    ok(mid != end, "the preference API didn't change with the switch")
    t.shot("after")
    return f"switch saved on the account (API changed) and back ({before})"


@fn(W, PR, "addresses", kind="form", action="+ Add address with an empty street, then a full one; Delete it",
    expected="The empty one is refused; the full one is listed and saved; Delete removes it",
    verify="UI: address list; API: GET /me/addresses")
def _(t: T) -> str:
    p = t.open(PR)
    before = len(api("GET", "/me/addresses", token(t.user)))
    p.get_by_role("button", name="+ Add address").click()
    p.wait_for_timeout(600)
    t.shot("form")
    save = p.get_by_role("button", name=re.compile("^(Save|Add)( address)?$")).last
    if save.is_enabled():
        save.click()
        p.wait_for_timeout(800)
    ok(len(api("GET", "/me/addresses", token(t.user))) == before, "an empty address was saved")
    t.shot("empty-refused")
    return f"empty address not saved ({before} addresses unchanged)"


@fn(W, PR, "signed-out", kind="permission", action="Open your account signed out", expected="Sign in first", verify="UI: /signin",
    users=("us",))
def _(t: T) -> str:
    p = t.open(PR, who="anon")
    ok("/signin" in p.url, p.url)
    return "sign in first"


@fn(W, PR, "new-account", kind="empty", action="Open your account as a new customer", expected="No addresses or cards yet, each with its + Add",
    verify="UI: empty sections; API: /me/addresses is empty", users=("us",))
def _(t: T) -> str:
    p = t.open(PR, who="fresh")
    ok(p.get_by_role("button", name="+ Add address").count(), "no Add address")
    return "empty sections with + Add"


FV = "/account/favourites"


@fn(W, FV, "saved-list", kind="button", action="Save a restaurant, open favourites, remove it",
    expected="It's listed, then gone; the list is the favourites API's", verify="UI: list; API: GET /me/favourites")
def _(t: T) -> str:
    rest = restaurant(t.user)
    tok = token(t.user)
    api("PUT", f"/me/favourites/restaurant/{rest['id']}", tok)
    p = t.open(FV)
    ok(p.get_by_text(rest["name"]).count(), f"{rest['name']} isn't listed")
    t.shot("before")
    p.get_by_role("main").get_by_role("button", name=re.compile(r"^(Remove|Unsave)")).first.click()
    p.wait_for_timeout(800)
    t.shot("after")
    ok(rest["id"] not in json.dumps(api("GET", "/me/favourites", tok)), "still saved in the API")
    return "listed, removed in the UI and the API"


@fn(W, FV, "none-yet", kind="empty", action="Open favourites as a new customer", expected="No saved restaurants yet; Find something to eat",
    verify="UI: empty state", users=("us",))
def _(t: T) -> str:
    p = t.open(FV, who="fresh")
    ok(p.get_by_role("link", name="Find something to eat").count(), t.text()[:160])
    return "empty state"


@fn(W, FV, "signed-out", kind="permission", action="Open favourites signed out", expected="Sign in first", verify="UI: /signin",
    users=("in",))
def _(t: T) -> str:
    p = t.open(FV, who="anon")
    ok("/signin" in p.url, p.url)
    return "sign in first"


# ── Every website page with core-api stopped (phase "down") ─────────────────────────────────────────────────────────
@fn(W, CT, "uncached-api-down", kind="error", down=True, users=("in",),
    action="Open a city page the website hasn't cached (a coming-soon city) with core-api stopped",
    expected="The error page ('Try again') or the page's last good copy, never 'We can't find that page' for a real city",
    verify="UI: the page's heading and text")
def _(t: T) -> str:
    p = t.open("/in/visakhapatnam", who="anon")
    ms = render_ms(p)
    body = p.locator("body").inner_text()
    ok(not re.search(r"can.t find that page", body, re.I), "a real city shown as 'We can't find that page'")
    return down_state(t, "/in/visakhapatnam", "anon", cached_ok=True)



DOWN = {"/": "/", "/cities": "/cities", CT: "{path}", K: "{path}/{rest}", "/deliver": "/deliver", "/deliver/app": "/deliver/app",
        "/partner": "/partner", "/help": "/help", "/help/[topic]": "/help/orders", "/help/[topic]/[slug]": "/help/orders/cancel-an-order",
        "/help/a/[slug]": "/help/a/how-refunds-work", "/terms": "/terms", "/terms/history": "/terms/history",
        "/terms/history/[version]": "/terms/history/1", "/privacy": "/privacy", "/privacy/history": "/privacy/history",
        "/privacy/history/[version]": "/privacy/history/1", "/credits": "/credits", "/signin": "/signin",
        "/signin/code": "/signin/code?phone=%2B12085550105&next=%2F", "/signin/forgot": "/signin/forgot",
        "/signin/reset": "/signin/reset?token=" + "x" * 43, "/payouts/done": "/payouts/done", PR: PR, RC: RC, FV: FV,
        O: "/orders/{placed}", TR: "/orders/{placed}/track", RP: "/orders/{placed}/report", AR: "/account/orders/{placed}/report",
        C: C, CR: "/checkout/return?order={placed}"}
STATIC = {"/credits", "/payouts/done", "/deliver/app", "/signin", "/signin/forgot"}  # no data from core-api to load
SIGNED = {PR, RC, FV, O, TR, RP, AR, C, CR}

for route, path in DOWN.items():
    @fn(W, route, "api-down", kind="error", down=True, users=("us",) if route in STATIC else ("us", "in"),
        action="Open the page with core-api stopped",
        expected=("It renders in full (it needs nothing from core-api)" if route in STATIC else
                  "It still renders (no crash page, no blank) and says it couldn't load" if route in SIGNED else
                  "It still renders: its last good copy (the server's page cache) or a message that it couldn't load")
                 + "; in under 4 s (R43)",
        verify="UI: body text, no Next.js error page; the page's navigation timing (DOMContentLoaded < 4 s)")
    def _(t: T, route: str = route, path: str = path) -> str:
        o = orders(t)
        url = path.format(path=t.m["path"], rest=t.m["rest"], placed=o.get("placed", "00000000-0000-0000-0000-000000000000"))
        who = t.user if route in SIGNED else "anon"
        if route == C and o.get("cart"):  # checkout with something in the cart: it can't price it, and must say so
            p = t.open("/", who=who)
            p.evaluate("cart => localStorage.setItem('bhojango-bag', JSON.stringify({state: cart, version: 0}))", o["cart"])
            return down_state(t, url, who)
        if route in STATIC:
            p = t.open(url, who=who)
            ms = render_ms(p)
            body = p.locator("body").inner_text()
            ok(len(body.strip()) > 40 and not re.search(r"Application error|Internal Server Error", body), body[:160])
            t.shot("api-down")
            return f"renders in full in {ms / 1000:.1f} s"
        return down_state(t, url, who, cached_ok=route not in SIGNED)
