"""Pilot dress rehearsal: a Boise dinner rush against `make dev`, over the real APIs.

Five kitchens, eight riders, ~150 orders in two hours with a rush in the middle.
Everyone is a bot doing what the apps do:

- customers quote, order, pay (some cards decline: half of those retry, the rest
  walk away and the order times out), watch the tracking WebSocket, sometimes
  cancel before the kitchen accepts, and sometimes report a problem afterwards;
- the kitchen accepts after a short while, cooks 4-9 minutes, marks it ready;
- riders stay online and send GPS every 10 s, take offers (and pass on some),
  ride to the kitchen, pick up, ride to the customer and hand over with the PIN.

Travel is shortened (a few minutes per leg) so eight riders can carry a rush:
the point is two hours of realistic, varied load, not road times.

    tools/soak/run.sh                  # what you run (sets up, samples, reports)
    python tools/soak/soak.py          # in the soak container: SOAK_MINUTES, SOAK_ORDERS, SOAK_OUT
"""
import asyncio
import json
import math
import os
import random
import statistics
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets

CORE = os.environ.get("SOAK_CORE", "http://core-api:8001")
RT = os.environ.get("SOAK_REALTIME", "http://realtime:8004")
MINUTES = float(os.environ.get("SOAK_MINUTES", "120"))
ORDERS = int(os.environ.get("SOAK_ORDERS", "150"))
OUT = os.environ.get("SOAK_OUT", "/out/soak-result.json")
PASSWORD = "BhojanGo123"
# Which seeded city (tools/seed/data.py market keys): Boise (default) or Hyderabad.
CITY_KEY = os.environ.get("SOAK_CITY", "boi")
CITY = {"boi": {"name": "Boise", "state": "ID", "country": "US", "zip": "83702", "tips": ["0", "2", "3", "5"],
                # US customers pay by card (Apple and Google Pay reach Stripe as cards)
                "methods": [("card", 1.0)]},
        "hyd": {"name": "Hyderabad", "state": "Telangana", "country": "IN", "zip": "500081", "tips": ["0", "10", "20", "30"],
                # India: mostly UPI (no fee), then cards and net banking (2%). ("wallet" is the BhojanGo balance.)
                "methods": [("upi", 0.65), ("card", 0.25), ("net_banking", 0.10)]}}[CITY_KEY]
RIDERS = [f"rider{i}.{CITY_KEY}@example.com" for i in range(1, int(os.environ.get("SOAK_RIDERS", "8")) + 1)]
CUSTOMERS = [f"customer{i}.{CITY_KEY}@example.com" for i in range(1, int(os.environ.get("SOAK_CUSTOMERS", "40")) + 1)]

# Behaviour mix (per order unless noted)
P_DECLINE = 0.08        # first card declines
P_RETRY = 0.5           # ... and the customer tries another card
P_CANCEL = 0.04         # customer cancels after paying, before the kitchen accepts
P_PROBLEM = 0.06        # customer reports a problem after delivery
P_PASS = 0.12           # a rider passes on an offer
LEG = (90, 210)         # seconds per ride leg (to the kitchen, to the customer)
PREP = (240, 540)       # kitchen: accept to ready

rnd = random.Random(int(os.environ.get("SOAK_SEED", "42")))
T0 = time.monotonic()


def now() -> float:
    return time.monotonic() - T0


def log(msg: str, **kw: Any) -> None:
    print(json.dumps({"t": round(now(), 1), "msg": msg, **kw}), flush=True)


# ── HTTP with sign-in and token refresh ──────────────────────────────────────

_login_lock = asyncio.Lock()


