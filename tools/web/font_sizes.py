"""Every font size a person sees on the website and the admin console, page by page
(Round 8: the fluid type scale is the only source of sizes).

    QA_WEB=https://web-... [QA_ADMIN=https://admin-...] [QA_CORE=https://core-api-...] \\
      [E2E_LOGINS_FILE=/outside/the/repo/logins.txt] [CHROMIUM=/path/to/chrome] \\
      [SHOTS_DIR=docs/screenshots/type-v1/web] python tools/web/font_sizes.py

With SHOTS_DIR it also saves a viewport screenshot (JPEG) of every page view it measures.

Visits every website page at 1440 px and 390 px and every admin page at 1440 px,
reads the computed font size of each visible text node (and of form fields), and
prints per page the distinct sizes with how many text nodes use each. The sizes are
fluid (packages/ui tokens.js typeScale: each role from its min at a 360 px viewport
to its max at 1440 px, clamp() in between), so a size is checked against its role:
the nearest type class on the element or an ancestor (text-h1 ... text-caption,
any responsive variant) names the role(s), and the size must lie in that role's
[min, max] and match what the role computes at this viewport width. Text with no
type class must match some role at this width. Exits 1 when any text is off the
scale, any 12 px text is not uppercase (12 px is only the caption: uppercase labels
and badges), or any readable text is under 13 px.

Pages are found the way a visitor finds them: the city and kitchen pages from the
links on /cities and a city page (plus Boise, a US city), the admin tabs from the
console's own links. With QA_CORE and E2E_LOGINS_FILE it also signs in, as the demo
customers of Hyderabad and Boise (screens_v3.py's demo1.hyd and demo1.boi: past orders,
favourites, an order on its way when the city is open) for the account, checkout and
tracking pages, and as the demo admin for the console.

Read-only, so it runs against any environment, QA included, without the target
guard (tools/target_guard.py refuses QA only for runs that write): it signs in and
browses. The bag lives in the browser; nothing is ordered, saved or changed.

e2e_web.py imports collect() and problems() for its own cheaper check on a few pages.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request

# The type scale (packages/ui/tokens.js typeScale): each role's [min, max] in px,
# min at a 360 px wide viewport, max at 1440 px, linear between.
SCALE = {
    "display": (36, 52), "h1": (28, 36), "h2": (22, 28), "h3": (17, 20), "body-lg": (16, 18),
    "body": (15, 16), "label": (14, 15), "small": (13, 14), "caption": (12, 12),
}
FLUID = (360, 1440)
CAPTION = 12
MIN_READABLE = 13
TOLERANCE = 0.5  # px: rounding of rem/vw in the browser


# One pass over the page: visible text nodes (their parent's computed style) and form fields.
COLLECT_JS = r"""({ scale, fluid, caption, minReadable, tolerance }) => {
  const sizes = {};
  const bad = [];
  const vw = window.innerWidth;
  const k = Math.min(1, Math.max(0, (vw - fluid[0]) / (fluid[1] - fluid[0])));
  const at = (r) => scale[r][0] + (scale[r][1] - scale[r][0]) * k;
  const ROLE = /(?:^|:)text-(display|h1|h2|h3|body-lg|body|label|small|caption)$/;
  // The roles named by the nearest element (itself or an ancestor) with a type class.
  const rolesOf = (el) => {
    for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
      const cls = typeof e.className === "string" ? e.className : (e.getAttribute && e.getAttribute("class")) || "";
      const roles = cls.split(/\s+/).map((c) => (ROLE.exec(c) || [])[1]).filter(Boolean);
      if (roles.length) return roles;
    }
    return null;
  };
  const shown = (el) => el.checkVisibility
    ? el.checkVisibility({ visibilityProperty: true })
    : el.getClientRects().length > 0;
  const note = (el, text) => {
    const cs = getComputedStyle(el);
    const px = Math.round(parseFloat(cs.fontSize) * 100) / 100;
    sizes[px] = (sizes[px] || 0) + 1;
    const upper = cs.textTransform === "uppercase" || !/\p{Ll}/u.test(text);
    const named = rolesOf(el);
    const roles = named || Object.keys(scale);
    const fits = roles.filter((r) => px >= scale[r][0] - tolerance && px <= scale[r][1] + tolerance && Math.abs(px - at(r)) <= tolerance);
    let why = null;
    if (!fits.length) why = named ? `${px}px is not ${named.join("/")} at ${vw}px (${named.map((r) => at(r).toFixed(1)).join("/")})` : `${px}px is not on the type scale at ${vw}px`;
    else if (px < minReadable && !(Math.abs(px - caption) <= 0.01 && upper)) why = px === caption ? `${caption}px text that isn't uppercase` : `${px}px is under ${minReadable}px`;
    if (why && bad.length < 25) {
      const cls = typeof el.className === "string" ? el.className : "";
      bad.push({ px, upper, why, tag: el.tagName.toLowerCase(), text: text.slice(0, 60), cls: cls.slice(0, 140) });
    }
  };
  const skip = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE"]);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = n.nodeValue.trim();
    const el = n.parentElement;
    if (!text || !el || skip.has(el.tagName) || !shown(el)) continue;
    note(el, text);
  }
  for (const el of document.querySelectorAll("input:not([type=hidden]):not([type=checkbox]):not([type=radio]), textarea, select")) {
    const text = (el.value || el.placeholder || "").trim();
    if (text && shown(el)) note(el, text);
  }
  return { sizes, bad, width: vw };
}"""


def collect(page) -> dict:  # type: ignore[no-untyped-def]
    """{"sizes": {px: text nodes}, "bad": [samples of text off the scale, under 13 px or lowercase at 12 px], "width": vw}."""
    return page.evaluate(COLLECT_JS, {"scale": {r: list(v) for r, v in SCALE.items()}, "fluid": list(FLUID),
                                      "caption": CAPTION, "minReadable": MIN_READABLE, "tolerance": TOLERANCE})


def problems(result: dict) -> list[str]:
    """What's wrong on the page, in words (empty when every size is on the scale)."""
    return [f"{b['why']}: <{b['tag']} class=\"{b['cls']}\"> {b['text']!r}" for b in result["bad"]]


