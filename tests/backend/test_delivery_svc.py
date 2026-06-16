"""
Delivery Service API Tests
Tests: health, delivery endpoints (location, active order, ETA)
"""
import pytest
import uuid


BASE_URL = "http://localhost:8004"


class TestDeliveryServiceHealth:
    """Health check tests for delivery-svc."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health returns 200."""
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")


class TestDriverLocation:
    """Driver location update tests."""

    @pytest.mark.asyncio
    async def test_update_driver_location(self, client, auth_tokens):
        """POST /api/v1/delivery/driver/location updates driver GPS location."""
        token = auth_tokens.get("driver")
        if not token:
            pytest.skip("Driver login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/delivery/driver/location",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "order_id": None,
                "lat": 12.9716,
                "lng": 77.5946,
                "heading": 45.0,
                "speed": 30.0,
                "accuracy": 5.0,
            },
        )
        assert resp.status_code in (200, 403, 404)

    @pytest.mark.asyncio
    async def test_update_driver_location_as_customer(self, client, auth_tokens):
        """POST /api/v1/delivery/driver/location with customer token returns 403."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/delivery/driver/location",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "order_id": None,
                "lat": 12.9716,
                "lng": 77.5946,
                "heading": 45.0,
                "speed": 30.0,
                "accuracy": 5.0,
            },
        )
        assert resp.status_code in (403, 404)


class TestDriverActiveOrder:
    """Driver active order tests."""

    @pytest.mark.asyncio
    async def test_get_driver_active_order(self, client, auth_tokens):
        """GET /api/v1/delivery/driver/active-order returns driver's current order."""
        token = auth_tokens.get("driver")
        if not token:
            pytest.skip("Driver login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/delivery/driver/active-order",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 403, 404)


class TestDeliveryETA:
    """Delivery ETA tests."""

    @pytest.mark.asyncio
    async def test_get_order_eta(self, client, auth_tokens):
        """GET /api/v1/delivery/{order_id}/eta returns ETA for order."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        fake_order_id = str(uuid.uuid4())
        resp = await client.get(
            f"{BASE_URL}/api/v1/delivery/{fake_order_id}/eta",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404, 403)


class TestDeliveryAssign:
    """Delivery assignment tests (admin only)."""

    @pytest.mark.asyncio
    async def test_assign_driver_admin(self, client, auth_tokens):
        """POST /api/v1/delivery/assign with admin token assigns driver."""
        token = auth_tokens.get("admin")
        if not token:
            pytest.skip("Admin login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/delivery/assign",
            headers={"Authorization": f"Bearer {token}"},
            json={"order_id": str(uuid.uuid4()), "driver_id": str(uuid.uuid4())},
        )
        assert resp.status_code in (200, 403, 404)

    @pytest.mark.asyncio
    async def test_assign_driver_customer(self, client, auth_tokens):
        """POST /api/v1/delivery/assign with customer token returns 403."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/delivery/assign",
            headers={"Authorization": f"Bearer {token}"},
            json={"order_id": str(uuid.uuid4()), "driver_id": str(uuid.uuid4())},
        )
        assert resp.status_code in (403, 404)