"""The resolver picks the most specific active rule per slot."""
import uuid
from datetime import UTC, datetime, timedelta

from core_api.modules.rules.service.resolver import Candidate, Context, resolve

T0 = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
ZONE = str(uuid.uuid4())
REST = str(uuid.uuid4())
HYD = Context(country="IN", region="IN-TG", city="IN-TG-HYD", zone_id=ZONE, restaurant_id=REST)


def rule(level: str, scope: str, *, slot: str = "customer_fee:service_fee", value: int = 1, priority: int = 0,
         version: int = 1, key: uuid.UUID | None = None, locked: bool = False, status: str = "published",
         start: datetime = T0 - timedelta(days=30), end: datetime | None = None) -> Candidate:
    return Candidate(
        id=uuid.uuid4(), rule_key=key or uuid.uuid4(), version=version, family=slot.split(":")[0],
        template=slot.split(":")[-1], slot=slot, params={"v": value}, scope_level=level, scope_id=scope,
        priority=priority, locked=locked, status=status, effective_from=start, effective_to=end,
    )


def pick(rules, ctx=HYD, at=T0, overlay=()):
    return {s: c.params["v"] for s, c in resolve(rules, ctx, at, list(overlay)).items()}


def test_most_specific_level_wins() -> None:
    levels = [("platform", "*"), ("country", "IN"), ("region", "IN-TG"), ("city", "IN-TG-HYD"), ("zone", ZONE), ("restaurant", REST)]
    rules = [rule(lvl, sid, value=i) for i, (lvl, sid) in enumerate(levels)]
    assert pick(rules) == {"customer_fee:service_fee": 5}  # restaurant
    for drop in range(5, 0, -1):  # remove the most specific one at a time
        rules = rules[:drop]
        assert pick(rules) == {"customer_fee:service_fee": drop - 1}


def test_rules_elsewhere_never_apply() -> None:
    rules = [rule("city", "US-ID-BOI", value=9), rule("restaurant", str(uuid.uuid4()), value=8), rule("country", "IN", value=1)]
    assert pick(rules) == {"customer_fee:service_fee": 1}
    assert pick(rules, ctx=Context(country="US", region="US-ID", city="US-ID-BOI")) == {"customer_fee:service_fee": 9}


def test_only_active_rules_count() -> None:
    rules = [
        rule("city", "IN-TG-HYD", value=1, start=T0 - timedelta(days=10), end=T0),  # just ended
        rule("city", "IN-TG-HYD", value=2, start=T0 + timedelta(seconds=1)),  # not started
        rule("city", "IN-TG-HYD", value=3, status="draft"),
        rule("city", "IN-TG-HYD", value=4, status="pending_approval"),
        rule("country", "IN", value=5),
    ]
    assert pick(rules) == {"customer_fee:service_fee": 5}
    assert pick(rules, at=T0 - timedelta(seconds=1)) == {"customer_fee:service_fee": 1}
    assert pick(rules, at=T0 + timedelta(hours=1)) == {"customer_fee:service_fee": 2}


def test_versions_hand_over_at_the_start_date() -> None:
    key = uuid.uuid4()
    switch = T0 + timedelta(days=1)
    rules = [rule("city", "IN-TG-HYD", key=key, version=1, value=1, end=switch),
             rule("city", "IN-TG-HYD", key=key, version=2, value=2, start=switch)]
    assert pick(rules, at=switch - timedelta(microseconds=1)) == {"customer_fee:service_fee": 1}
    assert pick(rules, at=switch) == {"customer_fee:service_fee": 2}


def test_ties_go_to_priority_then_version() -> None:
    a, b = rule("city", "IN-TG-HYD", value=1, priority=0, version=3), rule("city", "IN-TG-HYD", value=2, priority=5)
    assert pick([a, b]) == {"customer_fee:service_fee": 2}
    c, d = rule("city", "IN-TG-HYD", value=3, version=1), rule("city", "IN-TG-HYD", value=4, version=2)
    assert pick([c, d]) == {"customer_fee:service_fee": 4}


def test_locked_rule_cannot_be_overridden_below() -> None:
    rules = [rule("country", "IN", value=1, locked=True), rule("city", "IN-TG-HYD", value=2), rule("restaurant", REST, value=3)]
    assert pick(rules) == {"customer_fee:service_fee": 1}
    # A lock at the city still lets the city's own rule apply, and stops zone/restaurant ones.
    rules = [rule("country", "IN", value=1), rule("city", "IN-TG-HYD", value=2, locked=True), rule("zone", ZONE, value=3)]
    assert pick(rules) == {"customer_fee:service_fee": 2}


def test_slots_resolve_independently() -> None:
    rules = [
        rule("city", "IN-TG-HYD", slot="delivery_fee", value=35),
        rule("restaurant", REST, slot="delivery_fee", value=0),  # restaurant-funded free delivery
        rule("country", "IN", slot="tax:rate_on_lines:gst_food", value=5),
        rule("country", "IN", slot="tax:rate_on_lines:gst_fees", value=18),
        rule("platform", "*", slot="business:accept_timeout", value=180),
    ]
    assert pick(rules) == {
        "delivery_fee": 0,
        "tax:rate_on_lines:gst_food": 5,
        "tax:rate_on_lines:gst_fees": 18,
        "business:accept_timeout": 180,
    }


def test_overlay_drafts_replace_their_live_version() -> None:
    key = uuid.uuid4()
    live = rule("city", "IN-TG-HYD", key=key, value=2)
    draft = rule("city", "IN-TG-HYD", key=key, version=2, value=3, start=T0)
    new_rule = rule("zone", ZONE, slot="customer_fee:surge_levy", value=15, start=T0)
    assert pick([live]) == {"customer_fee:service_fee": 2}
    assert pick([live], overlay=[draft, new_rule]) == {"customer_fee:service_fee": 3, "customer_fee:surge_levy": 15}


def test_context_without_zone_or_restaurant() -> None:
    rules = [rule("zone", ZONE, value=9), rule("city", "IN-TG-HYD", value=1)]
    assert pick(rules, ctx=Context(country="IN", region="IN-TG", city="IN-TG-HYD")) == {"customer_fee:service_fee": 1}
    assert pick([rule("platform", "*", value=7)], ctx=Context()) == {"customer_fee:service_fee": 7}
