"""R14: the money adds up, every week, in every country (runs in CI with the integration suites).

For each of the last weeks that have ended, a payout run is prepared (inside a transaction
that is rolled back, so nothing stays) and compared with Reconciliation for the same week:
  - the run's kitchen and delivery partner totals equal "Kitchens are owed" and "Delivery
    partners are owed" to the cent (minimum pay top-ups included on both sides);
  - captured = refunded + kitchens owed + delivery partners owed + tax owed + platform revenue;
  - tax owed = customers' tax + GST on our commission + TDS, the last two equal to the run's (R16);
  - platform after payment fees = platform revenue - payment fees;
  - the top-ups in the run, Reconciliation and the contribution report are the same amount.
"""
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)
WEEKS = 4


async def test_runs_and_reconciliation_agree_every_week() -> None:
    from sqlalchemy import select

    from core_api.modules.finance.service import payouts
    from core_api.modules.finance.service.contribution import contribution
    from core_api.modules.markets.models import Country
    from shared.db import AsyncSessionLocal, engine

    checked = 0
    try:
        async with AsyncSessionLocal() as db:
            countries = (await db.execute(select(Country).where(Country.status.in_(("live", "beta"))))).scalars().all()
            for c in countries:
                today = datetime.now(UTC).astimezone(ZoneInfo(c.timezone)).date()
                for start, end in payouts.ended_weeks(today, WEEKS):
                    async with db.begin_nested() as tx:  # the run is thrown away
                        try:
                            run = await payouts.create_run(db, uuid.UUID(int=0), c.code, start, end)
                        except payouts.FinanceError:
                            await tx.rollback()
                            continue  # a run already covers part of this week (another test's)
                        rec = (await payouts.reconciliation(db, c.code, start, end))["money"]
                        where = f"{c.code} {start}..{end}"
                        assert payouts._minor(Decimal(run.totals["restaurants"])) == rec["restaurant_payable"], where
                        assert payouts._minor(Decimal(run.totals["riders"])) == rec["rider_payable"], where
                        assert payouts._minor(Decimal(run.totals["min_pay_top_ups"])) == rec["min_pay_top_ups"], where
                        assert rec["captured"] == (rec["refunded"] + rec["restaurant_payable"] + rec["rider_payable"]
                                                   + rec["tax_owed"] + rec["platform_revenue"]), (where, rec)
                        assert rec["platform_after_payment_fees"] == rec["platform_revenue"] - rec["payment_fees"], where
                        # R16: tax owed by type (customers' tax, GST on our commission, TDS) adds up, and the
                        # two taken from kitchen payouts are exactly what the run takes.
                        by_type = (await payouts.reconciliation(db, c.code, start, end))["tax_owed_by_type"]
                        assert sum(by_type.values()) == rec["tax_owed"], (where, by_type, rec["tax_owed"])
                        assert payouts._minor(Decimal(run.totals["commission_tax"])) == by_type["commission"], where
                        assert payouts._minor(Decimal(run.totals["tds"])) == by_type["tds"], where
                        rep = await contribution(db, c.code, start, end)
                        top_ups = Decimal(rep["all"]["totals"]["min_pay_top_ups"])
                        assert abs(payouts._minor(top_ups) - rec["min_pay_top_ups"]) <= len(rep["cities"]), where  # per-order shares round
                        await tx.rollback()
                        checked += 1
            await db.rollback()
    finally:
        await engine.dispose()
    assert checked >= 1, "no week could be checked"
