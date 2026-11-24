"""BhojanGo-funded offers in the admin console (R37): the monthly offer budgets and what an offer
costs against what the platform earns.

  * GET  /rules/offers/budgets?country=IN: the country, its states and its cities, each with its own
    budget (or none: it shares the level above's), the pool it spends from, and this month's spend.
  * PUT  /rules/offers/budgets/{level}/{code}: set a level's monthly budget, or null to share the
    level above's again. Money for offers BhojanGo pays for: rules.approve at that market.
  * GET  /rules/offers/{rule_id}/economics: for one offer, the most it can cost an order next to the
    platform fee BhojanGo earns on that order, a warning when the offer can cost more, and the budget
    pool it spends from (pricing/service/offer_budget.py).
"""
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.pricing.service import offer_budget
from core_api.modules.pricing.service.fees import from_cents, platform_fee_cents, to_cents
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleNotFound, RuleService
from shared.db import get_db

router = APIRouter(prefix="/rules/offers", tags=["Rules"])

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("rules.view"))]
Approver = Annotated[AdminContext, Depends(require_permission("rules.approve"))]
ZERO = Decimal("0")


class BudgetRow(BaseModel):
    level: Literal["country", "region", "city"]
    code: str
    name: str
    own: Decimal | None  # this level's own monthly budget; None: it shares its pool's
    pool: str  # the level it spends from (country:IN, region:IN-TG, city:IN-TG-HYD)
    pool_name: str
    monthly: Decimal  # the pool's monthly budget (0: BhojanGo-funded offers are off)
    spent: Decimal  # the pool's spend this month
    orders: int
    percent: int
    left: Decimal


class Budgets(BaseModel):
    country: str
    currency: str
    month: str  # 2026-11
    rows: list[BudgetRow]


class BudgetIn(BaseModel):
    monthly: Decimal | None


def _month(tz: str | None) -> datetime:
    return datetime.now(UTC).astimezone(ZoneInfo(tz or "UTC"))


@router.get("/budgets", response_model=Budgets)
async def budgets(admin: Viewer, db: DB, country: str = Query(pattern=r"^[A-Z]{2}$")) -> Budgets:
    from core_api.modules.markets.models import City, Country, Region

    admin.require("rules.view", country, within=True)
    c = (await db.execute(select(Country).where(Country.code == country))).scalars().first()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": f"Country {country} not found"})
    month = offer_budget.month_of(_month(c.timezone))
    regions = (await db.execute(select(Region).where(Region.country_id == c.id).order_by(Region.name))).scalars().all()
    cities = (await db.execute(select(City).where(City.country_id == c.id).order_by(City.name))).scalars().all()
    by_region = {r.id: r for r in regions}
    places: list[tuple[str, str, str, list]] = [("country", c.code, c.name, [("country", c.code, c.name, c.settings)])]
    for r in regions:
        places.append(("region", r.code, r.name, [("country", c.code, c.name, c.settings), ("region", r.code, r.name, r.settings)]))
        for ci in (x for x in cities if x.region_id == r.id):
            places.append(("city", ci.code, ci.name, [("country", c.code, c.name, c.settings), ("region", r.code, r.name, r.settings),
                                                      ("city", ci.code, ci.name, ci.settings)]))
    for ci in (x for x in cities if x.region_id not in by_region):
        places.append(("city", ci.code, ci.name, [("country", c.code, c.name, c.settings), ("city", ci.code, ci.name, ci.settings)]))
    rows = []
    for level, code, name, levels in places:
        pool = offer_budget.pool_for(levels, c.currency)
        used, orders = await offer_budget.spent(db, pool.key, month)
        rows.append(BudgetRow(
            level=level, code=code, name=name, own=offer_budget.parse((levels[-1][3] or {}).get(offer_budget.SETTING)),  # type: ignore[arg-type]
            pool=pool.key, pool_name=pool.name, monthly=pool.monthly, spent=used, orders=orders,
            percent=int(used * 100 / pool.monthly) if pool.monthly > 0 else (100 if used > 0 else 0),
            left=max(pool.monthly - used, ZERO)))
    return Budgets(country=c.code, currency=c.currency, month=month.isoformat()[:7], rows=rows)