class Person:
    def __init__(self, http: httpx.AsyncClient, email: str) -> None:
        self.http, self.email = http, email
        self.access = self.refresh = ""
        self.user: dict = {}

    async def login(self) -> None:
        async with _login_lock:  # sign-in is limited to 10/minute: queue, back off on 429
            for _ in range(60):
                r = await self.http.post(f"{CORE}/api/v1/auth/login", json={"email": self.email, "password": PASSWORD})
                if r.status_code != 429:
                    break
                await asyncio.sleep(7)
            r.raise_for_status()
        body = r.json()
        self.access, self.refresh, self.user = body["access_token"], body["refresh_token"], body["user"]

    async def _refresh(self) -> None:
        r = await self.http.post(f"{CORE}/api/v1/auth/refresh", json={"refresh_token": self.refresh})
        if r.status_code == 200:
            self.access, self.refresh = r.json()["access_token"], r.json()["refresh_token"]
        else:
            await self.login()

    async def call(self, base: str, method: str, path: str, **kw: Any) -> httpx.Response:
        if not self.access:
            await self.login()
        for attempt in range(4):
            try:
                r = await self.http.request(method, f"{base}/api/v1{path}",
                                            headers={"Authorization": f"Bearer {self.access}", **kw.pop("headers", {})}, **kw)
            except (httpx.TransportError,) as e:
                stats.transport_errors += 1
                log("transport_error", who=self.email, path=path, error=str(e)[:120])
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 401:
                await self._refresh()
                continue
            if r.status_code >= 500:
                stats.http_5xx += 1
                log("http_5xx", who=self.email, method=method, path=path, status=r.status_code, body=r.text[:200])
            return r
        raise RuntimeError(f"{method} {path}: gave up")

    def core(self, method: str, path: str, **kw: Any) -> Any:
        return self.call(CORE, method, path, **kw)

    def rt(self, method: str, path: str, **kw: Any) -> Any:
        return self.call(RT, method, path, **kw)


# ── Results ──────────────────────────────────────────────────────────────────

@dataclass
class OrderRun:
    n: int
    kitchen: str
    customer: str
    order_id: str = ""
    outcome: str = "started"  # delivered | cancelled_by_customer | payment_abandoned | failed:<why>
    declined_first: bool = False
    retried_card: bool = False
    passes: int = 0
    problem: str = ""
    placed_at: str = ""
    delivered_at: str = ""
    minutes: float | None = None  # placed (paid) -> delivered, from the order's own timestamps
    ws_messages: int = 0
    rider: str = ""                # who delivered it
    rider_pay: float | None = None  # what the offer promised the rider for this order (incl. tip)
    batched: bool = False          # carried with another order (task 43)
    method: str = ""               # how the customer paid
    timeline: list = field(default_factory=list)


@dataclass
class Stats:
    http_5xx: int = 0
    transport_errors: int = 0
    ws_errors: int = 0
    offers_seen: int = 0
    offers_passed: int = 0
    offers_accepted: int = 0
    batch_offers_seen: int = 0
    batches_accepted: int = 0
    location_pings: int = 0


stats = Stats()
runs: list[OrderRun] = []
pins: dict[str, str] = {}            # order id -> PIN the customer reads out (riders ask the customer bot)
customer_of: dict[str, "Person"] = {}  # order id -> customer
done: dict[str, asyncio.Event] = {}  # order id -> set when it reaches an end state
run_of: dict[str, "OrderRun"] = {}   # order id -> its run
shifts: dict[str, list[float]] = {}  # rider -> [online at, offline at] (soak seconds)


# ── Arrival schedule: a dinner rush ──────────────────────────────────────────

def arrival_times(n: int, minutes: float) -> list[float]:
    """n order times over the window: quiet start, a peak around 45-80 % of the
    way through (the 7 pm rush), tapering off."""
    def rate(x: float) -> float:  # x in 0..1
        return 0.35 + 1.4 * math.exp(-((x - 0.6) ** 2) / 0.03)
    xs, cum = [i / 1000 for i in range(1001)], [0.0]
    for i in range(1, len(xs)):
        cum.append(cum[-1] + rate(xs[i]))
    times = []
    for k in range(n):
        target = (k + rnd.random()) / n * cum[-1]
        i = next(j for j, c in enumerate(cum) if c >= target)
        times.append(xs[i] * minutes * 60 * 0.92)  # the last orders still get delivered inside the window
    return sorted(times)


# ── The bots ─────────────────────────────────────────────────────────────────

