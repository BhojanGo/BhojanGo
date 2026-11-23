"""Fees in the admin console (R29, fee model v2): for one level (Country -> State/Region -> City -> Restaurant),
each fee setting's effective value and where it comes from ("Inherited from: USA"), the level's own rule (with its
effective dates), changes waiting for a second admin, and the audit log (who, when, old -> new).

Settings: platform_fee_pct, min_platform_fee, restaurant_commission_pct, card_fee_estimate (R30: per payment method),
delivery_fee (R31: distance bands, all of it to the delivery partner), max_delivery_distance (R31). Each is a rule in the
rule engine (one slot each, so each inherits on its own). Setting a value makes a draft (or a new version of the
level's rule) and sends it for approval: these are money rules, so a second admin approves them (rules API).
Unsetting ends the level's rule, so the level inherits again.

Permissions: read rules.view, set rules.edit, unset rules.approve, at the level's market.
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.audit import service as audit
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.pricing.service import fees
from core_api.modules.rules.models import Rule
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleError, RuleService
from shared.db import get_db

router = APIRouter(prefix="/rules/fees", tags=["Rules"])

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("rules.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("rules.edit"))]
Approver = Annotated[AdminContext, Depends(require_permission("rules.approve"))]

Level = Literal["country", "region", "city", "restaurant"]
Field_ = Literal["platform_fee_pct", "min_platform_fee", "restaurant_commission_pct", "card_fee_estimate", "delivery_fee",
                 "max_delivery_distance", "pickup_platform_fee_pct", "gst_offer_base"]
LEVELS: tuple[str, ...] = ("country", "region", "city", "restaurant")
# field -> (family, template, rule name)
TEMPLATE = {
    "platform_fee_pct": ("fee", "platform_fee_pct", "Platform fee"),
    "min_platform_fee": ("fee", "min_platform_fee", "Minimum platform fee"),
    "restaurant_commission_pct": ("commission", "percent", "Restaurant commission"),
    "card_fee_estimate": ("fee", "card_fee_estimate", "Payment fee estimate"),
    "delivery_fee": ("delivery_fee", "distance_slabs", "Delivery fee"),  # R31: distance bands
    "max_delivery_distance": ("business", "max_radius", "Max delivery distance"),
    "pickup_platform_fee_pct": ("fee", "pickup_platform_fee_pct", "Pickup platform fee"),  # R32
    "gst_offer_base": ("business", "gst_offer_base", "Platform-funded offers reduce GST base"),  # R32, country only
}


def _now() -> datetime:
    return datetime.now(UTC)


async def _chain(db: AsyncSession, level: str, scope_id: str) -> list[dict[str, str]]:
    """The level and the levels above it, widest first: [{level, scope_id, name}]."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.markets.models import City, Country, Region

    city_code: str | None = None
    out: list[dict[str, str]] = []
    if level == "restaurant":
        r = await db.get(Restaurant, uuid.UUID(scope_id))
        if r is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Restaurant not found"})
        city_code = (await db.execute(select(City.code).where(City.name == r.city, City.code.like(f"{r.country}-%"))
                                      .limit(1))).scalar()
        if city_code is None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NO_CITY", "message": f"{r.name} isn't in a city we know"})
        rest = {"level": "restaurant", "scope_id": str(r.id), "name": r.name}
        country = r.country  # a restaurant: its own country (its scope id is a uuid)
    else:
        rest = None
        city_code = scope_id if level == "city" else None
        country = scope_id[:2]
    codes = {"country": country, "region": scope_id if level == "region" else None, "city": city_code}
    if city_code:
        codes["region"] = city_code[:5]
    for lvl, model in (("country", Country), ("region", Region), ("city", City)):
        code = codes.get(lvl)
        if not code:
            continue
        name = (await db.execute(select(model.name).where(model.code == code))).scalar()
        if name is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": f"No {lvl} {code}"})
        out.append({"level": lvl, "scope_id": code, "name": name})
        if lvl == level:
            break
    if rest:
        out.append(rest)
    return out


def _context(chain: list[dict[str, str]]) -> Context:
    ids = {c["level"]: c["scope_id"] for c in chain}
    return Context(country=ids.get("country"), region=ids.get("region"), city=ids.get("city"),
                   restaurant_id=ids.get("restaurant"))


def _market(chain: list[dict[str, str]]) -> str:
    """The market an admin needs permission for: the level's code (a restaurant: its city)."""
    return next(c["scope_id"] for c in reversed(chain) if c["level"] != "restaurant")


