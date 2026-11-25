"""R41 validation sweep: EVERY page of the customer website and the admin console, as a US user and an India user,
at 1440 and 390 px, with a screenshot and the same checks on each:

  status      the page answers (no 4xx/5xx; an auth page may redirect to sign-in)
  errors      no uncaught page error
  overflow    no sideways scroll
  cut-off     no text clipped by its box (overflow hidden, no ellipsis)
  sticky      no text under a bar pinned to the bottom of the screen, scrolled to the end
  words       no "kitchen" / "bag" in BhojanGo's own words (restaurants' trading names excepted)
  keys        no untranslated message key ("partner.apply.title") or unfilled placeholder ("{amount}")
  currency    the user's market only ($ for a US user, ₹ for an India user; customer pages)
  phone       +1 (208) 555-0123 / +91 98765 43210 formats
  weekday     every "Mon 16 Nov" matches its date (the year shown, else this year or the next)

Writes OUT/sweep-web.json and screenshots OUT/<app>/<slug>-<user>-<width>.png. Pages with parameters take the
first link on their parent page (a restaurant, an order, a help article, a statement...). The functions of each page
are exercised by the e2e suites (tools/web/e2e_web.py, tools/admin/e2e_admin.py); this sweep is the same checks
everywhere, so a page no suite visits is still looked at. Local stack only (tools/target_guard.py).
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
import threading
from datetime import date

from playwright.sync_api import sync_playwright

OUT = os.environ.get("OUT", "/out")
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402
from totp_signin import admin_console_second_step  # noqa: E402

ensure_safe_api("http://core-api:8001")
WEB, ADMIN = "http://localhost:3000", "http://localhost:3001"
FORWARD = {3000: ("web", 3000), 3001: ("admin", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
OTP = "123456"
USERS = {  # market: (phone, customer email, admin scope)
    "us": ("2085550105", "customer1.boi@example.com", "US"),
    "in": ("9000000101", "customer1.hyd@example.com", "IN"),
}
CITY = {"us": "/us/boise", "in": "/in/hyderabad"}
RESTAURANT = {"us": "/us/boise/boise-bowl-co-hyde-park", "in": "/in/hyderabad/spice-route-kitchen-madhapur"}

# (route, how to get there: a path, or "parent::selector" for the first matching link on the parent page, auth)
WEB_PAGES = [
    ("/", "/", False), ("/cities", "/cities", False), ("/[country]/[city]", "city", False),
    ("/[country]/[city]/[kitchen]", "restaurant", False), ("/deliver", "/deliver", False), ("/deliver/app", "/deliver/app", False),
    ("/partner", "/partner", False), ("/help", "/help", False), ("/help/[topic]", "/help::a[href^='/help/']:not([href^='/help/a/'])", False),
    ("/help/[topic]/[slug]", "help_article", False), ("/help/a/[slug]", "/help::a[href^='/help/a/']", False),
    ("/terms", "/terms", False), ("/terms/history", "/terms/history", False),
    ("/terms/history/[version]", "/terms/history::a[href^='/terms/history/']", False),
    ("/privacy", "/privacy", False), ("/privacy/history", "/privacy/history", False),
    ("/privacy/history/[version]", "/privacy/history::a[href^='/privacy/history/']", False),
    ("/credits", "/credits", False), ("/signin", "/signin", False), ("/signin/code", "/signin/code?phone=%2B12085550105&next=%2F", False),
    ("/signin/forgot", "/signin/forgot", False), ("/signin/reset", "/signin/reset?token=expired-sweep-token", False),
    ("/payouts/done", "/payouts/done", False),
    ("/account/profile", "/account/profile", True), ("/account/orders", "/account/orders", True),
    ("/account/favourites", "/account/favourites", True),
    ("/orders/[id]", "order", True),
    ("/orders/[id]/track", "order_track", True), ("/orders/[id]/report", "order_report", True),
    ("/account/orders/[id]/report", "account_order_report", True),
    ("/checkout", "/checkout", True), ("/checkout/return", "/checkout/return?order=00000000-0000-0000-0000-000000000000", True),
]
ADMIN_PAGES = [
    ("/login", "/login", False), ("/overview", "/overview?scope={scope}", True), ("/operations", "/operations?scope={scope}", True),
    ("/incidents", "/incidents?scope={scope}", True), ("/partners", "/partners?scope={scope}", True),
    ("/pricing", "/pricing?scope={scope}", True), ("/pricing/fees", "/pricing/fees?scope={scope}", True),
    ("/pricing/simulator", "/pricing/simulator?scope={scope}", True), ("/markets", "/markets?scope={scope}", True),
    ("/markets/[country]", "/markets/{scope}", True), ("/markets/[country]/[city]", "/markets/{scope}::a[href^='/markets/{scope}/']", True),
    ("/finance", "/finance?scope={scope}", True), ("/finance/statements/[id]", "/finance?scope={scope}::a[href^='/finance/statements/']", True),
    ("/settings", "/settings?scope={scope}", True), ("/content/help", "/content/help?scope={scope}", True),
    ("/content/help/new", "/content/help/new?scope={scope}", True),
    ("/content/help/[id]", "/content/help?scope={scope}::a[href^='/content/help/']:not([href$='/new'])", True),
    ("/content/legal", "/content/legal?scope={scope}", True),
]

CHECK_JS = """() => {
  const W = innerWidth, H = innerHeight, out = {overflow: document.documentElement.scrollWidth > W + 1, cut: [], sticky: []};
  const visible = el => { const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null; };
  for (const el of document.querySelectorAll('body *')) {
    if (out.cut.length > 4) break;
    if (!el.childNodes.length || ![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const s = getComputedStyle(el);
    if (!visible(el) || el.clientWidth < 2 || s.position === 'absolute' && el.clientWidth <= 1) continue;
    const clipX = (s.overflowX === 'hidden' || s.overflowX === 'clip') && el.scrollWidth > el.clientWidth + 1 && s.textOverflow !== 'ellipsis';
    if (clipX && !el.closest('[aria-hidden=true]') && !el.className.toString().includes('sr-only'))
      out.cut.push(el.textContent.trim().slice(0, 40));
  }
  const bars = [...document.querySelectorAll('body *')].filter(el => {
    const s = getComputedStyle(el); if (s.position !== 'fixed' || !visible(el)) return false;
    const r = el.getBoundingClientRect(); return r.bottom >= H - 2 && r.height > 30 && r.height < H / 2 && r.width > W / 2;
  });
  if (bars.length) {
    window.scrollTo(0, document.documentElement.scrollHeight);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode() && out.sticky.length < 5) {
      const n = walker.currentNode, el = n.parentElement;
      if (!n.textContent.trim() || !el || bars.some(b => b.contains(el)) || !visible(el)) continue;
      if (getComputedStyle(el).position === 'fixed' || el.closest('[role=dialog]')) continue;
      const range = document.createRange(); range.selectNodeContents(n);
      for (const q of range.getClientRects()) {
        if (q.width < 1 || q.bottom < 0 || q.top > H) continue;
        if (bars.some(b => { const r = b.getBoundingClientRect(); return q.left < r.right && q.right > r.left && q.top < r.bottom && q.bottom > r.top; }))
          { out.sticky.push(n.textContent.trim().slice(0, 40)); break; }
      }
    }
  }
  out.text = document.body.innerText;
  return out;
}"""
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAY_DATE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,? (\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*(?:,? (\d{4}))?")
KEY = re.compile(r"(?<![\w/@.-])[a-z][a-z_]+\.[a-z_]+\.[a-z_]+(?![\w/.@-])")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
PHONE = re.compile(r"\+(1|91)[\d\s()\-]{8,}\d")
GOOD_PHONE = re.compile(r"^\+1 \(\d{3}\) \d{3}-\d{4}$|^\+91 \d{5} \d{5}$")


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


def trading_names(page) -> list[str]:  # type: ignore[no-untyped-def]
    """Restaurants' own names may say "Kitchen": BhojanGo's words never do."""
    r = page.request.get("http://localhost:8001/api/v1/restaurants?limit=100")
    return [x["name"] for x in r.json().get("items", [])] if r.ok else []


def text_problems(text: str, market: str, customer_page: bool, names: list[str]) -> list[str]:
    found = []
    words = text
    for n in names:
        words = words.replace(n, "")
    words = re.sub(r"\b(Spice Route|Basque Corner|Ridgeline Pizza|Kesar|Golden Spoon|Nonna's|Lata's|Sawtooth|Hitech|Banjara)\s+Kitchen\b", "", words)
    words = re.sub(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", "", words)  # identifiers: a storage key, an article address
    for w in ("kitchen", "bag"):
        hits = re.findall(rf"[^\n]{{0,30}}\b{w}s?\b[^\n]{{0,30}}", words, re.I)
        if hits:
            found.append(f"words: '{w}' in {hits[0].strip()!r}")
    if (k := KEY.search(text)) and not re.search(r"\.(com|in|png|jpg|pdf|md)\b", k.group(0)):
        found.append(f"keys: untranslated {k.group(0)!r}")
    if p := PLACEHOLDER.search(text):
        found.append(f"keys: unfilled {p.group(0)!r}")
    if customer_page:
        other = "₹" if market == "us" else "$"
        if re.search(re.escape(other) + r"\s?\d", text):
            found.append(f"currency: {other} shown to a{' US' if market == 'us' else 'n India'} user")
    for m in PHONE.finditer(text):
        s = m.group(0).strip()
        if not GOOD_PHONE.match(s) and len(re.sub(r"\D", "", s)) >= 10:
            found.append(f"phone: {s!r}")
            break
    today = date.today()
    for m in WEEKDAY_DATE.finditer(text):
        wd, d, mon, y = m.group(1), int(m.group(2)), MONTHS.index(m.group(3)) + 1, m.group(4)
        years = [int(y)] if y else [today.year, today.year - 1, today.year + 1]
        ok = False
        for yy in years:
            try:
                ok = ok or DAYS[date(yy, mon, d).weekday()] == wd
            except ValueError:
                pass
        if not ok:
            found.append(f"weekday: {m.group(0)!r} is not a {wd}")
            break
    return found


def api(page, method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:  # type: ignore[no-untyped-def]
    """The API on the local stack (through the forwarded port); {} when it refuses."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(f"http://localhost:8001/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}),
                                          **({"X-Idempotency-Key": str(__import__("uuid").uuid4())} if path == "/orders" else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        return json.loads(raw) if raw else {}
    except (urllib.error.URLError, ValueError) as e:
        print("api", method, path, str(e)[:120], flush=True)
        return {}


def setup(page) -> None:  # type: ignore[no-untyped-def]
    """Something for the pages with an item to open: a paid order for each customer (its order, tracking and report
    pages) and last week's payout run in each country (a statement). Local and CI stacks only."""
    from totp_signin import finish

    for market, (_phone, email, _scope) in USERS.items():
        tok = api(page, "POST", "/auth/login", None, {"email": email, "password": "BhojanGo123"}).get("access_token")
        slug = RESTAURANT[market].rsplit("/", 1)[-1]
        rest = next((r for r in api(page, "GET", "/restaurants?limit=100").get("items", []) if r.get("slug") == slug), None)
        if not tok or not rest:
            continue
        menu = api(page, "GET", f"/restaurants/{rest['id']}/menu")
        dish = "Teriyaki Chicken Bowl" if market == "us" else "Veg Dum Biryani"  # no choices to make
        item = next((i for c in menu.get("categories", []) for i in c["items"] if i["name"] == dish), None)
        if not item:
            continue
        cart = [{"menu_item_id": item["id"], "quantity": 2}]
        to = {"lat": 43.6150, "lng": -116.2023} if market == "us" else {"lat": 17.4483, "lng": 78.3915}
        q = api(page, "POST", "/pricing/quote", tok, {"restaurant_id": rest["id"], "items": cart, "deliver_to": to})
        if not q.get("token"):
            continue
        addr = ({"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"} if market == "us"
                else {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"})
        method = "card" if market == "us" else "upi"
        order = api(page, "POST", "/orders", tok, {"restaurant_id": rest["id"], "items": cart, "quote_token": q["token"],
                                                  "payment_method": method, "delivery_address": addr})
        if order.get("id"):
            init = api(page, "POST", "/payments/initiate", tok, {"order_id": order["id"], "payment_method_type": method})
            if init.get("payment_intent_id"):
                api(page, "POST", f"/payments/fake/{init['payment_intent_id']}/complete", tok, {"outcome": "succeeded"})
    try:
        body = api(page, "POST", "/auth/login", None, {"email": "admin@example.com", "password": "BhojanGoAdmin1"})
        admin = finish(lambda path, d: api(page, "POST", path, None, d), "admin@example.com", body)["access_token"]
        for scope in ("US", "IN"):
            weeks = api(page, "GET", f"/finance/payout-weeks?country={scope}", admin).get("weeks", [])
            if weeks:
                api(page, "POST", "/finance/payout-runs", admin, {"country": scope, "period_start": weeks[0]["start"],
                                                                  "period_end": weeks[0]["end"]})
    except Exception as e:  # noqa: BLE001 - the statement pages are then skipped, and say why
        print("setup: no payout run:", str(e)[:120])


def main() -> int:
    for port, target in FORWARD.items():
        forward(port, target)
    rows: list[dict] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        sp = b.new_page()
        setup(sp)
        sp.close()
        for market, (phone, _email, scope) in USERS.items():
            for app, base, pages in (("web", WEB, WEB_PAGES), ("admin", ADMIN, ADMIN_PAGES)):
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                if app == "web":
                    ctx.add_cookies([{"name": "bg_city", "value": "US-ID-BOI" if market == "us" else "IN-TG-HYD", "url": WEB}])
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)[:120]))
                names = trading_names(page)
                signed = False
                for route, how, auth in pages:
                    if auth and not signed:
                        signed = sign_in(page, app, market, phone)
                    for width in (1440, 390):
                        page.set_viewport_size({"width": width, "height": 900 if width > 500 else 844})
                        errors.clear()
                        row = {"app": app, "page": route, "user": market, "width": width}
                        try:
                            url = resolve(page, app, base, how.replace("{scope}", scope), market)
                            if url is None:
                                rows.append({**row, "route": "", "result": "SKIP", "checks": [], "why": "no such item to open for this user"})
                                print("SKIP", app, route, market, width, flush=True)
                                continue
                            resp = page.goto(url, wait_until="networkidle", timeout=45000)
                            page.wait_for_timeout(400)
                            status = resp.status if resp else 0
                            got = page.evaluate(CHECK_JS)
                            problems = []
                            if status >= 400:
                                problems.append(f"status: {status}")
                            if errors:
                                problems.append(f"errors: {errors[0]}")
                            if got["overflow"]:
                                problems.append("overflow: sideways scroll")
                            if got["cut"]:
                                problems.append(f"cut-off: {got['cut'][0]!r}")
                            if got["sticky"]:
                                problems.append(f"sticky: {got['sticky'][0]!r} under a bottom bar")
                            problems += text_problems(got["text"], market, app == "web", names)
                            slug = re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-") or "home"
                            shot = f"{app}/{slug}-{market}-{width}.png"
                            os.makedirs(f"{OUT}/{app}", exist_ok=True)
                            page.screenshot(path=f"{OUT}/{shot}", full_page=True)
                            rows.append({**row, "route": url.replace(base, "") or "/", "result": "FAIL" if problems else "PASS",
                                         "checks": ["status", "errors", "overflow", "cut-off", "sticky", "words", "keys",
                                                    *(["currency"] if app == "web" else []), "phone", "weekday"],
                                         "why": "; ".join(problems), "screenshot": shot, "final_url": page.url.replace(base, "")})
                        except Exception as e:  # noqa: BLE001 - a page that can't be opened is a FAIL with its reason
                            rows.append({**row, "route": how, "result": "FAIL", "checks": [], "why": f"could not open: {str(e)[:160]}"})
                        print(rows[-1]["result"], app, route, market, width, rows[-1].get("why", "")[:140], flush=True)
                ctx.close()
        b.close()
    with open(f"{OUT}/sweep-web.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    fails = [r for r in rows if r["result"] == "FAIL"]
    print(f"{len(rows) - len(fails)}/{len(rows)} not failing ({sum(r['result'] == 'SKIP' for r in rows)} skipped)")
    return 1 if fails else 0


def sign_in(page, app: str, market: str, phone: str) -> bool:  # type: ignore[no-untyped-def]
    if app == "admin":
        page.goto(f"{ADMIN}/login", wait_until="networkidle")
        page.locator("input[type=email]").fill("admin@example.com")
        page.locator("input[type=password]").fill("BhojanGoAdmin1")
        page.get_by_role("button", name=re.compile("sign in", re.I)).click()
        admin_console_second_step(page, "admin@example.com")
        page.wait_for_url(re.compile(r"/overview"), timeout=20000)
        return True
    for _ in range(3):  # sign-in is limited per minute
        page.goto(f"{WEB}/signin", wait_until="networkidle")
        page.get_by_label("Country code").select_option("US" if market == "us" else "IN")
        page.get_by_role("textbox", name="Mobile number").fill(phone)
        page.get_by_role("button", name="Send code").click()
        try:
            page.wait_for_url(re.compile(r"/signin/code\?"), timeout=15000)
            page.get_by_role("textbox", name="Digit 1").fill(OTP)
            page.get_by_role("button", name="Verify and continue").click()
            page.wait_for_url(re.compile(r"^(?!.*/signin)"), timeout=20000)
            return True
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(20000)
    return False


def resolve(page, app: str, base: str, how: str, market: str) -> str | None:  # type: ignore[no-untyped-def]
    if how == "city":
        return base + CITY[market]
    if how == "restaurant":
        return base + RESTAURANT[market]
    if how == "help_article":
        topic = first_link(page, base, "/help", "a[href^='/help/']:not([href^='/help/a/'])")
        return first_link(page, base, topic.replace(base, ""), f"a[href^='{topic.replace(base, '')}/']") if topic else None
    if how in ("order", "order_track", "order_report", "account_order_report"):
        tok = api(page, "POST", "/auth/login", None, {"email": USERS[market][1], "password": "BhojanGo123"}).get("access_token")
        listed = api(page, "GET", "/orders?limit=5", tok) if tok else {}
        items = listed.get("items", listed) if isinstance(listed, dict) else listed
        oid = next((o["id"] for o in items if isinstance(o, dict) and o.get("id")), None) if items else None
        if not oid:
            return None
        return base + {"order": f"/orders/{oid}", "order_track": f"/orders/{oid}/track", "order_report": f"/orders/{oid}/report",
                       "account_order_report": f"/account/orders/{oid}/report"}[how]
    if "::" in how:
        parent, sel = how.split("::", 1)
        found = first_link(page, base, parent, sel)
        if found is None and parent.startswith(("/terms/history", "/privacy/history")):
            return base + parent + "/1"  # no published version yet: the page's own "not found" state
        if found is None and parent == "/help" and "help/a/" in sel:
            r = page.request.get("http://localhost:8001/api/v1/help?country=" + ("US" if market == "us" else "IN"))
            data = r.json() if r.ok else {}
            slug = next((a.get("slug") for t in data.get("topics", []) for a in t.get("articles", []) if a.get("slug")), None) \
                or next((a.get("slug") for a in data.get("popular", []) if a.get("slug")), None)
            return f"{base}/help/a/{slug}" if slug else None
        return found
    return base + how


def first_link(page, base: str, parent: str, selector: str) -> str | None:  # type: ignore[no-untyped-def]
    page.goto(base + parent, wait_until="networkidle", timeout=45000)
    link = page.locator(selector).first
    try:
        link.wait_for(state="attached", timeout=10000)  # a link in a layout hidden at this width counts too
    except Exception:  # noqa: BLE001
        return None
    href = link.get_attribute("href")
    return base + href if href and href.startswith("/") else href


if __name__ == "__main__":
    raise SystemExit(main())
