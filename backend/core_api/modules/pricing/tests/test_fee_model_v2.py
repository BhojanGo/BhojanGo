"""R29 fee model v2: platform fee on food, card fee off the restaurant's payout, delivery fee and tip to the
partner, each setting inherited Country -> State -> City -> Restaurant (most specific wins)."""
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from core_api.modules.pricing.service import fees
from core_api.modules.pricing.service.engine import CartLine, ExternalTax, QuoteInputs, compute
from core_api.modules.rules.service.resolver import Candidate, Context, resolve
from core_api.modules.rules.service.templates import slot_for, validate_params

T0 = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
BOISE = Context(country="US", region="US-ID", city="US-ID-BOI", restaurant_id="r1")


def rule(family: str, template: str, params: dict, level: str = "country", scope_id: str = "US",
         start: datetime = T0, end: datetime | None = None) -> Candidate:
    return Candidate(
        id=uuid.uuid4(), rule_key=uuid.uuid4(), version=1, family=family, template=template,
        slot=slot_for(family, template, None), params=validate_params(family, template, params),
        scope_level=level, scope_id=scope_id, priority=0, locked=False, status="published",
        effective_from=start, effective_to=end,
    )


def pct(*field_rules: Candidate, at: datetime = NOW) -> dict:
    s = fees.settings(resolve(list(field_rules), BOISE, at))["platform_fee_pct"]
    return {"value": s.value["percent"] if s.value else None, "level": s.source.level if s.source else None}


# ── A: resolution ────────────────────────────────────────────────────────────

US_10 = rule("fee", "platform_fee_pct", {"percent": 10})
IDAHO_9 = rule("fee", "platform_fee_pct", {"percent": 9}, "region", "US-ID")


def test_a_state_beats_country_and_an_unset_city_inherits() -> None:
    assert pct(US_10) == {"value": "10", "level": "country"}
    assert pct(US_10, IDAHO_9) == {"value": "9", "level": "region"}  # Boise has no rule: Idaho's 9%


def test_a_restaurant_override_wins() -> None:
    kitchen = rule("fee", "platform_fee_pct", {"percent": 7}, "restaurant", "r1")
    assert pct(US_10, IDAHO_9, kitchen) == {"value": "7", "level": "restaurant"}
    other = rule("fee", "platform_fee_pct", {"percent": 5}, "restaurant", "someone-else")
    assert pct(US_10, IDAHO_9, other) == {"value": "9", "level": "region"}


def test_a_expired_rule_ignored_and_future_rule_not_yet_applied() -> None:
    expired = rule("fee", "platform_fee_pct", {"percent": 9}, "region", "US-ID", end=NOW - timedelta(days=1))
    assert pct(US_10, expired) == {"value": "10", "level": "country"}
    future = rule("fee", "platform_fee_pct", {"percent": 9}, "region", "US-ID", start=NOW + timedelta(days=1))
    assert pct(US_10, future) == {"value": "10", "level": "country"}
    assert pct(US_10, future, at=NOW + timedelta(days=2)) == {"value": "9", "level": "region"}


def test_a_each_setting_inherits_on_its_own() -> None:
    """Idaho sets only the percentage; the minimum, commission and card fee still come from the USA."""
    rules = [US_10, IDAHO_9, rule("fee", "min_platform_fee", {"amount": "0.99"}),
             rule("commission", "percent", {"percent": 0}), rule("fee", "card_fee_estimate", {"percent": "2.9", "fixed": "0.30"})]
    s = fees.settings(resolve(rules, BOISE, NOW))
    assert (s["platform_fee_pct"].value, s["platform_fee_pct"].source.level) == ({"percent": "9"}, "region")
    assert (s["min_platform_fee"].value, s["min_platform_fee"].source.level) == ({"amount": "0.99"}, "country")
    assert (s["restaurant_commission_pct"].value, s["restaurant_commission_pct"].source.scope_id) == ({"percent": "0"}, "US")
    assert s["card_fee_estimate"].value == {"percent": "2.9", "fixed": "0.30"}


# ── B, C: the money ──────────────────────────────────────────────────────────

