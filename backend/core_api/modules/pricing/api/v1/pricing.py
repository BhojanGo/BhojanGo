"""Pricing API (P8): customer quotes and the admin price simulator."""
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.payments.api.dependencies import CurrentUser, get_current_user
from core_api.modules.pricing.schemas import QuoteOut, QuoteRequest, SimulateOut, SimulateRequest
from core_api.modules.pricing.service.quotes import QuoteError, QuoteService
from shared.db import get_db

router = APIRouter(prefix="/pricing", tags=["Pricing"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


def _unprocessable(e: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "CANNOT_QUOTE", "message": str(e)})


@router.post("/quote", response_model=QuoteOut)
async def quote(data: QuoteRequest, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> QuoteOut:
    """Price a bag: every line of the bill, and a token valid for 10 minutes.
    Checkout charges exactly this total."""
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
    lines = [{k: ln.get(k) for k in ("code", "label", "amount", "funded_by", "detail")} for ln in snap.lines]
    taxes = [ln for ln in lines if ln["code"] in ("tax", "tax_included")]
    return {"order_id": str(order_id), "currency": snap.currency, "total": str(snap.total), "lines": lines,
            "taxes": taxes, "zone": snap.context.get("zone"), "distance": snap.context.get("distance"),
            "distance_unit": snap.context.get("distance_unit")}


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
        "total": str(snap.total), "lines": snap.lines, "rule_versions": snap.rule_versions, "split": snap.split,
        "context": snap.context, "created_at": snap.created_at.isoformat(),
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
async def example_quote(db: DB, city: str = Query(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> dict:
    """An example bill for the web's home page, priced by the real engine with the
    city's live rules (a typical cart, today at 8 pm local), cached for an hour. Public."""
    import json
    from datetime import UTC, datetime, time

    from core_api.modules.pricing.schemas import SimCart, SimulateRequest
    from core_api.modules.pricing.service.quotes import city_chain
    from shared.redis import get_redis

    r = await get_redis()
    key = f"pricing:example:{city}"
    cached = await r.get(key)
    if cached:
        return json.loads(cached)
    try:
        c, _, country, tz = await city_chain(db, city)
    except QuoteError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    food, distance, tip = EXAMPLE_CARTS.get(country.code, EXAMPLE_CARTS["IN"])
    local = datetime.combine(datetime.now(UTC).astimezone(tz).date(), time(20, 0))
    try:
        out = await QuoteService(db).simulate(SimulateRequest(city=city, cart=SimCart(food_subtotal=food), distance=distance,
                                                               local_time=local, tip=tip, restaurant_tier="B"))
    except QuoteError as e:
        raise _unprocessable(e)
    if not out.live.ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "NOT_PRICED", "message": out.live.message})
    lines = [{**ln.model_dump(mode="json"), "label": "Food" if ln.code == "food" else ln.label} for ln in out.live.lines]
    body = {"city": city, "city_name": c.name, "currency": out.currency, "lines": lines, "total": str(out.live.total),
            "assumptions": {"food": str(food), "distance": str(distance), "distance_unit": country.distance_unit,
                            "tip": str(tip), "local_time": local.isoformat()}}
    await r.set(key, json.dumps(body), ex=3600)
    return body
