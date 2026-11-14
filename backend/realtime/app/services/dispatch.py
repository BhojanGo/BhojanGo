"""Dispatch and live tracking (P14). All state is in Redis, so several realtime
instances can share it; contested steps use atomic Redis operations.

Riders
  online riders are in the GEO set ``riders:geo``; their last fix is
  ``driver:{id}:location`` (expires after DRIVER_LOCATION_TTL, so a rider whose
  app stopped sending GPS is never offered anything); ``rider:{id}:state``
  holds available | offered | busy and the order.

Offers
  When an order is almost ready (or ready), it is offered to the nearest
  available rider within DISPATCH_RADIUS_KM of the restaurant, for the
  dispatch_offer_timeout rule (30 s). A pass or a timeout re-offers it to the
  next nearest rider who hasn't declined it. With nobody free it is retried
  every DISPATCH_RETRY_SECONDS. An accept assigns the rider in core_api.

Fairness (pilot dress rehearsal): orders waiting for a rider are served
  oldest first. ``dispatch:waiting`` holds when each one started looking; the
  moment a rider is free (online, a delivery done, an offer passed or timed
  out) the oldest waiting orders are offered first, and retries run oldest
  first. Before, each order retried on its own 15 s timer, so a newer order
  often got the next free rider while an older one kept waiting.

Tracking
  Customers (and the assigned rider, and admins for the city) subscribe to
  ``tracking:{order}``: rider assigned, location + ETA, status changes. The last
  200 positions are kept for the map (``trail:{order}``, 24 h).

Batching (task 43)
  The batch engine runs in the worker (app/batching/engine.py, a port of the
  TypeScript engine) and posts what it finds to /internal/dispatch/batches.
  Shadow mode (every city): suggestions are only stored
  (``shadow:batch_suggestions``) and logged. Live, where the city's
  ``business:batching`` rule says so (off by default): a new order is held for
  BATCH_HOLD_SECONDS before it's offered alone, so the engine can pair it; a
  pair is offered to one rider as one offer showing both drop-offs and the
  total pay; accepting assigns both, and the rider stays busy until both are
  delivered (``rider:{id}:state`` ``batch``: the orders left, in drop-off
  order). A pass or a timeout sends both back to solo dispatch.
"""
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.core.redis import get_redis, order_tracking_channel
from app.services.core_api import CoreApiError, core_api
from shared.config import get_settings
from shared.providers.routing import get_routing_provider, haversine_km  # noqa: F401  (riders.py uses dispatch.haversine_km)

logger = structlog.get_logger(__name__)

GEO = "riders:geo"
ONLINE = "riders:online"
OFFER_EXPIRY = "offers:expiry"
RETRY = "dispatch:retry"
ACTIVE = "dispatch:active"
WAITING = "dispatch:waiting"  # order -> when it started looking for a rider (oldest first)
HOLD = "dispatch:hold"  # order -> until when it waits for a batch partner (live batching cities)
WAITING_SCAN = 50  # how many waiting orders a free rider is matched against
SHADOW = "shadow:batch_suggestions"
TRAIL_KEEP = 200
DAY = 86400
MILE_KM = 1.609344


def _s() -> Any:
    return get_settings().realtime


def loc_key(rider: str) -> str:
    return f"driver:{rider}:location"


def state_key(rider: str) -> str:
    return f"rider:{rider}:state"


def offer_key(order: str) -> str:
    return f"offer:{order}"


def info_key(order: str) -> str:
    return f"dispatch:{order}"


def declined_key(order: str) -> str:
    return f"dispatch:{order}:declined"


def in_batch_offer_key(order: str) -> str:
    """Set while the order is part of another order's (the lead's) batch offer."""
    return f"dispatch:{order}:batch_offer"


def rider_channel(rider: str) -> str:
    return f"rider:{rider}:events"


def _now() -> float:
    return time.time()


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


async def _publish(channel: str, kind: str, payload: dict) -> None:
    r = await get_redis()
    await r.publish(channel, json.dumps({"type": kind, "payload": payload, "timestamp": datetime.now(UTC).isoformat()},
                                        default=str))


