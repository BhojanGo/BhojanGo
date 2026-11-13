"""Batch engine (task 43): the TypeScript engine's tests, ported one for one
(batch-engine/tests/batch-scorer.test.ts and batch-creation.test.ts), and parity
with numbers the TypeScript engine produced (fixtures/batch_parity.json, made by
batch-engine/tests/parity.ts)."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.batching.engine import PoolOrder, optimize_route, run_batch_cycle, score_batch

NOW = datetime(2026, 11, 13, 19, 0, tzinfo=UTC)
DRIVER_START = (40.7580, -73.9855)  # Times Square, as in the TS tests


def make_order(order_id: str, **kw) -> PoolOrder:  # type: ignore[no-untyped-def]
    return PoolOrder(
        order_id=order_id, restaurant_id=kw.get("restaurant_id", "rest-1"),
        pickup=kw.get("pickup", (40.7614, -73.9776)), delivery=kw.get("delivery", (40.7484, -73.9857)),
        prep_ready_at=kw.get("prep_ready_at", NOW + timedelta(minutes=5)), created_at=kw.get("created_at", NOW),
        priority=kw.get("priority", "standard"))


# ── batch-scorer.test.ts: Route Optimizer ────────────────────────────────────

def test_route_single_order_is_pickup_then_delivery() -> None:
    r = optimize_route([make_order("order-1")], DRIVER_START, NOW)
    assert [s.type for s in r.stops] == ["pickup", "delivery"]
    assert r.total_distance_km > 0 and r.max_detour_min == 0


def test_route_pickup_before_delivery_for_every_order() -> None:
    o1 = make_order("order-1", pickup=(40.7614, -73.9776), delivery=(40.7484, -73.9857))
    o2 = make_order("order-2", pickup=(40.7620, -73.9740), delivery=(40.7500, -73.9800))
    r = optimize_route([o1, o2], DRIVER_START, NOW)
    assert len(r.stops) == 4
    for oid in ("order-1", "order-2"):
        kinds = [(s.order_id, s.type) for s in r.stops]
        assert kinds.index((oid, "pickup")) < kinds.index((oid, "delivery"))


def test_route_distance_and_time_are_positive() -> None:
    r = optimize_route([make_order("order-1")], DRIVER_START, NOW)
    assert r.total_distance_km > 0 and r.total_time_min > 0


# ── batch-scorer.test.ts: Batch Scorer ───────────────────────────────────────

def test_score_single_order() -> None:
    c = score_batch([make_order("order-1")], DRIVER_START, NOW)
    assert c.score >= 0 and c.total_distance_km > 0 and len(c.route) == 2


def test_nearby_pair_saves_distance() -> None:
    o1 = make_order("order-1", pickup=(40.7614, -73.9776), delivery=(40.7484, -73.9857))
    o2 = make_order("order-2", pickup=(40.7618, -73.9770), delivery=(40.7488, -73.9850))
    batch = score_batch([o1, o2], DRIVER_START, NOW)
    solo = score_batch([o1], DRIVER_START, NOW).total_distance_km + score_batch([o2], DRIVER_START, NOW).total_distance_km
    assert batch.total_distance_km < solo and batch.savings_percent > 0


def test_priority_order_is_penalised() -> None:
    std = make_order("order-1")
    near = {"pickup": (40.7618, -73.9770), "delivery": (40.7488, -73.9850)}
    with_priority = score_batch([std, make_order("order-2", priority="priority", **near)], DRIVER_START, NOW)
    without = score_batch([std, make_order("order-3", **near)], DRIVER_START, NOW)
    assert with_priority.score <= without.score


def test_distant_deliveries_have_a_detour() -> None:
    o1 = make_order("order-1", delivery=(40.7484, -73.9857))
    o2 = make_order("order-2", pickup=(40.7618, -73.9770), delivery=(40.6892, -74.0445))
    assert score_batch([o1, o2], DRIVER_START, NOW).max_detour_min > 0


# ── batch-creation.test.ts: runBatchCycle ────────────────────────────────────

def test_cycle_empty_pool() -> None:
    r = run_batch_cycle([], DRIVER_START, NOW)
    assert r.batches == [] and r.expired_order_ids == []


def test_cycle_groups_two_nearby_orders() -> None:
    o1 = make_order("order-1", pickup=(40.7614, -73.9776), delivery=(40.7484, -73.9857))
    o2 = make_order("order-2", pickup=(40.7618, -73.977), delivery=(40.7488, -73.985))
    r = run_batch_cycle([o1, o2], DRIVER_START, NOW)
    multi = next(b for b in r.batches if len(b.orders) == 2)
    ids = [i for b in r.batches for i in b.order_ids]
    assert len(set(ids)) == len(ids) and len(multi.route) == 4


def test_cycle_does_not_batch_far_apart_deliveries() -> None:
    o1 = make_order("order-1", delivery=(40.7484, -73.9857))
    o2 = make_order("order-2", pickup=(40.7618, -73.977), delivery=(40.6892, -74.0445))
    assert [b for b in run_batch_cycle([o1, o2], DRIVER_START, NOW).batches if len(b.orders) > 1] == []


def test_cycle_ships_an_expired_order_solo() -> None:
    stale = make_order("order-stale", created_at=NOW - timedelta(hours=1))
    r = run_batch_cycle([stale], DRIVER_START, NOW)
    assert "order-stale" in r.expired_order_ids
    assert any(b.order_ids == ["order-stale"] for b in r.batches)


# ── parity with the TypeScript engine ────────────────────────────────────────

PARITY = json.loads((Path(__file__).parent / "fixtures" / "batch_parity.json").read_text())
STARTS = {"boise": (43.615, -116.2023), "hyd": (17.4486, 78.3908)}


def _pool(o: dict) -> PoolOrder:
    return PoolOrder(order_id=o["id"], restaurant_id=o["rest"], pickup=tuple(o["pickup"]), delivery=tuple(o["drop"]),
                     prep_ready_at=NOW + timedelta(minutes=o["readyIn"]), created_at=NOW - timedelta(minutes=o["ago"]),
                     priority=o.get("priority", "standard"))


@pytest.mark.parametrize("case", PARITY["scores"], ids=[c["name"] for c in PARITY["scores"]])
def test_scores_match_the_typescript_engine(case: dict) -> None:
    c = score_batch([_pool(o) for o in case["orders"]], STARTS[case["start"]], NOW)
    assert c.score == case["score"]
    assert c.total_distance_km == pytest.approx(case["totalDistanceKm"], abs=0.011)
    assert c.total_time_min == pytest.approx(case["totalTimeMin"], abs=0.011)
    assert c.max_detour_min == pytest.approx(case["maxDetourMin"], abs=0.011)
    assert c.savings_percent == pytest.approx(case["savingsPercent"], abs=0.011)
    assert [f"{s.type}:{s.order_id}" for s in c.route] == case["route"]


@pytest.mark.parametrize("case", PARITY["cycles"], ids=[c["name"] for c in PARITY["cycles"]])
def test_cycles_match_the_typescript_engine(case: dict) -> None:
    r = run_batch_cycle([_pool(o) for o in case["orders"]], STARTS[case["start"]], NOW)
    assert [{"orders": b.order_ids, "score": b.score} for b in r.batches] == case["batches"]
    assert r.expired_order_ids == case["expired"]