async def wait_status(p: Person, oid: str, want: set[str], timeout: float) -> str:
    end = now() + timeout
    st = ""
    while now() < end:
        r = await p.core("GET", f"/orders/{oid}")
        if r.status_code == 200:
            st = r.json()["status"]
            if st in want:
                return st
        await asyncio.sleep(3)
    return st


async def track(cust: Person, run: OrderRun, oid: str) -> None:
    """The customer's tracking screen: a WebSocket until the order ends."""
    url = RT.replace("http", "ws", 1) + f"/ws/track/{oid}"
    ev = done[oid]
    while not ev.is_set():
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {cust.access}"},
                                          open_timeout=10, ping_interval=20) as ws:
                while not ev.is_set():
                    try:
                        await asyncio.wait_for(ws.recv(), timeout=5)
                        run.ws_messages += 1
                    except TimeoutError:
                        continue
        except Exception as e:  # noqa: BLE001 - reconnect like the app does
            if ev.is_set():
                break
            stats.ws_errors += 1
            log("ws_error", order=oid, error=str(e)[:120])
            await asyncio.sleep(3)


HOMES: dict[str, tuple[float, float]] = {}  # customer -> home (lat, lng), read at the start


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math

    dlat, dlng = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


async def load_homes() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT u.email, a.lat, a.lng FROM addresses a JOIN users u ON u.id = a.user_id "
                                       "WHERE u.email = ANY(:e) AND a.lat IS NOT NULL"), {"e": CUSTOMERS})
        for email, lat, lng in rows:
            HOMES.setdefault(email, (float(lat), float(lng)))
    await engine.dispose()


async def place_and_follow(n: int, at: float, people: dict, kitchens: list[dict], http: httpx.AsyncClient) -> None:
    await asyncio.sleep(max(0.0, at - now()))
    kitchen = rnd.choices(kitchens, weights=[k["weight"] for k in kitchens])[0]
    email = rnd.choice(CUSTOMERS)
    # Hyderabad's kitchens are 15 km apart with a 5 km radius: if this one doesn't deliver to the
    # customer's home, they order from one that does (Boise: every kitchen reaches every home).
    home = HOMES.get(email)
    if home and km(home, (kitchen["lat"], kitchen["lng"])) > kitchen["radius_km"] * 0.95:
        near = [k for k in kitchens if km(home, (k["lat"], k["lng"])) <= k["radius_km"] * 0.95]
        if near:
            kitchen = rnd.choices(near, weights=[k["weight"] for k in near])[0]
    cust = people.setdefault(email, Person(http, email))
    run = OrderRun(n=n, kitchen=kitchen["name"], customer=email)
    runs.append(run)
    try:
        await order_flow(run, cust, kitchen, people["partner"])
    except Exception as e:  # noqa: BLE001 - one broken order mustn't stop the rehearsal
        run.outcome = f"failed:{type(e).__name__}: {str(e)[:160]}"
        log("order_failed", n=n, order=run.order_id, error=str(e)[:200])
    finally:
        if run.order_id in done:
            done[run.order_id].set()


