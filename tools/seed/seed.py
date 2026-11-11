"""Load the Hyderabad + Boise seed data into the database at DATABASE_URL.

Idempotent: users are upserted by email, restaurants by slug, and categories,
menu items and addresses by deterministic UUIDs, so running it again updates
rows instead of duplicating them.

Run (needs the backend dependencies, e.g. inside the core-api container):
    make seed                                   # via Docker
    cd backend && uv run python ../tools/seed/seed.py   # on the host
"""
import asyncio
import json
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import ADMINS, ADMIN_PASSWORD, COUNTRIES, MARKETS, PASSWORD  # noqa: E402

NS = uuid.UUID("6f1d3c52-6b0e-4a63-9a0d-5b7f6a2b8a11")  # fixed namespace for seed ids
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def sid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(NS, "/".join(parts))


UPSERT_USER = text("""
INSERT INTO users (id, email, phone, full_name, hashed_password, role, country,
                   preferred_currency, preferred_locale, loyalty_points,
                   is_active, is_verified, is_phone_verified, created_at, updated_at)
VALUES (:id, :email, :phone, :full_name, :hashed_password, :role, :country,
        :currency, :locale, 0, true, true, true, now(), now())
ON CONFLICT (email) DO UPDATE SET
    phone = EXCLUDED.phone, full_name = EXCLUDED.full_name,
    hashed_password = EXCLUDED.hashed_password, role = EXCLUDED.role,
    country = EXCLUDED.country, preferred_currency = EXCLUDED.preferred_currency,
    preferred_locale = EXCLUDED.preferred_locale, is_active = true, updated_at = now()
RETURNING id
""")

UPSERT_ADDRESS = text("""
INSERT INTO addresses (id, user_id, label, street, city, state, postal_code, country, created_at)
VALUES (:id, :user_id, 'Home', :street, :city, :state, :postal_code, :country, now())
ON CONFLICT (id) DO UPDATE SET
    user_id = EXCLUDED.user_id, street = EXCLUDED.street, city = EXCLUDED.city,
    state = EXCLUDED.state, postal_code = EXCLUDED.postal_code, country = EXCLUDED.country
""")

UPSERT_COUNTRY = text("""
INSERT INTO countries (id, code, name, currency, locales, timezone, distance_unit, phone_code,
                       payment_providers, tax_regime, settings, status)
VALUES (:id, :code, :name, :currency, :locales, :timezone, :distance_unit, :phone_code,
        :payment_providers, :tax_regime, CAST(:settings AS jsonb), :status)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name, currency = EXCLUDED.currency, locales = EXCLUDED.locales,
    timezone = EXCLUDED.timezone, distance_unit = EXCLUDED.distance_unit,
    phone_code = EXCLUDED.phone_code, payment_providers = EXCLUDED.payment_providers,
    tax_regime = EXCLUDED.tax_regime, settings = EXCLUDED.settings, status = EXCLUDED.status,
    updated_at = now()
RETURNING id
""")

UPSERT_REGION = text("""
INSERT INTO regions (id, country_id, code, name, timezone, settings, status)
VALUES (:id, :country_id, :code, :name, :timezone, CAST(:settings AS jsonb), :status)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name, timezone = EXCLUDED.timezone, settings = EXCLUDED.settings,
    status = EXCLUDED.status, updated_at = now()
RETURNING id
""")

UPSERT_CITY = text("""
INSERT INTO cities (id, country_id, region_id, code, name, center_lat, center_lng,
                    service_hours, settings, status)
VALUES (:id, :country_id, :region_id, :code, :name, :lat, :lng,
        CAST(:service_hours AS jsonb), CAST(:settings AS jsonb), :status)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name, center_lat = EXCLUDED.center_lat, center_lng = EXCLUDED.center_lng,
    service_hours = EXCLUDED.service_hours, settings = EXCLUDED.settings,
    status = EXCLUDED.status, updated_at = now()
RETURNING id
""")

UPSERT_ZONE = text("""
INSERT INTO zones (id, city_id, name, polygon, min_order, color, status, settings)
VALUES (:id, :city_id, :name, ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326), :min_order,
        :color, :status, '{}'::jsonb)
ON CONFLICT (city_id, name) DO UPDATE SET
    polygon = EXCLUDED.polygon, min_order = EXCLUDED.min_order, color = EXCLUDED.color,
    status = EXCLUDED.status, pause_reason = NULL, paused_until = NULL, updated_at = now()
""")


def box(south: float, west: float, north: float, east: float) -> str:
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return json.dumps({"type": "Polygon", "coordinates": [ring]})


