"""Playwright end-to-end run of the customer website (web v2) against `make dev`.

Runs inside mcr.microsoft.com/playwright/python on the compose network
(tools/web/e2e.sh). The browser talks to localhost like a person's would:
localhost:3000 (web), :8001 (core_api) and :8004 (realtime) are forwarded to
the compose services, so CORS and the app's API URLs are exactly as in dev.
Screenshots go to docs/screenshots/web.

What it walks through (desktop 1440 unless noted), all on seed data:
first visit (landing, directory, Notify me, country and language menus), the
address box -> personal home (offers, kitchen cards, filters), an address we
don't serve yet, /cities and city pages, a kitchen page with the customise
sheet and the bag, phone + OTP sign-in, checkout with the fair bill and a tip,
the fake payment provider, tracking to "delivered" (kitchen, ops and rider via
their APIs), the account area (orders, receipt, PDF, order again, report a
problem, addresses, a test card, notifications, data export, favourites), no
marketing when signed in, a US kitchen in dollars, SEO files and headers, and
no sideways scroll at 390 px.
"""
import json
import os
import random
import re
import socket
import sys
import threading

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
FORWARD = {3000: ("web", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
results: list[tuple[str, bool, str]] = []
ERR = int(os.environ.get("E2E_ERR_CHARS", "300"))  # more of each failure's message when debugging

# Hosted QA (Railway): the public URLs come from QA_WEB / QA_ADMIN / QA_CORE / QA_RT
# and the seed's random passwords from E2E_LOGINS_FILE (outside the repo).
PASSWORDS: dict[str, str] = {}
if os.environ.get("E2E_LOGINS_FILE"):
    with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as _f:
        PASSWORDS = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in _f) if len(r) == 4}
QA_WEB, QA_CORE, QA_RT = os.environ.get("QA_WEB", ""), os.environ.get("QA_CORE", ""), os.environ.get("QA_RT", "")
# The site's own address in canonical links and the sitemap (NEXT_PUBLIC_APP_URL):
# bhojango.com locally and in production, the QA web domain on QA.
SITE = QA_WEB or "https://bhojango.com"

# Tests never write to QA or production (tools/target_guard.py; at /guard in the Playwright image).
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402

ensure_safe_api(QA_CORE or "http://core-api:8001")

# Seed data (tools/seed/data.py). The website never names these; the test may.
HYD_PHONE, US_PHONE, OTP = "9000000101", "2085550101", "123456"
KITCHEN, KITCHEN_PATH = "Spice Route Kitchen", "/in/hyderabad/spice-route-kitchen-madhapur"
DISH = "Chicken Dum Biryani"
US_KITCHEN, US_KITCHEN_PATH = "Boise Bowl Co.", "/us/boise/boise-bowl-co-hyde-park"


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
        results.append((name, False, str(e)[:ERR]))
        print("FAIL", name, str(e)[:ERR], flush=True)


def step(name: str, fn) -> bool:  # type: ignore[no-untyped-def]
    """A setup step the checks after it need: recorded like a check, returns whether it worked."""
    check(name, fn)
    return results[-1][1]


def shot(page, name: str) -> None:  # type: ignore[no-untyped-def]
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)


