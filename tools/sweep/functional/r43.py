"""R43: menu editing, checked where customers and admins see it (website, admin console), as the US and India users.

* a menu change (price) reaches the restaurant page: measured, limit 60 s;
* a new dish, then renamed, is found by the website's dish search; a deleted one isn't;
* a dish outside its hours shows them and "Later" (no Add); spice marks;
* the held price: the restaurant raises the price while the customer is at checkout; Pay charges the quoted price;
* after the hold: "Get a fresh price" re-prices the cart and says "Price changed: <dish> <old> → <new>" above Pay;
* admin: the restaurant's menu history equals the API's (who, when, old → new).

Each function adds its own dish to the market's restaurant (as the restaurant's partner, over the API) and deletes it
afterwards, so the other functions see the seed menu. Times are measured by the runner's clock."""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from framework import MARKET, T, api, app_fn, fn, money, ok, sql, token
from web import last_quote, quote_capture, restaurant

W, A = "web", "admin"
K = "/[country]/[city]/[kitchen]"
C = "/checkout"
P = "/partners"
PROPAGATION_LIMIT = 60.0
TIMES: dict[str, float] = {}  # measured propagation, per market (the report prints them)


def price_text(market: str, amount: Decimal) -> str:
    """How the menu shows a price: "$12.50", "₹250" (whole rupees without decimals)."""
    m = MARKET[market]
    return f"{m['cur']}{amount:,.2f}" if market == "us" else f"{m['cur']}{int(amount):,}"


class Dish:
    """A dish of the function's own on the market's restaurant: added, changed and deleted by its partner."""

    def __init__(self, market: str, price: str, **more: object) -> None:
        self.market, self.tok = market, token(MARKET[market]["partner"])
        self.rid = restaurant(market)["id"]
        self.name = f"R43 {('Bowl' if market == 'us' else 'Thali')} {uuid.uuid4().hex[:5]}"
        self.item = api("POST", f"/restaurants/{self.rid}/menu-items", self.tok,
                        {"name": self.name, "price": price, "category": "R43", "description": "Round 43 check", **more})
        self.id = self.item["id"]

    def put(self, **body: object) -> dict:
        return api("PUT", f"/restaurants/{self.rid}/menu-items/{self.id}", self.tok, body)

    def delete(self) -> None:
        api("DELETE", f"/restaurants/{self.rid}/menu-items/{self.id}", self.tok, raw=True)

    def __enter__(self) -> "Dish":
        return self

    def __exit__(self, *_: object) -> None:
        self.delete()


def open_kitchen(t: T) -> object:
    p = t.open(f"{t.m['path']}/{t.m['rest']}")
    p.evaluate("() => { for (const k of Object.keys(localStorage)) if (/bag|cart/i.test(k)) localStorage.removeItem(k); }")
    p.reload(wait_until="networkidle")
    return p


def dish_row(p: object, name: str) -> object:
    return p.get_by_role("main").locator("div.flex.gap-4", has=p.get_by_text(name, exact=True)).first  # type: ignore[attr-defined]


@fn(W, K, "menu-change-reaches-page", kind="number",
    action="The restaurant changes a dish's price (BhojanGo Kitchen's API call); the customer reloads the restaurant page",
    expected="The new price shows within 60 s (measured); the menu API says the same price",
    verify="UI: the dish's price on the page, reloaded every 2 s; API: GET /restaurants/{id}/menu; the time from the change")
def _(t: T) -> str:
    base = Decimal("12.50") if t.user == "us" else Decimal("250")
    new = Decimal("13.75") if t.user == "us" else Decimal("280")
    with Dish(t.user, str(base)) as d:
        p = open_kitchen(t)
        row = dish_row(p, d.name)
        ok(price_text(t.user, base) in row.inner_text(), f"before: {row.inner_text()[:80]!r}")
        t.shot("before")
        d.put(price=str(new))
        start = time.monotonic()
        seen = None
        while time.monotonic() - start < PROPAGATION_LIMIT + 5:
            p.reload(wait_until="networkidle")
            if price_text(t.user, new) in dish_row(p, d.name).inner_text():
                seen = time.monotonic() - start
                break
            p.wait_for_timeout(2000)
        ok(seen is not None, f"the new price {price_text(t.user, new)} didn't show in {PROPAGATION_LIMIT:.0f} s")
        t.shot("after")
        menu = api("GET", f"/restaurants/{d.rid}/menu")
        item = next(i for c in menu["categories"] for i in c["items"] if i["id"] == d.id) if any(
            i["id"] == d.id for c in menu["categories"] for i in c["items"]) else next(i for i in menu["uncategorized_items"] if i["id"] == d.id)
        ok(Decimal(str(item["price"])) == new, f"menu API price {item['price']} != {new}")
        TIMES[t.user] = round(seen, 1)
        ok(seen <= PROPAGATION_LIMIT, f"{seen:.1f} s > {PROPAGATION_LIMIT:.0f} s")
        return f"{price_text(t.user, base)} → {price_text(t.user, new)} on the page {seen:.1f} s after the change (limit 60 s); API agrees"


