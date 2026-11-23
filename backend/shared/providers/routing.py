"""Routing: distance and travel time between points.

``osrm`` (R31) is the road distance from a self-hosted OSRM server (free, no API key: docker compose
service ``osrm``, map data for the live cities). When OSRM can't answer (down, slow, no route), the
straight-line estimate is used instead and every fallback is logged (``routing_fallback``).
``straight_line`` is great-circle distance x ROAD_FACTOR (1.3 by default, a common urban detour factor,
configurable) at AVG_SPEED_KMH: free and offline, and what the tests use.
"""
import math
from dataclasses import dataclass
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError

logger = structlog.get_logger(__name__)
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

    def legs_to(self, origins: list[Point], b: Point) -> list[Leg]: ...


class StraightLineRouting:
    name = "straight_line"

    def __init__(self, road_factor: float, speed_kmh: float) -> None:
        self.road_factor = road_factor
        self.speed_kmh = speed_kmh

    def leg(self, a: Point, b: Point) -> Leg:
        km = haversine_km(a, b) * self.road_factor
        return Leg(distance_km=km, minutes=km / self.speed_kmh * 60)

    def legs_to(self, origins: list[Point], b: Point) -> list[Leg]:
        return [self.leg(a, b) for a in origins]


class OsrmRouting:
    """Road distance and time from OSRM's HTTP API (route for one leg, table for many origins to one
    destination). Any failure falls back to the straight-line estimate, logged with the reason."""

    name = "osrm"

    def __init__(self, url: str, timeout: float, fallback: StraightLineRouting) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.fallback = fallback

    def _get(self, path: str) -> dict:
        import httpx

        r = httpx.get(f"{self.url}{path}", timeout=self.timeout)
        r.raise_for_status()
        body = r.json()
        if body.get("code") != "Ok":
            raise ValueError(f"osrm {body.get('code')}: {body.get('message', '')}"[:200])
        return body

    def _fell_back(self, reason: Exception, n: int) -> None:
        logger.warning("routing_fallback", provider="osrm", legs=n, reason=f"{type(reason).__name__}: {reason}"[:300],
                       road_factor=self.fallback.road_factor)

    def leg(self, a: Point, b: Point) -> Leg:
        try:  # OSRM takes lng,lat
            route = self._get(f"/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=false")["routes"][0]
            return Leg(distance_km=route["distance"] / 1000, minutes=route["duration"] / 60)
        except Exception as e:  # noqa: BLE001 - routing must never fail an order: estimate instead
            self._fell_back(e, 1)
            return self.fallback.leg(a, b)

    def legs_to(self, origins: list[Point], b: Point) -> list[Leg]:
        if not origins:
            return []
        try:
            coords = ";".join(f"{p[1]},{p[0]}" for p in [*origins, b])
            n = len(origins)
            t = self._get(f"/table/v1/driving/{coords}?sources={';'.join(map(str, range(n)))}&destinations={n}"
                          "&annotations=distance,duration")
            out = []
            for i, a in enumerate(origins):
                d, m = t["distances"][i][0], t["durations"][i][0]
                if d is None or m is None:  # no road between them: estimate this one
                    self._fell_back(ValueError("no route"), 1)
                    out.append(self.fallback.leg(a, b))
                else:
                    out.append(Leg(distance_km=d / 1000, minutes=m / 60))
            return out
        except Exception as e:  # noqa: BLE001
            self._fell_back(e, len(origins))
            return self.fallback.legs_to(origins, b)


def get_routing_provider() -> RoutingProvider:
    p = get_settings().providers
    if p.ROUTING_PROVIDER == "straight_line":
        return StraightLineRouting(p.ROAD_FACTOR, p.AVG_SPEED_KMH)
    if p.ROUTING_PROVIDER == "osrm":
        return OsrmRouting(p.OSRM_URL, p.OSRM_TIMEOUT_SECONDS, StraightLineRouting(p.ROAD_FACTOR, p.AVG_SPEED_KMH))
    raise ProviderConfigError(f"Unknown ROUTING_PROVIDER '{p.ROUTING_PROVIDER}'")