def summary(result: dict) -> str:
    sizes = sorted(((float(k), v) for k, v in result["sizes"].items()), reverse=True)
    return "  ".join(f"{k:g}px x{v}" for k, v in sizes)


# ── the run ───────────────────────────────────────────────────────────────────
WIDTHS = {1440: 900, 390: 844}
CUSTOMERS = ("demo1.hyd@example.com", "demo1.boi@example.com")  # India and the US
ADMIN = "admin@example.com"
WEB_PAGES = ("/", "/signin", "/signin/code?phone=%2B10000000000&next=%2F", "/cities", "/deliver", "/partner",
             "/help", "/privacy", "/terms", "/credits")
EXTRA_CITIES = ("/us/boise",)  # a US city: dollars, the US languages (the /cities list may show only one country)
ADMIN_SECTIONS = ("/overview", "/operations", "/partners", "/pricing", "/pricing/simulator", "/markets", "/finance", "/settings")


def api(core: str, method: str, path: str, token: str | None = None, body: dict | None = None):  # type: ignore[no-untyped-def]
    req = urllib.request.Request(f"{core}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "bhojango-font-sizes",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def links(page, pattern: str) -> list[str]:  # type: ignore[no-untyped-def]
    """Same-site paths on the page matching a regex, in page order, no repeats."""
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map((a) => a.getAttribute('href'))")
    seen: list[str] = []
    for h in hrefs:
        path = urllib.parse.urlsplit(h).path if h.startswith("http") else h
        if re.fullmatch(pattern, path.split("?")[0]) and path not in seen:
            seen.append(path)
    return seen


def main() -> int:
    from playwright.sync_api import sync_playwright

    web = os.environ.get("QA_WEB", "").rstrip("/")
    admin = os.environ.get("QA_ADMIN", "").rstrip("/")
    core = os.environ.get("QA_CORE", "").rstrip("/")
    if not web and not admin:
        print("set QA_WEB and/or QA_ADMIN (base URLs)", file=sys.stderr)
        return 2
    passwords: dict[str, str] = {}
    if os.environ.get("E2E_LOGINS_FILE"):
        with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as f:
            passwords = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in f) if len(r) == 4}

    failures: list[str] = []
    pages = 0
    shots = os.environ.get("SHOTS_DIR", "")
    if shots:
        os.makedirs(shots, exist_ok=True)

    def measure(page, label: str) -> None:  # type: ignore[no-untyped-def]
        nonlocal pages
        page.wait_for_timeout(800)  # fonts and late client renders
        r = collect(page)
        pages += 1
        bad = problems(r)
        if shots:  # SHOTS_DIR: a viewport screenshot of the page as measured
            name = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:90] or "page"
            page.screenshot(path=os.path.join(shots, f"{pages:03d}-{name}.jpg"), type="jpeg", quality=80)
        print(f"{'FAIL' if bad else 'ok  '} {label}: {summary(r)}", flush=True)
        for p in bad:
            print(f"       {p}", flush=True)
            failures.append(f"{label}: {p}")

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)

        # ── website, signed out ──────────────────────────────────────────────
        if web:
            for w, h in WIDTHS.items():
                pg = b.new_context(viewport={"width": w, "height": h}).new_page()
                found = list(WEB_PAGES)
                pg.goto(web + "/cities", wait_until="networkidle")
                cities = links(pg, r"/[a-z]{2}/[a-z0-9-]+")
                found += cities[:3]
                for city in ([cities[0]] if cities else []) + [c for c in EXTRA_CITIES if c != (cities[:1] or [None])[0]]:
                    pg.goto(web + city, wait_until="networkidle")
                    if city not in found:
                        found.append(city)
                    found += links(pg, r"/[a-z]{2}/[a-z0-9-]+/[a-z0-9-]+")[:2]
                for path in found:
                    pg.goto(web + path, wait_until="networkidle")
                    measure(pg, f"web {w} {path}")
                pg.context.close()

        # ── website, signed in as the demo customer ─────────────────────────
        if web and core and any(c in passwords for c in CUSTOMERS):
            for customer in (c for c in CUSTOMERS if c in passwords):
                t = api(core, "POST", "/auth/login", None, {"email": customer, "password": passwords[customer]})
                tok = t["access_token"]
                me = api(core, "GET", "/users/me", tok)
                session = json.dumps({"state": {"access": tok, "refreshToken": t["refresh_token"], "user": me}, "version": 0})
                cookies = []
                home = next((a for a in api(core, "GET", "/me/addresses", tok) if a.get("is_default")), None)
                if home:
                    loc = api(core, "GET", f"/markets/locate?lat={home['lat']}&lng={home['lng']}")
                    directory = api(core, "GET", "/markets/directory")
                    city_path = next((c["path"] for k in directory["countries"] for r in k["regions"] for c in r["cities"]
                                      if c.get("code") == loc.get("city_code")), None)
                    place = {"label": f"{loc.get('zone_name')}, {loc.get('city_name')}", "lat": home["lat"], "lng": home["lng"],
                             "country": loc.get("country_code"), "city_code": loc.get("city_code"), "city_path": city_path,
                             "zone": loc.get("zone_name"), "served": bool(loc.get("serviceable")), "address_id": home["id"]}
                    cookies = [{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": web}]
                orders = api(core, "GET", "/orders?limit=50", tok)
                orders = orders.get("items", orders) if isinstance(orders, dict) else orders
                account = ["/", "/checkout", "/account/orders", "/account/profile", "/account/favourites"]
                if orders:
                    active = next((o for o in orders if o["status"] not in ("delivered", "cancelled", "refunded", "rejected")), None)
                    done = next((o for o in orders if o["status"] == "delivered"), None)
                    if active:
                        account.append(f"/orders/{active['id']}/track")
                    if done:
                        account += [f"/account/orders?order={done['id']}", f"/account/orders/{done['id']}/report"]
                for w, h in WIDTHS.items():
                    ctx = b.new_context(viewport={"width": w, "height": h})
                    if cookies:
                        ctx.add_cookies(cookies)
                    ctx.add_init_script(f"if (!localStorage.getItem('bhojango-session')) localStorage.setItem('bhojango-session', {json.dumps(session)});")
                    pg = ctx.new_page()
                    for path in account:
                        pg.goto(web + path, wait_until="networkidle")
                        measure(pg, f"web {w} signed-in {customer.split('@')[0]} {path}")
                    ctx.close()
        elif web:
            print("(signed-in website pages skipped: set QA_CORE and E2E_LOGINS_FILE)", flush=True)

        # ── admin console at 1440 ───────────────────────────────────────────
        if admin:
            pg = b.new_context(viewport={"width": 1440, "height": 1000}).new_page()
            pg.goto(admin + "/login", wait_until="networkidle")
            measure(pg, "admin /login")
            if ADMIN in passwords:
                pg.locator("input[type=email]").fill(ADMIN)
                pg.locator("input[type=password]").fill(passwords[ADMIN])
                pg.get_by_role("button", name=re.compile("sign in", re.I)).click()
                pg.wait_for_url(re.compile(r"/overview"), timeout=30000)
                visited: set[str] = set()
                queue = list(ADMIN_SECTIONS)
                while queue and len(visited) < 60:
                    path = queue.pop(0)
                    key = re.sub(r"scope=[^&]*&?", "", path).rstrip("?&")
                    if key in visited:
                        continue
                    visited.add(key)
                    pg.goto(admin + path, wait_until="networkidle")
                    measure(pg, f"admin 1440 {path}")
                    # The section's tabs, and one country and one city under Markets.
                    section = path.split("?")[0]
                    for href in pg.eval_on_selector_all("a[href]", "els => els.map((a) => a.getAttribute('href'))"):
                        target = href.split("#")[0]
                        if target.startswith(section + "?") and "tab=" in target:
                            queue.append(target)
                    if section == "/markets":
                        queue += links(pg, r"/markets/[A-Za-z]{2}")[:1]
                    elif re.fullmatch(r"/markets/[A-Za-z]{2}", section):
                        queue += links(pg, r"/markets/[A-Za-z]{2}/[A-Za-z0-9-]+")[:1]
            else:
                print("(admin pages behind sign-in skipped: set E2E_LOGINS_FILE)", flush=True)
            pg.context.close()
        b.close()

    print(f"\n{pages} page views; {len(failures)} text nodes off the type scale")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
