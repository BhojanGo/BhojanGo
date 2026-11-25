"""R43: menu editing for the restaurant (BhojanGo Kitchen) and admins.

* GET  /restaurants/{id}/menu/manage    everything the editor needs: every category (hidden ones too), every dish
                                        not deleted (unavailable ones too), option groups, currency and country.
* POST /restaurants/{id}/categories      add a category.
* PUT  /restaurants/{id}/categories/{c}  rename, hide or show, set or clear a schedule.
* PUT  /restaurants/{id}/categories-order  the categories in this order (drag to reorder).
* GET  /restaurants/{id}/menu/history    the menu's history (who, when, old -> new), newest first.

Who: the restaurant's owner, or an admin with partners.edit for its city (reading the history: partners.view).
Dishes are added, changed and deleted with /restaurants/{id}/menu-items (restaurants.py); option groups with
/restaurants/{id}/option-groups (menu.py). Every change is in the history.
"""
import uuid
from datetime import datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.api.dependencies import CurrentUser, get_current_user
from core_api.modules.catalog.models.menu import MenuCategory, MenuItem
from core_api.modules.catalog.models.options import OptionGroup
from core_api.modules.catalog.service import access
from core_api.modules.catalog.service import menu as svc
from core_api.modules.catalog.service import menu_edit as edit
from shared.db import get_db

router = APIRouter(prefix="/restaurants", tags=["Menu editing"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
User = Annotated[CurrentUser, Depends(get_current_user)]


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Breakfast"])
    description: str | None = Field(default=None, max_length=500)
    available_from: time | None = None
    available_until: time | None = None


class CategoryPatch(BaseModel):
    """Fields left out stay as they are; available_from/until sent as null clear the schedule."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = Field(default=None, description="False hides the category and its dishes from customers")
    available_from: time | None = None
    available_until: time | None = None


class OrderIn(BaseModel):
    category_ids: list[uuid.UUID] = Field(min_length=1)


def _rule(e: edit.RuleError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={"code": e.code, "message": str(e), **e.details})


def _hm(t: time | None) -> str | None:
    return t.strftime("%H:%M") if t else None


def _category_out(c: MenuCategory) -> dict:
    return {"id": str(c.id), "name": c.name, "description": c.description, "sort_order": c.sort_order,
            "is_active": c.is_active, "available_from": _hm(c.available_from), "available_until": _hm(c.available_until)}


async def _category(db: AsyncSession, rid: uuid.UUID, cid: uuid.UUID) -> MenuCategory:
    c = await db.get(MenuCategory, cid)
    if c is None or c.restaurant_id != rid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    return c


@router.get("/{restaurant_id}/menu/manage")
async def manage_menu(restaurant_id: uuid.UUID, user: User, db: DB) -> dict:
    """The whole menu as the restaurant edits it (customers' menu hides hidden categories and unavailable dishes)."""
    r = await access.manage(db, user, restaurant_id)
    cats = list((await db.execute(select(MenuCategory).where(MenuCategory.restaurant_id == r.id)
                                  .order_by(MenuCategory.sort_order, MenuCategory.name))).scalars())
    items = list((await db.execute(select(MenuItem).where(MenuItem.restaurant_id == r.id, MenuItem.deleted_at.is_(None))
                                   .order_by(MenuItem.sort_order, MenuItem.name))).scalars())
    groups = await svc.groups_for_items(db, [i.id for i in items])
    all_groups = list((await db.execute(select(OptionGroup).where(OptionGroup.restaurant_id == r.id)
                                        .order_by(OptionGroup.sort_order, OptionGroup.name))).scalars())
    by_cat = {c.id: c for c in cats}
    return {
        "restaurant_id": str(r.id), "currency": r.currency, "country": r.country,
        "whole_units": r.currency.upper() in edit.WHOLE_UNIT_CURRENCIES,
        "categories": [_category_out(c) for c in cats],
        "items": [{
            "id": str(i.id), "name": i.name, "description": i.description, "price": f"{i.price:.2f}",
            "image_url": i.image_url, "category_id": str(i.category_id) if i.category_id in by_cat else None,
            "category": i.category, "is_veg": i.is_veg, "spice_level": i.spice_level, "is_available": i.is_available,
            "sold_out_today": svc.is_sold_out(i), "available_from": _hm(i.available_from),
            "available_until": _hm(i.available_until), "sort_order": i.sort_order,
            "option_group_ids": [str(g.id) for g in groups.get(i.id, [])],
        } for i in items],
        "option_groups": [svc.group_out(g) for g in all_groups],
    }


@router.post("/{restaurant_id}/categories", status_code=status.HTTP_201_CREATED)
async def add_category(restaurant_id: uuid.UUID, data: CategoryIn, user: User, db: DB) -> dict:
    r = await access.manage(db, user, restaurant_id)
    try:
        edit.check_window(data.available_from, data.available_until)
    except edit.RuleError as e:
        raise _rule(e)
    if await _name_taken(db, r.id, data.name, None):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "CATEGORY_EXISTS", "message": f"{data.name.strip()} is already a category"})
    last = (await db.execute(select(func.max(MenuCategory.sort_order)).where(MenuCategory.restaurant_id == r.id))).scalar()
    c = MenuCategory(restaurant_id=r.id, name=data.name.strip(), description=data.description, sort_order=(last or 0) + 1,
                     available_from=data.available_from, available_until=data.available_until)
    db.add(c)
    await db.flush()
    await edit.record(db, r, user, entity="category", entity_id=c.id, name=c.name, action="added",
                      changes=edit.diff({}, edit.snapshot(c, edit.CATEGORY_FIELDS)))
    return _category_out(c)


async def _name_taken(db: AsyncSession, rid: uuid.UUID, name: str, other_than: uuid.UUID | None) -> bool:
    q = select(MenuCategory.id).where(MenuCategory.restaurant_id == rid, func.lower(MenuCategory.name) == name.strip().lower())
    if other_than is not None:
        q = q.where(MenuCategory.id != other_than)
    return (await db.execute(q)).first() is not None


@router.put("/{restaurant_id}/categories/{category_id}")
async def change_category(restaurant_id: uuid.UUID, category_id: uuid.UUID, data: CategoryPatch, user: User, db: DB) -> dict:
    """Rename (its dishes follow), hide or show, or set a schedule (both times) or clear it (both null)."""
    r = await access.manage(db, user, restaurant_id)
    c = await _category(db, r.id, category_id)
    before = edit.snapshot(c, edit.CATEGORY_FIELDS)
    start = data.available_from if "available_from" in data.model_fields_set else c.available_from
    end = data.available_until if "available_until" in data.model_fields_set else c.available_until
    try:
        edit.check_window(start, end)
    except edit.RuleError as e:
        raise _rule(e)
    if data.name is not None and data.name.strip() != c.name:
        if await _name_taken(db, r.id, data.name, c.id):
            raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "CATEGORY_EXISTS", "message": f"{data.name.strip()} is already a category"})
        c.name = data.name.strip()
        await db.execute(update(MenuItem).where(MenuItem.category_id == c.id).values(category=c.name))
    if data.is_active is not None:
        c.is_active = data.is_active
    c.available_from, c.available_until = start, end
    await db.flush()
    await edit.record(db, r, user, entity="category", entity_id=c.id, name=c.name, action="changed",
                      changes=edit.diff(before, edit.snapshot(c, edit.CATEGORY_FIELDS)))
    return _category_out(c)


