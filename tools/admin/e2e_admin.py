"""Playwright end-to-end run of the admin console (P21) against `make dev`.

Runs in the Playwright image on the compose network (tools/admin/e2e.sh). The
browser opens the console at localhost:3001 (forwarded to the admin service,
which proxies /api to core_api and realtime). An order is placed through the
API first so Operations and Support have something live. Screenshots go to
docs/screenshots/admin.
"""
import os
import json
import re
import socket
import sys
import threading
import uuid
from datetime import date, timedelta
from decimal import Decimal

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
CORE = (os.environ.get("QA_CORE") or "http://core-api:8001") + "/api/v1"
PW = "BhojanGoAdmin1"

# Tests never write to QA or production (tools/target_guard.py; at /guard in the Playwright image).
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402
from totp_signin import SEED_TOTP_SECRET, admin_console_second_step, code_at, finish  # noqa: E402

# Accessibility (R9): axe-core on the main pages; serious or critical fails the run (tools/a11y, at /a11y).
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "a11y"), "/a11y"]
from axe_check import Axe  # noqa: E402

AXE = Axe("admin")

ensure_safe_api(CORE)

# Hosted QA (Railway): the public URLs come from QA_WEB / QA_ADMIN / QA_CORE / QA_RT
# and the seed's random passwords (and admins' authenticator keys) from E2E_LOGINS_FILE (outside the repo).
PASSWORDS: dict[str, str] = {}
TOTP_KEYS: dict[str, str] = {}
if os.environ.get("E2E_LOGINS_FILE"):
    with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as _f:
        _rows = [line.rstrip("\n").split("\t") for line in _f]
    PASSWORDS = {r[2]: r[3] for r in _rows if len(r) >= 4}
    TOTP_KEYS = {r[2]: r[4] for r in _rows if len(r) >= 5 and r[4]}
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


