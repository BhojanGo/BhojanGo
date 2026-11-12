"""Payout providers (P13): Stripe Connect Express (US), Razorpay Route (India),
or a local fake.

``PAYOUT_PROVIDER``: ``auto`` (the live provider for a country when its keys
are set, else the fake), ``live`` or ``fake``. Production refuses the fake.
"""
import asyncio
import uuid
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError

logger = structlog.get_logger(__name__)


class PayoutError(RuntimeError):
    pass


class PayoutProvider(Protocol):
    name: str

    async def create_account(self, payee: dict) -> dict:
        """{external_id, status, onboarding_url}"""
        ...

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        """Send money to the payee's account; returns the transfer id."""
        ...


class StripeConnect:
    """Stripe Connect Express: Stripe hosts onboarding (identity, bank) for us."""

    name = "stripe_connect"

    async def create_account(self, payee: dict) -> dict:
        import stripe

        stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
        acct = await asyncio.to_thread(
            stripe.Account.create, type="express", country=payee["country"], email=payee.get("email") or None,
            business_type="company" if payee["type"] == "restaurant" else "individual",
            capabilities={"transfers": {"requested": True}},
            metadata={"payee_type": payee["type"], "payee_id": payee["id"]},
        )
        link = await asyncio.to_thread(
            stripe.AccountLink.create, account=acct.id, type="account_onboarding",
            refresh_url=payee["return_url"], return_url=payee["return_url"],
        )
        return {"external_id": acct.id, "status": "pending", "onboarding_url": link.url}

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        import stripe

        stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
        try:
            tr = await asyncio.to_thread(stripe.Transfer.create, amount=amount, currency=currency.lower(),
                                         destination=external_id, transfer_group=reference.split(":")[0],
                                         idempotency_key=reference)
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            raise PayoutError(str(e)) from e
        return tr.id


class RazorpayRoute:
    """Razorpay Route: a linked account per payee, then transfers to it."""

    name = "razorpay_route"

    def _client(self):  # type: ignore[no-untyped-def]
        import razorpay

        p = get_settings().payments
        return razorpay.Client(auth=(p.RAZORPAY_KEY_ID, p.RAZORPAY_KEY_SECRET))

    async def create_account(self, payee: dict) -> dict:
        acc = await asyncio.to_thread(self._client().account.create, {
            "email": payee.get("email"), "phone": payee.get("phone"), "type": "route",
            "reference_id": payee["id"][:20], "legal_business_name": payee["name"],
            "business_type": "partnership" if payee["type"] == "restaurant" else "individual",
            "contact_name": payee["name"],
        })
        # KYC and the bank account are completed in Razorpay's dashboard / forms.
        return {"external_id": acc["id"], "status": "pending", "onboarding_url": None}

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        try:
            tr = await asyncio.to_thread(self._client().transfer.create, {
                "account": external_id, "amount": amount, "currency": currency, "notes": {"reference": reference}})
        except Exception as e:  # noqa: BLE001 - razorpay raises several error types
            raise PayoutError(str(e)) from e
        return tr["id"]


class FakePayouts:
    """No account, no money moves. Accounts are active at once."""

    name = "fake"

    async def create_account(self, payee: dict) -> dict:
        return {"external_id": f"fake_acct_{uuid.uuid4().hex[:16]}", "status": "active", "onboarding_url": None}

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        logger.info("fake_payout", account=external_id, amount=amount, currency=currency, reference=reference)
        return f"fake_tr_{uuid.uuid4().hex[:16]}"


def get_payout_provider(country: str) -> PayoutProvider:
    s = get_settings()
    mode = s.providers.PAYOUT_PROVIDER
    live_keys = bool(s.payments.STRIPE_SECRET_KEY) if country == "US" else bool(s.payments.RAZORPAY_KEY_ID and s.payments.RAZORPAY_KEY_SECRET)
    if mode == "fake" or (mode == "auto" and not live_keys):
        if s.is_production:
            raise ProviderConfigError("The fake payout provider is not allowed in production")
        return FakePayouts()
    if mode not in ("auto", "live"):
        raise ProviderConfigError(f"Unknown PAYOUT_PROVIDER '{mode}'")
    return StripeConnect() if country == "US" else RazorpayRoute()


def provider_by_name(name: str) -> PayoutProvider:
    return {"stripe_connect": StripeConnect, "razorpay_route": RazorpayRoute, "fake": FakePayouts}[name]()
