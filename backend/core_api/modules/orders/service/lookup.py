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
        "payment_due_at": order.payment_due_at.isoformat() if order.payment_due_at else None,
    }


async def order_market(db: AsyncSession, order_id: uuid.UUID) -> str | None:
    """The order's city code ("" if unknown); None if there is no such order."""
    order = await db.get(Order, order_id)
    return None if order is None else (order.market_city or "")


async def customer_order_ids(db: AsyncSession, customer_id: uuid.UUID) -> list[uuid.UUID]:
    q = select(Order.id).where(Order.customer_id == customer_id).order_by(Order.created_at)
    return [i for (i,) in (await db.execute(q)).all()]


async def orders_for_export(db: AsyncSession, customer_id: uuid.UUID) -> list[dict]:
    """The customer's orders as they saw them (data export). Not the rider, the
    proof photo or the platform/kitchen split: those are about other people."""
    rows = (await db.execute(select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at))).scalars()
    return [{
        "id": str(o.id), "status": o.status, "restaurant_id": str(o.restaurant_id), "restaurant_name": o.restaurant_name,
        "items": o.items, "subtotal": str(o.subtotal), "delivery_fee": str(o.delivery_fee), "taxes": str(o.taxes),
        "tip": str(o.tip), "discount": str(o.discount), "total": str(o.total), "currency": o.currency,
        "delivery_address": o.delivery_address, "special_instructions": o.special_instructions,
        "payment_method": o.payment_method, "promo_code": o.promo_code,
        "cancellation_reason": o.cancellation_reason,
        "created_at": o.created_at.isoformat(), "placed_at": o.placed_at.isoformat() if o.placed_at else None,
        "delivered_at": o.actual_delivery_time.isoformat() if o.actual_delivery_time else None,
        "cancelled_at": o.cancelled_at.isoformat() if o.cancelled_at else None,
    } for o in rows]


# Account deletion keeps orders (tax and restaurant records) but not where the
# person lives: street, landmark, the map pin, their notes and the door photo
# go. City, state, postal code and country stay because they decide which tax
# applied (GST place of supply, US sales-tax jurisdiction).
TAX_JURISDICTION_KEYS = ("city", "state", "zip", "postal_code", "country")


def scrub_delivery_address(address: dict | None) -> dict:
    a = address or {}
    return {**{k: a[k] for k in TAX_JURISDICTION_KEYS if k in a}, "street": "", "landmark": None}


async def forget_customer(db: AsyncSession, customer_id: uuid.UUID) -> int:
    """Account deletion: remove the personal details from the customer's orders."""
    rows = (await db.execute(select(Order).where(Order.customer_id == customer_id))).scalars().all()
    for o in rows:
        o.delivery_address = scrub_delivery_address(o.delivery_address)
        o.delivery_lat = o.delivery_lng = None
        o.special_instructions = None
        if o.cancelled_by == "customer":
            o.cancellation_note = None
        if o.delivery_proof:
            o.delivery_proof = {"method": o.delivery_proof.get("method")}  # how, not the photo of the door
    await db.flush()
    return len(rows)


async def orders_in_progress(db: AsyncSession, *, driver_id: uuid.UUID | None = None,
                             restaurant_ids: list[uuid.UUID] | None = None) -> int:
    """Paid orders not yet delivered or cancelled that this delivery partner carries or
    these kitchens make (account deletion waits for them: R19)."""
    from core_api.modules.orders.service.state_machine import TERMINAL_STATES

    who = []
    if driver_id is not None:
        who.append(Order.driver_id == driver_id)
    if restaurant_ids:
        who.append(Order.restaurant_id.in_(restaurant_ids))
    if not who:
        return 0
    from sqlalchemy import or_

    return int((await db.execute(select(func.count()).select_from(Order).where(
        or_(*who), Order.status.notin_(TERMINAL_STATES | {"pending_payment"})))).scalar_one())
