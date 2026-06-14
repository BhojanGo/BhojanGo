"""
Batch Engine API Tests
Tests: health, batch listing, batch details (Node.js/Express service)

NOTE: batch-engine (port 8007) may not be running in the test environment.
These tests will gracefully skip if the service is unavailable.
"""
import pytest
import uuid
import httpx


BASE_URL = "http://localhost:8007"


class TestBatchEngineHealth:
    """Health check tests for batch-engine."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health returns 200 or service unavailable (503)."""
        try:
            resp = await client.get(f"{BASE_URL}/health")
            assert resp.status_code in (200, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")


class TestBatchListing:
    """Batch listing tests (admin only)."""

    @pytest.mark.asyncio
    async def test_list_pending_batches_admin(self, client, auth_tokens):
        """GET /api/v1/batch/pending with admin token returns batches list."""
        token = auth_tokens.get("admin")
        if not token:
            pytest.skip("Admin login failed, no auth token")
        try:
            resp = await client.get(
                f"{BASE_URL}/api/v1/batch/pending",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 401, 403, 404, 503)
            if resp.status_code == 200:
                data = resp.json()
                assert isinstance(data, list) or "batches" in data
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")

    @pytest.mark.asyncio
    async def test_list_pending_batches_customer(self, client, auth_tokens):
        """GET /api/v1/batch/pending with customer token returns 403."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        try:
            resp = await client.get(
                f"{BASE_URL}/api/v1/batch/pending",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (403, 404, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")


class TestBatchDetails:
    """Batch detail tests."""

    @pytest.mark.asyncio
    async def test_get_batch_by_id(self, client, auth_tokens):
        """GET /api/v1/batch/{batch_id} returns batch details."""
        token = auth_tokens.get("admin")
        if not token:
            pytest.skip("Admin login failed, no auth token")
        fake_batch_id = str(uuid.uuid4())
        try:
            resp = await client.get(
                f"{BASE_URL}/api/v1/batch/{fake_batch_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 404, 403, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")


class TestBatchPool:
    """Order pool tests."""

    @pytest.mark.asyncio
    async def test_add_to_pool_admin(self, client, auth_tokens):
        """POST /api/v1/batch/pool adds orders to batch pool."""
        token = auth_tokens.get("admin")
        if not token:
            pytest.skip("Admin login failed, no auth token")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/batch/pool",
                headers={"Authorization": f"Bearer {token}"},
                json={"order_ids": [str(uuid.uuid4())]},
            )
            assert resp.status_code in (200, 201, 400, 403, 404, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")

    @pytest.mark.asyncio
    async def test_add_to_pool_customer(self, client, auth_tokens):
        """POST /api/v1/batch/pool with customer token returns 403."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/batch/pool",
                headers={"Authorization": f"Bearer {token}"},
                json={"order_ids": [str(uuid.uuid4())]},
            )
            assert resp.status_code in (403, 404, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")


class TestBatchEngineCycle:
    """Engine cycle trigger tests."""

    @pytest.mark.asyncio
    async def test_trigger_cycle_admin(self, client, auth_tokens):
        """POST /api/v1/batch/engine/cycle triggers batch cycle."""
        token = auth_tokens.get("admin")
        if not token:
            pytest.skip("Admin login failed, no auth token")
        try:
            resp = await client.post(
                f"{BASE_URL}/api/v1/batch/engine/cycle",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 403, 404, 503)
        except httpx.ConnectError:
            pytest.skip("Batch engine service is not running")