"""The batch engine's cycle (task 43): every BATCH_CYCLE_SECONDS, per city.

1. Read the pool: orders without a rider that the kitchen has accepted, still
   cooking or ready (as in the original design: an order is in the pool from
   acceptance, so it can be paired with one that's almost ready).
2. Shadow, every city: run the engine with its default settings (pairs and
   triples, kitchens up to 1.5 km apart) and send realtime the new
   suggestions. They're stored and logged; nothing is offered.
3. Live: run it again for pairs from the same kitchen only, which is what
   riders can be offered for now, where at least one order is already looking
   for a rider, and send them to realtime. Realtime offers
   a pair only if the city's ``business:batching`` rule says live and both
   orders are still waiting, so a city that's off never sees one.
"""
import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from prometheus_client import Counter
from sqlalchemy import text

from app.batching.engine import CONFIG, BatchCandidate, PoolOrder, run_batch_cycle
from shared import internal_auth
from shared.config import get_settings
from shared.db import AsyncSessionLocal

logger = structlog.get_logger(__name__)

# What riders can be offered: two orders from the same kitchen.
LIVE = replace(CONFIG, max_orders_per_batch=2, max_pickup_radius_km=0.05)
SUGGESTED = Counter("bhojango_batch_suggestions_total", "Batches the engine found", ["city", "mode"])
PATH = "/internal/dispatch/batches"
_seen: dict[tuple, float] = {}  # shadow suggestions already sent (orders) -> when
_running = False

WAITING_SQL = text("""
SELECT id, status, restaurant_id, restaurant_name, market_city, pickup_lat, pickup_lng, delivery_lat, delivery_lng,
       status_history, restaurant_accepted_at, estimated_prep_minutes, actual_ready_at, updated_at
FROM orders
WHERE status IN ('accepted', 'preparing', 'almost_ready', 'ready') AND driver_id IS NULL AND market_city IS NOT NULL
  AND pickup_lat IS NOT NULL AND delivery_lat IS NOT NULL AND created_at > :since
""")


DISPATCHING = ("almost_ready", "ready")


def _pool_order(row, now: datetime | None = None) -> PoolOrder:  # type: ignore[no-untyped-def]
    """An order as the engine sees it. Its wait counts from when it started looking for a
    rider; one still cooking isn't waiting yet (so it never "expires" into a solo trip)."""
    now = now or datetime.now(UTC)
    history = row.status_history or []
    joined = next((h["at"] for h in history if h.get("status") in DISPATCHING), None)
    created = datetime.fromisoformat(joined) if joined else now
    if row.actual_ready_at:
        ready = row.actual_ready_at
    elif row.restaurant_accepted_at:
        ready = row.restaurant_accepted_at + timedelta(minutes=row.estimated_prep_minutes or 20)
    else:
        ready = created
    if getattr(row, "status", None) in DISPATCHING:
        ready = min(ready, now)  # the kitchen says it's (almost) done, whatever the estimate said
    return PoolOrder(order_id=str(row.id), restaurant_id=str(row.restaurant_id), restaurant_name=row.restaurant_name or "",
                     pickup=(row.pickup_lat, row.pickup_lng), delivery=(row.delivery_lat, row.delivery_lng),
                     prep_ready_at=ready, created_at=created)


def _payload(b: BatchCandidate) -> dict:
    drops = [s.order_id for s in b.route if s.type == "delivery"]  # drop-off order; the first is the lead
    return {"orders": drops, "score": b.score, "savings_percent": b.savings_percent, "total_distance_km": b.total_distance_km,
            "total_time_min": b.total_time_min, "max_detour_min": b.max_detour_min}


def plan(orders: list[PoolOrder], now: datetime, dispatching: set[str] | None = None) -> tuple[list[dict], list[dict]]:
    """(shadow suggestions, live pairs) for one city's pool. Live pairs need at least one
    order already looking for a rider (``dispatching``; all of them when not given)."""
    if len(orders) < 2:
        return [], []
    dispatching = {o.order_id for o in orders} if dispatching is None else dispatching
    start = (sum(o.pickup[0] for o in orders) / len(orders), sum(o.pickup[1] for o in orders) / len(orders))
    shadow = [_payload(b) for b in run_batch_cycle(orders, start, now).batches if len(b.orders) > 1]
    live = [_payload(b) for b in run_batch_cycle(orders, start, now, LIVE).batches
            if len(b.orders) == 2 and b.orders[0].restaurant_id == b.orders[1].restaurant_id
            and dispatching.intersection(b.order_ids)]
    return shadow, live


async def _send(client: httpx.AsyncClient, mode: str, city: str, batches: list[dict]) -> dict:
    body = json.dumps({"mode": mode, "city": city, "batches": batches}).encode()
    r = await client.post(PATH, content=body, headers={"content-type": "application/json", **internal_auth.sign("POST", PATH, body)})
    r.raise_for_status()
    return r.json()


async def cycle_once(client: httpx.AsyncClient, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(WAITING_SQL, {"since": now - timedelta(hours=3)})).all()
    by_city: dict[str, list[PoolOrder]] = {}
    dispatching = {str(row.id) for row in rows if row.status in DISPATCHING}
    for row in rows:
        by_city.setdefault(row.market_city, []).append(_pool_order(row, now))
    counts = {"waiting": len(rows), "shadow": 0, "live": 0, "offered": 0}
    for city, orders in by_city.items():
        shadow, live = plan(orders, now, dispatching)
        fresh = [b for b in shadow if tuple(sorted(b["orders"])) not in _seen]
        for b in fresh:
            _seen[tuple(sorted(b["orders"]))] = time.time()
        if fresh:
            await _send(client, "shadow", city, fresh)
            SUGGESTED.labels(city=city, mode="shadow").inc(len(fresh))
            counts["shadow"] += len(fresh)
        if live:
            res = await _send(client, "live", city, live)
            if res.get("offered"):
                SUGGESTED.labels(city=city, mode="live").inc(res["offered"])
                logger.info("batches_offered", city=city, offered=res["offered"])
            counts["live"] += len(live)
            counts["offered"] += int(res.get("offered", 0))
    for k, at in list(_seen.items()):  # forget suggestions after an hour
        if time.time() - at > 3600:
            del _seen[k]
    return counts


async def run() -> None:
    global _running
    _running = True
    s = get_settings().worker
    logger.info("batch_engine_started", cycle_seconds=s.BATCH_CYCLE_SECONDS, mode="shadow everywhere; live where a city turns it on")
    async with httpx.AsyncClient(base_url=s.REALTIME_INTERNAL_URL, timeout=10) as client:
        while _running:
            try:
                await cycle_once(client)
            except Exception as e:  # noqa: BLE001 - keep cycling; the next one may work
                logger.warning("batch_cycle_failed", error=str(e))
            await asyncio.sleep(s.BATCH_CYCLE_SECONDS)


def stop() -> None:
    global _running
    _running = False
