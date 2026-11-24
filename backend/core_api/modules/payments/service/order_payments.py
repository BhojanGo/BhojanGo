"""Payments for orders: what the orders module asks of payments (P11).

* ``refund_in_full``: give back everything still refundable on an order
  (cancelled after it was paid, or paid after it was cancelled).
* ``place_review_order`` (R20): an app store review order costs nothing; it is
  paid on the spot with no payment provider (a $0 PaymentIntent is refused by
  Stripe, and there is nothing to charge).
"""
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment import PaymentIntent, Refund
from core_api.modules.payments.service.gateways import gateway_by_name
from shared import outbox

REVIEW_PROVIDER = "review"  # payment_intents.provider of a review order's (zero) payment

logger = structlog.get_logger(__name__)


async def refund_in_full(db: AsyncSession, order_id: uuid.UUID, reason: str) -> dict | None:
    """Refund what remains of the order's captured payment, to where it came
    from. Idempotent: an order already fully refunded returns None."""
    rows = (await db.execute(
        select(PaymentIntent)
        .where(PaymentIntent.order_id == order_id, PaymentIntent.status.in_(("succeeded", "partially_refunded")))
        .with_for_update()
    )).scalars().all()
    done = None
    for intent in rows:
        remaining = intent.amount - (intent.refunded_amount or 0)
        if remaining <= 0:
            continue
        key = f"refund-in-full:{intent.id}"
        if intent.provider == "wallet":
            from decimal import Decimal

            from core_api.modules.payments.repository.payment import WalletRepository

            await WalletRepository(db).credit(intent.user_id, Decimal(remaining) / 100, f"Refund: {reason}",
                                              reference_id=str(order_id), reference_type="refund")
            result = {"refund_id": f"wallet_refund_{uuid.uuid4()}", "status": "succeeded"}
        else:
            result = await gateway_by_name(intent.provider).refund(intent.provider_payment_id, remaining, key,
                                                                   {**intent.metadata_, "order_id": str(order_id)})
        full = not intent.refunded_amount
        intent.refunded_amount = intent.amount
        intent.status = "refunded"
        intent.metadata_ = {**intent.metadata_, "refunds": [*intent.metadata_.get("refunds", []), {
            "idempotency_key": key, "refund_id": result["refund_id"], "amount": remaining, "status": result["status"],
            "refund_to": "original_payment", "reason": reason, "created_at": datetime.now(UTC).isoformat()}]}
        from core_api.modules.payments.service.refunds import reverse_tax

        await reverse_tax(intent, key, remaining, full)
        db.add(Refund(order_id=order_id, payment_intent_id=intent.id, amount=remaining, currency=intent.currency,
                      kind="full", reason=reason[:60], lines=[], provider_refund_id=result["refund_id"],
                      status=result["status"]))
        await outbox.add(db, "payment.refunded", "order", order_id, {
            "order_id": str(order_id), "user_id": str(intent.user_id), "payment_intent_id": str(intent.id),
            "amount": remaining, "currency": intent.currency, "reason": reason, "provider": intent.provider,
        }, "payment-svc")
        from core_api.modules.pricing.service import offer_budget

        await offer_budget.give_back(db, order_id)  # R38: refunded in full: the offer cost goes back to its budget
        logger.info("order_refunded_in_full", order_id=str(order_id), amount=remaining, reason=reason)
        done = {"refund_id": result["refund_id"], "amount": remaining, "currency": intent.currency}
    await db.flush()
    return done


async def place_review_order(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID, currency: str) -> None:
    """Record a zero payment for an app store review order and place the order, in this
    transaction, as a provider's webhook would (payment.succeeded, then placed). The
    caller has checked it is one (orders: a review account's $0 order in its review-only
    city); no payment provider is called. Idempotent: a second call changes nothing."""
    from core_api.modules.payments.api.v1.payments import apply_payment_event
    from core_api.modules.payments.repository.payment import PaymentRepository

    provider_id = f"review:{order_id}"
    repo = PaymentRepository(db)
    if await repo.get_by_provider_id(provider_id) is None:
        await repo.create_intent(
            order_id=order_id, user_id=user_id, provider=REVIEW_PROVIDER, provider_payment_id=provider_id,
            amount=0, currency=currency, status="pending", idempotency_key=f"{order_id}:review",
            metadata_={"payment_method": "none", "review": True})
    await apply_payment_event(db, REVIEW_PROVIDER, {"event_type": "payment.succeeded", "provider_payment_id": provider_id,
                                                    "status": "succeeded", "event_id": provider_id})
    logger.info("review_order_placed_without_payment", order_id=str(order_id))
