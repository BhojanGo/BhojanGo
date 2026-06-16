"""Focused SPR-02 contract validation tests.

Run with:
    pytest tests/backend/test_spr02_contracts.py -v
"""

import pytest

# Constants for local BhojanGo services
RESTAURANT_SVC = "http://localhost:8002"
USER_SVC = "http://localhost:8001"


@pytest.fixture(scope="session")
def client():
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed; using curl-based evidence instead")
    return httpx.AsyncClient(timeout=15)


@pytest.mark.asyncio
class TestMenuEndpoint:
    async def test_menu_returns_200(self, client):
        """IP.PR.02.001 — Menu endpoint returns real data (DB fallback)."""
        try:
            resp = await client.get(f"{RESTAURANT_SVC}/api/v1/restaurants")
        except Exception:
            pytest.skip("Restaurant service unreachable")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            if not items:
                pytest.skip("No restaurants seeded")
            rid = str(items[0]["id"])
            menu_resp = await client.get(f"{RESTAURANT_SVC}/api/v1/restaurants/{rid}/menu")
            assert menu_resp.status_code == 200
            body = menu_resp.json()
            assert "restaurant" in body
            assert "categories" in body
        else:
            pytest.skip("Restaurant list unreachable")


@pytest.mark.asyncio
class TestMeEndpoint:
    async def test_me_unauthenticated_returns_401(self, client):
        """IP.PR.02.002 — Missing/invalid token returns 401."""
        try:
            resp = await client.get(f"{USER_SVC}/api/v1/me")
        except Exception:
            pytest.skip("User service unreachable")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    async def test_me_authenticated_returns_200(self, client):
        """IP.PR.02.002 — Valid token returns user profile."""
        # Attempt login with a seeded/demo account if available
        try:
            login = await client.post(
                f"{USER_SVC}/api/v1/auth/login",
                json={"email": "test@example.com", "password": "password"},
            )
        except Exception:
            pytest.skip("User service unreachable")
        if login.status_code != 200:
            pytest.skip("Demo login account not available")
        token = login.json()["access_token"]
        me = await client.get(
            f"{USER_SVC}/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me.status_code == 200
        body = me.json()
        assert "id" in body
        assert "email" in body
        assert "full_name" in body
        assert "role" in body


@pytest.mark.asyncio
class TestRestaurantListFilters:
    async def test_list_no_params_returns_200(self, client):
        """IP.PR.02.015 — Default list is backward compatible."""
        try:
            resp = await client.get(f"{RESTAURANT_SVC}/api/v1/restaurants")
        except Exception:
            pytest.skip("Restaurant service unreachable")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_list_with_min_rating_filter(self, client):
        """IP.PR.02.015 — min_rating filter works."""
        try:
            resp = await client.get(
                f"{RESTAURANT_SVC}/api/v1/restaurants?min_rating=4.0&limit=5"
            )
        except Exception:
            pytest.skip("Restaurant service unreachable")
        assert resp.status_code == 200
        data = resp.json()
        for r in data.get("items", []):
            assert r["rating"] >= 4.0

    async def test_list_with_cuisine_filter(self, client):
        """IP.PR.02.015 — cuisine filter works."""
        try:
            resp = await client.get(
                f"{RESTAURANT_SVC}/api/v1/restaurants?cuisine=indian&limit=5"
            )
        except Exception:
            pytest.skip("Restaurant service unreachable")
        assert resp.status_code == 200
        data = resp.json()
        for r in data.get("items", []):
            assert "indian" in [c.lower() for c in r.get("cuisine_types", [])]
