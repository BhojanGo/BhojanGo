"""The demo rider simulator (make dev and QA only; app/demo_sim/rules.py says when).

Every few seconds, for each demo city (its pool of simulator riders
rider.sim.<key>.<n>@example.com from tools/seed/demo.py), it plays the people
around the demo customer's order on its way, through the same APIs their apps
use, so every business rule, event, notification, tracking update and ETA
happens as it would for real:

- the demo customer (demo1.<key>) orders one of their past orders again
  (POST /orders/{id}/reorder, /pricing/quote, /orders, /payments/initiate) a few
  minutes after the last one arrived;
- the kitchen's owner accepts it, cooks, marks it almost ready (dispatch starts)
  and ready when the rider walks in (PUT /orders/{id}/status);
- one of the city's simulator riders who is free goes online near the kitchen,
  accepts the offer realtime makes (/riders/me, /offers/{id}/accept), rides to
  the kitchen and on to the customer's door at 18-25 km/h, a GPS fix every 4 s
  to realtime's /delivery/driver/location, picks up and delivers with the PIN
  the customer reads from their tracking screen, then goes offline.

Riders: the simulator has a pool of its own per city (users.dispatch_pool
"demo_sim", which only the demo seed writes). Before the kitchen makes an order
almost ready, the simulator marks it in realtime (signed POST
/internal/dispatch/pool-orders), and realtime offers it only to pool riders and
never offers pool riders anyone else's order (realtime dispatch.same_pool). So
the demo rider people test with by hand and in Maestro (rider.demo.<key>) never
gets a simulator order, and real riders never do. Each order that needs a rider
gets a pool rider not busy with another (rules.pick_rider); if realtime offers a
waiting order to another of the pool's riders, that rider takes it and the two
swap, so no simulator rider ever passes a simulator order.

Sign-in: each of them signs in like the apps do, with the phone code
(/auth/send-otp, /auth/phone). Seed phones get the fixed code outside production
(OTP_FIXED_CODE); production has none, and the simulator never starts there.
Tokens are refreshed with /auth/refresh. Nothing is minted here: only core_api
signs tokens. Reads (which orders, whose phone) come from the database; every
change goes through the APIs.
"""
import asyncio
import json
import os
import time
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import text

from app.demo_sim import rules
from app.demo_sim.path import FIX_SECONDS, rider_start
from shared import internal_auth, kitchen_live
from shared.config import get_settings
from shared.db import AsyncSessionLocal
from shared.redis import get_redis

logger = structlog.get_logger(__name__)

OURS = "demo_sim:orders"  # Redis set: the orders the simulator placed
PAYMENT_METHOD = "card"   # the demo customers' saved test card (demo seed)


def PAY_BODY(order_id: str) -> dict:  # noqa: N802
    """The demo customer pays at once: Stripe's test card where the country pays through Stripe
    (test mode on QA, confirmed server-side; R10), and the fake completes anything not "decline"."""
    return {"order_id": order_id, "payment_method_type": PAYMENT_METHOD, "payment_method_id": "pm_card_visa"}
SIGN_IN_BACKOFF_SECONDS = 65
_running = False

