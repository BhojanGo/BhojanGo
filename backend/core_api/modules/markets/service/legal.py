"""Who operates BhojanGo in a country (R15): the legal entity, as data in Markets (country
setting ``legal``), edited in admin, shown on the Terms and Privacy pages, the website footer,
receipts and invoices, email footers and admin Finance. No page or template names an entity.

Every country: legal name, registered address, support email and phone. Countries with GST
(``tax_regime == "gst"``, India) also need the company's CIN, its GSTIN and a grievance officer
(name, email, phone) before launch. Nothing is ever invented: an empty field stays empty and
admin says it's required before launch.
"""
import re
from typing import Any

from core_api.modules.markets.service.rules import MarketRuleError

SETTING = "legal"
FIELDS = ("name", "address", "support_email", "support_phone")
GST_FIELDS = ("cin", "gstin", "grievance_name", "grievance_email", "grievance_phone")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9][0-9 ()-]{5,19}$")
CIN = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
GSTIN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$")


def fields_for(tax_regime: str | None) -> tuple[str, ...]:
    return FIELDS + (GST_FIELDS if tax_regime == "gst" else ())


def check_settings(settings: dict[str, Any] | None, tax_regime: str | None) -> None:
    value = (settings or {}).get(SETTING)
    if value is None:
        return
    if not isinstance(value, dict):
        raise MarketRuleError("The legal entity is a set of fields (name, address, support email and phone)")
    allowed = fields_for(tax_regime)
    unknown = [k for k in value if k not in allowed]
    if unknown:
        raise MarketRuleError(f"Unknown legal entity fields for this country: {', '.join(unknown)}")
    for k, v in value.items():
        if v is None or v == "":
            continue
        if not isinstance(v, str) or len(v) > 300:
            raise MarketRuleError(f"{k} must be text (at most 300 characters)")
        if k.endswith("email") and not EMAIL.match(v):
            raise MarketRuleError(f"{k}: {v!r} isn't an email address")
        if k.endswith("phone") and not PHONE.match(v):
            raise MarketRuleError(f"{k}: {v!r} isn't a phone number")
        if k == "cin" and not CIN.match(v):
            raise MarketRuleError("The CIN is 21 characters, like U72900TG2020PTC123456")
        if k == "gstin" and not GSTIN.match(v):
            raise MarketRuleError("The GSTIN is 15 characters, like 36ABCDE1234F1Z5")


def entity(settings: dict[str, Any] | None, tax_regime: str | None) -> dict[str, str]:
    """The filled-in fields, for pages, receipts and emails (all of it is public information)."""
    value = (settings or {}).get(SETTING) or {}
    return {k: str(value[k]) for k in fields_for(tax_regime) if isinstance(value, dict) and value.get(k)}


def missing(settings: dict[str, Any] | None, tax_regime: str | None) -> list[str]:
    """Fields still empty: each is required before the country launches."""
    have = entity(settings, tax_regime)
    return [k for k in fields_for(tax_regime) if k not in have]
