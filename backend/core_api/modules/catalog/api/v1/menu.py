"""Menu modifiers, store hours, sold out today, prep time and FSSAI (P10).

Who may change a restaurant: its owner (partner account), or an admin with
partners.edit for the restaurant's city. Reads are public.
"""
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.catalog.models.menu import MenuItem
from core_api.modules.catalog.models.options import OptionGroup, StoreHours, StoreHoursOverride
from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service import access
from core_api.modules.catalog.service import menu as svc
from core_api.modules.catalog.service.lookup import restaurant_city_code
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/restaurants", tags=["Menu and hours"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]


class OptionIn(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    is_default: bool = False
    is_available: bool = True


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Spice"])
    min_picks: int = Field(default=0, ge=0, le=20)
    max_picks: int = Field(default=1, ge=1, le=20)
    options: list[OptionIn] = Field(min_length=1)


class ItemGroupsIn(BaseModel):
    group_ids: list[uuid.UUID]


class SoldOutIn(BaseModel):
    sold_out: bool = Field(description="True: sold out until the restaurant's next midnight")


class HoursRange(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    opens: time
    closes: time = Field(description="Earlier than opens = runs past midnight")


class HoursIn(BaseModel):
    weekly: list[HoursRange]


class OverrideIn(BaseModel):
    closed: bool = True
    opens: time | None = None
    closes: time | None = None
    note: str | None = Field(default=None, max_length=120, examples=["Diwali"])


class PrepIn(BaseModel):
    minutes: int = Field(ge=5, le=120)


class LicenceIn(BaseModel):
    fssai_number: str = Field(pattern=r"^\d{14}$")
    fssai_expires_on: date
    # The certificate, uploaded first with POST /uploads (purpose partner_document), P19.
    document_key: str | None = Field(default=None, max_length=300)


async def _restaurant(db: AsyncSession, rid: uuid.UUID) -> Restaurant:
    return await access.restaurant_or_404(db, rid)


async def _manage(db: AsyncSession, user: CurrentUser, rid: uuid.UUID) -> Restaurant:
    return await access.manage(db, user, rid)


def _menu_error(e: svc.MenuError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": "MENU_RULE", "message": str(e)})


# ── availability ──────────────────────────────────────────────────────────────

@router.get("/{restaurant_id}/availability")
async def get_availability(restaurant_id: uuid.UUID, db: DB) -> dict:
    """Open now? If not, why and when it opens (restaurant hours, holidays,
    the city's delivery hours, a paused listing)."""
    try:
        a = await svc.availability(db, restaurant_id)
    except svc.MenuError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
    return {
        "restaurant_id": a.restaurant_id, "listed": a.listed, "open_now": a.open_now, "reason": a.reason,
        "next_open_at": a.next_open_at.isoformat() if a.next_open_at else None,
        "local_time": a.local_time.isoformat(), "timezone": a.timezone, "paused_reason": a.paused_reason,
    }


# ── option groups ─────────────────────────────────────────────────────────────

@router.get("/{restaurant_id}/option-groups")
async def list_groups(restaurant_id: uuid.UUID, db: DB) -> list[dict]:
    rows = (await db.execute(select(OptionGroup).where(OptionGroup.restaurant_id == restaurant_id)
                             .order_by(OptionGroup.sort_order, OptionGroup.name))).scalars()
    return [svc.group_out(g) for g in rows]


@router.post("/{restaurant_id}/option-groups", status_code=status.HTTP_201_CREATED)
async def create_group(restaurant_id: uuid.UUID, data: GroupIn, user: User, db: DB) -> dict:
    await _manage(db, user, restaurant_id)
    try:
        g = await svc.create_group(db, restaurant_id, data.name, data.min_picks, data.max_picks,
                                   [o.model_dump() for o in data.options])
    except svc.MenuError as e:
        raise _menu_error(e)
    return svc.group_out(g)


async def _group(db: AsyncSession, restaurant_id: uuid.UUID, group_id: uuid.UUID) -> OptionGroup:
    g = await db.get(OptionGroup, group_id)
    if g is None or g.restaurant_id != restaurant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Option group not found")
    return g


@router.put("/{restaurant_id}/option-groups/{group_id}")
async def update_group(restaurant_id: uuid.UUID, group_id: uuid.UUID, data: GroupIn, user: User, db: DB) -> dict:
    """Change a group. Send option ids back to keep them; options left out are removed."""
    await _manage(db, user, restaurant_id)
    g = await _group(db, restaurant_id, group_id)
    try:
        g = await svc.replace_group(db, g, data.name, data.min_picks, data.max_picks,
                                    [o.model_dump(mode="json") for o in data.options])
    except svc.MenuError as e:
        raise _menu_error(e)
    await db.refresh(g, ["options"])
    return svc.group_out(g)


@router.delete("/{restaurant_id}/option-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(restaurant_id: uuid.UUID, group_id: uuid.UUID, user: User, db: DB) -> Response:
    await _manage(db, user, restaurant_id)
    await db.delete(await _group(db, restaurant_id, group_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _item(db: AsyncSession, restaurant_id: uuid.UUID, item_id: uuid.UUID) -> MenuItem:
    item = await db.get(MenuItem, item_id)
    if item is None or item.restaurant_id != restaurant_id or item.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Menu item not found")
    return item


@router.put("/{restaurant_id}/menu-items/{item_id}/option-groups")
async def set_item_groups(restaurant_id: uuid.UUID, item_id: uuid.UUID, data: ItemGroupsIn, user: User, db: DB) -> dict:
    """Which groups the item offers, in this order."""
    await _manage(db, user, restaurant_id)
    item = await _item(db, restaurant_id, item_id)
    try:
        await svc.set_item_groups(db, item, data.group_ids)
    except svc.MenuError as e:
        raise _menu_error(e)
    groups = await svc.groups_for_items(db, [item.id])
    return {"menu_item_id": str(item.id), "option_groups": [svc.group_out(g) for g in groups.get(item.id, [])]}


@router.put("/{restaurant_id}/menu-items/{item_id}/sold-out")
async def sold_out(restaurant_id: uuid.UUID, item_id: uuid.UUID, data: SoldOutIn, user: User, db: DB) -> dict:
    """Sold out today: the item can't be ordered until the restaurant's next midnight."""
    await _manage(db, user, restaurant_id)
    item = await svc.set_sold_out_today(db, await _item(db, restaurant_id, item_id), data.sold_out)
    return {"menu_item_id": str(item.id), "sold_out_today": svc.is_sold_out(item),
            "sold_out_until": item.sold_out_until.isoformat() if item.sold_out_until else None}


# ── hours ─────────────────────────────────────────────────────────────────────

@router.get("/{restaurant_id}/hours")
async def get_hours(restaurant_id: uuid.UUID, db: DB) -> dict:
    await _restaurant(db, restaurant_id)
    weekly = (await db.execute(select(StoreHours).where(StoreHours.restaurant_id == restaurant_id)
                               .order_by(StoreHours.weekday, StoreHours.opens))).scalars()
    overrides = (await db.execute(select(StoreHoursOverride).where(StoreHoursOverride.restaurant_id == restaurant_id)
                                  .where(StoreHoursOverride.day >= datetime.now(UTC).date())
                                  .order_by(StoreHoursOverride.day))).scalars()
    return {
        "weekly": [{"weekday": h.weekday, "opens": h.opens.strftime("%H:%M"), "closes": h.closes.strftime("%H:%M")} for h in weekly],
        "overrides": [{"day": o.day.isoformat(), "closed": o.closed, "opens": o.opens.strftime("%H:%M") if o.opens else None,
                       "closes": o.closes.strftime("%H:%M") if o.closes else None, "note": o.note} for o in overrides],
    }


@router.put("/{restaurant_id}/hours")
async def set_hours(restaurant_id: uuid.UUID, data: HoursIn, user: User, db: DB) -> dict:
    """Replace the weekly hours (several ranges a day are fine, e.g. lunch and dinner)."""
    await _manage(db, user, restaurant_id)
    try:
        await svc.set_hours(db, restaurant_id, [h.model_dump() for h in data.weekly])
    except svc.MenuError as e:
        raise _menu_error(e)
    return await get_hours(restaurant_id, db)


@router.put("/{restaurant_id}/hours/overrides/{day}")
async def set_override(restaurant_id: uuid.UUID, day: date, data: OverrideIn, user: User, db: DB) -> dict:
    """A holiday (closed) or special hours for one local date."""
    await _manage(db, user, restaurant_id)
    try:
        await svc.set_override(db, restaurant_id, day, data.closed, data.opens, data.closes, data.note)
    except svc.MenuError as e:
        raise _menu_error(e)
    return await get_hours(restaurant_id, db)


@router.delete("/{restaurant_id}/hours/overrides/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_override(restaurant_id: uuid.UUID, day: date, user: User, db: DB) -> Response:
    await _manage(db, user, restaurant_id)
    row = (await db.execute(select(StoreHoursOverride).where(
        StoreHoursOverride.restaurant_id == restaurant_id, StoreHoursOverride.day == day))).scalar_one_or_none()
    if row:
        await db.delete(row)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── prep time and licence ─────────────────────────────────────────────────────

@router.put("/{restaurant_id}/prep-time")
async def set_prep_time(restaurant_id: uuid.UUID, data: PrepIn, user: User, db: DB) -> dict:
    """Default minutes from accepting an order to it being ready."""
    r = await _manage(db, user, restaurant_id)
    r.avg_prep_minutes = data.minutes
    await db.flush()
    return {"restaurant_id": str(r.id), "avg_prep_minutes": r.avg_prep_minutes}


@router.put("/{restaurant_id}/licence")
async def set_licence(restaurant_id: uuid.UUID, data: LicenceIn, user: User, db: DB) -> dict:
    """India: the FSSAI licence. A renewed licence lists a paused restaurant again."""
    r = await _manage(db, user, restaurant_id)
    if data.document_key is not None and not data.document_key.startswith(f"partner_document/{user.user_id}/"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "FILE_NOT_YOURS", "message": "Upload the licence first (POST /uploads)"})
    try:
        r = await svc.set_licence(db, r, data.fssai_number, data.fssai_expires_on, datetime.now(UTC).date())
    except svc.MenuError as e:
        raise _menu_error(e)
    if data.document_key:
        r.fssai_document_key = data.document_key
        await db.flush()
    return {"restaurant_id": str(r.id), "fssai_number": r.fssai_number,
            "fssai_expires_on": r.fssai_expires_on.isoformat() if r.fssai_expires_on else None,
            "paused_reason": r.paused_reason, "document_key": r.fssai_document_key}


@router.post("/licences/check")
async def check_licences(user: User, db: DB) -> dict:
    """Pause listings whose FSSAI licence has expired (also runs every hour)."""
    if not authz.can([authz.Assignment.parse(a) for a in user.admin], "partners.edit", "IN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    paused = await svc.pause_expired_licences(db, datetime.now(UTC).date())
    return {"paused": [str(p) for p in paused]}