@router.put("/budgets/{level}/{code}", response_model=Budgets)
async def set_budget(level: Literal["country", "region", "city"], code: str, data: BudgetIn, admin: Approver, db: DB) -> Budgets:
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.markets.service.rules import merge_settings

    admin.require("rules.approve", code)
    model = {"country": Country, "region": Region, "city": City}[level]
    row = (await db.execute(select(model).where(model.code == code))).scalars().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": f"{code} not found"})
    value = None if data.monthly is None else {"monthly": f"{data.monthly:f}"}
    try:
        offer_budget.check_settings({offer_budget.SETTING: value})
    except offer_budget.BudgetError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "INVALID_BUDGET", "message": str(e)})
    before = (row.settings or {}).get(offer_budget.SETTING)
    row.settings = merge_settings(row.settings, {offer_budget.SETTING: value})
    await db.flush()
    await audit.record(db, actor_id=admin.user.id, action="offer_budget.set", entity_type=level, entity_id=code, scope=code,
                       before={"monthly": (before or {}).get("monthly")}, after={"monthly": (value or {}).get("monthly")})
    return await budgets(admin, db, country=code[:2])


class Economics(BaseModel):
    rule_id: uuid.UUID
    name: str | None
    template: str
    funded_by: str
    currency: str
    order_food: Decimal  # the order (food subtotal) where the offer costs most against the platform fee
    cost_per_order: Decimal | None  # what the offer gives on that order (None: not known here)
    platform_fee: Decimal  # the platform fee BhojanGo earns on that order
    max_cost: Decimal | None  # the most it can give one order (None: no ceiling)
    warning: bool  # it can cost more than the platform fee earned
    pool: str | None  # BhojanGo-funded: the budget it spends from
    pool_name: str | None
    monthly: Decimal | None
    spent: Decimal | None
    left: Decimal | None
    running: bool  # BhojanGo-funded: the budget has room for it now


def offer_cost(template: str, params: dict, food: Decimal, delivery: Decimal | None) -> Decimal | None:
    """What the offer takes off an order of this much food."""
    if template in ("percent_off", "first_order"):
        v = food * Decimal(str(params["percent"])) / 100
        return min(v, Decimal(str(params["max_discount"]))) if params.get("max_discount") is not None else v
    if template in ("flat_off", "referral"):
        return min(Decimal(str(params["amount"])), food)
    if template == "free_delivery":
        return delivery
    return None


def platform_fee(food: Decimal, percent: Decimal | None, minimum: Decimal) -> Decimal:
    if percent is None:
        return ZERO
    return from_cents(platform_fee_cents(to_cents(food), percent, to_cents(minimum)))


def worst_case(template: str, params: dict, percent: Decimal | None, minimum: Decimal, delivery: Decimal | None
               ) -> tuple[Decimal, Decimal | None, Decimal]:
    """(food, offer cost, platform fee) at the order where the offer costs most against the fee.
    Both are piecewise linear in the food subtotal, so the gap is largest at a corner: the offer's
    minimum order, where its cap starts, where the fee's minimum stops, or a large order."""
    floor = max(Decimal(str(params.get("min_subtotal") or 0)), Decimal("1"))
    points = {floor, floor * 10, Decimal("1000")}
    if params.get("max_discount") is not None and params.get("percent"):
        points.add(Decimal(str(params["max_discount"])) * 100 / Decimal(str(params["percent"])))
    if params.get("amount") is not None:
        points.add(Decimal(str(params["amount"])))
    if percent:
        points.add(minimum * 100 / percent)
    best: tuple[Decimal, Decimal | None, Decimal] | None = None
    for f in sorted(p.quantize(Decimal("0.01")) for p in points if p >= floor):
        cost = offer_cost(template, params, f, delivery)
        fee = platform_fee(f, percent, minimum)
        if best is None or (cost is not None and (best[1] is None or cost - fee > best[1] - best[2])):
            best = (f, cost.quantize(Decimal("0.01")) if cost is not None else None, fee)
    assert best is not None
    return best


