"""P20: what the web's search-friendly pages read: live cities and restaurants by slug."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    await close_redis()
    await engine.dispose()


async def test_cities_and_slugs(client: AsyncClient) -> None:
    cities = {c["slug"]: c for c in (await client.get("/api/v1/markets/cities")).json()}
    assert cities["hyderabad"]["code"] == "IN-TG-HYD" and cities["hyderabad"]["currency"] == "INR"
    assert cities["boise"]["region"] == "Idaho" and cities["boise"]["restaurants"] >= 1
    r = await client.get("/api/v1/restaurants/by-slug/spice-route-kitchen-madhapur")
    assert r.status_code == 200 and r.json()["name"] == "Spice Route Kitchen"
    # A kitchen still applying has no public page.
    assert (await client.get("/api/v1/restaurants/by-slug/kesar-kitchen-kondapur")).status_code == 404
