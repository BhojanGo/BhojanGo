"""R23 on Postgres: a kitchen's week below zero is carried into its next statement ("Carried
from last week"), nothing is paid until it is covered, it is never written off and the kitchen
is never charged. Four weeks below zero in a row: admin Finance lists it to collect.

A week below zero is made the way a payout run leaves one (a statement whose amount is below
zero: refunds the kitchen caused outweighed its sales; the arithmetic of such a week is in
finance/tests/test_carry.py). The weeks after it are real runs over real orders."""
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import login
from core_api.integration.test_payments_refunds import delivered_order
from core_api.integration.test_payouts import ADMIN, client, deliver_last_week, ist_last_week  # noqa: F401 - the client fixture

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture(autouse=True)
async def _no_earlier_runs():
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM payout_statements"))
        await db.execute(text("DELETE FROM payout_runs"))
        await db.execute(text("DELETE FROM payout_accounts"))
        await db.commit()
    yield


def cents(v: str) -> int:
    return int((Decimal(v) * 100).to_integral_value())


async def week_below_zero(restaurant_id: str, start: date, amount: int) -> tuple[str, str]:
    """A prepared run for the week from ``start`` whose kitchen statement is ``amount`` (minor, < 0)."""
    from core_api.modules.finance.models import PayoutRun, PayoutStatement
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        run = PayoutRun(country="IN", currency="INR", period_start=start, period_end=start + timedelta(days=7), status="draft",
                        created_by=uuid.UUID(int=0), totals={"orders": 1})
        db.add(run)
        await db.flush()
        st = PayoutStatement(run_id=run.id, payee_type="restaurant", payee_id=uuid.UUID(restaurant_id), payee_name="Spice Route Kitchen",
                             currency="INR", amount=amount, summary={"orders": 1, "net": str(Decimal(amount) / 100)}, lines=[])
        db.add(st)
        await db.commit()
        return str(run.id), str(st.id)


async def statement_of(client: AsyncClient, h: dict, run_id: str, restaurant_id: str) -> dict:  # noqa: F811
    run = (await client.get(f"/api/v1/finance/payout-runs/{run_id}", headers=h)).json()
    sid = next(s["id"] for s in run["statements"] if s["payee_id"] == restaurant_id)
    return (await client.get(f"/api/v1/finance/statements/{sid}", headers=h)).json()


async def no_charges() -> None:
    """Nothing below zero was ever sent to a provider, and every transfer is money to the payee."""
    from sqlalchemy import select

    from core_api.modules.finance.models import PayoutStatement
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for st in (await db.execute(select(PayoutStatement))).scalars():
            if st.transfer_id:
                assert st.amount > 0, (st.payee_name, st.amount)
            if st.amount < 0:
                assert st.status in ("carried", "pending") and st.transfer_id is None, (st.payee_name, st.status)


