"""Small read-only lookups other modules use instead of reading order tables."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.models.order import Order


async def has_previous_orders(db: AsyncSession, customer_id: uuid.UUID) -> bool:
    """True when the customer has an order that wasn't cancelled (first-order offers)."""
    q = select(func.count()).select_from(Order).where(Order.customer_id == customer_id, Order.status != "cancelled")
    return bool((await db.execute(q)).scalar())
