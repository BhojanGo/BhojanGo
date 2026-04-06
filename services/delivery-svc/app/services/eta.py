"""ETA calculation using AWS Location Service (or simple Haversine fallback)."""
import math
from datetime import UTC, datetime, timedelta

import boto3
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_location_client = None


def get_location_client():  # type: ignore[no-untyped-def]
    global _location_client
    if _location_client is None:
        kwargs: dict = {"region_name": settings.AWS_REGION}
        if settings.AWS_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
        _location_client = boto3.client("location", **kwargs)
    return _location_client


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Returns distance in km between two geo points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _estimate_minutes_from_km(distance_km: float, avg_speed_kmh: float = 30.0) -> int:
    return max(5, round((distance_km / avg_speed_kmh) * 60))


async def calculate_eta(
    driver_lat: float,
    driver_lng: float,
    restaurant_lat: float,
    restaurant_lng: float,
    delivery_lat: float,
    delivery_lng: float,
) -> dict:
    """
    Returns estimated pickup and delivery times.
    Uses AWS Location Service if available, falls back to Haversine.
    """
    try:
        client = get_location_client()
        # Calculate driver → restaurant → delivery
        response = client.calculate_route(
            CalculatorName=settings.AWS_LOCATION_ROUTE_CALCULATOR,
            DeparturePosition=[driver_lng, driver_lat],
            DestinationPosition=[delivery_lng, delivery_lat],
            WaypointPositions=[[restaurant_lng, restaurant_lat]],
            TravelMode="Car",
        )
        legs = response["Legs"]
        pickup_seconds = legs[0]["DurationSeconds"]
        delivery_seconds = legs[1]["DurationSeconds"]
        pickup_minutes = round(pickup_seconds / 60)
        delivery_minutes = round((pickup_seconds + delivery_seconds) / 60)

    except Exception as e:
        logger.warning("aws_location_failed_using_haversine", error=str(e))
        # Fallback: Haversine calculation
        d1 = _haversine_km(driver_lat, driver_lng, restaurant_lat, restaurant_lng)
        d2 = _haversine_km(restaurant_lat, restaurant_lng, delivery_lat, delivery_lng)
        pickup_minutes = _estimate_minutes_from_km(d1)
        delivery_minutes = pickup_minutes + _estimate_minutes_from_km(d2) + 10  # +10 prep buffer

    estimated_delivery_time = datetime.now(UTC) + timedelta(minutes=delivery_minutes)

    return {
        "estimated_pickup_minutes": pickup_minutes,
        "estimated_delivery_minutes": delivery_minutes,
        "estimated_delivery_time": estimated_delivery_time.isoformat(),
    }