RIDERS_SQL = text("""
SELECT id, email, phone, country FROM users
WHERE role = 'driver' AND dispatch_pool = 'demo_sim' AND email LIKE 'rider.sim.%@example.com'
  AND phone IS NOT NULL AND is_active
ORDER BY email
""")
POOL_ORDERS_PATH = "/internal/dispatch/pool-orders"  # realtime, signed (shared/internal_auth.py)
USER_SQL = text("SELECT id, email, phone, country FROM users WHERE email = :email AND phone IS NOT NULL AND is_active")
OWNER_SQL = text("SELECT id, email, phone, country FROM users WHERE id = :id AND phone IS NOT NULL AND is_active")
ORDERS_SQL = text("""
SELECT o.id, o.status, c.email AS customer_email, o.driver_id, r.owner_id, o.restaurant_id, o.pickup_lat, o.pickup_lng,
       o.delivery_lat, o.delivery_lng, o.created_at, o.placed_at, o.restaurant_accepted_at, o.rider_assigned_at,
       o.picked_up_at, o.market_city,
       EXISTS (SELECT 1 FROM payment_intents p WHERE p.order_id = o.id AND p.metadata->>'demo' = 'true') AS seeded
FROM orders o JOIN users c ON c.id = o.customer_id JOIN restaurants r ON r.id = o.restaurant_id
WHERE c.email = :email AND o.status NOT IN ('delivered', 'cancelled')
  AND o.pickup_lat IS NOT NULL AND o.delivery_lat IS NOT NULL
ORDER BY o.created_at
""")
LAST_DELIVERED_SQL = text("""
SELECT max(o.actual_delivery_time) FROM orders o JOIN users c ON c.id = o.customer_id
WHERE c.email = :email AND o.status = 'delivered'
""")
# Cities that take orders (core_api markets rules.OPEN): a beta city (Boise) is one of them.
OPEN_CITY_STATUSES = ("beta", "live")
# R27: the kitchens the simulator plays (it orders from them again and accepts as their owner): every
# kitchen the demo customer had an order delivered from in an open city. Each tick it says so
# (shared/kitchen_live.sim_beat), so they stay open without a tablet; a kitchen a real tablet has
# run in the last 12 h is governed by that tablet alone (kitchen_live).
PLAYED_KITCHENS_SQL = text("""
SELECT DISTINCT o.restaurant_id FROM orders o JOIN users c ON c.id = o.customer_id JOIN cities ci ON ci.code = o.market_city
WHERE c.email = :email AND o.status = 'delivered' AND ci.status IN ('beta', 'live')
""")
PAST_ORDERS_SQL = text("""
SELECT o.id FROM orders o JOIN users c ON c.id = o.customer_id JOIN cities ci ON ci.code = o.market_city
WHERE c.email = :email AND o.status = 'delivered' AND ci.status IN ('beta', 'live')
ORDER BY o.created_at DESC LIMIT 30
""")


def settings_enabled() -> tuple[bool, str]:
    s = get_settings()
    return rules.enabled(s.worker.DEMO_RIDER_SIM, s.APP_ENV, os.environ)


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"{status}: {body[:300]}")
        self.status = status


class Person:
    """One signed-in person (rider, customer or kitchen owner), as their app would be."""

    def __init__(self, api: "Api", user_id: str, phone: str, country: str) -> None:
        self.api, self.user_id, self.phone, self.country = api, user_id, phone, country
        self.access: str | None = None
        self.refresh: str | None = None
        self.wait_until = 0.0  # the code limit (3 a minute per address) was hit: try again after this

    async def sign_in(self) -> None:
        code = get_settings().providers.OTP_FIXED_CODE
        if not code:
            raise ApiError(0, "no fixed sign-in code here (OTP_FIXED_CODE): the demo rider can't sign in")
        if time.monotonic() < self.wait_until:
            raise ApiError(429, "waiting for the sign-in code limit")
        r = await self.api.core.post("/api/v1/auth/send-otp", json={"phone": self.phone, "country": self.country})
        if r.status_code == 429:
            self.wait_until = time.monotonic() + SIGN_IN_BACKOFF_SECONDS
        if r.status_code >= 400:
            raise ApiError(r.status_code, r.text)
        r = await self.api.core.post("/api/v1/auth/phone", json={"phone": self.phone, "otp": code, "country": self.country})
        if r.status_code >= 400:
            raise ApiError(r.status_code, r.text)
        self._tokens(r.json())

    def _tokens(self, body: dict) -> None:
        self.access, self.refresh = body["access_token"], body["refresh_token"]

    async def _renew(self) -> None:
        if self.refresh:
            r = await self.api.core.post("/api/v1/auth/refresh", json={"refresh_token": self.refresh})
            if r.status_code == 200:
                self._tokens(r.json())
                return
        await self.sign_in()

    async def call(self, service: str, method: str, path: str, **kw) -> dict:  # type: ignore[no-untyped-def]
        """``service`` "core" or "rt"; ``path`` after /api/v1. Signs in when needed."""
        client = self.api.core if service == "core" else self.api.rt
        if self.access is None:
            await self.sign_in()
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self.access}", **kw.pop("headers", {})}
            r = await client.request(method, f"/api/v1{path}", headers=headers, **kw)
            if r.status_code == 401 and attempt == 1:
                await self._renew()
                continue
            if r.status_code >= 400:
                raise ApiError(r.status_code, r.text)
            return r.json() if r.content else {}
        raise ApiError(401, "signed out")


