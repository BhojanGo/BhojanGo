"""Playwright end-to-end run of the customer web (P20) against `make dev`.

Runs inside mcr.microsoft.com/playwright/python on the compose network
(tools/web/e2e.sh). The browser talks to localhost like a person's would:
localhost:3000 (web), :8001 (core_api) and :8004 (realtime) are forwarded to
the compose services, so CORS and the app's API URLs are exactly as in dev.
Screenshots go to docs/screenshots/web.
"""
import json
import os
import socket
import threading

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
FORWARD = {3000: ("web", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
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


def shot(page, name: str) -> None:  # type: ignore[no-untyped-def]
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)


def api(method: str, path: str, token: str | None = None, body: dict | None = None, host: int = 8001) -> dict:
    """The rest of the world (kitchen, ops, rider) through the same APIs the apps use."""
    import urllib.request

    req = urllib.request.Request(f"http://localhost:{host}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def login(email: str, password: str = "BhojanGo123") -> str:
    return api("POST", "/auth/login", None, {"email": email, "password": password})["access_token"]


def sub(token: str) -> str:
    import base64

    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"]


def _assert(ok: bool) -> None:
    assert ok


def no_sideways_scroll(page) -> None:  # type: ignore[no-untyped-def]
    w = page.evaluate("document.documentElement.scrollWidth")
    assert w <= 392, f"page is {w}px wide at 390"


for port, target in FORWARD.items():
    forward(port, target)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, geolocation={"latitude": 17.4483, "longitude": 78.3915},
                        permissions=["geolocation"])
    page = ctx.new_page()
    base = "http://localhost:3000"

    page.goto(base, wait_until="networkidle")
    check("home: promise, cities and kitchens", lambda: (
        expect(page.get_by_role("heading", name="Real food. Fair prices.")).to_be_visible(),
        expect(page.get_by_role("link", name="Order in Hyderabad")).to_be_visible(),
        expect(page.get_by_role("heading", name="Kitchens in Boise")).to_be_visible(),
        expect(page.get_by_role("link", name="Spice Route Kitchen").first).to_be_visible()))
    fig = page.get_by_role("figure", name="An example of the fair bill")
    check("home: the example bill is a real quote (engine, Hyderabad rules) with who gets each line", lambda: (
        expect(fig.get_by_text("The fair bill")).to_be_visible(),
        expect(fig.get_by_text(__import__("re").compile("A real Hyderabad bill"))).to_be_visible(),
        expect(fig.get_by_text("GOVT").first).to_be_visible()))
    # The delivery fee is ours (riders are paid separately); RIDER is only the tip.
    rows = fig.locator("dt").all_inner_texts()
    payees = fig.locator("dd").all_inner_texts()
    check("fair bill: delivery fee is US, tip is RIDER", lambda: (
        payees[2 * next(i for i, r in enumerate(rows) if r.lower().startswith("delivery"))] == "US"
        and payees[2 * next(i for i, r in enumerate(rows) if "tip" in r.lower())] == "RIDER")
        or (_ for _ in ()).throw(AssertionError(list(zip(rows, payees[::2])))))
    shot(page, "01-home")

    page.get_by_role("link", name="Order in Hyderabad").click()
    page.wait_for_url("**/hyderabad")
    check("city page: title, heading, ItemList for search engines", lambda: (
        expect(page).to_have_title("Food delivery in Hyderabad · BhojanGo"),
        expect(page.get_by_role("heading", name="Food delivery in Hyderabad")).to_be_visible(),
        json.loads(page.locator('script[type="application/ld+json"]').first.inner_text())["@type"] == "ItemList" or (_ for _ in ()).throw(AssertionError("no ItemList")),
        expect(page.locator('link[rel="canonical"]')).to_have_attribute("href", "https://bhojango.com/hyderabad")))
    shot(page, "02-city")

    page.get_by_role("link", name="Spice Route Kitchen").first.click()
    page.wait_for_url("**/hyderabad/spice-route-kitchen-madhapur")
    ld = lambda: json.loads(page.locator('script[type="application/ld+json"]').first.inner_text())  # noqa: E731
    check("restaurant page: menu, Restaurant + Menu structured data", lambda: (
        expect(page.get_by_role("heading", name="Spice Route Kitchen", level=1)).to_be_visible(),
        expect(page.get_by_role("heading", name="Biryani")).to_be_visible(),
        ld()["@type"] == "Restaurant" and ld()["hasMenu"]["hasMenuSection"] or (_ for _ in ()).throw(AssertionError(ld()))))
    page.get_by_role("button", name="Chicken Dum Biryani").click()
    dialog = page.get_by_role("dialog", name="Chicken Dum Biryani")
    check("dish sheet: options with prices", lambda: expect(dialog.get_by_text("Extra raita")).to_be_visible())
    dialog.get_by_text("Extra raita").click()
    shot(page, "03-dish-options")
    dialog.get_by_role("button", name="Add to bag").click()
    check("bag: dish added with its options", lambda: (
        expect(page.get_by_role("link", name="Bag, 1 items")).to_be_visible(),
        expect(page.get_by_text("Extra raita").first).to_be_visible()))
    shot(page, "04-restaurant-bag")

    page.get_by_role("link", name="Go to checkout").click()
    check("checkout asks to sign in, keeps the bag", lambda: expect(page.get_by_role("link", name="Sign in with your phone")).to_be_visible())
    page.get_by_role("link", name="Sign in with your phone").click()
    page.locator("#phone").fill("9000000101")
    shot(page, "05-sign-in")
    page.get_by_role("button", name="Send code").click()
    page.get_by_label("Code", exact=True).fill("123456")
    page.get_by_role("button", name="Verify").click()
    page.wait_for_url("**/checkout")
    check("checkout: saved address, live fair bill with who gets what", lambda: (
        expect(page.get_by_text("The fair bill")).to_be_visible(timeout=20000),
        expect(page.get_by_text("KITCHEN").first).to_be_visible(),
        expect(page.get_by_text("GOVT").first).to_be_visible(),
        expect(page.get_by_text("Price held for")).to_be_visible()))
    page.get_by_role("radio", name="₹20").click()
    check("tip: shown on the bill as the rider's", lambda: expect(page.get_by_text("RIDER").first).to_be_visible())
    shot(page, "06-checkout")
    page.get_by_role("button", name="Pay").click()
    page.get_by_role("button", name="Approve").click()
    page.wait_for_url("**/orders/*", timeout=40000)
    order_url = page.url
    check("tracking: arrival time, steps, PIN for the door, the bill paid", lambda: (
        expect(page.get_by_text("Spice Route Kitchen has your order")).to_be_visible(timeout=20000),
        expect(page.get_by_test_id("eta")).to_be_visible(),
        expect(page.get_by_test_id("delivery-pin")).to_have_text(__import__("re").compile(r"^\d{4}$")),
        expect(page.get_by_text("You paid")).to_be_visible()))
    shot(page, "07-tracking")

    page.goto(f"{base}/orders", wait_until="networkidle")
    check("your orders: the new order is on its way", lambda: (
        expect(page.get_by_role("heading", name="On its way")).to_be_visible(),
        expect(page.get_by_text("Spice Route Kitchen").first).to_be_visible()))
    shot(page, "08-orders")

    # Quick messages with the rider (B2): the kitchen gets it ready, ops assigns a
    # rider, and the rider and the customer message each other; no phone numbers,
    # and the conversation is gone once the order is delivered.
    order_id = order_url.rstrip("/").split("/")[-1]
    partner, ops, rider = login("partner.hyd@example.com"), login("ops.hyd@example.com", "BhojanGoAdmin1"), login("rider3.hyd@example.com")
    for st in ("accepted", "preparing", "ready"):
        api("PUT", f"/orders/{order_id}/status", partner, {"status": st})
    api("POST", "/delivery/assign", ops, {"order_id": order_id, "driver_id": sub(rider)}, host=8004)
    api("POST", f"/orders/{order_id}/messages", rider, {"preset": "at_kitchen"})
    page.goto(order_url, wait_until="networkidle")
    chat = page.get_by_role("region", name=__import__("re").compile("^Messages with "))
    check("messages: the rider's quick message arrives on the tracking page", lambda: (
        expect(chat).to_be_visible(timeout=20000),
        expect(chat.get_by_text("I'm at the kitchen, waiting for your order.")).to_be_visible(),
        expect(chat.get_by_text("Your number stays private")).to_be_visible()))
    chat.get_by_role("button", name="I'm coming down.").click()
    chat.get_by_label("Write a short message").fill("Gate 2, my number is 98480 22334")
    chat.get_by_role("button", name="Send").click()
    check("messages: the customer's replies reach the rider, phone number hidden", lambda: (
        expect(chat.get_by_text("Gate 2, my number is •••")).to_be_visible(timeout=10000),
        _assert([m["text"] for m in api("GET", f"/orders/{order_id}/messages", rider)["messages"]][-2:]
                == ["I'm coming down.", "Gate 2, my number is •••"])))
    api("POST", f"/orders/{order_id}/messages", rider, {"preset": "outside"})
    check("messages: live from the rider without reloading", lambda: expect(chat.get_by_text("I'm outside.")).to_be_visible(timeout=15000))
    shot(page, "13-messages")
    pin = page.get_by_test_id("delivery-pin").inner_text()
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "picked_up"})
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    page.reload(wait_until="networkidle")
    check("messages: hidden after delivery", lambda: (
        expect(page.get_by_text("Delivered. Enjoy your meal.")).to_be_visible(timeout=20000),
        expect(chat).to_have_count(0)))

    for path, heading in (("/help", "Help"), ("/terms", "Terms of use"), ("/privacy", "Privacy notice")):
        page.goto(base + path, wait_until="networkidle")
        check(f"{path}: readable page", lambda h=heading: expect(page.get_by_role("heading", name=h, level=1)).to_be_visible())
    shot(page, "09-privacy")

    r = page.request.get(f"{base}/sitemap.xml")
    check("sitemap lists city and restaurant pages", lambda: (
        "https://bhojango.com/boise" in r.text() and "/hyderabad/spice-route-kitchen-madhapur" in r.text()
        and "kesar-kitchen" not in r.text()) or (_ for _ in ()).throw(AssertionError(r.text()[:300])))
    rb = page.request.get(f"{base}/robots.txt").text()
    check("robots keeps checkout and orders out", lambda: ("Disallow: /checkout" in rb and "Disallow: /orders" in rb) or (_ for _ in ()).throw(AssertionError(rb)))
    check("unknown kitchen is a 404", lambda: page.request.get(f"{base}/hyderabad/no-such-kitchen").status == 404 or (_ for _ in ()).throw(AssertionError("not 404")))
    check("old /restaurants URL redirects home", lambda: page.request.get(f"{base}/restaurants", max_redirects=0).status in (301, 308) or (_ for _ in ()).throw(AssertionError("no redirect")))

    # A kitchen applies on the web with a brand-new number (B1).
    k = b.new_context(viewport={"width": 1280, "height": 900}).new_page()
    k.goto(base + "/partner", wait_until="networkidle")
    k.get_by_role("link", name="Sign in to apply").click()
    k.locator("#phone").fill(f"90000{__import__('random').randint(10000, 99999)}")
    k.get_by_role("button", name="Send code").click()
    k.get_by_label("Code", exact=True).fill("123456")
    k.get_by_role("button", name="Verify").click()
    k.wait_for_url("**/partner", timeout=20000)
    form = k.get_by_role("form", name="Apply with your kitchen")
    for label, value in (("Your name", "Lata Menon"), ("Kitchen name", "Lata's Kitchen"), ("Area", "Banjara Hills"),
                         ("Street address", "Plot 9, Road 12"), ("PIN / ZIP code", "500034"), ("Cuisines", "Kerala, Thali")):
        form.get_by_label(label, exact=True).fill(value)
    k.screenshot(path=f"{OUT}/11-partner-apply.png", full_page=True)
    form.get_by_role("button", name="Send application").click()
    check("kitchen sign-up on the web: application created, FSSAI step next", lambda: (
        expect(k.get_by_role("region", name="Your application")).to_be_visible(timeout=20000),
        expect(k.get_by_text("Lata's Kitchen · 1 of 5 done")).to_be_visible(),
        expect(k.get_by_label("FSSAI licence number")).to_be_visible()))
    k.get_by_label("FSSAI licence number").fill("13623012000487")
    k.get_by_label("Valid until").fill("2028-03-31")
    k.get_by_role("button", name="Save licence").click()
    check("kitchen sign-up on the web: licence saved, GST next", lambda: expect(k.get_by_text("Lata's Kitchen · 2 of 5 done")).to_be_visible(timeout=15000))
    k.screenshot(path=f"{OUT}/12-partner-application.png", full_page=True)

    m = b.new_page(viewport={"width": 390, "height": 844})
    for path in ("/", "/hyderabad", "/hyderabad/spice-route-kitchen-madhapur", "/help"):
        m.goto(base + path, wait_until="networkidle")
        check(f"phone width {path}: no sideways scroll", lambda: no_sideways_scroll(m))
    m.goto(base + "/hyderabad/spice-route-kitchen-madhapur", wait_until="networkidle")
    m.screenshot(path=f"{OUT}/10-restaurant-phone.png", full_page=False)
    b.close()

failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
raise SystemExit(1 if failed else 0)
