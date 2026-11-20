"""Market rules without a database."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core_api.modules.markets.service import rules
from core_api.modules.markets.service.rules import MarketRuleError, ZoneState

NOW = datetime(2026, 11, 12, 20, 0, tzinfo=UTC)
INDIA = SimpleNamespace(name="India", currency="INR", locales=["en-IN", "hi-IN"], timezone="Asia/Kolkata",
                        distance_unit="km", phone_code="+91", payment_providers=["razorpay"], tax_regime="gst",
                        settings={"fssai_required": True, "late_night_fee": 20})
TELANGANA = SimpleNamespace(name="Telangana", timezone=None, settings={"late_night_fee": 25})
HYDERABAD = SimpleNamespace(name="Hyderabad", timezone=None, service_hours={"open": "07:00", "close": "23:30"},
                            settings={"late_night_fee": 30, "currency": "USD"})


def test_settings_inherit_most_specific_wins() -> None:
    s = {x["key"]: x for x in rules.effective_settings(INDIA, TELANGANA, HYDERABAD)}
    assert s["late_night_fee"] == {"key": "late_night_fee", "value": 30, "source": "Hyderabad", "source_level": "city"}
    assert s["fssai_required"]["source"] == "India"
    assert s["timezone"]["value"] == "Asia/Kolkata" and s["timezone"]["source"] == "India"
    assert s["currency"]["value"] == "INR"  # a city can't override the currency


def test_state_timezone_overrides_country() -> None:
    idaho = SimpleNamespace(name="Idaho", timezone="America/Boise", settings={})
    us = SimpleNamespace(**{**vars(INDIA), "name": "United States", "timezone": "America/New_York", "settings": {}})
    s = {x["key"]: x for x in rules.effective_settings(us, idaho, None)}
    assert s["timezone"]["value"] == "America/Boise" and s["timezone"]["source_level"] == "region"


def test_merge_and_reset_overrides() -> None:
    assert rules.merge_settings({"a": 1, "b": 2}, {"b": None, "c": 3}) == {"a": 1, "c": 3}
    with pytest.raises(MarketRuleError):
        rules.check_overrides({"currency": "USD"})


@pytest.mark.parametrize("key", ["review_only", "review_accounts"])
def test_review_accounts_are_never_set_through_the_api(key: str) -> None:
    """R21 S6: a review account's orders cost nothing; only tools/review_accounts.py names them."""
    with pytest.raises(MarketRuleError, match=key):
        rules.check_overrides({key: True if key == "review_only" else ["00000000-0000-0000-0000-000000000001"]})


def checklist(country="live", region="live", hours=True, zones=(ZoneState("live"),), priced=True, payouts="razorpay_route"):
    return rules.launch_checklist(country_status=country, region_status=region,
                                  service_hours={"open": "07:00", "close": "23:00"} if hours else None,
                                  zones=list(zones), now=NOW, priced=priced, payout_provider=payouts)


def test_city_can_open_only_when_checklist_complete() -> None:
    rules.check_city_status("live", checklist())
    rules.check_city_status("beta", checklist(region="beta"))
    for bad in (checklist(country="draft"), checklist(hours=False), checklist(zones=()),
                checklist(zones=(ZoneState("draft"),)), checklist(priced=False)):
        with pytest.raises(MarketRuleError):
            rules.check_city_status("live", bad)
    # Going back to draft or pausing is always allowed.
    rules.check_city_status("paused", checklist(zones=()))
    rules.check_city_status("draft", checklist(country="draft"))
    # A city with no delivery fee can be announced, not opened (the website would list no kitchens).
    rules.check_city_status("soon", checklist(priced=False))
    with pytest.raises(MarketRuleError, match="no delivery fee"):
        rules.check_city_status("live", checklist(priced=False))
    # Nobody to pay the kitchens and riders: announce, don't open.
    assert checklist(payouts="none")["payouts_set"] is False and checklist(payouts="fake")["payouts_set"]
    rules.check_city_status("soon", checklist(payouts="none"))
    with pytest.raises(MarketRuleError, match="no payout provider"):
        rules.check_city_status("beta", checklist(payouts="none"))


def test_a_country_opens_only_in_languages_we_have_words_for() -> None:
    """Round 5: every locale an open country lists must be one we translate into."""
    rules.check_country_languages("live", ["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN"])
    rules.check_country_languages("beta", ["en-US", "es-US"])
    rules.check_country_languages("draft", ["en-NZ", "mi-NZ"])  # set up first, translate, then open
    with pytest.raises(MarketRuleError, match="mi-NZ"):
        rules.check_country_languages("live", ["en-NZ", "mi-NZ"])


def test_a_country_opens_only_with_a_payout_provider() -> None:
    for provider in ("stripe_connect", "razorpay_route", "fake"):
        rules.check_country_payouts("live", provider, production=False)
    for status in ("draft", "soon", "paused"):
        rules.check_country_payouts(status, "none", production=False)
    for status in ("beta", "live"):
        with pytest.raises(MarketRuleError, match="no payout provider"):
            rules.check_country_payouts(status, "none", production=False)
    # production: the real providers only, whatever the status
    rules.check_country_payouts("live", "stripe_connect", production=True)
    for status in ("draft", "live"):
        with pytest.raises(MarketRuleError, match="fake payout provider"):
            rules.check_country_payouts(status, "fake", production=True)


def test_paused_zone_reopens_when_its_time_is_up() -> None:
    assert not ZoneState("paused").is_open(NOW)
    assert not ZoneState("paused", NOW + timedelta(hours=1)).is_open(NOW)
    assert ZoneState("paused", NOW - timedelta(minutes=1)).is_open(NOW)
    assert ZoneState("beta").is_open(NOW) and not ZoneState("draft").is_open(NOW)


def test_chain_open_and_parent_rule() -> None:
    assert rules.chain_open("live", "beta", "live")
    assert not rules.chain_open("live", "paused", "live")
    with pytest.raises(MarketRuleError):
        rules.check_parent_open("live", "draft", "India")
    rules.check_parent_open("draft", "draft", "India")
    rules.check_parent_open("beta", "paused", "India")  # a paused parent doesn't block setup
