"""Markets service. Other modules use this (never the tables): e.g. the quote
engine (P8) calls ``locate`` to turn an address into zone -> city -> country.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.markets.models import City, Country, Region, Zone
from core_api.modules.markets.repository import MarketRepository
from core_api.modules.markets.schemas import (
    CityCreate,
    CityDetail,
    CityOut,
    CitySummary,
    CityUpdate,
    CountryCreate,
    CountryOut,
    CountrySummary,
    CountryUpdate,
    LocateResult,
    RegionCreate,
    RegionOut,
    RegionSummary,
    RegionUpdate,
    SettingValue,
    ZoneCreate,
    ZoneOut,
    ZonePause,
    ZoneUpdate,
)
from core_api.modules.markets.service import rules
from core_api.modules.markets.service.rules import MarketRuleError, ZoneState
from shared import authz
from shared.providers.routing import haversine_km

MAX_ZONE_DISTANCE_KM = 80  # a zone's corners must be this close to its city centre


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    pass


def _visible(scopes: list[str], code: str) -> bool:
    return any(authz.covers(s, code) or authz.covers(code, s) for s in scopes)


class MarketService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MarketRepository(db)

    # ── views ────────────────────────────────────────────────────────────────
    async def overview(self, scopes: list[str]) -> list[CountrySummary]:
        """Countries -> states -> cities the caller may see (``scopes`` from authz)."""
        now = datetime.now(UTC)
        countries = [c for c in await self.repo.countries() if _visible(scopes, c.code)]
        regions = await self.repo.regions()
        cities = await self.repo.cities()
        zones = await self.repo.zones_with_geo([c.id for c in cities])
        zones_by_city: dict[uuid.UUID, list[Zone]] = {}
        for z, _, _ in zones:
            zones_by_city.setdefault(z.city_id, []).append(z)

        out = []
        for country in countries:
            regs = []
            for region in (r for r in regions if r.country_id == country.id and _visible(scopes, r.code)):
                city_rows = [
                    self._city_summary(city, country, region, zones_by_city.get(city.id, []), now)
                    for city in cities
                    if city.region_id == region.id and _visible(scopes, city.code)
                ]
                regs.append(RegionSummary(**RegionOut.model_validate(region).model_dump(), cities=city_rows))
            out.append(CountrySummary(**CountryOut.model_validate(country).model_dump(), regions=regs))
        return out

    def _city_summary(self, city: City, country: Country, region: Region, zones: list[Zone], now: datetime) -> CitySummary:
        states = [ZoneState(z.status, z.paused_until) for z in zones]
        checklist = rules.launch_checklist(
            country_status=country.status, region_status=region.status,
            service_hours=city.service_hours, zones=states, now=now,
        )
        return CitySummary(
            **CityOut.model_validate(city).model_dump(),
            zone_count=len(zones),
            live_zone_count=sum(1 for s in states if s.is_open(now)),
            launch_checklist=checklist,
        )

    async def city_detail(self, code: str) -> CityDetail:
        city, region, country = await self._city_chain(code)
        zone_rows = await self.repo.zones_with_geo([city.id])
        summary = self._city_summary(city, country, region, [z for z, _, _ in zone_rows], datetime.now(UTC))
        return CityDetail(
            **summary.model_dump(),
            country=CountryOut.model_validate(country),
            region=RegionOut.model_validate(region),
            zones=[self._zone_out(z, geo, area, city.code) for z, geo, area in zone_rows],
            effective_settings=[SettingValue(**s) for s in rules.effective_settings(country, region, city)],
        )

    async def region_chain(self, code: str) -> tuple[Region, Country]:
        region = await self.repo.region(code)
        if not region:
            raise NotFound(f"State {code} not found")
        country = await self.db.get(Country, region.country_id)
        assert country is not None
        return region, country

    async def _city_chain(self, code: str) -> tuple[City, Region, Country]:
        city = await self.repo.city(code)
        if not city:
            raise NotFound(f"City {code} not found")
        region = await self.db.get(Region, city.region_id)
        country = await self.db.get(Country, city.country_id)
        assert region is not None and country is not None
        return city, region, country

    @staticmethod
    def _zone_out(z: Zone, geo: dict, area: float, city_code: str) -> ZoneOut:
        return ZoneOut(
            id=z.id, city_code=city_code, name=z.name, polygon=geo, area_km2=area, min_order=z.min_order,
            color=z.color, status=z.status, pause_reason=z.pause_reason, paused_until=z.paused_until,  # type: ignore[arg-type]
        )

    # ── countries ────────────────────────────────────────────────────────────
    async def create_country(self, data: CountryCreate) -> CountryOut:
        if await self.repo.country(data.code):
            raise Conflict(f"Country {data.code} already exists")
        c = await self.repo.add(Country(**data.model_dump(), status="draft"))
        return CountryOut.model_validate(c)

    async def update_country(self, code: str, data: CountryUpdate) -> CountryOut:
        c = await self.repo.country(code)
        if not c:
            raise NotFound(f"Country {code} not found")
        patch = data.model_dump(exclude_unset=True)
        if "settings" in patch:
            c.settings = rules.merge_settings(c.settings, patch.pop("settings") or {})
        for k, v in patch.items():
            setattr(c, k, v)
        await self.db.flush()
        await self.db.refresh(c)
        return CountryOut.model_validate(c)

    # ── regions ──────────────────────────────────────────────────────────────
    async def create_region(self, country_code: str, data: RegionCreate) -> RegionOut:
        country = await self.repo.country(country_code)
        if not country:
            raise NotFound(f"Country {country_code} not found")
        if not data.code.startswith(country.code + "-"):
            raise MarketRuleError(f"A state in {country.name} has a code starting {country.code}-")
        if await self.repo.region(data.code):
            raise Conflict(f"State {data.code} already exists")
        rules.check_overrides(data.settings)
        r = await self.repo.add(Region(country_id=country.id, **data.model_dump(), status="draft"))
        return RegionOut.model_validate(r)

    async def update_region(self, code: str, data: RegionUpdate) -> RegionOut:
        region, country = await self.region_chain(code)
        patch = data.model_dump(exclude_unset=True)
        if "status" in patch:
            rules.check_parent_open(patch["status"], country.status, country.name)
        if "settings" in patch:
            s = patch.pop("settings") or {}
            rules.check_overrides(s)
            region.settings = rules.merge_settings(region.settings, s)
        for k, v in patch.items():
            setattr(region, k, v)
        await self.db.flush()
        await self.db.refresh(region)
        return RegionOut.model_validate(region)

    # ── cities ───────────────────────────────────────────────────────────────
    async def create_city(self, region_code: str, data: CityCreate) -> CityOut:
        region, country = await self.region_chain(region_code)
        if not data.code.startswith(region.code + "-"):
            raise MarketRuleError(f"A city in {region.name} has a code starting {region.code}-")
        if await self.repo.city(data.code):
            raise Conflict(f"City {data.code} already exists")
        rules.check_overrides(data.settings)
        payload = data.model_dump()
        city = await self.repo.add(City(country_id=country.id, region_id=region.id, **payload, status="draft"))
        return CityOut.model_validate(city)

    async def update_city(self, code: str, data: CityUpdate) -> CityOut:
        city, region, country = await self._city_chain(code)
        patch = data.model_dump(exclude_unset=True)
        if "settings" in patch:
            s = patch.pop("settings") or {}
            rules.check_overrides(s)
            city.settings = rules.merge_settings(city.settings, s)
        for k, v in patch.items():
            setattr(city, k, v)
        if "status" in patch:
            zones = [z for z, _, _ in await self.repo.zones_with_geo([city.id])]
            checklist = rules.launch_checklist(
                country_status=country.status, region_status=region.status, service_hours=city.service_hours,
                zones=[ZoneState(z.status, z.paused_until) for z in zones], now=datetime.now(UTC),
            )
            rules.check_city_status(patch["status"], checklist)
        await self.db.flush()
        await self.db.refresh(city)
        return CityOut.model_validate(city)

    # ── zones ────────────────────────────────────────────────────────────────
    async def _check_polygon(self, city: City, geojson: dict) -> None:
        for lng, lat in geojson["coordinates"][0]:
            if haversine_km((city.center_lat, city.center_lng), (lat, lng)) > MAX_ZONE_DISTANCE_KM:
                raise MarketRuleError(
                    f"This shape is more than {MAX_ZONE_DISTANCE_KM} km from {city.name}; are latitude and longitude swapped?"
                )
        if not await self.repo.polygon_is_valid(geojson):
            raise MarketRuleError("The shape crosses itself; redraw it so the edges don't cross")

    async def create_zone(self, city_code: str, data: ZoneCreate) -> ZoneOut:
        city, _, _ = await self._city_chain(city_code)
        geo = data.polygon.model_dump()
        await self._check_polygon(city, geo)
        zone = Zone(
            city_id=city.id, name=data.name, polygon=MarketRepository.polygon_expr(geo),
            min_order=data.min_order, color=data.color, status=data.status,
        )
        try:
            async with self.db.begin_nested():
                self.db.add(zone)
                await self.db.flush()
        except IntegrityError:
            raise Conflict(f"{city.name} already has a zone called {data.name}")
        return await self.zone_out(zone.id)

    async def zone_out(self, zone_id: uuid.UUID) -> ZoneOut:
        zone = await self.repo.zone(zone_id)
        if not zone:
            raise NotFound("Zone not found")
        city = await self.db.get(City, zone.city_id)
        assert city is not None
        for z, geo, area in await self.repo.zones_with_geo([city.id]):
            if z.id == zone_id:
                return self._zone_out(z, geo, area, city.code)
        raise NotFound("Zone not found")

    async def zone_city_code(self, zone_id: uuid.UUID) -> str:
        zone = await self.repo.zone(zone_id)
        if not zone:
            raise NotFound("Zone not found")
        city = await self.db.get(City, zone.city_id)
        assert city is not None
        return city.code

    async def update_zone(self, zone_id: uuid.UUID, data: ZoneUpdate) -> ZoneOut:
        zone = await self.repo.zone(zone_id)
        if not zone:
            raise NotFound("Zone not found")
        city = await self.db.get(City, zone.city_id)
        assert city is not None
        patch = data.model_dump(exclude_unset=True)
        if "polygon" in patch:
            geo = patch.pop("polygon")
            await self._check_polygon(city, geo)
            zone.polygon = MarketRepository.polygon_expr(geo)  # type: ignore[assignment]
        if "status" in patch:
            zone.pause_reason = None
            zone.paused_until = None
        for k, v in patch.items():
            setattr(zone, k, v)
        try:
            async with self.db.begin_nested():
                await self.db.flush()
        except IntegrityError:
            raise Conflict(f"{city.name} already has a zone called {data.name}")
        self.db.expire(zone)
        return await self.zone_out(zone_id)

    async def pause_zone(self, zone_id: uuid.UUID, data: ZonePause) -> ZoneOut:
        zone = await self.repo.zone(zone_id)
        if not zone:
            raise NotFound("Zone not found")
        if zone.status == "draft":
            raise MarketRuleError("A draft zone isn't open, so there is nothing to pause")
        if data.until is not None and data.until <= datetime.now(UTC):
            raise MarketRuleError("Pick a time in the future, or leave it empty to pause until resumed")
        zone.status, zone.pause_reason, zone.paused_until = "paused", data.reason, data.until
        await self.db.flush()
        return await self.zone_out(zone_id)

    async def resume_zone(self, zone_id: uuid.UUID) -> ZoneOut:
        zone = await self.repo.zone(zone_id)
        if not zone:
            raise NotFound("Zone not found")
        if zone.status != "paused":
            raise MarketRuleError("This zone isn't paused")
        zone.status, zone.pause_reason, zone.paused_until = "live", None, None
        await self.db.flush()
        return await self.zone_out(zone_id)

    # ── locate (used by apps and the quote engine) ───────────────────────────
    async def locate(self, lat: float, lng: float) -> LocateResult:
        now = datetime.now(UTC)
        hits = await self.repo.zones_containing(lat, lng)
        for zone, city, region, country in hits:
            if ZoneState(zone.status, zone.paused_until).is_open(now) and rules.chain_open(
                country.status, region.status, city.status
            ):
                return LocateResult(
                    serviceable=True, country_code=country.code, region_code=region.code, city_code=city.code,
                    city_name=city.name, zone_id=zone.id, zone_name=zone.name, min_order=zone.min_order,
                    currency=country.currency, timezone=city.timezone or region.timezone or country.timezone,
                    status="beta" if "beta" in (country.status, region.status, city.status, zone.status) else "live",
                )
        if hits:
            zone, city, _, _ = hits[0]
            why = (
                f"Delivery in {zone.name} is paused: {zone.pause_reason}" if zone.status == "paused"
                else f"We're not delivering in {city.name} yet"
            )
            return LocateResult(serviceable=False, reason=why, city_code=city.code, city_name=city.name)
        return LocateResult(serviceable=False, reason="We don't deliver here yet")
