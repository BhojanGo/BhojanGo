"""A country's payment methods (setting ``payment_methods``, R13): what checkout offers there.
Stripe countries show the Stripe ones (payments/service/stripe_methods.py: cards, and Apple Pay /
Google Pay on cards; never Link); Razorpay countries the rest (UPI, wallets, net banking)."""
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "payment_methods"
KNOWN = ("card", "apple_pay", "google_pay", "upi", "wallet", "net_banking")


def check_settings(settings: dict[str, Any] | None) -> None:
    value = (settings or {}).get(SETTING)
    if value is None:
        return
    if not isinstance(value, list) or not value or any(m not in KNOWN for m in value) or len(set(value)) != len(value):
        raise MarketRuleError(f"Payment methods must be a list of {', '.join(KNOWN)} (each once, at least one)")
    if ("apple_pay" in value or "google_pay" in value) and "card" not in value:
        raise MarketRuleError("Apple Pay and Google Pay run on cards: keep cards on to offer them")
