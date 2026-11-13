"""Pilot KPIs as Prometheus gauges (P23), per city, refreshed every 30 seconds.

The numbers come from the same function as the admin overview (ops._totals),
so Grafana and the console always agree. Prometheus scrapes core_api's
/metrics; the alert rules in infra/observe/prometheus/alerts.yml use:

- bhojango_payment_failures_15m           payment failures in the last 15 minutes
- bhojango_payment_attempts_15m           payments that finished (succeeded or failed) in the last 15 minutes
- bhojango_orders_waiting_for_rider_5m    ready orders without a rider for more than 5 minutes
- (error spikes come from the HTTP metrics every service already exposes)
"""
import asyncio
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog
from prometheus_client import Gauge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
REFRESH_SECONDS = 30
L = ["country", "city"]

LIVE = Gauge("bhojango_orders_live", "Orders on their way now", L)
TODAY = Gauge("bhojango_orders_today", "Orders placed today (the city's local day)", L)
GMV = Gauge("bhojango_gmv_today", "Value of today's orders, in the country's currency", L + ["currency"])
MEDIAN = Gauge("bhojango_median_delivery_minutes", "Median delivery time today (completed orders, NaN under 5)", L)
ON_TIME = Gauge("bhojango_on_time_percent", "Delivered within 5 min of the promised time (late ones still out count)", L)
COMPLETED = Gauge("bhojango_completed_percent", "Finished orders that were delivered, not cancelled", L)
REFUNDED = Gauge("bhojango_refund_percent", "Delivered orders with a refund", L)
WAITING = Gauge("bhojango_orders_waiting_for_rider", "Ready (or almost) orders without a rider", L)
WAITING_5M = Gauge("bhojango_orders_waiting_for_rider_5m", "Orders without a rider for more than 5 minutes", L)
LATE = Gauge("bhojango_orders_late", "Orders more than 5 minutes past the promised time", L)
PAY_FAIL = Gauge("bhojango_payment_failures_15m", "Payments that failed in the last 15 minutes", L)
# The alert needs a rate, not a count: at a rush, ordinary card declines alone reach 3 in
# 15 minutes (pilot dress rehearsal), so it fires on failures as a share of attempts.
PAY_ATTEMPTS = Gauge("bhojango_payment_attempts_15m", "Payments that succeeded or failed in the last 15 minutes", L)
REFRESHED = Gauge("bhojango_kpi_refreshed_timestamp_seconds", "When these KPIs were last worked out")


def _pct(v: float | None) -> float:
    return math.nan if v is None else float(v)


async def refresh(db: AsyncSession, now: datetime | None = None) -> int:
    """Work out every city's KPIs and set the gauges; returns the number of cities."""
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.orders.api.v1.ops import RIDER_WAIT_ALERT, WAITING_FOR_RIDER, _totals, _tz
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import PaymentIntent, Refund

    now = now or datetime.now(UTC)
    cities = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                               .join(Country, Country.id == City.country_id))).all()
    orders = (await db.execute(select(Order).where(Order.created_at >= now - timedelta(hours=40)))).scalars().all()
    ids = [o.id for o in orders]
    refunds = {i: True for (i,) in (await db.execute(select(Refund.order_id).where(Refund.order_id.in_(ids))))} if ids else {}
    finished = (await db.execute(select(Order.market_city, PaymentIntent.status).join(PaymentIntent, PaymentIntent.order_id == Order.id).where(
        PaymentIntent.status.in_(("failed", "succeeded")), PaymentIntent.updated_at >= now - timedelta(minutes=15)))).all()
    fails: dict[str, int] = defaultdict(int)
    attempts: dict[str, int] = defaultdict(int)
    for city, status in finished:
        attempts[city or ""] += 1
        if status == "failed":
            fails[city or ""] += 1
    by_city: dict[str, list] = defaultdict(list)  # type: ignore[type-arg]
    for o in orders:
        by_city[o.market_city or ""].append(o)

    for c, r, k in cities:
        tz = _tz(c, r, k)
        start = datetime.combine(now.astimezone(tz).date(), datetime.min.time(), tzinfo=tz).astimezone(UTC)
        mine = by_city[c.code]
        t = _totals(mine, refunds, start, now)
        lab = {"country": k.code, "city": c.code}
        LIVE.labels(**lab).set(t.live)
        TODAY.labels(**lab).set(t.today)
        GMV.labels(**lab, currency=k.currency).set(float(t.gmv_today))
        MEDIAN.labels(**lab).set(_pct(t.median_delivery_min))
        ON_TIME.labels(**lab).set(_pct(t.on_time_pct))
        COMPLETED.labels(**lab).set(_pct(t.completed_pct))
        REFUNDED.labels(**lab).set(_pct(t.refund_pct))
        WAITING.labels(**lab).set(t.waiting_for_rider)
        WAITING_5M.labels(**lab).set(sum(1 for o in mine if o.status in WAITING_FOR_RIDER and o.driver_id is None
                                         and (o.actual_ready_at or o.updated_at) and now - (o.actual_ready_at or o.updated_at) > RIDER_WAIT_ALERT))
        LATE.labels(**lab).set(t.late)
        PAY_FAIL.labels(**lab).set(fails.get(c.code, 0))
        PAY_ATTEMPTS.labels(**lab).set(attempts.get(c.code, 0))
    REFRESHED.set(now.timestamp())
    return len(cities)


async def refresh_forever() -> None:
    from shared.db import AsyncSessionLocal

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await refresh(db)
        except Exception as e:  # noqa: BLE001 - keep measuring
            logger.warning("kpi_refresh_failed", error=str(e))
        await asyncio.sleep(REFRESH_SECONDS)
