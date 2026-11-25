"""R41 on Postgres: each order is in exactly one payout week (by delivered time in the payout zone), an order can
never be on two payout runs, a run is a Monday-to-Monday week, and demo-scale numbers stay realistic."""
import os
import random
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from core_api.integration.test_fee_model_v2 import boise_quote
from core_api.integration.test_orders_flow import client, login, new_order, pay  # noqa: F401
from core_api.integration.test_tax import place

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
ADMIN = "BhojanGoAdmin1"


async def rows(q: str, **p):  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(text(q), p)
        out = res.all() if res.returns_rows else []
        await db.commit()
        return out


async def delivered_at(order_id: str, at: datetime) -> None:
    await rows("UPDATE orders SET status = 'delivered', actual_delivery_time = CAST(:t AS timestamptz), "
               "created_at = CAST(:t AS timestamptz) - interval '40 minutes' WHERE id = CAST(:o AS uuid)", t=at, o=order_id)


async def week_ids(country: str, start: date) -> set[str]:
    from core_api.modules.finance.service import payouts
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        week = await payouts.week_statements(db, country, start, start + timedelta(days=7))
    return {o.order_id for o in week.orders}


async def paid_order(client: AsyncClient, country: str = "IN") -> str:  # noqa: F811
    """A real paid order in that country (Hyderabad or Boise): its city, currency and money are that country's."""
    if country == "IN":
        cust = await login(client, "customer1.hyd@example.com")
        order = await new_order(client, cust)
    else:
        cust = await login(client, "customer1.boi@example.com")
        rid, cart, q = await boise_quote(client, cust)
        order = await place(client, cust, rid, cart, q, "US")
    await pay(client, cust, order)
    return order["id"]


@pytest.mark.parametrize("country,zone", [("IN", "Asia/Kolkata"), ("US", "America/Boise")])
async def test_sunday_2359_and_monday_0000_go_to_their_own_weeks(client: AsyncClient, country: str, zone: str) -> None:  # noqa: F811
    tz = ZoneInfo(zone)
    monday = date(2004, 1, 5) + timedelta(weeks=random.randint(0, 500))  # an old week no other test uses
    sunday_late, monday_early = await paid_order(client, country), await paid_order(client, country)
    await delivered_at(sunday_late, datetime.combine(monday + timedelta(days=6), time(23, 59, 59), tzinfo=tz))
    await delivered_at(monday_early, datetime.combine(monday + timedelta(days=7), time(0, 0), tzinfo=tz))
    this, nxt = await week_ids(country, monday), await week_ids(country, monday + timedelta(days=7))
    assert sunday_late in this and sunday_late not in nxt
    assert monday_early in nxt and monday_early not in this


async def test_the_us_clock_change_week(client: AsyncClient) -> None:  # noqa: F811
    """26 Oct to 2 Nov 2026 (clocks go back on Sunday 1 Nov): Sunday 23:59 is that week, Monday 00:00 the next."""
    tz = ZoneInfo("America/Boise")
    a, b, c = await paid_order(client, "US"), await paid_order(client, "US"), await paid_order(client, "US")
    await delivered_at(a, datetime(2026, 11, 1, 1, 30, tzinfo=tz, fold=1))  # the second 01:30, after the change
    await delivered_at(b, datetime(2026, 11, 1, 23, 59, 59, tzinfo=tz))
    await delivered_at(c, datetime(2026, 11, 2, 0, 0, tzinfo=tz))
    week, after = await week_ids("US", date(2026, 10, 26)), await week_ids("US", date(2026, 11, 2))
    assert {a, b} <= week and c not in week and c in after and not ({a, b} & after)


