"""WebSocket endpoint for real-time order tracking."""
import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.auth import _decode_token
from app.core.hub import hub
from app.core.redis import get_redis, order_tracking_channel
from app.services.core_api import CoreApiError

router = APIRouter(tags=["WebSocket"])
logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections per order."""

    def __init__(self) -> None:
        # order_id -> list of WebSocket connections
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, order_id: str) -> None:
        await websocket.accept()
        if order_id not in self.active_connections:
            self.active_connections[order_id] = []
        self.active_connections[order_id].append(websocket)
        logger.info("ws_connected", order_id=order_id, total=len(self.active_connections[order_id]))

    def disconnect(self, websocket: WebSocket, order_id: str) -> None:
        if order_id in self.active_connections:
            try:
                self.active_connections[order_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[order_id]:
                del self.active_connections[order_id]
        logger.info("ws_disconnected", order_id=order_id)

    async def broadcast_to_order(self, order_id: str, message: dict) -> None:
        connections = self.active_connections.get(order_id, [])
        dead_connections = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        for ws in dead_connections:
            self.disconnect(ws, order_id)


manager = ConnectionManager()


def _extract_ws_token(websocket: WebSocket, query_token: str | None) -> str | None:
    """Resolve the JWT, preferring transport that does not leak it into URLs/logs.

    Order of preference:
      1. ``Authorization: Bearer <jwt>`` header (native/mobile clients)
      2. ``Sec-WebSocket-Protocol`` subprotocol (browser-settable, unlike headers)
      3. ``?token=`` query param (legacy fallback — discouraged, logged by proxies)
    """
    header = websocket.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    subprotocol = websocket.headers.get("sec-websocket-protocol")
    if subprotocol:
        # May be a comma-separated list; the token is the last/identifying value.
        return subprotocol.split(",")[-1].strip()
    return query_token


@router.websocket("/ws/track/{order_id}")
async def track_order(
    websocket: WebSocket,
    order_id: str,
    token: str | None = Query(default=None, description="JWT access token (legacy; prefer Authorization header)"),
) -> None:
    """
    WebSocket endpoint for real-time order tracking.

    Client connects to: ws://host/ws/track/{order_id}
    Token is supplied via the Authorization header or Sec-WebSocket-Protocol;
    ?token=<jwt> remains supported as a fallback.

    Messages received by client:
    - {"type": "location_update", "payload": {...}, "timestamp": "..."}
    - {"type": "status_change", "payload": {"status": "..."}, "timestamp": "..."}
    - {"type": "eta_update", "payload": {...}, "timestamp": "..."}
    - {"type": "error", "payload": {"message": "..."}, "timestamp": "..."}
    """
    # Authenticate (never log the token itself)
    auth_token = _extract_ws_token(websocket, token)
    if not auth_token:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        current_user = _decode_token(auth_token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Only the customer, the assigned rider and admins for the city may watch (P14).
    from app.api.v1.delivery import can_see
    from app.services import dispatch

    try:
        uuid.UUID(order_id)
        info = await dispatch.order_info(order_id, max_age=15)  # fresh enough for who may watch
    except (ValueError, CoreApiError):
        info = None
    if info is None or not can_see(current_user, info):
        await websocket.close(code=4004, reason="Order not found")
        return

    await manager.connect(websocket, order_id)

    # Send the current picture first: status, rider position, ETA, the trail so far.
    fix = await dispatch.last_fix(info["driver_id"]) if info.get("driver_id") else None
    trail = [json.loads(x) for x in await (await get_redis()).lrange(f"trail:{order_id}", 0, 199)]
    await websocket.send_json({
        "type": "connected",
        "payload": {"order_id": order_id, "user_id": current_user.user_id, "status": info.get("status"),
                    "driver_id": info.get("driver_id"), "location": fix,
                    "eta": dispatch.eta_for(info, (fix["lat"], fix["lng"])) if fix else None,
                    "pickup": info.get("pickup"), "dropoff": info.get("dropoff"), "trail": list(reversed(trail))},
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Updates for this order through the process's shared subscription (app/core/hub.py):
    # this socket gets its own queue and sends only to itself.
    async def forward(q: "asyncio.Queue[str]") -> None:
        while True:
            await websocket.send_text(await q.get())

    async def keepalive() -> None:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping", "payload": {}, "timestamp": datetime.now(UTC).isoformat()})

    try:
        async with hub.subscribe(order_tracking_channel(order_id)) as q:
            tasks = [asyncio.create_task(forward(q)), asyncio.create_task(keepalive())]
            try:
                while True:
                    if await websocket.receive_text() == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                pass
            finally:
                for t in tasks:
                    t.cancel()
    except Exception as e:  # noqa: BLE001
        logger.error("ws_error", order_id=order_id, error=str(e))
    finally:
        manager.disconnect(websocket, order_id)
