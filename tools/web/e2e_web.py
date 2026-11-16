"""Playwright end-to-end run of the customer website (web v2) against `make dev`.

Runs inside mcr.microsoft.com/playwright/python on the compose network
(tools/web/e2e.sh). The browser talks to localhost like a person's would:
localhost:3000 (web), :8001 (core_api) and :8004 (realtime) are forwarded to
the compose services, so CORS and the app's API URLs are exactly as in dev.
Screenshots go to docs/screenshots/web.

What it walks through (desktop 1440 unless noted), all on seed data:
first visit (landing, directory, Notify me, the language pill and the location
line with Change city), the
address box -> personal home (offers, kitchen cards, filters), an address we
don't serve yet, /cities and city pages, a kitchen page with the customise
sheet and the bag, phone + OTP sign-in, checkout with the fair bill and a tip,
the fake payment provider, tracking to "delivered" (kitchen, ops and rider via
their APIs), the account area (orders, receipt, PDF, order again, report a
problem, addresses, a test card, notifications, data export, favourites), the
receipt seen from a browser in a US time zone (the order's city time, not the device's), no
marketing when signed in, a US kitchen in dollars, SEO files and headers, and
no sideways scroll at 390 px, and only the type scale's font sizes on the
kitchen page, home, receipt and (at 390) checkout (font_sizes.py).
"""
import json
import os
import random
import re
import socket
import sys
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

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

# The type scale check (font_sizes.py, next to this file): every visible text's size.
from font_sizes import collect as font_sizes_on, problems as font_problems  # noqa: E402

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


def type_scale_only(page) -> None:  # type: ignore[no-untyped-def]
    """Every visible text is a type-scale size (64 44 40 30 28 22 20 18 17 16 15 14 12); 12 px only uppercase."""
    page.wait_for_timeout(300)  # web fonts
    bad = font_problems(font_sizes_on(page))
    _assert(not bad, f"{len(bad)} off the scale: " + "; ".join(bad[:4]))


def no_sideways_scroll_at(page, width: int) -> None:  # type: ignore[no-untyped-def]
    w = page.evaluate("document.documentElement.scrollWidth")
    assert w <= width + 2, f"page is {w}px wide at {width}"


HINT_NONE = {"country": None, "place": None, "region": None, "region_code": None, "city_code": None, "city_name": None,
             "city_path": None, "served": False}


