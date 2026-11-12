"""Order states and who may move them (P11)."""
import pytest

from core_api.modules.orders.service.state_machine import (
    ACTIVE_STATES,
    LEGACY_NAMES,
    PAID_STATES,
    TRANSITION_ACTORS,
    VALID_TRANSITIONS,
    actor_allowed,
    can_transition,
    is_terminal,
)

HAPPY_PATH = ["pending_payment", "placed", "accepted", "preparing", "almost_ready", "ready", "picked_up", "delivered"]


def test_happy_path_is_a_chain() -> None:
    for a, b in zip(HAPPY_PATH, HAPPY_PATH[1:]):
        assert can_transition(a, b), (a, b)
    assert can_transition("preparing", "ready")  # almost_ready is optional


@pytest.mark.parametrize(("a", "b"), [
    ("pending_payment", "accepted"),  # no order without payment
    ("placed", "preparing"),          # the restaurant must accept first
    ("ready", "delivered"),           # must be picked up
    ("picked_up", "cancelled"),       # on its way: can't cancel
    ("delivered", "cancelled"),
    ("cancelled", "placed"),
])
def test_impossible_moves(a, b) -> None:
    assert not can_transition(a, b)


@pytest.mark.parametrize(("a", "b", "actor", "ok"), [
    ("pending_payment", "placed", "system", True),
    ("pending_payment", "placed", "customer", False),   # only a payment places an order
    ("pending_payment", "placed", "admin", False),
    ("placed", "accepted", "restaurant", True),
    ("placed", "accepted", "customer", False),
    ("placed", "accepted", "rider", False),
    ("placed", "cancelled", "system", True),           # accept timeout
    ("placed", "cancelled", "customer", True),
    ("accepted", "preparing", "restaurant", True),
    ("preparing", "ready", "restaurant", True),
    ("preparing", "cancelled", "customer", False),
    ("ready", "picked_up", "rider", True),
    ("ready", "picked_up", "restaurant", False),
    ("ready", "cancelled", "restaurant", False),
    ("ready", "cancelled", "admin", True),
    ("picked_up", "delivered", "rider", True),
    ("picked_up", "delivered", "customer", False),
])
def test_who_moves_what(a, b, actor, ok) -> None:
    assert actor_allowed(a, b, actor) is ok


def test_every_transition_has_actors_and_vice_versa() -> None:
    pairs = {(a, b) for a, bs in VALID_TRANSITIONS.items() for b in bs}
    assert pairs == set(TRANSITION_ACTORS)


def test_terminal_paid_active() -> None:
    assert is_terminal("delivered") and is_terminal("cancelled") and not is_terminal("placed")
    assert "pending_payment" not in PAID_STATES and "placed" in PAID_STATES
    assert "pending_payment" in ACTIVE_STATES and "delivered" not in ACTIVE_STATES


def test_legacy_names_map_onto_new_states() -> None:
    assert {LEGACY_NAMES[k] for k in LEGACY_NAMES} <= set(VALID_TRANSITIONS)
