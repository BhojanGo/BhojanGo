"""Read-only lookups other modules use instead of reading pricing tables."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.pricing.models import OrderPricingSnapshot
from shared.texts import bill_line_label, language_for

BILL_KEYS = ("code", "label", "amount", "funded_by", "detail")


def relabel(lines: list[dict], locale: str | None = None) -> list[dict]:
    """Lines with today's label for the codes shared/texts.py BILL_LINES names (the tip:
    "Tip for your delivery partner", also on orders priced as "Tip for your rider"),
    in the locale's language. Everything else as stored."""
    language = language_for(locale)
    return [{**ln, "label": bill_line_label(ln.get("code"), str(ln.get("label") or ""), language)}
            if ln.get("code") else ln for ln in lines]


def customer_lines(lines: list[dict], locale: str | None = None) -> list[dict]:
    """Bill lines as the customer sees them (GET /pricing/orders/{id}/bill): no rule ids,
    the tip in today's words in the reader's language (``locale``, e.g. hi-IN)."""
    return relabel([{k: ln.get(k) for k in BILL_KEYS} for ln in lines], locale)


async def order_bills(db: AsyncSession, order_ids: list[uuid.UUID], locale: str | None = None) -> dict[uuid.UUID, dict]:
    """Each order's fair bill (lines, total, currency); orders priced before
    itemised bills have none. ``locale``: the reader's, for the relabelled lines."""
    if not order_ids:
        return {}
    rows = (await db.execute(select(OrderPricingSnapshot).where(OrderPricingSnapshot.order_id.in_(order_ids)))).scalars()
    return {s.order_id: {"currency": s.currency, "total": str(s.total), "lines": customer_lines(s.lines, locale)}
            for s in rows}
