"""Fee model v2 (R29): the customer pays a platform fee, commission defaults to 0%, the card fee comes off the
restaurant's payout. Adds two columns; nothing is dropped or renamed.

Schema:
  orders.card_fee                          the card fee taken from the restaurant's payout (estimate at placement;
                                           production replaces it with the processor's actual fee)
  order_pricing_snapshots.fee_settings     the fee settings in force at placement, each with the rule it came from

Data, only for countries that exist (QA and local; an empty database is left alone):
  * new country rules (family ``fee``): platform fee 10% of food, minimum $0.99 / ₹85, card fee estimate
    2.9% + $0.30 (US, Stripe) / 2% (India, Razorpay); commission 0% (``commission:rate``, template percent)
  * the service fee rules and the country commission rules they replace stop at the migration (effective_to);
    their versions stay for history, and orders already placed keep their own snapshot
  * India's "GST on platform fees" rule gets a new version that also covers the platform fee line
Idaho and Boise have no fee rules of their own: they inherit the country's. Admins change any of it per country,
state, city or kitchen in admin Pricing → Fees (maker-checker, audited).

Revision ID: 0045_fee_model_v2
Revises: 0044_boise_live_basque_photo
"""
import json
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0045_fee_model_v2"
down_revision = "0044_boise_live_basque_photo"
branch_labels = None
depends_on = None

NS = uuid.UUID("6f1d7a52-2b0e-4d38-9d0a-2f0c1b5e7a29")  # this migration's rules: uuid5(NS, name)
START = "2026-11-22T00:00:00+00:00"  # shown in the audit rows
START_AT = datetime(2026, 11, 22, tzinfo=UTC)  # bound to queries (asyncpg wants a datetime)

NEW_RULES = {
    "US": [
        ("fee", "platform_fee_pct", "fee:platform_fee_pct", "Platform fee", {"percent": "10"}),
        ("fee", "min_platform_fee", "fee:min_platform_fee", "Minimum platform fee", {"amount": "0.99"}),
        ("fee", "card_fee_estimate", "fee:card_fee_estimate", "Card fee estimate (Stripe)", {"percent": "2.9", "fixed": "0.30"}),
        ("commission", "percent", "commission:rate", "Restaurant commission", {"percent": "0", "base": "food_subtotal"}),
    ],
    "IN": [
        ("fee", "platform_fee_pct", "fee:platform_fee_pct", "Platform fee", {"percent": "10"}),
        ("fee", "min_platform_fee", "fee:min_platform_fee", "Minimum platform fee", {"amount": "85"}),
        ("fee", "card_fee_estimate", "fee:card_fee_estimate", "Card fee estimate (Razorpay)", {"percent": "2", "fixed": "0"}),
        ("commission", "percent", "commission:rate", "Restaurant commission", {"percent": "0", "base": "food_subtotal"}),
    ],
}