# ── riders ────────────────────────────────────────────────────────────────────

async def rider_state(rider: str) -> dict:
    r = await get_redis()
    state = await r.hgetall(state_key(rider)) or {"status": "offline"}
    if "batch" in state:  # the orders still to deliver on a batch, in drop-off order
        state = {**state, "batch": [o for o in state["batch"].split(",") if o]}
    return state


async def batch_of(rider: str) -> list[str]:
    raw = await (await get_redis()).hget(state_key(rider), "batch")
    return [o for o in (raw or "").split(",") if o]


async def _engaged(rider: str, on: bool) -> None:
    """Engaged time for the hourly floor runs from accepting an offer to drop-off."""
    from app.services import shifts

    try:
        await shifts.set_activity(rider, shifts.ACTIVE if on else shifts.AVAILABLE, _now())
    except LookupError:  # no shift (went online before shifts were tracked)
        pass


async def go_online(rider: str, lat: float, lng: float) -> dict:
    from app.services import shifts

    r = await get_redis()
    if not await r.exists(f"driver:{rider}:shift"):
        await shifts.start_shift(rider, _now())
    await r.sadd(ONLINE, rider)
    state = await r.hgetall(state_key(rider))
    if state.get("status") not in ("offered", "busy"):
        await r.hset(state_key(rider), mapping={"status": "available", "order_id": ""})
    await update_location(rider, lat, lng)
    await offer_waiting()
    return await rider_state(rider)


async def go_offline(rider: str) -> dict:
    r = await get_redis()
    state = await r.hgetall(state_key(rider))
    if state.get("status") == "busy":
        raise ValueError("Finish your delivery before going offline")
    if state.get("status") == "offered" and state.get("order_id"):
        await decline(rider, state["order_id"], "went_offline")
    await r.srem(ONLINE, rider)
    await r.zrem(GEO, rider)
    await r.hset(state_key(rider), mapping={"status": "offline", "order_id": ""})
    from app.services import shifts

    await shifts.end_shift(rider, _now())
    return await rider_state(rider)


async def update_location(rider: str, lat: float, lng: float, extra: dict | None = None) -> dict:
    """Store a GPS fix. If the rider is on an order, the customer sees it move."""
    r = await get_redis()
    fix = {"driver_id": rider, "lat": lat, "lng": lng, "timestamp": datetime.now(UTC).isoformat(), **(extra or {})}
    await r.set(loc_key(rider), json.dumps(fix), ex=_s().DRIVER_LOCATION_TTL)
    if await r.sismember(ONLINE, rider):
        await r.geoadd(GEO, (lng, lat, rider))
    state = await r.hgetall(state_key(rider))
    order = state.get("order_id") if state.get("status") == "busy" else None
    if order:
        info = await order_info(order)
        eta = eta_for(info, (lat, lng)) if info else None
        await r.lpush(f"trail:{order}", json.dumps([lat, lng, fix["timestamp"]]))
        await r.ltrim(f"trail:{order}", 0, TRAIL_KEEP - 1)
        await r.expire(f"trail:{order}", DAY)
        await _publish(order_tracking_channel(order), "location_update", {**fix, "order_id": order, "eta": eta})
    return {**fix, "order_id": order}


async def last_fix(rider: str) -> dict | None:
    r = await get_redis()
    raw = await r.get(loc_key(rider))
    return json.loads(raw) if raw else None


# ── orders ────────────────────────────────────────────────────────────────────

async def order_info(order: str, refresh: bool = False, max_age: float | None = None) -> dict | None:
    """The order as dispatch sees it, from the cache unless ``refresh`` or the cached
    copy is older than ``max_age`` seconds (P24: a burst of trackers opening at once
    shouldn't each make a call to core_api)."""
    r = await get_redis()
    raw = None if refresh else await r.get(info_key(order))
    if raw:
        cached = json.loads(raw)
        if max_age is None or time.time() - float(cached.get("_at", 0)) <= max_age:
            return cached
    try:
        info = await core_api.dispatch_info(order)
    except CoreApiError as e:
        if e.status == 404:
            return None
        raise
    await _save_info(info)
    return info


