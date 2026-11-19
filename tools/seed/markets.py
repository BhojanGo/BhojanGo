"""The markets-only seed: production's base data and nothing else (R19). Allowed in production.

    cd backend && python ../tools/seed/markets.py        # DATABASE_URL and the environment's settings

What it writes is chosen in markets_data.py (no database): countries, states, cities (Boise live,
India kept but switched off), zones, the market rules, the help articles, and Terms and Privacy as
unpublished drafts. No users, kitchens, menus, orders or payout accounts: the first admin comes
from `python -m core_api.modules.identity.first_admin`, kitchens and delivery partners sign up.

Idempotent and safe to run again on a live database: it only ADDS what is missing (rows are
matched by code, by the base seed's fixed ids, or by kind and country for legal documents) and
never changes a row an admin may have edited since (statuses, zones, rules, documents). Help
articles follow the base seed's rule: refreshed unless an admin changed them.

The full seed (seed.py, with demo accounts) and the demo seed refuse production; this one
doesn't. docs/launch/go-live.md step 11.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent))
import markets_data  # noqa: E402
import seed as base  # noqa: E402  (its SQL, ids and help loader; its main() is not run)
from legal_docs import documents  # noqa: E402


def insert_only(stmt, conflict: str):  # type: ignore[no-untyped-def]
    """The base seed's INSERT with ON CONFLICT ... DO NOTHING (add what's missing, change nothing)."""
    return text(str(stmt.text).split("ON CONFLICT")[0] + f"ON CONFLICT {conflict} DO NOTHING")


ADD_COUNTRY = insert_only(base.UPSERT_COUNTRY, "(code)")
ADD_REGION = insert_only(base.UPSERT_REGION, "(code)")
ADD_CITY = insert_only(base.UPSERT_CITY, "(code)")
ADD_ZONE = insert_only(base.UPSERT_ZONE, "(city_id, name)")
ADD_RULE = insert_only(base.UPSERT_RULE, "(id)")
ADD_LEGAL_DRAFT = text("""
    INSERT INTO legal_documents (id, kind, country, language, version, status, title, key_points, body,
        summary_of_changes, effective_date, created_at, updated_at)
    SELECT CAST(:id AS uuid), CAST(:kind AS varchar), CAST(:country AS varchar), 'en', NULL, 'draft',
           CAST(:title AS varchar), CAST(:points AS jsonb), CAST(:body AS text), CAST(:summary AS varchar), NULL, now(), now()
    WHERE NOT EXISTS (SELECT 1 FROM legal_documents
                      WHERE kind = CAST(:kind AS varchar) AND country = CAST(:country AS varchar) AND language = 'en')
    ON CONFLICT (id) DO NOTHING
""")


async def _added(conn, stmt, params: dict) -> int:  # type: ignore[no-untyped-def]
    return (await conn.execute(stmt, params)).rowcount or 0


async def _id(conn, table: str, code: str):  # type: ignore[no-untyped-def]
    return (await conn.execute(text(f"SELECT id FROM {table} WHERE code = :c"), {"c": code})).scalar_one()  # noqa: S608


async def seed_markets_only(conn) -> dict[str, int]:  # type: ignore[no-untyped-def]
    from core_api.modules.rules.service.templates import slot_for, validate_params

    sid = base.sid
    added = dict.fromkeys(("countries", "regions", "cities", "zones", "rules", "legal_drafts"), 0)
    for c in markets_data.markets():
        added["countries"] += await _added(conn, ADD_COUNTRY, {
            "id": sid("country", c["code"]), **{k: c[k] for k in (
                "code", "name", "currency", "locales", "timezone", "distance_unit", "phone_code",
                "payment_providers", "tax_regime", "payout_provider", "status")},
            "settings": json.dumps(c["settings"])})
        cid = await _id(conn, "countries", c["code"])
        for r in c["regions"]:
            added["regions"] += await _added(conn, ADD_REGION, {
                "id": sid("region", r["code"]), "country_id": cid, "code": r["code"], "name": r["name"],
                "timezone": r.get("timezone"), "settings": json.dumps(r["settings"]), "status": r["status"]})
            rid = await _id(conn, "regions", r["code"])
            for city in r["cities"]:
                added["cities"] += await _added(conn, ADD_CITY, {
                    "id": sid("city", city["code"]), "country_id": cid, "region_id": rid, "code": city["code"],
                    "name": city["name"], "lat": city["center"][0], "lng": city["center"][1],
                    "service_hours": json.dumps(city["service_hours"]), "settings": json.dumps(city["settings"]),
                    "status": city["status"], "timezone": city.get("timezone") or r.get("timezone") or c["timezone"]})
                city_id = await _id(conn, "cities", city["code"])
                for name, bounds, min_order, status, color in city["zones"]:
                    added["zones"] += await _added(conn, ADD_ZONE, {
                        "id": sid("zone", city["code"], name), "city_id": city_id, "name": name,
                        "geojson": base.box(*bounds), "min_order": Decimal(min_order), "color": color, "status": status})
    for family, template, key, name, level, scope_id, params in markets_data.rules():
        added["rules"] += await _added(conn, ADD_RULE, {
            "id": sid("rule", family, template, key or "", level, scope_id), "family": family, "template": template,
            "key": key, "slot": slot_for(family, template, key), "name": name,
            "params": json.dumps(validate_params(family, template, params)), "scope_level": level,
            "scope_id": scope_id, "market_scope": scope_id, "created_by": None})
    countries = {c["code"] for c in markets_data.markets()}
    for d in documents():
        if d["country"] in countries:
            added["legal_drafts"] += await _added(conn, ADD_LEGAL_DRAFT, {
                "id": sid("legal_document", d["country"], d["kind"], "en", "draft"), "kind": d["kind"],
                "country": d["country"], "title": d["title"], "points": json.dumps(d["key_points"]), "body": d["body"],
                "summary": d["summary"]})
    added["help_articles"] = await base.seed_help(conn)
    return added


CHECKS = text("""
SELECT (SELECT count(*) FROM countries), (SELECT count(*) FROM cities WHERE status IN ('beta', 'live')),
       (SELECT string_agg(code, ',' ORDER BY code) FROM cities WHERE status IN ('beta', 'live')),
       (SELECT count(*) FROM zones), (SELECT count(*) FROM rules WHERE status = 'published'),
       (SELECT count(*) FROM users WHERE email LIKE '%@example.com'), (SELECT count(*) FROM restaurants),
       (SELECT count(*) FROM payout_accounts WHERE provider = 'fake')
""")


async def run(database_url: str) -> dict[str, int]:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as conn:
            added = await seed_markets_only(conn)
            c = (await conn.execute(CHECKS)).one()
    finally:
        await engine.dispose()
    print("Markets-only seed: added " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in added.items()) + ".")
    print(f"Now: {c[0]} countries; open cities: {c[1]} ({c[2] or 'none'}); {c[3]} zones; {c[4]} published rules; "
          f"{c[5]} @example.com users, {c[6]} restaurants, {c[7]} fake payout accounts.")
    return added


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    asyncio.run(run(url))


if __name__ == "__main__":
    main()
