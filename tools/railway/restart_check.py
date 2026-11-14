"""Restart each QA service once and check nothing is lost: the order, the session
(refresh tokens live in Redis), and events queued while the worker was down (the
outbox relay runs in the worker; the customer's tracking WebSocket gets them).

    python tools/railway/restart_check.py <core url> <realtime url> <web url> <admin url> <logins file> <railway command...>

The railway command restarts a service: `<command> restart --service <name> --yes --json`.
Prints timings and results only.
"""
import asyncio
import json
import subprocess
import sys
import time
import uuid

import httpx
import websockets

CORE, RT, WEB, ADMIN, LOGINS = (a.rstrip("/") for a in sys.argv[1:6])
RAILWAY = sys.argv[6:]
PASSWORDS = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in open(LOGINS, encoding="utf-8")) if len(r) == 4}
ORDER = ["postgres", "redis", "core-api", "realtime", "worker", "web", "admin"]
# The order moves one step during each backend's restart; each event must reach the customer.
# (Realtime keeps no backlog for a socket that's down with it; the app refetches on reconnect,
# so its restart checks that the socket reconnects.)
STEPS = {"postgres": "accepted", "redis": "preparing", "core-api": "almost_ready", "worker": "ready"}
messages: list[tuple[float, str]] = []


async def login(c: httpx.AsyncClient, email: str) -> dict:
    for _ in range(12):
        r = await c.post(f"{CORE}/api/v1/auth/login", json={"email": email, "password": PASSWORDS[email]})
        if r.status_code != 429:
            break
        await asyncio.sleep(6)
    r.raise_for_status()
    return r.json()


async def until_ok(c: httpx.AsyncClient, url: str, timeout: float = 300) -> float:
    """Seconds until url answers 200 (after the restart has had a moment to begin)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if (await c.get(url, timeout=10)).status_code == 200:
                return time.time() - t0
        except httpx.HTTPError:
            pass
        await asyncio.sleep(2)
    raise TimeoutError(url)


async def tracker(oid: str, token: dict, stop: asyncio.Event) -> None:
    """The customer's tracking screen: reconnects like the app if realtime restarts."""
    url = RT.replace("https://", "wss://") + f"/ws/track/{oid}"
    while not stop.is_set():
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token['access']}"},
                                          open_timeout=15, ping_interval=None) as ws:
                while not stop.is_set():
                    try:
                        messages.append((time.time(), await asyncio.wait_for(ws.recv(), timeout=2)))
                    except TimeoutError:
                        continue
        except Exception:  # noqa: BLE001 - reconnect
            await asyncio.sleep(2)


