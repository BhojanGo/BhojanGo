"""US sales tax providers (P9)."""
from decimal import Decimal

import pytest

from core_api.modules.payments.service.tax import LocalTax, StripeTax, TaxableLine, TaxAddress, TaxError, get_tax_provider
from shared.config import get_settings
from shared.providers import ProviderConfigError

LINES = [TaxableLine("food", Decimal("25.00")), TaxableLine("delivery_fee", Decimal("1.99")),
         TaxableLine("service_fee", Decimal("1.25"))]


async def test_local_idaho_rate() -> None:
    r = await LocalTax().calculate("USD", LINES, TaxAddress("US", "ID", "Boise", "83702"))
    assert r.calculation_id.startswith("taxcalc_local_")
    [b] = r.breakdown
    assert (b.label, b.rate_percent, b.taxable_amount, b.amount) == ("Idaho sales tax", Decimal("6"), Decimal("28.24"), Decimal("1.69"))
    assert r.total == Decimal("1.69")


async def test_local_no_tax_state_and_unknown_state() -> None:
    r = await LocalTax().calculate("USD", LINES, TaxAddress("US", "OR"))
    assert r.breakdown == [] and r.total == 0
    with pytest.raises(TaxError):
        await LocalTax().calculate("USD", LINES, TaxAddress("US", "ZZ"))


def test_provider_selection(monkeypatch) -> None:
    assert isinstance(get_tax_provider(), LocalTax)  # no Stripe key locally
    monkeypatch.setattr(get_settings().payments, "STRIPE_SECRET_KEY", "sk_test_x")
    assert isinstance(get_tax_provider(), StripeTax)
    monkeypatch.setattr(get_settings().providers, "TAX_PROVIDER", "local")
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")
    with pytest.raises(ProviderConfigError):
        get_tax_provider()


async def test_stripe_tax_request_shape(monkeypatch) -> None:
    """What we send Stripe Tax and how we read its answer (no network)."""
    import stripe

    sent: dict = {}

    class Rate:
        display_name, percentage_decimal = "Sales Tax", "6.0"

    class Breakdown:
        tax_rate_details, taxable_amount, amount = Rate(), 2824, 169

    class Calc:
        id, tax_breakdown = "taxcalc_123", [Breakdown()]

    def create(**kw):  # type: ignore[no-untyped-def]
        sent.update(kw)
        return Calc()

    monkeypatch.setattr(stripe.tax.Calculation, "create", create)
    r = await StripeTax().calculate("USD", LINES, TaxAddress("US", "ID", "Boise", "83702", "1510 N 13th St"))
    assert sent["currency"] == "usd" and sent["customer_details"]["address"]["postal_code"] == "83702"
    assert [li["amount"] for li in sent["line_items"]] == [2500, 199, 125]
    assert sent["line_items"][0]["tax_code"] == "txcd_40060003"  # prepared food
    assert r.calculation_id == "taxcalc_123" and r.total == Decimal("1.69")
    with pytest.raises(TaxError):
        await StripeTax().calculate("USD", LINES, TaxAddress("US", "ID"))  # no ZIP
