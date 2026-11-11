"""Every admin role at every scope level (shared/authz.py)."""
import pytest

from shared import authz
from shared.authz import Assignment as A

HYD = "IN-TG-HYD"      # Hyderabad
WGL = "IN-TG-WGL"      # Warangal: same state, other city
TG = "IN-TG"           # Telangana
KA_BLR = "IN-KA-BLR"   # Bengaluru: other state
BOI = "US-ID-BOI"      # Boise


# role, assignment scope, permission, target scope, allowed?
MATRIX = [
    # super admin: everything, everywhere
    ("super_admin", "*", "rules.approve", HYD, True),
    ("super_admin", "*", "admins.grant", BOI, True),
    ("super_admin", "*", "markets.edit", "*", True),
    # country manager (India)
    ("country_manager", "IN", "rules.approve", HYD, True),
    ("country_manager", "IN", "markets.edit", TG, True),
    ("country_manager", "IN", "markets.edit", "IN", True),
    ("country_manager", "IN", "refunds.issue", KA_BLR, True),
    ("country_manager", "IN", "rules.approve", BOI, False),
    ("country_manager", "IN", "markets.edit", "*", False),
    ("country_manager", "IN", "payouts.approve", HYD, False),
    # country manager scoped to a state
    ("country_manager", TG, "rules.edit", HYD, True),
    ("country_manager", TG, "rules.edit", KA_BLR, False),
    ("country_manager", TG, "rules.edit", "IN", False),
    # city ops (Hyderabad)
    ("city_ops", HYD, "orders.edit", HYD, True),
    ("city_ops", HYD, "dispatch.edit", HYD, True),
    ("city_ops", HYD, "partners.edit", HYD, True),
    ("city_ops", HYD, "orders.edit", WGL, False),
    ("city_ops", HYD, "orders.view", TG, False),
    ("city_ops", HYD, "orders.view", "IN", False),
    ("city_ops", HYD, "orders.view", BOI, False),
    ("city_ops", HYD, "rules.edit", HYD, False),
    ("city_ops", HYD, "rules.approve", HYD, False),
    ("city_ops", HYD, "admins.grant", HYD, False),
    # city ops at state level covers every city in it
    ("city_ops", TG, "orders.edit", WGL, True),
    ("city_ops", TG, "orders.edit", KA_BLR, False),
    # support agent
    ("support_agent", HYD, "refunds.issue", HYD, True),
    ("support_agent", HYD, "customers.edit", HYD, True),
    ("support_agent", HYD, "orders.edit", HYD, False),
    ("support_agent", HYD, "rules.view", HYD, False),
    ("support_agent", "US", "refunds.issue", BOI, True),
    ("support_agent", "US", "refunds.issue", HYD, False),
    # finance
    ("finance", "IN", "payouts.approve", HYD, True),
    ("finance", "IN", "rules.approve", HYD, True),
    ("finance", "IN", "finance.edit", "IN", True),
    ("finance", "IN", "rules.edit", HYD, False),
    ("finance", "IN", "dispatch.edit", HYD, False),
    ("finance", "IN", "payouts.approve", BOI, False),
    # viewer: reads only, never admin lists
    ("viewer", "US", "orders.view", BOI, True),
    ("viewer", "US", "finance.view", BOI, True),
    ("viewer", "US", "orders.edit", BOI, False),
    ("viewer", "US", "refunds.issue", BOI, False),
    ("viewer", "US", "admins.view", "US", False),
    ("viewer", "US", "orders.view", HYD, False),
]


@pytest.mark.parametrize(("role", "scope", "perm", "target", "allowed"), MATRIX)
def test_role_scope_matrix(role, scope, perm, target, allowed) -> None:
    assert authz.can([A(role, scope)], perm, target) is allowed


def test_every_role_is_covered_by_the_matrix() -> None:
    assert {row[0] for row in MATRIX} == set(authz.ROLES)


@pytest.mark.parametrize(("role", "scope", "ok"), [
    ("super_admin", "*", True),
    ("super_admin", "IN", False),
    ("country_manager", "IN", True),
    ("country_manager", "*", False),
    ("city_ops", HYD, True),
    ("city_ops", TG, True),
    ("city_ops", "IN", True),
    ("support_agent", BOI, True),
    ("finance", "US", True),
    ("viewer", "US-ID", True),
    ("viewer", "*", False),
    ("pilot", "IN", False),
])
def test_allowed_levels(role, scope, ok) -> None:
    if ok:
        authz.validate_assignment(role, scope)
    else:
        with pytest.raises(authz.ScopeError):
            authz.validate_assignment(role, scope)


@pytest.mark.parametrize("bad", ["india", "IN_TG", "IN-TG-HYD-X", "I", "in-tg", ""])
def test_bad_scope_codes(bad) -> None:
    with pytest.raises(authz.ScopeError):
        authz.scope_level(bad)


def test_covers_is_by_segment_not_by_prefix() -> None:
    assert authz.covers("IN-TG", "IN-TG-HYD")
    assert not authz.covers("IN-T", "IN-TG")          # not a string prefix match
    assert not authz.covers("IN-TG-HYD", "IN-TG")
    assert authz.covers("*", "US")
    assert not authz.covers("US", "*")


def test_multiple_assignments_combine() -> None:
    admin = [A("city_ops", HYD), A("viewer", "US")]
    assert authz.can(admin, "orders.edit", HYD)
    assert authz.can(admin, "orders.view", BOI)
    assert not authz.can(admin, "orders.edit", BOI)


def test_scopes_with_returns_widest() -> None:
    admin = [A("city_ops", HYD), A("country_manager", "IN"), A("viewer", "US")]
    assert authz.scopes_with(admin, "orders.view") == ["IN", "US"]
    assert authz.scopes_with(admin, "rules.approve") == ["IN"]
    assert authz.scopes_with([A("super_admin", "*")], "rules.approve") == ["*"]
    assert authz.scopes_with([A("viewer", "US")], "orders.edit") == []


@pytest.mark.parametrize(("granter", "role", "scope", "ok"), [
    ([A("super_admin", "*")], "country_manager", "US", True),
    ([A("super_admin", "*")], "super_admin", "*", True),
    ([A("country_manager", "IN")], "city_ops", HYD, True),
    ([A("country_manager", "IN")], "finance", "IN", True),
    ([A("country_manager", "IN")], "support_agent", KA_BLR, True),
    ([A("country_manager", "IN")], "city_ops", BOI, False),
    ([A("country_manager", "IN")], "country_manager", "IN", False),
    ([A("country_manager", "IN")], "super_admin", "*", False),
    ([A("city_ops", HYD)], "support_agent", HYD, False),
    ([A("finance", "IN")], "viewer", "IN", False),
    ([A("viewer", "IN")], "viewer", "IN", False),
])
def test_who_can_grant_what(granter, role, scope, ok) -> None:
    assert authz.can_grant(granter, role, scope) is ok


def test_can_within_for_country_records() -> None:
    # A Hyderabad support agent may look up an Indian customer, not a US one.
    agent = [A("support_agent", HYD)]
    assert authz.can_within(agent, "customers.view", "IN")
    assert not authz.can_within(agent, "customers.view", "US")
