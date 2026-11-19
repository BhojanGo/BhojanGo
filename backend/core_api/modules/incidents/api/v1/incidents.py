"""Incident tools in admin (R17; docs/launch/incident-plan.md).

Each action needs its permission for the scope, a reason, and ``confirm: true`` (the console sends it
only from its confirmation step, after a preview); each writes an audit entry.

- Kitchens: pause (with an optional "back at") and resume. Permission kitchens.pause.
- Ordering: pause a city, a country or everywhere ("*": only a super admin), end a pause. ordering.pause.
  Public: GET /incidents/ordering-pauses/active (the website and app banner).
- Bulk refunds: preview, create (runs at once when every order is within the city's auto-refund
  limit; otherwise waits for a second admin), approve or reject. refunds.bulk / refunds.approve.
- Bulk messages: preview, send (push and email; outside production only test accounts). customers.message.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, get_admin, require_permission
from core_api.modules.incidents import service as svc
from core_api.modules.incidents.models import BulkMessage, BulkRefund, OrderingPause
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/incidents", tags=["Incidents"])
DB = Annotated[AsyncSession, Depends(get_db)]
Reason = Annotated[str, Field(min_length=5, max_length=500, description="Why (kept in the audit log)")]


def _refused(e: svc.IncidentError) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": "INCIDENT_REFUSED", "message": str(e)})


async def _kitchen_city(db: AsyncSession, restaurant_id: uuid.UUID) -> str:
    from core_api.modules.catalog.service.lookup import restaurant_city_code

    city = await restaurant_city_code(db, restaurant_id)
    if not city:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Kitchen not found")
    return city


# ── kitchens ────────────────────────────────────────────────────────────────

class KitchenPause(BaseModel):
    reason: Reason
    back_at: datetime | None = Field(default=None, description="Opens again by itself then; empty: until resumed")
    confirm: Literal[True]


class KitchenResume(BaseModel):
    reason: Reason
    confirm: Literal[True]


@router.post("/kitchens/{restaurant_id}/pause")
async def pause_kitchen(restaurant_id: uuid.UUID, body: KitchenPause, db: DB,
                        admin: Annotated[AdminContext, Depends(require_permission("kitchens.pause"))]) -> dict:
    city = await _kitchen_city(db, restaurant_id)
    admin.require("kitchens.pause", city)
    try:
        return await svc.pause_kitchen(db, restaurant_id, reason=body.reason.strip(), back_at=body.back_at,
                                       actor_id=admin.user.id, scope=city)
    except svc.IncidentError as e:
        raise _refused(e)


@router.post("/kitchens/{restaurant_id}/resume")
async def resume_kitchen(restaurant_id: uuid.UUID, body: KitchenResume, db: DB,
                         admin: Annotated[AdminContext, Depends(require_permission("kitchens.pause"))]) -> dict:
    city = await _kitchen_city(db, restaurant_id)
    admin.require("kitchens.pause", city)
    try:
        return await svc.resume_kitchen(db, restaurant_id, reason=body.reason.strip(), actor_id=admin.user.id, scope=city)
    except svc.IncidentError as e:
        raise _refused(e)


@router.get("/kitchens/paused")
async def paused_kitchens(db: DB, admin: Annotated[AdminContext, Depends(require_permission("partners.view"))]) -> list[dict]:
    """Kitchens an admin has paused, in the scopes I can see."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.catalog.service.lookup import restaurant_city_code

    out = []
    for r in (await db.execute(select(Restaurant).where(Restaurant.admin_paused_at.is_not(None)))).scalars():
        city = await restaurant_city_code(db, r.id)
        if city and admin.can("partners.view", city) and r.closed_for_now:
            out.append({"id": str(r.id), "city": city, **svc._kitchen_state(r)})
    return out


# ── ordering pauses ──────────────────────────────────────────────────────────

class OrderingPauseIn(BaseModel):
    scope: str = Field(min_length=1, max_length=20, description='"*" (everywhere), a country ("IN") or a city ("IN-TG-HYD")')
    reason: Reason
    note: str | None = Field(default=None, max_length=200, description="Shown to customers as written")
    until: datetime | None = None
    confirm: Literal[True]


class EndIn(BaseModel):
    reason: Reason
    confirm: Literal[True]


@router.get("/ordering-pauses/active")
async def active_ordering_pauses(db: DB) -> list[dict]:
    """Public: where new orders are paused now, and the customer-facing note (the website and app banner).
    The admin's reason stays private."""
    return [svc.pause_out(p, admin=False) for p in await svc.active_pauses(db)]


