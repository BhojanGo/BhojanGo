"""Time zones of cities, for other modules: a city's own zone, else its region's,
else its country's (IANA names, Markets data)."""
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def city_time_zones(db: AsyncSession, codes: Iterable[str | None]) -> dict[str, str]:
    """{city code: IANA zone} for the given city codes, in one query. Unknown codes are left out."""
    from core_api.modules.markets.models import City, Country, Region

    wanted = {c for c in codes if c}
    if not wanted:
        return {}
    rows = (await db.execute(
        select(City.code, City.timezone, Region.timezone, Country.timezone)
        .join(Region, Region.id == City.region_id).join(Country, Country.id == City.country_id)
        .where(City.code.in_(wanted)))).all()
    return {code: city_tz or region_tz or country_tz for code, city_tz, region_tz, country_tz in rows}
