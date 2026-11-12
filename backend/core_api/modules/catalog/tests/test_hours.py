"""Store hours: weekly ranges, past midnight, holidays and special hours (P10)."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from core_api.modules.catalog.service.hours import (
    Override,
    Range,
    end_of_local_day,
    is_open,
    next_open,
    within_service_hours,
)

# 2026-11-13 is a Friday.
FRI = date(2026, 11, 13)
SAT = date(2026, 11, 14)
WEEK = [Range(d, time(11), time(23)) for d in range(5)] + [Range(d, time(11), time(1)) for d in (4, 5)]  # Fri/Sat to 1 am
LUNCH_DINNER = [Range(4, time(11), time(15, 30)), Range(4, time(18, 30), time(23))]


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm))


def test_open_inside_and_closed_outside() -> None:
    assert is_open(at(FRI, 12), WEEK, {})
    assert not is_open(at(FRI, 10, 59), WEEK, {})
    assert is_open(at(FRI, 11), WEEK, {})  # opening minute counts
    assert is_open(at(FRI, 23, 30), WEEK, {})  # the Friday late range


def test_runs_past_midnight_into_the_next_day() -> None:
    assert is_open(at(SAT, 0, 30), WEEK, {})  # Friday's 11:00-01:00
    assert not is_open(at(SAT, 1), WEEK, {})  # closing minute doesn't
    assert not is_open(at(date(2026, 11, 10), 0, 30), WEEK, {})  # Tuesday 00:30: Monday closed at 23:00


def test_split_lunch_and_dinner() -> None:
    assert is_open(at(FRI, 13), LUNCH_DINNER, {})
    assert not is_open(at(FRI, 16), LUNCH_DINNER, {})
    assert is_open(at(FRI, 20), LUNCH_DINNER, {})
    assert next_open(at(FRI, 16), LUNCH_DINNER, {}) == at(FRI, 18, 30)


def test_holiday_closes_the_day_but_last_nights_range_finishes() -> None:
    holiday = {SAT: Override(SAT, closed=True, note="Diwali")}
    assert is_open(at(SAT, 0, 30), WEEK, holiday)  # Friday's range still runs past midnight
    assert not is_open(at(SAT, 12), WEEK, holiday)
    assert not is_open(at(SAT, 23, 30), WEEK, holiday)


def test_special_hours_replace_the_day() -> None:
    event = {FRI: Override(FRI, closed=False, opens=time(16), closes=time(2))}
    assert not is_open(at(FRI, 12), WEEK, event)
    assert is_open(at(FRI, 17), WEEK, event)
    assert is_open(at(SAT, 1, 30), WEEK, event)  # the event runs to 2 am


def test_next_open() -> None:
    assert next_open(at(FRI, 9), WEEK, {}) == at(FRI, 11)
    assert next_open(at(FRI, 12), WEEK, {}) == at(FRI, 12)  # open now
    sunday = date(2026, 11, 15)  # no Sunday hours in WEEK
    assert next_open(at(sunday, 12), WEEK, {}) == at(date(2026, 11, 16), 11)
    assert next_open(at(FRI, 9), [], {}) is None


def test_city_service_hours() -> None:
    assert within_service_hours(at(FRI, 12), {"open": "07:00", "close": "23:30"})
    assert not within_service_hours(at(FRI, 23, 45), {"open": "07:00", "close": "23:30"})
    assert within_service_hours(at(FRI, 1), {"open": "18:00", "close": "02:00"})
    assert within_service_hours(at(FRI, 4), {"open": "00:00", "close": "00:00"})  # all day
    assert within_service_hours(at(FRI, 4), None)


def test_end_of_local_day_keeps_the_timezone() -> None:
    ist = ZoneInfo("Asia/Kolkata")
    eod = end_of_local_day(datetime(2026, 11, 13, 21, 15, tzinfo=ist))
    assert eod == datetime(2026, 11, 14, 0, 0, tzinfo=ist)
