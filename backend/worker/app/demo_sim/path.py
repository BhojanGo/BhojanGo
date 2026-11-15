"""Where the demo rider is (the demo rider simulator, app/demo_sim): a believable
path between two points, no routing service, and a city riding speed.

The path runs the way a street grid makes you ride: mostly along one axis, then
the other, with a bend in the corner and a couple of kinks, never a straight
line. It is a pure function of its seed (the order id), so after a worker
restart the rider carries on from the same place.
"""
import math
import random
from dataclasses import dataclass

Point = tuple[float, float]  # (lat, lng)

EARTH_KM = 6371.0
FIX_SECONDS = 4.0               # a GPS fix every few seconds, like the rider app
SPEED_KMH = (18.0, 25.0)        # a scooter in city traffic
START_KM = (1.0, 1.8)           # where the rider is when they accept, from the kitchen


def haversine_km(a: Point, b: Point) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return EARTH_KM * 2 * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(a: Point, b: Point) -> float:
    """Compass heading from a to b, 0-360."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def offset(p: Point, km: float, heading: float) -> Point:
    """The point ``km`` from ``p`` towards ``heading`` (degrees), flat-earth (fine over a few km)."""
    rad = math.radians(heading)
    return (p[0] + km * math.cos(rad) / 111.32, p[1] + km * math.sin(rad) / (111.32 * math.cos(math.radians(p[0]))))


def waypoints(a: Point, b: Point, seed: str) -> list[Point]:
    """``a`` to ``b`` through the streets: along one axis, a rounded corner, then the
    other, each stretch with a small sideways kink. 5-6 points; never longer than
    about 1.5 times the straight line."""
    if haversine_km(a, b) < 0.05:
        return [a, b]
    rng = random.Random(seed)
    corner = (b[0], a[1]) if rng.random() < 0.5 else (a[0], b[1])
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    t = rng.uniform(0.4, 0.75)  # how square the corner is
    bend = (middle[0] + (corner[0] - middle[0]) * t, middle[1] + (corner[1] - middle[1]) * t)
    out = [a]
    for p, q in ((a, bend), (bend, b)):
        f = rng.uniform(0.3, 0.7)
        along = (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
        side = rng.uniform(-0.06, 0.06) * haversine_km(p, q)
        out.append(offset(along, abs(side), bearing_deg(p, q) + (90 if side >= 0 else -90)))
        out.append(q)
    return out


def speed_kmh(seed: str) -> float:
    return random.Random(f"{seed}/speed").uniform(*SPEED_KMH)


def rider_start(kitchen: Point, seed: str) -> Point:
    """Where the rider is when they take the order: 1-1.8 km from the kitchen."""
    rng = random.Random(f"{seed}/start")
    return offset(kitchen, rng.uniform(*START_KM), rng.uniform(0, 360))


@dataclass(frozen=True)
class Path:
    points: tuple[Point, ...]

    @classmethod
    def between(cls, a: Point, b: Point, seed: str) -> "Path":
        return cls(tuple(waypoints(a, b, seed)))

    @property
    def legs(self) -> list[float]:
        return [haversine_km(p, q) for p, q in zip(self.points, self.points[1:])]

    @property
    def length_km(self) -> float:
        return sum(self.legs)

    def at(self, km: float) -> tuple[Point, float]:
        """(position, heading) ``km`` along the path; the end once past it."""
        km = max(0.0, km)
        for (p, q), leg in zip(zip(self.points, self.points[1:]), self.legs):
            if km <= leg and leg > 0:
                f = km / leg
                return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f), bearing_deg(p, q)
            km -= leg
        last = self.points[-2:] if len(self.points) > 1 else (self.points[0], self.points[0])
        return self.points[-1], bearing_deg(last[0], last[1])

    def minutes(self, speed: float) -> float:
        return self.length_km / speed * 60

    def ride(self, elapsed_seconds: float, speed: float) -> tuple[Point, float, bool]:
        """(position, heading, arrived) after riding ``elapsed_seconds`` at ``speed`` km/h."""
        km = speed * max(0.0, elapsed_seconds) / 3600
        point, heading = self.at(km)
        return point, heading, km >= self.length_km
