"""The monthly budget for offers BhojanGo pays for (R37).

An offer the platform funds (``funded_by: platform``) comes out of BhojanGo's own money, so it
runs only while a budget set by an admin has room for it. The budget is a Markets setting,
``platform_offer_budget``, in the country's currency:

    {"monthly": "5000"}

set on a country, a state or a city (admin: Pricing, Offer budgets). The nearest level that
sets one is the *pool* an order's offers are paid from: a city with its own budget spends
its own; a city without one shares its state's, then its country's. No budget anywhere is a
budget of 0, so BhojanGo-funded offers are off until an admin gives them one (the seeds set
none, and pause those offers too).

Spend is counted per pool and calendar month (market time) in ``platform_offer_spend`` when
an order is placed (QuoteService.attach), under a row lock:

  * a quote offers a BhojanGo-funded discount only when its whole cost fits in what's left
    (no partial offer: budget 10, offer 3 -> three orders get it, the fourth doesn't);
  * placing the order checks again; an offer that no longer fits refuses the order
    (OFFER_ENDED) and the customer's bag prices again, without it;
  * Operations gets an alert (ops_alerts, the admin console) at 80% of the month's budget and
    at 100%: spent in full, or too little left to pay for the offer just given again
    (the offers have stopped).

Restaurant-funded offers are not affected: they have their own weekly caps.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

SETTING = "platform_offer_budget"
ALERT_NAME = "PlatformOfferBudget"
THRESHOLDS = (80, 100)
MAX_VALUE = Decimal("100000000")
ZERO = Decimal("0")


class BudgetError(ValueError):
    """A bad budget setting; the message is shown to the admin."""


class OfferEnded(ValueError):
    """The month's budget can't pay for this order's BhojanGo-funded offer any more."""


def parse(value: Any) -> Decimal | None:
    """A stored setting's monthly amount, or None when it isn't a valid one."""
    if not isinstance(value, dict) or isinstance(value.get("monthly"), bool):
        return None
    try:
        d = Decimal(str(value.get("monthly")))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() and ZERO <= d <= MAX_VALUE else None


def check_settings(patch: dict) -> None:
    """When an admin saves settings: {"monthly": amount >= 0}, or None (inherit again)."""
    if SETTING not in patch or patch[SETTING] is None:
        return
    value = patch[SETTING]
    if not isinstance(value, dict) or set(value) != {"monthly"} or parse(value) is None:
        raise BudgetError(f'{SETTING} must be {{"monthly": "5000"}}: an amount from 0 to {MAX_VALUE:,}')


@dataclass(frozen=True)
class Pool:
    level: str  # country | region | city
    code: str
    name: str
    currency: str
    monthly: Decimal  # 0: none set anywhere

    @property
    def key(self) -> str:
        return f"{self.level}:{self.code}"


def pool_for(levels: list[tuple[str, str, str, dict | None]], currency: str) -> Pool:
    """The pool for a place: ``levels`` are (level, code, name, settings), widest first (country,
    state, city). The nearest level that sets a budget; none: the widest level with 0."""
    for level, code, name, settings in reversed(levels):
        monthly = parse((settings or {}).get(SETTING))
        if monthly is not None:
            return Pool(level, code, name, currency, monthly)
    level, code, name, _ = levels[0]
    return Pool(level, code, name, currency, ZERO)


def month_of(local: datetime | date) -> date:
    return date(local.year, local.month, 1)


async def chain(db: AsyncSession, country: str, region: str | None = None, city: str | None = None) -> tuple[list, str]:
    """(levels, currency) for pool_for, from market codes."""
    from core_api.modules.markets.models import City, Country, Region

    c = (await db.execute(select(Country).where(Country.code == country))).scalars().first()
    if c is None:
        return [("country", country, country, None)], ""
    levels: list = [("country", c.code, c.name, c.settings)]
    if region:
        r = (await db.execute(select(Region).where(Region.code == region))).scalars().first()
        if r is not None:
            levels.append(("region", r.code, r.name, r.settings))
    if city:
        ci = (await db.execute(select(City).where(City.code == city))).scalars().first()
        if ci is not None:
            levels.append(("city", ci.code, ci.name, ci.settings))
    return levels, c.currency


