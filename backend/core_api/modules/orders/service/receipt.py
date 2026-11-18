"""The PDF receipt for a paid order (GET /orders/{id}/receipt.pdf).

India: a "Tax invoice" with the kitchen's FSSAI licence (and GSTIN when it has
one) and every GST line with its rate. US: a "Receipt" with the same bill and
the sales tax. The bill lines are the order's pricing snapshot, the same ones
GET /pricing/orders/{id}/bill shows, so the PDF never disagrees with the app.

Fonts: Noto Sans (Latin, ₹, $) with Noto Sans Devanagari, Telugu, Tamil,
Kannada and Bengali as fallbacks, embedded from ../fonts (SIL Open Font
License, ../fonts/OFL.txt; from github.com/notofonts). Text is shaped with
HarfBuzz (uharfbuzz), so a customer or kitchen named "శ్రీనివాస్" or "प्रिया"
prints in its own script, and amounts read "₹617.39" / "$31.42".
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from shared.money import format_money

TIMEZONE = {"IN": "Asia/Kolkata", "US": "UTC"}
WHO_FUNDS = {"restaurant": "the kitchen", "platform": "BhojanGo"}
WHO_COLLECTS = {"restaurant": "the kitchen", "platform": "BhojanGo"}


def country_of(market_city: str | None, currency: str) -> str:
    """The country from the order's city code (IN-TG-HYD); old orders without one: from the currency."""
    if market_city and len(market_city) >= 2 and market_city[:2].isalpha():
        return market_city[:2].upper()
    return "IN" if currency == "INR" else "US"


def invoice_number(order_id: uuid.UUID, created_at: datetime, country: str) -> str:
    """BG-IN-202611-1A2B3C4D: the same for an order every time it's downloaded.
    The month is the order's month in India time (GST invoices are dated locally)."""
    local = created_at.astimezone(ZoneInfo(TIMEZONE.get(country, "UTC")))
    return f"BG-{country}-{local:%Y%m}-{order_id.hex[:8].upper()}"


FONTS_DIR = Path(__file__).resolve().parent.parent / "fonts"
BASE_FONT = "NotoSans"
# Scripts after Latin, in the order fpdf2 tries them for a character Noto Sans lacks.
FALLBACK_FONTS = ("NotoSansDevanagari", "NotoSansTelugu", "NotoSansTamil", "NotoSansKannada", "NotoSansBengali")


def money(amount: Decimal | float | str, currency: str) -> str:
    """₹1,24,050.00 (Indian grouping) or $1,240.50; a currency without a symbol: "AED 12.00".
    The one backend formatter (shared.money), so the PDF reads like the app."""
    return format_money(amount, currency)


def _pct(rate: str | None) -> str:
    if not rate:
        return ""
    d = Decimal(rate).normalize()
    return f"{d:f}%"


def bill_rows(lines: list[dict], currency: str) -> list[tuple[str, str]]:
    """Each fair-bill line as (label, amount): discounts say who pays for them,
    taxes their rate, what they were charged on and who collects them."""
    rows: list[tuple[str, str]] = []
    for ln in lines:
        code, label, amount = ln.get("code"), str(ln.get("label") or ""), Decimal(str(ln.get("amount") or "0"))
        detail = ln.get("detail") or {}
        if code == "promotion":
            who = WHO_FUNDS.get(str(ln.get("funded_by")), ln.get("funded_by"))
            rows.append((f"{label} (paid for by {who})" if who else label, money(amount, currency)))
        elif code == "tax":
            parts = [label]
            if detail.get("rate_percent"):
                parts.append(f"@ {_pct(detail['rate_percent'])}")
            if detail.get("base"):
                parts.append(f"on {money(detail['base'], currency)}")
            who = WHO_COLLECTS.get(str(detail.get("collected_by")))
            if who:
                parts.append(f"(collected by {who})")
            rows.append((" ".join(parts), money(amount, currency)))
        elif code == "tax_included":
            rate = f" @ {_pct(detail.get('rate_percent'))}" if detail.get("rate_percent") else ""
            rows.append((f"{label}{rate}: {money(detail.get('included', '0'), currency)}", "included"))
        elif code == "tip":  # every tip, also on orders priced before Round 8 ("Tip for your rider")
            rows.append(("Tip for your delivery partner", money(amount, currency)))
        else:
            rows.append((label, money(amount, currency)))
    return rows


def fallback_lines(subtotal: Decimal, delivery_fee: Decimal, discount: Decimal, taxes: Decimal, tip: Decimal) -> list[dict]:
    """Orders from before itemised bills (no pricing snapshot): the order's totals."""
    lines = [{"code": "food", "label": "Food", "amount": str(subtotal)}]
    if discount:
        lines.append({"code": "promotion", "label": "Discount", "amount": str(-abs(discount))})
    if delivery_fee:
        lines.append({"code": "delivery_fee", "label": "Delivery and other fees", "amount": str(delivery_fee)})
    if taxes:
        lines.append({"code": "tax", "label": "Taxes", "amount": str(taxes)})
    if tip:
        lines.append({"code": "tip", "label": "Tip for your delivery partner", "amount": str(tip)})
    return lines


