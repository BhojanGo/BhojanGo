"""Internal order endpoints for realtime (P14) and the worker's review simulator (R20).
Not for apps: every request must be signed with INTERNAL_SERVICE_SECRET (shared/internal_auth.py)."""
import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order
from core_api.modules.orders.service import review_sim
from core_api.modules.orders.service.order import OrderService
from shared import internal_auth
from shared.contracts import DispatchInfo
from shared.db import get_db

router = APIRouter(prefix="/internal/orders", tags=["Internal"], include_in_schema=False)
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
logger = structlog.get_logger(__name__)


async def signed(request: Request) -> None:
    try:
        internal_auth.verify(request.method, request.url.path, await request.body(),
                             request.headers.get("x-internal-timestamp"), request.headers.get("x-internal-signature"))
    except internal_auth.InternalAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Internal endpoint")


class AssignRider(BaseModel):
    rider_id: uuid.UUID
    batch_id: uuid.UUID | None = None  # set when the rider took several orders as one batch
    batch_position: int | None = Field(default=None, ge=1, le=3)  # 1 = the first drop-off


async def dispatch_info(db: AsyncSession, order: Order) -> dict:
    from core_api.modules.orders.service.order import business_rules  # noqa: F401  (rules module import)
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    city = order.market_city or ""
    rules = await RuleService(db).resolve(Context(country=city[:2] or None, region=city[:5] or None, city=city or None,
                                                  zone_id=str(order.zone_id) if order.zone_id else None))
    timeout = rules.get("business:dispatch_offer_timeout")
    exclusion, late = rules.get("business:dispatch_offer_exclusion"), rules.get("business:no_partner_alert")
    base_rule, bonus_rule = rules.get("rider_pay:base_distance_wait"), rules.get("rider_pay:batch_bonus")
    batching = rules.get("business:batching")
    from core_api.modules.catalog.models.restaurant import Restaurant

    rest = await db.get(Restaurant, order.restaurant_id)
    offer = await offer_details(db, order)
    flat_pay = offer.pop("pay_is_delivery_fee", False)
    return {**offer,
        "restaurant_owner_id": str(rest.owner_id) if rest and rest.owner_id else None,
        "order_id": str(order.id), "status": order.status, "customer_id": str(order.customer_id),
        "restaurant_id": str(order.restaurant_id), "restaurant_name": order.restaurant_name,
        "driver_id": str(order.driver_id) if order.driver_id else None, "market_city": order.market_city,
        "pickup": [order.pickup_lat, order.pickup_lng] if order.pickup_lat is not None else None,
        "dropoff": [order.delivery_lat, order.delivery_lng] if order.delivery_lat is not None else None,
        "offer_timeout_seconds": int(timeout.params["seconds"]) if timeout else 30,
        "offer_exclusion_seconds": int(exclusion.params["seconds"]) if exclusion else 120,
        "no_partner_alert_minutes": int(late.params["minutes"]) if late else 8,
        "distance_unit": "mi" if city.startswith("US") else "km",
        "batching_live": bool(batching and batching.params.get("live")),
        **(batch_rate(offer.get("rider_pay"), None, None) if flat_pay
           else batch_rate(offer.get("rider_pay"), base_rule, bonus_rule)),
    }


def batch_rate(rider_pay: str | None, base_rule, bonus_rule) -> dict:  # type: ignore[no-untyped-def]
    """Item 2: as a later drop-off of a batch, an order pays its rider pay without the base,
    plus the city's batch bonus. The offer card shows it as "Drop-off 2 · batch rate"."""
    from decimal import Decimal

    if rider_pay is None:
        return {"rider_pay_batched": None}
    base = Decimal(str(base_rule.params.get("base", 0))) if base_rule else Decimal(0)
    bonus = Decimal(str(bonus_rule.params.get("per_extra_order", 0))) if bonus_rule else Decimal(0)
    return {"rider_pay_batched": str(max(Decimal(0), Decimal(rider_pay) - base) + bonus)}


def drop_area(address: dict | None) -> str | None:
    """Roughly where the drop-off is, for the offer (the address comes after pickup)."""
    a = address or {}
    if a.get("landmark"):
        return str(a["landmark"])
    parts = [p.strip() for p in str(a.get("street") or "").split(",") if p.strip()]
    return parts[-1] if len(parts) > 1 else a.get("city")


