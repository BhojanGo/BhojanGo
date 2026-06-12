"""Unit tests for hyper-local delivery radius validation."""
from app.services.geo import haversine_km, is_long_distance, is_within_radius

# Bengaluru reference points
MG_ROAD = (12.9756, 77.6068)
INDIRANAGAR = (12.9719, 77.6412)  # ~3.8 km from MG Road
WHITEFIELD = (12.9698, 77.7500)   # ~15.6 km from MG Road


def test_haversine_zero_distance():
    assert haversine_km(*MG_ROAD, *MG_ROAD) == 0.0


def test_haversine_known_distance():
    d = haversine_km(*MG_ROAD, *INDIRANAGAR)
    assert 3.0 < d < 4.5  # ~3.8 km


def test_haversine_symmetric():
    a = haversine_km(*MG_ROAD, *WHITEFIELD)
    b = haversine_km(*WHITEFIELD, *MG_ROAD)
    assert abs(a - b) < 1e-9


def test_within_radius_true():
    assert is_within_radius(*MG_ROAD, *INDIRANAGAR, radius_km=5.0) is True


def test_within_radius_false_outside():
    # Whitefield (~15.6 km) is outside a 5 km radius
    assert is_within_radius(*MG_ROAD, *WHITEFIELD, radius_km=5.0) is False


def test_within_radius_boundary_inclusive():
    d = haversine_km(*MG_ROAD, *INDIRANAGAR)
    assert is_within_radius(*MG_ROAD, *INDIRANAGAR, radius_km=d) is True


def test_long_distance_flag():
    # 4.5 km within a 5 km radius -> >= 80% -> long distance
    assert is_long_distance(4.5, 5.0) is True
    # 2 km within a 5 km radius -> not long distance
    assert is_long_distance(2.0, 5.0) is False


def test_long_distance_zero_radius_safe():
    assert is_long_distance(1.0, 0.0) is False


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all geo tests passed")
