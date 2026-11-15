"""A third city, and a third country, with no code change (make web-third-city;
tools/web/third_city.sh; on GitHub: e2e.yml "Third city and third country").

On a clean, seeded stack (compose project bhojango-3c), twice:
  A. Meridian, Idaho: a new city in an existing country (United States);
  B. Wellington, New Zealand: a new country with its own currency (NZD), tax
     (GST), phone code and language; one region, one city, one zone, one kitchen.

  1. admin, in the console: (B only: Markets > Add a country; its delivery fee
     and GST as rules, made by one admin and approved by a second; the country
     and region opened) Markets > <country> > New city, draws one zone on the
     map, makes it live, sets service hours, opens the city;
  2. a partner opens a kitchen there through the APIs the partner app uses
     (register in that country, apply, hours, five dishes, payout account), and
     the admin approves it in Partners > Applications;
  3. the website, from data alone: /cities lists the city live under its region,
     the city page shows the kitchen, the sitemap has both, the personal home for
     an address typed in the address box shows the kitchen, and its page has the
     menu priced in the country's currency.

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
ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.com", "BhojanGoAdmin1"  # seed (tools/seed/data.py)
CHECKER = "cm.us@example.com"  # a second admin, granted the new country so it can approve its rules
WAIT_S = 180  # the website caches Markets reads (Next revalidate 60 s, /discover 60 s in Redis)

MARKETS = [
    {"key": "city", "country": "US", "country_name": "United States", "new_country": None,
     "city": "Meridian", "state": "Idaho", "lat": 43.6121, "lng": -116.3915, "zone": "Meridian Downtown",
     "kitchen": "Treasure Valley Kitchen", "owner": "Maya Ortiz", "phone": ("+1208555", 4), "street": "33 E Broadway Ave",
     "area": "Downtown", "zip": "83642", "cuisines": ["American"], "currency": "USD", "price_text": r"\$14(\.00)?",
     "dishes": [("Finger Steak Basket", "14.00", "Mains"), ("Huckleberry Salmon", "21.00", "Mains"),
                ("Basque Chorizo Sandwich", "13.50", "Mains"), ("Fry Sauce Fries", "6.00", "Sides"),
                ("Huckleberry Shake", "7.50", "Drinks")]},
    {"key": "country", "country": "NZ", "country_name": "New Zealand",
     "new_country": {"code": "NZ", "name": "New Zealand", "currency": "NZD", "locales": "en-NZ",
                     "timezone": "Pacific/Auckland", "distance_unit": "km", "phone_code": "+64", "tax_regime": "gst"},
     "city": "Wellington", "state": "Wellington Region", "lat": -41.2865, "lng": 174.7762, "zone": "Wellington Central",
     "kitchen": "Harbour Kai Kitchen", "owner": "Aroha Ngata", "phone": ("+6421", 7), "street": "120 Cuba St",
     "area": "Te Aro", "zip": "6011", "cuisines": ["New Zealand"], "currency": "NZD", "price_text": r"\$24(\.00)?",
     "dishes": [("Fish and Chips", "24.00", "Mains"), ("Lamb Shank Pie", "19.50", "Mains"),
                ("Kumara Fries", "8.00", "Sides"), ("Pavlova", "11.00", "Desserts"), ("Flat White", "5.50", "Drinks")],
     "rules": [
         ("delivery_fee", "distance_slabs", None, "New Zealand delivery fee",
          {"slabs": [{"up_to": 3, "fee": 4.99}, {"up_to": 6, "fee": 6.99}, {"up_to": 10, "fee": 8.99}]}),
         ("tax", "rate_on_lines", "gst_all", "GST 15%",
          {"label": "GST", "rate_percent": 15, "collected_by": "platform",
           "target_lines": ["food", "packaging", "delivery_fee", "service_fee", "surge", "small_order_fee", "late_night_fee"]}),
     ]},
]
for _m in MARKETS:
    _m["slug"] = _m["city"].lower()
    _m["city_path"] = f"/{_m['country'].lower()}/{_m['slug']}"

results: list[tuple[str, bool, str]] = []
state: dict = {}  # per market key: city_code, region, rid, slug, path


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


def token(email: str) -> str:
    return api("POST", "/auth/login", None, {"email": email, "password": ADMIN_PASSWORD})["access_token"]  # type: ignore[index]


def country_summary(code: str) -> dict:
    """The country with its regions and cities, as the admin console reads it (GET /markets)."""
    return next(c for c in api("GET", "/markets", token(ADMIN_EMAIL)) if c["code"] == code)  # type: ignore[union-attr,index]


def shot(page, name: str) -> None:  # type: ignore[no-untyped-def]
    page.screenshot(path=f"{OUT}/{name}.png", full_page=True)


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode()


# ── 1. admin: the country (when new) and the city in Markets ─────────────────

def admin_sign_in(page) -> None:  # type: ignore[no-untyped-def]
    page.goto(f"{ADMIN}/login", wait_until="networkidle")
    page.locator("input[type=email]").fill(ADMIN_EMAIL)
    page.locator("input[type=password]").fill(ADMIN_PASSWORD)
    page.get_by_role("button", name=re.compile("sign in", re.I)).click()
    page.wait_for_url("**/overview**", timeout=30000)


def add_country(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    """Markets > Add a country: the form a super admin fills for a new market."""
    c = m["new_country"]
    page.get_by_role("link", name="Markets", exact=True).first.click()
    page.wait_for_url("**/markets")
    card = page.get_by_role("region", name="Add a country")
    card.get_by_role("button", name="New country").click()
    card.get_by_label("Country code (ISO, 2 letters)").fill(c["code"])
    card.get_by_label("Name", exact=True).fill(c["name"])
    card.get_by_label("Currency (ISO, 3 letters)").fill(c["currency"])
    card.get_by_label(re.compile("^Languages")).fill(c["locales"])
    card.get_by_label(re.compile("^Time zone")).fill(c["timezone"])
    card.get_by_label("Distance").select_option(c["distance_unit"])
    card.get_by_label("Phone code").fill(c["phone_code"])
    card.get_by_label("Tax regime").select_option(c["tax_regime"])
    boxes = card.get_by_role("checkbox")
    if not any(boxes.nth(i).is_checked() for i in range(boxes.count())):
        boxes.first.check()
    card.get_by_role("button", name="Create country").click()
    expect(card.get_by_role("button", name="New country")).to_be_visible(timeout=15000)  # the form closes on success
    expect(page.get_by_role("link", name=f"Open {c['code']}")).to_be_visible(timeout=15000)
    got = country_summary(c["code"])
    assert got["currency"] == c["currency"] and got["phone_code"] == c["phone_code"], got
    shot(page, f"00-admin-country-{c['code'].lower()}")


def country_rules(m: dict) -> None:
    """The country's delivery fee and GST: made by one admin, approved by a second
    (the super admin grants the checker the new country first)."""
    maker = token(ADMIN_EMAIL)
    api("POST", "/admin/role-assignments", maker, {"email": CHECKER, "role": "country_manager", "scope": m["country"]})
    checker = token(CHECKER)
    for family, template, key, name, params in m["rules"]:
        r = api("POST", "/rules", maker, {"family": family, "template": template, "key": key, "name": name,
                                          "params": params, "scope_level": "country", "scope_id": m["country"]})
        api("POST", f"/rules/{r['id']}/submit", maker, {})  # type: ignore[index]
        api("POST", f"/rules/{r['id']}/approve", checker, {})  # type: ignore[index]
    slots = [r["slot"] for r in api("GET", f"/rules/resolve?country={m['country']}", maker)]  # type: ignore[union-attr]
    assert "delivery_fee" in slots, slots


def add_city(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("link", name="Markets", exact=True).first.click()
    page.wait_for_url("**/markets")
    page.get_by_role("link", name=f"Open {m['country']}").click()
    page.wait_for_url(f"**/markets/{m['country']}")
    card = page.get_by_role("region", name="Add a city")
    card.get_by_role("button", name="New city").click()
    if m["new_country"]:
        card.get_by_label("State name").fill(m["state"])  # no states yet: the form starts on "A new state…"
    else:
        card.locator("select").first.select_option(label=m["state"])  # the label's name includes the picked option
    card.get_by_label("City name").fill(m["city"])
    card.get_by_label("Centre latitude").fill(str(m["lat"]))
    card.get_by_label("Centre longitude").fill(str(m["lng"]))
    card.get_by_role("button", name="Create city").click()
    expect(card.get_by_role("button", name="New city")).to_be_visible(timeout=15000)  # the form closes on success
    d = country_summary(m["country"])
    found = [(r["code"], c["code"]) for r in d["regions"] for c in r["cities"] if c["name"] == m["city"]]
    assert len(found) == 1, found
    region, code = found[0]
    assert re.fullmatch(rf"{m['country']}-[A-Z0-9]{{1,3}}-[A-Z0-9]{{2,5}}", code), f"auto code {code!r}"
    state[m["key"]] = {"city_code": code, "region": region}
    table = page.get_by_role("region", name="States and cities")
    expect(table.get_by_role("link", name=m["city"], exact=True)).to_be_visible(timeout=15000)


def open_country(m: dict) -> None:
    """A city can't open inside a draft country or state."""
    t = token(ADMIN_EMAIL)
    api("PATCH", f"/markets/countries/{m['country']}", t, {"status": "live"})
    api("PATCH", f"/markets/regions/{state[m['key']]['region']}", t, {"status": "live"})


