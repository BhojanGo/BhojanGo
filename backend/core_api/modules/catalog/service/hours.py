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
