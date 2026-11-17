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


# ── who can sign up (R9): the country's minimum age and vehicles ──────────────

def test_sign_up_rules_come_from_the_country_with_safe_defaults() -> None:
    r = delivery.sign_up_rules({"delivery_partner": GOOD})
    assert r == {"min_age": 18, "vehicles": ["motorcycle", "scooter"], "rules_set": True}
    assert delivery.sign_up_rules({"delivery_partner": {**GOOD, "min_age": 21}})["min_age"] == 21
    # No rules: the platform minimum and every vehicle the app supports.
    for none in (None, {}, {"delivery_partner": {}}, {"delivery_partner": "junk"}):
        assert delivery.sign_up_rules(none) == {"min_age": delivery.DEFAULT_MIN_AGE, "vehicles": list(delivery.VEHICLES),
                                                "rules_set": False}
    half = delivery.sign_up_rules({"delivery_partner": {"min_age": 20}})
    assert half["min_age"] == 20 and half["vehicles"] == list(delivery.VEHICLES) and half["rules_set"] is False


def test_age_on_the_countrys_date() -> None:
    from datetime import date

    assert delivery.age_on(date(2008, 11, 16), date(2026, 11, 16)) == 18  # the birthday itself
    assert delivery.age_on(date(2008, 11, 17), date(2026, 11, 16)) == 17  # one day short
    assert delivery.age_on(date(2008, 2, 29), date(2026, 2, 28)) == 17  # leap-day births: 1 March
    assert delivery.age_on(date(2008, 2, 29), date(2026, 3, 1)) == 18


def test_check_applicant() -> None:
    from datetime import date

    today = date(2026, 11, 16)
    r = delivery.sign_up_rules({"delivery_partner": GOOD})
    assert delivery.check_applicant(r, date(2008, 11, 16), "motorcycle", today) is None  # exactly 18
    assert delivery.check_applicant(r, date(2008, 11, 17), "motorcycle", today) == "UNDER_AGE"
    assert delivery.check_applicant(r, date(1990, 1, 1), "car", today) == "VEHICLE"
    assert delivery.check_applicant(r, date(1990, 1, 1), "scooter", today) is None
    assert delivery.check_applicant(r, date(2027, 1, 1), "scooter", today) == "DOB"
    assert delivery.check_applicant(r, date(1900, 1, 1), "scooter", today) == "DOB"
    # No rules: 18 and any supported vehicle; still never an unknown one.
    d = delivery.sign_up_rules(None)
    assert delivery.check_applicant(d, date(1990, 1, 1), "car", today) is None
    assert delivery.check_applicant(d, date(2009, 1, 1), "car", today) == "UNDER_AGE"
    assert delivery.check_applicant(d, date(1990, 1, 1), "bicycle", today) == "VEHICLE"


def test_sign_up_refusals_are_written_in_every_language() -> None:
    from shared.texts import DELIVERY_SIGN_UP, LANGUAGES

    for key, texts in DELIVERY_SIGN_UP.items():
        assert set(texts) == set(LANGUAGES), key
        assert all(("{age}" in v) == ("{age}" in texts["en"]) for v in texts.values()), key
