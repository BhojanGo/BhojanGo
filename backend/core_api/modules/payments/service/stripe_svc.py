"""Stripe payment integration (USA): webhooks and refunds.

Every call that creates something at Stripe sends an idempotency key derived
from our own ids, so a retry (ours or the network's) never charges, refunds or
records twice.

Webhook events we act on (subscribe the endpoint
``POST /api/v1/payments/stripe/webhook`` to exactly these):

* ``payment_intent.succeeded``       -> the payment succeeded; the order is placed
* ``payment_intent.payment_failed``  -> the attempt failed (declined, 3-D Secure failed);
  the order stays ``pending_payment`` with its price held so the customer can retry
* ``payment_intent.canceled``        -> treated as a failed attempt
* ``charge.refunded``, ``refund.created``, ``refund.updated``, ``refund.failed``,
  ``charge.refund.updated``           -> a refund's final status (most card refunds
  succeed at once; a failed one is taken back off the order's refunded amount)
* ``charge.dispute.created``, ``charge.dispute.updated``, ``charge.dispute.closed`` -> a chargeback
  (R39, payments/service/disputes.py: hold the restaurant's share, alert ops, won/lost)

Anything else is acknowledged and ignored.
"""
import asyncio
import json

import structlog
import stripe

from shared.config import get_settings

logger = structlog.get_logger(__name__)

PAYMENT_EVENTS = {
    "payment_intent.succeeded": "succeeded",
    "payment_intent.payment_failed": "failed",
    "payment_intent.canceled": "failed",
}
REFUND_EVENTS = {"charge.refunded", "refund.created", "refund.updated", "refund.failed", "charge.refund.updated"}
DISPUTE_EVENTS = {"charge.dispute.created", "charge.dispute.updated", "charge.dispute.closed"}
WEBHOOK_EVENTS = sorted([*PAYMENT_EVENTS, *REFUND_EVENTS, *DISPUTE_EVENTS])


def get_stripe():  # returns the configured `stripe` module
    stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
    return stripe


def _get(obj, key: str, default=None):  # type: ignore[no-untyped-def]
    """Read a field from a StripeObject or a plain dict."""
    try:
        v = obj[key] if obj is not None else default
    except (KeyError, TypeError):
        return default
    return default if v is None else v


def _failure_reason(intent) -> str:  # type: ignore[no-untyped-def]
    """What the customer is told: Stripe's message for the last error (e.g.
    "Your card was declined."), or why it was cancelled."""
    err = _get(intent, "last_payment_error")
    if err:
        return str(_get(err, "message") or _get(err, "decline_code") or _get(err, "code") or "declined")
    return str(_get(intent, "cancellation_reason") or "canceled")


def _refunds_of(event_type: str, obj) -> list[dict]:  # type: ignore[no-untyped-def]
    if event_type == "charge.refunded":
        refunds = _get(_get(obj, "refunds", {}), "data", []) or []
        pi = _get(obj, "payment_intent", "")
    else:
        refunds = [obj]
        pi = _get(obj, "payment_intent", "")
    return [{"refund_id": _get(r, "id", ""), "status": _get(r, "status", "unknown"), "amount": _get(r, "amount", 0),
             "provider_payment_id": _get(r, "payment_intent", pi) or pi} for r in refunds]


