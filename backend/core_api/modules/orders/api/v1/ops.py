"""Operations for the admin console (P21): the overview of every country, state
and city you can see, and the orders list behind Operations and Support.

Everything is cut to the caller's scopes: a city admin sees their city, a
country manager their country, a super admin everything. Money stays in each
country's currency; "today" is each city's local day.
"""
import statistics
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/ops", tags=["Operations"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("orders.view"))]

ACTIVE = ("placed", "accepted", "preparing", "almost_ready", "ready", "picked_up")
WAITING_FOR_RIDER = ("almost_ready", "ready")
LATE_AFTER = timedelta(minutes=5)
MIN_FOR_MEDIAN = 5  # fewer completed deliveries than this: no median ("—")
RIDER_WAIT_ALERT = timedelta(minutes=5)


class OpsTotals(BaseModel):
    live: int = 0
    today: int = 0
    gmv_today: Decimal = Decimal(0)
    median_delivery_min: float | None = None
    on_time_pct: float | None = None
    completed_pct: float | None = None
    refund_pct: float | None = None
    waiting_for_rider: int = 0
    late: int = 0
    kitchens: int = 0


class OpsCity(BaseModel):
    code: str
    name: str
    status: str
    timezone: str
    totals: OpsTotals


class OpsState(BaseModel):
    code: str
    name: str
    totals: OpsTotals
    cities: list[OpsCity]


class OpsAction(BaseModel):
    kind: Literal["rule_approval", "kitchen_application", "rider_documents", "waiting_for_rider", "late_orders"]
    label: str
    detail: str
    count: int
    scope: str
    urgent: bool = False


class OpsCountry(BaseModel):
    code: str
    name: str
    currency: str
    timezone: str
    tax: str
    payments: str
    totals: OpsTotals
    states: list[OpsState]
    needs_action: list[OpsAction]


class OpsOverview(BaseModel):
    scope: str
    generated_at: datetime
    countries: list[OpsCountry]


