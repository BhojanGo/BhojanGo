import math
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.idempotency import check_idempotency, store_idempotency, validate_idempotency_key
from app.core.redis import get_redis
from app.db.base import get_db
from app.repositories.order import OrderRepository
from app.schemas.order import (
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
from app.services.order import OrderService

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = structlog.get_logger(__name__)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str, Depends(validate_idempotency_key)],
) -> OrderResponse:
    """Create a new order."""
    # Check idempotency
    redis = await get_redis()
    cached = await check_idempotency(redis, "order", idempotency_key)
    if cached:
        return cached

    currency = "INR" if current_user.country == "IN" else "USD"
    order = await OrderService(db).create_order(data, current_user.id, currency)

    # Store for idempotency
    response = OrderResponse.model_validate(order)
    await store_idempotency(redis, "order", idempotency_key, response.model_dump())
    return response


@router.get("", response_model=OrderListResponse)
async def list_my_orders(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> OrderListResponse:
    """Get all orders for a restaurant (restaurant owner / admin)."""
    if current_user.role not in ("restaurant_owner", "admin", "super_admin"):
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PainPointMetrics:
    """Aggregate pain-point analytics (admin / city-manager only)."""
    if current_user.role not in ("admin", "super_admin", "city_manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    metrics = await OrderRepository(db).pain_point_metrics()
    return PainPointMetrics(**metrics)


@router.get("/driver/active", response_model=OrderResponse)
async def get_driver_active_order(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    # Customers can only view their own orders
    if current_user.role == "customer" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return OrderResponse.model_validate(order)


@router.get("/{order_id}/breakdown", response_model=FeeBreakdown)
async def get_order_breakdown(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FeeBreakdown:
    """Customer-facing fee transparency breakdown for an order."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if current_user.role == "customer" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderTimelineResponse:
    """Detailed order status timeline for customer transparency."""
    repo = OrderRepository(db)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if current_user.role == "customer" and order.customer_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    """Update order status (restaurant/driver/admin only, enforces state machine)."""
    updated = await OrderService(db).update_status(order_id, data, current_user.id, current_user.role)
    return OrderResponse.model_validate(updated)


@router.patch("/{order_id}/cancel", response_model=OrderResponse)
@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: uuid.UUID,
    data: OrderCancelRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrderResponse:
    updated = await OrderService(db).cancel_order(order_id, data, current_user.id, current_user.role)
    return OrderResponse.model_validate(updated)
