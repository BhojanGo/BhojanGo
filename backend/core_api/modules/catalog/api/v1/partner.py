"""The partner tablet (P19): pause orders, "busy, add 10 min", today's numbers,
offers the restaurant funds (with a weekly cap) and the partner application.
The restaurant's owner, or an admin with partners.edit for its city."""
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.catalog.models.menu import MenuItem
from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service import access, ratings
from core_api.modules.catalog.service.applications import business_done
from core_api.modules.catalog.service.menu import busy_minutes, paused_by_kitchen
from shared.db import get_db

router = APIRouter(prefix="/restaurants", tags=["Partner tablet"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]

BUSY_FOR = timedelta(hours=1)


class PauseIn(BaseModel):
    paused: bool
    minutes: int | None = Field(default=None, ge=5, le=24 * 60, description="None = until you resume")


class BusyIn(BaseModel):
    extra_minutes: int = Field(ge=0, le=60, description="0 = not busy any more")


class StateOut(BaseModel):
    restaurant_id: str
    name: str
    area: str | None
    currency: str
    status: str
    open_now: bool
    reason: str | None
    paused: bool
    paused_until: datetime | None
    busy_extra_minutes: int
    busy_until: datetime | None
    prep_minutes: int
    today_orders: int
    today_sales: Decimal
    closes_at: str | None
    # The kitchen's city time zone (IANA): paused_until, busy_until and its orders' times are shown in it.
    time_zone: str | None = None


async def _state(db: AsyncSession, r: Restaurant) -> StateOut:
    from core_api.modules.catalog.service.menu import availability
    from core_api.modules.orders.models.order import Order

    now = datetime.now(UTC)
    a = await availability(db, r.id, now)
    tz = a.local_time.tzinfo
    start = datetime.combine(a.local_time.date(), datetime.min.time(), tzinfo=tz).astimezone(UTC)
    n, sales = (await db.execute(select(func.count(Order.id), func.coalesce(func.sum(Order.subtotal), 0)).where(
        Order.restaurant_id == r.id, Order.created_at >= start,
        Order.status.not_in(("pending_payment", "cancelled"))))).one()
    from core_api.modules.catalog.service import hours as H
    from core_api.modules.catalog.service.menu import _hours  # weekly hours, for "Open till"

    weekly, overrides = await _hours(db, r.id)
    closes = H.closes_at(a.local_time, weekly, overrides)
    return StateOut(
        restaurant_id=str(r.id), name=r.name, area=(r.address or {}).get("landmark") or r.city, currency=r.currency,
        status=r.status, open_now=a.open_now, reason=a.reason, paused=paused_by_kitchen(r, now),
        paused_until=r.paused_until if paused_by_kitchen(r, now) else None,
        busy_extra_minutes=busy_minutes(r, now), busy_until=r.busy_until if busy_minutes(r, now) else None,
        prep_minutes=r.avg_prep_minutes + busy_minutes(r, now), today_orders=n, today_sales=Decimal(sales),
        # r.closes_at is the legacy "HH:MM" string, used when the hours give no end (open all day, or closed now).
        closes_at=closes.strftime("%H:%M") if closes else (r.closes_at or None), time_zone=a.timezone,
    )


class MineOut(BaseModel):
    id: str
    name: str
    status: str
    currency: str
    city: str | None
    # R20: the kitchen's country (Markets code): BhojanGo Kitchen offers its languages.
    country: str


@router.get("/mine", response_model=list[MineOut])
async def mine(user: User, db: DB) -> list[MineOut]:
    """The partner's own restaurants, live or still applying (the tablet picks the first)."""
    rows = (await db.execute(select(Restaurant).where(Restaurant.owner_id == user.id, Restaurant.deleted_at.is_(None))
                             .order_by(Restaurant.created_at))).scalars()
    return [MineOut(id=str(r.id), name=r.name, status=r.status, currency=r.currency, city=r.city,
                    country=r.country) for r in rows]


@router.get("/{restaurant_id}/today", response_model=StateOut)
async def today(restaurant_id: uuid.UUID, user: User, db: DB) -> StateOut:
    """The tablet's header: open or paused, busy, prep time, today's orders and sales."""
    return await _state(db, await access.manage(db, user, restaurant_id))


@router.get("/{restaurant_id}/ratings/summary", response_model=ratings.RatingSummary)
async def rating_summary(restaurant_id: uuid.UUID, user: User, db: DB) -> ratings.RatingSummary:
    """The dashboard's ratings: "New" until 5 ratings (as customers see it), the
    average and count, how many gave each star, and the latest comments (no names)."""
    return await ratings.summary(db, await access.manage(db, user, restaurant_id, "partners.view"))


@router.put("/{restaurant_id}/pause", response_model=StateOut)
async def pause(restaurant_id: uuid.UUID, data: PauseIn, user: User, db: DB) -> StateOut:
    """Stop new orders for a while (customers see "Paused by the restaurant"); orders
    already placed carry on. Resumes by itself after ``minutes``."""
    r = await access.manage(db, user, restaurant_id)
    r.is_open = not data.paused
    r.paused_until = datetime.now(UTC) + timedelta(minutes=data.minutes) if data.paused and data.minutes else None
    await db.flush()
    return await _state(db, r)


@router.put("/{restaurant_id}/busy", response_model=StateOut)
async def busy(restaurant_id: uuid.UUID, data: BusyIn, user: User, db: DB) -> StateOut:
    """Kitchen slammed: new orders quote this many extra prep minutes for the next hour."""
    r = await access.manage(db, user, restaurant_id)
    r.busy_extra_minutes = data.extra_minutes
    r.busy_until = datetime.now(UTC) + BUSY_FOR if data.extra_minutes else None
    await db.flush()
    return await _state(db, r)


# ── offers the restaurant funds ──────────────────────────────────────────────

class OfferIn(BaseModel):
    template: Literal["free_delivery", "percent_off", "flat_off"]
    name: str = Field(min_length=2, max_length=60, examples=["Free delivery"])
    percent: Decimal | None = Field(default=None, gt=0, le=60)
    max_discount: Decimal | None = Field(default=None, gt=0)
    amount: Decimal | None = Field(default=None, gt=0)
    min_subtotal: Decimal = Field(default=Decimal("0"), ge=0)
    weekly_cap: Decimal = Field(gt=0, description="Stops for the week when this much has gone on the offer")


class OfferOut(BaseModel):
    id: str
    name: str
    template: str
    params: dict
    live: bool
    weekly_cap: Decimal | None
    used_this_week: Decimal
    orders_this_week: int
    paused: bool = False  # B4: paused by BhojanGo
    paused_reason: str | None = None


async def _offers(db: AsyncSession, r: Restaurant) -> list[OfferOut]:
    from core_api.modules.pricing.models import PromotionSpendWeek
    from core_api.modules.pricing.service.quotes import week_of
    from core_api.modules.catalog.service.menu import availability
    from core_api.modules.rules.models import Rule

    week = week_of((await availability(db, r.id)).local_time)
    now = datetime.now(UTC)
    rows = (await db.execute(select(Rule).where(
        Rule.family == "promotion", Rule.scope_level == "restaurant", Rule.scope_id == str(r.id),
        Rule.status == "published").order_by(Rule.created_at.desc()))).scalars().all()
    rows = [x for x in rows if x.params.get("funded_by") == "restaurant" and (x.effective_to is None or x.effective_to > now)]
    spend = {w.rule_key: w for w in (await db.execute(select(PromotionSpendWeek).where(
        PromotionSpendWeek.week_start == week, PromotionSpendWeek.rule_key.in_([x.rule_key for x in rows])))).scalars()} if rows else {}
    out = []
    for x in rows:
        s = spend.get(x.rule_key)
        cap = Decimal(str(x.params["weekly_cap"])) if x.params.get("weekly_cap") is not None else None
        used = Decimal(s.spent) if s else Decimal(0)
        out.append(OfferOut(id=str(x.id), name=x.name or x.template, template=x.template, params=x.params,
                            live=x.paused_at is None and x.effective_from <= now and (cap is None or used < cap), weekly_cap=cap,
                            used_this_week=used, orders_this_week=s.orders if s else 0,
                            paused=x.paused_at is not None, paused_reason=x.paused_reason))
    return out


@router.get("/{restaurant_id}/offers", response_model=list[OfferOut])
async def offers(restaurant_id: uuid.UUID, user: User, db: DB) -> list[OfferOut]:
    """Offers this restaurant pays for, with what they've cost this week."""
    return await _offers(db, await access.manage(db, user, restaurant_id))


@router.post("/{restaurant_id}/offers", response_model=list[OfferOut], status_code=status.HTTP_201_CREATED)
async def create_offer(restaurant_id: uuid.UUID, data: OfferIn, user: User, db: DB) -> list[OfferOut]:
    """Start an offer the restaurant funds. It comes off the weekly payout (itemised on
    the statement) and stops for the week at the cap. Live at once: the restaurant
    pays for it, so there's no platform approval."""
    from core_api.modules.rules.service.rules import RuleError, RuleService

    r = await access.manage(db, user, restaurant_id)
    params: dict = {"funded_by": "restaurant", "min_subtotal": str(data.min_subtotal), "weekly_cap": str(data.weekly_cap)}
    if data.template == "percent_off":
        if data.percent is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "OFFER", "message": "Give the percent off"})
        params |= {"percent": str(data.percent), **({"max_discount": str(data.max_discount)} if data.max_discount else {})}
    elif data.template == "flat_off":
        if data.amount is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "OFFER", "message": "Give the amount off"})
        params |= {"amount": str(data.amount)}
    # R22 security review (S11): within the most its market lets a kitchen give (Markets setting kitchen_offer_ceiling).
    from core_api.modules.markets.service import offer_ceiling

    try:
        running = sum((o.weekly_cap or Decimal(0)) for o in await _offers(db, r))  # its other offers, paused ones too
        params = offer_ceiling.apply(data.template, params, await offer_ceiling.for_restaurant(db, r), r.currency, running)
    except offer_ceiling.OfferOverCeiling as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "OFFER_OVER_CEILING", "message": str(e)})
    svc = RuleService(db)
    try:
        rule = await svc.create(user.id, family="promotion", template=data.template, params=params, scope_level="restaurant",
                                scope_id=str(r.id), key=f"r{uuid.uuid4().hex[:12]}", name=data.name)
        await svc._publish(user.id, rule, "partner_offer_started")  # noqa: SLF001
    except RuleError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "OFFER", "message": str(e)})
    await db.flush()
    return await _offers(db, r)