@router.put("/{restaurant_id}/categories-order")
async def order_categories(restaurant_id: uuid.UUID, data: OrderIn, user: User, db: DB) -> list[dict]:
    """Every category of the menu, in the new order (the list must name each one once)."""
    r = await access.manage(db, user, restaurant_id)
    cats = {c.id: c for c in (await db.execute(select(MenuCategory).where(MenuCategory.restaurant_id == r.id))).scalars()}
    if len(data.category_ids) != len(set(data.category_ids)) or set(data.category_ids) != set(cats):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail={"code": "ORDER_RULE", "message": "Send every category of this menu once"})
    old = [c.name for c in sorted(cats.values(), key=lambda c: (c.sort_order, c.name))]
    for i, cid in enumerate(data.category_ids):
        cats[cid].sort_order = i + 1
    await db.flush()
    new = [cats[cid].name for cid in data.category_ids]
    if old != new:
        await edit.record(db, r, user, entity="menu", entity_id=None, name="Categories", action="reordered",
                          changes=[{"field": "order", "old": " · ".join(old), "new": " · ".join(new)}])
    return [_category_out(cats[cid]) for cid in data.category_ids]


@router.get("/{restaurant_id}/menu/history")
async def menu_history(restaurant_id: uuid.UUID, user: User, db: DB,
                       limit: int = Query(default=50, ge=1, le=200),
                       before: datetime | None = Query(default=None, description="Older than this (the last row's `at`)"),
                       item_id: uuid.UUID | None = Query(default=None, description="Only this dish, category or group")) -> dict:
    """Who changed what on the menu, newest first: {"changes": [...], "next": <before for the next page> | null}."""
    r = await access.manage(db, user, restaurant_id, permission="partners.view")
    rows = await edit.history(db, r.id, limit=limit, before=before, entity_id=item_id)
    is_admin = r.owner_id != user.id
    return {"changes": [edit.change_out(c, is_admin, user.id) for c in rows],
            "next": rows[-1].at.isoformat() if len(rows) == limit else None}

