"""Read-only lookups other modules use instead of reading pricing tables."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.pricing.models import OrderPricingSnapshot

BILL_KEYS = ("code", "label", "amount", "funded_by", "detail")


def customer_lines(lines: list[dict]) -> list[dict]:
    """Bill lines as the customer sees them (GET /pricing/orders/{id}/bill): no rule ids."""
    return [{k: ln.get(k) for k in BILL_KEYS} for ln in lines]


async def order_bills(db: AsyncSession, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Each order's fair bill (lines, total, currency); orders priced before
    itemised bills have none."""
    if not order_ids:
        return {}
    rows = (await db.execute(select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id.in_(order_ids)))).scalars()
    return {s.order_id: {"currency": s.currency, "total": str(s.total), "lines": customer_lines(s.lines)} for s in rows}
