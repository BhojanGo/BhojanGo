"""The admin overview's numbers agree with each other (P21 review): late orders
count against "on time", and the median delivery time comes only from
completed orders, once there are at least five."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from core_api.modules.orders.api.v1.ops import _totals

NOW = datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
START = NOW - timedelta(hours=10)


def order(status: str, minutes: float | None = None, late_by: float = 0, eta_from_now: float | None = None) -> SimpleNamespace:
    placed = NOW - timedelta(hours=2)
    eta = placed + timedelta(minutes=35)
    delivered = placed + timedelta(minutes=minutes) if minutes is not None else None
    if eta_from_now is not None:
        eta = NOW + timedelta(minutes=eta_from_now)
    return SimpleNamespace(id=uuid.uuid4(), status=status, created_at=placed, placed_at=placed, total="500.00",
                           actual_delivery_time=delivered, estimated_delivery_time=eta, driver_id=uuid.uuid4(),
                           actual_ready_at=None, updated_at=placed)


def test_median_needs_five_completed_orders() -> None:
    four = [order("delivered", m) for m in (20, 30, 40, 50)] + [order("preparing", eta_from_now=20)]
    assert _totals(four, {}, START, NOW).median_delivery_min is None
    five = four + [order("delivered", 25)]
    assert _totals(five, {}, START, NOW).median_delivery_min == 30.0  # cancelled or live orders never count


def test_late_orders_count_against_on_time() -> None:
    orders = [order("delivered", 30), order("delivered", 30), order("delivered", 50)]  # given 35 min: two on time, one late
    assert _totals(orders, {}, START, NOW).on_time_pct == 66.7
    # One more still on its way and already 20 min past what the customer was told.
    orders.append(order("picked_up", eta_from_now=-20))
    t = _totals(orders, {}, START, NOW)
    assert t.on_time_pct == 50.0 and t.late == 1
    # On its way but not late yet: not counted either way.
    orders.append(order("preparing", eta_from_now=15))
    assert _totals(orders, {}, START, NOW).on_time_pct == 50.0
