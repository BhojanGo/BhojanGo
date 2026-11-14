"""Quote engine. The first test is the Hyderabad worked example from
docs/specs/01-structure.md section 4, which must match to the paisa."""
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from core_api.modules.pricing.service.engine import CartLine, NotDeliverable, QuoteInputs, compute
from core_api.modules.rules.service.resolver import Candidate
from core_api.modules.rules.service.templates import slot_for, validate_params

IST = ZoneInfo("Asia/Kolkata")
THU_8PM = datetime(2026, 11, 12, 20, 0, tzinfo=IST)


def rule(family: str, template: str, params: dict, key: str | None = None, name: str | None = None) -> Candidate:
    return Candidate(
        id=uuid.uuid4(), rule_key=uuid.uuid4(), version=1, family=family, template=template,
        slot=slot_for(family, template, key), params=validate_params(family, template, params),
        scope_level="city", scope_id="IN-TG-HYD", priority=0, locked=False, status="published",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC), effective_to=None, name=name,
    )


def hyderabad_rules(**overrides) -> dict[str, Candidate]:
    rules = [
        rule("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 3, "fee": 25}, {"up_to": 6, "fee": 35}, {"up_to": 10, "fee": 50}]}),
        rule("customer_fee", "service_fee", {"percent": 2, "min": 5, "max": 15}),
        rule("customer_fee", "packaging_levy", {"amount": 10}),
        rule("customer_fee", "surge_levy", {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 15}),
        rule("customer_fee", "small_order_fee", {"below": 99, "fee": 15}),
        rule("promotion", "percent_off", {"percent": 10, "max_discount": 50, "funded_by": "platform"}, key="hyd_launch",
             name="10% off, up to ₹50"),
        rule("tax", "rate_on_lines", {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"]}, key="gst_food"),
        rule("tax", "rate_on_lines", {"label": "GST on platform fees", "rate_percent": 18,
                                      "target_lines": ["delivery_fee", "service_fee", "surge", "small_order_fee"]}, key="gst_fees"),
        rule("commission", "percent_by_tier", {"tiers": {"A": 18, "B": 15, "C": 12}, "default_tier": "B"}),
        rule("rider_pay", "base_distance_wait", {"base": 25, "per_unit": 6, "per_wait_minute": 1, "free_wait_minutes": 5}),
        rule("business", "max_radius", {"distance": 10}),
    ]
    out = {r.slot: r for r in rules}
    out.update(overrides)
    return {k: v for k, v in out.items() if v is not None}


CART = [
    CartLine("Chicken Dum Biryani · Regular · Extra raita", 1, Decimal("340.00")),
    CartLine("Paneer Tikka", 1, Decimal("220.00")),
]


def quote(**kw):
    inp = dict(currency="INR", lines=CART, distance=Decimal("4.2"), local_time=THU_8PM, tip=Decimal("20"), restaurant_tier="B")
    rules = kw.pop("rules", None) or hyderabad_rules()
    inp.update(kw)
    return compute(QuoteInputs(**inp), rules)


def test_hyderabad_worked_example_to_the_paisa() -> None:
    q = quote()
    bill = [(ln.label, ln.amount) for ln in q.lines]
    assert bill == [
        ("Food", Decimal("560.00")),
        ("10% off, up to ₹50", Decimal("-50.00")),
        ("Delivery fee", Decimal("35.00")),
        ("Service fee", Decimal("11.20")),
        ("Packaging", Decimal("10.00")),
        ("Busy-hour fee", Decimal("15.00")),
        ("GST on food", Decimal("26.00")),
        ("GST on platform fees", Decimal("11.02")),
        ("Tip for your rider", Decimal("20.00")),
    ]
    assert q.total == Decimal("638.22")
    assert q.split.restaurant == Decimal("486.00")
    assert q.split.rider == Decimal("70.20")
    assert q.split.tax == Decimal("37.02")
    assert q.split.platform == Decimal("45.00")
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform == q.total
    assert q.split.detail["commission"] == Decimal("84.00")
    assert next(ln for ln in q.lines if ln.code == "promotion").funded_by == "platform"
    assert len(q.rules_used) == 10  # every rule that priced this order is recorded


def test_design_board_live_column() -> None:
    """The simulator on the board: live v3 charges ₹30 for 3–6 km -> ₹632.32, platform ₹40."""
    live = hyderabad_rules(delivery_fee=rule("delivery_fee", "distance_slabs",
                                             {"slabs": [{"up_to": 3, "fee": 20}, {"up_to": 6, "fee": 30}, {"up_to": 9, "fee": 50}]}))
    q = quote(rules=live)
    assert q.line("tax") == Decimal("36.12")  # 26.00 + 10.12
    assert q.total == Decimal("632.32")
    assert (q.split.restaurant, q.split.rider, q.split.platform) == (Decimal("486.00"), Decimal("70.20"), Decimal("40.00"))


def test_surge_only_in_its_window() -> None:
    q = quote(local_time=THU_8PM.replace(hour=13))
    assert q.line("surge") == 0
    assert q.total == Decimal("638.22") - Decimal("15.00") - Decimal("2.70")  # surge and its 18% GST


def test_window_wrapping_midnight() -> None:
    rules = hyderabad_rules(**{"customer_fee:late_night_fee": rule(
        "customer_fee", "late_night_fee", {"window": {"start": "23:00", "end": "02:00"}, "amount": 20})})
    assert quote(rules=rules, local_time=THU_8PM.replace(hour=1)).line("late_night_fee") == 20
    assert quote(rules=rules, local_time=THU_8PM.replace(hour=23, minute=30)).line("late_night_fee") == 20
    assert quote(rules=rules, local_time=THU_8PM.replace(hour=3)).line("late_night_fee") == 0


@pytest.mark.parametrize(("distance", "fee"), [("0.5", "25.00"), ("3", "25.00"), ("3.01", "35.00"), ("6", "35.00"), ("9.9", "50.00")])
def test_distance_slabs(distance, fee) -> None:
    assert quote(distance=Decimal(distance)).line("delivery_fee") == Decimal(fee)


def test_too_far() -> None:
    with pytest.raises(NotDeliverable):
        quote(distance=Decimal("10.5"))  # beyond max_radius
    rules = hyderabad_rules(**{"business:max_radius": None})
    with pytest.raises(NotDeliverable):
        quote(rules=rules, distance=Decimal("12"))  # beyond the last slab


def test_service_fee_min_and_max() -> None:
    small = [CartLine("Chai", 2, Decimal("40.00"))]  # 80 -> 2% = 1.60 -> min 5
    q = quote(lines=small)
    assert q.line("service_fee") == Decimal("5.00")
    assert q.line("small_order_fee") == Decimal("15.00")  # below ₹99
    big = [CartLine("Family Pack Biryani", 2, Decimal("980.00"))]  # 1960 -> 39.20 -> max 15
    assert quote(lines=big).line("service_fee") == Decimal("15.00")


def test_promotions_best_offer_codes_and_budgets() -> None:
    flat = rule("promotion", "flat_off", {"amount": 75, "funded_by": "restaurant", "min_subtotal": 500, "code": "FEAST75"}, key="feast")
    rules = hyderabad_rules(**{flat.slot: flat})
    assert quote(rules=rules).line("promotion") == Decimal("-50.00")  # code not given: only the auto 10%
    q = quote(rules=rules, promo_code="feast75")
    assert q.line("promotion") == Decimal("-75.00")  # the better offer wins, not both
    assert q.split.detail["restaurant_funded_offers"] == Decimal("75.00")
    assert q.split.restaurant == Decimal("560.00") + 10 - 84 - 75

    launch = rules["promotion:percent_off:hyd_launch"]
    spent = {str(launch.rule_key): Decimal("99980")}  # ₹20 left of ₹1,00,000
    launch_capped = hyderabad_rules(**{launch.slot: rule("promotion", "percent_off",
        {"percent": 10, "max_discount": 50, "funded_by": "platform", "budget_cap": 100000}, key="hyd_launch")})
    capped_rule = launch_capped["promotion:percent_off:hyd_launch"]
    q = quote(rules=launch_capped, promo_spent={str(capped_rule.rule_key): Decimal("99980")})
    assert q.line("promotion") == Decimal("-20.00")
    q = quote(rules=launch_capped, promo_spent={str(capped_rule.rule_key): Decimal("100000")})
    assert q.line("promotion") == 0
    assert spent  # (kept for readability)


def test_weekly_cap_on_an_offer_the_restaurant_funds() -> None:
    flat = rule("promotion", "flat_off", {"amount": 75, "funded_by": "restaurant", "weekly_cap": 100}, key="r_weekly")
    rules = hyderabad_rules(**{flat.slot: flat})
    k = str(flat.rule_key)
    assert quote(rules=rules).line("promotion") == Decimal("-75.00")
    # ₹70 used this week: ₹30 of the offer left, so the platform's ₹50 launch offer is better now.
    assert quote(rules=rules, promo_spent_week={k: Decimal("70")}).line("promotion") == Decimal("-50.00")
    assert quote(rules=rules, promo_spent_week={k: Decimal("30")}).line("promotion") == Decimal("-70.00")
    assert quote(rules=rules, promo_spent_week={k: Decimal("100")}).line("promotion") == Decimal("-50.00")


def test_first_order_only_for_first_orders() -> None:
    fo = rule("promotion", "first_order", {"percent": 50, "max_discount": 100, "funded_by": "platform"}, key="welcome")
    rules = hyderabad_rules(**{fo.slot: fo})
    assert quote(rules=rules).line("promotion") == Decimal("-50.00")
    assert quote(rules=rules, first_order=True).line("promotion") == Decimal("-100.00")


def test_free_delivery_stacks_with_a_discount_and_untaxes_the_fee() -> None:
    fd = rule("promotion", "free_delivery", {"funded_by": "restaurant"}, key="kitchen_free_delivery")
    q = quote(rules=hyderabad_rules(**{fd.slot: fd}))
    promos = [ln for ln in q.lines if ln.code == "promotion"]
    assert [p.amount for p in promos] == [Decimal("-50.00"), Decimal("-35.00")]
    # GST on fees now only on service fee + surge: 26.20 x 18% = 4.716 -> 4.72
    assert next(ln for ln in q.lines if ln.label == "GST on platform fees").amount == Decimal("4.72")
    assert q.split.restaurant == Decimal("486.00") - Decimal("35.00")


def test_restaurant_collected_tax_goes_to_the_restaurant() -> None:
    rest = rule("tax", "rate_on_lines", {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"],
                                         "collected_by": "restaurant"}, key="gst_food")
    q = quote(rules=hyderabad_rules(**{rest.slot: rest}))
    assert q.split.restaurant == Decimal("512.00")  # 486 + 26
    assert q.split.restaurant + q.split.rider + q.split.platform + Decimal("11.02") == q.total


def test_rider_waiting_pay_after_free_minutes() -> None:
    q = quote(wait_minutes=Decimal("12"))
    assert q.split.rider == Decimal("70.20") + 7  # 7 paid minutes at ₹1


def test_external_tax_marks_quote_pending() -> None:
    us = {
        "delivery_fee": rule("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 2, "fee": "1.99"}, {"up_to": 4, "fee": "3.49"}]}),
        "tax:external": rule("tax", "external", {"provider": "stripe_tax"}),
    }
    q = compute(QuoteInputs(currency="USD", lines=[CartLine("Bowl", 2, Decimal("12.50"))], distance=Decimal("1.5"),
                            local_time=datetime(2026, 11, 12, 18, 0, tzinfo=ZoneInfo("America/Boise"))), us)
    assert q.tax_pending and q.total == Decimal("26.99")


def test_empty_cart_and_no_delivery_rule() -> None:
    with pytest.raises(NotDeliverable):
        quote(lines=[])
    with pytest.raises(NotDeliverable):
        quote(rules=hyderabad_rules(delivery_fee=None))


def test_tax_lines_show_rate_and_base() -> None:
    q = quote()
    food_gst = next(ln for ln in q.lines if ln.label == "GST on food")
    fee_gst = next(ln for ln in q.lines if ln.label == "GST on platform fees")
    assert food_gst.detail == {"rate_percent": "5", "base": "520.00", "collected_by": "platform", "targets": "food,packaging"}
    assert fee_gst.detail["base"] == "61.20" and fee_gst.detail["rate_percent"] == "18"
    assert "delivery_fee" in fee_gst.detail["targets"]


def test_inclusive_tax_is_shown_but_not_added() -> None:
    incl = rule("tax", "rate_on_lines", {"label": "GST on food", "rate_percent": 5, "target_lines": ["food"],
                                         "inclusive": True}, key="gst_food")
    q = quote(rules=hyderabad_rules(**{incl.slot: incl}))
    shown = next(ln for ln in q.lines if ln.code == "tax_included")
    assert shown.amount == 0 and shown.detail["included"] == "24.29"
    assert shown.label == "GST on food (included in prices)"
    assert q.split.tax == Decimal("11.02") + Decimal("24.29")  # 510 - 510/1.05 = 24.285... -> 24.29


def test_external_tax_lines_from_the_provider() -> None:
    from dataclasses import replace

    from core_api.modules.pricing.service.engine import ExternalTax, taxable_amounts

    us = {
        "delivery_fee": rule("delivery_fee", "distance_slabs", {"slabs": [{"up_to": 2, "fee": "1.99"}, {"up_to": 4, "fee": "3.49"}]}),
        "customer_fee:service_fee": rule("customer_fee", "service_fee", {"percent": 5, "min": 1, "max": 5}),
        "tax:external": rule("tax", "external", {"provider": "stripe_tax"}),
    }
    inp = QuoteInputs(currency="USD", lines=[CartLine("Bowl", 2, Decimal("12.50"))], distance=Decimal("1.5"),
                      local_time=datetime(2026, 11, 12, 18, 0, tzinfo=ZoneInfo("America/Boise")), tip=Decimal("3"))
    first = compute(inp, us)
    assert first.tax_pending
    assert taxable_amounts(first) == {"food": Decimal("25.00"), "delivery_fee": Decimal("1.99"), "service_fee": Decimal("1.25")}

    ext = [ExternalTax("Idaho sales tax", Decimal("6"), Decimal("28.24"), Decimal("1.69"), "US-ID", "local", "taxcalc_x")]
    q = compute(replace(inp, external_tax=ext), us)
    assert not q.tax_pending
    tax = next(ln for ln in q.lines if ln.code == "tax")
    assert (tax.label, tax.amount, tax.detail["rate_percent"], tax.detail["base"]) == ("Idaho sales tax", Decimal("1.69"), "6", "28.24")
    assert q.total == Decimal("25.00") + Decimal("1.99") + Decimal("1.25") + Decimal("1.69") + Decimal("3.00")
    assert q.split.tax == Decimal("1.69")
    assert q.split.restaurant + q.split.rider + q.split.tax + q.split.platform == q.total


# ── commission precedence: restaurant > city > country (one rate slot) ─────────

def _at(c: Candidate, level: str, sid: str, **kw) -> Candidate:  # type: ignore[no-untyped-def]
    from dataclasses import replace

    return replace(c, scope_level=level, scope_id=sid, **kw)


def test_commission_rate_most_specific_wins_and_ended_override_falls_back() -> None:
    from core_api.modules.rules.service.resolver import Context, resolve

    country = _at(rule("commission", "percent_by_tier", {"tiers": {"A": 25, "B": 20, "C": 15}, "default_tier": "B"}), "country", "US")
    city = _at(rule("commission", "percent", {"percent": 15}), "city", "US-ID-BOI")
    kitchen = _at(rule("commission", "percent", {"percent": 12}), "restaurant", "r1")
    flat = _at(rule("commission", "flat_per_order", {"amount": 1}), "country", "US")
    ctx = Context(country="US", region="US-ID", city="US-ID-BOI", restaurant_id="r1")
    at = datetime(2026, 11, 14, tzinfo=UTC)

    def pct(cands: list[Candidate]) -> Decimal:
        picked = resolve(cands, ctx, at)
        q = quote(rules={**hyderabad_rules(), **{s: c for s, c in picked.items() if s.startswith("commission")}})
        return q.split.detail["commission"]

    food = Decimal("560.00")
    assert pct([country, city, kitchen, flat]) == food * 12 / 100 + 1          # the restaurant's own deal, plus the flat fee
    assert pct([country, city, flat]) == food * 15 / 100 + 1                   # no restaurant deal: the city's
    assert pct([country, flat]) == food * 20 / 100 + 1                         # neither: the country's, tier B
    ended = _at(kitchen, "restaurant", "r1", effective_to=datetime(2026, 11, 1, tzinfo=UTC))
    assert pct([country, city, ended, flat]) == food * 15 / 100 + 1            # an ended override falls back to the city