@router.post("/{restaurant_id}/offers/{offer_id}/end", response_model=list[OfferOut])
async def end_offer(restaurant_id: uuid.UUID, offer_id: uuid.UUID, user: User, db: DB) -> list[OfferOut]:
    from core_api.modules.rules.models import Rule
    from core_api.modules.rules.service.rules import RuleError, RuleService

    r = await access.manage(db, user, restaurant_id)
    rule = await db.get(Rule, offer_id)
    if rule is None or rule.scope_level != "restaurant" or rule.scope_id != str(r.id) or rule.family != "promotion":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Offer not found")
    try:
        await RuleService(db).end(user.id, offer_id)
    except RuleError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "OFFER", "message": str(e)})
    await db.flush()
    return await _offers(db, r)


# ── the partner application ──────────────────────────────────────────────────

class StepOut(BaseModel):
    key: Literal["business", "fssai", "gst_bank", "menu", "go_live"]
    title: str
    done: bool
    detail: str


class ApplicationOut(BaseModel):
    restaurant_id: str
    fssai_number: str | None
    fssai_expires_on: str | None
    fssai_document: bool
    fssai_document_key: str | None = None  # for the admins who check it (GET /uploads/view)
    gstin: str | None
    payout_account: str | None  # its status: pending | active | restricted
    name: str
    area: str | None
    status: str
    done: int
    total: int
    current: str | None
    commission_percent: Decimal | None
    steps: list[StepOut]
    # The business details as saved (the website pre-fills the step with them)
    street: str | None = None
    zip: str | None = None
    city: str | None = None
    country: str | None = None
    cuisines: list[str] = []


