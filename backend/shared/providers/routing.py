"""Routing: distance and travel time between points.

``straight_line`` is great-circle distance x ROAD_FACTOR (1.3 by default, a
common urban detour factor) at AVG_SPEED_KMH. It is free and offline; a
routing API can be added behind the same interface later.
"""
import math
from dataclasses import dataclass
from typing import Protocol

from shared.config import get_settings
from shared.providers import ProviderConfigError

Point = tuple[float, float]  # (lat, lng)


def haversine_km(a: Point, b: Point) -> float:
    lat1, lng1 = a
    lat2, lng2 = b
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


@dataclass(frozen=True)
class Leg:
    distance_km: float
    minutes: float


class RoutingProvider(Protocol):
    name: str

    def leg(self, a: Point, b: Point) -> Leg: ...


class StraightLineRouting:
    name = "straight_line"

    def __init__(self, road_factor: float, speed_kmh: float) -> None:
        self.road_factor = road_factor
        self.speed_kmh = speed_kmh

    def leg(self, a: Point, b: Point) -> Leg:
        km = haversine_km(a, b) * self.road_factor
        return Leg(distance_km=km, minutes=km / self.speed_kmh * 60)


def get_routing_provider() -> RoutingProvider:
    p = get_settings().providers
    if p.ROUTING_PROVIDER == "straight_line":
        return StraightLineRouting(p.ROAD_FACTOR, p.AVG_SPEED_KMH)
    raise ProviderConfigError(f"Unknown ROUTING_PROVIDER '{p.ROUTING_PROVIDER}'")
