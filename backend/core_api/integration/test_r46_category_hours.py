"""R46: a category with hours is on customers' menu only inside them, on the restaurant's own clock (Boise and
Hyderabad); an "All day" category (no hours) always is. Runs against the migrated test database like the r43 tests."""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

from core_api.integration.test_r43_menu_editing import client, login  # noqa: F401  (fixture)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)

MARKETS = [("partner.boi@example.com", "Boise Bowl Co.", "12.50"), ("partner.hyd@example.com", "Spice Route Kitchen", "120")]


async def shown(client: AsyncClient, rid: str) -> dict[str, list[str]]:  # noqa: F811
    menu = (await client.get(f"/api/v1/restaurants/{rid}/menu")).json()
    return {c["name"]: [i["name"] for i in c["items"]] for c in menu["categories"]}


@pytest.mark.parametrize(("partner_email", "name", "price"), MARKETS)
async def test_category_hours_on_the_restaurants_clock(client: AsyncClient, partner_email: str, name: str, price: str) -> None:  # noqa: F811
    partner = await login(client, partner_email)
    rid = next(r for r in (await client.get("/api/v1/restaurants", params={"limit": 100})).json()["items"] if r["name"] == name)["id"]
    base = f"/api/v1/restaurants/{rid}"
    tag = uuid.uuid4().hex[:6]
    timed = (await client.post(f"{base}/categories", headers=partner, json={"name": f"Breakfast {tag}"})).json()
    always = (await client.post(f"{base}/categories", headers=partner, json={"name": f"Mains {tag}"})).json()
    dishes = []
    for cat, dish in ((timed, f"Poha {tag}"), (always, f"Bowl {tag}")):
        r = await client.post(f"{base}/menu-items", headers=partner, json={"name": dish, "price": price, "category": cat["name"], "category_id": cat["id"]})
        assert r.status_code == 201, r.text
        dishes.append(r.json()["id"])
    try:
        local = (await client.get(f"{base}/availability")).json()["local_time"]  # the restaurant's clock
        h = int(local[11:13])
        later = {"available_from": f"{(h + 2) % 24:02d}:00", "available_until": f"{(h + 3) % 24:02d}:00"}
        around = {"available_from": f"{h:02d}:00", "available_until": f"{(h + 1) % 24:02d}:00"}
        # hours that aren't now: not listed; the all-day category is
        assert (await client.put(f"{base}/categories/{timed['id']}", headers=partner, json=later)).status_code == 200
        menu = await shown(client, rid)
        assert f"Breakfast {tag}" not in menu and menu[f"Mains {tag}"] == [f"Bowl {tag}"]
        # hours around now: listed with its dish
        assert (await client.put(f"{base}/categories/{timed['id']}", headers=partner, json=around)).status_code == 200
        assert (await shown(client, rid))[f"Breakfast {tag}"] == [f"Poha {tag}"]
        # cleared (All day): listed at any time
        r = await client.put(f"{base}/categories/{timed['id']}", headers=partner, json={"available_from": None, "available_until": None})
        assert r.status_code == 200 and r.json()["available_from"] is None
        menu = await shown(client, rid)
        assert f"Breakfast {tag}" in menu and f"Mains {tag}" in menu
    finally:
        for d in dishes:
            await client.delete(f"{base}/menu-items/{d}", headers=partner)
        for c in (timed, always):
            await client.delete(f"{base}/categories/{c['id']}", headers=partner)
