"""Razorpay payment integration (India)."""
import hashlib
import hmac

import razorpay
import structlog

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def get_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


async def create_order(
    amount: int,   # paise (1 INR = 100 paise)
    currency: str,
    order_id: str,
    idempotency_key: str,
) -> dict:
    client = get_client()
    order = client.order.create({
        "amount": amount,
        "currency": currency,
        "receipt": order_id[:40],
        "notes": {"order_id": order_id, "idempotency_key": idempotency_key},
    })
    logger.info("razorpay_order_created", rz_order_id=order["id"], amount=amount)
    return {"provider_payment_id": order["id"], "razorpay_order_id": order["id"]}


def verify_webhook_signature(payload: bytes, sig_header: str) -> bool:
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


async def process_webhook(payload: bytes, sig_header: str) -> dict:
    if not verify_webhook_signature(payload, sig_header):
        raise ValueError("Invalid Razorpay webhook signature")

    import json
    data = json.loads(payload)
    event_type = data.get("event", "")
    payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})

    if event_type == "payment.captured":
        return {
            "event_type": "payment.captured",
            "provider_payment_id": payment_entity.get("order_id", ""),
            "razorpay_payment_id": payment_entity.get("id", ""),
            "status": "succeeded",
        }
    elif event_type == "payment.failed":
        return {
            "event_type": "payment.failed",
            "provider_payment_id": payment_entity.get("order_id", ""),
            "status": "failed",
        }
    return {"event_type": event_type, "provider_payment_id": "", "status": "unknown"}


async def create_refund(razorpay_payment_id: str, amount: int | None = None) -> dict:
    client = get_client()
    kwargs: dict = {}
    if amount:
        kwargs["amount"] = amount
    refund = client.payment.refund(razorpay_payment_id, kwargs)
    return {"refund_id": refund["id"], "status": refund["status"], "amount": refund["amount"]}
