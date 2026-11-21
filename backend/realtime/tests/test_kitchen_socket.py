"""R27: the kitchen tablet's socket (/ws/kitchen/{id}). Only the kitchen's staff may open it;
it brings each order change as it happens, and its opening and every ping are the tablet's
heartbeat (shared/kitchen_live.py). Each test fails by timing out, never by hanging the run."""
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

from shared import kitchen_live
from shared.auth import encode_jwt

KITCHEN = str(uuid.uuid4())
OTHER_KITCHEN = str(uuid.uuid4())
OWNER, OTHER_OWNER, CUSTOMER = (str(uuid.uuid4()) for _ in range(3))
DOWN = str(uuid.uuid4())  # core_api doesn't answer for this one


def token(sub: str, role: str = "restaurant_owner", ttl: float = 900) -> str:
    now = int(time.time())
    return encode_jwt({"sub": sub, "type": "access", "role": role, "country": "US", "iat": now, "exp": int(now + ttl)})


@pytest.fixture
def state(monkeypatch):  # type: ignore[no-untyped-def]
    from app.api.v1 import websocket
    from app.core import hub as H
    from app.core import sockets
    from app.services import core_api as C
    from app.services.core_api import CoreApiError

    server = fakeredis.FakeServer()
    clients: dict[int, fakeredis.aioredis.FakeRedis] = {}

    async def get_redis():  # type: ignore[no-untyped-def]
        import asyncio

        loop = id(asyncio.get_running_loop())
        if loop not in clients:
            clients[loop] = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        return clients[loop]

    staff = {(KITCHEN, OWNER), (OTHER_KITCHEN, OTHER_OWNER)}
    asked: list[tuple[str, str]] = []

    class FakeCore:
        async def kitchen_staff(self, restaurant_id: str, user_id: str) -> bool:
            asked.append((restaurant_id, user_id))
            if restaurant_id == DOWN:
                raise CoreApiError(503, "core_api down")
            return (restaurant_id, user_id) in staff

    monkeypatch.setattr(C, "core_api", FakeCore())
    monkeypatch.setattr(H, "get_redis", get_redis)
    monkeypatch.setattr(websocket, "get_redis", get_redis)
    monkeypatch.setattr(kitchen_live, "redis_client", get_redis)  # heartbeats: core_api's database
    monkeypatch.setattr(websocket, "hub", H.Hub())
    monkeypatch.setattr(sockets, "limits", sockets.Limits())
    app = FastAPI()
    app.include_router(websocket.router)
    with TestClient(app) as client:
        yield {"client": client, "server": server, "asked": asked}


def receive(ws, timeout: float = 6.0):  # type: ignore[no-untyped-def]
    """The socket's next message (JSON, or the text itself), or {"closed": code}."""
    out: queue.Queue = queue.Queue()

    def read() -> None:
        try:
            text = ws.receive_text()
            try:
                out.put(json.loads(text))
            except ValueError:
                out.put(text)
        except WebSocketDisconnect as e:
            out.put({"closed": e.code})
        except Exception as e:  # noqa: BLE001
            out.put({"error": repr(e)})

    threading.Thread(target=read, daemon=True).start()
    try:
        return out.get(timeout=timeout)
    except queue.Empty:
        pytest.fail(f"nothing on the socket after {timeout} s")


def heartbeat(server) -> dict | None:  # type: ignore[no-untyped-def]
    raw = fakeredis.FakeRedis(server=server, decode_responses=True).get(kitchen_live.tablet_key(KITCHEN))
    return json.loads(raw) if raw else None


def test_the_kitchens_staff_opens_it_and_each_ping_is_a_heartbeat(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/kitchen/{KITCHEN}",
                                           headers={"Authorization": f"Bearer {token(OWNER)}"}) as ws:
        assert receive(ws)["type"] == "connected"
        first = heartbeat(state["server"])
        assert first and first["via"] == "socket", "opening the socket is a heartbeat"
        time.sleep(0.05)
        ws.send_text("ping")
        assert receive(ws) == "pong"
        assert heartbeat(state["server"])["at"] > first["at"], "each ping renews the heartbeat"


