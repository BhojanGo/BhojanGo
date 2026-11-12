"""Support tickets (B3, B5).

Kitchens ask for a call back from the partner tablet; the ticket shows in the
admin support console for the kitchen's city with the number to call. Whoever
calls resolves it with a note (audited).
"""
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.support.models import SupportTicket
from shared import authz
from shared.db import get_db

router = APIRouter(tags=["Support"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]
Viewer = Annotated[AdminContext, Depends(require_permission("orders.view"))]

CallbackTopic = Literal["order", "payout", "menu", "account", "other"]
TOPIC_WORDS = {"order": "An order", "payout": "A payout", "menu": "The menu", "account": "The account", "other": "Something else"}
# Any of these, for the ticket's city, lets an admin resolve it.
RESOLVERS = ("orders.edit", "customers.edit", "partners.edit")


class CallbackIn(BaseModel):
    topic: CallbackTopic
    note: str | None = Field(default=None, max_length=300)


class TicketOut(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    topic: str
    note: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolution: str | None


class OpsTicket(TicketOut):
    city: str | None
    requester_name: str
    requester_phone: str | None  # the number to call back (admins only)
    requester_role: str
    restaurant_id: uuid.UUID | None
    restaurant_name: str | None
    order_id: uuid.UUID | None
    order_code: str | None
    details: dict


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=3, max_length=500)


def _out(t: SupportTicket) -> TicketOut:
    return TicketOut(id=t.id, kind=t.kind, status=t.status, topic=t.topic, note=t.note, created_at=t.created_at,
                     resolved_at=t.resolved_at, resolution=t.resolution)


async def _own_kitchen(db: AsyncSession, user: CurrentUser, restaurant_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """The kitchen, if it's the caller's own (owners only: admins call, they don't ask)."""
    from core_api.modules.catalog.service import access

    r = await access.restaurant_or_404(db, restaurant_id)
    if r.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "Not your restaurant"})
    return r


async def _open_callback(db: AsyncSession, restaurant_id: uuid.UUID) -> SupportTicket | None:
    return (await db.execute(select(SupportTicket).where(
        SupportTicket.restaurant_id == restaurant_id, SupportTicket.kind == "callback", SupportTicket.status == "open")
        .order_by(SupportTicket.created_at.desc()))).scalars().first()