@fn(W, K, "dish-search-new-renamed", kind="filter",
    action="Add a dish, search the restaurant's menu for it; rename it and search the new name; delete it and search again",
    expected="Found by its name, then by its new name (not the old); not found once deleted",
    verify="UI: the menu search results; API: GET /discover/search (dishes) for the city")
def _(t: T) -> str:
    d = Dish(t.user, "11.00" if t.user == "us" else "180")
    try:
        def search(word: str) -> list[str]:
            """The dish rows the menu search shows (its "nothing matches" note repeats the words: not a result)."""
            p = open_kitchen(t)
            box = p.get_by_role("searchbox").first
            box.fill(word)
            p.wait_for_timeout(600)
            return [x.split(chr(10))[0] for x in p.get_by_role("main").locator("b.text-h3").all_inner_texts()]

        def api_hits(word: str) -> list[str]:
            to = MARKET[t.user]["to"]
            return [x["name"] for x in api("GET", f"/discover/search?q={word.replace(' ', '%20')}&lat={to['lat']}&lng={to['lng']}")["dishes"]]

        ok(search(d.name) == [d.name], f"{d.name} not found on the menu")
        ok(d.name in api_hits(d.name), f"{d.name} not in /discover/search")
        t.shot("found")
        renamed = d.name.replace("R43", "R43 Special")
        d.put(name=renamed)
        ok(search(renamed) == [renamed], f"renamed {renamed} not found")
        ok(search(d.name) == [], f"the old name {d.name} still finds it")
        ok(renamed in api_hits(renamed) and d.name not in api_hits(d.name.split()[-1]), "search API still has the old name")
        t.shot("renamed")
        d.delete()
        ok(search(renamed) == [], "a deleted dish still found on the menu")
        ok(api_hits(renamed) == [], "a deleted dish still in /discover/search")
        t.shot("deleted")
        return f"new dish found; renamed found by its new name only; deleted: gone (menu search and /discover/search)"
    finally:
        d.delete()


@fn(W, K, "dish-hours-and-spice", kind="display",
    action="A dish served only at another time of day, with spice 'Medium'; open the restaurant page",
    expected="The dish shows 'Served <from> – <until>' in the restaurant's clock and 'Later' instead of Add; '🌶🌶 Medium'",
    verify="UI: the dish row; API: the menu's schedule, available_now, spice_level; the quote refuses it")
def _(t: T) -> str:
    tz = ZoneInfo(t.m["tz"])
    h = (datetime.now(tz).hour + 3) % 24
    frm, until = f"{h:02d}:00", f"{(h + 2) % 24:02d}:00"
    with Dish(t.user, "9.00" if t.user == "us" else "150", spice_level=2, available_from=frm, available_until=until) as d:
        menu = api("GET", f"/restaurants/{d.rid}/menu")
        item = next(i for i in [*menu["uncategorized_items"], *(x for c in menu["categories"] for x in c["items"])] if i["id"] == d.id)
        ok(item["available_now"] is False and item["schedule"] == {"from": frm, "until": until} and item["spice_level"] == 2, item)
        p = open_kitchen(t)
        row = dish_row(p, d.name)
        text = row.inner_text()
        clock = lambda hm: (f"{int(hm[:2]) % 12 or 12}:{hm[3:]}")  # noqa: E731 - "7:00" (am/pm per locale)
        ok(re.search(rf"Served {clock(frm)}\s?[ap]m – {clock(until)}\s?[ap]m", text, re.I), f"hours not shown: {text[:160]!r}")
        ok("Later" in text and row.get_by_role("button", name=f"Add {d.name}").count() == 0, "an Add button outside its hours")
        ok(re.search(r"🌶🌶 medium", text, re.I), f"no spice mark: {text[:160]!r}")  # a caption: shown upper-case
        t.shot("later")
        q = api("POST", "/pricing/quote", token(t.user), {"restaurant_id": d.rid, "items": [{"menu_item_id": d.id, "quantity": 5}],
                                                         "deliver_to": t.m["to"]}, raw=True)
        ok(q[0] == 422 and "is served" in str(q[1]), f"the quote took a dish outside its hours: {q}")
        return f"'Served {frm}–{until}' + 'Later' (no Add), '🌶🌶 Medium'; the quote refuses it (422)"


