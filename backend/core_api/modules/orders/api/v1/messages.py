"""Quick messages between the customer and the rider during an active order (B2).

Preset messages (in each reader's language, round 5) plus short free text, delivered live on the order's tracking
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
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.orders.api.dependencies import CurrentUser, get_current_user
from core_api.modules.orders.models import Order, OrderMessage
from core_api.modules.orders.service.state_machine import TERMINAL_STATES
from shared import outbox
from shared.db import get_db
from shared.redis import get_redis
from shared.texts import LANGUAGES, QUICK_PRESETS, fallback_name, language_for, preset_text

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = structlog.get_logger(__name__)

# The presets in English (their keys, for validation and the tests); every
# language is in shared/texts.py QUICK_PRESETS. Each reader sees a preset in
# their own language: the `lang` query parameter (the app's language), else
# their account's preferred_locale. Free text is shown as written.
PRESETS: dict[str, dict[str, str]] = {side: {k: t["en"] for k, t in presets.items()}
                                      for side, presets in QUICK_PRESETS.items()}
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


async def _first_name(db: AsyncSession, user_id: uuid.UUID | None) -> str:
    """The first name on the account; "" when there is none."""
    from core_api.modules.identity.models.user import User

    u = await db.get(User, user_id) if user_id else None
    return (u.full_name or "").split(" ")[0] if u else ""


async def _language(db: AsyncSession, me: CurrentUser, lang: str | None) -> str:
    """The reader's language: what the app asks for, else the account's preferred_locale."""
    if lang in LANGUAGES:
        return lang  # type: ignore[return-value]
    from core_api.modules.identity.models.user import User

    u = await db.get(User, uuid.UUID(me.user_id))
    return language_for(u.preferred_locale if u else None)


def _shown(row: OrderMessage, language: str) -> str:
    """A preset in the reader's language; free text as written."""
    return (preset_text(row.sender_role, row.preset, language) if row.preset else None) or row.text


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


# The app's language ("hi"); a language we don't write in falls back to the account's.
Lang = Annotated[str | None, Query(pattern=r"^[a-z]{2}$", description="The reader's language (the app's), e.g. hi")]


@router.get("/{order_id}/messages", response_model=QuickMessagesOut)
async def list_messages(
    order_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Lang = None,
) -> QuickMessagesOut:
    """The conversation with the rider (or the customer). Empty and closed
    before a rider is assigned and after the order is delivered or cancelled.
    Quick messages (and the presets offered) are in the reader's language."""
    order, me = await _load(db, order_id, current_user)
    language = await _language(db, current_user, lang)
    other_role = "rider" if me == "customer" else "customer"
    other = (await _first_name(db, order.driver_id if me == "customer" else order.customer_id)
             or fallback_name(other_role, language))
    if not is_open(order):
        return QuickMessagesOut(open=False, me=me, other_name=other, presets=[], messages=[])
    rows = (await db.execute(select(OrderMessage).where(OrderMessage.order_id == order.id)
                             .order_by(OrderMessage.created_at))).scalars().all()
    return QuickMessagesOut(
        open=True, me=me, other_name=other,
        presets=[QuickPreset(key=k, text=preset_text(me, k, language) or v) for k, v in PRESETS[me].items()],
        messages=[QuickMessage(id=r.id, mine=r.sender_role == me, sender_role=r.sender_role,  # type: ignore[arg-type]
                               text=_shown(r, language), at=r.created_at)
                  for r in rows],
    )


@router.post("/{order_id}/messages", response_model=QuickMessage, status_code=status.HTTP_201_CREATED)
async def send_message(
    order_id: uuid.UUID,
    data: QuickMessageIn,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Lang = None,
) -> QuickMessage:
    """Send a quick message or a short text (140 characters) to the other side.
    A quick message is stored by its key and shown to each side in their own
    language (the reply is in the sender's)."""
    order, me = await _load(db, order_id, current_user)
    if not is_open(order):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "CHAT_CLOSED", "message": "Messages are open while a delivery partner is bringing the order."})
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
    name = await _first_name(db, uuid.UUID(current_user.user_id))  # "": the worker says "Your delivery partner" in the reader's language
    # Push to the other person (worker, via the outbox), who reads a preset in their own language ...
    await outbox.add(db, "order.message", "order", order.id,
                     {"order_id": str(order.id), "message_id": str(msg.id), "to_user_id": str(to),
                      "from_role": me, "from_name": name, "text": text, "preset": data.preset}, "order-svc")
    # Commit before telling anyone: with a preset the watchers fetch the conversation
    # again, and a fetch that beats the request's own commit (get_db commits after the
    # endpoint returns) gets the list without this message until the next poll (R7:
    # the flaky "live from the rider" e2e check). The outbox row commits with it.
    await db.commit()
    # ... and live to anyone watching the order (realtime relays the tracking channel). With a
    # preset the apps fetch the conversation again, so it shows in the watcher's language.
    try:
        await (await get_redis()).publish(f"tracking:{order.id}", json.dumps({
            "type": "chat_message",
            "payload": {"id": str(msg.id), "sender_role": me, "text": text, "preset": data.preset,
                        "at": msg.created_at.isoformat()},
            "timestamp": datetime.now(UTC).isoformat(),
        }))
    except Exception as e:  # noqa: BLE001 - the push and the next refresh still deliver it
        logger.warning("chat_publish_failed", order_id=str(order.id), error=str(e))
    language = await _language(db, current_user, lang)
    return QuickMessage(id=msg.id, mine=True, sender_role=me, text=_shown(msg, language), at=msg.created_at)  # type: ignore[arg-type]