@dataclass
class Receipt:
    country: str
    invoice_no: str
    issued_at: datetime
    order_code: str
    currency: str
    total: Decimal
    kitchen: dict
    customer_name: str
    delivery_address: dict
    items: list[dict]
    lines: list[dict]
    payment_method: str = ""
    # The order's city time zone (Markets); the date is printed in it.
    time_zone: str | None = None
    # Who operates BhojanGo in the country (R15: Markets setting "legal"; only the filled-in fields).
    operator: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return "Tax invoice" if self.country == "IN" else "Receipt"


def _address_lines(a: dict) -> list[str]:
    street = ", ".join(x for x in (a.get("street"), a.get("area"), a.get("landmark")) if x)
    place = " ".join(x for x in (a.get("city"), a.get("state"), a.get("zip") or a.get("postal_code")) if x)
    return [x for x in (street, place, a.get("country")) if x]


def _fonts(pdf) -> None:  # type: ignore[no-untyped-def]
    """Noto Sans and the Indic Noto fonts, regular and bold, shaped by HarfBuzz."""
    for family in (BASE_FONT, *FALLBACK_FONTS):
        pdf.add_font(family, "", FONTS_DIR / f"{family}-Regular.ttf")
        pdf.add_font(family, "B", FONTS_DIR / f"{family}-Bold.ttf")
    pdf.set_fallback_fonts(list(FALLBACK_FONTS), exact_match=False)
    pdf.set_text_shaping(True)


def render(r: Receipt) -> bytes:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF(format="A4" if r.country == "IN" else "Letter")
    _fonts(pdf)
    pdf.set_title(f"{r.title} {r.invoice_no}")
    pdf.set_author("BhojanGo")
    pdf.set_creation_date(r.issued_at)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    nl = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    def font(style: str, size: float) -> None:
        # Always (re)select: a line set with a fallback font is wrapped in q/Q, which
        # restores the PDF's font without fpdf2 noticing; re-selecting writes Tf again.
        pdf.font_family = ""
        pdf.set_font(BASE_FONT, style, size)

    def text(s: str, size: float = 10, style: str = "", h: float = 5, align: str = "L") -> None:
        font(style, size)
        pdf.multi_cell(width, h, s, align=align, **nl)  # type: ignore[arg-type]

    def row(label: str, amount: str, style: str = "", size: float = 10) -> None:
        font(style, size)
        y = pdf.get_y()
        pdf.multi_cell(width - 45, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
        bottom = pdf.get_y()
        pdf.set_xy(pdf.l_margin + width - 45, y)
        pdf.cell(45, 6, amount, align="R", **nl)  # type: ignore[arg-type]
        pdf.set_y(max(bottom, y + 6, pdf.get_y()))

    def rule() -> None:
        pdf.ln(1)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + width, pdf.get_y())
        pdf.ln(2)

    text("BhojanGo", 18, "B", 9)
    text(r.title, 14, "B", 8)
    tz = ZoneInfo(r.time_zone or TIMEZONE.get(r.country, "UTC"))
    text(f"{'Invoice' if r.country == 'IN' else 'Receipt'} number: {r.invoice_no}")
    text(f"Date: {r.issued_at.astimezone(tz):%d %b %Y}    Order: {r.order_code}")
    if r.payment_method:
        text(f"Paid by: {r.payment_method.replace('_', ' ')}")
    rule()

    k = r.kitchen
    text("Sold by", 10, "B")
    text(k.get("name", ""))
    for line in _address_lines(k.get("address") or {}):
        text(line)
    if r.country == "IN":
        text(f"FSSAI licence no.: {k.get('fssai') or 'not on file'}")
        if k.get("gstin"):
            text(f"GSTIN: {k['gstin']}")
    pdf.ln(2)
    text("Billed to", 10, "B")
    text(r.customer_name)
    for line in _address_lines(r.delivery_address):
        text(line)
    rule()

    row("Item", "Amount", "B")
    for it in r.items:
        qty = int(it.get("quantity", 1))
        unit = Decimal(str(it.get("unit_price", it.get("price", 0))))
        opts = ", ".join(str(o) for o in it.get("options") or [])
        name = f"{qty} x {it.get('name', 'Item')}" + (f" ({opts})" if opts else "")
        row(f"{name}  @ {money(unit, r.currency)}", money(unit * qty, r.currency))
    rule()

    for label, amount in bill_rows(r.lines, r.currency):
        row(label, amount)
    rule()
    row("Total", money(r.total, r.currency), "B", 12)
    pdf.ln(4)
    op = r.operator or {}
    if op.get("name"):  # R15: the platform's legal entity, from Markets
        text(f"BhojanGo is operated by {op['name']}" + (f", {op['address']}" if op.get("address") else "") + ".", 8)
        ids = [f"GSTIN: {op['gstin']}" if op.get("gstin") else "", f"CIN: {op['cin']}" if op.get("cin") else ""]
        if any(ids):
            text("    ".join(i for i in ids if i), 8)
        if op.get("support_email") or op.get("support_phone"):
            text("Help: " + " · ".join(v for v in (op.get("support_email"), op.get("support_phone")) if v), 8)
    text(f"All amounts in {r.currency}.", 8)
    if r.country == "IN":
        text("This is a computer-generated invoice and needs no signature.", 8)
    return bytes(pdf.output())