def cart_with(t: T, d: Dish, qty: int) -> object:
    p = open_kitchen(t)
    p.get_by_role("button", name=f"Add {d.name}").first.click()
    for _ in range(qty - 1):
        p.get_by_role("main").get_by_role("button", name=f"One more {d.name}").first.click()
    return p


@fn(W, C, "held-price-at-pay", kind="number",
    action="At checkout (price held), the restaurant raises the dish's price; then Pay",
    expected="The order is charged the held (quoted) price, not the new one",
    verify="UI: Pay amount; API: the quote the page received, GET /orders/{id}; DB: orders.total, the order's item price")
def _(t: T) -> str:
    base, raised = (Decimal("10.00"), Decimal("12.00")) if t.user == "us" else (Decimal("200"), Decimal("240"))
    with Dish(t.user, str(base)) as d:
        cart_with(t, d, 2)
        got = quote_capture(t)
        p = t.page
        p.goto("http://localhost:3000/checkout", wait_until="networkidle")
        q = last_quote(t, got)
        line = next(i for i in q["items"] if i["menu_item_id"] == d.id)
        ok(Decimal(line["unit_price"]) == base, f"quote unit price {line['unit_price']} != {base}")
        t.shot("before")
        d.put(price=str(raised))
        p.get_by_role("button", name=re.compile(r"^Pay ")).first.click()
        p.get_by_role("dialog", name="Pay (test mode)").get_by_role("button", name=re.compile("^Approve")).click()
        p.wait_for_url(re.compile(r"/orders/[0-9a-f-]{36}/track$"), timeout=40000)
        oid = p.url.rstrip("/").split("/")[-2]
        t.shot("after")
        o = api("GET", f"/orders/{oid}", token(t.user))
        ok(Decimal(str(o["total"])) == Decimal(str(q["total"])), f"order total {o['total']} != the held quote {q['total']}")
        it = next(i for i in o["items"] if i["menu_item_id"] == d.id)
        ok(Decimal(str(it["unit_price"])) == base, f"order charged {it['unit_price']} a dish, not the held {base}")
        row = sql("SELECT total FROM orders WHERE id = %s", oid)[0]
        ok(Decimal(str(row[0])) == Decimal(str(q["total"])), f"DB total {row[0]}")
        return f"price raised {base} → {raised} during the hold; order {oid[:8]} charged the held {base} a dish, total {q['total']} = quote"


@fn(W, C, "price-changed-after-hold", kind="number",
    action="At checkout, the restaurant raises the price; the 10-minute hold runs out (browser clock moved on); Get a fresh price",
    expected="The cart is re-priced and says 'Price changed: <dish> <old> → <new>' above Pay; Pay = the new quote's total",
    verify="UI: the notice, the Pay amount; API: the old and new quotes the page received (items' unit_price)")
