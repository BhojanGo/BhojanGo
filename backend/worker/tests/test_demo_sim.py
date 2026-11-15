"""The demo rider simulator (app/demo_sim): its path and speed, the guard that keeps
it out of production, which orders it may touch, and what it does next."""
from datetime import UTC, datetime, timedelta

import pytest
from app.demo_sim import path as P
from app.demo_sim import rules as R

KITCHEN = (17.4400, 78.3550)
HOME = (17.4560, 78.3870)
NOW = datetime(2026, 11, 15, 13, 0, tzinfo=UTC)
RIDER = "rider-1"


def _off_line(p: P.Point, a: P.Point, b: P.Point) -> float:
    """km from p to the straight line a-b (flat, fine at city scale)."""
    import math

    k = math.cos(math.radians(a[0]))
    ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], p[1] * k, p[0]
    num = abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax)
    return num / math.hypot(by - ay, bx - ax) * 111.32


# ── path and speed ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", [f"order-{i}" for i in range(25)])
def test_path_is_believable(seed: str) -> None:
    path = P.Path.between(KITCHEN, HOME, seed)
    straight = P.haversine_km(KITCHEN, HOME)
    assert path.points[0] == KITCHEN and path.points[-1] == HOME
    assert 4 <= len(path.points) <= 6
    assert straight < path.length_km <= straight * 1.55, "a few turns, not a detour"
    assert max(_off_line(p, KITCHEN, HOME) for p in path.points) > 0.15, "never a straight line"
    assert path == P.Path.between(KITCHEN, HOME, seed), "the same order rides the same way after a restart"


def test_riding_along_the_path() -> None:
    path = P.Path.between(KITCHEN, HOME, "o")
    assert path.at(0)[0] == KITCHEN
    assert path.at(path.length_km + 1)[0] == HOME
    point, heading, arrived = path.ride(60, 20)  # one minute at 20 km/h: a third of a km
    assert not arrived and 0 <= heading < 360
    assert P.haversine_km(KITCHEN, point) <= 1 / 3 + 1e-6
    _, _, arrived = path.ride(path.minutes(20) * 60 + 1, 20)
    assert arrived
    # consecutive fixes FIX_SECONDS apart are a believable 20-28 m apart at city speed
    a, _, _ = path.ride(120, 20)
    b, _, _ = path.ride(120 + P.FIX_SECONDS, 20)
    assert 0.015 <= P.haversine_km(a, b) <= 0.03


@pytest.mark.parametrize("seed", [f"o{i}" for i in range(20)])
def test_speed_and_start(seed: str) -> None:
    assert 18 <= P.speed_kmh(seed) <= 25
    assert P.speed_kmh(seed) == P.speed_kmh(seed)
    assert 0.95 <= P.haversine_km(KITCHEN, P.rider_start(KITCHEN, seed)) <= 1.85


def test_trip_takes_city_minutes() -> None:
    path = P.Path.between(KITCHEN, HOME, "o")  # ~3.8 km apart
    assert 9 <= path.minutes(P.SPEED_KMH[1]) <= path.minutes(P.SPEED_KMH[0]) <= 22


def test_heading_points_the_way() -> None:
    assert P.bearing_deg((0, 0), (1, 0)) == pytest.approx(0)
    assert P.bearing_deg((0, 0), (0, 1)) == pytest.approx(90)
    assert P.haversine_km((0, 0), P.offset((0, 0), 2, 45)) == pytest.approx(2, rel=0.01)


# ── the guard ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("app_env", ["local", "development", "dev", "qa", "QA"])
def test_on_in_dev_and_qa_with_the_flag(app_env: str) -> None:
    assert R.enabled("1", app_env, {})[0]
    assert R.enabled(True, app_env, {"RAILWAY_ENVIRONMENT_NAME": "QA"})[0]


@pytest.mark.parametrize("flag", [None, "", "0", "false", "no", False])
def test_off_without_the_flag(flag) -> None:  # type: ignore[no-untyped-def]
    assert R.enabled(flag, "development", {}) == (False, "off (DEMO_RIDER_SIM is not set)")


