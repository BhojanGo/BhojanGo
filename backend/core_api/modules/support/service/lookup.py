"""Read-only lookups other modules use instead of reading support tables."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.support.models import SupportTicket


async def tickets_by(db: AsyncSession, requester_id: uuid.UUID) -> list[dict]:
    """Tickets the person opened (data export). Not who resolved them."""
    rows = (await db.execute(select(SupportTicket).where(SupportTicket.requester_id == requester_id)
                             .order_by(SupportTicket.created_at))).scalars()
    return [{"id": str(t.id), "kind": t.kind, "status": t.status, "topic": t.topic, "note": t.note,
             "order_id": str(t.order_id) if t.order_id else None, "details": t.details,
             "created_at": t.created_at.isoformat(), "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
             "resolution": t.resolution} for t in rows]
