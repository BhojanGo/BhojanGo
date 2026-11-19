"""The commission tax invoice to a kitchen (R16), one per weekly statement where tax is charged
on our commission (India: 18% GST, business rule ``commission_tax``).

Supplier: the platform's legal entity in the country (Markets setting "legal": name, address,
GSTIN once it is set; until then the invoice says the GSTIN is pending, never an invented one).
Recipient: the kitchen (name, address, GSTIN when it has one). Lines: the week's commission, the
tax on it at the statement's rate, and the total, which was taken from the kitchen's payout.

Rounding (R17), one method everywhere: GST on commission is worked out on each order's commission
and rounded to the paisa (cent) on the kitchen's statement (statements.restaurant_statement); the
invoice adds those per-order amounts up and never re-rounds the total, so its GST equals the sum of
"Tax on commission" on the kitchen's statements for the period to the paisa (the invariant test).
"""
import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from core_api.modules.orders.service.receipt import BASE_FONT, _address_lines, _fonts, money


@dataclass
class CommissionInvoice:
    invoice_no: str
    issued_at: datetime
    period_start: date
    period_end: date  # not included
    currency: str
    supplier: dict  # the legal entity's filled-in fields
    kitchen: dict  # restaurant_brief
    commission: Decimal
    rate_percent: Decimal
    tax: Decimal
    label: str = "GST on commission"
    orders: int = 0
    notes: list[str] = field(default_factory=lambda: [ROUNDING_NOTE])


def totals(statement_lines: list[list[dict]]) -> tuple[Decimal, Decimal, int]:
    """Commission, the tax on it and the number of orders, added up from the statements' order lines
    (lines store deductions as negative amounts). Per order, never re-rounded: see the module notes."""
    commission = tax = Decimal(0)
    orders = 0
    for lines in statement_lines:
        for ln in lines:
            commission -= Decimal(str(ln.get("commission") or 0))
            tax -= Decimal(str(ln.get("commission_tax") or 0))
            orders += 1
    return commission, tax, orders


ROUNDING_NOTE = ("Tax on commission is worked out on each order's commission and rounded to the paisa, as on your "
                 "weekly statement; this invoice adds those amounts up.")


def invoice_number(statement_id: str, issued_at: datetime) -> str:
    return f"CI-{issued_at:%Y%m}-{statement_id.replace('-', '')[:8].upper()}"


def render(inv: CommissionInvoice) -> bytes:
    from datetime import timedelta

    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF(format="A4")
    _fonts(pdf)
    pdf.set_title(f"Tax invoice {inv.invoice_no}")
    pdf.set_author("BhojanGo")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin
    nl = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    def text(s: str, size: float = 10, style: str = "", h: float = 5) -> None:
        pdf.font_family = ""
        pdf.set_font(BASE_FONT, style, size)
        pdf.multi_cell(width, h, s, **nl)  # type: ignore[arg-type]

    def row(label: str, amount: str, style: str = "") -> None:
        pdf.font_family = ""
        pdf.set_font(BASE_FONT, style, 10)
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

    s = inv.supplier
    text("Tax invoice", 16, "B", 8)
    text(f"Commission on orders through BhojanGo · Invoice number: {inv.invoice_no}")
    last = inv.period_end - timedelta(days=1)
    text(f"Date: {inv.issued_at:%d %b %Y}    Period: {inv.period_start:%d %b %Y} – {last:%d %b %Y}")
    rule()
    text("Supplier", 10, "B")
    text(s.get("name") or "Legal entity not set in Markets")
    if s.get("address"):
        text(s["address"])
    text(f"GSTIN: {s['gstin']}" if s.get("gstin") else "GSTIN: pending registration (required before launch)")
    if s.get("cin"):
        text(f"CIN: {s['cin']}")
    pdf.ln(2)
    k = inv.kitchen
    text("Recipient", 10, "B")
    text(k.get("name", ""))
    for line in _address_lines(k.get("address") or {}):
        text(line)
    if k.get("gstin"):
        text(f"GSTIN: {k['gstin']}")
    rule()
    row("Description", "Amount", "B")
    row(f"Commission on {inv.orders} delivered order(s)", money(inv.commission, inv.currency))
    row(f"{inv.label} @ {inv.rate_percent.normalize()}%", money(inv.tax, inv.currency))
    rule()
    row("Total (taken from your weekly payout)", money(inv.commission + inv.tax, inv.currency), "B")
    pdf.ln(4)
    for n in inv.notes:
        text(n, 8)
    text(f"All amounts in {inv.currency}. This is a computer-generated invoice and needs no signature.", 8)
    return bytes(pdf.output())


# ── a link that opens the invoice in a browser (one hour) ──────────────────────

def _key() -> bytes:
    from shared.config import get_settings

    return hashlib.sha256(b"commission-invoice:" + get_settings().INTERNAL_SERVICE_SECRET.encode()).digest()


def _sig(body: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(_key(), body.encode(), hashlib.sha256).digest()[:18]).decode().rstrip("=")


def make_token(statement_id: uuid.UUID, seconds: int = 3600, now: float | None = None) -> str:
    body = f"{statement_id.hex}.{int((now or time.time()) + seconds)}"
    return f"{body}.{_sig(body)}"


def read_token(token: str, now: float | None = None) -> uuid.UUID | None:
    """The statement a token is for; None when forged or expired."""
    try:
        sid, exp, sig = token.split(".")
        if not hmac.compare_digest(sig, _sig(f"{sid}.{exp}")) or int(exp) < (now or time.time()):
            return None
        return uuid.UUID(hex=sid)
    except (ValueError, TypeError):
        return None