async def main() -> int:
    results: dict = {}
    async with httpx.AsyncClient(timeout=30) as c:
        cust = await login(c, "customer2.hyd@example.com")
        partner = await login(c, "partner.hyd@example.com")
        tok = {"access": cust["access_token"], "refresh": cust["refresh_token"]}
        H = lambda: {"Authorization": f"Bearer {tok['access']}"}  # noqa: E731
        P = {"Authorization": f"Bearer {partner['access_token']}"}

        rest = next(r for r in (await c.get(f"{CORE}/api/v1/restaurants", params={"limit": 50})).json()["items"]
                    if r["name"] == "Curry Leaf" or r["name"] == "Spice Route Kitchen")
        menu = (await c.get(f"{CORE}/api/v1/restaurants/{rest['id']}/menu")).json()
        item = next(i for cat in menu["categories"] for i in cat["items"]
                    if not any((g.get("min_picks") or 0) > 0 for g in i.get("option_groups") or []))
        cart = [{"menu_item_id": item["id"], "quantity": 2}]
        addr = (await c.get(f"{CORE}/api/v1/me/addresses", headers=H())).json()[0]
        q = await c.post(f"{CORE}/api/v1/pricing/quote", headers=H(), json={"restaurant_id": rest["id"], "items": cart,
                                                                            "deliver_to": {"address_id": addr["id"]}})
        q.raise_for_status()
        o = await c.post(f"{CORE}/api/v1/orders", headers={**H(), "X-Idempotency-Key": str(uuid.uuid4())}, json={
            "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
            "delivery_address": {"street": addr.get("street", ""), "city": "Hyderabad", "state": "Telangana",
                                 "zip": addr.get("postal_code") or "500081", "country": "IN"}})
        o.raise_for_status()
        oid = o.json()["id"]
        (await c.post(f"{CORE}/api/v1/payments/initiate", headers=H(), json={"order_id": oid, "payment_method_type": "upi"})).raise_for_status()
        for _ in range(30):
            if (await c.get(f"{CORE}/api/v1/orders/{oid}", headers=H())).json()["status"] == "placed":
                break
            await asyncio.sleep(1)
        before = (await c.get(f"{CORE}/api/v1/orders/{oid}", headers=H())).json()
        stop = asyncio.Event()
        track = asyncio.create_task(tracker(oid, tok, stop))
        await asyncio.sleep(3)

        health = {"core-api": f"{CORE}/health/ready", "realtime": f"{RT}/health/ready", "web": f"{WEB}/",
                  "admin": f"{ADMIN}/login", "postgres": f"{CORE}/health/ready", "redis": f"{CORE}/health/ready",
                  "worker": f"{CORE}/health/ready"}
        for svc in ORDER:
            t0 = time.time()
            # no stdin and --json: otherwise the CLI waits on the terminal and never returns
            out = subprocess.run([*RAILWAY, "restart", "--service", svc, "--yes", "--json"], capture_output=True,
                                 text=True, stdin=subprocess.DEVNULL, timeout=120)
            row: dict = {"restart_cmd_ok": out.returncode == 0, "restart_error": out.stderr.strip()[-160:] or None}
            step = STEPS.get(svc)
            if step:
                # During the restart the kitchen moves the order on (retrying while the API is down).
                # The event goes outbox → worker's relay → Redis stream → realtime → this
                # customer's tracking socket; it must arrive however the restart falls.
                await asyncio.sleep(2)
                t_evt, accepted = time.time(), None
                while time.time() - t_evt < 240:
                    try:
                        r = await c.put(f"{CORE}/api/v1/orders/{oid}/status", headers=P, json={"status": step})
                        if r.status_code == 200:
                            accepted = time.time()
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(2)
                row["status_change_after_s"] = round(accepted - t_evt, 1) if accepted else None
                got = None
                while accepted and time.time() - t_evt < 300 and got is None:
                    got = next((t for t, m in messages if t >= t_evt and f'"{step}"' in m), None)
                    await asyncio.sleep(1)
                row["event_delivered_after_s"] = round(got - t_evt, 1) if got else None
            await asyncio.sleep(15)  # let the restart take the old container down
            row["healthy_after_s"] = round(await until_ok(c, health[svc]) + 15, 1)
            # nothing lost: the order, and the session (refresh rotates the pair)
            cur = (await c.get(f"{CORE}/api/v1/orders/{oid}", headers=H()))
            row["order_kept"] = cur.status_code == 200 and cur.json()["id"] == oid and cur.json()["total"] == before["total"]
            r = await c.post(f"{CORE}/api/v1/auth/refresh", json={"refresh_token": tok["refresh"]})
            row["session_refreshed"] = r.status_code == 200
            if r.status_code == 200:
                tok.update(access=r.json()["access_token"], refresh=r.json()["refresh_token"])
            # realtime: the worker's step comes after it, so that event arriving means the socket reconnected
            row["total_s"] = round(time.time() - t0, 1)
            results[svc] = row
            print(svc, json.dumps(row), flush=True)
        stop.set()
        await asyncio.gather(track, return_exceptions=True)
        final = (await c.get(f"{CORE}/api/v1/orders/{oid}", headers=H())).json()["status"]
        ops = await login(c, "ops.hyd@example.com")  # tidy up: ops cancels it, as the e2e scripts do
        await c.post(f"{CORE}/api/v1/orders/{oid}/cancel", headers={"Authorization": f"Bearer {ops['access_token']}"},
                     json={"reason": "other", "note": "restart check"})
    ok = all(r["restart_cmd_ok"] and r["order_kept"] and r["session_refreshed"] for r in results.values()) \
        and all(results[s].get("event_delivered_after_s") is not None for s in STEPS) and final == STEPS["worker"]
    print(json.dumps({"order": oid[:8], "final_status": final, "ws_messages": len(messages), "result": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
