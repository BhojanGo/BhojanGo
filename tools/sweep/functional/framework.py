"""R42 functional validation: the framework the page functions are written in (web.py, admin.py) and the registry
the spec files are generated from (specs.py). Each function on a page is one decorated Python function:

    @fn("web", "/checkout", "tip-chips", kind="button", users=("us", "in"),
        action="Choose each tip chip", expected="the bill's tip line and total change by the chip",
        verify="UI: tip row and total; API: a new quote with that tip has the same lines")
    def _(t: T) -> str: ...            # returns what actually happened (the report's "actual"); raises to fail

Kinds (tools/sweep/routes.py checks each page has an action, empty, error and permission function, or "na"):
button link form filter toggle navigation | empty | error | permission | number | display.
A function with down=True runs in the second phase, with core-api stopped (the "API down" error state).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from zoneinfo import ZoneInfo

REGISTRY: list["Fn"] = []
NA: list[dict] = []  # {"app", "route", "kind", "na": why}
WEB, ADMIN, CORE = "http://localhost:3000", "http://localhost:3001", "http://localhost:8001"
OTP = "123456"
PASSWORD, ADMIN_PASSWORD = "BhojanGo123", "BhojanGoAdmin1"
MARKET = {  # the customer, their city and a restaurant with a dish that has no choices to make
    "us": {"email": "customer1.boi@example.com", "phone": "2085550105", "cc": "US", "city": "US-ID-BOI", "path": "/us/boise",
           "rest": "boise-bowl-co-hyde-park", "dish": "Teriyaki Chicken Bowl", "dish2": "Miso Soup", "tz": "America/Boise",
           "cur": "$", "to": {"lat": 43.6150, "lng": -116.2023}, "partner": "partner.boi@example.com", "rider": "rider1.boi@example.com",
           "addr": {"street": "1 Main St", "city": "Boise", "state": "ID", "zip": "83702", "country": "US"}, "method": "card"},
    "in": {"email": "customer1.hyd@example.com", "phone": "9000000101", "cc": "IN", "city": "IN-TG-HYD", "path": "/in/hyderabad",
           "rest": "spice-route-kitchen-madhapur", "dish": "Veg Dum Biryani", "dish2": "Paneer Tikka", "tz": "Asia/Kolkata",
           "cur": "₹", "to": {"lat": 17.4483, "lng": 78.3915}, "partner": "partner.hyd@example.com", "rider": "rider3.hyd@example.com",
           "addr": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}, "method": "upi"},
}
ADMINS = {"super": "admin@example.com", "cm_us": "cm.us@example.com", "cm_in": "cm.in@example.com",
          "finance_us": "finance.us@example.com", "finance_in": "finance.in@example.com", "viewer_us": "viewer.us@example.com",
          "viewer_in": "viewer@example.com", "ops_boi": "ops.boi@example.com", "ops_hyd": "ops.hyd@example.com",
          "support_boi": "support.boi@example.com"}


@dataclass
class Fn:
    app: str
    route: str
    id: str
    kind: str
    action: str
    expected: str
    verify: str
    users: tuple[str, ...]
    run: Callable[["T"], str] | None
    down: bool = False
    maestro: str = ""  # an app screen's function: the Maestro flow that does and checks it (apps/<app>/.maestro/<flow>.yaml)


def fn(app: str, route: str, id: str, *, kind: str, action: str, expected: str, verify: str,
       users: tuple[str, ...] = ("us", "in"), down: bool = False):  # type: ignore[no-untyped-def]
    def wrap(f: Callable[["T"], str]) -> Callable[["T"], str]:
        REGISTRY.append(Fn(app, route, id, kind, action, expected, verify, users, f, down))
        return f
    return wrap


def app_fn(app: str, route: str, id: str, *, kind: str, action: str, expected: str, verify: str, flow: str,
           users: tuple[str, ...] = ("us", "in")) -> None:
    """A function of an app screen, done and checked on the emulator by a Maestro flow."""
    REGISTRY.append(Fn(app, route, id, kind, action, expected, verify, users, None, False, flow))


def na(app: str, route: str, kind: str, why: str) -> None:
    NA.append({"app": app, "route": route, "kind": kind, "na": why})


class Fail(AssertionError):
    pass


def ok(cond: object, why: object = "") -> None:
    if not cond:
        raise Fail(str(why)[:300])


# ── API and database ────────────────────────────────────────────────────────────────────────────────────────────────
def api(method: str, path: str, token: str | None = None, body: Any = None, *, raw: bool = False,
        headers: dict | None = None) -> Any:
    """core-api through the forwarded port. raw=True: (status, json) without raising."""
    h = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {}), **(headers or {})}
    if method == "POST" and path.rstrip("/") == "/orders":
        h.setdefault("X-Idempotency-Key", str(uuid.uuid4()))
    req = urllib.request.Request(f"{CORE}/api/v1{path}", method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        data, status = e.read(), e.code
    try:
        out = json.loads(data) if data else {}
    except ValueError:
        out = {"_text": data[:200].decode(errors="replace")}
    if raw:
        return status, out
    if status >= 400:
        raise Fail(f"{method} {path} -> {status}: {str(out)[:200]}")
    return out


_tokens: dict[str, tuple[float, str]] = {}


def token(who: str) -> str:
    """A bearer token for a customer market ("us"/"in"), an admin role (ADMINS) or an email."""
    hit = _tokens.get(who)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    email = MARKET[who]["email"] if who in MARKET else ADMINS.get(who, who)
    is_admin = who in ADMINS or email.split("@")[0] in {a.split("@")[0] for a in ADMINS.values()}
    body = api("POST", "/auth/login", None, {"email": email, "password": ADMIN_PASSWORD if is_admin else PASSWORD})
    if body.get("mfa_required"):
        from totp_signin import finish
        body = finish(lambda path, d: api("POST", path, None, d), email, body)
    _tokens[who] = (time.time(), body["access_token"])
    return body["access_token"]


def db_url() -> str:
    name = os.environ.get("POSTGRES_DB", "")
    from target_guard import test_database
    if not test_database(name):
        raise SystemExit(f"REFUSED: the functional run reads and writes only a test database, not {name!r}")
    return f"postgresql://bhojango:bhojango_dev@postgres:5432/{name}"


def sql(q: str, *args: Any) -> list[tuple]:
    import psycopg
    with psycopg.connect(db_url(), autocommit=True) as c:
        cur = c.execute(q, args)
        return cur.fetchall() if cur.description else []


# ── Numbers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
MONEY = re.compile(r"(−|-)?\s?([$₹])\s?([\d,]+(?:\.\d+)?)")
WEEKDAY_DATE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*,? (\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*(?:,? (\d{4}))?")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def money(text: str) -> Decimal:
    m = MONEY.search(text or "")
    ok(m, f"no amount in {text!r}")
    v = Decimal(m.group(3).replace(",", ""))
    return -v if m.group(1) else v


def amounts(text: str) -> list[Decimal]:
    return [Decimal(m.group(3).replace(",", "")) for m in MONEY.finditer(text or "")]


def api_numbers(*docs: Any) -> set[Decimal]:
    """Every number in API answers, as shown amounts could be: the value itself (major units, 2 places) and, for an
    integer, the value / 100 (minor units: cents, paise)."""
    out: set[Decimal] = set()

    def add(v: Any) -> None:
        try:
            d = Decimal(str(v))
        except (InvalidOperation, ValueError):
            return
        out.add(abs(d).quantize(Decimal("0.01")))
        if d == d.to_integral_value():
            out.add((abs(d) / 100).quantize(Decimal("0.01")))

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, bool) or x is None:
            return
        elif isinstance(x, (int, float, Decimal)):
            add(x)
        elif isinstance(x, str) and re.fullmatch(r"-?\d+(\.\d+)?", x):
            add(x)
        elif isinstance(x, str):  # amounts packed in a string, e.g. a tax line's by_line "food=24.00;packaging=0.50"
            for v in re.findall(r"(?<![\w.])-?\d+\.\d{2}(?![\d])", x):
                add(v)
    for d in docs:
        walk(d)
    return out


def amounts_backed(text: str, *docs: Any, also: tuple = ()) -> str:
    """Every amount the page shows is a number the API gave for that page (or a stated sum of them, `also`)."""
    shown = amounts(text)
    have = api_numbers(*docs) | {Decimal(str(a)).quantize(Decimal("0.01")) for a in also}
    missing = sorted({str(a) for a in shown if a.quantize(Decimal("0.01")) not in have})
    if missing:
        flat = " ".join((text or "").split())
        where = []
        for a in missing[:4]:
            i = flat.find(f"{int(Decimal(a)):,}" if Decimal(a) == int(Decimal(a)) else a)
            i = i if i >= 0 else flat.find(a.split(".")[0])
            where.append(f"{a} in '…{flat[max(0, i - 50):i + 20]}…'" if i >= 0 else a)
        raise Fail(f"shown but not in the API's answer: {'; '.join(where)} (of {len(shown)} amounts)")
    return f"{len(shown)} amounts shown, each equal to the API's"


def api_dates(tz: str, *docs: Any) -> set[date]:
    out: set[date] = set()
    zone = ZoneInfo(tz)

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and re.match(r"\d{4}-\d{2}-\d{2}", x):
            try:
                if len(x) == 10:
                    d = date.fromisoformat(x)
                    out.update({d})
                else:
                    dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
                    out.add(dt.astimezone(zone).date() if dt.tzinfo else dt.date())
            except ValueError:
                pass
    for d in docs:
        walk(d)
    return out


def dates_backed(text: str, tz: str, *docs: Any, extra: set[date] | None = None) -> str:
    """Every "Mon 16 Nov" the page shows is a date the API gave (in the payout or city time zone) and the right weekday."""
    have = api_dates(tz, *docs) | (extra or set())
    today = date.today()
    bad = []
    n = 0
    for m in WEEKDAY_DATE.finditer(text or ""):
        n += 1
        day, mon, year = int(m.group(2)), MONTHS.index(m.group(3)) + 1, m.group(4)
        cands = [date(int(year), mon, day)] if year else [date(today.year + k, mon, day) for k in (-1, 0, 1)]
        hit = [c for c in cands if c in have or (c - __import__("datetime").timedelta(days=1)) in have and m.group(1) == "Sun"]
        if not hit or hit[0].strftime("%a") != m.group(1):
            bad.append(m.group(0))
    ok(not bad, f"dates shown but not the API's (or the wrong weekday): {bad[:6]}")
    return f"{n} dates shown, each the API's"


# ── The test context ────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class T:
    browser: Any
    user: str
    out: str
    fn: Fn
    shots: list[str] = field(default_factory=list)
    vars: dict = field(default_factory=dict)
    page: Any = None
    _ctx: Any = None

    @property
    def m(self) -> dict:
        return MARKET[self.user] if self.user in MARKET else MARKET["us" if self.user.endswith("us") or "boi" in self.user else "in"]

    def open(self, path: str, *, who: str | None = None, width: int = 1440, app: str | None = None) -> Any:
        """A page as a user: who = "us"/"in" customer, an ADMINS role, "anon", "fresh" (a new customer, nothing yet)."""
        app = app or self.fn.app
        who = who or self.user
        if self.page is None or self.vars.get("_who") != (who, app):
            if self._ctx:
                self._ctx.close()
            state = sessions.get(self.browser, app, who, self.m)
            self._ctx = self.browser.new_context(viewport={"width": width, "height": 900}, storage_state=state)
            if app == "web":
                self._ctx.add_cookies([{"name": "bg_city", "value": self.m["city"], "url": WEB}])
            self.page = self._ctx.new_page()
            self.page.set_default_timeout(15000)
            self.vars["_who"] = (who, app)
            self.vars["_errors"] = []
            self.vars["_seen"] = []
            self.page.on("pageerror", lambda e: self.vars["_errors"].append(str(e)[:160]))

            def seen(resp):  # type: ignore[no-untyped-def]
                # core-api, or the admin console's own /api proxy to it
                if "/api/" in resp.url and resp.ok and "json" in (resp.headers.get("content-type") or ""):
                    try:
                        self.vars["_seen"].append(resp.json())
                    except Exception:  # noqa: BLE001
                        pass
            self.page.on("response", seen)
        self.page.set_viewport_size({"width": width, "height": 900 if width > 500 else 844})
        base = WEB if app == "web" else ADMIN
        self.page.goto(base + path, wait_until="networkidle", timeout=45000)
        self.page.wait_for_timeout(300)
        return self.page

    def seen(self) -> list:
        """Every core-api JSON answer this page received (what a client-rendered page draws its numbers from)."""
        return list(self.vars.get("_seen") or [])

    def shot(self, label: str) -> None:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{self.fn.app}{self.fn.route}-{self.fn.id}-{self.user}-{label}".lower()).strip("-")
        path = f"{self.fn.app}/{slug}.png"
        os.makedirs(f"{self.out}/{self.fn.app}", exist_ok=True)
        self.page.screenshot(path=f"{self.out}/{path}", full_page=True)
        self.shots.append(path)

    def text(self, locator: Any = None) -> str:
        return (locator if locator is not None else self.page.locator("main").first).inner_text()

    def close(self) -> None:
        if self._ctx:
            self._ctx.close()


class Sessions:
    """Signed-in browser storage per (app, who), made once per run (sign-in is rate-limited and a TOTP code works once)."""

    def __init__(self) -> None:
        self.states: dict[tuple[str, str], dict | None] = {}
        self.fresh_email: str | None = None

    def get(self, browser: Any, app: str, who: str, market: dict) -> dict | None:
        key = (app, who)
        if who == "anon":
            return None
        if key not in self.states:
            ctx = browser.new_context()
            page = ctx.new_page()
            try:
                if app == "admin":  # the admin console's "us" / "in" users are the two country managers
                    self._admin(page, ADMINS.get(who) or {"us": ADMINS["cm_us"], "in": ADMINS["cm_in"]}.get(who, who))
                else:
                    self._web(page, who, market)
                self.states[key] = ctx.storage_state()
            finally:
                ctx.close()
        return self.states[key]

    def _admin(self, page: Any, email: str) -> None:
        from totp_signin import admin_console_second_step
        page.goto(f"{ADMIN}/login", wait_until="networkidle")
        page.locator("input[type=email]").fill(email)
        page.locator("input[type=password]").fill(ADMIN_PASSWORD)
        page.get_by_role("button", name=re.compile("sign in", re.I)).click()
        admin_console_second_step(page, email)
        page.wait_for_url(re.compile(r"/overview|/finance|/operations|/partners"), timeout=30000)

    def _web(self, page: Any, who: str, market: dict) -> None:
        if who == "fresh":
            self.fresh_email = self.fresh_email or f"r42.fresh.{uuid.uuid4().hex[:8]}@example.com"
            page.goto(f"{WEB}/signin?way=email&mode=create", wait_until="networkidle")
            page.get_by_role("textbox", name="Email").fill(self.fresh_email)
            page.locator("input[name=new-password]").fill("R42-fresh-password-2026")
            page.get_by_role("button", name="Create account").click()
            page.get_by_role("textbox", name="Digit 1").fill(OTP)
            page.get_by_role("button", name="Continue").click()
        else:
            email = MARKET[who]["email"] if who in MARKET else who
            for attempt in range(3):
                page.goto(f"{WEB}/signin?way=email", wait_until="networkidle")
                page.get_by_role("textbox", name="Email").fill(email)
                page.locator("input[type=password]").first.fill(PASSWORD)
                page.get_by_role("button", name="Sign in", exact=True).click()
                try:
                    page.wait_for_url(re.compile(r"^(?!.*/signin).*$"), timeout=20000)
                    return
                except Exception:  # noqa: BLE001 - the per-minute sign-in limit
                    page.wait_for_timeout(20000 * (attempt + 1))
            raise Fail(f"could not sign in {email}")
        page.wait_for_url(re.compile(r"^(?!.*/signin).*$"), timeout=20000)


sessions = Sessions()


def down_state(t: T, path: str, who: str | None = None, cached_ok: bool = False) -> str:
    """With core-api stopped: the page still renders (no crash, no blank) and says it couldn't load. A website page the
    server renders may instead show its last good copy (Next.js keeps serving it): cached_ok accepts that when the page
    has its heading and real content, not an empty shell."""
    p = t.open(path, who=who)
    p.wait_for_timeout(1500)  # a client page's first calls fail, then it says so
    body = p.locator("body").inner_text()
    ok(len(body.strip()) > 40, "a blank page")
    ok(not re.search(r"Application error|Unhandled Runtime Error|Internal Server Error|This page could not be found", body),
       f"a crash page: {body[:120]!r}")
    said = re.search(r"couldn.t|could not|try again|unavailable|can.t (load|reach)|something went wrong|not available|offline|"
                     r"no connection|isn.t loading|didn.t load|reach", body, re.I)
    t.shot("api-down")
    if said:
        return f"renders with: {said.group(0)!r}"
    main = p.locator("main").first.inner_text() if p.locator("main").count() else body
    if cached_ok and p.get_by_role("heading", level=1).count() and len(main.strip()) > 300:
        return f"renders its last good copy (Next.js cache): {p.get_by_role('heading', level=1).first.inner_text()[:60]!r}, {len(main)} characters"
    raise Fail(f"no message that it couldn't load{' and no cached content' if cached_ok else ''}: {body[:160]!r}")


def forward(port: int, target: tuple[str, int]) -> None:
    """localhost:<port> in the Playwright container to a compose service (the pages call localhost:8001). A service
    that is down (the "API down" phase) closes the browser's connection, as a stopped server would."""
    import socket
    import threading

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
                u = socket.create_connection(target, timeout=5)
            except OSError:
                c.close()
                continue
            threading.Thread(target=pipe, args=(c, u), daemon=True).start()
            threading.Thread(target=pipe, args=(u, c), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()


FORWARD = {3000: ("web", 3000), 3001: ("admin", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
