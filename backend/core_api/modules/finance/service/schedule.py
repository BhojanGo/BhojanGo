"""Weekly payout drafts (P13): on each live country's payout day (the
payout_schedule rule: weekly, on `day`, holding `hold_days` for refunds), make
a draft run for the previous Monday-to-Monday week if there isn't one. On the
payout day it also pays again what was sent back or didn't go through (R12:
the apps tell the payee that date)."""
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutRun, PayoutStatement
from core_api.modules.finance.service.payouts import (
    FinanceError,
    _provider,
    _rule,
    create_run,
    pay_pending,
    payout_tz,
    payout_weekday,
)

logger = structlog.get_logger(__name__)
SYSTEM = uuid.UUID(int=0)  # drafts made by the scheduler
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


async def ensure_weekly_drafts(db: AsyncSession, now: datetime | None = None) -> list[PayoutRun]:
    from core_api.modules.markets.models import Country

    now = now or datetime.now(UTC)
    made = []
    for c in (await db.execute(select(Country).where(Country.status.in_(("live", "beta"))))).scalars():
        sched = await _rule(db, c.code, "commission:payout_schedule") or {"day": "mon", "hold_days": 2}
        local = now.astimezone(payout_tz(c))  # R27: the country's payout zone
        week_start = (local - timedelta(days=local.weekday() + 7)).date()  # last week's Monday
        week_end = week_start + timedelta(days=7)
        pay_day = week_end + timedelta(days=DAYS.index(sched.get("day", "mon")))
        if local.date() < max(pay_day, week_end + timedelta(days=int(sched.get("hold_days", 2)))):
            continue
        exists = (await db.execute(select(PayoutRun.id).where(
            PayoutRun.country == c.code, PayoutRun.period_start == week_start))).first()
        if exists:
            continue
        try:
            run = await create_run(db, SYSTEM, c.code, week_start, week_end, now=now)
            made.append(run)
            logger.info("payout_draft_created", country=c.code, period=f"{week_start}..{week_end}")
        except FinanceError as e:
            logger.info("payout_draft_skipped", country=c.code, reason=str(e))
    return made


async def repay_unpaid(db: AsyncSession, now: datetime | None = None) -> int:
    """On each live country's payout day, pay again every statement of an approved run that
    was reversed or failed (a new transfer; pay_pending). Returns how many runs it retried."""
    from core_api.modules.markets.models import Country

    now = now or datetime.now(UTC)
    retried = 0
    for c in (await db.execute(select(Country).where(Country.status.in_(("live", "beta"))))).scalars():
        if now.astimezone(payout_tz(c)).weekday() != await payout_weekday(db, c.code):
            continue
        runs = (await db.execute(select(PayoutRun).where(
            PayoutRun.country == c.code, PayoutRun.status == "partially_paid",
            PayoutRun.id.in_(select(PayoutStatement.run_id).where(PayoutStatement.status.in_(("reversed", "failed"))))))).scalars().all()
        for run in runs:
            await pay_pending(db, run, await _provider(db, c.code))
            retried += 1
            logger.info("payout_repaid", country=c.code, run_id=str(run.id), status=run.status)
    return retried