async def process_webhook(payload: bytes, sig_header: str) -> dict:
    try:
        stripe.Webhook.construct_event(payload, sig_header, get_settings().payments.STRIPE_WEBHOOK_SECRET)
    except (stripe.error.SignatureVerificationError, ValueError):  # type: ignore[attr-defined]
        raise ValueError("Invalid Stripe webhook signature")
    # Verified: read the event as plain JSON. The SDK's Event object is not a dict
    # (event.get raised on QA, R10, so no paid order was ever placed); finance reads it the same way.
    event = json.loads(payload)

    event_type = event["type"]
    data = event["data"]["object"]
    eid = event.get("id")
    if event_type in PAYMENT_EVENTS:
        status = PAYMENT_EVENTS[event_type]
        out = {"event_type": event_type, "provider_payment_id": data["id"], "status": status, "event_id": eid}
        if status == "failed":
            out["failure_reason"] = _failure_reason(data)
        return out
    if event_type in DISPUTE_EVENTS:
        return {"event_type": event_type, "kind": "dispute", "event_id": eid, "status": "dispute",
                "provider_payment_id": _get(data, "payment_intent") or "", "dispute": await _dispute_of(data)}
    if event_type in REFUND_EVENTS:
        refunds = _refunds_of(event_type, data)
        return {"event_type": event_type, "kind": "refund", "refunds": refunds, "status": "refund",
                "provider_payment_id": refunds[0]["provider_payment_id"] if refunds else "", "event_id": eid}
    return {"event_type": event_type, "provider_payment_id": _get(data, "id", ""), "status": "unknown", "event_id": eid}


async def _dispute_of(data) -> dict:  # type: ignore[no-untyped-def]
    """A Stripe Dispute as plain fields. Older API versions name only the charge: its PaymentIntent is looked up."""
    pi = _get(data, "payment_intent")
    if not pi and _get(data, "charge"):
        try:
            charge = await asyncio.to_thread(get_stripe().Charge.retrieve, _get(data, "charge"))
            pi = _get(charge, "payment_intent")
        except Exception as e:  # noqa: BLE001 - recorded without its order; finance can still see it
            logger.warning("dispute_charge_lookup_failed", dispute=_get(data, "id"), error=type(e).__name__)
    details = _get(data, "evidence_details") or {}
    return {"id": _get(data, "id"), "amount": _get(data, "amount"), "currency": _get(data, "currency"),
            "reason": _get(data, "reason"), "status": _get(data, "status"), "payment_intent": pi,
            "charge": _get(data, "charge"), "created": _get(data, "created"), "due_by": _get(details, "due_by")}


async def submit_dispute_evidence(dispute_id: str, text: str, files: list[tuple[str, bytes, str]]) -> None:
    """R39: send finance's evidence to Stripe and submit it: the files (Stripe File API, purpose
    dispute_evidence) and the note. In test mode a note of "winning_evidence" / "losing_evidence"
    closes the dispute as won / lost."""
    import io

    s = get_stripe()
    ids = []
    for name, data, _ctype in files[:5]:
        f = await asyncio.to_thread(s.File.create, purpose="dispute_evidence", file=(name, io.BytesIO(data)))
        ids.append(f["id"])
    evidence: dict = {"uncategorized_text": text[:20000]} if text else {}
    if ids:
        evidence["uncategorized_file"] = ids[0]
    await asyncio.to_thread(s.Dispute.modify, dispute_id, evidence=evidence, submit=True)


async def create_refund(
    provider_payment_id: str, amount: int | None = None, idempotency_key: str | None = None, metadata: dict | None = None,
) -> dict:
    """Refund part (``amount`` in cents) or all of a PaymentIntent."""
    s = get_stripe()
    kwargs: dict = {"payment_intent": provider_payment_id}
    if amount:
        kwargs["amount"] = amount
    if metadata:
        kwargs["metadata"] = {k: str(v) for k, v in metadata.items()}
    if idempotency_key:
        # Stripe dedupes retries with the same idempotency key at the provider too.
        kwargs["idempotency_key"] = idempotency_key
    refund = await asyncio.to_thread(s.Refund.create, **kwargs)
    logger.info("stripe_refund_created", refund_id=refund.id, amount=refund.amount, status=refund.status)
    return {"refund_id": refund.id, "status": refund.status, "amount": refund.amount}


def actual_fee(payment_intent_id: str) -> int | None:
    """What Stripe kept of a succeeded payment (R15), in minor units: the charge's balance
    transaction fee. None when Stripe doesn't say (yet); the reports then estimate it."""
    s = get_stripe()
    pi = s.PaymentIntent.retrieve(payment_intent_id, expand=["latest_charge.balance_transaction"])
    bt = _get(_get(pi, "latest_charge"), "balance_transaction")
    fee = _get(bt, "fee")
    return int(fee) if isinstance(fee, int) else None