async def _save_info(info: dict) -> None:
    r = await get_redis()
    await r.set(info_key(info["order_id"]), json.dumps({**info, "_at": time.time()}), ex=DAY)


def eta_for(info: dict, rider_at: tuple[float, float] | None) -> dict | None:
    """Minutes to pickup and to drop-off from the rider's position (routing provider)."""
    if not info or not info.get("dropoff") or rider_at is None:
        return None
    routing = get_routing_provider()
    pickup = tuple(info["pickup"]) if info.get("pickup") else None
    dropoff = tuple(info["dropoff"])
    picked = info.get("status") in ("picked_up", "delivered")
    if picked or pickup is None:
        to_customer = routing.leg(rider_at, dropoff).minutes  # type: ignore[arg-type]
        return {"to_pickup_minutes": 0, "to_customer_minutes": max(1, round(to_customer)),
                "arrives_at": _iso(_now() + to_customer * 60)}
    to_pickup = routing.leg(rider_at, pickup).minutes  # type: ignore[arg-type]
    to_customer = to_pickup + routing.leg(pickup, dropoff).minutes  # type: ignore[arg-type]
    return {"to_pickup_minutes": max(1, round(to_pickup)), "to_customer_minutes": max(1, round(to_customer)),
            "arrives_at": _iso(_now() + to_customer * 60)}


async def start_dispatch(order: str, info: dict | None = None) -> str | None:
    info = info or await order_info(order, refresh=True)
    if not info or info.get("driver_id") or not info.get("pickup"):
        return None
    await _save_info(info)
    r = await get_redis()
    if not await r.sadd(ACTIVE, order):  # already dispatching (duplicate event)
        return None
    await r.zadd(WAITING, {order: _now()}, nx=True)
    await _publish(order_tracking_channel(order), "searching_rider", {"order_id": order})
    if info.get("batching_live"):  # give the batch engine a moment to find it a partner
        until = _now() + _s().BATCH_HOLD_SECONDS
        await r.zadd(HOLD, {order: until})
        await r.zadd(RETRY, {order: until})
        return None
    return await offer_next(order)


async def _claim_rider(order: str, pickup: list, declined: set, timeout: int) -> tuple[str, float] | None:
    """The nearest free rider within DISPATCH_RADIUS_KM who hasn't declined, claimed atomically."""
    r = await get_redis()
    lat, lng = pickup
    near = await r.geosearch(GEO, longitude=lng, latitude=lat, radius=_s().DISPATCH_RADIUS_KM, unit="km",
                             sort="ASC", count=25, withdist=True)
    for rider, dist_km in near:
        if rider in declined or not await r.sismember(ONLINE, rider):
            continue
        if not await r.exists(loc_key(rider)):
            continue  # no GPS for a while: the app is probably closed
        # Claim the rider atomically: only one order can offer to them at a time.
        if not await r.set(f"rider:{rider}:offer_lock", order, nx=True, ex=timeout + 5):
            continue
        if await r.hget(state_key(rider), "status") != "available":
            await r.delete(f"rider:{rider}:offer_lock")
            continue
        return rider, float(dist_km)
    return None


