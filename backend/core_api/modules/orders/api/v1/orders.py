import math
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from core_api.modules.orders.api.idempotency import check_idempotency, store_idempotency, validate_idempotency_key
from shared import authz
from shared.redis import get_redis
from shared.db import get_db
from core_api.modules.orders.repository.order import OrderRepository
from core_api.modules.orders.schemas.order import (
    FeeBreakdown,
    HistoryStatus,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
    OrderTimelineResponse,
    PainPointMetrics,
    ReorderResponse,
    StatusTimelineEntry,
)
from core_api.modules.orders.service.order import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = structlog.get_logger(__name__)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    idempotency_key: Annotated[str, Depends(validate_idempotency_key)],
) -> OrderResponse:
    """Place an order from a quote (POST /pricing/quote). It waits for payment
    (pending_payment) until POST /payments/initiate and the payment webhook."""
    # Check idempotency
    redis = await get_redis()
    cached = await check_idempotency(redis, "order", idempotency_key)
    if cached:
        return cached

    order = await OrderService(db).create_order(data, current_user.id)

    # Store for idempotency
    response = OrderResponse.model_validate(order)
    await store_idempotency(redis, "order", idempotency_key, response.model_dump())
    return response


@router.get("", response_model=OrderListResponse)
async def list_my_orders(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, min_length=1, max_length=100, description="Kitchen or item name (any case), or the order code (#A9D1F0)"),
    status_filter: list[HistoryStatus] | None = Query(None, alias="status", description="delivered | cancelled | active; repeatable"),
    date_from: date | None = Query(None, alias="from", description="Placed on or after this day (UTC)"),
    date_to: date | None = Query(None, alias="to", description="Placed on or before this day (UTC)"),
    restaurant_id: uuid.UUID | None = Query(None),
) -> OrderListResponse:
    """Get authenticated customer's order history, newest first, with optional filters."""
    from core_api.modules.catalog.service.lookup import restaurant_slugs
    from core_api.modules.orders.service.history import items_summary, statuses_for

    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "BAD_DATES", "message": "'from' must be on or before 'to'"})
    repo = OrderRepository(db)
    orders, total = await repo.list_by_customer(
        current_user.id, page=page, limit=limit, q=q, statuses=statuses_for(status_filter),  # type: ignore[arg-type]
        created_from=datetime.combine(date_from, time.min, UTC) if date_from else None,
        created_before=datetime.combine(date_to + timedelta(days=1), time.min, UTC) if date_to else None,
        restaurant_id=restaurant_id,
    )
    slugs = await restaurant_slugs(db, {o.restaurant_id for o in orders})
    items = []
    for o in orders:
        out = OrderResponse.model_validate(o)
        out.restaurant_slug = slugs.get(o.restaurant_id)
        out.items_summary = items_summary(o.items)
        items.append(out)
    return OrderListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/restaurant/{restaurant_id}", response_model=OrderListResponse)
