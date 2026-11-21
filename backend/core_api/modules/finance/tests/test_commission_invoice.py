"""R25: the commission tax invoice is built from one statement row (period, orders, commission, GST),
names the country's legal entity from Markets and never a placeholder, and says "1 delivered order" /
"2 delivered orders" (no database: commission_invoice.for_statement and render)."""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from core_api.modules.finance.service import commission_invoice as ci
from core_api.modules.finance.service.statements import restaurant_statement
from core_api.modules.finance.tests.test_statements import worked_example
from core_api.modules.orders.tests.test_receipt import pdf_text

IN = {"name": "DeepTrics Software Solutions Pvt Ltd"}


def statement(orders: int, start: date, end: date, amount: int = 0, carried_in: int = 0):  # type: ignore[no-untyped-def]
    """A kitchen statement (PayoutStatement-like) of a run (PayoutRun-like) for start..end."""
    _, summary, lines = restaurant_statement([worked_example(f"o{i}") for i in range(orders)], Decimal(18))
    run = SimpleNamespace(country="IN", period_start=start, period_end=end, approved_at=None,
                          created_at=datetime(2026, 11, 9, 4, 0, tzinfo=UTC))
    s = SimpleNamespace(id=uuid.uuid4(), currency="INR", summary=summary, lines=lines, amount=amount, carried_in=carried_in)
    return s, run


def text_of(inv: ci.CommissionInvoice) -> str:
    return " ".join(pdf_text(ci.render(inv)).split())


def test_the_invoice_is_its_statement_row_period_orders_commission_and_gst() -> None:
    s, run = statement(2, date(2026, 10, 26), date(2026, 11, 2), amount=-8000, carried_in=-5000)
    inv = ci.for_statement(s, run, IN, {"name": "Spice Route Kitchen"})
    assert (inv.period_start, inv.period_end) == (run.period_start, run.period_end)
    assert inv.orders == s.summary["orders"] == len(s.lines) == 2
    assert inv.commission == Decimal(s.summary["commission"]) == Decimal("168.00")
    assert inv.tax == Decimal(s.summary["commission_tax"]) == Decimal("30.24")
    assert inv.issued_at == run.created_at and inv.supplier == IN
    text = text_of(inv)
    assert "Period: 26 Oct 2026 – 01 Nov 2026" in text
    assert "Commission on 2 delivered orders ₹168.00" in text and "₹30.24" in text
    assert "This week came to ₹30.00 below zero." in text  # the same statement's balance (R24)


def test_one_order_is_singular() -> None:
    s, run = statement(1, date(2026, 11, 2), date(2026, 11, 9))
    text = text_of(ci.for_statement(s, run, IN, {"name": "Spice Route Kitchen"}))
    assert "Commission on 1 delivered order ₹84.00" in text and "order(s)" not in text


def test_the_supplier_is_the_legal_entity_never_a_placeholder() -> None:
    s, run = statement(1, date(2026, 11, 2), date(2026, 11, 9))
    text = text_of(ci.for_statement(s, run, IN, {"name": "Spice Route Kitchen"}))
    assert "Supplier DeepTrics Software Solutions Pvt Ltd" in text
    assert "Markets" not in text and "legal entity" not in text.lower()
    for supplier in ({}, {"name": ""}, {"address": "Hyderabad"}):
        with pytest.raises(ci.LegalEntityMissing):
            ci.for_statement(s, run, supplier, {"name": "Spice Route Kitchen"})
    inv = ci.for_statement(s, run, IN, {"name": "Spice Route Kitchen"})
    with pytest.raises(ci.LegalEntityMissing):  # render() refuses too, whoever builds the invoice
        ci.render(ci.CommissionInvoice(**{**inv.__dict__, "supplier": {}}))


def test_the_orders_line_in_every_language() -> None:
    from shared.texts import INVOICE_ORDERS, LANGUAGES, invoice_orders_line

    assert set(INVOICE_ORDERS) == set(LANGUAGES)
    assert invoice_orders_line(1) == "Commission on 1 delivered order"
    assert invoice_orders_line(2) == "Commission on 2 delivered orders"
    assert invoice_orders_line(0) == "Commission on 0 delivered orders"
    assert invoice_orders_line(1, "es") == "Comisión por 1 pedido entregado"
    assert invoice_orders_line(3, "es") == "Comisión por 3 pedidos entregados"
    for lang in LANGUAGES:
        assert "(s)" not in invoice_orders_line(2, lang) and "5" in invoice_orders_line(5, lang)
