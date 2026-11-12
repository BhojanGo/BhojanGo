"""Markets API: admins set up countries, states, cities and zones; apps ask
whether an address is served (``/markets/locate``).

Permissions (shared/authz.py), always at the scope of the record:
  read           markets.view
  add a country  markets.edit everywhere ("*": super admin)
  add a state    markets.edit on the country
  add a city     markets.edit on the state
  change a city or its zones   markets.edit on the city
  pause/resume a zone          zones.pause on the city (city ops too)
"""
import uuid
from typing import Annotated

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import AdminContext, require_permission
from core_api.modules.markets.schemas import (
    CityCreate,
    CityDetail,
    CityOut,
    CityUpdate,
    CountryCreate,
    CountryOut,
    CountrySummary,
    CountryUpdate,
    LocateResult,
    RegionCreate,
    RegionOut,
    RegionUpdate,
    ZoneCreate,
    ZoneOut,
    ZonePause,
    ZoneUpdate,
)
from core_api.modules.markets.service.markets import Conflict, MarketService, NotFound
from core_api.modules.markets.service.rules import MarketRuleError
from shared import authz
from shared.db import get_db

router = APIRouter(prefix="/markets", tags=["Markets"])

DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Viewer = Annotated[AdminContext, Depends(require_permission("markets.view"))]
Editor = Annotated[AdminContext, Depends(require_permission("markets.edit"))]
Pauser = Annotated[AdminContext, Depends(require_permission("zones.pause"))]


async def _run(coro):  # type: ignore[no-untyped-def]
    """Map service errors to HTTP responses."""
    try:
        return await coro
    except NotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": str(e)})
    except Conflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "ALREADY_EXISTS", "message": str(e)})
    except MarketRuleError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "MARKET_RULE", "message": str(e)})


# ── Public ────────────────────────────────────────────────────────────────────

@router.get("/locate", response_model=LocateResult)
async def locate(db: DB, lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)) -> LocateResult:
    """Is this point served? Returns the zone, city and country, or why not
    (the app's "not in your area" screen)."""
    return await MarketService(db).locate(lat, lng)


class WaitlistIn(BaseModel):
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$", examples=["+12085550199"])
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/waitlist", status_code=status.HTTP_202_ACCEPTED)
async def join_waitlist(data: WaitlistIn, db: DB) -> dict:
    """"Tell me when you launch" from the not-in-your-area screen. Signing up twice is fine."""
    from sqlalchemy.dialects.postgresql import insert

    from core_api.modules.markets.models import LaunchWaitlist

    await db.execute(insert(LaunchWaitlist).values(id=uuid.uuid4(), phone=data.phone, lat=data.lat, lng=data.lng)
                     .on_conflict_do_update(constraint="uq_launch_waitlist_phone", set_={"lat": data.lat, "lng": data.lng}))
    return {"ok": True}


# ── Overview ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CountrySummary])
async def overview(admin: Viewer, db: DB) -> list[CountrySummary]:
    """All countries -> states -> cities you can see, with launch checklists."""
    return await MarketService(db).overview(authz.scopes_with(admin.assignments, "markets.view"))


# ── Countries ─────────────────────────────────────────────────────────────────

@router.post("/countries", response_model=CountryOut, status_code=status.HTTP_201_CREATED)
async def create_country(data: CountryCreate, admin: Editor, db: DB) -> CountryOut:
    admin.require("markets.edit", authz.GLOBAL)
    return await _run(MarketService(db).create_country(data))


@router.patch("/countries/{code}", response_model=CountryOut)
async def update_country(code: str, data: CountryUpdate, admin: Editor, db: DB) -> CountryOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).update_country(code, data))


# ── States ────────────────────────────────────────────────────────────────────

@router.post("/countries/{code}/regions", response_model=RegionOut, status_code=status.HTTP_201_CREATED)
async def create_region(code: str, data: RegionCreate, admin: Editor, db: DB) -> RegionOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).create_region(code, data))


@router.patch("/regions/{code}", response_model=RegionOut)
async def update_region(code: str, data: RegionUpdate, admin: Editor, db: DB) -> RegionOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).update_region(code, data))


# ── Cities ────────────────────────────────────────────────────────────────────

@router.post("/regions/{code}/cities", response_model=CityOut, status_code=status.HTTP_201_CREATED)
async def create_city(code: str, data: CityCreate, admin: Editor, db: DB) -> CityOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).create_city(code, data))


@router.get("/cities/{code}", response_model=CityDetail)
async def city_detail(code: str, admin: Viewer, db: DB) -> CityDetail:
    admin.require("markets.view", code)
    return await _run(MarketService(db).city_detail(code))


@router.patch("/cities/{code}", response_model=CityOut)
async def update_city(code: str, data: CityUpdate, admin: Editor, db: DB) -> CityOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).update_city(code, data))


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.post("/cities/{code}/zones", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
async def create_zone(code: str, data: ZoneCreate, admin: Editor, db: DB) -> ZoneOut:
    admin.require("markets.edit", code)
    return await _run(MarketService(db).create_zone(code, data))


async def _zone_scope(db: AsyncSession, zone_id: uuid.UUID) -> str:
    return await _run(MarketService(db).zone_city_code(zone_id))


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
async def update_zone(zone_id: uuid.UUID, data: ZoneUpdate, admin: Editor, db: DB) -> ZoneOut:
    admin.require("markets.edit", await _zone_scope(db, zone_id))
    return await _run(MarketService(db).update_zone(zone_id, data))


@router.post("/zones/{zone_id}/pause", response_model=ZoneOut)
async def pause_zone(zone_id: uuid.UUID, data: ZonePause, admin: Pauser, db: DB) -> ZoneOut:
    """Close a zone for a while (rain, event, too few riders), with a reason."""
    admin.require("zones.pause", await _zone_scope(db, zone_id))
    return await _run(MarketService(db).pause_zone(zone_id, data))


@router.post("/zones/{zone_id}/resume", response_model=ZoneOut)
async def resume_zone(zone_id: uuid.UUID, admin: Pauser, db: DB) -> ZoneOut:
    admin.require("zones.pause", await _zone_scope(db, zone_id))
    return await _run(MarketService(db).resume_zone(zone_id))
