"""Batch engine (tracker task 43): which orders one rider should carry together.

A Python port of the TypeScript engine in ``backend/worker/batch-engine/src/engine``
(batch-builder.ts, batch-scorer.ts, route-optimizer.ts, utils/geo.ts, config). The
TypeScript is kept only as the reference: ``tests/test_batching.py`` ports its tests
one for one, and ``tests/fixtures/batch_parity.json`` holds numbers the TypeScript
produced for the same inputs, which this module must reproduce.

Pure functions, no I/O. ``run_batch_cycle`` takes the orders waiting for a rider
and returns the batches to make (multi-order where it pays off, solo for priority
and long-waiting orders). The worker runs it every few seconds per city
(``app/services/batching.py``): in shadow mode it only logs what it would do; where
a city has turned live batching on, realtime offers the pairs to riders.
"""
from __future__ import annotations

import itertools
import math
import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

# ── config (same names and defaults as batch-engine/src/config/index.ts) ───────


def _f(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v else default


@dataclass(frozen=True)
class EngineConfig:
    max_orders_per_batch: int = int(_f("MAX_ORDERS_PER_BATCH", 3))
    max_pickup_radius_km: float = _f("MAX_PICKUP_RADIUS_KM", 1.5)
    max_delivery_radius_km: float = _f("MAX_DELIVERY_RADIUS_KM", 3.0)
    max_detour_minutes: float = _f("MAX_DETOUR_MINUTES", 8)
    max_wait_in_pool_minutes: float = _f("MAX_WAIT_IN_POOL_MINUTES", 5)
    min_savings_percent: float = _f("MIN_SAVINGS_PERCENT", 15)
    priority_order_batchable: bool = os.environ.get("PRIORITY_ORDER_BATCHABLE", "false") == "true"
    driver_pickup_dwell_min: float = _f("DRIVER_PICKUP_DWELL_MIN", 2)
    driver_delivery_dwell_min: float = _f("DRIVER_DELIVERY_DWELL_MIN", 3)
    average_speed_kmh: float = _f("AVERAGE_SPEED_KMH", 25)


@dataclass(frozen=True)
class Weights:
    distance_saving: float = _f("SCORE_WEIGHT_DISTANCE", 0.30)
    time_saving: float = _f("SCORE_WEIGHT_TIME", 0.25)
    detour_penalty: float = _f("SCORE_WEIGHT_DETOUR", 0.20)
    priority_penalty: float = _f("SCORE_WEIGHT_PRIORITY", 0.15)
    capacity_fit: float = _f("SCORE_WEIGHT_CAPACITY", 0.10)


CONFIG = EngineConfig()
WEIGHTS = Weights()

# ── types ────────────────────────────────────────────────────────────────────

Point = tuple[float, float]  # (lat, lng)


@dataclass
class PoolOrder:
    order_id: str
    restaurant_id: str
    pickup: Point
    delivery: Point
    prep_ready_at: datetime
    created_at: datetime
    priority: str = "standard"  # standard | priority | scheduled
    restaurant_name: str = ""
    item_count: int = 1


@dataclass
class RouteStop:
    sequence: int
    type: str  # pickup | delivery
    order_id: str
    point: Point
    estimated_arrival_at: datetime
    estimated_dwell_min: float


@dataclass
class Route:
    stops: list[RouteStop]
    total_distance_km: float
    total_time_min: float
    max_detour_min: float
    per_order_detour: dict[str, float] = field(default_factory=dict)


@dataclass
class BatchCandidate:
    orders: list[PoolOrder]
    route: list[RouteStop]
    total_distance_km: float
    total_time_min: float
    max_detour_min: float
    savings_percent: float
    score: int

    @property
    def order_ids(self) -> list[str]:
        return [o.order_id for o in self.orders]


@dataclass
class CycleResult:
    batches: list[BatchCandidate]
    expired_order_ids: list[str]


# ── geo (utils/geo.ts) ───────────────────────────────────────────────────────

EARTH_RADIUS_KM = 6371
CITY_DRIVING_FACTOR = 1.4


def haversine_km(a: Point, b: Point) -> float:
    d_lat, d_lng = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(d_lng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def road_distance_km(a: Point, b: Point) -> float:
    return haversine_km(a, b) * CITY_DRIVING_FACTOR


def drive_time_min(a: Point, b: Point, cfg: EngineConfig = CONFIG) -> float:
    return road_distance_km(a, b) / cfg.average_speed_kmh * 60


def within(a: Point, b: Point, radius_km: float) -> bool:
    return haversine_km(a, b) <= radius_km


def _r2(x: float) -> float:
    """Math.round(x * 100) / 100 (JavaScript rounds .5 up, Python's round() to even)."""
    return math.floor(x * 100 + 0.5) / 100


# ── route (engine/route-optimizer.ts) ────────────────────────────────────────

@dataclass
class _Stop:
    order_id: str
    type: str
    point: Point
    ready_at: datetime | None
    dwell_min: float


def optimize_route(orders: list[PoolOrder], start: Point, now: datetime | None = None, cfg: EngineConfig = CONFIG) -> Route:
    now = now or datetime.now(UTC)
    if not orders:
        return Route([], 0, 0, 0)
    if len(orders) == 1:
        return _single_route(orders[0], start, now, cfg)
    pickups = [_Stop(o.order_id, "pickup", o.pickup, o.prep_ready_at, cfg.driver_pickup_dwell_min) for o in orders]
    deliveries = [_Stop(o.order_id, "delivery", o.delivery, None, cfg.driver_delivery_dwell_min) for o in orders]
    solo = {o.order_id: drive_time_min(start, o.pickup, cfg) + cfg.driver_pickup_dwell_min + drive_time_min(o.pickup, o.delivery, cfg)
            for o in orders}
    best: Route | None = None
    for perm in _valid_permutations(pickups + deliveries):
        route = _evaluate(perm, start, solo, now, cfg)
        if (best is None or route.total_time_min < best.total_time_min) and route.max_detour_min <= cfg.max_detour_minutes:
            best = route
    return best or _evaluate(pickups + deliveries, start, solo, now, cfg)


def _single_route(o: PoolOrder, start: Point, now: datetime, cfg: EngineConfig) -> Route:
    to_pickup, to_drop = drive_time_min(start, o.pickup, cfg), drive_time_min(o.pickup, o.delivery, cfg)
    total = to_pickup + cfg.driver_pickup_dwell_min + to_drop + cfg.driver_delivery_dwell_min
    dist = road_distance_km(start, o.pickup) + road_distance_km(o.pickup, o.delivery)
    at_pickup = now + timedelta(minutes=to_pickup)
    at_drop = at_pickup + timedelta(minutes=cfg.driver_pickup_dwell_min + to_drop)
    stops = [RouteStop(1, "pickup", o.order_id, o.pickup, at_pickup, cfg.driver_pickup_dwell_min),
             RouteStop(2, "delivery", o.order_id, o.delivery, at_drop, cfg.driver_delivery_dwell_min)]
    return Route(stops, _r2(dist), _r2(total), 0, {o.order_id: 0})


def _valid_permutations(stops: list[_Stop]) -> list[list[_Stop]]:
    """Every order of stops with each pickup before its delivery (capped at 500, as in TS)."""
    out: list[list[_Stop]] = []

    def go(cur: list[_Stop], rest: list[_Stop]) -> None:
        if not rest:
            out.append(list(cur))
            return
        if len(out) >= 500:
            return
        for i, s in enumerate(rest):
            if s.type == "delivery" and not any(c.order_id == s.order_id and c.type == "pickup" for c in cur):
                continue
            cur.append(s)
            go(cur, rest[:i] + rest[i + 1:])
            cur.pop()

    go([], stops)
    return out


def _evaluate(stops: list[_Stop], start: Point, solo: dict[str, float], now: datetime, cfg: EngineConfig) -> Route:
    point, t, dist = start, now, 0.0
    out: list[RouteStop] = []
    delivered: dict[str, float] = {}
    for i, s in enumerate(stops):
        dist += road_distance_km(point, s.point)
        t = t + timedelta(minutes=drive_time_min(point, s.point, cfg))
        if s.type == "pickup" and s.ready_at and t < s.ready_at:
            t = s.ready_at  # food not ready: wait
        out.append(RouteStop(i + 1, s.type, s.order_id, s.point, t, s.dwell_min))
        if s.type == "delivery":
            delivered[s.order_id] = (t - now).total_seconds() / 60
        t = t + timedelta(minutes=s.dwell_min)
        point = s.point
    detours = {oid: _r2(max(0.0, at - solo.get(oid, at))) for oid, at in delivered.items()}
    worst = max((max(0.0, at - solo.get(oid, at)) for oid, at in delivered.items()), default=0.0)
    return Route(out, _r2(dist), _r2((t - now).total_seconds() / 60), _r2(worst), detours)


# ── scoring (engine/batch-scorer.ts) ─────────────────────────────────────────

def _normalize(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 50
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100))


def _solo_metrics(orders: list[PoolOrder], start: Point, cfg: EngineConfig) -> tuple[float, float]:
    dist = sum(road_distance_km(start, o.pickup) + road_distance_km(o.pickup, o.delivery) for o in orders)
    time = sum(drive_time_min(start, o.pickup, cfg) + cfg.driver_pickup_dwell_min + drive_time_min(o.pickup, o.delivery, cfg)
               + cfg.driver_delivery_dwell_min for o in orders)
    return dist, time


def score_batch(orders: list[PoolOrder], start: Point, now: datetime | None = None, cfg: EngineConfig = CONFIG,
                w: Weights = WEIGHTS) -> BatchCandidate:
    route = optimize_route(orders, start, now, cfg)
    solo_dist, solo_time = _solo_metrics(orders, start, cfg)
    saved_dist, saved_time = solo_dist - route.total_distance_km, solo_time - route.total_time_min
    savings = saved_dist / solo_dist * 100 if solo_dist > 0 else 0
    if savings < cfg.min_savings_percent and len(orders) > 1:
        return _candidate(orders, route, 0, savings)
    dist_score = _normalize(savings, 0, 50)
    time_score = _normalize(saved_time / solo_time * 100, 0, 40) if solo_time > 0 else 0
    detour_score = 100 - _normalize(route.max_detour_min, 0, cfg.max_detour_minutes)
    priority_score = 20 if any(o.priority == "priority" for o in orders) else 100
    capacity_score = _normalize(len(orders), 1, cfg.max_orders_per_batch)
    total = (dist_score * w.distance_saving + time_score * w.time_saving + detour_score * w.detour_penalty
             + priority_score * w.priority_penalty + capacity_score * w.capacity_fit)
    return _candidate(orders, route, math.floor(total + 0.5), savings)  # Math.round


def _candidate(orders: list[PoolOrder], route: Route, score: int, savings: float) -> BatchCandidate:
    return BatchCandidate(orders, route.stops, route.total_distance_km, route.total_time_min, route.max_detour_min,
                          _r2(savings), score)


# ── the cycle (engine/batch-builder.ts) ──────────────────────────────────────

def run_batch_cycle(waiting: list[PoolOrder], start: Point, now: datetime | None = None,
                    cfg: EngineConfig = CONFIG) -> CycleResult:
    now = now or datetime.now(UTC)
    if not waiting:
        return CycleResult([], [])
    max_wait = timedelta(minutes=cfg.max_wait_in_pool_minutes)
    expired = [o for o in waiting if now - o.created_at > max_wait]
    eligible = [o for o in waiting if now - o.created_at <= max_wait]
    solo_only = [o for o in eligible if o.priority == "priority" and not cfg.priority_order_batchable]
    batchable = [o for o in eligible if not (o.priority == "priority" and not cfg.priority_order_batchable)]
    candidates = [c for g in group_by_pickup(batchable, cfg) for c in _candidates(g, start, now, cfg)]
    selected = greedy_select(candidates)
    selected += [score_batch([o], start, now, cfg) for o in solo_only + expired]
    return CycleResult(selected, [o.order_id for o in expired])


def group_by_pickup(orders: list[PoolOrder], cfg: EngineConfig = CONFIG) -> list[list[PoolOrder]]:
    """Greedy clustering by pickup point, same-restaurant orders first (sorted by restaurant)."""
    groups: list[list[PoolOrder]] = []
    done: set[str] = set()
    ordered = sorted(orders, key=lambda o: o.restaurant_id)
    for o in ordered:
        if o.order_id in done:
            continue
        group = [o]
        done.add(o.order_id)
        for other in ordered:
            if other.order_id not in done and within(o.pickup, other.pickup, cfg.max_pickup_radius_km):
                group.append(other)
                done.add(other.order_id)
        groups.append(group)
    return groups


def delivery_compatible(a: PoolOrder, b: PoolOrder, cfg: EngineConfig = CONFIG) -> bool:
    return within(a.delivery, b.delivery, cfg.max_delivery_radius_km)


def _candidates(group: list[PoolOrder], start: Point, now: datetime, cfg: EngineConfig) -> list[BatchCandidate]:
    out: list[BatchCandidate] = []
    biggest = min(len(group), cfg.max_orders_per_batch)
    for size in (2, 3):
        if biggest < size:
            continue
        for combo in itertools.combinations(group, size):
            if all(delivery_compatible(a, b, cfg) for a, b in itertools.combinations(combo, 2)):
                c = score_batch(list(combo), start, now, cfg)
                if c.score > 0:
                    out.append(c)
    return out


def greedy_select(candidates: list[BatchCandidate]) -> list[BatchCandidate]:
    """Highest score first (then bigger batches); no order in two batches."""
    used: set[str] = set()
    out: list[BatchCandidate] = []
    for c in sorted(candidates, key=lambda c: (-c.score, -len(c.orders))):
        if not used.intersection(c.order_ids):
            out.append(c)
            used.update(c.order_ids)
    return out


__all__ = ["CONFIG", "WEIGHTS", "BatchCandidate", "CycleResult", "EngineConfig", "PoolOrder", "Route", "RouteStop",
           "Weights", "delivery_compatible", "drive_time_min", "greedy_select", "group_by_pickup", "haversine_km",
           "optimize_route", "replace", "road_distance_km", "run_batch_cycle", "score_batch"]
