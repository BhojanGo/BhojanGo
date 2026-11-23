"""Idaho's taxable lines as a state tax setting, and the busy-hour fee off (R33). Rules only: no column is
added, dropped or renamed.

Each a new published rule with an audit row (who: system, note "R33 (migration 0049)"), only where the market
exists (QA and local; an empty database is left alone):
  * Idaho (state US-ID): tax:external with taxable_lines food, packaging, platform fee and the other service
    charges; not the delivery fee (separately stated) and not the busy-hour fee (a delivery charge). Tips are
    never taxed.
  * Hyderabad's busy-hour fee (customer_fee:surge_levy): amount 0 (off), where one is published today.

Revision ID: 0049_idaho_tax_lines
Revises: 0048_pickup_orders
"""
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0049_idaho_tax_lines"
down_revision = "0048_pickup_orders"
branch_labels = None
depends_on = None

NS = uuid.UUID("7d2f4b1e-8a6c-4c3d-9e5f-0a1b2c3d4e49")  # this migration's rows: uuid5(NS, ...)
NOTE = "R33 (migration 0049)"
IDAHO = ["food", "packaging", "platform_fee", "service_fee", "small_order_fee", "late_night_fee"]

# (scope_level, scope_id, family, template, slot, name, params, only_replace)
CHANGES = [
    ("region", "US-ID", "tax", "external", "tax:external", "Idaho sales tax: taxable lines",
     {"provider": "stripe_tax", "collected_by": "platform", "taxable_lines": IDAHO}, False),
    ("city", "IN-TG-HYD", "customer_fee", "surge_levy", "customer_fee:surge_levy", "Busy-hour fee (off)",
     {"windows": [{"start": "19:00", "end": "21:30"}], "amount": "0"}, True),
]

CURRENT = ("status = 'published' AND (effective_to IS NULL OR effective_to > now())")
LOG = sa.text(
    "INSERT INTO audit_log (id, actor_id, action, entity_type, entity_id, scope, before, after, at) "
    "VALUES (:id, NULL, :action, 'rule', :entity, :scope, CAST(:before AS jsonb), CAST(:after AS jsonb), now()) "
    "ON CONFLICT DO NOTHING"
)


def _id(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def _snap(r: dict) -> dict:
    return {"version": r["version"], "family": r["family"], "template": r["template"], "params": r["params"],
            "status": "published"}


def upgrade() -> None:
    conn = op.get_bind()
    countries = {r[0] for r in conn.execute(sa.text("SELECT code FROM countries WHERE code IN ('US', 'IN')"))}
    if not countries:
        return
    for level, scope, family, template, slot, name, params, only_replace in CHANGES:
        if scope[:2] not in countries:
            continue
        old = conn.execute(sa.text(
            f"SELECT id, rule_key, version, family, template, params, market_scope, priority, locked FROM rules "
            f"WHERE slot = :slot AND scope_level = :level AND scope_id = :scope AND {CURRENT} "
            f"ORDER BY version DESC LIMIT 1"), {"slot": slot, "level": level, "scope": scope}).mappings().first()
        if old is not None and old["template"] == template and old["params"] == params:
            continue
        if old is None and only_replace:
            continue
        key = str(old["rule_key"]) if old else _id("rule", level, scope, slot)
        version = old["version"] + 1 if old else 1
        rid = key if old is None else _id(key, str(version))
        if old is not None:
            conn.execute(sa.text("UPDATE rules SET effective_to = now(), updated_at = now() WHERE id = :id"), {"id": old["id"]})
        conn.execute(sa.text(
            "INSERT INTO rules (id, rule_key, version, family, template, key, slot, name, params, scope_level, scope_id, "
            "market_scope, priority, locked, status, effective_from, effective_to, created_by, created_at, updated_at) "
            "VALUES (:id, :key, :version, :family, :template, NULL, :slot, :name, CAST(:params AS jsonb), :level, :scope, "
            ":market, :priority, :locked, 'published', now(), NULL, NULL, now(), now()) ON CONFLICT DO NOTHING"),
            {"id": rid, "key": key, "version": version, "family": family, "template": template, "slot": slot, "name": name,
             "params": json.dumps(params), "level": level, "scope": scope,
             "market": old["market_scope"] if old else scope, "priority": old["priority"] if old else 0,
             "locked": old["locked"] if old else False})
        after = {"id": rid, "rule_key": key, "version": version, "family": family, "template": template, "params": params,
                 "scope_level": level, "scope_id": scope, "status": "published", "effective_to": None, "note": NOTE,
                 "replaces": str(old["id"]) if old else None}
        # entity: the rule key, as the rules API records it (admin Pricing -> Fees reads the history by key)
        conn.execute(LOG, {"id": _id("audit", rid), "action": "rule.published", "entity": key, "scope": scope,
                           "before": json.dumps(_snap(old) if old else None), "after": json.dumps(after)})


def downgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, action, entity_id, after FROM audit_log WHERE entity_type = 'rule' AND after->>'note' = :note"),
        {"note": NOTE}).mappings().all()
    for a in rows:
        after = a["after"] or {}
        reopen = after.get("ended") or after.get("replaces")
        if reopen:
            conn.execute(sa.text("UPDATE rules SET effective_to = NULL, updated_at = now() WHERE id = :id"), {"id": reopen})
        if a["action"] == "rule.published":
            conn.execute(sa.text("DELETE FROM rules WHERE id = :id"), {"id": after["id"]})
    conn.execute(sa.text("DELETE FROM audit_log WHERE entity_type = 'rule' AND after->>'note' = :note"), {"note": NOTE})
