"""Restaurant-friendly commission model — platform revenue per order.

Pure functions so they are easy to unit-test and free of side effects.
Money is handled as exact Decimals in major units (dollars/rupees).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

PRICING_MODELS = ("percentage_commission", "flat_fee_per_order", "monthly_subscription")

_CENTS = Decimal("0.01")


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)


def platform_revenue(
    pricing_model: str,
    subtotal: object,
    *,
    commission_rate: object = 0,
    flat_fee_per_order: object = 0,
    monthly_subscription_fee: object = 0,
) -> Decimal:
    """Platform revenue earned from a single order, by the restaurant's pricing model.

    - percentage_commission: subtotal * commission_rate (rate is a 0..1 fraction)
    - flat_fee_per_order:     a fixed fee per order
    - monthly_subscription:   0 per order (revenue is the monthly fee, billed separately)
    """
    sub = _money(subtotal)
    if pricing_model == "flat_fee_per_order":
        return _money(flat_fee_per_order)
    if pricing_model == "monthly_subscription":
        return Decimal("0.00")
    # default + percentage_commission
    rate = Decimal(str(commission_rate))
    return _money(sub * rate)


def restaurant_payout(subtotal: object, platform_fee: object) -> Decimal:
    """What the restaurant receives for the order (subtotal minus platform revenue)."""
    return _money(_money(subtotal) - _money(platform_fee))