def fake_hint(ctx, hint: dict) -> None:  # type: ignore[no-untyped-def]
    """The browser's GET /markets/hint answers `hint` (the visitor's IP place), so the run doesn't depend on
    where the test machine is (QA has GeoIP on; make dev has none)."""
    body = json.dumps({**HINT_NONE, **hint})
    ctx.route(re.compile(r".*/api/v1/markets/hint$"), lambda route: route.fulfill(
        status=200, content_type="application/json", body=body, headers={"Access-Control-Allow-Origin": "*"}))


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
    fake_hint(ctx, {})  # an IP we can't place
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
        expect(page.get_by_role("button", name="Find food")).to_be_visible()))
    # R8: nothing known about the visitor's place -> no city named, no city's kitchens or example bill.
    check("location line, nothing known: Set your delivery location · Change city; no other city's bill", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Set your delivery location · Change city"),
        expect(page.get_by_test_id("location-line")).to_have_attribute("data-source", "none"),
        expect(page.get_by_test_id("who-gets")).to_have_count(0),
        expect(page.get_by_role("heading", name="What's cooking near you")).to_have_count(0)))

    def set_location_opens_the_address_box() -> None:
        page.get_by_test_id("set-location").click()
        dialog = page.get_by_role("dialog", name="Set your delivery location")
        expect(dialog).to_be_visible()
        expect(dialog.get_by_role("combobox", name="Delivery address")).to_be_focused()
        page.keyboard.press("Escape")
        expect(dialog).to_have_count(0)
    check("location line: Set your delivery location opens the address box (Escape closes it)", set_location_opens_the_address_box)
    check("landing: the directory lists every live and coming-soon city from Markets", lambda: (
        _assert(bool(live) and bool(soon), "seed has live and soon cities"),
        [expect(dir_region.get_by_role("link", name=c["name"], exact=True)).to_be_visible() for c in live],
        [expect(dir_region.get_by_role("link", name=f"{c['name']} · soon")).to_be_visible() for c in soon],
        expect(dir_region.get_by_text(f"{len(live)} cities live · {len(soon)} coming soon")).to_be_visible()))
    hero_of = {k["code"]: k["hero_photo"] for k in directory["countries"]}
    check("landing: the hero is the country's photo chosen in Markets (Hero dish)", lambda: (
        expect(page.get_by_test_id("landing-hero")).to_have_attribute("src", re.compile(
            "/food/" + re.escape(hero_of["IN"]) + r"-\d+\.webp$")),
        _assert(page.get_by_test_id("landing-hero").evaluate("img => img.complete && img.naturalWidth > 0"), "hero not loaded")))
    # Outside production (make dev, QA, staging) every page says it's a test site; production never does
    # (packages/ui/environment.js, unit-tested there).
    TEST_BANNER = "Test site: demo kitchens, no real orders or payments"
    check("test-site banner: on the landing page, above the header, a note (not an alert)", lambda: (
        expect(page.get_by_role("note").filter(has_text=TEST_BANNER)).to_be_visible(),
        expect(page.get_by_role("alert").filter(has_text=TEST_BANNER)).to_have_count(0),
        _assert(page.get_by_test_id("test-site-banner").bounding_box()["y"] < page.locator("header").first.bounding_box()["y"],
                "banner is not above the header")))
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

    # ── Header (R6): no country selector; a globe + code language pill; where the
    # visitor is shows on the page ("<city>, <CC> · Change city"), not in the header.
    by_code = {c["code"]: c for c in cities}
    hyd_city, boise_city = by_code["IN-TG-HYD"], by_code["US-ID-BOI"]
    own_names = {"en": "English", "hi": "हिन्दी", "te": "తెలుగు", "ta": "தமிழ்", "kn": "ಕನ್ನಡ", "mr": "मराठी", "bn": "বাংলা", "es": "Español"}
    langs_of = {k["code"]: [own_names[loc.split("-")[0]] for loc in k["locales"]] for k in directory["countries"]}
    header = page.locator("header").first
    pill = page.get_by_test_id("language-pill")
    check("header: no country selector, no flags; the language pill says EN", lambda: (
        expect(header.get_by_role("button", name=re.compile("^Country"))).to_have_count(0),
        [expect(header.get_by_text(k["name"], exact=True)).to_have_count(0) for k in directory["countries"]],
        _assert(not re.search("[\U0001F1E6-\U0001F1FF]", header.inner_text()), "a flag in the header"),
        expect(pill).to_have_text("EN"),
        expect(pill).to_have_accessible_name("Language: English")))

    def choose_city(pg, city: dict) -> None:  # type: ignore[no-untyped-def]
        """The location line's "Change city" -> /cities?choose=1 -> the city -> home."""
        pg.get_by_test_id("change-city").click()
        url_is(pg, r"/cities\?choose=1$")
        card = pg.locator(f'main a[data-city="{city["code"]}"]')
        if not card.is_visible():  # another country: behind "Other countries"
            pg.get_by_test_id("other-countries").locator("summary").click()
        card.click()
        expect(pg.get_by_test_id("location-line")).to_contain_text(city["name"], timeout=15000)

    def split_matches_api(pg) -> None:  # type: ignore[no-untyped-def]
        """Who gets your money: whole percentages adding to 100, from the engine's example quote for the city."""
        card = pg.get_by_test_id("who-gets")
        expect(card).to_be_visible()
        shown = {li.get_attribute("data-payee"): int(li.get_attribute("data-percent") or "-1") for li in card.locator("li[data-payee]").all()}
        _assert(sum(shown.values()) == 100 and min(shown.values()) >= 0, shown)
        ex = api("GET", f"/pricing/example?city={card.get_attribute('data-city')}")
        # The engine's split (R7): the rider's share is their pay (base + distance + wait) plus the tip.
        _assert(shown["rider"] > 0, ("no rider share", shown))
        amounts = [max(float(ex["shares"][k]), 0.0) for k in ("kitchen", "rider", "tax", "us")]
        exact = [a / sum(amounts) * 100 for a in amounts]
        pct = [int(x) for x in exact]
        for i in sorted(range(4), key=lambda i: (-(exact[i] - int(exact[i])), i))[:100 - sum(pct)]:
            pct[i] += 1
        # the page and the API each cache the example for an hour: compare when both show the same bill
        if card.get_attribute("data-total") == ex["total"]:
            _assert([shown[k] for k in ("kitchen", "rider", "tax", "us")] == pct, (shown, pct, ex["total"]))
        for txt in card.locator("li[data-payee] b").all_inner_texts():
            _assert(re.fullmatch(r"\d+\s?%", txt.strip()) is not None, txt)

    # Change city (R8): the visitor's country's cities only, a search, other countries behind a disclosure.
    page.get_by_test_id("change-city").click()
    url_is(page, r"/cities\?choose=1$")
    home_cc = page.get_by_test_id("choose-home").get_attribute("data-country")
    others = page.get_by_test_id("other-countries")
    home_cities = [c for k in directory["countries"] if k["code"] == home_cc for r in k["regions"] for c in r["cities"]]
    away_cities = [c for k in directory["countries"] if k["code"] != home_cc for r in k["regions"] for c in r["cities"]]

    def waiting_text(c: dict) -> str:
        n = c.get("waiting") or 0
        return "Coming soon" + (f" · {n:,} {'person' if n == 1 else 'people'} waiting" if n > 0 else "")

    def choose_page_country_first() -> None:
        home = page.get_by_test_id("choose-home")
        for c in home_cities:
            card = home.locator(f'a[data-city="{c["code"]}"]')
            expect(card).to_be_visible()
            expect(card.locator("img")).to_have_count(1)  # a photo, never an empty box
            if c["status"] == "soon":
                expect(card.get_by_test_id("city-status")).to_have_text(waiting_text(c))
        for c in away_cities:
            expect(page.locator(f'main a[data-city="{c["code"]}"]')).to_be_hidden()
        _assert(others.get_attribute("open") is None, "Other countries should start closed")
    check("change city: only the visitor's country, coming soon with the waiting count, other countries closed", choose_page_country_first)

    def choose_page_search() -> None:
        box = page.get_by_role("searchbox", name="Search a city or state")
        box.fill(hyd_city["name"][:4].lower())
        expect(page.locator('main a[data-city="IN-TG-HYD"]')).to_be_visible()
        box.fill(boise_city["name"][:3].lower())  # only another country has it: the disclosure opens by itself
        expect(page.locator('main a[data-city="US-ID-BOI"]')).to_be_visible()
        box.fill("")
    check("change city: search filters as you type; a match abroad opens Other countries", choose_page_search)
    page.goto(base, wait_until="networkidle")
    choose_city(page, hyd_city)
    check("landing in a served city: the example bill is there", lambda: expect(
        page.get_by_role("img", name=re.compile(r"^Kitchen \d+%"))).to_be_visible())
    check("location line: Hyderabad, IN · Change city (above the hero)", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Hyderabad, IN · Change city"),
        _assert(cookie(ctx, "bg_city") == "IN-TG-HYD", ctx.cookies()),
        _assert(page.get_by_test_id("location-line").bounding_box()["y"] < page.get_by_role("heading", level=1).bounding_box()["y"],
                "the location line is not above the hero")))
    check("who gets your money: real percentages from the example quote, adding to 100", lambda: split_matches_api(page))
    pill.click()
    lang_menu = page.get_by_role("menu", name="Language")
    check("language pill: a plain list of India's languages in their own scripts, Markets order", lambda: (
        expect(lang_menu).to_be_visible(),
        _assert(lang_menu.locator("span[lang]").all_inner_texts() == langs_of["IN"], lang_menu.locator("span[lang]").all_inner_texts()),
        expect(page.get_by_role("dialog")).to_have_count(0)))
    lang_menu.get_by_role("menuitemradio", name="తెలుగు").click()
    check("language: Telugu switches the page", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", "te", timeout=15000),
        expect(pill).to_have_text("TE"),
        expect(page.get_by_role("heading", level=1)).not_to_have_text("Real food. Fair prices.")))
    page.reload(wait_until="networkidle")
    check("language: Telugu survives a reload", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", "te"),
        expect(pill).to_have_text("TE"),
        _assert(cookie(ctx, "bg_lang") == "te", ctx.cookies())))
    choose_city(page, boise_city)
    check("change city to Boise: Boise, US; dollars; Telugu isn't offered there, so English", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Boise, US · Change city"),
        expect(page.locator("html")).to_have_attribute("lang", "en"),
        expect(pill).to_have_text("EN"),
        expect(page.get_by_test_id("who-gets")).to_contain_text("$"),
        expect(page.get_by_test_id("who-gets")).not_to_contain_text("₹"),
        _assert(cookie(ctx, "bg_lang") is None, ctx.cookies())))
    check("landing: another country, its own hero photo", lambda: expect(page.get_by_test_id("landing-hero")).to_have_attribute(
        "src", re.compile("/food/" + re.escape(hero_of["US"]) + r"-\d+\.webp$"), timeout=15000))
    check("who gets your money in Boise: from Boise's example quote", lambda: split_matches_api(page))
    pill.click()
    check("language pill in the US: English and Español only", lambda: _assert(
        page.get_by_role("menu", name="Language").locator("span[lang]").all_inner_texts() == langs_of["US"] == ["English", "Español"],
        page.get_by_role("menu", name="Language").locator("span[lang]").all_inner_texts()))
    page.keyboard.press("Escape")
    shot(page, "02a-landing-boise")
    choose_city(page, hyd_city)

    # Language: Hindi changes the words, never a price; remembered after a reload.
    page.goto(base + KITCHEN_PATH, wait_until="networkidle")
    price = page.get_by_role("region", name="Biryani").get_by_text(re.compile(r"^₹\d+$")).first.inner_text()
    english_hero = "Real food. Fair prices."
    pill.click()
    page.get_by_role("menuitemradio", name=re.compile("^हिन्दी")).click()
    check("language: Hindi changes the words, not the prices", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", re.compile("^hi"), timeout=15000),
        expect(pill).to_have_text("HI"),
        expect(page.get_by_role("link", name="Sign in")).to_have_count(0),
        expect(page.get_by_text(price, exact=True).first).to_be_visible()))
    page.reload(wait_until="networkidle")
    check("language: remembered after a reload", lambda: (
        expect(page.locator("html")).to_have_attribute("lang", re.compile("^hi")),
        _assert(cookie(ctx, "bg_lang") == "hi", ctx.cookies())))
    page.goto(base, wait_until="networkidle")
    check("language: the landing page in Hindi", lambda: expect(page.get_by_role("heading", level=1)).not_to_have_text(english_hero))
    shot(page, "02-landing-hindi")
    pill.click()
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
    check("personal home: the address is on the page, not in the header; no marketing", lambda: (
        expect(page.get_by_test_id("change-address")).to_contain_text("Madhapur"),
        expect(page.locator("header").get_by_role("button", name="Change address")).to_have_count(0),
        expect(page.get_by_role("heading", name="Cook with BhojanGo")).to_have_count(0)))
    check("personal home: the location line names the address's city", lambda: expect(
        page.get_by_test_id("location-line")).to_have_text("Hyderabad, IN · Change city"))
    shot(page, "03-home-address")
    cards = feed.get_by_role("link")

    def counts_agree() -> None:
        # "N kitchens deliver to <address>", "See all N" and the cards are one list (/discover for the address).
        said = page.get_by_text(re.compile(r"^\d+ kitchens? delivers? to Madhapur")).inner_text()
        n = int(said.split()[0])
        see_all = feed.get_by_role("button", name=re.compile(r"^See all \d+$"))
        if see_all.count():
            _assert(int(see_all.inner_text().split()[-1]) == n, f"{said!r} but {see_all.inner_text()!r}")
            see_all.click()
            expect(see_all).to_have_count(0)
        expect(cards).to_have_count(n)
    check("personal home: kitchens that deliver, See all and the cards are the same number", counts_agree)
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
    # The FAQ answers with Hyderabad's own rules (tools/seed/data.py): delivery slabs, service fee, tips.
    check("live city page: FAQ from the city's rules (actual amounts and distances)", lambda: (
        expect(page.get_by_text(re.compile(r"₹25 up to 3 km; ₹35 up to 6 km; ₹50 up to 10 km"))).to_be_attached(),
        expect(page.get_by_text(re.compile(r"service fee of 2% of the food \(at least ₹5, at most ₹15\)"))).to_be_attached(),
        expect(page.get_by_text(re.compile(r"Checkout suggests ₹10, ₹20, ₹30"))).to_be_attached()))
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
    check("type scale: the kitchen page uses only the scale's font sizes", lambda: type_scale_only(page))
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
    # "None", then India's tip_presets rule (10, 20, 30; the second preselected), then "Other".
    check("tip: choices from the tip_presets rule, its default preselected", lambda: (
        _assert([tips.nth(i).inner_text().strip() for i in range(tips.count())] == ["None", "₹10", "₹20", "₹30", "Other"],
                [tips.nth(i).inner_text() for i in range(tips.count())]),
        expect(tips.nth(2)).to_have_attribute("aria-checked", "true")))
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
    check("type scale: the signed-in home uses only the scale's font sizes", lambda: type_scale_only(page))
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
    # The rider's GPS, as the rider app sends it: a rider marker on the real map
    # (MapLibre + OpenFreeMap, OSM credited) between the kitchen and home, and it moves.
    o = api("GET", f"/orders/{order_id}", rider)
    a, z = (o["pickup_lat"], o["pickup_lng"]), (o["delivery_lat"], o["delivery_lng"])
    fix = lambda f: api("POST", "/delivery/driver/location", rider, {  # noqa: E731
        "lat": a[0] + (z[0] - a[0]) * f, "lng": a[1] + (z[1] - a[1]) * f, "order_id": order_id}, host=8004)
    fix(0.3)
    route_map = page.get_by_role("region", name="Map of your order's route")
    marker = route_map.get_by_role("img", name=re.compile("your rider$"))
    check("tracking map: kitchen, home and the rider's live position, OSM credited", lambda: (
        expect(route_map.get_by_role("img", name=re.compile(r"\(pickup\)$"))).to_be_visible(timeout=20000),
        expect(route_map.get_by_role("img", name="Your address (drop-off)")).to_be_visible(),
        expect(marker).to_be_visible(timeout=20000),
        expect(page.get_by_text("OpenStreetMap").first).to_be_visible()))
    before_box = marker.bounding_box() if marker.count() else None
    fix(0.7)
    check("tracking map: the rider marker moves with the next GPS fix (no reload)", lambda: eventually(
        lambda: _assert(before_box is not None and marker.bounding_box() is not None
                        and abs(marker.bounding_box()["x"] - before_box["x"]) + abs(marker.bounding_box()["y"] - before_box["y"]) > 5,
                        (before_box, marker.bounding_box()))))
    shot(page, "13c-rider-on-map")
    check("tracking map: the rider's trail so far, a dashed line to home only (no kitchen-to-home route)", lambda: (
        expect(route_map).to_have_attribute("data-heading", "home"),
        eventually(lambda: _assert(int(route_map.get_attribute("data-trail") or 0) >= 2, route_map.get_attribute("data-trail")))))

    # The ETA comes from the distance left: further away, then closer, and the minutes and "km left" go down.
    eta_box = page.locator('[data-testid="eta"]:visible')
    north = lambda km: api("POST", "/delivery/driver/location", rider, {  # noqa: E731
        "lat": z[0] + km / 111.195, "lng": z[1], "order_id": order_id}, host=8004)
    left_re = re.compile(r"On the way · ([\d.]+) km left")
    timeline = page.get_by_role("region", name="Order steps")
    seen: dict[str, float] = {}

    def eta_after(km: float, key: str) -> None:
        north(km)
        def read() -> None:
            # minutes and km left from the same render: read km, minutes, km again (one GPS fix
            # updates both at once; a fix landing between two reads would pair old with new)
            def km_left() -> float:
                m = left_re.search(timeline.inner_text())
                _assert(m is not None, timeline.inner_text())
                return float(m.group(1))  # type: ignore[union-attr]
            before = km_left()
            minutes = int(re.search(r"\d+", eta_box.inner_text()).group())  # type: ignore[union-attr]
            _assert(km_left() == before, "the ETA changed while reading it")
            # road distance (x1.3) from the rider to the door, as realtime worked it out
            _assert(abs(before - km * 1.3) < 0.3, f"{before} km left for a rider {km} km away")
            # the minutes are realtime's for the rider's last fix (GET /delivery/{id}/eta)
            want = api("GET", f"/delivery/{order_id}/eta", rider, host=8004)["estimated_delivery_minutes"]
            _assert(minutes == want, f"page says {minutes} min, realtime {want} min ({before} km left)")
            seen[key], seen[key + "_km"] = minutes, before
        eventually(read)
    check("tracking: the ETA comes from the distance left and goes down as the rider gets closer", lambda: (
        eta_after(3, "far"), eta_after(1, "near"),
        _assert(seen["near"] < seen["far"] and seen["near_km"] < seen["far_km"], seen)))
    # back at the door for the handover
    fix(1.0)
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    check("tracking: delivered, live (no reload), messages closed", lambda: (
        expect(status).to_contain_text("Delivered. Enjoy your meal.", timeout=20000),
        expect(page.get_by_role("button", name="Message")).to_have_count(0, timeout=10000)))
    shot(page, "14-delivered")
    # Rate after delivery: 1-5 stars, saved, shown back.
    rate = page.get_by_role("radiogroup", name="Your rating")
    rate.get_by_role("radio", name="5 stars").click()
    page.get_by_role("button", name="Send rating").click()
    check("rating: rate the delivered order, saved and shown back", lambda: (
        expect(page.get_by_text("Thanks for rating this order.")).to_be_visible(timeout=15000),
        # still there after a reload (from GET /orders/{id}/rating, not the page's memory)
        page.reload(wait_until="networkidle"),
        expect(page.get_by_role("heading", name="Your rating")).to_be_visible(timeout=15000),
        expect(page.get_by_text("5 stars").first).to_be_attached()))
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
    check("type scale: the receipt uses only the scale's font sizes", lambda: type_scale_only(page))
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

    # ── Time zones: a device in a US zone sees the order's city time ─────────────
    # Same customer (the session copied over), the browser set to America/Boise. The receipt's
    # "paid" time must be placed_at in the order's time_zone (from the API), not the device's clock.
    tz_ctx = b.new_context(viewport={"width": 1440, "height": 900}, timezone_id="America/Boise", storage_state=ctx.storage_state())
    tz_page = tz_ctx.new_page()
    placed = api("GET", f"/orders/{order_id}", ops)

    def clock(at: str, zone: str) -> re.Pattern[str]:
        t = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(ZoneInfo(zone))
        return re.compile(rf"\b{t.hour % 12 or 12}:{t.minute:02d}\s?{'am' if t.hour < 12 else 'pm'}", re.I)

    tz_page.goto(f"{base}/account/orders?order={order_id}", wait_until="networkidle")
    check("time zones: a US-zone browser sees the receipt in the order's city time", lambda: (
        _assert(tz_page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone") == "America/Boise", "device zone not set"),
        _assert(placed["time_zone"] == "Asia/Kolkata", placed.get("time_zone")),
        expect(tz_page.get_by_test_id("receipt-time")).to_have_text(clock(placed["placed_at"], placed["time_zone"]), timeout=15000),
        expect(tz_page.get_by_test_id("receipt-time")).not_to_have_text(clock(placed["placed_at"], "America/Boise"))))
    tz_ctx.close()

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
        if path in ("/", KITCHEN_PATH, "/checkout"):
            check(f"phone width {path}: only the type scale's font sizes", lambda: type_scale_only(m))
    m.goto(base, wait_until="networkidle")

    def banner_scrolls_away() -> None:
        expect(m.get_by_role("note").filter(has_text=TEST_BANNER)).to_be_visible()
        m.mouse.wheel(0, 900)
        m.wait_for_timeout(400)
        header = m.locator("header").first.bounding_box()
        _assert(header is not None and abs(header["y"]) < 1, f"sticky header not at the top after scrolling: {header}")
        banner = m.get_by_test_id("test-site-banner").bounding_box()
        _assert(banner is None or banner["y"] + banner["height"] <= 1, f"banner still covers the page: {banner}")
        m.mouse.wheel(0, -900)
    check("phone width: the test-site banner scrolls away; the sticky header still sticks", banner_scrolls_away)
    m.goto(base + KITCHEN_PATH, wait_until="networkidle")
    m.screenshot(path=f"{OUT}/19-kitchen-phone.png", full_page=False)
    anon_phone = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    anon_phone.goto(base + "/signin", wait_until="networkidle")
    check("phone width /signin: no sideways scroll", lambda: no_sideways_scroll(anon_phone))
    anon_phone.goto(base, wait_until="networkidle")
    check("phone width landing: no sideways scroll", lambda: no_sideways_scroll(anon_phone))

    def phone_pill_and_line() -> None:
        expect(anon_phone.locator("header").first.get_by_test_id("language-pill")).to_have_text("EN")
        expect(anon_phone.get_by_test_id("location-line")).to_contain_text("Change city")
        anon_phone.get_by_test_id("language-pill").click()
        menu = anon_phone.get_by_role("menu", name="Language")
        expect(menu).to_be_visible()
        expect(anon_phone.get_by_role("dialog")).to_have_count(0)  # a dropdown anchored to the pill, not a sheet
        box = menu.bounding_box()
        _assert(box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["height"] < 600, box)
        anon_phone.keyboard.press("Escape")
    check("phone width: the same language pill (a small dropdown) and the location line", phone_pill_and_line)

    # R8: the IP's own town, shown as itself; "We deliver here" only inside a live zone, and only then that
    # city's kitchens and example bill. Never the country's first live city.
    def ip_visit(hint: dict, width: int = 1440):  # type: ignore[no-untyped-def]
        c = b.new_context(viewport={"width": width, "height": 900})
        fake_hint(c, hint)
        pg = c.new_page()
        pg.goto(base, wait_until="networkidle")
        expect(pg.get_by_test_id("location-line")).to_have_attribute("data-source", "ip", timeout=15000)  # after the hint's refresh
        return c, pg

    c_in, pg_in = ip_visit({"country": "US", "place": "Meridian", "region": "Idaho", "region_code": "ID",
                            "city_code": "US-ID-BOI", "city_name": "Boise", "city_path": "/us/boise", "served": True})
    check("IP place inside a live zone: Meridian, ID · We deliver here · Change city; Boise's bill in dollars", lambda: (
        expect(pg_in.get_by_test_id("location-line")).to_have_text("Meridian, ID · We deliver here · Change city"),
        expect(pg_in.get_by_test_id("who-gets")).to_have_attribute("data-city", "US-ID-BOI"),
        expect(pg_in.get_by_test_id("who-gets")).to_contain_text("$")))
    c_in.close()
    c_out, pg_out = ip_visit({"country": "US", "place": "Challis", "region": "Idaho", "region_code": "ID", "served": False})
    check("IP place we don't serve: Challis, ID · Set your delivery location; no other city's kitchens or bill", lambda: (
        expect(pg_out.get_by_test_id("location-line")).to_have_text("Challis, ID · Set your delivery location · Change city"),
        expect(pg_out.get_by_test_id("who-gets")).to_have_count(0),
        expect(pg_out.get_by_role("heading", name="What's cooking near you")).to_have_count(0),
        expect(pg_out.get_by_test_id("landing-hero")).to_have_attribute("src", re.compile(
            "/food/" + re.escape(hero_of["US"]) + r"-\d+\.webp$"))))  # the IP's country's hero and currency
    c_out.close()

    # R8: /cities and Change city at 360 px: no sideways scroll (coming-soon cards used to push it)
    narrow = b.new_context(viewport={"width": 360, "height": 780})
    fake_hint(narrow, {})
    nar = narrow.new_page()
    for path in ("/cities", "/cities?choose=1"):
        nar.goto(base + path, wait_until="networkidle")
        check(f"360 px {path}: no sideways scroll", lambda: no_sideways_scroll_at(nar, 360))
    nar.screenshot(path=f"{OUT}/22-change-city-360.png", full_page=True)
    narrow.close()

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
