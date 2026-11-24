"""R33: Idaho's taxable lines as a state tax setting (food and the platform fee, a service charge, are taxable;
a separately stated delivery fee and the tip are not), the same answer from the local stand-in and the Stripe
Tax mapping, and the busy-hour fee: off in every seed, and 100% the delivery partner's if it is ever on."""
import asyncio
import importlib
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from core_api.modules.payments.service import tax as tx
from core_api.modules.pricing.service.engine import CartLine, ExternalTax, QuoteInputs, compute
from core_api.modules.pricing.service.quotes import tax_lines, taxable_set
from core_api.modules.pricing.tests.test_delivery_bands import BOISE_AT, HYD_AT, india, us
from core_api.modules.pricing.tests.test_fee_model_v2 import BOISE, NOW, rule
from core_api.modules.rules.service.resolver import resolve

IDAHO = ["food", "packaging", "platform_fee", "service_fee", "small_order_fee", "late_night_fee"]
ITEMS = [CartLine("A", 1, Decimal("3.99")), CartLine("B", 1, Decimal("10.99")), CartLine("C", 1, Decimal("22.00"))]


def idaho(rules: dict) -> dict:
    """The rules with Idaho's state tax setting (the region rule beats the country's in the tax:external slot)."""
    return {**rules, "tax:external": rule("tax", "external", {"provider": "stripe_tax", "taxable_lines": IDAHO},
                                          "region", "US-ID")}


def taxed(inp: QuoteInputs, rules: dict):  # type: ignore[no-untyped-def]
    """The real path: price, send the lines the rule marks to the tax provider (the local stand-in), price again."""
    first = compute(inp, rules)
    assert first.tax_pending
    calc = asyncio.run(tx.LocalTax().calculate("USD", tax_lines(inp, first, taxable_set(rules)),
                                               tx.TaxAddress("US", "ID", "Boise", "83702")))
    ext = [ExternalTax(b.label, b.rate_percent, b.taxable_amount, b.amount, b.jurisdiction, calc.provider,
                       calc.calculation_id) for b in calc.breakdown]
    return compute(replace(inp, external_tax=ext), rules)


def split_adds_up(q) -> None:  # type: ignore[no-untyped-def]
    s = q.split
    assert s.restaurant + s.rider + s.tax + s.platform + s.card_fee == q.total


def test_boise_delivery_3_miles() -> None:
    """3.99 + 10.99 + 22.00, 3.00 mi, card: platform 3.70, delivery 4.50 (untaxed), tax 2.44 (6% of 40.68),
    total 47.62, card fee 1.68, restaurant 35.30, partner 4.50."""
    q = taxed(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT), idaho(us()))
    line = {ln.code: ln.amount for ln in q.lines}
    assert (line["platform_fee"], line["delivery_fee"], line["tax"]) == (Decimal("3.70"), Decimal("4.50"), Decimal("2.44"))
    tax = next(ln for ln in q.lines if ln.code == "tax")
    assert tax.detail["base"] == "40.68" and tax.detail["targets"] == "food,platform_fee"  # no delivery_fee
    assert q.total == Decimal("47.62")
    assert q.split.card_fee == Decimal("1.68")  # 2.9% of 47.62 + 0.30 = 1.6810
    assert q.split.restaurant == Decimal("35.30")
    assert q.split.rider == Decimal("4.50")
    assert q.split.tax == Decimal("2.44") and q.split.platform == Decimal("3.70")
    split_adds_up(q)


def test_boise_pickup() -> None:
    """Pickup: platform 1.85 (5%), tax 2.33 (6% of 38.83), total 41.16, card fee 1.49, restaurant 35.49."""
    rules = idaho({**us(), "fee:pickup_platform_fee_pct": rule("fee", "pickup_platform_fee_pct", {"percent": 5})})
    q = taxed(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("0"), local_time=BOISE_AT, fulfillment="pickup"), rules)
    line = {ln.code: ln.amount for ln in q.lines}
    assert "delivery_fee" not in line
    assert (line["platform_fee"], line["tax"]) == (Decimal("1.85"), Decimal("2.33"))
    assert q.total == Decimal("41.16")
    assert q.split.card_fee == Decimal("1.49")  # 2.9% of 41.16 + 0.30 = 1.4936
    assert q.split.restaurant == Decimal("35.49") and q.split.rider == Decimal("0")
    split_adds_up(q)


def test_tip_is_never_taxed() -> None:
    inp = QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT, tip=Decimal("5"))
    q = taxed(inp, idaho(us()))
    assert next(ln for ln in q.lines if ln.code == "tax").amount == Decimal("2.44")  # same as without the tip
    assert q.split.rider == Decimal("9.50")


def test_without_a_state_setting_the_provider_decides() -> None:
    """No taxable_lines (a state not set up yet): every line goes, and the stand-in taxes its default set."""
    first = compute(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT), us())
    sent = tax_lines(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT), first,
                     taxable_set(us()))
    assert {ln.taxable for ln in sent} == {None}


def test_the_state_setting_is_resolved_per_state() -> None:
    """Idaho's region rule wins for Boise; another state keeps the country rule (no list)."""
    from core_api.modules.rules.service.resolver import Context

    country = rule("tax", "external", {"provider": "stripe_tax"})
    state = rule("tax", "external", {"provider": "stripe_tax", "taxable_lines": IDAHO}, "region", "US-ID")
    assert taxable_set(resolve([country, state], BOISE, NOW)) == set(IDAHO)
    oregon = Context(country="US", region="US-OR", city="US-OR-PDX", restaurant_id="r2")
    assert taxable_set(resolve([country, state], oregon, NOW)) is None


