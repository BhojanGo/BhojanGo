"""Sales tax for US orders (P9): Stripe Tax, or a local stand-in.

The quote engine prices the bag, then hands the taxable lines and the delivery
address to the tax provider, which returns the tax per jurisdiction and a
calculation id. The id is stored with the quote and the order (Stripe needs it
to record the tax transaction once the payment succeeds, P12).

``TAX_PROVIDER``: ``auto`` (Stripe Tax when STRIPE_SECRET_KEY is set, else the
local stand-in), ``stripe_tax`` or ``local``. Production refuses ``local``.
The local stand-in uses illustrative state rates only; it is not tax advice.
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

import structlog

from shared.config import get_settings
from shared.providers import ProviderConfigError

logger = structlog.get_logger(__name__)
CENT = Decimal("0.01")

# Stripe Tax product codes for what a delivery platform sells.
TAX_CODES = {
    "food": "txcd_40060003",          # prepared food
    "delivery_fee": "txcd_92010001",  # delivery / shipping
    "service_fee": "txcd_20030000",   # general services
    "small_order_fee": "txcd_20030000",
    "surge": "txcd_20030000",
    "late_night_fee": "txcd_20030000",
    "packaging": "txcd_99999999",     # general tangible goods
}


class TaxError(RuntimeError):
    """The provider couldn't calculate tax; never charge without it."""


@dataclass(frozen=True)
class TaxableLine:
    reference: str  # food | delivery_fee | service_fee | ...
    amount: Decimal  # after discounts, in major units


@dataclass(frozen=True)
class TaxAddress:
    country: str
    state: str
    city: str | None = None
    postal_code: str | None = None
    line1: str | None = None


@dataclass(frozen=True)
class TaxBreakdown:
    label: str  # shown on the bill, e.g. "Idaho sales tax"
    jurisdiction: str
    rate_percent: Decimal
    taxable_amount: Decimal
    amount: Decimal


@dataclass(frozen=True)
class TaxResult:
    provider: str
    calculation_id: str
    breakdown: list[TaxBreakdown] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((b.amount for b in self.breakdown), Decimal(0))


class TaxProvider(Protocol):
    name: str

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress) -> TaxResult: ...


# Illustrative combined rates for the local stand-in (state rate; Boise has no
# local sales tax). Food, delivery and service fees are treated as taxable.
LOCAL_RATES: dict[str, tuple[str, Decimal]] = {
    "ID": ("Idaho sales tax", Decimal("6")),
    "WA": ("Washington sales tax", Decimal("6.5")),
    "OR": ("Oregon (no sales tax)", Decimal("0")),
    "UT": ("Utah sales tax", Decimal("6.1")),
}
LOCAL_TAXABLE = {"food", "delivery_fee", "service_fee", "small_order_fee", "surge", "late_night_fee", "packaging"}


class LocalTax:
    """No account, no network. Mirrors what Stripe Tax returns."""

    name = "local"

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress) -> TaxResult:
        if address.state not in LOCAL_RATES:
            raise TaxError(f"No local tax rate for {address.state}; add it to LOCAL_RATES or use Stripe Tax")
        label, rate = LOCAL_RATES[address.state]
        base = sum((ln.amount for ln in lines if ln.reference in LOCAL_TAXABLE), Decimal(0))
        amount = (base * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        return TaxResult(
            provider=self.name, calculation_id=f"taxcalc_local_{uuid.uuid4().hex[:20]}",
            breakdown=[TaxBreakdown(label, f"US-{address.state}", rate, base, amount)] if rate > 0 else [],
        )


class StripeTax:
    name = "stripe_tax"

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress) -> TaxResult:
        import stripe

        stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
        if not address.postal_code:
            raise TaxError("A US address needs a ZIP code to calculate tax")
        try:
            calc = await asyncio.to_thread(
                stripe.tax.Calculation.create,
                currency=currency.lower(),
                line_items=[
                    {"amount": int((ln.amount * 100).to_integral_value(rounding=ROUND_HALF_UP)), "reference": ln.reference,
                     "tax_code": TAX_CODES.get(ln.reference, "txcd_99999999"), "tax_behavior": "exclusive"}
                    for ln in lines if ln.amount > 0
                ],
                customer_details={
                    "address": {"country": address.country, "state": address.state, "city": address.city,
                                "postal_code": address.postal_code, "line1": address.line1},
                    "address_source": "shipping",
                },
                expand=["line_items.data.tax_breakdown"],
            )
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            logger.error("stripe_tax_failed", error=str(e))
            raise TaxError("We couldn't calculate tax right now; please try again")
        breakdown = []
        for b in calc.tax_breakdown:
            details = b.tax_rate_details
            rate = Decimal(str(details.percentage_decimal)) if details else Decimal(0)
            label = f"{details.display_name} ({address.state})" if details else "Sales tax"
            breakdown.append(TaxBreakdown(label, f"US-{address.state}", rate, Decimal(b.taxable_amount) / 100,
                                          Decimal(b.amount) / 100))
        return TaxResult(provider=self.name, calculation_id=calc.id, breakdown=breakdown)


def get_tax_provider() -> TaxProvider:
    s = get_settings()
    mode = s.providers.TAX_PROVIDER
    if mode == "local" or (mode == "auto" and not s.payments.STRIPE_SECRET_KEY):
        if s.is_production:
            raise ProviderConfigError("The local tax stand-in is not allowed in production; set up Stripe Tax")
        return LocalTax()
    if mode in ("auto", "stripe_tax"):
        return StripeTax()
    raise ProviderConfigError(f"Unknown TAX_PROVIDER '{mode}'")
