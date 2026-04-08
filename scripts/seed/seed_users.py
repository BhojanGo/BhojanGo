"""Seed user accounts for local development."""

import asyncio
import uuid
from datetime import UTC, datetime

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS = [
    # Customers
    {
        "id": "11111111-1111-1111-1111-111111111101",
        "email": "customer1@test.com",
        "phone": "+14155551001",
        "full_name": "Priya Sharma",
        "password": "Test1234!",
        "role": "customer",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "en-IN",
        "loyalty_points": 250,
    },
    {
        "id": "11111111-1111-1111-1111-111111111102",
        "email": "customer2@test.com",
        "phone": "+14155551002",
        "full_name": "John Smith",
        "password": "Test1234!",
        "role": "customer",
        "country": "US",
        "preferred_currency": "USD",
        "preferred_locale": "en-US",
        "loyalty_points": 100,
    },
    {
        "id": "11111111-1111-1111-1111-111111111103",
        "email": "customer3@test.com",
        "phone": "+14155551003",
        "full_name": "Amit Patel",
        "password": "Test1234!",
        "role": "customer",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "hi-IN",
        "loyalty_points": 500,
    },
    {
        "id": "11111111-1111-1111-1111-111111111104",
        "email": "customer4@test.com",
        "phone": "+14155551004",
        "full_name": "Emily Davis",
        "password": "Test1234!",
        "role": "customer",
        "country": "US",
        "preferred_currency": "USD",
        "preferred_locale": "en-US",
        "loyalty_points": 0,
    },
    {
        "id": "11111111-1111-1111-1111-111111111105",
        "email": "customer5@test.com",
        "phone": "+14155551005",
        "full_name": "Ravi Kumar",
        "password": "Test1234!",
        "role": "customer",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "en-IN",
        "loyalty_points": 75,
    },
    # Restaurant Owners
    {
        "id": "22222222-2222-2222-2222-222222222201",
        "email": "owner1@test.com",
        "phone": "+14155552001",
        "full_name": "Rajesh Mehta",
        "password": "Test1234!",
        "role": "restaurant_owner",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "en-IN",
    },
    {
        "id": "22222222-2222-2222-2222-222222222202",
        "email": "owner2@test.com",
        "phone": "+14155552002",
        "full_name": "Maria Garcia",
        "password": "Test1234!",
        "role": "restaurant_owner",
        "country": "US",
        "preferred_currency": "USD",
        "preferred_locale": "en-US",
    },
    # Drivers
    {
        "id": "33333333-3333-3333-3333-333333333301",
        "email": "driver1@test.com",
        "phone": "+14155553001",
        "full_name": "Suresh Yadav",
        "password": "Test1234!",
        "role": "driver",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "en-IN",
    },
    {
        "id": "33333333-3333-3333-3333-333333333302",
        "email": "driver2@test.com",
        "phone": "+14155553002",
        "full_name": "Mike Johnson",
        "password": "Test1234!",
        "role": "driver",
        "country": "US",
        "preferred_currency": "USD",
        "preferred_locale": "en-US",
    },
    {
        "id": "33333333-3333-3333-3333-333333333303",
        "email": "driver3@test.com",
        "phone": "+14155553003",
        "full_name": "Vikram Singh",
        "password": "Test1234!",
        "role": "driver",
        "country": "IN",
        "preferred_currency": "INR",
        "preferred_locale": "en-IN",
    },
    # Admin
    {
        "id": "44444444-4444-4444-4444-444444444401",
        "email": "admin@bhojango.com",
        "phone": "+14155554001",
        "full_name": "Admin User",
        "password": "Admin1234!",
        "role": "super_admin",
        "country": "US",
        "preferred_currency": "USD",
        "preferred_locale": "en-US",
        "is_verified": True,
    },
]


def generate_sql() -> str:
    lines = [
        "-- Seed users (idempotent: uses ON CONFLICT DO NOTHING)",
        "INSERT INTO users (id, email, phone, full_name, hashed_password, role, country, preferred_currency, preferred_locale, loyalty_points, is_active, is_verified, is_phone_verified, created_at, updated_at)",
        "VALUES",
    ]
    values = []
    for u in USERS:
        hashed = pwd_context.hash(u["password"])
        loyalty = u.get("loyalty_points", 0)
        verified = u.get("is_verified", False)
        values.append(
            f"  ('{u['id']}', '{u['email']}', '{u['phone']}', '{u['full_name']}', "
            f"'{hashed}', '{u['role']}', '{u['country']}', '{u['preferred_currency']}', "
            f"'{u['preferred_locale']}', {loyalty}, true, {'true' if verified else 'false'}, false, NOW(), NOW())"
        )
    lines.append(",\n".join(values))
    lines.append("ON CONFLICT (id) DO NOTHING;\n")
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_sql())
    print("\n-- Test credentials:")
    for u in USERS:
        print(f"--   {u['email']} / {u['password']} ({u['role']})")
