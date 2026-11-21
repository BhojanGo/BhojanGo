"""3-D Secure in a real, headed browser: a manual release check (docs/runbooks/stripe-test-mode.md).

Stripe's 3-D Secure challenge is a page from Stripe's test ACS in nested frames inside the
Payment Element. The automated stripe-e2e job completes it in headless Chromium; this check
does it the way a customer sees it, in a visible Chrome window on a developer's machine,
against a stack that takes Stripe's webhooks (tools/stripe_e2e/run.sh in hold mode, whose
`stripe listen` forwards them):

  complete  card 4000 0027 6000 3184, press COMPLETE in Stripe's challenge
            -> the payment succeeds and the order becomes placed (webhook)
  fail      the same card, press FAIL
            -> Stripe says authentication failed; the payment is failed and the order
               stays pending_payment with "try again" offered (can_retry)

  python tools/stripe_e2e/headed_3ds.py --api https://<stack> [--out DIR] [--browser CHROME] [--headless]

Needs Playwright with a Chromium (python -m playwright install chromium) and httpx. Signs in
as the base seed's Boise customer; the publishable key and the PaymentIntent's client secret
come from the stack (POST /payments/initiate), so no Stripe key is needed here. Prints no keys
or secrets. Exits 1 if either path fails.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import re
import sys
import threading
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CUSTOMER, PASSWORD = "customer1.boi@example.com", "BhojanGo123"  # the base seed's fixed test login
KITCHEN_OWNER = "partner.boi@example.com"  # owns Boise Bowl Co. (base seed); same password
CARD = "4000002760003184"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # type: ignore[no-untyped-def]
        pass  # the request line carries the client secret


def _serve() -> tuple[http.server.ThreadingHTTPServer, int]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(HERE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


class Stack:
    def __init__(self, api: str) -> None:
        self.base = api.rstrip("/") + "/api/v1"
        self.c = httpx.Client(timeout=60)
        r = self.c.post(f"{self.base}/auth/login", json={"email": CUSTOMER, "password": PASSWORD})
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def call(self, method: str, path: str, **kw):  # type: ignore[no-untyped-def]
        r = self.c.request(method, f"{self.base}{path}", headers={**self.h, **kw.pop("headers", {})}, **kw)
        r.raise_for_status()
        return r.json()

    def tablet(self, restaurant_id: str) -> None:
        """R27: be Boise Bowl Co.'s tablet while this runs (a kitchen takes orders only while its tablet
        is live): its owner, the base seed's Boise partner, polls the board now and every 15 s."""
        if getattr(self, "_tablet", False):
            return
        board = f"{self.base}/orders/restaurant/{restaurant_id}"

        def signed_in() -> dict:
            r = httpx.post(f"{self.base}/auth/login", json={"email": KITCHEN_OWNER, "password": PASSWORD}, timeout=30)
            r.raise_for_status()
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        h = signed_in()
        httpx.get(board, headers=h, params={"limit": 1}, timeout=30).raise_for_status()
        self._tablet = True

        def poll() -> None:
            headers = h
            while True:
                time.sleep(15)
                try:
                    if httpx.get(board, headers=headers, params={"limit": 1}, timeout=30).status_code == 401:
                        headers = signed_in()
                except Exception:  # noqa: BLE001 - keep beating
                    pass

        threading.Thread(target=poll, daemon=True).start()

    def new_order(self) -> tuple[dict, dict]:
        """A Boise order (2 bowls) waiting for payment, and its Stripe checkout payload."""
        rest = next(r for r in self.call("GET", "/restaurants", params={"limit": 50})["items"] if r["name"] == "Boise Bowl Co.")
        self.tablet(rest["id"])
        menu = self.call("GET", f"/restaurants/{rest['id']}/menu")
        item = next(i["id"] for c in menu["categories"] for i in c["items"] if i["name"] == "Teriyaki Chicken Bowl")
        addr = self.call("GET", "/me/addresses")[0]
        cart = [{"menu_item_id": item, "quantity": 2}]
        q = self.call("POST", "/pricing/quote", json={"restaurant_id": rest["id"], "items": cart,
                                                       "deliver_to": {"address_id": addr["id"]}, "tip": "2"})
        order = self.call("POST", "/orders", headers={"X-Idempotency-Key": str(uuid.uuid4())}, json={
            "restaurant_id": rest["id"], "items": cart, "payment_method": "card", "quote_token": q["token"],
            "delivery_address": {"street": addr.get("street") or "1510 N 13th St", "city": "Boise", "state": "ID",
                                 "zip": addr.get("postal_code") or "83702", "country": "US"}})
        init = self.call("POST", "/payments/initiate", json={"order_id": order["id"], "payment_method_type": "card"})
        assert init["provider"] == "stripe", f"this stack doesn't pay US orders with Stripe ({init['provider']})"
        return order, init["checkout"]

    def wait_status(self, order_id: str, want: str, timeout: float = 120) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            s = self.call("GET", f"/payments/orders/{order_id}/status")
            if s["payment_status"] == want:
                return s
            time.sleep(2)
        raise AssertionError(f"payment_status never became {want} (last: {s['payment_status']}, order {s['order_status']})")


