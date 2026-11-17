"""Payout providers (P13): Stripe Connect Express, Razorpay Route, or a local fake.

Which one a country uses is a Markets field, ``countries.payout_provider``
(stripe_connect, razorpay_route, fake or none), set by an admin; nothing here
knows a country. ``PAYOUT_PROVIDER`` (env) only says whether this deployment
may move real money:

    live   the country's provider, for real (missing keys fail loudly)
    auto   the country's provider when its keys are set, else the fake (dev, CI, QA)
    fake   always the fake (CI and QA with no keys)

A country set to ``fake`` always gets the fake; one set to ``none`` has no
payouts (Markets won't let it open). Production refuses the fake in every case
(``PAYOUT_PROVIDER=fake`` already fails at start-up: shared/config.py).
"""
import asyncio
import uuid
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError

logger = structlog.get_logger(__name__)


class PayoutError(RuntimeError):
    """A payout or account call failed. ``final``: the provider refused it (a retry with
    the same idempotency key would be refused again); otherwise the outcome is unknown
    (timeout, the provider's own error) and a retry reuses the key."""

    def __init__(self, message: str, *, final: bool = True) -> None:
        super().__init__(message)
        self.final = final


class ConnectSetupError(PayoutError):
    """The platform's Stripe account can't open connected accounts yet: a one-time
    setting in the Stripe Dashboard (Connect, platform profile). Shown to admins as is."""


class PayoutProvider(Protocol):
    name: str
    hosted_onboarding: bool  # the payee finishes set-up on the provider's own pages (onboarding_link)

    async def create_account(self, payee: dict) -> dict:
        """{external_id, status, onboarding_url}"""
        ...

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        """Send money to the payee's account; returns the transfer id. ``reference`` is
        "<run id>:<statement id>:<attempt>" and is the idempotency key."""
        ...


# The Stripe Dashboard page that unblocks Connect, and the words its errors use.
CONNECT_SETUP_URL = "https://dashboard.stripe.com/test/settings/connect/platform-profile"
_SETUP_HINTS = ("platform-profile", "platform profile", "signed up for connect", "responsibilities of managing losses",
                "review the responsibilities", "connect/platform")


def _stripe():  # type: ignore[no-untyped-def]
    import stripe

    stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
    return stripe


def _stripe_error(e: Exception) -> PayoutError:
    """A StripeError as a PayoutError: refused (4xx) is final; no answer or 5xx isn't."""
    msg = getattr(e, "user_message", None) or str(e)
    if any(h in str(e).lower() for h in _SETUP_HINTS):
        return ConnectSetupError(
            "Stripe Connect isn't set up on the platform account yet. In the Stripe Dashboard (test mode) open "
            f"Settings → Connect → Platform profile ({CONNECT_SETUP_URL}), complete the platform profile and accept "
            "the responsibilities for connected accounts (Express), then try again. Stripe said: " + str(e)[:300])
    status = getattr(e, "http_status", None)
    return PayoutError(msg, final=bool(status) and int(status) < 500)