async def order_flow(run: OrderRun, cust: Person, kitchen: dict, partner: Person) -> None:
    # Basket: random items until the kitchen's minimum is met.
    cart: dict[str, int] = {}
    total = 0.0
    while total < kitchen["min"] + rnd.uniform(0, 12):
        item = rnd.choice(kitchen["items"])
        cart[item["id"]] = cart.get(item["id"], 0) + 1
        total += item["price"]
    items = [{"menu_item_id": k, "quantity": v} for k, v in cart.items()]
    if not cust.access:
        await cust.login()
    addr = (await cust.core("GET", "/me/addresses")).json()[0]
    tip = rnd.choice(CITY["tips"])
    method = rnd.choices([m for m, _ in CITY["methods"]], weights=[w for _, w in CITY["methods"]])[0]
    run.method = method
    for _ in range(4):  # a zone minimum above the kitchen's: add something, as the app asks
        r = await cust.core("POST", "/pricing/quote", json={"restaurant_id": kitchen["id"], "items": items,
                                                           "deliver_to": {"address_id": addr["id"]}, "tip": tip})
        if r.status_code == 422 and "minimum order" in r.text:
            item = rnd.choice(kitchen["items"])
            cart[item["id"]] = cart.get(item["id"], 0) + 1
            items = [{"menu_item_id": k, "quantity": v} for k, v in cart.items()]
            continue
        break
    if r.status_code != 200:
        raise RuntimeError(f"quote {r.status_code} {r.text[:120]}")
    q = r.json()
    r = await cust.core("POST", "/orders", headers={"X-Idempotency-Key": str(uuid.uuid4())}, json={
        "restaurant_id": kitchen["id"], "items": items, "payment_method": method, "quote_token": q["token"],
        "delivery_address": {"street": addr.get("street", ""), "city": CITY["name"], "state": CITY["state"],
                             "zip": addr.get("postal_code") or CITY["zip"], "country": CITY["country"]}})
    if r.status_code != 201:
        raise RuntimeError(f"order {r.status_code} {r.text[:120]}")
    oid = run.order_id = r.json()["id"]
    run_of[oid] = run
    done[oid] = asyncio.Event()
    customer_of[oid] = cust
    run.timeline.append(("ordered", round(now())))

    # Pay. Some cards decline; half of those customers try another card.
    if rnd.random() < P_DECLINE:
        run.declined_first = True
        await cust.core("POST", "/payments/initiate", json={"order_id": oid, "payment_method_type": method,
                                                            "payment_method_id": "pm_card_decline"})
        await asyncio.sleep(rnd.uniform(5, 20))
        if rnd.random() >= P_RETRY:
            run.outcome = "payment_abandoned"  # the payment timeout cancels it
            st = await wait_status(cust, oid, {"cancelled"}, timeout=30 * 60)
            run.timeline.append((f"abandoned->{st}", round(now())))
            return
        run.retried_card = True
    r = await cust.core("POST", "/payments/initiate", json={"order_id": oid, "payment_method_type": method})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"pay {r.status_code} {r.text[:120]}")
    st = await wait_status(cust, oid, {"placed"}, timeout=120)
    if st != "placed":
        raise RuntimeError(f"payment never placed the order (status {st})")
    run.timeline.append(("placed", round(now())))
    tracker = asyncio.create_task(track(cust, run, oid))

    # Some customers change their mind before the kitchen accepts.
    if rnd.random() < P_CANCEL:
        await asyncio.sleep(rnd.uniform(5, 25))
        r = await cust.core("POST", f"/orders/{oid}/cancel", json={"reason": "customer_cancelled", "note": "soak"})
        if r.status_code == 200:
            run.outcome = "cancelled_by_customer"
            run.timeline.append(("cancelled", round(now())))
            done[oid].set()
            await tracker
            return
        log("cancel_refused", order=oid, status=r.status_code, body=r.text[:120])

    # The kitchen.
    await asyncio.sleep(rnd.uniform(20, 75))
    for s in ("accepted", "preparing"):
        r = await partner.core("PUT", f"/orders/{oid}/status", json={"status": s})
        if r.status_code != 200:
            raise RuntimeError(f"kitchen {s}: {r.status_code} {r.text[:120]}")
    run.timeline.append(("accepted", round(now())))
    prep = rnd.uniform(*PREP)
    await asyncio.sleep(prep * 0.6)
    r = await partner.core("PUT", f"/orders/{oid}/status", json={"status": "almost_ready"})
    if r.status_code != 200:
        raise RuntimeError(f"kitchen almost_ready: {r.status_code} {r.text[:120]}")
    await asyncio.sleep(prep * 0.4)
    r = await partner.core("PUT", f"/orders/{oid}/status", json={"status": "ready"})
    if r.status_code != 200:
        raise RuntimeError(f"kitchen ready: {r.status_code} {r.text[:120]}")
    run.timeline.append(("ready", round(now())))

    # The rider bot takes it from here; wait for the hand-over.
    end = now() + 60 * 60
    while now() < end and not done[oid].is_set():
        if not pins.get(oid):
            r = await cust.core("GET", f"/orders/{oid}")
            if r.status_code == 200 and r.json().get("pin"):
                pins[oid] = r.json()["pin"]
        o = (await cust.core("GET", f"/orders/{oid}")).json()
        if o["status"] == "delivered":
            run.outcome = "delivered"
            break
        if o["status"] == "cancelled":
            run.outcome = f"failed:cancelled ({o.get('cancellation_reason')})"
            break
        await asyncio.sleep(5)
    else:
        if not run.outcome.startswith(("delivered", "failed")):
            run.outcome = "failed:not delivered within an hour of ready"
    done[oid].set()
    await tracker
    if run.outcome != "delivered":
        return
    o = (await cust.core("GET", f"/orders/{oid}")).json()
    at = {h["status"]: h["at"] for h in o.get("status_history") or []}
    run.placed_at, run.delivered_at = o.get("placed_at") or at.get("placed", ""), at.get("delivered", "")
    try:
        t1 = datetime.fromisoformat(run.placed_at)
        t2 = datetime.fromisoformat(run.delivered_at)
        run.minutes = round((t2 - t1).total_seconds() / 60, 1)
    except ValueError:
        pass
    run.timeline.append(("delivered", round(now())))

    # Afterwards: a few customers report a problem (small ones auto-refund, the rest become tickets).
    if rnd.random() < P_PROBLEM:
        await asyncio.sleep(rnd.uniform(10, 60))
        line = rnd.choice(o["items"])
        r = await cust.core("POST", f"/orders/{oid}/problems", json={
            "items": [{"menu_item_id": line["menu_item_id"], "quantity": 1}],
            "reason": rnd.choice(["missing_item", "wrong_item", "quality", "damaged_in_transit"]), "note": "soak"})
        run.problem = r.json().get("outcome", f"error {r.status_code}") if r.status_code == 201 else f"error {r.status_code}: {r.text[:100]}"


