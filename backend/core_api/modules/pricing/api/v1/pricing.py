"""Pricing API (P8): customer quotes and the admin price simulator."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.payments.api.dependencies import CurrentUser, get_current_user
from core_api.modules.pricing.schemas import QuoteOut, QuoteRequest, SimulateOut, SimulateRequest
from core_api.modules.pricing.service.quotes import QuoteError, QuoteService
from shared.db import get_db

router = APIRouter(prefix="/pricing", tags=["Pricing"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _unprocessable(e: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "CANNOT_QUOTE", "message": str(e)})


@router.post("/quote", response_model=QuoteOut)
async def quote(data: QuoteRequest, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> QuoteOut:
    """Price a bag: every line of the bill, and a token valid for 10 minutes.
    Checkout charges exactly this total."""
    try:
        return await QuoteService(db).quote(user.id, data)
    except QuoteError as e:
        raise _unprocessable(e)


@router.get("/quotes/{quote_id}")
async def get_quote(quote_id: uuid.UUID, user: Annotated[CurrentUser, Depends(get_current_user)], db: DB) -> dict:
    """A quote you made, while it is valid (bill lines; no payout split)."""
    try:
        q = await QuoteService(db).get(user.id, quote_id)
    except QuoteError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "QUOTE_EXPIRED", "message": str(e)})
    return {k: q[k] for k in ("quote_id", "restaurant_id", "currency", "total", "lines", "tax_pending", "expires_at", "items")}


@router.get("/orders/{order_id}/snapshot")
async def order_snapshot(
    order_id: uuid.UUID,
    admin: Annotated[AdminContext, Depends(require_permission("orders.view"))],
    db: DB,
) -> dict:
    """Admin: what an order was charged and why (lines, rule versions, split)."""
    snap = await QuoteService(db).snapshot(order_id)
    if snap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No pricing snapshot for this order")
    admin.require("orders.view", snap.context.get("city", "*"))
    return {
        "order_id": str(snap.order_id), "quote_id": str(snap.quote_id), "currency": snap.currency,
        "total": str(snap.total), "lines": snap.lines, "rule_versions": snap.rule_versions, "split": snap.split,
        "context": snap.context, "created_at": snap.created_at.isoformat(),
    }


@router.post("/simulate", response_model=SimulateOut)
async def simulate(
    data: SimulateRequest,
    admin: Annotated[AdminContext, Depends(require_permission("pricing.simulate"))],
    db: DB,
) -> SimulateOut:
    """Price simulator: the same cart with live rules and with your drafts."""
    admin.require("pricing.simulate", data.city)
    try:
        return await QuoteService(db).simulate(data)
    except QuoteError as e:
        raise _unprocessable(e)