def api(method: str, path: str, token: str | None = None, body: dict | None = None, host: int = 8001) -> dict:
    """The rest of the world (kitchen, ops, rider) through the same APIs the apps use."""
    import urllib.request

    root = (QA_RT if host == 8004 else QA_CORE) or f"http://localhost:{host}"
    req = urllib.request.Request(f"{root}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def login(email: str, password: str = "BhojanGo123") -> str:
    return api("POST", "/auth/login", None, {"email": email, "password": PASSWORDS.get(email, password)})["access_token"]


def sub(token: str) -> str:
    import base64

    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"]


def _assert(ok: bool, why: object = "") -> None:
    if not ok:
        raise AssertionError(why)


def eventually(fn, timeout: float = 15) -> None:  # type: ignore[no-untyped-def]
    """Retry an API-side assertion until it holds (the page's request may still be on its way)."""
    import time

    end = time.monotonic() + timeout
    while True:
        try:
            fn()
            return
        except AssertionError:
            if time.monotonic() > end:
                raise
            time.sleep(0.5)


def no_sideways_scroll(page) -> None:  # type: ignore[no-untyped-def]
    w = page.evaluate("document.documentElement.scrollWidth")
    assert w <= 392, f"page is {w}px wide at 390"


def url_is(page, pattern: str, timeout: int = 20000) -> None:  # type: ignore[no-untyped-def]
    """Client-side navigations (router.push) never fire "load": wait on the URL itself."""
    expect(page).to_have_url(re.compile(pattern), timeout=timeout)


def sign_in(page, phone: str, country: str | None = None) -> None:  # type: ignore[no-untyped-def]
    """/signin -> /signin/code with the seed's fixed OTP (the page must already be /signin)."""
    if country:
        page.get_by_label("Country code").select_option(country)
    page.get_by_role("textbox", name="Mobile number").fill(phone)
    page.get_by_role("button", name="Send code").click()
    url_is(page, r"/signin/code\?")
    page.get_by_role("textbox", name="Digit 1").fill(OTP)  # pasting fills all six boxes
    page.get_by_role("button", name="Verify and continue").click()


def cookie(ctx, name: str) -> str | None:  # type: ignore[no-untyped-def]
    return next((c["value"] for c in ctx.cookies() if c["name"] == name), None)


if not QA_WEB:  # make dev: forward localhost to the compose services
    for port, target in FORWARD.items():
        forward(port, target)

RUN = random.randint(100000, 999999)

with sync_playwright() as p:
    b = p.chromium.launch()
    base = QA_WEB or "http://localhost:3000"
    admin = login("admin@example.com", "BhojanGoAdmin1")

    # ── First visit: no address, no account ───────────────────────────────────
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(base, wait_until="networkidle")
    directory = api("GET", "/markets/directory")
    cities = [c for k in directory["countries"] for r in k["regions"] for c in r["cities"]]
    live = [c for c in cities if c["status"] == "live"]
    soon = [c for c in cities if c["status"] == "soon"]
    dir_region = page.get_by_role("region", name="Where we deliver")
    check("landing: hero with the address box, no address yet", lambda: (
        expect(page.get_by_role("heading", name="Real food. Fair prices.", level=1)).to_be_visible(),
        expect(page.get_by_role("combobox", name="Delivery address")).to_be_visible(),
        expect(page.get_by_role("button", name="Find food")).to_be_visible(),
        expect(page.get_by_role("img", name=re.compile(r"^Kitchen \d+%"))).to_be_visible()))
    check("landing: the directory lists every live and coming-soon city from Markets", lambda: (
        _assert(bool(live) and bool(soon), "seed has live and soon cities"),
        [expect(dir_region.get_by_role("link", name=c["name"], exact=True)).to_be_visible() for c in live],
        [expect(dir_region.get_by_role("link", name=f"{c['name']} · soon")).to_be_visible() for c in soon],
        expect(dir_region.get_by_text(f"{len(live)} cities live · {len(soon)} coming soon")).to_be_visible()))
    shot(page, "01-landing")

    # Notify me ("Don't see your city?"), then the demand shows it in Markets (admin API).
    town = f"Testpur {RUN}"
    band = page.get_by_role("region", name="Notify me")
    band.get_by_role("textbox", name="Your city").fill(town)
    band.get_by_role("textbox", name="Your email").fill(f"e2e-{RUN}@example.com")
    band.get_by_role("button", name="Notify me").click()
    check("notify me: asks for consent first", lambda: expect(band.get_by_role("alert")).to_have_text("Tick the box so we may email you."))
    band.get_by_role("checkbox").check()
    band.get_by_role("button", name="Notify me").click()
    check("notify me: signed up, counted in Markets' demand", lambda: (
        expect(band.get_by_role("status")).to_have_text("Thanks. We'll email you the day we arrive.", timeout=15000),
        _assert(town.lower() in json.dumps(api("GET", "/markets/waitlist/demand", admin)).lower(), "not in /markets/waitlist/demand")))

    # Country menu: the other country, then back.
    page.get_by_role("button", name="Country: India").click()
    menu = page.get_by_role("menu", name="Country")
    check("country menu: every country from the directory, current one ticked", lambda: (
        [expect(menu.get_by_role("menuitemradio", name=re.compile("^" + re.escape(k["name"])))).to_be_visible() for k in directory["countries"]],
        expect(menu.get_by_role("menuitemradio", name=re.compile("^India"))).to_have_attribute("aria-checked", "true")))
    menu.get_by_role("menuitemradio", name=re.compile("^United States")).click()
    check("country menu: switching country changes the language list", lambda: (
        expect(page.get_by_role("button", name="Country: United States")).to_be_visible(timeout=15000),
        _assert(cookie(ctx, "bg_country") == "US", ctx.cookies())))
    page.get_by_role("button", name="Language").click()
    check("language menu follows the country (US: English, Spanish)", lambda: (
        expect(page.get_by_role("menu", name="Language").get_by_text("Language · United States")).to_be_visible(),
        expect(page.get_by_role("menuitemradio", name=re.compile("^Español"))).to_be_visible()))
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Country: United States").click()
    page.get_by_role("menu", name="Country").get_by_role("menuitemradio", name=re.compile("^India")).click()
    expect(page.get_by_role("button", name="Country: India")).to_be_visible(timeout=15000)

    # Language: Hindi changes the words, never a price; remembered after a reload.
    page.goto(base + KITCHEN_PATH, wait_until="networkidle")
    price = page.get_by_role("region", name="Biryani").get_by_text(re.compile(r"^₹\d+$")).first.inner_text()
    english_hero = "Real food. Fair prices."
    page.get_by_role("button", name="Language").click()
    page.get_by_role("menuitemradio", name=re.compile("^हिन्दी")).click()
    check("language: Hindi changes the words, not the prices", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", re.compile("^hi"), timeout=15000),
        expect(page.get_by_role("link", name="Sign in")).to_have_count(0),
        expect(page.get_by_text(price, exact=True).first).to_be_visible()))
    page.reload(wait_until="networkidle")
    check("language: remembered after a reload", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", re.compile("^hi")),
        _assert(cookie(ctx, "bg_lang") == "hi", ctx.cookies())))
    page.goto(base, wait_until="networkidle")
    check("language: the landing page in Hindi", lambda: expect(page.get_by_role("heading", level=1)).not_to_have_text(english_hero))
    shot(page, "02-landing-hindi")
    page.locator("header button[aria-haspopup], header button[aria-expanded]").filter(has_text="हिन्दी").first.click()
    page.get_by_role("menuitemradio", name=re.compile("^English")).click()
    check("language: back to English", lambda: (
        expect(page.get_by_role("heading", name=english_hero, level=1)).to_be_visible(timeout=15000),
        expect(page.locator("html")).to_have_attribute("lang", re.compile("^en"))))

    # ── The address box -> the personal home ──────────────────────────────────
    page.get_by_role("combobox", name="Delivery address").fill("Madhap")
    option = page.get_by_role("option", name=re.compile("^Madhapur"))
    check("address box: finds an area as you type, says we deliver there", lambda: (
        expect(option).to_be_visible(timeout=10000), expect(option).to_contain_text("Delivering")))
    option.click()
    feed = page.get_by_role("region", name="Kitchens near you")
    check("personal home: kitchens for the address, offers with who pays, cards with the delivery fee", lambda: (
        expect(page.get_by_text(re.compile(r"^\d+ kitchens? delivers? to Madhapur"))).to_be_visible(timeout=20000),
        expect(page.get_by_role("region", name="Offers near you").get_by_text(re.compile("BhojanGo pays|Kitchen pays")).first).to_be_visible(),
        expect(feed.get_by_role("link", name=re.compile(KITCHEN))).to_be_visible(),
        expect(feed.get_by_role("link", name=re.compile(KITCHEN))).to_contain_text(re.compile(r"₹\d+ delivery|Free delivery")),
        expect(page.get_by_text("Orders over ₹0")).to_have_count(0)))
    check("personal home: the header carries the address, no marketing", lambda: (
        expect(page.get_by_role("button", name="Change address").first).to_contain_text("Madhapur"),
        expect(page.get_by_role("heading", name="Cook with BhojanGo")).to_have_count(0)))
    shot(page, "03-home-address")
    cards = feed.get_by_role("link")
    n_all = cards.count()
    chips = page.get_by_role("group", name="Filter kitchens")
    chips.get_by_role("button", name="Veg only").click()
    check("filters: a chip narrows the kitchens, pressed state shown", lambda: (
        expect(chips.get_by_role("button", name="Veg only")).to_have_attribute("aria-pressed", "true"),
        _assert(cards.count() < n_all or page.get_by_text("No kitchens match those filters. Try fewer.").is_visible(),
                f"{cards.count()} of {n_all}")))
    chips.get_by_role("button", name="Veg only").click()
    chips.get_by_role("button", name="Open now").click()
    check("filters: chip off again shows them all; Open now keeps the open ones", lambda: (
        expect(chips.get_by_role("button", name="Veg only")).to_have_attribute("aria-pressed", "false"),
        _assert(cards.count() >= 1, "no open kitchens: did hours.py open run?")))
    chips.get_by_role("button", name="Open now").click()

    # ── An address we don't serve yet (a coming-soon city, from the address box) ─
    soon_city = soon[0]
    page.get_by_role("button", name="Change address").first.click()
    sheet = page.get_by_role("dialog", name="Change address")
    sheet.get_by_role("combobox", name="Delivery address").fill(soon_city["name"][:5])
    sheet.get_by_role("option", name=re.compile("^" + re.escape(soon_city["name"]))).click()
    check("not in your area: says so, Notify me for that city", lambda: (
        expect(page.get_by_role("heading", name="We don't deliver to this address yet.")).to_be_visible(timeout=20000),
        expect(page.get_by_text(f"BhojanGo is coming to {soon_city['name']}")).to_be_visible()))
    nb = page.get_by_role("region", name="Notify me")
    nb.get_by_role("textbox", name="Your email").fill(f"e2e-soon-{RUN}@example.com")
    nb.get_by_role("checkbox").check()
    nb.get_by_role("button", name="Notify me").click()
    check("not in your area: Notify me there is counted for the city", lambda: (
        expect(nb.get_by_role("status")).to_be_visible(timeout=15000),
        _assert(soon_city["code"] in json.dumps(api("GET", "/markets/waitlist/demand", admin)), "city not in demand")))
    shot(page, "04-not-in-area")
    # The cookie route too: served=false for a point outside every zone.
    outside = {"label": "Somewhere far", "lat": 10.0, "lng": 10.0, "country": "IN", "city_code": None, "city_path": None, "zone": None, "served": False}
    ctx.add_cookies([{"name": "bg_addr", "value": __import__("urllib.parse").parse.quote(json.dumps(outside)), "url": base}])
    page.goto(base, wait_until="networkidle")
    check("not in your area (cookie): nearest live city named, notify me for the point", lambda: (
        expect(page.get_by_role("heading", name="We don't deliver to this address yet.")).to_be_visible(),
        expect(page.get_by_role("heading", name="Nearest cities we deliver in")).to_be_visible(),
        expect(page.get_by_role("region", name="Notify me").get_by_role("textbox", name="Your email")).to_be_visible()))

    # ── /cities, city pages ───────────────────────────────────────────────────
    page.goto(base + "/cities", wait_until="networkidle")
    hyd, boise = next(c for c in live if c["name"] == "Hyderabad"), next(c for c in live if c["name"] == "Boise")
    check("/cities: every city in the directory", lambda: [
        expect(page.get_by_role("link", name=re.compile("^" + re.escape(c["name"])))).to_be_visible() for c in cities])
    page.get_by_role("searchbox", name="Search a city or state").fill("Idah")
    check("/cities: search filters by city or state", lambda: (
        expect(page.get_by_role("link", name=re.compile("^Boise"))).to_be_visible(),
        expect(page.get_by_role("link", name=re.compile("^Hyderabad"))).to_have_count(0)))
    shot(page, "05-cities")
    page.goto(base + hyd["path"], wait_until="networkidle")
    check("live city page: title, kitchens, a real bill, ItemList and canonical", lambda: (
        expect(page).to_have_title("Food delivery in Hyderabad · BhojanGo"),
        expect(page.get_by_role("heading", name="Food delivery in Hyderabad", level=1)).to_be_visible(),
        expect(page.get_by_role("region", name="Kitchens in Hyderabad").get_by_role("link", name=re.compile(KITCHEN))).to_be_visible(),
        # a real recent order's bill, or a typical one on a fresh database
        expect(page.get_by_text(re.compile(r"^A (real|typical) Hyderabad bill$"))).to_be_visible(),
        _assert(any(json.loads(s).get("@type") == "ItemList" for s in page.locator('script[type="application/ld+json"]').all_inner_texts()), "no ItemList"),
        expect(page.locator('link[rel="canonical"]')).to_have_attribute("href", f"{SITE}{hyd['path']}")))
    # Only cuisines with 2+ kitchens are listed: South Indian (Curry Leaf, Banjara Dosa Co.).
    check("live city page: a cuisine with one kitchen isn't listed", lambda:
          expect(page.get_by_role("navigation", name="Cuisines").get_by_role("link", name="Biryani")).to_have_count(0))
    page.get_by_role("navigation", name="Cuisines").get_by_role("link", name="South Indian").click()
    check("live city page: a cuisine filters the kitchens", lambda: (
        url_is(page, r"cuisine=South(\+|%20)Indian"),
        expect(page.locator("#kitchens").get_by_role("link", name=re.compile("Curry Leaf"))).to_be_visible(),
        expect(page.locator("#kitchens").get_by_role("link", name=re.compile(KITCHEN))).to_have_count(0),
        expect(page.locator("#kitchens").get_by_role("link", name=re.compile("Charminar Chai House"))).to_have_count(0)))
    shot(page, "06-city")
    page.goto(base + soon_city["path"], wait_until="networkidle")
    check("coming-soon city page: Notify me for that city", lambda: (
        expect(page.get_by_role("heading", name=f"Coming soon to {soon_city['name']}", level=1)).to_be_visible(),
        expect(page.get_by_role("region", name="Notify me").get_by_text(f"Tell me when BhojanGo arrives in {soon_city['name']}")).to_be_visible()))
    check("a draft city is a 404", lambda: _assert(page.request.get(f"{base}/in/warangal").status == 404, "not 404"))

    # ── Kitchen page, customise sheet, bag (signed out) ───────────────────────
    ctx.clear_cookies()
    page.goto(base, wait_until="networkidle")
    page.get_by_role("combobox", name="Delivery address").fill("Madhapur")
    page.get_by_role("option", name=re.compile("^Madhapur")).click()
    expect(page.get_by_role("region", name="Kitchens near you")).to_be_visible(timeout=20000)
    page.get_by_role("region", name="Kitchens near you").get_by_role("link", name=re.compile(KITCHEN)).click()
    url_is(page, KITCHEN_PATH + "$")
    ld = lambda: [json.loads(s) for s in page.locator('script[type="application/ld+json"]').all_inner_texts()]  # noqa: E731
    check("kitchen page: menu sections, Restaurant + Menu structured data", lambda: (
        expect(page.get_by_role("heading", name=KITCHEN, level=1)).to_be_visible(timeout=15000),
        expect(page.get_by_role("navigation", name="Menu sections")).to_be_visible(),
        expect(page.get_by_role("region", name="Biryani")).to_be_visible(),
        _assert(any(x.get("@type") == "Restaurant" and x.get("hasMenu") for x in ld()), ld())))
    page.get_by_role("button", name=f"Add {DISH}").click()
    dialog = page.get_by_role("dialog", name=DISH)
    check("customise sheet: required and optional groups with prices", lambda: (
        expect(dialog.get_by_role("group", name=re.compile("^Size Required"))).to_be_visible(),
        expect(dialog.get_by_role("radio", name=re.compile(r"^Regular"))).to_be_checked(),
        expect(dialog.get_by_role("checkbox", name=re.compile(r"^Extra raita \+₹\d+"))).to_be_visible()))
    total_before = dialog.get_by_role("button", name=re.compile("^Add to bag")).inner_text()
    dialog.get_by_text("Extra raita").click()
    check("customise sheet: an add-on changes the price on the button", lambda: expect(dialog.get_by_role("button", name=re.compile("^Add to bag"))).not_to_have_text(total_before))
    shot(page, "07-customise")
    dialog.get_by_role("button", name=re.compile("^Add to bag")).click()
    bag = page.get_by_role("complementary", name="Your bag")
    check("bag: the dish with its options; asks to sign in for the whole bill", lambda: (
        expect(bag.get_by_text(re.compile(rf"1 × {DISH}"))).to_be_visible(),
        expect(bag.get_by_text(re.compile("Extra raita"))).to_be_visible(),
        expect(bag.get_by_text(re.compile("^Sign in and choose your address"))).to_be_visible()))
    shot(page, "08-kitchen-bag")

    # ── Sign in with phone + OTP (/signin, /signin/code) ──────────────────────
    bag.get_by_role("link", name="Go to checkout").click()
    url_is(page, r"/signin\?next=%2Fcheckout|/signin\?next=/checkout")
    check("sign in: phone first, country code from the directory", lambda: (
        expect(page.get_by_role("heading", name="Sign in or create an account", level=1)).to_be_visible(),
        expect(page.get_by_label("Country code")).to_have_value("IN")))
    shot(page, "09-signin")
    page.get_by_role("textbox", name="Mobile number").fill(HYD_PHONE)
    page.get_by_role("button", name="Send code").click()
    url_is(page, r"/signin/code\?")
    check("sign in: six boxes for the code", lambda: (
        expect(page.get_by_role("heading", name="Enter the 6-digit code")).to_be_visible(),
        expect(page.get_by_role("textbox", name=re.compile("^Digit "))).to_have_count(6)))
    shot(page, "10-otp")
    page.get_by_role("textbox", name="Digit 1").fill(OTP)
    page.get_by_role("button", name="Verify and continue").click()
    signed_in = step("sign in: back to checkout, signed in", lambda: url_is(page, r"/checkout$"))
    customer = login("customer1.hyd@example.com")

    # The bag on the kitchen page now has the whole bill (signed in, an address).
    page.goto(base + KITCHEN_PATH, wait_until="networkidle")
    check("bag: the fair bill once signed in", lambda: (
        expect(bag.get_by_role("row", name=re.compile("^Food Kitchen"))).to_be_visible(timeout=20000),
        expect(bag.get_by_role("row", name=re.compile("^Delivery.*BhojanGo"))).to_be_visible(),
        expect(bag.get_by_role("row", name=re.compile("^GST on food Tax"))).to_be_visible()))
    check("signed in: no marketing on the kitchen page header", lambda: expect(page.get_by_role("link", name="Ride with us")).to_have_count(0))

    # ── Checkout ──────────────────────────────────────────────────────────────
    page.goto(base + "/checkout", wait_until="networkidle")
    bill = page.get_by_role("complementary", name="Your order")
    check("checkout: saved address, live fair bill with who gets what, price held", lambda: (
        expect(page.get_by_role("region", name="Deliver to")).to_contain_text("Home", timeout=20000),
        expect(bill.get_by_text("The fair bill")).to_be_visible(timeout=20000),
        expect(bill.get_by_role("row", name=re.compile("^Food Kitchen"))).to_be_visible(),
        expect(bill.get_by_role("row", name=re.compile("^Delivery.*BhojanGo"))).to_be_visible(),
        expect(bill.get_by_text(re.compile("This price is held for"))).to_be_visible()))
    tips = page.get_by_role("radiogroup", name="Tip your rider").get_by_role("radio")
    tip_label = tips.nth(2).inner_text().strip()
    tips.nth(2).click()
    check("tip: on the bill as the rider's", lambda: (
        expect(bill.get_by_role("row", name=re.compile(r"^Tip for your rider Rider"))).to_contain_text(re.sub(r"\D", "", tip_label), timeout=15000)))
    shot(page, "11-checkout")
    page.get_by_role("button", name=re.compile(r"^Pay ")).click()
    pay = page.get_by_role("dialog", name="Pay (test mode)")
    check("pay: the test provider's checkout", lambda: expect(pay).to_be_visible(timeout=30000))
    pay.get_by_role("button", name=re.compile("^Approve")).click()
    url_is(page, r"/orders/[0-9a-f-]{36}/track$", 40000)
    order_id = page.url.rstrip("/").split("/")[-2]
    status = page.get_by_role("region", name="Order status")
    check("tracking: status, ETA, PIN for the door, the bill paid", lambda: (
        expect(status.get_by_text(f"{KITCHEN} has your order")).to_be_visible(timeout=20000),
        expect(page.locator('[data-testid="eta"]:visible')).to_be_visible(),
        expect(page.locator('[data-testid="delivery-pin"]:visible')).to_have_text(re.compile(r"^\d{4}$")),
        expect(page.get_by_role("region", name="Your order").get_by_text("The fair bill")).to_be_visible(),
        expect(page.get_by_text("You paid")).to_be_visible()))
    shot(page, "12-tracking")

    # The home page while an order is on: the active order bar, still no marketing.
    page.goto(base, wait_until="networkidle")
    check("signed-in home: active order bar, no marketing sections", lambda: (
        expect(page.get_by_role("region", name="Your order").get_by_role("link", name=re.compile(f"^Your order from {KITCHEN}.*Track order$"))).to_be_visible(timeout=20000),
        expect(page.get_by_role("heading", name="Cook with BhojanGo")).to_have_count(0),
        expect(page.get_by_role("heading", name="Ride with BhojanGo")).to_have_count(0),
        expect(page.get_by_role("region", name="Work with us")).to_have_count(0),
        expect(page.get_by_role("contentinfo").get_by_role("link", name="Ride with BhojanGo")).to_be_visible()))
    shot(page, "13-home-signed-in")

    # The kitchen, ops and the rider move the order along; the page follows live.
    page.goto(f"{base}/orders/{order_id}/track", wait_until="networkidle")
    partner, ops, rider = login("partner.hyd@example.com"), login("ops.hyd@example.com", "BhojanGoAdmin1"), login("rider3.hyd@example.com")
    for st in ("accepted", "preparing", "ready"):
        api("PUT", f"/orders/{order_id}/status", partner, {"status": st})
    check("tracking: the kitchen cooking, live", lambda: expect(status).to_contain_text(re.compile(f"{KITCHEN} is cooking|Finding a rider"), timeout=20000))
    api("POST", "/delivery/assign", ops, {"order_id": order_id, "driver_id": sub(rider)}, host=8004)
    api("POST", f"/orders/{order_id}/messages", rider, {"preset": "at_kitchen"})
    chat = page.get_by_role("region", name=re.compile("^Your rider, "))
    expect(chat.get_by_role("button", name="Message")).to_be_visible(timeout=20000)
    chat.get_by_role("button", name="Message").click()
    check("messages: the rider's quick message reaches the tracking page, numbers private", lambda: (
        expect(chat.get_by_text("I'm at the kitchen, waiting for your order.")).to_be_visible(timeout=20000),
        expect(chat.get_by_text("Phone numbers stay private on both sides.")).to_be_visible()))
    chat.get_by_label("Write a short message").fill("Gate 2, my number is 98480 22334")
    chat.get_by_role("button", name="Send").click()
    check("messages: the customer's reply reaches the rider, phone number hidden", lambda: (
        expect(chat.get_by_text("Gate 2, my number is •••")).to_be_visible(timeout=10000),
        eventually(lambda: _assert(api("GET", f"/orders/{order_id}/messages", rider)["messages"][-1]["text"] == "Gate 2, my number is •••",
                                   api("GET", f"/orders/{order_id}/messages", rider)["messages"][-1:]))))
    api("POST", f"/orders/{order_id}/messages", rider, {"preset": "outside"})
    check("messages: live from the rider without reloading", lambda: expect(chat.get_by_text("I'm outside.")).to_be_visible(timeout=15000))
    shot(page, "13b-messages")
    pin = page.locator('[data-testid="delivery-pin"]:visible').inner_text()
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "picked_up"})
    check("tracking: picked up, live", lambda: expect(status).to_contain_text("has picked up your order", timeout=20000))
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    check("tracking: delivered, live (no reload), messages closed", lambda: (
        expect(status).to_contain_text("Delivered. Enjoy your meal.", timeout=20000),
        expect(page.get_by_role("button", name="Message")).to_have_count(0, timeout=10000)))
    shot(page, "14-delivered")
    page.get_by_role("link", name=re.compile("Report a problem")).click()
    check("report a problem: the form opens for this order", lambda: (
        url_is(page, rf"/orders/{order_id}/report|/account/orders/{order_id}/report"),
        expect(page.get_by_role("heading", name="Report a problem", level=1)).to_be_visible(timeout=15000),
        expect(page.get_by_text("What went wrong?")).to_be_visible()))
    shot(page, "15-report")
    # The biryani came cold: over the city's automatic refund limit, so it goes to support with the photo.
    page.get_by_label(f"How many {DISH}").fill("1")
    page.get_by_text("Not good", exact=True).click()
    page.get_by_label("Tell us more (optional)").fill("Cold when it came")
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63000100000500010d0a2db40000000049454e44ae426082")
    page.get_by_label("A photo helps (optional)").set_input_files(files=[{"name": "biryani.png", "mimeType": "image/png", "buffer": png}])
    page.get_by_role("button", name="Send report").click()
    check("report a problem: over the city's limit, sent to support with the photo", lambda: (
        expect(page.get_by_text(re.compile("^(Sent to support|Refunded)"))).to_be_visible(timeout=20000),
        _assert(any(t["kind"] == "problem" and t["order_id"] == order_id and t["details"].get("photo_key")
                    for t in api("GET", "/ops/tickets?scope=IN-TG-HYD", ops)), "no ticket with the photo")))
    shot(page, "15b-problem-sent")

    # ── Account: orders, receipt, PDF, order again ────────────────────────────
    code = "#" + order_id.replace("-", "")[:6].upper()
    page.goto(base + "/account/orders", wait_until="networkidle")
    lst = page.get_by_role("main")
    check("orders: the new order first, delivered", lambda: (
        expect(page.get_by_role("heading", name="Orders", level=1)).to_be_visible(timeout=15000),
        expect(lst.get_by_role("button", name=re.compile(re.escape(code))).first).to_contain_text("Delivered", timeout=15000)))
    page.get_by_role("searchbox", name="Search by kitchen, dish or order code").fill(code[1:])
    check("orders: search by order code", lambda: (
        expect(lst.get_by_role("button", name=re.compile(re.escape(code)))).to_have_count(1, timeout=15000),
        expect(lst.get_by_role("button", name=re.compile(r"· #[0-9A-F]{6} "))).to_have_count(1)))
    page.get_by_role("searchbox", name="Search by kitchen, dish or order code").fill("")
    page.get_by_role("group", name="Show orders").get_by_role("button", name="Cancelled").click()
    check("orders: status filter", lambda: (
        expect(page.get_by_role("group", name="Show orders").get_by_role("button", name="Cancelled")).to_have_attribute("aria-pressed", "true"),
        expect(lst.get_by_role("button", name=re.compile(re.escape(code)))).to_have_count(0, timeout=15000),
        _assert(all(t.strip().endswith("Cancelled") for t in lst.get_by_role("button", name=re.compile(r"· #[0-9A-F]{6} ")).all_inner_texts()),
                "a non-cancelled order in the Cancelled filter")))
    page.get_by_role("group", name="Show orders").get_by_role("button", name="Delivered").click()
    lst.get_by_role("button", name=re.compile(re.escape(code))).first.click()
    receipt = page.get_by_role("article", name=f"Receipt for order {code}")
    check("receipt: the full bill with who gets each line", lambda: (
        expect(receipt.get_by_role("heading", name=KITCHEN)).to_be_visible(timeout=15000),
        expect(receipt.get_by_role("row", name=re.compile("^Food Kitchen"))).to_be_visible(),
        expect(receipt.get_by_role("row", name=re.compile("^GST on food Tax"))).to_be_visible(),
        expect(receipt.get_by_role("row", name=re.compile("^Tip for your rider Rider"))).to_be_visible(),
        expect(receipt.get_by_text("You paid")).to_be_visible()))
    shot(page, "16-receipt")

    def pdf() -> None:
        with page.expect_download(timeout=30000) as dl:
            receipt.get_by_role("button", name="Tax invoice (PDF)").click()
        with open(dl.value.path(), "rb") as fh:
            data = fh.read()
        _assert(data[:5] == b"%PDF-", data[:40])
    check("receipt: India's tax invoice downloads as a PDF", pdf)
    receipt.get_by_role("button", name="Order again").click()
    check("order again: fills the bag and goes to checkout", lambda: (
        url_is(page, r"/checkout$"),
        expect(page.get_by_role("complementary", name="Your order").get_by_text(re.compile(rf"1 × {DISH}"))).to_be_visible(timeout=20000)))
    page.goto(f"{base}/account/orders/{order_id}/report", wait_until="networkidle")
    check("report a problem from the account opens", lambda: expect(page.get_by_role("heading", name="Report a problem", level=1)).to_be_visible(timeout=15000))

    # ── Profile: address, test card, notifications, data export ───────────────
    page.goto(base + "/account/profile", wait_until="networkidle")
    addresses = page.get_by_role("region", name="Addresses")
    addresses.get_by_role("button", name="+ Add address").click()
    form = addresses.get_by_role("form", name="New address")
    form.get_by_role("combobox", name="Search your area").fill("Gachib")
    form.get_by_role("option", name=re.compile("^Gachibowli")).click()
    label = f"Office {RUN}"
    form.get_by_role("textbox", name="Name it (Home, Work…)").fill(label)
    form.get_by_role("textbox", name="Flat, house, street").fill("Tower 3, Floor 9")
    for name, value in (("City", "Hyderabad"), ("State", "Telangana"), ("Postal code", "500032")):
        if not form.get_by_role("textbox", name=name).input_value():
            form.get_by_role("textbox", name=name).fill(value)
    form.get_by_role("textbox", name="Delivery notes (gate code, floor…)").fill("Gate B, ask for reception")
    form.get_by_role("button", name="Save").click()
    mine = lambda: next((a for a in api("GET", "/me/addresses", customer) if a["label"] == label), None)  # noqa: E731
    check("addresses: a new address with delivery notes", lambda: (
        expect(addresses.get_by_text(label)).to_be_visible(timeout=15000),
        eventually(lambda: _assert((mine() or {}).get("delivery_notes") == "Gate B, ask for reception", mine()))))
    row = addresses.locator("div").filter(has_text=label).filter(has=page.get_by_role("button", name="Make default")).last
    row.get_by_role("button", name="Make default").click()
    check("addresses: make it the default", lambda: (
        expect(addresses.get_by_text(label, exact=True).locator("xpath=following-sibling::*[1]")).to_have_text("Default", timeout=15000),
        eventually(lambda: _assert((mine() or {}).get("is_default") is True, mine()))))
    shot(page, "17-profile")
    check("addresses: the site now delivers to the default address", lambda: eventually(
        lambda: _assert(label in __import__("urllib.parse").parse.unquote(cookie(ctx, "bg_addr") or ""), cookie(ctx, "bg_addr"))))
    # Home back as the default (the site follows it back), the new address removed: the next run starts the same.
    addresses.locator("div").filter(has_text="Home").filter(has=page.get_by_role("button", name="Make default")).last.get_by_role("button", name="Make default").click()
    eventually(lambda: _assert(next(a for a in api("GET", "/me/addresses", customer) if a["label"] == "Home")["is_default"], "Home not default"))
    eventually(lambda: _assert("Home" in __import__("urllib.parse").parse.unquote(cookie(ctx, "bg_addr") or ""), cookie(ctx, "bg_addr")))
    if mine():
        api("DELETE", f"/me/addresses/{mine()['id']}", customer)

    sent: list[str] = []
    page.on("request", lambda r: sent.append(r.post_data or "") if r.method == "POST" and r.url.endswith("/me/payment-methods") else None)
    page.reload(wait_until="networkidle")
    payments = page.get_by_role("region", name="Payment methods")
    payments.get_by_role("button", name="+ Add payment method").click()
    card = payments.get_by_role("form", name="Add a test card")
    card.get_by_role("combobox", name="Card brand").select_option("Visa")
    card.get_by_role("textbox", name="Last 4 digits").fill("4242")
    card.get_by_role("button", name="Save card").click()
    check("payment methods: a test card saved as a token, never a card number", lambda: (
        expect(payments.get_by_text("Visa ending 4242")).to_be_visible(timeout=15000),
        _assert(len(sent) == 1, sent),
        _assert(json.loads(sent[0])["provider_token"].startswith("pm_fake_"), sent[0]),
        _assert(not ({"number", "card_number", "pan", "cvc", "cvv"} & set(json.loads(sent[0]))), sent[0]),
        _assert(not re.search(r"\d{12,19}", sent[0]), sent[0])))
    for pm in api("GET", "/me/payment-methods", customer):
        if pm.get("last4") == "4242" and str(pm.get("provider_token", "pm_fake")).startswith("pm_fake"):
            api("DELETE", f"/me/payment-methods/{pm['id']}", customer)

    offers_email = page.get_by_role("switch", name="Offers by Email")
    check("notifications: offers are off by default", lambda: expect(offers_email).to_have_attribute("aria-checked", "false"))
    offers_email.click()
    prefs = lambda: json.dumps(api("GET", "/me/notification-preferences", customer))  # noqa: E731
    check("notifications: turning offers on by email is saved", lambda: (
        expect(offers_email).to_have_attribute("aria-checked", "true", timeout=10000),
        page.wait_for_timeout(500),
        page.reload(wait_until="networkidle"),
        expect(page.get_by_role("switch", name="Offers by Email")).to_have_attribute("aria-checked", "true", timeout=15000)))
    page.get_by_role("switch", name="Offers by Email").click()
    expect(page.get_by_role("switch", name="Offers by Email")).to_have_attribute("aria-checked", "false", timeout=10000)

    def export() -> None:
        with page.expect_download(timeout=30000) as dl:
            page.get_by_role("button", name="Download my data").click()
        with open(dl.value.path(), "rb") as fh:
            data = json.loads(fh.read())
        _assert(isinstance(data, dict) and data, str(data)[:200])
    check("download my data: a JSON file", export)

    # ── Favourites: heart a kitchen on a card ─────────────────────────────────
    for r in api("GET", "/me/favourites", customer)["restaurants"]:  # start from "not saved"
        if r.get("name") == KITCHEN:
            api("DELETE", f"/me/favourites/restaurant/{r['id']}", customer)
    page.goto(base, wait_until="networkidle")
    heart = page.get_by_role("button", name=f"Save {KITCHEN}").first
    expect(heart).to_be_visible(timeout=15000)
    heart.click()
    check("favourites: the heart fills, saved on the account", lambda: (expect(page.get_by_role("button", name=re.compile(f"(Remove|Unsave).*{KITCHEN}")).first).to_have_attribute("aria-pressed", "true", timeout=10000),
        eventually(lambda: _assert(any(r.get("name") == KITCHEN for r in api("GET", "/me/favourites", customer)["restaurants"]), "not saved"))))
    page.goto(base + "/account/favourites", wait_until="networkidle")
    check("favourites: the kitchen is on /account/favourites", lambda: expect(page.get_by_role("main").get_by_text(KITCHEN).first).to_be_visible(timeout=15000))
    shot(page, "18-favourites")
    page.get_by_role("main").get_by_role("button", name=re.compile(f"(Remove|Unsave).*{KITCHEN}")).first.click()
    check("favourites: unheart removes it", lambda: (
        eventually(lambda: _assert(not any(r.get("name") == KITCHEN for r in api("GET", "/me/favourites", customer)["restaurants"]), "still saved")),
        page.reload(wait_until="networkidle"),
        expect(page.get_by_role("main").get_by_role("button", name=re.compile(f"(Remove|Unsave).*{KITCHEN}"))).to_have_count(0, timeout=15000)))

    for path, heading in (("/help", "Help"), ("/terms", "Terms of use"), ("/privacy", "Privacy notice")):
        page.goto(base + path, wait_until="networkidle")
        check(f"{path}: readable page", lambda h=heading: expect(page.get_by_role("heading", name=h, level=1)).to_be_visible())

    # A kitchen applies on the web with a brand-new number (B1).
    k = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    k.goto(base + "/partner", wait_until="networkidle")
    k.get_by_role("link", name="Sign in to apply").click()
    url_is(k, r"/signin\?")
    k.get_by_role("textbox", name="Mobile number").fill(f"90000{random.randint(10000, 99999)}")
    k.get_by_role("button", name="Send code").click()
    url_is(k, r"/signin/code\?")
    k.get_by_role("textbox", name="Digit 1").fill(OTP)
    k.get_by_role("button", name="Verify and continue").click()
    url_is(k, r"/partner$")
    apply = k.get_by_role("form", name="Apply with your kitchen")
    for label, value in (("Your name", "Lata Menon"), ("Kitchen name", "Lata's Kitchen"), ("Area", "Banjara Hills"),
                         ("Street address", "Plot 9, Road 12"), ("PIN / ZIP code", "500034"), ("Cuisines", "Kerala, Thali")):
        apply.get_by_label(label, exact=True).fill(value)
    apply.get_by_role("button", name="Send application").click()
    check("kitchen sign-up on the web: application created, licence step next", lambda: (
        expect(k.get_by_role("region", name="Your application")).to_be_visible(timeout=20000),
        expect(k.get_by_text("Lata's Kitchen · 1 of 5 done")).to_be_visible()))
    shot(k, "21-partner-application")

    # ── Phone width (390): no sideways scroll on the main pages ──────────────
    m = ctx.new_page()
    m.set_viewport_size({"width": 390, "height": 844})
    for path in ("/", KITCHEN_PATH, "/checkout", f"/orders/{order_id}/track", "/cities", "/account/orders"):
        m.goto(base + path, wait_until="networkidle")
        m.wait_for_timeout(500)
        check(f"phone width {path}: no sideways scroll", lambda: no_sideways_scroll(m))
    m.goto(base + KITCHEN_PATH, wait_until="networkidle")
    m.screenshot(path=f"{OUT}/19-kitchen-phone.png", full_page=False)
    anon_phone = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    anon_phone.goto(base + "/signin", wait_until="networkidle")
    check("phone width /signin: no sideways scroll", lambda: no_sideways_scroll(anon_phone))
    anon_phone.goto(base, wait_until="networkidle")
    check("phone width landing: no sideways scroll", lambda: no_sideways_scroll(anon_phone))

    # ── US: Boise in dollars, a US number ─────────────────────────────────────
    us_ctx = b.new_context(viewport={"width": 1440, "height": 900})
    us = us_ctx.new_page()
    us.goto(base + US_KITCHEN_PATH, wait_until="networkidle")
    check("US: Boise kitchen page in dollars", lambda: (
        expect(us.get_by_role("heading", name=US_KITCHEN, level=1)).to_be_visible(timeout=15000),
        expect(us.get_by_text("$14.50").first).to_be_visible(),
        expect(us.get_by_text("₹")).to_have_count(0)))
    us.get_by_role("button", name="Add Teriyaki Chicken Bowl").click()
    us_dialog = us.get_by_role("dialog", name="Teriyaki Chicken Bowl")
    if us_dialog.count():
        us_dialog.get_by_role("button", name=re.compile("^Add to bag")).click()
    us.get_by_role("complementary", name="Your bag").get_by_role("button", name="One more Teriyaki Chicken Bowl").click()
    us.get_by_role("complementary", name="Your bag").get_by_role("link", name="Go to checkout").click()
    url_is(us, r"/signin\?")
    sign_in(us, US_PHONE, "US")
    url_is(us, r"/checkout$")
    us_bill = us.get_by_role("complementary", name="Your order")
    check("US checkout: the fair bill in dollars with sales tax", lambda: (
        expect(us_bill.get_by_text("The fair bill")).to_be_visible(timeout=20000),
        expect(us_bill.get_by_role("row", name=re.compile("Tax"))).not_to_have_count(0),
        expect(us_bill.get_by_text(re.compile(r"^\$\d+\.\d{2}$")).first).to_be_visible(),
        expect(us_bill.get_by_text("₹")).to_have_count(0)))
    shot(us, "20-us-checkout")

    # ── SEO and headers ──────────────────────────────────────────────────────
    r = page.request.get(f"{base}/sitemap.xml")
    check("sitemap lists city and kitchen pages", lambda: _assert(
        f"{SITE}{hyd['path']}" in r.text() and f"{SITE}{boise['path']}" in r.text() and f"{SITE}{KITCHEN_PATH}" in r.text()
        and "/in/warangal" not in r.text(), r.text()[:300]))
    rb = page.request.get(f"{base}/robots.txt").text()
    # Locally and on QA (never production): crawlers kept out by robots.txt and a header.
    check("robots.txt keeps every crawler out outside production", lambda: _assert(
        re.search(r"(?m)^Disallow: /$", rb) and "Allow:" not in rb.replace("Disallow:", ""), rb))
    check("X-Robots-Tag: noindex outside production", lambda: _assert(
        "noindex" in (page.request.get(base + "/").headers.get("x-robots-tag") or ""), page.request.get(base + "/").headers))
    check("unknown kitchen is a 404", lambda: _assert(page.request.get(f"{base}{hyd['path']}/no-such-kitchen").status == 404, "not 404"))
    old = page.request.get(f"{base}/orders", max_redirects=0)
    check("old /orders redirects to the account", lambda: _assert(
        old.status in (301, 308) and old.headers.get("location", "").endswith("/account/orders"), (old.status, old.headers)))
    b.close()

failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
raise SystemExit(1 if failed else 0)
