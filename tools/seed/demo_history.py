"""The demo kitchens' order history and ratings (tools/seed/demo.py), planned here.

Standard library only (tested by tools/seed/demo_test.py in make ci-guard) and
deterministic: each kitchen's plan comes from a random generator seeded with its
slug, so the demo seed writes the same orders (same ids) every time it runs.

For each demo kitchen: a believable number of past orders (8-60 over the last six
months; 2-6 this week for a kitchen that just joined), from the demo customers who
live within reach of it, at times the kitchen and the city were open, with a
basket that clears the minimum order. A share of them is rated, with a star
spread that suits the kitchen (most kitchens get mostly fours and fives, a few
are more mixed). Ratings exist only on delivered orders: the kitchen's rating and
review_count are then recomputed from them, as the ratings service does.
"""
import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from data import COUNTRIES
from demo_data import BASKET_FLOOR, DEMO, ORDERS, RATING_COMMENTS, REGULARS, STREETS

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
HISTORY_DAYS = 180         # established kitchens: orders over the last six months
NEW_DAYS = 6               # a kitchen new on BhojanGo joined 6 days ago (demo.py's created_at)
MIN_RATINGS_FOR_STARS = 5  # core_api/modules/catalog/service/ratings.py: "New" below this
REACH_KM = 5.0             # straight line; the quote engine's road distance is about 1.3x
DONE_BEFORE = timedelta(hours=3)  # a past order is finished well before now
# Star spreads (weights for 5, 4, 3, 2, 1 stars) and how many kitchens get each.
PROFILES = {
    "loved": (62, 26, 7, 3, 2),
    "good": (48, 32, 12, 5, 3),
    "steady": (38, 38, 15, 6, 3),
    "mixed": (40, 26, 14, 9, 11),
}
PROFILE_WEIGHTS = {"loved": 3, "good": 4, "steady": 2, "mixed": 1}
PEAKS = (time(13, 0), time(20, 0), time(9, 0))


