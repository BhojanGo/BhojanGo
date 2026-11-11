"""
Order State Machine
===================
Valid transitions:

pending -> confirmed | cancelled
confirmed -> preparing | cancelled
preparing -> ready_for_pickup | cancelled
ready_for_pickup -> picked_up | cancelled
picked_up -> delivered
delivered -> (terminal)
cancelled -> (terminal)
"""
from typing import Final

VALID_TRANSITIONS: Final[dict[str, set[str]]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"preparing", "cancelled"},
    # "almost_ready" is an optional intermediate used for predictive dispatch.
    # "preparing -> ready_for_pickup" remains valid for backward compatibility.
    "preparing": {"almost_ready", "ready_for_pickup", "cancelled"},
    "almost_ready": {"ready_for_pickup", "cancelled"},
    "ready_for_pickup": {"picked_up", "cancelled"},
    "picked_up": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

# Which roles can trigger which transitions
TRANSITION_PERMISSIONS: Final[dict[tuple[str, str], set[str]]] = {
    ("pending", "confirmed"): {"restaurant_owner", "admin", "super_admin"},
    ("pending", "cancelled"): {"customer", "restaurant_owner", "admin", "super_admin"},
    ("confirmed", "preparing"): {"restaurant_owner", "admin", "super_admin"},
    ("confirmed", "cancelled"): {"customer", "restaurant_owner", "admin", "super_admin"},
    ("preparing", "almost_ready"): {"restaurant_owner", "admin", "super_admin"},
    ("preparing", "ready_for_pickup"): {"restaurant_owner", "admin", "super_admin"},
    ("preparing", "cancelled"): {"restaurant_owner", "admin", "super_admin"},
    ("almost_ready", "ready_for_pickup"): {"restaurant_owner", "admin", "super_admin"},
    ("almost_ready", "cancelled"): {"restaurant_owner", "admin", "super_admin"},
    ("ready_for_pickup", "picked_up"): {"driver", "admin", "super_admin"},
    ("ready_for_pickup", "cancelled"): {"admin", "super_admin"},
    ("picked_up", "delivered"): {"driver", "admin", "super_admin"},
}

# Status at which the order is "near ready" — the trigger point for predictive
# driver dispatch (don't assign a driver before this to avoid idle waiting).
DISPATCH_TRIGGER_STATUS = "almost_ready"


def can_transition(current_status: str, new_status: str) -> bool:
    return new_status in VALID_TRANSITIONS.get(current_status, set())


def is_transition_allowed(current_status: str, new_status: str, role: str) -> bool:
    if not can_transition(current_status, new_status):
        return False
    allowed_roles = TRANSITION_PERMISSIONS.get((current_status, new_status), set())
    return role in allowed_roles


TERMINAL_STATES = {"delivered", "cancelled"}


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES
