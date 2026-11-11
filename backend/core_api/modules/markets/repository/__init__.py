"""Database access for markets, including the PostGIS zone queries."""
import json
import uuid

from geoalchemy2.functions import ST_Area, ST_AsGeoJSON, ST_Contains, ST_GeomFromGeoJSON, ST_IsValid, ST_SetSRID
from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.markets.models import City, Country, Region, Zone


class MarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.s = session

    # ── reads ────────────────────────────────────────────────────────────────
    async def countries(self) -> list[Country]:
        return list((await self.s.execute(select(Country).order_by(Country.name))).scalars())

    async def country(self, code: str) -> Country | None:
        return (await self.s.execute(select(Country).where(Country.code == code))).scalar_one_or_none()

    async def regions(self, country_id: uuid.UUID | None = None) -> list[Region]:
        q = select(Region).order_by(Region.name)
        if country_id:
            q = q.where(Region.country_id == country_id)
        return list((await self.s.execute(q)).scalars())

    async def region(self, code: str) -> Region | None:
        return (await self.s.execute(select(Region).where(Region.code == code))).scalar_one_or_none()

    async def cities(self, country_id: uuid.UUID | None = None) -> list[City]:
        q = select(City).order_by(City.name)
        if country_id:
            q = q.where(City.country_id == country_id)
        return list((await self.s.execute(q)).scalars())

    async def city(self, code: str) -> City | None:
        return (await self.s.execute(select(City).where(City.code == code))).scalar_one_or_none()

    async def zone(self, zone_id: uuid.UUID) -> Zone | None:
        return await self.s.get(Zone, zone_id)

    async def zones_with_geo(self, city_ids: list[uuid.UUID]) -> list[tuple[Zone, dict, float]]:
        """Zones with their polygon as GeoJSON and area in km²."""
        if not city_ids:
            return []
        q = (
            select(
                Zone,
                ST_AsGeoJSON(Zone.polygon),
                (ST_Area(cast(Zone.polygon, _geography())) / 1_000_000.0).cast(Float),
            )
            .where(Zone.city_id.in_(city_ids))
            .order_by(Zone.name)
        )
        rows = (await self.s.execute(q)).all()
        return [(z, json.loads(geo), round(area or 0.0, 2)) for z, geo, area in rows]

    async def zones_containing(self, lat: float, lng: float) -> list[tuple[Zone, City, Region, Country]]:
        """Every zone whose polygon contains the point, smallest first."""
        point = ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
        q = (
            select(Zone, City, Region, Country)
            .join(City, City.id == Zone.city_id)
            .join(Region, Region.id == City.region_id)
            .join(Country, Country.id == City.country_id)
            .where(ST_Contains(Zone.polygon, point))
            .order_by(ST_Area(Zone.polygon))
        )
        return [tuple(r) for r in (await self.s.execute(q)).all()]  # type: ignore[misc]

    async def polygon_is_valid(self, geojson: dict) -> bool:
        geom = ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(geojson)), 4326)
        return bool((await self.s.execute(select(ST_IsValid(geom)))).scalar())

    # ── writes ───────────────────────────────────────────────────────────────
    async def add(self, obj):  # type: ignore[no-untyped-def]
        self.s.add(obj)
        await self.s.flush()
        await self.s.refresh(obj)
        return obj

    @staticmethod
    def polygon_expr(geojson: dict):  # type: ignore[no-untyped-def]
        return ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(geojson)), 4326)


def _geography():  # type: ignore[no-untyped-def]
    from geoalchemy2 import Geography

    return Geography(srid=4326)
