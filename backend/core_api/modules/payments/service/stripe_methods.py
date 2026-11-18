"""Which payment methods Stripe offers at checkout comes from data (R13): the country's
``payment_methods`` setting in Markets (e.g. US ["card", "apple_pay", "google_pay"]).

Stripe no longer takes ``payment_method_types`` on a PaymentIntent: what it shows is a
*payment method configuration*. So each distinct set of methods gets its own configuration
on the Stripe account, named after the set ("BhojanGo apple_pay+card+google_pay"), with
those methods on and every other method off, Link included (no "Pay with Link", no bank
tab, no Klarna, no cash-back offers). It is found by name, or created once, and cached.

Apple Pay and Google Pay are card wallets: they only show where ``card`` is on. Methods
Stripe doesn't handle for us (UPI, wallets, net banking: Razorpay in India) are left out.
"""
import asyncio
from typing import Any

import structlog

from core_api.modules.payments.service import stripe_svc

logger = structlog.get_logger(__name__)

STRIPE_METHODS = ("apple_pay", "card", "google_pay")  # what Stripe may offer for a country, from its setting
_ids: dict[tuple[str, ...], str] = {}


def stripe_methods(country_methods: list[str] | None) -> tuple[str, ...]:
    """The Stripe methods in a country's setting, sorted; wallets need cards; none: cards only."""
    picked = {m for m in (country_methods or []) if m in STRIPE_METHODS}
    if picked and "card" not in picked:
        picked = set()  # Apple Pay / Google Pay without cards can't run: fall back to cards
    return tuple(sorted(picked or {"card"}))


def config_name(methods: tuple[str, ...]) -> str:
    return "BhojanGo " + "+".join(methods)


def _method_fields(cfg: dict[str, Any]) -> list[str]:
    return [k for k, v in cfg.items() if isinstance(v, dict) and "display_preference" in v]


def _matches(cfg: dict[str, Any], methods: tuple[str, ...]) -> bool:
    on = {k for k in _method_fields(cfg) if (cfg[k].get("display_preference") or {}).get("value") == "on"}
    return on == set(methods)


async def configuration_id(methods: tuple[str, ...]) -> str:
    """The Stripe payment method configuration that offers exactly ``methods``."""
    if methods in _ids:
        return _ids[methods]
    s = stripe_svc.get_stripe()
    listed = (await asyncio.to_thread(s.PaymentMethodConfiguration.list, limit=100)).to_dict()["data"]
    name = config_name(methods)
    found = next((c for c in listed if c.get("name") == name and c.get("active") and not c.get("application")
                  and _matches(c, methods)), None)
    if found is None:
        template = next((c for c in listed if c.get("is_default") and not c.get("application")), listed[0] if listed else {})
        fields = _method_fields(template) or list(methods) + ["link"]
        prefs = {k: {"display_preference": {"preference": "on" if k in methods else "off"}} for k in fields}
        found = (await asyncio.to_thread(s.PaymentMethodConfiguration.create, name=name, **prefs)).to_dict()
        logger.info("stripe_payment_method_configuration_created", name=name, configuration=found["id"])
    _ids[methods] = found["id"]
    return found["id"]
