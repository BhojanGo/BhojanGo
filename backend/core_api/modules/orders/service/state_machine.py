"""Order states (P11).

    pending_payment -> placed -> accepted -> preparing -> almost_ready -> ready -> picked_up -> delivered
          \\            \\          \\           \\              \\           \\
           `------------`----------`-----------`--------------`-----------`--> cancelled

* pending_payment: created from a quote, waiting for the payment. Cancelled by
  the system if unpaid after the unpaid_auto_cancel rule (10 min).
* placed: paid; the restaurant must accept within the accept_timeout rule
  (3 min) or the order is cancelled and refunded.
* almost_ready is optional (preparing -> ready is fine); it triggers rider
  dispatch (P14).

Who may make each move ("actors"): customer, restaurant (the order's own),
rider (the order's own), admin (orders.edit for the order's city), system.
"""
from typing import Final

VALID_TRANSITIONS: Final[dict[str, set[str]]] = {
    "pending_payment": {"placed", "cancelled"},
    "placed": {"accepted", "cancelled"},
    "accepted": {"preparing", "cancelled"},
    "preparing": {"almost_ready", "ready", "cancelled"},
    "almost_ready": {"ready", "cancelled"},
    "ready": {"picked_up", "cancelled"},
    "picked_up": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

RESTAURANT = frozenset({"restaurant", "admin"})
TRANSITION_ACTORS: Final[dict[tuple[str, str], frozenset[str]]] = {
    ("pending_payment", "placed"): frozenset({"system"}),
    ("pending_payment", "cancelled"): frozenset({"customer", "admin", "system"}),
    ("placed", "accepted"): RESTAURANT,
    ("placed", "cancelled"): frozenset({"customer", "restaurant", "admin", "system"}),
    ("accepted", "preparing"): RESTAURANT,
    ("accepted", "cancelled"): frozenset({"customer", "restaurant", "admin"}),  # customer: within the cancel window
    ("preparing", "almost_ready"): RESTAURANT,
    ("preparing", "ready"): RESTAURANT,
    ("preparing", "cancelled"): RESTAURANT,
    ("almost_ready", "ready"): RESTAURANT,
    ("almost_ready", "cancelled"): RESTAURANT,
    ("ready", "picked_up"): frozenset({"rider", "admin"}),
    ("ready", "cancelled"): frozenset({"admin"}),
    ("picked_up", "delivered"): frozenset({"rider", "admin"}),
}

PAID_STATES = frozenset({"placed", "accepted", "preparing", "almost_ready", "ready", "picked_up", "delivered"})
TERMINAL_STATES = frozenset({"delivered", "cancelled"})
ACTIVE_STATES = frozenset(VALID_TRANSITIONS) - TERMINAL_STATES

# The trigger point for rider dispatch (P14): don't send a rider too early.
DISPATCH_TRIGGER_STATUS = "almost_ready"

# Older names, accepted on input so existing apps keep working until P17-P21.
LEGACY_NAMES: Final[dict[str, str]] = {"pending": "pending_payment", "confirmed": "accepted", "ready_for_pickup": "ready"}


def can_transition(current: str, new: str) -> bool:
    return new in VALID_TRANSITIONS.get(current, set())


def actor_allowed(current: str, new: str, actor: str) -> bool:
    return can_transition(current, new) and actor in TRANSITION_ACTORS.get((current, new), frozenset())


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES
