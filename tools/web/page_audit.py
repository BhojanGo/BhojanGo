"""Every website and admin page, as each kind of visitor sees it, at every width (R8).

    QA_WEB=https://web-... QA_ADMIN=https://admin-... QA_CORE=https://core-api-... \\
      E2E_LOGINS_FILE=/outside/the/repo/logins.txt [CHROMIUM=/path/to/chrome] \\
      [OUT=docs/screenshots/round8] [ONLY=partner,help] python tools/web/page_audit.py

For each page in PAGES (the website signed out, signed in as a customer in India and
in the US, the kitchen partner applying, and the admin console):

- the layout checks of docs/specs/page-checklist.md at 360, 390, 768, 1024, 1280,
  1366, 1536 and 1920 CSS px, and at 1366 and 1920 screens with 125 % and 150 %
  display scaling (the browser then lays out 1093 / 911 and 1536 / 1280 CSS px):
  sideways scroll, anything past the right edge, text cut off by its box, and
  readable text under 13 px (the small token at 360 px; 12 px is the uppercase caption);
- one sheet per page (OUT/<page>.jpg): the page at 390 (phone), at 1366 with 125 %
  scaling (a common laptop) and at 1920, side by side, top of the page;
- OUT/results.json: per page and width, what failed.

Read-only (it signs in and browses), so it may run against QA (tools/target_guard.py
refuses QA only for runs that write). The bag lives in the browser.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

# Width x height in CSS px, device scale factor, and how the sheet names it.
CHECKS = [(360, 780, 1, "360"), (390, 844, 1, "390"), (768, 1024, 1, "768"), (1024, 768, 1, "1024"),
          (1280, 800, 1, "1280"), (1366, 768, 1, "1366"), (1536, 864, 1, "1536"), (1920, 1080, 1, "1920"),
          (1093, 614, 1.25, "1366@125%"), (911, 512, 1.5, "1366@150%"),
          (1536, 864, 1.25, "1920@125%"), (1280, 720, 1.5, "1920@150%")]
SHEET = ["390", "1366@125%", "1920"]

# The layout checks, in the page: sideways scroll, boxes past the right edge, text cut
# off (overflow hidden without an ellipsis), small text.
PROBE = r"""() => {
  const out = {scroll: document.documentElement.scrollWidth - window.innerWidth, past: [], clipped: [], small: []};
  const vw = window.innerWidth;
  const name = (e) => (e.getAttribute('data-testid') || e.getAttribute('aria-label') || e.tagName.toLowerCase() +
    (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').slice(0, 2).join('.') : '')) +
    ' "' + (e.innerText || '').trim().slice(0, 40) + '"';
  for (const e of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = e.getBoundingClientRect();
    if (r.width <= 2 || r.height <= 2) continue;  // hidden, or screen-reader only (sr-only is 1 x 1)
    // past the right edge (ignore things inside a sideways scroller, and off-canvas)
    let inScroller = false;
    for (let p = e.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') { inScroller = true; break; }
    }
    if (!inScroller && r.right > vw + 1 && r.left < vw) out.past.push(name(e));
    // text cut off by its own box
    const hasText = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (hasText && (cs.overflow === 'hidden' || cs.overflowX === 'hidden') && cs.textOverflow !== 'ellipsis'
        && cs.webkitLineClamp === 'none' && e.scrollWidth > e.clientWidth + 1) out.clipped.push(name(e));
    if (hasText) {
      const px = parseFloat(cs.fontSize);
      if (px < 12.95 && !(px === 12 && cs.textTransform === 'uppercase')) out.small.push(px + 'px ' + name(e));
    }
  }
  for (const k of ['past', 'clipped', 'small']) out[k] = [...new Set(out[k])].slice(0, 8);
  return out;
}"""


def api(core: str, method: str, path: str, token: str | None = None, body: dict | None = None):  # type: ignore[no-untyped-def]
    req = urllib.request.Request(f"{core}/api/v1{path}", method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:80] or "home"


def main() -> int:  # noqa: C901 - one walk through the site
    from PIL import Image
    from playwright.sync_api import sync_playwright

    web, admin, core = (os.environ.get(k, "").rstrip("/") for k in ("QA_WEB", "QA_ADMIN", "QA_CORE"))
    out = os.environ.get("OUT", "docs/screenshots/round8")
    only = [s for s in os.environ.get("ONLY", "").split(",") if s]
    os.makedirs(out, exist_ok=True)
    passwords: dict[str, str] = {}
    if os.environ.get("E2E_LOGINS_FILE"):
        with open(os.environ["E2E_LOGINS_FILE"], encoding="utf-8") as f:
            passwords = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in f) if len(r) == 4}

    def session(email: str) -> tuple[str, list[dict], dict]:
        """A signed-in browser for this account: the session in localStorage, its default address as the place."""
        t = api(core, "POST", "/auth/login", None, {"email": email, "password": passwords[email]})
        tok = t["access_token"]
        me = api(core, "GET", "/users/me", tok)
        cookies: list[dict] = []
        home = next((a for a in api(core, "GET", "/me/addresses", tok) if a.get("is_default")), None) if me.get("role") == "customer" else None
        if home:
            loc = api(core, "GET", f"/markets/locate?lat={home['lat']}&lng={home['lng']}")
            directory = api(core, "GET", "/markets/directory")
            city_path = next((c["path"] for k in directory["countries"] for r in k["regions"] for c in r["cities"]
                              if c.get("code") == loc.get("city_code")), None)
            place = {"label": f"{loc.get('zone_name')}, {loc.get('city_name')}", "lat": home["lat"], "lng": home["lng"],
                     "country": loc.get("country_code"), "city_code": loc.get("city_code"), "city_path": city_path,
                     "zone": loc.get("zone_name"), "served": bool(loc.get("serviceable")), "address_id": home["id"]}
            cookies = [{"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": web}]
        state = json.dumps({"state": {"access": tok, "refreshToken": t["refresh_token"], "user": me}, "version": 0})
        return state, cookies, {"token": tok, "me": me}

    # ── the pages, per kind of visitor ───────────────────────────────────────
    pages: list[tuple[str, str, str, str | None]] = []  # (name, who, url, signed-in email)
    if web:
        directory = api(core, "GET", "/markets/directory") if core else {"countries": []}
        for path, name in [("/", "home"), ("/signin", "sign-in"), ("/signin/code?phone=%2B12085550199&next=%2F", "sign-in-code"),
                           ("/cities", "cities"), ("/partner", "add-your-kitchen"), ("/ride", "deliver"), ("/help", "help"),
                           ("/terms", "terms"), ("/privacy", "privacy"), ("/credits", "credits"), ("/no-such-page", "not-found")]:
            pages.append((name, "visitor", web + path, None))
        for k in directory["countries"]:
            for r in k["regions"]:
                for c in r["cities"]:
                    if c.get("status") in ("live", "beta") and c.get("path"):
                        pages.append((f"city-{c['code'].lower()}", "visitor", web + c["path"], None))
        for email, tag in (("demo1.hyd@example.com", "in"), ("demo1.boi@example.com", "us")):
            if email not in passwords:
                continue
            tok = api(core, "POST", "/auth/login", None, {"email": email, "password": passwords[email]})["access_token"]
            orders = api(core, "GET", "/orders?limit=50", tok)
            orders = orders.get("items", orders) if isinstance(orders, dict) else orders
            done = next((o for o in orders if o["status"] == "delivered"), None)
            active = next((o for o in orders if o["status"] not in ("delivered", "cancelled", "refunded", "rejected", "pending_payment")), None)
            for path, name in [("/", "home-signed-in"), ("/checkout", "checkout-empty"), ("/account/orders", "orders"),
                               ("/account/profile", "profile"), ("/account/favourites", "favourites"), ("/help", "help-signed-in")]:
                pages.append((f"{name}-{tag}", "customer", web + path, email))
            if done:
                pages += [(f"order-receipt-{tag}", "customer", f"{web}/orders/{done['id']}", email),
                          (f"report-problem-{tag}", "customer", f"{web}/account/orders/{done['id']}/report", email)]
            if active:
                pages.append((f"tracking-{tag}", "customer", f"{web}/orders/{active['id']}/track", email))
            # a kitchen page of the customer's city
            city = next((c for k in directory["countries"] for r in k["regions"] for c in r["cities"]
                         if c.get("code", "").endswith("HYD" if tag == "in" else "BOI")), None)
            if city:
                pages.append((f"kitchen-{tag}", "customer", web + city["path"], email))  # resolved to a kitchen below
        if "applicant.hyd@example.com" in passwords:
            pages.append(("add-your-kitchen-applying", "kitchen partner", web + "/partner", "applicant.hyd@example.com"))
    if admin:
        for path in ("/login", "/overview", "/operations", "/partners", "/pricing", "/pricing/simulator", "/markets",
                     "/markets/IN", "/markets/IN/IN-TG-HYD", "/finance", "/settings"):
            pages.append((f"admin{slug(path) and '-' + slug(path)}", "admin", admin + path, None if path == "/login" else "admin@example.com"))
    if only:
        pages = [p for p in pages if any(o in p[0] for o in only)]

    results: dict[str, dict] = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM") or None)
        sessions: dict[str, tuple[str, list[dict], dict]] = {}
        admin_state = None
        for name, who, url, email in pages:
            shots: dict[str, str] = {}
            res: dict[str, dict] = {}
            # One load per display scaling; the widths are window resizes (the page reflows like a person's would).
            for dpr in sorted({c[2] for c in CHECKS}):
                group = [c for c in CHECKS if c[2] == dpr]
                ctx = b.new_context(viewport={"width": group[0][0], "height": group[0][1]}, device_scale_factor=dpr,
                                    storage_state=admin_state if (who == "admin" and email) else None)
                if email and who != "admin":
                    if email not in sessions:
                        sessions[email] = session(email)
                    state, cookies, _ = sessions[email]
                    if cookies:
                        ctx.add_cookies(cookies)
                    ctx.add_init_script(f"if (!localStorage.getItem('bhojango-session')) localStorage.setItem('bhojango-session', {json.dumps(state)});")
                pg = ctx.new_page()
                if who == "admin" and email and admin_state is None:
                    pg.goto(admin + "/login", wait_until="networkidle")
                    pg.locator("input[type=email]").fill(email)
                    pg.locator("input[type=password]").fill(passwords[email])
                    pg.get_by_role("button", name="Sign in").click()
                    pg.wait_for_url(re.compile(r".*/overview.*"), timeout=30000)
                    admin_state = ctx.storage_state()
                try:
                    pg.goto(url, wait_until="networkidle", timeout=45000)
                except Exception:  # noqa: BLE001 - a slow page is measured as it stands
                    pass
                if name.startswith("kitchen-"):  # a city page: open its first kitchen
                    first = pg.locator("main a[href*='/']").filter(has=pg.locator("img")).first
                    href = first.get_attribute("href") if first.count() else None
                    if href:
                        pg.goto(urllib.parse.urljoin(url, href), wait_until="networkidle")
                for w, h, _, label in group:
                    pg.set_viewport_size({"width": w, "height": h})
                    pg.wait_for_timeout(600)
                    pg.evaluate("window.scrollTo(0, 0)")
                    res[label] = pg.evaluate(PROBE)
                    if label in SHEET:
                        path = os.path.join(out, f"_{slug(name)}-{slug(label)}.png")
                        pg.screenshot(path=path)
                        shots[label] = path
                ctx.close()
            # one sheet: 390 | 1366@125% | 1920, scaled to one height
            ims = [Image.open(shots[k]).convert("RGB") for k in SHEET if k in shots]
            if ims:
                hgt = 900
                ims = [im.resize((round(im.width * hgt / im.height), hgt)) for im in ims]
                sheet = Image.new("RGB", (sum(i.width for i in ims) + 24 * (len(ims) + 1), hgt + 48), "#E2E7E8")
                x = 24
                for im in ims:
                    sheet.paste(im, (x, 24))
                    x += im.width + 24
                sheet.save(os.path.join(out, f"{slug(name)}.jpg"), quality=78)
                for k in shots.values():
                    os.remove(k)
            fails = {lab: {k: v for k, v in r.items() if (v if k != "scroll" else v > 1)} for lab, r in res.items()}
            fails = {lab: f for lab, f in fails.items() if f}
            results[name] = {"who": who, "url": url.replace(web, "").replace(admin, "admin:"), "layout_fails": fails}
            print(f"{'ok  ' if not fails else 'FAIL'} {name} ({who}) {'' if not fails else json.dumps(fails)[:400]}", flush=True)
        b.close()
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, ensure_ascii=False)
    bad = [n for n, r in results.items() if r["layout_fails"]]
    print(f"\n{len(results)} pages; {len(bad)} with layout problems", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