class Api:
    def __init__(self, core: httpx.AsyncClient, rt: httpx.AsyncClient) -> None:
        self.core, self.rt = core, rt
        self.people: dict[str, Person] = {}

    def person(self, row) -> Person:  # type: ignore[no-untyped-def]
        uid = str(row.id)
        if uid not in self.people:
            self.people[uid] = Person(self, uid, row.phone, row.country)
        return self.people[uid]

    async def mark(self, order_id: str) -> None:
        """Tell realtime this order is the simulator's: only its pool's riders get it."""
        body = json.dumps({"order_id": order_id, "pool": rules.SIM_POOL}).encode()
        r = await self.rt.post(POOL_ORDERS_PATH, content=body, headers={
            "content-type": "application/json", **internal_auth.sign("POST", POOL_ORDERS_PATH, body)})
        if r.status_code >= 400:
            raise ApiError(r.status_code, r.text)


def _order(row) -> rules.DemoOrder:  # type: ignore[no-untyped-def]
    return rules.DemoOrder(
        id=str(row.id), status=row.status, customer_email=row.customer_email,
        driver_id=str(row.driver_id) if row.driver_id else None,
        restaurant_owner_id=str(row.owner_id) if row.owner_id else None,
        pickup=(row.pickup_lat, row.pickup_lng), dropoff=(row.delivery_lat, row.delivery_lng),
        created_at=row.created_at, placed_at=row.placed_at, accepted_at=row.restaurant_accepted_at,
        assigned_at=row.rider_assigned_at, picked_up_at=row.picked_up_at, seeded=bool(row.seeded))


