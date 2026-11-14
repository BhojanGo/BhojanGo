"""Playwright end-to-end run of the admin console (P21) against `make dev`.

Runs in the Playwright image on the compose network (tools/admin/e2e.sh). The
browser opens the console at localhost:3001 (forwarded to the admin service,
which proxies /api to core_api and realtime). An order is placed through the
API first so Operations and Support have something live. Screenshots go to
docs/screenshots/admin.
"""
import os
import re
import socket
import threading
import uuid
from datetime import date, timedelta
from decimal import Decimal

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
CORE = "http://core-api:8001/api/v1"
PW = "BhojanGoAdmin1"
results: list[tuple[str, bool, str]] = []


def forward(port: int, target: tuple[str, int]) -> None:
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(64)

    def pipe(a: socket.socket, b: socket.socket) -> None:
        try:
            while data := a.recv(65536):
                b.sendall(data)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def serve() -> None:
        while True:
            c, _ = srv.accept()
            u = socket.create_connection(target)
            threading.Thread(target=pipe, args=(c, u), daemon=True).start()
            threading.Thread(target=pipe, args=(u, c), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()


def check(name: str, fn) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
        results.append((name, True, ""))
        print("PASS", name, flush=True)
    except Exception as e:  # noqa: BLE001
        results.append((name, False, str(e)[:300]))
        print("FAIL", name, str(e)[:300], flush=True)


def _ok(v: bool) -> None:
    assert v


def fail(msg: str):  # type: ignore[no-untyped-def]
    raise AssertionError(msg)


forward(3001, ("admin", 3000))
BASE = "http://localhost:3001"

with sync_playwright() as p:
    b = p.chromium.launch()
    api = p.request.new_context()

    # A paid order at Spice Route Kitchen, so there's something live.
    _tokens: dict[str, dict] = {}

    def token(email: str, pw: str = "BhojanGo123") -> dict:
        """Signed in once per run (sign-in is limited to 10 a minute; tokens last 15)."""
        if email not in _tokens:
            for _ in range(20):
                r = api.post(f"{CORE}/auth/login", data={"email": email, "password": pw})
                if r.status != 429:
                    break
                page_wait(6000)
            _tokens[email] = {"Authorization": f"Bearer {r.json()['access_token']}"}
        return _tokens[email]

    def page_wait(ms: int) -> None:
        import time

        time.sleep(ms / 1000)

    cust = token("customer3.hyd@example.com")
    rest = next(r for r in api.get(f"{CORE}/restaurants?limit=50").json()["items"] if r["name"] == "Spice Route Kitchen")
    item = next(i for c in api.get(f"{CORE}/restaurants/{rest['id']}/menu").json()["categories"] for i in c["items"] if i["name"] == "Veg Dum Biryani")
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = api.post(f"{CORE}/pricing/quote", headers=cust, data={"restaurant_id": rest["id"], "items": cart, "deliver_to": {"lat": 17.4307, "lng": 78.4072}}).json()
    order = api.post(f"{CORE}/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, data={
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q["token"],
        "delivery_address": {"street": "12-2-41, Road No. 36", "city": "Hyderabad", "state": "Telangana", "zip": "500033", "country": "IN"}}).json()
    intent = api.post(f"{CORE}/payments/initiate", headers=cust, data={"order_id": order["id"], "payment_method_type": "upi"}).json()
    api.post(f"{CORE}/payments/fake/{intent['payment_intent_id']}/complete", headers=cust, data={"outcome": "succeeded"})
    code = "#" + order["id"].replace("-", "")[:6].upper()

    def sign_in(page, email: str) -> None:  # type: ignore[no-untyped-def]
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.locator("input[type=email]").fill(email)
        page.locator("input[type=password]").fill(PW)
        page.get_by_role("button", name=re.compile("sign in", re.I)).click()
        page.wait_for_url("**/overview**", timeout=20000)

    page = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(page, "admin@example.com")
    check("overview, all countries: each country in its own money, side by side, needs action", lambda: (
        expect(page.get_by_role("heading", name="All countries", exact=True)).to_be_visible(timeout=15000),
        expect(page.get_by_role("region", name="India")).to_be_visible(),
        expect(page.get_by_role("region", name="United States")).to_be_visible(),
        expect(page.get_by_role("region", name="Side by side")).to_be_visible(),
        expect(page.get_by_text(re.compile("kitchen.* applying to join")).first).to_be_visible()))
    page.screenshot(path=f"{OUT}/01-all-countries.png", full_page=True)

    page.get_by_role("link", name="Open India").click()
    check("country page: states and cities, settings, scope bar shows the state chips", lambda: (
        expect(page.get_by_role("heading", name="India", level=1)).to_be_visible(timeout=15000),
        expect(page.get_by_role("link", name="Hyderabad", exact=True).first).to_be_visible(),
        expect(page.get_by_role("navigation", name="State and city in India")).to_be_visible(),
        expect(page.get_by_role("region", name="India settings")).to_be_visible()))
    page.screenshot(path=f"{OUT}/02-country.png", full_page=True)

    page.get_by_role("link", name=re.compile("^Telangana")).first.click()
    check("state chip keeps the section and narrows the scope", lambda: (page.wait_for_url("**/overview?scope=IN-TG"), True))

    page.goto(f"{BASE}/operations?scope=IN-TG-HYD&tab=live", wait_until="networkidle")
    check("operations: the new order is live, the scope bar is on the page", lambda: (
        expect(page.get_by_role("cell", name=code)).to_be_visible(timeout=20000),
        expect(page.get_by_role("navigation", name="Country")).to_be_visible()))
    page.screenshot(path=f"{OUT}/03-live-orders.png", full_page=True)

    page.goto(f"{BASE}/operations?scope=IN-TG-HYD&tab=dispatch", wait_until="networkidle")
    check("dispatch map: OpenStreetMap with riders and the waiting list", lambda: (
        expect(page.get_by_role("img", name="Dispatch map")).to_be_visible(timeout=20000),
        expect(page.locator(".leaflet-tile-pane")).to_have_count(1),
        expect(page.get_by_role("region", name="Waiting for a rider")).to_be_visible()))
    page.screenshot(path=f"{OUT}/04-dispatch-map.png")

    page.goto(f"{BASE}/operations?scope=IN-TG-HYD&tab=support", wait_until="networkidle")
    page.get_by_label("Find an order").fill(code)
    page.get_by_role("button", name=re.compile(re.escape(code))).click()
    check("support: order, timeline and items to refund", lambda: (
        expect(page.get_by_role("region", name=f"Order {code}")).to_be_visible(timeout=15000),
        expect(page.get_by_label("Order timeline")).to_be_visible()))
    page.get_by_label("How many Veg Dum Biryani to refund").fill("1")
    page.get_by_label("Reason").select_option("missing_item")
    check("support: refund is charged to the kitchen for a missing item", lambda: expect(page.get_by_text(re.compile("charged to the kitchen's payout"))).to_be_visible())
    page.screenshot(path=f"{OUT}/05-support-refund.png", full_page=True)
    page.get_by_role("button", name="Refund to original payment").click()
    check("support: refund by item goes through", lambda: expect(page.get_by_role("status")).to_contain_text("Refunded", timeout=20000))

    # The kitchen asks for a call back from its tablet (B3): a ticket in the support console.
    partner = token("partner.hyd@example.com")
    api.post(f"{CORE}/restaurants/{rest['id']}/callback", headers=partner, data={"topic": "payout", "note": "Last week's payout looks short"})
    page.goto(f"{BASE}/operations?scope=IN-TG-HYD&tab=support", wait_until="networkidle")
    tickets = page.get_by_role("region", name="Tickets")
    check("support: the kitchen's call-back request is an open ticket", lambda: (
        expect(tickets.get_by_role("button", name=re.compile("Call back · Spice Route Kitchen"))).to_be_visible(timeout=20000),
        expect(tickets.get_by_text(re.compile("Last week's payout looks short")).first).to_be_visible()))
    tickets.get_by_role("button", name=re.compile("Call back · Spice Route Kitchen")).first.click()
    case = page.get_by_role("region", name="Call back · Spice Route Kitchen")
    check("support: the ticket shows who to call and what about", lambda: (
        expect(case.get_by_role("link", name=re.compile(r"^\+\d+"))).to_be_visible(timeout=10000),
        expect(case.get_by_text("a payout")).to_be_visible()))
    case.get_by_label("What did you do?").fill("Called the kitchen; the payout covered six days, explained the cut-off")
    page.screenshot(path=f"{OUT}/05b-support-callback.png", full_page=True)
    case.get_by_role("button", name="Mark resolved").click()
    check("support: resolved tickets leave the open queue", lambda: (
        expect(tickets.get_by_role("button", name=re.compile("Call back · Spice Route Kitchen"))).to_have_count(0, timeout=15000),
        tickets.get_by_role("button", name="Show resolved").click(),
        expect(tickets.get_by_role("button", name=re.compile("Call back · Spice Route Kitchen")).first).to_be_visible(timeout=15000)))

    page.goto(f"{BASE}/partners?scope=IN-TG-HYD&tab=applications", wait_until="networkidle")
    page.get_by_role("button", name=re.compile("Kesar Kitchen")).click()
    check("partners: an application with its five steps and the licence", lambda: (
        expect(page.get_by_role("region", name="Application · Kesar Kitchen")).to_be_visible(timeout=15000),
        expect(page.get_by_text("FSSAI licence").first).to_be_visible(),
        expect(page.get_by_role("button", name="Approve and go live")).to_be_visible()))
    page.screenshot(path=f"{OUT}/06-application.png", full_page=True)

    page.goto(f"{BASE}/partners?scope=IN&tab=riders", wait_until="networkidle")
    check("partners: rider documents by country", lambda: expect(page.get_by_text(re.compile("reviewed by country"))).to_be_visible())

    page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=delivery_fee", wait_until="networkidle")
    page.get_by_role("region", name="Rules").get_by_test_id("row-source").first.click()
    check("pricing & rules: a rule's settings, where it comes from, history", lambda: (
        expect(page.get_by_role("heading", name="History")).to_be_visible(timeout=15000),
        expect(page.get_by_role("button", name=re.compile("^Approvals"))).to_be_visible()))
    page.screenshot(path=f"{OUT}/07-pricing-rules.png", full_page=True)
    page.get_by_role("link", name="Price simulator", exact=True).click()
    check("price simulator opens from Pricing & Rules", lambda: expect(page.get_by_role("heading", name=re.compile("Price simulator"))).to_be_visible(timeout=15000))

    # Rule approval (P22): a country manager changes a money rule; a second admin approves it.
    cm = token("cm.in@example.com", PW)
    live = next(r for r in api.get(f"{CORE}/rules", headers=cm, params={"family": "delivery_fee"}).json()
                if r["status"] == "published" and r["market_scope"] == "IN-TG-HYD" and not (r.get("effective_to")))
    draft = api.post(f"{CORE}/rules/{live['id']}/versions", headers=cm, data={"params": live["params"]}).json()
    submitted = api.post(f"{CORE}/rules/{draft['id']}/submit", headers=cm).json()
    check("rule approval: a money rule waits for a second admin", lambda: _ok(submitted["status"] == "pending_approval"))
    page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=approvals", wait_until="networkidle")
    queue = page.get_by_role("region", name="Rules")
    queue.get_by_role("button", name=re.compile(re.escape(live["name"] or "distance slabs"))).first.click()
    detail = page.get_by_role("region", name=re.compile("^Rule · "))
    expect(detail.get_by_role("button", name="Approve and schedule")).to_be_visible(timeout=15000)
    page.screenshot(path=f"{OUT}/07c-rule-approval.png", full_page=True)
    detail.get_by_label("Comment").fill("Checked against the simulator")
    detail.get_by_role("button", name="Approve and schedule").click()
    check("rule approval: approved by the second admin, the new version is live", lambda: (
        expect(page.get_by_text("Nothing waiting for you.")).to_be_visible(timeout=15000),
        _ok(api.get(f"{CORE}/rules/{draft['id']}", headers=cm).json()["status"] == "published")))

    # A kitchen's own offer is live without approval; an admin pauses it (B4).
    partner_h = token("partner.hyd@example.com")
    offer_name = f"Rs 40 off, admin pause {uuid.uuid4().hex[:4]}"
    for o in api.get(f"{CORE}/restaurants/{rest['id']}/offers", headers=partner_h).json():  # left from an earlier run
        if o["name"].startswith("Rs 40 off, admin pause"):
            api.post(f"{CORE}/restaurants/{rest['id']}/offers/{o['id']}/end", headers=partner_h)
    offers = api.post(f"{CORE}/restaurants/{rest['id']}/offers", headers=partner_h, data={
        "template": "flat_off", "name": offer_name, "amount": "40", "weekly_cap": "2000"}).json()
    offer = next(o for o in offers if o["name"] == offer_name)
    page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=promotion", wait_until="networkidle")
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile(re.escape(offer_name))).first.click()
    box = page.get_by_role("region", name="The kitchen's own offer")
    check("promotions: the kitchen's own offer is live without approval", lambda: expect(box.get_by_text(re.compile("went live without approval"))).to_be_visible(timeout=15000))
    box.get_by_label("Why pause it (the kitchen sees this)").fill("Looks like a typo in the amount; please check")
    box.get_by_role("button", name="Pause offer").click()
    check("promotions: paused, the reason shown, audited", lambda: (
        expect(page.get_by_role("region", name="Rules").get_by_text("Paused").first).to_be_visible(timeout=15000),
        page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile(re.escape(offer_name))).first.click(),
        expect(page.get_by_role("region", name="The kitchen's own offer").get_by_text(re.compile("Looks like a typo"))).to_be_visible(timeout=15000),
        expect(page.get_by_role("button", name="Resume offer")).to_be_visible(),
        _ok(any(o["id"] == offer["id"] and o["paused"] for o in api.get(f"{CORE}/restaurants/{rest['id']}/offers", headers=partner_h).json())),
        _ok(any(a["action"] == "offer.paused" for a in api.get(f"{CORE}/audit", headers=token("admin@example.com", PW), params={"entity_type": "rule"}).json()))))
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile(re.escape(offer_name))).first.click()
    expect(page.get_by_role("button", name="Resume offer")).to_be_visible(timeout=10000)
    page.screenshot(path=f"{OUT}/07b-offer-paused.png", full_page=True)
    api.post(f"{CORE}/restaurants/{rest['id']}/offers/{offer['id']}/end", headers=partner_h)

    # Batching (task 43): a per-city switch among the business rules, off by default. It changes
    # rider pay, so it needs a second admin like money rules.
    fin_us = token("finance.us@example.com", PW)

    def batching_rule():  # type: ignore[no-untyped-def]
        page.goto(f"{BASE}/pricing?scope=US-ID-BOI&tab=business", wait_until="networkidle")
        page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("Batching")).first.click()
        return page.get_by_role("region", name=re.compile("^Rule · Batching"))

    def live_batching_rule() -> dict | None:
        rules = api.get(f"{CORE}/rules", headers=fin_us, params={"family": "business"}).json()
        return next((r for r in rules if r["template"] == "batching" and r["market_scope"] == "US-ID-BOI"), None)

    def set_batching(live: bool) -> None:
        rule = batching_rule()
        rule.get_by_role("button", name="New version").click()
        box = rule.get_by_label("Live")
        box.check() if live else box.uncheck()
        rule.get_by_role("button", name="Send for approval").click()
        for _ in range(30):
            r = live_batching_rule()
            if r and r["status"] == "pending_approval":
                break
            page.wait_for_timeout(500)
        assert r and r["status"] == "pending_approval", f"batching didn't wait for approval: {r and r['status']}"
        ok = api.post(f"{CORE}/rules/{r['id']}/approve", headers=fin_us, data={"note": "e2e"})
        assert ok.status == 200, ok.text()

    detail = batching_rule()
    check("batching: a switch per city, off by default", lambda: expect(detail.get_by_test_id("rule-words")).to_contain_text("Off:", timeout=15000))
    set_batching(True)
    detail = batching_rule()
    check("batching: needs a second admin; approved by Finance, then live", lambda: (
        expect(detail.get_by_test_id("rule-words")).to_contain_text("Live:", timeout=15000),
        expect(detail.get_by_role("list", name="Versions").get_by_text(re.compile("^Replaced on ")).first).to_be_visible()))
    page.screenshot(path=f"{OUT}/07d-batching-switch.png", full_page=True)
    set_batching(False)  # leave it as the seed has it
    check("rule history: only the current version is Live, older ones say when they were replaced", lambda: (
        expect(batching_rule().get_by_test_id("rule-words")).to_contain_text("Off:", timeout=15000),
        expect(page.get_by_role("list", name="Versions").get_by_text("Live", exact=True)).to_have_count(1, timeout=15000)))

    # Commissions (Pricing & Rules, commissions first): add a Boise override, Finance approves it,
    # an order and its payout use it; end it and the next order is back on the US rate; delete a draft.
    boi_rest = next(r for r in api.get(f"{CORE}/restaurants?limit=50").json()["items"] if r["name"] == "Boise Bowl Co.")
    boi_menu = {i["name"]: i["id"] for c in api.get(f"{CORE}/restaurants/{boi_rest['id']}/menu").json()["categories"] for i in c["items"]}
    RT = "http://realtime:8004/api/v1"

    def delivered_boise_order() -> dict:
        """customer1.boi orders a bowl, pays; the kitchen cooks; rider1.boi takes the offer and delivers it."""
        c, partner, rider = token("customer1.boi@example.com"), token("partner.boi@example.com"), token("rider1.boi@example.com")
        cart = [{"menu_item_id": boi_menu["Teriyaki Chicken Bowl"], "quantity": 2}]
        addr = api.get(f"{CORE}/me/addresses", headers=c).json()[0]
        qq = api.post(f"{CORE}/pricing/quote", headers=c, data={"restaurant_id": boi_rest["id"], "items": cart, "deliver_to": {"address_id": addr["id"]}}).json()
        o = api.post(f"{CORE}/orders", headers={**c, "X-Idempotency-Key": str(uuid.uuid4())}, data={
            "restaurant_id": boi_rest["id"], "items": cart, "payment_method": "card", "quote_token": qq["token"],
            "delivery_address": {"street": "1510 N 13th St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}}).json()
        pi = api.post(f"{CORE}/payments/initiate", headers=c, data={"order_id": o["id"], "payment_method_type": "card"}).json()
        api.post(f"{CORE}/payments/fake/{pi['payment_intent_id']}/complete", headers=c, data={"outcome": "succeeded"})
        api.post(f"{RT}/riders/me/online", headers=rider, data={"lat": 43.6299, "lng": -116.2008})
        for st in ("accepted", "preparing", "almost_ready"):
            api.put(f"{CORE}/orders/{o['id']}/status", headers=partner, data={"status": st})
        for _ in range(60):
            if ((api.get(f"{RT}/riders/me", headers=rider).json().get("offer") or {}).get("order_id")) == o["id"]:
                break
            page.wait_for_timeout(500)
        assert api.post(f"{RT}/offers/{o['id']}/accept", headers=rider).status == 200
        api.put(f"{CORE}/orders/{o['id']}/status", headers=partner, data={"status": "ready"})
        api.put(f"{CORE}/orders/{o['id']}/status", headers=rider, data={"status": "picked_up"})
        pin = api.get(f"{CORE}/orders/{o['id']}", headers=c).json()["pin"]
        done = api.put(f"{CORE}/orders/{o['id']}/status", headers=rider, data={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
        assert done.status == 200, done.text()
        api.post(f"{RT}/riders/me/offline", headers=rider)
        return o

    def commission_of(order_id: str) -> tuple[str, str]:
        snap = api.get(f"{CORE}/pricing/orders/{order_id}/snapshot", headers=fin_us).json()
        food = Decimal(snap["split"]["detail"].get("commission", "0"))
        lines = {ln["code"]: Decimal(ln["amount"]) for ln in snap["lines"] if ln["code"] == "food"}
        return str(food), str((lines["food"] * Decimal("0.12")).quantize(Decimal("0.01")))

    page.goto(f"{BASE}/pricing?scope=US-ID-BOI&tab=commission", wait_until="networkidle")
    check("commissions: each row says where it comes from", lambda: expect(
        page.get_by_role("region", name="Rules").get_by_test_id("row-source").filter(has_text="Inherited from United States · 20% (tier B)").first).to_be_visible(timeout=15000))
    for r in api.get(f"{CORE}/rules", headers=fin_us, params={"family": "commission"}).json():  # left from an earlier run
        if r["market_scope"] == "US-ID-BOI" and r["status"] in ("draft", "rejected"):
            api.delete(f"{CORE}/rules/{r['id']}", headers=token("cm.us@example.com", PW))
        elif r["market_scope"] == "US-ID-BOI" and r["status"] == "published" and not r.get("effective_to"):
            api.post(f"{CORE}/rules/{r['id']}/end", headers=token("cm.us@example.com", PW), data={})
    page.reload(wait_until="networkidle")
    page.get_by_role("region", name="Rules").get_by_role("button", name="Add").click()
    add = page.get_by_role("region", name="Add a rule")
    add.get_by_label("Type").select_option("percent")
    add.get_by_label("For").select_option("city")
    add.get_by_label("Name").fill("Boise launch rate")
    add.get_by_label("Percent", exact=True).fill("12")
    add.get_by_role("button", name="Create draft").click()
    draft = page.get_by_role("region", name="Rule · Boise launch rate")
    check("commissions: a new Boise rule starts as a draft with a 7-day preview", lambda: (
        expect(draft.get_by_text("Draft", exact=True).first).to_be_visible(timeout=15000),
        expect(draft.get_by_role("region", name="Preview: the last 7 days").get_by_test_id("preview-summary")).to_be_visible(timeout=15000),
        expect(draft.get_by_test_id("rule-source")).to_contain_text("Set for Boise · 12%")))
    page.screenshot(path=f"{OUT}/07e-commission-draft-preview.png", full_page=True)
    draft.get_by_role("button", name="Submit for approval").click()
    check("commissions: submitted, waiting for a second admin", lambda: expect(draft.get_by_text("Waiting for approval").first).to_be_visible(timeout=15000))

    fctx = b.new_context(viewport={"width": 1440, "height": 1000})
    fpage = fctx.new_page()
    sign_in(fpage, "finance.us@example.com")
    fpage.goto(f"{BASE}/pricing?scope=US-ID-BOI&tab=approvals", wait_until="networkidle")
    fpage.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("Boise launch rate")).first.click()
    frule = fpage.get_by_role("region", name="Rule · Boise launch rate")
    frule.get_by_label("Comment").fill("Matches the signed launch deal")
    frule.get_by_role("button", name="Approve and schedule").click()
    check("commissions: Finance approves it, it's live", lambda: expect(fpage.get_by_text("Nothing waiting for you.")).to_be_visible(timeout=15000))
    fctx.close()

    o1 = delivered_boise_order()
    got, want = commission_of(o1["id"])
    check("commissions: an order uses the Boise override (12% of food)", lambda: _ok(got == want))
    # Payment fees (item 1): a US card order pays Stripe 2.9% + $0.30 and Stripe Tax 0.5% of the total.
    snap1 = api.get(f"{CORE}/pricing/orders/{o1['id']}/snapshot", headers=fin_us).json()
    total1 = Decimal(snap1["total"])
    fd = snap1["split"].get("detail", {}).get("payment_fees") or {}
    taxed = any((ln.get("detail") or {}).get("provider") for ln in snap1["lines"] if ln["code"] == "tax")
    fee_want = (total1 * Decimal("0.029") + Decimal("0.30")).quantize(Decimal("0.01")) + (
        (total1 * Decimal("0.005")).quantize(Decimal("0.01")) if taxed else Decimal(0))
    fee_got = Decimal(snap1["split"].get("payment_fees", "-1"))
    check(f"payment fees: a US card order's split carries Stripe 2.9% + $0.30 (+0.5% Stripe Tax when it taxed) ({fee_got} = {fee_want})",
          lambda: _ok(fee_got == fee_want and fd.get("method") == "card" and "platform_keeps" in snap1["split"]))
    today_d = date.today()
    prev = api.get(f"{CORE}/finance/payout-preview/restaurants/{boi_rest['id']}", headers=fin_us,
                   params={"country": "US", "start": str(today_d - timedelta(days=1)), "end": str(today_d + timedelta(days=1))}).json()
    line = next(ln for ln in prev["lines"] if ln["order_id"] == o1["id"])
    check("commissions: the payout uses it too (the restaurant's statement line)", lambda: _ok(line["commission"] == f"-{want}"))

    page.goto(f"{BASE}/pricing?scope=US-ID-BOI&tab=commission", wait_until="networkidle")
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("Boise launch rate")).first.click()
    live = page.get_by_role("region", name="Rule · Boise launch rate")
    check("commissions: a live rule has no Delete, only New version / End / Roll back", lambda: (
        expect(live.get_by_role("button", name="End now")).to_be_visible(timeout=15000),
        expect(live.get_by_role("button", name="Delete draft")).to_have_count(0)))
    live.get_by_role("button", name="End now").click()
    check("commissions: ended; Boise is back on the US rate", lambda: expect(page.get_by_role("status")).to_contain_text("Ended now", timeout=15000))
    o2 = delivered_boise_order()
    got2, _ = commission_of(o2["id"])
    food2 = next(Decimal(ln["amount"]) for ln in api.get(f"{CORE}/pricing/orders/{o2['id']}/snapshot", headers=fin_us).json()["lines"] if ln["code"] == "food")
    check("commissions: the next order uses the country rate again (20%, tier B)", lambda: _ok(got2 == str((food2 * Decimal("0.20")).quantize(Decimal("0.01")))))

    page.goto(f"{BASE}/pricing?scope=US-ID-BOI&tab=commission", wait_until="networkidle")
    page.get_by_role("region", name="Rules").get_by_role("button", name="Add").click()
    add = page.get_by_role("region", name="Add a rule")
    add.get_by_label("Type").select_option("percent")
    add.get_by_label("Name").fill("Draft to delete")
    add.get_by_label("Percent", exact=True).fill("13")
    add.get_by_role("button", name="Create draft").click()
    gone = page.get_by_role("region", name="Rule · Draft to delete")
    gone.get_by_role("button", name="Delete draft").click()
    check("commissions: a draft can be deleted", lambda: expect(page.get_by_role("region", name="Rules").get_by_text("Draft to delete")).to_have_count(0, timeout=15000))

    # The restaurant's commission: rate, source, end date, tier (change approved by a second admin).
    page.goto(f"{BASE}/partners?scope=US-ID-BOI&tab=kitchens", wait_until="networkidle")
    page.get_by_role("button", name="Boise Bowl Co.").click()
    kc = page.get_by_role("region", name="Commission · Boise Bowl Co.")
    check("kitchen page: effective commission, where it comes from, tier", lambda: (
        expect(kc.get_by_test_id("kitchen-commission")).to_contain_text("20%", timeout=15000),
        expect(kc.get_by_test_id("kitchen-commission")).to_contain_text("country"),
        expect(kc.get_by_test_id("kitchen-tier")).to_have_text("B")))
    page.screenshot(path=f"{OUT}/06b-kitchen-commission.png", full_page=True)

    page.goto(f"{BASE}/markets/IN/IN-TG-HYD", wait_until="networkidle")
    check("markets: the city with its zones", lambda: expect(page.get_by_text(re.compile("Zones")).first).to_be_visible(timeout=15000))
    page.screenshot(path=f"{OUT}/08-markets-city.png")

    page.goto(f"{BASE}/finance?scope=IN", wait_until="networkidle")
    check("finance: payout runs and reconciliation", lambda: (
        expect(page.get_by_role("region", name="Payout runs")).to_be_visible(timeout=15000),
        expect(page.get_by_role("region", name="Reconciliation")).to_be_visible(timeout=20000)))
    page.screenshot(path=f"{OUT}/09-finance.png", full_page=True)
    page.goto(f"{BASE}/finance?scope=US", wait_until="networkidle")
    page.get_by_label("to").fill(str(date.today() + timedelta(days=1)))  # this run's orders are today's
    check("finance: contribution per order, after payment fees", lambda: (
        expect(page.get_by_role("region", name="Contribution per order")).to_contain_text("Payment fees", timeout=20000),
        expect(page.get_by_test_id("platform-keeps")).to_contain_text("$", timeout=20000)))
    page.get_by_role("region", name="Contribution per order").screenshot(path=f"{OUT}/09b-contribution.png")

    page.goto(f"{BASE}/settings", wait_until="networkidle")
    check("settings: your access and the admins", lambda: (
        expect(page.get_by_role("region", name="Admins")).to_be_visible(timeout=15000),
        expect(page.get_by_text("ops.hyd@example.com")).to_be_visible()))
    page.screenshot(path=f"{OUT}/10-settings.png", full_page=True)

    # No raw data on any page: JSON-like text, "null", "undefined" or "NaN" fail the run.
    RAW = re.compile(r'[{\[]\s*"[A-Za-z_]+"\s*:|\bnull\b|\bundefined\b|\bNaN\b')
    pages = ["/overview", "/overview?scope=IN", "/overview?scope=US-ID-BOI", "/operations?scope=IN-TG-HYD&tab=live",
             "/operations?scope=IN-TG-HYD&tab=attention", "/operations?scope=IN-TG-HYD&tab=dispatch", "/operations?scope=IN-TG-HYD&tab=support",
             "/partners?scope=IN-TG-HYD&tab=kitchens", "/partners?scope=IN-TG-HYD&tab=applications", "/partners?scope=IN&tab=riders",
             "/markets", "/markets/IN", "/markets/IN/IN-TG-HYD", "/pricing/simulator?city=IN-TG-HYD", "/finance?scope=IN", "/finance?scope=US",
             "/settings"] + [f"/pricing?scope=IN-TG-HYD&tab={f}" for f in
                             ("delivery_fee", "customer_fee", "tax", "commission", "rider_pay", "business", "promotion", "approvals")]
    dirty: list[str] = []
    for path in pages:
        page.goto(BASE + path, wait_until="networkidle")
        page.wait_for_timeout(800)
        if "/pricing?" in path and "approvals" not in path:
            for i in range(page.get_by_role("region", name="Rules").get_by_role("button").count()):
                page.get_by_role("region", name="Rules").get_by_role("button").nth(i).click()
                page.wait_for_timeout(300)
                hit = RAW.search(page.inner_text("body"))
                if hit:
                    dirty.append(f"{path} rule {i}: {hit.group(0)!r}")
        hit = RAW.search(page.inner_text("body"))
        if hit:
            dirty.append(f"{path}: {hit.group(0)!r}")
    check("no JSON-like text or null on any admin page", lambda: not dirty or fail("; ".join(dirty[:8])))
    page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=delivery_fee", wait_until="networkidle")
    check("rule settings read as plain words", lambda: expect(page.get_by_text(re.compile(r"0–\d+ km: ₹\d+")).first).to_be_visible(timeout=10000))

    # Role scopes: a Hyderabad city ops sees Hyderabad only, and no Finance or Settings.
    ops = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(ops, "ops.hyd@example.com")
    check("city ops: India only, Hyderabad only, no Finance or Settings", lambda: (
        expect(ops.get_by_text("You can see India only")).to_be_visible(timeout=15000),
        expect(ops.get_by_role("link", name="All countries")).to_have_count(0),
        expect(ops.get_by_role("navigation", name="Admin sections").get_by_role("link", name="Finance")).to_have_count(0),
        expect(ops.get_by_role("navigation", name="Admin sections").get_by_role("link", name="Settings")).to_have_count(0),
        expect(ops.get_by_role("link", name="Hyderabad", exact=True).first).to_be_visible()))
    ops.screenshot(path=f"{OUT}/11-city-ops.png", full_page=True)
    ops.goto(f"{BASE}/overview?scope=US", wait_until="networkidle")
    check("city ops: another country is refused", lambda: expect(ops.get_by_text("You can't see this part of BhojanGo.")).to_be_visible(timeout=15000))

    sup = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(sup, "support.hyd@example.com")
    nav = sup.get_by_role("navigation", name="Admin sections")
    check("support agent: Operations and Partners, no Pricing, Markets or Finance", lambda: (
        expect(nav.get_by_role("link", name="Operations")).to_be_visible(timeout=15000),
        expect(nav.get_by_role("link", name="Pricing & Rules")).to_have_count(0),
        expect(nav.get_by_role("link", name="Finance")).to_have_count(0)))
    b.close()

failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
raise SystemExit(1 if failed else 0)
