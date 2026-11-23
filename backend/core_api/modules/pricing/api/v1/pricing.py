"""Pricing API (P8): customer quotes and the admin price simulator."""
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.payments.api.dependencies import CurrentUser, get_current_user
from core_api.modules.pricing.schemas import QuoteOut, QuoteRequest, SimulateOut, SimulateRequest
from core_api.modules.pricing.service.lookup import relabel
from core_api.modules.pricing.service.quotes import QuoteError, QuoteService
from shared.db import get_db

router = APIRouter(prefix="/pricing", tags=["Pricing"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


def _unprocessable(e: Exception) -> HTTPException:
    """422 {code, message, ...details}: CANNOT_QUOTE, or MIN_ORDER with zone, amount and
    currency (the client formats and words it; ``message`` is English for older
    clients) and, for a customer quote, the city's ``tip_presets``."""
    code = getattr(e, "code", "CANNOT_QUOTE")
    details = getattr(e, "details", None) or {}
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={**details, "code": code, "message": str(e)})


# R21 security review (S7): quotes per signed-in person. A US quote asks Stripe Tax, so an
# unlimited loop would spend its rate limit (and money). A person re-quoting a bag never comes close.
def quote_limits() -> list[tuple[int, int]]:
    """(window seconds, quotes) pairs in force; 0 turns a limit off, never in production."""
    from shared.config import get_settings

    s = get_settings()
    pairs = [(60, s.QUOTE_LIMIT_PER_MINUTE), (86400, s.QUOTE_LIMIT_PER_DAY)]
    production = s.is_production or s.production_named
    return [(w, n if n > 0 else default) for (w, n), default in zip(pairs, (60, 2000)) if n > 0 or production]


async def _quote_wait(user_id: uuid.UUID) -> int:
    """0 if this person may quote now (and the quote is counted), else the seconds to wait."""
    from shared.redis import get_redis

    limits = quote_limits()
    if not limits:
        return 0
    redis = await get_redis()
    keys = [f"rl:quote:{window}:{user_id}" for window, _ in limits]
    counts = await redis.mget(keys)
    for (window, limit), key, count in zip(limits, keys, counts):
        if count is not None and int(count) >= limit:
            return max(1, int(await redis.ttl(key) or window))
    for (window, _), key in zip(limits, keys):
        if await redis.incr(key) == 1:
            await redis.expire(key, window)
    return 0


@router.post("/quote", response_model=QuoteOut)
async def quote(data: QuoteRequest, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> QuoteOut:
    """Price a bag: every line of the bill, and a token valid for 10 minutes.
    Checkout charges exactly this total. 429 TOO_MANY_QUOTES (retry_after) past
    QUOTE_LIMIT_PER_MINUTE (60) or QUOTE_LIMIT_PER_DAY (2000) for one person."""
    wait = await _quote_wait(user.id)
    if wait:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, headers={"Retry-After": str(wait)}, detail={
            "code": "TOO_MANY_QUOTES", "message": f"Too many price checks. Try again in {wait} seconds.", "retry_after": wait})
    try:
        return await QuoteService(db).quote(user.id, data)
    except QuoteError as e:
        raise _unprocessable(e)


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: uuid.UUID, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> dict:
    """A quote you made, while it is valid (bill lines; no payout split)."""
    try:
        q = await QuoteService(db).get(user.id, quote_id)
    except QuoteError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "QUOTE_EXPIRED", "message": str(e)})
    return {k: q[k] for k in ("quote_id", "restaurant_id", "currency", "total", "lines", "tax_pending", "expires_at", "items")}


