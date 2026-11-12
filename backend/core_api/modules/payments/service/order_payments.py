"""Payments for orders: what the orders module asks of payments (P11).

* ``refund_in_full``: give back everything still refundable on an order
  (cancelled after it was paid, or paid after it was cancelled).
"""
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment import PaymentIntent, Refund
from core_api.modules.payments.service.gateways import gateway_by_name
from shared import outbox

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
            result = await gateway_by_name(intent.provider).refund(intent.provider_payment_id, remaining, key, intent.metadata_)
        intent.refunded_amount = intent.amount
        intent.status = "refunded"
        intent.metadata_ = {**intent.metadata_, "refunds": [*intent.metadata_.get("refunds", []), {
            "idempotency_key": key, "refund_id": result["refund_id"], "amount": remaining, "status": result["status"],
            "refund_to": "original_payment", "reason": reason, "created_at": datetime.now(UTC).isoformat()}]}
        db.add(Refund(order_id=order_id, payment_intent_id=intent.id, amount=remaining, currency=intent.currency,
                      kind="full", reason=reason[:60], lines=[], provider_refund_id=result["refund_id"],
                      status=result["status"]))
        await outbox.add(db, "payment.refunded", "order", order_id, {
            "order_id": str(order_id), "user_id": str(intent.user_id), "payment_intent_id": str(intent.id),
            "amount": remaining, "currency": intent.currency, "reason": reason, "provider": intent.provider,
        }, "payment-svc")
        logger.info("order_refunded_in_full", order_id=str(order_id), amount=remaining, reason=reason)
        done = {"refund_id": result["refund_id"], "amount": remaining, "currency": intent.currency}
    await db.flush()
    return done
