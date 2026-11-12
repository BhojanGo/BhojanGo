"""Weekly payout drafts (P13): on each live country's payout day (the
payout_schedule rule: weekly, on `day`, holding `hold_days` for refunds), make
a draft run for the previous Monday-to-Monday week if there isn't one."""
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.finance.models import PayoutRun
from core_api.modules.finance.service.payouts import FinanceError, _rule, create_run

logger = structlog.get_logger(__name__)
SYSTEM = uuid.UUID(int=0)  # drafts made by the scheduler
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


async def ensure_weekly_drafts(db: AsyncSession, now: datetime | None = None) -> list[PayoutRun]:
    from core_api.modules.markets.models import Country

    now = now or datetime.now(UTC)
    made = []
    for c in (await db.execute(select(Country).where(Country.status.in_(("live", "beta"))))).scalars():
        sched = await _rule(db, c.code, "commission:payout_schedule") or {"day": "mon", "hold_days": 2}
        local = now.astimezone(ZoneInfo(c.timezone))
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
            run = await create_run(db, SYSTEM, c.code, week_start, week_end)
            made.append(run)
            logger.info("payout_draft_created", country=c.code, period=f"{week_start}..{week_end}")
        except FinanceError as e:
            logger.info("payout_draft_skipped", country=c.code, reason=str(e))
    return made
