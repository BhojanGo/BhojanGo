"""Data retention (R8 F10): what the Privacy notices promise, enforced.

Every RETENTION_CYCLE_SECONDS (6 hours by default) the worker:

- deletes quick messages between customers and delivery partners 90 days after
  they were sent (order_messages);
- deletes support tickets 3 years after they were resolved (support_tickets; open
  ones stay until someone resolves them);
- makes sure every delivery route (realtime's ``trail:{order}`` lists in Redis) expires
  at most one day after its last position. Realtime already sets a one-day expiry on
  each fix; this catches any key left without one.

Idempotent and batched (DELETE ... WHERE id IN (SELECT ... LIMIT n), repeated until
nothing is left), so several worker replicas can run it at once. Each run logs its
counts, and a run that removed anything writes one row to the audit log
(action retention.purged). The periods are the notices' numbers: change both together.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)

MESSAGES_KEEP = timedelta(days=90)
TICKETS_KEEP = timedelta(days=3 * 365)
ROUTE_KEEP_SECONDS = 24 * 3600
BATCH = 1000
TRAIL_PATTERN = "trail:*"

_running = False


async def _purge(db: Any, sql: str, params: dict) -> int:
    """Run a batched DELETE until it removes nothing; the total removed."""
    total = 0
    while True:
        n = (await db.execute(text(sql), {**params, "batch": BATCH})).rowcount or 0
        total += n
        if n < BATCH:
            return total


async def purge_order_messages(db: Any, now: datetime) -> int:
    return await _purge(db, """
        DELETE FROM order_messages WHERE id IN (
            SELECT id FROM order_messages WHERE created_at < :cutoff ORDER BY created_at LIMIT :batch)""",
        {"cutoff": now - MESSAGES_KEEP})


async def purge_resolved_tickets(db: Any, now: datetime) -> int:
    return await _purge(db, """
        DELETE FROM support_tickets WHERE id IN (
            SELECT id FROM support_tickets WHERE status = 'resolved' AND resolved_at < :cutoff
            ORDER BY resolved_at LIMIT :batch)""",
        {"cutoff": now - TICKETS_KEEP})


async def cap_route_trails(redis: Any) -> int:
    """Every delivery route expires within a day: give any trail without an expiry
    (or with a longer one) a one-day expiry. Returns how many it had to fix."""
    fixed = 0
    async for key in redis.scan_iter(match=TRAIL_PATTERN, count=500):
        ttl = await redis.ttl(key)
        if ttl == -1 or ttl > ROUTE_KEEP_SECONDS:
            await redis.expire(key, ROUTE_KEEP_SECONDS)
            fixed += 1
    return fixed


async def run_once(now: datetime | None = None) -> dict[str, int]:
    """One retention pass over the database and Redis; returns the counts."""
    from shared.db import AsyncSessionLocal
    from shared.redis import get_redis

    now = now or datetime.now(UTC)
    counts = {"order_messages": 0, "support_tickets": 0, "route_trails_capped": 0}
    async with AsyncSessionLocal() as db:
        counts["order_messages"] = await purge_order_messages(db, now)
        counts["support_tickets"] = await purge_resolved_tickets(db, now)
        if counts["order_messages"] or counts["support_tickets"]:
            import json
            import uuid

            await db.execute(text("""
                INSERT INTO audit_log (id, actor_id, action, entity_type, entity_id, scope, before, after, at)
                VALUES (:id, NULL, 'retention.purged', 'retention', :day, '*', NULL, CAST(:after AS jsonb), now())"""),
                {"id": uuid.uuid4(), "day": now.date().isoformat(),
                 "after": json.dumps({**counts, "messages_older_than_days": MESSAGES_KEEP.days,
                                      "tickets_resolved_before_days": TICKETS_KEEP.days})})
        await db.commit()
    try:
        counts["route_trails_capped"] = await cap_route_trails(await get_redis())
    except Exception as e:  # noqa: BLE001 - the database part is done; Redis is checked again next run
        logger.warning("retention_routes_failed", error=str(e))
    logger.info("retention_run", **counts)
    return counts


async def run() -> None:
    from shared.config import get_settings

    global _running
    _running = True
    every = get_settings().worker.RETENTION_CYCLE_SECONDS
    logger.info("retention_started", cycle_seconds=every)
    while _running:
        try:
            await run_once()
        except Exception as e:  # noqa: BLE001 - keep going; the next run catches up
            logger.warning("retention_run_failed", error=str(e))
        await asyncio.sleep(every)


def stop() -> None:
    global _running
    _running = False
