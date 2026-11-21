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


# R27: the refunds a receipt shows (customer app, website, PDF): every refund that wasn't refused.
REFUND_REASONS = ("missing_item", "wrong_item", "quality", "late", "damaged_in_transit", "rider_issue", "goodwill")
NOT_REFUNDED = ("failed", "canceled", "cancelled")


def refund_reason_code(kind: str, reason: str) -> str:
    """A reason the receipt can name in the reader's language: an item refund's reason, "full"
    for the whole order (a cancellation, an incident), "other" for anything else."""
    if reason in REFUND_REASONS:
        return reason
    return "full" if kind == "full" else "other"


async def order_refunds(db: AsyncSession, order_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[dict]]:
    """Each order's refunds, oldest first: amount (major units, str), kind, reason code, items refunded."""
    if not order_ids:
        return {}
    rows = (await db.execute(select(Refund).where(Refund.order_id.in_(order_ids), Refund.status.not_in(NOT_REFUNDED))
                             .order_by(Refund.created_at))).scalars()
    out: dict[uuid.UUID, list[dict]] = {}
    for r in rows:
        out.setdefault(r.order_id, []).append({
            "amount": str((Decimal(r.amount) / 100).quantize(Decimal("0.01"))), "currency": r.currency, "kind": r.kind,
            "reason": refund_reason_code(r.kind, r.reason), "fault": r.fault,
            "items": [str(ln.get("name")) for ln in (r.lines or []) if ln.get("name") and not ln.get("code")],
            "food": str(sum((Decimal(str(ln.get("food") or 0)) for ln in (r.lines or [])), Decimal(0))),
            "created_at": r.created_at.isoformat() if r.created_at else None})
    return out
