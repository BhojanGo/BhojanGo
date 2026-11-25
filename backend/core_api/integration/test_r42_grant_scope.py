"""R42: an admin role is granted only at a place Markets has (the functional sweep stored viewer @ XX-NOPE)."""
import os

import pytest
from httpx import AsyncClient

from core_api.integration.test_orders_flow import client, login  # noqa: F401

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def test_a_grant_at_an_unknown_place_is_refused(client: AsyncClient) -> None:  # noqa: F811
    admin = await login(client, "admin@example.com", "BhojanGoAdmin1")
    for scope in ("XX-NOPE", "US-ZZ", "US-ID-NOWHERE", "ZZ"):
        r = await client.post("/api/v1/admin/role-assignments", headers=admin,
                              json={"email": "support.boi@example.com", "role": "viewer", "scope": scope})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "UNKNOWN_SCOPE", (scope, r.text)
    mine = (await client.get("/api/v1/admin/role-assignments", headers=admin)).json()
    assert not [a for a in mine if a["scope"] in ("XX-NOPE", "US-ZZ", "US-ID-NOWHERE", "ZZ")]
    for scope in ("US", "US-ID", "US-ID-BOI"):  # real places still work
        r = await client.post("/api/v1/admin/role-assignments", headers=admin,
                              json={"email": "support.boi@example.com", "role": "viewer", "scope": scope})
        assert r.status_code in (200, 201), (scope, r.text)
        await client.delete(f"/api/v1/admin/role-assignments/{r.json()['id']}", headers=admin)
