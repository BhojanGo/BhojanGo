"""Every website page in every language at phone (360 px) and desktop (1440 px) width:
no sideways scroll and no catalog text cut off or spilling out of its box (R27).

    sh tools/web/i18n_layout.sh                   (CI: e2e.yml, after the web run, on `make dev`)
    WEB=https://qa.bhojango.com CORE=https://api.qa.bhojango.com [CHROMIUM=...] python tools/web/i18n_layout.py [out]
                                                   (read only: public pages; signed-in pages
                                                    only with LOGINS_OK=1 and the seed's password)

For each live country in Markets (/markets/directory) and each of its languages (its
locales: India en hi te ta kn mr bn, the US en es), the visitor's language cookie
(bg_lang) and city (bg_city) are set and every page below is opened at both widths:

  /  (landing, and the personal home for an address in the city: offers, kitchens)
  /cities, the city page, a kitchen page (the first on the city page), /help, a help
  topic and article, /deliver, /partner, /signin, /terms, /privacy, /credits;
  signed in (the seed's customer1.<city>, password from SEED_PASSWORD): /account/orders,
  /account/favourites, /account/profile, and the customer's latest order (receipt).

A page fails when
  page      the document is wider than the window (sideways scroll), or
  clipped   an element with overflow hidden/clip (Tailwind `truncate`, `overflow-hidden`) or a
            line clamp cuts its text (scrollWidth > clientWidth, scrollHeight > clientHeight), or
  spill     a box's text runs past its own edge (a nowrap button label wider than the button), or
  off       a text sticks out of the window (not inside a scroller such as a carousel),
and the text is the site's own words: phrases from that language's catalog
(packages/i18n/messages/<lang>.json, the parts between {placeholders}) make up at least half of it. A kitchen's or a
dish's name (data) cut by `truncate` is by design and only listed, not failed.

Not covered here: checkout (its bag lives in the browser), the order tracking map and the
sign-in code step; the admin console. The Expo apps: tools/i18n/check_app_lengths.py.
Screenshots of failures: <out>/<lang>-<width>-<page>.png. Exit 1 on any failure.
"""
import json
import os
import re
import socket
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import web_session  # noqa: E402