def _id(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def upgrade() -> None:
    op.add_column("orders", sa.Column("card_fee", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("order_pricing_snapshots", sa.Column("fee_settings", JSONB, nullable=True))

    conn = op.get_bind()
    countries = {r[0] for r in conn.execute(sa.text("SELECT code FROM countries WHERE code IN ('US', 'IN')"))}
    if not countries:
        return
    ended = sa.text(
        "UPDATE rules SET effective_to = GREATEST(effective_from, CAST(:start AS timestamptz)), updated_at = now() "
        "WHERE status = 'published' AND (effective_to IS NULL OR effective_to > CAST(:start AS timestamptz)) "
        "AND market_scope LIKE :scope AND (slot LIKE 'customer_fee:service_fee%' "
        "OR (slot = 'commission:rate' AND scope_level = 'country'))"
    )
    insert = sa.text(
        "INSERT INTO rules (id, rule_key, version, family, template, key, slot, name, params, scope_level, scope_id, "
        "market_scope, priority, locked, status, effective_from, effective_to, created_by, created_at, updated_at) "
        "VALUES (:id, :id, 1, :family, :template, NULL, :slot, :name, CAST(:params AS jsonb), 'country', :country, "
        ":country, 0, false, 'published', CAST(:start AS timestamptz), NULL, NULL, now(), now()) ON CONFLICT DO NOTHING"
    )
    log = sa.text(
        "INSERT INTO audit_log (id, actor_id, action, entity_type, entity_id, scope, before, after, at) "
        "VALUES (:id, NULL, :action, 'rule', :entity, :scope, CAST(:before AS jsonb), CAST(:after AS jsonb), now()) "
        "ON CONFLICT DO NOTHING"
    )
    for country in sorted(countries):
        # The old commission rule's value, so the audit log reads "15% -> 0%" (who: system, this migration).
        old_commission = conn.execute(sa.text(
            "SELECT rule_key, version, family, template, params FROM rules WHERE slot = 'commission:rate' "
            "AND scope_level = 'country' AND scope_id = :c AND status = 'published' "
            "AND (effective_to IS NULL OR effective_to > CAST(:start AS timestamptz)) ORDER BY version DESC LIMIT 1"),
            {"c": country, "start": START_AT}).mappings().first()
        conn.execute(ended, {"start": START_AT, "scope": f"{country}%"})
        for family, template, slot, name, params in NEW_RULES[country]:
            rid = _id(country, slot)
            conn.execute(insert, {"id": rid, "family": family, "template": template, "slot": slot,
                                  "name": name, "params": json.dumps(params), "country": country, "start": START_AT})
            after = {"id": rid, "rule_key": rid, "version": 1, "family": family, "template": template, "params": params,
                     "scope_level": "country", "scope_id": country, "status": "published", "effective_from": START,
                     "effective_to": None, "note": "Fee model v2 (migration 0045)"}
            before = None
            if slot == "commission:rate" and old_commission is not None:
                before = {"version": old_commission["version"], "family": old_commission["family"],
                          "template": old_commission["template"], "params": old_commission["params"], "status": "published"}
            conn.execute(log, {"id": _id("audit", country, slot), "action": "rule.published", "entity": rid,
                               "scope": country, "before": json.dumps(before), "after": json.dumps(after)})
    if "IN" in countries:
        # GST on platform fees: a new version that also covers the platform fee (the tax rules decide, not code).
        rows = conn.execute(sa.text(
            "SELECT id, rule_key, version, name, params, market_scope, priority, locked FROM rules "
            "WHERE slot = 'tax:rate_on_lines:gst_fees' AND scope_level = 'country' AND scope_id = 'IN' "
            "AND status = 'published' AND effective_to IS NULL")).mappings().all()
        for r in rows:
            params = dict(r["params"])
            if "platform_fee" in params.get("target_lines", []):
                continue
            params["target_lines"] = [*params["target_lines"], "platform_fee"]
            new_id = _id("IN", "gst_fees", str(r["rule_key"]))
            conn.execute(sa.text("UPDATE rules SET effective_to = GREATEST(effective_from, CAST(:start AS timestamptz)) "
                                 "WHERE id = :id"), {"id": r["id"], "start": START_AT})
            conn.execute(sa.text(
                "INSERT INTO rules (id, rule_key, version, family, template, key, slot, name, params, scope_level, scope_id, "
                "market_scope, priority, locked, status, effective_from, effective_to, created_by, created_at, updated_at) "
                "VALUES (:id, :key, :version, 'tax', 'rate_on_lines', 'gst_fees', 'tax:rate_on_lines:gst_fees', :name, "
                "CAST(:params AS jsonb), 'country', 'IN', :scope, :priority, :locked, 'published', "
                "GREATEST(CAST(:start AS timestamptz), now()), NULL, NULL, now(), now()) ON CONFLICT DO NOTHING"),
                {"id": new_id, "key": r["rule_key"], "version": r["version"] + 1, "name": r["name"], "params": json.dumps(params),
                 "scope": r["market_scope"], "priority": r["priority"], "locked": r["locked"], "start": START_AT})


def downgrade() -> None:
    conn = op.get_bind()
    mine = [_id(c, slot) for c, rules in NEW_RULES.items() for _, _, slot, _, _ in rules]
    conn.execute(sa.text("DELETE FROM rules WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": mine})
    conn.execute(sa.text("DELETE FROM audit_log WHERE id = ANY(CAST(:ids AS uuid[]))"),
                 {"ids": [_id("audit", c, slot) for c, rules in NEW_RULES.items() for _, _, slot, _, _ in rules]})
    gst = conn.execute(sa.text("SELECT id, rule_key FROM rules WHERE slot = 'tax:rate_on_lines:gst_fees' AND scope_id = 'IN'")).all()
    ours = [str(i) for i, key in gst if str(i) == _id("IN", "gst_fees", str(key))]
    if ours:
        conn.execute(sa.text("DELETE FROM rules WHERE id = ANY(CAST(:ids AS uuid[]))"), {"ids": ours})
    # Reopen what upgrade ended (the rules it ended stop exactly at START, or at their own start if later).
    conn.execute(sa.text(
        "UPDATE rules SET effective_to = NULL WHERE status = 'published' "
        "AND effective_to = GREATEST(effective_from, CAST(:start AS timestamptz)) "
        "AND (slot LIKE 'customer_fee:service_fee%' OR (slot = 'commission:rate' AND scope_level = 'country') "
        "OR (slot = 'tax:rate_on_lines:gst_fees' AND scope_id = 'IN')) AND (market_scope LIKE 'US%' OR market_scope LIKE 'IN%')"),
        {"start": START_AT})
    op.drop_column("order_pricing_snapshots", "fee_settings")
    op.drop_column("orders", "card_fee")
