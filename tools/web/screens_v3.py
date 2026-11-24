"""Viewport screenshots of every website page on a hosted environment's demo data
(web v3, QA review item 11), and side-by-sides with the design.

    QA_WEB=https://web-... QA_CORE=https://core-api-... E2E_LOGINS_FILE=/outside/the/repo/logins.txt \\
      [CHROMIUM=/path/to/chrome] python tools/web/screens_v3.py [out dir]

Full-page captures break on sticky headers and fixed bars, so each page is shot
as a person sees it: the top, the middle and the bottom of the page in the
window, at 1440 px (desktop) and 390 px (phone). Saved as
<out>/raw/<Page>-<width>-<top|middle|bottom>.jpg, then <out>/<Page>-<width>.jpg:
the design (docs/design/web/r_<Page>.png, r_MWeb<Page>.png at 390 px, when there
is one) on the left and the three website views on the right.

Read-only on purpose (QA gets no test writes): it signs in as a demo customer
(demo1.hyd, who has an order on its way, past orders and favourites from
tools/seed/demo.py) and only browses. The bag lives in the browser; checkout
asks for a price quote, as any visitor's checkout does. Nothing is ordered,
saved or changed.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import expect, sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # this folder: web_session
import web_session  # noqa: E402  (the website's session in cookies, R22 S8)

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "design" / "web"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "screenshots" / "web-v3")
RAW = OUT / "raw"
WEB = os.environ["QA_WEB"].rstrip("/")
CORE = os.environ["QA_CORE"].rstrip("/")
CUSTOMER = "demo1.hyd@example.com"
WIDTHS = {1440: 900, 390: 844}
PANEL = 520  # each column's width in a side-by-side

with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as _f:
    PASSWORDS = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in _f) if len(r) >= 4}


def api(method: str, path: str, token: str | None = None, body: dict | None = None):  # type: ignore[no-untyped-def]
    req = urllib.request.Request(f"{CORE}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "bhojango-screens",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


# ── what the signed-in pages show: the demo customer's own data (read only) ──
t = api("POST", "/auth/login", None, {"email": CUSTOMER, "password": PASSWORDS[CUSTOMER]})
cust = t["access_token"]
me = api("GET", "/users/me", cust)
home = next(a for a in api("GET", "/me/addresses", cust) if a.get("is_default"))
orders = api("GET", "/orders?limit=50", cust)
orders = orders.get("items", orders) if isinstance(orders, dict) else orders
active = next(o for o in orders if o["status"] not in ("delivered", "cancelled", "refunded", "rejected"))
loc = api("GET", f"/markets/locate?lat={home['lat']}&lng={home['lng']}")
place = {"label": f"{loc.get('zone_name')}, {loc.get('city_name')}", "lat": home["lat"], "lng": home["lng"],
         "country": loc.get("country_code"), "city_code": loc.get("city_code"), "city_path": "/in/hyderabad",
         "zone": loc.get("zone_name"), "served": True, "address_id": home["id"]}
session = web_session.script(me)
session_jar = web_session.cookies(CORE, cust, t["refresh_token"])

# A kitchen near home with a dish that has choices (the customise sheet) and another to add.
near = api("GET", f"/discover?lat={home['lat']}&lng={home['lng']}")
kitchen_path, dish, second = None, None, None
for k in near["restaurants"]:
    menu = api("GET", f"/restaurants/{k['id']}/menu")
    items = [i for c in menu.get("categories", []) for i in c["items"] if i.get("is_available", True)]
    withopts = [i for i in items if i.get("option_groups")]
    plain = [i for i in items if not i.get("option_groups")]
    if withopts and plain:
        kitchen_path, dish, second = f"/in/hyderabad/{k['slug']}", withopts[0]["name"], plain[0]["name"]
        break
assert kitchen_path, "no kitchen near home with a customisable dish"
directory = api("GET", "/markets/directory")
soon = next(c["path"] for k in directory["countries"] for r in k["regions"] for c in r["cities"] if c["status"] == "soon")

done: list[str] = []


def shoot(page, name: str, width: int) -> None:  # type: ignore[no-untyped-def]
    """Top, middle and bottom of the page in the window."""
    page.wait_for_timeout(1200)  # fonts, images, map tiles
    height = page.evaluate("() => document.documentElement.scrollHeight")
    view = page.viewport_size["height"]
    for pos, y in (("top", 0), ("middle", max(0, (height - view) // 2)), ("bottom", max(0, height - view))):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(500)
        png = RAW / f"{name}-{width}-{pos}.png"
        page.screenshot(path=str(png))
        Image.open(png).convert("RGB").save(png.with_suffix(".jpg"), quality=80, optimize=True)
        png.unlink()
    page.evaluate("window.scrollTo(0, 0)")
    done.append(f"{name}-{width}")
    print("saved", name, width, flush=True)


def font(size: int):  # type: ignore[no-untyped-def]
    for name in ("arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def side_by_side(name: str, width: int) -> None:
    design = DESIGN / (f"r_{name}.png" if width == 1440 else f"r_M{name}.png")
    cols: list[tuple[str, Image.Image | None]] = [
        ("Design" if design.exists() else "Design: none at this width", Image.open(design).convert("RGB") if design.exists() else None)]
    cols += [(f"Website {pos} ({width} px)", Image.open(RAW / f"{name}-{width}-{pos}.jpg"))
             for pos in ("top", "middle", "bottom") if (RAW / f"{name}-{width}-{pos}.jpg").exists()]
    scaled = []
    for label, im in cols:
        if im is None:
            scaled.append((label, Image.new("RGB", (PANEL, 200), "#F4F6F6")))
        else:
            scaled.append((label, im.resize((PANEL, max(1, round(im.height * PANEL / im.width))))))
    head = 34
    h = head + max(im.height for _, im in scaled)
    out = Image.new("RGB", (PANEL * len(scaled) + 12 * (len(scaled) - 1), h), "white")
    d = ImageDraw.Draw(out)
    for i, (label, im) in enumerate(scaled):
        x = i * (PANEL + 12)
        d.text((x + 4, 8), label, fill="#111418", font=font(16))
        out.paste(im, (x, head))
    out.save(OUT / f"{name}-{width}.jpg", quality=80, optimize=True)


RAW.mkdir(parents=True, exist_ok=True)
CHROMIUM = os.environ.get("CHROMIUM") or None
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)

    def anon(width: int):  # type: ignore[no-untyped-def]
        return b.new_context(viewport={"width": width, "height": WIDTHS[width]}).new_page()

    def signed_in(width: int):  # type: ignore[no-untyped-def]
        ctx = b.new_context(viewport={"width": width, "height": WIDTHS[width]})
        ctx.add_cookies([{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": WEB}])
        ctx.add_init_script(session)
        ctx.add_cookies(session_jar)
        return ctx.new_page()

    def add(page, name: str) -> None:  # type: ignore[no-untyped-def]
        page.get_by_role("button", name=f"Add {name}").first.click()
        sheet = page.get_by_role("dialog")
        if sheet.count():
            sheet.get_by_role("button", name=re.compile("^Add to cart")).click()
            expect(sheet).to_have_count(0, timeout=10000)

    for w in WIDTHS:
        # ── signed out ────────────────────────────────────────────────────────
        pg = anon(w)
        for name, path in (("WebLanding", "/"), ("WebSignIn", "/signin"),
                           ("WebOTP", "/signin/code?phone=%2B919000000101&country=IN&next=%2F"),
                           ("WebCity", "/in/hyderabad"), ("WebCities", "/cities"), ("WebComingSoon", soon)):
            pg.goto(WEB + path, wait_until="networkidle")
            shoot(pg, name, w)
        far = {"label": "Twin Falls, Idaho", "lat": 42.5558, "lng": -114.4701, "country": "US", "city_code": None,
               "city_path": None, "zone": None, "served": False}
        pg.context.add_cookies([{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(far)), "url": WEB}])
        pg.goto(WEB, wait_until="networkidle")
        shoot(pg, "WebNotInArea", w)
        pg.context.close()

        # ── signed in: demo1.hyd, home address, an order on its way ──────────
        pg = signed_in(w)
        pg.goto(WEB, wait_until="networkidle")
        expect(pg.get_by_role("region", name="Your order")).to_be_visible(timeout=20000)
        shoot(pg, "WebHome", w)
        pg.goto(f"{WEB}/orders/{active['id']}/track", wait_until="networkidle")
        expect(pg.locator('[data-testid="delivery-pin"]:visible')).to_be_visible(timeout=20000)
        pg.wait_for_timeout(3000)  # map tiles
        shoot(pg, "WebTracking", w)
        pg.goto(WEB + kitchen_path, wait_until="networkidle")
        pg.get_by_role("button", name=f"Add {dish}").first.click()
        expect(pg.get_by_role("dialog")).to_be_visible(timeout=10000)
        pg.wait_for_timeout(800)
        png = RAW / f"WebCustomise-{w}-top.png"  # the sheet is fixed to the window: one view
        pg.screenshot(path=str(png))
        Image.open(png).convert("RGB").save(png.with_suffix(".jpg"), quality=80, optimize=True)
        png.unlink()
        pg.get_by_role("dialog").get_by_role("button", name=re.compile("^Add to cart")).click()
        add(pg, second)
        shoot(pg, "WebKitchen", w)
        pg.goto(WEB + "/checkout", wait_until="networkidle")
        pg.wait_for_timeout(2000)
        shoot(pg, "WebCheckout", w)
        pg.goto(WEB + "/account/orders", wait_until="networkidle")
        delivered = pg.get_by_role("group", name="Show orders").get_by_role("button", name="Delivered")
        if delivered.count():
            delivered.click()
        rows = pg.get_by_role("main").get_by_role("button", name=re.compile(r"#[0-9A-F]{6}"))
        if rows.count():
            rows.first.click()
            pg.wait_for_timeout(1500)
        shoot(pg, "WebOrders", w)
        pg.goto(WEB + "/account/profile", wait_until="networkidle")
        shoot(pg, "WebProfile", w)
        pg.goto(WEB + "/account/favourites", wait_until="networkidle")
        shoot(pg, "WebFavourites", w)
        pg.context.close()
    b.close()

for w in WIDTHS:
    for name in ("WebLanding", "WebSignIn", "WebOTP", "WebCity", "WebCities", "WebComingSoon", "WebNotInArea", "WebHome",
                 "WebTracking", "WebCustomise", "WebKitchen", "WebCheckout", "WebOrders", "WebProfile", "WebFavourites"):
        side_by_side(name, w)
print(f"{len(done)} page views (x3 positions) saved in {RAW}; side-by-sides in {OUT}")
