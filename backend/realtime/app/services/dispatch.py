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

Tracking
  Customers (and the assigned rider, and admins for the city) subscribe to
  ``tracking:{order}``: rider assigned, location + ETA, status changes. The last
  200 positions are kept for the map (``trail:{order}``, 24 h).

Batching
  Shadow mode only: when an order starts dispatch, nearby orders it could be
  batched with are logged and counted (``shadow:batch_suggestions``); nothing
  is batched.
"""
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.core.redis import get_redis, order_tracking_channel
from app.services.core_api import CoreApiError, core_api
from shared.config import get_settings
from shared.providers.routing import get_routing_provider, haversine_km

logger = structlog.get_logger(__name__)

GEO = "riders:geo"
ONLINE = "riders:online"
OFFER_EXPIRY = "offers:expiry"
RETRY = "dispatch:retry"
ACTIVE = "dispatch:active"
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
    return await r.hgetall(state_key(rider)) or {"status": "offline"}


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

async def order_info(order: str, refresh: bool = False) -> dict | None:
    r = await get_redis()
    raw = None if refresh else await r.get(info_key(order))
    if raw:
        return json.loads(raw)
    try:
        info = await core_api.dispatch_info(order)
    except CoreApiError as e:
        if e.status == 404:
            return None
        raise
    await r.set(info_key(order), json.dumps(info), ex=DAY)
    return info


async def _save_info(info: dict) -> None:
    r = await get_redis()
    await r.set(info_key(info["order_id"]), json.dumps(info), ex=DAY)


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
    await _shadow_batching(info)
    await _publish(order_tracking_channel(order), "searching_rider", {"order_id": order})
    return await offer_next(order)


async def offer_next(order: str) -> str | None:
    """Offer the order to the nearest free rider who hasn't declined it."""
    r = await get_redis()
    info = await order_info(order)
    if not info or info.get("driver_id") or not await r.sismember(ACTIVE, order):
        return None
    lat, lng = info["pickup"]
    declined = await r.smembers(declined_key(order))
    near = await r.geosearch(GEO, longitude=lng, latitude=lat, radius=_s().DISPATCH_RADIUS_KM, unit="km",
                             sort="ASC", count=25, withdist=True)
    timeout = int(info.get("offer_timeout_seconds") or 30)
    for rider, dist_km in near:
        if rider in declined or not await r.sismember(ONLINE, rider):
            continue
        if not await r.exists(loc_key(rider)):
            continue  # no GPS for a while: the app is probably closed
        # Claim the rider atomically: only one order can offer to them at a time.
        if not await r.set(f"rider:{rider}:offer_lock", order, nx=True, ex=timeout + 5):
            continue
        state = await r.hgetall(state_key(rider))
        if state.get("status") != "available":
            await r.delete(f"rider:{rider}:offer_lock")
            continue
        expires = _now() + timeout
        fix = await last_fix(rider)
        eta = eta_for(info, (fix["lat"], fix["lng"])) if fix else None
        offer = {"order_id": order, "rider_id": rider, "expires_at": _iso(expires), "expires_in": timeout,
                 "distance_km": round(float(dist_km), 2), "restaurant_name": info.get("restaurant_name"),
                 "pickup": info["pickup"], "dropoff": info.get("dropoff"), "eta": eta}
        await r.set(offer_key(order), json.dumps(offer), ex=timeout + 5)
        await r.hset(state_key(rider), mapping={"status": "offered", "order_id": order})
        await r.zadd(OFFER_EXPIRY, {order: expires})
        await _publish(rider_channel(rider), "offer", offer)
        logger.info("rider_offered", order_id=order, rider_id=rider, distance_km=round(float(dist_km), 2), timeout=timeout)
        return rider
    await r.zadd(RETRY, {order: _now() + _s().DISPATCH_RETRY_SECONDS})
    logger.info("no_rider_available", order_id=order, nearby=len(near), declined=len(declined))
    return None


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
    try:
        info = await core_api.assign_rider(order, rider)
    except CoreApiError as e:
        await _clear_offer(rider, order)
        await _finish(order)
        raise LookupError(e.args[0] if e.args else "The order is no longer available")
    await _save_info(info)
    await r.delete(offer_key(order), f"rider:{rider}:offer_lock")
    await r.srem(ACTIVE, order)
    await r.zrem(RETRY, order)
    await r.hset(state_key(rider), mapping={"status": "busy", "order_id": order})
    await _engaged(rider, True)
    fix = await last_fix(rider)
    eta = eta_for(info, (fix["lat"], fix["lng"])) if fix else None
    await _publish(order_tracking_channel(order), "rider_assigned", {"order_id": order, "rider_id": rider, "eta": eta,
                                                                    "location": fix})
    logger.info("rider_accepted", order_id=order, rider_id=rider)
    return {"order_id": order, "status": "assigned", "eta": eta, "pickup": info.get("pickup"), "dropoff": info.get("dropoff")}


