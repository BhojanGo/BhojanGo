"""Public responses never carry a restaurant's commission or payout terms, its
owner, bank or tax registration, or licence documents.

1. Static (no database, runs with the unit tests too): for every route the
   access sweep marks public (POLICY in test_zz_access_sweep.py), walk its
   success response schema in the OpenAPI document, through $refs, arrays,
   unions and nested objects, and fail on any forbidden property name.
2. Live (migrated + seeded database): call the public restaurant endpoints and
   fail if a forbidden key appears anywhere in the JSON, including inside
   untyped dicts the schema can't see (discover's offer.restaurant).

The FSSAI licence NUMBER is allowed: Indian law requires showing it to customers.
"""
import os
import re
from typing import Any

import pytest

FORBIDDEN = re.compile(
    r"commission|payout|^bank|_bank|account_number|ifsc|^routing|^gst|_gst|tax_id|^pan$|"
    r"licen[cs]e_document|document|owner_id|pricing_model|^flat_fee|subscription|^tier$|fssai_expires",
    re.IGNORECASE,
)

# The one public route that publishes terms on purpose: what ANY new kitchen partner in a
# country gets ("Add your kitchen", R8 F7): the country's commission range and tiers from
# the live rules, the payout schedule, and the documents to have ready. Nothing about a
# particular restaurant; only these exact fields are allowed, anything else still fails.
PUBLISHED_TERMS = {
    ("GET", "/api/v1/kitchens/terms"): {"commission", "commission.tiers[].tier", "documents", "payout"},
}

needs_db = pytest.mark.skipif(
    os.environ.get("RUN_MIGRATED_DB_TESTS") != "1",
    reason="needs a migrated + seeded Postgres and Redis (set RUN_MIGRATED_DB_TESTS=1)",
)


def forbidden_in_schema(schema: dict, components: dict, where: str = "", seen: frozenset = frozenset()) -> list[str]:
    """Every forbidden property name reachable from this schema, as dotted paths."""
    out: list[str] = []
    if not isinstance(schema, dict):
        return out
    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return out
        return forbidden_in_schema(components.get(name, {}), components, where, seen | {name})
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        for sub in schema.get(key, []):
            out += forbidden_in_schema(sub, components, where, seen)
    for key in ("items", "additionalProperties", "not"):
        if isinstance(schema.get(key), dict):
            out += forbidden_in_schema(schema[key], components, f"{where}[]", seen)
    for prop, sub in (schema.get("properties") or {}).items():
        path = f"{where}.{prop}" if where else prop
        if FORBIDDEN.search(prop):
            out.append(path)
        out += forbidden_in_schema(sub, components, path, seen)
    return out


def forbidden_in_json(data: Any, where: str = "") -> list[str]:
    out: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            path = f"{where}.{k}" if where else str(k)
            if FORBIDDEN.search(str(k)):
                out.append(path)
            out += forbidden_in_json(v, path)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            out += forbidden_in_json(v, f"{where}[{i}]")
    return out


def public_routes() -> list[tuple[str, str]]:
    """(method, OpenAPI path) of every route the access sweep calls public."""
    from core_api.integration.test_zz_access_sweep import _ALIASES, POLICY

    real = {alias: path for path, alias in _ALIASES.items()}
    return sorted((m, real.get(p, p)) for (m, p), pol in POLICY.items() if pol.kind == "public")


def response_schemas(doc: dict, method: str, path: str) -> list[dict]:
    op = (doc["paths"].get(path) or {}).get(method.lower()) or {}
    return [content["schema"] for code, resp in (op.get("responses") or {}).items() if str(code).startswith("2")
            for content in (resp.get("content") or {}).values() if "schema" in content]


def openapi() -> dict:
    from core_api.main import app

    return app.openapi()


# ── 1. static ────────────────────────────────────────────────────────────────

def test_no_public_route_can_expose_commission_payout_or_tax_fields() -> None:
    doc = openapi()
    components = doc.get("components", {}).get("schemas", {})
    routes = public_routes()
    assert ("GET", "/api/v1/restaurants/{restaurant_id}") in routes  # the sweep's policy is where we think
    leaks = {f"{m} {p}": bad for m, p in routes
             for bad in [sorted({b for s in response_schemas(doc, m, p) for b in forbidden_in_schema(s, components)}
                                - PUBLISHED_TERMS.get((m, p), set()))]
             if bad}
    assert not leaks, f"public routes whose response schema has private fields: {leaks}"


def test_canary_the_static_check_catches_a_leak() -> None:
    """The check must find a forbidden field when there is one: the owners' schema has several."""
    doc = openapi()
    components = doc["components"]["schemas"]
    bad = forbidden_in_schema({"$ref": "#/components/schemas/RestaurantResponse"}, components)
    assert {"commission_rate", "pricing_model", "owner_id", "flat_fee_per_order", "monthly_subscription_fee",
            "tier", "fssai_expires_on"} <= set(bad), bad
    nested = {"type": "object", "properties": {"items": {"type": "array", "items": {"$ref": "#/components/schemas/RestaurantResponse"}}}}
    assert "items[].commission_rate" in forbidden_in_schema(nested, components)
    assert forbidden_in_json({"a": [{"x": {"payout_account": 1}}], "fssai_number": "1"}) == ["a[0].x.payout_account"]


def test_public_restaurant_keeps_what_customers_must_see() -> None:
    components = openapi()["components"]["schemas"]
    props = components["PublicRestaurant"]["properties"]
    assert {"fssai_number", "name", "slug", "delivery_fee", "currency"} <= set(props)
    assert not forbidden_in_schema({"$ref": "#/components/schemas/PublicRestaurant"}, components)


# ── 2. live ──────────────────────────────────────────────────────────────────

@needs_db
async def test_public_restaurant_endpoints_return_no_private_fields() -> None:
    from httpx import ASGITransport, AsyncClient

    from core_api.main import app
    from shared.db import engine
    from shared.redis import close_redis

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            lst = await c.get("/api/v1/restaurants", params={"limit": 100})
            assert lst.status_code == 200 and lst.json()["items"], lst.text
            first = lst.json()["items"][0]
            rid, slug = first["id"], first["slug"]
            urls = [
                "/api/v1/restaurants?limit=100",
                f"/api/v1/restaurants?city={first['city']}",
                "/api/v1/restaurants/search?q=a",
                f"/api/v1/restaurants/{rid}", f"/api/v1/restaurants/{rid}",  # the second from the cache
                f"/api/v1/restaurants/by-slug/{slug}",
                f"/api/v1/restaurants/{rid}/menu",
                f"/api/v1/restaurants/{rid}/availability",
                f"/api/v1/restaurants/{rid}/hours",
                f"/api/v1/restaurants/{rid}/option-groups",
                f"/api/v1/restaurants/{rid}/delivery-check?lat={first['lat']}&lng={first['lng']}",
                f"/api/v1/discover?lat={first['lat']}&lng={first['lng']}",
                "/api/v1/markets/directory",
            ]
            for u in urls:
                r = await c.get(u)
                assert r.status_code == 200, f"{u} → {r.status_code} {r.text[:200]}"
                assert not forbidden_in_json(r.json()), f"{u} exposes {forbidden_in_json(r.json())}"
            # the record has these columns; the public view leaves them out and keeps the licence number
            body = (await c.get(f"/api/v1/restaurants/{rid}")).json()
            assert "commission_rate" not in body and "owner_id" not in body and "fssai_number" in body
    finally:
        await close_redis()
        await engine.dispose()
