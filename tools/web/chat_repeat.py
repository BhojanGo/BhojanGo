"""The website's "messages: live from the rider without reloading" check, N times in a row.

    tools/web/chat_repeat.sh [N]        (default 50; against `make dev`, seeded)

R7: that e2e check was flaky. Each round here is the e2e's exact sequence on a new
order: the tracking page is open, a rider is assigned, the rider sends "I'm at the
kitchen", the customer replies, then the rider sends "I'm outside." and the page
must show it within the e2e's 15 s without reloading. No retries: one miss fails
the run. Then the order is delivered, which frees the rider for the next round.

Runs in the Playwright image on the compose network (chat_repeat.sh), like
e2e_web.py; local only (tools/target_guard.py refuses hosted targets).
"""
import base64
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
import uuid

from playwright.sync_api import expect, sync_playwright

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "/guard"]
from target_guard import ensure_safe_api  # noqa: E402

ensure_safe_api("http://core-api:8001")

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50
FORWARD = {3000: ("web", 3000), 8001: ("core-api", 8001), 8004: ("realtime", 8004)}
KITCHEN, DISH = "Spice Route Kitchen", "Veg Dum Biryani"


def forward(port: int, target: tuple[str, int]) -> None:
    """localhost:<port> -> the compose service, so the browser's origins are as in dev."""
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


def api(method: str, path: str, token: str | None = None, body: dict | None = None, host: int = 8001,
        headers: dict | None = None) -> dict:
    req = urllib.request.Request(f"http://localhost:{host}/api/v1{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {}),
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def login(email: str, password: str = "BhojanGo123") -> dict:
    from totp_signin import finish  # admins: the second step (seed key)

    return finish(lambda path, data: api("POST", path, None, data), email,
                  api("POST", "/auth/login", None, {"email": email, "password": password}))


def sub(token: str) -> str:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["sub"]


def new_paid_order(token: str) -> str:
    """Two biryanis from the seed's Hyderabad kitchen to Madhapur, paid with the fake provider."""
    rest = next(r for r in api("GET", "/restaurants?limit=50")["items"] if r["name"] == KITCHEN)
    menu = api("GET", f"/restaurants/{rest['id']}/menu")
    item = next(i for c in menu["categories"] for i in c["items"] if i["name"] == DISH)
    cart = [{"menu_item_id": item["id"], "quantity": 2}]
    q = api("POST", "/pricing/quote", token, {"restaurant_id": rest["id"], "items": cart, "deliver_to": {"lat": 17.4483, "lng": 78.3915}})
    order = api("POST", "/orders", token, {
        "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q["token"],
        "delivery_address": {"street": "Flat 302", "city": "Hyderabad", "state": "Telangana", "zip": "500081", "country": "IN"}},
        headers={"X-Idempotency-Key": str(uuid.uuid4())})
    intent = api("POST", "/payments/initiate", token, {"order_id": order["id"], "payment_method_type": "upi"})
    api("POST", f"/payments/fake/{intent['payment_intent_id']}/complete", token, {"outcome": "succeeded"})
    return order["id"]


for port, target in FORWARD.items():
    forward(port, target)

cust = login("customer1.hyd@example.com")
partner = login("partner.hyd@example.com")["access_token"]
ops = login("ops.hyd@example.com", "BhojanGoAdmin1")["access_token"]
rider = login("rider3.hyd@example.com")["access_token"]
me = api("GET", "/users/me", cust["access_token"])
session = json.dumps({"state": {"access": cust["access_token"], "refreshToken": cust["refresh_token"], "user": me}, "version": 0})

passed, failed = 0, []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    ctx.add_init_script(f"if (!localStorage.getItem('bhojango-session')) localStorage.setItem('bhojango-session', {json.dumps(session)});")
    page = ctx.new_page()
    for i in range(1, N + 1):
        t0 = time.monotonic()
        order_id = new_paid_order(cust["access_token"])
        page.goto(f"http://localhost:3000/orders/{order_id}/track", wait_until="networkidle")
        for st in ("accepted", "preparing", "ready"):
            api("PUT", f"/orders/{order_id}/status", partner, {"status": st})
        api("POST", "/delivery/assign", ops, {"order_id": order_id, "driver_id": sub(rider)}, host=8004)
        api("POST", f"/orders/{order_id}/messages", rider, {"preset": "at_kitchen"})
        chat = page.get_by_role("region", name=re.compile("^Your delivery partner, "))
        try:
            # Setup, as in e2e_web.py (same waits).
            expect(chat.get_by_role("button", name="Message")).to_be_visible(timeout=20000)
            chat.get_by_role("button", name="Message").click()
            expect(chat.get_by_text("I'm at the kitchen, waiting for your order.")).to_be_visible(timeout=20000)
            chat.get_by_label("Write a short message").fill("Gate 2, my number is 98480 22334")
            chat.get_by_role("button", name="Send").click()
            expect(chat.get_by_text("Gate 2, my number is •••")).to_be_visible(timeout=10000)
            # The check: live from the rider without reloading, within the e2e's 15 s.
            api("POST", f"/orders/{order_id}/messages", rider, {"preset": "outside"})
            t1 = time.monotonic()
            expect(chat.get_by_text("I'm outside.")).to_be_visible(timeout=15000)
            passed += 1
            print(f"PASS {i}/{N} live from the rider in {time.monotonic() - t1:.2f}s (round {time.monotonic() - t0:.1f}s)", flush=True)
        except Exception as e:  # noqa: BLE001 - recorded; the run fails at the end
            failed.append(i)
            print(f"FAIL {i}/{N} {str(e)[:300]}", flush=True)
            page.screenshot(path=f"/out/chat-fail-{i}.png", full_page=True)
        # Free the rider: picked up and delivered with the door PIN (the customer's order shows it).
        pin = api("GET", f"/orders/{order_id}", cust["access_token"]).get("pin")
        api("PUT", f"/orders/{order_id}/status", rider, {"status": "picked_up"})
        api("PUT", f"/orders/{order_id}/status", rider, {"status": "delivered", "proof": {"method": "pin", "pin": pin}})
    b.close()

print(f"\n{passed}/{N} passed in a row" if not failed else f"\n{passed}/{N} passed; failed rounds: {failed}", flush=True)
sys.exit(1 if failed else 0)