async def decline(rider: str, order: str, reason: str = "passed") -> str | None:
    """A pass, a timeout or going offline: next rider."""
    r = await get_redis()
    raw = await r.get(offer_key(order))
    offer = json.loads(raw) if raw else None
    if not offer or offer["rider_id"] != rider:
        return None
    await r.zrem(OFFER_EXPIRY, order)
    await r.sadd(declined_key(order), rider)
    await r.expire(declined_key(order), DAY)
    await _clear_offer(rider, order)
    logger.info("offer_declined", order_id=order, rider_id=rider, reason=reason)
    await _publish(rider_channel(rider), "offer_withdrawn", {"order_id": order, "reason": reason})
    return await offer_next(order)


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
    for order in await r.zrangebyscore(RETRY, 0, now):
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
    if kind == "order.status_changed" and status in DISPATCH_STATES and not p.get("driver_id"):
        await start_dispatch(order)
    if kind in ("order.status_changed", "order.cancelled", "driver.assigned"):
        await _publish(order_tracking_channel(order), "status_change", {"order_id": order, "status": status,
                                                                        "driver_id": p.get("driver_id")})
    if kind == "order.cancelled" or status in ("delivered", "cancelled"):
        offer = await r.get(offer_key(order))
        if offer:
            await _clear_offer(json.loads(offer)["rider_id"], order)
        await _finish(order)
        rider = p.get("driver_id")
        if rider:
            state = await r.hgetall(state_key(rider))
            if state.get("order_id") == order:
                await r.hset(state_key(rider), mapping={"status": "available", "order_id": ""})
                await _engaged(rider, False)


# ── shadow batching ───────────────────────────────────────────────────────────

async def _shadow_batching(info: dict) -> None:
    """Which waiting orders this one could share a rider with (logged only)."""
    r = await get_redis()
    me = info["order_id"]
    for other in await r.smembers(ACTIVE):
        if other == me:
            continue
        raw = await r.get(info_key(other))
        o = json.loads(raw) if raw else None
        if not o or not o.get("pickup") or not o.get("dropoff") or not info.get("dropoff"):
            continue
        pickup_km = haversine_km(tuple(info["pickup"]), tuple(o["pickup"]))  # type: ignore[arg-type]
        drop_km = haversine_km(tuple(info["dropoff"]), tuple(o["dropoff"]))  # type: ignore[arg-type]
        if pickup_km <= 1.0 and drop_km <= 2.0:
            suggestion = {"orders": [me, other], "pickup_km": round(pickup_km, 2), "dropoff_km": round(drop_km, 2),
                          "at": datetime.now(UTC).isoformat(), "mode": "shadow"}
            await r.lpush(SHADOW, json.dumps(suggestion))
            await r.ltrim(SHADOW, 0, 499)
            logger.info("batch_shadow_suggestion", **suggestion)


async def shadow_suggestions(limit: int = 50) -> list[dict]:
    r = await get_redis()
    return [json.loads(x) for x in await r.lrange(SHADOW, 0, limit - 1)]


def within_window(ts_iso: str, seconds: int) -> bool:
    return datetime.fromisoformat(ts_iso) > datetime.now(UTC) - timedelta(seconds=seconds)
