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
    page.get_by_label("Code").fill("123456")
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
