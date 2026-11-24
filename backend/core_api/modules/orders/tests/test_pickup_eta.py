"""R34: a pickup order's estimate is its ready time (prep only); delivery keeps ride + handover."""
from datetime import UTC, datetime, timedelta

from core_api.modules.orders.service.order import HANDOVER_MINUTES, order_eta

START = datetime(2026, 11, 23, 18, 0, tzinfo=UTC)


def test_pickup_is_prep_only() -> None:
    assert order_eta("pickup", 15, (43.6, -116.2), (None, None), START) == START + timedelta(minutes=15)


def test_pickup_ignores_a_dropoff() -> None:
    assert order_eta("pickup", 25, (43.6, -116.2), (43.61, -116.21), START) == START + timedelta(minutes=25)


def test_delivery_adds_ride_and_handover() -> None:
    eta = order_eta("delivery", 15, None, None, START)  # no coordinates: the base ride time
    assert eta > START + timedelta(minutes=15 + HANDOVER_MINUTES)
