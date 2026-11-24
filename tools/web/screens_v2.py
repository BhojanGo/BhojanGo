"""Full-page screenshots of every designed website page (docs/design/web) on seed data.

    sh tools/web/screens_v2.sh            (runs this in the Playwright image)

Saves <DesignName>.png (WebLanding, WebHome, ..., MWebSignIn) into OUT
(docs/screenshots/web-v2/raw), ready for tools/web/design_compare.py. Desktop
pages at 1440 px, MWeb* at 390 px. The states match the designs: a signed-in
customer with the Madhapur address, an order on its way (placed through the
APIs, driven by the kitchen, ops and a rider, and delivered at the end), two
dishes in the bag, a saved kitchen and dish (removed again at the end).
"""
import json
import os
import re
import socket
import sys
import threading
import urllib.parse
import urllib.request
import uuid

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
BASE = "http://localhost:3000"
FORWARD = {3000: ("web", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
KITCHEN_PATH = "/in/hyderabad/spice-route-kitchen-madhapur"
CUSTOMER = "customer1.hyd@example.com"

# Tests never write to QA or production (tools/target_guard.py; at /guard in the Playwright image).
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # this folder: web_session
import web_session  # noqa: E402  (the website's session in cookies, R22 S8)

ensure_safe_api("http://core-api:8001")


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


def api(method: str, path: str, token: str | None = None, body: dict | None = None, host: int = 8001,
        headers: dict | None = None) -> dict:
    req = urllib.request.Request(f"http://localhost:{host}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {}),
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def tokens(email: str, password: str = "BhojanGo123") -> dict:
    from totp_signin import finish  # admins: the second step (seed key)

    return finish(lambda path, data: api("POST", path, None, data), email,
                  api("POST", "/auth/login", None, {"email": email, "password": password}))


def sub(token: str) -> str:
    import base64

    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"]


done: list[str] = []


def save(page, name: str, full: bool = True) -> None:  # type: ignore[no-untyped-def]
    page.wait_for_timeout(800)  # fonts, images
    page.screenshot(path=f"{OUT}/{name}.png", full_page=full)
    done.append(name)
    print("saved", name, flush=True)


for port, target in FORWARD.items():
    forward(port, target)

# ── Data the designs show: an order on its way, a saved kitchen and dish ───────
t = tokens(CUSTOMER)
cust = t["access_token"]
me = api("GET", "/users/me", cust)
home = next(a for a in api("GET", "/me/addresses", cust) if a.get("is_default"))
kitchen = api("GET", "/restaurants/by-slug/spice-route-kitchen-madhapur")
menu = api("GET", f"/restaurants/{kitchen['id']}/menu")
dishes = {i["name"]: i for c in menu["categories"] for i in c["items"]}
biryani = dishes["Chicken Dum Biryani"]
picks = [{"group": g["name"], "option": next((o for o in g["options"] if o.get("is_default")), g["options"][0])["name"]}
         for g in biryani.get("option_groups") or [] if g.get("min_picks", 0) >= 1]  # the required choices, as the sheet preselects them
cart = [{"menu_item_id": biryani["id"], "quantity": 2, "options": picks}]
quote = api("POST", "/pricing/quote", cust, {"restaurant_id": kitchen["id"], "items": cart, "deliver_to": {"address_id": home["id"]}, "tip": 30})
order = api("POST", "/orders", cust, {
    "restaurant_id": kitchen["id"], "items": cart, "payment_method": "upi", "quote_token": quote["token"],
    "delivery_address": {"street": home["street"], "city": home["city"], "state": home.get("state") or "", "zip": home.get("postal_code") or "",
                         "country": home["country"], "lat": home.get("lat"), "lng": home.get("lng")}},
    headers={"X-Idempotency-Key": str(uuid.uuid4())})
intent = api("POST", "/payments/initiate", cust, {"order_id": order["id"], "payment_method_type": "upi"})
api("POST", f"/payments/fake/{intent['payment_intent_id']}/complete", cust, {"outcome": "succeeded"})
partner = tokens("partner.hyd@example.com")["access_token"]
ops = tokens("ops.hyd@example.com", "BhojanGoAdmin1")["access_token"]
rider = tokens("rider3.hyd@example.com")["access_token"]
for st in ("accepted", "preparing", "ready"):
    api("PUT", f"/orders/{order['id']}/status", partner, {"status": st})
api("POST", "/delivery/assign", ops, {"order_id": order["id"], "driver_id": sub(rider)}, host=8004)
api("PUT", f"/orders/{order['id']}/status", rider, {"status": "picked_up"})
api("PUT", f"/me/favourites/restaurant/{kitchen['id']}", cust)
api("PUT", f"/me/favourites/item/{biryani['id']}", cust)

# The address cookie the site sets after sign-in: the default saved address.
loc = api("GET", f"/markets/locate?lat={home['lat']}&lng={home['lng']}")
place = {"label": f"{loc.get('zone_name')}, {loc.get('city_name')}", "lat": home["lat"], "lng": home["lng"], "country": loc.get("country_code"),
         "city_code": loc.get("city_code"), "city_path": "/in/hyderabad", "zone": loc.get("zone_name"), "served": True, "address_id": home["id"]}
session = web_session.script(me)
session_jar = web_session.cookies("http://localhost:8001", cust, t["refresh_token"])

try:
    with sync_playwright() as p:
        b = p.chromium.launch()

        def anon(width: int = 1440, height: int = 900):  # type: ignore[no-untyped-def]
            return b.new_context(viewport={"width": width, "height": height}).new_page()

        def signed_in(width: int = 1440, height: int = 900):  # type: ignore[no-untyped-def]
            ctx = b.new_context(viewport={"width": width, "height": height})
            ctx.add_cookies([{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": BASE}])
            ctx.add_init_script(session)
            ctx.add_cookies(session_jar)
            return ctx.new_page()

        def bag_with_two(page) -> None:  # type: ignore[no-untyped-def]
            page.goto(BASE + KITCHEN_PATH, wait_until="networkidle")
            page.get_by_role("button", name="Add Chicken Dum Biryani").click()
            page.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
            page.get_by_role("button", name="Add Double Ka Meetha").click()
            sheet = page.get_by_role("dialog")
            if sheet.count():
                sheet.get_by_role("button", name=re.compile("^Add to cart")).click()
            expect(page.locator("text=/2 items/ >> visible=true").first).to_be_visible(timeout=15000)  # the bag (desktop) or the bag bar (phone)

        # ── signed out ────────────────────────────────────────────────────────
        pg = anon()
        pg.goto(BASE, wait_until="networkidle")
        save(pg, "WebLanding")
        pg.goto(BASE + "/signin", wait_until="networkidle")
        save(pg, "WebSignIn")
        pg.goto(BASE + "/signin/code?phone=%2B919000000101&country=IN&next=%2F", wait_until="networkidle")
        save(pg, "WebOTP")
        pg.goto(BASE + "/in/hyderabad", wait_until="networkidle")
        save(pg, "WebCity")
        pg.goto(BASE + "/cities", wait_until="networkidle")
        save(pg, "WebCities")
        # An address outside every zone, in a country we serve (the design: a town near a live city).
        far = {"label": "Twin Falls, Idaho", "lat": 42.5558, "lng": -114.4701, "country": "US", "city_code": None, "city_path": None, "zone": None, "served": False}
        pg.context.add_cookies([{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(far)), "url": BASE}])
        pg.goto(BASE, wait_until="networkidle")
        save(pg, "WebNotInArea")
        m = anon(390, 844)
        m.goto(BASE + "/signin", wait_until="networkidle")
        save(m, "MWebSignIn")

        # ── signed in, Madhapur, an order on its way ─────────────────────────
        pg = signed_in()
        pg.goto(BASE, wait_until="networkidle")
        expect(pg.get_by_role("region", name="Your order")).to_be_visible(timeout=20000)
        save(pg, "WebHome")
        pg.goto(f"{BASE}/orders/{order['id']}/track", wait_until="networkidle")
        expect(pg.locator('[data-testid="delivery-pin"]:visible')).to_be_visible(timeout=20000)
        save(pg, "WebTracking")
        pg.set_viewport_size({"width": 1440, "height": 1240})  # the design's frame; the sheet is fixed to the window
        pg.goto(BASE + KITCHEN_PATH, wait_until="networkidle")
        pg.get_by_role("button", name="Add Chicken Dum Biryani").click()
        pg.get_by_role("dialog").get_by_text("Extra raita").click()
        save(pg, "WebCustomise", full=False)
        pg.get_by_role("dialog").get_by_role("button", name="Close").click()
        pg.set_viewport_size({"width": 1440, "height": 900})
        bag_with_two(pg)
        save(pg, "WebKitchen")
        pg.goto(BASE + "/checkout", wait_until="networkidle")
        expect(pg.get_by_role("complementary", name="Your order").get_by_role("row").first).to_be_visible(timeout=20000)
        save(pg, "WebCheckout")
        pg.goto(BASE + "/account/orders", wait_until="networkidle")
        pg.get_by_role("group", name="Show orders").get_by_role("button", name="Delivered").click()
        pg.get_by_role("main").get_by_role("button", name=re.compile(r"· #[0-9A-F]{6} Delivered$")).first.click()
        expect(pg.get_by_role("article").get_by_role("row").first).to_be_visible(timeout=15000)
        save(pg, "WebOrders")
        pg.goto(BASE + "/account/profile", wait_until="networkidle")
        expect(pg.get_by_role("switch").first).to_be_visible(timeout=15000)
        save(pg, "WebProfile")
        pg.goto(BASE + "/account/favourites", wait_until="networkidle")
        expect(pg.get_by_role("main").get_by_text("Chicken Dum Biryani").first).to_be_visible(timeout=15000)
        save(pg, "WebFavourites")

        m = signed_in(390, 844)
        m.goto(BASE, wait_until="networkidle")
        expect(m.get_by_role("region", name="Your order")).to_be_visible(timeout=20000)
        save(m, "MWebHome")
        m.goto(f"{BASE}/orders/{order['id']}/track", wait_until="networkidle")
        expect(m.locator('[data-testid="delivery-pin"]:visible')).to_be_visible(timeout=20000)
        save(m, "MWebTracking")
        bag_with_two(m)
        m.goto(BASE + KITCHEN_PATH, wait_until="networkidle")
        save(m, "MWebMenu")
        m.goto(BASE + "/checkout", wait_until="networkidle")
        expect(m.get_by_role("row").first).to_be_visible(timeout=20000)
        save(m, "MWebCheckout")
        b.close()
finally:
    # Leave the seed as it was: the order delivered, the favourites removed.
    pin = api("GET", f"/orders/{order['id']}", cust).get("pin")
    api("PUT", f"/orders/{order['id']}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    api("DELETE", f"/me/favourites/restaurant/{kitchen['id']}", cust)
    api("DELETE", f"/me/favourites/item/{biryani['id']}", cust)

print(f"{len(done)} screenshots in {OUT}")
sys.exit(0 if len(done) == 19 else 1)
