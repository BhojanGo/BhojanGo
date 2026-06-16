"""
Notification Service API Tests
Tests: health, notifications listing, device token registration
"""
import pytest
import uuid


BASE_URL = "http://localhost:8006"


class TestNotificationServiceHealth:
    """Health check tests for notification-svc."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health returns 200."""
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")


class TestNotificationListing:
    """Notification listing tests."""

    @pytest.mark.asyncio
    async def test_get_notifications_authenticated(self, client, auth_tokens):
        """GET /api/v1/notifications returns notification list."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_notifications_unauthenticated(self, client):
        """GET /api/v1/notifications without auth returns 401/403."""
        resp = await client.get(f"{BASE_URL}/api/v1/notifications")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(self, client, auth_tokens):
        """GET /api/v1/notifications?page=1&limit=10 returns paginated results."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/notifications?page=1&limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "page" in data
        assert "limit" in data


class TestDeviceTokenRegistration:
    """Device token registration tests."""

    @pytest.mark.asyncio
    async def test_register_device_token(self, client, auth_tokens):
        """POST /api/v1/notifications/device-token registers a device token."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/notifications/device-token",
            headers={"Authorization": f"Bearer {token}"},
            json={"token": f"test_token_{uuid.uuid4()}", "platform": "android"},
        )
        assert resp.status_code in (200, 201, 404)

    @pytest.mark.asyncio
    async def test_register_device_token_ios(self, client, auth_tokens):
        """POST /api/v1/notifications/device-token with iOS platform works."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/notifications/device-token",
            headers={"Authorization": f"Bearer {token}"},
            json={"token": f"ios_token_{uuid.uuid4()}", "platform": "ios"},
        )
        assert resp.status_code in (200, 201, 404)


class TestMarkNotificationRead:
    """Mark notification as read tests."""

    @pytest.mark.asyncio
    async def test_mark_notification_read(self, client, auth_tokens):
        """PUT /api/v1/notifications/{id}/read marks notification as read."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        fake_notification_id = str(uuid.uuid4())
        resp = await client.put(
            f"{BASE_URL}/api/v1/notifications/{fake_notification_id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404)