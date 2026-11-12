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


def fail(msg: str):  # type: ignore[no-untyped-def]
    raise AssertionError(msg)


forward(3001, ("admin", 3000))
BASE = "http://localhost:3001"

with sync_playwright() as p:
    b = p.chromium.launch()
    api = p.request.new_context()

    # A paid order at Spice Route Kitchen, so there's something live.
    def token(email: str, pw: str = "BhojanGo123") -> dict:
        r = api.post(f"{CORE}/auth/login", data={"email": email, "password": pw})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

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
    page.get_by_role("region", name="Rules").get_by_role("button").first.click()
    check("pricing & rules: a rule's settings, where it comes from, history", lambda: (
        expect(page.get_by_role("heading", name="History")).to_be_visible(timeout=15000),
        expect(page.get_by_role("button", name=re.compile("^Approvals"))).to_be_visible()))
    page.screenshot(path=f"{OUT}/07-pricing-rules.png", full_page=True)
    page.get_by_role("link", name="Price simulator", exact=True).click()
    check("price simulator opens from Pricing & Rules", lambda: expect(page.get_by_role("heading", name=re.compile("Price simulator"))).to_be_visible(timeout=15000))

    page.goto(f"{BASE}/markets/IN/IN-TG-HYD", wait_until="networkidle")
    check("markets: the city with its zones", lambda: expect(page.get_by_text(re.compile("Zones")).first).to_be_visible(timeout=15000))
    page.screenshot(path=f"{OUT}/08-markets-city.png")

    page.goto(f"{BASE}/finance?scope=IN", wait_until="networkidle")
    check("finance: payout runs and reconciliation", lambda: (
        expect(page.get_by_role("region", name="Payout runs")).to_be_visible(timeout=15000),
        expect(page.get_by_role("region", name="Reconciliation")).to_be_visible(timeout=20000)))
    page.screenshot(path=f"{OUT}/09-finance.png", full_page=True)

    page.goto(f"{BASE}/settings", wait_until="networkidle")
    check("settings: your access and the admins", lambda: (
        expect(page.get_by_role("region", name="Admins")).to_be_visible(timeout=15000),
        expect(page.get_by_text("ops.hyd@example.com")).to_be_visible()))
    page.screenshot(path=f"{OUT}/10-settings.png", full_page=True)

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
