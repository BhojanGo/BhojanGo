"""Is a restaurant open? Pure functions over local times (no database, no clock).

Weekly ranges belong to the day they start on; one that ends at or before its
start runs past midnight (Fri 22:00-02:00 covers Saturday 00:00-02:00). An
override for a date replaces the ranges *starting* that day: closed all day,
or different hours. A range that started the day before still finishes.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class Range:
    weekday: int  # 0 = Monday
    opens: time
    closes: time


@dataclass(frozen=True)
class Override:
    day: date
    closed: bool
    opens: time | None = None
    closes: time | None = None
    note: str | None = None


def _ranges_starting(day: date, weekly: list[Range], overrides: dict[date, Override]) -> list[tuple[datetime, datetime]]:
    o = overrides.get(day)
    if o is not None:
        if o.closed or o.opens is None or o.closes is None:
            return []
        pairs = [(o.opens, o.closes)]
    else:
        pairs = [(r.opens, r.closes) for r in weekly if r.weekday == day.weekday()]
    out = []
    for opens, closes in pairs:
        start = datetime.combine(day, opens)
        end = datetime.combine(day if closes > opens else day + timedelta(days=1), closes)
        out.append((start, end))
    return out


def is_open(local: datetime, weekly: list[Range], overrides: dict[date, Override]) -> bool:
    """``local`` is a naive or aware local time; only its wall clock is used."""
    t = local.replace(tzinfo=None)
    for day in (t.date() - timedelta(days=1), t.date()):
        if any(start <= t < end for start, end in _ranges_starting(day, weekly, overrides)):
            return True
    return False


def closes_at(local: datetime, weekly: list[Range], overrides: dict[date, Override]) -> datetime | None:
    """When the range we're in now ends ("Open till 11:30 pm"); None if closed."""
    t = local.replace(tzinfo=None)
    for day in (t.date() - timedelta(days=1), t.date()):
        for start, end in _ranges_starting(day, weekly, overrides):
            if start <= t < end:
                return end
    return None


def next_open(local: datetime, weekly: list[Range], overrides: dict[date, Override], days: int = 8) -> datetime | None:
    """When it next opens (now if open), within ``days``; None if not in that time."""
    t = local.replace(tzinfo=None)
    if is_open(t, weekly, overrides):
        return t
    starts = [
        start
        for d in range(days)
        for start, _ in _ranges_starting(t.date() + timedelta(days=d), weekly, overrides)
        if start > t
    ]
    return min(starts) if starts else None


def _service_windows(day: date, hours: dict | None) -> list[tuple[datetime, datetime]]:
    """The city's delivery window starting on ``day`` (open == close: all day; close before open: past midnight)."""
    if not hours:
        return []
    opens, closes = time.fromisoformat(hours["open"]), time.fromisoformat(hours["close"])
    start = datetime.combine(day, opens)
    end = datetime.combine(day if closes > opens else day + timedelta(days=1), closes)
    return [(start, end)]


def orderable(local: datetime, weekly: list[Range], overrides: dict[date, Override], service_hours: dict | None) -> bool:
    """The kitchen is open by its own hours (none set: always) and the city delivers (none set: always)."""
    t = local.replace(tzinfo=None)
    return (not (weekly or overrides) or is_open(t, weekly, overrides)) and within_service_hours(t, service_hours)


def next_orderable(local: datetime, weekly: list[Range], overrides: dict[date, Override], service_hours: dict | None,
                   days: int = 8) -> datetime | None:
    """R27: the first moment at or after ``local`` when an order can be placed: inside the kitchen's
    own hours AND the city's delivery window (wall clock, naive). Now if both hold now.

    A kitchen opening at 06:30 in a city delivering 08:00-23:00 is orderable from 08:00; one
    opening at 09:00 from 09:00. Both are unions of intervals, so the first moment in both is
    ``local`` itself or the start of one of them: those are the only candidates checked.
    None if not within ``days`` (closed all week, a long holiday)."""
    t = local.replace(tzinfo=None)
    has_hours = bool(weekly or overrides)
    if not has_hours and not service_hours:
        return t
    candidates = {t}
    for d in range(-1, days):
        day = t.date() + timedelta(days=d)
        candidates |= {start for start, _ in _ranges_starting(day, weekly, overrides) if start > t}
        candidates |= {start for start, _ in _service_windows(day, service_hours) if start > t}
    horizon = t + timedelta(days=days)
    for c in sorted(candidates):
        if c > horizon:
            break
        if orderable(c, weekly, overrides, service_hours):
            return c
    return None


def orderable_until(local: datetime, weekly: list[Range], overrides: dict[date, Override],
                    service_hours: dict | None) -> datetime | None:
    """When ordering stops ("Open till 11 pm"): the earlier of the kitchen's closing and the end of the
    city's delivery window, following ranges that run on into each other. None if not orderable now,
    or open around the clock."""
    t = local.replace(tzinfo=None)
    if not orderable(t, weekly, overrides, service_hours):
        return None
    ends: list[datetime] = []
    for d in range(-1, 2):
        day = t.date() + timedelta(days=d)
        ends += [end for start, end in _ranges_starting(day, weekly, overrides) if start <= t < end]
        ends += [end for start, end in _service_windows(day, service_hours) if start <= t < end and end != start]
    for _ in range(8):  # a stretch can run into the next range (Fri 11:00-23:00, then 23:00-01:00)
        later = [e for e in ends if e > t]
        if not later:
            return None
        stop = min(later)
        if not orderable(stop, weekly, overrides, service_hours):
            return stop
        t = stop
        ends = [end for day in (stop.date() - timedelta(days=1), stop.date())
                for start, end in [*_ranges_starting(day, weekly, overrides), *_service_windows(day, service_hours)]
                if start <= stop < end]
    return None  # open for days on end


def within_service_hours(local: datetime, hours: dict | None) -> bool:
    """City service hours from markets ({"open": "07:00", "close": "23:30"}); None = always."""
    if not hours:
        return True
    opens, closes = time.fromisoformat(hours["open"]), time.fromisoformat(hours["close"])
    now = local.replace(tzinfo=None).time()
    if closes > opens:
        return opens <= now < closes
    return now >= opens or now < closes


def end_of_local_day(local: datetime) -> datetime:
    """Midnight after ``local``, in the same timezone (for "sold out today")."""
    return datetime.combine(local.date() + timedelta(days=1), time(0), tzinfo=local.tzinfo)