async def rider_bot(p: Person, home: tuple[float, float], stop: asyncio.Event) -> None:
    """One rider for the whole shift: online, pings, offers, deliveries."""
    await p.login()
    lat, lng = home[0] + rnd.uniform(-0.01, 0.01), home[1] + rnd.uniform(-0.01, 0.01)
    r = await p.rt("POST", "/riders/me/online", json={"lat": lat, "lng": lng})
    if r.status_code != 200:
        log("rider_online_failed", rider=p.email, status=r.status_code, body=r.text[:160])
        return
    last_ping = 0.0
    seen: set[str] = set()
    shifts[p.email] = [now(), now()]

    async def ping(order_id: str | None = None) -> None:
        nonlocal last_ping
        body: dict = {"lat": lat, "lng": lng, "speed": 7.5, "heading": 90.0, "accuracy": 8.0}
        if order_id:
            body["order_id"] = order_id
        await p.rt("POST", "/delivery/driver/location", json=body)
        stats.location_pings += 1
        last_ping = now()

    async def ride(order_id: str, seconds: float) -> None:
        nonlocal lat, lng
        end = now() + seconds
        while now() < end:
            lat += rnd.uniform(-0.0008, 0.0008)
            lng += rnd.uniform(-0.0008, 0.0008)
            await ping(order_id)
            await asyncio.sleep(10)

    while not stop.is_set():
        if now() - last_ping > 10:
            await ping()
        me = (await p.rt("GET", "/riders/me")).json()
        offer = me.get("offer") or {}
        oid = offer.get("order_id")
        if oid and oid not in seen:
            seen.add(oid)
            stats.offers_seen += 1
            batch = [b["order_id"] for b in offer.get("batch") or []]
            if len(batch) > 1:
                stats.batch_offers_seen += 1
            await asyncio.sleep(rnd.uniform(2, 12))  # reads the offer card
            if rnd.random() < P_PASS:
                await p.rt("POST", f"/offers/{oid}/pass")
                stats.offers_passed += 1
                for run in runs:
                    if run.order_id == oid:
                        run.passes += 1
                continue
            r = await p.rt("POST", f"/offers/{oid}/accept")
            if r.status_code != 200:
                log("accept_failed", rider=p.email, order=oid, status=r.status_code)
                continue
            stats.offers_accepted += 1
            carrying = (r.json().get("batch") or [oid])
            pays = {b["order_id"]: b.get("rider_pay") for b in offer.get("batch") or []} or {oid: offer.get("rider_pay")}
            if len(carrying) > 1:
                stats.batches_accepted += 1
            for o in carrying:
                run = run_of.get(o)
                if run:
                    run.rider, run.batched = p.email, len(carrying) > 1
                    run.rider_pay = float(pays[o]) if pays.get(o) is not None else None
            try:
                await deliver(p, carrying, ride)
            except Exception as e:  # noqa: BLE001
                log("delivery_failed", rider=p.email, orders=carrying, error=str(e)[:200])
            continue
        await asyncio.sleep(2)
    shifts[p.email][1] = now()
    await p.rt("POST", "/riders/me/offline")