@router.post("/restaurants/{restaurant_id}/callback", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def request_callback(restaurant_id: uuid.UUID, data: CallbackIn, user: User, db: DB) -> TicketOut:
    """Ask BhojanGo to call the kitchen back. One open request at a time: asking
    again while one is open returns it (with the newer topic and note)."""
    from core_api.modules.catalog.service.lookup import restaurant_city_code

    r = await _own_kitchen(db, user, restaurant_id)
    t = await _open_callback(db, r.id)
    if t is None:
        t = SupportTicket(kind="callback", status="open", market_city=await restaurant_city_code(db, r.id), country=r.country,
                          requester_id=user.id, requester_role="partner", restaurant_id=r.id, topic=data.topic,
                          note=(data.note or "").strip() or None, details={})
        db.add(t)
    else:
        t.topic, t.note = data.topic, (data.note or "").strip() or t.note
    await db.flush()
    await db.refresh(t)
    return _out(t)


@router.get("/restaurants/{restaurant_id}/callback", response_model=TicketOut | None)
async def my_callback(restaurant_id: uuid.UUID, user: User, db: DB) -> TicketOut | None:
    """The kitchen's open call-back request, if any (the tablet shows "we'll call you")."""
    r = await _own_kitchen(db, user, restaurant_id)
    t = await _open_callback(db, r.id)
    return _out(t) if t else None


@router.get("/ops/tickets", response_model=list[OpsTicket])
async def list_tickets(admin: Viewer, db: DB, scope: str = Query("*", pattern=r"^(\*|[A-Z]{2}(-[A-Z0-9]{1,3}(-[A-Z0-9]{2,5})?)?)$"),
                       state: Literal["open", "resolved"] = "open", limit: int = Query(100, ge=1, le=300)) -> list[OpsTicket]:
    """Tickets in your scope for the support console: open ones oldest first,
    resolved ones newest first."""
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.models.user import User as UserRow

    q = select(SupportTicket).where(SupportTicket.status == state)
    q = q.order_by(SupportTicket.created_at if state == "open" else SupportTicket.created_at.desc()).limit(500)
    rows = [t for t in (await db.execute(q)).scalars()
            if authz.covers(scope, t.market_city or t.country) and admin.can("orders.view", t.market_city or t.country)][:limit]
    people = {u.id: u for u in (await db.execute(select(UserRow).where(UserRow.id.in_({t.requester_id for t in rows})))).scalars()} if rows else {}
    kitchens = {k.id: k.name for k in (await db.execute(select(Restaurant).where(
        Restaurant.id.in_({t.restaurant_id for t in rows if t.restaurant_id})))).scalars()} if rows else {}
    out = []
    for t in rows:
        u = people.get(t.requester_id)
        out.append(OpsTicket(**_out(t).model_dump(), city=t.market_city, requester_name=(u.full_name if u else "") or "Unknown",
                             requester_phone=u.phone if u else None, requester_role=t.requester_role,
                             restaurant_id=t.restaurant_id, restaurant_name=kitchens.get(t.restaurant_id) if t.restaurant_id else None,
                             order_id=t.order_id, order_code=("#" + t.order_id.hex[:6].upper()) if t.order_id else None,
                             details=t.details or {}))
    return out


@router.post("/ops/tickets/{ticket_id}/resolve", response_model=TicketOut)
async def resolve_ticket(ticket_id: uuid.UUID, data: ResolveIn, admin: Viewer, db: DB) -> TicketOut:
    """Done: we called, refunded or explained. The note is kept and audited."""
    from core_api.modules.audit.service import record

    t = await db.get(SupportTicket, ticket_id)
    where = (t.market_city or t.country) if t else ""
    if t is None or not admin.can("orders.view", where):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not any(admin.can(p, where) for p in RESOLVERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN_SCOPE", "message": f"You can't resolve tickets for {where}"})
    if t.status == "resolved":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ALREADY_RESOLVED", "message": "This ticket is already resolved"})
    before = {"status": t.status}
    t.status, t.resolved_at, t.resolved_by, t.resolution = "resolved", datetime.now(UTC), admin.user.id, data.resolution.strip()
    await record(db, actor_id=admin.user.id, action="ticket.resolved", entity_type="support_ticket", entity_id=t.id,
                 scope=where, before=before, after={"status": "resolved", "resolution": t.resolution, "kind": t.kind})
    await db.flush()
    return _out(t)


# ── Report a problem (B5) ─────────────────────────────────────────────────────

ProblemReason = Literal["missing_item", "wrong_item", "quality", "damaged_in_transit", "late"]
REASON_WORDS = {"missing_item": "Missing", "wrong_item": "Wrong item", "quality": "Not good",
                "damaged_in_transit": "Spilled or damaged", "late": "Very late"}


class ProblemItem(BaseModel):
    menu_item_id: uuid.UUID
    quantity: int = Field(ge=1, le=50)


class ProblemIn(BaseModel):
    items: list[ProblemItem] = Field(min_length=1, max_length=30)
    reason: ProblemReason
    note: str | None = Field(default=None, max_length=300)
    photo_key: str | None = Field(default=None, max_length=300)


class ProblemOut(BaseModel):
    outcome: Literal["refunded", "ticket"]
    amount: str  # what the items come to (refunded, or what support will look at)
    currency: str
    limit: str  # the city's automatic refund limit per order
    ticket_id: uuid.UUID | None = None
    message: str


@router.post("/orders/{order_id}/problems", response_model=ProblemOut, status_code=status.HTTP_201_CREATED)
async def report_problem(order_id: uuid.UUID, data: ProblemIn, user: User, db: DB) -> ProblemOut:
    """The customer reports a problem with a delivered order: which items, why,
    and a photo if they like. Up to the city's automatic refund limit per order
    it's refunded at once to the original payment (who pays follows the reason:
    the kitchen for its own mistakes, BhojanGo for delivery problems). Above the
    limit, support gets a ticket and gets back to them."""
    from decimal import Decimal

    from sqlalchemy import func

    from core_api.modules.orders.models.order import Order
    from core_api.modules.payments.models.payment import Refund
    from core_api.modules.payments.service import refunds

    order = await db.get(Order, order_id)
    if order is None or order.customer_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "delivered":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "NOT_DELIVERED", "message": "You can report a problem once the order is delivered"})
    window = await refunds.business_rule(db, order.market_city, "refund_window")
    hours = int(window.params["hours"]) if window else 72
    delivered = order.actual_delivery_time or order.updated_at
    if delivered and (datetime.now(UTC) - delivered).total_seconds() > hours * 3600:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "TOO_LATE", "message": f"Problems can be reported up to {hours} hours after delivery"})
    if data.photo_key and not data.photo_key.startswith(f"problem_photo/{user.user_id}/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "PHOTO", "message": "Upload the photo first"})

    requests = [refunds.ItemRequest(str(i.menu_item_id), i.quantity) for i in data.items]
    try:
        amount, lines, currency = await refunds.preview_items(db, order.id, requests)
    except refunds.RefundError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "CANT_REFUND", "message": str(e)})
    rule = await refunds.business_rule(db, order.market_city, "auto_refund_limit")
    limit = Decimal(str(rule.params["max_per_order"])) if rule else Decimal(0)
    # What this customer was already refunded automatically on this order counts towards the limit.
    auto_before = (await db.execute(select(func.coalesce(func.sum(Refund.amount), 0)).where(
        Refund.order_id == order.id, Refund.requested_by == user.id))).scalar_one()
    sym = "₹" if currency == "INR" else "$"
    if amount + Decimal(auto_before) / 100 <= limit:
        try:
            await refunds.refund_items(db, order_id=order.id, requests=requests, include_delivery=False, reason=data.reason,
                                       note=f"Customer report{': ' + data.note.strip() if data.note and data.note.strip() else ''}",
                                       actor_id=user.id, assignments=[])
        except refunds.RefundError as e:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "CANT_REFUND", "message": str(e)})
        return ProblemOut(outcome="refunded", amount=str(amount), currency=currency, limit=str(limit),
                          message=f"Refunded {sym}{amount:.2f} to your original payment. Sorry about that.")
    t = SupportTicket(kind="problem", status="open", market_city=order.market_city, country=(order.market_city or "IN")[:2],
                      requester_id=user.id, requester_role="customer", restaurant_id=order.restaurant_id, order_id=order.id,
                      topic=data.reason, note=(data.note or "").strip() or None,
                      details={"items": [{"menu_item_id": ln["menu_item_id"], "name": ln["name"], "quantity": ln["quantity"],
                                          "amount": ln["amount"]} for ln in lines],
                               "amount": str(amount), "currency": currency, "photo_key": data.photo_key,
                               "reason_words": REASON_WORDS[data.reason]})
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return ProblemOut(outcome="ticket", amount=str(amount), currency=currency, limit=str(limit), ticket_id=t.id,
                      message="Thanks for telling us. Our support team will look at it and get back to you within a day.")