@pytest.mark.parametrize("who", ["other_owner", "customer"])
def test_anyone_but_the_kitchens_staff_is_refused(state, who: str) -> None:  # type: ignore[no-untyped-def]
    sub, role = {"other_owner": (OTHER_OWNER, "restaurant_owner"), "customer": (CUSTOMER, "customer")}[who]
    with pytest.raises(WebSocketDisconnect) as refused:
        with state["client"].websocket_connect(f"/ws/kitchen/{KITCHEN}",
                                               headers={"Authorization": f"Bearer {token(sub, role)}"}) as ws:
            receive(ws)
    assert refused.value.code == 4004
    assert heartbeat(state["server"]) is None, "a refused socket is no heartbeat"


def test_no_token_or_a_bad_one_is_refused(state) -> None:  # type: ignore[no-untyped-def]
    for url in (f"/ws/kitchen/{KITCHEN}", f"/ws/kitchen/{KITCHEN}?token=not-a-jwt"):
        with pytest.raises(WebSocketDisconnect) as refused:
            with state["client"].websocket_connect(url) as ws:
                receive(ws)
        assert refused.value.code == 4001
    assert state["asked"] == [], "no staff lookup without a valid token"


def test_core_api_unreachable_says_try_again_rather_than_opening(state) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(WebSocketDisconnect) as refused:
        with state["client"].websocket_connect(f"/ws/kitchen/{DOWN}", headers={"Authorization": f"Bearer {token(OWNER)}"}) as ws:
            receive(ws)
    assert refused.value.code == 1013, "not 4004: the tablet must reconnect"


def test_an_order_change_reaches_the_kitchens_socket(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/kitchen/{KITCHEN}",
                                           headers={"Authorization": f"Bearer {token(OWNER)}"}) as ws:
        assert receive(ws)["type"] == "connected"
        publisher = fakeredis.FakeRedis(server=state["server"])
        message = json.dumps({"type": "order_changed", "payload": {"order_id": "o1", "status": "placed", "event": "order.placed"}})
        stop = threading.Event()

        def publish() -> None:  # until the socket's subscription is up
            while not stop.is_set():
                publisher.publish(f"kitchen:{KITCHEN}", message)
                time.sleep(0.2)

        threading.Thread(target=publish, daemon=True).start()
        try:
            got = receive(ws)
        finally:
            stop.set()
        assert got["type"] == "order_changed" and got["payload"]["status"] == "placed"


def test_the_socket_closes_when_its_token_expires(state) -> None:  # type: ignore[no-untyped-def]
    with state["client"].websocket_connect(f"/ws/kitchen/{KITCHEN}?token={token(OWNER, ttl=2)}") as ws:
        assert receive(ws)["type"] == "connected"
        assert receive(ws) == {"closed": 4401}


async def test_order_events_are_published_to_the_kitchen_channel(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.services import dispatch

    r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def get_redis():  # type: ignore[no-untyped-def]
        return r

    monkeypatch.setattr(dispatch, "get_redis", get_redis)

    async def nothing(*a, **k):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(dispatch, "_republish_eta", nothing)
    monkeypatch.setattr(dispatch, "_finish", nothing)
    sub = r.pubsub()
    await sub.subscribe(f"kitchen:{KITCHEN}")
    await sub.get_message(timeout=1)  # the subscribe confirmation
    for kind, st in (("order.placed", "placed"), ("order.status_changed", "accepted"), ("order.cancelled", "cancelled")):
        await dispatch.on_order_event({"event_type": kind, "payload": {
            "order_id": "o1", "restaurant_id": KITCHEN, "status": st, "new_status": st}})
        msg = await sub.get_message(ignore_subscribe_messages=True, timeout=1)
        assert msg is not None, kind
        body = json.loads(msg["data"])
        assert body["type"] == "order_changed" and body["payload"]["status"] == st and body["payload"]["event"] == kind
    await sub.aclose()
