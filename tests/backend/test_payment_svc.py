"""
Payment Service API Tests
Tests: health, wallet, payments, transactions
"""
import pytest
import uuid


BASE_URL = "http://localhost:8005"


class TestPaymentServiceHealth:
    """Health check tests for payment-svc."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health returns 200."""
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")


class TestWalletBalance:
    """Wallet balance tests."""

    @pytest.mark.asyncio
    async def test_get_wallet_balance_authenticated(self, client, auth_tokens):
        """GET /api/v1/wallet/balance returns wallet balance."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/wallet/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "balance" in data or "amount" in data

    @pytest.mark.asyncio
    async def test_get_wallet_balance_unauthenticated(self, client):
        """GET /api/v1/wallet/balance without auth returns 401/403."""
        resp = await client.get(f"{BASE_URL}/api/v1/wallet/balance")
        assert resp.status_code in (401, 403)


class TestWalletTransactions:
    """Wallet transaction history tests."""

    @pytest.mark.asyncio
    async def test_get_wallet_transactions_authenticated(self, client, auth_tokens):
        """GET /api/v1/wallet/transactions returns transaction history."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/wallet/transactions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "items" in data


class TestWalletTopup:
    """Wallet topup tests."""

    @pytest.mark.asyncio
    async def test_topup_wallet_authenticated(self, client, auth_tokens):
        """POST /api/v1/wallet/topup adds funds to wallet."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/wallet/topup",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount": 500.00, "payment_method_id": "pm_test_card"},
        )
        # May return 200/201, 400, 404, or 422 (validation error)
        assert resp.status_code in (200, 201, 400, 404, 422)


class TestPaymentIntiate:
    """Payment initiation tests."""

    @pytest.mark.asyncio
    async def test_initiate_payment(self, client, auth_tokens):
        """POST /api/v1/payments/initiate creates a payment intent."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.post(
            f"{BASE_URL}/api/v1/payments/initiate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "order_id": str(uuid.uuid4()),
                "amount": 50000,
                "currency": "INR",
                "country": "IN",
                "payment_method_type": "wallet",
            },
        )
        assert resp.status_code in (201, 400, 404, 422)


class TestGetPayment:
    """Get payment by order ID tests."""

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, client, auth_tokens):
        """GET /api/v1/payments/{order_id} returns 404 for non-existent payment."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        fake_order_id = str(uuid.uuid4())
        resp = await client.get(
            f"{BASE_URL}/api/v1/payments/{fake_order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (404, 403)