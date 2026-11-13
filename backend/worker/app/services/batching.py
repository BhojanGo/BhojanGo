"""The batch engine's cycle (task 43): every BATCH_CYCLE_SECONDS, per city.

1. Read the orders waiting for a rider (almost ready or ready, no rider yet).
2. Shadow, every city: run the engine with its default settings (pairs and
   triples, kitchens up to 1.5 km apart) and send realtime the new
   suggestions. They're stored and logged; nothing is offered.
3. Live: run it again for pairs from the same kitchen only, which is what
   riders can be offered for now, and send them to realtime. Realtime offers
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
SELECT id, restaurant_id, restaurant_name, market_city, pickup_lat, pickup_lng, delivery_lat, delivery_lng,
       status_history, restaurant_accepted_at, estimated_prep_minutes, actual_ready_at, updated_at
FROM orders
WHERE status IN ('almost_ready', 'ready') AND driver_id IS NULL AND market_city IS NOT NULL
  AND pickup_lat IS NOT NULL AND delivery_lat IS NOT NULL AND created_at > :since
""")


def _pool_order(row) -> PoolOrder:  # type: ignore[no-untyped-def]
    """An order as the engine sees it. It joined the pool when it started looking for a rider."""
    history = row.status_history or []
    joined = next((h["at"] for h in history if h.get("status") in ("almost_ready", "ready")), None)
    created = datetime.fromisoformat(joined) if joined else row.updated_at
    if row.actual_ready_at:
        ready = row.actual_ready_at
    elif row.restaurant_accepted_at:
        ready = row.restaurant_accepted_at + timedelta(minutes=row.estimated_prep_minutes or 20)
    else:
        ready = created
    return PoolOrder(order_id=str(row.id), restaurant_id=str(row.restaurant_id), restaurant_name=row.restaurant_name or "",
                     pickup=(row.pickup_lat, row.pickup_lng), delivery=(row.delivery_lat, row.delivery_lng),
                     prep_ready_at=ready, created_at=created)


def _payload(b: BatchCandidate) -> dict:
    drops = [s.order_id for s in b.route if s.type == "delivery"]  # drop-off order; the first is the lead
    return {"orders": drops, "score": b.score, "savings_percent": b.savings_percent, "total_distance_km": b.total_distance_km,
            "total_time_min": b.total_time_min, "max_detour_min": b.max_detour_min}


def plan(orders: list[PoolOrder], now: datetime) -> tuple[list[dict], list[dict]]:
    """(shadow suggestions, live pairs) for one city's waiting orders."""
    if len(orders) < 2:
        return [], []
    start = (sum(o.pickup[0] for o in orders) / len(orders), sum(o.pickup[1] for o in orders) / len(orders))
    shadow = [_payload(b) for b in run_batch_cycle(orders, start, now).batches if len(b.orders) > 1]
    live = [_payload(b) for b in run_batch_cycle(orders, start, now, LIVE).batches
            if len(b.orders) == 2 and b.orders[0].restaurant_id == b.orders[1].restaurant_id]
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
    for row in rows:
        by_city.setdefault(row.market_city, []).append(_pool_order(row))
    counts = {"waiting": len(rows), "shadow": 0, "live": 0, "offered": 0}
    for city, orders in by_city.items():
        shadow, live = plan(orders, now)
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
