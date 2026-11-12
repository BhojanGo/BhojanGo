"""Small read-only lookups other modules use instead of reading order tables."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order


async def has_previous_orders(db: AsyncSession, customer_id: uuid.UUID) -> bool:
    """True when the customer has an order that wasn't cancelled (first-order offers)."""
    q = select(func.count()).select_from(Order).where(Order.customer_id == customer_id, Order.status != "cancelled")
    return bool((await db.execute(q)).scalar())


async def order_customer(db: AsyncSession, order_id: uuid.UUID) -> uuid.UUID | None:
    """Who placed the order (None if there is no such order)."""
    order = await db.get(Order, order_id)
    return order.customer_id if order else None


async def order_for_payment(db: AsyncSession, order_id: uuid.UUID, customer_id: uuid.UUID) -> dict | None:
    """What payments needs to charge an order: its total in minor units, the
    currency and country. None if it isn't this customer's order."""
    from decimal import Decimal

    order = await db.get(Order, order_id)
    if order is None or order.customer_id != customer_id:
        return None
    return {
        "status": order.status,
        "amount_minor": int((Decimal(order.total) * 100).to_integral_value()),
        "currency": order.currency,
        "country": (order.market_city or "")[:2] or ("IN" if order.currency == "INR" else "US"),
    }
