"""WebSocket endpoint for real-time order tracking."""
import asyncio
import json
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.auth import _decode_token
from app.core.redis import get_redis, order_tracking_channel

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

    await manager.connect(websocket, order_id)

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "payload": {"order_id": order_id, "user_id": current_user.user_id},
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Subscribe to Redis pub/sub channel for this order
    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = order_tracking_channel(order_id)
    await pubsub.subscribe(channel)

    try:
        # Listen for messages from Redis pub/sub
        async def redis_listener() -> None:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await manager.broadcast_to_order(order_id, data)
                    except Exception as e:
                        logger.error("ws_broadcast_error", error=str(e))

        async def ws_keepalive() -> None:
            """Keep connection alive with periodic pings."""
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "payload": {},
                        "timestamp": datetime.now(UTC).isoformat(),
                    })
                except Exception:
                    break

        # Run both tasks concurrently
        listener_task = asyncio.create_task(redis_listener())
        keepalive_task = asyncio.create_task(ws_keepalive())

        # Wait for WebSocket to disconnect
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        finally:
            listener_task.cancel()
            keepalive_task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("ws_error", order_id=order_id, error=str(e))
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        manager.disconnect(websocket, order_id)
