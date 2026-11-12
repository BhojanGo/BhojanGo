"""Who may change a restaurant: its owner, or an admin whose role gives the
permission for the restaurant's city (shared/authz.py). Never the legacy
`role == "admin"` check, which let any admin of any city through."""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service.lookup import restaurant_city_code
from shared import authz
from shared.auth import CurrentUser


def assignments(user: CurrentUser) -> list[authz.Assignment]:
    return [authz.Assignment.parse(a) for a in user.admin]


async def restaurant_or_404(db: AsyncSession, rid: uuid.UUID) -> Restaurant:
    r = await db.get(Restaurant, rid)
    if r is None or r.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return r


async def scope_of(db: AsyncSession, r: Restaurant) -> str:
    return await restaurant_city_code(db, r.id) or r.country


async def admin_may(db: AsyncSession, user: CurrentUser, r: Restaurant, permission: str) -> bool:
    return authz.can(assignments(user), permission, await scope_of(db, r))


async def manage(db: AsyncSession, user: CurrentUser, rid: uuid.UUID, permission: str = "partners.edit") -> Restaurant:
    """The restaurant, if the user owns it or may edit partners in its city; else 403."""
    r = await restaurant_or_404(db, rid)
    if r.owner_id == user.id or await admin_may(db, user, r, permission):
        return r
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "Not your restaurant"})


async def administer(db: AsyncSession, user: CurrentUser, rid: uuid.UUID, permission: str = "partners.edit") -> Restaurant:
    """Admin-only actions (approve, suspend): the owner may not; 403 for anyone else."""
    r = await restaurant_or_404(db, rid)
    if await admin_may(db, user, r, permission):
        return r
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": "You need partners.edit for this city"})