async def offer_next(order: str) -> str | None:
    """Offer the order to the nearest free rider who hasn't declined it."""
    r = await get_redis()
    info = await order_info(order)
    if not info or info.get("driver_id") or not await r.sismember(ACTIVE, order):
        return None
    if await r.exists(in_batch_offer_key(order)):
        return None  # offered as part of a batch right now
    held = await r.zscore(HOLD, order)
    if held is not None and held > _now():
        await r.zadd(RETRY, {order: held})  # waiting for a batch partner a little longer
        return None
    declined = await r.smembers(declined_key(order))
    timeout = int(info.get("offer_timeout_seconds") or 30)
    claimed = await _claim_rider(order, info["pickup"], declined, timeout)
    if claimed:
        rider, dist_km = claimed
        expires = _now() + timeout
        fix = await last_fix(rider)
        eta = eta_for(info, (fix["lat"], fix["lng"])) if fix else None
        offer = {"order_id": order, "rider_id": rider, "expires_at": _iso(expires), "expires_in": timeout,
                 "distance_km": round(float(dist_km), 2), "restaurant_name": info.get("restaurant_name"),
                 "pickup": info["pickup"], "dropoff": info.get("dropoff"), "eta": eta,
                 # P18: what the offer card shows
                 **{k: info.get(k) for k in ("code", "currency", "rider_pay", "tip", "items_count", "bags",
                                             "ready_in_minutes", "drop_area", "distance_unit")},
                 "trip_km": _trip_km(info)}
        await r.set(offer_key(order), json.dumps(offer), ex=timeout + 5)
        await r.hset(state_key(rider), mapping={"status": "offered", "order_id": order})
        await r.zadd(OFFER_EXPIRY, {order: expires})
        await _publish(rider_channel(rider), "offer", offer)
        logger.info("rider_offered", order_id=order, rider_id=rider, distance_km=round(float(dist_km), 2), timeout=timeout)
        return rider
    await r.zadd(RETRY, {order: _now() + _s().DISPATCH_RETRY_SECONDS})
    logger.info("no_rider_available", order_id=order, declined=len(declined))
    return None


# ── batches (task 43) ─────────────────────────────────────────────────────────

def _money_sum(values: list) -> str | None:
    from decimal import Decimal

    if any(v is None for v in values):
        return None
    return str(sum((Decimal(str(v)) for v in values), Decimal("0")))


async def offer_batch(orders: list[str], meta: dict | None = None) -> str | None:
    """Offer several orders to one rider as one offer (live batching).

    ``orders`` are in drop-off order (the engine's route); the first is the lead:
    the offer is stored under it. Every order must be unassigned, not on an
    offer, in the same city, with live batching on there. At least one must be
    looking for a rider already; the others may still be cooking at the same
    kitchen ("early": the rider collects them together), and go back to
    waiting for their own turn if the batch is turned down."""
    meta = meta or {}
    r = await get_redis()
    if len(orders) < 2 or len(set(orders)) != len(orders):
        return None
    infos, early = [], []
    for o in orders:
        info = await order_info(o, max_age=10)
        if (not info or info.get("driver_id") or not info.get("pickup") or not info.get("batching_live")
                or await r.zscore(OFFER_EXPIRY, o) is not None or await r.exists(in_batch_offer_key(o))):
            return None
        if not await r.sismember(ACTIVE, o):
            if info.get("status") not in ("accepted", "preparing"):
                return None
            early.append(o)
        infos.append(info)
    if len(early) == len(orders) or len({i.get("market_city") for i in infos}) != 1:
        return None
    if early and len({i.get("restaurant_id") for i in infos}) != 1:
        return None  # an order still cooking can only join a pickup at its own kitchen
    lead, lead_info = orders[0], infos[0]
    declined: set = set()
    for o in orders:
        declined |= await r.smembers(declined_key(o))
    timeout = int(lead_info.get("offer_timeout_seconds") or 30)
    claimed = await _claim_rider(lead, lead_info["pickup"], declined, timeout)
    if not claimed:
        return None
    rider, dist_km = claimed
    for o in early:  # now part of dispatch, without an offer of their own
        await r.sadd(ACTIVE, o)
        await r.zadd(WAITING, {o: _now()}, nx=True)
    expires = _now() + timeout
    fix = await last_fix(rider)
    # Item 2: the first drop-off pays as usual; later ones at the batch rate (no base, + the batch bonus).
    stops = [{"order_id": i["order_id"], "code": i.get("code"), "restaurant_name": i.get("restaurant_name"),
              "pickup": i.get("pickup"), "dropoff": i.get("dropoff"), "drop_area": i.get("drop_area"),
              "rider_pay": i.get("rider_pay") if n == 0 else (i.get("rider_pay_batched") or i.get("rider_pay")),
              "batch_rate": n > 0, "tip": i.get("tip"), "bags": i.get("bags"),
              "items_count": i.get("items_count"), "trip_km": _trip_km(i)} for n, i in enumerate(infos)]
    offer = {"order_id": lead, "rider_id": rider, "expires_at": _iso(expires), "expires_in": timeout,
             "distance_km": round(dist_km, 2), "restaurant_name": lead_info.get("restaurant_name"),
             "pickup": lead_info["pickup"], "dropoff": lead_info.get("dropoff"),
             "eta": eta_for(lead_info, (fix["lat"], fix["lng"])) if fix else None,
             **{k: lead_info.get(k) for k in ("code", "currency", "ready_in_minutes", "distance_unit")},
             # What the rider decides on: every drop-off and the total pay.
             "batch": stops, "rider_pay": _money_sum([s["rider_pay"] for s in stops]),
             "tip": _money_sum([i.get("tip") or 0 for i in infos]), "bags": sum(int(i.get("bags") or 1) for i in infos),
             "items_count": sum(int(i.get("items_count") or 0) for i in infos),
             "drop_area": " · ".join(str(i.get("drop_area") or "drop-off") for i in infos),
             "trip_km": meta.get("total_distance_km") or sum(x["trip_km"] or 0 for x in stops),
             "batch_minutes": meta.get("total_time_min"), "early": early}
    await r.set(offer_key(lead), json.dumps(offer), ex=timeout + 5)
    for o in orders[1:]:
        await r.set(in_batch_offer_key(o), lead, ex=timeout + 5)
    for o in orders:
        await r.zrem(HOLD, o)
        await r.zrem(RETRY, o)
    await r.hset(state_key(rider), mapping={"status": "offered", "order_id": lead})
    await r.zadd(OFFER_EXPIRY, {lead: expires})
    await _publish(rider_channel(rider), "offer", offer)
    logger.info("batch_offered", orders=orders, rider_id=rider, rider_pay=offer["rider_pay"], score=meta.get("score"))
    return rider