def _rule_value(field: str, r: Rule) -> dict[str, str]:
    from core_api.modules.rules.service.resolver import Candidate

    c = Candidate(id=r.id, rule_key=r.rule_key, version=r.version, family=r.family, template=r.template, slot=r.slot,
                  params=r.params, scope_level=r.scope_level, scope_id=r.scope_id, priority=r.priority, locked=r.locked,
                  status=r.status, effective_from=r.effective_from, effective_to=r.effective_to)
    return fees.settings({fees.SLOTS[field]: c})[field].value or {}


def _rule_out(field: str, r: Rule) -> dict[str, Any]:
    return {"rule_id": str(r.id), "rule_key": str(r.rule_key), "version": r.version, "status": r.status,
            "value": _rule_value(field, r), "template": r.template,
            "effective_from": r.effective_from.isoformat(), "effective_to": r.effective_to.isoformat() if r.effective_to else None}


async def _own(db: AsyncSession, level: str, scope_id: str) -> dict[str, list[Rule]]:
    """This level's rules per field: published (current or scheduled) and open (draft, waiting)."""
    q = select(Rule).where(Rule.scope_level == level, Rule.scope_id == scope_id, Rule.slot.in_(list(fees.SLOTS.values())),
                           Rule.status.in_(("published", "draft", "pending_approval")))
    rows = list((await db.execute(q.order_by(Rule.effective_from, Rule.version))).scalars())
    by_slot = {slot: field for field, slot in fees.SLOTS.items()}
    out: dict[str, list[Rule]] = {f: [] for f in fees.FIELDS}
    for r in rows:
        if r.status == "published" and r.effective_to is not None and r.effective_to <= _now():
            continue  # ended
        out[by_slot[r.slot]].append(r)
    return out


async def _history(db: AsyncSession, level: str, scope_id: str) -> list[dict[str, Any]]:
    """Who changed what at this level, and when: old -> new, from the audit log."""
    keys = (await db.execute(select(Rule.rule_key, Rule.slot).where(
        Rule.scope_level == level, Rule.scope_id == scope_id, Rule.slot.in_(list(fees.SLOTS.values()))))).all()
    if not keys:
        return []
    field_of = {str(k): next(f for f, s in fees.SLOTS.items() if s == slot) for k, slot in keys}
    rows = await audit.history(db, "rule", list(field_of))
    from core_api.modules.identity.service.profile import user_profile

    names: dict[str, str] = {}
    out = []
    for a in rows:
        field = field_of.get(str(a.entity_id))
        if field is None:
            continue
        who = "system"
        if a.actor_id:
            if str(a.actor_id) not in names:
                p = await user_profile(db, a.actor_id) or {}
                names[str(a.actor_id)] = p.get("name") or p.get("email") or "an admin"
            who = names[str(a.actor_id)]

        def val(snap: dict | None) -> dict | None:
            if not snap or "params" not in snap:
                return None
            r = Rule(id=uuid.uuid4(), rule_key=uuid.uuid4(), version=snap.get("version") or 1, family=snap["family"],
                     template=snap["template"], slot=fees.SLOTS[field], params=snap["params"], scope_level=level,
                     scope_id=scope_id, priority=0, locked=False, status=snap.get("status") or "draft",
                     effective_from=_now(), effective_to=None)
            return _rule_value(field, r)

        out.append({"at": a.at.isoformat(), "who": who, "action": a.action, "field": field,
                    "old": val(a.before), "new": val(a.after),
                    "effective_from": (a.after or {}).get("effective_from"), "effective_to": (a.after or {}).get("effective_to")})
    return out[::-1]