@router.get("/ordering-pauses")
async def ordering_pauses(db: DB, admin: Annotated[AdminContext, Depends(require_permission("markets.view"))],
                          limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    rows = (await db.execute(select(OrderingPause).order_by(OrderingPause.created_at.desc()).limit(limit))).scalars()
    active = {p.id for p in await svc.active_pauses(db)}
    return [{**svc.pause_out(p), "active": p.id in active} for p in rows
            if p.scope == "*" or admin.can("markets.view", p.scope)]


@router.post("/ordering-pauses")
async def pause_ordering(body: OrderingPauseIn, db: DB,
                         admin: Annotated[AdminContext, Depends(require_permission("ordering.pause"))]) -> dict:
    try:
        if body.scope != "*":
            authz.scope_level(body.scope)
    except authz.ScopeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pick everywhere, a country or a city")
    admin.require("ordering.pause", body.scope)
    try:
        p = await svc.pause_ordering(db, scope=body.scope, reason=body.reason.strip(), note=(body.note or "").strip() or None,
                                     until=body.until, actor_id=admin.user.id)
    except svc.IncidentError as e:
        raise _refused(e)
    return svc.pause_out(p)


@router.post("/ordering-pauses/{pause_id}/end")
async def end_ordering_pause(pause_id: uuid.UUID, body: EndIn, db: DB,
                             admin: Annotated[AdminContext, Depends(require_permission("ordering.pause"))]) -> dict:
    p = await db.get(OrderingPause, pause_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    admin.require("ordering.pause", p.scope)
    try:
        return svc.pause_out(await svc.end_pause(db, pause_id, reason=body.reason.strip(), actor_id=admin.user.id))
    except svc.IncidentError as e:
        raise _refused(e)


# ── bulk refunds ─────────────────────────────────────────────────────────────

class RefundPickIn(BaseModel):
    city: str = Field(min_length=5, max_length=20)
    restaurant_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    placed_from: datetime
    placed_to: datetime
    mode: Literal["full", "percent"]
    percent: Decimal | None = Field(default=None, gt=0, lt=100)

    def pick(self) -> svc.RefundPick:
        return svc.RefundPick(self.city, self.restaurant_id, self.zone_id, self.placed_from, self.placed_to, self.mode, self.percent)


class RefundCreate(RefundPickIn):
    reason: Reason
    confirm: Literal[True]


class Decision(BaseModel):
    note: Reason
    confirm: Literal[True]


def _city(admin: AdminContext, perm: str, city: str) -> None:
    try:
        if authz.scope_level(city) != "city":
            raise authz.ScopeError(city)
    except authz.ScopeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pick a city")
    admin.require(perm, city)


@router.post("/refunds/preview")
async def preview_refund(body: RefundPickIn, db: DB,
                         admin: Annotated[AdminContext, Depends(require_permission("refunds.bulk"))]) -> dict:
    _city(admin, "refunds.bulk", body.city)
    try:
        return await svc.preview_refund(db, body.pick())
    except svc.IncidentError as e:
        raise _refused(e)


@router.post("/refunds")
async def create_refund(body: RefundCreate, db: DB,
                        admin: Annotated[AdminContext, Depends(require_permission("refunds.bulk"))]) -> dict:
    _city(admin, "refunds.bulk", body.city)
    try:
        return svc.refund_out(await svc.create_refund(db, body.pick(), reason=body.reason.strip(), actor_id=admin.user.id))
    except svc.IncidentError as e:
        raise _refused(e)


@router.get("/refunds")
async def list_refunds(db: DB, admin: Annotated[AdminContext, Depends(require_permission("orders.view"))],
                       limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    rows = (await db.execute(select(BulkRefund).order_by(BulkRefund.created_at.desc()).limit(limit))).scalars()
    return [svc.refund_out(b, orders=False) for b in rows if admin.can("orders.view", b.market_city)]


@router.get("/refunds/{refund_id}")
async def get_refund(refund_id: uuid.UUID, db: DB, admin: Annotated[AdminContext, Depends(require_permission("orders.view"))]) -> dict:
    b = await db.get(BulkRefund, refund_id)
    if b is None or not admin.can("orders.view", b.market_city):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return svc.refund_out(b)


async def _decide(refund_id: uuid.UUID, body: Decision, db: AsyncSession, admin: AdminContext, approve: bool) -> dict:
    b = await db.get(BulkRefund, refund_id)
    if b is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    admin.require("refunds.approve", b.market_city)
    try:
        return svc.refund_out(await svc.decide_refund(db, refund_id, approve=approve, note=body.note.strip(), actor_id=admin.user.id))
    except svc.IncidentError as e:
        raise _refused(e)


@router.post("/refunds/{refund_id}/approve")
async def approve_refund(refund_id: uuid.UUID, body: Decision, db: DB,
                         admin: Annotated[AdminContext, Depends(require_permission("refunds.approve"))]) -> dict:
    return await _decide(refund_id, body, db, admin, True)


@router.post("/refunds/{refund_id}/reject")
async def reject_refund(refund_id: uuid.UUID, body: Decision, db: DB,
                        admin: Annotated[AdminContext, Depends(require_permission("refunds.approve"))]) -> dict:
    return await _decide(refund_id, body, db, admin, False)


# ── bulk messages ────────────────────────────────────────────────────────────

class AudienceIn(BaseModel):
    bulk_refund_id: uuid.UUID | None = None
    city: str | None = Field(default=None, max_length=20)
    days: int = Field(default=30, ge=1, le=90)
    template: str = Field(max_length=40)
    params: dict[str, str] = Field(default_factory=dict)

    def audience(self) -> svc.Audience:
        return svc.Audience(self.bulk_refund_id, None if self.bulk_refund_id else self.city, self.days)


class MessageSend(AudienceIn):
    reason: Reason
    confirm: Literal[True]


async def _audience_city(db: AsyncSession, admin: AdminContext, body: AudienceIn) -> None:
    if body.bulk_refund_id:
        b = await db.get(BulkRefund, body.bulk_refund_id)
        if b is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Bulk refund not found")
        admin.require("customers.message", b.market_city)
    elif body.city:
        _city(admin, "customers.message", body.city)
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pick a bulk refund's customers or a city")


@router.get("/messages/templates")
async def message_templates(admin: Annotated[AdminContext, Depends(require_permission("customers.message"))]) -> list[dict]:
    """The incident plan's customer messages, in English, with what each needs filled in."""
    from shared.texts import INCIDENT_ADMIN_PARAMS, INCIDENT_FROM_ORDER, INCIDENT_MESSAGES, incident_placeholders

    return [{"key": k, "title": v["en"][0], "body": v["en"][1],
             "needs": sorted(incident_placeholders(k) & INCIDENT_ADMIN_PARAMS),
             "per_order": bool(incident_placeholders(k) & INCIDENT_FROM_ORDER)} for k, v in INCIDENT_MESSAGES.items()]


@router.post("/messages/preview")
async def preview_message(body: AudienceIn, db: DB,
                          admin: Annotated[AdminContext, Depends(require_permission("customers.message"))]) -> dict:
    await _audience_city(db, admin, body)
    try:
        return await svc.preview_message(db, body.audience(), body.template, body.params)
    except svc.IncidentError as e:
        raise _refused(e)


@router.post("/messages")
async def send_message(body: MessageSend, db: DB,
                       admin: Annotated[AdminContext, Depends(require_permission("customers.message"))]) -> dict:
    await _audience_city(db, admin, body)
    try:
        return svc.message_out(await svc.send_message(db, body.audience(), body.template, body.params,
                                                      reason=body.reason.strip(), actor_id=admin.user.id))
    except svc.IncidentError as e:
        raise _refused(e)


@router.get("/messages")
async def list_messages(db: DB, admin: Annotated[AdminContext, Depends(get_admin)],
                        limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    rows = (await db.execute(select(BulkMessage).order_by(BulkMessage.created_at.desc()).limit(limit))).scalars()
    return [svc.message_out(m) for m in rows if admin.can("customers.view", m.scope)]


# ── the log ──────────────────────────────────────────────────────────────────

INCIDENT_ACTIONS = ("kitchen.paused", "kitchen.resumed", "ordering.paused", "ordering.resumed", "bulk_refund.requested",
                    "bulk_refund.approved", "bulk_refund.rejected", "bulk_refund.done", "customers.messaged")


@router.get("/log")
async def incident_log(db: DB, admin: Annotated[AdminContext, Depends(get_admin)], limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """The audit entries of incident actions, newest first, in the scopes I can see."""
    from core_api.modules.audit.models import AuditLog
    from core_api.modules.identity.models.user import User

    rows = (await db.execute(select(AuditLog).where(AuditLog.action.in_(INCIDENT_ACTIONS))
                             .order_by(AuditLog.at.desc()).limit(limit))).scalars().all()
    rows = [r for r in rows if admin.can("markets.view", r.scope) or admin.can("orders.view", r.scope)]
    people = {u.id: u.full_name or u.email or "" for u in (await db.execute(
        select(User).where(User.id.in_({r.actor_id for r in rows if r.actor_id})))).scalars()} if rows else {}
    return [{"at": r.at.isoformat(), "action": r.action, "scope": r.scope, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "by": people.get(r.actor_id, ""), "after": r.after} for r in rows]