async def record_shadow(suggestion: dict) -> None:
    """What the engine would have batched (every city; nothing is offered)."""
    r = await get_redis()
    await r.lpush(SHADOW, json.dumps({**suggestion, "mode": "shadow", "at": datetime.now(UTC).isoformat()}))
    await r.ltrim(SHADOW, 0, 499)
    logger.info("batch_shadow_suggestion", **{k: suggestion.get(k) for k in ("orders", "score", "savings_percent", "city")})


async def offer_waiting() -> int:
    """A rider is free: offer the oldest waiting orders first. Each order still
    goes to its nearest free rider; this decides which orders go first.
    Stops as soon as nobody is free. Returns how many offers were made."""
    r = await get_redis()
    made = 0
    for order in await r.zrange(WAITING, 0, WAITING_SCAN - 1):
        if not await _anyone_free(r):
            break
        if await r.zscore(OFFER_EXPIRY, order) is not None:
            continue  # already offered to someone
        if await offer_next(order):
            await r.zrem(RETRY, order)
            made += 1
    return made


async def _anyone_free(r) -> bool:  # type: ignore[no-untyped-def]
    for rider in await r.smembers(ONLINE):
        if await r.hget(state_key(rider), "status") == "available" and await r.exists(loc_key(rider)):
            return True
    return False


def _trip_km(info: dict) -> float | None:
    """Pickup to drop-off, by the routing provider (road distance)."""
    if not info.get("pickup") or not info.get("dropoff"):
        return None
    return round(get_routing_provider().leg(tuple(info["pickup"]), tuple(info["dropoff"])).distance_km, 2)  # type: ignore[arg-type]


async def current_offer(rider: str) -> dict | None:
    r = await get_redis()
    state = await r.hgetall(state_key(rider))
    if state.get("status") != "offered":
        return None
    raw = await r.get(offer_key(state["order_id"]))
    offer = json.loads(raw) if raw else None
    return offer if offer and offer["rider_id"] == rider else None


