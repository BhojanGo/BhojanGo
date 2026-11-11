"""Endpoints that used to 500 on a migrated database must return 200.

These run against a real Postgres built by `alembic upgrade head` and loaded
with tools/seed, plus a real Redis. They are skipped unless
RUN_MIGRATED_DB_TESTS=1 (CI's migrations job sets it after seeding):

    cd backend
    uv run alembic upgrade head
    uv run python ../tools/seed/seed.py
    RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration -v
"""
import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    # Each test gets its own event loop; drop pooled connections bound to this one
    # (core_api's lifespan does the same on shutdown).
    await close_redis()
    await engine.dispose()


@pytest.fixture
async def customer_token(client: AsyncClient) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": "customer1.hyd@example.com", "password": "BhojanGo123"}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_restaurant_list_detail_and_menu(client: AsyncClient) -> None:
    r = await client.get("/api/v1/restaurants")
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, "seeded restaurants should be listed"
    names = {i["name"] for i in items}
    assert {"Spice Route Kitchen", "Boise Bowl Co."} <= names, names

    restaurant_id = items[0]["id"]
    r = await client.get(f"/api/v1/restaurants/{restaurant_id}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == restaurant_id

    r = await client.get(f"/api/v1/restaurants/{restaurant_id}/menu")
    assert r.status_code == 200, r.text
    menu = r.json()
    assert menu["categories"] or menu["uncategorized_items"], "seeded restaurants have menu items"


async def test_me_addresses(client: AsyncClient, customer_token: str) -> None:
    headers = {"Authorization": f"Bearer {customer_token}"}

    r = await client.get("/api/v1/me/addresses", headers=headers)
    assert r.status_code == 200, r.text

    r = await client.post(
        "/api/v1/me/addresses",
        headers=headers,
        json={"label": "Home", "street": "123 MG Road", "city": "Bengaluru", "country": "IN"},
    )
    assert r.status_code == 201, r.text

    r = await client.get("/api/v1/me/addresses", headers=headers)
    assert r.status_code == 200, r.text
    assert any(a["street"] == "123 MG Road" for a in r.json())
