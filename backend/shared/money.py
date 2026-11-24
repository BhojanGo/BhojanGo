"""One money formatter for every amount the backend says to people (round 6).

Errors, notifications, receipts and emails all print money through
``format_money``, the same way the website and the apps do
(apps/web/src/lib/format.ts ``money``, packages/mobile-core/src/locale.ts
``formatMoney``, both Intl.NumberFormat with style "currency"):

- the country's first Markets locale (``formatLocale``) decides the grouping:
  en-IN groups in lakhs and crores (₹1,24,050), others in thousands ($124,050);
- the symbol comes first (₹, $, €, £); a currency without one here prints its
  code, "AED 1,240.50", as Intl does;
- two decimals, or none for a whole amount when ``whole`` is set ("$15", but
  "$14.50"): never round real cents away;
- a negative amount starts with a minus sign (U+2212), "−₹56.00", as the
  clients print it.

Never write "{currency} {amount}" in a message: a US customer reads "USD 15"
(core_api/modules/pricing/tests/test_money_format.py fails on that pattern).
Markets' locales today all write "1,234.50"; a locale with a decimal comma would
need its separators added here.

Stdlib only.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
# The locale to use when the caller has no country to hand: the currency's home market.
HOME_LOCALE = {"INR": "en-IN", "USD": "en-US"}
MINUS = "−"
_REGION = re.compile(r"^[a-z]{2,3}(?:[-_][A-Za-z]{4})?[-_]([A-Za-z]{2})\b")


def region_of(locale: str | None) -> str | None:
    """en-IN / en_IN / hi-Deva-IN -> IN; a bare language -> None."""
    m = _REGION.match(locale or "")
    return m.group(1).upper() if m else None


def _group(digits: str, indian: bool) -> str:
    if not indian or len(digits) <= 3:
        return f"{int(digits):,}"
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + groups + [tail])


def format_money(amount: Decimal | float | int | str, currency: str, locale: str | None = None, *,
                 whole: bool = False) -> str:
    """"₹1,24,050.00", "$1,240.50", "$15" (whole), "−₹56.00", "AED 1,240.50".

    ``locale``: the country's first Markets locale (formatLocale); None means the
    currency's home market (en-IN for INR, en-US otherwise)."""
    loc = locale or HOME_LOCALE.get(currency, "en-US")
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = MINUS if value < 0 else ""
    value = abs(value)
    drop_cents = whole and value == value.to_integral_value()
    digits, cents = f"{value:.2f}".split(".")
    body = _group(digits, region_of(loc) == "IN") + ("" if drop_cents else f".{cents}")
    symbol = SYMBOLS.get(currency)
    return f"{sign}{symbol}{body}" if symbol else f"{sign}{currency} {body}"


def customer_money(amount: Decimal | float | int | str, currency: str, locale: str | None = None) -> str:
    """R36: money as a customer reads it. India shows whole rupees (₹289, never ₹289.40): rounded half
    up for display only, the amount itself (and what's charged) stays exact. Other currencies keep cents.
    Restaurants' and delivery partners' statements keep ``format_money`` (exact paise)."""
    if currency == "INR":
        whole = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return format_money(whole, currency, locale, whole=True)
    return format_money(amount, currency, locale)


def paid_after_refunds(total: object, refunds: list[dict]) -> tuple[Decimal, Decimal]:
    """(refunded, paid): what came back on an order and what the customer paid after it (R27: the
    receipt's "Total paid"). Never below zero; ``refunds`` [{"amount": major units}]."""
    cent = Decimal("0.01")
    t = Decimal(str(total or 0)).quantize(cent)
    refunded = min(sum((Decimal(str(r.get("amount") or 0)) for r in refunds), Decimal(0)).quantize(cent), t)
    return refunded, (t - refunded).quantize(cent)