@dataclass
class Planned:
    """One past order: who, where from, when (city local time), what, and its rating."""

    kitchen: str
    n: int                       # the order's number at this kitchen (its id: demo.py history_id)
    customer: str                # demo customer key
    local: datetime              # placed at, city local time (naive)
    lines: list  # [(dish, quantity, {group: option})], as demo_data.ORDERS
    review: tuple[int, str | None] | None = None  # (stars, comment)
    review_after: timedelta = timedelta(hours=2)  # after delivery


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (lat1, lng1), (lat2, lng2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def live_zones(key: str) -> list[tuple[str, tuple[float, float, float, float]]]:
    """(name, (south, west, north, east)) of the city's live zones: the base seed's and the demo's."""
    code = DEMO[key]["city_code"]
    out = [(z[0], z[1]) for c in COUNTRIES for r in c["regions"] for city in r["cities"] if city["code"] == code
           for z in city["zones"] if z[3] == "live"]
    return out + [(z[0], z[1]) for z in DEMO[key]["zones"] if z[3] == "live"]


def zone_of(p: tuple[float, float], zones: list) -> str | None:
    for name, (s, w, n, e) in zones:
        if s + 0.001 <= p[0] <= n - 0.001 and w + 0.001 <= p[1] <= e - 0.001:
            return name
    return None


def _offset(p: tuple[float, float], km: float, bearing: float) -> tuple[float, float]:
    dlat = km * math.cos(bearing) / 111.32
    dlng = km * math.sin(bearing) / (111.32 * math.cos(math.radians(p[0])))
    return p[0] + dlat, p[1] + dlng


def regulars(key: str) -> list[tuple]:
    """The city's regulars as demo customers: (key, name, street, area, postal, lat, lng, notes, phone).
    Regular i lives 0.8-3 km from demo kitchen i (mod the kitchens), inside a live zone."""
    city = DEMO[key]
    zones = live_zones(key)
    fmt, streets = STREETS[key]
    out = []
    for i, name in enumerate(REGULARS[key]):
        rng = random.Random(f"regular/{key}/{i}")
        k = city["kitchens"][i % len(city["kitchens"])]
        home, area = (k["lat"], k["lng"]), None
        for _ in range(400):
            p = _offset((k["lat"], k["lng"]), rng.uniform(0.8, 3.0), rng.uniform(0, 2 * math.pi))
            area = zone_of(p, zones)
            if area:
                home = p
                break
        if area is None:  # the kitchen's own block (always in a zone: it was quoted from there)
            area = zone_of(home, zones) or k["area"]
        street = fmt.format(n=rng.randint(101, 804) if key == "hyd" else rng.randint(100, 3999), street=rng.choice(streets))
        out.append((f"regular{i + 1:02d}.{key}", name, street, area, k["zip"], round(home[0], 5), round(home[1], 5),
                    None, f"4{i + 1:02d}"))
    return out


def customers(key: str) -> list[tuple]:
    """Everyone who orders in the history: the demo customers (as demo_data) and the regulars."""
    return [tuple(c) for c in DEMO[key]["customers"]] + [c[:8] for c in regulars(key)]


def _minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def open_windows(k: dict, weekday: int, service: dict | None) -> list[tuple[int, int]]:
    """Minutes of the day an order can be placed and delivered that day: the kitchen's
    hours that day, inside the city's service hours, 15 minutes after opening to
    45 minutes before closing, never past 23:00 (no overnight edge cases)."""
    lo, hi = (_minutes(service["open"]), _minutes(service["close"])) if service else (0, 24 * 60)
    if hi <= lo:
        hi = 24 * 60
    out = []
    for days, opens, closes in k["hours"]:
        if DAYS[weekday] not in days:
            continue
        a, b = _minutes(opens), _minutes(closes)
        if b <= a:
            b = 24 * 60
        a, b = max(a, lo) + 15, min(b, hi, 23 * 60) - 45
        if b > a:
            out.append((a, b))
    return out


def service_hours(key: str) -> dict | None:
    code = DEMO[key]["city_code"]
    return next(city["service_hours"] for c in COUNTRIES for r in c["regions"] for city in r["cities"] if city["code"] == code)


def _dishes(k: dict) -> list[tuple[str, float]]:
    """(name, price with the required options' first choice)."""
    out = []
    for items in k["menu"].values():
        for name, price, _veg, _desc, groups in items:
            extra = sum(g["options"][0]["price"] for g in groups if g.get("required"))
            out.append((name, float(price) + extra))
    return out


def basket(rng: random.Random, key: str, k: dict) -> list:
    dishes = _dishes(k)
    floor = max(float(k["min_order"]), BASKET_FLOOR[key]) * rng.uniform(1.05, 1.7)
    lines, total = [], 0.0
    for name, price in rng.sample(dishes, len(dishes)):
        qty = rng.choice((1, 1, 1, 2, 2, 3)) if price * 2 < floor else 1
        lines.append((name, qty, {}))
        total += price * qty
        if total >= floor or len(lines) == 4:
            break
    while total < floor:  # a fourth line still short: more of the first dish
        name, qty, picks = lines[0]
        lines[0] = (name, qty + 1, picks)
        total += next(p for d, p in dishes if d == name)
    return lines


def _when(rng: random.Random, key: str, k: dict, days_ago: int, today: date, now_local: datetime) -> datetime | None:
    service = service_hours(key)
    for back in range(14):
        day = today - timedelta(days=days_ago + back)
        windows = open_windows(k, day.weekday(), service)
        if not windows:
            continue
        a, b = rng.choice(windows)
        peak = next((p.hour * 60 + p.minute for p in PEAKS if a <= p.hour * 60 + p.minute <= b), (a + b) / 2)
        m = int(rng.triangular(a, b, peak))
        at = datetime.combine(day, time(m // 60, m % 60))
        if at <= now_local - DONE_BEFORE:
            return at
    return None


def _rated_count(rng: random.Random, k: dict, orders: int, typed: int) -> int:
    """How many of the kitchen's history orders get a rating (``typed``: the curated
    demo orders' ratings, already counted). New kitchens stay below five in all."""
    if k["new"]:
        return max(0, min(orders, MIN_RATINGS_FOR_STARS - 1 - typed, rng.randint(1, 4)))
    want = round(orders * rng.uniform(0.35, 0.6))
    return min(orders, max(want, MIN_RATINGS_FOR_STARS - typed))


def plan_kitchen(key: str, k: dict, people: list[tuple], today: date, now_local: datetime) -> list[Planned]:
    rng = random.Random(f"history/{key}/{k['slug']}")
    here = (k["lat"], k["lng"])
    demo_keys = {c[0] for c in DEMO[key]["customers"]}
    near = [(c, haversine_km(here, (c[5], c[6]))) for c in people]
    reach = [(c, d) for c, d in near if d <= REACH_KM] or sorted(near, key=lambda x: x[1])[:3]
    weights = [(0.25 if c[0] in demo_keys else 1.0) / (0.4 + d) for c, d in reach]
    if k["new"]:
        count, spread = rng.randint(2, 6), NEW_DAYS - 1
    else:
        count, spread = round(rng.triangular(8, 60, 14)), HISTORY_DAYS
    stars_w = PROFILES[rng.choices(list(PROFILE_WEIGHTS), weights=list(PROFILE_WEIGHTS.values()))[0]]
    typed = sum(1 for o in ORDERS[key] if o[1] == k["slug"] and o[5])
    placed = []
    for n in range(count):
        at = _when(rng, key, k, int(rng.triangular(0, spread, min(10, spread))), today, now_local)
        if at is not None and not (k["new"] and at.date() < today - timedelta(days=NEW_DAYS - 1)):
            placed.append((n, at))
    rated = {placed[i][0] for i in rng.sample(range(len(placed)), _rated_count(rng, k, len(placed), typed))}
    out = []
    for n, at in placed:
        who = rng.choices([c for c, _ in reach], weights=weights)[0][0]
        lines = basket(rng, key, k)
        review = None
        if n in rated:
            stars = rng.choices((5, 4, 3, 2, 1), weights=stars_w)[0]
            comment = rng.choice(RATING_COMMENTS[stars]).format(dish=lines[0][0]) if rng.random() < 0.5 else None
            review = (stars, comment)
        out.append(Planned(k["slug"], n, who, at, lines, review, timedelta(minutes=rng.randint(20, 20 * 60))))
    return out


def plan_city(key: str, today: date, now_local: datetime) -> list[Planned]:
    """The city's whole history, oldest first (so each customer's first order is priced as one)."""
    people = customers(key)
    plans = [p for k in DEMO[key]["kitchens"] for p in plan_kitchen(key, k, people, today, now_local)]
    return sorted(plans, key=lambda p: (p.local, p.kitchen, p.n))
