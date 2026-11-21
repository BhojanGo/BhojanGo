"""WebSocket endpoint for real-time order tracking."""
import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core import sockets
from app.core.auth import CurrentUser, socket_user
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
    token: str | None = Query(default=None, description="JWT access token or socket ticket (prefer the Authorization header)"),
) -> None:
    """
    WebSocket endpoint for real-time order tracking.

    Client connects to: ws://host/ws/track/{order_id}
    Token (an access token, or the website's socket ticket from POST /auth/socket-ticket)
    is supplied via the Authorization header or Sec-WebSocket-Protocol;
    ?token=<jwt> remains supported as a fallback.

    Closes with 4401 when the token expires (reconnect with a fresh one), 4403 when the
    caller may no longer watch the order (e.g. its rider changed), 4429 when the caller
    already has too many sockets open (R22 S10).

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
        current_user = socket_user(auth_token)
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

    try:
        async with sockets.limits.hold(current_user.user_id, sockets.address(websocket)):
            await _track(websocket, order_id, current_user, info)
    except sockets.TooManySockets:
        await websocket.close(code=sockets.TOO_MANY, reason="Too many connections")


# Messages after which the order's rider may have changed: who may watch is checked again (R22 S10).
RECHECK = frozenset({"rider_assigned", "searching_rider", "status_change"})


async def still_allowed(order_id: str, user: CurrentUser) -> bool:
    from app.api.v1.delivery import can_see
    from app.services import dispatch

    try:
        info = await dispatch.order_info(order_id, max_age=5)
    except CoreApiError:
        return True  # core_api unreachable: keep the socket; the next change checks again
    return info is not None and can_see(user, info)


async def _track(websocket: WebSocket, order_id: str, current_user: CurrentUser, info: dict) -> None:
    from app.services import dispatch

    await manager.connect(websocket, order_id)
    try:
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
                text = await q.get()
                try:
                    kind = json.loads(text).get("type")
                except (ValueError, AttributeError):
                    kind = None
                if kind in RECHECK and not await still_allowed(order_id, current_user):
                    # e.g. a rider taken off the order stops seeing it at once (R22 S10)
                    logger.info("ws_no_longer_allowed", order_id=order_id)
                    await websocket.close(code=sockets.NOT_ALLOWED, reason="Not your order any more")
                    return
                await websocket.send_text(text)

        async def keepalive() -> None:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping", "payload": {}, "timestamp": datetime.now(UTC).isoformat()})

        async with hub.subscribe(order_tracking_channel(order_id)) as q:
            tasks = [asyncio.create_task(forward(q)), asyncio.create_task(keepalive()),
                     asyncio.create_task(sockets.close_at(websocket, current_user.exp))]
            try:
                while True:
                    if await websocket.receive_text() == "ping":
                        await websocket.send_text("pong")
            except (WebSocketDisconnect, RuntimeError):
                pass  # the client left, or a task above closed the socket
            finally:
                for t in tasks:
                    t.cancel()
    except Exception as e:  # noqa: BLE001
        logger.error("ws_error", order_id=order_id, error=str(e))
    finally:
        manager.disconnect(websocket, order_id)


# ── R27: the kitchen's socket ────────────────────────────────────────────────

KITCHEN_KEEPALIVE_SECONDS = 25
TRY_AGAIN_LATER = 1013


@router.websocket("/ws/kitchen/{restaurant_id}")
async def kitchen_socket(
    websocket: WebSocket,
    restaurant_id: str,
    token: str | None = Query(default=None, description="JWT access token (prefer the Authorization header)"),
) -> None:
    """
    The kitchen tablet's live board (R27): every change to the kitchen's orders (a new paid
    order, accepted, ready, cancelled, a rider assigned) as it happens; the tablet refreshes its
    board on each and keeps polling as a fallback. Only the kitchen's staff (its owner: the
    account BhojanGo Kitchen signs in with) may open it; anyone else is closed with 4004
    (1013 when core_api can't say: the tablet tries again).

    The tablet sends "ping" every 10 s and gets "pong"; each ping (and the opening) is the
    tablet's heartbeat (shared/kitchen_live.py): a kitchen whose tablet has sent none for 60 s
    stops taking orders until it does. Closes with 4401 when the token expires (reconnect with
    a fresh one) and 4429 when the account has too many sockets open.

    Messages: {"type": "connected" | "order_changed" | "ping", "payload": {...}, "timestamp": "..."}
    and the text "pong".
    """
    auth_token = _extract_ws_token(websocket, token)
    if not auth_token:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    try:
        current_user = socket_user(auth_token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    from app.services.core_api import core_api

    try:
        uuid.UUID(restaurant_id)
        staff = await core_api.kitchen_staff(restaurant_id, current_user.user_id)
    except ValueError:
        staff = False
    except CoreApiError:
        # core_api didn't answer: "try again later" (the tablet reconnects; 4004 would stop it for good)
        await websocket.close(code=TRY_AGAIN_LATER, reason="Try again")
        return
    if not staff:
        await websocket.close(code=4004, reason="Kitchen not found")
        return
    try:
        async with sockets.limits.hold(current_user.user_id, sockets.address(websocket)):
            await _kitchen(websocket, restaurant_id, current_user)
    except sockets.TooManySockets:
        await websocket.close(code=sockets.TOO_MANY, reason="Too many connections")


async def _kitchen(websocket: WebSocket, restaurant_id: str, current_user: CurrentUser) -> None:
    from app.core.redis import kitchen_channel
    from shared import kitchen_live

    await websocket.accept()
    redis = await get_redis()
    try:
        await kitchen_live.beat(restaurant_id, "socket", redis)
        await websocket.send_json({"type": "connected", "payload": {"restaurant_id": restaurant_id},
                                   "timestamp": datetime.now(UTC).isoformat()})

        async def forward(q: "asyncio.Queue[str]") -> None:
            while True:
                await websocket.send_text(await q.get())

        async def keepalive() -> None:
            while True:
                await asyncio.sleep(KITCHEN_KEEPALIVE_SECONDS)
                await websocket.send_json({"type": "ping", "payload": {}, "timestamp": datetime.now(UTC).isoformat()})

        async with hub.subscribe(kitchen_channel(restaurant_id)) as q:
            tasks = [asyncio.create_task(forward(q)), asyncio.create_task(keepalive()),
                     asyncio.create_task(sockets.close_at(websocket, current_user.exp))]
            try:
                while True:
                    if await websocket.receive_text() == "ping":
                        await kitchen_live.beat(restaurant_id, "socket", redis)
                        await websocket.send_text("pong")
            except (WebSocketDisconnect, RuntimeError):
                pass  # the tablet left, or a task above closed the socket
            finally:
                for t in tasks:
                    t.cancel()
    except Exception as e:  # noqa: BLE001
        logger.error("ws_kitchen_error", restaurant_id=restaurant_id, error=str(e))
