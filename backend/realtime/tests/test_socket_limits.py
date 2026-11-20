"""R22 security review, S10 (docs/launch/security-review.md): a WebSocket lives only
as long as its token, a rider taken off an order stops seeing it, and one account or
address can't hold more than its share of sockets. Each test fails without the fix
(a socket that stays open fails by timing out, never by hanging the run).

Also S8: the website's socket ticket opens a WebSocket but no HTTP route.
"""
import json
import queue
import threading
import time
import uuid

import fakeredis
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from shared.auth import encode_jwt
from shared.config import get_settings

ORDER = str(uuid.uuid4())
CUSTOMER, RIDER, OTHER_RIDER = (str(uuid.uuid4()) for _ in range(3))


def token(sub: str, role: str = "customer", ttl: float = 900, kind: str = "access") -> str:
    now = int(time.time())
    return encode_jwt({"sub": sub, "type": kind, "role": role, "country": "IN", "iat": now, "exp": int(now + ttl)})


@pytest.fixture
def state(monkeypatch):  # type: ignore[no-untyped-def]
    """A realtime app with only its WebSocket routes, fake Redis and a fake order."""
    from app.api.v1 import riders, websocket
    from app.core import hub as H
    from app.services import dispatch

    try:
        from app.core import sockets
    except ImportError:  # before the fix: no caps to reset
        sockets = None

    server = fakeredis.FakeServer()
    clients: dict[int, fakeredis.aioredis.FakeRedis] = {}

    async def get_redis():  # type: ignore[no-untyped-def]
        import asyncio

        loop = id(asyncio.get_running_loop())
        if loop not in clients:
            clients[loop] = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        return clients[loop]

    order = {"order_id": ORDER, "status": "picked_up", "customer_id": CUSTOMER, "driver_id": RIDER,
             "restaurant_owner_id": None, "market_city": "IN-TG-HYD", "pickup": [17.44, 78.39], "dropoff": [17.43, 78.41]}

    async def order_info(order_id: str, refresh: bool = False, max_age: float | None = None):  # type: ignore[no-untyped-def]
        return dict(order) if order_id == ORDER else None

    async def last_fix(rider: str):  # type: ignore[no-untyped-def]
        return None

    async def current_offer(rider: str):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(H, "get_redis", get_redis)
    monkeypatch.setattr(websocket, "get_redis", get_redis)
    fresh = H.Hub()
    monkeypatch.setattr(websocket, "hub", fresh)
    monkeypatch.setattr(riders, "hub", fresh)
    monkeypatch.setattr(dispatch, "order_info", order_info)
    monkeypatch.setattr(dispatch, "last_fix", last_fix)
    monkeypatch.setattr(dispatch, "current_offer", current_offer)
    limits = getattr(sockets, "Limits", None) if sockets else None
    if limits is not None:
        monkeypatch.setattr(sockets, "limits", limits())
    app = FastAPI()
    app.include_router(websocket.router)
    app.include_router(riders.router)
    with TestClient(app) as client:
        yield {"client": client, "order": order, "server": server}


def receive(ws, timeout: float = 6.0) -> dict:  # type: ignore[no-untyped-def]
    """The socket's next message, or {"closed": code} when it was closed; fails after ``timeout``
    (a daemon thread does the blocking read, so a socket that never closes can't hang the run)."""
    out: queue.Queue = queue.Queue()

    def read() -> None:
        try:
            out.put(ws.receive_json())
        except WebSocketDisconnect as e:
            out.put({"closed": e.code})
        except Exception as e:  # noqa: BLE001
            out.put({"error": repr(e)})

    threading.Thread(target=read, daemon=True).start()
    try:
        return out.get(timeout=timeout)
    except queue.Empty:
        pytest.fail(f"the socket was still open after {timeout} s")


def test_a_tracking_socket_closes_when_its_token_expires(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/track/{ORDER}?token={token(CUSTOMER, ttl=2)}") as ws:
        assert receive(ws)["type"] == "connected"
        assert receive(ws) == {"closed": 4401}


def test_a_rider_socket_closes_when_its_token_expires(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect("/ws/rider", headers={"Authorization": f"Bearer {token(RIDER, 'driver', ttl=2)}"}) as ws:
        assert receive(ws) == {"closed": 4401}


def test_a_rider_taken_off_the_order_stops_seeing_it(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/track/{ORDER}?token={token(RIDER, 'driver')}") as ws:
        assert receive(ws)["type"] == "connected"
        state["order"]["driver_id"] = OTHER_RIDER  # reassigned
        publisher = fakeredis.FakeRedis(server=state["server"])
        message = json.dumps({"type": "rider_assigned", "payload": {"order_id": ORDER, "rider_id": OTHER_RIDER}})
        stop = threading.Event()

        def publish() -> None:  # until the socket's subscription is up
            while not stop.is_set():
                publisher.publish(f"tracking:{ORDER}", message)
                time.sleep(0.2)

        threading.Thread(target=publish, daemon=True).start()
        try:
            got = receive(ws)
        finally:
            stop.set()
        assert got == {"closed": 4403}, got


def test_the_customer_keeps_watching_when_the_rider_changes(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/track/{ORDER}?token={token(CUSTOMER)}") as ws:
        assert receive(ws)["type"] == "connected"
        state["order"]["driver_id"] = OTHER_RIDER
        publisher = fakeredis.FakeRedis(server=state["server"])
        for _ in range(30):
            publisher.publish(f"tracking:{ORDER}", json.dumps({"type": "rider_assigned", "payload": {"rider_id": OTHER_RIDER}}))
            time.sleep(0.1)
        assert receive(ws)["type"] == "rider_assigned"


def test_one_account_cant_hold_more_than_its_sockets(state, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings().realtime, "WS_MAX_PER_USER", 2, raising=False)
    url = f"/ws/track/{ORDER}?token={token(CUSTOMER)}"
    with state["client"].websocket_connect(url) as a, state["client"].websocket_connect(url) as b:
        assert receive(a)["type"] == "connected" and receive(b)["type"] == "connected"
        with pytest.raises(WebSocketDisconnect) as refused:
            with state["client"].websocket_connect(url) as c:
                receive(c)
        assert refused.value.code == 4429
    with state["client"].websocket_connect(url) as again:  # closed sockets free their place
        assert receive(again)["type"] == "connected"


def test_one_address_cant_hold_more_than_its_sockets(state, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(get_settings().realtime, "WS_MAX_PER_IP", 1, raising=False)
    with state["client"].websocket_connect("/ws/rider", headers={"Authorization": f"Bearer {token(RIDER, 'driver')}"}):
        with pytest.raises(WebSocketDisconnect) as refused:
            with state["client"].websocket_connect("/ws/rider", headers={"Authorization": f"Bearer {token(OTHER_RIDER, 'driver')}"}) as c:
                receive(c)
        assert refused.value.code == 4429


def test_a_socket_ticket_opens_a_socket_but_no_http_route(state) -> None:  # type: ignore[no-untyped-def]
    ticket = token(CUSTOMER, kind="ws")
    with state["client"].websocket_connect(f"/ws/track/{ORDER}?token={ticket}") as ws:
        assert receive(ws)["type"] == "connected"
    from app.api.v1 import delivery

    app = FastAPI()
    app.include_router(delivery.router, prefix="/api/v1")
    with TestClient(app) as http:
        r = http.get(f"/api/v1/delivery/{ORDER}/eta", headers={"Authorization": f"Bearer {ticket}"})
    assert r.status_code == 401, r.text
