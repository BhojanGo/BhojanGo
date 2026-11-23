"""Fee model v2 follow-up (R30). Data only: no column is added, dropped or renamed.

Only for countries that exist (QA and local; an empty database is left alone). Each change is a new
published version of the rule (or a new rule where the level had none), effective from the migration; the
version it replaces stops then. Every change has an audit row (who: system, note "R30 (migration 0046)"), so
admin Pricing -> Fees shows old -> new. Orders already placed keep their own snapshot.

  * India's minimum platform fee: ₹85 -> ₹15 (10% stays: ₹100 of food -> ₹15, ₹300 -> ₹30)
  * the payment fee estimate per payment method (card, UPI, wallet, net banking; cash has none):
    US card 2.9% + $0.30 (Stripe); India card / wallet / net banking 2%, UPI 0% (Razorpay)
  * the delivery fee is base + per km/mi, all of it to the delivery partner: US and Boise $3.00 + $1.00/mile,
    India and Hyderabad ₹20 + ₹6/km
  * the delivery partner pay rules (base + distance + waiting, the hourly floor, the batch bonus) stop: a partner
    gets the delivery fee and the whole tip, and nothing is topped up out of the platform fee

Revision ID: 0046_fee_model_v2_fix
Revises: 0045_fee_model_v2
"""
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0046_fee_model_v2_fix"
down_revision = "0045_fee_model_v2"
branch_labels = None
depends_on = None

NS = uuid.UUID("0b8f3e1c-5a77-4c2e-9e64-3d2a8c7f1b46")  # this migration's rows: uuid5(NS, ...)
NOTE = "R30 (migration 0046)"

# (scope_level, scope_id, family, template, slot, name, params); a city only where it exists
CHANGES = [
    ("country", "IN", "fee", "min_platform_fee", "fee:min_platform_fee", "Minimum platform fee", {"amount": "15.00"}),
    ("country", "US", "fee", "card_fee_estimate", "fee:card_fee_estimate", "Payment fee estimate (Stripe)",
     {"card": {"percent": "2.9", "fixed": "0.30"}}),
    ("country", "IN", "fee", "card_fee_estimate", "fee:card_fee_estimate", "Payment fee estimate (Razorpay)",
     {"card": {"percent": "2", "fixed": "0.00"}, "upi": {"percent": "0", "fixed": "0.00"},
      "wallet": {"percent": "2", "fixed": "0.00"}, "net_banking": {"percent": "2", "fixed": "0.00"}}),
    ("country", "US", "delivery_fee", "base_per_distance", "delivery_fee", "United States delivery fee",
     {"base": "3.00", "per_unit": "1.00"}),
    ("city", "US-ID-BOI", "delivery_fee", "base_per_distance", "delivery_fee", "Boise delivery fee",
     {"base": "3.00", "per_unit": "1.00"}),
    ("country", "IN", "delivery_fee", "base_per_distance", "delivery_fee", "India delivery fee",
     {"base": "20.00", "per_unit": "6.00"}),
    ("city", "IN-TG-HYD", "delivery_fee", "base_per_distance", "delivery_fee", "Hyderabad delivery fee",
     {"base": "20.00", "per_unit": "6.00"}),
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
    # The delivery partner pay rules stop: the partner gets the delivery fee and the whole tip.
    pay = conn.execute(sa.text(
        f"SELECT id, rule_key, version, family, template, params, scope_id FROM rules WHERE family = 'rider_pay' "
        f"AND (market_scope LIKE 'US%' OR market_scope LIKE 'IN%') AND {CURRENT}")).mappings().all()
    for r in pay:
        conn.execute(sa.text("UPDATE rules SET effective_to = now(), updated_at = now() WHERE id = :id"), {"id": r["id"]})
        conn.execute(LOG, {"id": _id("audit", "ended", str(r["id"])), "action": "rule.ended", "entity": str(r["rule_key"]),
                           "scope": r["scope_id"], "before": json.dumps(_snap(r)),
                           "after": json.dumps({**_snap(r), "status": "ended", "note": NOTE, "ended": str(r["id"])})})


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
