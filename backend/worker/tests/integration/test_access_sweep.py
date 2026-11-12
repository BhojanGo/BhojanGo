"""Access-control sweep for the worker: every endpoint without a token, and
against someone else's notification or device. Every route needs a policy."""
import os
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

PUBLIC = {("GET", "/health"), ("GET", "/health/live"), ("GET", "/health/ready"), ("GET", "/metrics")}
# All signed-in, all on the caller's own data; "other" is someone else's notification or device token.
OWN = {
    ("GET", "/api/v1/notifications"): None,
    ("POST", "/api/v1/notifications/device-token"): {"token": "ExponentPushToken[sweep-own-device-00]", "platform": "android"},
    ("DELETE", "/api/v1/notifications/device-token"): {"token": "ExponentPushToken[sweep-own-device-00]", "platform": "android"},
    ("PUT", "/api/v1/notifications/{notification_id}/read"): None,
}


def token(user_id: str) -> dict:
    from shared.auth import encode_jwt

    now = int(time.time())
    return {"Authorization": "Bearer " + encode_jwt({"sub": user_id, "type": "access", "role": "customer", "country": "IN",
                                                    "adm": [], "iat": now, "exp": now + 900})}


def routes() -> set[tuple[str, str]]:
    from fastapi.routing import APIRoute

    from app.main import app

    out = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            out |= {(m, r.path) for m in r.methods}
        elif type(r).__name__ == "_IncludedRouter":
            out |= {(m, c.path) for c in r.effective_route_contexts() for m in (c.methods or ())}
    return {(m, p) for m, p in out if m != "HEAD"}


def test_every_route_has_a_policy() -> None:
    assert routes() == PUBLIC | set(OWN)


@pytest.fixture
async def setup():  # type: ignore[no-untyped-def]
    from app.main import app
    from app.models.notification import DeviceToken, Notification
    from shared.db import AsyncSessionLocal, engine

    me, other = str(uuid.uuid4()), str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        theirs = Notification(user_id=uuid.UUID(other), type="order_placed", channel="in_app", title="t", body="b")
        db.add(theirs)
        db.add(DeviceToken(user_id=uuid.UUID(other), token="ExponentPushToken[sweep-their-device]", platform="ios",
                           provider="expo"))
        await db.commit()
        nid = str(theirs.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, me, other, nid
    async with AsyncSessionLocal() as db:
        await db.execute(Notification.__table__.delete().where(Notification.user_id.in_([uuid.UUID(me), uuid.UUID(other)])))
        await db.execute(DeviceToken.__table__.delete().where(DeviceToken.user_id.in_([uuid.UUID(me), uuid.UUID(other)])))
        await db.commit()
    await engine.dispose()


@pytest.mark.parametrize(("method", "path"), sorted(OWN))
async def test_no_token_is_refused(setup, method: str, path: str) -> None:  # type: ignore[no-untyped-def]
    client, _, _, nid = setup
    r = await client.request(method, path.format(notification_id=nid), json=OWN[(method, path)])
    assert r.status_code in {401, 403}, (method, path, r.status_code)


async def test_someone_elses_notification_and_device(setup) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models.notification import DeviceToken, Notification
    from shared.db import AsyncSessionLocal

    client, me, other, nid = setup
    assert (await client.put(f"/api/v1/notifications/{nid}/read", headers=token(me))).status_code == 404
    inbox = (await client.get("/api/v1/notifications", headers=token(me))).json()
    assert all(n["id"] != nid for n in inbox["items"])
    # Removing someone else's device token does nothing to it.
    r = await client.request("DELETE", "/api/v1/notifications/device-token", headers=token(me),
                             json={"token": "ExponentPushToken[sweep-their-device]", "platform": "ios"})
    assert r.status_code in (200, 204, 404)
    async with AsyncSessionLocal() as db:
        n = await db.get(Notification, uuid.UUID(nid))
        assert n is not None and not n.is_read
        owner = (await db.execute(select(DeviceToken.user_id).where(
            DeviceToken.token == "ExponentPushToken[sweep-their-device]"))).scalar()
        assert str(owner) == other
