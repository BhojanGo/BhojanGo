import math
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from core_api.modules.orders.api.idempotency import check_idempotency, store_idempotency, validate_idempotency_key
from shared import authz
from shared.redis import get_redis
from shared.db import get_db
from core_api.modules.orders.repository.order import OrderRepository
from core_api.modules.orders.schemas.order import (
    FeeBreakdown,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderListResponse,
    OrderResponse,
    OrderStatusUpdateRequest,
    OrderTimelineResponse,
    PainPointMetrics,
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
) -> OrderListResponse:
    """Get authenticated customer's order history."""
    repo = OrderRepository(db)
    orders, total = await repo.list_by_customer(current_user.id, page=page, limit=limit)
    return OrderListResponse(
        items=[OrderResponse.model_validate(o) for o in orders],
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
        items=[OrderResponse.model_validate(o) for o in orders],
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
    return OrderResponse.model_validate(order)


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
    return OrderResponse.model_validate(order)


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