async def seed_markets(conn) -> None:
    for c in COUNTRIES:
        cid = (await conn.execute(UPSERT_COUNTRY, {
            "id": sid("country", c["code"]), **{k: c[k] for k in (
                "code", "name", "currency", "locales", "timezone", "distance_unit", "phone_code",
                "payment_providers", "tax_regime", "status")},
            "settings": json.dumps(c["settings"]),
        })).scalar_one()
        for r in c["regions"]:
            rid = (await conn.execute(UPSERT_REGION, {
                "id": sid("region", r["code"]), "country_id": cid, "code": r["code"], "name": r["name"],
                "timezone": r.get("timezone"), "settings": json.dumps(r["settings"]), "status": r["status"],
            })).scalar_one()
            for city in r["cities"]:
                city_id = (await conn.execute(UPSERT_CITY, {
                    "id": sid("city", city["code"]), "country_id": cid, "region_id": rid, "code": city["code"],
                    "name": city["name"], "lat": city["center"][0], "lng": city["center"][1],
                    "service_hours": json.dumps(city["service_hours"]), "settings": json.dumps(city["settings"]),
                    "status": city["status"],
                })).scalar_one()
                for name, bounds, min_order, status, color in city["zones"]:
                    await conn.execute(UPSERT_ZONE, {
                        "id": sid("zone", city["code"], name), "city_id": city_id, "name": name,
                        "geojson": box(*bounds), "min_order": Decimal(min_order), "color": color, "status": status,
                    })


UPSERT_ADMIN_ROLE = text("""
INSERT INTO admin_role_assignments (id, user_id, role, scope, created_at)
VALUES (:id, :user_id, :role, :scope, now())
ON CONFLICT (user_id, role, scope) DO NOTHING
""")

UPSERT_RESTAURANT = text("""
INSERT INTO restaurants (id, name, slug, owner_id, description, cuisine_types, address, lat, lng,
                         rating, review_count, is_open, opens_at, closes_at,
                         delivery_time_min, delivery_time_max, minimum_order_amount, delivery_fee,
                         currency, country, city, tags, status, is_active, avg_prep_minutes,
                         created_at, updated_at)
VALUES (:id, :name, :slug, :owner_id, :description, :cuisines, CAST(:address AS jsonb), :lat, :lng,
        :rating, :review_count, true, '11:00', '23:00',
        :eta_min, :eta_max, :min_order, :delivery_fee,
        :currency, :country, :city, :tags, 'active', true, 20,
        now(), now())
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name, owner_id = EXCLUDED.owner_id, description = EXCLUDED.description,
    cuisine_types = EXCLUDED.cuisine_types, address = EXCLUDED.address,
    lat = EXCLUDED.lat, lng = EXCLUDED.lng, rating = EXCLUDED.rating,
    delivery_time_min = EXCLUDED.delivery_time_min, delivery_time_max = EXCLUDED.delivery_time_max,
    minimum_order_amount = EXCLUDED.minimum_order_amount, delivery_fee = EXCLUDED.delivery_fee,
    currency = EXCLUDED.currency, country = EXCLUDED.country, city = EXCLUDED.city,
    tags = EXCLUDED.tags, status = 'active', is_active = true, deleted_at = NULL,
    updated_at = now()
RETURNING id
""")

UPSERT_CATEGORY = text("""
INSERT INTO menu_categories (id, restaurant_id, name, sort_order, is_active, created_at)
VALUES (:id, :restaurant_id, :name, :sort_order, true, now())
ON CONFLICT (id) DO UPDATE SET
    restaurant_id = EXCLUDED.restaurant_id, name = EXCLUDED.name,
    sort_order = EXCLUDED.sort_order, is_active = true
""")

UPSERT_ITEM = text("""
INSERT INTO menu_items (id, restaurant_id, category_id, name, description, price, category,
                        is_veg, is_vegan, is_available, allergens, customizations, sort_order,
                        prep_time_minutes, created_at, updated_at)
VALUES (:id, :restaurant_id, :category_id, :name, :description, :price, :category,
        :is_veg, false, true, '{}', CAST(:customizations AS jsonb), :sort_order,
        15, now(), now())
ON CONFLICT (id) DO UPDATE SET
    restaurant_id = EXCLUDED.restaurant_id, category_id = EXCLUDED.category_id,
    name = EXCLUDED.name, description = EXCLUDED.description, price = EXCLUDED.price,
    category = EXCLUDED.category, is_veg = EXCLUDED.is_veg, is_available = true,
    customizations = EXCLUDED.customizations, sort_order = EXCLUDED.sort_order,
    deleted_at = NULL, updated_at = now()
""")


async def upsert_user(conn, email, name, role, market, phone, password=PASSWORD) -> uuid.UUID:
    row = await conn.execute(UPSERT_USER, {
        "id": sid("user", email), "email": email, "phone": phone, "full_name": name,
        "hashed_password": pwd.hash(password), "role": role,
        "country": market["country"] if market else "US",
        "currency": market["currency"] if market else "USD",
        "locale": market["locale"] if market else "en-US",
    })
    return row.scalar_one()


