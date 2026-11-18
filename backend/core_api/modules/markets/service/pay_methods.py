"""A country's payment methods (setting ``payment_methods``, R13): what checkout offers there.

R14: what a country may offer follows from its payment providers in Markets
(``payment_providers``), never from the country itself: each provider says which methods
it takes, and a country offers some of what its providers take. Stripe: cards, and Apple
Pay / Google Pay (they run on cards; never Link). Razorpay: cards, UPI, wallets and net
banking. The fake gateway (local and tests) takes all of them.
"""
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "payment_methods"
KNOWN = ("card", "apple_pay", "google_pay", "upi", "wallet", "net_banking")
PROVIDER_METHODS: dict[str, tuple[str, ...]] = {
    "stripe": ("card", "apple_pay", "google_pay"),
    "razorpay": ("card", "upi", "wallet", "net_banking"),
    "fake": KNOWN,
}
NAMES = {"card": "Cards", "apple_pay": "Apple Pay", "google_pay": "Google Pay", "upi": "UPI", "wallet": "Wallets",
         "net_banking": "Net banking"}


def supported(providers: list[str] | None) -> list[str]:
    """The methods a country's providers take, in KNOWN order."""
    took = {m for p in providers or [] for m in PROVIDER_METHODS.get(p, ())}
    return [m for m in KNOWN if m in took]


def check_settings(settings: dict[str, Any] | None, providers: list[str] | None = None) -> None:
    value = (settings or {}).get(SETTING)
    if value is None:
        return
    if not isinstance(value, list) or not value or any(m not in KNOWN for m in value) or len(set(value)) != len(value):
        raise MarketRuleError(f"Payment methods must be a list of {', '.join(KNOWN)} (each once, at least one)")
    if ("apple_pay" in value or "google_pay" in value) and "card" not in value:
        raise MarketRuleError("Apple Pay and Google Pay run on cards: keep cards on to offer them")
    if providers is not None:
        ok = supported(providers)
        refused = [m for m in value if m not in ok]
        if refused:
            names = ", ".join(p.capitalize() for p in providers) or "no payment provider"
            raise MarketRuleError(f"{', '.join(NAMES[m] for m in refused)} isn't offered by {names}: "
                                  f"pick from {', '.join(NAMES[m] for m in ok) or 'nothing (set a payment provider first)'}")
