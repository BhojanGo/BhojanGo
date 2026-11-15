"""ETA for a delivery: rider -> restaurant -> customer, via the routing provider.

The default provider (shared/providers/routing.py) is straight-line distance x
1.3 road factor at an average city speed: free, offline, and good enough for
the pilot. A routing API can replace it behind the same interface.
"""
from datetime import UTC, datetime, timedelta

from shared.providers.routing import get_routing_provider, haversine_km

MIN_LEG_MINUTES = 5
PREP_BUFFER_MINUTES = 10  # handover at the restaurant


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km((lat1, lng1), (lat2, lng2))


def _estimate_minutes_from_km(distance_km: float, avg_speed_kmh: float = 30.0) -> int:
    return max(MIN_LEG_MINUTES, round((distance_km / avg_speed_kmh) * 60))


async def calculate_eta(
    driver_lat: float,
    driver_lng: float,
    restaurant_lat: float,
    restaurant_lng: float,
    delivery_lat: float,
    delivery_lng: float,
) -> dict:
    """Estimated pickup and delivery minutes from now."""
    routing = get_routing_provider()
    to_restaurant = routing.leg((driver_lat, driver_lng), (restaurant_lat, restaurant_lng))
    to_customer = routing.leg((restaurant_lat, restaurant_lng), (delivery_lat, delivery_lng))

    pickup_minutes = max(MIN_LEG_MINUTES, round(to_restaurant.minutes))
    delivery_minutes = pickup_minutes + max(MIN_LEG_MINUTES, round(to_customer.minutes)) + PREP_BUFFER_MINUTES

    return {
        "estimated_pickup_minutes": pickup_minutes,
        "estimated_delivery_minutes": delivery_minutes,
        "estimated_delivery_time": (datetime.now(UTC) + timedelta(minutes=delivery_minutes)).isoformat(),
    }


KM_PER_MI = 1.609344
Point = tuple[float, float]


def distance_left_eta(
    rider_at: Point,
    pickup: Point | None,
    dropoff: Point,
    *,
    picked_up: bool,
    prep_left_minutes: float = 0.0,
    distance_unit: str = "km",
    now: float | None = None,
    routing=None,  # type: ignore[no-untyped-def]
) -> dict:
    """The live ETA on the tracking page, from the distance the rider still has to go.

    After pickup: rider -> home. Before pickup: rider -> kitchen -> home, and the
    rider can't leave the kitchen before the food is ready, so the wait there is
    the longer of the ride to the kitchen and the prep time left. Travel time is
    the routing provider's (road distance at a realistic city speed).

    ``distance_left`` is the road distance still to ride to the customer, in the
    country's unit (``distance_unit``: km or mi), so "N km left" and the minutes
    always tell the same story.
    """
    routing = routing or get_routing_provider()
    now = datetime.now(UTC).timestamp() if now is None else now
    if picked_up or pickup is None:
        home = routing.leg(rider_at, dropoff)
        to_pickup, to_customer, km = 0.0, home.minutes, home.distance_km
    else:
        kitchen = routing.leg(rider_at, pickup)
        home = routing.leg(pickup, dropoff)
        to_pickup = kitchen.minutes
        to_customer = max(to_pickup, max(0.0, prep_left_minutes)) + home.minutes
        km = kitchen.distance_km + home.distance_km
    left = km / KM_PER_MI if distance_unit == "mi" else km
    return {
        "to_pickup_minutes": 0 if picked_up or pickup is None else max(1, round(to_pickup)),
        "to_customer_minutes": max(1, round(to_customer)),
        "arrives_at": datetime.fromtimestamp(now + to_customer * 60, UTC).isoformat(),
        "distance_left": round(left, 2),
        "distance_unit": "mi" if distance_unit == "mi" else "km",
    }