async def deliver(p: Person, orders: list[str], ride: Any) -> None:
    """One order, or a batch from one kitchen: pick everything up at the counter,
    then each drop-off in the order realtime gave (the rider app does the same)."""
    lead = orders[0]
    await ride(lead, rnd.uniform(*LEG))  # to the kitchen
    live = list(orders)
    for o in orders:
        for _ in range(240):  # wait at the counter until it's ready
            st = (await p.core("GET", f"/orders/{o}")).json()["status"]
            if st in ("ready", "cancelled"):
                break
            await ride(lead, 10)
        if st == "cancelled":
            live.remove(o)
            continue
        r = await p.core("PUT", f"/orders/{o}/status", json={"status": "picked_up"})
        if r.status_code != 200:
            raise RuntimeError(f"picked_up {r.status_code} {r.text[:120]}")
    for i, o in enumerate(live):
        await ride(o, rnd.uniform(*LEG) * (1 if i == 0 else 0.5))  # the next drop-off is close by
        for _ in range(30):
            if pins.get(o):
                break
            await asyncio.sleep(2)
        r = await p.core("PUT", f"/orders/{o}/status", json={"status": "delivered", "proof": {"method": "pin", "pin": pins.get(o, "")}})
        if r.status_code != 200:
            raise RuntimeError(f"delivered {r.status_code} {r.text[:120]}")


async def main() -> None:
    limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
    async with httpx.AsyncClient(timeout=30, limits=limits) as http:
        partner = Person(http, f"partner.{CITY_KEY}@example.com")
        await partner.login()
        people: dict = {"partner": partner}
        # The city's five kitchens and their menus.
        lst = (await partner.core("GET", "/restaurants", params={"limit": 100})).json()["items"]
        kitchens = []
        for k in lst:
            if k.get("city") != CITY["name"] or not k.get("is_active", True) or k.get("status") == "pending_approval":
                continue
            menu = (await partner.core("GET", f"/restaurants/{k['id']}/menu")).json()
            # Dishes that need a choice (a size, a spice level) are left out: the bot doesn't choose.
            items = [{"id": i["id"], "price": float(i["price"])} for c in menu["categories"] for i in c["items"]
                     if i.get("is_available", True) and not any((g.get("min_picks") or 0) > 0 for g in i.get("option_groups") or [])]
            kitchens.append({"id": k["id"], "name": k["name"], "min": float(k.get("minimum_order_amount") or 0),
                             "lat": k["lat"], "lng": k["lng"], "items": items, "weight": 1.0,
                             "radius_km": float(k.get("delivery_radius_km") or 5)})
        kitchens = [k for k in kitchens if k["items"]][:5]
        for k, w in zip(kitchens, [1.4, 1.0, 1.2, 1.1, 0.8]):
            k["weight"] = w
        log("kitchens", names=[k["name"] for k in kitchens], items=[len(k["items"]) for k in kitchens])
        await load_homes()
        log("homes", customers=len(HOMES))
        assert len(kitchens) == 5, f"expected 5 {CITY['name']} kitchens, got {len(kitchens)}"

        stop = asyncio.Event()
        riders = [asyncio.create_task(rider_bot(Person(http, e), (kitchens[i % 5]["lat"], kitchens[i % 5]["lng"]), stop))
                  for i, e in enumerate(RIDERS)]
        await asyncio.sleep(60)  # riders sign in (rate-limited) and go online
        times = arrival_times(ORDERS, MINUTES)
        log("schedule", orders=len(times), first=round(times[0]), last=round(times[-1]))
        orders = [asyncio.create_task(place_and_follow(i + 1, 60 + t, people, kitchens, http)) for i, t in enumerate(times)]
        # Everything in flight gets until the end of the window plus 20 minutes to finish.
        await asyncio.wait(orders, timeout=max(60.0, MINUTES * 60 + 20 * 60 - now()))
        stop.set()
        await asyncio.wait(riders, timeout=120)
        for t in orders:
            t.cancel()

    write_result()