async def test_a_negative_week_is_carried_and_next_weeks_sales_cover_it(client: AsyncClient) -> None:  # noqa: F811
    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)  # Spice Route Kitchen
    await deliver_last_week(order["id"])
    spice = order["restaurant_id"]
    last_start, last_end = ist_last_week()
    before_run, before = await week_below_zero(spice, last_start - timedelta(days=7), -5000)  # -₹50.00

    admin = await login(client, "admin@example.com", ADMIN)
    finance = await login(client, "finance.in@example.com", ADMIN)
    # The week below zero is approved: nothing is sent, and the balance is kept for next week.
    r = await client.post(f"/api/v1/finance/payout-runs/{before_run}/approve", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"  # the run is settled: nothing left to send in it

    # Reconciliation for last week, before its run is prepared, already carries the balance in.
    params = {"country": "IN", "start": last_start.isoformat(), "end": last_end.isoformat()}
    preview = (await client.get("/api/v1/finance/reconciliation", headers=finance, params=params)).json()["money"]

    r = await client.post("/api/v1/finance/payout-runs", headers=finance,
                          json={"country": "IN", "period_start": last_start.isoformat(), "period_end": last_end.isoformat()})
    assert r.status_code == 201, r.text
    run = r.json()
    stmt = await statement_of(client, finance, run["id"], spice)
    week_net = cents(stmt["summary"]["net"])
    assert week_net > 5000, stmt["summary"]
    # The core of R23: next week's payout is reduced by the carried balance (before: the full week, the -50 lost).
    assert stmt["amount"] == week_net - 5000, (stmt["amount"], week_net)
    assert stmt["carried_in"] == -5000 and stmt["summary"]["carried_from_last_week"] == "-50.00"
    assert stmt["negative_weeks"] == 0 and stmt["negative_since"] is None

    old = (await client.get(f"/api/v1/finance/statements/{before}", headers=finance)).json()
    assert old["status"] == "carried" and old["carried"] is True and old["transfer_id"] is None

    # The run, Reconciliation (before and after the run) and the statements agree on the carry.
    assert run["totals"]["kitchen_carried_in"] == "-50.00" and run["totals"]["kitchen_carried_forward"] == "0.00"
    rec = (await client.get("/api/v1/finance/reconciliation", headers=finance, params=params)).json()["money"]
    for k in ("kitchen_carried_in", "kitchen_carried_forward", "restaurant_to_pay", "restaurant_payable"):
        assert rec[k] == preview[k], (k, rec[k], preview[k])
    assert rec["kitchen_carried_in"] == -5000 and rec["kitchen_carried_forward"] == 0
    assert rec["restaurant_to_pay"] == rec["restaurant_payable"] + rec["kitchen_carried_in"] - rec["kitchen_carried_forward"]
    assert rec["restaurant_to_pay"] == cents(run["totals"]["restaurants_to_pay"])

    # Idempotent: the week can't be prepared again, and nothing is left to carry a second time.
    r = await client.post("/api/v1/finance/payout-runs", headers=finance,
                          json={"country": "IN", "period_start": last_start.isoformat(), "period_end": last_end.isoformat()})
    assert r.status_code == 409
    from core_api.modules.finance.service.payouts import open_carries
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        assert spice not in await open_carries(db, "IN", last_end + timedelta(days=7))

    # The kitchen sets up payouts and the run is approved: the reduced amount is what is sent.
    partner = await login(client, "partner.hyd@example.com")
    assert (await client.post("/api/v1/finance/payout-accounts", headers=partner,
                              json={"payee_type": "restaurant", "restaurant_id": spice})).status_code == 201
    r = await client.post(f"/api/v1/finance/payout-runs/{run['id']}/approve", headers=admin)
    assert r.status_code == 200, r.text
    paid = next(s for s in r.json()["statements"] if s["payee_id"] == spice)
    assert paid["status"] == "paid" and paid["amount"] == week_net - 5000
    # A retry and a second approval change nothing (the balance stays carried, paid once).
    assert (await client.post(f"/api/v1/finance/payout-runs/{before_run}/retry", headers=admin)).status_code == 409  # nothing to pay
    assert (await client.post(f"/api/v1/finance/payout-runs/{before_run}/approve", headers=admin)).status_code == 409
    old = (await client.get(f"/api/v1/finance/statements/{before}", headers=finance)).json()
    assert old["status"] == "carried" and old["transfer_id"] is None

    # The kitchen sees both weeks: below zero and carried, then the carried line in the paid week.
    mine = {s["id"]: s for s in (await client.get("/api/v1/finance/statements/me", headers=partner)).json()}
    assert mine[before]["status"] == "carried" and mine[before]["amount"] == -5000
    assert mine[stmt["id"]]["carried_in"] == -5000 and mine[stmt["id"]]["status"] == "paid"
    await no_charges()


async def test_still_negative_after_four_weeks_is_flagged_to_collect(client: AsyncClient) -> None:  # noqa: F811
    from sqlalchemy import select

    from core_api.modules.finance.models import PayoutStatement
    from core_api.modules.finance.service import payouts
    from shared.db import AsyncSessionLocal

    cust = await login(client, "customer1.hyd@example.com")
    order = await delivered_order(client, cust)
    await deliver_last_week(order["id"])
    spice = order["restaurant_id"]
    last_start, last_end = ist_last_week()
    first = last_start - timedelta(days=28)
    await week_below_zero(spice, first, -100_000_000)  # far more than any week's sales: still below zero after them
    finance = await login(client, "finance.in@example.com", ADMIN)

    runs = []
    for i in (3, 2, 1):  # the three weeks after it, each a real run (sales or none: a statement with the carry)
        start = last_start - timedelta(days=7 * i)
        async with AsyncSessionLocal() as db:
            runs.append(await payouts.create_run(db, uuid.UUID(int=0), "IN", start, start + timedelta(days=7)))
            await db.commit()
        listed = (await client.get("/api/v1/finance/to-collect", headers=finance, params={"country": "IN"})).json()
        if i > 1:  # 2 and 3 weeks below zero: not yet
            assert all(k["restaurant_id"] != spice for k in listed), listed
    async with AsyncSessionLocal() as db:
        chain = [(await db.execute(select(PayoutStatement).where(
            PayoutStatement.run_id == r.id, PayoutStatement.payee_id == uuid.UUID(spice)))).scalar_one() for r in runs]
    assert [s.negative_weeks for s in chain] == [2, 3, 4]
    assert {s.negative_since for s in chain} == {first}
    for prev, nxt in zip(chain, chain[1:]):
        assert nxt.carried_in == prev.amount and nxt.amount < 0
    assert runs[-1].totals["kitchens_to_collect"] >= 1

    # Four weeks below zero in a row: Finance lists the kitchen to collect from (what it owes, weeks, since).
    listed = (await client.get("/api/v1/finance/to-collect", headers=finance, params={"country": "IN"})).json()
    row = next(k for k in listed if k["restaurant_id"] == spice)
    assert (row["amount"], row["weeks"], row["since"]) == (-chain[-1].amount, 4, first.isoformat())
    assert row["kitchen"] == "Spice Route Kitchen" and row["currency"] == "INR"
    viewer_us = await login(client, "finance.us@example.com", ADMIN)
    assert (await client.get("/api/v1/finance/to-collect", headers=viewer_us, params={"country": "IN"})).status_code == 403

    # Last week's sales cover part of it: still nothing paid, the rest carried again (week 5).
    r = await client.post("/api/v1/finance/payout-runs", headers=finance,
                          json={"country": "IN", "period_start": last_start.isoformat(), "period_end": last_end.isoformat()})
    assert r.status_code == 201, r.text
    stmt = await statement_of(client, finance, r.json()["id"], spice)
    assert cents(stmt["summary"]["net"]) > 0
    assert stmt["amount"] == chain[-1].amount + cents(stmt["summary"]["net"]) < 0
    assert stmt["negative_weeks"] == 5
    admin = await login(client, "admin@example.com", ADMIN)
    partner = await login(client, "partner.hyd@example.com")
    assert (await client.post("/api/v1/finance/payout-accounts", headers=partner,
                              json={"payee_type": "restaurant", "restaurant_id": spice})).status_code == 201
    r = await client.post(f"/api/v1/finance/payout-runs/{r.json()['id']}/approve", headers=admin)
    assert next(s for s in r.json()["statements"] if s["payee_id"] == spice)["status"] == "carried"
    listed = (await client.get("/api/v1/finance/to-collect", headers=finance, params={"country": "IN"})).json()
    assert [k["weeks"] for k in listed if k["restaurant_id"] == spice] == [5]  # the latest week only, never twice
    await no_charges()
