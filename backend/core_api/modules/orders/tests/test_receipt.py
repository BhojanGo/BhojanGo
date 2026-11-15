"""Receipts and tax invoices (GET /orders/{id}/receipt.pdf): the invoice
number, the bill lines as printed, and the PDF itself."""
import re
import uuid
import zlib
from datetime import UTC, datetime
from decimal import Decimal

from core_api.modules.orders.service import receipt as R

ORDER = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000001")


def pdf_text(data: bytes) -> str:
    """The PDF's page text: content streams inflated (fpdf2 compresses them)."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            out.append(zlib.decompress(m.group(1)).decode("latin-1"))
        except zlib.error:
            out.append(m.group(1).decode("latin-1"))
    return "\n".join(out)


def test_invoice_number_is_deterministic_and_dated_in_india_time() -> None:
    # 31 Oct 2026, 20:00 UTC is 1 Nov 01:30 in India.
    at = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    assert R.invoice_number(ORDER, at, "IN") == "BG-IN-202611-1A2B3C4D"
    assert R.invoice_number(ORDER, at, "IN") == R.invoice_number(ORDER, at, "IN")
    assert R.invoice_number(ORDER, at, "US") == "BG-US-202610-1A2B3C4D"


def test_country_and_money() -> None:
    assert R.country_of("IN-TG-HYD", "INR") == "IN" and R.country_of("US-TX-AUS", "USD") == "US"
    assert R.country_of(None, "INR") == "IN" and R.country_of(None, "USD") == "US"
    assert R.money(Decimal("617.389"), "INR") == "INR 617.39"
    assert R.money("124050", "INR") == "INR 1,24,050.00"
    assert R.money(-12.5, "USD") == "USD -12.50"


def test_bill_lines_say_who_funds_discounts_and_each_tax_rate() -> None:
    lines = [
        {"code": "food", "label": "Food", "amount": "560.00"},
        {"code": "promotion", "label": "Weekend 10%", "amount": "-56.00", "funded_by": "restaurant"},
        {"code": "promotion", "label": "Free delivery", "amount": "-30.00", "funded_by": "platform"},
        {"code": "delivery_fee", "label": "Delivery fee", "amount": "30.00"},
        {"code": "tax", "label": "GST on food", "amount": "25.20",
         "detail": {"rate_percent": "5", "base": "504.00", "collected_by": "platform"}},
        {"code": "tax_included", "label": "VAT (included in prices)", "amount": "0.00",
         "detail": {"rate_percent": "18.0", "included": "4.58"}},
    ]
    rows = R.bill_rows(lines, "INR")
    assert rows[0] == ("Food", "INR 560.00")
    assert rows[1] == ("Weekend 10% (paid for by the kitchen)", "INR -56.00")
    assert rows[2] == ("Free delivery (paid for by BhojanGo)", "INR -30.00")
    assert rows[4] == ("GST on food @ 5% on INR 504.00 (collected by BhojanGo)", "INR 25.20")
    assert rows[5] == ("VAT (included in prices) @ 18%: INR 4.58", "included")


def test_text_helvetica_cannot_draw_is_replaced_not_fatal() -> None:
    assert R.latin1("Café Déjà") == "Café Déjà"
    assert R.latin1("Srī Krishna – Bhavan") == "Sri Krishna - Bhavan"
    assert R.latin1("ప్రియ") == "?" * len("ప్రియ")


def receipt(country: str = "IN") -> R.Receipt:
    inr = country == "IN"
    return R.Receipt(
        country=country, invoice_no=R.invoice_number(ORDER, datetime(2026, 11, 14, 14, tzinfo=UTC), country),
        issued_at=datetime(2026, 11, 14, 14, tzinfo=UTC), order_code="#1A2B3C", currency="INR" if inr else "USD",
        total=Decimal("617.39") if inr else Decimal("31.42"),
        kitchen={"name": "Spice Route Kitchen", "address": {"street": "Road 36", "city": "Hyderabad", "zip": "500081"},
                 "fssai": "13622012000123" if inr else None, "gstin": "36AABCS1429B1Z5" if inr else None},
        customer_name="Priya Sharma", delivery_address={"street": "Flat 302", "city": "Hyderabad", "zip": "500081"},
        items=[{"name": "Veg Dum Biryani", "quantity": 2, "unit_price": 280.0, "options": ["Extra raita"]}],
        lines=[{"code": "food", "label": "Food", "amount": "560.00"},
               {"code": "tax", "label": "GST" if inr else "Sales tax", "amount": "28.00",
                "detail": {"rate_percent": "5" if inr else "8.25", "base": "560.00"}}],
        payment_method="upi",
    )


def test_india_gets_a_tax_invoice_with_the_licence_and_gst() -> None:
    data = R.render(receipt("IN"))
    assert data.startswith(b"%PDF-")
    text = pdf_text(data)
    for want in ("Tax invoice", "BG-IN-202611-1A2B3C4D", "INR 617.39", "13622012000123", "36AABCS1429B1Z5",
                 "GST @ 5%", "Priya Sharma", "Flat 302", "Veg Dum Biryani"):
        assert want in text, want


def test_us_gets_a_receipt_with_sales_tax() -> None:
    text = pdf_text(R.render(receipt("US")))
    for want in ("Receipt", "BG-US-202611-1A2B3C4D", "USD 31.42", "Sales tax @ 8.25%"):
        assert want in text, want
    assert "Tax invoice" not in text and "FSSAI" not in text


def test_orders_without_an_itemised_bill_use_their_totals() -> None:
    lines = R.fallback_lines(Decimal("500"), Decimal("40"), Decimal("50"), Decimal("25"), Decimal("0"))
    assert [ln["code"] for ln in lines] == ["food", "promotion", "delivery_fee", "tax"]
    assert lines[1]["amount"] == "-50"
