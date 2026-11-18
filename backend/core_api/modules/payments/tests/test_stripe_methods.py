"""R13: Stripe's methods come from the country's setting; cards only when it lists none; never Link."""
import pytest

from core_api.modules.markets.service.pay_methods import check_settings
from core_api.modules.markets.service.rules import MarketRuleError
from core_api.modules.payments.service.stripe_methods import config_name, stripe_methods


def test_the_setting_picks_the_stripe_methods() -> None:
    assert stripe_methods(["card", "apple_pay", "google_pay"]) == ("apple_pay", "card", "google_pay")
    assert stripe_methods(["card"]) == ("card",)
    assert stripe_methods(["upi", "card", "wallet"]) == ("card",)  # UPI and wallets are Razorpay's
    assert stripe_methods(None) == ("card",) and stripe_methods([]) == ("card",)
    assert stripe_methods(["apple_pay"]) == ("card",)  # wallets run on cards
    assert "link" not in stripe_methods(["card", "link"])
    assert config_name(("apple_pay", "card", "google_pay")) == "BhojanGo apple_pay+card+google_pay"


def test_markets_checks_the_setting() -> None:
    check_settings({"payment_methods": ["card", "apple_pay", "google_pay"]})
    check_settings({"payment_methods": ["upi", "card", "wallet"]})
    check_settings({"hero_photo": "x"})
    for bad in ([], ["card", "card"], ["link"], ["klarna"], "card", ["apple_pay"]):
        with pytest.raises(MarketRuleError):
            check_settings({"payment_methods": bad})


def test_methods_follow_the_payment_provider() -> None:  # R14
    from core_api.modules.markets.service.pay_methods import supported

    assert supported(["stripe"]) == ["card", "apple_pay", "google_pay"]
    assert supported(["razorpay"]) == ["card", "upi", "wallet", "net_banking"]
    assert supported([]) == [] and supported(None) == []
    check_settings({"payment_methods": ["card", "apple_pay"]}, ["stripe"])
    check_settings({"payment_methods": ["upi", "card", "wallet"]}, ["razorpay"])
    for bad, providers in ((["card", "upi"], ["stripe"]), (["card", "apple_pay"], ["razorpay"]), (["card"], [])):
        with pytest.raises(MarketRuleError):
            check_settings({"payment_methods": bad}, providers)