def _(t: T) -> str:
    base, raised = (Decimal("10.00"), Decimal("12.00")) if t.user == "us" else (Decimal("200"), Decimal("240"))
    with Dish(t.user, str(base)) as d:
        p = open_kitchen(t)
        p.clock.install()
        p.reload(wait_until="networkidle")
        p.get_by_role("button", name=f"Add {d.name}").first.click()
        p.get_by_role("main").get_by_role("button", name=f"One more {d.name}").first.click()
        got = quote_capture(t)
        p.goto("http://localhost:3000/checkout", wait_until="networkidle")
        q1 = last_quote(t, got)
        ok(Decimal(next(i for i in q1["items"] if i["menu_item_id"] == d.id)["unit_price"]) == base, "first quote")
        ok(p.get_by_test_id("price-changed").count() == 0, "a price-changed note before any change")
        t.shot("held")
        d.put(price=str(raised))
        p.clock.fast_forward("10:05")
        fresh = p.get_by_role("button", name=re.compile("fresh price", re.I)).first
        fresh.wait_for(timeout=15000)
        t.shot("hold-over")
        p.clock.set_system_time(datetime.now())  # back to now: the new quote is held from the server's clock
        fresh.click()
        for _ in range(40):
            p.wait_for_timeout(250)
            if got and got[-1]["quote_id"] != q1["quote_id"]:
                break
        q2 = got[-1]
        ok(q2["quote_id"] != q1["quote_id"], "no new quote after Get a fresh price")
        ok(Decimal(next(i for i in q2["items"] if i["menu_item_id"] == d.id)["unit_price"]) == raised, "the new quote's price")
        note = p.get_by_test_id("price-changed").first
        note.wait_for(timeout=10000)
        text = " ".join(note.inner_text().split())
        old_s, new_s = price_text(t.user, base), price_text(t.user, raised)
        ok(text == f"Price changed: {d.name} {old_s} → {new_s}", f"note {text!r}")
        pay = p.get_by_role("button", name=re.compile(r"^Pay ")).first.inner_text()
        ok(money(pay) == Decimal(str(q2["total"])), f"Pay {pay!r} != the new quote {q2['total']}")
        t.shot("price-changed")
        return f"'{text}'; Pay {q2['total']} = the new quote (was {q1['total']})"


@fn(A, P, "menu-history", kind="number",
    action="Partners → Restaurants → the market's restaurant: read Menu history after a dish's price change",
    expected="The newest rows are the dish's change: who (the partner's email), when (date and time), Price old → new; as the API says",
    verify="UI: the Menu history table; API: GET /restaurants/{id}/menu/history", users=("us", "in"))
def _(t: T) -> str:
    admin = "cm_us" if t.user == "us" else "cm_in"
    base, new = ("8.00", "8.50") if t.user == "us" else ("120", "130")
    with Dish(t.user, base) as d:
        d.put(price=new)
        h = api("GET", f"/restaurants/{d.rid}/menu/history?limit=30", token(admin))["changes"]
        top = h[0]
        ok(top["name"] == d.name and top["action"] == "changed" and top["who"] == MARKET[t.user]["partner"], top)
        ch = next(c for c in top["changes"] if c["field"] == "price")
        p = t.open(f"/partners?scope={t.m['city']}", who=admin)
        p.get_by_role("button", name=restaurant(t.user)["name"]).first.click()
        rows = p.get_by_test_id("menu-history-row")
        rows.first.wait_for(timeout=20000)
        first = " ".join(rows.first.inner_text().split())
        cur = MARKET[t.user]["cur"]
        ok(d.name in first and MARKET[t.user]["partner"] in first, f"first row {first[:160]!r}")
        ok(re.search(rf"Price: {re.escape(cur)}{Decimal(ch['old']):,.2f} → {re.escape(cur)}{Decimal(ch['new']):,.2f}", first), f"price change not shown: {first!r}")
        at = datetime.fromisoformat(top["at"]).astimezone(ZoneInfo(t.m["tz"]))  # shown in the restaurant's city clock
        want = f"{at:%b} {at.day}, {at.year}, {at.hour % 12 or 12}:{at:%M} {'AM' if at.hour < 12 else 'PM'}"
        ok(want in first.replace("\u202f", " "), f"the row's date and time {want!r} (in {t.m['tz']}) not in {first[:80]!r}")
        ok(rows.count() == min(30, len(h)), f"{rows.count()} rows shown, the API's first page has {min(30, len(h))}")
        t.shot("history")
        return f"{rows.count()} rows = API; newest: {d.name} by {top['who']}, Price {ch['old']} → {ch['new']}"


# R43 (brief item 5): the full US path on real Stripe test mode. Stripe's keys live only on the Railway QA runner
# (sealed), so it runs there (tools/stripe_e2e/test_r43_full_path.py, the "Payments e2e (Stripe test mode)" check);
# the report reads its result line from that run's log.
app_fn(W, C, "stripe-full-path", kind="number",
       action="Menu → cart → checkout → Stripe Payment Element, card 4242 → tracking to delivered → receipt → refund one dish",
       expected="Placed by Stripe's webhook; PaymentIntent and charge = the order's total, captured; every status in order; "
                "receipt = Stripe's amount; Stripe's Refund = the stored refund; payment row partially refunded",
       verify="Stripe API (PaymentIntent, Charge, Refund) vs API (order, refunds) and DB (payment_intents)",
       flow="stripe-r43_full_us_path_on_stripe", users=("us",))
