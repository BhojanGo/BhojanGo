"""The signed-in account area: favourites, notification preferences, data export."""
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user
from core_api.modules.identity.models.user import User
from core_api.modules.identity.service import account
from shared.db import get_db

router = APIRouter(prefix="/me", tags=["Account"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[User, Depends(get_current_active_user)]
FavouriteKind = Literal["restaurant", "item"]


# ── favourites ───────────────────────────────────────────────────────────────

class FavouriteRestaurant(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    cuisine_types: list[str]
    cover_url: str | None
    city: str
    country: str
    rating: float
    review_count: int
    delivery_time_min: int
    delivery_time_max: int
    delivery_fee: float
    currency: str
    saved_at: datetime


class FavouriteItemRestaurant(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class FavouriteItem(BaseModel):
    id: uuid.UUID
    name: str
    price: float
    currency: str
    image_url: str | None
    available: bool
    restaurant: FavouriteItemRestaurant
    saved_at: datetime


class FavouritesOut(BaseModel):
    restaurants: list[FavouriteRestaurant]
    items: list[FavouriteItem]


@router.get("/favourites", response_model=FavouritesOut)
async def list_favourites(me: Me, db: DB) -> FavouritesOut:
    """Your saved kitchens and dishes (ones no longer on BhojanGo aren't shown)."""
    return FavouritesOut(**await account.favourites(db, me.id))


@router.put("/favourites/{kind}/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_favourite(kind: FavouriteKind, target_id: uuid.UUID, me: Me, db: DB) -> None:
    """Save a kitchen or a dish. Saving it again changes nothing."""
    if not await account.target_exists(db, kind, target_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found" if kind == "restaurant" else "Item not found")
    await account.add_favourite(db, me.id, kind, target_id)


@router.delete("/favourites/{kind}/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favourite(kind: FavouriteKind, target_id: uuid.UUID, me: Me, db: DB) -> None:
    await account.remove_favourite(db, me.id, kind, target_id)


# ── notification preferences ─────────────────────────────────────────────────

class Channels(BaseModel):
    push: bool
    sms: bool
    email: bool


class ChannelsUpdate(BaseModel):
    push: bool | None = None
    sms: bool | None = None
    email: bool | None = None


class NotificationPreferencesOut(BaseModel):
    """What we may send you, per kind of message and channel. Offers are off
    until you turn them on."""

    orders: Channels
    offers: Channels
    account: Channels


class NotificationPreferencesUpdate(BaseModel):
    """Only the switches you send change."""

    orders: ChannelsUpdate | None = None
    offers: ChannelsUpdate | None = None
    account: ChannelsUpdate | None = None


@router.get("/notification-preferences", response_model=NotificationPreferencesOut)
async def get_notification_preferences(me: Me, db: DB) -> NotificationPreferencesOut:
    return NotificationPreferencesOut(**await account.preferences(db, me.id))  # type: ignore[arg-type]


@router.put("/notification-preferences", response_model=NotificationPreferencesOut)
async def set_notification_preferences(data: NotificationPreferencesUpdate, me: Me, db: DB) -> NotificationPreferencesOut:
    changes = {c: sent.model_dump(exclude_none=True) for c in account.CATEGORIES if (sent := getattr(data, c)) is not None}
    return NotificationPreferencesOut(**await account.set_preferences(db, me.id, changes))  # type: ignore[arg-type]


# ── data export ──────────────────────────────────────────────────────────────

@router.get("/export", responses={200: {"content": {"application/json": {}},
                                        "description": "Your data as a JSON file"}})
async def export_my_data(me: Me, db: DB) -> Response:
    """Download everything we hold about you as JSON: profile, addresses,
    orders with their bills, saved cards (masked), favourites, notification
    preferences, support tickets, refunds and problems, reviews."""
    data = await account.export(db, me)
    name = f"bhojango-data-{datetime.now(UTC):%Y-%m-%d}.json"
    return Response(json.dumps(data, indent=2, ensure_ascii=False, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
