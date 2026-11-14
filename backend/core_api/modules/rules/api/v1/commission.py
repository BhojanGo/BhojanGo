"""Commission in the admin console: a restaurant's effective rate and where it
comes from, tier changes (approved by a second admin, audited), and a preview
of a commission draft against the last days' orders before it's submitted.
"""
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.audit import service as audit
from core_api.modules.rules.models import TierChange
from core_api.modules.rules.service import templates
from core_api.modules.rules.service.resolver import Context
from core_api.modules.rules.service.rules import RuleNotFound, RuleService
from shared.db import get_db

router = APIRouter(prefix="/rules/commission", tags=["Rules"])

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("rules.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("rules.edit"))]
Approver = Annotated[AdminContext, Depends(require_permission("rules.approve"))]
TIERS = ("A", "B", "C")


def _ctx_for_city(city: str | None, restaurant_id: str | None = None, zone_id: str | None = None) -> Context:
    city = city or ""
    return Context(country=city[:2] or None, region=city[:5] or None, city=city or None, zone_id=zone_id,
                   restaurant_id=restaurant_id)


async def _restaurant(db: AsyncSession, rid: uuid.UUID):  # type: ignore[no-untyped-def]
    from core_api.modules.catalog.models.restaurant import Restaurant

    r = await db.get(Restaurant, rid)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return r


async def _city_code(db: AsyncSession, restaurant) -> str | None:  # type: ignore[no-untyped-def]
    from core_api.modules.markets.models import City

    return (await db.execute(select(City.code).where(City.name == restaurant.city, City.code.like(f"{restaurant.country}-%"))
                             .limit(1))).scalar()


def _source(c) -> dict | None:  # type: ignore[no-untyped-def]
    if c is None:
        return None
    return {"rule_id": str(c.id), "rule_key": str(c.rule_key), "version": c.version, "template": c.template, "name": c.name,
            "params": c.params, "scope_level": c.scope_level, "scope_id": c.scope_id,
            "effective_to": c.effective_to.isoformat() if c.effective_to else None}


@router.get("/restaurants/{restaurant_id}")
async def restaurant_commission(restaurant_id: uuid.UUID, admin: Viewer, db: DB) -> dict:
    """What this restaurant pays now: the rate, which rule sets it (the restaurant's own,
    its city's or its country's), when that rule ends, its tier, and any tier change waiting."""
    r = await _restaurant(db, restaurant_id)
    city = await _city_code(db, r)
    admin.require("rules.view", city or r.country)
    picked = await RuleService(db).resolve(_ctx_for_city(city, str(r.id)))
    rate, flat = picked.get("commission:rate"), picked.get("commission:flat_per_order")
    pending = (await db.execute(select(TierChange).where(TierChange.restaurant_id == r.id, TierChange.status == "pending")
                                .order_by(TierChange.requested_at.desc()))).scalars().first()
    return {
        "restaurant_id": str(r.id), "name": r.name, "city": city, "country": r.country, "tier": r.tier,
        "percent": str(templates.commission_percent(rate.template, rate.params, r.tier)) if rate else None,
        "flat_per_order": str(flat.params["amount"]) if flat else None,
        "rate_source": _source(rate), "flat_source": _source(flat),
        "pending_tier_change": {"id": str(pending.id), "to": pending.to_tier, "from": pending.from_tier,
                                "requested_by": str(pending.requested_by), "requested_at": pending.requested_at.isoformat(),
                                "note": pending.note} if pending else None,
    }


class TierIn(BaseModel):
    tier: Literal["A", "B", "C"]
    note: str = Field(min_length=3, max_length=300)


@router.post("/restaurants/{restaurant_id}/tier", status_code=status.HTTP_201_CREATED)
async def request_tier_change(restaurant_id: uuid.UUID, data: TierIn, admin: Editor, db: DB) -> dict:
    """A tier changes the restaurant's commission (and tier-based delivery fees), so a second
    admin approves it, like a money rule."""
    r = await _restaurant(db, restaurant_id)
    city = await _city_code(db, r)
    admin.require("rules.edit", city or r.country)
    if (r.tier or None) == data.tier:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "SAME_TIER", "message": f"{r.name} is already tier {data.tier}"})
    if (await db.execute(select(TierChange).where(TierChange.restaurant_id == r.id, TierChange.status == "pending"))).scalars().first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "PENDING", "message": "A tier change is already waiting for approval"})
    tc = TierChange(restaurant_id=r.id, from_tier=r.tier, to_tier=data.tier, note=data.note.strip(), requested_by=admin.user.id,
                    status="pending", scope=city or r.country)
    db.add(tc)
    await db.flush()
    await audit.record(db, actor_id=admin.user.id, action="restaurant.tier_change_requested", entity_type="restaurant",
                       entity_id=r.id, scope=tc.scope, before={"tier": r.tier}, after={"tier": data.tier, "note": tc.note})
    return {"id": str(tc.id), "status": tc.status}


class Decision(BaseModel):
    note: str | None = Field(default=None, max_length=300)


