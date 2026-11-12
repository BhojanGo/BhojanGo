"""Address lookups other modules use (never the table directly)."""
import uuid

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
