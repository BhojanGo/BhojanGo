"""Read-only lookups other modules use instead of reading payments tables."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment import Refund


async def refunds_for(db: AsyncSession, order_ids: list[uuid.UUID], customer_id: uuid.UUID) -> list[dict]:
    """Refunds on the customer's orders, including problems they reported (data
    export). A note is theirs only when they wrote it (not an agent's note)."""
    if not order_ids:
        return []
    rows = (await db.execute(select(Refund).where(Refund.order_id.in_(order_ids)).order_by(Refund.created_at))).scalars()
    return [{"id": str(r.id), "order_id": str(r.order_id), "amount": str(Decimal(r.amount) / 100), "currency": r.currency,
             "kind": r.kind, "reason": r.reason, "status": r.status,
             "reported_by_you": r.requested_by == customer_id,
             "note": r.note if r.requested_by == customer_id else None,
             "created_at": r.created_at.isoformat()} for r in rows]
