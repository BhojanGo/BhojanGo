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
