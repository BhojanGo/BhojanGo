"""Delivery fee from distance bands (R31). Data only: no column is added, dropped or renamed.

Only for countries that exist (QA and local; an empty database is left alone). Each change is a new
published version of the level's rule (or a new rule where the level had none), effective from the migration;
the version it replaces stops then. Every change has an audit row (who: system, note "R31 (migration 0047)").
Orders already placed keep their own snapshot.

  * the delivery fee comes from distance bands (road distance), replacing R30's base + per mile/km:
    US and Boise (miles) 0-2 $3.50 | >2-4 $4.50 | >4-6 $5.50 | >6-8 $6.50;
    India and Hyderabad (km) 0-3 ₹30 | >3-5 ₹40 | >5-7 ₹50 (whole rupees)
  * the max delivery distance is the last band: US 8 mi (was 6), India 7 km (was 10)

Revision ID: 0047_delivery_bands
Revises: 0046_fee_model_v2_fix
"""
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0047_delivery_bands"
down_revision = "0046_fee_model_v2_fix"
branch_labels = None
depends_on = None

NS = uuid.UUID("5c1e9a0d-3b4f-4e8a-a7c2-91d6f0b3e5a8")  # this migration's rows: uuid5(NS, ...)
NOTE = "R31 (migration 0047)"

US_BANDS = {"slabs": [{"up_to": "2", "fee": "3.50"}, {"up_to": "4", "fee": "4.50"}, {"up_to": "6", "fee": "5.50"},
                      {"up_to": "8", "fee": "6.50"}], "beyond_per_unit": None}
IN_BANDS = {"slabs": [{"up_to": "3", "fee": "30"}, {"up_to": "5", "fee": "40"}, {"up_to": "7", "fee": "50"}],
            "beyond_per_unit": None}
# (scope_level, scope_id, family, template, slot, name, params); a city only where it exists
CHANGES = [
    ("country", "US", "delivery_fee", "distance_slabs", "delivery_fee", "United States delivery fee", US_BANDS),
    ("city", "US-ID-BOI", "delivery_fee", "distance_slabs", "delivery_fee", "Boise delivery fee", US_BANDS),
    ("country", "IN", "delivery_fee", "distance_slabs", "delivery_fee", "India delivery fee", IN_BANDS),
    ("city", "IN-TG-HYD", "delivery_fee", "distance_slabs", "delivery_fee", "Hyderabad delivery fee", IN_BANDS),
    ("country", "US", "business", "max_radius", "business:max_radius", "Max delivery distance", {"distance": "8"}),
    ("country", "IN", "business", "max_radius", "business:max_radius", "Max delivery distance", {"distance": "7"}),
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
    cities = {r[0] for r in conn.execute(sa.text("SELECT code FROM cities WHERE code IN ('US-ID-BOI', 'IN-TG-HYD')"))}
    for level, scope, family, template, slot, name, params in CHANGES:
        if scope[:2] not in countries or (level == "city" and scope not in cities):
            continue
        old = conn.execute(sa.text(
            f"SELECT id, rule_key, version, family, template, params, market_scope, priority, locked FROM rules "
            f"WHERE slot = :slot AND scope_level = :level AND scope_id = :scope AND {CURRENT} "
            f"ORDER BY version DESC LIMIT 1"), {"slot": slot, "level": level, "scope": scope}).mappings().first()
        if old is not None and old["template"] == template and old["params"] == params:
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