class NotYourOffer(LookupError):
    """No offer of this order is open for this rider (another rider's, or none)."""


async def accept(rider: str, order: str) -> dict:
    r = await get_redis()
    raw = await r.get(offer_key(order))
    offer = json.loads(raw) if raw else None
    if not offer or offer["rider_id"] != rider:
        raise NotYourOffer("This offer has expired or went to another rider")
    if not await r.zrem(OFFER_EXPIRY, order):  # the timeout got there first
        raise LookupError("This offer has expired")
    batch_ids = [b["order_id"] for b in offer.get("batch") or []]
    batch_id = str(uuid.uuid4()) if len(batch_ids) > 1 else None
    try:
        info = await core_api.assign_rider(order, rider, batch_id, 1) if batch_id else await core_api.assign_rider(order, rider)
    except CoreApiError as e:
        await _clear_offer(rider, order)
        await _finish(order)
        for o in [b["order_id"] for b in offer.get("batch") or []][1:]:  # the rest go back to solo dispatch
            await r.delete(in_batch_offer_key(o))
            await offer_next(o)
        raise LookupError(e.args[0] if e.args else "The order is no longer available")
    await _save_info(info)
    await r.delete(offer_key(order), f"rider:{rider}:offer_lock")
    carrying = [order]
    for position, other in enumerate(batch_ids[1:], start=2):
        await r.delete(in_batch_offer_key(other))
        try:
            other_info = await core_api.assign_rider(other, rider, batch_id, position)
        except CoreApiError as e:  # cancelled meanwhile: the rider just has one fewer
            logger.warning("batch_order_not_assigned", order_id=other, rider_id=rider, error=str(e))
            await _finish(other)
            continue
        await _save_info(other_info)
        carrying.append(other)
    for o in carrying:
        await r.srem(ACTIVE, o)
        await r.zrem(RETRY, o)
        await r.zrem(WAITING, o)
        await r.zrem(HOLD, o)
    state = {"status": "busy", "order_id": order}
    if len(carrying) > 1:
        state["batch"] = ",".join(carrying)
    await r.hset(state_key(rider), mapping=state)
    await _engaged(rider, True)
    for o in carrying[1:]:
        await _publish(order_tracking_channel(o), "rider_assigned", {"order_id": o, "rider_id": rider, "location": await last_fix(rider)})
    fix = await last_fix(rider)
    eta = eta_for(info, (fix["lat"], fix["lng"])) if fix else None
    await _publish(order_tracking_channel(order), "rider_assigned", {"order_id": order, "rider_id": rider, "eta": eta,
                                                                    "location": fix})
    logger.info("rider_accepted", order_id=order, rider_id=rider, batch=carrying if len(carrying) > 1 else None)
    return {"order_id": order, "status": "assigned", "eta": eta, "pickup": info.get("pickup"), "dropoff": info.get("dropoff"),
            "batch": carrying if len(carrying) > 1 else None}


async def decline(rider: str, order: str, reason: str = "passed") -> str | None:
    """A pass, a timeout or going offline: next rider."""
    r = await get_redis()
    raw = await r.get(offer_key(order))
    offer = json.loads(raw) if raw else None
    if not offer or offer["rider_id"] != rider:
        return None
    await r.zrem(OFFER_EXPIRY, order)
    orders = [b["order_id"] for b in offer.get("batch") or []] or [order]
    for o in orders:
        await r.sadd(declined_key(o), rider)
        await r.expire(declined_key(o), DAY)
        await r.delete(in_batch_offer_key(o))
        await r.zrem(HOLD, o)  # a batch that was turned down goes out alone now
    await _clear_offer(rider, order)
    logger.info("offer_declined", order_id=order, rider_id=rider, reason=reason, batch=orders if len(orders) > 1 else None)
    await _publish(rider_channel(rider), "offer_withdrawn", {"order_id": order, "reason": reason})
    await _release_early(offer)
    nxt = await offer_next(order)
    for o in orders[1:]:
        if o not in (offer.get("early") or []):
            await offer_next(o)
    await offer_waiting()  # the rider who passed is free again: the oldest waiting order first
    return nxt


