"""R27: payout weeks are counted in the country's payout time zone (Markets payout_timezone),
and every city keeps its own zone for hours, receipts and admin times (no database)."""
from datetime import UTC, date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from core_api.modules.finance.service.payouts import local_today, payout_tz, week_window
from core_api.modules.markets.models import payout_zone

US = SimpleNamespace(code="US", timezone="America/New_York", payout_timezone="America/Boise")
IN = SimpleNamespace(code="IN", timezone="Asia/Kolkata", payout_timezone="Asia/Kolkata")
NEW = SimpleNamespace(code="AE", timezone="Asia/Dubai", payout_timezone=None)


def test_the_payout_zone_is_the_countrys_payout_timezone_else_its_timezone() -> None:
    assert payout_zone(US) == "America/Boise"  # not New York: the US's cities are in Idaho
    assert payout_zone(IN) == "Asia/Kolkata"
    assert payout_zone(NEW) == "Asia/Dubai"
    assert payout_tz(US) == ZoneInfo("America/Boise")


def test_a_us_week_starts_at_midnight_in_boise() -> None:
    a, b = week_window(date(2026, 11, 9), date(2026, 11, 16), payout_tz(US))
    assert a == datetime(2026, 11, 9, 7, 0, tzinfo=UTC)  # 00:00 MST
    assert b == datetime(2026, 11, 16, 7, 0, tzinfo=UTC)
    # A delivery at 11:30 pm Sunday in Boise is in that week; New York's clock would have put it in the next.
    late_sunday = datetime(2026, 11, 16, 6, 30, tzinfo=UTC)
    assert a <= late_sunday < b
    assert late_sunday.astimezone(ZoneInfo("America/New_York")).date() == date(2026, 11, 16)


def test_an_india_week_starts_at_midnight_ist() -> None:
    a, b = week_window(date(2026, 11, 9), date(2026, 11, 16), payout_tz(IN))
    assert a == datetime(2026, 11, 8, 18, 30, tzinfo=UTC)
    assert b - a == (b - a).__class__(days=7)


def test_weeks_across_boises_dst_changes() -> None:
    # Clocks go back on Sun 1 Nov 2026: that week is 169 hours; forward on Sun 8 Mar 2026: 167 hours.
    a, b = week_window(date(2026, 10, 26), date(2026, 11, 2), payout_tz(US))
    assert a == datetime(2026, 10, 26, 6, 0, tzinfo=UTC) and b == datetime(2026, 11, 2, 7, 0, tzinfo=UTC)
    assert (b - a).total_seconds() == 169 * 3600
    a, b = week_window(date(2026, 3, 2), date(2026, 3, 9), payout_tz(US))
    assert (b - a).total_seconds() == 167 * 3600
    # The next week starts exactly where this one ended: nothing falls between two weeks.
    assert week_window(date(2026, 3, 9), date(2026, 3, 16), payout_tz(US))[0] == b


def test_today_is_the_payout_zones_day() -> None:
    # Monday 05:00 UTC is still Sunday in Boise: last week hasn't ended there yet.
    now = datetime(2026, 11, 16, 5, 0, tzinfo=UTC)
    assert local_today(payout_tz(US), now) == date(2026, 11, 15)
    assert local_today(ZoneInfo(US.timezone), now) == date(2026, 11, 16)  # New York's would have said Monday
    assert local_today(payout_tz(IN), now) == date(2026, 11, 16)
