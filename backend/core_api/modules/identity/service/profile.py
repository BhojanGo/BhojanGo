"""User details other modules may read (never the users table directly)."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.models.user import User


async def user_profile(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    u = await db.get(User, user_id)
    if u is None:
        return None
    return {"user_id": str(u.id), "name": u.full_name, "email": u.email, "phone": u.phone, "country": u.country,
            "locale": u.preferred_locale}
