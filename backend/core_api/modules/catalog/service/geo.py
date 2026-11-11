"""Geo utilities for hyper-local delivery radius enforcement.

Pure functions (no I/O) so they are trivial to unit-test and reuse.
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0

# An order whose delivery distance exceeds this fraction of the restaurant's
# allowed radius is flagged as "long distance" (deadhead-miles risk for drivers).
LONG_DISTANCE_RATIO = 0.8


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def is_within_radius(
    restaurant_lat: float,
    restaurant_lng: float,
    dest_lat: float,
    dest_lng: float,
    radius_km: float,
) -> bool:
    """True if the destination is within the restaurant's delivery radius."""
    return haversine_km(restaurant_lat, restaurant_lng, dest_lat, dest_lng) <= radius_km


def is_long_distance(distance_km: float, radius_km: float, ratio: float = LONG_DISTANCE_RATIO) -> bool:
    """True if the (in-radius) order is far enough to risk deadhead miles for drivers."""
    if radius_km <= 0:
        return False
    return distance_km >= radius_km * ratio