def draw_zone(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    code = state[m["key"]]["city_code"]
    page.goto(f"{ADMIN}/markets/{m['country']}/{code}", wait_until="networkidle")
    expect(page.get_by_role("heading", name=m["city"], exact=True)).to_be_visible(timeout=15000)
    page.get_by_role("button", name="+ Draw zone").click()
    mp = page.get_by_role("application", name=re.compile("click to add"))
    expect(mp).to_be_visible()
    page.wait_for_timeout(500)  # Leaflet sizes itself after mount
    box = mp.bounding_box()
    assert box, "no map"
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2  # the city's centre (setView)
    d = 110  # px at zoom 12: about 4 km each way
    for i, (dx, dy) in enumerate([(-d, -d), (d, -d), (d, d), (-d, d)], start=1):
        page.mouse.click(cx + dx, cy + dy)
        expect(page.get_by_text(f"Click the map to add corners · {i} added")).to_be_visible()
    page.get_by_role("button", name="Finish shape").click()
    form = page.locator("form").filter(has_text="New zone")
    form.get_by_label("Name").fill(m["zone"])
    form.get_by_role("button", name="Create zone").click()
    zones = page.get_by_role("region", name="Zones")
    expect(zones.get_by_role("heading", name="Zones · 1")).to_be_visible(timeout=15000)
    expect(zones.get_by_role("button", name=re.compile(m["zone"]))).to_contain_text("Draft")


def zone_live(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    zones = page.get_by_role("region", name="Zones")
    zones.get_by_role("button", name=re.compile(m["zone"])).click()
    page.get_by_role("button", name="Make live").click()
    expect(zones.get_by_role("button", name=re.compile(m["zone"]))).to_contain_text("Live", timeout=15000)


def service_hours(page) -> None:  # type: ignore[no-untyped-def]
    page.get_by_role("button", name="Edit", exact=True).click()
    form = page.locator("form").filter(has=page.get_by_label("Opens"))
    form.get_by_label("Opens").fill("00:00")
    form.get_by_label("Closes").fill("23:59")
    form.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("00:00 – 23:59")).to_be_visible(timeout=15000)


def city_live(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    group = page.get_by_role("radiogroup", name="City status")
    expect(page.get_by_text(re.compile(f"Before {m['city']} can open"))).to_have_count(0, timeout=15000)
    group.get_by_role("radio", name="live").click()
    expect(group.get_by_role("radio", name="live")).to_have_attribute("aria-checked", "true", timeout=15000)
    expect(page.get_by_role("button", name="Dismiss")).to_have_count(0)  # no error note (Next's route announcer is also role=alert)
    shot(page, f"01-admin-{m['slug']}")


# ── 2. a partner opens a kitchen; the admin approves it ──────────────────────

def partner_kitchen(m: dict) -> None:
    st = state[m["key"]]
    d = api("GET", "/markets/directory")
    city = next(c for k in d["countries"] for r in k["regions"] for c in r["cities"] if c["name"] == m["city"])  # type: ignore[index]
    assert city["code"] == st["city_code"] and city["status"] == "live", city
    email = f"partner.{uuid.uuid4().hex[:8]}@example.com"
    prefix, digits = m["phone"]
    phone = f"{prefix}{uuid.uuid4().int % 10 ** digits:0{digits}d}"
    tok = api("POST", "/auth/register", None, {"email": email, "full_name": m["owner"], "country": m["country"],
                                               "phone": phone, "password": "Kitchen2026x"})["access_token"]  # type: ignore[index]
    applied = api("POST", "/restaurants/apply", tok, {
        "full_name": m["owner"], "kitchen_name": m["kitchen"], "city_code": city["code"], "street": m["street"],
        "area": m["area"], "zip": m["zip"], "lat": m["lat"] + 0.002, "lng": m["lng"] + 0.002, "cuisines": m["cuisines"]})
    tok, rid = applied["access_token"], applied["restaurant_id"]  # type: ignore[index]
    api("PUT", f"/restaurants/{rid}/hours", tok, {"weekly": [{"weekday": w, "opens": "00:00", "closes": "23:59"} for w in range(7)]})
    for i, (name, price, cat) in enumerate(m["dishes"]):
        api("POST", f"/restaurants/{rid}/menu-items", tok, {"name": name, "price": price, "category": cat,
                                                            "description": f"{name}, made in {m['city']}.", "sort_order": i})
    api("POST", "/finance/payout-accounts", tok, {"payee_type": "restaurant", "restaurant_id": rid})
    app = api("GET", f"/restaurants/{rid}/application", tok)
    assert app["done"] >= app["total"] - 1, app  # type: ignore[index]
    st.update(rid=rid, partner=tok)


def approve(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    st = state[m["key"]]
    page.get_by_role("link", name="Partners", exact=True).first.click()
    page.wait_for_url("**/partners**")
    page.get_by_role("navigation", name="Partners", exact=True).get_by_role("button", name="Applications").click()
    apps = page.get_by_role("region", name="Kitchens applying")
    apps.get_by_role("button", name=re.compile(m["kitchen"])).click()
    detail = page.get_by_role("region", name=f"Application · {m['kitchen']}")
    expect(detail).to_be_visible(timeout=15000)
    detail.get_by_role("button", name="Approve and go live").click()
    expect(page.get_by_text("Approved: the kitchen is live")).to_be_visible(timeout=15000)
    r = api("GET", f"/restaurants/{st['rid']}")
    assert r["status"] == "active", r["status"]  # type: ignore[index]
    assert r["currency"] == m["currency"], r["currency"]  # type: ignore[index]
    st["slug"] = r["slug"]  # type: ignore[index]
    st["path"] = f"{m['city_path']}/{r['slug']}"  # type: ignore[index]


# ── 3. the website, from data ────────────────────────────────────────────────

def directory(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    def look() -> None:
        page.goto(f"{WEB}/cities", wait_until="networkidle")
        country = page.get_by_role("region", name=m["country_name"])
        link = country.locator(f"xpath=.//h3[normalize-space()='{m['state']}']/following-sibling::div[1]//a[@href='{m['city_path']}']")
        expect(link).to_have_count(1, timeout=2000)
        expect(link).to_contain_text(m["city"])
        expect(link).to_contain_text("1 kitchen")  # live: kitchens counted (soon would say "Coming soon")
    until(f"/cities lists {m['city']} live under {m['state']}", look)
    shot(page, f"02-directory-{m['slug']}")


def city_page(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    path = state[m["key"]]["path"]

    def look() -> None:
        resp = page.goto(f"{WEB}{m['city_path']}", wait_until="networkidle")
        assert resp and resp.status == 200, f"{m['city_path']}: {resp.status if resp else None}"
        expect(page.get_by_role("heading", level=1)).to_contain_text(m["city"], timeout=2000)
        expect(page.locator(f"a[href='{path}']").first).to_be_visible(timeout=2000)
    until(f"{m['city_path']} shows the kitchen", look)
    expect(page.locator(f"a[href='{path}']").first).to_contain_text(m["kitchen"])
    shot(page, f"03-city-page-{m['slug']}")


def sitemap(m: dict) -> None:
    path = state[m["key"]]["path"]

    def look() -> None:
        xml = get_text(f"{WEB}/sitemap.xml")
        missing = [u for u in (f"{SITE}{m['city_path']}", f"{SITE}{path}") if f"<loc>{u}</loc>" not in xml]
        assert not missing, f"not in sitemap.xml: {missing}"
    until(f"sitemap.xml has {m['city']} and its kitchen", look)


def personal_home(browser, m: dict) -> None:  # type: ignore[no-untyped-def]
    path = state[m["key"]]["path"]
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})  # a new visitor: no address cookie
    page = ctx.new_page()
    try:
        def look() -> None:
            ctx.clear_cookies()
            page.goto(WEB, wait_until="networkidle")
            box = page.get_by_role("combobox", name="Delivery address")
            box.fill(m["city"])
            opt = page.get_by_role("option").filter(has_text=f"{m['zone']}, {m['city']}")
            expect(opt).to_be_visible(timeout=5000)
            opt.get_by_role("button").click()
            expect(page.get_by_text(re.compile(rf"1 kitchen delivers to .*{m['city']}"))).to_be_visible(timeout=10000)
            expect(page.locator(f"a[href='{path}']").first).to_be_visible(timeout=2000)
        try:
            until(f"the personal home for an address in {m['city']} shows the kitchen", look)
        except AssertionError as e:
            shot(page, f"fail-personal-home-{m['slug']}")
            raise AssertionError(f"{e} | why: {why_not_home(m)}") from e
        shot(page, f"04-personal-home-{m['slug']}")
    finally:
        ctx.close()


def why_not_home(m: dict) -> str:
    """What the API says for the picked area, to point at the cause of a failure."""
    st = state[m["key"]]
    try:
        area = next(a for a in api("GET", f"/markets/areas?q={m['city']}") if a["area"] == m["zone"])  # type: ignore[union-attr]
        at = api("GET", f"/discover?lat={area['lat']}&lng={area['lng']}")
        city = api("GET", f"/discover?city={st['city_code']}")
        slots = [r["slot"] for r in api(  # type: ignore[union-attr]
            "GET", f"/rules/resolve?country={m['country']}&region={st['region']}&city={st['city_code']}", token(ADMIN_EMAIL))]
        return (f"/discover at the area: served={at['served']} kitchens={len(at['restaurants'])}; "  # type: ignore[index]
                f"/discover?city: kitchens={len(city['restaurants'])}; "  # type: ignore[index]
                f"delivery_fee rule for {st['city_code']}: {'yes' if 'delivery_fee' in slots else 'NONE'} (slots: {', '.join(slots)})")
    except Exception as e:  # noqa: BLE001
        return f"(diagnosis failed: {e})"


def kitchen_page(page, m: dict) -> None:  # type: ignore[no-untyped-def]
    path = state[m["key"]]["path"]

    def look() -> None:
        resp = page.goto(f"{WEB}{path}", wait_until="networkidle")
        assert resp and resp.status == 200, f"{path}: {resp.status if resp else None}"
        expect(page.get_by_role("heading", level=1)).to_contain_text(m["kitchen"], timeout=2000)
        for name, _, _ in m["dishes"]:
            expect(page.get_by_text(name, exact=True).first).to_be_visible(timeout=2000)
        # priced in the country's currency, formatted for its locale (en-NZ shows NZD as "$")
        expect(page.get_by_text(re.compile(m["price_text"])).first).to_be_visible(timeout=2000)
    until(f"the kitchen page shows its menu in {m['currency']}", look)
    shot(page, f"05-kitchen-page-{m['slug']}")


def before() -> None:
    for path in ("/cities", "/sitemap.xml", "/"):
        text = get_text(f"{WEB}{path}")
        for m in MARKETS:
            assert m["city"] not in text, f"{path} already names {m['city']}"
    assert "New Zealand" not in get_text(f"{WEB}/cities"), "/cities already lists New Zealand"


def run_market(b, admin, m: dict) -> None:  # type: ignore[no-untyped-def]
    where = f"{m['city']}, {m['state']}"
    steps = []
    if m["new_country"]:
        c = m["new_country"]
        steps += [
            (f"admin: Markets > Add a country: {c['name']} ({c['currency']}, {c['tax_regime'].upper()}, {c['phone_code']}, {c['locales']})",
             lambda: add_country(admin, m)),
            (f"admin: {c['name']} delivery fee and GST as rules (one admin makes, a second approves)", lambda: country_rules(m)),
        ]
    steps.append((f"admin: Markets > {m['country_name']} > New city: {where} (codes made from the names)", lambda: add_city(admin, m)))
    if m["new_country"]:
        steps.append((f"admin: open {m['country_name']} and {m['state']}", lambda: open_country(m)))
    steps += [
        ("admin: draw a zone on the map (4 corners) and name it", lambda: draw_zone(admin, m)),
        ("admin: make the zone live", lambda: zone_live(admin, m)),
        ("admin: service hours 00:00-23:59", lambda: service_hours(admin)),
        ("admin: open the city (status live)", lambda: city_live(admin, m)),
        (f"partner: register in {m['country']}, apply in {m['city']}, hours, 5 dishes, payout account (partner app APIs)",
         lambda: partner_kitchen(m)),
        ("admin: Partners > Applications > approve the kitchen", lambda: approve(admin, m)),
    ]
    for name, fn in steps:
        if not check(f"[{m['city']}] {name}", fn):
            shot(admin, f"fail-admin-{m['slug']}")
            return
    web = b.new_page(viewport={"width": 1280, "height": 900})
    check(f"[{m['city']}] web: /cities lists {m['city']} live under {m['state']}, linking to {m['city_path']}", lambda: directory(web, m))
    check(f"[{m['city']}] web: {m['city_path']} renders the city page with the kitchen", lambda: city_page(web, m))
    check(f"[{m['city']}] web: /sitemap.xml has {m['city_path']} and the kitchen's page", lambda: sitemap(m))
    check(f"[{m['city']}] web: type '{m['city']}' in the address box: the personal home shows the kitchen", lambda: personal_home(b, m))
    check(f"[{m['city']}] web: the kitchen page renders its menu in {m['currency']}", lambda: kitchen_page(web, m))
    web.close()


def main() -> int:
    for port, target in FORWARD.items():
        forward(port, target)
    t0 = time.monotonic()
    with sync_playwright() as p:
        b = p.chromium.launch()
        # What a crawler and visitors have already seen before the places exist:
        # the website's caches must still pick them up by themselves.
        check("before: the website is up and names neither new place yet", before)
        admin = b.new_page(viewport={"width": 1440, "height": 1000})
        if check("admin: sign in", lambda: admin_sign_in(admin)):
            for m in MARKETS:
                run_market(b, admin, m)
        b.close()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed in {time.monotonic() - t0:.0f} s", flush=True)
    for name, _, msg in failed:
        print(f"  FAIL {name}: {msg}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
