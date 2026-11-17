"""Small read-only lookups other modules use instead of reading catalog tables."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant
from core_api.modules.catalog.service.ratings import rating_display


async def restaurant_city_code(db: AsyncSession, restaurant_id: str | uuid.UUID) -> str | None:
    """The market city code (e.g. IN-TG-HYD) a restaurant sits in: found from
    its location via markets (the zone it is in), or by city name."""
    from core_api.modules.markets.service.markets import MarketService

    try:
        rid = uuid.UUID(str(restaurant_id))
    except ValueError:
        return None
    r = await db.get(Restaurant, rid)
    if r is None:
        return None
    markets = MarketService(db)
    if r.lat is not None and r.lng is not None:
        for zone, city, _, _ in await markets.repo.zones_containing(r.lat, r.lng):
            return city.code
    for city in await markets.repo.cities():
        country = await markets.repo.country(r.country)
        if country and city.country_id == country.id and city.name.lower() == (r.city or "").lower():
            return city.code
    return None


def _live(r: Restaurant) -> bool:
    return r.is_active and r.status == "active" and r.deleted_at is None


def _restaurant_card(r: Restaurant, photo_url: str | None = None) -> dict:
    return {"id": str(r.id), "slug": r.slug, "name": r.name, "cuisine_types": list(r.cuisine_types or []),
            "cover_url": r.cover_url, "photo_url": photo_url, "city": r.city, "country": r.country, "rating": r.rating,
            "review_count": r.review_count, "delivery_time_min": r.delivery_time_min,
            "delivery_time_max": r.delivery_time_max, "delivery_fee": float(r.delivery_fee), "currency": r.currency,
            "rating_display": rating_display(r.rating, r.review_count).model_dump()}


async def restaurant_cards(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Listing cards for live restaurants (favourites). Gone or paused-for-good ones are left out."""
    from sqlalchemy import select

    if not ids:
        return {}
    from core_api.modules.catalog.service.photos import photos_for

    rows = [r for r in (await db.execute(select(Restaurant).where(Restaurant.id.in_(ids)))).scalars() if _live(r)]
    shown = await photos_for(db, rows)
    return {r.id: _restaurant_card(r, shown.get(str(r.id))) for r in rows}


async def item_cards(db: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    """Dishes on a live menu, each with its restaurant (id, slug, name, city, country: its page's address) (favourites)."""
    from sqlalchemy import select

    from core_api.modules.catalog.models.menu import MenuItem
    from core_api.modules.catalog.service.menu import is_sold_out

    if not ids:
        return {}
    items = list((await db.execute(select(MenuItem).where(MenuItem.id.in_(ids), MenuItem.deleted_at.is_(None)))).scalars())
    rests = {r.id: r for r in (await db.execute(
        select(Restaurant).where(Restaurant.id.in_({i.restaurant_id for i in items})))).scalars()} if items else {}
    out = {}
    for i in items:
        r = rests.get(i.restaurant_id)
        if r is None or not _live(r):
            continue
        out[i.id] = {"id": str(i.id), "name": i.name, "price": float(i.price), "currency": r.currency,
                     "image_url": i.image_url, "available": i.is_available and not is_sold_out(i),
                     "restaurant": {"id": str(r.id), "slug": r.slug, "name": r.name, "city": r.city, "country": r.country}}
    return out


async def restaurant_brief(db: AsyncSession, restaurant_id: uuid.UUID) -> dict | None:
    """Who the kitchen is, for receipts and reorders: name, slug, address, licences."""
    r = await db.get(Restaurant, restaurant_id)
    if r is None:
        return None
    return {"id": str(r.id), "slug": r.slug, "name": r.name, "address": dict(r.address or {}), "city": r.city,
            "country": r.country, "currency": r.currency, "fssai": r.fssai_number, "gstin": r.gstin}


async def restaurant_slugs(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Slugs by id (order history links to the kitchen's page)."""
    from sqlalchemy import select

    if not ids:
        return {}
    return {rid: slug for rid, slug in (await db.execute(select(Restaurant.id, Restaurant.slug).where(Restaurant.id.in_(ids)))).all()}


async def reviews_by(db: AsyncSession, customer_id: uuid.UUID) -> list[dict]:
    """The customer's own reviews (data export)."""
    from sqlalchemy import select

    from core_api.modules.catalog.models.review import Review

    rows = (await db.execute(select(Review).where(Review.customer_id == customer_id).order_by(Review.created_at))).scalars()
    return [{"id": str(v.id), "restaurant_id": str(v.restaurant_id), "order_id": str(v.order_id), "rating": v.rating,
             "food_rating": v.food_rating, "delivery_rating": v.delivery_rating, "comment": v.comment,
             "created_at": v.created_at.isoformat()} for v in rows]


async def forget_reviewer(db: AsyncSession, customer_id: uuid.UUID) -> None:
    """Account deletion: reviews stay (they're the kitchen's rating) without the name or photo."""
    from sqlalchemy import update

    from core_api.modules.catalog.models.review import Review

    await db.execute(update(Review).where(Review.customer_id == customer_id)
                     .values(customer_name="Deleted user", customer_avatar=None))
