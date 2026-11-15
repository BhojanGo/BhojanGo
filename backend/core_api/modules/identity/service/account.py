"""Favourites, notification preferences and the data export (the web's
signed-in account area)."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.account import Favourite, NotificationPreference
from core_api.modules.identity.models.address import Address
from core_api.modules.identity.models.user import User

CATEGORIES = ("orders", "offers", "account")
CHANNELS = ("push", "sms", "email")
# Offers are opt-in (consent for marketing: DPDP, TCPA, CAN-SPAM); order and
# account messages are on until the customer turns them off.
DEFAULTS: dict[str, bool] = {"orders": True, "offers": False, "account": True}


# ── notification preferences ─────────────────────────────────────────────────

async def preferences(db: AsyncSession, user_id: uuid.UUID) -> dict[str, dict[str, bool]]:
    out = {c: {ch: DEFAULTS[c] for ch in CHANNELS} for c in CATEGORIES}
    rows = (await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))).scalars()
    for p in rows:
        if p.category in out and p.channel in out[p.category]:
            out[p.category][p.channel] = p.enabled
    return out


async def set_preferences(db: AsyncSession, user_id: uuid.UUID, changes: dict[str, dict[str, bool]]) -> dict[str, dict[str, bool]]:
    """Store the switches sent; the others keep their value."""
    for category, channels in changes.items():
        for channel, enabled in channels.items():
            await db.merge(NotificationPreference(user_id=user_id, category=category, channel=channel, enabled=enabled))
    await db.flush()
    return await preferences(db, user_id)


# ── favourites ───────────────────────────────────────────────────────────────

async def favourites(db: AsyncSession, user_id: uuid.UUID) -> dict[str, list[dict]]:
    """Saved kitchens and dishes that are still live, newest first."""
    from core_api.modules.catalog.service.lookup import item_cards, restaurant_cards

    rows = list((await db.execute(select(Favourite).where(Favourite.user_id == user_id)
                                  .order_by(Favourite.created_at.desc()))).scalars())
    rest = await restaurant_cards(db, [f.target_id for f in rows if f.kind == "restaurant"])
    items = await item_cards(db, [f.target_id for f in rows if f.kind == "item"])
    return {
        "restaurants": [{**rest[f.target_id], "saved_at": f.created_at} for f in rows if f.kind == "restaurant" and f.target_id in rest],
        "items": [{**items[f.target_id], "saved_at": f.created_at} for f in rows if f.kind == "item" and f.target_id in items],
    }


async def target_exists(db: AsyncSession, kind: str, target_id: uuid.UUID) -> bool:
    from core_api.modules.catalog.service.lookup import item_cards, restaurant_cards

    found = await (restaurant_cards if kind == "restaurant" else item_cards)(db, [target_id])
    return target_id in found


async def add_favourite(db: AsyncSession, user_id: uuid.UUID, kind: str, target_id: uuid.UUID) -> None:
    if await db.get(Favourite, (user_id, kind, target_id)) is None:
        db.add(Favourite(user_id=user_id, kind=kind, target_id=target_id))
        await db.flush()


async def remove_favourite(db: AsyncSession, user_id: uuid.UUID, kind: str, target_id: uuid.UUID) -> None:
    await db.execute(delete(Favourite).where(Favourite.user_id == user_id, Favourite.kind == kind,
                                             Favourite.target_id == target_id))


async def forget(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Account deletion: favourites and preferences go."""
    await db.execute(delete(Favourite).where(Favourite.user_id == user_id))
    await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user_id))


# ── data export ──────────────────────────────────────────────────────────────

def _iso(v: object) -> object:
    return v.isoformat() if isinstance(v, datetime) else v


async def export(db: AsyncSession, user: User) -> dict:
    """Everything we hold about the signed-in person (GDPR art. 15/20, DPDP
    s.11), and nothing about anyone else: no riders, no agents, no other customers."""
    from core_api.modules.catalog.service.lookup import reviews_by
    from core_api.modules.orders.service.lookup import customer_order_ids, orders_for_export
    from core_api.modules.payments.service import methods
    from core_api.modules.payments.service.lookup import refunds_for
    from core_api.modules.pricing.service.lookup import order_bills
    from core_api.modules.support.service.lookup import tickets_by

    addresses = (await db.execute(select(Address).where(Address.user_id == user.id).order_by(Address.created_at))).scalars()
    orders = await orders_for_export(db, user.id)
    order_ids = await customer_order_ids(db, user.id)
    bills = await order_bills(db, order_ids)
    for o in orders:
        o["bill"] = bills.get(uuid.UUID(o["id"]))
    favs = await favourites(db, user.id)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "profile": {
            "id": str(user.id), "full_name": user.full_name, "email": user.email, "phone": user.phone,
            "country": user.country, "preferred_currency": user.preferred_currency,
            "preferred_locale": user.preferred_locale, "loyalty_points": user.loyalty_points,
            "is_verified": user.is_verified, "is_phone_verified": user.is_phone_verified,
            "signed_in_with": [p for p, v in (("google", user.google_id), ("apple", user.apple_id)) if v],
            "created_at": _iso(user.created_at),
        },
        "addresses": [{"id": str(a.id), "label": a.label, "street": a.street, "city": a.city, "state": a.state,
                       "postal_code": a.postal_code, "country": a.country, "lat": a.lat, "lng": a.lng,
                       "delivery_notes": a.delivery_notes, "is_default": a.is_default,
                       "created_at": _iso(a.created_at)} for a in addresses],
        "orders": orders,
        "payment_methods": [{k: (str(v) if k == "id" else _iso(v)) for k, v in methods.as_dict(m).items()}
                            for m in await methods.list_for(db, user.id)],
        "favourites": {k: [{kk: _iso(vv) for kk, vv in row.items()} for row in v] for k, v in favs.items()},
        "notification_preferences": await preferences(db, user.id),
        "support_tickets": await tickets_by(db, user.id),
        "refunds_and_problems": await refunds_for(db, order_ids, user.id),
        "reviews": await reviews_by(db, user.id),
    }