class BusinessIn(BaseModel):
    """The application's first step: where the kitchen is and what it cooks."""

    street: str = Field(min_length=3, max_length=200)
    area: str = Field(min_length=2, max_length=80, description="Neighbourhood, e.g. Banjara Hills")
    zip: str = Field(min_length=3, max_length=12, description="PIN or ZIP code")
    cuisines: list[str] = Field(min_length=1, max_length=5)
    lat: float | None = Field(default=None, ge=-90, le=90, description="The kitchen's pin; None keeps the current one")
    lng: float | None = Field(default=None, ge=-180, le=180)


class GstIn(BaseModel):
    gstin: str = Field(pattern=r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", description="15-character GSTIN")


async def _application(db: AsyncSession, r: Restaurant) -> ApplicationOut:
    from core_api.modules.finance.models import PayoutAccount

    items = (await db.execute(select(func.count(MenuItem.id)).where(MenuItem.restaurant_id == r.id))).scalar() or 0
    bank = (await db.execute(select(PayoutAccount).where(
        PayoutAccount.payee_type == "restaurant", PayoutAccount.payee_id == r.id))).scalars().first()
    india = r.country == "IN"
    steps = [
        StepOut(key="business", title="Business details", done=business_done(r),
                detail="Name, address and pin on the map"),
        StepOut(key="fssai", title="FSSAI licence" if india else "Food permit", done=bool(r.fssai_number) or not india,
                detail="14-digit licence and expiry date" if india else "Not needed in your city"),
        StepOut(key="gst_bank", title="GST and bank" if india else "Tax and bank",
                done=bool(bank) and (bool(r.gstin) or not india),
                detail="GSTIN and where we send your weekly payout" if india else "Where we send your weekly payout"),
        StepOut(key="menu", title="Menu and photos", done=items >= 5, detail=f"{items} of at least 5 dishes"),
        StepOut(key="go_live", title="Tablet and go live", done=r.status == "active",
                detail="We check everything and switch you on" if r.status != "active" else "Live"),
    ]
    done = sum(1 for s in steps if s.done)
    current = next((s.key for s in steps if not s.done), None)
    # R15: the commission the kitchen will pay comes from the commission rules (its own, its city's,
    # its country's), never from the old per-restaurant column.
    from core_api.modules.rules.api.v1.commission import _city_code, _ctx_for_city
    from core_api.modules.rules.service import templates as rule_templates
    from core_api.modules.rules.service.rules import RuleService

    rate = (await RuleService(db).resolve(_ctx_for_city(await _city_code(db, r), str(r.id)))).get("commission:rate")
    commission_percent = (rule_templates.commission_percent(rate.template, rate.params, r.tier).quantize(Decimal("0.1"))
                          if rate else None)
    return ApplicationOut(restaurant_id=str(r.id), fssai_number=r.fssai_number,
                          fssai_expires_on=r.fssai_expires_on.isoformat() if r.fssai_expires_on else None,
                          fssai_document=bool(r.fssai_document_key), fssai_document_key=r.fssai_document_key, gstin=r.gstin, payout_account=bank.status if bank else None, name=r.name, area=(r.address or {}).get("landmark") or r.city, status=r.status,
                          done=done, total=len(steps), current=current,
                          commission_percent=commission_percent,
                          steps=steps, street=(r.address or {}).get("street"), zip=(r.address or {}).get("zip"),
                          city=r.city, country=r.country, cuisines=list(r.cuisine_types or []))


@router.get("/{restaurant_id}/application", response_model=ApplicationOut)
async def application(restaurant_id: uuid.UUID, user: User, db: DB) -> ApplicationOut:
    """Where the partner application is: the five steps and what's left."""
    return await _application(db, await access.manage(db, user, restaurant_id))


@router.put("/{restaurant_id}/business", response_model=ApplicationOut)
async def set_business(restaurant_id: uuid.UUID, data: BusinessIn, user: User, db: DB) -> ApplicationOut:
    """Business details while applying: the street address, area, PIN/ZIP, cuisines
    and (optionally) the map pin. A live kitchen changes its address through support."""
    r = await access.manage(db, user, restaurant_id)
    if r.status != "pending_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "NOT_APPLYING", "message": "Your kitchen is already approved. Ask support to change its address."})
    lat = r.lat if data.lat is None or data.lng is None else data.lat
    lng = r.lng if data.lat is None or data.lng is None else data.lng
    r.address = {**(r.address or {}), "street": data.street.strip(), "landmark": data.area.strip(), "zip": data.zip.strip(),
                 "lat": lat, "lng": lng}
    r.lat, r.lng = lat, lng
    r.cuisine_types = [c.strip() for c in data.cuisines if c.strip()][:5]
    await db.flush()
    return await _application(db, r)


@router.put("/{restaurant_id}/gst", response_model=ApplicationOut)
async def set_gst(restaurant_id: uuid.UUID, data: GstIn, user: User, db: DB) -> ApplicationOut:
    r = await access.manage(db, user, restaurant_id)
    r.gstin = data.gstin
    await db.flush()
    return await _application(db, r)
