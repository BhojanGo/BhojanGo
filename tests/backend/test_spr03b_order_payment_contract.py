"""SPR-03B live API contract tests: order creation + simulated payment.

Strict synchronous live-HTTP tests. These deliberately avoid tests/backend/conftest.py
async fixtures because the local pytest/pytest-asyncio mode treats undecorated async
fixtures as setup errors. The objective here is live API proof, not fixture reuse.
"""
from __future__ import annotations

import uuid

import httpx

USER_URL = "http://localhost:8001"
RESTAURANT_URL = "http://localhost:8002"
ORDER_URL = "http://localhost:8003"
PAYMENT_URL = "http://localhost:8005"
CUSTOMER_EMAIL = "customer1@test.com"
CUSTOMER_PASSWORD = "Test1234!"


def _client() -> httpx.Client:
    return httpx.Client(timeout=30.0)


def _customer_token(client: httpx.Client) -> str:
    response = client.post(
        f"{USER_URL}/api/v1/auth/login",
        json={"email": CUSTOMER_EMAIL, "password": CUSTOMER_PASSWORD},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token"), body
    return body["access_token"]


def _restaurant_and_menu_item(client: httpx.Client) -> tuple[dict, dict]:
    restaurants_response = client.get(f"{RESTAURANT_URL}/api/v1/restaurants?limit=10")
    assert restaurants_response.status_code == 200, restaurants_response.text
    restaurants = restaurants_response.json().get("items", [])
    assert restaurants, "at least one seeded restaurant is required"

    for restaurant in restaurants:
        menu_response = client.get(f"{RESTAURANT_URL}/api/v1/restaurants/{restaurant['id']}/menu")
        if menu_response.status_code != 200:
            continue
        menu = menu_response.json()
        items: list[dict] = []
        for category in menu.get("categories", []):
            items.extend(category.get("items", []))
        items.extend(menu.get("uncategorized_items", []))
        items = [item for item in items if item.get("is_available", True)]
        if items:
            return restaurant, items[0]

    raise AssertionError("no seeded restaurant menu item found for SPR-03B contract")


def _order_payload(restaurant: dict, item: dict, country: str = "IN") -> dict:
    return {
        "restaurant_id": restaurant["id"],
        "items": [{"menu_item_id": item["id"], "quantity": 1, "customizations": []}],
        "delivery_address": {
            "street": "123 SPR-03B Contract Street",
            "city": "Bangalore" if country == "IN" else "Boston",
            "state": "KA" if country == "IN" else "MA",
            "zip": "560001" if country == "IN" else "02114",
            "country": country,
        },
        "payment_method": "card",
    }


def test_spr03b_create_order_requires_idempotency_key() -> None:
    with _client() as client:
        token = _customer_token(client)
        restaurant, item = _restaurant_and_menu_item(client)
        response = client.post(
            f"{ORDER_URL}/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json=_order_payload(restaurant, item),
        )
        assert response.status_code == 422, response.text
        assert "X-Idempotency-Key" in response.text


def test_spr03b_create_order_is_idempotent_and_payment_is_simulated() -> None:
    with _client() as client:
        token = _customer_token(client)
        restaurant, item = _restaurant_and_menu_item(client)
        idempotency_key = str(uuid.uuid4())
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Idempotency-Key": idempotency_key,
        }

        first = client.post(
            f"{ORDER_URL}/api/v1/orders",
            headers=headers,
            json=_order_payload(restaurant, item),
        )
        assert first.status_code == 201, first.text
        order = first.json()
        assert order["id"]
        assert order["status"] == "pending"
        assert order["restaurant_id"] == restaurant["id"]
        assert float(order["subtotal"]) > 0
        assert float(order["total"]) > 0
        assert order["currency"] in ("INR", "USD")

        replay = client.post(
            f"{ORDER_URL}/api/v1/orders",
            headers=headers,
            json=_order_payload(restaurant, item),
        )
        assert replay.status_code == 201, replay.text
        assert replay.json()["id"] == order["id"]

        amount_minor = round(float(order["total"]) * 100)
        currency = order["currency"]
        country = "IN" if currency == "INR" else "US"
        payment = client.post(
            f"{PAYMENT_URL}/api/v1/payments/initiate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "order_id": order["id"],
                "amount": amount_minor,
                "currency": currency,
                "country": country,
                "payment_method_type": "card",
            },
        )
        assert payment.status_code == 201, payment.text
        payment_body = payment.json()
        assert payment_body["provider"] == "mock", payment_body
        assert payment_body["payment_intent_id"]
        assert payment_body["amount"] == amount_minor

        lookup = client.get(
            f"{PAYMENT_URL}/api/v1/payments/{order['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert lookup.status_code == 200, lookup.text
        payment_record = lookup.json()
        assert payment_record["provider"] == "mock"
        assert payment_record["status"] == "succeeded"