BASE = os.environ.get("QA_ADMIN", "")
if not BASE:  # make dev: the console on localhost:3001, forwarded to the admin service
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
                r = api.post(f"{CORE}/auth/login", data={"email": email, "password": PASSWORDS.get(email, pw)})
                if r.status != 429:
                    break
                page_wait(6000)
            body = finish(lambda path, data: api.post(f"{CORE}{path}", data=data).json(), email, r.json(), TOTP_KEYS)
            _tokens[email] = {"Authorization": f"Bearer {body['access_token']}"}
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
        page.locator("input[type=password]").fill(PASSWORDS.get(email, PW))
        page.get_by_role("button", name=re.compile("sign in", re.I)).click()
        # Every admin: the second step, a code from the authenticator (the seed's key; QA: the logins file's).
        admin_console_second_step(page, email, TOTP_KEYS)
        # A client-side navigation never fires "load": wait on the URL itself.
        expect(page).to_have_url(re.compile(r"/overview"), timeout=20000)

    def second_step_checks(page, email: str) -> None:  # type: ignore[no-untyped-def]
        """Round 8 D5: a password alone is not enough; wrong codes say so; recovery codes are offered."""
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.locator("input[type=email]").fill(email)
        page.locator("input[type=password]").fill(PASSWORDS.get(email, PW))
        page.get_by_role("button", name=re.compile("sign in", re.I)).click()
        check("admin sign-in: the password alone asks for the authenticator code", lambda: (
            expect(page.get_by_role("heading", name="Enter your authenticator code")).to_be_visible(timeout=20000),
            expect(page.get_by_label("6-digit code")).to_be_focused()))
        import time

        wrong = code_at(TOTP_KEYS.get(email, SEED_TOTP_SECRET), int(time.time() // 30) + 20)  # far from now: never valid
        page.get_by_label("6-digit code").fill(wrong)
        page.get_by_role("button", name="Continue").click()
        check("admin sign-in: a wrong code says so, in words", lambda:
              expect(page.locator("p[role=alert]")).to_contain_text("That code didn't work", timeout=10000))
        page.get_by_role("button", name=re.compile("Use a recovery code")).click()
        check("admin sign-in: a recovery code can be used instead of the app", lambda: (
            expect(page.get_by_role("heading", name="Use a recovery code")).to_be_visible(),
            expect(page.get_by_label("Recovery code")).to_be_visible()))
        page.screenshot(path=f"{OUT}/00-sign-in-recovery.png")
        page.get_by_role("button", name="Use your authenticator app instead").click()
        admin_console_second_step(page, email, TOTP_KEYS)
        check("admin sign-in: the right code opens the console", lambda:
              expect(page).to_have_url(re.compile(r"/overview"), timeout=20000))

    page = b.new_page(viewport={"width": 1440, "height": 1000})
    # Outside production (make dev, QA, staging) the console says it's a test site, on the
    # login page and inside; production never does (packages/ui/environment.js, unit-tested there).
    test_banner = "Test site: demo restaurants, no real orders or payments"
    page.goto(f"{BASE}/login", wait_until="networkidle")
    check("test-site banner: on the login page, a note (not an alert)", lambda: (
        expect(page.get_by_role("note").filter(has_text=test_banner)).to_be_visible(),
        expect(page.get_by_role("alert").filter(has_text=test_banner)).to_have_count(0)))
    check("logo: the wordmark is the h3 token (20 px at desktop width)", lambda:
          expect(page.get_by_test_id("logo-wordmark")).to_have_css("font-size", "20px"))
    check("a11y login: no serious or critical accessibility issues (axe)", lambda: AXE.scan(page, "login"))
    second_step_checks(page, "admin@example.com")
    # R22 S8: the console's session is an httpOnly cookie on its own host; the page's storage holds no token.
    check("admin session: an httpOnly cookie, and no token in the page's storage", lambda: (
        _ok(not re.search(r"eyJ[\w-]+\.eyJ", page.evaluate("JSON.stringify(Object.assign({}, localStorage, sessionStorage))"))),
        _ok(any(c["name"] == "bg_admin_at" and c["httpOnly"] and c["sameSite"] == "Lax" for c in page.context.cookies())),
        _ok("bg_admin_" not in page.evaluate("document.cookie"))))
    # R22 S9: each page has its own CSP nonce and no 'unsafe-inline' script; the console above ran with it.
    _csp = [page.request.get(f"{BASE}/login").headers.get("content-security-policy") or "" for _ in range(2)]
    check("admin CSP: a fresh nonce on every page and no inline script allowed", lambda: _ok(
        "'nonce-" in _csp[0] and "unsafe-inline" not in _csp[0].split("script-src", 1)[1].split(";", 1)[0] and _csp[0] != _csp[1]))
    check("test-site banner: inside the console too", lambda: expect(page.get_by_role("note").filter(has_text=test_banner)).to_be_visible())
    check("overview, all countries: each country in its own money, side by side, needs action", lambda: (
        expect(page.get_by_role("heading", name="All countries", exact=True)).to_be_visible(timeout=15000),
        expect(page.get_by_role("region", name="India")).to_be_visible(),
        expect(page.get_by_role("region", name="United States")).to_be_visible(),
        expect(page.get_by_role("region", name="Side by side")).to_be_visible(),
        expect(page.get_by_text(re.compile("restaurant.* applying to join")).first).to_be_visible()))
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
        expect(page.get_by_role("region", name="Waiting for a delivery partner")).to_be_visible()))
    page.screenshot(path=f"{OUT}/04-dispatch-map.png")

    page.goto(f"{BASE}/operations?scope=IN-TG-HYD&tab=support", wait_until="networkidle")
    page.get_by_label("Find an order").fill(code)
    page.get_by_role("button", name=re.compile(re.escape(code))).click()
    check("support: order, timeline and items to refund", lambda: (
        expect(page.get_by_role("region", name=f"Order {code}")).to_be_visible(timeout=15000),
        expect(page.get_by_label("Order timeline")).to_be_visible()))
    page.get_by_label("How many Veg Dum Biryani to refund").fill("1")
    page.get_by_label("Reason").select_option("missing_item")
    check("support: refund is charged to the kitchen for a missing item", lambda: expect(page.get_by_text(re.compile("charged to the restaurant's payout"))).to_be_visible())
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
    # R22: the number reads in its country's format ("+91 90000 00900"); the tel: link keeps the E.164.
    check("support: the call-back number is formatted, its tel: link is E.164", lambda: (
        expect(case.get_by_test_id("ticket-phone")).to_have_text(re.compile(r"^\+91 \d{5} \d{5}$"), timeout=10000),
        expect(case.get_by_test_id("ticket-phone")).to_have_attribute("href", re.compile(r"^tel:\+91\d{10}$"))))
    case.get_by_label("What did you do?").fill("Called the restaurant; the payout covered six days, explained the cut-off")
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
        # the documents and their names come from Markets -> India (kitchen_documents)
        expect(page.get_by_test_id("application-docs")).to_contain_text("GST registration (GSTIN)"),
        expect(page.get_by_role("button", name="Approve and go live")).to_be_visible()))
    page.screenshot(path=f"{OUT}/06-application.png", full_page=True)

    page.goto(f"{BASE}/partners?scope=IN&tab=riders", wait_until="networkidle")
    check("partners: rider documents by country", lambda: expect(page.get_by_text(re.compile("reviewed by country"))).to_be_visible())
    # R22: a delivery partner's number in its country's format, when there are documents to review.
    page.wait_for_timeout(1500)
    rider_rows = page.get_by_text(re.compile(r"· \+\d"))
    if rider_rows.count():
        check("partners: rider numbers are formatted (+91 90000 00291)", lambda: expect(rider_rows.first).to_have_text(
            re.compile(r"· \+(91 \d{5} \d{5}|1 \d{3}-\d{3}-\d{4}) · [A-Z]{2}")))
    page.screenshot(path=f"{OUT}/06c-rider-documents.png", full_page=True)

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
    box = page.get_by_role("region", name="The restaurant's own offer")
    check("promotions: the kitchen's own offer is live without approval", lambda: expect(box.get_by_text(re.compile("went live without approval"))).to_be_visible(timeout=15000))
    box.get_by_label("Why pause it (the restaurant sees this)").fill("Looks like a typo in the amount; please check")
    box.get_by_role("button", name="Pause offer").click()
    check("promotions: paused, the reason shown, audited", lambda: (
        expect(page.get_by_role("region", name="Rules").get_by_text("Paused").first).to_be_visible(timeout=15000),
        page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile(re.escape(offer_name))).first.click(),
        expect(page.get_by_role("region", name="The restaurant's own offer").get_by_text(re.compile("Looks like a typo"))).to_be_visible(timeout=15000),
        expect(page.get_by_role("button", name="Resume offer")).to_be_visible(),
        _ok(any(o["id"] == offer["id"] and o["paused"] for o in api.get(f"{CORE}/restaurants/{rest['id']}/offers", headers=partner_h).json())),
        _ok(any(a["action"] == "offer.paused" for a in api.get(f"{CORE}/audit", headers=token("admin@example.com", PW), params={"entity_type": "rule"}).json()))))
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile(re.escape(offer_name))).first.click()
    expect(page.get_by_role("button", name="Resume offer")).to_be_visible(timeout=10000)
    page.screenshot(path=f"{OUT}/07b-offer-paused.png", full_page=True)
    api.post(f"{CORE}/restaurants/{rest['id']}/offers/{offer['id']}/end", headers=partner_h)

    # R37: offers BhojanGo pays for: off (paused) in the seed, a monthly budget per place, and for each offer
    # what it costs an order next to the platform fee it earns, with a warning when it can cost more.
    adm = token("admin@example.com", PW)
    api.put(f"{CORE}/rules/offers/budgets/city/IN-TG-HYD", headers=adm, data={"monthly": None})
    costly = api.post(f"{CORE}/rules", headers=adm, data={
        "family": "promotion", "template": "flat_off", "key": "r37_e2e", "name": "R37 ₹100 off any order",
        "params": {"amount": 100, "funded_by": "platform"}, "scope_level": "city", "scope_id": "IN-TG-HYD"}).json()
    try:
        page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=promotion", wait_until="networkidle")
        budgets = page.get_by_role("region", name="BhojanGo offer budgets")
        check("R37 offer budgets: Hyderabad has none, so BhojanGo's offers are off", lambda: (
            expect(budgets.get_by_test_id("budget-IN-TG-HYD")).to_contain_text("Off: no budget", timeout=15000),
            expect(budgets.get_by_test_id("budget-IN-TG-HYD").get_by_test_id("budget-spent")).to_contain_text("0%")))
        page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("10% off, up to")).first.click()
        check("R37 the seeded launch offer: paused, BhojanGo pays for it, approvers can resume it", lambda: (
            expect(page.get_by_role("region", name="An offer BhojanGo pays for").get_by_text(re.compile("Off by default"))).to_be_visible(timeout=15000),
            expect(page.get_by_test_id("offer-running")).to_have_text("Paused: customers don't see it."),
            expect(page.get_by_role("button", name="Resume offer")).to_be_visible(),
            expect(page.get_by_test_id("offer-cost-warning")).to_have_count(0)))  # 10% up to ₹50 never beats a 10% fee
        budgets.get_by_label("Monthly budget for Hyderabad").fill("5000")
        budgets.get_by_test_id("budget-IN-TG-HYD").get_by_role("button", name="Save").click()
        check("R37 a city budget: saved, spends from Hyderabad's own", lambda: (
            expect(budgets.get_by_test_id("budget-IN-TG-HYD")).to_contain_text("₹0.00 of ₹5,000.00", timeout=15000),
            expect(budgets.get_by_test_id("budget-IN-TG-HYD")).not_to_contain_text("Off: no budget")))
        page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("R37 ₹100 off any order")).first.click()
        check("R37 an offer that can cost more than the platform fee: the warning", lambda: (
            expect(page.get_by_test_id("offer-cost-warning")).to_contain_text("can cost more than the platform fee", timeout=15000),
            expect(page.get_by_test_id("offer-cost")).to_contain_text("up to ₹100"),
            expect(page.get_by_test_id("offer-budget")).to_contain_text("Hyderabad: ₹0.00 of ₹5,000.00"),
            expect(page.get_by_test_id("offer-running")).to_contain_text("Not live yet")))  # a draft
        page.screenshot(path=f"{OUT}/07h-offer-budget-warning.png", full_page=True)
    finally:
        api.delete(f"{CORE}/rules/{costly['id']}", headers=adm)
        api.put(f"{CORE}/rules/offers/budgets/city/IN-TG-HYD", headers=adm, data={"monthly": None})

    # R38 item 3: a cancelled order gives its BhojanGo-funded offer cost back (budget 10, offer 3, three orders,
    # one cancelled: 6 spent). Item 5: no "kitchen" in the admin's words ("paid by the restaurant").
    def r38_budget(market: str, city: str, maker_email: str, checker_email: str, cust_email: str, rest_name: str,
                   dish: str, qty: int, deliver_to: dict, address: dict, budget: str, amount: int, shown: str) -> None:
        maker, checker, cust = token(maker_email, PW), token(checker_email, PW), token(cust_email)
        api.put(f"{CORE}/rules/offers/budgets/city/{city}", headers=maker, data={"monthly": budget})
        rule = api.post(f"{CORE}/rules", headers=maker, data={
            "family": "promotion", "template": "flat_off", "key": f"r38_e2e_{market}", "name": f"R38 {amount} off (BhojanGo)",
            "params": {"amount": amount, "funded_by": "platform"}, "scope_level": "city", "scope_id": city}).json()
        api.post(f"{CORE}/rules/{rule['id']}/submit", headers=maker)
        api.post(f"{CORE}/rules/{rule['id']}/approve", headers=checker, data={})
        try:
            rest = next(r for r in api.get(f"{CORE}/restaurants?limit=100").json()["items"] if r["name"] == rest_name)
            item = next(i for c in api.get(f"{CORE}/restaurants/{rest['id']}/menu").json()["categories"] for i in c["items"] if i["name"] == dish)
            items = [{"menu_item_id": item["id"], "quantity": qty}]
            orders = []
            for _ in range(3):
                q = api.post(f"{CORE}/pricing/quote", headers=cust, data={"restaurant_id": rest["id"], "items": items, "deliver_to": deliver_to}).json()
                o = api.post(f"{CORE}/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, data={
                    "restaurant_id": rest["id"], "items": items, "payment_method": "card", "quote_token": q["token"], "delivery_address": address}).json()
                orders.append(o)
            api.post(f"{CORE}/orders/{orders[1]['id']}/cancel", headers=cust, data={"reason": "customer_cancelled"})
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                page.goto(f"{BASE}/pricing?scope={city}&tab=promotion", wait_until="networkidle")
                row = page.get_by_role("region", name="BhojanGo offer budgets").get_by_test_id(f"budget-{city}")
                check(f"R38 {market} {width} px: 3 orders, 1 cancelled: {shown} spent", lambda row=row: expect(row.get_by_test_id("budget-spent")).to_contain_text(shown, timeout=15000))
                page.screenshot(path=f"{OUT}/r38-3-web{width}-{market}.png", full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})
        finally:
            for o in orders if "orders" in locals() else []:
                api.post(f"{CORE}/orders/{o['id']}/cancel", headers=cust, data={"reason": "customer_cancelled"})
            api.post(f"{CORE}/rules/{rule['id']}/end", headers=checker, data={})
            api.put(f"{CORE}/rules/offers/budgets/city/{city}", headers=maker, data={"monthly": None})

    r38_budget("us", "US-ID-BOI", "cm.us@example.com", "finance.us@example.com", "customer2.boi@example.com", "Boise Bowl Co.",
               "Crispy Tofu Bowl", 2, {"lat": 43.6150, "lng": -116.2023},
               {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}, "10", 3, "$6.00 of $10.00")
    r38_budget("in", "IN-TG-HYD", "cm.in@example.com", "finance.in@example.com", "customer3.hyd@example.com", "Spice Route Kitchen",
               "Veg Dum Biryani", 2, {"lat": 17.4483, "lng": 78.3915},
               {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}, "100", 30, "₹60.00 of ₹100.00")

    for market, city in (("us", "US-ID-BOI"), ("in", "IN-TG-HYD")):
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{BASE}/pricing?scope={city}&tab=promotion", wait_until="networkidle")
            rules = page.get_by_role("region", name="Rules")

            def restaurant_words() -> None:
                # Hyderabad has the restaurant's own offer made (and ended) above; Boise's base seed may have none
                expect(rules.get_by_text(re.compile("paid by the restaurant" if market == "in" else "paid by (the restaurant|BhojanGo)")).first).to_be_visible(timeout=15000)
                text = page.locator("body").inner_text()
                # a restaurant's own trading name may say Kitchen (Spice Route Kitchen); BhojanGo's words never do
                left = re.sub(r"\b(Spice Route|Basque Corner|Kesar|Golden Spoon|Nonna's) Kitchen\b", "", text)
                _ok("kitchen" not in left.lower())
            check(f"R38 admin wording {market} {width} px: 'paid by the restaurant', no 'kitchen'", restaurant_words)
            page.screenshot(path=f"{OUT}/r38-5-web{width}-{market}.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})

    # ── R39 ── item 4: a chargeback (the fake provider's webhook, shaped as Stripe's charge.dispute.created) shows
    # in Finance > Chargebacks with the restaurant's share held, and takes evidence; item 5: a food permit to review
    # (a renewal from partner.boi), approved here; item 6: Settings > Monitoring > Send test alert. US and India,
    # 1440 and 390 px. Not on QA (the fake provider's webhook secret is local).
    import hashlib
    import hmac
    import time as _time

    fake_secret = os.environ.get("FAKE_PAYMENT_WEBHOOK_SECRET", "local-fake-webhook-secret")
    PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082")

    def r39_dispute(cust_email: str, rest_name: str, dish: str, deliver_to: dict, address: dict, method: str, reason: str) -> str:
        cust = token(cust_email)
        rest = next(r for r in api.get(f"{CORE}/restaurants?limit=100").json()["items"] if r["name"] == rest_name)
        item = next(i for c in api.get(f"{CORE}/restaurants/{rest['id']}/menu").json()["categories"] for i in c["items"] if i["name"] == dish)
        items = [{"menu_item_id": item["id"], "quantity": 2}]
        q = api.post(f"{CORE}/pricing/quote", headers=cust, data={"restaurant_id": rest["id"], "items": items, "deliver_to": deliver_to}).json()
        o = api.post(f"{CORE}/orders", headers={**cust, "X-Idempotency-Key": str(uuid.uuid4())}, data={
            "restaurant_id": rest["id"], "items": items, "payment_method": method, "quote_token": q["token"], "delivery_address": address}).json()
        init = api.post(f"{CORE}/payments/initiate", headers=cust, data={"order_id": o["id"], "payment_method_type": method}).json()
        api.post(f"{CORE}/payments/fake/{init['payment_intent_id']}/complete", headers=cust, data={"outcome": "succeeded"})
        body = json.dumps({"id": f"evt_fake_{uuid.uuid4().hex[:16]}", "type": "dispute.created", "dispute": {
            "id": f"dp_e2e_{uuid.uuid4().hex[:12]}", "amount": init["amount"], "currency": init["currency"].lower(), "reason": reason,
            "status": "needs_response", "payment_intent": init["client_secret"].split("_secret_")[0],
            "due_by": int(_time.time()) + 7 * 86400}})
        sig = hmac.new(fake_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        r = api.post(f"{CORE}/payments/fake/webhook", headers={"x-fake-signature": sig, "Content-Type": "application/json"}, data=body)
        _ok(r.status == 200 and r.json().get("dispute"))
        return o["id"]

    if not os.environ.get("QA_CORE"):
        for market, country, args, held_word in (
                ("us", "US", ("customer2.boi@example.com", "Boise Bowl Co.", "Crispy Tofu Bowl", {"lat": 43.6150, "lng": -116.2023},
                              {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}, "card", "fraudulent"), "$"),
                ("in", "IN", ("customer3.hyd@example.com", "Spice Route Kitchen", "Veg Dum Biryani", {"lat": 17.4483, "lng": 78.3915},
                              {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}, "upi",
                              "product_unacceptable"), "₹")):
            order_id = r39_dispute(*args)
            code = order_id[:8].upper()
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                page.goto(f"{BASE}/finance?scope={country}", wait_until="networkidle")
                box = page.get_by_role("region", name="Chargebacks")
                row = box.get_by_test_id("dispute-row").filter(has_text=f"#{code}")

                def held() -> None:
                    expect(row).to_be_visible(timeout=15000)
                    # R40: fraud (US) is BhojanGo's, nothing held; food quality (India) holds the restaurant's share
                    expect(row.get_by_test_id("dispute-state")).to_contain_text(
                        "Open: BhojanGo bears it (nothing held from the restaurant)" if market == "us"
                        else re.compile(rf"^Open: {re.escape(held_word)}[\d,.]+ will be held from the next payout"))
                check(f"R39 chargeback {market} {width} px: listed with the restaurant's share held from the next payout", held)
                if width == 1440:
                    row.get_by_role("button", name="Evidence").click()
                    ev = box.get_by_test_id("dispute-evidence")
                    ev.get_by_label("Note for the bank").fill("Delivered to the door at 19:42; photo and chat attached.")
                    ev.get_by_label("Evidence file").set_input_files({"name": "door.png", "mimeType": "image/png", "buffer": PNG})
                    ev.get_by_role("button", name="Add evidence").click()
                    check(f"R39 chargeback {market}: evidence added (file and note), ready to send", lambda ev=ev: (
                        expect(ev.get_by_role("button", name="door.png")).to_be_visible(timeout=15000),
                        expect(ev.get_by_role("button", name="Send evidence to the bank")).to_be_enabled()))
                else:
                    row.get_by_role("button", name="Evidence").click()
                    box.get_by_test_id("dispute-evidence").scroll_into_view_if_needed()
                page.screenshot(path=f"{OUT}/r39-4-admin{width}-{market}.png", full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})

    # Item 5: partner.boi's restaurant sends a renewed permit; ops approves it here. India keeps FSSAI (no permit to review).
    owner = token("partner.boi@example.com")
    mine = api.get(f"{CORE}/restaurants/mine", headers=owner).json()
    boise_rest = sorted(mine, key=lambda r: r["name"])[0]
    up = api.post(f"{CORE}/uploads", headers=owner, multipart={"purpose": "partner_document",
                                                                 "file": {"name": "permit.png", "mimeType": "image/png", "buffer": PNG}}).json()
    renewed = api.put(f"{CORE}/restaurants/{boise_rest['id']}/food-permit", headers=owner,
                      data={"number": "CDH-2027-0417", "expires_on": "2027-12-31", "document_key": up["key"]})
    _ok(renewed.status == 200)
    for market, scope in (("us", "US-ID-BOI"), ("in", "IN-TG-HYD")):
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{BASE}/partners?scope={scope}&tab=applications", wait_until="networkidle")
            permits = page.get_by_role("region", name="Food permits to review")
            if market == "us":
                prow = permits.get_by_test_id("permit-row").filter(has_text=boise_rest["name"])
                check(f"R39 food permit {width} px: the renewal waits for review with its number, expiry and file", lambda prow=prow: (
                    expect(prow).to_contain_text("CDH-2027-0417", timeout=15000), expect(prow).to_contain_text("31 Dec 2027"),
                    expect(prow.get_by_role("button", name="View permit")).to_be_visible()))
                page.screenshot(path=f"{OUT}/r39-5-admin{width}-us.png", full_page=True)
                if width == 390:
                    prow.get_by_role("button", name="Approve permit").click()
                    check("R39 food permit: approved by city ops, gone from the list", lambda: (
                        expect(permits.get_by_role("status")).to_contain_text(f"{boise_rest['name']}: permit approved", timeout=15000),
                        expect(permits.get_by_test_id("permit-row").filter(has_text=boise_rest["name"])).to_have_count(0)))
            else:
                check(f"R39 food permits {width} px (India): nothing to review; India keeps the FSSAI licence", lambda permits=permits: (
                    expect(permits).to_contain_text("Food permits to review", timeout=15000),
                    _ok(permits.get_by_test_id("permit-row").filter(has_text="Hyderabad").count() == 0)))
                page.screenshot(path=f"{OUT}/r39-5-admin{width}-in.png", full_page=True)
    after = api.get(f"{CORE}/restaurants/{boise_rest['id']}/food-permit", headers=owner).json()
    check("R39 food permit: the restaurant sees it approved", lambda: _ok(after["status"] == "approved"))

    # Item 6: Settings > Monitoring
    for market, scope in (("us", "US"), ("in", "IN")):
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{BASE}/settings?scope={scope}", wait_until="networkidle")
            mon = page.get_by_role("region", name="Monitoring")
            mon.get_by_role("button", name="Send test alert").click()
            check(f"R39 send test alert {market} {width} px: each channel says sent, off or failed", lambda mon=mon: (
                expect(mon.get_by_test_id("test-alert-result")).to_contain_text("Operations page: sent", timeout=15000),
                expect(mon.get_by_test_id("test-alert-result")).to_contain_text(re.compile(r"Paging webhook: (sent|off \(not set\))")),
                expect(mon.get_by_test_id("test-alert-result")).to_contain_text(re.compile(r"Sentry: (sent|off \(not set\))"))))
            page.screenshot(path=f"{OUT}/r39-6-admin{width}-{market}.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})

    # ── R40: the finance model on the screens. Card fees are the restaurants' (their own line, never taken from
    # BhojanGo), "BhojanGo keeps" = platform fees - offers - refunds it bears, Reconciliation adds up
    # (captured = refunded + restaurants + card fees + partners + tax + BhojanGo), and a payout run that pays less than
    # "owed" says why. US and India, 1440 and 390 px. WORKED_STATEMENT (tools/finance/worked_example.py, local only):
    # the worked example's restaurant statement.
    for market, country in (("us", "US"), ("in", "IN")):
        cur = "$" if country == "US" else "₹"
        rec_api = None
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 1000})
            page.goto(f"{BASE}/finance?scope={country}", wait_until="networkidle")
            recon = page.get_by_role("region", name="Reconciliation")
            contrib = page.get_by_role("region", name="Contribution per order")

            def model(recon=recon, contrib=contrib) -> None:  # type: ignore[no-untyped-def]
                expect(recon).to_contain_text("Card fees (paid by restaurants)", timeout=20000)
                expect(recon).to_contain_text("BhojanGo keeps")
                expect(recon.get_by_test_id("recon-identity")).to_contain_text("Captured = refunded + restaurants are owed + card fees")
                expect(recon).not_to_contain_text("Payment fees")
                expect(recon).not_to_contain_text("Platform after payment fees")
                expect(contrib).to_contain_text("Card fees (paid by restaurants, not BhojanGo)")
            check(f"R40 finance {market} {width} px: card fees are the restaurants' line; BhojanGo pays no payment fees", model)
            if rec_api is None:
                weeks = api.get(f"{CORE}/finance/payout-runs", headers=token("admin@example.com", PW), params={"country": country}).json()
                if weeks:
                    r0 = weeks[0]
                    rec_api = api.get(f"{CORE}/finance/reconciliation", headers=token("admin@example.com", PW), params={
                        "country": country, "start": r0["period_start"], "end": r0["period_end"]}).json()
            if rec_api:
                m = rec_api["money"]
                check(f"R40 reconciliation {market}: captured = refunded + restaurants + card fees + partners + tax + BhojanGo", lambda m=m: _ok(
                    m["captured"] == m["refunded"] + m["restaurant_payable"] + m["card_fees"] + m["rider_payable"] + m["tax_owed"] + m["platform_revenue"]))
                if (rec_api.get("not_in_run") or {}).get("orders"):
                    check(f"R40 reconciliation {market} {width} px: what the run doesn't pay yet is labelled, with why",
                          lambda recon=recon: expect(recon.get_by_test_id("not-in-run")).to_contain_text(
                              re.compile(rf"Not in this payout yet: {re.escape(cur)}[\d,.]+ \(\d+ orders?: .*\. Delivered after this payout run was prepared")))
            page.screenshot(path=f"{OUT}/r40-finance-admin{width}-{market}.png", full_page=True)
        # A restaurant statement: the card fee on each order line (US: the worked example's when it ran)
        statement = os.environ.get("WORKED_STATEMENT") if country == "US" else None
        if not statement:
            runs = api.get(f"{CORE}/finance/payout-runs", headers=token("admin@example.com", PW), params={"country": country}).json()
            if runs:
                detail = api.get(f"{CORE}/finance/payout-runs/{runs[0]['id']}", headers=token("admin@example.com", PW)).json()
                statement = next((st["id"] for st in detail["statements"] if st["payee_type"] == "restaurant" and st["summary"].get("orders")), None)
        if statement:
            for width in (1440, 390):
                page.set_viewport_size({"width": width, "height": 1000})
                page.goto(f"{BASE}/finance/statements/{statement}", wait_until="networkidle")
                check(f"R40 restaurant statement {market} {width} px: the card fee comes off the restaurant's line",
                      lambda: expect(page.locator("main")).to_contain_text(re.compile(r"[Cc]ard fee"), timeout=20000))
                page.screenshot(path=f"{OUT}/r40-statement-admin{width}-{market}.png", full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})

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
    RT = (os.environ.get("QA_RT") or "http://realtime:8004") + "/api/v1"

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
        page.get_by_role("region", name="Rules").get_by_test_id("row-source").filter(has_text="Inherited from United States · 0%").first).to_be_visible(timeout=15000))
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
    # R29 fee model v2: the US commission is 0% (customers pay a platform fee instead)
    check("commissions: the next order uses the country rate again (0%; R29)", lambda: _ok(Decimal(got2) == 0 and food2 > 0))

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
        expect(kc.get_by_test_id("kitchen-commission")).to_contain_text("0%", timeout=15000),  # R29: the US default
        expect(kc.get_by_test_id("kitchen-commission")).to_contain_text("country"),
        expect(kc.get_by_test_id("kitchen-tier")).to_have_text("B")))
    page.screenshot(path=f"{OUT}/06b-kitchen-commission.png", full_page=True)

    page.goto(f"{BASE}/markets/IN/IN-TG-HYD", wait_until="networkidle")
    check("markets: the city with its zones", lambda: expect(page.get_by_text(re.compile("Zones")).first).to_be_visible(timeout=15000))
    page.screenshot(path=f"{OUT}/08-markets-city.png")

    # R22 (S11): the kitchen offer ceiling, inherited from India and overridden on the city;
    # the API then refuses a kitchen's offer above it. Put back afterwards.
    ceiling_box = page.get_by_role("region", name="Restaurant offer ceiling")
    check("markets: the kitchen offer ceiling shows what the city inherits", lambda: (
        expect(ceiling_box.get_by_label("Amount off, per order")).to_have_attribute("placeholder", "200", timeout=15000),
        expect(ceiling_box.get_by_label("Most a %-off offer can take off one order")).to_be_visible(),
        expect(ceiling_box).to_contain_text(re.compile("From (India|BhojanGo's default)"))))
    ceiling_box.get_by_label("Amount off, per order").fill("150")
    ceiling_box.get_by_role("button", name="Save offer ceiling").click()

    def ceiling_saved() -> None:
        expect(ceiling_box.get_by_role("status")).to_contain_text("Saved", timeout=15000)
        r = api.post(f"{CORE}/restaurants/{rest['id']}/offers", headers=token("partner.hyd@example.com"), data={
            "template": "flat_off", "name": "Over the ceiling", "amount": "180", "weekly_cap": "1000"})
        assert r.status == 422 and "OFFER_OVER_CEILING" in r.text(), r.text()

    check("markets: a city's offer ceiling refuses a kitchen offer above it", ceiling_saved)
    ceiling_box.scroll_into_view_if_needed()
    ceiling_box.screenshot(path=f"{OUT}/08a-markets-offer-ceiling.png")
    api.patch(f"{CORE}/markets/cities/IN-TG-HYD", headers=token("admin@example.com", PW), data={"settings": {"kitchen_offer_ceiling": None}})

    # Markets for the website: a coming-soon city, its "Notify me" sign-ups (one sent
    # here like the website does), the demand card, and "Add a city".
    soon = next(c for k in api.get(f"{CORE}/markets/directory").json()["countries"] if k["code"] == "IN"
                for r in k["regions"] for c in r["cities"] if c["status"] == "soon")
    api.post(f"{CORE}/markets/waitlist", data={"email": f"admin-e2e-{uuid.uuid4().hex[:8]}@example.com", "consent": True,
                                                "source": "soon_city", "city_code": soon["code"]})
    page.goto(f"{BASE}/markets/IN", wait_until="networkidle")
    cities_table = page.get_by_role("region", name="States and cities")
    soon_row = cities_table.get_by_role("row", name=re.compile("^" + re.escape(soon["name"]) + " "))
    check("markets: a coming-soon city with its Notify me sign-ups", lambda: (
        expect(cities_table.get_by_role("cell", name="Notify me", exact=True)).to_be_visible(timeout=15000),
        expect(soon_row.get_by_role("cell", name="Coming soon")).to_be_visible(),
        expect(soon_row.get_by_role("cell").last).to_have_text(re.compile(r"^[1-9]\d*$"))))
    demand = page.get_by_role("region", name="Notify me demand")
    check("markets: the demand card counts sign-ups per city", lambda: (
        expect(demand.get_by_role("row", name=re.compile("^" + re.escape(soon["name"]) + r" [1-9]"))).to_be_visible(timeout=15000)))
    add = page.get_by_role("region", name="Add a city")
    add.get_by_role("button", name="New city").click()
    add.locator("select").first.select_option(label="Telangana")  # the State list
    add.get_by_label("City name").fill("Testville")
    check("add a city: the code is made from the state and the name", lambda: expect(add.get_by_label("City code")).to_have_value("IN-TG-TST"))
    # One E2E city, created on the first run only (cities aren't deleted): a draft, so the website never shows it.
    in_markets = api.get(f"{CORE}/markets/cities/IN-TG-TST", headers=token("admin@example.com", PW)).status == 200
    if in_markets:
        add.get_by_role("button", name="Cancel").click()
    else:
        add.get_by_label("Centre latitude").fill("17.95")
        add.get_by_label("Centre longitude").fill("79.10")
        add.get_by_role("button", name="Create city").click()
    check("add a city: a new city starts as a draft in its state", lambda: (
        expect(cities_table.get_by_role("row", name=re.compile(r"^Testville .*Draft"))).to_be_visible(timeout=15000)))
    page.screenshot(path=f"{OUT}/08b-markets-country.png", full_page=True)

    payouts = page.get_by_role("region", name="Payouts")
    check("markets: the country's payout provider, from Markets", lambda: (
        expect(payouts).to_contain_text("Razorpay Route", timeout=15000),
        expect(payouts.get_by_label("Payout provider")).to_have_value("razorpay_route")))

    # Hero dish: the website's landing photo for the country, picked from the library
    # thumbnails and saved as the country's hero_photo setting (put back afterwards).
    admin_h = token("admin@example.com", PW)
    before = api.get(f"{CORE}/markets", headers=admin_h).json()
    was = next(k for k in before if k["code"] == "IN")["settings"].get("hero_photo")
    hero = page.get_by_role("region", name="Hero dish")
    choice = "masala-dosa" if was != "masala-dosa" else "idli-sambar"
    hero.locator(f'[data-slug="{choice}"]').click()
    hero.get_by_role("button", name="Save hero dish").click()

    def hero_saved() -> None:
        expect(hero.get_by_role("status")).to_contain_text("Saved", timeout=15000)
        expect(hero.locator(f'[data-slug="{choice}"]')).to_have_attribute("aria-checked", "true")
        now = next(k for k in api.get(f"{CORE}/markets", headers=admin_h).json() if k["code"] == "IN")
        assert now["settings"].get("hero_photo") == choice, now["settings"]
        d = api.get(f"{CORE}/markets/directory").json()
        assert next(k for k in d["countries"] if k["code"] == "IN")["hero_photo"] == choice

    check("markets: the Hero dish picker saves the country's landing photo", hero_saved)
    check("markets: the Hero dish thumbnails load", lambda: _ok(hero.locator(f'[data-slug="{choice}"] img').evaluate(
        "img => img.complete && img.naturalWidth > 0")))
    page.screenshot(path=f"{OUT}/08c-markets-hero-dish.png", full_page=True)
    api.patch(f"{CORE}/markets/countries/IN", headers=admin_h, data={"settings": {"hero_photo": was}})

    # R16: India's tax settings are rules, flagged until a CA confirms them.
    page.goto(f"{BASE}/pricing?scope=IN&tab=tax", wait_until="networkidle")
    check("tax rules: India's GST settings say 'Confirm with CA' until confirmed", lambda: expect(
        page.get_by_role("region", name="Rules").get_by_test_id("ca-warning").first).to_be_visible(timeout=15000))
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("GST on food")).first.click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/07f-tax-rules-ca.png", full_page=True)
    page.goto(f"{BASE}/pricing?scope=IN&tab=business", wait_until="networkidle")
    check("business rules: GST on commission (18%) and TDS (0%), both to confirm with a CA", lambda: (
        expect(page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("GST on commission"))).not_to_have_count(0, timeout=15000),
        expect(page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("TDS on restaurant payouts"))).not_to_have_count(0)))
    page.get_by_role("region", name="Rules").get_by_role("button", name=re.compile("GST on commission")).first.click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/07g-commission-tax-rule.png", full_page=True)

    page.goto(f"{BASE}/finance?scope=IN", wait_until="networkidle")
    check("finance: payout runs and reconciliation", lambda: (
        expect(page.get_by_role("region", name="Payout runs")).to_be_visible(timeout=15000),
        expect(page.get_by_role("region", name="Reconciliation")).to_be_visible(timeout=20000)))
    check("reconciliation: tax owed by type (customers, on commission, TDS)", lambda: expect(
        page.get_by_test_id("tax-by-type")).to_contain_text("On commission", timeout=20000))
    page.screenshot(path=f"{OUT}/09-finance.png", full_page=True)
    page.goto(f"{BASE}/finance?scope=US", wait_until="networkidle")
    # R12: a run covers an ended week (Monday to Sunday) and the reports follow it: the week picker lists
    # only ended weeks, and the contribution shows last week's figures, or "—" and why when it had none.
    weeks = api.get(f"{CORE}/finance/payout-weeks", headers=fin_us, params={"country": "US"}).json()["weeks"]
    check("finance: the week picker lists only weeks that have ended, newest first", lambda: _ok(
        page.get_by_test_id("payout-week").locator("option").first.get_attribute("value") == weeks[0]["start"]
        and date.fromisoformat(weeks[0]["end"]) <= date.today() + timedelta(days=1)))
    check("finance: contribution per order; card fees are the restaurants' (R40)", lambda: (
        expect(page.get_by_role("region", name="Contribution per order")).to_contain_text("Card fees (paid by restaurants, not BhojanGo)", timeout=20000),
        expect(page.get_by_role("region", name="Contribution per order")).not_to_contain_text("Payment fees"),
        expect(page.get_by_role("region", name="Contribution per order")).to_contain_text(
            re.compile(r"\$[\d,]+\.\d{2}|No delivered orders in this week"), timeout=20000)))
    page.get_by_role("region", name="Contribution per order").screenshot(path=f"{OUT}/09b-contribution.png")

    page.goto(f"{BASE}/settings", wait_until="networkidle")
    check("settings: your access and the admins", lambda: (
        expect(page.get_by_role("region", name="Admins")).to_be_visible(timeout=15000),
        expect(page.get_by_text("ops.hyd@example.com")).to_be_visible()))
    page.screenshot(path=f"{OUT}/10-settings.png", full_page=True)

    # Content → Legal (R8 F10): edit a draft of the US Terms and publish it as the next version.
    page.goto(f"{BASE}/content/legal?scope=US", wait_until="networkidle")
    legal_list = page.get_by_test_id("legal-list")
    check("legal: the Content group in the nav, the US documents listed with their live version", lambda: (
        expect(page.get_by_role("navigation", name="Admin sections").get_by_role("link", name="Legal")).to_be_visible(),
        expect(page.get_by_role("group", name="Content").get_by_role("link", name="Legal")).to_be_visible(),
        expect(legal_list.get_by_role("row", name=re.compile("Terms of use.*Live · v\d+"))).not_to_have_count(0, timeout=15000)))
    live_before = api.get(f"{CORE}/legal/terms?country=US").json()["version"]
    form = page.get_by_role("form", name="Start a draft")
    form.get_by_label("Document").select_option("terms")
    form.get_by_label("Country").select_option("US")
    form.get_by_role("button", name="Start a draft").click()
    editor = page.get_by_test_id("legal-editor")
    check("legal: a new draft starts from the live text", lambda: (
        expect(editor.get_by_role("heading", name="Terms of use · US · EN")).to_be_visible(timeout=15000),
        expect(editor.get_by_test_id("legal-body")).to_have_value(re.compile("## 1. About these terms"))))
    point = f"Plain words about tips (e2e {uuid.uuid4().hex[:6]})"
    pts = editor.get_by_test_id("legal-points")
    pts.fill(pts.input_value() + "\n" + point)
    editor.get_by_label(re.compile("What changed")).fill("A key point about tips")
    editor.get_by_test_id("legal-save").click()
    check("legal: the draft saves", lambda: expect(editor.get_by_test_id("legal-msg")).to_have_text("Draft saved.", timeout=15000))
    editor.get_by_role("tab", name="Preview").click()
    check("legal: the preview reads the Markdown like the website", lambda: expect(
        editor.get_by_test_id("legal-preview").get_by_role("heading", name="1. About these terms")).to_be_visible())
    editor.get_by_test_id("legal-publish").click()
    check("legal: publishing asks once, naming the version", lambda: expect(editor.get_by_role("alertdialog")).to_contain_text(
        f"Publish version {live_before + 1} of Terms of use for US"))
    editor.get_by_test_id("legal-publish-confirm").click()
    check("legal: published as the next version, the old one replaced, audited", lambda: (
        expect(editor.get_by_test_id("legal-msg")).to_have_text(f"Published version {live_before + 1}.", timeout=15000),
        expect(editor.get_by_test_id("legal-audit")).to_contain_text("Published"),
        _ok(api.get(f"{CORE}/legal/terms?country=US").json()["version"] == live_before + 1),
        _ok(point in api.get(f"{CORE}/legal/terms?country=US").json()["key_points"]),
        _ok(api.get(f"{CORE}/legal/terms/versions/{live_before}?country=US").json()["status"] == "superseded")))
    page.screenshot(path=f"{OUT}/10b-legal.png", full_page=True)
    # Content -> Help (F9): India's country manager writes an article, publishes it, edits and publishes again.
    cm = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(cm, "cm.in@example.com")
    cm.goto(f"{BASE}/content/help?country=IN", wait_until="networkidle")
    check("help: Content > Help lists India's articles, filtered", lambda: (
        expect(cm.get_by_role("group", name="Content").get_by_role("link", name="Help")).to_be_visible(timeout=15000),
        expect(cm.get_by_role("region", name="Articles").get_by_role("link").first).to_be_visible(timeout=15000)))
    cm.screenshot(path=f"{OUT}/12-help-list.png", full_page=True)
    slug = f"e2e-help-{uuid.uuid4().hex[:6]}"
    cm.goto(f"{BASE}/content/help/new", wait_until="networkidle")
    cm.get_by_label("Slug (the address)").fill(slug)
    cm.get_by_label("Country").select_option("IN")
    cm.get_by_label("Language").select_option("en")
    cm.get_by_label("Topic").select_option("orders")
    cm.get_by_label("Title").fill("E2E: how help articles work")
    cm.get_by_label("Summary").fill("Written by the admin end-to-end run.")
    cm.get_by_test_id("help-body").fill("## First\n\nThe **first** version.\n\n- one\n- two")
    check("help editor: the preview shows the Markdown as the website will", lambda: (
        expect(cm.get_by_role("article", name="Preview").get_by_role("heading", name="First")).to_be_visible(),
        expect(cm.get_by_role("article", name="Preview").locator("strong", has_text="first")).to_be_visible()))
    cm.get_by_test_id("help-publish").click()
    expect(cm).to_have_url(re.compile(r"/content/help/[0-9a-f-]{36}$"), timeout=20000)

    def public_title() -> str:
        import json as _json
        import urllib.request
        with urllib.request.urlopen(f"{CORE}/help/articles/{slug}?country=IN&language=en", timeout=20) as r:
            return _json.loads(r.read())["title"]
    check("help: published, the website's API serves it", lambda: (
        expect(cm.get_by_text("Published", exact=True).first).to_be_visible(timeout=15000),
        _ok(public_title() == "E2E: how help articles work")))
    cm.get_by_label("Title").fill("E2E: how help articles work, edited")
    cm.get_by_test_id("help-save").click()
    check("help: a saved edit waits; the website still shows the live title", lambda: (
        expect(cm.get_by_text("Published · changes not live").first).to_be_visible(timeout=15000),
        _ok(public_title() == "E2E: how help articles work")))
    cm.get_by_test_id("help-publish").click()
    check("help: publishing the changes makes them live", lambda: (
        expect(cm.get_by_role("status").filter(has_text="Published.")).to_be_visible(timeout=15000),
        _ok(public_title() == "E2E: how help articles work, edited")))
    cm.screenshot(path=f"{OUT}/12b-help-editor.png", full_page=True)
    cm.get_by_role("tab", name="History").click()
    check("help: history lists every version with who made it", lambda: (
        expect(cm.get_by_role("list", name="Versions").get_by_role("listitem")).to_have_count(4, timeout=15000),
        expect(cm.get_by_role("list", name="Versions")).to_contain_text("India Country Manager")))
    hsup = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(hsup, "support.hyd@example.com")
    hsup.goto(f"{BASE}/content/help?country=IN", wait_until="networkidle")
    hsup.get_by_role("region", name="Articles").get_by_role("table").get_by_role("link").first.click()
    check("help: support reads articles but can't edit or publish", lambda: (
        expect(hsup.get_by_role("tab", name="Read")).to_be_visible(timeout=15000),
        expect(hsup.get_by_test_id("help-publish")).to_have_count(0)))

    # No raw data on any page: JSON-like text, "null", "undefined" or "NaN" fail the run.
    RAW = re.compile(r'[{\[]\s*"[A-Za-z_]+"\s*:|\bnull\b|\bundefined\b|\bNaN\b')
    pages = ["/overview", "/overview?scope=IN", "/overview?scope=US-ID-BOI", "/operations?scope=IN-TG-HYD&tab=live",
             "/operations?scope=IN-TG-HYD&tab=attention", "/operations?scope=IN-TG-HYD&tab=dispatch", "/operations?scope=IN-TG-HYD&tab=support",
             "/partners?scope=IN-TG-HYD&tab=kitchens", "/partners?scope=IN-TG-HYD&tab=applications", "/partners?scope=IN&tab=riders",
             "/markets", "/markets/IN", "/markets/IN/IN-TG-HYD", "/pricing/simulator?city=IN-TG-HYD", "/finance?scope=IN", "/finance?scope=US",
             "/settings", "/content/help", "/content/legal", "/content/legal?scope=IN"] + [f"/pricing?scope=IN-TG-HYD&tab={f}" for f in
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

    # Accessibility (R9): the main pages as the super admin sees them.
    for name, path in [("overview", "/overview"), ("operations", "/operations?scope=IN-TG-HYD&tab=live"),
                       ("partners", "/partners?scope=IN-TG-HYD&tab=kitchens"), ("pricing", "/pricing?scope=IN-TG-HYD&tab=delivery_fee"),
                       ("pricing-simulator", "/pricing/simulator?city=IN-TG-HYD"), ("markets", "/markets"), ("markets-country", "/markets/IN"),
                       ("markets-city", "/markets/IN/IN-TG-HYD"), ("finance", "/finance?scope=IN"), ("settings", "/settings"),
                       ("content-help", "/content/help"), ("content-legal", "/content/legal")]:
        page.goto(BASE + path, wait_until="networkidle")
        page.wait_for_timeout(800)
        check(f"a11y {name}: no serious or critical accessibility issues (axe)", lambda n=name: AXE.scan(page, n))
    page.goto(f"{BASE}/pricing?scope=IN-TG-HYD&tab=delivery_fee", wait_until="networkidle")
    # R31: Hyderabad's delivery fee from distance bands ("0–3 km: ₹30 · …")
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
    # R27: the console says so before asking the API (the API refuses too: test_zz_access_sweep.py)
    check("city ops: another country is refused", lambda: expect(ops.get_by_test_id("no-access")).to_contain_text(
        "You don't have access to Overview in", timeout=15000))

    # R17: the incident tools (docs/launch/incident-plan.md), as Hyderabad's city ops: pause ordering and a
    # kitchen (the website shows both), preview a bulk refund, message the city's customers, resume everything.
    # They write, so only on the CI / make dev stack: never on QA (tests never write to QA).
    if not os.environ.get("QA_ADMIN"):
        ops_h = token("ops.hyd@example.com", PW)
        forward(3002, ("web", 3000))
        web = "http://localhost:3002"
        try:
            ops.goto(f"{BASE}/incidents?scope=IN-TG-HYD", wait_until="networkidle")
            check("incidents: pause ordering, pause a kitchen, bulk refund, message customers and the log", lambda: [
                expect(ops.get_by_role("region", name=n)).to_be_visible(timeout=15000)
                for n in ("Pause ordering", "Pause a restaurant", "Bulk refund", "Message customers", "Incident log")])
            ops.screenshot(path=f"{OUT}/13-incidents.png", full_page=True)
            sec = ops.get_by_role("region", name="Pause ordering")
            sec.get_by_label("Note for customers").fill("Back by 9 pm")
            sec.get_by_role("button", name="Pause ordering…").click()
            dlg = ops.get_by_test_id("confirm-pause-ordering")
            check("incidents: pausing needs a reason before it can be confirmed", lambda:
                  expect(dlg.get_by_role("button", name="Yes, pause ordering")).to_be_disabled())
            dlg.get_by_label("Reason").fill("E2E drill: the payment provider is down")
            ops.screenshot(path=f"{OUT}/13a-incidents-confirm-pause.png", full_page=True)
            dlg.get_by_role("button", name="Yes, pause ordering").click()
            check("incidents: ordering in Hyderabad paused, with its reason", lambda: expect(
                sec.get_by_test_id("pause-row")).to_contain_text("E2E drill: the payment provider is down", timeout=15000))
            kit = ops.get_by_role("region", name="Pause a restaurant")
            kit.get_by_label("Find a restaurant").fill("Spice Route")
            kit.get_by_role("button", name="Spice Route Kitchen").first.click()
            kit.get_by_role("button", name="Pause Spice Route Kitchen…").click()
            kd = ops.get_by_test_id("confirm-pause-kitchen")
            kd.get_by_label("Reason").fill("E2E drill: gas supply cut")
            kd.get_by_role("button", name="Yes, pause the restaurant").click()
            check("incidents: Spice Route Kitchen closed for now", lambda: expect(
                kit.get_by_test_id("paused-kitchen")).to_contain_text("Spice Route Kitchen", timeout=15000))
            ops.screenshot(path=f"{OUT}/13b-incidents-paused.png", full_page=True)

            wp = b.new_page(viewport={"width": 1280, "height": 900})

            def web_shows_both() -> None:  # the site caches the pause 30 s and availability 60 s
                for _ in range(24):
                    wp.goto(f"{web}/in/hyderabad/spice-route-kitchen-madhapur", wait_until="networkidle")
                    if wp.get_by_test_id("ordering-paused").count() and wp.get_by_text("This restaurant is closed for now").count():
                        return
                    page_wait(5000)
                fail("the website didn't show the ordering pause and 'Closed for now' within 2 minutes")

            check("website: the city's ordering pause and the kitchen's 'Closed for now'", web_shows_both)
            check("website: the customers' note, not the admin's reason", lambda: (
                expect(wp.get_by_test_id("ordering-paused")).to_contain_text("Back by 9 pm"),
                expect(wp.get_by_text("E2E drill")).to_have_count(0)))
            check("website: the bag says ordering is paused instead of 'Pick a dish' (R18)", lambda: expect(
                wp.get_by_test_id("bag-blocked")).to_have_text("Ordering is paused"))
            wp.screenshot(path=f"{OUT}/13c-web-ordering-paused-kitchen-closed.png", full_page=False)
            wp.set_viewport_size({"width": 390, "height": 844})
            wp.reload(wait_until="networkidle")
            wp.screenshot(path=f"{OUT}/13d-web-phone-paused.png", full_page=False)
            wp.close()

            ref = ops.get_by_role("region", name="Bulk refund")
            ref.get_by_label("Restaurant").select_option(label="Spice Route Kitchen")
            ref.get_by_label("Refund", exact=True).select_option("percent")
            ref.get_by_label("Percent").fill("50")
            ref.get_by_role("button", name="Preview").click()
            check("bulk refund: the preview counts the orders and the total", lambda: expect(
                ref.get_by_test_id("refund-preview")).to_contain_text("order", timeout=15000))
            ref.get_by_role("button", name=re.compile(r"^Refund \d+ orders?…$")).click()
            ref.get_by_test_id("confirm-bulk-refund").get_by_label("Reason").fill("E2E drill: cold food in the outage")
            ops.screenshot(path=f"{OUT}/13e-incidents-bulk-refund-confirm.png", full_page=True)
            ref.get_by_test_id("confirm-bulk-refund").get_by_role("button", name="Cancel").click()  # previewed only

            msg = ops.get_by_role("region", name="Message customers")
            msg.get_by_label("Message", exact=True).select_option("area_paused")
            msg.get_by_role("button", name="Preview").click()
            check("message customers: the preview says who gets it and shows the message", lambda: expect(
                msg.get_by_test_id("message-preview")).to_contain_text("Ordering in Hyderabad is paused", timeout=15000))
            msg.get_by_role("button", name=re.compile(r"^Send to \d+…$")).click()
            msg.get_by_test_id("confirm-send-message").get_by_label("Reason").fill("E2E drill: tell the city's customers")
            ops.screenshot(path=f"{OUT}/13f-incidents-message-confirm.png", full_page=True)
            msg.get_by_test_id("confirm-send-message").get_by_role("button", name="Yes, send").click()
            check("message customers: sent", lambda: expect(msg.get_by_role("status")).to_contain_text("Sending now", timeout=15000))

            kit.get_by_role("button", name="Resume").first.click()
            ops.get_by_test_id("confirm-resume-kitchen").get_by_label("Reason").fill("E2E drill: gas back on")
            ops.get_by_test_id("confirm-resume-kitchen").get_by_role("button", name="Yes, resume").click()
            sec.get_by_role("button", name="Resume ordering").first.click()
            ops.get_by_test_id("confirm-resume-ordering").get_by_label("Reason").fill("E2E drill: provider is back")
            ops.get_by_test_id("confirm-resume-ordering").get_by_role("button", name="Yes, resume ordering").click()
            check("incidents: everything resumed, and the log has each step", lambda: (
                expect(sec.get_by_test_id("no-pauses")).to_be_visible(timeout=15000),
                expect(kit.get_by_test_id("paused-kitchen")).to_have_count(0, timeout=15000),
                expect(ops.get_by_test_id("incident-log")).to_contain_text("Customers messaged", timeout=15000),
                expect(ops.get_by_test_id("incident-log")).to_contain_text("Ordering resumed")))
            ops.screenshot(path=f"{OUT}/13g-incidents-log.png", full_page=True)
        finally:  # whatever failed above, Hyderabad and Spice Route are open again for anything after
            for pz in api.get(f"{CORE}/incidents/ordering-pauses/active").json():
                if pz["scope"] == "IN-TG-HYD":
                    api.post(f"{CORE}/incidents/ordering-pauses/{pz['id']}/end", headers=ops_h,
                             data={"reason": "E2E clean-up", "confirm": True})
            api.post(f"{CORE}/incidents/kitchens/{rest['id']}/resume", headers=ops_h, data={"reason": "E2E clean-up", "confirm": True})

    sup = b.new_page(viewport={"width": 1440, "height": 1000})
    sign_in(sup, "support.hyd@example.com")
    nav = sup.get_by_role("navigation", name="Admin sections")
    check("support agent: Operations and Partners, no Pricing, Markets or Finance", lambda: (
        expect(nav.get_by_role("link", name="Operations")).to_be_visible(timeout=15000),
        expect(nav.get_by_role("link", name="Pricing & Rules")).to_have_count(0),
        expect(nav.get_by_role("link", name="Finance")).to_have_count(0)))
    b.close()

AXE.write(OUT)
failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
raise SystemExit(1 if failed else 0)
