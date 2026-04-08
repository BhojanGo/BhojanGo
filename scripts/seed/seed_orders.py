"""Seed historical orders for local development."""

import json
import random
import uuid
from datetime import datetime, timedelta

STATUSES = ["delivered", "delivered", "delivered", "delivered", "cancelled", "confirmed", "preparing", "picked_up", "pending"]

CUSTOMERS = [
    "11111111-1111-1111-1111-111111111101",
    "11111111-1111-1111-1111-111111111102",
    "11111111-1111-1111-1111-111111111103",
    "11111111-1111-1111-1111-111111111104",
    "11111111-1111-1111-1111-111111111105",
]

RESTAURANTS = [
    ("aaaa0001-0001-0001-0001-000000000001", "INR"),
    ("aaaa0001-0001-0001-0001-000000000002", "INR"),
    ("aaaa0001-0001-0001-0001-000000000003", "INR"),
    ("aaaa0001-0001-0001-0001-000000000006", "USD"),
    ("aaaa0001-0001-0001-0001-000000000007", "USD"),
    ("aaaa0001-0001-0001-0001-000000000008", "USD"),
]

DRIVERS = [
    "33333333-3333-3333-3333-333333333301",
    "33333333-3333-3333-3333-333333333302",
    "33333333-3333-3333-3333-333333333303",
]

ADDRESSES_IN = [
    {"street": "123 MG Road", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560001", "lat": 12.975, "lng": 77.605},
    {"street": "45 Koramangala 5th Block", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560095", "lat": 12.934, "lng": 77.626},
]

ADDRESSES_US = [
    {"street": "350 5th Avenue", "city": "New York", "state": "NY", "postal_code": "10118", "lat": 40.748, "lng": -73.985},
    {"street": "200 Broadway", "city": "New York", "state": "NY", "postal_code": "10038", "lat": 40.710, "lng": -74.007},
]

PAYMENT_METHODS = ["card", "upi", "cash_on_delivery", "wallet"]

random.seed(42)


def generate_sql() -> str:
    lines = ["-- Seed orders (idempotent)"]
    now = datetime.utcnow()

    for i in range(50):
        order_id = f"eeee{i+1:04d}-0001-0001-0001-000000000001"
        rest_id, currency = random.choice(RESTAURANTS)
        cust_id = random.choice(CUSTOMERS)
        driver_id = random.choice(DRIVERS)
        status = random.choice(STATUSES)

        if currency == "INR":
            subtotal = round(random.uniform(150, 800), 2)
            delivery_fee = round(random.uniform(20, 50), 2)
            tax_rate = 0.18
            address = random.choice(ADDRESSES_IN)
        else:
            subtotal = round(random.uniform(12, 60), 2)
            delivery_fee = round(random.uniform(2, 5), 2)
            tax_rate = 0.08
            address = random.choice(ADDRESSES_US)

        taxes = round(subtotal * tax_rate, 2)
        tip = round(random.uniform(0, subtotal * 0.15), 2)
        total = round(subtotal + delivery_fee + taxes + tip, 2)

        created_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        payment = random.choice(PAYMENT_METHODS if currency == "INR" else ["card", "wallet"])

        items = json.dumps([
            {"menu_item_id": str(uuid.uuid4()), "name": "Item 1", "quantity": random.randint(1, 3), "unit_price": round(subtotal * 0.6, 2), "total": round(subtotal * 0.6, 2)},
            {"menu_item_id": str(uuid.uuid4()), "name": "Item 2", "quantity": random.randint(1, 2), "unit_price": round(subtotal * 0.4, 2), "total": round(subtotal * 0.4, 2)},
        ]).replace("'", "''")

        delivery_addr = json.dumps(address).replace("'", "''")

        actual_time = f"'{(created_at + timedelta(minutes=random.randint(25, 55))).isoformat()}'" if status == "delivered" else "NULL"
        cancel_reason = "'changed_mind'" if status == "cancelled" else "NULL"

        assigned_driver = f"'{driver_id}'" if status in ("picked_up", "delivered", "ready_for_pickup") else "NULL"

        lines.append(f"""
INSERT INTO orders (id, customer_id, restaurant_id, driver_id, items, status, subtotal, delivery_fee, taxes, tip, discount, total, currency, delivery_address, payment_method, estimated_delivery_time, actual_delivery_time, cancellation_reason, created_at, updated_at)
VALUES (
    '{order_id}', '{cust_id}', '{rest_id}', {assigned_driver},
    '{items}', '{status}', {subtotal}, {delivery_fee}, {taxes}, {tip}, 0, {total}, '{currency}',
    '{delivery_addr}', '{payment}', '{(created_at + timedelta(minutes=35)).isoformat()}', {actual_time}, {cancel_reason},
    '{created_at.isoformat()}', '{created_at.isoformat()}'
)
ON CONFLICT (id) DO NOTHING;""")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_sql())
