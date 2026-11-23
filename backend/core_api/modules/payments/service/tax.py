"""Sales tax for US orders (P9): Stripe Tax, or a local stand-in.

The quote engine prices the bag, then hands the taxable lines (one per cart
line for food, one per fee) and the delivery address to the tax provider, which
returns the tax per jurisdiction and a calculation id. The tax lines on the
fair bill are exactly what the provider returned. The id is stored with the
quote and the order's pricing snapshot; once the payment succeeds it becomes a
Stripe Tax transaction (what Stripe reports and files), and refunds reverse
their share of it.

``TAX_PROVIDER``: ``auto`` (Stripe Tax when STRIPE_SECRET_KEY is set, else the
local stand-in), ``stripe_tax`` or ``local``. Production refuses ``local``.
The local stand-in uses illustrative state rates only; it is not tax advice.

When Stripe Tax can't help (documented degradation, never made-up tax):

* No registration in the delivery state: Stripe answers with zero tax and
  ``taxability_reason`` ``not_collecting``. That *is* Stripe's answer: the bill
  shows a $0.00 tax line per jurisdiction Stripe named, and the reason is kept
  in the line's detail. Fix: Dashboard > Tax > Registrations > add the state
  (test mode: any state, e.g. Idaho), or ``POST /v1/tax/registrations``.
* Stripe Tax not set up on the account (e.g. head office address missing,
  settings "pending"): Stripe refuses the calculation. Production refuses the
  quote (never charge without tax). Outside production the quote goes ahead
  with one $0.00 line, "Sales tax not calculated", provider
  ``stripe_tax_unavailable``, no calculation id and so no tax transaction; the
  log says ``stripe_tax_not_configured`` with Stripe's message. Fix: Dashboard >
  Settings > Tax > set the head office address and default tax behaviour
  (``POST /v1/tax/settings`` with ``head_office[address]`` and
  ``defaults[tax_behavior]=exclusive``), then add a registration as above.
* Network / rate limit / Stripe outage: the quote is refused with "try again"
  everywhere (a transient problem must not produce a tax-free order).
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
    "platform_fee": "txcd_20030000",  # R29: general services; Stripe Tax decides if it's taxable where the customer is
    "small_order_fee": "txcd_20030000",
    "surge": "txcd_20030000",
    "late_night_fee": "txcd_20030000",
    "packaging": "txcd_99999999",     # general tangible goods
}
# R33: the state's tax rule (tax:external taxable_lines) decides what is taxable; the Stripe mapping follows it.
NONTAXABLE_CODE = "txcd_00000000"     # Stripe's "nontaxable": the line is reported, never taxed
MEAL_CODE = TAX_CODES["food"]         # a fee the rule taxes (a service charge) is part of the meal's sale price


class TaxError(RuntimeError):
    """The provider couldn't calculate tax; never charge without it."""


@dataclass(frozen=True)
class TaxableLine:
    reference: str  # unique within one calculation: "food-1-<item id>", "delivery_fee", ...
    amount: Decimal  # after discounts, in major units
    kind: str | None = None  # food | delivery_fee | service_fee | ... (defaults to reference)
    tax_code: str | None = None  # a product tax code for this line (else the kind's)
    taxable: bool | None = None  # R33: the state's tax rule says (None: the provider decides by the tax code)

    @property
    def what(self) -> str:
        return self.kind or self.reference


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
    reason: str | None = None  # Stripe's taxability_reason when no tax applies (e.g. not_collecting)


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

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress,
                        idempotency_key: str | None = None) -> TaxResult: ...


# Illustrative combined rates for the local stand-in (state rate; Boise has no
# local sales tax). R33: which lines are taxable comes from the state's tax rule
# (TaxableLine.taxable); LOCAL_TAXABLE is only used when no rule says.
LOCAL_RATES: dict[str, tuple[str, Decimal]] = {
    "ID": ("Idaho sales tax", Decimal("6")),
    "WA": ("Washington sales tax", Decimal("6.5")),
    "OR": ("Oregon (no sales tax)", Decimal("0")),
    "UT": ("Utah sales tax", Decimal("6.1")),
}
LOCAL_TAXABLE = {"food", "delivery_fee", "platform_fee", "service_fee", "small_order_fee", "surge", "late_night_fee", "packaging"}