async def pool_at(db: AsyncSession, country: str, region: str | None = None, city: str | None = None) -> Pool:
    levels, currency = await chain(db, country, region, city)
    return pool_for(levels, currency)


async def spent(db: AsyncSession, pool_key: str, month: date) -> tuple[Decimal, int]:
    from core_api.modules.pricing.models import PlatformOfferSpend

    row = await db.get(PlatformOfferSpend, (pool_key, month))
    return (Decimal(row.spent), row.orders) if row else (ZERO, 0)


async def left(db: AsyncSession, pool: Pool, month: date) -> Decimal:
    """What the pool has left this month (never below 0)."""
    used, _ = await spent(db, pool.key, month)
    return max(pool.monthly - used, ZERO)


async def record(db: AsyncSession, pool: Pool, month: date, cost: Decimal, now: datetime) -> Decimal:
    """Count an order's BhojanGo-funded offers against the pool (row locked), or OfferEnded when
    they no longer fit. Raises the 80% / 100% alerts. Returns what is left."""
    from core_api.modules.pricing.models import PlatformOfferSpend

    row = await db.get(PlatformOfferSpend, (pool.key, month), with_for_update=True)
    if row is None:
        row = PlatformOfferSpend(pool=pool.key, month=month, currency=pool.currency, spent=ZERO, orders=0, alerted=0)
        db.add(row)
    before = Decimal(row.spent)
    if before + cost > pool.monthly:
        raise OfferEnded(f"BhojanGo's offer budget for {pool.name} is used up this month")
    row.spent = before + cost
    row.orders += 1
    now_left = pool.monthly - Decimal(row.spent)
    pct = int(Decimal(row.spent) * 100 / pool.monthly) if pool.monthly > 0 else 100
    # 100%: spent in full, or not enough left to give this offer once more (it has stopped)
    level = 100 if (pct >= 100 or now_left < cost) else 80 if pct >= 80 else 0
    if level > (row.alerted or 0):
        for t in THRESHOLDS:
            if (row.alerted or 0) < t <= level:
                await _alert(db, pool, month, t, Decimal(row.spent), now)
        row.alerted = level
    await db.flush()
    return now_left


def fingerprint(pool: Pool, month: date, threshold: int) -> str:
    return f"offer-budget:{pool.key}:{month.isoformat()[:7]}:{threshold}"


async def _alert(db: AsyncSession, pool: Pool, month: date, threshold: int, used: Decimal, now: datetime) -> None:
    from shared.money import format_money
    from core_api.modules.support.models import OpsAlert

    m = lambda v: format_money(v, pool.currency)  # noqa: E731
    stopped = threshold >= 100
    values = {
        "name": ALERT_NAME, "status": "firing", "severity": "critical" if stopped else "warning",
        "city": pool.code[:20],
        "summary": (f"BhojanGo-funded offers stopped in {pool.name}: this month's offer budget is used up"
                    if stopped else f"BhojanGo-funded offers in {pool.name} have used 80% of this month's budget"),
        "description": (f"{m(used)} of {m(pool.monthly)} spent in {month:%B %Y}. "
                        + ("Offers BhojanGo pays for no longer apply here until next month or a bigger budget "
                           "(admin: Pricing, Offer budgets)." if stopped else
                           "They stop by themselves at 100%. Raise the budget in admin (Pricing, Offer budgets) to keep them running.")),
        "starts_at": now, "ends_at": None, "updated_at": now,
    }
    fp = fingerprint(pool, month, threshold)
    exists = (await db.execute(select(OpsAlert.id).where(OpsAlert.fingerprint == fp))).first()
    if exists:
        await db.execute(update(OpsAlert).where(OpsAlert.fingerprint == fp).values(**values))
    else:
        await db.execute(insert(OpsAlert).values(fingerprint=fp, **values))
    logger.warning("platform_offer_budget_alert", pool=pool.key, month=month.isoformat(), threshold=threshold,
                   spent=str(used), budget=str(pool.monthly))