def test_stripe_mapping_matches_the_rule() -> None:
    """What Stripe Tax is sent for an Idaho order: food as prepared food, the platform fee as part of the meal
    (taxable), the delivery fee as a separately stated shipping line with the non-taxable code."""
    import stripe

    q = compute(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT), idaho(us()))
    lines = tax_lines(QuoteInputs(currency="USD", lines=ITEMS, distance=Decimal("3.00"), local_time=BOISE_AT), q,
                      taxable_set(idaho(us())))
    sent: dict = {}

    class Calc:
        id, tax_breakdown = "taxcalc_1", []

    def create(**kw):  # type: ignore[no-untyped-def]
        sent.update(kw)
        return Calc()

    mp = pytest.MonkeyPatch()
    mp.setattr(stripe.tax.Calculation, "create", create)
    try:
        asyncio.run(tx.StripeTax().calculate("USD", lines, tx.TaxAddress("US", "ID", "Boise", "83702")))
    finally:
        mp.undo()
    codes = {li["reference"]: (li["amount"], li["tax_code"]) for li in sent["line_items"]}
    assert codes["platform_fee"] == (370, tx.MEAL_CODE)
    assert {c for r, (_, c) in codes.items() if r.startswith("food-")} == {"txcd_40060003"}
    assert sum(a for r, (a, _) in codes.items() if r.startswith("food-")) == 3698
    assert sent["shipping_cost"] == {"amount": 450, "tax_code": tx.NONTAXABLE_CODE, "tax_behavior": "exclusive"}
    # A state whose rule taxes delivery keeps Stripe's shipping code (Stripe applies that state's shipping rule).
    taxed_delivery = [replace(ln, taxable=True) if ln.what == "delivery_fee" else ln for ln in lines]
    mp = pytest.MonkeyPatch()
    mp.setattr(stripe.tax.Calculation, "create", create)
    try:
        asyncio.run(tx.StripeTax().calculate("USD", taxed_delivery, tx.TaxAddress("US", "ID", "Boise", "83702")))
    finally:
        mp.undo()
    assert sent["shipping_cost"]["tax_code"] == tx.SHIPPING_TAX_CODE


def test_stripe_codes_per_line() -> None:
    L = tx.TaxableLine
    assert tx.stripe_code(L("platform_fee", Decimal(1), taxable=True)) == tx.MEAL_CODE
    assert tx.stripe_code(L("platform_fee", Decimal(1), taxable=False)) == tx.NONTAXABLE_CODE
    assert tx.stripe_code(L("platform_fee", Decimal(1))) == "txcd_20030000"  # no rule: Stripe decides
    assert tx.stripe_code(L("packaging", Decimal(1), taxable=True)) == "txcd_99999999"
    assert tx.stripe_code(L("food-1-x", Decimal(1), kind="food", taxable=True)) == "txcd_40060003"


# ── busy-hour fee ────────────────────────────────────────────────────────────

SURGE_15 = {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 15}
EVENING = HYD_AT.replace(hour=20)


def hyd(amount: int) -> dict:
    return {**india(), "customer_fee:surge_levy": rule("customer_fee", "surge_levy", {**SURGE_15, "amount": amount},
                                                       "city", "IN-TG-HYD")}


def hyd_order() -> QuoteInputs:
    return QuoteInputs(currency="INR", lines=[CartLine("Thali", 1, Decimal("300"))], distance=Decimal("2.50"),
                       local_time=EVENING, payment_method="upi")


def test_busy_hour_fee_when_on_goes_100_percent_to_the_delivery_partner() -> None:
    off, on = compute(hyd_order(), hyd(0)), compute(hyd_order(), hyd(15))
    assert "surge" not in {ln.code for ln in off.lines}  # 0 = off: no line at all
    assert next(ln.amount for ln in on.lines if ln.code == "surge") == Decimal("15")
    assert on.split.rider - off.split.rider == Decimal("15")  # every rupee of it
    # BhojanGo keeps nothing of it (the GST on it is in split.tax, for the government)
    assert on.split.platform == off.split.platform
    assert on.split.restaurant == off.split.restaurant
    assert on.split.detail["busy_hour_fee_to_partner"] == Decimal("15")
    assert on.split.detail["delivery_fee_to_partner"] == off.split.detail["delivery_fee_to_partner"] + Decimal("15")
    split_adds_up(on)


def test_busy_hour_fee_is_off_in_every_seed() -> None:
    seed = Path(__file__).resolve().parents[5] / "tools" / "seed"
    sys.path.insert(0, str(seed))
    try:
        data = importlib.import_module("data")
        md = importlib.import_module("markets_data")
    finally:
        sys.path.remove(str(seed))
    for rules in (data.RULES, md.rules()):
        surges = [r for r in rules if r[0] == "customer_fee" and r[1] == "surge_levy"]
        assert all(Decimal(str(r[6]["amount"])) == 0 for r in surges), surges
    idaho_rule = [r for r in data.RULES if r[:2] == ("tax", "external") and r[5] == "US-ID"]
    assert [r[6]["taxable_lines"] for r in idaho_rule] == [IDAHO]
    assert "delivery_fee" not in IDAHO and "surge" not in IDAHO
