"""R27: when a kitchen can next take an order is inside its own hours AND the city's delivery hours.

R26 saw a kitchen opening at 06:30 in Boise (deliveries 08:00-23:00) report opens_at == now between
06:30 and 08:00, and the app say "Closed · opens 6:30 am" after 6:30. The edges, on the wall clock."""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core_api.modules.catalog.service.hours import Override, Range, next_orderable, orderable, orderable_until

FRI = date(2026, 11, 13)  # a Friday
SAT, SUN = FRI + timedelta(days=1), FRI + timedelta(days=2)
BOISE = {"open": "08:00", "close": "23:00"}
EVERY_DAY = [Range(d, time(6, 30), time(22)) for d in range(7)]  # opens before the city, closes before it
LATE = [Range(d, time(9), time(23, 30)) for d in range(7)]  # opens after the city, closes after it


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm))


def test_kitchen_opens_before_the_city_starts_delivering() -> None:
    # 06:30 kitchen, 08:00 city: orders from 08:00, never "now" in between.
    assert next_orderable(at(FRI, 5), EVERY_DAY, {}, BOISE) == at(FRI, 8)
    assert next_orderable(at(FRI, 6, 30), EVERY_DAY, {}, BOISE) == at(FRI, 8)  # kitchen open, city not yet
    assert next_orderable(at(FRI, 7, 59), EVERY_DAY, {}, BOISE) == at(FRI, 8)
    assert not orderable(at(FRI, 7, 59), EVERY_DAY, {}, BOISE)
    assert next_orderable(at(FRI, 8), EVERY_DAY, {}, BOISE) == at(FRI, 8)  # exactly at the start: now
    assert orderable(at(FRI, 8), EVERY_DAY, {}, BOISE)


def test_kitchen_opens_after_the_city_starts() -> None:
    assert next_orderable(at(FRI, 8), LATE, {}, BOISE) == at(FRI, 9)
    assert not orderable(at(FRI, 8, 59), LATE, {}, BOISE)  # one minute before it opens
    assert orderable(at(FRI, 9), LATE, {}, BOISE)  # exactly at open


def test_at_and_after_closing() -> None:
    assert orderable(at(FRI, 21, 59), EVERY_DAY, {}, BOISE)  # a minute before the kitchen closes
    assert not orderable(at(FRI, 22), EVERY_DAY, {}, BOISE)  # at close
    assert not orderable(at(FRI, 22, 1), EVERY_DAY, {}, BOISE)  # a minute after
    assert next_orderable(at(FRI, 22), EVERY_DAY, {}, BOISE) == at(SAT, 8)  # tomorrow, when the city starts


def test_kitchen_closes_after_the_city_stops() -> None:
    # Kitchen till 23:30, city till 23:00: no orders 23:00-23:30; open till 11 pm, not 11:30.
    assert orderable(at(FRI, 22, 59), LATE, {}, BOISE)
    assert not orderable(at(FRI, 23), LATE, {}, BOISE)
    assert next_orderable(at(FRI, 23, 15), LATE, {}, BOISE) == at(SAT, 9)
    assert orderable_until(at(FRI, 12), LATE, {}, BOISE) == at(FRI, 23)
    assert orderable_until(at(FRI, 12), EVERY_DAY, {}, BOISE) == at(FRI, 22)
    assert orderable_until(at(FRI, 23, 15), LATE, {}, BOISE) is None  # not orderable now


def test_overnight_hours() -> None:
    night = [Range(d, time(18), time(2)) for d in range(7)]  # 6 pm to 2 am
    city = {"open": "07:00", "close": "01:00"}  # Hyderabad-style window past midnight
    assert orderable(at(SAT, 0, 30), night, {}, city)  # Friday's range, the city's window from Friday
    assert not orderable(at(SAT, 1, 30), night, {}, city)  # kitchen open, city stopped at 1 am
    assert next_orderable(at(SAT, 1, 30), night, {}, city) == at(SAT, 18)
    assert orderable_until(at(FRI, 20), night, {}, city) == at(SAT, 1)
    assert next_orderable(at(FRI, 12), night, {}, city) == at(FRI, 18)


def test_a_closed_day_and_a_holiday() -> None:
    weekdays = [Range(d, time(9), time(21)) for d in range(5)]  # closed Saturday and Sunday
    assert next_orderable(at(FRI, 21), weekdays, {}, BOISE) == at(FRI + timedelta(days=3), 9)  # Monday
    holiday = {FRI: Override(FRI, closed=True, note="Staff holiday")}
    assert next_orderable(at(FRI, 10), weekdays, holiday, BOISE) == at(FRI + timedelta(days=3), 9)
    short = {SAT: Override(SAT, closed=False, opens=time(7), closes=time(12))}  # special hours on Saturday
    assert next_orderable(at(FRI, 21), weekdays, short, BOISE) == at(SAT, 8)  # 07:00 kitchen, 08:00 city
    assert orderable_until(at(SAT, 10), weekdays, short, BOISE) == at(SAT, 12)


def test_no_hours_set() -> None:
    assert next_orderable(at(FRI, 5), [], {}, BOISE) == at(FRI, 8)  # the kitchen has no hours: the city's
    assert next_orderable(at(FRI, 5), EVERY_DAY, {}, None) == at(FRI, 6, 30)  # the city has none: the kitchen's
    assert next_orderable(at(FRI, 5), [], {}, None) == at(FRI, 5)  # neither: always
    assert next_orderable(at(FRI, 5), [], {FRI + timedelta(days=d): Override(FRI + timedelta(days=d), True)
                                          for d in range(10)}, BOISE) is None  # closed for longer than we look
    assert orderable_until(at(FRI, 12), [], {}, {"open": "00:00", "close": "00:00"}) is None  # around the clock


def test_across_boises_dst_change() -> None:
    # Clocks go forward at 2 am on Sunday 8 March 2026: 08:00 that morning is MDT (14:00 UTC), not MST.
    boise = ZoneInfo("America/Boise")
    sat, sun = date(2026, 3, 7), date(2026, 3, 8)
    local = datetime(2026, 3, 8, 7, 0, tzinfo=UTC).astimezone(boise)  # Sun 00:00 MST
    assert local.date() == sun and local.hour == 0
    nxt = next_orderable(local, EVERY_DAY, {}, BOISE)
    assert nxt == at(sun, 8)
    assert nxt.replace(tzinfo=boise).astimezone(UTC) == datetime(2026, 3, 8, 14, 0, tzinfo=UTC)
    # The night before (MST): Saturday's 23:00 close is 06:00 UTC on Sunday.
    assert orderable_until(at(sat, 12), LATE, {}, BOISE).replace(tzinfo=boise).astimezone(UTC) == \
        datetime(2026, 3, 8, 6, 0, tzinfo=UTC)
    # Back in November (1 Nov 2026, 2 am -> 1 am): 08:00 that day is MST again.
    nov = next_orderable(at(date(2026, 11, 1), 5), EVERY_DAY, {}, BOISE)
    assert nov.replace(tzinfo=boise).astimezone(UTC) == datetime(2026, 11, 1, 15, 0, tzinfo=UTC)
