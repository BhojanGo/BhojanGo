"""Pick the rule that applies, without a database (easy to test and reuse).

For each slot (templates.slot_for) take the *active* rule at the most specific
scope that matches the order's context:

    restaurant -> zone -> city -> region (state) -> country -> platform

Active = published and effective_from <= at < effective_to. Ties at the same
level go to the higher priority, then the newer version. A rule marked
``locked`` can't be overridden below its level: narrower rules for the same
slot are ignored.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core_api.modules.rules.service.templates import LEVELS

SPECIFICITY = {lvl: i for i, lvl in enumerate(LEVELS)}  # platform 0 ... restaurant 5


@dataclass(frozen=True)
class Context:
    """Where and when an order happens. Codes as in markets (IN, IN-TG, IN-TG-HYD)."""

    country: str | None = None
    region: str | None = None
    city: str | None = None
    zone_id: str | None = None
    restaurant_id: str | None = None

    def scope_ids(self) -> dict[str, str]:
        out = {"platform": "*"}
        for level, value in (("country", self.country), ("region", self.region), ("city", self.city),
                             ("zone", self.zone_id), ("restaurant", self.restaurant_id)):
            if value:
                out[level] = str(value)
        return out


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    rule_key: uuid.UUID
    version: int
    family: str
    template: str
    slot: str
    params: dict[str, Any]
    scope_level: str
    scope_id: str
    priority: int
    locked: bool
    status: str
    effective_from: datetime
    effective_to: datetime | None
    name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def active_at(self, at: datetime) -> bool:
        return (
            self.status == "published"
            and self.effective_from <= at
            and (self.effective_to is None or at < self.effective_to)
        )


def resolve(candidates: list[Candidate], ctx: Context, at: datetime, overlay: list[Candidate] = ()) -> dict[str, Candidate]:
    """Slot -> the rule that applies. ``overlay`` rules (drafts in the price
    simulator) count as published from ``at`` and replace the versions they
    belong to."""
    scopes = ctx.scope_ids()
    replaced = {c.rule_key for c in overlay}
    pool = [c for c in candidates if c.rule_key not in replaced and c.active_at(at)]
    pool += list(overlay)

    by_slot: dict[str, list[Candidate]] = {}
    for c in pool:
        if scopes.get(c.scope_level) == c.scope_id:
            by_slot.setdefault(c.slot, []).append(c)

    out: dict[str, Candidate] = {}
    for slot, rules in by_slot.items():
        # Widest locked rule wins outright.
        locked = sorted((r for r in rules if r.locked), key=lambda r: SPECIFICITY[r.scope_level])
        if locked:
            floor = SPECIFICITY[locked[0].scope_level]
            rules = [r for r in rules if SPECIFICITY[r.scope_level] <= floor]
        rules.sort(key=lambda r: (SPECIFICITY[r.scope_level], r.priority, r.version), reverse=True)
        out[slot] = rules[0]
    return out