def _challenge(page, press: str, shot: Path):  # type: ignore[no-untyped-def]
    """Wait for Stripe's test challenge (COMPLETE / FAIL buttons), screenshot it, press one."""
    for _ in range(240):
        for f in page.frames:
            try:
                b = f.get_by_role("button", name=re.compile(rf"^{press}$", re.I))
                if b.count() and b.first.is_visible():
                    page.wait_for_timeout(1500)  # the challenge animates in; a click while it loads is lost
                    page.screenshot(path=str(shot))
                    host = re.sub(r"^https://([^/]+)/.*", r"\1", f.url)
                    b.first.click()
                    return host
            except Exception:  # noqa: BLE001 (a frame navigating away)
                pass
        page.wait_for_timeout(500)
    raise AssertionError("Stripe's 3-D Secure challenge didn't appear")


def run(stack: Stack, path: str, out: Path, headless: bool, browser_path: str | None = None) -> str:
    order, c = stack.new_order()
    srv, port = _serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, slow_mo=150,
                                        **({"executable_path": browser_path} if browser_path else {"channel": "chromium"}))
            page = browser.new_page(viewport={"width": 900, "height": 900})
            page.goto(f"http://127.0.0.1:{port}/pay.html?pk={c['publishable_key']}&cs={c['payment_intent_client_secret']}")
            page.wait_for_function("document.getElementById('out').textContent !== 'loading'", timeout=30000)
            card = None
            for _ in range(120):
                card = next((f for f in page.frames if f.locator('input[name="number"]').count()), None)
                if card:
                    break
                page.wait_for_timeout(500)
            assert card, "the Payment Element's card form didn't appear"
            card.locator('input[name="number"]').fill(CARD)
            card.locator('input[name="expiry"]').fill("12 / 34")
            card.locator('input[name="cvc"]').fill("123")
            if card.locator('input[name="postalCode"]').count():
                card.locator('input[name="postalCode"]').fill("83702")
            page.screenshot(path=str(out / f"3ds-{path}-1-card.png"))
            page.click("#pay")
            host = _challenge(page, "complete" if path == "complete" else "fail", out / f"3ds-{path}-2-challenge.png")
            page.wait_for_function("/^(done|error)/.test(document.getElementById('out').textContent)", timeout=60000)
            result = page.inner_text("#out")
            page.screenshot(path=str(out / f"3ds-{path}-3-result.png"))
            browser.close()
    finally:
        srv.shutdown()
    if path == "complete":
        assert result == "done succeeded", result
        s = stack.wait_status(order["id"], "succeeded")
        assert s["order_status"] == "placed", s
        return f"challenge from {host}; Stripe: {result}; order {order['id'][:8]} placed"
    assert result.startswith("error") and "authenticat" in result.lower(), result
    s = stack.wait_status(order["id"], "failed")
    assert s["order_status"] == "pending_payment" and s["can_retry"], s
    return f"challenge from {host}; Stripe: {result}; order {order['id'][:8]} still pending_payment, can_retry"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="the stack's core-api base URL")
    ap.add_argument("--out", default=".", help="where the screenshots go")
    ap.add_argument("--headless", action="store_true", help="no window (the check itself is meant to be headed)")
    ap.add_argument("--browser", help="a Chrome/Chromium executable (default: Playwright's Chromium)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stack = Stack(a.api)
    failed = 0
    for path in ("complete", "fail"):
        try:
            print(f"PASS 3ds-{path}: {run(stack, path, out, a.headless, a.browser)}", flush=True)
        except Exception as e:  # noqa: BLE001 (reported per path)
            failed += 1
            print(f"FAIL 3ds-{path}: {type(e).__name__}: {e}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