def riders_summary(delivered: list[OrderRun]) -> dict:
    """Utilisation and pay: orders per rider per hour online, and pay per order and per hour."""
    hours = {r: max(1e-9, (b - a) / 3600) for r, (a, b) in shifts.items()}
    total_h = sum(hours.values())
    per = {r: sum(1 for x in delivered if x.rider == r) for r in shifts}
    pay = [x.rider_pay for x in delivered if x.rider_pay is not None]
    batched = [x for x in delivered if x.batched]
    solo = [x for x in delivered if not x.batched]

    def avg_pay(rs: list[OrderRun]) -> float | None:
        v = [x.rider_pay for x in rs if x.rider_pay is not None]
        return round(sum(v) / len(v), 2) if v else None

    return {
        "riders": len(shifts), "rider_hours": round(total_h, 2),
        "orders_per_rider_hour": round(len(delivered) / total_h, 2) if total_h else None,
        "orders_per_rider": {"min": min(per.values(), default=0), "median": statistics.median(per.values()) if per else 0,
                             "max": max(per.values(), default=0)},
        "pay_per_rider_hour": round(sum(pay) / total_h, 2) if total_h and pay else None,
        "pay_per_order": avg_pay(delivered), "orders_batched": len(batched),
        "pay_per_order_batched": avg_pay(batched), "pay_per_order_solo": avg_pay(solo),
        "minutes_batched": statistics.median([x.minutes for x in batched if x.minutes is not None] or [0]) if batched else None,
        "minutes_solo": statistics.median([x.minutes for x in solo if x.minutes is not None] or [0]) if solo else None,
    }


def write_result() -> None:
    delivered = [r for r in runs if r.outcome == "delivered"]
    paid = [r for r in runs if r.outcome not in ("payment_abandoned",) and r.order_id]
    mins = [r.minutes for r in delivered if r.minutes is not None]
    counts: dict[str, int] = {}
    for r in runs:
        key = r.outcome.split(":")[0] if r.outcome.startswith("failed") else r.outcome
        counts[key] = counts.get(key, 0) + 1
    summary = {
        "finished_at": datetime.now(UTC).isoformat(), "minutes": MINUTES, "orders_scheduled": ORDERS,
        "orders_started": len(runs), "outcomes": counts,
        "completion_rate": round(len(delivered) / max(1, len([r for r in paid if r.outcome != "cancelled_by_customer"])), 4),
        "delivery_minutes": {"median": statistics.median(mins) if mins else None,
                             "p90": statistics.quantiles(mins, n=10)[-1] if len(mins) >= 10 else None,
                             "max": max(mins) if mins else None},
        "declined_first": sum(r.declined_first for r in runs), "retried_card": sum(r.retried_card for r in runs),
        "problems": {v: sum(1 for r in runs if r.problem == v) for v in {r.problem for r in runs if r.problem}},
        "stats": asdict(stats),
        "riders": riders_summary(delivered),
        "failures": [{"n": r.n, "order": r.order_id, "outcome": r.outcome, "timeline": r.timeline}
                     for r in runs if r.outcome.startswith("failed") or r.outcome == "started"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"summary": summary, "orders": [asdict(r) for r in runs]}, f, indent=1)
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except BaseException:
        write_result()  # whatever happened, keep what was measured
        raise