class City:
    """One demo city: its pool of simulator riders, its demo customer, and the orders on their way."""

    def __init__(self, api: Api, key: str, rider_rows: list) -> None:  # type: ignore[type-arg]
        self.api, self.key = api, key
        self.pool: list[str] = []  # the simulator's riders here, in a fixed order (by email)
        self.riders: dict[str, Person] = {}
        self.set_riders(rider_rows)
        self.customer_email = rules.customer_email(key)
        self.last_attempt: datetime | None = None
        self.paid: set[str] = set()
        self.claims: dict[str, str] = {}  # order still without a rider -> the pool rider waiting for it
        self.waiting: set[str] = set()  # this tick: our orders still without a rider
        self.no_rider: set[str] = set()  # orders told "every pool rider is busy" (logged once)
        self.off_duty: set[str] = set()  # delivered: off duty once realtime has seen it delivered
        self.watches: dict[str, rules.Watch] = {}  # order -> its step and since when (the watchdog)
        self.given_up: set[str] = set()  # stalled twice: cancelled, or left alone if it can't be

    def set_riders(self, rows: list) -> None:  # type: ignore[type-arg]
        """The pool as the database has it now (the demo seed may add riders)."""
        self.pool = [str(r.id) for r in rows]
        self.riders = {str(r.id): self.api.person(r) for r in rows}

    def rider_of(self, o: rules.DemoOrder) -> str | None:
        """The pool rider on this order: its rider, or the one waiting for its offer."""
        if o.driver_id:
            return o.driver_id if o.driver_id in self.riders else None
        return self.claims.get(o.id)

    def claim(self, o: rules.DemoOrder, busy: set[str]) -> str | None:
        """A free pool rider for an order that needs one (kept until it has its rider)."""
        rider = self.claims.get(o.id)
        if rider is None:
            rider = rules.pick_rider(self.pool, busy | set(self.claims.values()))
            if rider is None:
                if o.id not in self.no_rider:  # once per order, not every 4 s
                    self.no_rider.add(o.id)
                    logger.info("demo_riders_all_busy", city=self.key, order_id=o.id, pool=len(self.pool))
                return None
            self.claims[o.id] = rider
            self.off_duty.discard(rider)
        return rider

    async def tick(self, now: datetime) -> list[str]:
        async with AsyncSessionLocal() as db:
            customer = (await db.execute(USER_SQL, {"email": self.customer_email})).first()
            if customer is None:
                return []
            rows = (await db.execute(ORDERS_SQL, {"email": self.customer_email})).all()
            last = (await db.execute(LAST_DELIVERED_SQL, {"email": self.customer_email})).scalar()
            owners = {str(r.owner_id): (await db.execute(OWNER_SQL, {"id": r.owner_id})).first() for r in rows if r.owner_id}
            played = {str(k) for (k,) in (await db.execute(PLAYED_KITCHENS_SQL, {"email": self.customer_email})).all()}
        await kitchen_live.sim_beat(sorted(played | {str(r.restaurant_id) for r in rows}), await get_redis())
        ours = set(await (await get_redis()).smembers(OURS))
        mine = [o for o in map(_order, rows) if rules.is_sim_order(o, ours) and o.id not in self.given_up]
        # Pool riders on an open order (any of the customer's, given up ones too: realtime keeps them busy).
        busy = {str(r.driver_id) for r in rows if r.driver_id and str(r.driver_id) in self.riders}
        self.waiting = {o.id for o in mine if o.driver_id is None}
        self.claims = {o: r for o, r in self.claims.items() if o in self.waiting}
        for rider in sorted(self.off_duty - busy - set(self.claims.values())):
            try:  # so realtime never offers it an order it would ignore
                await self.riders[rider].call("rt", "POST", "/riders/me/offline")
                self.off_duty.discard(rider)
            except (ApiError, KeyError):
                pass  # realtime hasn't seen the delivery yet (still busy): next tick
        steps = []
        for o in mine:
            rider = self.rider_of(o)
            step = rules.next_step(o, rider or "", now)
            steps.append(step)
            owner = owners.get(o.restaurant_owner_id or "")
            w, verdict = rules.watch(self.watches.get(o.id), step, now)
            self.watches[o.id] = w
            if verdict == "new":
                logger.info("demo_order_step", city=self.key, order_id=o.id, status=o.status, step=step, rider_id=rider)
            else:
                logger.debug("demo_order_tick", city=self.key, order_id=o.id, status=o.status, step=step)
            if verdict == "stalled":
                logger.warning("demo_order_stalled", city=self.key, order_id=o.id, status=o.status, step=step,
                               action="recover: rider signs in and goes online again, step retried")
                await self.recover(o)
            elif verdict == "give_up":
                await self.give_up(o, customer, owner)
                continue
            if step != "wait":
                await self.do(step, o, customer, owner, now, busy)
        for gone in set(self.watches) - {o.id for o in mine}:  # delivered, cancelled or given up
            del self.watches[gone]
        if rules.should_create(len(mine), last, self.last_attempt, now):
            self.last_attempt = now
            await self.place(customer)
        return steps

    async def recover(self, o: rules.DemoOrder) -> None:
        """First aid for a stalled order: its rider signs in afresh (the others renew on a 401
        anyway), the order is marked for the pool again, payment is retried, and the rider goes
        online again near the kitchen, which also frees it in realtime if it was left busy with
        an order that is over (realtime dispatch.free_if_stale)."""
        self.paid.discard(o.id)
        rider = self.rider_of(o)
        if rider is None:
            return
        self.riders[rider].access = None  # signs in again on the next call (with the phone code)
        if o.status != "picked_up":
            start = rider_start(o.pickup, o.id)
            try:
                if o.driver_id is None:
                    await self.api.mark(o.id)
                await self.riders[rider].call("rt", "POST", "/riders/me/online", json={"lat": start[0], "lng": start[1]})
            except ApiError as e:
                logger.warning("demo_rider_online_failed", city=self.key, order_id=o.id, error=str(e))

    async def give_up(self, o: rules.DemoOrder, customer, owner) -> None:  # type: ignore[no-untyped-def]
        """Stalled again after a recovery: cancel it the way its kitchen or customer could,
        so the next order can start; if nobody may cancel it (ready, on its way), leave it."""
        self.given_up.add(o.id)
        self.claims.pop(o.id, None)
        who = rules.cancel_as(o.status)
        person = None
        if who == "kitchen" and owner is not None:
            person = self.api.person(owner)
        elif who == "customer":
            person = self.api.person(customer)
        if person is None:
            logger.error("demo_order_given_up", city=self.key, order_id=o.id, status=o.status,
                         reason="stalled and nobody but an admin can cancel it now; the next order starts")
            return
        try:
            await person.call("core", "POST", f"/orders/{o.id}/cancel", json={
                "reason": "other", "note": "Demo order stalled; cancelled by the demo rider simulator"})
            logger.warning("demo_order_cancelled_stalled", city=self.key, order_id=o.id, status=o.status, by=who)
        except ApiError as e:
            logger.error("demo_order_given_up", city=self.key, order_id=o.id, status=o.status, error=str(e))

    async def do(self, step: str, o: rules.DemoOrder, customer, owner, now: datetime,  # type: ignore[no-untyped-def]
                 busy: set[str] | None = None) -> None:
        """One step of one order. ``busy``: pool riders already on another order."""
        cust = self.api.person(customer)
        kitchen = self.api.person(owner) if owner is not None else None
        if step == "pay":
            if o.id not in self.paid:  # once; the fake provider completes it and core_api places it
                self.paid.add(o.id)
                await cust.call("core", "POST", "/payments/initiate", json=PAY_BODY(o.id))
        elif step == "cancel":
            await cust.call("core", "POST", f"/orders/{o.id}/cancel", json={"reason": "other", "note": "Demo order not paid"})
        elif step in ("accept", "prepare", "almost_ready", "ready") and kitchen is not None:
            if step == "almost_ready":
                rider_id = self.claim(o, busy or set())
                if rider_id is None:
                    return  # every pool rider is on another order: the kitchen waits a little
                # Marked first, so dispatch offers it to the pool's riders only; then the rider
                # is about by the time dispatch looks for one.
                await self.api.mark(o.id)
                start = rider_start(o.pickup, o.id)
                await self.riders[rider_id].call("rt", "POST", "/riders/me/online", json={"lat": start[0], "lng": start[1]})
            status = {"accept": "accepted", "prepare": "preparing"}.get(step, step)
            await kitchen.call("core", "PUT", f"/orders/{o.id}/status", json={"status": status})
        elif step == "find_rider":
            rider_id = self.claim(o, busy or set())
            if rider_id is None:
                return
            rider = self.riders[rider_id]
            await self.api.mark(o.id)  # again: cheap, and a realtime restart can't lose it
            start = rider_start(o.pickup, o.id)
            me = await rider.call("rt", "GET", "/riders/me")
            state = me.get("state") or {}
            if state.get("status", "offline") not in ("available", "offered"):
                # Offline (another device, a restart), or busy with an order that isn't this one:
                # going online again frees a rider left busy with an order that is over.
                logger.info("demo_rider_online_again", city=self.key, order_id=o.id, rider_id=rider_id,
                            state=state.get("status"), busy_with=state.get("order_id") or None)
                await rider.call("rt", "POST", "/riders/me/online", json={"lat": start[0], "lng": start[1]})
                me = await rider.call("rt", "GET", "/riders/me")
            else:
                # Keep the GPS fresh while waiting, as the app does: dispatch skips a rider
                # whose last fix is older than DRIVER_LOCATION_TTL (60 s).
                await rider.call("rt", "POST", "/delivery/driver/location", json={
                    "lat": round(start[0], 6), "lng": round(start[1], 6), "speed": 0, "accuracy": 8})
            offered = (me.get("offer") or {}).get("order_id")
            if offered == o.id or (offered and offered in self.waiting):
                # This order, or another of ours that realtime offered to this rider first:
                # take it, and the two orders swap riders.
                await rider.call("rt", "POST", f"/offers/{offered}/accept")
                if offered != o.id:
                    other = self.claims.get(offered)  # the rider who was waiting for that one
                    self.claims[offered] = rider_id
                    if other and other != rider_id:
                        self.claims[o.id] = other
                    else:
                        self.claims.pop(o.id, None)
                logger.info("demo_rider_accepted", city=self.key, order_id=offered, rider_id=rider_id)
            elif offered:  # someone else's order (pools keep these away; never ours to take)
                await rider.call("rt", "POST", f"/offers/{offered}/pass")
        elif step in ("to_kitchen", "to_home", "pick_up", "deliver"):
            rider_id = self.rider_of(o)
            if rider_id is None:
                return
            rider = self.riders[rider_id]
            if step in ("to_kitchen", "to_home"):
                (lat, lng), heading, speed = rules.position(o, step, now)
                await rider.call("rt", "POST", "/delivery/driver/location", json={
                    "lat": round(lat, 6), "lng": round(lng, 6), "heading": round(heading, 1), "speed": speed, "accuracy": 8})
            elif step == "pick_up":
                await rider.call("core", "PUT", f"/orders/{o.id}/status", json={"status": "picked_up"})
            else:
                (lat, lng), heading, _ = rules.position(o, "to_home", now)
                await rider.call("rt", "POST", "/delivery/driver/location", json={
                    "lat": round(lat, 6), "lng": round(lng, 6), "heading": round(heading, 1), "speed": 0, "accuracy": 8})
                pin = (await cust.call("core", "GET", f"/orders/{o.id}")).get("pin")  # read out at the door
                await rider.call("core", "PUT", f"/orders/{o.id}/status", json={
                    "status": "delivered", "proof": {"method": "pin", "pin": pin}})
                logger.info("demo_order_delivered", city=self.key, order_id=o.id, rider_id=rider_id)
                self.off_duty.add(rider_id)

    async def place(self, customer) -> str | None:  # type: ignore[no-untyped-def]
        """The demo customer orders one of their past orders again, from a kitchen
        that is open now (the quote says so), to their default address."""
        cust = self.api.person(customer)
        async with AsyncSessionLocal() as db:
            past = [str(r.id) for r in (await db.execute(PAST_ORDERS_SQL, {"email": self.customer_email})).all()]
        addresses = await cust.call("core", "GET", "/me/addresses")
        home = next((a for a in addresses if a.get("is_default")), addresses[0] if addresses else None)
        if home is None or home.get("lat") is None:
            logger.warning("demo_order_skipped", city=self.key, reason="the demo customer has no address on the map")
            return None
        if not past:
            logger.warning("demo_order_not_placed", city=self.key,
                           reason="the demo customer has no delivered order in an open city to order again")
            return None
        seen: set[str] = set()
        for past_id in past:
            again = await cust.call("core", "POST", f"/orders/{past_id}/reorder")
            kitchen = str(again["restaurant"]["id"])
            items = [{"menu_item_id": str(i["menu_item_id"]), "quantity": i["quantity"],
                      "options": [{"group": p["group"], "option": p["option"]} for p in i["options"]]}
                     for i in again["items"] if i.get("available", True)]
            if kitchen in seen or not items:
                continue
            seen.add(kitchen)
            try:
                quote = await cust.call("core", "POST", "/pricing/quote", json={
                    "restaurant_id": kitchen, "items": items, "deliver_to": {"address_id": home["id"]}})
            except ApiError as e:  # closed now, sold out, too far: try another kitchen
                logger.info("demo_order_kitchen_skipped", city=self.key, restaurant_id=kitchen, reason=str(e))
                continue
            order = await cust.call("core", "POST", "/orders", headers={"X-Idempotency-Key": str(uuid.uuid4())}, json={
                "restaurant_id": kitchen, "items": items, "payment_method": PAYMENT_METHOD, "quote_token": quote["token"],
                "delivery_address": {"street": home["street"], "city": home["city"], "state": home.get("state") or "",
                                     "zip": home.get("postal_code") or "", "country": home["country"],
                                     "lat": home["lat"], "lng": home["lng"]}})
            await (await get_redis()).sadd(OURS, order["id"])
            self.paid.add(order["id"])
            await cust.call("core", "POST", "/payments/initiate", json=PAY_BODY(order["id"]))
            logger.info("demo_order_placed", city=self.key, order_id=order["id"], restaurant_id=kitchen)
            return str(order["id"])
        logger.info("demo_order_not_placed", city=self.key, reason="no restaurant the demo customer ordered from is open now")
        return None


