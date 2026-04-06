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
