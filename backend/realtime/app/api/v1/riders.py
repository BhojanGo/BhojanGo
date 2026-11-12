"""Riders (P14): go online, receive offers (30 s to accept), accept or pass."""
import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.api.v1.websocket import _extract_ws_token
from app.core.auth import CurrentUser, _decode_token, get_current_user
from app.core.hub import hub
from app.services import dispatch

router = APIRouter(tags=["Dispatch"])


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


def _rider(user: CurrentUser) -> str:
    if user.role != "driver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Riders only")
    return user.user_id


@router.post("/api/v1/riders/me/online")
async def online(data: Point, user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    """Start taking orders here. Keep sending /delivery/driver/location while online.
    Only riders who have finished onboarding (core_api /riders/me/onboarding)."""
    rider = _rider(user)
    try:
        ready = (await dispatch.core_api.rider_ready(rider)).get("ready")
    except dispatch.CoreApiError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Can't check your account right now") from e
    if not ready:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "ONBOARDING_INCOMPLETE", "message": "Finish your checklist before you go online"})
    return await dispatch.go_online(rider, data.lat, data.lng)


@router.post("/api/v1/riders/me/offline")
async def offline(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    try:
        return await dispatch.go_offline(_rider(user))
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/api/v1/riders/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    rider = _rider(user)
    return {"state": await dispatch.rider_state(rider), "offer": await dispatch.current_offer(rider),
            "location": await dispatch.last_fix(rider)}


@router.post("/api/v1/offers/{order_id}/accept")
async def accept(order_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    try:
        return await dispatch.accept(_rider(user), order_id)
    except dispatch.NotYourOffer as e:  # never yours, or no longer open: nothing to accept
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "OFFER_GONE", "message": str(e)})
    except LookupError as e:  # timed out at the same moment, or the order went elsewhere
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "OFFER_GONE", "message": str(e)})


@router.post("/api/v1/offers/{order_id}/pass")
async def pass_offer(order_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    offer = await dispatch.current_offer(_rider(user))
    if not offer or offer["order_id"] != order_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "OFFER_GONE", "message": "No open offer of this order for you"})
    nxt = await dispatch.decline(user.user_id, order_id, "passed")
    return {"order_id": order_id, "passed": True, "offered_to_next": bool(nxt)}


class SosIn(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    note: str | None = Field(default=None, max_length=500)


@router.post("/api/v1/riders/me/sos", status_code=status.HTTP_201_CREATED)
async def sos(data: SosIn, user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    """The rider needs help: the safety team sees it at once (admin dispatch view)
    with where they are and the order they're on. Call emergency services first."""
    rider = _rider(user)
    return await dispatch.raise_sos(rider, user.country, data.lat, data.lng, data.note)


@router.get("/api/v1/dispatch/sos")
async def open_sos(user: Annotated[CurrentUser, Depends(get_current_user)]) -> list[dict]:
    """Open SOS alerts in the cities the admin dispatches for."""
    from shared import authz

    mine = [authz.Assignment.parse(a) for a in user.admin]
    if not authz.scopes_with(mine, "dispatch.edit"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    return [a for a in await dispatch.open_sos() if authz.can(mine, "dispatch.edit", a.get("market_city") or a["country"])]


@router.get("/api/v1/dispatch/riders")
async def dispatch_riders(user: Annotated[CurrentUser, Depends(get_current_user)],
                          city: str = Query(pattern=r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$")) -> dict:
    """Online riders in a city for the admin dispatch map: admins who can see
    orders or dispatch there."""
    from shared import authz

    mine = [authz.Assignment.parse(a) for a in user.admin]
    if not (authz.can(mine, "dispatch.edit", city) or authz.can(mine, "orders.view", city)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins for this city only")
    try:
        centre = await dispatch.core_api.city_centre(city)
    except dispatch.CoreApiError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Can't look up the city right now") from e
    if centre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="City not found")
    riders = await dispatch.riders_near(*centre)
    sos = [a for a in await dispatch.open_sos() if a.get("market_city") == city or (a.get("market_city") is None and a.get("lat") is not None
           and dispatch.haversine_km((a["lat"], a["lng"]), centre) <= 30)]
    return {"city": city, "centre": list(centre), "riders": riders, "sos": sos}


@router.get("/api/v1/dispatch/shadow-batches")
async def shadow_batches(user: Annotated[CurrentUser, Depends(get_current_user)], limit: int = Query(50, le=500)) -> list[dict]:
    """Batches the shadow batcher would have made (nothing is batched): dispatch admins."""
    from shared import authz

    if not authz.scopes_with([authz.Assignment.parse(a) for a in user.admin], "dispatch.edit"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admins only")
    return await dispatch.shadow_suggestions(limit)


@router.websocket("/ws/rider")
async def rider_socket(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Offers and withdrawals for the signed-in rider, as they happen."""
    raw = _extract_ws_token(websocket, token)
    try:
        user = _decode_token(raw) if raw else None
    except Exception:  # noqa: BLE001
        user = None
    if user is None or user.role != "driver":
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()
    offer = await dispatch.current_offer(user.user_id)
    if offer:
        await websocket.send_json({"type": "offer", "payload": offer})
    # Offers through the process's shared subscription (app/core/hub.py), not a connection per rider.
    async with hub.subscribe(dispatch.rider_channel(user.user_id)) as q:
        async def forward() -> None:
            while True:
                await websocket.send_json(json.loads(await q.get()))

        task = asyncio.create_task(forward())
        try:
            while True:
                await websocket.receive_text()  # pings from the app; a disconnect ends it
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            task.cancel()