@router.get("/orders/{order_id}/bill")
async def order_bill(order_id: uuid.UUID, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> dict:
    """The fair bill of your order: every line, and each tax with its rate and
    what it was charged on. (Who gets what stays internal.)"""
    from core_api.modules.orders.service.lookup import order_customer

    if await order_customer(db, order_id) != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    snap = await QuoteService(db).snapshot(order_id)
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This order has no itemised bill")
    from core_api.modules.identity.service.profile import user_profile
    from core_api.modules.pricing.service.lookup import customer_lines

    lines = customer_lines(snap.lines, ((await user_profile(db, user.id)) or {}).get("locale"))
    taxes = [ln for ln in lines if ln["code"] in ("tax", "tax_included")]
    from core_api.modules.payments.service.lookup import order_refunds
    from shared.money import paid_after_refunds

    # R27: the receipt shows each refund ("Refunded $4.51 · missing item") and what was paid after them.
    refunds = (await order_refunds(db, [order_id])).get(order_id, [])
    refunded, paid = paid_after_refunds(snap.total, refunds)
    return {"order_id": str(order_id), "currency": snap.currency, "total": str(snap.total), "lines": lines,
            "taxes": taxes, "zone": snap.context.get("zone"), "distance": snap.context.get("distance"),
            "distance_unit": snap.context.get("distance_unit"),
            "refunds": [{k: r[k] for k in ("amount", "kind", "reason", "items", "created_at")} for r in refunds],
            "refunded": str(refunded), "paid": str(paid)}


@router.get("/orders/{order_id}/snapshot")
async def order_snapshot(
    order_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(require_permission("orders.view"))],
    db: DB,
) -> dict:
    """Admin: what an order was charged and why (lines, rule versions, split)."""
    snap = await QuoteService(db).snapshot(order_id)
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No pricing snapshot for this order")
    admin.require("orders.view", snap.context.get("city", "*"))
    return {
        "order_id": str(snap.order_id), "quote_id": str(snap.quote_id), "currency": snap.currency,
        "total": str(snap.total), "lines": relabel(snap.lines), "rule_versions": snap.rule_versions, "split": snap.split,
        "context": snap.context, "created_at": snap.created_at.isoformat(),
        "fee_settings": snap.fee_settings,  # R29: the fee settings in force at placement, and their source
    }


@router.post("/simulate", response_model=SimulateOut)
async def simulate(
    data: SimulateRequest,
    admin: Annotated[AdminContext, Depends(require_permission("pricing.simulate"))],
    db: DB,
) -> SimulateOut:
    """Price simulator: the same cart with live rules and with your drafts."""
    admin.require("pricing.simulate", data.city)
    try:
        return await QuoteService(db).simulate(data)
    except QuoteError as e:
        raise _unprocessable(e)


EXAMPLE_CARTS = {"IN": (Decimal("480"), Decimal("3.5"), Decimal("20")), "US": (Decimal("28"), Decimal("2.5"), Decimal("3"))}