async def _pending(db: AsyncSession, change_id: uuid.UUID, admin: AdminContext) -> TierChange:
    tc = await db.get(TierChange, change_id)
    if tc is None or tc.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No tier change waiting with that id")
    admin.require("rules.approve", tc.scope)
    if tc.requested_by == admin.user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "RULE_WORKFLOW", "message": "A second admin must approve: you asked for this change"})
    return tc


@router.post("/tier-changes/{change_id}/approve")
async def approve_tier_change(change_id: uuid.UUID, data: Decision, admin: Approver, db: DB) -> dict:
    tc = await _pending(db, change_id, admin)
    r = await _restaurant(db, tc.restaurant_id)
    before = r.tier
    r.tier = tc.to_tier
    tc.status, tc.decided_by, tc.decided_at, tc.decision_note = "approved", admin.user.id, datetime.now(UTC), data.note
    await db.flush()
    await audit.record(db, actor_id=admin.user.id, action="restaurant.tier_changed", entity_type="restaurant", entity_id=r.id,
                       scope=tc.scope, before={"tier": before}, after={"tier": r.tier, "note": data.note})
    return {"id": str(tc.id), "status": tc.status, "tier": r.tier}


@router.post("/tier-changes/{change_id}/reject")
async def reject_tier_change(change_id: uuid.UUID, data: Decision, admin: Approver, db: DB) -> dict:
    tc = await _pending(db, change_id, admin)
    tc.status, tc.decided_by, tc.decided_at, tc.decision_note = "rejected", admin.user.id, datetime.now(UTC), data.note
    await db.flush()
    await audit.record(db, actor_id=admin.user.id, action="restaurant.tier_change_rejected", entity_type="restaurant",
                       entity_id=tc.restaurant_id, scope=tc.scope, after={"to": tc.to_tier, "note": data.note})
    return {"id": str(tc.id), "status": tc.status}


@router.get("/preview/{rule_id}")
async def preview(rule_id: uuid.UUID, admin: Viewer, db: DB, days: int = Query(7, ge=1, le=31)) -> dict:
    """A commission draft against the last ``days`` days of delivered orders in its scope: each
    order's commission as priced (its snapshot) and as this draft would have priced it, and
    what that does to restaurant payouts. Nothing changes; it's for deciding."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.orders.models.order import Order
    from core_api.modules.pricing.models import OrderPricingSnapshot

    svc = RuleService(db)
    try:
        draft = await svc.get(rule_id)
    except RuleNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Rule not found")
    admin.require("rules.view", draft.market_scope)
    if draft.family != "commission" or draft.template == "payout_schedule":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "NOT_COMMISSION", "message": "Only commission rates can be previewed"})
    since = datetime.now(UTC) - timedelta(days=days)
    q = (select(Order, OrderPricingSnapshot, Restaurant)
         .join(OrderPricingSnapshot, OrderPricingSnapshot.order_id == Order.id)
         .join(Restaurant, Restaurant.id == Order.restaurant_id)
         .where(Order.status == "delivered", Order.created_at >= since))
    if draft.scope_level == "restaurant":
        q = q.where(Order.restaurant_id == uuid.UUID(draft.scope_id))
    elif draft.scope_level in ("country", "region", "city"):
        q = q.where(Order.market_city.like(draft.scope_id if draft.scope_level == "city" else f"{draft.scope_id}-%"))
    rows = (await db.execute(q.limit(2000))).all()
    total_now = total_new = Decimal(0)
    by_rest: dict[str, dict] = defaultdict(lambda: {"orders": 0, "commission_now": Decimal(0), "commission_new": Decimal(0)})
    for o, snap, rest in rows:
        ctx = _ctx_for_city(o.market_city, str(o.restaurant_id), str(o.zone_id) if o.zone_id else None)
        picked = await svc.resolve(ctx, at=o.created_at, overlay_ids=[draft.id])
        rate, flat = picked.get("commission:rate"), picked.get("commission:flat_per_order")
        food = Decimal(str(o.subtotal))
        new = Decimal(0)
        if rate:
            new += (food * templates.commission_percent(rate.template, rate.params, rest.tier) / 100).quantize(Decimal("0.01"))
        if flat:
            new += Decimal(str(flat.params["amount"]))
        now = Decimal(str((snap.split.get("detail") or {}).get("commission", "0")))
        total_now += now
        total_new += new
        b = by_rest[rest.name]
        b["orders"] += 1
        b["commission_now"] += now
        b["commission_new"] += new
    return {
        "rule_id": str(draft.id), "days": days, "orders": len(rows),
        "commission_now": str(total_now), "commission_new": str(total_new),
        # Restaurants get what commission doesn't take: their payouts move the other way.
        "payout_difference": str(total_now - total_new),
        "restaurants": sorted(({"name": k, "orders": v["orders"], "commission_now": str(v["commission_now"]),
                                "commission_new": str(v["commission_new"]),
                                "payout_difference": str(v["commission_now"] - v["commission_new"])} for k, v in by_rest.items()),
                              key=lambda x: -x["orders"]),
    }
