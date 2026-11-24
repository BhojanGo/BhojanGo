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
marketing when signed in, a US kitchen in dollars, Deliver with BhojanGo (/deliver: each seed
city's real pay and requirements; locally, signing up a new phone), SEO files and headers, and
no sideways scroll at 390 px, and only the type scale's font sizes on the
kitchen page, home, receipt and (at 390) checkout (font_sizes.py); Terms and Privacy per
country (key points, contents, versions, the draft banner, a country without documents)
and the "updated policies" notice after an admin publishes a new version (R8 F10).
"""
import json
import os
import random
import re
import socket
import sys
import threading
import uuid
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
TOTP_KEYS: dict[str, str] = {}
if os.environ.get("E2E_LOGINS_FILE"):
    with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as _f:
        _rows = [line.rstrip("\n").split("\t") for line in _f]
    PASSWORDS = {r[2]: r[3] for r in _rows if len(r) >= 4}
    TOTP_KEYS = {r[2]: r[4] for r in _rows if len(r) >= 5 and r[4]}  # admins' authenticator keys
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

# Accessibility (R9): axe-core on the main pages; serious or critical fails the run (tools/a11y, at /a11y).
sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "a11y"), "/a11y"]
from axe_check import Axe  # noqa: E402

AXE = Axe("web")

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


def a11y(page, name: str) -> None:  # type: ignore[no-untyped-def]
    """axe on the page as it is now: no serious or critical violations (all are written to a11y-web.md)."""
    check(f"a11y {name}: no serious or critical accessibility issues (axe)", lambda: AXE.scan(page, name))


def api(method: str, path: str, token: str | None = None, body: dict | None = None, host: int = 8001,
        headers: dict | None = None) -> dict:
    """The rest of the world (kitchen, ops, rider) through the same APIs the apps use."""
    import urllib.request

    root = (QA_RT if host == 8004 else QA_CORE) or f"http://localhost:{host}"
    req = urllib.request.Request(f"{root}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}),
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def login(email: str, password: str = "BhojanGo123") -> str:
    """API sign-in; admins pass the second step with the seed's authenticator key (tools/totp_signin.py)."""
    from totp_signin import finish

    body = api("POST", "/auth/login", None, {"email": email, "password": PASSWORDS.get(email, password)})
    return finish(lambda path, data: api("POST", path, None, data), email, body, TOTP_KEYS)["access_token"]


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
    # The site's calls carry its session cookies (R22 S8), so the answer names the page's origin, not "*".
    ctx.route(re.compile(r".*/api/v1/markets/hint$"), lambda route: route.fulfill(
        status=200, content_type="application/json", body=body,
        headers={"Access-Control-Allow-Origin": route.request.headers.get("origin", "*"), "Access-Control-Allow-Credentials": "true"}))


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
    check("location line, nothing known: only Set your delivery location; no other city's bill", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Set your delivery location"),
        expect(page.get_by_test_id("change-city")).to_have_count(0),
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
    TEST_BANNER = "Test site: demo restaurants, no real orders or payments"
    check("test-site banner: on the landing page, above the header, a note (not an alert)", lambda: (
        expect(page.get_by_role("note").filter(has_text=TEST_BANNER)).to_be_visible(),
        expect(page.get_by_role("alert").filter(has_text=TEST_BANNER)).to_have_count(0),
        _assert(page.get_by_test_id("test-site-banner").bounding_box()["y"] < page.locator("header").first.bounding_box()["y"],
                "banner is not above the header")))
    shot(page, "01-landing")
    a11y(page, "landing")

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
        """The location line's "Change" (a known city) or the city list itself (nothing known) -> the city -> home."""
        if pg.get_by_test_id("change-city").count():
            pg.get_by_test_id("change-city").click()
        else:
            pg.goto(base + "/cities?choose=1", wait_until="networkidle")
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
    # Nothing is known about this visitor yet, so the line has no "Change": the city list itself.
    page.goto(base + "/cities?choose=1", wait_until="networkidle")
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
        page.get_by_role("img", name=re.compile(r"^Restaurant \d+%"))).to_be_visible())
    check("location line: Hyderabad, TG · Change (above the hero)", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Hyderabad, TG · Change"),
        _assert(cookie(ctx, "bg_city") == "IN-TG-HYD", ctx.cookies()),
        _assert(page.get_by_test_id("location-line").bounding_box()["y"] < page.get_by_role("heading", level=1).bounding_box()["y"],
                "the location line is not above the hero")))
    check("who gets your money: real percentages from the example quote, adding to 100", lambda: split_matches_api(page))

    def who_gets_one_line(width: int) -> None:
        """Round 20: at desktop widths every payee label sits on one line, next to its percentage."""
        page.set_viewport_size({"width": width, "height": 1000})
        page.wait_for_timeout(400)
        card = page.get_by_test_id("who-gets")
        card.scroll_into_view_if_needed()
        for li in card.locator("li[data-payee]").all():
            label, pct = li.get_by_test_id("payee-label"), li.locator("b")
            lb, pb = label.bounding_box(), pct.bounding_box()
            line = float(label.evaluate("el => parseFloat(getComputedStyle(el).lineHeight)"))
            _assert(lb is not None and pb is not None, li.inner_text())
            _assert(lb["height"] <= line * 1.2, (width, li.get_attribute("data-payee"), "label wraps", lb["height"], line))
            _assert(label.evaluate("el => el.scrollWidth <= el.clientWidth"), (width, li.get_attribute("data-payee"), "label cut off"))
            _assert(abs((lb["y"] + lb["height"] / 2) - (pb["y"] + pb["height"] / 2)) <= 2, (width, "percentage out of line", lb, pb))
        card.screenshot(path=f"{OUT}/24-who-gets-{width}.png")

    for w in (1024, 1440):
        check(f"who gets your money at {w}: each label on one line, next to its percentage", lambda w=w: who_gets_one_line(w))
    page.set_viewport_size({"width": 1440, "height": 900})
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
    check("change city to Boise: Boise, ID; dollars; Telugu isn't offered there, so English", lambda: (
        expect(page.get_by_test_id("location-line")).to_have_text("Boise, ID · Change"),
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
    price = page.get_by_role("region", name="Biryani").get_by_text(re.compile(r"^₹[\d,]+$")).first.inner_text()  # R36: whole rupees
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
    feed = page.get_by_role("region", name="Restaurants near you")
    check("personal home: kitchens for the address, offers with who pays, cards with the delivery fee", lambda: (
        expect(page.get_by_text(re.compile(r"^\d+ restaurants? delivers? to Madhapur"))).to_be_visible(timeout=20000),
        # R37: offers BhojanGo pays for are off in every seed: only restaurants' own offers (the demo data's; the
        # base seed has none), each saying who pays
        expect(page.get_by_role("region", name="Offers near you").get_by_text(re.compile("BhojanGo pays", re.I))).to_have_count(0),
        _assert(page.get_by_role("region", name="Offers near you").count() == 0
                or page.get_by_role("region", name="Offers near you").get_by_text(re.compile("Restaurant pays", re.I)).count() > 0, "an offer without who pays"),
        expect(feed.get_by_role("link", name=re.compile(KITCHEN))).to_be_visible(),
        expect(feed.get_by_role("link", name=re.compile(KITCHEN))).to_contain_text(re.compile(r"₹[\d,]+ delivery|Free delivery")),  # R36: whole rupees
        expect(page.get_by_text("Orders over ₹0")).to_have_count(0)))
    check("personal home: the address is on the page, not in the header; no marketing", lambda: (
        expect(page.get_by_test_id("change-address")).to_contain_text("Madhapur"),
        expect(page.locator("header").get_by_role("button", name="Change address")).to_have_count(0),
        expect(page.get_by_role("heading", name="Cook with BhojanGo")).to_have_count(0)))
    check("personal home: the location line names the address's city", lambda: expect(
        page.get_by_test_id("location-line")).to_have_text("Hyderabad, TG · Change"))
    shot(page, "03-home-address")
    cards = feed.get_by_role("link")

    def counts_agree() -> None:
        # "N restaurants deliver to <address>" counts the deliverable cards; "See all M" opens every card, R31: with
        # the ones past the max delivery distance last, marked "Too far to deliver" (/discover for the address).
        said = page.get_by_text(re.compile(r"^\d+ restaurants? delivers? to Madhapur")).inner_text()
        n = int(said.split()[0])
        see_all = feed.get_by_role("button", name=re.compile(r"^See all \d+$"))
        total = int(see_all.inner_text().split()[-1]) if see_all.count() else None
        if see_all.count():
            see_all.click()
            expect(see_all).to_have_count(0)
        far = feed.get_by_test_id("too-far").count()
        pickup = feed.get_by_test_id("pickup-only").count()  # R36: too far to deliver, but takes pickup
        _assert(cards.count() - far - pickup == n, f"{said!r} but {cards.count()} cards, {far} too far, {pickup} pickup only")
        if total is not None:
            _assert(cards.count() == total, f"See all {total} but {cards.count()} cards")
    check("personal home: kitchens that deliver, See all and the cards are the same number", counts_agree)
    n_all = cards.count()
    chips = page.get_by_role("group", name="Filter restaurants")
    chips.get_by_role("button", name="Veg only").click()
    check("filters: a chip narrows the kitchens, pressed state shown", lambda: (
        expect(chips.get_by_role("button", name="Veg only")).to_have_attribute("aria-pressed", "true"),
        _assert(cards.count() < n_all or page.get_by_text("No restaurants match those filters. Try fewer.").is_visible(),
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
    a11y(page, "cities")
    page.goto(base + hyd["path"], wait_until="networkidle")
    check("live city page: title, kitchens, a real bill, ItemList and canonical", lambda: (
        expect(page).to_have_title("Food delivery in Hyderabad · BhojanGo"),
        expect(page.get_by_role("heading", name="Food delivery in Hyderabad", level=1)).to_be_visible(),
        expect(page.get_by_role("region", name="Restaurants in Hyderabad").get_by_role("link", name=re.compile(KITCHEN))).to_be_visible(),
        # a real recent order's bill, or a typical one on a fresh database
        expect(page.get_by_text(re.compile(r"^A (real|typical) Hyderabad bill$"))).to_be_visible(),
        _assert(any(json.loads(s).get("@type") == "ItemList" for s in page.locator('script[type="application/ld+json"]').all_inner_texts()), "no ItemList"),
        expect(page.locator('link[rel="canonical"]')).to_have_attribute("href", f"{SITE}{hyd['path']}")))
    # The FAQ answers with Hyderabad's own rules (tools/seed/data.py): delivery slabs, service fee, tips.
    check("live city page: FAQ from the city's rules (actual amounts and distances)", lambda: (
        # R31: the delivery fee from distance bands, up to the max delivery distance
        expect(page.get_by_text(re.compile(r"₹30 up to 3 km; ₹40 up to 5 km; ₹50 up to 7 km"))).to_be_attached(),
        # R29 fee model v2: the platform fee replaced the service fee
        expect(page.get_by_text(re.compile(r"A platform fee of 10% of the food \(at least ₹15\) goes to BhojanGo"))).to_be_attached(),
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
    a11y(page, "city")
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
    expect(page.get_by_role("region", name="Restaurants near you")).to_be_visible(timeout=20000)
    page.get_by_role("region", name="Restaurants near you").get_by_role("link", name=re.compile(KITCHEN)).click()
    url_is(page, KITCHEN_PATH + "$")
    ld = lambda: [json.loads(s) for s in page.locator('script[type="application/ld+json"]').all_inner_texts()]  # noqa: E731
    check("kitchen page: menu sections, Restaurant + Menu structured data", lambda: (
        expect(page.get_by_role("heading", name=KITCHEN, level=1)).to_be_visible(timeout=15000),
        expect(page.get_by_role("navigation", name="Menu sections")).to_be_visible(),
        expect(page.get_by_role("region", name="Biryani")).to_be_visible(),
        _assert(any(x.get("@type") == "Restaurant" and x.get("hasMenu") for x in ld()), ld())))
    check("type scale: the kitchen page uses only the scale's font sizes", lambda: type_scale_only(page))
    a11y(page, "kitchen")
    page.get_by_role("button", name=f"Add {DISH}").click()
    dialog = page.get_by_role("dialog", name=DISH)
    check("customise sheet: required and optional groups with prices", lambda: (
        expect(dialog.get_by_role("group", name=re.compile("^Size Required"))).to_be_visible(),
        expect(dialog.get_by_role("radio", name=re.compile(r"^Regular"))).to_be_checked(),
        expect(dialog.get_by_role("checkbox", name=re.compile(r"^Extra raita \+₹\d+"))).to_be_visible()))
    total_before = dialog.get_by_role("button", name=re.compile("^Add to cart")).inner_text()
    dialog.get_by_text("Extra raita").click()
    check("customise sheet: an add-on changes the price on the button", lambda: expect(dialog.get_by_role("button", name=re.compile("^Add to cart"))).not_to_have_text(total_before))
    shot(page, "07-customise")
    dialog.get_by_role("button", name=re.compile("^Add to cart")).click()
    bag = page.get_by_role("complementary", name="Your cart")
    check("bag: the dish with its options; asks to sign in for the whole bill", lambda: (
        expect(bag.get_by_text(re.compile(rf"1 × {DISH}"))).to_be_visible(),
        expect(bag.get_by_text(re.compile("Extra raita"))).to_be_visible(),
        expect(bag.get_by_text(re.compile("^Sign in and choose your address"))).to_be_visible()))
    shot(page, "08-kitchen-bag")

    # ── Email sign-in (round 8, D5): two equal tabs; password, code, new account, forgot, reset ──
    em_ctx = b.new_context(viewport={"width": 1366, "height": 900})
    em = em_ctx.new_page()
    em.goto(base + "/signin", wait_until="networkidle")

    def equal_tabs() -> None:
        phone_tab, email_tab = em.get_by_role("tab", name="Phone"), em.get_by_role("tab", name="Email")
        expect(phone_tab).to_have_attribute("aria-selected", "true")
        expect(email_tab).to_have_attribute("aria-selected", "false")
        a, c = phone_tab.bounding_box(), email_tab.bounding_box()
        _assert(a and c and abs(a["width"] - c["width"]) < 1 and abs(a["height"] - c["height"]) < 1, f"tabs differ: {a} {c}")
        expect(phone_tab).to_have_css("font-weight", email_tab.evaluate("e => getComputedStyle(e).fontWeight"))
    check("sign in: Phone and Email are two equal tabs (same size and weight)", equal_tabs)
    em.get_by_role("tab", name="Phone").focus()
    em.keyboard.press("ArrowRight")
    check("sign in: arrow keys move between the tabs; the address keeps the choice", lambda: (
        expect(em.get_by_role("tab", name="Email")).to_be_focused(),
        expect(em.get_by_role("tab", name="Email")).to_have_attribute("aria-selected", "true"),
        _assert("way=email" in em.url, em.url)))
    check("email tab: email and password, an email code instead, forgot password, a new account", lambda: (
        expect(em.get_by_role("textbox", name="Email")).to_be_visible(),
        expect(em.locator("input[name=password]")).to_have_attribute("autocomplete", "current-password"),
        expect(em.get_by_role("button", name="Email me a code instead")).to_be_visible(),
        expect(em.get_by_role("link", name="Forgot password?")).to_be_visible(),
        expect(em.get_by_role("button", name="Create an account")).to_be_visible()))
    shot(em, "09b-signin-email")
    a11y(em, "signin-email")
    wrong_answers = []
    for who in ("customer2.hyd@example.com", f"nobody.{uuid.uuid4().hex[:8]}@example.com"):
        em.get_by_role("textbox", name="Email").fill(who)
        em.locator("input[name=password]").fill("not-the-password-1")
        em.get_by_role("button", name="Sign in", exact=True).click()
        expect(em.locator("p[role=alert]")).to_be_visible(timeout=15000)  # (Next's route announcer is an empty alert too)
        wrong_answers.append(em.locator("p[role=alert]").inner_text())
    check("email sign-in: a wrong password and an unknown email get the same plain answer", lambda: (
        _assert(wrong_answers[0] == wrong_answers[1], f"{wrong_answers}"),
        _assert("don't match" in wrong_answers[0], wrong_answers[0])))
    em.get_by_role("textbox", name="Email").fill("customer2.hyd@example.com")
    em.locator("input[name=password]").fill(PASSWORDS.get("customer2.hyd@example.com", "BhojanGo123"))
    em.get_by_role("button", name="Sign in", exact=True).click()
    step("email sign-in: the seeded customer's password signs in", lambda: url_is(em, r"^(?!.*/signin).*$"))
    em_ctx.close()

    em_ctx = b.new_context(viewport={"width": 390, "height": 844})
    em = em_ctx.new_page()
    new_email = f"web.e2e.{uuid.uuid4().hex[:8]}@example.com"
    em.goto(base + "/signin?way=email&mode=create", wait_until="networkidle")
    check("new account: the Email tab opens on Create your account (?way=email&mode=create)", lambda: (
        expect(em.get_by_role("heading", name="Create your account")).to_be_visible(),
        expect(em.locator("input[name=new-password]")).to_have_attribute("autocomplete", "new-password")))
    em.get_by_role("textbox", name="Email").fill(new_email)
    em.locator("input[name=new-password]").fill("short")
    em.get_by_role("button", name="Create account").click()
    check("new account: a short password is refused before anything is sent", lambda:
          expect(em.locator("p[role=alert]")).to_contain_text("at least 10 characters"))
    em.locator("input[name=new-password]").fill("Web-e2e-password-2026")
    em.get_by_role("button", name="Create account").click()
    check("new account: a 6-digit code goes to the email first", lambda: (
        expect(em.get_by_role("heading", name="Check your email")).to_be_visible(timeout=15000),
        expect(em.get_by_role("textbox", name=re.compile("^Digit "))).to_have_count(6)))
    shot(em, "09c-signup-code-phone")
    em.get_by_role("textbox", name="Digit 1").fill(OTP)  # @example.com: the fixed code outside production
    em.get_by_role("button", name="Continue").click()
    step("new account: the code signs the new account in", lambda: url_is(em, r"^(?!.*/signin).*$"))
    em.goto(base + "/account/profile", wait_until="networkidle")
    check("profile: Sign-in and security shows the verified email and the password", lambda: (
        expect(em.get_by_role("heading", name="Sign-in and security")).to_be_visible(timeout=15000),
        expect(em.get_by_text(new_email)).to_be_visible(),
        expect(em.get_by_text("Verified · you can sign in with it")).to_be_visible(),
        expect(em.get_by_role("button", name="Add", exact=True)).to_be_visible()))
    shot(em, "09d-profile-security-phone")
    a11y(em, "profile")
    em_ctx.close()

    em_ctx = b.new_context(viewport={"width": 1366, "height": 900})
    em = em_ctx.new_page()
    forgot_answers = []
    for who in ("customer3.hyd@example.com", f"nobody.{uuid.uuid4().hex[:8]}@example.com"):
        em.goto(base + "/signin/forgot", wait_until="networkidle")
        em.get_by_role("textbox", name="Email").fill(who)
        em.get_by_role("button", name="Send link").click()
        expect(em.get_by_role("heading", name="Check your email")).to_be_visible(timeout=15000)
        forgot_answers.append(em.get_by_role("status").filter(has_text="BhojanGo account").inner_text().replace(who, "<email>"))
    check("forgot password: the same answer whether or not the email has an account", lambda:
          _assert(forgot_answers[0] == forgot_answers[1], f"{forgot_answers}"))
    shot(em, "09e-forgot-sent")
    em.goto(base + "/signin/reset?token=" + "x" * 43, wait_until="networkidle")
    check("reset link: an expired or used link says so and offers a new one", lambda: (
        expect(em.locator("p[role=alert]")).to_contain_text("expired or was already used", timeout=15000),
        expect(em.get_by_role("link", name="Ask for a new link")).to_have_attribute("href", "/signin/forgot")))
    em_ctx.close()

    # ── Sign in with phone + OTP (/signin, /signin/code) ──────────────────────
    bag.get_by_role("link", name="Go to checkout").click()
    url_is(page, r"/signin\?next=%2Fcheckout|/signin\?next=/checkout")
    check("sign in: phone first, country code from the directory", lambda: (
        expect(page.get_by_role("heading", name="Sign in or create an account", level=1)).to_be_visible(),
        expect(page.get_by_label("Country code")).to_have_value("IN")))
    shot(page, "09-signin")
    a11y(page, "signin-phone")
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
    # R22 S8: the session is in httpOnly cookies on the API's host; the page's storage holds no token.
    check("sign in: the session is an httpOnly cookie, and no token is in the page's storage", lambda: (
        _assert(not re.search(r"eyJ[\w-]+\.eyJ", page.evaluate("JSON.stringify(Object.assign({}, localStorage, sessionStorage))")),
                "a token in web storage"),
        _assert(any(c["name"] == "bg_web_at" and c["httpOnly"] and c["secure"] and c["sameSite"] == "Lax" for c in ctx.cookies()),
                [(c["name"], c["httpOnly"], c["sameSite"]) for c in ctx.cookies()]),
        _assert(page.evaluate("document.cookie").find("bg_web_") == -1, "a script can read the session cookie")))

    # The bag on the kitchen page now has the whole bill (signed in, an address).
    page.goto(base + KITCHEN_PATH, wait_until="networkidle")
    check("bag: the fair bill once signed in", lambda: (
        expect(bag.get_by_role("row", name=re.compile("^Food Restaurant"))).to_be_visible(timeout=20000),
        expect(bag.get_by_role("row", name=re.compile("^Delivery.*100% to your delivery partner"))).to_be_visible(),  # R29: all of it
        expect(bag.get_by_role("row", name=re.compile("^Platform fee BhojanGo"))).to_be_visible(),
        expect(bag.get_by_role("row", name=re.compile("^GST on food Government"))).to_be_visible()))
    check("signed in: no marketing on the kitchen page header", lambda: expect(page.get_by_role("banner").get_by_role("link", name="Deliver with BhojanGo")).to_have_count(0))

    # ── Checkout ──────────────────────────────────────────────────────────────
    page.goto(base + "/checkout", wait_until="networkidle")
    bill = page.get_by_role("complementary", name="Your order")
    check("checkout: saved address, live fair bill with who gets what, price held", lambda: (
        expect(page.get_by_role("region", name="Deliver to")).to_contain_text("Home", timeout=20000),
        expect(bill.get_by_text("The fair bill")).to_be_visible(timeout=20000),
        expect(bill.get_by_role("row", name=re.compile("^Food Restaurant"))).to_be_visible(),
        expect(bill.get_by_role("row", name=re.compile("^Delivery.*100% to your delivery partner"))).to_be_visible(),  # R29: all of it
        expect(bill.get_by_role("row", name=re.compile("^Platform fee BhojanGo"))).to_be_visible(),
        expect(bill.get_by_text(re.compile("This price is held for"))).to_be_visible()))
    tips = page.get_by_role("radiogroup", name="Tip your delivery partner").get_by_role("radio")
    # "None", then India's tip_presets rule (10, 20, 30; the second preselected), then "Other".
    check("tip: choices from the tip_presets rule, its default preselected", lambda: (
        _assert([tips.nth(i).inner_text().strip() for i in range(tips.count())] == ["None", "₹10", "₹20", "₹30", "Other"],  # R36: whole rupees
                [tips.nth(i).inner_text() for i in range(tips.count())]),
        expect(tips.nth(2)).to_have_attribute("aria-checked", "true")))
    tip_label = tips.nth(2).inner_text().strip()
    tips.nth(2).click()
    check("tip: on the bill as the rider's", lambda: (
        expect(bill.get_by_role("row", name=re.compile(r"^Tip for your delivery partner 100% to your delivery partner"))).to_contain_text(tip_label, timeout=15000)))  # the chip and the bill read alike (R12: two decimals)
    def bill_to_the_paisa() -> None:
        """R37: India's bill in exact paise (₹385.80, never ₹386): every printed line adds up to the printed total."""
        cells = [c.strip() for c in bill.locator("table tbody tr:not([data-testid='tax-share']) td:last-child").all_inner_texts()]
        total = bill.locator("div.border-dashed b").last.inner_text().strip()
        _assert(cells and all(re.fullmatch(r"−?₹[\d,]+\.\d{2}", c) for c in cells + [total]), (cells, total))
        paise = lambda v: (-1 if v.startswith("−") else 1) * int(re.sub(r"[^\d]", "", v))  # noqa: E731
        _assert(sum(paise(c) for c in cells) == paise(total), (cells, total))
        expect(page.get_by_role("button", name=re.compile(r"^Pay ")).first).to_contain_text(total)
    check("R37 India: the fair bill and Pay in exact paise, the lines add up to the total", bill_to_the_paisa)
    shot(page, "11-checkout")
    a11y(page, "checkout")
    page.get_by_role("button", name=re.compile(r"^Pay ")).click()
    pay = page.get_by_role("dialog", name="Pay (test mode)")
    check("pay: the test provider's checkout", lambda: expect(pay).to_be_visible(timeout=30000))
    pay.get_by_role("button", name=re.compile("^Approve")).click()
    url_is(page, r"/orders/[0-9a-f-]{36}/track$", 40000)
    order_id = page.url.rstrip("/").split("/")[-2]
    status = page.get_by_role("region", name="Order status")
    check("tracking: status, ETA, the bill paid; no door PIN before pickup (R27)", lambda: (
        expect(status.get_by_text(f"{KITCHEN} has your order")).to_be_visible(timeout=20000),
        expect(page.locator('[data-testid="eta"]:visible')).to_be_visible(),
        expect(page.locator('[data-testid="delivery-pin"]')).to_have_count(0),
        expect(page.get_by_role("region", name="Your order").get_by_text("The fair bill")).to_be_visible(),
        expect(page.get_by_text("You paid")).to_be_visible()))
    shot(page, "12-tracking")
    a11y(page, "tracking")

    # The home page while an order is on: the active order bar, still no marketing.
    page.goto(base, wait_until="networkidle")
    check("signed-in home: active order bar, no marketing sections", lambda: (
        expect(page.get_by_role("region", name="Your order").get_by_role("link", name=re.compile(f"^Your order from {KITCHEN}.*Track order$"))).to_be_visible(timeout=20000),
        expect(page.get_by_role("heading", name="Cook with BhojanGo")).to_have_count(0),
        expect(page.get_by_role("heading", name="Deliver with BhojanGo")).to_have_count(0),
        expect(page.get_by_role("region", name="Work with us")).to_have_count(0),
        expect(page.get_by_role("contentinfo").get_by_role("link", name="Deliver with BhojanGo")).to_be_visible()))
    check("type scale: the signed-in home uses only the scale's font sizes", lambda: type_scale_only(page))
    shot(page, "13-home-signed-in")

    # The kitchen, ops and the rider move the order along; the page follows live.
    page.goto(f"{base}/orders/{order_id}/track", wait_until="networkidle")
    partner, ops, rider = login("partner.hyd@example.com"), login("ops.hyd@example.com", "BhojanGoAdmin1"), login("rider3.hyd@example.com")
    for st in ("accepted", "preparing", "ready"):
        api("PUT", f"/orders/{order_id}/status", partner, {"status": st})
    check("tracking: the kitchen cooking, live", lambda: expect(status).to_contain_text(re.compile(f"{KITCHEN} is cooking|Finding a delivery partner"), timeout=20000))
    api("POST", "/delivery/assign", ops, {"order_id": order_id, "driver_id": sub(rider)}, host=8004)
    api("POST", f"/orders/{order_id}/messages", rider, {"preset": "at_kitchen"})
    chat = page.get_by_role("region", name=re.compile("^Your delivery partner, "))
    expect(chat.get_by_role("button", name="Message")).to_be_visible(timeout=20000)
    chat.get_by_role("button", name="Message").click()
    check("messages: the rider's quick message reaches the tracking page, numbers private", lambda: (
        expect(chat.get_by_text("I'm at the restaurant, waiting for your order.")).to_be_visible(timeout=20000),
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
    check("tracking: still no door PIN while the rider waits at the kitchen", lambda: (
        expect(page.locator('[data-testid="delivery-pin"]')).to_have_count(0)))
    api("PUT", f"/orders/{order_id}/status", rider, {"status": "picked_up"})
    check("tracking: picked up, live, and now the PIN for the door", lambda: (
        expect(status).to_contain_text("has picked up your order", timeout=20000),
        expect(page.locator('[data-testid="delivery-pin"]:visible')).to_have_text(re.compile(r"^\d{4}$"), timeout=20000)))
    pin = page.locator('[data-testid="delivery-pin"]:visible').inner_text()
    # The rider's GPS, as the rider app sends it: a rider marker on the real map
    # (MapLibre + OpenFreeMap, OSM credited) between the kitchen and home, and it moves.
    o = api("GET", f"/orders/{order_id}", rider)
    a, z = (o["pickup_lat"], o["pickup_lng"]), (o["delivery_lat"], o["delivery_lng"])
    fix = lambda f: api("POST", "/delivery/driver/location", rider, {  # noqa: E731
        "lat": a[0] + (z[0] - a[0]) * f, "lng": a[1] + (z[1] - a[1]) * f, "order_id": order_id}, host=8004)
    fix(0.3)
    route_map = page.get_by_role("region", name="Map of your order's route")
    marker = route_map.get_by_role("img", name=re.compile("your delivery partner$"))
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
            # R31: the road distance from the rider to the door (OSRM, or straight-line x 1.3 when routing is off):
            # never less than the straight line, and not absurdly more
            _assert(km - 0.05 <= before <= km * 2.5, f"{before} km left for a rider {km} km away")
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

    # R33: a pickup order's steps: Placed -> Preparing -> Ready for pickup -> Picked up (no "On the way", no home).
    import uuid as _uuid

    thali = next(x for x in api("GET", "/restaurants?limit=50")["items"] if x.get("slug") == "hitech-thali-hitec-city")
    meals = next(i["id"] for c in api("GET", f"/restaurants/{thali['id']}/menu")["categories"] for i in c["items"] if i["name"] == "Andhra Meals")
    cart = [{"menu_item_id": meals, "quantity": 2}]
    pq = api("POST", "/pricing/quote", customer, {"restaurant_id": thali["id"], "items": cart, "fulfillment": "pickup"})
    po = api("POST", "/orders", customer, {"restaurant_id": thali["id"], "items": cart, "payment_method": "upi", "quote_token": pq["token"]},
             headers={"X-Idempotency-Key": str(_uuid.uuid4())})
    intent = api("POST", "/payments/initiate", customer, {"order_id": po["id"], "payment_method_type": "upi"})
    api("POST", f"/payments/fake/{intent['payment_intent_id']}/complete", customer, {"outcome": "succeeded"})
    eventually(lambda: _assert(api("GET", f"/orders/{po['id']}", customer)["status"] == "placed", "pickup order not placed"), 30)
    pk = ctx.new_page()
    pk.goto(f"{base}/orders/{po['id']}/track", wait_until="networkidle")
    steps = pk.get_by_test_id("pickup-steps")
    check("pickup tracking: Placed, Preparing, Ready for pickup, Picked up; no delivery steps", lambda: (
        expect(steps.locator("li")).to_have_count(4, timeout=20000),
        expect(steps.locator("li b")).to_have_text(["Placed", "Preparing", "Ready for pickup", "Picked up"]),
        expect(pk.get_by_test_id("delivery-steps")).to_have_count(0),
        expect(steps).not_to_contain_text("On the way")))
    # R34: a pickup order never "arrives": "Ready in about N min" until it's ready
    hero_label, hero = pk.locator("[data-testid=eta-label]:visible"), pk.locator("[data-testid=eta]:visible")
    for st in ("accepted", "preparing"):
        api("PUT", f"/orders/{po['id']}/status", partner, {"status": st})
    pk.reload(wait_until="networkidle")
    check("pickup tracking before ready: 'Ready in about N min', never 'Arriving'", lambda: (
        expect(hero_label).to_have_text("Ready in about", timeout=20000),
        expect(hero).to_have_text(re.compile(r"^\d+ min$")),
        expect(pk.get_by_text("Arriving", exact=True)).to_have_count(0)))
    shot(pk, "14a-pickup-ready-in")
    api("PUT", f"/orders/{po['id']}/status", partner, {"status": "ready"})
    street = api("GET", f"/orders/{po['id']}", customer)["pickup_address"]["street"]
    check("pickup tracking: ready, the code shown, live", lambda: (
        expect(steps.locator("li[aria-current=step] b")).to_have_text("Ready for pickup", timeout=20000),
        expect(pk.get_by_test_id("pickup-code")).to_be_visible()))
    check("pickup tracking when ready: 'Ready for pickup' with the restaurant's address, no minutes", lambda: (
        expect(hero).to_have_text("Ready for pickup", timeout=20000),
        expect(hero.locator("xpath=..")).to_contain_text(street),
        expect(pk.get_by_text("Arriving", exact=True)).to_have_count(0)))
    shot(pk, "14b-pickup-steps-ready")
    code = api("GET", f"/orders/{po['id']}", customer)["pickup_code"]
    api("POST", f"/orders/{po['id']}/pickup", partner, {"code": code})
    pk.reload(wait_until="networkidle")
    check("pickup tracking: picked up, every step done", lambda: (
        expect(steps.locator("li")).to_have_count(4, timeout=20000),
        expect(steps.locator("li[aria-current=step]")).to_have_count(0),
        expect(pk.get_by_test_id("pickup-code")).to_have_count(0)))
    shot(pk, "14c-pickup-steps-collected")
    pk.close()
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
    page.get_by_label("Add a photo").set_input_files(files=[{"name": "biryani.png", "mimeType": "image/png", "buffer": png}])
    check("report a problem: the chosen photo is named in the page's language (no browser 'No file chosen')", lambda: (
        expect(page.get_by_text("biryani.png")).to_be_visible(),
        expect(page.get_by_role("button", name="Remove photo")).to_be_visible()))
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
    a11y(page, "account-orders")
    page.get_by_role("searchbox", name="Search by restaurant, dish or order code").fill(code[1:])
    check("orders: search by order code", lambda: (
        expect(lst.get_by_role("button", name=re.compile(re.escape(code)))).to_have_count(1, timeout=15000),
        expect(lst.get_by_role("button", name=re.compile(r"· #[0-9A-F]{6} "))).to_have_count(1)))
    page.get_by_role("searchbox", name="Search by restaurant, dish or order code").fill("")
    page.get_by_role("group", name="Show orders").get_by_role("button", name="Cancelled").click()
    check("orders: status filter", lambda: (
        expect(page.get_by_role("group", name="Show orders").get_by_role("button", name="Cancelled")).to_have_attribute("aria-pressed", "true"),
        expect(lst.get_by_role("button", name=re.compile(re.escape(code)))).to_have_count(0, timeout=15000),
        _assert(all(t.strip().endswith("Cancelled") for t in lst.get_by_role("button", name=re.compile(r"· #[0-9A-F]{6} ")).all_inner_texts()),
                "a non-cancelled order in the Cancelled filter")))
    # R27: at phone width every filter chip and every order code shows in full (R26: "Cancellec", "#7...")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("group", name="Show orders").get_by_role("button", name="All").click()
    expect(lst.get_by_role("button", name=re.compile(re.escape(code))).first).to_be_visible(timeout=15000)
    check("orders at 390 px: filter chips and order codes are never cut off", lambda: _assert(page.evaluate("""() => {
        const vw = window.innerWidth;
        const chips = [...document.querySelectorAll('[role=group] button[aria-pressed]')];
        const codes = [...document.querySelectorAll('[data-testid=order-code]')];
        const inside = (e, box) => { const r = e.getBoundingClientRect(); return r.left >= box.left - 1 && r.right <= box.right + 1; };
        return chips.length >= 4 && codes.length > 0
          && chips.every((e) => inside(e, {left: 0, right: vw}) && e.scrollWidth <= e.clientWidth + 1)
          && codes.every((e) => /^#[0-9A-F]{6}$/.test(e.textContent.trim()) && inside(e, e.closest('button').getBoundingClientRect()));
    }"""), "a filter chip or an order code is cut off at 390 px"))
    shot(page, "16a-orders-phone")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.get_by_role("group", name="Show orders").get_by_role("button", name="Delivered").click()
    lst.get_by_role("button", name=re.compile(re.escape(code))).first.click()
    receipt = page.get_by_role("article", name=f"Receipt for order {code}")
    check("receipt: the full bill with who gets each line", lambda: (
        expect(receipt.get_by_role("heading", name=KITCHEN)).to_be_visible(timeout=15000),
        expect(receipt.get_by_role("row", name=re.compile("^Food Restaurant"))).to_be_visible(),
        expect(receipt.get_by_role("row", name=re.compile("^GST on food Government"))).to_be_visible(),
        expect(receipt.get_by_role("row", name=re.compile("^Tip for your delivery partner 100% to your delivery partner"))).to_be_visible(),
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
    # R8: the customer cancels the new order before the kitchen accepts: one confirmation that
    # says what comes back and where, then the cancelled state and the refund line.
    page.get_by_role("button", name=re.compile(r"^Pay ")).click()
    page.get_by_role("dialog", name="Pay (test mode)").get_by_role("button", name=re.compile("^Approve")).click()
    url_is(page, r"/orders/[0-9a-f-]{36}/track$", 40000)
    cancel_box = page.get_by_test_id("cancel-order")
    check("cancel: offered while the kitchen hasn't started, with the API's rule", lambda: (
        expect(cancel_box.get_by_text("You can cancel until the restaurant starts cooking.")).to_be_visible(timeout=20000),
        expect(cancel_box.get_by_role("button", name="Cancel order")).to_be_visible()))
    cancel_box.get_by_role("button", name="Cancel order").click()
    check("cancel: asks once and says what comes back, to where", lambda: (
        expect(cancel_box.get_by_role("heading", name="Cancel this order?")).to_be_visible(),
        expect(cancel_box).to_contain_text(re.compile(r"You'll get ₹[\d,.]+ back to your \w+"))))
    cancel_box.get_by_role("button", name="Yes, cancel order").click()
    check("cancel: the order is cancelled and the refund line shows", lambda: (
        expect(page.locator('[data-testid="eta"]:visible')).to_have_text("Cancelled", timeout=20000),
        expect(page.get_by_test_id("refund-line")).to_contain_text(re.compile(r"₹[\d,.]+ (refunded to your|to your .* is on its way)")),
        expect(page.get_by_test_id("cancel-order")).to_have_count(0)))
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

    # "Add your kitchen" (R8 F7): a landing page, then a new kitchen partner account
    # with email and password, straight into the application's steps.
    kctx = b.new_context(viewport={"width": 1440, "height": 900})
    kctx.add_cookies([{"name": "bg_city", "value": "IN-TG-HYD", "url": base}])
    k = kctx.new_page()
    k.goto(base + "/partner", wait_until="networkidle")
    a11y(k, "partner")
    check("/partner: a landing page with live terms, documents and FAQ (not a sign-in wall)", lambda: (
        expect(k.get_by_role("heading", level=1)).to_be_visible(),
        expect(k.get_by_test_id("partner-hero")).to_be_visible(),
        expect(k.get_by_test_id("fact-commission")).to_contain_text("%"),
        expect(k.get_by_test_id("partner-docs").locator("[data-doc=fssai]")).to_be_visible(),
        expect(k.get_by_test_id("partner-bill")).to_be_visible(),
        expect(k.locator("details")).to_have_count(8),
        _assert(k.locator("a[href='/sign-in'], a[href^='/sign-in?']").count() == 0, "a link to /sign-in (no such page)")))
    shot(k, "21-partner-landing")
    k.get_by_test_id("partner-start").click()
    form = k.get_by_test_id("partner-form")
    form.get_by_role("button", name="Create account and continue").click()
    check("/partner form: empty fields are named, tied to their inputs, nothing sent", lambda: (
        expect(k.get_by_test_id("partner-form-error")).to_have_text(re.compile(r"Fix [67] fields to continue.")),  # 6 when the city is the visitor's own
        expect(form.get_by_label("Restaurant name")).to_have_attribute("aria-invalid", "true"),
        expect(form.get_by_text("Use at least 10 characters.")).to_be_visible()))
    n = random.randint(10000, 99999)
    email = f"kitchen{n}@example.com"
    form.get_by_label("Restaurant name").fill("Lata's Kitchen")
    form.get_by_label("City").select_option("IN-TG-HYD")
    form.get_by_label("Your name").fill("Lata Menon")
    form.get_by_label("Mobile number").fill(f"90002{n}")
    form.get_by_label("Email").fill(email)
    form.get_by_label("Password", exact=True).fill("short")
    form.get_by_role("checkbox").check()
    form.get_by_role("button", name="Create account and continue").click()
    check("/partner form: a short password is refused before sending", lambda: expect(k.get_by_test_id("partner-form-error")).to_have_text("Fix 1 field to continue."))
    form.get_by_label("Password", exact=True).fill("a long enough password")
    form.get_by_role("button", name="Create account and continue").click()
    # Round 8 (D5): the account is made once the emailed code is entered (@example.com: the fixed code here).
    check("/partner: a code goes to the email first; no account yet", lambda: (
        expect(k.get_by_test_id("partner-code")).to_be_visible(timeout=20000),
        expect(k.get_by_test_id("partner-code")).to_contain_text(email)))
    k.get_by_label("6-digit code").fill(OTP)
    k.get_by_test_id("partner-verify").click()
    check("/partner: submitting creates a kitchen partner and continues to business details", lambda: (
        expect(k.get_by_test_id("partner-application")).to_have_attribute("data-current", "business", timeout=20000),
        expect(k.get_by_text(f"We've emailed {email}")).to_be_visible(),
        _assert(api("GET", "/restaurants/mine", login(email, "a long enough password"))[0]["status"] == "pending_approval", "no kitchen")))
    step_form = k.get_by_test_id("step-business")
    for label, value in (("Street address", "Plot 9, Road 12"), ("Area or neighbourhood", "Madhapur"), ("Postal code", "500081"), ("Cuisines", "Kerala, Thali")):
        step_form.get_by_label(label, exact=True).fill(value)
    step_form.get_by_role("button", name="Save and continue").click()
    check("/partner: business details saved, the licence step is next", lambda: expect(k.get_by_test_id("partner-application")).to_have_attribute("data-current", "fssai", timeout=20000))
    k.reload(wait_until="networkidle")
    check("/partner: save and continue later (signed in, back where they left off)", lambda: (
        expect(k.get_by_test_id("partner-application")).to_have_attribute("data-current", "fssai", timeout=20000),
        expect(k.get_by_test_id("partner-saved")).to_contain_text(email)))
    shot(k, "21-partner-application")
    page.goto(base + "/partner", wait_until="networkidle")
    check("/partner as a customer: apply with this account (it has orders, so the API says no)", lambda: expect(page.get_by_test_id("partner-customer")).to_be_visible())
    kp = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    kp.goto(base + "/partner", wait_until="networkidle")
    check("phone width /partner: no sideways scroll", lambda: no_sideways_scroll(kp))
    check("phone width /partner: only the type scale's font sizes", lambda: type_scale_only(kp))

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
        expect(anon_phone.get_by_test_id("location-line")).to_have_text("Set your delivery location")
        anon_phone.get_by_test_id("language-pill").click()
        menu = anon_phone.get_by_role("menu", name="Language")
        expect(menu).to_be_visible()
        expect(anon_phone.get_by_role("dialog")).to_have_count(0)  # a dropdown anchored to the pill, not a sheet
        box = menu.bounding_box()
        _assert(box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["height"] < 600, box)
        anon_phone.keyboard.press("Escape")
    check("phone width: the same language pill (a small dropdown) and the location line", phone_pill_and_line)

    # The IP's guess counts only inside a live zone, and then names that live city: "Boise, ID · Change" and
    # that city's kitchens and example bill. A guess outside every live zone (Nampa, next to Boise) shows
    # nothing guessed: only "Set your delivery location". Never the country's first live city.
    def ip_visit(hint: dict, source: str, width: int = 1440):  # type: ignore[no-untyped-def]
        c = b.new_context(viewport={"width": width, "height": 900})
        fake_hint(c, hint)
        pg = c.new_page()
        pg.goto(base, wait_until="networkidle")
        if source == "ip":
            expect(pg.get_by_test_id("location-line")).to_have_attribute("data-source", "ip", timeout=15000)  # after the hint's refresh
        else:  # the hint is read (its country decides the currency, and may refresh the page) but names no place
            pg.wait_for_timeout(2500)
            pg.wait_for_load_state("networkidle")
        return c, pg

    boise_ip = {"country": "US", "place": "Meridian", "region": "Idaho", "region_code": "ID",
                "city_code": "US-ID-BOI", "city_name": "Boise", "city_path": "/us/boise", "served": True}
    nampa_ip = {"country": "US", "place": "Nampa", "region": "Idaho", "region_code": "ID", "served": False}
    c_in, pg_in = ip_visit(boise_ip, "ip")
    check("IP guess inside a live zone: Boise, ID · Change (one action); Boise's bill in dollars", lambda: (
        expect(pg_in.get_by_test_id("location-line")).to_have_text("Boise, ID · Change"),
        expect(pg_in.get_by_test_id("change-city")).to_have_attribute("href", "/cities?choose=1"),
        expect(pg_in.get_by_test_id("who-gets")).to_have_attribute("data-city", "US-ID-BOI"),
        expect(pg_in.get_by_test_id("who-gets")).to_contain_text("$")))
    pg_in.screenshot(path=f"{OUT}/23-location-known-desktop.png", full_page=False)
    c_in.close()
    c_in_phone, pg_in_phone = ip_visit(boise_ip, "ip", width=390)
    check("phone: Boise, ID · Change", lambda: expect(pg_in_phone.get_by_test_id("location-line")).to_have_text("Boise, ID · Change"))
    pg_in_phone.screenshot(path=f"{OUT}/23-location-known-phone.png", full_page=False)
    c_in_phone.close()
    c_nampa, pg_nampa = ip_visit(nampa_ip, "none", width=390)
    check("IP guess outside every zone (Nampa): nothing guessed, only Set your delivery location", lambda: (
        expect(pg_nampa.get_by_test_id("location-line")).to_have_text("Set your delivery location", timeout=15000),
        expect(pg_nampa.get_by_test_id("location-line")).to_have_attribute("data-source", "none"),
        expect(pg_nampa.get_by_test_id("location-line")).not_to_contain_text("Nampa")))  # (Nampa may be listed as coming soon below)
    pg_nampa.screenshot(path=f"{OUT}/23-location-unknown-phone.png", full_page=False)
    c_nampa.close()
    c_out, pg_out = ip_visit({"country": "US", "place": "Challis", "region": "Idaho", "region_code": "ID", "served": False}, "none")
    check("IP place we don't serve (Challis): only Set your delivery location; no other city's kitchens or bill", lambda: (
        expect(pg_out.get_by_test_id("location-line")).to_have_text("Set your delivery location", timeout=15000),
        expect(pg_out.get_by_test_id("who-gets")).to_have_count(0),
        expect(pg_out.get_by_role("heading", name="What's cooking near you")).to_have_count(0),
        expect(pg_out.get_by_test_id("landing-hero")).to_have_attribute("src", re.compile(
            "/food/" + re.escape(hero_of["US"]) + r"-\d+\.webp$"))))  # the IP's country's hero and currency
    pg_out.screenshot(path=f"{OUT}/23-location-unknown-desktop.png", full_page=False)
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
        us_dialog.get_by_role("button", name=re.compile("^Add to cart")).click()
    us.get_by_role("complementary", name="Your cart").get_by_role("button", name="One more Teriyaki Chicken Bowl").click()
    us.get_by_role("complementary", name="Your cart").get_by_role("link", name="Go to checkout").click()
    url_is(us, r"/signin\?")
    # R22: the code screen shows the number in its country's format ("+1 (208) 555-0101").
    us.get_by_label("Country code").select_option("US")
    us.get_by_role("textbox", name="Mobile number").fill(US_PHONE)
    us.get_by_role("button", name="Send code").click()
    url_is(us, r"/signin/code\?")
    check("sign in (US): the code was sent to +1 (208) 555-0101", lambda:
          expect(us.get_by_text("+1 (208) 555-0101", exact=True)).to_be_visible(timeout=15000))
    shot(us, "20a-us-code")
    us.get_by_role("textbox", name="Digit 1").fill(OTP)
    us.get_by_role("button", name="Verify and continue").click()
    url_is(us, r"/checkout$")
    us_bill = us.get_by_role("complementary", name="Your order")
    check("US checkout: the fair bill in dollars with sales tax", lambda: (
        expect(us_bill.get_by_text("The fair bill")).to_be_visible(timeout=20000),
        expect(us_bill.get_by_role("row", name=re.compile("sales tax"))).not_to_have_count(0),  # R38: its payee reads "Government"
        expect(us_bill.get_by_text(re.compile(r"^\$\d+\.\d{2}$")).first).to_be_visible(),
        expect(us_bill.get_by_text("₹")).to_have_count(0)))
    shot(us, "20-us-checkout")
    # R22: the account shows the number formatted (the side card and Sign-in and security).
    us.goto(base + "/account/profile", wait_until="networkidle")
    check("account (US): the phone reads +1 (208) 555-0101, never the raw E.164", lambda: (
        expect(us.get_by_text("+1 (208) 555-0101", exact=True).first).to_be_visible(timeout=15000),
        expect(us.get_by_text("+12085550101")).to_have_count(0)))
    shot(us, "20b-us-account-phone")

    # ── Terms and Privacy (R8 F10): per country, published in the admin console ──
    lp = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
    lp.goto(f"{base}/terms?country=IN", wait_until="networkidle")
    check("terms: India's document, key points first, contents from its headings, version and history", lambda: (
        expect(lp.get_by_role("heading", level=1)).to_have_text("Terms of use"),
        _assert(lp.get_by_test_id("legal-key-points").get_by_role("listitem").count() >= 3, "key points"),
        _assert(lp.get_by_test_id("legal-toc").get_by_role("link").count() >= 10, "table of contents"),
        expect(lp.get_by_test_id("legal-meta")).to_contain_text(re.compile(r"Last updated .+Version \d+")),
        expect(lp.get_by_test_id("legal-meta").get_by_role("link", name="Version history")).to_be_visible(),
        expect(lp.get_by_role("button", name="Print / Save as PDF")).to_be_visible()))
    check("legal pages outside production say Draft: pending legal review", lambda:
          expect(lp.get_by_test_id("legal-draft-banner")).to_have_text("Draft: pending legal review"))
    def toc_jumps() -> None:
        link = lp.get_by_test_id("legal-toc").get_by_role("link", name=re.compile("Cancellations and refunds"))
        link.click()
        url_is(lp, r"#cancellations-and-refunds$")
        expect(lp.get_by_role("heading", name=re.compile("Cancellations and refunds"), level=2)).to_be_in_viewport()
    check("terms: a contents link goes to its section", toc_jumps)
    shot(lp, "22-terms-in")
    a11y(lp, "terms")
    lp.goto(f"{base}/privacy?country=IN", wait_until="networkidle")
    check("privacy (India): the Grievance Officer, data principal rights, nomination", lambda: (
        expect(lp.get_by_role("heading", name=re.compile("Grievance Officer"), level=2)).to_be_visible(),
        expect(lp.get_by_text(re.compile("Nominate"))).not_to_have_count(0)))
    a11y(lp, "privacy")
    lp.goto(f"{base}/privacy?country=US", wait_until="networkidle")
    check("privacy (US): state privacy rights and Do Not Sell or Share", lambda: (
        expect(lp.get_by_role("heading", name="Do Not Sell or Share My Personal Information")).to_be_visible(),
        expect(lp.get_by_test_id("legal-countries").get_by_role("link", name="India", exact=True)).to_be_visible()))
    lp.goto(f"{base}/terms/history?country=US", wait_until="networkidle")
    check("terms: version history with the current version", lambda: (
        expect(lp.get_by_test_id("legal-history").get_by_text("Current version")).to_be_visible()))
    lp.goto(f"{base}/terms?country=GB", wait_until="networkidle")
    check("terms: a country without documents says they're being prepared", lambda: (
        expect(lp.get_by_test_id("legal-unavailable")).to_contain_text("we're preparing our Terms of use"),
        expect(lp.get_by_test_id("legal-draft-banner")).to_be_visible(),
        expect(lp.get_by_role("link", name="India", exact=True).first).to_be_visible()))
    lp.set_viewport_size({"width": 390, "height": 844})
    lp.goto(f"{base}/privacy?country=IN", wait_until="networkidle")
    def phone_contents() -> None:
        no_sideways_scroll(lp)
        expect(lp.get_by_test_id("legal-toc")).to_be_hidden()
        lp.get_by_test_id("legal-toc-mobile").locator("summary").click()
        expect(lp.get_by_test_id("legal-toc-mobile").get_by_role("link", name=re.compile("Your rights"))).to_be_visible()
    check("privacy at 390: contents fold open, no sideways scroll", phone_contents)
    lp.screenshot(path=f"{OUT}/23-privacy-in-phone.png", full_page=False)

    # Publishing a new version: a signed-in customer is told once (here the US privacy notice).
    def updated_notice() -> None:
        cm = login("cm.us@example.com", "BhojanGoAdmin1")
        d = api("POST", "/admin/legal/documents", cm, {"kind": "privacy", "country": "US", "language": "en",
                                                        "summary_of_changes": f"e2e {RUN}"})["document"]
        api("POST", f"/admin/legal/documents/{d['id']}/publish", cm)
        us.goto(base, wait_until="networkidle")
        notice = us.get_by_test_id("legal-updated-notice")
        expect(notice).to_contain_text("Privacy notice", timeout=15000)
        notice.get_by_role("button", name="Got it").click()
        expect(notice).to_have_count(0)
        us.reload(wait_until="networkidle")
        us.wait_for_timeout(1500)
        expect(us.get_by_test_id("legal-updated-notice")).to_have_count(0)
    check("updated privacy notice: shown once to a signed-in customer, gone after Got it", updated_notice)

    # ── Deliver with BhojanGo (/deliver, R8 F8): real pay for each seed city ───
    symbols = {"INR": "₹", "USD": "$"}  # the test may know the seed's currencies

    def whole(v: str) -> str:  # R12: one money format, always two decimals (under 1,000 here: no grouping)
        return f"{float(v):.2f}"

    dl = b.new_context(viewport={"width": 1366, "height": 900}).new_page()
    for code in ("IN-TG-HYD", "US-ID-BOI"):
        terms = api("GET", f"/delivery/terms?city={code}")

        def deliver_page(code: str = code, terms: dict = terms) -> None:
            dl.goto(f"{base}/deliver?city={code}", wait_until="networkidle")
            sym = symbols[terms["currency"]]
            expect(dl.get_by_role("heading", level=1)).to_have_text("Deliver from local restaurants, on your own hours")
            expect(dl.get_by_test_id("pay-cards")).to_have_attribute("data-city", code)
            expect(dl.get_by_test_id("pay-trip")).to_contain_text(f"{sym}{whole(terms['example']['total'])}")
            expect(dl.get_by_test_id("pay-trip")).to_contain_text(f"{sym}{whole(terms['example']['base'])}")
            # R30: a trip pays its delivery fee + the tip; no hourly floor in the seed (the card shows only where a city has one)
            _assert(terms["hourly_floor"] is None and terms["example"]["per_wait_minute"] in ("0", "0.00", 0), terms)
            expect(dl.get_by_test_id("pay-floor")).to_have_count(0)
            expect(dl.get_by_test_id("pay-tips")).to_contain_text("100%")
            expect(dl.get_by_test_id("pay-weekly")).to_contain_text("Monday")
            expect(dl.get_by_test_id("requirements")).to_have_attribute("data-country", terms["country"])
            for d in terms["requirements"]["papers"]:
                expect(dl.get_by_test_id("requirements").locator(f'[data-key="{d["key"]}"]')).to_have_count(1)
            expect(dl.get_by_test_id("no-fee")).to_be_visible()
            other = "$" if sym == "₹" else "₹"
            _assert(other not in dl.get_by_test_id("pay-cards").inner_text(), "the other country's money on the page")
        check(f"/deliver?city={code}: the city's real pay and its country's requirements", deliver_page)
        shot(dl, f"30-deliver-{code.lower()}")
        a11y(dl, f"deliver-{code.lower()}")

    def deliver_phone() -> None:
        m390 = b.new_context(viewport={"width": 390, "height": 844}).new_page()
        m390.goto(base + "/deliver", wait_until="networkidle")
        no_sideways_scroll(m390)
        expect(m390.get_by_test_id("pay-trip")).to_be_visible()
        m390.screenshot(path=f"{OUT}/31-deliver-phone.png", full_page=True)
    check("phone width /deliver: no sideways scroll", deliver_phone)

    if not QA_WEB:  # signing up writes an account: local only (tests never write to QA)
        def deliver_sign_up() -> None:
            dl.goto(f"{base}/deliver?city=IN-TG-HYD#get-started", wait_until="networkidle")
            form = dl.get_by_test_id("gs-form")
            form.get_by_label("Your full name").fill("Kiran Rao")
            # R9: the vehicles are India's (Markets) and the minimum age is checked as you type.
            rules = api("GET", "/delivery/sign-up?country=IN")
            vehicles = form.get_by_test_id("gs-vehicles").get_by_role("radio")
            expect(vehicles).to_have_count(len(rules["vehicles"]))
            _assert("car" not in rules["vehicles"] and form.get_by_test_id("gs-vehicle-car").count() == 0, "a car offered in India")
            y = int(rules["today"][:4])
            dob = form.get_by_label("Date of birth")
            dob.fill(f"{y - rules['min_age'] + 1:04d}-01-01")  # a year short of the minimum
            dob.blur()
            expect(form.get_by_test_id("gs-dob-error")).to_contain_text(f"{rules['min_age']} or older")
            dob.fill("1995-06-15")
            expect(form.get_by_test_id("gs-dob-error")).to_have_count(0)
            form.get_by_text("Motorcycle", exact=True).click()
            expect(form.get_by_test_id("gs-vehicle-motorcycle")).to_be_checked()
            form.get_by_label("Country code").select_option("IN")
            form.get_by_label("Mobile number").fill(f"90000{random.randint(10000, 99999)}")
            form.get_by_label("City you'll deliver in").select_option("IN-TG-HYD")
            form.get_by_role("button", name="Send code").click()
            dl.get_by_label("6-digit code").fill(OTP)
            dl.get_by_role("button", name="Verify and sign up").click()
            done = dl.get_by_test_id("gs-done")
            expect(done).to_contain_text("You're signed up, Kiran", timeout=20000)
            expect(done.get_by_test_id("gs-qr")).to_have_attribute("data-url", re.compile(r"/deliver/app\?country=IN$"))
            shot(dl, "32-deliver-signed-up")
            done.get_by_test_id("gs-app-link").click()
            url_is(dl, r"/deliver/app\?country=IN")
            expect(dl.get_by_test_id("app-not-yet")).to_contain_text("isn't in Google Play or the App Store yet")
        check("/deliver: get started with a new phone -> a delivery partner account -> the app's QR code", deliver_sign_up)

    # ── Help centre (F9): articles from the console, search, an article, a vote, contact ──
    help_ctx = b.new_context(viewport={"width": 1366, "height": 900})
    hp = help_ctx.new_page()
    hp.goto(base + "/help", wait_until="networkidle")
    check("help: search at the top, six topics with counts, popular articles", lambda: (
        expect(hp.get_by_role("heading", name="How can we help?", level=1)).to_be_visible(),
        expect(hp.get_by_role("searchbox", name="Search help articles")).to_be_visible(),
        expect(hp.locator("[data-testid^=topic-]")).to_have_count(6),
        expect(hp.get_by_test_id("topic-orders")).to_contain_text(re.compile(r"\d+ articles?")),
        expect(hp.get_by_role("heading", name="Popular articles")).to_be_visible()))
    shot(hp, "21-help")
    a11y(hp, "help")
    hp.get_by_role("searchbox", name="Search help articles").fill("zzqqxx nothing")
    check("help: no results says so, with suggestions and contact", lambda: (
        expect(hp.get_by_test_id("help-results")).to_contain_text("No articles match", timeout=10000),
        expect(hp.get_by_test_id("help-results").get_by_role("link", name="Contact us")).to_be_visible()))
    hp.get_by_role("searchbox", name="Search help articles").fill("delivery PIN")
    pin_link = hp.get_by_test_id("help-results").get_by_role("link", name=re.compile("delivery PIN", re.I)).first
    check("help: search finds an article as you type", lambda: expect(pin_link).to_be_visible(timeout=10000))
    pin_link.click()
    url_is(hp, r"/help/delivery/delivery-pin$")
    article = hp.get_by_test_id("help-article")
    check("help: the article with breadcrumbs, its text and related articles", lambda: (
        expect(hp.get_by_role("navigation", name="Breadcrumb").get_by_role("link", name="Help centre")).to_be_visible(),
        expect(article.get_by_role("heading", level=1)).to_contain_text("PIN"),
        expect(article.get_by_text("4-digit").first).to_be_visible(),
        expect(hp.get_by_role("heading", name="Related articles")).to_be_visible()))
    shot(hp, "22-help-article")
    a11y(hp, "help-article")
    hp.get_by_test_id("helpful").get_by_role("button", name="No").click()
    check("help: 'No' thanks you and offers contact", lambda: (
        expect(hp.get_by_test_id("helpful")).to_contain_text("Sorry this didn't answer"),
        expect(hp.get_by_test_id("helpful").get_by_role("link", name="Contact us")).to_be_visible()))
    form = hp.get_by_test_id("contact-form")
    form.get_by_label("Your name").fill("E2E Visitor")
    form.get_by_label("Email").fill("e2e.visitor@example.com")
    form.get_by_label("How can we help?").fill("Testing the help contact form end to end.")
    form.get_by_role("button", name="Send message").click()
    check("help: the contact form (signed out) sends a ticket and says what's next", lambda:
          expect(hp.get_by_test_id("contact-sent")).to_contain_text("e2e.visitor@example.com", timeout=10000))
    hp.goto(base + "/help/a/how-refunds-work", wait_until="networkidle")
    check("help: a short link goes to the article under its topic", lambda: url_is(hp, r"/help/payments-refunds/how-refunds-work$"))
    hp.goto(base + "/help/orders", wait_until="networkidle")
    check("help: a topic page lists its articles", lambda: (
        expect(hp.get_by_role("heading", name="Orders", level=1)).to_be_visible(),
        expect(hp.get_by_role("link", name=re.compile("Cancel", re.I)).first).to_be_visible()))
    check("help: an unknown article is a 404", lambda: _assert(hp.request.get(f"{base}/help/orders/no-such-article").status == 404, "not 404"))
    hpm = b.new_context(viewport={"width": 390, "height": 844}).new_page()
    for path in ("/help", "/help/orders", "/help/delivery/delivery-pin"):
        hpm.goto(base + path, wait_until="networkidle")
        check(f"phone width {path}: no sideways scroll", lambda: no_sideways_scroll(hpm))
        check(f"phone width {path}: only the type scale's font sizes", lambda: type_scale_only(hpm))
    help_ctx.close()

    # ── R36: compact lists, menu add buttons, pickup only, closed, dish search, restaurant minimum, no overflow ──
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    import urllib.parse as _up

    def place(ctx, label: str, lat: float, lng: float, country: str, city: str, path: str, zone: str) -> None:  # type: ignore[no-untyped-def]
        """The delivery address cookie the website reads (bg_addr), as the address box writes it."""
        ctx.add_cookies([{"name": "bg_addr", "url": base, "value": _up.quote(json.dumps({
            "label": label, "lat": lat, "lng": lng, "country": country, "city_code": city, "city_path": path, "zone": zone, "served": True}))}])

    NORTH_END = ("North End, Boise", 43.6400, -116.2100, "US", "US-ID-BOI", "/us/boise", "North End")
    OLD_CITY = ("Old City, Hyderabad", 17.3620, 78.4750, "IN", "IN-TG-HYD", "/in/hyderabad", "Old City")

    def list_group(k: dict) -> int:
        if k["open_now"] and k["deliverable"]:
            return 0
        if k["open_now"] and k.get("pickup_only"):
            return 1
        return 2 if (k["deliverable"] or k.get("pickup_only")) else 3

    def cards_are_compact_and_whole(pg) -> None:  # type: ignore[no-untyped-def]
        cards = pg.locator("[data-testid^='kitchen-card-']")
        _assert(cards.count() > 0, "no cards")
        for i in range(cards.count()):
            card = cards.nth(i)
            box = card.get_by_test_id("card-photo").bounding_box()
            _assert(2.2 <= box["width"] / box["height"] <= 2.6, ("photo ratio", box))
            name = card.get_by_test_id("card-name")
            # the whole name: up to two lines, nothing clipped (an ellipsis would mean scrollHeight > clientHeight)
            _assert(name.evaluate("e => e.scrollHeight <= e.clientHeight + 1 && e.scrollWidth <= e.clientWidth + 1"),
                    ("name cut off", name.inner_text()))

    r36 = b.new_context(viewport={"width": 1440, "height": 900})
    fake_hint(r36, {})
    place(r36, *NORTH_END)
    rp = r36.new_page()
    near = api("GET", f"/discover?lat={NORTH_END[1]}&lng={NORTH_END[2]}")
    for width in (1440, 1280):
        rp.set_viewport_size({"width": width, "height": 900})
        rp.goto(f"{base}/us/boise", wait_until="networkidle")
        check(f"R36 {width} px: compact cards (2.4:1 photo), names never cut off", lambda: cards_are_compact_and_whole(rp))
    shot(rp, "r36-boise-list-1280")
    check("R36 list order: open and deliverable, then pickup only, then closed (the API's order on the page)", lambda: (
        _assert([list_group(k) for k in near["restaurants"]] == sorted(list_group(k) for k in near["restaurants"]), near["restaurants"]),
        _assert([e.get_attribute("data-testid") for e in rp.locator("[data-testid^='kitchen-card-']").all()]
                == [f"kitchen-card-{k['slug']}" for k in near["restaurants"]], "page order differs from the API's")))
    rp.goto(base, wait_until="networkidle")
    check("R36 Free delivery filter only when a restaurant here funds free delivery", lambda: expect(
        rp.get_by_role("group", name="Filter restaurants").get_by_role("button", name="Free delivery")).to_have_count(1 if near.get("free_delivery_chip") else 0))

    # Menu: rating · distance · time, the Delivery / Pickup switch, "+" on the dish photo's corner, then "− 1 +"
    def add_on_photo() -> None:
        rp.goto(base + US_KITCHEN_PATH, wait_until="networkidle")
        expect(rp.get_by_test_id("kitchen-meta")).to_contain_text(re.compile(r"min$"))
        expect(rp.get_by_test_id("how-pickup")).to_have_text(re.compile(r"^Pickup · \d+% fee$"))
        expect(rp.get_by_test_id("how-delivery")).to_have_text(re.compile(r"delivery$"))
        row = rp.locator("div.flex.gap-4").filter(has=rp.locator("img")).first
        plus = row.get_by_role("button", name=re.compile(r"^Add "))
        img = row.locator("img").first.bounding_box()
        btn = plus.bounding_box()
        _assert(btn["x"] + btn["width"] / 2 > img["x"] + img["width"] / 2 and btn["y"] + btn["height"] / 2 > img["y"] + img["height"] / 2,
                ("the + is not on the photo's bottom-right", img, btn))
        plus.click()
        if rp.get_by_role("dialog").count():
            rp.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
        expect(row.get_by_test_id("dish-stepper")).to_contain_text("1")
    check("R36 menu: rating · distance · time; Delivery / Pickup; + on the photo's corner becomes − 1 +", add_on_photo)
    shot(rp, "r36-menu-add-on-photo")

    # Closed: a banner and no adds, the menu still readable (Basque Corner Kitchen closed today, then opened again)
    partner_boi = login("partner.boi@example.com")
    basque = next(k for k in near["restaurants"] if k["slug"].startswith("basque-corner-kitchen"))
    boise_today = (_dt.now(_tz.utc) - _td(hours=7)).date()  # Boise's day (MST; an hour off can't matter: today and tomorrow)
    for d in (boise_today, boise_today + _td(days=1)):
        api("PUT", f"/restaurants/{basque['id']}/hours/overrides/{d}", partner_boi, {"closed": True, "note": "R36 test"})

    def closed_menu() -> None:
        rp.goto(base + basque["path"], wait_until="networkidle")
        expect(rp.get_by_test_id("kitchen-closed")).to_contain_text("Closed")
        adds = rp.get_by_role("button", name=re.compile(r"^Add "))
        _assert(adds.count() > 0, "no dishes to browse")
        for i in range(adds.count()):
            expect(adds.nth(i)).to_be_disabled()
    check("R36 closed: 'Closed · opens …' banner, adds disabled, the menu still there to browse", closed_menu)
    shot(rp, "r36-menu-closed")
    def closed_card() -> None:  # the website keeps a city's list for up to 30 s (its fetch cache)
        rp.goto(f"{base}/us/boise", wait_until="networkidle")
        expect(rp.get_by_test_id(f"kitchen-card-{basque['slug']}").get_by_test_id("card-status")).to_contain_text("Closed", timeout=3000)
    check("R36 closed: the card says Closed, after the open ones", lambda: eventually(closed_card, 45))
    for d in (boise_today, boise_today + _td(days=1)):
        api("PUT", f"/restaurants/{basque['id']}/hours/overrides/{d}", partner_boi, {"closed": False, "opens": "00:00", "closes": "00:00", "note": "E2E"})

    # Dish search: "curry" in Boise finds the dishes of every restaurant that has one (from their own menus)
    def curry_search() -> None:
        expected = set()
        for k in near["restaurants"]:
            m = api("GET", f"/restaurants/{k['id']}/menu")
            for item in [i for c in m["categories"] for i in c["items"]] + m.get("uncategorized_items", []):
                if "curry" in item["name"].lower() and item.get("is_available", True):
                    expected.add((k["name"], item["name"]))
        rp.goto(f"{base}/us/boise?q=curry", wait_until="networkidle")
        expect(rp.get_by_role("navigation", name="Cuisines")).to_have_count(0)  # no cuisine chips while searching
        hits = rp.get_by_test_id("dish-hit")
        shown = {(h.get_by_test_id("dish-hit-restaurant").inner_text(), h.locator("b").first.inner_text()) for h in hits.all()}
        _assert(shown == expected, (sorted(shown), sorted(expected)))
        if expected:
            expect(rp.get_by_test_id("search-dishes")).to_have_text("Dishes")
    check("R36 search 'curry' (Boise): restaurants, then the dishes of every restaurant that has curry", curry_search)
    shot(rp, "r36-search-curry")
    r36.close()

    # Pickup only: Old City is too far for Spice Route Kitchen to deliver, and it takes pickup
    po = b.new_context(viewport={"width": 1440, "height": 900})
    fake_hint(po, {})
    place(po, *OLD_CITY)
    pp = po.new_page()

    def pickup_only() -> None:
        pp.goto(f"{base}/in/hyderabad", wait_until="networkidle")
        expect(pp.get_by_test_id("kitchen-card-spice-route-kitchen-madhapur").get_by_test_id("pickup-only")).to_have_text("Pickup only")
        pp.goto(base + KITCHEN_PATH, wait_until="networkidle")
        expect(pp.get_by_test_id("kitchen-banner-pickup")).to_have_text("Too far to deliver · Pickup available")
        expect(pp.get_by_test_id("how-delivery")).to_be_disabled()
        expect(pp.get_by_test_id("how-pickup")).to_have_attribute("aria-checked", "true")
        expect(pp.get_by_role("button", name=re.compile(r"^Add ")).first).to_be_enabled()
    check("R36 pickup only: 'Pickup only' card; menu banner, switch locked to Pickup, adds on", pickup_only)
    shot(pp, "r36-menu-pickup-only")
    po.close()

    # The cart under Boise Bowl Co.'s own $15 minimum: the whole bill, "Add $0.50 more …", a progress bar, Pay off
    mc = b.new_context(viewport={"width": 1440, "height": 900})
    fake_hint(mc, {})
    place(mc, *NORTH_END)
    mp = mc.new_page()
    mp.goto(base + "/signin", wait_until="networkidle")
    sign_in(mp, "2085550101", "US")
    mp.wait_for_url(lambda u: "/signin" not in u, timeout=30000)

    def under_minimum() -> None:
        mp.evaluate("localStorage.removeItem('bhojango-bag')")
        mp.goto(base + US_KITCHEN_PATH, wait_until="networkidle")
        mp.get_by_role("button", name="Add Teriyaki Chicken Bowl").click()  # $14.50
        if mp.get_by_role("dialog").count():
            mp.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
        mp.goto(f"{base}/checkout", wait_until="networkidle")
        expect(mp.get_by_test_id("minimum-note").first).to_have_text("Add $0.50 more to order from Boise Bowl Co.", timeout=20000)
        expect(mp.get_by_role("progressbar").first).to_have_attribute("aria-valuenow", "97")
        expect(mp.get_by_role("complementary", name="Your order").get_by_text("Food")).to_be_visible()
        expect(mp.get_by_role("button", name=re.compile(r"^Pay ")).first).to_be_disabled()
    check("R36 cart under the restaurant's minimum: the whole bill, Add $0.50 more, progress, Pay off", under_minimum)
    shot(mp, "r36-cart-under-minimum")
    mc.close()

    # No sideways scroll on a phone, at 360, 390 and 414 px (the page is never wider than the screen)
    for width in (360, 390, 414):
        ph = b.new_context(viewport={"width": width, "height": 800})
        fake_hint(ph, {})
        place(ph, *OLD_CITY)
        pg = ph.new_page()
        for path in ("/", "/in/hyderabad", "/in/hyderabad?q=biryani", KITCHEN_PATH, "/us/boise?q=curry", "/checkout", "/cities", "/help"):
            pg.goto(base + path, wait_until="networkidle")
            check(f"R36 {width} px {path}: page no wider than the screen", lambda pg=pg, width=width: no_sideways_scroll_at(pg, width))
        ph.close()

    # ── R37: offers BhojanGo pays for are off in the seed: no home screen shows one ──
    nh = b.new_context(viewport={"width": 1440, "height": 900})
    fake_hint(nh, {})
    place(nh, "Madhapur, Hyderabad", 17.4483, 78.3915, "IN", "IN-TG-HYD", "/in/hyderabad", "Madhapur")
    hp = nh.new_page()
    for lat, lng, where in ((17.4483, 78.3915, "Madhapur"), (43.6150, -116.2023, "Downtown Boise")):
        d = api("GET", f"/discover?lat={lat}&lng={lng}")
        check(f"R37 {where}: no BhojanGo-funded offer on the home screen (off in the seed)", lambda d=d: (
            _assert(all(o["funded_by"] == "restaurant" for o in d["offers"]), d["offers"]),
            _assert(all(k["offer"] is None or k["offer"]["funded_by"] == "restaurant" for k in d["restaurants"]), "a card shows one")))
    hp.goto(base, wait_until="networkidle")
    check("R37 Hyderabad home: the launch offer BhojanGo pays for isn't shown", lambda: (
        expect(hp.get_by_role("link", name=re.compile(KITCHEN)).first).to_be_visible(timeout=20000),
        expect(hp.get_by_text(re.compile(r"10% off, up to"))).to_have_count(0)))
    shot(hp, "r37-home-no-bhojango-offer")
    nh.close()

    # ── R38: the bill in two columns, phone numbers by country, "GST on fees"; a US (Boise) and an India
    # (Hyderabad) customer, at 1440 px (desktop), 390 px and 360 px (phones) ──
    MADHAPUR = ("Madhapur, Hyderabad", 17.4483, 78.3915, "IN", "IN-TG-HYD", "/in/hyderabad", "Madhapur")
    R38 = {"us": (NORTH_END, "2085550105", "US", US_KITCHEN_PATH, "Teriyaki Chicken Bowl", "+1", "(208) 555-0123", "+1 (208) 555-0123"),
           "in": (MADHAPUR, "9000000102", "IN", KITCHEN_PATH, "Veg Dum Biryani", "+91", "98765 43210", "+91 98765 43210")}
    WHO = {"Restaurant", "100% to your delivery partner", "BhojanGo", "Government", "Restaurant pays", "BhojanGo pays"}

    def two_column_bill(pg, width: int, market: str) -> None:  # type: ignore[no-untyped-def]
        lines = pg.locator("[data-testid='bill-line']:visible")
        expect(lines.first).to_be_visible(timeout=20000)
        _assert(lines.count() >= 4, f"{lines.count()} bill lines")
        for i in range(lines.count()):
            row = lines.nth(i)
            _assert(row.locator("td").count() == 2, ("not two columns", row.inner_text()))
            who = row.get_by_test_id("bill-payee").inner_text().strip()
            _assert(who in WHO, ("who gets it", who))
            amount = row.get_by_test_id("bill-amount")
            box = amount.bounding_box()
            # the amount's text sits on one line (its line boxes share one top), and nothing is cut off
            fits = amount.evaluate("e => { const r = document.createRange(); r.selectNodeContents(e);"
                                   " const tops = new Set([...r.getClientRects()].map((x) => Math.round(x.top)));"
                                   " return tops.size === 1 && e.scrollWidth <= e.clientWidth + 1 }")
            _assert(fits and box["x"] + box["width"] <= width + 0.5, ("an amount wraps or is cut off", amount.inner_text(), box))
        text = pg.locator("body").inner_text()
        if market == "in":
            _assert("GST on fees" in text and "GST on platform fees" not in text, "the GST line on fees")
        _assert("the fair bill" in text.lower(), "the section title")  # styled in capitals, written "The fair bill"
        no_sideways_scroll_at(pg, width)

    for market, (where, phone, country, path, dish, code, placeholder, example) in R38.items():
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        fake_hint(ctx, {})
        place(ctx, *where)
        pg = ctx.new_page()

        # Item 2: the sign-in phone box follows the address's country; an invalid number is refused in words
        for width in (1440, 390):
            pg.set_viewport_size({"width": width, "height": 900})
            pg.goto(f"{base}/signin", wait_until="networkidle")
            box = pg.get_by_role("textbox", name="Mobile number")

            def phone_box() -> None:
                expect(box).to_have_attribute("placeholder", placeholder)
                expect(pg.get_by_test_id("phone-example")).to_have_text(f"For example {example}")
                # what the form shows (the country list's options aside: it names every country's code)
                body = pg.locator("form").filter(has=box).evaluate(
                    "f => { const c = f.cloneNode(true); c.querySelectorAll('select,option').forEach(e => e.remove()); return c.textContent }")
                _assert(code in body, f"{code} not shown")
                _assert(("+91" not in body) if market == "us" else ("+1 (" not in body and "+1\n" not in body), f"the other country's code: {body[:300]}")
                box.fill("12345 678")
                pg.get_by_role("button", name="Send code").click()
                expect(pg.locator("form").filter(has=box).get_by_role("alert")).to_have_text(f"Enter a valid phone number, like {example}")
            check(f"R38 phone {market} {width} px: {code} by default, placeholder {placeholder}, invalid refused", phone_box)
            shot(pg, f"r38-2-web{width}-{market}")

        # Item 1 and 4: the bill at checkout, signed in, one dish in the cart
        pg.set_viewport_size({"width": 1440, "height": 900})
        # signed in for real (sign-in is limited per minute and this suite signs in often: wait and try again once)
        for attempt in range(2):
            pg.goto(f"{base}/signin", wait_until="networkidle")
            try:
                sign_in(pg, phone, country)
                expect(pg).not_to_have_url(re.compile(r"/signin"), timeout=20000)
                break
            except Exception:  # noqa: BLE001
                if attempt:
                    raise
                pg.wait_for_timeout(65000)
        pg.wait_for_load_state("networkidle")
        pg.evaluate("localStorage.removeItem('bhojango-bag')")
        pg.goto(base + path, wait_until="networkidle")
        check(f"R38 {market}: signed in, {dish} in the cart", lambda pg=pg, dish=dish: (
            expect(pg.get_by_role("button", name=f"Add {dish}").first).to_be_enabled(timeout=15000),
            pg.get_by_role("button", name=f"Add {dish}").first.click(),
            pg.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click() if pg.get_by_role("dialog").count() else None,
            expect(pg.get_by_role("link", name=re.compile(r"Cart · [1-9]"))).to_be_visible(timeout=15000)))
        shot(pg, f"r38-1-cart-{market}")
        for width in (1440, 390, 360):
            pg.set_viewport_size({"width": width, "height": 900})
            pg.goto(f"{base}/checkout", wait_until="networkidle")
            check(f"R38 bill {market} {width} px: two columns, who gets it under the label, amounts on one line",
                  lambda pg=pg, width=width, market=market: two_column_bill(pg, width, market))
            if width != 360:
                shot(pg, f"r38-1-web{width}-{market}")  # full page: the bill whatever the check found
        ctx.close()

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
    # R22 S9: each page has its own CSP nonce and no 'unsafe-inline' script; the pages above ran with it.
    csp1, csp2 = (page.request.get(base + KITCHEN_PATH).headers.get("content-security-policy") or "" for _ in range(2))
    check("CSP: a fresh nonce on every page and no inline script allowed", lambda: _assert(
        "'nonce-" in csp1 and "'strict-dynamic'" in csp1 and "unsafe-inline" not in csp1.split("script-src", 1)[1].split(";", 1)[0]
        and csp1 != csp2, csp1))
    page.goto(f"{base}/no-such-page", wait_until="networkidle")
    a11y(page, "404")
    old = page.request.get(f"{base}/orders", max_redirects=0)
    check("old /orders redirects to the account", lambda: _assert(
        old.status in (301, 308) and old.headers.get("location", "").endswith("/account/orders"), (old.status, old.headers)))
    b.close()

AXE.write(OUT)
failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
raise SystemExit(1 if failed else 0)
