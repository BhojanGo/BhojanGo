"""R23: a kitchen's week below zero is carried into its next statement, never written off and
never charged to the kitchen (no database: statements.balance / settle / combine).

The payout run (payouts.create_run, pay_pending) uses exactly these; the integration tests
(core_api/integration/test_negative_statements.py) run them on Postgres."""
from datetime import date, timedelta
from decimal import Decimal

from core_api.modules.finance.service import statements as S
from core_api.modules.finance.tests.test_statements import worked_example

W1 = date(2026, 10, 26)  # a Monday


def week(n: int) -> date:
    return W1 + timedelta(days=7 * n)


def minor(v: Decimal) -> int:
    return int(v * 100)


def refunded_week() -> int:
    """The kitchen's only order of the week, every item refunded as its fault (wrong item):
    560 food + 10 packaging - 84 commission - 15.12 GST on it - 476 refund = -5.12."""
    o = worked_example(refunds=[{"food": "560.00", "name": "Veg Dum Biryani", "quantity": 2, "reason": "wrong_item",
                                 "fault": "restaurant"}])
    total, _, _ = S.restaurant_statement([o], Decimal("18"))
    return minor(total)


def run_weeks(nets: list[int]) -> list[S.Balance]:
    """Weekly runs one after another, as payouts.create_run carries balances (minor units)."""
    out: list[S.Balance] = []
    carry: S.Carry | None = None
    for i, net in enumerate(nets):
        b = S.balance(net, carry, week(i))
        out.append(b)
        carry = S.Carry(b.amount, b.negative_weeks, b.negative_since, (f"s{i}",)) if b.amount < 0 else None  # type: ignore[arg-type]
    return out


def test_a_week_below_zero_is_carried_not_written_off() -> None:
    net = refunded_week()
    assert net == -512
    b = S.balance(net, None, W1)
    assert (b.amount, b.to_pay, b.carried_forward) == (-512, 0, -512)
    assert (b.negative_weeks, b.negative_since) == (1, W1)
    # The payout run sends nothing and keeps the balance (before R23 this was "paid": written off).
    assert S.settle(b.amount) == "carried"


def test_next_weeks_sales_cover_it_fully_and_the_payout_is_reduced() -> None:
    first, second = run_weeks([refunded_week(), 48600])
    assert first.amount == -512
    assert (second.carried_in, second.amount, second.to_pay) == (-512, 48600 - 512, 48088)
    assert S.settle(second.amount) is None  # money to send: 486.00 - 5.12
    assert (second.negative_weeks, second.negative_since) == (0, None)


def test_next_weeks_sales_cover_it_partly_and_nothing_is_paid() -> None:
    first, second, third = run_weeks([-10000, 3000, 9000])
    assert (second.carried_in, second.amount, second.to_pay, S.settle(second.amount)) == (-10000, -7000, 0, "carried")
    assert (second.negative_weeks, second.negative_since) == (2, week(0))
    assert (third.carried_in, third.amount, third.to_pay) == (-7000, 2000, 2000)  # covered in week 3; 20.00 paid


def test_exactly_covered_pays_nothing_and_carries_nothing() -> None:
    _, second = run_weeks([-2500, 2500])
    assert (second.amount, second.to_pay, second.carried_forward, S.settle(second.amount)) == (0, 0, 0, "paid")


def test_still_below_zero_after_four_weeks_is_flagged_to_collect() -> None:
    weeks = run_weeks([-100000, 0, 2000, 3000, 4000])
    assert [b.negative_weeks for b in weeks] == [1, 2, 3, 4, 5]
    assert [S.to_collect(b.negative_weeks) for b in weeks] == [False, False, False, True, True]
    assert {b.negative_since for b in weeks} == {week(0)}
    assert weeks[-1].amount == -100000 + 9000


def test_runs_prepared_out_of_order_carry_every_open_balance_once() -> None:
    a = S.Carry(-300, 1, week(1), ("s1",))
    b = S.Carry(-200, 3, week(0), ("s0",))
    c = S.combine([a, b])
    assert c == S.Carry(-500, 3, week(0), ("s1", "s0"))
    assert S.combine([]) is None
    assert S.balance(400, c, week(4)) == S.Balance(400, -500, -100, 4, week(0))


def test_nothing_is_ever_charged_to_the_kitchen() -> None:
    """Whatever the weeks, a statement never asks for money from the kitchen: below zero it
    sends nothing, and every amount ends up paid or carried, never lost."""
    nets = [-5000, -100, 0, 7000, -9000, 1, 50000, -3, -3, -3, -3, 2]
    weeks = run_weeks(nets)
    assert all(b.to_pay >= 0 for b in weeks)
    assert all(S.settle(b.amount) in ("carried", "paid") for b in weeks if b.to_pay == 0)
    # Money is kept: everything paid plus the balance still open equals all the weeks' nets.
    assert sum(b.to_pay for b in weeks) + weeks[-1].carried_forward == sum(nets)
    for b in weeks:  # each statement: paid = earned + carried in - carried on
        assert b.to_pay == b.net + b.carried_in - b.carried_forward


def test_major_units_for_summaries() -> None:
    assert (S.major(-512), S.major(0), S.major(48088)) == ("-5.12", "0.00", "480.88")
