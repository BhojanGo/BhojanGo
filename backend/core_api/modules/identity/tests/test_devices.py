"""R19: the apps' push tokens on core_api (POST/DELETE /api/v1/me/devices), on SQLite.
Writes the worker's device_tokens table, the one its dispatcher pushes order updates to."""
import uuid

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from core_api.modules.identity.api.v1.devices import device_tokens
from core_api.modules.identity.tests.conftest import test_engine
from core_api.modules.identity.tests.test_p5_auth import bearer, login, make_user
from shared.db import Base

EXPO = "ExponentPushToken[r19-test-device-0001]"


@pytest_asyncio.fixture(autouse=True)
async def devices_table():  # type: ignore[no-untyped-def]
    t = device_tokens()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[t])
    yield t
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all, tables=[t])


async def person(client: AsyncClient, db_session) -> tuple[dict, uuid.UUID]:  # type: ignore[no-untyped-def]
    email = f"dev-{uuid.uuid4().hex[:8]}@example.com"
    user = await make_user(db_session, email)
    return bearer(await login(client, email)), user.id


async def rows(db_session, t):  # type: ignore[no-untyped-def]
    return (await db_session.execute(select(t.c.token, t.c.user_id, t.c.platform, t.c.provider))).all()


async def test_register_names_the_expo_service_and_moves_to_the_last_sign_in(client, db_session, devices_table) -> None:
    alice, alice_id = await person(client, db_session)
    bob, bob_id = await person(client, db_session)

    r = await client.post("/api/v1/me/devices", headers=alice, json={"token": EXPO, "platform": "android"})
    assert r.status_code == 201, r.text
    assert r.json() == {"platform": "android", "provider": "expo"}  # worked out from the token
    assert await rows(db_session, devices_table) == [(EXPO, alice_id, "android", "expo")]

    # Again (every start): still one row.
    assert (await client.post("/api/v1/me/devices", headers=alice,
                              json={"token": EXPO, "platform": "android", "provider": "expo"})).status_code == 201
    assert len(await rows(db_session, devices_table)) == 1

    # Bob signs in on the same phone: the token is his now, never pushed to both.
    assert (await client.post("/api/v1/me/devices", headers=bob, json={"token": EXPO, "platform": "ios"})).status_code == 201
    assert await rows(db_session, devices_table) == [(EXPO, bob_id, "ios", "expo")]


async def test_remove_only_takes_the_persons_own_token(client, db_session, devices_table) -> None:
    alice, _ = await person(client, db_session)
    bob, bob_id = await person(client, db_session)
    await client.post("/api/v1/me/devices", headers=bob, json={"token": EXPO, "platform": "android"})

    # Someone else's token: nothing happens (and nothing says whose it is).
    assert (await client.delete("/api/v1/me/devices", headers=alice, params={"token": EXPO})).status_code == 204
    assert await rows(db_session, devices_table) == [(EXPO, bob_id, "android", "expo")]

    assert (await client.delete("/api/v1/me/devices", headers=bob, params={"token": EXPO})).status_code == 204
    assert await rows(db_session, devices_table) == []
    # Unknown (already removed): fine.
    assert (await client.delete("/api/v1/me/devices", headers=bob, params={"token": EXPO})).status_code == 204


async def test_signed_in_only_and_valid_bodies(client, db_session) -> None:
    assert (await client.post("/api/v1/me/devices", json={"token": EXPO, "platform": "android"})).status_code in (401, 403)
    assert (await client.delete("/api/v1/me/devices", params={"token": EXPO})).status_code in (401, 403)
    h, _ = await person(client, db_session)
    assert (await client.post("/api/v1/me/devices", headers=h, json={"token": EXPO, "platform": "pager"})).status_code == 422
    assert (await client.post("/api/v1/me/devices", headers=h,
                              json={"token": EXPO, "platform": "ios", "provider": "pigeon"})).status_code == 422
    assert (await client.post("/api/v1/me/devices", headers=h, json={"token": "short", "platform": "ios"})).status_code == 422
