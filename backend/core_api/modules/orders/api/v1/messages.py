"""Quick messages between the customer and the rider during an active order (B2).

Preset messages plus short free text, delivered live on the order's tracking
channel (realtime WebSocket) and by push to the other person. Open from the
moment a rider is assigned until the order is delivered or cancelled; after
that the conversation is hidden from both sides. Nobody sees a phone number:
people appear by first name and phone-like digits in free text are masked.
"""
import json
import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from core_api.modules.orders.models import Order, OrderMessage
from core_api.modules.orders.service.state_machine import TERMINAL_STATES
from shared import outbox
from shared.db import get_db
from shared.redis import get_redis

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = structlog.get_logger(__name__)

PRESETS: dict[str, dict[str, str]] = {
    "rider": {
        "at_kitchen": "I'm at the kitchen, waiting for your order.",
        "on_my_way": "Picked up. On my way to you.",
        "outside": "I'm outside.",
        "cant_find": "I can't find the address. Please check the pin on the map.",
        "running_late": "Running a few minutes late, sorry.",
    },
    "customer": {
        "leave_at_door": "Please leave it at the door.",
        "coming_down": "I'm coming down.",
        "ring_bell": "Please ring the bell.",
        "ask_guard": "Please ask the guard at the gate.",
    },
}
MAX_TEXT = 140
MAX_PER_SENDER = 40
# A run of 7 or more digits, with the usual separators: looks like a phone number.
PHONE_LIKE = re.compile(r"\+?\d(?:[\s\-().]*\d){6,}")


def mask_phone_numbers(text: str) -> str:
    return PHONE_LIKE.sub("•••", text)


class QuickPreset(BaseModel):
    key: str
    text: str


class QuickMessage(BaseModel):
    id: uuid.UUID
    mine: bool
    sender_role: Literal["customer", "rider"]
    text: str
    at: datetime


class QuickMessagesOut(BaseModel):
    open: bool
    me: Literal["customer", "rider"]
    other_name: str  # first name only
    presets: list[QuickPreset]
    messages: list[QuickMessage]


class QuickMessageIn(BaseModel):
    preset: str | None = Field(default=None, max_length=30)
    text: str | None = Field(default=None, max_length=MAX_TEXT)

    @model_validator(mode="after")
    def one_of(self) -> "QuickMessageIn":
        if bool(self.preset) == bool(self.text and self.text.strip()):
            raise ValueError("Send a quick message or a short text")
        return self


async def _first_name(db: AsyncSession, user_id: uuid.UUID | None, fallback: str) -> str:
    from core_api.modules.identity.models.user import User

    u = await db.get(User, user_id) if user_id else None
    return ((u.full_name or "").split(" ")[0] if u else "") or fallback


async def _load(db: AsyncSession, order_id: uuid.UUID, me: CurrentUser) -> tuple[Order, str]:
    """The order and my side of it; anyone else gets a 404 (not even "it exists")."""
    order = await db.get(Order, order_id)
    me_id = uuid.UUID(me.user_id)
    if order is not None and order.customer_id == me_id:
        return order, "customer"
    if order is not None and order.driver_id is not None and order.driver_id == me_id:
        return order, "rider"
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


def is_open(order: Order) -> bool:
    return order.driver_id is not None and order.status not in TERMINAL_STATES


@router.get("/{order_id}/messages", response_model=QuickMessagesOut)
async def list_messages(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> QuickMessagesOut:
    """The conversation with the rider (or the customer). Empty and closed
    before a rider is assigned and after the order is delivered or cancelled."""
    order, me = await _load(db, order_id, current_user)
    other = await _first_name(db, order.driver_id if me == "customer" else order.customer_id,
                              "Your rider" if me == "customer" else "The customer")
    if not is_open(order):
        return QuickMessagesOut(open=False, me=me, other_name=other, presets=[], messages=[])
    rows = (await db.execute(select(OrderMessage).where(OrderMessage.order_id == order.id)
                             .order_by(OrderMessage.created_at))).scalars().all()
    return QuickMessagesOut(
        open=True, me=me, other_name=other,
        presets=[QuickPreset(key=k, text=v) for k, v in PRESETS[me].items()],
        messages=[QuickMessage(id=r.id, mine=r.sender_role == me, sender_role=r.sender_role, text=r.text, at=r.created_at)  # type: ignore[arg-type]
                  for r in rows],
    )


@router.post("/{order_id}/messages", response_model=QuickMessage, status_code=status.HTTP_201_CREATED)
async def send_message(
    order_id: uuid.UUID,
    data: QuickMessageIn,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> QuickMessage:
    """Send a quick message or a short text (140 characters) to the other side."""
    order, me = await _load(db, order_id, current_user)
    if not is_open(order):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "CHAT_CLOSED", "message": "Messages are open while a rider is bringing the order."})
    if data.preset:
        text = PRESETS[me].get(data.preset)
        if text is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail={"code": "UNKNOWN_PRESET", "message": "That quick message isn't available."})
    else:
        text = mask_phone_numbers(" ".join((data.text or "").split()))
    sent = (await db.execute(select(func.count()).select_from(OrderMessage).where(
        OrderMessage.order_id == order.id, OrderMessage.sender_role == me))).scalar_one()
    if sent >= MAX_PER_SENDER:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail={"code": "TOO_MANY_MESSAGES", "message": "That's a lot of messages for one order."})

    msg = OrderMessage(order_id=order.id, sender_id=uuid.UUID(current_user.user_id), sender_role=me,
                       preset=data.preset, text=text)
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    to = order.driver_id if me == "customer" else order.customer_id
    name = await _first_name(db, uuid.UUID(current_user.user_id), "Your rider" if me == "rider" else "The customer")
    # Push to the other person (worker, via the outbox) ...
    await outbox.add(db, "order.message", "order", order.id,
                     {"order_id": str(order.id), "message_id": str(msg.id), "to_user_id": str(to),
                      "from_role": me, "from_name": name, "text": text}, "order-svc")
    # ... and live to anyone watching the order (realtime relays the tracking channel).
    try:
        await (await get_redis()).publish(f"tracking:{order.id}", json.dumps({
            "type": "chat_message",
            "payload": {"id": str(msg.id), "sender_role": me, "text": text, "at": msg.created_at.isoformat()},
            "timestamp": datetime.now(UTC).isoformat(),
        }))
    except Exception as e:  # noqa: BLE001 - the push and the next refresh still deliver it
        logger.warning("chat_publish_failed", order_id=str(order.id), error=str(e))
    return QuickMessage(id=msg.id, mine=True, sender_role=me, text=text, at=msg.created_at)  # type: ignore[arg-type]