async def list_restaurant_orders(
    restaurant_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> OrderListResponse:
    """A restaurant's orders: its owner, or an admin with orders.view for its city."""
    if not await _can_see_restaurant(db, current_user, restaurant_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    repo = OrderRepository(db)
    orders, total = await repo.list_by_restaurant(restaurant_id, page=page, limit=limit)
    return OrderListResponse(
        items=[await _as_kitchen_sees_it(db, o) for o in orders],
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/admin/pain-points", response_model=PainPointMetrics)
async def admin_pain_point_metrics(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> PainPointMetrics:
    """Platform-wide pain-point analytics: admins who can see reports for the whole platform."""
    from shared import authz

    if not authz.can([authz.Assignment.parse(a) for a in current_user.admin], "reports.view", "*"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    metrics = await OrderRepository(db).pain_point_metrics()
    return PainPointMetrics(**metrics)


@router.get("/driver/active", response_model=OrderResponse)
async def get_driver_active_order(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> OrderResponse:
    """Get the driver's currently active order."""
    if current_user.role != "driver":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Driver access required")
    repo = OrderRepository(db)
    order = await repo.get_driver_active_order(current_user.id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active order")
    return await _as_rider_sees_it(db, order, OrderResponse.model_validate(order))


async def _as_kitchen_sees_it(db: AsyncSession, order) -> OrderResponse:  # type: ignore[no-untyped-def]
    """The customer's first name ("#A9F3 · Priya") and the rider's, for the tablet (P19)."""
    from core_api.modules.identity.models.user import User

    out = OrderResponse.model_validate(order)
    cust = await db.get(User, order.customer_id)
    out.customer = {"name": (cust.full_name or "").split(" ")[0] if cust else "Customer"}
    if order.driver_id:
        rider = await db.get(User, order.driver_id)
        if rider is not None:
            parts = (rider.full_name or "").split()
            out.rider = {"id": str(rider.id), "first_name": parts[0] if parts else "",
                         "name": f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else (parts[0] if parts else "")}
    return out


async def _as_rider_sees_it(db: AsyncSession, order, out: OrderResponse) -> OrderResponse:  # type: ignore[no-untyped-def]
    """The customer's first name and initial; the full address only after pickup (P18)."""
    from core_api.modules.identity.models.user import User
    from core_api.modules.orders.api.v1.internal import drop_area

    cust = await db.get(User, order.customer_id)
    parts = (cust.full_name if cust else "").split()
    out.customer = {"name": f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else (parts[0] if parts else "Customer")}
    if order.status not in ("picked_up", "delivered"):
        out.delivery_address = {"area": drop_area(order.delivery_address), "city": order.delivery_address.get("city")}
    return out


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> OrderResponse:
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if not await _can_see_order(db, current_user, order):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    out = OrderResponse.model_validate(order)
    if order.customer_id == current_user.id and order.status not in ("delivered", "cancelled"):
        out.pin = order.delivery_pin
    if order.driver_id is not None and order.driver_id == current_user.id:
        await _as_rider_sees_it(db, order, out)
    if order.driver_id:
        from core_api.modules.identity.models.user import User

        rider = await db.get(User, order.driver_id)
        if rider is not None:
            out.rider = {"id": str(rider.id), "first_name": (rider.full_name or "").split(" ")[0]}
    return out


@router.get("/{order_id}/breakdown", response_model=FeeBreakdown)
async def get_order_breakdown(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> FeeBreakdown:
    """Customer-facing fee transparency breakdown for an order."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not await _can_see_order(db, current_user, order):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return FeeBreakdown(
        food_subtotal=float(order.subtotal),
        delivery_fee=float(order.delivery_fee),
        platform_fee=float(order.platform_fee),
        restaurant_payout=float(order.restaurant_payout),
        tip=float(order.tip),
        taxes=float(order.taxes),
        discount=float(order.discount),
        total=float(order.total),
        currency=order.currency,
    )


@router.get("/{order_id}/timeline", response_model=OrderTimelineResponse)
async def get_order_timeline(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> OrderTimelineResponse:
    """Detailed order status timeline for customer transparency."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if not await _can_see_order(db, current_user, order):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    timeline = [StatusTimelineEntry(status=e.get("status", ""), at=e.get("at")) for e in (order.status_history or [])]
    return OrderTimelineResponse(
        order_id=order.id,
        status=order.status,
        estimated_prep_minutes=order.estimated_prep_minutes,
        restaurant_accepted_at=order.restaurant_accepted_at,
        actual_ready_at=order.actual_ready_at,
        timeline=timeline,
    )


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: uuid.UUID,
    data: OrderStatusUpdateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> OrderResponse:
    """Move an order on: the restaurant accepts and prepares, the rider picks up
    and delivers (each only on their own orders; see service/state_machine.py)."""
    updated = await OrderService(db).update_status(order_id, data, current_user)
    return OrderResponse.model_validate(updated)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: uuid.UUID,
    data: OrderCancelRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> OrderResponse:
    """Cancel: refunded in full if it was paid."""
    updated = await OrderService(db).cancel_order(order_id, data, current_user)
    return OrderResponse.model_validate(updated)


async def _own_order(db: AsyncSession, user: CurrentUser, order_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """The order, if the signed-in user placed it (404 otherwise, as for any order you can't see)."""
    order = await OrderRepository(db).get_by_id(order_id)
    if order is None or order.customer_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.post("/{order_id}/reorder", response_model=ReorderResponse)
async def reorder(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> ReorderResponse:
    """Order again: your past order's items at today's menu prices, ready for
    the bag. Sold-out or removed items are listed in ``unavailable`` and left
    out. Nothing is ordered: checkout quotes the bag as usual."""
    from core_api.modules.catalog.service.cart import reorder_lines
    from core_api.modules.catalog.service.lookup import restaurant_brief

    order = await _own_order(db, current_user, order_id)
    kitchen = await restaurant_brief(db, order.restaurant_id)
    if kitchen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This kitchen is no longer on BhojanGo")
    items, unavailable = await reorder_lines(db, order.restaurant_id, order.items or [])
    return ReorderResponse.model_validate({"restaurant": kitchen, "items": items, "unavailable": unavailable})


@router.get("/{order_id}/receipt.pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}, "description": "The receipt (India: tax invoice) as a PDF"}})
async def receipt_pdf(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Response:
    """Your receipt for a paid order: a tax invoice in India (GST, FSSAI), a
    receipt with sales tax in the US. Same lines as the fair bill."""
    from core_api.modules.catalog.service.lookup import restaurant_brief
    from core_api.modules.identity.service.profile import user_profile
    from core_api.modules.orders.service import receipt as rcpt
    from core_api.modules.orders.service.state_machine import PAID_STATES
    from core_api.modules.pricing.service.lookup import order_bills

    order = await _own_order(db, current_user, order_id)
    if order.status not in PAID_STATES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "NOT_PAID", "message": "A receipt is ready once the order is paid"})
    country = rcpt.country_of(order.market_city, order.currency)
    bill = (await order_bills(db, [order.id])).get(order.id)
    lines = bill["lines"] if bill else rcpt.fallback_lines(order.subtotal, order.delivery_fee, order.discount,
                                                           order.taxes, order.tip)
    profile = await user_profile(db, order.customer_id)
    doc = rcpt.Receipt(
        country=country, invoice_no=rcpt.invoice_number(order.id, order.created_at, country),
        issued_at=order.placed_at or order.created_at, order_code="#" + order.id.hex[:6].upper(),
        currency=order.currency, total=order.total,
        kitchen=await restaurant_brief(db, order.restaurant_id) or {"name": order.restaurant_name},
        customer_name=(profile or {}).get("name") or "Customer", delivery_address=order.delivery_address or {},
        items=order.items or [], lines=lines, payment_method=order.payment_method,
    )
    return Response(rcpt.render(doc), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{doc.invoice_no}.pdf"',
                             "Cache-Control": "private, no-store"})


async def _can_see_order(db: AsyncSession, user: CurrentUser, order) -> bool:  # type: ignore[no-untyped-def]
    """The customer, the restaurant's owner, the assigned rider, or an admin
    with orders.view for the order's city."""
    if order.customer_id == user.id or (order.driver_id is not None and order.driver_id == user.id):
        return True
    if order.market_city and authz.can([authz.Assignment.parse(a) for a in user.admin], "orders.view", order.market_city):
        return True
    return await _owns_restaurant(db, user, order.restaurant_id)


async def _owns_restaurant(db: AsyncSession, user: CurrentUser, restaurant_id: uuid.UUID) -> bool:
    if user.role != "restaurant_owner":
        return False
    from core_api.modules.catalog.models.restaurant import Restaurant

    r = await db.get(Restaurant, restaurant_id)
    return r is not None and r.owner_id == user.id


async def _can_see_restaurant(db: AsyncSession, user: CurrentUser, restaurant_id: uuid.UUID) -> bool:
    if await _owns_restaurant(db, user, restaurant_id):
        return True
    from core_api.modules.catalog.service.lookup import restaurant_city_code

    city = await restaurant_city_code(db, restaurant_id)
    return bool(city) and authz.can([authz.Assignment.parse(a) for a in user.admin], "orders.view", city)