async def pools() -> dict[str, list]:  # type: ignore[type-arg]
    """Each demo city's pool of simulator riders, from the database (the demo seed writes them)."""
    async with AsyncSessionLocal() as db:
        riders = (await db.execute(RIDERS_SQL)).all()
    out: dict[str, list] = {}  # type: ignore[type-arg]
    for row in riders:
        key = rules.city_key(row.email)
        if key:
            out.setdefault(key, []).append(row)
    return out


async def cities(api: Api, known: list[City] | None = None) -> list[City]:
    """The demo cities now; a city already running keeps its state and takes the pool as it is now."""
    have = {c.key: c for c in known or []}
    out = []
    for key, rows in (await pools()).items():
        city = have.get(key)
        if city is None:
            city = City(api, key, rows)
        else:
            city.set_riders(rows)
        out.append(city)
    return out


async def run() -> None:
    """The simulator's loop: every FIX_SECONDS, each demo city one step on."""
    global _running
    on, why = settings_enabled()
    if not on:
        logger.info("demo_rider_sim", status=why)
        return
    _running = True
    s = get_settings()
    async with httpx.AsyncClient(base_url=s.CORE_API_URL, timeout=15) as core, \
            httpx.AsyncClient(base_url=s.worker.REALTIME_INTERNAL_URL, timeout=15) as rt:
        api = Api(core, rt)
        found: list[City] = []
        logger.info("demo_rider_sim", status="on", core_api=s.CORE_API_URL, realtime=s.worker.REALTIME_INTERNAL_URL)
        last_scan = 0.0
        while _running:
            loop_now = asyncio.get_event_loop().time()
            if not found or loop_now - last_scan > 300:  # demo cities appear after the demo seed runs
                try:
                    found = await cities(api, found)
                except Exception as e:  # noqa: BLE001 - the database may not be there yet
                    logger.warning("demo_rider_sim_scan_failed", error=str(e))
                last_scan = loop_now
            for city in found:
                try:
                    await city.tick(datetime.now(UTC))
                except Exception as e:  # noqa: BLE001 - one city's trouble never stops the others
                    logger.warning("demo_rider_sim_step_failed", city=city.key, error=str(e))
            await asyncio.sleep(FIX_SECONDS)


def stop() -> None:
    global _running
    _running = False
