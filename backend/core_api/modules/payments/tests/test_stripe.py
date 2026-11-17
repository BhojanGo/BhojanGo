"""Stripe (US) with Stripe mocked: idempotency keys on every create, webhook
events, refunds, Stripe Tax parsing and its documented degradation. No network."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core_api.modules.payments.service import gateways, stripe_svc, tax
from core_api.modules.payments.service.tax import StripeTax, TaxableLine, TaxAddress, TaxError
from core_api.modules.pricing.service.engine import BillLine, CartLine, QuoteInputs, QuoteResult, Split
from core_api.modules.pricing.service.quotes import tax_lines
from shared.config import get_settings

ADDR = TaxAddress("US", "ID", "Boise", "83702", "1510 N 13th St")


async def test_customer_and_intent_idempotency(monkeypatch) -> None:
    import stripe

    calls: dict = {}

    class Cus:
        id = "cus_1"

    class PI:
        id, client_secret = "pi_1", "pi_1_secret"

    class Key:
        secret = "ek_1"

    monkeypatch.setattr(stripe.Customer, "create", lambda **kw: calls.setdefault("cus", kw) and Cus())
    monkeypatch.setattr(stripe.PaymentIntent, "create", lambda **kw: calls.setdefault("pi", kw) and PI())
    monkeypatch.setattr(stripe.EphemeralKey, "create", lambda **kw: calls.setdefault("key", kw) and Key())
    g = gateways.StripeGateway()
    await g.ensure_customer({"user_id": "u-9", "email": "a@example.com", "name": "", "phone": None}, None)
    assert calls["cus"]["idempotency_key"] == "cus:u-9"
    assert "name" not in calls["cus"] and "phone" not in calls["cus"]  # no empty fields at Stripe
    r = await g.create(amount=1999, currency="USD", order_id="o-9", idempotency_key="o-9:attempt-2", payment_method_id=None,
                       customer={"provider_customer_id": "cus_1", "methods": ["card"]})
    pi = calls["pi"]
    assert pi["idempotency_key"] == "o-9:attempt-2" and pi["metadata"] == {"order_id": "o-9", "attempt": "o-9:attempt-2"}
    assert pi["payment_method_types"] == ["card", "link"]
    c = r["checkout"]
    assert c["amount"] == 1999 and c["currency"] == "USD" and c["customer_id"] == "cus_1" and c["customer_ephemeral_key"] == "ek_1"


async def test_refresh_checkout_gets_a_new_ephemeral_key(monkeypatch) -> None:
    import stripe

    n = {"i": 0}

    def key(**kw):  # type: ignore[no-untyped-def]
        n["i"] += 1
        return type("K", (), {"secret": f"ek_{n['i']}"})()

    monkeypatch.setattr(stripe.EphemeralKey, "create", key)
    g = gateways.StripeGateway()
    assert (await g.refresh_checkout({"customer_id": "cus_1", "customer_ephemeral_key": "old"}))["customer_ephemeral_key"] == "ek_1"
    assert await g.refresh_checkout({"sdk": "stripe_payment_sheet"}) == {"sdk": "stripe_payment_sheet"}  # no customer


async def test_refund_by_amount_with_idempotency_key(monkeypatch) -> None:
    import stripe

    sent: dict = {}

    class R:
        id, status, amount = "re_1", "succeeded", 1234

    monkeypatch.setattr(stripe.Refund, "create", lambda **kw: sent.update(kw) or R())
    r = await gateways.StripeGateway().refund("pi_1", 1234, "refund:abc", {"order_id": "o-1", "refund_id": "abc", "x": 1})
    assert r == {"refund_id": "re_1", "status": "succeeded"}
    assert sent == {"payment_intent": "pi_1", "amount": 1234, "idempotency_key": "refund:abc",
                    "metadata": {"order_id": "o-1", "refund_id": "abc"}}


def _event(monkeypatch, event: dict) -> None:
    import stripe

    def construct(payload, sig, secret):  # type: ignore[no-untyped-def]
        if sig != "good":
            raise stripe.SignatureVerificationError("bad", sig)
        return event

    monkeypatch.setattr(stripe.Webhook, "construct_event", construct)


async def test_webhook_payment_events(monkeypatch) -> None:
    _event(monkeypatch, {"id": "evt_1", "type": "payment_intent.succeeded", "data": {"object": {"id": "pi_1"}}})
    assert await stripe_svc.process_webhook(b"{}", "good") == {
        "event_type": "payment_intent.succeeded", "provider_payment_id": "pi_1", "status": "succeeded", "event_id": "evt_1"}
    with pytest.raises(ValueError):
        await stripe_svc.process_webhook(b"{}", "forged")

    _event(monkeypatch, {"id": "evt_2", "type": "payment_intent.payment_failed", "data": {"object": {
        "id": "pi_1", "last_payment_error": {"message": "Your card was declined.", "decline_code": "generic_decline"}}}})
    e = await stripe_svc.process_webhook(b"{}", "good")
    assert e["status"] == "failed" and e["failure_reason"] == "Your card was declined."

    _event(monkeypatch, {"id": "evt_3", "type": "payment_intent.canceled", "data": {"object": {
        "id": "pi_1", "cancellation_reason": "abandoned"}}})
    e = await stripe_svc.process_webhook(b"{}", "good")
    assert e["status"] == "failed" and e["failure_reason"] == "abandoned"

    _event(monkeypatch, {"id": "evt_4", "type": "payment_intent.requires_action", "data": {"object": {"id": "pi_1"}}})
    assert (await stripe_svc.process_webhook(b"{}", "good"))["status"] == "unknown"  # 3-D Secure: the client handles it


async def test_webhook_refund_events(monkeypatch) -> None:
    _event(monkeypatch, {"id": "evt_5", "type": "charge.refunded", "data": {"object": {
        "id": "ch_1", "payment_intent": "pi_1",
        "refunds": {"data": [{"id": "re_1", "status": "succeeded", "amount": 500}]}}}})
    e = await stripe_svc.process_webhook(b"{}", "good")
    assert e["kind"] == "refund" and e["refunds"] == [
        {"refund_id": "re_1", "status": "succeeded", "amount": 500, "provider_payment_id": "pi_1"}]
    _event(monkeypatch, {"id": "evt_6", "type": "refund.failed", "data": {"object": {
        "id": "re_2", "status": "failed", "amount": 700, "payment_intent": "pi_1"}}})
    e = await stripe_svc.process_webhook(b"{}", "good")
    assert e["refunds"][0]["status"] == "failed" and e["refunds"][0]["refund_id"] == "re_2"
    assert set(stripe_svc.WEBHOOK_EVENTS) >= {"payment_intent.succeeded", "payment_intent.payment_failed", "charge.refunded"}


# ── Stripe Tax ───────────────────────────────────────────────────────────────
def _calc(items: list[dict], cid: str = "taxcalc_1") -> dict:
    return {"id": cid, "tax_breakdown": [], "line_items": {"has_more": False, "data": items}}


def _bd(name: str, level: str, taxable: int, amount: int, rate: str | None = "6.0", reason: str = "standard_rated") -> dict:
    return {"amount": amount, "taxable_amount": taxable, "taxability_reason": reason,
            "jurisdiction": {"display_name": name, "level": level, "state": "ID", "country": "US"},
            "tax_rate_details": {"display_name": "Sales Tax", "percentage_decimal": rate, "tax_type": "sales_tax"} if rate else None}


class _Calc(dict):
    @property
    def id(self) -> str:  # type: ignore[override]
        return self["id"]


def _mock_calc(monkeypatch, result=None, error=None) -> dict:  # type: ignore[no-untyped-def]
    import stripe

    sent: dict = {}

    def create(**kw):  # type: ignore[no-untyped-def]
        sent.update(kw)
        if error:
            raise error
        return _Calc(result)

    monkeypatch.setattr(stripe.tax.Calculation, "create", create)
    return sent


async def test_stripe_tax_per_line_and_per_jurisdiction(monkeypatch) -> None:
    calc = _calc([
        {"reference": "food-1-a", "tax_breakdown": [_bd("Idaho", "state", 1500, 90)]},
        {"reference": "food-2-b", "tax_breakdown": [_bd("Idaho", "state", 1000, 60)]},
    ])
    # The delivery fee is Stripe's shipping_cost (a shipping tax code is refused on a line item).
    calc["shipping_cost"] = {"amount": 199, "tax_breakdown": [_bd("Idaho", "state", 199, 0, "0.0", "product_exempt")]}
    sent = _mock_calc(monkeypatch, calc)
    lines = [TaxableLine("food-1-a", Decimal("15.00"), kind="food"), TaxableLine("food-2-b", Decimal("10.00"), kind="food"),
             TaxableLine("delivery_fee", Decimal("1.99"), kind="delivery_fee")]
    r = await StripeTax().calculate("USD", lines, ADDR, idempotency_key="taxcalc:q-1")
    assert sent["idempotency_key"] == "taxcalc:q-1"
    assert [(li["reference"], li["amount"], li["tax_code"]) for li in sent["line_items"]] == [
        ("food-1-a", 1500, "txcd_40060003"), ("food-2-b", 1000, "txcd_40060003")]
    assert sent["shipping_cost"] == {"amount": 199, "tax_code": "txcd_92010001", "tax_behavior": "exclusive"}
    [b] = r.breakdown
    assert (b.label, b.rate_percent, b.taxable_amount, b.amount) == ("Idaho sales tax", Decimal("6.0"), Decimal("26.99"), Decimal("1.50"))
    assert r.provider == "stripe_tax" and r.calculation_id == "taxcalc_1"


async def test_stripe_tax_not_collecting_is_shown_as_stripe_said(monkeypatch) -> None:
    """No registration in the state: Stripe answers zero tax; we show its zero, not a made-up rate."""
    _mock_calc(monkeypatch, _calc([{"reference": "food", "tax_breakdown": [_bd("Idaho", "state", 0, 0, None, "not_collecting")]}]))
    r = await StripeTax().calculate("USD", [TaxableLine("food", Decimal("25"))], ADDR)
    [b] = r.breakdown
    assert b.amount == 0 and b.reason == "not_collecting" and r.calculation_id == "taxcalc_1"


async def test_stripe_tax_not_set_up_degrades_outside_production_only(monkeypatch) -> None:
    import stripe

    err = stripe.InvalidRequestError("Stripe Tax has not been activated on your account.", "tax", code="stripe_tax_inactive")
    _mock_calc(monkeypatch, error=err)
    r = await StripeTax().calculate("USD", [TaxableLine("food", Decimal("25"))], ADDR)
    assert r.provider == tax.UNAVAILABLE and r.calculation_id == "" and r.total == 0
    assert r.breakdown[0].reason == "stripe_tax_not_configured"
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(TaxError):
        await StripeTax().calculate("USD", [TaxableLine("food", Decimal("25"))], ADDR)


async def test_stripe_tax_transient_error_refuses(monkeypatch) -> None:
    import stripe

    _mock_calc(monkeypatch, error=stripe.APIConnectionError("network"))
    with pytest.raises(TaxError):
        await StripeTax().calculate("USD", [TaxableLine("food", Decimal("25"))], ADDR)


async def test_tax_transaction_and_reversal_keys(monkeypatch) -> None:
    import stripe

    sent: dict = {}
    monkeypatch.setattr(stripe.tax.Transaction, "create_from_calculation",
                        lambda **kw: sent.setdefault("tx", kw) and type("T", (), {"id": "tax_1"})())
    monkeypatch.setattr(stripe.tax.Transaction, "create_reversal",
                        lambda **kw: sent.setdefault("rev", kw) and type("T", (), {"id": "tax_rev_1"})())
    assert await tax.record_tax_transaction("local", "taxcalc_local_x", "o-1") is None
    assert await tax.record_tax_transaction(tax.UNAVAILABLE, "", "o-1") is None
    tx = await tax.record_tax_transaction("stripe_tax", "taxcalc_1", "o-1")
    assert tx == {"provider": "stripe_tax", "transaction_id": "tax_1"}
    assert sent["tx"] == {"calculation": "taxcalc_1", "reference": "o-1", "idempotency_key": "taxtx:o-1"}
    rev = await tax.reverse_tax_transaction(tx, "refund:r-1", 1234, full=False)
    assert rev == {"provider": "stripe_tax", "reversal_id": "tax_rev_1"}
    assert sent["rev"] == {"original_transaction": "tax_1", "reference": "refund:r-1", "idempotency_key": "taxrev:refund:r-1",
                           "mode": "partial", "flat_amount": -1234}
    assert await tax.reverse_tax_transaction(None, "refund:r-2", 1, full=True) is None


def test_tax_lines_one_per_cart_line_adding_up_to_the_food_after_discounts() -> None:
    inputs = QuoteInputs(currency="USD", lines=[CartLine("Bowl", 2, Decimal("7.50"), "a"), CartLine("Naan", 1, Decimal("3.00"), "b"),
                                                CartLine("Lassi", 3, Decimal("2.99"), "c")],
                         distance=Decimal(2), local_time=datetime.now(UTC))
    food = Decimal("26.97")
    result = QuoteResult(currency="USD", lines=[
        BillLine("food", "Food", food, taxable_as="food"), BillLine("promotion", "Offer", Decimal("-5.00"), taxable_as="food"),
        BillLine("delivery_fee", "Delivery fee", Decimal("1.99"), taxable_as="delivery_fee")],
        food_subtotal=food, total=Decimal(0), split=Split(Decimal(0), Decimal(0), Decimal(0), Decimal(0), {}), rules_used=[])
    out = tax_lines(inputs, result)
    assert [ln.reference for ln in out] == ["food-1-a", "food-2-b", "food-3-c", "delivery_fee"]
    assert sum((ln.amount for ln in out if ln.kind == "food"), Decimal(0)) == Decimal("21.97")
    assert all(ln.amount > 0 for ln in out)


async def test_stripe_tax_bad_request_is_an_error_not_a_zero_line(monkeypatch) -> None:
    """Our own malformed request (a bug) must not be shown as "Sales tax not calculated" (R10, QA)."""
    import pytest
    import stripe

    from core_api.modules.payments.service.tax import TaxError

    err = stripe.InvalidRequestError("The shipping tax code txcd_92010001 cannot be used on a line item.", "line_items[1][tax_code]")
    _mock_calc(monkeypatch, error=err)
    with pytest.raises(TaxError):
        await StripeTax().calculate("USD", [TaxableLine("food", Decimal("25"))], ADDR)
