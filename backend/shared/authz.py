"""Admin roles, what each may do, and where (docs/specs/01-structure.md, section 6).

Each admin holds one or more *assignments*: a role at a scope. Scopes are
market codes, from widest to narrowest:

    global     "*"            super admin only
    country    "IN"           ISO 3166-1
    state      "IN-TG"        ISO 3166-2
    city       "IN-TG-HYD"    state code + city code

An assignment covers its own scope and everything inside it (``IN`` covers
``IN-TG`` and ``IN-TG-HYD``, not ``US``). A check passes when any assignment
whose role has the permission covers the target scope. These are pure
functions, so realtime and worker can check the ``adm`` token claim too.
"""
from dataclasses import dataclass

GLOBAL = "*"

ROLES = ("super_admin", "country_manager", "city_ops", "support_agent", "finance", "viewer")

VIEW = {
    "markets.view", "rules.view", "partners.view", "riders.view", "orders.view",
    "customers.view", "finance.view", "reports.view", "admins.view",
}

PERMISSIONS: dict[str, frozenset[str]] = {
    "super_admin": frozenset({"*"}),
    "country_manager": frozenset(VIEW | {
        "markets.edit", "rules.edit", "rules.approve", "pricing.simulate",
        "partners.edit", "riders.edit", "orders.edit", "dispatch.edit",
        "customers.edit", "refunds.issue", "admins.grant", "zones.pause",
    }),
    "city_ops": frozenset({
        "markets.view", "rules.view", "pricing.simulate", "partners.view", "partners.edit",
        "riders.view", "riders.edit", "orders.view", "orders.edit", "dispatch.edit",
        "customers.view", "refunds.issue", "reports.view", "zones.pause",
    }),
    "support_agent": frozenset({
        "orders.view", "customers.view", "customers.edit", "refunds.issue", "partners.view", "riders.view",
    }),
    "finance": frozenset({
        "finance.view", "finance.edit", "payouts.approve", "refunds.issue", "rules.view",
        "rules.approve", "orders.view", "reports.view", "partners.view", "riders.view",
    }),
    "viewer": frozenset(VIEW - {"admins.view"}),
}

# Which scope levels each role may be assigned at.
ALLOWED_LEVELS: dict[str, frozenset[str]] = {
    "super_admin": frozenset({"global"}),
    **{r: frozenset({"country", "state", "city"}) for r in ROLES if r != "super_admin"},
}

# Roles a holder of admins.grant may hand out (super admin: any).
GRANTABLE_BY_COUNTRY_MANAGER = frozenset({"city_ops", "support_agent", "finance", "viewer"})


class ScopeError(ValueError):
    pass


def scope_level(code: str) -> str:
    if code == GLOBAL:
        return "global"
    parts = code.split("-")
    if not all(p.isalnum() and p.isupper() for p in parts) or len(parts[0]) != 2 or len(parts) > 3:
        raise ScopeError(f"Invalid scope code {code!r}; use IN, IN-TG or IN-TG-HYD")
    return ("country", "state", "city")[len(parts) - 1]


def covers(assignment_scope: str, target_scope: str) -> bool:
    """True when assignment_scope is target_scope or contains it."""
    if assignment_scope == GLOBAL:
        return True
    if target_scope == GLOBAL:
        return False
    return target_scope == assignment_scope or target_scope.startswith(assignment_scope + "-")


@dataclass(frozen=True)
class Assignment:
    role: str
    scope: str

    @classmethod
    def parse(cls, claim: str) -> "Assignment":
        role, _, scope = claim.partition("@")
        return cls(role, scope)

    def claim(self) -> str:
        return f"{self.role}@{self.scope}"


def validate_assignment(role: str, scope: str) -> None:
    if role not in PERMISSIONS:
        raise ScopeError(f"Unknown role {role!r}; one of {', '.join(ROLES)}")
    level = scope_level(scope)
    if level not in ALLOWED_LEVELS[role]:
        allowed = ", ".join(sorted(ALLOWED_LEVELS[role]))
        raise ScopeError(f"{role} can only be assigned at {allowed} level, not {level}")


def role_allows(role: str, permission: str) -> bool:
    perms = PERMISSIONS.get(role, frozenset())
    return "*" in perms or permission in perms


def can(assignments: list[Assignment], permission: str, scope: str) -> bool:
    return any(role_allows(a.role, permission) and covers(a.scope, scope) for a in assignments)


def can_within(assignments: list[Assignment], permission: str, scope: str) -> bool:
    """Looser check for records that belong to a whole country (e.g. a
    customer): the permission held anywhere at, above or inside that scope."""
    return any(
        role_allows(a.role, permission) and (covers(a.scope, scope) or covers(scope, a.scope)) for a in assignments
    )


def scopes_with(assignments: list[Assignment], permission: str) -> list[str]:
    """The widest scopes where the permission holds (for filtering lists).
    ["*"] means everywhere; [] means nowhere."""
    scopes = sorted({a.scope for a in assignments if role_allows(a.role, permission)}, key=lambda s: (len(s), s))
    widest: list[str] = []
    for s in scopes:
        if not any(covers(w, s) for w in widest):
            widest.append(s)
    return widest


def can_grant(granter: list[Assignment], role: str, scope: str) -> bool:
    """Super admins grant anything; country managers grant the operational
    roles inside their own country (never super_admin or country_manager)."""
    if any(a.role == "super_admin" for a in granter):
        return True
    if role not in GRANTABLE_BY_COUNTRY_MANAGER:
        return False
    return can(granter, "admins.grant", scope)
