"""Live tracking over a hosted environment's public proxy (Railway QA): the customer's
tracking WebSocket gets the rider's positions, stays open through an idle spell
with no client pings (like the app), and still delivers afterwards.

    python tools/railway/ws_check.py <core url> <realtime url> <logins file> [idle seconds]

Logins: the tab-separated file the QA seed wrote (email in column 3, password in 4).
Places one Hyderabad order with the fake payment and completes it. Prints timings
and counts only.
"""
import asyncio
import json
import sys
import time
import uuid

import httpx
import websockets

CORE, RT, LOGINS = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
IDLE = int(sys.argv[4]) if len(sys.argv) > 4 else 150
PASSWORDS = {r[2]: r[3] for r in (line.rstrip("\n").split("\t") for line in open(LOGINS, encoding="utf-8")) if len(r) == 4}
SPICE_AT = (17.4486, 78.3908)  # Spice Route Kitchen, Madhapur


class Person:
    def __init__(self, client: httpx.AsyncClient, email: str) -> None:
        self.c, self.email, self.token = client, email, ""

    async def login(self) -> "Person":
        for _ in range(12):
            r = await self.c.post(f"{CORE}/api/v1/auth/login", json={"email": self.email, "password": PASSWORDS[self.email]})
            if r.status_code != 429:
                break
            await asyncio.sleep(6)
        r.raise_for_status()
        self.token = r.json()["access_token"]
        return self

    async def call(self, base: str, method: str, path: str, **kw) -> httpx.Response:  # type: ignore[no-untyped-def]
        headers = {"Authorization": f"Bearer {self.token}", **kw.pop("headers", {})}
        return await self.c.request(method, f"{base}/api/v1{path}", headers=headers, **kw)


async def wait_for(pred, timeout: float = 60, every: float = 1.0):  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        v = await pred()
        if v:
            return v
        await asyncio.sleep(every)
    return None


async def main() -> int:
    async with httpx.AsyncClient(timeout=30) as c:
        cust = await Person(c, "customer1.hyd@example.com").login()
        partner = await Person(c, "partner.hyd@example.com").login()
        rider = await Person(c, "rider2.hyd@example.com").login()

        rest = next(r for r in (await cust.call(CORE, "GET", "/restaurants", params={"limit": 50})).json()["items"]
                    if r["name"] == "Spice Route Kitchen")
        menu = (await cust.call(CORE, "GET", f"/restaurants/{rest['id']}/menu")).json()
        item = next(i for cat in menu["categories"] for i in cat["items"]
                    if not any((g.get("min_picks") or 0) > 0 for g in i.get("option_groups") or []))
        cart = [{"menu_item_id": item["id"], "quantity": 2}]
        addr = (await cust.call(CORE, "GET", "/me/addresses")).json()[0]
        q = await cust.call(CORE, "POST", "/pricing/quote", json={"restaurant_id": rest["id"], "items": cart,
                                                                   "deliver_to": {"address_id": addr["id"]}})
        assert q.status_code == 200, q.text
        r = await cust.call(CORE, "POST", "/orders", headers={"X-Idempotency-Key": str(uuid.uuid4())}, json={
            "restaurant_id": rest["id"], "items": cart, "payment_method": "upi", "quote_token": q.json()["token"],
            "delivery_address": {"street": addr.get("street", ""), "city": "Hyderabad", "state": "Telangana",
                                 "zip": addr.get("postal_code") or "500081", "country": "IN"}})
        assert r.status_code == 201, r.text
        oid = r.json()["id"]
        assert (await cust.call(CORE, "POST", "/payments/initiate", json={"order_id": oid, "payment_method_type": "upi"})).status_code == 201

        async def placed():  # type: ignore[no-untyped-def]
            return (await cust.call(CORE, "GET", f"/orders/{oid}")).json()["status"] == "placed"
        assert await wait_for(placed), "the fake payment never placed the order"

        lat, lng = SPICE_AT[0] + 0.003, SPICE_AT[1]
        assert (await rider.call(RT, "POST", "/riders/me/online", json={"lat": lat, "lng": lng})).status_code == 200
        for s in ("accepted", "preparing", "almost_ready"):
            assert (await partner.call(CORE, "PUT", f"/orders/{oid}/status", json={"status": s})).status_code == 200, s

        async def offered():  # type: ignore[no-untyped-def]
            return ((await rider.call(RT, "GET", "/riders/me")).json().get("offer") or {}).get("order_id") == oid
        assert await wait_for(offered, 90), "dispatch never offered the order"
        assert (await rider.call(RT, "POST", f"/offers/{oid}/accept")).status_code == 200

        got: list[float] = []
        url = RT.replace("https://", "wss://").replace("http://", "ws://") + f"/ws/track/{oid}"
        t0 = time.time()
        # ping_interval=None: the app's WebSocket sends no pings; keep-alives must come from the server.
        async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {cust.token}"},
                                      open_timeout=15, ping_interval=None) as ws:
            connect_s = time.time() - t0

            async def pings(n: int) -> None:
                nonlocal lat
                for _ in range(n):
                    lat += 0.0005
                    await rider.call(RT, "POST", "/delivery/driver/location",
                                     json={"lat": lat, "lng": lng, "speed": 7.5, "heading": 0.0, "accuracy": 8.0, "order_id": oid})
                    await asyncio.sleep(1.5)

            async def receive(until: float) -> int:
                n = 0
                while time.time() < until:
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=max(0.1, until - time.time())))
                    except TimeoutError:
                        break
                    if "lat" in json.dumps(msg):
                        n += 1
                        got.append(time.time())
                return n

            sender = asyncio.create_task(pings(4))
            before = await receive(time.time() + 12)
            await sender
            idle_start = time.time()
            idle_msgs = await receive(idle_start + IDLE)  # no positions are sent: nothing should arrive, nothing should drop
            idle_s = time.time() - idle_start
            t_send = time.time()
            sender = asyncio.create_task(pings(2))
            after = await receive(time.time() + 12)
            await sender
            first_after = (got[-after] - t_send) if after else None

        # finish the order so it doesn't linger
        assert (await partner.call(CORE, "PUT", f"/orders/{oid}/status", json={"status": "ready"})).status_code == 200
        assert (await rider.call(CORE, "PUT", f"/orders/{oid}/status", json={"status": "picked_up"})).status_code == 200
        pin = (await cust.call(CORE, "GET", f"/orders/{oid}")).json()["pin"]
        done = await rider.call(CORE, "PUT", f"/orders/{oid}/status", json={"status": "delivered", "proof": {"method": "pin", "pin": pin}})
        await rider.call(RT, "POST", "/riders/me/offline")

    ok = before >= 3 and after >= 1 and idle_s >= IDLE - 1 and done.status_code == 200
    print(json.dumps({"order": oid[:8], "connect_s": round(connect_s, 2), "positions_before_idle": before,
                      "idle_seconds_survived": round(idle_s), "messages_during_idle": idle_msgs,
                      "positions_after_idle": after, "first_after_idle_s": round(first_after, 2) if first_after else None,
                      "order_delivered": done.status_code == 200, "result": "PASS" if ok else "FAIL"}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
