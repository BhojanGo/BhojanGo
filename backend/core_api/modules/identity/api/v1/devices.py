"""This phone's push token (R19): the apps register it after sign-in and remove it
on sign-out. Same table as the worker's own endpoint (worker/app/models DeviceToken,
which the core image copies); the worker's dispatcher reads it to push order updates.

A token belongs to one person at a time: it moves to whoever signed in on the phone
last, so a shared phone never gets the previous person's order updates.
"""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Table, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user
from core_api.modules.identity.models.user import User
from shared.db import Base, get_db
from shared.providers.push import provider_for_token

router = APIRouter(prefix="/me", tags=["Account"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[User, Depends(get_current_active_user)]


def device_tokens() -> Table:
    """The worker's table. Looked up on first use rather than imported at start-up: a
    process that already loaded the worker's models as ``app.models`` (the worker's tests
    import core_api too) must not define the table a second time."""
    table = Base.metadata.tables.get("device_tokens")
    if table is None:
        import worker.app.models.notification  # noqa: F401  (registers the table)

        table = Base.metadata.tables["device_tokens"]
    return table


class DeviceIn(BaseModel):
    token: str = Field(min_length=10, max_length=4096)
    platform: Literal["ios", "android", "web"]
    # Which push service issued the token; left out, it's worked out from the token.
    provider: Literal["expo", "fcm", "apns"] | None = None


class DeviceOut(BaseModel):
    platform: str
    provider: str


@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(data: DeviceIn, me: Me, db: DB) -> DeviceOut:
    """Push this phone's token to the signed-in person (it moves from anyone else)."""
    t = device_tokens()
    provider = data.provider or provider_for_token(data.token, data.platform)
    values = {"user_id": me.id, "platform": data.platform, "provider": provider}
    found = (await db.execute(select(t.c.id).where(t.c.token == data.token))).scalar_one_or_none()
    if found:
        await db.execute(update(t).where(t.c.id == found).values(**values))
    else:
        await db.execute(insert(t).values(id=uuid.uuid4(), token=data.token, **values))
    await db.flush()
    return DeviceOut(platform=data.platform, provider=provider)


@router.delete("/devices", status_code=status.HTTP_204_NO_CONTENT)
async def remove_device(me: Me, db: DB, token: Annotated[str, Query(min_length=10, max_length=4096)]) -> None:
    """Stop pushing to this phone (sign-out). Only the person's own token; an unknown one is fine."""
    t = device_tokens()
    await db.execute(delete(t).where(t.c.token == token, t.c.user_id == me.id))
    await db.flush()