async def offer_details(db: AsyncSession, order: Order) -> dict:
    """What the rider sees on an offer (P18): guaranteed pay including the tip,
    bags, when the food is ready and roughly where it goes."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from core_api.modules.pricing.models import OrderPricingSnapshot

    snap = (await db.execute(select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id == order.id))).scalars().first()
    pay = (snap.split or {}).get("rider") if snap else None
    detail = ((snap.split or {}).get("detail") or {}) if snap else {}
    # R30: the partner's pay is the delivery fee + tip, the same whether or not the order is batched
    flat = detail.get("delivery_fee_to_partner") is not None and "rider_top_up" not in detail
    ready_in = None
    if order.status == "ready":
        ready_in = 0
    elif order.restaurant_accepted_at and order.estimated_prep_minutes:
        due = order.restaurant_accepted_at + timedelta(minutes=order.estimated_prep_minutes)
        ready_in = max(0, round((due - datetime.now(UTC)).total_seconds() / 60))
    items = sum(int(i.get("quantity", 1)) for i in (order.items or []))
    return {"code": "#" + str(order.id).replace("-", "")[:6].upper(), "currency": order.currency,
            "rider_pay": str(pay) if pay is not None else None, "tip": str(order.tip),
            "items_count": items, "bags": max(1, (items + 3) // 4), "ready_in_minutes": ready_in,
            "drop_area": drop_area(order.delivery_address), "pay_is_delivery_fee": flat}


@router.get("/{order_id}/dispatch", dependencies=[Depends(signed)], response_model=DispatchInfo)
async def get_dispatch(order_id: uuid.UUID, db: DB) -> dict:
    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await dispatch_info(db, order)


@router.post("/{order_id}/assign-rider", dependencies=[Depends(signed)], response_model=DispatchInfo)
async def assign_rider(order_id: uuid.UUID, data: AssignRider, db: DB) -> dict:
    order = await OrderService(db).assign_rider(order_id, data.rider_id, data.batch_id, data.batch_position)
    return await dispatch_info(db, order)


class NoPartner(BaseModel):
    """R28: realtime's word on an order still without a delivery partner (business:no_partner_alert)."""

    firing: bool  # true: still none after the city's minutes; false: one accepted, or the order ended
    waited_minutes: int = Field(default=0, ge=0, le=1440)
    # The later arrival time realtime worked out (kitchen to home from now, plus time to find a partner).
    eta: datetime | None = None


def no_partner_fingerprint(order_id: uuid.UUID) -> str:
    return f"no-partner-{order_id}"


@router.post("/{order_id}/no-partner", dependencies=[Depends(signed)], response_model=DispatchInfo)
async def no_partner(order_id: uuid.UUID, data: NoPartner, db: DB) -> dict:
    """R28: an order with no delivery partner after the city's minutes is an alert in admin Operations
    (its city), and its estimated delivery moves to the later time the customer is told; once a
    partner accepts or the order ends, the alert is resolved. Answers the order's dispatch info, as every
    /internal/orders route does (the realtime contract)."""
    from datetime import UTC

    from sqlalchemy import update
    from sqlalchemy.dialects.postgresql import insert

    from core_api.modules.support.models import OpsAlert

    order = await db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    now = datetime.now(UTC)
    fp = no_partner_fingerprint(order_id)
    if not data.firing:
        await db.execute(update(OpsAlert).where(OpsAlert.fingerprint == fp, OpsAlert.status == "firing")
                         .values(status="resolved", ends_at=now, updated_at=now))
        await db.commit()
        return await dispatch_info(db, order)
    code = "#" + str(order.id).replace("-", "")[:6].upper()
    values = {"name": "OrderWithoutPartner", "status": "firing", "severity": "warning", "city": order.market_city,
              "summary": f"Order {code} has no delivery partner after {data.waited_minutes} min",
              "description": f"{order.restaurant_name}: still looking for a delivery partner. The customer was told "
                             "and given a later arrival time.",
              "starts_at": now, "ends_at": None, "updated_at": now}
    await db.execute(insert(OpsAlert).values(fingerprint=fp, **values)
                     .on_conflict_do_update(index_elements=["fingerprint"], set_=values))
    if data.eta and (order.estimated_delivery_time is None or data.eta > order.estimated_delivery_time):
        order.estimated_delivery_time = data.eta
    await db.commit()
    logger.warning("order_without_partner", order_id=str(order_id), city=order.market_city, waited_minutes=data.waited_minutes)
    return await dispatch_info(db, order)


class ReviewStep(BaseModel):
    step: review_sim.Step


# The worker's review simulator (R20): its own prefix (the /internal/orders routes are realtime's contract).
review_router = APIRouter(prefix="/internal/review", tags=["Internal"], include_in_schema=False)


@review_router.post("/orders/{order_id}/step", dependencies=[Depends(signed)])
async def review_step(order_id: uuid.UUID, data: ReviewStep, db: DB) -> dict:
    """R20: the worker's review simulator moves an app store review order one step (the
    review kitchen accepts, cooks, hands over; the review delivery partner is assigned,
    picks up, delivers). 404 for any order that isn't a review order (orders.service.review_sim)."""
    order = await review_sim.step(db, order_id, data.step)
    return {"order_id": str(order.id), "status": order.status,
            "driver_id": str(order.driver_id) if order.driver_id else None}
