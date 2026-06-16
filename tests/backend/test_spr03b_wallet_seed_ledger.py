"""SPR-03B-WALLET-01 live API tests: wallet seed, top-up, debit, and ledger.

Strict live-HTTP tests. These require local services started by scripts/start-all.sh.
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
DEMO_SEED_REFERENCE_ID = "SPR-03B-WALLET-01-DEMO-SEED"


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


def _wallet_balance(client: httpx.Client, token: str) -> dict:
    response = client.get(f"{PAYMENT_URL}/api/v1/wallet/balance", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"] in ("USD", "INR"), body
    assert float(body["balance"]) >= 0, body
    return body


def _wallet_transactions(client: httpx.Client, token: str) -> list[dict]:
    response = client.get(f"{PAYMENT_URL}/api/v1/wallet/transactions?limit=50", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body.get("items"), list), body
    return body["items"]


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

    raise AssertionError("no seeded restaurant menu item found for wallet contract")


def _order_payload(restaurant: dict, item: dict, country: str = "US") -> dict:
    return {
        "restaurant_id": restaurant["id"],
        "items": [{"menu_item_id": item["id"], "quantity": 1, "customizations": []}],
        "delivery_address": {
            "street": "123 SPR-03B Wallet Street",
            "city": "Boston" if country == "US" else "Bangalore",
            "state": "MA" if country == "US" else "KA",
            "zip": "02114" if country == "US" else "560001",
            "country": country,
        },
        "payment_method": "wallet",
    }


def test_spr03b_wallet_seed_topup_order_debit_and_transactions() -> None:
    with _client() as client:
        token = _customer_token(client)

        seeded = _wallet_balance(client, token)
        currency = seeded["currency"]
        txns = _wallet_transactions(client, token)
        assert any(
            txn.get("reference_id") == DEMO_SEED_REFERENCE_ID
            and txn.get("reference_type") == "demo_seed"
            and txn.get("type") == "credit"
            for txn in txns
        ), "default demo seed must be visible in wallet transactions"

        topup = client.post(
            f"{PAYMENT_URL}/api/v1/wallet/topup",
            headers=_auth_headers(token),
            json={"amount": 100.0, "currency": currency, "payment_method_id": "spr03b_wallet01_test_topup"},
        )
        assert topup.status_code == 200, topup.text
        topup_balance = float(topup.json()["balance"])
        assert topup_balance >= float(seeded["balance"]) + 99.99

        restaurant, item = _restaurant_and_menu_item(client)
        order = client.post(
            f"{ORDER_URL}/api/v1/orders",
            headers={**_auth_headers(token), "X-Idempotency-Key": str(uuid.uuid4())},
            json=_order_payload(restaurant, item, country="US" if currency == "USD" else "IN"),
        )
        assert order.status_code == 201, order.text
        order_body = order.json()
        assert order_body["id"]
        assert order_body["payment_method"] in ("wallet", "card", "cash_on_delivery")
        total_major = float(order_body["total"])
        assert total_major > 0

        amount_minor = round(total_major * 100)
        payment = client.post(
            f"{PAYMENT_URL}/api/v1/payments/initiate",
            headers=_auth_headers(token),
            json={
                "order_id": order_body["id"],
                "amount": amount_minor,
                "currency": currency,
                "country": "US" if currency == "USD" else "IN",
                "payment_method_type": "wallet",
            },
        )
        assert payment.status_code == 201, payment.text
        payment_body = payment.json()
        assert payment_body["provider"] == "wallet", payment_body
        assert payment_body["amount"] == amount_minor

        after = _wallet_balance(client, token)
        expected = topup_balance - total_major
        assert abs(float(after["balance"]) - expected) < 0.05, (after, topup_balance, total_major)

        txns_after = _wallet_transactions(client, token)
        debit_tx = next(
            (txn for txn in txns_after if txn.get("reference_id") == order_body["id"] and txn.get("reference_type") == "order"),
            None,
        )
        assert debit_tx is not None, "wallet order debit transaction must be recorded"
        assert debit_tx["type"] == "debit", debit_tx
        assert abs(float(debit_tx["amount"]) - total_major) < 0.05, debit_tx

        topup_tx = next(
            (txn for txn in txns_after if txn.get("reference_id") == "spr03b_wallet01_test_topup" and txn.get("reference_type") == "topup"),
            None,
        )
        assert topup_tx is not None, "dummy top-up transaction must be recorded"
        assert topup_tx["type"] == "credit", topup_tx
