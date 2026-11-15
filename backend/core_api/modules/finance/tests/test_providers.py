"""Payout provider selection: the country's choice in Markets, then whether this
deployment may move real money (PAYOUT_PROVIDER and keys). No country in the code."""
from types import SimpleNamespace

import pytest

from core_api.modules.finance.service import providers as P
from shared.providers import ProviderConfigError


def env(monkeypatch, mode: str = "auto", stripe: str = "", razorpay: bool = False, production: bool = False) -> None:  # type: ignore[no-untyped-def]
    s = SimpleNamespace(
        is_production=production,
        providers=SimpleNamespace(PAYOUT_PROVIDER=mode),
        payments=SimpleNamespace(STRIPE_SECRET_KEY=stripe, RAZORPAY_KEY_ID="rzp_id" if razorpay else "",
                                 RAZORPAY_KEY_SECRET="rzp_secret" if razorpay else ""))
    monkeypatch.setattr(P, "get_settings", lambda: s)


def test_live_keys_pick_the_countrys_provider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "live", stripe="sk_test", razorpay=True)
    assert P.get_payout_provider("stripe_connect").name == "stripe_connect"
    assert P.get_payout_provider("razorpay_route").name == "razorpay_route"
    env(monkeypatch, "auto", stripe="sk_test", razorpay=True)
    assert P.get_payout_provider("stripe_connect").name == "stripe_connect"
    assert P.get_payout_provider("razorpay_route").name == "razorpay_route"


def test_auto_without_keys_uses_the_fake_per_provider(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "auto", stripe="sk_test")  # Stripe keys only
    assert P.get_payout_provider("stripe_connect").name == "stripe_connect"
    assert P.get_payout_provider("razorpay_route").name == "fake"
    env(monkeypatch, "auto")
    assert P.get_payout_provider("stripe_connect").name == "fake"


def test_ci_and_qa_can_force_the_fake(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "fake", stripe="sk_test", razorpay=True)
    assert P.get_payout_provider("stripe_connect").name == "fake"
    assert P.get_payout_provider("razorpay_route").name == "fake"


def test_a_country_set_to_fake_gets_the_fake_even_with_keys(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "live", stripe="sk_test", razorpay=True)
    assert P.get_payout_provider("fake").name == "fake"


def test_none_means_no_payouts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "auto")
    with pytest.raises(P.NoPayoutProvider):
        P.get_payout_provider("none")


def test_production_never_uses_the_fake(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "live", stripe="sk_live", razorpay=True, production=True)
    assert P.get_payout_provider("stripe_connect").name == "stripe_connect"
    with pytest.raises(ProviderConfigError, match="production"):
        P.get_payout_provider("fake")
    with pytest.raises(ProviderConfigError, match="production"):
        P.provider_by_name("fake")
    env(monkeypatch, "auto", production=True)  # live provider chosen, keys missing
    with pytest.raises(ProviderConfigError, match="production"):
        P.get_payout_provider("razorpay_route")


def test_unknown_names_fail_loudly(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    env(monkeypatch, "auto")
    with pytest.raises(ProviderConfigError):
        P.get_payout_provider("paypal")
    env(monkeypatch, "sometimes")
    with pytest.raises(ProviderConfigError, match="PAYOUT_PROVIDER"):
        P.get_payout_provider("stripe_connect")