class LocalTax:
    """No account, no network. Mirrors what Stripe Tax returns."""

    name = "local"

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress,
                        idempotency_key: str | None = None) -> TaxResult:
        if address.state not in LOCAL_RATES:
            raise TaxError(f"No local tax rate for {address.state}; add it to LOCAL_RATES or use Stripe Tax")
        label, rate = LOCAL_RATES[address.state]
        base = sum((ln.amount for ln in lines if (ln.what in LOCAL_TAXABLE if ln.taxable is None else ln.taxable)), Decimal(0))
        amount = (base * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        return TaxResult(
            provider=self.name, calculation_id=f"taxcalc_local_{uuid.uuid4().hex[:20]}",
            breakdown=[TaxBreakdown(label, f"US-{address.state}", rate, base, amount)] if rate > 0 else [],
        )


def _cents(v: Decimal) -> int:
    return int((v * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _g(obj, key: str, default=None):  # type: ignore[no-untyped-def]
    """A field of a StripeObject (or dict), or ``default``."""
    try:
        v = obj[key]
    except (KeyError, TypeError, AttributeError):
        v = getattr(obj, key, default) if not isinstance(obj, dict) else default
    return default if v is None else v


def _tax_type_label(tax_type: str | None, display: str | None) -> str:
    if display:
        return display.lower()
    return (tax_type or "sales_tax").replace("_", " ")


def parse_calculation(calc, state: str) -> list[TaxBreakdown]:  # type: ignore[no-untyped-def]
    """Stripe's answer as bill lines: one per jurisdiction (state, county,
    city...), from the line items' breakdowns; the calculation-level summary
    when the line items aren't all there."""
    items = _g(calc, "line_items")
    data = _g(items, "data", []) if items is not None else []
    if data and not _g(items, "has_more", False):
        by: dict[tuple, dict] = {}
        ship = _g(calc, "shipping_cost")  # the delivery fee's tax (sent as shipping_cost)
        for li in [*data, *([ship] if ship is not None else [])]:
            for b in _g(li, "tax_breakdown", []) or []:
                j = _g(b, "jurisdiction", {})
                d = _g(b, "tax_rate_details")
                name = _g(j, "display_name") or state
                level = _g(j, "level", "state")
                kind = _tax_type_label(_g(d, "tax_type") if d else None, _g(d, "display_name") if d else None)
                key = (level, name, kind)
                row = by.setdefault(key, {"label": f"{name} {kind}", "jur": f"US-{_g(j, 'state') or state}"
                                          + ("" if level == "state" else f"-{level}:{name}"),
                                          "rate": Decimal(0), "rate_base": -1, "taxable": 0, "amount": 0, "reasons": set()})
                taxable, amount = int(_g(b, "taxable_amount", 0)), int(_g(b, "amount", 0))
                row["taxable"] += taxable
                row["amount"] += amount
                if d is not None and taxable > row["rate_base"]:  # the rate of the biggest line it applies to
                    row["rate"], row["rate_base"] = Decimal(str(_g(d, "percentage_decimal", "0"))), taxable
                if amount == 0 and _g(b, "taxability_reason"):
                    row["reasons"].add(str(_g(b, "taxability_reason")))
        out = []
        for row in by.values():
            reason = ",".join(sorted(row["reasons"])) if row["amount"] == 0 and row["reasons"] else None
            out.append(TaxBreakdown(row["label"], row["jur"], row["rate"], Decimal(row["taxable"]) / 100,
                                    Decimal(row["amount"]) / 100, reason))
        return out
    out = []
    for b in _g(calc, "tax_breakdown", []) or []:
        d = _g(b, "tax_rate_details")
        st = (_g(d, "state") if d else None) or state
        rate = Decimal(str(_g(d, "percentage_decimal", "0"))) if d else Decimal(0)
        amount = int(_g(b, "amount", 0))
        out.append(TaxBreakdown(f"{st} {_tax_type_label(_g(d, 'tax_type') if d else None, None)}", f"US-{st}", rate,
                                Decimal(int(_g(b, "taxable_amount", 0))) / 100, Decimal(amount) / 100,
                                str(_g(b, "taxability_reason")) if amount == 0 and _g(b, "taxability_reason") else None))
    return out


UNAVAILABLE = "stripe_tax_unavailable"
SHIPPING_TAX_CODE = "txcd_92010001"


def stripe_code(ln: TaxableLine) -> str:
    """R33: the tax code a line is sent with. The state's rule decides: a line it doesn't tax goes as
    non-taxable (still reported); a fee it taxes goes as part of the meal (Idaho: a service charge with a
    meal is part of its sale price); otherwise the line's own code, and Stripe Tax decides."""
    if ln.tax_code:
        return ln.tax_code
    own = TAX_CODES.get(ln.what, "txcd_99999999")
    if ln.taxable is False:
        return NONTAXABLE_CODE
    if ln.taxable and own == TAX_CODES["service_fee"]:
        return MEAL_CODE
    return own


def _not_set_up(e) -> bool:  # type: ignore[no-untyped-def]
    """Stripe's answer when Stripe Tax isn't activated (head office, settings) on the account."""
    text = f"{getattr(e, 'code', '') or ''} {e}".lower()
    return "stripe_tax_inactive" in text or "not been activated" in text or "head office" in text or "tax settings" in text


class StripeTax:
    name = "stripe_tax"

    async def calculate(self, currency: str, lines: list[TaxableLine], address: TaxAddress,
                        idempotency_key: str | None = None) -> TaxResult:
        import stripe

        stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
        if not address.postal_code:
            raise TaxError("A US address needs a ZIP code to calculate tax")
        # Stripe Tax refuses a shipping tax code on a line item: the delivery fee goes in
        # shipping_cost (found on QA, R10: every US quote fell back to "not calculated").
        shipping = [ln for ln in lines if ln.amount > 0 and TAX_CODES.get(ln.what) == SHIPPING_TAX_CODE and not ln.tax_code]
        params: dict = {
            "currency": currency.lower(),
            "line_items": [
                {"amount": _cents(ln.amount), "reference": ln.reference[:500],
                 "tax_code": stripe_code(ln), "tax_behavior": "exclusive"}
                for ln in lines if ln.amount > 0 and ln not in shipping
            ],
            "customer_details": {
                "address": {k: v for k, v in {"country": address.country, "state": address.state, "city": address.city,
                                              "postal_code": address.postal_code, "line1": address.line1}.items() if v},
                "address_source": "shipping",
            },
            "expand": ["line_items.data.tax_breakdown"],
        }
        if shipping:
            # Separately stated delivery; R33: non-taxable when the state's rule says so (Idaho).
            taxed = any(ln.taxable is not False for ln in shipping)
            params["shipping_cost"] = {"amount": sum(_cents(ln.amount) for ln in shipping),
                                       "tax_code": SHIPPING_TAX_CODE if taxed else NONTAXABLE_CODE, "tax_behavior": "exclusive"}
        if idempotency_key:
            params["idempotency_key"] = idempotency_key
        try:
            calc = await asyncio.to_thread(stripe.tax.Calculation.create, **params)
        except (stripe.InvalidRequestError, stripe.PermissionError, stripe.AuthenticationError) as e:  # type: ignore[attr-defined]
            if isinstance(e, stripe.InvalidRequestError) and not _not_set_up(e):  # type: ignore[attr-defined]
                # Our request is wrong (a bug), not the account: never hide it behind a $0 line.
                logger.error("stripe_tax_bad_request", error=str(e)[:300], param=getattr(e, "param", None))
                raise TaxError("We couldn't calculate tax right now; please try again")
            # The account can't calculate tax (Stripe Tax not set up / no access).
            logger.error("stripe_tax_not_configured", error=str(e)[:300], code=getattr(e, "code", None))
            if get_settings().is_production:
                raise TaxError("We couldn't calculate tax right now; please try again")
            return TaxResult(provider=UNAVAILABLE, calculation_id="", breakdown=[
                TaxBreakdown("Sales tax not calculated", f"US-{address.state}", Decimal(0),
                             sum((ln.amount for ln in lines), Decimal(0)), Decimal(0), "stripe_tax_not_configured")])
        except stripe.StripeError as e:  # type: ignore[attr-defined]
            logger.error("stripe_tax_failed", error=str(e)[:300])
            raise TaxError("We couldn't calculate tax right now; please try again")
        breakdown = parse_calculation(calc, address.state)
        if not any(b.amount for b in breakdown):
            logger.warning("stripe_tax_zero", calculation_id=calc.id,
                           reasons=sorted({b.reason for b in breakdown if b.reason}))
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


async def record_tax_transaction(provider: str, calculation_id: str, reference: str) -> dict | None:
    """After a US payment succeeds: Stripe Tax turns the calculation into a
    transaction (what it reports and files). The local stand-in records nothing.
    Idempotent at Stripe (key ``taxtx:<order id>``)."""
    if provider != "stripe_tax" or not calculation_id:
        return None
    import stripe

    stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
    try:
        tx = await asyncio.to_thread(stripe.tax.Transaction.create_from_calculation,
                                     calculation=calculation_id, reference=reference,
                                     idempotency_key=f"taxtx:{reference}")
        return {"provider": provider, "transaction_id": tx.id}
    except stripe.StripeError as e:  # type: ignore[attr-defined]
        logger.error("stripe_tax_transaction_failed", calculation_id=calculation_id, error=str(e))
        return {"provider": provider, "error": str(e)[:200]}


async def reverse_tax_transaction(tx: dict | None, reference: str, amount_minor: int, full: bool) -> dict | None:
    """A refund: reverse its share of the order's Stripe Tax transaction (all of
    it, or ``amount_minor`` tax-inclusive). Best effort, idempotent at Stripe
    (key ``taxrev:<reference>``); a failure is logged for finance."""
    if not tx or tx.get("provider") != "stripe_tax" or not tx.get("transaction_id"):
        return None
    import stripe

    stripe.api_key = get_settings().payments.STRIPE_SECRET_KEY
    params: dict = {"original_transaction": tx["transaction_id"], "reference": reference[:500],
                    "idempotency_key": f"taxrev:{reference}"}
    params.update({"mode": "full"} if full else {"mode": "partial", "flat_amount": -abs(amount_minor)})
    try:
        rev = await asyncio.to_thread(stripe.tax.Transaction.create_reversal, **params)
        return {"provider": "stripe_tax", "reversal_id": rev.id}
    except stripe.StripeError as e:  # type: ignore[attr-defined]
        logger.error("stripe_tax_reversal_failed", transaction_id=tx["transaction_id"], error=str(e))
        return {"provider": "stripe_tax", "error": str(e)[:200]}
