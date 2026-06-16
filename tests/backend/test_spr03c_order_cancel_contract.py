"""SPR-03C live API contract tests: order detail/list/timeline + customer cancellation.

Strict live-HTTP tests. Start local services before running.
"""
from __future__ import annotations

import uuid

import httpx

USER_URL = "http://localhost:8001"
RESTAURANT_URL = "http://localhost:8002"
ORDER_URL = "http://localhost:8003"
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


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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

    raise AssertionError("no seeded restaurant menu item found for SPR-03C order contract")


def _order_payload(restaurant: dict, item: dict) -> dict:
    return {
        "restaurant_id": restaurant["id"],
        "items": [{"menu_item_id": item["id"], "quantity": 1, "customizations": []}],
        "delivery_address": {
            "street": "123 SPR-03C Contract Street",
            "city": "Bangalore",
            "state": "KA",
            "zip": "560001",
            "country": "IN",
        },
        "payment_method": "cash_on_delivery",
    }


def _create_order(client: httpx.Client, token: str) -> dict:
    restaurant, item = _restaurant_and_menu_item(client)
    response = client.post(
        f"{ORDER_URL}/api/v1/orders",
        headers={**_auth_headers(token), "X-Idempotency-Key": str(uuid.uuid4())},
        json=_order_payload(restaurant, item),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"]
    assert body["status"] == "pending"
    assert body["items"], body
    assert "unit_price" in body["items"][0] or "price" in body["items"][0]
    assert float(body["total"]) > 0
    return body


def test_spr03c_order_list_detail_timeline_and_cancel_patch() -> None:
    with _client() as client:
        token = _customer_token(client)
        order = _create_order(client, token)
        order_id = order["id"]

        listing = client.get(f"{ORDER_URL}/api/v1/orders?limit=50", headers=_auth_headers(token))
        assert listing.status_code == 200, listing.text
        listed_ids = {item["id"] for item in listing.json().get("items", [])}
        assert order_id in listed_ids

        detail = client.get(f"{ORDER_URL}/api/v1/orders/{order_id}", headers=_auth_headers(token))
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["id"] == order_id
        assert detail_body["restaurant_name"]
        assert detail_body["items"][0]["name"]

        breakdown = client.get(f"{ORDER_URL}/api/v1/orders/{order_id}/breakdown", headers=_auth_headers(token))
        assert breakdown.status_code == 200, breakdown.text
        breakdown_body = breakdown.json()
        assert breakdown_body["total"] == detail_body["total"]
        assert breakdown_body["currency"] == detail_body["currency"]

        timeline = client.get(f"{ORDER_URL}/api/v1/orders/{order_id}/timeline", headers=_auth_headers(token))
        assert timeline.status_code == 200, timeline.text
        timeline_body = timeline.json()
        assert timeline_body["order_id"] == order_id
        assert any(entry.get("status") == "pending" for entry in timeline_body.get("timeline", []))

        cancel = client.patch(
            f"{ORDER_URL}/api/v1/orders/{order_id}/cancel",
            headers=_auth_headers(token),
            json={"reason": "customer_cancelled", "note": "SPR-03C live cancel proof"},
        )
        assert cancel.status_code == 200, cancel.text
        cancel_body = cancel.json()
        assert cancel_body["status"] == "cancelled"
        assert cancel_body["cancellation_reason"] == "customer_cancelled"
        assert cancel_body["cancellation_note"] == "SPR-03C live cancel proof"

        cancelled_timeline = client.get(f"{ORDER_URL}/api/v1/orders/{order_id}/timeline", headers=_auth_headers(token))
        assert cancelled_timeline.status_code == 200, cancelled_timeline.text
        assert any(entry.get("status") == "cancelled" for entry in cancelled_timeline.json().get("timeline", []))

        repeat_cancel = client.patch(
            f"{ORDER_URL}/api/v1/orders/{order_id}/cancel",
            headers=_auth_headers(token),
            json={"reason": "customer_cancelled", "note": "repeat should fail"},
        )
        assert repeat_cancel.status_code == 422, repeat_cancel.text
        assert "ORDER_STATE_INVALID" in repeat_cancel.text
