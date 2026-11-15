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


# ── the live ETA from the distance left (tracking page) ───────────────────────
from app.services import dispatch  # noqa: E402
from app.services.eta import distance_left_eta  # noqa: E402
from shared.providers.routing import StraightLineRouting  # noqa: E402

ROUTE = StraightLineRouting(road_factor=1.3, speed_kmh=25)
KITCHEN, HOME = (17.4486, 78.3908), (17.4483, 78.3915)
NOW = 1_800_000_000.0


def north_of(p: tuple[float, float], km: float) -> tuple[float, float]:
    return (p[0] + km / 111.195, p[1])


def test_after_pickup_minutes_come_from_the_ride_home():
    eta = distance_left_eta(north_of(HOME, 3), KITCHEN, HOME, picked_up=True, now=NOW, routing=ROUTE)
    # 3 km x 1.3 = 3.9 km at 25 km/h = 9.4 min
    assert eta["to_customer_minutes"] == 9 and eta["to_pickup_minutes"] == 0
    assert eta["distance_left"] == pytest.approx(3.9, abs=0.02) and eta["distance_unit"] == "km"
    assert eta["arrives_at"].startswith("2027-01-15T08:")


def test_minutes_and_distance_go_down_as_the_rider_gets_closer():
    far = distance_left_eta(north_of(HOME, 3), KITCHEN, HOME, picked_up=True, now=NOW, routing=ROUTE)
    near = distance_left_eta(north_of(HOME, 1), KITCHEN, HOME, picked_up=True, now=NOW, routing=ROUTE)
    assert near["to_customer_minutes"] < far["to_customer_minutes"]
    assert near["distance_left"] < far["distance_left"]
    assert near["arrives_at"] < far["arrives_at"]


def test_at_the_door_is_never_zero_minutes():
    eta = distance_left_eta(HOME, KITCHEN, HOME, picked_up=True, now=NOW, routing=ROUTE)
    assert eta["to_customer_minutes"] == 1 and eta["distance_left"] == 0


def test_before_pickup_the_ride_goes_through_the_kitchen():
    kitchen, home = (17.40, 78.40), north_of((17.40, 78.40), 2)
    rider = north_of(kitchen, -1)  # 1 km south of the kitchen, home 2 km north of it
    eta = distance_left_eta(rider, kitchen, home, picked_up=False, now=NOW, routing=ROUTE)
    # (1 + 2) km x 1.3 = 3.9 km: 3.1 min to the kitchen, 9.4 min in all
    assert eta["to_pickup_minutes"] == 3 and eta["to_customer_minutes"] == 9
    assert eta["distance_left"] == pytest.approx(3.9, abs=0.02)


def test_before_pickup_the_rider_waits_for_the_food():
    kitchen, home = (17.40, 78.40), north_of((17.40, 78.40), 2)
    rider = north_of(kitchen, -1)
    eta = distance_left_eta(rider, kitchen, home, picked_up=False, prep_left_minutes=12, now=NOW, routing=ROUTE)
    # the food is ready in 12 min (the rider is there in 3): 12 + 6.2 to the door
    assert eta["to_pickup_minutes"] == 3 and eta["to_customer_minutes"] == 18
    late = distance_left_eta(rider, kitchen, home, picked_up=False, prep_left_minutes=1, now=NOW, routing=ROUTE)
    assert late["to_customer_minutes"] == 9  # food ready before the rider arrives: no wait


def test_distance_left_in_miles_for_a_miles_country():
    km = distance_left_eta(north_of(HOME, 3), KITCHEN, HOME, picked_up=True, now=NOW, routing=ROUTE)
    mi = distance_left_eta(north_of(HOME, 3), KITCHEN, HOME, picked_up=True, distance_unit="mi", now=NOW, routing=ROUTE)
    assert mi["distance_unit"] == "mi" and mi["distance_left"] == pytest.approx(km["distance_left"] / 1.609344, abs=0.01)
    assert mi["to_customer_minutes"] == km["to_customer_minutes"]  # the unit never changes the time


def test_prep_left_counts_down_from_ready_at(monkeypatch):
    monkeypatch.setattr(dispatch, "_now", lambda: NOW)
    assert dispatch.prep_left_minutes({"status": "preparing", "ready_at": NOW + 600}) == pytest.approx(10)
    assert dispatch.prep_left_minutes({"status": "preparing", "ready_at": NOW - 60}) == 0
    assert dispatch.prep_left_minutes({"status": "preparing", "ready_in_minutes": 7}) == 7
    assert dispatch.prep_left_minutes({"status": "ready", "ready_at": NOW + 600}) == 0
    assert dispatch.prep_left_minutes({"status": "accepted"}) == 0


def test_eta_for_uses_the_order_status_and_unit(monkeypatch):
    monkeypatch.setattr(dispatch, "_now", lambda: NOW)
    monkeypatch.setattr(dispatch, "get_routing_provider", lambda: ROUTE)
    info = {"pickup": list(KITCHEN), "dropoff": list(HOME), "status": "picked_up", "distance_unit": "mi"}
    eta = dispatch.eta_for(info, north_of(HOME, 3))
    assert eta is not None and eta["to_customer_minutes"] == 9 and eta["distance_unit"] == "mi"
    assert dispatch.eta_for({**info, "dropoff": None}, north_of(HOME, 3)) is None
    assert dispatch.eta_for(info, None) is None
