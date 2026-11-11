"""Payment gateways behind one interface: Stripe (US), Razorpay (India), Fake (local).

``get_gateway(country)`` picks the real gateway when its keys are set and
``settings.providers.PAYMENT_PROVIDER`` is ``auto`` or ``live``; otherwise the
fake one, which needs no account. Production never uses the fake.

The fake gateway behaves like the real ones from the API's point of view: it
returns a provider payment id and a client secret, and the outcome arrives
later as a signed webhook at ``POST /api/v1/payments/fake/webhook``.
Outcomes follow Stripe's test payment methods: a ``payment_method_id`` that
contains "decline" or "fail" (e.g. ``pm_card_chargeDeclined``) fails,
anything else succeeds.
"""
import asyncio
import hashlib
import hmac
import json
import uuid
from typing import Protocol

import httpx
import structlog

from core_api.modules.payments.service import razorpay_svc, stripe_svc
from shared.config import get_settings
from shared.providers import ProviderConfigError

logger = structlog.get_logger(__name__)

FAKE_SIGNATURE_HEADER = "x-fake-signature"


class PaymentGateway(Protocol):
    name: str
    signature_header: str

    async def create(
        self, *, amount: int, currency: str, order_id: str, idempotency_key: str, payment_method_id: str | None
    ) -> dict:
        """Returns provider_payment_id plus client_secret / razorpay_order_id for the app."""
        ...

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        """Verifies the signature (ValueError if bad). Returns event_type,
        provider_payment_id, status (succeeded | failed | unknown) and extras."""
        ...

    async def refund(self, provider_payment_id: str, amount: int, idempotency_key: str | None, meta: dict) -> dict:
        """Returns refund_id and status."""
        ...


class StripeGateway:
    name = "stripe"
    signature_header = "stripe-signature"

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id):  # type: ignore[no-untyped-def]
        r = await stripe_svc.create_payment_intent(amount, currency, order_id, idempotency_key, payment_method_id)
        return {"provider_payment_id": r["provider_payment_id"], "client_secret": r["client_secret"]}

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        return await stripe_svc.process_webhook(payload, signature)

    async def refund(self, provider_payment_id, amount, idempotency_key, meta):  # type: ignore[no-untyped-def]
        r = await stripe_svc.create_refund(provider_payment_id, amount, idempotency_key=idempotency_key)
        return {"refund_id": r["refund_id"], "status": r["status"]}


class RazorpayGateway:
    name = "razorpay"
    signature_header = "x-razorpay-signature"

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id):  # type: ignore[no-untyped-def]
        r = await razorpay_svc.create_order(amount, currency, order_id, idempotency_key)
        return {"provider_payment_id": r["provider_payment_id"], "razorpay_order_id": r["razorpay_order_id"]}

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        return await razorpay_svc.process_webhook(payload, signature)

    async def refund(self, provider_payment_id, amount, idempotency_key, meta):  # type: ignore[no-untyped-def]
        # Razorpay refunds a payment (pay_...), not the order we created; the
        # payment id arrives with the payment.captured webhook.
        payment_id = meta.get("razorpay_payment_id") or provider_payment_id
        r = await razorpay_svc.create_refund(payment_id, amount)
        return {"refund_id": r["refund_id"], "status": r["status"]}


def sign_fake(payload: bytes) -> str:
    secret = get_settings().providers.FAKE_PAYMENT_WEBHOOK_SECRET.encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def fake_outcome(payment_method_id: str | None) -> str:
    pm = (payment_method_id or "").lower()
    return "failed" if ("decline" in pm or "fail" in pm) else "succeeded"


def fake_webhook_body(provider_payment_id: str, outcome: str) -> bytes:
    return json.dumps({
        "id": f"evt_fake_{uuid.uuid4().hex[:16]}",
        "type": f"payment.{outcome}",
        "provider_payment_id": provider_payment_id,
    }).encode()


async def _deliver_fake_webhook_later(provider_payment_id: str, outcome: str, delay: float) -> None:
    await asyncio.sleep(delay)
    body = fake_webhook_body(provider_payment_id, outcome)
    url = get_settings().providers.FAKE_PAYMENT_WEBHOOK_URL
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, content=body, headers={FAKE_SIGNATURE_HEADER: sign_fake(body)})
        logger.info("fake_webhook_delivered", provider_payment_id=provider_payment_id, outcome=outcome, status=r.status_code)
    except httpx.HTTPError as e:
        logger.error("fake_webhook_failed", provider_payment_id=provider_payment_id, error=str(e))


_background: set[asyncio.Task] = set()


class FakeGateway:
    """No account, no network. Local development and tests only."""

    name = "fake"
    signature_header = FAKE_SIGNATURE_HEADER

    def __init__(self, country: str) -> None:
        self.country = country

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id):  # type: ignore[no-untyped-def]
        pid = f"fake_pay_{uuid.uuid4().hex[:20]}"
        outcome = fake_outcome(payment_method_id)
        delay = get_settings().providers.FAKE_PAYMENT_AUTO_COMPLETE_SECONDS
        if delay > 0:
            task = asyncio.create_task(_deliver_fake_webhook_later(pid, outcome, delay))
            _background.add(task)
            task.add_done_callback(_background.discard)
        logger.info("fake_payment_created", provider_payment_id=pid, amount=amount, currency=currency, outcome=outcome)
        result = {"provider_payment_id": pid, "client_secret": f"{pid}_secret_fake", "fake_outcome": outcome}
        if self.country == "IN":
            result["razorpay_order_id"] = pid
        return result

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        if not hmac.compare_digest(sign_fake(payload), signature or ""):
            raise ValueError("Invalid fake webhook signature")
        data = json.loads(payload)
        event_type = data.get("type", "")
        status = {"payment.succeeded": "succeeded", "payment.failed": "failed"}.get(event_type, "unknown")
        return {"event_type": event_type, "provider_payment_id": data.get("provider_payment_id", ""), "status": status}

    async def refund(self, provider_payment_id, amount, idempotency_key, meta):  # type: ignore[no-untyped-def]
        return {"refund_id": f"fake_re_{uuid.uuid4().hex[:20]}", "status": "succeeded"}


def _live_keys_present(country: str) -> bool:
    p = get_settings().payments
    if country == "US":
        return bool(p.STRIPE_SECRET_KEY)
    return bool(p.RAZORPAY_KEY_ID and p.RAZORPAY_KEY_SECRET)


def get_gateway(country: str) -> PaymentGateway:
    s = get_settings()
    mode = s.providers.PAYMENT_PROVIDER
    use_fake = mode == "fake" or (mode == "auto" and not _live_keys_present(country))
    if use_fake:
        if s.is_production:
            raise ProviderConfigError(f"No live payment keys for {country}; the fake gateway is not allowed in production")
        return FakeGateway(country)
    if mode not in ("auto", "live"):
        raise ProviderConfigError(f"Unknown PAYMENT_PROVIDER '{mode}'")
    return StripeGateway() if country == "US" else RazorpayGateway()


def gateway_by_name(name: str) -> PaymentGateway:
    if name == "stripe":
        return StripeGateway()
    if name == "razorpay":
        return RazorpayGateway()
    if name == "fake":
        if get_settings().is_production:
            raise ProviderConfigError("The fake payment gateway is not allowed in production")
        return FakeGateway("US")
    raise ProviderConfigError(f"Unknown payment gateway '{name}'")
