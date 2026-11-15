"""Round 6: every amount the backend shows people goes through shared.money,
which prints it as the website and the apps do (Intl, the country's first locale):
"$15", never "USD 15"."""
import re
from decimal import Decimal
from pathlib import Path

import pytest

from core_api.modules.pricing.api.v1.pricing import _unprocessable
from core_api.modules.pricing.service.quotes import QuoteError
from shared.money import format_money, region_of

BACKEND = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(("amount", "currency", "locale", "whole", "want"), [
    ("15", "USD", "en-US", True, "$15"),                    # the US minimum order
    ("14.5", "USD", "en-US", True, "$14.50"),               # whole never rounds real cents away
    ("15", "USD", "en-US", False, "$15.00"),
    ("124050", "INR", "en-IN", True, "₹1,24,050"),          # lakhs and crores
    ("12405000.5", "INR", "en-IN", False, "₹1,24,05,000.50"),
    ("124050", "INR", "en-US", True, "₹124,050"),           # the locale groups, not the currency
    ("124050", "USD", "en-IN", True, "$1,24,050"),
    ("124050", "USD", "es-US", True, "$124,050"),
    ("124050", "INR", "hi-IN", True, "₹1,24,050"),
    ("-56", "INR", None, False, "−₹56.00"),           # minus sign, as the clients print it
    ("1240.5", "AED", None, False, "AED 1,240.50"),         # no symbol here: the code, as Intl does
    (Decimal("617.385"), "INR", None, False, "₹617.39"),    # half up
    (199, "INR", None, True, "₹199"),                       # no locale: the currency's home market
    (0, "USD", None, True, "$0"),
])
def test_format_money(amount, currency, locale, whole, want) -> None:  # type: ignore[no-untyped-def]
    assert format_money(amount, currency, locale, whole=whole) == want


def test_region_of() -> None:
    assert [region_of(x) for x in ("en-IN", "en_US", "hi-Deva-IN", "en", None)] == ["IN", "US", "IN", None, None]


def test_min_order_refusal_is_structured() -> None:
    """The client gets the code, zone, amount and currency to word and format it in
    its own language, the English message for older clients, and the tip buttons."""
    tips = {"amounts": ["2.00", "3.00", "5.00"], "default_index": 1}
    e = QuoteError("The minimum order in Downtown is $15", code="MIN_ORDER",
                   details={"zone": "Downtown", "amount": "15.00", "currency": "USD", "tip_presets": tips})
    detail = _unprocessable(e).detail
    assert detail == {"code": "MIN_ORDER", "message": "The minimum order in Downtown is $15", "zone": "Downtown",
                      "amount": "15.00", "currency": "USD", "tip_presets": tips}
    assert _unprocessable(QuoteError("City not found")).detail == {"code": "CANNOT_QUOTE", "message": "City not found"}


# ── the guard: no hand-made money strings in backend code ────────────────────

FORBIDDEN = [
    # "{currency} {amount}": "USD 15" (f-strings and .format templates)
    (re.compile(r"\{[^{}\n]*\bcur(?:rency)?\b[^{}\n]*\}[  ]?[-−]?\{"), "a currency code next to an amount"),
    # a symbol picked by hand: sym = "₹" if currency == "INR" else "$"
    (re.compile(r"""["'][₹$€£]["']\s*(?:if|else)\b"""), "a currency symbol chosen in code"),
    (re.compile(r"""\bSYMBOLS?\s*=\s*\{"""), "a second symbol table"),
]


def _sources() -> list[Path]:
    skip = ("tests", "integration", "migrations", ".venv", "e2e", "tools")
    return [p for p in BACKEND.rglob("*.py") if not any(part in skip for part in p.relative_to(BACKEND).parts)
            and p.relative_to(BACKEND).as_posix() != "shared/money.py"]


def test_no_hand_made_money_strings() -> None:
    files = _sources()
    assert len(files) > 50  # really scanning the backend
    found = [f"{p.relative_to(BACKEND).as_posix()}:{n}: {why}: {line.strip()}"
             for p in files for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
             for rx, why in FORBIDDEN if rx.search(line)]
    assert not found, "format money with shared.money.format_money:\n" + "\n".join(found)


@pytest.mark.parametrize("line", [
    'raise QuoteError(f"The minimum order in {zone} is {country.currency} {where.min_order:.0f}")',
    'f"Above your refund limit of {intent.currency} {limit:.0f} for one order"',
    'sym = "₹" if currency == "INR" else "$"',
    'SYMBOL = {"INR": "₹", "USD": "$"}',
])
def test_the_guard_catches(line: str) -> None:
    assert any(rx.search(line) for rx, _ in FORBIDDEN)
