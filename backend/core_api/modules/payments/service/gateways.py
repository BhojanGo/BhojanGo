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
        self, *, amount: int, currency: str, order_id: str, idempotency_key: str, payment_method_id: str | None,
        customer: dict | None = None,
    ) -> dict:
        """Returns provider_payment_id, client_secret / razorpay_order_id, and
        ``checkout``: what the app's payment SDK needs (P12)."""
        ...

    async def ensure_customer(self, profile: dict, existing: str | None) -> str | None:
        """The customer's id at the provider (created once), or None."""
        ...

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        """Verifies the signature (ValueError if bad). Returns event_type,
        provider_payment_id, status (succeeded | failed | unknown) and extras."""
        ...

    async def refund(self, provider_payment_id: str, amount: int, idempotency_key: str | None, meta: dict) -> dict:
        """Returns refund_id and status."""
        ...


STRIPE_API_VERSION = "2024-06-20"  # the version the mobile SDK's ephemeral keys are made for


class StripeGateway:
    """Stripe PaymentSheet: cards, Apple Pay and Google Pay in one sheet."""

    name = "stripe"
    signature_header = "stripe-signature"

    async def ensure_customer(self, profile: dict, existing: str | None) -> str | None:
        if existing:
            return existing
        s = stripe_svc.get_stripe()
        cus = await asyncio.to_thread(s.Customer.create, email=profile.get("email") or None,
                                      name=profile.get("name") or None, phone=profile.get("phone") or None,
                                      metadata={"user_id": profile["user_id"]})
        return cus.id

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id, customer=None):  # type: ignore[no-untyped-def]
        s = stripe_svc.get_stripe()
        customer = customer or {}
        kwargs: dict = {"amount": amount, "currency": currency.lower(), "metadata": {"order_id": order_id},
                        "idempotency_key": idempotency_key, "automatic_payment_methods": {"enabled": True}}
        if customer.get("provider_customer_id"):
            kwargs["customer"] = customer["provider_customer_id"]
        if payment_method_id:  # server-side confirm (saved card)
            kwargs.update(payment_method=payment_method_id, confirm=True)
            kwargs.pop("automatic_payment_methods")
        pi = await asyncio.to_thread(s.PaymentIntent.create, **kwargs)
        checkout = {"sdk": "stripe_payment_sheet", "payment_intent_client_secret": pi.client_secret,
                    "publishable_key": get_settings().payments.STRIPE_PUBLISHABLE_KEY,
                    "merchant_display_name": "BhojanGo", "apple_pay": {"merchant_country_code": "US"},
                    "google_pay": {"merchant_country_code": "US", "test_env": not get_settings().is_production},
                    "methods": customer.get("methods", [])}
        if kwargs.get("customer"):
            eph = await asyncio.to_thread(s.EphemeralKey.create, customer=kwargs["customer"], stripe_version=STRIPE_API_VERSION)
            checkout.update(customer_id=kwargs["customer"], customer_ephemeral_key=eph.secret)
        logger.info("stripe_intent_created", intent_id=pi.id, amount=amount)
        return {"provider_payment_id": pi.id, "client_secret": pi.client_secret, "checkout": checkout}

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        return await stripe_svc.process_webhook(payload, signature)

    async def refund(self, provider_payment_id, amount, idempotency_key, meta):  # type: ignore[no-untyped-def]
        r = await stripe_svc.create_refund(provider_payment_id, amount, idempotency_key=idempotency_key)
        return {"refund_id": r["refund_id"], "status": r["status"]}


class RazorpayGateway:
    """Razorpay Checkout: UPI, cards and wallets."""

    name = "razorpay"
    signature_header = "x-razorpay-signature"

    async def ensure_customer(self, profile: dict, existing: str | None) -> str | None:
        return existing  # Razorpay Checkout works without a saved customer

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id, customer=None):  # type: ignore[no-untyped-def]
        customer = customer or {}
        r = await razorpay_svc.create_order(amount, currency, order_id, idempotency_key)
        methods = customer.get("methods", [])
        checkout = {"sdk": "razorpay_checkout", "key_id": get_settings().payments.RAZORPAY_KEY_ID,
                    "order_id": r["razorpay_order_id"], "amount": amount, "currency": currency, "name": "BhojanGo",
                    "prefill": {"name": customer.get("name") or "", "email": customer.get("email") or "",
                                "contact": customer.get("phone") or ""},
                    "method": {"upi": "upi" in methods, "card": "card" in methods, "wallet": "wallet" in methods,
                               "netbanking": "net_banking" in methods},
                    "methods": methods}
        return {"provider_payment_id": r["provider_payment_id"], "razorpay_order_id": r["razorpay_order_id"], "checkout": checkout}

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

    async def ensure_customer(self, profile: dict, existing: str | None) -> str | None:
        return existing or f"fake_cus_{profile['user_id'][:8]}"

    async def create(self, *, amount, currency, order_id, idempotency_key, payment_method_id, customer=None):  # type: ignore[no-untyped-def]
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
        # What the app would get from Stripe/Razorpay; locally it "pays" by calling complete_path.
        result["checkout"] = {"sdk": "fake", "mimics": "razorpay_checkout" if self.country == "IN" else "stripe_payment_sheet",
                              "methods": (customer or {}).get("methods", []), "outcome": outcome,
                              "complete_path": "/api/v1/payments/fake/{payment_intent_id}/complete"}
        return result

    async def parse_webhook(self, payload: bytes, signature: str) -> dict:
        if not hmac.compare_digest(sign_fake(payload), signature or ""):
            raise ValueError("Invalid fake webhook signature")
        data = json.loads(payload)
        event_type = data.get("type", "")
        status = {"payment.succeeded": "succeeded", "payment.failed": "failed"}.get(event_type, "unknown")
        return {"event_type": event_type, "provider_payment_id": data.get("provider_payment_id", ""), "status": status,
                "event_id": data.get("id")}

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


def verify_razorpay_checkout(order_id: str, payment_id: str, signature: str) -> bool:
    """The signature Razorpay Checkout hands the app: HMAC-SHA256 of
    "order_id|payment_id" with the key secret."""
    secret = get_settings().payments.RAZORPAY_KEY_SECRET.encode()
    expected = hmac.new(secret, f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return bool(secret) and hmac.compare_digest(expected, signature or "")


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
