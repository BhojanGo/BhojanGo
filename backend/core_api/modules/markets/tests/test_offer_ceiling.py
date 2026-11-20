"""R22 security review (S11): a kitchen's own offer stays within its market's ceiling
(Markets setting kitchen_offer_ceiling, country -> state -> city, markets/service/offer_ceiling.py).

Imports are inside the tests so the file still collects with the fix reverted (each
test then fails, which is how the fix was proven)."""
from decimal import Decimal

import pytest


def test_an_admin_saves_only_a_well_formed_ceiling() -> None:
    from core_api.modules.markets.service import offer_ceiling
    from core_api.modules.markets.service.rules import MarketRuleError

    offer_ceiling.check_settings({"kitchen_offer_ceiling": {"flat_off": "200", "weekly_cap": 25000, "max_discount": "150.50"}})
    offer_ceiling.check_settings({"kitchen_offer_ceiling": None})  # reset to inherited
    offer_ceiling.check_settings({"payment_methods": ["card"]})
    for bad in ("200", {}, {"flat_off": "-1"}, {"flat_off": "0"}, {"flat_off": "lots"}, {"flat_off": True},
                {"weekly_cap": "1e12"}, {"percent": "90"}, {"flat_off": "NaN"}):
        with pytest.raises(MarketRuleError):
            offer_ceiling.check_settings({"kitchen_offer_ceiling": bad})


def test_the_ceiling_is_inherited_country_state_city_key_by_key() -> None:
    from core_api.modules.markets.service.offer_ceiling import ceiling

    country = {"kitchen_offer_ceiling": {"flat_off": "100", "weekly_cap": "10000"}}
    state = {"kitchen_offer_ceiling": {"weekly_cap": "8000"}}
    city = {"kitchen_offer_ceiling": {"flat_off": "50"}}
    got = ceiling([country, state, city], "INR")
    assert got == {"flat_off": Decimal(50), "weekly_cap": Decimal(8000), "max_discount": Decimal(200)}  # max_discount: INR default
    assert ceiling([None, None, None], "USD")["weekly_cap"] == Decimal(1500)
    assert ceiling([{}], "NZD") == {}  # no default, nothing set: offers refused below


def test_a_kitchen_offer_over_the_ceiling_is_refused() -> None:
    from core_api.modules.markets.service.offer_ceiling import OfferOverCeiling, apply

    limits = {"flat_off": Decimal(200), "max_discount": Decimal(150), "weekly_cap": Decimal(25000)}
    base = {"funded_by": "restaurant", "min_subtotal": "0"}
    with pytest.raises(OfferOverCeiling):
        apply("flat_off", {**base, "amount": "5000", "weekly_cap": "1000"}, limits, "INR")
    with pytest.raises(OfferOverCeiling):
        apply("free_delivery", {**base, "weekly_cap": "9999999"}, limits, "INR")
    with pytest.raises(OfferOverCeiling):
        apply("percent_off", {**base, "percent": "50", "max_discount": "1000", "weekly_cap": "1000"}, limits, "INR")
    ok = apply("flat_off", {**base, "amount": "200", "weekly_cap": "25000"}, limits, "INR")
    assert ok["amount"] == "200"


def test_a_percent_offer_without_a_maximum_gets_the_markets() -> None:
    from core_api.modules.markets.service.offer_ceiling import apply

    limits = {"flat_off": Decimal(200), "max_discount": Decimal(150), "weekly_cap": Decimal(25000)}
    got = apply("percent_off", {"percent": "20", "weekly_cap": "1000"}, limits, "INR")
    assert got["max_discount"] == "150"


def test_more_offers_dont_raise_the_weekly_ceiling() -> None:
    from core_api.modules.markets.service.offer_ceiling import OfferOverCeiling, apply

    limits = {"flat_off": Decimal(200), "max_discount": Decimal(150), "weekly_cap": Decimal(25000)}
    apply("free_delivery", {"weekly_cap": "5000"}, limits, "INR", Decimal(20000))
    with pytest.raises(OfferOverCeiling, match="5000"):
        apply("free_delivery", {"weekly_cap": "5001"}, limits, "INR", Decimal(20000))


def test_no_ceiling_anywhere_refuses_kitchen_offers() -> None:
    from core_api.modules.markets.service.offer_ceiling import OfferOverCeiling, apply

    with pytest.raises(OfferOverCeiling):
        apply("free_delivery", {"weekly_cap": "10"}, {}, "NZD")


def test_markets_saves_check_the_ceiling() -> None:
    """Every settings save in markets/service/markets.py checks the ceiling's shape."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "service" / "markets.py").read_text(encoding="utf-8")
    assert src.count("offer_ceiling.check_settings(") == 6  # create/update for country, state and city