def us_rules(**extra: Candidate) -> dict[str, Candidate]:
    rs = [
        rule("delivery_fee", "flat", {"amount": "3.99"}),
        rule("fee", "platform_fee_pct", {"percent": 10}),
        rule("fee", "min_platform_fee", {"amount": "0.99"}),
        rule("commission", "percent", {"percent": 0}),
        rule("fee", "card_fee_estimate", {"percent": "2.9", "fixed": "0.30"}),
        rule("tax", "external", {"provider": "stripe_tax"}),
    ]
    out = {r.slot: r for r in rs}
    out.update(extra)
    return out


def priced(items: list[Decimal], tax: Decimal | None, tip: Decimal = Decimal(0), rules: dict | None = None):  # type: ignore[no-untyped-def]
    inp = QuoteInputs(currency="USD", lines=[CartLine(f"Dish {i}", 1, p) for i, p in enumerate(items)], distance=Decimal("1.2"),
                      local_time=datetime(2026, 11, 22, 12, 0, tzinfo=ZoneInfo("America/Boise")), tip=tip)
    first = compute(inp, rules or us_rules())
    assert first.tax_pending
    # The tax provider decides what's taxable; here it taxes the food only, at 6%.
    food = first.food_subtotal
    amount = (food * Decimal("0.06")).quantize(Decimal("0.01")) if tax is None else tax
    ext = [ExternalTax("Idaho sales tax", Decimal("6"), food, amount, "US-ID", "local", "taxcalc_test")]
    return compute(replace(inp, external_tax=ext), rules or us_rules())


def test_b_exact_order() -> None:
    q = priced([Decimal("3.99"), Decimal("10.99"), Decimal("22.00")], tax=None)
    line = {ln.code: ln.amount for ln in q.lines}
    assert q.food_subtotal == Decimal("36.98")
    assert line["platform_fee"] == Decimal("3.70")
    assert line["tax"] == Decimal("2.22")
    assert line["delivery_fee"] == Decimal("3.99")
    assert q.total == Decimal("46.89")
    assert q.split.card_fee == Decimal("1.66")
    assert q.split.detail["commission"] == Decimal("0")
    assert q.split.restaurant == Decimal("35.32")
    assert q.split.rider == Decimal("3.99")
    assert q.split.tax == Decimal("2.22")
    assert q.split.platform == Decimal("3.70")  # BhojanGo keeps the platform fee
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform + q.split.card_fee == q.total


def test_b_tip_goes_to_the_partner_and_is_left_out_of_the_card_fee() -> None:
    q = priced([Decimal("3.99"), Decimal("10.99"), Decimal("22.00")], tax=None, tip=Decimal("5.00"))
    assert q.total == Decimal("51.89")
    assert q.split.card_fee == Decimal("1.66")  # 2.9% of 46.89 (51.89 less the 5.00 tip) + 0.30
    assert q.split.rider == Decimal("8.99")
    assert q.split.restaurant == Decimal("35.32")


def test_c_minimum_platform_fee() -> None:
    q = priced([Decimal("6.00")], tax=Decimal("0.36"))
    assert next(ln.amount for ln in q.lines if ln.code == "platform_fee") == Decimal("0.99")  # not 0.60


def test_guaranteed_pay_top_up_never_pays_a_partner_less() -> None:
    guaranteed = rule("rider_pay", "base_distance_wait", {"base": "3.00", "per_unit": "1.00"})  # 3.00 + 1.2 mi = 4.20
    q = priced([Decimal("20.00")], tax=Decimal("1.20"), rules=us_rules(**{guaranteed.slot: guaranteed}))
    assert q.split.detail["delivery_fee_to_partner"] == Decimal("3.99")
    assert q.split.detail["rider_top_up"] == Decimal("0.21")  # BhojanGo funds it, out of the platform fee
    assert q.split.rider == Decimal("4.20")
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform + q.split.card_fee == q.total


def test_integer_cents_half_up() -> None:
    assert fees.percent_of(3698, 10) == 370  # 369.8
    assert fees.percent_of(25, 10) == 3  # 2.5 rounds half up
    assert fees.platform_fee_cents(600, 10, 99) == 99
    assert fees.platform_fee_cents(0, 10, 99) == 0
    assert fees.card_fee_cents(4689, 0, "2.9", 30) == 166
    assert fees.to_cents("46.885") == 4689
