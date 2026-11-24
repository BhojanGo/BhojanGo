"""R37: BhojanGo-funded offers run only while the month's budget can pay for them; the admin's
cost-per-order vs platform-fee warning (pricing/service/offer_budget.py, rules/api/v1/offers.py)."""
from datetime import date, datetime
from decimal import Decimal

import pytest

from core_api.modules.pricing.service import offer_budget as B
from core_api.modules.pricing.tests.test_engine import THU_8PM, hyderabad_rules, quote, rule
from core_api.modules.rules.api.v1.offers import worst_case

D = Decimal


def promo(q) -> list:  # type: ignore[no-untyped-def]
    return [(ln.label, ln.amount, ln.funded_by) for ln in q.lines if ln.code == "promotion"]


def flat3(funded_by: str = "platform"):  # type: ignore[no-untyped-def]
    return rule("promotion", "flat_off", {"amount": 3, "funded_by": funded_by}, key="r37", name="₹3 off")


def test_budget_10_offer_3_three_orders_then_none() -> None:
    """The engine side of "budget 10, offer 3": the offer applies while 3 or more is left."""
    rules = hyderabad_rules(**{"promotion:percent_off:hyd_launch": None, "promotion:flat_off:r37": flat3()})
    left, given = D("10"), []
    for _ in range(4):
        q = quote(rules=rules, platform_offer_left=left)
        p = promo(q)
        given.append(bool(p))
        if p:
            left += p[0][1]  # the line is negative
    assert given == [True, True, True, False] and left == D("1.00")


def test_no_budget_no_bhojango_offer_but_the_restaurants_still_runs() -> None:
    assert promo(quote(platform_offer_left=D("0"))) == []  # the seeded launch offer (platform) is off
    assert promo(quote(platform_offer_left=None))  # unit tests and drafts without a budget check: as before
    own = hyderabad_rules(**{"promotion:percent_off:hyd_launch": None, "promotion:flat_off:r37": flat3("restaurant")})
    assert promo(quote(rules=own, platform_offer_left=D("0"))) == [("₹3 off", D("-3.00"), "restaurant")]


def test_no_partial_offer_when_the_budget_cannot_pay_all_of_it() -> None:
    q = quote(platform_offer_left=D("49.99"))  # 10% of 560 is capped at ₹50: 49.99 can't pay it
    assert promo(q) == []
    assert promo(quote(platform_offer_left=D("50")))[0][1] == D("-50.00")


def test_free_delivery_the_budget_pays_for_after_the_discount() -> None:
    free = rule("promotion", "free_delivery", {"funded_by": "platform"}, key="free", name="Free delivery")
    rules = hyderabad_rules(**{"promotion:free_delivery:free": free})
    both = quote(rules=rules, platform_offer_left=D("100"))  # ₹50 off + the ₹35 delivery fee = 85
    assert [p[1] for p in promo(both)] == [D("-50.00"), D("-35.00")]
    only_discount = quote(rules=rules, platform_offer_left=D("80"))  # 50 off leaves 30: not the 35 fee
    assert [p[1] for p in promo(only_discount)] == [D("-50.00")]


def test_pool_is_the_nearest_level_with_a_budget() -> None:
    s = lambda v: {B.SETTING: {"monthly": v}}  # noqa: E731
    country, state, city = ("country", "IN", "India", None), ("region", "IN-TG", "Telangana", s("50000")), ("city", "IN-TG-HYD", "Hyderabad", None)
    p = B.pool_for([country, state, city], "INR")
    assert (p.key, p.monthly, p.name) == ("region:IN-TG", D("50000"), "Telangana")
    p = B.pool_for([country, state, ("city", "IN-TG-HYD", "Hyderabad", s("0"))], "INR")
    assert (p.key, p.monthly) == ("city:IN-TG-HYD", D("0"))  # a city can switch its offers off
    p = B.pool_for([country, ("region", "IN-TG", "Telangana", {}), city], "INR")
    assert (p.key, p.monthly) == ("country:IN", D("0"))  # nothing set anywhere: off


@pytest.mark.parametrize("bad", [{"monthly": "-1"}, {"monthly": True}, {"monthly": "lots"}, {"weekly": "5"}, "500",
                                 {"monthly": "500", "extra": 1}])
def test_bad_budget_settings_are_refused(bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(B.BudgetError):
        B.check_settings({B.SETTING: bad})


def test_good_budget_settings() -> None:
    B.check_settings({B.SETTING: {"monthly": "0"}})
    B.check_settings({B.SETTING: {"monthly": 2500}})
    B.check_settings({B.SETTING: None})  # back to the level above's
    assert B.month_of(THU_8PM) == date(2026, 11, 1) and B.month_of(datetime(2026, 12, 31, 23, 59)) == date(2026, 12, 1)


def test_warning_when_an_offer_can_cost_more_than_the_platform_fee() -> None:
    # India: platform fee 10%, at least ₹15
    pct, minimum = D("10"), D("15")
    food, cost, fee = worst_case("percent_off", {"percent": 10, "max_discount": 50, "min_subtotal": 0}, pct, minimum, None)
    assert cost <= fee  # 10% off up to ₹50 never beats a 10% fee with a ₹15 floor
    food, cost, fee = worst_case("flat_off", {"amount": 100, "min_subtotal": 499}, pct, minimum, None)
    assert (food, cost, fee) == (D("499.00"), D("100.00"), D("49.90"))  # ₹100 off a ₹499 order earns ₹49.90
    food, cost, fee = worst_case("free_delivery", {"min_subtotal": 199}, pct, minimum, D("50"))
    assert (food, cost, fee) == (D("199.00"), D("50"), D("19.90"))
    food, cost, fee = worst_case("percent_off", {"percent": 20, "max_discount": 6}, D("10"), D("0.99"), None)
    assert cost == D("6.00") and fee == D("3.00") and food == D("30.00")  # 20% up to $6: worst at a $30 order