MESSAGES = Path(os.environ.get("MESSAGES", HERE.parents[1] / "packages" / "i18n" / "messages"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OUT", HERE.parents[1] / "docs" / "screenshots" / "web-i18n"))
WEB = os.environ.get("WEB", "").rstrip("/")
CORE = os.environ.get("CORE", "").rstrip("/")
LOCAL = not WEB  # `make dev` on the compose network (tools/web/i18n_layout.sh)
SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "BhojanGo123")
SIGNED_IN = LOCAL or os.environ.get("LOGINS_OK") == "1"
WIDTHS = {360: 800, 1440: 900}
FORWARD = {3000: ("web", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
if LOCAL:
    WEB, CORE = "http://localhost:3000", "http://localhost:8001"
ONLY = set(filter(None, os.environ.get("LANGS", "").split(",")))  # e.g. LANGS=es,te while fixing; CI checks all


def forward(port: int, target: tuple[str, int]) -> None:
    """localhost:<port> -> a compose service, so the site's API URLs and CORS are as in dev."""
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


def api(method: str, path: str, token: str | None = None, body: dict | None = None):  # type: ignore[no-untyped-def]
    req = urllib.request.Request(f"{CORE}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": "bhojango-i18n-layout",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def phrases(lang: str) -> list[str]:
    """The catalog's own words in this language: each message split at its {placeholders},
    the parts with at least 4 letters (short ones like "min" or "·" match data too). Cuisine
    names are left out: they translate data and appear inside kitchens' names ("... Pizza Kitchen")."""
    data = json.loads((MESSAGES / f"{lang}.json").read_text(encoding="utf-8"))
    data.pop("cuisine_names", None)  # names of data (a kitchen's cuisines), and words in kitchens' names
    out: set[str] = set()

    def walk(v) -> None:  # type: ignore[no-untyped-def]
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, str):
            for part in re.split(r"\{\w+\}", v):
                part = part.strip(" .,:;·•–—-()|/?!¿¡\"'“”«»…")
                if sum(ch.isalpha() for ch in part) >= 4:
                    out.add(part)
    walk(data)
    return sorted(out, key=len, reverse=True)


# What a page shows that doesn't fit, as [kind, tag, text, detail]: run in the page.
FIND = r"""
(phrases) => {
  const W = document.documentElement.clientWidth;
  const found = [];
  const sw = document.documentElement.scrollWidth;
  if (sw > W + 1) found.push(["page", "html", "", `document is ${sw}px wide in a ${W}px window`]);
  const shown = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const srOnly = (el) => { const r = el.getBoundingClientRect(); return r.width <= 1 || r.height <= 1; };
  const scroller = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX;
      if (o === "auto" || o === "scroll") return true;
    }
    return false;
  };
  const words = (el) => (el.innerText || "").replace(/\s+/g, " ").trim();
  // The site's own words: catalog phrases make up at least half of the text (a kitchen called
  // "Ridgeline Pizza Kitchen" contains the word "Kitchen" but is data).
  const catalog = (text) => {
    let rest = text, hit = null;
    for (const p of phrases) {
      if (rest.includes(p)) { hit = hit || p; rest = rest.split(p).join(" "); }
    }
    const letters = (s) => (s.match(/[\p{L}\p{M}]/gu) || []).length;
    return hit && letters(rest) <= letters(text) / 2 ? hit : null;
  };
  const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "svg", "SVG", "IMG", "PICTURE", "VIDEO", "CANVAS", "IFRAME",
    "INPUT", "TEXTAREA", "SELECT", "OPTION", "HTML", "BODY"]);
  for (const el of document.body.querySelectorAll("*")) {
    if (SKIP.has(el.tagName) || el.closest("svg, [aria-hidden=true], .maplibregl-map, .leaflet-container")) continue;
    if (!shown(el) || srOnly(el)) continue;
    const cs = getComputedStyle(el);
    const text = words(el);
    if (!text) continue;
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const clips = cs.overflowX === "hidden" || cs.overflowX === "clip" || cs.textOverflow === "ellipsis";
    const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== "none";
    let kind = null, detail = "";
    if (clips && el.scrollWidth > el.clientWidth + 1) {
      kind = "clipped"; detail = `text ${el.scrollWidth}px in a ${el.clientWidth}px box`;
    } else if ((clamp || cs.overflowY === "hidden" || cs.overflowY === "clip") && ownText && el.scrollHeight > el.clientHeight + 2) {
      kind = "clipped"; detail = `text ${el.scrollHeight}px tall in a ${el.clientHeight}px box`;
    } else if (ownText && cs.display !== "inline" && cs.overflowX === "visible" && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1) {
      kind = "spill"; detail = `text ${el.scrollWidth}px runs past its ${el.clientWidth}px box`;
    } else if (ownText && !scroller(el)) {
      const r = el.getBoundingClientRect();
      if (r.right > W + 1 || r.left < -1) { kind = "off"; detail = `text from ${Math.round(r.left)} to ${Math.round(r.right)}px in a ${W}px window`; }
    }
    if (!kind && (clips || cs.overflowY === "hidden" || cs.overflowY === "clip")
        && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 1)) {
      // A box that clips (a card of fixed height, overflow hidden): a text inside it cut at its edge.
      const box = el.getBoundingClientRect();
      for (const inner of el.querySelectorAll("*")) {
        if (SKIP.has(inner.tagName) || !shown(inner) || srOnly(inner)) continue;
        if (![...inner.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) continue;
        const r = inner.getBoundingClientRect();
        if (r.bottom > box.bottom + 2 || r.top < box.top - 2 || r.right > box.right + 2 || r.left < box.left - 2) {
          const t = words(inner);
          found.push(["clipped", inner.tagName.toLowerCase(), t.slice(0, 80),
            `cut by a ${Math.round(box.width)}x${Math.round(box.height)}px box (overflow hidden)`, catalog(t)]);
          break;
        }
      }
      continue;
    }
    if (!kind) continue;
    const hit = catalog(text);
    found.push([kind, el.tagName.toLowerCase() + (el.getAttribute("data-testid") ? `[data-testid=${el.getAttribute("data-testid")}]` : ""),
      text.slice(0, 80), detail, hit]);
  }
  return found;
}
"""


def main() -> int:
    if LOCAL:
        for port, target in FORWARD.items():
            forward(port, target)
    OUT.mkdir(parents=True, exist_ok=True)
    directory = api("GET", "/markets/directory")
    failures: list[str] = []
    listed: list[str] = []
    checked = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}))
        for country in directory["countries"]:
            live = [c for r in country["regions"] for c in r["cities"] if c["status"] == "live"]
            if not live:
                continue
            city = live[0]
            langs = []
            for loc in country.get("locales") or ["en"]:
                lang = loc.split("-")[0]
                if lang not in langs and (MESSAGES / f"{lang}.json").exists() and (not ONLY or lang in ONLY):
                    langs.append(lang)
            loc = api("GET", f"/markets/locate?lat={city['lat']}&lng={city['lng']}")
            place = {"label": f"{loc.get('zone_name') or city['name']}, {city['name']}", "lat": city["lat"], "lng": city["lng"],
                     "country": country["code"], "city_code": city["code"], "city_path": city["path"],
                     "zone": loc.get("zone_name"), "served": bool(loc.get("served", True))}
            # A kitchen page and a help article: the first links the city and help pages show.
            probe = browser.new_page()
            probe.goto(WEB + city["path"], wait_until="networkidle")
            kitchen = probe.eval_on_selector_all(
                f"a[href^='{city['path']}/']", "els => els.map(e => e.getAttribute('href'))")
            probe.goto(WEB + "/help/orders", wait_until="networkidle")
            article = probe.eval_on_selector_all("a[href^='/help/orders/']", "els => els.map(e => e.getAttribute('href'))")
            probe.close()
            pages = ["/", "/cities", city["path"], *(kitchen[:1]), "/help", "/help/orders", *(article[:1]),
                     "/deliver", "/partner", "/signin", "/terms", "/privacy", "/credits"]
            signed: list[str] = []
            session = None
            if SIGNED_IN:
                short = {"IN-TG-HYD": "hyd", "US-ID-BOI": "boi"}.get(city["code"])
                try:
                    tok = api("POST", "/auth/login", None, {"email": f"customer1.{short}@example.com", "password": SEED_PASSWORD})
                    me = api("GET", "/users/me", tok["access_token"])
                    orders = api("GET", "/orders?limit=5", tok["access_token"])
                    orders = orders.get("items", orders) if isinstance(orders, dict) else orders
                    signed = ["/account/orders", "/account/favourites", "/account/profile", *[f"/orders/{o['id']}" for o in orders[:1]]]
                    session = (me, tok)
                except Exception as e:  # noqa: BLE001
                    print(f"note: {country['code']}: no signed-in pages ({str(e)[:120]})", flush=True)
            for lang in langs:
                words = phrases(lang)
                for width, height in WIDTHS.items():
                    for mode, paths in (("visitor", pages), ("address", ["/"]), ("signed-in", signed)):
                        if not paths:
                            continue
                        ctx = browser.new_context(viewport={"width": width, "height": height})
                        cookies = [{"name": "bg_lang", "value": lang, "url": WEB}, {"name": "bg_city", "value": city["code"], "url": WEB}]
                        if mode != "visitor":
                            cookies.append({"name": "bg_addr", "value": urllib.parse.quote(json.dumps(place)), "url": WEB})
                        ctx.add_cookies(cookies)
                        if mode == "signed-in" and session:
                            me, tok = session
                            ctx.add_init_script(web_session.script(me))
                            ctx.add_cookies(web_session.cookies(CORE, tok["access_token"], tok["refresh_token"]))
                        page = ctx.new_page()
                        for path in paths:
                            page.goto(WEB + path, wait_until="networkidle")
                            page.wait_for_timeout(250)  # web fonts
                            found = page.evaluate(FIND, words)
                            checked += 1
                            label = f"{country['code']} {lang} {width}px {mode} {path}"
                            bad = [f for f in found if f[0] == "page" or f[4]]
                            for f in found:
                                if not (f[0] == "page" or f[4]):
                                    listed.append(f"{label}: {f[0]} {f[1]} \"{f[2]}\" ({f[3]}; data, by design)")
                            name = re.sub(r"[^a-z0-9]+", "-", f"{lang}-{width}-{mode}-{path}".lower()).strip("-")
                            if os.environ.get("SHOT_ALL") == "1" and not bad:
                                page.screenshot(path=str(OUT / f"ok-{name}.png"), full_page=False)
                            if bad:
                                page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
                                for f in bad:
                                    failures.append(f"{label}: {f[0]} {f[1]} \"{f[2]}\" ({f[3]})")
                            print(("FAIL " if bad else "ok   ") + label, flush=True)
                        ctx.close()
        browser.close()
    report = OUT / "i18n-layout.md"
    report.write_text("# Every page, every language, 360 and 1440 px\n\n"
                      + f"{checked} page views, {len(failures)} problems.\n\n"
                      + "".join(f"- FAIL {f}\n" for f in failures)
                      + "".join(f"- note {f}\n" for f in listed[:200]), encoding="utf-8")
    for f in failures:
        print("FAIL", f)
    print(f"{checked} page views; {len(failures)} problems" + (f"; {len(listed)} data texts truncated by design" if listed else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
