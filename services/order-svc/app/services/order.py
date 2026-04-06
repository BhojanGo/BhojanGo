import math
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.events import publish_order_event
from app.core.state_machine import TRANSITION_PERMISSIONS, can_transition, is_transition_allowed
from app.repositories.order import OrderRepository
from app.schemas.order import OrderCancelRequest, OrderCreateRequest, OrderStatusUpdateRequest

logger = structlog.get_logger(__name__)
settings = get_settings()

TAX_RATES = {"USD": 0.08, "INR": 0.18}  # 8% US, 18% India GST


class OrderService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = OrderRepository(db)

    async def create_order(self, data: OrderCreateRequest, customer_id: uuid.UUID, currency: str) -> dict:
        # Fetch restaurant info from restaurant-svc
        restaurant_name = "Unknown Restaurant"
        delivery_fee = 0.0
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.RESTAURANT_SVC_URL}/api/v1/restaurants/{data.restaurant_id}")
                if resp.status_code == 200:
                    r_data = resp.json()
                    restaurant_name = r_data.get("name", restaurant_name)
                    delivery_fee = r_data.get("delivery_fee", 0.0)
        except Exception as e:
            logger.warning("restaurant_fetch_failed", error=str(e))

        # Calculate totals
        subtotal = 0.0
        items_serialized = []
        for item in data.items:
            item_price = 0.0  # Would be fetched from restaurant-svc in production
            customization_total = sum(
                0.0  # Would fetch option prices
                for _ in item.customizations
            )
            item_total = (item_price + customization_total) * item.quantity
            subtotal += item_total
            items_serialized.append({
                "menu_item_id": str(item.menu_item_id),
                "quantity": item.quantity,
                "price": item_price,
                "customizations": [c.model_dump() for c in item.customizations],
                "subtotal": item_total,
            })

        # In real flow, item prices come from a validated cart snapshot
        # For now we use the provided items structure
        tax_rate = TAX_RATES.get(currency, 0.08)
        taxes = round(subtotal * tax_rate, 2)
        loyalty_discount = 0.0  # data.loyalty_points_to_use * 0.01 (1 point = $0.01)
        total = round(subtotal + delivery_fee + taxes + data.tip - loyalty_discount, 2)

        # Estimated delivery time
        estimated_delivery = datetime.now(UTC) + timedelta(minutes=settings.BASE_DELIVERY_MINUTES)

        order = await self.repo.create(
            customer_id=customer_id,
            restaurant_id=data.restaurant_id,
            restaurant_name=restaurant_name,
            items=items_serialized,
            status="pending",
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            taxes=taxes,
            tip=data.tip,
            discount=loyalty_discount,
            total=total,
            currency=currency,
            delivery_address=data.delivery_address.model_dump(),
            payment_method=data.payment_method,
            special_instructions=data.special_instructions,
            promo_code=data.promo_code,
            loyalty_points_used=data.loyalty_points_to_use,
            estimated_delivery_time=estimated_delivery,
        )

        await publish_order_event("order.created", {
            "order_id": str(order.id),
            "customer_id": str(customer_id),
            "restaurant_id": str(data.restaurant_id),
            "total": total,
            "currency": currency,
            "payment_method": data.payment_method,
        })

        logger.info("order_created", order_id=str(order.id), customer_id=str(customer_id))
        return order

    async def update_status(
        self,
        order_id: uuid.UUID,
        data: OrderStatusUpdateRequest,
        user_id: uuid.UUID,
        role: str,
    ):  # type: ignore[no-untyped-def]
        order = await self.repo.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if not can_transition(order.status, data.status):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ORDER_STATE_INVALID", "message": f"Cannot transition from {order.status} to {data.status}"},
            )

        if not is_transition_allowed(order.status, data.status, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "You don't have permission to make this status change"},
            )

        previous_status = order.status
        updated = await self.repo.update_status(order_id, data.status)

        await publish_order_event("order.status_changed", {
            "order_id": str(order_id),
            "customer_id": str(order.customer_id),
            "driver_id": str(order.driver_id) if order.driver_id else None,
            "restaurant_id": str(order.restaurant_id),
            "previous_status": previous_status,
            "new_status": data.status,
            "note": data.note,
        })

        logger.info("order_status_updated", order_id=str(order_id), previous=previous_status, new=data.status)
        return updated

    async def cancel_order(self, order_id: uuid.UUID, data: OrderCancelRequest, user_id: uuid.UUID, role: str):  # type: ignore[no-untyped-def]
        order = await self.repo.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        if not can_transition(order.status, "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ORDER_STATE_INVALID", "message": f"Cannot cancel order in {order.status} state"},
            )

        if not is_transition_allowed(order.status, "cancelled", role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot cancel this order")

        updated = await self.repo.update_status(
            order_id,
            "cancelled",
            cancellation_reason=data.reason,
            cancellation_note=data.note,
        )

        await publish_order_event("order.cancelled", {
            "order_id": str(order_id),
            "customer_id": str(order.customer_id),
            "restaurant_id": str(order.restaurant_id),
            "reason": data.reason,
            "refund_amount": order.total,
            "currency": order.currency,
        })

        return updated