async def _release_early(offer: dict) -> None:
    """Orders that joined a batch offer while still cooking wait for their own turn again."""
    r = await get_redis()
    for o in offer.get("early") or []:
        await r.srem(ACTIVE, o)
        await r.zrem(WAITING, o)
        await r.zrem(RETRY, o)
        await r.delete(in_batch_offer_key(o))
        info = await order_info(o, refresh=True)
        if info and info.get("status") in DISPATCH_STATES and not info.get("driver_id"):
            await start_dispatch(o, info)  # it became almost ready while the batch offer was open


async def _clear_offer(rider: str, order: str) -> None:
    r = await get_redis()
    await r.delete(offer_key(order), f"rider:{rider}:offer_lock")
    state = await r.hgetall(state_key(rider))
    if state.get("order_id") == order and state.get("status") == "offered":
        await r.hset(state_key(rider), mapping={"status": "available", "order_id": ""})


async def _finish(order: str) -> None:
    r = await get_redis()
    await r.srem(ACTIVE, order)
    await r.zrem(RETRY, order)
    await r.zrem(OFFER_EXPIRY, order)
    await r.zrem(WAITING, order)
    await r.zrem(HOLD, order)


async def tick(now: float | None = None) -> dict[str, int]:
    """Expire offers past their window and retry orders waiting for a rider.
    ZREM decides which instance handles each one."""
    now = now or _now()
    r = await get_redis()
    counts = {"expired": 0, "retried": 0}
    for order in await r.zrangebyscore(OFFER_EXPIRY, 0, now):
        raw = await r.get(offer_key(order))
        offer = json.loads(raw) if raw else None
        if offer and await r.zrem(OFFER_EXPIRY, order):  # this instance handles it
            await decline(offer["rider_id"], order, "timeout")
            counts["expired"] += 1
        elif not offer:
            await r.zrem(OFFER_EXPIRY, order)
    due = await r.zrangebyscore(RETRY, 0, now)
    if due:  # oldest waiting first, not in the order their retry timers came up
        started = await r.zmscore(WAITING, due)
        due = [o for _, o in sorted(zip([x if x is not None else now for x in started], due))]
    for order in due:
        if await r.zrem(RETRY, order):
            await offer_next(order)
            counts["retried"] += 1
    return counts


# ── order events (from SQS) ───────────────────────────────────────────────────

DISPATCH_STATES = ("almost_ready", "ready")


async def on_order_event(event: dict) -> None:
    kind = event.get("event_type", "")
    p = event.get("payload", {})
    order = p.get("order_id")
    if not order:
        return
    r = await get_redis()
    status = p.get("new_status") or p.get("status")
    if await r.exists(info_key(order)):  # keep the cached info current
        info = json.loads(await r.get(info_key(order)))
        info.update(status=status or info.get("status"), driver_id=p.get("driver_id") or info.get("driver_id"))
        await _save_info(info)
    if (kind == "order.status_changed" and status in DISPATCH_STATES and not p.get("driver_id")
            and not await r.exists(in_batch_offer_key(order))):
        await start_dispatch(order)
    if kind in ("order.status_changed", "order.cancelled", "driver.assigned"):
        await _publish(order_tracking_channel(order), "status_change", {"order_id": order, "status": status,
                                                                        "driver_id": p.get("driver_id")})
    if kind == "order.cancelled" or status in ("delivered", "cancelled"):
        lead = await r.get(in_batch_offer_key(order))
        raw = await r.get(offer_key(lead or order))
        if raw:  # it was on an open offer (alone or in a batch): withdraw it, the rest go out alone
            offer = json.loads(raw)
            await r.zrem(OFFER_EXPIRY, lead or order)
            await _clear_offer(offer["rider_id"], lead or order)
            await _publish(rider_channel(offer["rider_id"]), "offer_withdrawn", {"order_id": lead or order, "reason": "cancelled"})
            await _release_early(offer)
            for o in [b["order_id"] for b in offer.get("batch") or []]:
                await r.delete(in_batch_offer_key(o))
                if o != order and o not in (offer.get("early") or []):
                    await r.zrem(HOLD, o)
                    await offer_next(o)
        await _finish(order)
        rider = p.get("driver_id")
        if rider:
            state = await r.hgetall(state_key(rider))
            left = [o for o in (state.get("batch") or "").split(",") if o and o != order]
            if state.get("order_id") == order or order in (state.get("batch") or "").split(","):
                if left:  # on to the next drop-off of the batch
                    nxt = state["order_id"] if state.get("order_id") in left else left[0]
                    await r.hset(state_key(rider), mapping={"status": "busy", "order_id": nxt, "batch": ",".join(left)})
                else:
                    await r.hset(state_key(rider), mapping={"status": "available", "order_id": ""})
                    await r.hdel(state_key(rider), "batch")
                    await _engaged(rider, False)
                    await offer_waiting()