async def test_an_order_is_on_one_payout_run_only(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy.exc import IntegrityError

    from core_api.modules.finance.models import PayoutRun, PayoutRunOrder, PayoutStatement
    from core_api.modules.finance.service import payouts
    from shared.db import AsyncSessionLocal

    oid = await paid_order(client)
    tz = ZoneInfo("Asia/Kolkata")
    monday = date(2004, 1, 5) + timedelta(weeks=random.randint(0, 500))
    await delivered_at(oid, datetime.combine(monday + timedelta(days=2), time(13), tzinfo=tz))
    async with AsyncSessionLocal() as db:
        run = await payouts.create_run(db, uuid.UUID(int=0), "IN", monday, monday + timedelta(days=7))
        await db.commit()
    (claimed,), = await rows("SELECT run_id FROM payout_run_orders WHERE order_id = CAST(:o AS uuid)", o=oid)
    assert claimed == run.id
    # The database refuses the same order on a second run
    async with AsyncSessionLocal() as db:
        other = PayoutRun(country="IN", currency="INR", period_start=monday + timedelta(days=7), period_end=monday + timedelta(days=14),
                          status="draft", created_by=uuid.UUID(int=0), totals={})
        db.add(other)
        await db.flush()
        db.add(PayoutRunOrder(order_id=uuid.UUID(oid), run_id=other.id))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
    # A run made before payout_run_orders existed (only its statement lines name the order) counts too: with the new
    # run gone and an old-style run for the week before naming the order, the order's week can't be paid again.
    await rows("DELETE FROM payout_statements WHERE run_id = CAST(:r AS uuid)", r=str(run.id))
    await rows("DELETE FROM payout_runs WHERE id = CAST(:r AS uuid)", r=str(run.id))  # its claim goes with it (cascade)
    assert not await rows("SELECT 1 FROM payout_run_orders WHERE order_id = CAST(:o AS uuid)", o=oid)
    async with AsyncSessionLocal() as db:
        legacy = PayoutRun(country="IN", currency="INR", period_start=monday - timedelta(days=7), period_end=monday,
                           status="draft", created_by=uuid.UUID(int=0), totals={})
        db.add(legacy)
        await db.flush()
        db.add(PayoutStatement(run_id=legacy.id, payee_type="restaurant", payee_id=uuid.uuid4(), payee_name="old run",
                               currency="INR", amount=0, summary={}, lines=[{"order_id": oid}]))
        await db.commit()
    async with AsyncSessionLocal() as db:
        with pytest.raises(payouts.FinanceError, match="already on payout run"):
            await payouts.create_run(db, uuid.UUID(int=0), "IN", monday, monday + timedelta(days=7))
        await db.rollback()


async def test_a_run_is_a_monday_to_monday_week() -> None:
    from sqlalchemy.exc import IntegrityError

    from core_api.modules.finance.models import PayoutRun
    from shared.db import AsyncSessionLocal

    tuesday = date(2008, 12, 16)
    for start, end in ((tuesday, tuesday + timedelta(days=7)), (date(2008, 12, 15), date(2008, 12, 23))):
        async with AsyncSessionLocal() as db:
            db.add(PayoutRun(country="US", currency="USD", period_start=start, period_end=end, status="draft",
                             created_by=uuid.UUID(int=0), totals={}))
            with pytest.raises(IntegrityError, match="ck_payout_runs_monday_week"):
                await db.flush()
            await db.rollback()


async def test_finance_shows_real_small_business_numbers(client: AsyncClient) -> None:  # noqa: F811
    """R41 item 4: what admin Finance shows for recent weeks looks like a real small business: no restaurant balance
    beyond ±₹50,000 / ±$1,000 and no chargeback under ₹100 / $5."""
    from core_api.modules.finance.service.payouts import ended_weeks

    since = ended_weeks(date.today())[-1][0]
    limit = {"INR": 5_000_000, "USD": 100_000}
    floor = {"INR": 10_000, "USD": 500}
    big = await rows("SELECT s.payee_name, s.currency, s.amount FROM payout_statements s JOIN payout_runs r ON r.id = s.run_id "
                     "WHERE r.period_start >= :d AND s.payee_type = 'restaurant'", d=since)
    assert not [(n, c, a) for n, c, a in big if abs(a) > limit[c]], big
    small = await rows("SELECT currency, amount, reason FROM payment_disputes WHERE opened_at >= now() - interval '60 days'")
    assert not [(c, a, r) for c, a, r in small if a < floor.get(c, 0)], small
