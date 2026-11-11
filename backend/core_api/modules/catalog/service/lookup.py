"""Small read-only lookups other modules use instead of reading catalog tables."""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.catalog.models.restaurant import Restaurant


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
