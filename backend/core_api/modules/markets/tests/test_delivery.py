"""Deliver with BhojanGo: the country's delivery_partner setting (Markets data) and
the example trip the /deliver page shows (the engine's own rider pay)."""
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from core_api.modules.markets.service import delivery, rules
from core_api.modules.markets.service.rules import MarketRuleError
from core_api.modules.pricing.service.engine import rider_base_pay

GOOD = {"min_age": 18, "vehicles": ["motorcycle", "scooter"],
        "documents": ["driving_licence", "vehicle_rc_insurance", "bank_account", "background_check"],
        "example_trip": {"distance": 3}, "app_links": {"android": None, "ios": "https://apps.apple.com/app/id1"}}


def seed_countries() -> list[dict]:
    root = Path(__file__).resolve().parents[5]
    sys.path.insert(0, str(root / "tools" / "seed"))
    import data  # type: ignore[import-not-found]

    return data.COUNTRIES


def test_good_settings_pass_and_none_clears() -> None:
    delivery.check_settings({"delivery_partner": GOOD})
    delivery.check_settings({"delivery_partner": None})
    delivery.check_settings({"hero_photo": "poke-bowl"})
    delivery.check_settings(None)


@pytest.mark.parametrize("bad", [
    "yes",
    {**GOOD, "min_age": 12},
    {**GOOD, "min_age": "18"},
    {**GOOD, "vehicles": []},
    {**GOOD, "vehicles": ["rocket"]},
    {**GOOD, "documents": ["passport"]},  # the delivery app never asks for one
    {**GOOD, "documents": ["bank_account", "payout_account"]},  # one step, named twice
    {**GOOD, "example_trip": {"distance": 0}},
    {**GOOD, "example_trip": {"distance": "far"}},
    {**GOOD, "app_links": {"android": "https://evil.example.com/app"}},
    {**GOOD, "app_links": {"windows": "https://apps.microsoft.com/"}},
    {**GOOD, "fee": 100},
])
def test_bad_settings_are_refused(bad: object) -> None:
    with pytest.raises(MarketRuleError, match="Delivery partners"):
        delivery.check_settings({"delivery_partner": bad})


def test_every_document_is_a_step_the_delivery_app_collects() -> None:
    from core_api.modules.identity.api.v1 import riders

    steps = set(riders._labels("XX")) | set(riders._labels("IN"))
    assert set(delivery.APP_STEP.values()) <= steps


def test_seeded_countries_have_valid_terms_that_differ() -> None:
    found = {c["code"]: c["settings"] for c in seed_countries()}
    for settings in found.values():
        delivery.check_settings(settings)
        t = delivery.terms(settings)
        assert t["min_age"] and t["vehicles"] and t["documents"] and t["app_links"] == {"android": None, "ios": None}
    assert len({tuple(delivery.terms(s)["documents"]) for s in found.values()}) == len(found)


def test_terms_defaults() -> None:
    t = delivery.terms({})
    assert t == {"min_age": None, "vehicles": [], "documents": [], "example_distance": Decimal("3"),
                 "app_links": {"android": None, "ios": None}}
    # an unsafe stored link is dropped rather than shown
    assert delivery.terms({"delivery_partner": {"app_links": {"android": "javascript:alert(1)"}}})["app_links"]["android"] is None


def test_only_the_country_sets_it() -> None:
    assert "delivery_partner" in rules.LOCKED_BELOW_COUNTRY


def test_example_trip_is_the_engines_rider_pay() -> None:
    p = {"base": 25, "per_unit": 6, "per_wait_minute": 1, "free_wait_minutes": 5}
    assert rider_base_pay(p, Decimal("3")) == Decimal("43.00")
    assert rider_base_pay(p, Decimal("3"), Decimal("4")) == Decimal("43.00")  # inside the free minutes
    assert rider_base_pay(p, Decimal("3"), Decimal("10")) == Decimal("48.00")
    us = {"base": "3.00", "per_unit": "1.00", "per_wait_minute": "0.25", "free_wait_minutes": 5}
    assert rider_base_pay(us, Decimal("2")) == Decimal("5.00")
