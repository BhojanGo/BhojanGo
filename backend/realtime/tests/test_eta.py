import pytest

from app.services.eta import _estimate_minutes_from_km, _haversine_km


def test_haversine_same_point():
    assert _haversine_km(40.7128, -74.0060, 40.7128, -74.0060) == pytest.approx(0.0, abs=0.001)


def test_haversine_known_distance():
    # NYC to LA is ~3940 km
    dist = _haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3800 < dist < 4100


def test_haversine_short_distance():
    # ~1.5 km apart
    dist = _haversine_km(28.6139, 77.2090, 28.6200, 77.2180)
    assert 0 < dist < 5


def test_estimate_minutes_minimum():
    assert _estimate_minutes_from_km(0.0) == 5  # minimum 5 minutes


def test_estimate_minutes_normal():
    # 15 km at 30 km/h = 30 minutes
    assert _estimate_minutes_from_km(15.0, avg_speed_kmh=30.0) == 30


def test_estimate_minutes_fast_speed():
    # 60 km at 60 km/h = 60 minutes
    assert _estimate_minutes_from_km(60.0, avg_speed_kmh=60.0) == 60


async def test_calculate_eta_uses_road_factor():
    from app.services.eta import calculate_eta

    # Rider at the restaurant; customer ~4.2 km straight line away in Hyderabad.
    eta = await calculate_eta(17.4483, 78.3915, 17.4483, 78.3915, 17.4861, 78.3915)
    assert eta["estimated_pickup_minutes"] == 5  # minimum leg
    # 4.2 km x 1.3 = 5.46 km at 25 km/h = 13 min, + 5 pickup + 10 handover
    assert eta["estimated_delivery_minutes"] == 28


def test_straight_line_leg():
    from shared.providers.routing import StraightLineRouting

    leg = StraightLineRouting(road_factor=1.3, speed_kmh=30).leg((17.4483, 78.3915), (17.4861, 78.3915))
    assert leg.distance_km == pytest.approx(4.2 * 1.3, rel=0.01)
    assert leg.minutes == pytest.approx(leg.distance_km / 30 * 60)
