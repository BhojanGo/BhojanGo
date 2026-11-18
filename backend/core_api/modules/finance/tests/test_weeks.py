"""A payout run covers one week that has ended (R12), and the payout day unpaid statements are paid again."""
from datetime import date

import pytest

from core_api.modules.finance.service.payouts import FinanceError, check_week, ended_weeks

MON = date(2026, 11, 9)  # a Monday
NEXT = date(2026, 11, 16)


def test_an_ended_week_is_allowed() -> None:
    check_week(MON, NEXT, today=NEXT)  # Monday after the week: Sunday has ended
    check_week(MON, NEXT, today=date(2026, 11, 30))


def test_an_unfinished_week_is_refused() -> None:
    with pytest.raises(FinanceError, match="hasn't ended yet"):
        check_week(MON, NEXT, today=date(2026, 11, 15))  # Sunday: still running
    with pytest.raises(FinanceError, match="hasn't ended yet"):
        check_week(NEXT, date(2026, 11, 23), today=date(2026, 11, 17))  # this week


def test_only_monday_to_sunday() -> None:
    for start, end in ((date(2026, 11, 10), date(2026, 11, 17)), (MON, date(2026, 11, 15)), (MON, date(2026, 11, 23))):
        with pytest.raises(FinanceError, match="Monday to Sunday"):
            check_week(start, end, today=date(2026, 12, 31))


def test_ended_weeks_newest_first() -> None:
    weeks = ended_weeks(date(2026, 11, 17), n=3)  # a Tuesday
    assert weeks == [(MON, NEXT), (date(2026, 11, 2), MON), (date(2026, 10, 26), date(2026, 11, 2))]
    assert ended_weeks(NEXT, n=1) == [(MON, NEXT)]  # on Monday last week is ready
    for a, b in weeks:
        check_week(a, b, today=date(2026, 11, 17))
