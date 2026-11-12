"""Refunds by item (P12).

Refunding "2 × Paneer Tikka" gives back what the customer actually paid for
them: the items' price, minus their share of any food discount, plus their
share of every tax charged on food (GST 5% in India, Stripe Tax in the US).
The delivery fee (and the tax on it) can be refunded too. Amounts come from the
order's pricing snapshot, so a refund always matches the original bill.

Support agents may refund up to the support_refund_limit business rule per
order; city ops, country managers and finance have no limit.
"""
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment import PaymentIntent, Refund
from core_api.modules.payments.service.gateways import gateway_by_name
from shared import authz, outbox

logger = structlog.get_logger(__name__)
CENT = Decimal("0.01")
DEFAULT_AGENT_LIMIT = {"INR": Decimal("500"), "USD": Decimal("25")}


class RefundError(ValueError):
    """Shown to the admin as is."""


def _m(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ItemRequest:
    menu_item_id: str
    quantity: int


def compute_item_refund(order_items: list[dict], bill: list[dict], requests: list[ItemRequest],
                        already: dict[str, int], include_delivery: bool, delivery_already: bool) -> tuple[Decimal, list[dict]]:
    """Pure: (total, lines) for refunding these items (and maybe delivery)."""
    def amt(ln: dict) -> Decimal:
        return Decimal(str(ln["amount"]))

    food_total = sum((amt(ln) for ln in bill if ln["code"] == "food"), Decimal(0))
    food_discount = sum((amt(ln) for ln in bill if ln["code"] == "promotion" and ln.get("taxable_as") == "food"), Decimal(0))
    taxes = [ln for ln in bill if ln["code"] == "tax" and ln.get("detail")]
    by_id = {str(i["menu_item_id"]): i for i in order_items}

    lines: list[dict] = []
    total = Decimal(0)
    for req in requests:
        item = by_id.get(req.menu_item_id)
        if item is None:
            raise RefundError("That item isn't in this order")
        left = int(item["quantity"]) - already.get(req.menu_item_id, 0)
        if req.quantity < 1 or req.quantity > left:
            raise RefundError(f"Only {left} × {item['name']} can still be refunded")
        food = _m(Decimal(str(item["unit_price"])) * req.quantity)
        share = food / food_total if food_total else Decimal(0)
        discount = _m(food_discount * share)  # negative or zero
        net = food + discount
        tax = Decimal(0)
        for t in taxes:
            targets = (t["detail"].get("targets") or "").split(",")
            base = Decimal(t["detail"].get("base") or "0")
            if "food" in targets and base > 0:
                tax += amt(t) * net / base
        tax = _m(tax)
        amount = net + tax
        lines.append({"menu_item_id": req.menu_item_id, "name": item["name"], "quantity": req.quantity,
                      "food": str(food), "discount": str(discount), "tax": str(tax), "amount": str(amount)})
        total += amount

    if include_delivery:
        if delivery_already:
            raise RefundError("The delivery fee was already refunded")
        fee = sum((amt(ln) for ln in bill if ln["code"] == "delivery_fee"), Decimal(0))
        fee += sum((amt(ln) for ln in bill if ln["code"] == "promotion" and ln.get("taxable_as") == "delivery_fee"), Decimal(0))
        tax = Decimal(0)
        for t in taxes:
            targets = (t["detail"].get("targets") or "").split(",")
            base = Decimal(t["detail"].get("base") or "0")
            if "delivery_fee" in targets and base > 0:
                tax += amt(t) * fee / base
        tax = _m(tax)
        lines.append({"code": "delivery_fee", "name": "Delivery fee", "food": "0", "discount": "0",
                      "fee": str(_m(fee)), "tax": str(tax), "amount": str(_m(fee) + tax)})
        total += _m(fee) + tax
    return _m(total), lines


async def business_rule(db: AsyncSession, market_city: str | None, name: str):  # type: ignore[no-untyped-def]
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    city = market_city or ""
    rules = await RuleService(db).resolve(Context(country=city[:2] or None, region=city[:5] or None, city=city or None))
    return rules.get(f"business:{name}")


async def preview_items(db: AsyncSession, order_id: uuid.UUID, requests: list[ItemRequest]) -> tuple[Decimal, list[dict], str]:
    """(amount, lines, currency) refunding these items would give back now; RefundError if it can't."""
    from core_api.modules.orders.models.order import Order
    from core_api.modules.pricing.service.quotes import QuoteService

    order = await db.get(Order, order_id)
    snap = await QuoteService(db).snapshot(order_id) if order else None
    if order is None or snap is None:
        raise RefundError("This order has no itemised bill to refund against")
    previous = (await db.execute(select(Refund).where(Refund.order_id == order_id))).scalars().all()
    already: dict[str, int] = {}
    for r in previous:
        for ln in r.lines:
            if ln.get("menu_item_id"):
                already[ln["menu_item_id"]] = already.get(ln["menu_item_id"], 0) + int(ln["quantity"])
    total, lines = compute_item_refund(order.items, snap.lines, requests, already, False, False)
    return total, lines, order.currency


async def agent_limit(db: AsyncSession, market_city: str | None, currency: str) -> Decimal:
    from core_api.modules.rules.service.resolver import Context
    from core_api.modules.rules.service.rules import RuleService

    city = market_city or ""
    rules = await RuleService(db).resolve(Context(country=city[:2] or None, region=city[:5] or None, city=city or None))
    r = rules.get("business:support_refund_limit")
    return Decimal(str(r.params["max_per_order"])) if r else DEFAULT_AGENT_LIMIT.get(currency, Decimal("25"))


# Why the customer gets money back decides who pays for it (Phase 1 decision):
# the restaurant for its own mistakes, the platform for delivery problems and goodwill.
FAULT_BY_REASON = {
    "wrong_item": "restaurant", "missing_item": "restaurant", "quality": "restaurant",
    "late": "delivery", "damaged_in_transit": "delivery", "rider_issue": "delivery",
    "goodwill": "goodwill",
}


def fault_for(reason: str) -> str:
    try:
        return FAULT_BY_REASON[reason]
    except KeyError:
        raise RefundError(f"Unknown refund reason {reason!r}; pick one of {', '.join(FAULT_BY_REASON)}")


def limited_to_agent(assignments: list[authz.Assignment], city: str) -> bool:
    """True when refunds.issue here comes only from the support agent role."""
    roles = {a.role for a in assignments if authz.role_allows(a.role, "refunds.issue") and authz.covers(a.scope, city)}
    return roles == {"support_agent"}


async def refund_items(db: AsyncSession, *, order_id: uuid.UUID, requests: list[ItemRequest], include_delivery: bool,
                       reason: str, note: str | None, actor_id: uuid.UUID, assignments: list[authz.Assignment]) -> Refund:
    from core_api.modules.orders.models.order import Order
    from core_api.modules.pricing.service.quotes import QuoteService

    fault = fault_for(reason)
    order = await db.get(Order, order_id)
    if order is None:
        raise RefundError("Order not found")
    snap = await QuoteService(db).snapshot(order_id)
    if snap is None:
        raise RefundError("This order has no itemised bill to refund against")
    intent = (await db.execute(
        select(PaymentIntent).where(PaymentIntent.order_id == order_id, PaymentIntent.status.in_(("succeeded", "partially_refunded")))
        .with_for_update()
    )).scalars().first()
    if intent is None:
        raise RefundError("Nothing to refund: the order has no captured payment left")

    previous = (await db.execute(select(Refund).where(Refund.order_id == order_id))).scalars().all()
    already: dict[str, int] = {}
    delivery_already = False
    for r in previous:
        for ln in r.lines:
            if ln.get("menu_item_id"):
                already[ln["menu_item_id"]] = already.get(ln["menu_item_id"], 0) + int(ln["quantity"])
            if ln.get("code") == "delivery_fee":
                delivery_already = True

    total, lines = compute_item_refund(order.items, snap.lines, requests, already, include_delivery, delivery_already)
    minor = int((total * 100).to_integral_value())
    remaining = intent.amount - (intent.refunded_amount or 0)
    if minor <= 0:
        raise RefundError("Choose at least one item or the delivery fee")
    minor = min(minor, remaining)

    city = order.market_city or ""
    if limited_to_agent(assignments, city):
        limit = await agent_limit(db, order.market_city, intent.currency)
        given = sum(r.amount for r in previous) + minor
        if Decimal(given) / 100 > limit:
            raise RefundError(f"Above your refund limit of {intent.currency} {limit:.0f} for one order; "
                              "ask city ops, a country manager or finance")

    refund = Refund(order_id=order_id, payment_intent_id=intent.id, amount=minor, currency=intent.currency, kind="items",
                    reason=reason, fault=fault, note=note, lines=lines, requested_by=actor_id, status="pending")
    db.add(refund)
    await db.flush()
    result = await gateway_by_name(intent.provider).refund(intent.provider_payment_id, minor, f"refund:{refund.id}", intent.metadata_)
    refund.provider_refund_id, refund.status = result["refund_id"], result["status"]
    intent.refunded_amount = (intent.refunded_amount or 0) + minor
    intent.status = "refunded" if intent.refunded_amount >= intent.amount else "partially_refunded"
    await outbox.add(db, "payment.refunded", "order", order_id, {
        "order_id": str(order_id), "user_id": str(intent.user_id), "refund_id": str(refund.id), "amount": minor,
        "currency": intent.currency, "reason": reason, "fault": fault, "items": lines, "provider": intent.provider,
    }, "payment-svc")
    await db.flush()
    logger.info("refund_by_item", order_id=str(order_id), amount=minor, items=len(lines), by=str(actor_id))
    return refund


async def list_refunds(db: AsyncSession, order_id: uuid.UUID) -> list[Refund]:
    return list((await db.execute(select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at))).scalars())