@router.get("/example")
async def example_quote(db: DB, city: str = Query(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$"),
                        zone: uuid.UUID | None = Query(default=None)) -> dict:
    """An example bill for the website: a real recent order's bill in this zone (or
    city), as the customer saw it; a new city with no orders yet gets a typical cart
    from its own menus priced by the engine with live rules. With it, "shares": who
    gets the money, from the engine's split (see _shares). Cached for an hour. Public."""
    import json

    from shared.redis import get_redis

    r = await get_redis()
    key = f"pricing:example:v2:{city}:{zone or ''}"  # v2: with the shares
    cached = await r.get(key)
    if cached:
        return json.loads(cached)
    body = await _real_bill(db, city, zone) or await _typical_bill(db, city)
    await r.set(key, json.dumps(body), ex=3600)
    return body


def _shares(split: dict, total: Decimal | str) -> dict[str, str]:
    """Who gets the customer's money, from the engine's split of this bill: the kitchen
    (its payout), the rider (rider pay: base + distance + wait, plus the whole tip), the
    tax the platform remits, and BhojanGo (what is left: fees less rider pay and
    platform-funded offers; below zero when an order costs us money). The four add up
    to the total exactly. R29: the card fee is the kitchen's cost, paid out of its food money, so it counts in the
    kitchen's share (never as tax)."""
    total = Decimal(str(total))
    kitchen, rider, us = (Decimal(str(split[k])) for k in ("restaurant", "rider", "platform"))
    kitchen += Decimal(str(split.get("card_fee") or 0))
    return {"kitchen": str(kitchen), "rider": str(rider), "tax": str(total - kitchen - rider - us), "us": str(us)}


async def _real_bill(db: AsyncSession, city: str, zone: uuid.UUID | None) -> dict | None:
    """The newest bill of a paid order from the last 30 days (zone first, then city).
    Only the bill lines: nothing about the customer or the kitchen."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from core_api.modules.orders.models.order import Order
    from core_api.modules.pricing.models import OrderPricingSnapshot
    from core_api.modules.pricing.service.quotes import city_chain

    try:
        c, _, country, _ = await city_chain(db, city)
    except QuoteError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    since = datetime.now(UTC) - timedelta(days=30)
    for where in ([Order.zone_id == zone] if zone else []) + [Order.market_city == city]:
        snap = (await db.execute(
            select(OrderPricingSnapshot).join(Order, Order.id == OrderPricingSnapshot.order_id)
            .where(where, OrderPricingSnapshot.created_at >= since,
                   Order.status.notin_(("pending_payment", "cancelled", "payment_failed")),
                   Order.fulfillment == "delivery")  # R32: the example is a delivered order
            .order_by(OrderPricingSnapshot.created_at.desc()).limit(1))).scalar_one_or_none()
        if snap is not None:
            lines = relabel([{**ln, "label": "Food" if ln.get("code") == "food" else ln.get("label")} for ln in snap.lines])
            ctx = snap.context or {}
            return {"city": city, "city_name": c.name, "currency": snap.currency, "lines": lines, "total": str(snap.total),
                    "shares": _shares(snap.split, snap.total), "source": "order", "assumptions": {"distance": str(ctx.get("distance", "")),
                                                       "distance_unit": country.distance_unit}}
    return None


async def _typical_bill(db: AsyncSession, city: str) -> dict:
    """Two typical dishes from the city's own menus, 3 km (or mi) away, 8 pm local,
    the country's default tip: priced by the engine with the city's live rules."""
    from datetime import UTC, datetime, time
    from statistics import median

    from sqlalchemy import select

    from core_api.modules.catalog.models.menu import MenuItem
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.pricing.schemas import SimCart, SimulateRequest
    from core_api.modules.pricing.service.quotes import city_chain
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    try:
        c, region, country, tz = await city_chain(db, city)
    except QuoteError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    prices = (await db.execute(select(MenuItem.price).join(Restaurant, Restaurant.id == MenuItem.restaurant_id).where(
        Restaurant.country == country.code, Restaurant.city.ilike(c.name), Restaurant.status == "active"))).scalars().all()
    food = (Decimal(str(median(prices))) * 2).quantize(Decimal("1")) if prices else EXAMPLE_CARTS.get(country.code, EXAMPLE_CARTS["IN"])[0]
    local = datetime.combine(datetime.now(UTC).astimezone(tz).date(), time(20, 0))
    resolved = await RuleService(db).resolve(Context(country=country.code, region=region.code, city=c.code))
    from core_api.modules.pricing.service.summary import tip_presets

    presets = tip_presets(resolved)
    tip = presets.amounts[presets.default_index or 0] if presets else Decimal("0")
    try:
        out = await QuoteService(db).simulate(SimulateRequest(city=city, cart=SimCart(food_subtotal=food), distance=Decimal("3"),
                                                               local_time=local, tip=tip, restaurant_tier="B"))
    except QuoteError as e:
        raise _unprocessable(e)
    if not out.live.ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "NOT_PRICED", "message": out.live.message})
    lines = [{**ln.model_dump(mode="json"), "label": "Food" if ln.code == "food" else ln.label} for ln in out.live.lines]
    sp = out.live.split
    shares = (_shares({"restaurant": sp.restaurant, "rider": sp.rider, "platform": sp.platform, "card_fee": sp.card_fee},
                      out.live.total) if sp else None)
    return {"city": city, "city_name": c.name, "currency": out.currency, "lines": lines, "total": str(out.live.total),
            "shares": shares, "source": "typical", "assumptions": {"food": str(food), "distance": "3", "distance_unit": country.distance_unit,
                                                 "tip": str(tip), "local_time": local.isoformat()}}
