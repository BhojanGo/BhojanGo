"""Riders (P14): go online, receive offers (30 s to accept), accept or pass."""
import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.api.v1.websocket import _extract_ws_token
from app.core.auth import CurrentUser, _decode_token, get_current_user
from app.core.redis import get_redis
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
    """Start taking orders here. Keep sending /delivery/driver/location while online."""
    return await dispatch.go_online(_rider(user), data.lat, data.lng)


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
    except LookupError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "OFFER_GONE", "message": str(e)})


@router.post("/api/v1/offers/{order_id}/pass")
async def pass_offer(order_id: str, user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    nxt = await dispatch.decline(_rider(user), order_id, "passed")
    return {"order_id": order_id, "passed": True, "offered_to_next": bool(nxt)}


@router.get("/api/v1/dispatch/shadow-batches")
async def shadow_batches(user: Annotated[CurrentUser, Depends(get_current_user)], limit: int = Query(50, le=500)) -> list[dict]:
    """Batches the shadow batcher would have made (nothing is batched)."""
    if not user.admin:
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
    pubsub = (await get_redis()).pubsub()
    await pubsub.subscribe(dispatch.rider_channel(user.user_id))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                await websocket.send_json(json.loads(msg["data"]))
            await asyncio.sleep(0.05)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
