"""R41: payout weeks are Monday 00:00 to the next Monday 00:00 in the country's payout zone; every instant is in
exactly one week; no overlap, no gap; across the US clock change too. And no delivery in the future."""
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from core_api.modules.finance.service.payouts import FinanceError, check_week, ended_weeks, week_of, week_window

BOISE, INDIA = ZoneInfo("America/Boise"), ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize("tz", [BOISE, INDIA])
def test_sunday_2359_and_monday_0000_local(tz: ZoneInfo) -> None:
    sunday = datetime(2026, 11, 22, 23, 59, 59, tzinfo=tz)
    monday = datetime(2026, 11, 23, 0, 0, 0, tzinfo=tz)
    assert week_of(sunday, tz) == (date(2026, 11, 16), date(2026, 11, 23))
    assert week_of(monday, tz) == (date(2026, 11, 23), date(2026, 11, 30))
    # the same instants seen from UTC belong to the same weeks (the zone decides, not UTC's date)
    assert week_of(sunday.astimezone(UTC), tz) == week_of(sunday, tz)
    assert week_of(monday.astimezone(UTC), tz) == week_of(monday, tz)
    # and the week's window holds the Sunday instant, not the Monday one
    a, b = week_window(date(2026, 11, 16), date(2026, 11, 23), tz)
    assert a <= sunday < b and not (a <= monday < b)


@pytest.mark.parametrize("tz", [BOISE, INDIA])
def test_weeks_never_overlap_or_leave_a_gap(tz: ZoneInfo) -> None:
    start = date(2026, 9, 28)
    for i in range(12):
        a, b = week_window(start + timedelta(weeks=i), start + timedelta(weeks=i + 1), tz)
        a2, _ = week_window(start + timedelta(weeks=i + 1), start + timedelta(weeks=i + 2), tz)
        assert b == a2  # this week ends exactly when the next starts
        assert a.astimezone(tz).weekday() == 0 and a.astimezone(tz).hour == 0


def test_the_us_clock_change_week() -> None:
    """1 Nov 2026, 02:00 MDT -> 01:00 MST: the week of 26 Oct is 169 hours, still Monday to Monday."""
    a, b = week_window(date(2026, 10, 26), date(2026, 11, 2), BOISE)
    assert b - a == timedelta(hours=169)
    before = datetime(2026, 11, 1, 1, 30, tzinfo=BOISE, fold=0)  # the first 01:30 (MDT)
    after = datetime(2026, 11, 1, 1, 30, tzinfo=BOISE, fold=1)  # the second 01:30 (MST)
    assert week_of(before, BOISE) == week_of(after, BOISE) == (date(2026, 10, 26), date(2026, 11, 2))
    assert week_of(datetime(2026, 11, 1, 23, 59, 59, tzinfo=BOISE), BOISE)[0] == date(2026, 10, 26)
    assert week_of(datetime(2026, 11, 2, 0, 0, tzinfo=BOISE), BOISE)[0] == date(2026, 11, 2)


def test_only_ended_monday_weeks_can_be_prepared() -> None:
    today = date(2026, 11, 24)  # a Tuesday
    check_week(date(2026, 11, 16), date(2026, 11, 23), today)  # ended: fine
    with pytest.raises(FinanceError, match="hasn't ended"):
        check_week(date(2026, 11, 23), date(2026, 11, 30), today)  # this week
    with pytest.raises(FinanceError, match="hasn't ended"):
        check_week(date(2026, 12, 14), date(2026, 12, 21), today)  # a future week
    for bad in (date(2026, 12, 15), date(2026, 10, 25)):  # a Tuesday, a Sunday
        with pytest.raises(FinanceError, match="Monday to Sunday"):
            check_week(bad, bad + timedelta(days=7), today)
    weeks = ended_weeks(today)
    assert weeks[0] == (date(2026, 11, 16), date(2026, 11, 23)) and all(s.weekday() == 0 for s, _ in weeks)
    assert all(weeks[i][0] == weeks[i + 1][1] for i in range(len(weeks) - 1))  # back to back


def test_a_delivery_in_the_future_is_refused() -> None:
    from core_api.modules.orders.models.order import Order

    o = Order()
    o.actual_delivery_time = datetime.now(UTC)  # now is fine
    o.actual_delivery_time = datetime(2008, 12, 18, 2, 0, tzinfo=UTC)  # the past is fine
    with pytest.raises(ValueError, match="future"):
        o.actual_delivery_time = datetime.now(UTC) + timedelta(days=24)
