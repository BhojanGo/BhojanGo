"""The worker's batch cycle (task 43): shadow suggestions for every city, and
live pairs only from the same kitchen, sent in drop-off order."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.batching.engine import PoolOrder
from app.services import batching

NOW = datetime(2026, 11, 13, 1, 0, tzinfo=UTC)  # 6 pm in Boise
BOWL, PIZZA = (43.6295, -116.2008), (43.6320, -116.2110)  # ~0.9 km apart


def order(oid: str, rest: str, pickup: tuple, drop: tuple, waited: float = 1, ready_in: float = 2) -> PoolOrder:
    return PoolOrder(order_id=oid, restaurant_id=rest, pickup=pickup, delivery=drop,
                     prep_ready_at=NOW + timedelta(minutes=ready_in), created_at=NOW - timedelta(minutes=waited))


def test_live_pairs_come_from_one_kitchen_and_shadow_sees_more() -> None:
    orders = [
        order("a", "bowl", BOWL, (43.6390, -116.2080)),
        order("b", "bowl", BOWL, (43.6400, -116.2060)),   # next door to a's drop-off
        order("c", "pizza", PIZZA, (43.6380, -116.2100)),  # another kitchen, close by
        order("d", "pizza", PIZZA, (43.6395, -116.2070)),
    ]
    shadow, live = batching.plan(orders, NOW)
    assert shadow, "the engine finds something to suggest"
    assert live and all(len(b["orders"]) == 2 for b in live)
    kitchens = {o.order_id: o.restaurant_id for o in orders}
    for b in live:
        assert len({kitchens[o] for o in b["orders"]}) == 1  # riders are only offered same-kitchen pairs
        assert b["score"] > 0 and b["savings_percent"] >= 15


def test_far_apart_drop_offs_are_never_live() -> None:
    orders = [order("a", "bowl", BOWL, (43.6390, -116.2080)), order("b", "bowl", BOWL, (43.5600, -116.2900))]
    assert batching.plan(orders, NOW)[1] == []


def test_one_order_waiting_plans_nothing() -> None:
    assert batching.plan([order("a", "bowl", BOWL, (43.6390, -116.2080))], NOW) == ([], [])


def test_pool_entry_is_when_it_started_looking_for_a_rider() -> None:
    accepted = NOW - timedelta(minutes=9)
    row = SimpleNamespace(
        id="o1", restaurant_id="r1", restaurant_name="Boise Bowl Co.", market_city="US-ID-BOI",
        pickup_lat=BOWL[0], pickup_lng=BOWL[1], delivery_lat=43.639, delivery_lng=-116.208,
        status_history=[{"status": "accepted", "at": accepted.isoformat()},
                        {"status": "almost_ready", "at": (NOW - timedelta(minutes=2)).isoformat()}],
        restaurant_accepted_at=accepted, estimated_prep_minutes=12, actual_ready_at=None, updated_at=NOW)
    o = batching._pool_order(row)
    assert o.created_at == NOW - timedelta(minutes=2)          # not when it was ordered
    assert o.prep_ready_at == accepted + timedelta(minutes=12)  # the kitchen's estimate


def test_live_pairs_need_one_order_already_looking_for_a_rider() -> None:
    a = order("a", "bowl", BOWL, (43.6390, -116.2080))
    b = order("b", "bowl", BOWL, (43.6400, -116.2060), ready_in=4)
    assert batching.plan([a, b], NOW, dispatching=set())[1] == []       # both still cooking: nothing yet
    assert batching.plan([a, b], NOW, dispatching={"a"})[1] != []      # a is almost ready: pair it with b


def test_an_order_still_cooking_is_not_waiting_yet() -> None:
    accepted = NOW - timedelta(minutes=3)
    row = SimpleNamespace(
        id="o2", status="preparing", restaurant_id="r1", restaurant_name="Boise Bowl Co.", market_city="US-ID-BOI",
        pickup_lat=BOWL[0], pickup_lng=BOWL[1], delivery_lat=43.639, delivery_lng=-116.208,
        status_history=[{"status": "accepted", "at": accepted.isoformat()}],
        restaurant_accepted_at=accepted, estimated_prep_minutes=8, actual_ready_at=None, updated_at=NOW)
    o = batching._pool_order(row, NOW)
    assert o.created_at == NOW                                  # not waiting, so it never expires into a solo trip
    assert o.prep_ready_at == accepted + timedelta(minutes=8)   # ready in 5 minutes
