"""R39: the US food permit (Idaho: the health district's food establishment permit).

Required where the restaurant's country has the Markets setting ``food_permit_required`` (the seeds turn it
on for the US). The restaurant gives the permit number, its expiry date and a photo or PDF of it (website
"Add your restaurant", the BhojanGo Restaurant app); an admin reviews it (Partners > Applications > Food
permits). The restaurant goes live only with an approved permit. 30 days before it expires the owner is
reminded (outbox ``restaurant.permit_expiring`` -> worker push and email); once it has expired the listing
pauses itself (``paused_reason = food_permit_expired``) until a renewed permit is approved.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant
from shared import outbox

logger = structlog.get_logger(__name__)

EXPIRED = "food_permit_expired"
REMIND_DAYS = 30
SETTING = "food_permit_required"


class PermitError(ValueError):
    pass


async def required(db: AsyncSession, country: str | None) -> bool:
    from core_api.modules.markets.models import Country

    if not country:
        return False
    c = (await db.execute(select(Country).where(Country.code == country))).scalars().first()
    return bool(c and (c.settings or {}).get(SETTING))


async def _countries(db: AsyncSession) -> list[str]:
    from core_api.modules.markets.models import Country

    return [c.code for c in (await db.execute(select(Country))).scalars() if (c.settings or {}).get(SETTING)]


def expired(r: Restaurant, today: date) -> bool:
    return r.food_permit_expires_on is not None and r.food_permit_expires_on < today


def submitted(r: Restaurant) -> bool:
    return bool(r.food_permit_number and r.food_permit_expires_on and r.food_permit_document_key)


def problem(r: Restaurant, today: date, is_required: bool) -> str | None:
    """Why the restaurant can't go live yet (None: it can)."""
    if not is_required:
        return None
    if not submitted(r):
        return "Food permit missing"
    if expired(r, today):
        return "Food permit expired"
    if r.food_permit_status != "approved":
        return "Food permit not approved yet"
    return None


async def submit(db: AsyncSession, r: Restaurant, number: str, expires_on: date, document_key: str | None, today: date) -> Restaurant:
    number = " ".join(number.split())
    if not 3 <= len(number) <= 40:
        raise PermitError("Enter the permit number as it is printed on the permit")
    if expires_on < today:
        raise PermitError("This permit has already expired: add the renewed one")
    if not document_key and not r.food_permit_document_key:
        raise PermitError("Add a photo or PDF of the permit")
    r.food_permit_number, r.food_permit_expires_on = number, expires_on
    if document_key:
        r.food_permit_document_key = document_key
    r.food_permit_status, r.food_permit_note = "pending", None
    r.food_permit_reviewed_by = r.food_permit_reviewed_at = None
    await db.flush()
    logger.info("food_permit_submitted", restaurant_id=str(r.id), expires_on=expires_on.isoformat())
    return r


async def review(db: AsyncSession, r: Restaurant, approve: bool, admin_id: uuid.UUID, note: str | None, today: date) -> Restaurant:
    from core_api.modules.catalog.service.menu import _forget_cached_listings

    if not submitted(r):
        raise PermitError("There is no permit to review")
    if approve and expired(r, today):
        raise PermitError("This permit has expired: ask the restaurant for the renewed one")
    if not approve and not (note or "").strip():
        raise PermitError("Say why the permit is turned down (the restaurant sees it)")
    r.food_permit_status = "approved" if approve else "rejected"
    r.food_permit_note = None if approve else (note or "").strip()[:300]
    r.food_permit_reviewed_by, r.food_permit_reviewed_at = admin_id, datetime.now(UTC)
    if approve and r.paused_reason == EXPIRED:
        r.paused_reason = None  # renewed and approved: listed again
        await _forget_cached_listings()
        logger.info("restaurant_relisted_after_permit", restaurant_id=str(r.id))
    await db.flush()
    return r


async def pause_expired(db: AsyncSession, today: date) -> list[uuid.UUID]:
    """Pause every listing whose food permit has expired (idempotent; every hour)."""
    from core_api.modules.catalog.service.menu import _forget_cached_listings

    countries = await _countries(db)
    if not countries:
        return []
    paused = list((await db.execute(
        update(Restaurant)
        .where(Restaurant.country.in_(countries), Restaurant.paused_reason.is_(None), Restaurant.deleted_at.is_(None),
               Restaurant.food_permit_expires_on < today)
        .values(paused_reason=EXPIRED).returning(Restaurant.id))).scalars())
    for rid in paused:
        logger.warning("restaurant_paused_food_permit_expired", restaurant_id=str(rid))
    if paused:
        await _forget_cached_listings()
    return paused


async def remind_expiring(db: AsyncSession, today: date) -> list[uuid.UUID]:
    """Remind each owner once per permit, 30 days before it expires (or at the first check after that)."""
    countries = await _countries(db)
    if not countries:
        return []
    rows = (await db.execute(select(Restaurant).where(
        Restaurant.country.in_(countries), Restaurant.deleted_at.is_(None), Restaurant.owner_id.is_not(None),
        Restaurant.food_permit_expires_on >= today, Restaurant.food_permit_expires_on <= today + timedelta(days=REMIND_DAYS),
    ).with_for_update(skip_locked=True))).scalars().all()
    done = []
    for r in rows:
        if r.food_permit_reminded_for == r.food_permit_expires_on:
            continue
        r.food_permit_reminded_for = r.food_permit_expires_on
        assert r.food_permit_expires_on is not None
        await outbox.add(db, "restaurant.permit_expiring", "restaurant", r.id, {
            "restaurant_id": str(r.id), "owner_id": str(r.owner_id), "restaurant": r.name,
            "expires_on": r.food_permit_expires_on.isoformat(), "days_left": (r.food_permit_expires_on - today).days}, "catalog")
        logger.info("food_permit_reminder", restaurant_id=str(r.id), expires_on=r.food_permit_expires_on.isoformat())
        done.append(r.id)
    await db.flush()
    return done


def out(r: Restaurant, is_required: bool | None = None) -> dict:
    return {"restaurant_id": str(r.id), "required": is_required, "number": r.food_permit_number,
            "expires_on": r.food_permit_expires_on.isoformat() if r.food_permit_expires_on else None,
            "document": bool(r.food_permit_document_key), "document_key": r.food_permit_document_key,
            "status": r.food_permit_status, "note": r.food_permit_note,
            "reviewed_at": r.food_permit_reviewed_at.isoformat() if r.food_permit_reviewed_at else None,
            "paused": r.paused_reason == EXPIRED}
