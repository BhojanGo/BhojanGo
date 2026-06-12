"""Geo helper for delivery-radius validation at order time.

Mirrors restaurant-svc/app/services/geo.py (services are deployed independently,
so the small pure helper is duplicated rather than shared).
"""
from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0
LONG_DISTANCE_RATIO = 0.8


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_long_distance(distance_km: float, radius_km: float, ratio: float = LONG_DISTANCE_RATIO) -> bool:
    if radius_km <= 0:
        return False
    return distance_km >= radius_km * ratio
