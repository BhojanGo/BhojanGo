"""The demo rider simulator's decisions (app/demo_sim), with no I/O: when it may
run at all, which orders are its own, and what to do next for each.

It runs only with DEMO_RIDER_SIM=1 and APP_ENV local, development, dev or qa,
and never where anything says production. It touches only orders of the demo
seed's customers (tools/seed/demo_data.py: demo<N>.<city>@example.com; the
example.com domain is reserved, so no real person has one) that the simulator
placed itself or the demo seed wrote (its payments carry {"demo": true}); a
person testing with a demo account keeps their own orders.

It rides only its own riders (rider.sim.<city>.<n>@example.com, users.dispatch_pool
"demo_sim"), never the demo rider people test with (rider.demo.<city>), and realtime
offers its orders to those riders only (dispatch.same_pool).
"""
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.demo_sim.path import Path, Point, rider_start, speed_kmh

ALLOWED_ENVS = frozenset({"local", "development", "dev", "qa"})
PRODUCTION = frozenset({"production", "prod"})  # shared/config.py PRODUCTION_NAMES
DEMO_CUSTOMER = re.compile(r"^demo\d+\.([a-z0-9-]+)@example\.com$")
SIM_RIDER = re.compile(r"^rider\.sim\.([a-z0-9-]+)\.(\d+)@example\.com$")  # the simulator's own riders
SIM_POOL = "demo_sim"  # their users.dispatch_pool (tools/seed/demo_data.py SIM_POOL)
ACTIVE = frozenset({"pending_payment", "placed", "accepted", "preparing", "almost_ready", "ready", "picked_up"})

# The kitchen and the rider at a believable pace (and well inside the business rules'
# timeouts: accept within 3 minutes, unpaid orders cancel after 10).
ACCEPT_AFTER = timedelta(seconds=25)
ALMOST_READY_AFTER = timedelta(minutes=4)     # from accepted: dispatch starts looking for a rider
READY_WITHOUT_OUR_RIDER = timedelta(minutes=9)  # from accepted, when another rider took it
UNPAID_GIVE_UP = timedelta(minutes=5)
NEXT_ORDER_AFTER = timedelta(minutes=3)       # after the last one was delivered
RETRY_CREATE_AFTER = timedelta(minutes=10)    # no kitchen could take an order (closed hours)


def enabled(flag: str | bool | None, app_env: str, environ: Mapping[str, str]) -> tuple[bool, str]:
    """(on, why): DEMO_RIDER_SIM must say yes, APP_ENV must be local/dev/qa, and
    nothing (APP_ENV, ENVIRONMENT, RAILWAY_ENVIRONMENT_NAME) may say production."""
    names = {"APP_ENV": app_env, **{v: environ.get(v, "") for v in ("ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME")}}
    for var, value in names.items():
        if (value or "").strip().lower() in PRODUCTION:
            return False, f"refused: {var}={value!r} (the demo rider never runs in production)"
    on = flag if isinstance(flag, bool) else str(flag or "").strip().lower() in ("1", "true", "yes", "on")
    if not on:
        return False, "off (DEMO_RIDER_SIM is not set)"
    if (app_env or "").strip().lower() not in ALLOWED_ENVS:
        return False, f"refused: APP_ENV={app_env!r} (only {', '.join(sorted(ALLOWED_ENVS))})"
    return True, "on"


def city_key(rider_email: str) -> str | None:
    """The demo city one of the simulator's riders rides in (rider.sim.<key>.<n>@example.com),
    else None: the demo rider people test with (rider.demo.<key>) is never the simulator's."""
    m = SIM_RIDER.match((rider_email or "").lower())
    return m.group(1) if m else None


def pick_rider(pool: list[str], busy: set[str]) -> str | None:
    """The simulator's rider for an order that needs one: the first of the city's pool
    who isn't carrying or waiting for another of its orders; None if all of them are."""
    return next((r for r in pool if r not in busy), None)


def customer_email(key: str) -> str:
    """The demo customer whose order is on its way (the demo seed's ACTIVE customer)."""
    return f"demo1.{key}@example.com"


def is_demo_customer(email: str | None) -> bool:
    return bool(DEMO_CUSTOMER.match((email or "").lower()))


@dataclass(frozen=True)
class DemoOrder:
    """An order as the simulator reads it (worker database, read only)."""

    id: str
    status: str
    customer_email: str
    driver_id: str | None
    restaurant_owner_id: str | None
    pickup: Point
    dropoff: Point
    created_at: datetime
    placed_at: datetime | None = None
    accepted_at: datetime | None = None
    assigned_at: datetime | None = None
    picked_up_at: datetime | None = None
    seeded: bool = False  # written by the demo seed (its payment says {"demo": true})


