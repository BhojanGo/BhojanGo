"""Delivery PINs on the migrated database: a seed-number customer's order gets
the fixed test PIN (Maestro/e2e); a customer on a real number gets random ones."""
import os
import re

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from core_api.integration.test_orders_flow import client, login, new_order  # noqa: F401  (client: fixture)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


async def pin_of(order_id: str) -> str:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        return (await db.execute(text("SELECT delivery_pin FROM orders WHERE id = :i"), {"i": order_id})).scalar()


async def test_seed_number_customer_gets_the_fixed_pin(client: AsyncClient) -> None:  # noqa: F811
    from shared.config import get_settings

    fixed = get_settings().providers.DELIVERY_PIN_FIXED
    assert fixed, "the fixed test PIN is on outside production"
    h = await login(client, "customer1.hyd@example.com")
    assert await pin_of((await new_order(client, h))["id"]) == fixed


async def test_real_number_customer_gets_random_pins(client: AsyncClient) -> None:  # noqa: F811
    from shared.config import get_settings
    from shared.db import AsyncSessionLocal

    fixed = get_settings().providers.DELIVERY_PIN_FIXED
    email = "customer2.hyd@example.com"
    async with AsyncSessionLocal() as db:
        seed_phone = (await db.execute(text("SELECT phone FROM users WHERE email = :e"), {"e": email})).scalar()
        await db.execute(text("UPDATE users SET phone = '+919812398123' WHERE email = :e"), {"e": email})
        await db.commit()
    try:
        h = await login(client, email)
        pins = [await pin_of((await new_order(client, h))["id"]) for _ in range(3)]
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("UPDATE users SET phone = :p WHERE email = :e"), {"p": seed_phone, "e": email})
            await db.commit()
    assert all(re.fullmatch(r"\d{4}", p) for p in pins), pins
    assert len(set(pins)) > 1, pins  # three equal random PINs: 1 in 10^8
    assert pins.count(fixed) < len(pins), "the fixed test PIN was used for a real number"
