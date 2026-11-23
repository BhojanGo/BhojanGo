"""Production build smoke test (R9 item 8): web and admin built with APP_ENV=production.

Runs inside mcr.microsoft.com/playwright/python on the compose network
(tools/web/prod_smoke.sh, the "Production build smoke" workflow), against the
stack started with infra/docker/compose.prod-smoke.yaml on top of compose.yaml:
the same `next start` images as the end-to-end run, but built for production.

What it checks, on the key pages of each app:
- the page answers 200 (an unknown URL answers 404 with the branded not-found page);
- no "Test site" banner, and no "Draft: pending legal review" banner on Terms and Privacy
  (the seed's documents are published);
- the security headers (CSP, X-Frame-Options, nosniff, Referrer-Policy, HSTS,
  Permissions-Policy, COOP); the website is indexable (no X-Robots-Tag noindex,
  robots.txt allows crawling), the admin console never is;
- no console errors and no uncaught page errors.
"""
import os
import re
import socket
import sys
import threading

from playwright.sync_api import sync_playwright

FORWARD = {3000: ("web", 3000), 3001: ("admin", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
results: list[tuple[str, bool, str]] = []
HEADERS = ["content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy",
           "strict-transport-security", "permissions-policy", "cross-origin-opener-policy"]
WEB_PAGES = ["/", "/cities", "/in/hyderabad", "/in/hyderabad/spice-route-kitchen-madhapur", "/signin", "/partner",
             "/deliver", "/help", "/help/delivery/delivery-pin", "/terms?country=IN", "/privacy?country=US"]
TEST_BANNER = "Test site: demo restaurants, no real orders or payments"
DRAFT_BANNER = "Draft: pending legal review"


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


def check(name: str, ok: bool, why: object = "") -> None:
    results.append((name, ok, "" if ok else str(why)[:400]))
    print("PASS" if ok else "FAIL", name, "" if ok else str(why)[:400], flush=True)


def visit(page, url: str, expect_status: int, errors: list[str]):  # type: ignore[no-untyped-def]
    errors.clear()
    r = page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(500)
    check(f"{url}: answers {expect_status}", r is not None and r.status == expect_status, r.status if r else "no response")
    return r


for port, target in FORWARD.items():
    forward(port, target)

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(f"console {m.text[:200]}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror {str(e)[:200]}"))

    web = "http://localhost:3000"
    for path in WEB_PAGES:
        r = visit(page, web + path, 200, errors)
        body = page.inner_text("body")
        check(f"web {path}: no test-site banner", TEST_BANNER not in body and page.get_by_test_id("test-site-banner").count() == 0)
        if path.startswith(("/terms", "/privacy")):
            check(f"web {path}: the published document, no draft banner",
                  DRAFT_BANNER not in body and page.get_by_test_id("legal-draft-banner").count() == 0
                  and page.get_by_test_id("legal-document").count() == 1, body[:200])
        if r is not None:
            h = r.all_headers()
            missing = [k for k in HEADERS if not h.get(k)]
            check(f"web {path}: security headers", not missing, f"missing {missing}")
            check(f"web {path}: indexable (no X-Robots-Tag noindex)", "noindex" not in (h.get("x-robots-tag") or ""), h.get("x-robots-tag"))
        check(f"web {path}: no console errors", not errors, errors[:5])

    r = visit(page, web + "/no-such-page", 404, errors)
    check("web 404: the branded not-found page (site header, title, ways on)",
          page.locator("header").count() > 0 and page.get_by_role("heading", level=1).filter(has_text="We can't find that page").count() == 1
          and page.get_by_role("link", name=re.compile("home", re.I)).count() > 0, page.inner_text("body")[:200])
    check("web 404: no test-site banner", page.get_by_test_id("test-site-banner").count() == 0)
    check("web 404: no console errors (other than the 404 itself)", not [e for e in errors if "404" not in e], errors[:5])

    robots = page.request.get(web + "/robots.txt").text()
    check("web robots.txt: crawlers allowed in production", not re.search(r"(?m)^Disallow: /$", robots), robots[:200])

    admin = "http://localhost:3001"
    r = visit(page, admin + "/login", 200, errors)
    check("admin /login: the sign-in form", page.get_by_role("button", name=re.compile("sign in|continue", re.I)).count() > 0, page.inner_text("body")[:200])
    check("admin /login: no test-site banner", TEST_BANNER not in page.inner_text("body"))
    if r is not None:
        h = r.all_headers()
        missing = [k for k in HEADERS if not h.get(k)]
        check("admin /login: security headers", not missing, f"missing {missing}")
        check("admin /login: never indexed (X-Robots-Tag noindex)", "noindex" in (h.get("x-robots-tag") or ""), h.get("x-robots-tag"))
    check("admin /login: no console errors", not errors, errors[:5])
    page.screenshot(path=f"{os.environ.get('OUT', '/out')}/admin-login.png")
    page.goto(web + "/", wait_until="networkidle")
    page.screenshot(path=f"{os.environ.get('OUT', '/out')}/web-landing.png", full_page=True)
    b.close()

failed = [n for n, ok, _ in results if not ok]
print(f"{len(results) - len(failed)}/{len(results)} passed" + (f"; failed: {failed}" if failed else ""))
sys.exit(1 if failed else 0)
