"""The delivery PIN the customer gives the rider at the door (proof of delivery).

Every order gets its own 4 digits from the operating system's secure random source,
in every environment: no fixed PIN for seed phones, tests or demos (R27; R26 saw 1234 on
every QA order). Codes anyone would guess first (0000, 1111, 1234, 9876 ...) are skipped.
The customer only sees it once a rider has picked the order up (``visible_to_customer``).
"""
import secrets

_RUNS = "0123456789012"  # ascending runs, wrapping at 9-0: 7890, 8901, 9012


def is_weak(pin: str) -> bool:
    """One digit four times, or four digits in a row up or down (wrapping at 9-0)."""
    return len(set(pin)) == 1 or pin in _RUNS or pin[::-1] in _RUNS


def delivery_pin() -> str:
    """A random 4-digit PIN that isn't one of the weak ones (``is_weak``)."""
    while True:
        pin = f"{secrets.randbelow(10000):04d}"
        if not is_weak(pin):
            return pin


def visible_to_customer(status: str) -> bool:
    """The customer reads the PIN out at the door: shown only while the order is
    on its way (picked up), not while it is placed, cooking or waiting for pickup,
    and not once it is delivered or cancelled."""
    return status == "picked_up"