async def seed(database_url: str) -> list[tuple[str, str, str, str]]:
    engine = create_async_engine(database_url)
    logins: list[tuple[str, str, str, str]] = []
    async with engine.begin() as conn:
        await seed_markets(conn)
        for m in MARKETS:
            k = m["key"]
            where = f"{m['country_name']} ▸ {m['state']} ▸ {m['city']}"

            partner_email = f"partner.{k}@example.com"
            partner_id = await upsert_user(conn, partner_email, m["partner"], "restaurant_owner", m, f"{m['phone_prefix']}900")
            logins.append((where, "partner (owns the restaurants)", partner_email, PASSWORD))

            for i, (name, street, area, postal, _lat, _lng) in enumerate(m["customers"], start=1):
                email = f"customer{i}.{k}@example.com"
                user_id = await upsert_user(conn, email, name, "customer", m, f"{m['phone_prefix']}1{i:02d}")
                await conn.execute(UPSERT_ADDRESS, {
                    "id": sid("address", email, "home"), "user_id": user_id,
                    "street": f"{street}, {area}", "city": m["city"], "state": m["state"],
                    "postal_code": postal, "country": m["country"],
                })
                logins.append((where, f"customer · {name}", email, PASSWORD))

            for i, name in enumerate(m["riders"], start=1):
                email = f"rider{i}.{k}@example.com"
                await upsert_user(conn, email, name, "driver", m, f"{m['phone_prefix']}2{i:02d}")
                logins.append((where, f"rider · {name}", email, PASSWORD))

            for r in m["restaurants"]:
                address = {
                    "street": r["street"], "city": m["city"], "state": m["state"], "zip": r["zip"],
                    "country": m["country"], "lat": r["lat"], "lng": r["lng"], "landmark": r["area"],
                }
                rid = (await conn.execute(UPSERT_RESTAURANT, {
                    "id": sid("restaurant", r["slug"]), "name": r["name"], "slug": r["slug"],
                    "owner_id": partner_id, "description": r["description"], "cuisines": r["cuisines"],
                    "address": json.dumps(address), "lat": r["lat"], "lng": r["lng"],
                    "rating": r["rating"], "review_count": 0,
                    "eta_min": r["eta"][0], "eta_max": r["eta"][1],
                    "min_order": Decimal(r["min_order"]), "delivery_fee": Decimal(r["delivery_fee"]),
                    "currency": m["currency"], "country": m["country"], "city": m["city"],
                    "tags": r["tags"],
                })).scalar_one()
                for c_order, (category, items) in enumerate(r["menu"].items()):
                    cid = sid("category", r["slug"], category)
                    await conn.execute(UPSERT_CATEGORY, {"id": cid, "restaurant_id": rid, "name": category, "sort_order": c_order})
                    for i_order, (name, price, veg, desc, custom) in enumerate(items):
                        await conn.execute(UPSERT_ITEM, {
                            "id": sid("item", r["slug"], name), "restaurant_id": rid, "category_id": cid,
                            "name": name, "description": desc, "price": Decimal(price), "category": category,
                            "is_veg": veg, "customizations": json.dumps(custom), "sort_order": i_order,
                        })

        for email, name, country, roles in ADMINS:
            market = next(m for m in MARKETS if m["country"] == country)
            # users.role is the persona the current admin app checks; the scoped
            # permissions come from admin_role_assignments (shared/authz.py).
            persona = "super_admin" if any(r == "super_admin" for r, _ in roles) else "admin"
            user_id = await upsert_user(conn, email, name, persona, market, None, ADMIN_PASSWORD)
            for role, scope in roles:
                await conn.execute(UPSERT_ADMIN_ROLE, {
                    "id": sid("admin_role", email, role, scope), "user_id": user_id, "role": role, "scope": scope,
                })
            logins.append(("Admin console", ", ".join(f"{r} @ {s}" for r, s in roles), email, ADMIN_PASSWORD))

        counts = (await conn.execute(text(
            "SELECT (SELECT count(*) FROM restaurants WHERE slug = ANY(:slugs)),"
            "       (SELECT count(*) FROM menu_items mi JOIN restaurants r ON r.id = mi.restaurant_id WHERE r.slug = ANY(:slugs)),"
            "       (SELECT count(*) FROM users WHERE email LIKE '%@example.com'),"
            "       (SELECT count(*) FROM cities), (SELECT count(*) FROM zones)"
        ), {"slugs": [r["slug"] for m in MARKETS for r in m["restaurants"]]})).one()
    await engine.dispose()
    print(f"Seeded {counts[3]} cities with {counts[4]} zones, {counts[0]} restaurants, "
          f"{counts[1]} menu items, {counts[2]} users.")
    return logins


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logins = asyncio.run(seed(url))
    print("\nTest logins (local/staging only):")
    width = max(len(e) for _, _, e, _ in logins)
    current = None
    for where, who, email, password in logins:
        if where != current:
            print(f"\n  {where}")
            current = where
        print(f"    {email:<{width}}  {password:<15} {who}")
    print()


if __name__ == "__main__":
    main()
