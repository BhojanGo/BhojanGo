"""Stripe payment integration (USA)."""
from typing import Any

import structlog
import stripe

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def get_stripe() -> Any:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe  # type: ignore[return-value]


async def create_payment_intent(
    amount: int,        # cents
    currency: str,
    order_id: str,
    idempotency_key: str,
    payment_method_id: str | None = None,
) -> dict:
    s = get_stripe()
    kwargs: dict = {
        "amount": amount,
        "currency": currency.lower(),
        "metadata": {"order_id": order_id},
        "idempotency_key": idempotency_key,
        "automatic_payment_methods": {"enabled": True},
    }
    if payment_method_id:
        kwargs["payment_method"] = payment_method_id
        kwargs["confirm"] = True
        del kwargs["automatic_payment_methods"]

    intent = s.PaymentIntent.create(**kwargs)
    logger.info("stripe_intent_created", intent_id=intent.id, amount=amount)
    return {"provider_payment_id": intent.id, "client_secret": intent.client_secret}


async def process_webhook(payload: bytes, sig_header: str) -> dict:
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise ValueError("Invalid Stripe webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        return {"event_type": "payment_intent.succeeded", "provider_payment_id": data["id"], "status": "succeeded"}
    elif event_type == "payment_intent.payment_failed":
        return {"event_type": "payment_intent.payment_failed", "provider_payment_id": data["id"], "status": "failed"}
    return {"event_type": event_type, "provider_payment_id": data.get("id", ""), "status": "unknown"}


async def create_refund(
    provider_payment_id: str, amount: int | None = None, idempotency_key: str | None = None
) -> dict:
    s = get_stripe()
    kwargs: dict = {"payment_intent": provider_payment_id}
    if amount:
        kwargs["amount"] = amount
    if idempotency_key:
        # Stripe dedupes retries with the same idempotency key at the provider too.
        kwargs["idempotency_key"] = idempotency_key
    refund = s.Refund.create(**kwargs)
    return {"refund_id": refund.id, "status": refund.status, "amount": refund.amount}
