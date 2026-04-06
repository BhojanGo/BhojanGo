import pytest

from app.core.state_machine import (
    can_transition,
    is_terminal,
    is_transition_allowed,
)


def test_pending_to_confirmed():
    assert can_transition("pending", "confirmed") is True


def test_pending_to_cancelled():
    assert can_transition("pending", "cancelled") is True


def test_invalid_transition_skip_state():
    assert can_transition("pending", "preparing") is False


def test_terminal_state_no_transitions():
    assert can_transition("delivered", "cancelled") is False
    assert can_transition("cancelled", "pending") is False


def test_is_terminal():
    assert is_terminal("delivered") is True
    assert is_terminal("cancelled") is True
    assert is_terminal("pending") is False
    assert is_terminal("confirmed") is False


def test_role_permission_restaurant_owner():
    assert is_transition_allowed("pending", "confirmed", "restaurant_owner") is True
    assert is_transition_allowed("pending", "confirmed", "customer") is False


def test_role_permission_driver_pickup():
    assert is_transition_allowed("ready_for_pickup", "picked_up", "driver") is True
    assert is_transition_allowed("ready_for_pickup", "picked_up", "customer") is False


def test_role_permission_driver_deliver():
    assert is_transition_allowed("picked_up", "delivered", "driver") is True


def test_admin_can_all():
    assert is_transition_allowed("pending", "confirmed", "admin") is True
    assert is_transition_allowed("ready_for_pickup", "picked_up", "admin") is True


def test_full_happy_path():
    states = ["pending", "confirmed", "preparing", "ready_for_pickup", "picked_up", "delivered"]
    roles = [
        ("pending", "confirmed", "restaurant_owner"),
        ("confirmed", "preparing", "restaurant_owner"),
        ("preparing", "ready_for_pickup", "restaurant_owner"),
        ("ready_for_pickup", "picked_up", "driver"),
        ("picked_up", "delivered", "driver"),
    ]
    for current, next_state, role in roles:
        assert is_transition_allowed(current, next_state, role), (
            f"Expected {role} to be able to transition {current} -> {next_state}"
        )
