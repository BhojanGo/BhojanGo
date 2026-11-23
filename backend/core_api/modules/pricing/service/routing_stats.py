"""R32: how orders are priced: road distance (OSRM) or the fallback estimate.

Every delivery quote counts its routing source in Redis for the hour. When more than FALLBACK_ALERT_PCT of an
hour's quotes (at least MIN_VOLUME of them) used the fallback, admin Operations gets an alert (one per hour);
it is resolved when a later hour is healthy. The dashboard tile reads placed orders' pricing snapshots.
"""
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.redis import get_redis

logger = structlog.get_logger(__name__)
FALLBACK_ALERT_PCT = 5.0
MIN_VOLUME = 20
ALERT_NAME = "RoutingFallbackHigh"


def _hour(now: datetime) -> str:
    return now.strftime("%Y%m%d%H")


def fingerprint(now: datetime) -> str:
    return f"routing-fallback-{_hour(now)}"


def over_threshold(fallback: int, total: int) -> bool:
    return total >= MIN_VOLUME and fallback * 100 > FALLBACK_ALERT_PCT * total


async def record_routing(db: AsyncSession, source: str, now: datetime | None = None) -> None:
    """Count one priced delivery and raise/resolve the hourly fallback alert. Never fails a quote."""
    if source not in ("road", "fallback"):
        return  # straight_line (no OSRM configured) and pickup are not routing health
    now = now or datetime.now(UTC)
    try:
        redis = await get_redis()
        key = f"routing:{_hour(now)}"
        pipe = redis.pipeline()
        pipe.hincrby(key, source, 1)
        pipe.expire(key, 26 * 3600)
        pipe.hgetall(key)
        counts = (await pipe.execute())[2]
        c = {(k.decode() if isinstance(k, bytes) else k): int(v) for k, v in counts.items()}
        fb, total = c.get("fallback", 0), c.get("fallback", 0) + c.get("road", 0)
        if over_threshold(fb, total) and source == "fallback":
            await raise_alert(db, fb, total, now)
        elif total >= MIN_VOLUME and total % MIN_VOLUME == 0 and not over_threshold(fb, total):
            await resolve_alerts(db, now)  # a healthy hour (checked every MIN_VOLUME quotes) ends earlier alerts
    except Exception as e:  # noqa: BLE001
        logger.warning("routing_stats_failed", error=f"{type(e).__name__}: {e}"[:200])


async def raise_alert(db: AsyncSession, fallback: int, total: int, now: datetime) -> None:
    from core_api.modules.support.models import OpsAlert

    pct = round(fallback * 100 / total, 1)
    values = {"name": ALERT_NAME, "status": "firing", "severity": "warning", "city": None,
              "summary": f"Road routing is failing: {pct}% of deliveries priced by the estimate this hour",
              "description": f"{fallback} of {total} delivery prices this hour used straight-line distance x the road "
                             "factor because OSRM didn't answer. Check the osrm service (logs: routing_fallback).",
              "starts_at": now, "ends_at": None, "updated_at": now}
    # resolve earlier hours' alerts, then upsert this hour's
    await db.execute(update(OpsAlert).where(OpsAlert.name == ALERT_NAME, OpsAlert.status == "firing",
                                            OpsAlert.fingerprint != fingerprint(now))
                     .values(status="resolved", ends_at=now, updated_at=now))
    await db.execute(insert(OpsAlert).values(fingerprint=fingerprint(now), **values)
                     .on_conflict_do_update(index_elements=["fingerprint"], set_=values))
    await db.commit()
    logger.warning("routing_fallback_alert", fallback=fallback, total=total, pct=pct)


async def resolve_alerts(db: AsyncSession, now: datetime) -> None:
    from core_api.modules.support.models import OpsAlert

    r = await db.execute(update(OpsAlert).where(OpsAlert.name == ALERT_NAME, OpsAlert.status == "firing",
                                                OpsAlert.fingerprint != fingerprint(now))
                         .values(status="resolved", ends_at=now, updated_at=now))
    if r.rowcount:
        await db.commit()
        logger.info("routing_fallback_alert_resolved", alerts=r.rowcount)


async def routing_share(db: AsyncSession, hours: int = 24, now: datetime | None = None) -> dict:
    """Placed delivery orders in the last `hours`, by how their distance was measured (from the snapshots)."""
    from core_api.modules.pricing.models import OrderPricingSnapshot

    now = now or datetime.now(UTC)
    src = OrderPricingSnapshot.context["routing"].astext
    rows = (await db.execute(select(src, func.count()).where(OrderPricingSnapshot.created_at >= now - timedelta(hours=hours))
                             .group_by(src))).all()
    c = {(k or "unknown"): n for k, n in rows}
    road, fallback, straight = c.get("road", 0), c.get("fallback", 0), c.get("straight_line", 0)
    measured = road + fallback
    return {"hours": hours, "road": road, "fallback": fallback, "straight_line": straight,
            "pickup": c.get("none", 0), "road_pct": round(road * 100 / measured, 1) if measured else None,
            "fallback_pct": round(fallback * 100 / measured, 1) if measured else None,
            "alert_pct": FALLBACK_ALERT_PCT}
