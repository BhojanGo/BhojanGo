"""The delivery PIN the customer gives the rider (proof of delivery)."""
import secrets

from shared.config import get_settings


def delivery_pin(phone: str | None) -> str:
    """A random 4-digit PIN; the fixed test PIN only for the fictional seed
    numbers, and never in production (shared/config.py refuses to start with one)."""
    settings = get_settings()
    p = settings.providers
    if (p.DELIVERY_PIN_FIXED and phone and not settings.production_named
            and any(phone.startswith(x) for x in p.DELIVERY_PIN_FIXED_PHONE_PREFIXES)):
        return p.DELIVERY_PIN_FIXED
    return f"{secrets.randbelow(10000):04d}"