# ── the dispatch map (P21) ───────────────────────────────────────────────────

async def riders_near(lat: float, lng: float, radius_km: float = 30) -> list[dict]:
    """Online riders around a point with their state and last fix."""
    r = await get_redis()
    near = await r.geosearch(GEO, longitude=lng, latitude=lat, radius=radius_km, unit="km", sort="ASC", count=500, withdist=True)
    out = []
    for rider, dist in near:
        if not await r.sismember(ONLINE, rider):
            continue
        fix = await last_fix(rider)
        if not fix:
            continue  # GPS gone quiet: not offered anything, not shown
        state = await r.hgetall(state_key(rider))
        out.append({"rider_id": rider, "lat": fix["lat"], "lng": fix["lng"], "at": fix["timestamp"], "km": round(float(dist), 2),
                    "status": state.get("status", "available"), "order_id": state.get("order_id") or None})
    return out


# ── SOS ───────────────────────────────────────────────────────────────────────

SOS_OPEN = "sos:open"
SOS_CHANNEL = "ops:sos"
EMERGENCY = {"IN": "112", "US": "911"}


async def raise_sos(rider: str, country: str, lat: float | None, lng: float | None, note: str | None) -> dict:
    """Store the alert (kept 7 days) and tell the ops consoles listening on ops:sos."""
    import uuid

    r = await get_redis()
    state = await r.hgetall(state_key(rider))
    order = state.get("order_id") or None
    fix = await last_fix(rider)
    if lat is None and fix:
        lat, lng = fix["lat"], fix["lng"]
    info = await order_info(order) if order else None
    alert = {"id": str(uuid.uuid4()), "rider_id": rider, "country": country, "order_id": order,
             "market_city": (info or {}).get("market_city"), "lat": lat, "lng": lng, "note": note,
             "at": datetime.now(UTC).isoformat()}
    await r.set(f"sos:{alert['id']}", json.dumps(alert), ex=7 * DAY)
    await r.zadd(SOS_OPEN, {alert["id"]: _now()})
    await _publish(SOS_CHANNEL, "sos", alert)
    logger.warning("rider_sos", **{k: v for k, v in alert.items() if k != "note"})
    return {**alert, "emergency_number": EMERGENCY.get(country, "112")}


async def open_sos(limit: int = 100) -> list[dict]:
    r = await get_redis()
    out = []
    for sid in await r.zrevrange(SOS_OPEN, 0, limit - 1):
        raw = await r.get(f"sos:{sid}")
        if raw:
            out.append(json.loads(raw))
        else:
            await r.zrem(SOS_OPEN, sid)
    return out


# ── shadow batching ───────────────────────────────────────────────────────────

async def shadow_suggestions(limit: int = 50) -> list[dict]:
    r = await get_redis()
    return [json.loads(x) for x in await r.lrange(SHADOW, 0, limit - 1)]


def within_window(ts_iso: str, seconds: int) -> bool:
    return datetime.fromisoformat(ts_iso) > datetime.now(UTC) - timedelta(seconds=seconds)