@pytest.mark.parametrize(("app_env", "environ"), [
    ("production", {}), ("prod", {}), (" Production ", {}),
    ("qa", {"RAILWAY_ENVIRONMENT_NAME": "production"}), ("development", {"ENVIRONMENT": "production"}),
    ("dev", {"ENVIRONMENT": "PROD"}),
])
def test_refused_in_production_even_with_the_flag(app_env: str, environ: dict) -> None:
    on, why = R.enabled("1", app_env, environ)
    assert not on and why.startswith("refused") and "production" in why.lower()


@pytest.mark.parametrize("app_env", ["staging", "test", "", "preview"])
def test_refused_anywhere_else(app_env: str) -> None:
    on, why = R.enabled("1", app_env, {})
    assert not on and why.startswith("refused")


async def test_run_does_nothing_when_off(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Under test (APP_ENV=test) it returns at once: no database, no HTTP."""
    from app.demo_sim import runner

    monkeypatch.setattr(runner, "settings_enabled", lambda: (False, "off"))
    await runner.run()


def test_production_settings_refuse_the_flag(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from shared.config import ProductionConfigError, Settings

    for k, v in {"APP_ENV": "production", "PAYMENT_PROVIDER": "live", "PAYOUT_PROVIDER": "live", "OTP_FIXED_CODE": "",
                 "DELIVERY_PIN_FIXED": "", "DEMO_RIDER_SIM": "1"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ProductionConfigError, match="DEMO_RIDER_SIM"):
        Settings(_env_file=None)  # type: ignore[call-arg]


# ── which orders ────────────────────────────────────────────────────────────────

def order(**kw) -> R.DemoOrder:  # type: ignore[no-untyped-def]
    base = {"id": "o1", "status": "placed", "customer_email": "demo1.hyd@example.com", "driver_id": None,
            "restaurant_owner_id": "owner", "pickup": KITCHEN, "dropoff": HOME, "created_at": NOW - timedelta(minutes=1)}
    return R.DemoOrder(**{**base, **kw})


def test_demo_people_are_recognised() -> None:
    assert R.city_key("rider.sim.hyd.1@example.com") == "hyd"
    assert R.city_key("Rider.Sim.BOI.3@example.com") == "boi"
    for email in ("rider.demo.hyd@example.com",  # the demo rider people test with: never the simulator's
                  "rider1.hyd@example.com", "rider.sim.hyd@example.com", "rider.sim.hyd.1@gmail.com",
                  "x.rider.sim.hyd.1@example.com", ""):
        assert R.city_key(email) is None, email
    assert R.customer_email("boi") == "demo1.boi@example.com"
    assert R.is_demo_customer("demo3.hyd@example.com")
    for email in ("customer1.hyd@example.com", "regular01.hyd@example.com", "demo1.hyd@example.org",
                  "demo1.hyd@example.com.evil.io", None):
        assert not R.is_demo_customer(email)


def test_only_its_own_or_the_seeds_open_orders() -> None:
    assert R.is_sim_order(order(), {"o1"})
    assert R.is_sim_order(order(id="seeded", status="picked_up", seeded=True), set())
    assert not R.is_sim_order(order(id="by-a-person"), {"o1"}), "a tester's order with a demo account"
    assert not R.is_sim_order(order(customer_email="customer1.hyd@example.com"), {"o1"}), "never a real customer"
    assert not R.is_sim_order(order(customer_email="someone@gmail.com", seeded=True), set())
    for done in ("delivered", "cancelled"):
        assert not R.is_sim_order(order(status=done), {"o1"})


# ── what next ───────────────────────────────────────────────────────────────────

def test_the_kitchen_side() -> None:
    assert R.next_step(order(status="pending_payment"), RIDER, NOW) == "pay"
    assert R.next_step(order(status="pending_payment", created_at=NOW - timedelta(minutes=6)), RIDER, NOW) == "cancel"
    assert R.next_step(order(placed_at=NOW - timedelta(seconds=5)), RIDER, NOW) == "wait"
    assert R.next_step(order(placed_at=NOW - timedelta(seconds=30)), RIDER, NOW) == "accept"
    assert R.next_step(order(status="accepted"), RIDER, NOW) == "prepare"
    assert R.next_step(order(status="preparing", accepted_at=NOW - timedelta(minutes=1)), RIDER, NOW) == "wait"
    assert R.next_step(order(status="preparing", accepted_at=NOW - timedelta(minutes=5)), RIDER, NOW) == "almost_ready"
    assert R.next_step(order(status="almost_ready"), RIDER, NOW) == "find_rider"
    assert R.next_step(order(status="ready"), RIDER, NOW) == "find_rider"


def test_the_rider_side() -> None:
    o = order(status="almost_ready", driver_id=RIDER, assigned_at=NOW - timedelta(seconds=30))
    assert R.next_step(o, RIDER, NOW) == "to_kitchen"
    later = NOW + timedelta(minutes=R.to_kitchen(o).minutes(P.speed_kmh(o.id)) + 0.5)
    assert R.next_step(o, RIDER, later) == "ready", "the kitchen hands it over when the rider walks in"
    assert R.next_step(order(**{**o.__dict__, "status": "ready"}), RIDER, later) == "pick_up"
    o = order(status="picked_up", driver_id=RIDER, picked_up_at=NOW - timedelta(minutes=1))
    assert R.next_step(o, RIDER, NOW) == "to_home"
    (lat, lng), heading, speed = R.position(o, "to_home", NOW)
    assert 18 / 3.6 <= speed <= 25 / 3.6 and 0 <= heading < 360
    assert 0.2 < P.haversine_km(KITCHEN, (lat, lng)) < 0.5  # a minute out at 18-25 km/h
    done = NOW + timedelta(minutes=R.to_home(o).minutes(P.speed_kmh(o.id)))
    assert R.next_step(o, RIDER, done) == "deliver"


def test_someone_elses_rider() -> None:
    o = order(status="almost_ready", driver_id="a-person", accepted_at=NOW - timedelta(minutes=5))
    assert R.next_step(o, RIDER, NOW) == "wait"
    assert R.next_step(o, RIDER, NOW + timedelta(minutes=5)) == "ready"
    assert R.next_step(order(status="picked_up", driver_id="a-person"), RIDER, NOW) == "wait"


def test_a_new_order_after_a_pause() -> None:
    assert not R.should_create(1, None, None, NOW)
    assert R.should_create(0, None, None, NOW)
    assert not R.should_create(0, NOW - timedelta(minutes=1), None, NOW)
    assert R.should_create(0, NOW - timedelta(minutes=4), None, NOW)
    assert not R.should_create(0, None, NOW - timedelta(minutes=2), NOW), "no kitchen open: try again later"
    assert R.should_create(0, None, NOW - timedelta(minutes=11), NOW)


# ── the simulator's riders (Round 5, item 3) ────────────────────────────────────

def test_each_order_gets_a_free_pool_rider() -> None:
    pool = ["r1", "r2", "r3"]
    assert R.pick_rider(pool, set()) == "r1"
    assert R.pick_rider(pool, {"r1"}) == "r2", "the first one is on another order"
    assert R.pick_rider(pool, {"r1", "r3"}) == "r2"
    assert R.pick_rider(pool, set(pool)) is None, "all on orders: the next one waits"
    assert R.pick_rider([], set()) is None


def test_it_reads_only_its_own_riders() -> None:
    from app.demo_sim import runner

    sql = str(runner.RIDERS_SQL)
    assert "dispatch_pool = 'demo_sim'" in sql and "rider.sim.%@example.com" in sql
    assert "rider.demo" not in sql, "never the demo rider people test with"
    assert R.SIM_POOL == "demo_sim"


def test_reorders_come_from_every_city_that_takes_orders() -> None:
    """A beta city takes orders like a live one (Boise is beta): the demo customer's
    past orders there are ones to order again, so a demo order is always on its way."""
    from app.demo_sim import runner

    from core_api.modules.markets.service.rules import OPEN

    assert set(runner.OPEN_CITY_STATUSES) == set(OPEN)
    sql = str(runner.PAST_ORDERS_SQL)
    assert "ci.status IN (" + ", ".join(f"'{x}'" for x in sorted(OPEN)) + ")" in sql