class StripeConnect:
    """Stripe Connect Express: Stripe hosts onboarding (identity, bank) for us."""

    name = "stripe_connect"
    hosted_onboarding = True

    async def create_account(self, payee: dict) -> dict:
        stripe = _stripe()
        kitchen = payee["type"] == "restaurant"
        # Prefilled so Stripe asks less: who they are and what they do (MCC 5812 eating
        # places, 4215 courier services). A kitchen may be a company or a sole trader, so
        # Stripe asks; a delivery partner is an individual.
        profile = {"mcc": "5812" if kitchen else "4215",
                   "product_description": "Food sold through BhojanGo" if kitchen else "Food delivery with BhojanGo"}
        if kitchen and payee.get("name"):
            profile["name"] = payee["name"]
        try:
            acct = await asyncio.to_thread(
                stripe.Account.create, type="express", country=payee["country"], email=payee.get("email") or None,
                **({} if kitchen else {"business_type": "individual"}),
                business_profile=profile,
                capabilities={"transfers": {"requested": True}},
                metadata={"payee_type": payee["type"], "payee_id": payee["id"]},
                idempotency_key=f"payout-account-{payee['type']}-{payee['id']}",
            )
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            raise _stripe_error(e) from e
        return {"external_id": acct.id, "status": "pending", "onboarding_url": None}

    async def onboarding_link(self, external_id: str, refresh_url: str, return_url: str) -> str:
        """A fresh Account Link (they last a few minutes and work once)."""
        stripe = _stripe()
        try:
            link = await asyncio.to_thread(stripe.AccountLink.create, account=external_id, type="account_onboarding",
                                           refresh_url=refresh_url, return_url=return_url)
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            raise _stripe_error(e) from e
        return link.url

    async def account_state(self, external_id: str) -> dict:
        """The account as Stripe has it now (the same fields as account.updated)."""
        stripe = _stripe()
        try:
            acct = await asyncio.to_thread(stripe.Account.retrieve, external_id)
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            raise _stripe_error(e) from e
        return acct.to_dict() if hasattr(acct, "to_dict") else dict(acct)

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        stripe = _stripe()
        run_id, _, rest = reference.partition(":")
        statement_id = rest.split(":")[0]
        try:
            tr = await asyncio.to_thread(stripe.Transfer.create, amount=amount, currency=currency.lower(),
                                         destination=external_id, transfer_group=f"payout-run-{run_id}",
                                         metadata={"payout_run_id": run_id, "payout_statement_id": statement_id},
                                         idempotency_key=f"payout-{reference}")
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            raise _stripe_error(e) from e
        return tr.id


class RazorpayRoute:
    """Razorpay Route: a linked account per payee, then transfers to it."""

    name = "razorpay_route"
    hosted_onboarding = False

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
    hosted_onboarding = False

    async def create_account(self, payee: dict) -> dict:
        return {"external_id": f"fake_acct_{uuid.uuid4().hex[:16]}", "status": "active", "onboarding_url": None}

    async def transfer(self, external_id: str, amount: int, currency: str, reference: str) -> str:
        logger.info("fake_payout", account=external_id, amount=amount, currency=currency, reference=reference)
        return f"fake_tr_{uuid.uuid4().hex[:16]}"


class NoPayoutProvider(PayoutError):
    """The country has no payout provider in Markets (``none``)."""


LIVE: dict[str, type] = {"stripe_connect": StripeConnect, "razorpay_route": RazorpayRoute}


def _has_keys(choice: str) -> bool:
    p = get_settings().payments
    if choice == "stripe_connect":
        return bool(p.STRIPE_SECRET_KEY)
    return bool(p.RAZORPAY_KEY_ID and p.RAZORPAY_KEY_SECRET)


def _fake() -> PayoutProvider:
    if get_settings().is_production:
        raise ProviderConfigError("The fake payout provider is not allowed in production")
    return FakePayouts()


def get_payout_provider(choice: str) -> PayoutProvider:
    """The provider for a country's Markets choice (``Country.payout_provider``)."""
    if choice == "none":
        raise NoPayoutProvider("No payout provider is set for this country in Markets")
    if choice == "fake":
        return _fake()
    if choice not in LIVE:
        raise ProviderConfigError(f"Unknown payout provider '{choice}'")
    mode = get_settings().providers.PAYOUT_PROVIDER
    if mode not in ("auto", "live", "fake"):
        raise ProviderConfigError(f"Unknown PAYOUT_PROVIDER '{mode}'")
    if mode == "fake" or (mode == "auto" and not _has_keys(choice)):
        return _fake()
    return LIVE[choice]()


async def country_payout_provider(db, country: str) -> PayoutProvider:  # type: ignore[no-untyped-def]
    """The provider a country pays with, from Markets."""
    from core_api.modules.markets.service.markets import MarketService

    c = await MarketService(db).repo.country(country)
    if c is None:
        raise NoPayoutProvider(f"Country {country} not found")
    try:
        return get_payout_provider(c.payout_provider)
    except NoPayoutProvider:
        raise NoPayoutProvider(f"Payouts aren't set up in {c.name} yet: choose a payout provider in Markets") from None


def provider_by_name(name: str) -> PayoutProvider:
    """An existing account's provider (webhooks, transfers to an account opened earlier)."""
    if name == "fake":
        return _fake()
    return LIVE[name]()
