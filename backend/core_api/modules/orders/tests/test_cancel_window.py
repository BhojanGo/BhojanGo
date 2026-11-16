"""R8: when the customer may cancel (orders.service.order.customer_cancel_window), the
one rule behind the cancel itself and the "Cancel order" button."""
from datetime import UTC, datetime, timedelta

from core_api.modules.orders.service.order import customer_cancel_window

NOW = datetime(2026, 11, 15, 20, 0, tzinfo=UTC)


def test_before_the_kitchen_accepts_any_time():
    assert customer_cancel_window("pending_payment", None, 2, NOW) == (True, None)
    assert customer_cancel_window("placed", NOW - timedelta(minutes=30), 2, NOW) == (True, None)


def test_after_accepting_only_within_the_window_from_placing():
    placed = NOW - timedelta(minutes=1)
    assert customer_cancel_window("accepted", placed, 2, NOW) == (True, placed + timedelta(minutes=2))
    late = NOW - timedelta(minutes=3)
    assert customer_cancel_window("accepted", late, 2, NOW) == (False, late + timedelta(minutes=2))


def test_never_once_cooking_or_later():
    for status in ("preparing", "almost_ready", "ready", "picked_up", "delivered", "cancelled"):
        assert customer_cancel_window(status, NOW, 60, NOW) == (False, None)
