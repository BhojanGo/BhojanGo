"""Internal kitchen endpoint for realtime (R27): may this account watch this kitchen's orders?
Not for apps: every request must be signed with INTERNAL_SERVICE_SECRET (shared/internal_auth.py)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant
from shared import internal_auth
from shared.db import get_db


async def signed(request: Request) -> None:
    try:
        internal_auth.verify(request.method, request.url.path, await request.body(),
                             request.headers.get("x-internal-timestamp"), request.headers.get("x-internal-signature"))
    except internal_auth.InternalAuthError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Internal endpoint")

router = APIRouter(prefix="/internal/restaurants", tags=["Internal"], include_in_schema=False, dependencies=[Depends(signed)])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


@router.get("/{restaurant_id}/staff/{user_id}")
async def is_staff(restaurant_id: uuid.UUID, user_id: uuid.UUID, db: DB) -> dict:
    """Is this account the kitchen's staff (its owner: the account its BhojanGo Kitchen tablet signs in
    with)? realtime's kitchen socket (/ws/kitchen/{id}) opens only for them."""
    r = await db.get(Restaurant, restaurant_id)
    staff = r is not None and r.deleted_at is None and r.owner_id == user_id
    return {"restaurant_id": str(restaurant_id), "user_id": str(user_id), "staff": staff}
