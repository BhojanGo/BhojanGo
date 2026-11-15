"""Saved cards (tokens only). We never take a card number: PCI DSS scope stays
with Stripe and Razorpay, whose own forms collect the card and give us a token.
A request that carries anything shaped like a card number is refused outright
(422), so a buggy client can't make us store one by accident."""
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.payments.models.payment_method import PaymentMethod

# 13-19 digits, optionally grouped with single spaces or dashes ("4242 4242 4242 4242").
_PAN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")

TOKEN_FORMAT = {
    "stripe": re.compile(r"^pm_[A-Za-z0-9_]{4,250}$"),
    "razorpay": re.compile(r"^token_[A-Za-z0-9]{4,249}$"),
    "fake": re.compile(r"^pm_fake_[A-Za-z0-9_]{1,247}$"),
}


def looks_like_card_number(value: object) -> bool:
    """True if any string or number in ``value`` (keys included, nested) could be a card number."""
    if isinstance(value, dict):
        return any(looks_like_card_number(k) or looks_like_card_number(v) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(looks_like_card_number(v) for v in value)
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float, str)):
        return bool(_PAN.search(str(value)))
    return False


def is_expired(exp_month: int, exp_year: int, now: datetime | None = None) -> bool:
    """A card is good until the end of its expiry month."""
    today = now or datetime.now(UTC)
    return (exp_year, exp_month) < (today.year, today.month)


def as_dict(m: PaymentMethod) -> dict:
    """What the API and the data export show: never the token."""
    return {"id": m.id, "provider": m.provider, "brand": m.brand, "last4": m.last4, "exp_month": m.exp_month,
            "exp_year": m.exp_year, "is_default": m.is_default, "created_at": m.created_at}


async def list_for(db: AsyncSession, user_id: uuid.UUID) -> list[PaymentMethod]:
    q = select(PaymentMethod).where(PaymentMethod.user_id == user_id).order_by(PaymentMethod.created_at, PaymentMethod.id)
    return list((await db.execute(q)).scalars())


async def make_default(db: AsyncSession, m: PaymentMethod) -> None:
    """One default card per user (a unique index): clear the old one first."""
    await db.execute(update(PaymentMethod).where(PaymentMethod.user_id == m.user_id, PaymentMethod.id != m.id,
                                                 PaymentMethod.is_default.is_(True)).values(is_default=False))
    m.is_default = True
    await db.flush()


async def remove(db: AsyncSession, m: PaymentMethod) -> None:
    """Delete a card; if it was the default, the newest remaining one takes over."""
    user_id, was_default = m.user_id, m.is_default
    await db.delete(m)
    await db.flush()
    if was_default:
        q = (select(PaymentMethod).where(PaymentMethod.user_id == user_id)
             .order_by(PaymentMethod.created_at.desc(), PaymentMethod.id.desc()).limit(1))
        newest = (await db.execute(q)).scalar_one_or_none()
        if newest is not None:
            await make_default(db, newest)


async def forget_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Account deletion: every saved card goes."""
    await db.execute(delete(PaymentMethod).where(PaymentMethod.user_id == user_id))
