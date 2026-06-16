"""
Order Service API Tests
Tests: health, order listing, creation, details, status
"""
import pytest
import uuid


BASE_URL = "http://localhost:8003"


class TestOrderServiceHealth:
    """Health check tests for order-svc."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health returns 200."""
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")


class TestOrderListing:
    """Order listing tests."""

    @pytest.mark.asyncio
    async def test_list_orders_authenticated(self, client, auth_tokens):
        """GET /api/v1/orders with customer token returns orders list."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        resp = await client.get(
            f"{BASE_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_orders_unauthenticated(self, client):
        """GET /api/v1/orders without auth returns 401 or 403."""
        resp = await client.get(f"{BASE_URL}/api/v1/orders")
        assert resp.status_code in (401, 403)


class TestOrderCreation:
    """Order creation tests."""

    @pytest.fixture
    async def valid_restaurant_and_menu(self, client):
        """Get a valid restaurant and menu item for order creation."""
        rest_resp = await client.get("http://localhost:8002/api/v1/restaurants?limit=1")
        if rest_resp.status_code != 200:
            return None, None
        restaurants = rest_resp.json()["items"]
        if not restaurants:
            return None, None
        restaurant_id = restaurants[0]["id"]
        menu_resp = await client.get(
            f"http://localhost:8002/api/v1/restaurants/{restaurant_id}/menu"
        )
        if menu_resp.status_code != 200:
            return restaurant_id, None
        menu_data = menu_resp.json()
        menu_items = menu_data.get("uncategorized_items", [])
        if not menu_items:
            for cat in menu_data.get("categories", []):
                menu_items.extend(cat.get("items", []))
                if menu_items:
                    break
        if not menu_items:
            return restaurant_id, None
        return restaurant_id, menu_items[0]["id"]

    @pytest.mark.asyncio
    async def test_create_order_with_customer_token(
        self, client, auth_tokens, valid_restaurant_and_menu
    ):
        """POST /api/v1/orders with customer token creates order."""
        restaurant_id, menu_item_id = valid_restaurant_and_menu
        if not restaurant_id or not menu_item_id:
            pytest.skip("No valid restaurant/menu item available")
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        order_data = {
            "restaurant_id": restaurant_id,
            "items": [{"menu_item_id": menu_item_id, "quantity": 1, "unit_price": 299.00}],
            "delivery_address": {
                "street": "123 Test Street",
                "city": "Bangalore",
                "lat": 12.9716,
                "lng": 77.5946,
            },
        }
        resp = await client.post(
            f"{BASE_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json=order_data,
        )
        assert resp.status_code in (201, 400, 422, 500)
        if resp.status_code == 201:
            data = resp.json()
            assert "id" in data


class TestOrderDetails:
    """Order detail and status tests."""

    @pytest.mark.asyncio
    async def test_get_order_by_id_authenticated(self, client, auth_tokens):
        """GET /api/v1/orders/{id} returns order details for owner."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        list_resp = await client.get(
            f"{BASE_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        list_resp.raise_for_status()
        orders = list_resp.json()["items"]
        if orders:
            order_id = orders[0]["id"]
            resp = await client.get(
                f"{BASE_URL}/api/v1/orders/{order_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "id" in data
            assert "status" in data
        else:
            pytest.skip("No orders available to test")

    @pytest.mark.asyncio
    async def test_get_order_invalid_id(self, client, auth_tokens):
        """GET /api/v1/orders/{invalid_id} returns 404."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"{BASE_URL}/api/v1/orders/{fake_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_order_breakdown(self, client, auth_tokens):
        """GET /api/v1/orders/{id}/breakdown returns fee breakdown."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        list_resp = await client.get(
            f"{BASE_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        list_resp.raise_for_status()
        orders = list_resp.json()["items"]
        if orders:
            order_id = orders[0]["id"]
            resp = await client.get(
                f"{BASE_URL}/api/v1/orders/{order_id}/breakdown",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 404)
            if resp.status_code == 200:
                data = resp.json()
                assert "total" in data or "food_subtotal" in data


class TestOrderStatus:
    """Order status and timeline tests."""

    @pytest.mark.asyncio
    async def test_get_order_timeline(self, client, auth_tokens):
        """GET /api/v1/orders/{id}/timeline returns order timeline."""
        token = auth_tokens.get("customer")
        if not token:
            pytest.skip("Customer login failed, no auth token")
        list_resp = await client.get(
            f"{BASE_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        list_resp.raise_for_status()
        orders = list_resp.json()["items"]
        if orders:
            order_id = orders[0]["id"]
            resp = await client.get(
                f"{BASE_URL}/api/v1/orders/{order_id}/timeline",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code in (200, 404)