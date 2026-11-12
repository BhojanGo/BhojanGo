"""What each gateway sends the provider and hands the app (P12). No network:
Stripe and Razorpay calls are replaced by recorders."""
import hashlib
import hmac

import pytest

from core_api.modules.payments.service import gateways
from shared.config import get_settings

CUSTOMER = {"user_id": "u-1", "name": "Emily Carter", "email": "e@example.com", "phone": "+120855500101",
            "methods": ["card", "apple_pay", "google_pay"]}


async def test_stripe_payment_sheet(monkeypatch) -> None:
    import stripe

    calls: dict = {}

    class PI:
        id, client_secret = "pi_123", "pi_123_secret_abc"

    class Key:
        secret = "ek_test_123"

    class Cus:
        id = "cus_123"

    monkeypatch.setattr(stripe.PaymentIntent, "create", lambda **kw: calls.setdefault("pi", kw) and PI())
    monkeypatch.setattr(stripe.EphemeralKey, "create", lambda **kw: calls.setdefault("key", kw) and Key())
    monkeypatch.setattr(stripe.Customer, "create", lambda **kw: calls.setdefault("cus", kw) and Cus())
    monkeypatch.setattr(get_settings().payments, "STRIPE_PUBLISHABLE_KEY", "pk_test_123")

    g = gateways.StripeGateway()
    cus = await g.ensure_customer(CUSTOMER, None)
    assert cus == "cus_123" and calls["cus"]["metadata"] == {"user_id": "u-1"}
    assert await g.ensure_customer(CUSTOMER, "cus_existing") == "cus_existing"  # created once

    r = await g.create(amount=3973, currency="USD", order_id="o-1", idempotency_key="o-1:attempt-1",
                       payment_method_id=None, customer={**CUSTOMER, "provider_customer_id": cus})
    assert calls["pi"]["automatic_payment_methods"] == {"enabled": True}  # cards, Apple Pay, Google Pay
    assert calls["pi"]["customer"] == "cus_123" and calls["pi"]["amount"] == 3973 and calls["pi"]["currency"] == "usd"
    assert calls["key"]["stripe_version"] == gateways.STRIPE_API_VERSION
    sheet = r["checkout"]
    assert sheet["sdk"] == "stripe_payment_sheet" and sheet["payment_intent_client_secret"] == "pi_123_secret_abc"
    assert sheet["customer_ephemeral_key"] == "ek_test_123" and sheet["publishable_key"] == "pk_test_123"
    assert sheet["apple_pay"]["merchant_country_code"] == "US" and sheet["google_pay"]["test_env"] is True


async def test_razorpay_checkout(monkeypatch) -> None:
    from core_api.modules.payments.service import razorpay_svc

    async def create_order(amount, currency, order_id, key):  # type: ignore[no-untyped-def]
        return {"provider_payment_id": "order_rzp_1", "razorpay_order_id": "order_rzp_1"}

    monkeypatch.setattr(razorpay_svc, "create_order", create_order)
    monkeypatch.setattr(get_settings().payments, "RAZORPAY_KEY_ID", "rzp_test_key")
    r = await gateways.RazorpayGateway().create(
        amount=63822, currency="INR", order_id="o-2", idempotency_key="k", payment_method_id=None,
        customer={"name": "Srini Rao", "email": "c@example.com", "phone": "+9190000101", "methods": ["upi", "card", "wallet"]})
    c = r["checkout"]
    assert c["sdk"] == "razorpay_checkout" and c["key_id"] == "rzp_test_key" and c["order_id"] == "order_rzp_1"
    assert c["method"] == {"upi": True, "card": True, "wallet": True, "netbanking": False}
    assert c["prefill"]["contact"] == "+9190000101"


def test_razorpay_checkout_signature(monkeypatch) -> None:
    monkeypatch.setattr(get_settings().payments, "RAZORPAY_KEY_SECRET", "secret")
    good = hmac.new(b"secret", b"order_1|pay_1", hashlib.sha256).hexdigest()
    assert gateways.verify_razorpay_checkout("order_1", "pay_1", good)
    assert not gateways.verify_razorpay_checkout("order_1", "pay_2", good)
    monkeypatch.setattr(get_settings().payments, "RAZORPAY_KEY_SECRET", "")
    assert not gateways.verify_razorpay_checkout("order_1", "pay_1", good)  # no key: never trust


@pytest.mark.parametrize(("country", "mimics"), [("IN", "razorpay_checkout"), ("US", "stripe_payment_sheet")])
async def test_fake_checkout_mirrors_the_real_one(country, mimics) -> None:
    r = await gateways.FakeGateway(country).create(amount=100, currency="INR", order_id="o", idempotency_key="k",
                                                   payment_method_id=None, customer={"methods": ["upi"]})
    assert r["checkout"]["sdk"] == "fake" and r["checkout"]["mimics"] == mimics and r["checkout"]["methods"] == ["upi"]