@router.get("/{rule_id}/economics", response_model=Economics)
async def economics(rule_id: uuid.UUID, admin: Viewer, db: DB) -> Economics:
    from core_api.modules.catalog.service.lookup import restaurant_city_code
    from core_api.modules.markets.models import City, Country, Region

    try:
        r = await RuleService(db).get(rule_id)
    except RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Rule not found"})
    admin.require("rules.view", r.market_scope)
    if r.family != "promotion":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NOT_AN_OFFER", "message": "Only offers have economics"})
    # where it applies: its city (a restaurant's: the restaurant's city), else its country
    city_code = r.scope_id if r.scope_level == "city" else (await restaurant_city_code(db, r.scope_id)
                                                               if r.scope_level == "restaurant" else None)
    city = (await db.execute(select(City).where(City.code == city_code))).scalars().first() if city_code else None
    if city is not None:
        country, region = await db.get(Country, city.country_id), await db.get(Region, city.region_id)
    else:
        country, region = (await db.execute(select(Country).where(Country.code == r.market_scope[:2]))).scalars().first(), None
    assert country is not None
    ctx = Context(country=country.code, region=region.code if region else None, city=city.code if city else None,
                  restaurant_id=r.scope_id if r.scope_level == "restaurant" else None)
    resolved = await RuleService(db).resolve(ctx, datetime.now(UTC))
    pf, mf = resolved.get("fee:platform_fee_pct"), resolved.get("fee:min_platform_fee")
    percent = Decimal(str(pf.params["percent"])) if pf else None
    minimum = Decimal(str(mf.params["amount"])) if mf else ZERO
    delivery = None
    dr = resolved.get("delivery_fee")
    if dr is not None:  # free delivery: the dearest delivery fee it can waive
        p = dr.params
        if dr.template == "distance_slabs":
            delivery = max(Decimal(str(s["fee"])) for s in p["slabs"])
        elif dr.template == "flat":
            delivery = Decimal(str(p["amount"]))
        elif dr.template == "tier_base":
            delivery = max(Decimal(str(v)) for v in p["tiers"].values())
    params = r.params
    food, cost, fee = worst_case(r.template, params, percent, minimum, delivery)
    max_cost = (Decimal(str(params["amount"])) if params.get("amount") is not None
                else Decimal(str(params["max_discount"])) if params.get("max_discount") is not None
                else delivery if r.template == "free_delivery" else None)
    out = Economics(rule_id=r.id, name=r.name, template=r.template, funded_by=params.get("funded_by", "platform"),
                    currency=country.currency, order_food=food, cost_per_order=cost, platform_fee=fee, max_cost=max_cost,
                    warning=cost is not None and cost > fee, pool=None, pool_name=None, monthly=None, spent=None, left=None,
                    running=True)
    if out.funded_by == "platform":
        levels = [("country", country.code, country.name, country.settings)]
        if region is not None:
            levels.append(("region", region.code, region.name, region.settings))
        if city is not None:
            levels.append(("city", city.code, city.name, city.settings))
        pool = offer_budget.pool_for(levels, country.currency)
        tz = (city.timezone if city else None) or (region.timezone if region else None) or country.timezone
        used, _ = await offer_budget.spent(db, pool.key, offer_budget.month_of(_month(tz)))
        left = max(pool.monthly - used, ZERO)
        out.pool, out.pool_name, out.monthly, out.spent, out.left = pool.key, pool.name, pool.monthly, used, left
        out.running = left > 0 and (max_cost is None or max_cost <= left) and r.paused_at is None
    return out