def is_sim_order(o: DemoOrder, ours: set[str]) -> bool:
    """One the simulator may drive: a demo customer's, still open, and placed by the
    simulator (``ours``) or written by the demo seed. Anything else is a person's."""
    return is_demo_customer(o.customer_email) and o.status in ACTIVE and (o.id in ours or o.seeded)


def to_kitchen(o: DemoOrder) -> Path:
    return Path.between(rider_start(o.pickup, o.id), o.pickup, f"{o.id}/to-kitchen")


def to_home(o: DemoOrder) -> Path:
    return Path.between(o.pickup, o.dropoff, f"{o.id}/to-home")


def _since(t: datetime | None, now: datetime) -> float:
    return (now - t).total_seconds() if t else 0.0


def next_step(o: DemoOrder, rider_id: str, now: datetime) -> str:
    """What happens next, from the order as it is now (so a restart picks up where it was):
    pay, cancel, accept, prepare, almost_ready, find_rider, to_kitchen, ready, pick_up,
    to_home, deliver or wait."""
    ours = o.driver_id == rider_id
    accepted = o.accepted_at or o.placed_at or o.created_at
    if o.status == "pending_payment":
        return "cancel" if now - o.created_at > UNPAID_GIVE_UP else "pay"
    if o.status == "placed":
        return "accept" if now - (o.placed_at or o.created_at) >= ACCEPT_AFTER else "wait"
    if o.status == "accepted":
        return "prepare"
    if o.status in ("preparing", "almost_ready", "ready") and o.driver_id is None:
        if o.status == "preparing":
            return "almost_ready" if now - accepted >= ALMOST_READY_AFTER else "wait"
        return "find_rider"
    if o.status in ("preparing", "almost_ready", "ready"):
        if not ours:  # another rider took it: the kitchen still finishes the food
            return "ready" if o.status != "ready" and now - accepted >= READY_WITHOUT_OUR_RIDER else "wait"
        _, _, there = to_kitchen(o).ride(_since(o.assigned_at, now), speed_kmh(o.id))
        if not there:
            return "to_kitchen"
        return "pick_up" if o.status == "ready" else "ready"
    if o.status == "picked_up" and ours:
        _, _, there = to_home(o).ride(_since(o.picked_up_at, now), speed_kmh(o.id))
        return "deliver" if there else "to_home"
    return "wait"


def position(o: DemoOrder, step: str, now: datetime) -> tuple[Point, float, float]:
    """(where, heading, speed m/s) of the rider for a riding step."""
    speed = speed_kmh(o.id)
    path, since = (to_kitchen(o), o.assigned_at) if step == "to_kitchen" else (to_home(o), o.picked_up_at)
    point, heading, _ = path.ride(_since(since, now), speed)
    return point, heading, round(speed / 3.6, 2)


def should_create(open_orders: int, last_delivered: datetime | None, last_attempt: datetime | None,
                  now: datetime) -> bool:
    """A new order on its way when the city has none, a short pause after the last
    delivery, and not more often than every 10 minutes when no kitchen could take one."""
    if open_orders:
        return False
    if last_delivered and now - last_delivered < NEXT_ORDER_AFTER:
        return False
    return not (last_attempt and now - last_attempt < RETRY_CREATE_AFTER)


# -- the watchdog ----------------------------------------------------------------
# An order that stays on one step too long (the rider never got the offer, a sign-in
# keeps failing, realtime lost track of the rider) is first recovered: the rider goes
# online again (realtime frees a rider stuck on an order that is over), everyone signs
# in afresh and the step is retried. If it is still stuck after another bound, it is
# cancelled through the normal API (by the kitchen, or the customer before payment)
# and the next order starts.
STALL_AFTER = timedelta(minutes=15)
RIDING_STALL_AFTER = timedelta(minutes=45)  # riding steps take as long as the ride
RIDING = frozenset({"to_kitchen", "to_home"})


@dataclass(frozen=True)
class Watch:
    step: str
    since: datetime
    recoveries: int = 0


def watch(prev: Watch | None, step: str, now: datetime) -> tuple[Watch, str]:
    """(the order's watch, verdict): "new" (it moved on to this step), "same",
    "stalled" (recover now) or "give_up" (cancel it)."""
    if prev is None or prev.step != step:
        return Watch(step, now), "new"
    if now - prev.since < (RIDING_STALL_AFTER if step in RIDING else STALL_AFTER):
        return prev, "same"
    if prev.recoveries == 0:
        return Watch(step, now, 1), "stalled"
    return Watch(step, now, prev.recoveries + 1), "give_up"


def cancel_as(status: str) -> str | None:
    """Who may cancel an order in this state through the normal API (state_machine.py):
    the kitchen until it's ready, the customer before payment; nobody after (admin only)."""
    if status in ("placed", "accepted", "preparing", "almost_ready"):
        return "kitchen"
    if status == "pending_payment":
        return "customer"
    return None