@router.get("")
async def fee_level(admin: Viewer, db: DB, level: Level = Query(...), scope_id: str = Query(..., min_length=2)) -> dict:
    """Every fee setting at this level: the effective value, where it comes from, and the level's own rule."""
    chain = await _chain(db, level, scope_id)
    admin.require("rules.view", _market(chain), within=True)
    resolved = await RuleService(db).resolve(_context(chain), _now())
    tier = None
    if level == "restaurant":
        from core_api.modules.catalog.models.restaurant import Restaurant

        tier = (await db.get(Restaurant, uuid.UUID(scope_id))).tier  # type: ignore[union-attr]
    effective = fees.settings(resolved, tier)
    names = {(c["level"], c["scope_id"]): c["name"] for c in chain}
    own = await _own(db, level, scope_id)
    fields = []
    from core_api.modules.rules.service.templates import allowed_levels

    for f in fees.FIELDS:
        family, template, _ = TEMPLATE[f]
        if level not in allowed_levels(family, template):
            continue  # R32: e.g. the GST offer setting is the country's only
        if f == "gst_offer_base" and chain[0]["scope_id"] != "IN":
            continue  # India's GST
        s = effective[f]
        src = s.source
        rules = own[f]
        current = next((r for r in rules if r.status == "published" and r.effective_from <= _now()), None)
        fields.append({
            "field": f,
            "effective": s.value,
            "source": {"level": src.level, "scope_id": src.scope_id, "name": names.get((src.level, src.scope_id), src.scope_id),
                       "rule_id": src.rule_id, "version": src.version} if src else None,
            "inherited": bool(src) and (src.level, src.scope_id) != (level, chain[-1]["scope_id"]),
            "own": _rule_out(f, current) if current else None,
            "scheduled": [_rule_out(f, r) for r in rules if r.status == "published" and r.effective_from > _now()],
            "pending": [_rule_out(f, r) for r in rules if r.status in ("draft", "pending_approval")],
        })
    return {"level": level, "scope_id": chain[-1]["scope_id"], "name": chain[-1]["name"], "chain": chain,
            "fields": fields, "history": await _history(db, level, chain[-1]["scope_id"])}


class SetFee(BaseModel):
    level: Level
    scope_id: str
    field: Field_
    value: dict[str, Any]  # {"percent": 9} | {"amount": "0.99"} | {"card": {"percent": "2.9", "fixed": "0.30"}, "upi": ...}
    #                        | {"base": "3.00", "per_unit": "1.00"} (delivery fee)
    effective_from: datetime | None = None
    effective_to: datetime | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def set_fee(data: SetFee, admin: Editor, db: DB) -> dict:
    """Set a fee at this level from ``effective_from`` (now if empty): a draft sent for a second admin's approval."""
    chain = await _chain(db, data.level, data.scope_id)
    admin.require("rules.edit", _market(chain))
    family, template, name = TEMPLATE[data.field]
    params = {"percent": data.value.get("percent")} if template == "percent" else data.value
    if template == "gst_offer_base":  # R32: {"on": true|false}
        params = {"platform_offers_reduce_base": str(data.value.get("on")).lower() in ("true", "1", "on")}
    if template == "distance_slabs":  # R31: {"bands": [{up_to, fee}...]}
        params = {"slabs": data.value.get("bands") or data.value.get("slabs") or []}
    svc = RuleService(db)
    scope = chain[-1]["scope_id"]
    own = await _own(db, data.level, scope)
    try:
        if own[data.field] and any(r.status in ("draft", "pending_approval") for r in own[data.field]):
            raise RuleError("A change to this fee is already waiting for approval here; approve or reject it first")
        base = next((r for r in own[data.field] if r.status == "published"), None)
        if base is not None:  # R30: a delivery fee on slabs becomes base + per km/mi in a new version of its rule
            r = await svc.new_version(admin.user.id, base.id, params=params, effective_from=data.effective_from,
                                      template=template)
            if data.effective_to is not None:
                r = await svc.update_draft(admin.user.id, r.id, {"effective_to": data.effective_to})
        else:
            r = await svc.create(admin.user.id, family=family, template=template, params=params, scope_level=data.level,
                                 scope_id=scope, name=name, effective_from=data.effective_from, effective_to=data.effective_to)
        r = await svc.submit(admin.user.id, r.id)
    except (RuleError, ValueError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "INVALID_FEE", "message": str(e)})
    return _rule_out(data.field, r)


@router.delete("", status_code=status.HTTP_200_OK)
async def unset_fee(admin: Approver, db: DB, level: Level = Query(...), scope_id: str = Query(...),
                    field: Field_ = Query(...)) -> dict:
    """Stop this level's own value: from now the level inherits again (the version stays in the history)."""
    chain = await _chain(db, level, scope_id)
    admin.require("rules.approve", _market(chain))
    own = await _own(db, level, chain[-1]["scope_id"])
    current = [r for r in own[field] if r.status == "published"]
    if not current:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_SET", "message": "This level has no value of its own"})
    svc = RuleService(db)
    for r in current:
        await svc.end(admin.user.id, r.id)
    return {"ended": [str(r.id) for r in current]}
