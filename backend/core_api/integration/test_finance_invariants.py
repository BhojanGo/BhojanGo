"""R14: the money adds up, every week, in every country (runs in CI with the integration suites).

For each of the last weeks that have ended, a payout run is prepared (inside a transaction
that is rolled back, so nothing stays) and compared with Reconciliation for the same week:
  - the run's kitchen and delivery partner totals equal "Kitchens are owed" and "Delivery
    partners are owed" to the cent (minimum pay top-ups included on both sides);
  - captured = refunded + kitchens owed + delivery partners owed + tax owed + platform revenue;
  - tax owed = customers' tax + GST on our commission + TDS, the last two equal to the run's (R16);
  - each kitchen's commission tax invoice: GST = the sum of "Tax on commission" on its statements for
    the week, to the paisa, each order's amount rounded once (R17);
  - R25: every kitchen statement with tax on commission: its invoice, built as the API builds it
    (commission_invoice.for_statement), has the run's period, the statement's orders (= its order
    lines), commission and GST; one statement row, never another week's;
  - platform after payment fees = platform revenue - payment fees;
  - the top-ups in the run, Reconciliation and the contribution report are the same amount;
  - R23, kitchens below zero: a balance carried in from an earlier week (one is added to every
    week here) is on the kitchen's statement, netted into its amount, and the run and Reconciliation
    (before and after the run is prepared) agree on it:
        kitchens paid = kitchens are owed + carried from last week - carried to next week
    with the statements adding up to exactly that; nothing below zero is written off.
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

    from datetime import timedelta

    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.finance.models import PayoutRun, PayoutStatement
    from core_api.modules.finance.service import commission_invoice as ci
    from core_api.modules.finance.service import payouts
    from core_api.modules.finance.service.statements import m
    from core_api.modules.finance.service.contribution import contribution
    from core_api.modules.markets.models import Country
    from core_api.modules.markets.service import legal
    from shared.db import AsyncSessionLocal, engine

    checked = invoices = 0
    try:
        async with AsyncSessionLocal() as db:
            countries = (await db.execute(select(Country).where(Country.status.in_(("live", "beta"))))).scalars().all()
            for c in countries:
                today = datetime.now(UTC).astimezone(ZoneInfo(c.timezone)).date()
                for start, end in payouts.ended_weeks(today, WEEKS):
                    async with db.begin_nested() as tx:  # the run is thrown away
                        # R23: a kitchen left -123.45 below zero by an earlier run (a day's run ending at
                        # this week's start), so every week checked carries a balance explicitly.
                        kitchen = (await db.execute(select(Restaurant.id).where(Restaurant.country == c.code)
                                                    .order_by(Restaurant.name).limit(1))).scalar()
                        carried_before = 0
                        if kitchen is not None:
                            already = (await payouts.open_carries(db, c.code, start)).get(str(kitchen))
                            carried_before = (already.amount if already else 0) - 12345
                            earlier = PayoutRun(country=c.code, currency=c.currency, period_start=start - timedelta(days=1),
                                                period_end=start, status="paid", created_by=uuid.UUID(int=0), totals={})
                            db.add(earlier)
                            await db.flush()
                            db.add(PayoutStatement(run_id=earlier.id, payee_type="restaurant", payee_id=kitchen, payee_name="",
                                                   currency=c.currency, amount=-12345, summary={}, lines=[], status="carried",
                                                   negative_weeks=1, negative_since=start - timedelta(days=1)))
                            await db.flush()
                        before = (await payouts.reconciliation(db, c.code, start, end))["money"]
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
                        # R23: the carry, in the run, in Reconciliation and on the statements
                        kitchens = (await db.execute(select(PayoutStatement).where(
                            PayoutStatement.run_id == run.id, PayoutStatement.payee_type == "restaurant"))).scalars().all()
                        if kitchen is not None:
                            mine = next(s for s in kitchens if s.payee_id == kitchen)
                            assert mine.carried_in == carried_before, (where, mine.carried_in, carried_before)
                            assert mine.amount == payouts._minor(Decimal(mine.summary["net"])) + mine.carried_in, where
                            assert rec["kitchen_carried_in"] <= -12345, where
                        assert rec["restaurant_to_pay"] == (rec["restaurant_payable"] + rec["kitchen_carried_in"]
                                                            - rec["kitchen_carried_forward"]), (where, rec)
                        assert sum(s.amount for s in kitchens) == rec["restaurant_payable"] + rec["kitchen_carried_in"], where
                        assert sum(s.carried_in for s in kitchens) == rec["kitchen_carried_in"], where
                        assert sum(s.amount for s in kitchens if s.amount > 0) == rec["restaurant_to_pay"], where
                        assert sum(s.amount for s in kitchens if s.amount < 0) == rec["kitchen_carried_forward"], where
                        for k in ("kitchen_carried_in", "kitchen_carried_forward", "restaurant_to_pay"):
                            assert before[k] == rec[k], (where, k, before[k], rec[k])  # Reconciliation before the run = the run
                        assert payouts._minor(Decimal(run.totals["kitchen_carried_in"])) == rec["kitchen_carried_in"], where
                        assert payouts._minor(Decimal(run.totals["kitchen_carried_forward"])) == rec["kitchen_carried_forward"], where
                        assert payouts._minor(Decimal(run.totals["restaurants_to_pay"])) == rec["restaurant_to_pay"], where
                        assert not await payouts.open_carries(db, c.code, start), where  # every earlier balance was carried
                        # R16: tax owed by type (customers' tax, GST on our commission, TDS) adds up, and the
                        # two taken from kitchen payouts are exactly what the run takes.
                        by_type = (await payouts.reconciliation(db, c.code, start, end))["tax_owed_by_type"]
                        assert sum(by_type.values()) == rec["tax_owed"], (where, by_type, rec["tax_owed"])
                        assert payouts._minor(Decimal(run.totals["commission_tax"])) == by_type["commission"], where
                        assert payouts._minor(Decimal(run.totals["tds"])) == by_type["tds"], where
                        # R17: one rounding method (per order) on statements and invoices alike
                        stmts = (await db.execute(select(PayoutStatement).where(
                            PayoutStatement.run_id == run.id, PayoutStatement.payee_type == "restaurant"))).scalars().all()
                        for s in stmts:
                            pct = Decimal(s.summary.get("commission_tax_percent") or 0)
                            for ln in s.lines:
                                assert -Decimal(ln["commission_tax"]) == m(-Decimal(ln["commission"]) * pct / 100), (where, ln)
                            commission, tax, orders = ci.totals([s.lines])
                            assert tax == Decimal(s.summary["commission_tax"]), (where, s.payee_name, tax)
                            assert commission == Decimal(s.summary["commission"]) and orders == s.summary["orders"], where
                        assert sum((ci.totals([s.lines])[1] for s in stmts), Decimal(0)) == Decimal(run.totals["commission_tax"]), where
                        # R25: each invoice is its own statement's: period, orders, commission and GST
                        supplier = legal.entity(c.settings, c.tax_regime)
                        for s in stmts:
                            if Decimal(str(s.summary.get("commission_tax") or 0)) <= 0:
                                continue  # no tax on commission: no invoice (409 NO_COMMISSION_TAX)
                            if not supplier.get("name"):
                                with pytest.raises(ci.LegalEntityMissing):
                                    ci.for_statement(s, run, supplier, {"name": s.payee_name}, issued_at=datetime.now(UTC))
                                continue
                            inv = ci.for_statement(s, run, supplier, {"name": s.payee_name}, issued_at=datetime.now(UTC))
                            who = (where, s.payee_name)
                            assert (inv.period_start, inv.period_end) == (run.period_start, run.period_end) == (start, end), who
                            assert inv.orders == s.summary["orders"] == len(s.lines), who
                            assert inv.commission == Decimal(s.summary["commission"]), who
                            assert inv.tax == Decimal(s.summary["commission_tax"]), who
                            assert inv.rate_percent == Decimal(str(s.summary["commission_tax_percent"])), who
                            invoices += 1
                        rep = await contribution(db, c.code, start, end)
                        top_ups = Decimal(rep["all"]["totals"]["min_pay_top_ups"])
                        assert abs(payouts._minor(top_ups) - rec["min_pay_top_ups"]) <= len(rep["cities"]), where  # per-order shares round
                        await tx.rollback()
                        checked += 1
            await db.rollback()
    finally:
        await engine.dispose()
    assert checked >= 1, "no week could be checked"
    print(f"invariants: {checked} week(s) checked, {invoices} commission tax invoice(s) matched their statements")
