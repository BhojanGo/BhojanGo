"""Address lookups other modules use (never the table directly)."""
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.address import Address


async def address_point(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> tuple[float, float] | None:
    """(lat, lng) of one of the user's saved addresses, if it has a map pin."""
    a = await db.get(Address, address_id)
    if a is None or a.user_id != user_id or a.lat is None or a.lng is None:
        return None
    return a.lat, a.lng


async def address_details(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> dict | None:
    """Pin and postal details of one of the user's saved addresses (quotes, tax)."""
    a = await db.get(Address, address_id)
    if a is None or a.user_id != user_id:
        return None
    return {"lat": a.lat, "lng": a.lng, "street": a.street, "city": a.city, "state": a.state,
            "postal_code": a.postal_code, "country": a.country}


async def make_default(db: AsyncSession, address: Address) -> None:
    """Make ``address`` its user's only default. The old default is cleared
    first: a unique index allows one default per user at any moment."""
    await db.execute(update(Address).where(Address.user_id == address.user_id, Address.id != address.id,
                                           Address.is_default.is_(True)).values(is_default=False))
    address.is_default = True
    await db.flush()


async def promote_newest(db: AsyncSession, user_id: uuid.UUID) -> None:
    """After the default is deleted, the newest remaining address takes over."""
    q = select(Address).where(Address.user_id == user_id).order_by(Address.created_at.desc(), Address.id.desc()).limit(1)
    newest = (await db.execute(q)).scalar_one_or_none()
    if newest is not None:
        await make_default(db, newest)