async def _visible_cities(db: AsyncSession, admin: AdminContext, scope: str, permission: str = "orders.view"):  # type: ignore[no-untyped-def]
    """(city, region, country) rows under ``scope`` that the admin may see."""
    from core_api.modules.markets.models import City, Country, Region

    rows = (await db.execute(select(City, Region, Country).join(Region, Region.id == City.region_id)
                             .join(Country, Country.id == City.country_id).order_by(Country.code, Region.name, City.name))).all()
    out = [(c, r, k) for c, r, k in rows if authz.covers(scope, c.code) and admin.can(permission, c.code)]
    if not out and not any(admin.can(permission, x) for x in (scope,)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN_SCOPE", "message": f"You can't see {scope}"})
    return out


def _tz(city, region, country) -> ZoneInfo:  # type: ignore[no-untyped-def]
    return ZoneInfo(city.timezone or region.timezone or country.timezone)


def _totals(orders: list, refunds: dict, start_utc: datetime, now: datetime) -> OpsTotals:  # type: ignore[type-arg]
    t = OpsTotals()
    today = [o for o in orders if o.created_at >= start_utc and o.status != "pending_payment"]
    t.live = sum(1 for o in orders if o.status in ACTIVE)
    t.today = len(today)
    t.gmv_today = sum((Decimal(o.total) for o in today if o.status != "cancelled"), Decimal(0))
    delivered = [o for o in today if o.status == "delivered" and o.actual_delivery_time and o.placed_at]
    # Median delivery time: completed orders only, and only once there are enough of them.
    if len(delivered) >= MIN_FOR_MEDIAN:
        t.median_delivery_min = round(statistics.median((o.actual_delivery_time - o.placed_at).total_seconds() / 60 for o in delivered), 1)
    # On time: delivered within 5 min of the time the customer was given. Orders still on
    # their way and already past it count as late, so a bad evening shows at once.
    timed = [o for o in delivered if o.estimated_delivery_time]
    running_late = [o for o in today if o.status in ACTIVE and o.estimated_delivery_time and now > o.estimated_delivery_time + LATE_AFTER]
    if timed or running_late:
        on_time = sum(1 for o in timed if o.actual_delivery_time <= o.estimated_delivery_time + LATE_AFTER)
        t.on_time_pct = round(100 * on_time / (len(timed) + len(running_late)), 1)
    if delivered:
        t.refund_pct = round(100 * sum(1 for o in delivered if refunds.get(o.id)) / len(delivered), 1)
    finished = [o for o in today if o.status in ("delivered", "cancelled")]
    if finished:
        t.completed_pct = round(100 * sum(1 for o in finished if o.status == "delivered") / len(finished), 1)
    t.waiting_for_rider = sum(1 for o in orders if o.status in WAITING_FOR_RIDER and o.driver_id is None)
    t.late = sum(1 for o in orders if o.status in ACTIVE and o.estimated_delivery_time and now > o.estimated_delivery_time + LATE_AFTER)
    return t


def _sum(parts: list[OpsTotals], orders: list, refunds: dict, start: datetime, now: datetime) -> OpsTotals:  # type: ignore[type-arg]
    t = _totals(orders, refunds, start, now)
    t.kitchens = sum(p.kitchens for p in parts)
    return t


@router.get("/overview", response_model=OpsOverview)
async def overview(admin: Viewer, db: DB, scope: str = Query("*", pattern=r"^(\*|[A-Z]{2}(-[A-Z0-9]{1,3}(-[A-Z0-9]{2,5})?)?)$")) -> OpsOverview:
    """Live orders, today's orders and money, delivery times and what needs
    someone's attention, for each country, state and city in ``scope``."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.models.rider import RiderDocument
    from core_api.modules.identity.models.user import User
    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import Refund
    from core_api.modules.rules.models import Rule

    now = datetime.now(UTC)
    cities = await _visible_cities(db, admin, scope)
    codes = [c.code for c, _, _ in cities]
    orders = (await db.execute(select(Order).where(Order.market_city.in_(codes), Order.created_at >= now - timedelta(hours=40)))
              ).scalars().all() if codes else []
    ids = [o.id for o in orders]
    refunds = {r for (r,) in (await db.execute(select(Refund.order_id).where(Refund.order_id.in_(ids))))} if ids else set()
    rmap = {i: True for i in refunds}
    kitchens: dict[str, int] = defaultdict(int)
    for name, n in (await db.execute(select(Restaurant.city, Restaurant.id).where(
            Restaurant.status == "active", Restaurant.deleted_at.is_(None)))).all():
        kitchens[name] += 1
    by_city: dict[str, list] = defaultdict(list)  # type: ignore[type-arg]
    for o in orders:
        by_city[o.market_city].append(o)

    countries: dict[str, dict] = {}
    for c, r, k in cities:
        tz = _tz(c, r, k)
        start = datetime.combine(now.astimezone(tz).date(), datetime.min.time(), tzinfo=tz).astimezone(UTC)
        ct = _totals(by_city[c.code], rmap, start, now)
        ct.kitchens = kitchens.get(c.name, 0)
        entry = countries.setdefault(k.code, {"k": k, "start": start, "states": {}})
        st = entry["states"].setdefault(r.code, {"r": r, "cities": [], "orders": []})
        st["cities"].append(OpsCity(code=c.code, name=c.name, status=c.status, timezone=str(tz), totals=ct))
        st["orders"] += by_city[c.code]

    out: list[OpsCountry] = []
    for code, e in countries.items():
        k = e["k"]
        states = []
        all_orders: list = []  # type: ignore[type-arg]
        for st in e["states"].values():
            states.append(OpsState(code=st["r"].code, name=st["r"].name, cities=st["cities"],
                                   totals=_sum([x.totals for x in st["cities"]], st["orders"], rmap, e["start"], now)))
            all_orders += st["orders"]
        totals = _sum([s.totals for s in states], all_orders, rmap, e["start"], now)
        visible = [cc.code for s in states for cc in s.cities]

        actions: list[OpsAction] = []
        if admin.can("rules.approve", code) or any(admin.can("rules.approve", x) for x in visible):
            pending = (await db.execute(select(Rule).where(Rule.status == "pending_approval"))).scalars().all()
            mine = [x for x in pending if (x.market_scope or "*") != "*" and authz.covers(scope if scope != "*" else code, x.market_scope)
                    and admin.can("rules.approve", x.market_scope)]
            if mine:
                actions.append(OpsAction(kind="rule_approval", count=len(mine), scope=code,
                                      label=f"{len(mine)} rule{'s' if len(mine) > 1 else ''} waiting for approval",
                                      detail=", ".join(sorted({f"{x.name or x.template} · {x.market_scope}" for x in mine}))[:200]))
        apps = (await db.execute(select(Restaurant).where(Restaurant.status == "pending_approval", Restaurant.country == code,
                                                          Restaurant.deleted_at.is_(None)))).scalars().all()
        city_by_name = {cc.name: cc.code for s in states for cc in s.cities}
        apps = [a for a in apps if a.city in city_by_name and admin.can("partners.edit", city_by_name[a.city])]
        if apps:
            actions.append(OpsAction(kind="kitchen_application", count=len(apps), scope=code,
                                  label=f"{len(apps)} kitchen{'s' if len(apps) > 1 else ''} applying to join",
                                  detail=", ".join(f"{a.name} · {a.city}" for a in apps)[:200]))
        if admin.can("riders.edit", code):
            docs = (await db.execute(select(RiderDocument).join(User, User.id == RiderDocument.rider_id).where(
                RiderDocument.status == "submitted", User.country == code))).scalars().all()
            if docs:
                actions.append(OpsAction(kind="rider_documents", count=len(docs), scope=code,
                                      label=f"{len(docs)} rider document{'s' if len(docs) > 1 else ''} to check",
                                      detail="Licences, insurance and background checks waiting for review"))
        waiting = [o for o in all_orders if o.status in WAITING_FOR_RIDER and o.driver_id is None
                   and (o.actual_ready_at or o.updated_at) and now - (o.actual_ready_at or o.updated_at) > RIDER_WAIT_ALERT]
        if waiting:
            actions.append(OpsAction(kind="waiting_for_rider", count=len(waiting), scope=code, urgent=True,
                                  label=f"{len(waiting)} order{'s' if len(waiting) > 1 else ''} waiting for a rider",
                                  detail=", ".join(sorted({o.market_city for o in waiting}))))
        if totals.late:
            actions.append(OpsAction(kind="late_orders", count=totals.late, scope=code, urgent=True,
                                  label=f"{totals.late} order{'s' if totals.late > 1 else ''} running late",
                                  detail="Past the time the customer was given"))
        out.append(OpsCountry(code=code, name=k.name, currency=k.currency, timezone=k.timezone,
                              tax="GST" if code == "IN" else "Sales tax", payments="Razorpay" if code == "IN" else "Stripe",
                              totals=totals, states=states, needs_action=actions))
    return OpsOverview(scope=scope, generated_at=now, countries=out)


# ── the orders list (Operations, Support) ────────────────────────────────────

class OpsOrder(BaseModel):
    id: str
    code: str
    status: str
    restaurant_name: str
    market_city: str | None
    customer: str
    rider: str | None
    total: Decimal
    currency: str
    placed_at: datetime | None
    estimated_delivery_time: datetime | None
    minutes_late: int | None
    waiting_for_rider_min: int | None
    flags: list[str]
    pickup: list[float] | None = None


def search_terms(q: str) -> tuple[str, bool, bool]:
    """How a search box entry is read: (term, by order code, by phone).

    An order code is the first hex digits of its id (#A9D1F0), and some codes are
    all digits (#418292), so a number of 6+ digits is tried both as the end of a
    customer's phone and as a code. A leading # means a code only."""
    raw = q.strip()
    term = raw.lstrip("#").lower().replace("-", "")
    if raw.startswith("#"):
        return term, True, False
    if term.isdigit() and len(term) >= 6:
        return term, len(term) <= 32, True
    return term, True, False


@router.get("/orders", response_model=list[OpsOrder])
async def orders(admin: Viewer, db: DB, scope: str = Query("*", pattern=r"^(\*|[A-Z]{2}(-[A-Z0-9]{1,3}(-[A-Z0-9]{2,5})?)?)$"),
                 view: Literal["live", "attention", "today", "search"] = "live", q: str | None = Query(None, max_length=40),
                 limit: int = Query(100, ge=1, le=300)) -> list[OpsOrder]:
    """Orders in your scope: live ones, the ones that need attention (late,
    waiting for a rider, kitchen not answering), today's, or a search by order
    code (#A9D1) or the customer's phone."""
    from core_api.modules.identity.models.user import User
    from core_api.modules.orders.models.order import Order

    now = datetime.now(UTC)
    codes = [c.code for c, _, _ in await _visible_cities(db, admin, scope)]
    if not codes:
        return []
    stmt = select(Order).where(Order.market_city.in_(codes))
    if view == "search":
        if not q:
            return []
        from sqlalchemy import String, cast, func, or_

        term, by_code, by_phone = search_terms(q)
        match = []
        if by_code:
            match.append(func.replace(cast(Order.id, String), "-", "").like(f"{term}%"))
        if by_phone:
            users = [u for (u,) in (await db.execute(select(User.id).where(User.phone.like(f"%{term}")))).all()]
            if users:
                match.append(Order.customer_id.in_(users))
        stmt = stmt.where(or_(*match)) if match else stmt.where(Order.id == uuid.UUID(int=0))
        stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
    elif view == "today":
        stmt = stmt.where(Order.created_at >= now - timedelta(hours=24), Order.status != "pending_payment").order_by(Order.created_at.desc()).limit(limit)
    else:
        stmt = stmt.where(Order.status.in_(ACTIVE)).order_by(Order.created_at).limit(500)
    rows = (await db.execute(stmt)).scalars().all()
    names: dict[uuid.UUID, str] = {}
    ids = {o.customer_id for o in rows} | {o.driver_id for o in rows if o.driver_id}
    if ids:
        for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars():
            parts = (u.full_name or "").split()
            names[u.id] = f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else (parts[0] if parts else "")
    out = []
    for o in rows:
        flags = []
        late = int((now - o.estimated_delivery_time).total_seconds() // 60) if o.status in ACTIVE and o.estimated_delivery_time and now > o.estimated_delivery_time else None
        if late is not None and late >= 5:
            flags.append("late")
        waiting = None
        if o.status in WAITING_FOR_RIDER and o.driver_id is None:
            waiting = int((now - (o.actual_ready_at or o.updated_at)).total_seconds() // 60)
            flags.append("waiting_for_rider")
        if o.status == "placed" and o.accept_due_at and now > o.accept_due_at - timedelta(seconds=60):
            flags.append("kitchen_not_answering")
        if view == "attention" and not flags:
            continue
        out.append(OpsOrder(id=str(o.id), code="#" + o.id.hex[:6].upper(), status=o.status, restaurant_name=o.restaurant_name,
                            market_city=o.market_city, customer=names.get(o.customer_id, "Customer"),
                            rider=names.get(o.driver_id) if o.driver_id else None, total=Decimal(o.total), currency=o.currency,
                            placed_at=o.placed_at, estimated_delivery_time=o.estimated_delivery_time, minutes_late=late,
                            waiting_for_rider_min=waiting, flags=flags,
                            pickup=[o.pickup_lat, o.pickup_lng] if o.pickup_lat is not None else None))
    return out[:limit]
