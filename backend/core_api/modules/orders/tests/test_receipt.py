"""Receipts and tax invoices (GET /orders/{id}/receipt.pdf): the invoice
number, the bill lines as printed, and the PDF itself."""
import io
import unicodedata
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from core_api.modules.orders.service import receipt as R

ORDER = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000001")


def pdf_text(data: bytes) -> str:
    """The PDF's text as a reader extracts it (pypdf, through the embedded fonts'
    ToUnicode maps), NFC-normalised so shaped Indic clusters compare equal. A
    shaped cluster drawn with several glyphs (a reordered vowel sign) maps its
    extra glyphs to control characters in fpdf2's ToUnicode; they are dropped."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return unicodedata.normalize("NFC", "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch) != "Cc"))


def test_invoice_number_is_deterministic_and_dated_in_india_time() -> None:
    # 31 Oct 2026, 20:00 UTC is 1 Nov 01:30 in India.
    at = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
    assert R.invoice_number(ORDER, at, "IN") == "BG-IN-202611-1A2B3C4D"
    assert R.invoice_number(ORDER, at, "IN") == R.invoice_number(ORDER, at, "IN")
    assert R.invoice_number(ORDER, at, "US") == "BG-US-202610-1A2B3C4D"


def test_country_and_money() -> None:
    assert R.country_of("IN-TG-HYD", "INR") == "IN" and R.country_of("US-TX-AUS", "USD") == "US"
    assert R.country_of(None, "INR") == "IN" and R.country_of(None, "USD") == "US"
    assert R.money(Decimal("617.389"), "INR") == "₹617.39"
    assert R.money("124050", "INR") == "₹1,24,050.00"
    assert R.money(-12.5, "USD") == "-$12.50"
    assert R.money("1240.5", "AED") == "AED 1,240.50"  # a currency with no symbol here: its code
    assert R.country_of("GB-ENG-LON", "GBP") == "GB"  # from Markets' city code, no country list


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
    assert rows[0] == ("Food", "₹560.00")
    assert rows[1] == ("Weekend 10% (paid for by the kitchen)", "-₹56.00")
    assert rows[2] == ("Free delivery (paid for by BhojanGo)", "-₹30.00")
    assert rows[4] == ("GST on food @ 5% on ₹504.00 (collected by BhojanGo)", "₹25.20")
    assert rows[5] == ("VAT (included in prices) @ 18%: ₹4.58", "included")


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
    for want in ("Tax invoice", "BG-IN-202611-1A2B3C4D", "₹617.39", "13622012000123", "36AABCS1429B1Z5",
                 "GST @ 5%", "Priya Sharma", "Flat 302", "Veg Dum Biryani"):
        assert want in text, want


def test_us_gets_a_receipt_with_sales_tax() -> None:
    text = pdf_text(R.render(receipt("US")))
    for want in ("Receipt", "BG-US-202611-1A2B3C4D", "$31.42", "Sales tax @ 8.25%"):
        assert want in text, want
    assert "Tax invoice" not in text and "FSSAI" not in text


def test_orders_without_an_itemised_bill_use_their_totals() -> None:
    lines = R.fallback_lines(Decimal("500"), Decimal("40"), Decimal("50"), Decimal("25"), Decimal("0"))
    assert [ln["code"] for ln in lines] == ["food", "promotion", "delivery_fee", "tax"]
    assert lines[1]["amount"] == "-50"


def test_names_print_in_their_own_script_with_the_rupee_sign() -> None:
    """Telugu and Devanagari names (shaped by HarfBuzz, Noto fonts embedded), mixed with Latin, and ₹."""
    r = receipt("IN")
    r.customer_name = "శ్రీనివాస్ Rao"
    r.kitchen = {**r.kitchen, "name": "प्रिया की रसोई"}
    r.items = [{"name": "ಮಸಾಲೆ ದೋಸೆ", "quantity": 1, "unit_price": 120.0}, {"name": "সন্দেশ", "quantity": 2, "unit_price": 40.0},
               {"name": "தோசை", "quantity": 1, "unit_price": 90.0}]
    data = R.render(r)
    text = pdf_text(data)
    for want in ("శ్రీనివాస్ Rao", "प्रिया की रसोई", "₹617.39", "₹120.00", "Tax invoice"):
        assert want in text, (want, text)
    for script in ("NotoSans", "NotoSansTelugu", "NotoSansDevanagari", "NotoSansKannada", "NotoSansBengali", "NotoSansTamil"):
        assert f"/BaseFont /{script}".encode() in data or f"+{script}".encode() in data, script  # embedded, subset
    assert b"Helvetica" not in data


def test_us_receipt_uses_the_dollar_sign() -> None:
    text = pdf_text(R.render(receipt("US")))
    assert "$31.42" in text and "USD 31.42" not in text


def test_the_date_is_the_orders_city_day() -> None:
    """Paid at 01:30 UTC on 15 Nov: still 14 Nov in a US city, already 15 Nov in India."""
    r = receipt("US")
    r.issued_at = datetime(2026, 11, 15, 1, 30, tzinfo=UTC)
    r.time_zone = "America/Boise"
    assert "Date: 14 Nov 2026" in pdf_text(R.render(r))
    r = receipt("IN")
    r.issued_at = datetime(2026, 11, 14, 20, 0, tzinfo=UTC)
    r.time_zone = "Asia/Kolkata"
    assert "Date: 15 Nov 2026" in pdf_text(R.render(r))
