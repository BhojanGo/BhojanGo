"""A third city with no code change (make web-third-city; tools/web/third_city.sh).

On a clean, seeded stack (compose project bhojango-3c):
  1. admin, in the console: Markets > United States > New city (Meridian, Idaho),
     draws one zone on the map, makes it live, sets service hours, opens the city;
  2. a partner opens a kitchen there through the APIs the partner app uses
     (register, apply, hours, five dishes, payout account), and the admin
     approves it in Partners > Applications;
  3. the website, from data alone: /cities lists Meridian live under Idaho, the
     city page shows the kitchen, the sitemap has both, the personal home for an
     address typed in the address box shows the kitchen, and its page has the menu.

Runs in mcr.microsoft.com/playwright/python on the project's network; the
browser uses localhost like a person's would (3000 web, 3001 admin, 8001
core_api, 8004 realtime are forwarded to the compose services, as in
tools/web/e2e_web.py). PASS/FAIL per check; exit 1 on any failure.
Screenshots go to /out (docs/screenshots/web-v2/third-city).
"""
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

from playwright.sync_api import expect, sync_playwright

OUT = os.environ.get("OUT", "/out")
WEB, ADMIN, CORE = "http://localhost:3000", "http://localhost:3001", "http://localhost:8001"
SITE = "https://bhojango.com"  # NEXT_PUBLIC_APP_URL in the local image: sitemap URLs
FORWARD = {3000: ("web", 3000), 3001: ("admin", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}

CITY, STATE, LAT, LNG = "Meridian", "Idaho", 43.6121, -116.3915
ZONE = "Meridian Downtown"
KITCHEN = "Treasure Valley Kitchen"
DISHES = [("Finger Steak Basket", "14.00", "Mains"), ("Huckleberry Salmon", "21.00", "Mains"),
          ("Basque Chorizo Sandwich", "13.50", "Mains"), ("Fry Sauce Fries", "6.00", "Sides"),
          ("Huckleberry Shake", "7.50", "Drinks")]
WAIT_S = 180  # the website caches Markets reads (Next revalidate 60 s, /discover 60 s in Redis)

# Tests never write to QA or production (tools/target_guard.py; at /guard in the Playwright image).
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402

ensure_safe_api("http://core-api:8001")

results: list[tuple[str, bool, str]] = []
state: dict = {}


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
            try:
                u = socket.create_connection(target, timeout=10)
                u.settimeout(None)
            except OSError:
                c.close()
                continue
            threading.Thread(target=pipe, args=(c, u), daemon=True).start()
            threading.Thread(target=pipe, args=(u, c), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()


def check(name: str, fn) -> bool:  # type: ignore[no-untyped-def]
    t0 = time.monotonic()
    try:
        fn()
        results.append((name, True, ""))
        print(f"PASS {name} ({time.monotonic() - t0:.0f} s)", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        msg = " ".join(str(e).split())[:900]
        results.append((name, False, msg))
        print(f"FAIL {name}: {msg}", flush=True)
        return False


def until(what: str, fn, timeout: float = WAIT_S, every: float = 5):  # type: ignore[no-untyped-def]
    """Retry fn until it returns without raising (the website's caches expire), bounded."""
    end = time.monotonic() + timeout
    while True:
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            if time.monotonic() > end:
                raise AssertionError(f"{what}: still failing after {timeout:.0f} s: {e}") from e
            time.sleep(every)


def api(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(f"{CORE}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise AssertionError(f"{method} {path}: {e.code} {e.read()[:300]!r}") from e
    return json.loads(raw) if raw else {}


def shot(page, name: str) -> None:  # type: ignore[no-untyped-def]
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode()


# ── 1. admin: Meridian in Markets ────────────────────────────────────────────

def admin_sign_in(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(f"{ADMIN}/login", wait_until="networkidle")
    page.locator("input[type=email]").fill("admin@example.com")
    page.locator("input[type=password]").fill("BhojanGoAdmin1")
    page.get_by_role("button", name=re.compile("sign in", re.I)).click()
    page.wait_for_url("**/overview**", timeout=30000)


def add_city(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("link", name="Markets", exact=True).first.click()
    page.wait_for_url("**/markets")
    page.get_by_role("link", name="Open US").click()
    page.wait_for_url("**/markets/US")
    card = page.get_by_role("region", name="Add a city")
    card.get_by_role("button", name="New city").click()
    card.locator("select").first.select_option(label=STATE)  # the label's name includes the picked option
    card.get_by_label("City name").fill(CITY)
    code = card.get_by_label("City code").input_value()
    assert re.fullmatch(r"US-ID-[A-Z0-9]{2,4}", code), f"auto code {code!r}"
    card.get_by_label("Centre latitude").fill(str(LAT))
    card.get_by_label("Centre longitude").fill(str(LNG))
    card.get_by_role("button", name="Create city").click()
    expect(card.get_by_role("button", name="New city")).to_be_visible(timeout=15000)  # the form closes on success
    state["city_code"] = code
    table = page.get_by_role("region", name="States and cities")
    expect(table.get_by_role("link", name=CITY, exact=True)).to_be_visible(timeout=15000)


def draw_zone(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("region", name="States and cities").get_by_role("link", name=CITY, exact=True).click()
    page.wait_for_url(f"**/markets/US/{state['city_code']}")
    expect(page.get_by_role("heading", name=CITY, exact=True)).to_be_visible(timeout=15000)
    page.get_by_role("button", name="+ Draw zone").click()
    m = page.get_by_role("application", name=re.compile("click to add"))
    expect(m).to_be_visible()
    page.wait_for_timeout(500)  # Leaflet sizes itself after mount
    box = m.bounding_box()
    assert box, "no map"
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2  # the city's centre (setView)
    d = 110  # px at zoom 12: about 4 km each way
    for i, (dx, dy) in enumerate([(-d, -d), (d, -d), (d, d), (-d, d)], start=1):
        page.mouse.click(cx + dx, cy + dy)
        expect(page.get_by_text(f"Click the map to add corners · {i} added")).to_be_visible()
    page.get_by_role("button", name="Finish shape").click()
    form = page.locator("form").filter(has_text="New zone")
    form.get_by_label("Name").fill(ZONE)
    form.get_by_role("button", name="Create zone").click()
    zones = page.get_by_role("region", name="Zones")
    expect(zones.get_by_role("heading", name="Zones · 1")).to_be_visible(timeout=15000)
    expect(zones.get_by_role("button", name=re.compile(ZONE))).to_contain_text("Draft")


def zone_live(page) -> None:  # type: ignore[no-untyped-def]
    zones = page.get_by_role("region", name="Zones")
    zones.get_by_role("button", name=re.compile(ZONE)).click()
    page.get_by_role("button", name="Make live").click()
    expect(zones.get_by_role("button", name=re.compile(ZONE))).to_contain_text("Live", timeout=15000)


def service_hours(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name="Edit", exact=True).click()
    form = page.locator("form").filter(has=page.get_by_label("Opens"))
    form.get_by_label("Opens").fill("00:00")
    form.get_by_label("Closes").fill("23:59")
    form.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("00:00 – 23:59")).to_be_visible(timeout=15000)


def city_live(page) -> None:  # type: ignore[no-untyped-def]
    group = page.get_by_role("radiogroup", name="City status")
    expect(page.get_by_text(re.compile(f"Before {CITY} can open"))).to_have_count(0, timeout=15000)
    group.get_by_role("radio", name="live").click()
    expect(group.get_by_role("radio", name="live")).to_have_attribute("aria-checked", "true", timeout=15000)
    expect(page.get_by_role("button", name="Dismiss")).to_have_count(0)  # no error note (Next's route announcer is also role=alert)
    shot(page, "01-admin-meridian")


# ── 2. a partner opens a kitchen; the admin approves it ──────────────────────

def partner_kitchen() -> None:
    d = api("GET", "/markets/directory")
    city = next(c for k in d["countries"] for r in k["regions"] for c in r["cities"] if c["name"] == CITY)  # type: ignore[index]
    assert city["code"] == state["city_code"] and city["status"] == "live", city
    email = f"partner.{uuid.uuid4().hex[:8]}@example.com"
    tok = api("POST", "/auth/register", None, {"email": email, "full_name": "Maya Ortiz", "country": "US",
                                               "phone": f"+1208555{uuid.uuid4().int % 10000:04d}",
                                               "password": "Kitchen2026x"})["access_token"]  # type: ignore[index]
    applied = api("POST", "/restaurants/apply", tok, {
        "full_name": "Maya Ortiz", "kitchen_name": KITCHEN, "city_code": city["code"], "street": "33 E Broadway Ave",
        "area": "Downtown", "zip": "83642", "lat": LAT + 0.002, "lng": LNG + 0.002, "cuisines": ["American"]})
    tok, rid = applied["access_token"], applied["restaurant_id"]  # type: ignore[index]
    api("PUT", f"/restaurants/{rid}/hours", tok, {"weekly": [{"weekday": w, "opens": "00:00", "closes": "23:59"} for w in range(7)]})
    for i, (name, price, cat) in enumerate(DISHES):
        api("POST", f"/restaurants/{rid}/menu-items", tok, {"name": name, "price": price, "category": cat,
                                                            "description": f"{name}, made in {CITY}.", "sort_order": i})
    api("POST", "/finance/payout-accounts", tok, {"payee_type": "restaurant", "restaurant_id": rid})
    app = api("GET", f"/restaurants/{rid}/application", tok)
    assert app["done"] >= app["total"] - 1, app  # type: ignore[index]
    state.update(rid=rid, partner=tok)


def approve(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("link", name="Partners", exact=True).first.click()
    page.wait_for_url("**/partners**")
    page.get_by_role("navigation", name="Partners", exact=True).get_by_role("button", name="Applications").click()
    apps = page.get_by_role("region", name="Kitchens applying")
    apps.get_by_role("button", name=re.compile(KITCHEN)).click()
    detail = page.get_by_role("region", name=f"Application · {KITCHEN}")
    expect(detail).to_be_visible(timeout=15000)
    detail.get_by_role("button", name="Approve and go live").click()
    expect(page.get_by_text("Approved: the kitchen is live")).to_be_visible(timeout=15000)
    r = api("GET", f"/restaurants/{state['rid']}")
    assert r["status"] == "active", r["status"]  # type: ignore[index]
    state["slug"] = r["slug"]  # type: ignore[index]
    state["path"] = f"/us/meridian/{r['slug']}"  # type: ignore[index]


# ── 3. the website, from data ────────────────────────────────────────────────

def directory(page) -> None:  # type: ignore[no-untyped-def]
    def look() -> None:
        page.goto(f"{WEB}/cities", wait_until="networkidle")
        us = page.get_by_role("region", name="United States")
        link = us.locator(f"xpath=.//h3[normalize-space()='{STATE}']/following-sibling::div[1]//a[@href='/us/meridian']")
        expect(link).to_have_count(1, timeout=2000)
        expect(link).to_contain_text(CITY)
        expect(link).to_contain_text("1 kitchen")  # live: kitchens counted (soon would say "Coming soon")
    until("/cities lists Meridian live under Idaho", look)
    shot(page, "02-directory")


def city_page(page) -> None:  # type: ignore[no-untyped-def]
    def look() -> None:
        resp = page.goto(f"{WEB}/us/meridian", wait_until="networkidle")
        assert resp and resp.status == 200, f"/us/meridian: {resp.status if resp else None}"
        expect(page.get_by_role("heading", level=1)).to_contain_text(CITY, timeout=2000)
        expect(page.locator(f"a[href='{state['path']}']").first).to_be_visible(timeout=2000)
    until("/us/meridian shows the kitchen", look)
    expect(page.locator(f"a[href='{state['path']}']").first).to_contain_text(KITCHEN)
    shot(page, "03-city-page")


def sitemap() -> None:
    def look() -> None:
        xml = get_text(f"{WEB}/sitemap.xml")
        missing = [u for u in (f"{SITE}/us/meridian", f"{SITE}{state['path']}") if f"<loc>{u}</loc>" not in xml]
        assert not missing, f"not in sitemap.xml: {missing}"
    until("sitemap.xml has Meridian and its kitchen", look)


def personal_home(browser) -> None:  # type: ignore[no-untyped-def]
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})  # a new visitor: no address cookie
    page = ctx.new_page()
    try:
        def look() -> None:
            ctx.clear_cookies()
            page.goto(WEB, wait_until="networkidle")
            box = page.get_by_role("combobox", name="Delivery address")
            box.fill(CITY)
            opt = page.get_by_role("option").filter(has_text=f"{ZONE}, {CITY}")
            expect(opt).to_be_visible(timeout=5000)
            opt.get_by_role("button").click()
            expect(page.get_by_text(re.compile(rf"1 kitchen delivers to .*{CITY}"))).to_be_visible(timeout=10000)
            expect(page.locator(f"a[href='{state['path']}']").first).to_be_visible(timeout=2000)
        try:
            until("the personal home for an address in Meridian shows the kitchen", look)
        except AssertionError as e:
            shot(page, "fail-personal-home")
            raise AssertionError(f"{e} | why: {why_not_home()}") from e
        shot(page, "04-personal-home")
    finally:
        ctx.close()


def why_not_home() -> str:
    """What the API says for the picked area, to point at the cause of a failure."""
    try:
        area = next(a for a in api("GET", f"/markets/areas?q={CITY}") if a["area"] == ZONE)  # type: ignore[union-attr]
        at = api("GET", f"/discover?lat={area['lat']}&lng={area['lng']}")
        city = api("GET", f"/discover?city={state['city_code']}")
        admin = api("POST", "/auth/login", None, {"email": "admin@example.com", "password": "BhojanGoAdmin1"})["access_token"]  # type: ignore[index]
        slots = [r["slot"] for r in api("GET", f"/rules/resolve?country=US&region=US-ID&city={state['city_code']}", admin)]  # type: ignore[union-attr]
        return (f"/discover at the area: served={at['served']} kitchens={len(at['restaurants'])}; "  # type: ignore[index]
                f"/discover?city: kitchens={len(city['restaurants'])}; "  # type: ignore[index]
                f"delivery_fee rule for {state['city_code']}: {'yes' if 'delivery_fee' in slots else 'NONE'} (slots: {', '.join(slots)})")
    except Exception as e:  # noqa: BLE001
        return f"(diagnosis failed: {e})"


def kitchen_page(page) -> None:  # type: ignore[no-untyped-def]
    def look() -> None:
        resp = page.goto(f"{WEB}{state['path']}", wait_until="networkidle")
        assert resp and resp.status == 200, f"{state['path']}: {resp.status if resp else None}"
        expect(page.get_by_role("heading", level=1)).to_contain_text(KITCHEN, timeout=2000)
        for name, _, _ in DISHES:
            expect(page.get_by_text(name, exact=True).first).to_be_visible(timeout=2000)
    until("the kitchen page shows its menu", look)
    shot(page, "05-kitchen-page")


def before() -> None:
    for path in ("/cities", "/sitemap.xml", "/"):
        assert CITY not in get_text(f"{WEB}{path}"), f"{path} already names {CITY}"


def main() -> int:
    for port, target in FORWARD.items():
        forward(port, target)
    t0 = time.monotonic()
    with sync_playwright() as p:
        b = p.chromium.launch()
        # What a crawler and visitors have already seen before the city exists:
        # the website's caches must still pick the new city up by themselves.
        check("before: the website is up and has no Meridian yet", before)

        admin = b.new_page(viewport={"width": 1440, "height": 1000})
        steps = [
            ("admin: sign in", lambda: admin_sign_in(admin)),
            ("admin: Markets > United States > New city: Meridian, Idaho (code made from the name)", lambda: add_city(admin)),
            ("admin: draw a zone on the map (4 corners) and name it", lambda: draw_zone(admin)),
            ("admin: make the zone live", lambda: zone_live(admin)),
            ("admin: service hours 00:00-23:59", lambda: service_hours(admin)),
            ("admin: open the city (status live)", lambda: city_live(admin)),
            ("partner: register, apply in Meridian, hours, 5 dishes, payout account (partner app APIs)", partner_kitchen),
            ("admin: Partners > Applications > approve the kitchen", lambda: approve(admin)),
        ]
        for name, fn in steps:
            if not check(name, fn):
                shot(admin, "fail-admin")
                break
        else:
            web = b.new_page(viewport={"width": 1280, "height": 900})
            check("web: /cities lists Meridian as live under Idaho, linking to /us/meridian", lambda: directory(web))
            check("web: /us/meridian renders the city page with the kitchen", lambda: city_page(web))
            check("web: /sitemap.xml has /us/meridian and the kitchen's page", sitemap)
            check("web: type 'Meridian' in the address box: the personal home shows the kitchen", lambda: personal_home(b))
            check("web: the kitchen page renders its menu", lambda: kitchen_page(web))
        b.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed in {time.monotonic() - t0:.0f} s", flush=True)
    for name, _, msg in failed:
        print(f"  FAIL {name}: {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
