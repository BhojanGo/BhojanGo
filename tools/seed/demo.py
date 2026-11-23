"""Demo data on top of the base seed (tools/seed/demo_data.py), for make dev and QA.

Run after tools/seed/seed.py, never in CI or G1 (the tests keep the base seed),
never in production (refused). Idempotent: every id is a uuid5 of the seed's
namespace, so running it again updates rows instead of duplicating them; orders
already there are kept, and the order on its way is moved to "now" again.

    make seed                                        # base seed, then this
    docker compose ... exec core-api python /srv/tools/seed/demo.py
    tools/railway/qa-runner.sh job demo              # QA (random passwords)

Orders are priced by the real quote engine (QuoteService) for the time they were
placed, so the bill, the pricing snapshot and the receipt agree, then written
with their whole history (paid, accepted, ready, picked up, delivered by the
city's demo rider). The order on its way is carried by the demo rider
simulator's first rider: the simulator has riders of its own (demo_data.py
sim_riders, users.dispatch_pool "demo_sim"), and the demo rider people test with
never gets the simulator's orders.

Ratings: each demo kitchen's months of past orders from the demo customers
(tools/seed/demo_history.py) are written like the others, a share of them rated;
the kitchen's rating and review_count are then recomputed from those rows by the
ratings service's own code (RestaurantRepository.update_rating). Nothing is typed
in, and no rating exists without a delivered order behind it.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_guard import refuse_production  # noqa: E402  (standard library only)

if __name__ == "__main__":
    refuse_production()  # before any database driver is even imported (tools/seed/demo_test.py)

import asyncio  # noqa: E402
import json  # noqa: E402
import time as clock  # noqa: E402
import uuid  # noqa: E402
from datetime import UTC, date, datetime, time, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

import demo_history  # noqa: E402
import seed as base  # noqa: E402  (also puts the backend on sys.path)
from core_api.modules.orders.service.pin import delivery_pin  # noqa: E402
from data import MARKETS, covers, dish_photo, menu_dishes, photo_url  # noqa: E402
from demo_data import ACTIVE, DEMO, ORDERS, PROMOTIONS, SIM_POOL, active_rider  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

sid = base.sid
TZ = {"hyd": ZoneInfo("Asia/Kolkata"), "boi": ZoneInfo("America/Boise")}
DAY_INDEX = base.DAY_INDEX


def history_id(key: str, slug: str, n: int) -> uuid.UUID:
    """A history order's id (demo_history.Planned): stable, so a second run keeps it."""
    return sid("order", "demo", key, "history", slug, str(n))


def active_id(key: str) -> uuid.UUID:
    """The city's order on its way (ACTIVE)."""
    return sid("order", "demo", key, "999")


UPSERT_ADDRESS = text("""
INSERT INTO addresses (id, user_id, label, street, city, state, postal_code, country, lat, lng, is_default,
                       delivery_notes, created_at)
VALUES (:id, :user_id, :label, :street, :city, :state, :postal_code, :country, :lat, :lng,
        :want_default AND NOT EXISTS (SELECT 1 FROM addresses WHERE user_id = :user_id AND is_default AND id <> :id),
        :notes, now())
ON CONFLICT (id) DO UPDATE SET
    label = EXCLUDED.label, street = EXCLUDED.street, city = EXCLUDED.city, state = EXCLUDED.state,
    postal_code = EXCLUDED.postal_code, country = EXCLUDED.country, lat = EXCLUDED.lat, lng = EXCLUDED.lng,
    delivery_notes = EXCLUDED.delivery_notes
""")

UPDATE_KITCHEN = text("""
UPDATE restaurants SET delivery_radius_km = :radius, opens_at = :opens, closes_at = :closes,
    tier = :tier, fssai_number = :fssai, fssai_expires_on = :fssai_expires, paused_reason = NULL, paused_until = NULL,
    is_open = true, busy_extra_minutes = 0, busy_until = NULL,
    created_at = CASE WHEN :new THEN now() - interval '6 days' ELSE now() - interval '14 months' END
WHERE id = :id
""")

INSERT_ORDER = text("""
INSERT INTO orders (id, customer_id, restaurant_id, restaurant_name, driver_id, items, status, market_city, zone_id,
    payment_due_at, accept_due_at, placed_at, rider_assigned_at, picked_up_at, delivery_pin, delivery_proof,
    pickup_lat, pickup_lng, delivery_lat, delivery_lng, subtotal, delivery_fee, taxes, tip, discount, total, currency,
    platform_fee, restaurant_payout, card_fee, estimated_prep_minutes, restaurant_accepted_at, actual_ready_at,
    delivery_distance_km, is_long_distance, status_history, delivery_address, estimated_delivery_time,
    actual_delivery_time, payment_method, payment_intent_id, loyalty_points_earned, loyalty_points_used,
    created_at, updated_at)
VALUES (:id, :customer_id, :restaurant_id, :restaurant_name, :driver_id, CAST(:items AS jsonb), :status, :market_city,
    :zone_id, :payment_due_at, NULL, :placed_at, :rider_assigned_at, :picked_up_at, :pin, CAST(:proof AS jsonb),
    :pickup_lat, :pickup_lng, :delivery_lat, :delivery_lng, :subtotal, :delivery_fee, :taxes, :tip, :discount, :total,
    :currency, :platform_fee, :restaurant_payout, :card_fee, :prep, :accepted_at, :ready_at, :distance, false,
    CAST(:history AS jsonb), CAST(:address AS jsonb), :eta, :delivered_at, :method, :pi, 0, 0, :created_at, :updated_at)
""")

INSERT_SNAPSHOT = text("""
INSERT INTO order_pricing_snapshots (id, order_id, quote_id, currency, total, lines, rule_versions, split, context,
    fee_settings, created_at)
VALUES (:id, :order_id, :quote_id, :currency, :total, CAST(:lines AS jsonb), CAST(:rules AS jsonb), CAST(:split AS jsonb),
        CAST(:context AS jsonb), CAST(:fee_settings AS jsonb), :created_at)
""")

INSERT_PAYMENT = text("""
INSERT INTO payment_intents (id, order_id, user_id, provider, provider_payment_id, amount, refunded_amount, currency,
                             status, idempotency_key, metadata, created_at, updated_at)
VALUES (:id, :order_id, :user_id, 'fake', :ppid, :amount, 0, :currency, 'succeeded', :key,
        '{"demo": true}'::jsonb, :created_at, :created_at)
ON CONFLICT DO NOTHING
""")


class Demo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.logins: list[tuple[str, str, str, str]] = []
        self.users: dict[str, uuid.UUID] = {}
        self.addresses: dict[str, uuid.UUID] = {}
        self.kitchens: dict[str, dict] = {}
        self.people: dict[str, tuple] = {}  # customer key -> (key, name, street, area, postal, lat, lng, notes)
        self.counts = {"orders": 0, "orders_kept": 0, "history": 0, "history_kept": 0, "history_skipped": 0}

    async def run(self, key: str) -> None:
        city = DEMO[key]
        market = next(m for m in MARKETS if m["key"] == key)
        where = f"{market['country_name']} ▸ {market['state']} ▸ {market['city']} (demo)"
        await self.zones(city)
        partner_id = await self.person(market, where, city["partner"], "restaurant_owner", "partner (owns the demo kitchens)")
        # The demo rider people test with (by hand, Maestro): the order history is theirs.
        self.users[f"rider.{key}"] = await self.rider(market, where, city["rider"], None,
                                                      "rider (for testing; delivered the order history)")
        # The simulator's own riders: only they get its orders, and they get nothing else.
        for n, who in enumerate(city["sim_riders"], start=1):
            self.users[who[0]] = await self.rider(market, where, who, SIM_POOL,
                                                  f"rider (demo simulator {n}; don't sign in, it rides this account)")
        for i, k in enumerate(city["kitchens"]):
            await self.kitchen(market, city, k, partner_id, i)
        await self.city_covers(key, market, city)
        for c in city["customers"]:
            await self.customer(market, city, where, c)
        for r in demo_history.regulars(key):
            await self.regular(market, r)
        await self.promotions(key, market)
        await self.favourites_and_card(key, city)

    # ── places and people ────────────────────────────────────────────────────
    async def zones(self, city: dict) -> None:
        city_id = (await self.db.execute(text("SELECT id FROM cities WHERE code = :c"), {"c": city["city_code"]})).scalar_one()
        for name, bounds, min_order, status, color in city["zones"]:
            await self.db.execute(base.UPSERT_ZONE, {
                "id": sid("zone", city["city_code"], name), "city_id": city_id, "name": name,
                "geojson": base.box(*bounds), "min_order": Decimal(min_order), "color": color, "status": status})

    async def person(self, market: dict, where: str, who: tuple, role: str, label: str) -> uuid.UUID:
        email, name, phone = who
        user_id = await base.upsert_user(self.db, email, name, role, market, f"{market['phone_prefix']}{phone}")
        self.logins.append((where, f"{label} · {name}", email, base.password_for(email)))
        return user_id

    async def rider(self, market: dict, where: str, who: tuple, pool: str | None, label: str) -> uuid.UUID:
        """A demo rider, onboarded (documents approved) and in ``pool`` (users.dispatch_pool:
        SIM_POOL for the simulator's riders, None for everyone else)."""
        rider_id = await self.person(market, where, who, "driver", label)
        for kind in ("licence", "insurance", "background_check"):
            await self.db.execute(base.UPSERT_RIDER_DOC, {
                "id": sid("rider_document", who[0], kind), "rider_id": rider_id, "kind": kind,
                "file_key": None if kind == "background_check" else f"rider_document/{rider_id}/seed-{kind}.jpg"})
        await self.db.execute(text("UPDATE users SET dispatch_pool = :pool WHERE id = :id"), {"pool": pool, "id": rider_id})
        return rider_id

    async def customer(self, market: dict, city: dict, where: str, c: tuple) -> None:
        key, name, street, area, postal, lat, lng, notes = c
        email = f"{key}@example.com"
        user_id = await self.person(market, where, (email, name, city["phones"][key]), "customer", "customer")
        self.users[key] = user_id
        self.people[key] = tuple(c)
        home = sid("address", email, "home")
        self.addresses[key] = home
        await self.db.execute(UPSERT_ADDRESS, {
            "id": home, "user_id": user_id, "label": "Home", "street": f"{street}, {area}", "city": market["city"],
            "state": market["state"], "postal_code": postal, "country": market["country"], "lat": lat, "lng": lng,
            "want_default": True, "notes": notes})
        if key == city["customers"][0][0]:
            w_street, w_area, w_postal, w_lat, w_lng = city["work"]
            await self.db.execute(UPSERT_ADDRESS, {
                "id": sid("address", email, "work"), "user_id": user_id, "label": "Work", "street": f"{w_street}, {w_area}",
                "city": market["city"], "state": market["state"], "postal_code": w_postal, "country": market["country"],
                "lat": w_lat, "lng": w_lng, "want_default": False, "notes": "Reception desk, ground floor"})

    async def regular(self, market: dict, r: tuple) -> None:
        """A neighbourhood regular (demo_history.regulars): a demo customer with a home
        address, behind the order history; not listed with the demo logins."""
        key, name, street, area, postal, lat, lng, notes, phone = r
        email = f"{key}@example.com"
        user_id = await base.upsert_user(self.db, email, name, "customer", market, f"{market['phone_prefix']}{phone}")
        self.users[key] = user_id
        self.people[key] = r[:8]
        home = sid("address", email, "home")
        self.addresses[key] = home
        await self.db.execute(UPSERT_ADDRESS, {
            "id": home, "user_id": user_id, "label": "Home", "street": f"{street}, {area}", "city": market["city"],
            "state": market["state"], "postal_code": postal, "country": market["country"], "lat": lat, "lng": lng,
            "want_default": True, "notes": notes})

    async def kitchen(self, market: dict, city: dict, k: dict, owner: uuid.UUID, i: int) -> None:
        address = {"street": k["street"], "city": market["city"], "state": market["state"], "zip": k["zip"],
                   "country": market["country"], "lat": k["lat"], "lng": k["lng"], "landmark": k["area"]}
        rid = (await self.db.execute(base.UPSERT_RESTAURANT, {
            "id": sid("restaurant", k["slug"]), "name": k["name"], "slug": k["slug"], "owner_id": owner,
            "description": k["description"], "cuisines": k["cuisines"], "address": json.dumps(address),
            "lat": k["lat"], "lng": k["lng"], "rating": 0, "review_count": 0,  # from its ratings, after the orders
            "cover_url": None, "logo_url": None, "eta_min": k["eta"][0], "eta_max": k["eta"][1],
            "min_order": Decimal(k["min_order"]), "delivery_fee": Decimal(k["delivery_fee"]),
            "currency": market["currency"], "country": market["country"], "city": market["city"], "tags": k["tags"],
        })).scalar_one()
        first = k["hours"][0]
        fssai = f"{city['fssai_base'] + i}" if city["fssai_base"] else None
        await self.db.execute(UPDATE_KITCHEN, {
            "id": rid, "radius": Decimal(str(k["radius_km"])), "opens": first[1],
            "closes": first[2], "tier": None, "fssai": fssai, "fssai_expires": date(2028, 3, 31) if fssai else None,
            "new": k["new"]})
        await self.db.execute(text("DELETE FROM store_hours WHERE restaurant_id = :r"), {"r": rid})
        for days, opens, closes in k["hours"]:
            for day in days:
                await self.db.execute(text(
                    "INSERT INTO store_hours (id, restaurant_id, weekday, opens, closes) VALUES (:id, :r, :w, :o, :c)"),
                    {"id": sid("hours", k["slug"], day, opens), "r": rid, "w": DAY_INDEX[day],
                     "o": time.fromisoformat(opens), "c": time.fromisoformat(closes)})
        await self.menu(k["slug"], rid, k["menu"])
        self.kitchens[k["slug"]] = {**k, "id": rid}

    async def menu(self, slug: str, rid: uuid.UUID, menu: dict) -> None:
        for c_order, (category, items) in enumerate(menu.items()):
            cid = sid("category", slug, category)
            await self.db.execute(base.UPSERT_CATEGORY, {"id": cid, "restaurant_id": rid, "name": category, "sort_order": c_order})
            for i_order, (name, price, veg, desc, custom) in enumerate(items):
                item_id = sid("item", slug, name)
                await self.db.execute(base.UPSERT_ITEM, {
                    "id": item_id, "restaurant_id": rid, "category_id": cid, "name": name, "description": desc,
                    "price": Decimal(price), "category": category, "is_veg": veg, "sort_order": i_order,
                    "image_url": dish_photo(name)})
                await self.db.execute(text("DELETE FROM menu_item_option_groups WHERE menu_item_id = :i"), {"i": item_id})
                for g_order, g in enumerate(custom):
                    gid = sid("group", slug, name, g["name"])
                    await self.db.execute(base.UPSERT_GROUP, {
                        "id": gid, "restaurant_id": rid, "name": g["name"], "sort_order": g_order,
                        "min_picks": 1 if g.get("required") else 0, "max_picks": g.get("max", 1)})
                    for o_order, o in enumerate(g["options"]):
                        await self.db.execute(base.UPSERT_OPTION, {
                            "id": sid("option", slug, name, g["name"], o["name"]), "group_id": gid, "name": o["name"],
                            "price": Decimal(str(o["price"])), "is_default": o_order == 0 and bool(g.get("required")),
                            "sort_order": o_order})
                    await self.db.execute(base.UPSERT_ITEM_GROUP, {"item": item_id, "group": gid, "sort_order": g_order})
        await self.db.execute(text(
            "DELETE FROM option_groups g WHERE g.restaurant_id = :r AND NOT EXISTS "
            "(SELECT 1 FROM menu_item_option_groups l WHERE l.group_id = g.id)"), {"r": rid})

    async def city_covers(self, key: str, market: dict, city: dict) -> None:
        """No two kitchens in the city share a cover: the base kitchens keep theirs, the
        demo kitchens take the next free photo of one of their own dishes."""
        kitchens = [(r["slug"], menu_dishes(r["menu"])) for r in market["restaurants"]]
        kitchens += [(k["slug"], menu_dishes(k["menu"])) for k in city["kitchens"]]
        for slug, photo in covers(kitchens).items():
            await self.db.execute(text("UPDATE restaurants SET cover_url = :c, logo_url = :l WHERE slug = :s"),
                                  {"c": photo_url(photo, 1600), "l": photo_url(photo, 400), "s": slug})

    async def promotions(self, key: str, market: dict) -> None:
        from core_api.modules.rules.service.templates import slot_for, validate_params

        for template, rkey, name, level, scope, params in PROMOTIONS[key]:
            scope_id = str(sid("restaurant", scope)) if level == "restaurant" else scope
            await self.db.execute(base.UPSERT_RULE, {
                "id": sid("rule", "promotion", template, rkey, level, scope_id), "family": "promotion", "template": template,
                "key": rkey, "slot": slot_for("promotion", template, rkey), "name": name,
                "params": json.dumps(validate_params("promotion", template, params)), "scope_level": level,
                "scope_id": scope_id, "market_scope": market["scope"], "created_by": sid("user", "admin@example.com")})

    async def favourites_and_card(self, key: str, city: dict) -> None:
        user = self.users[city["customers"][0][0]]
        fav = city["favourites"]
        targets = [("restaurant", sid("restaurant", s)) for s in fav["restaurants"]]
        targets += [("item", sid("item", s, dish)) for s, dish in fav["items"]]
        for kind, target in targets:
            await self.db.execute(text(
                "INSERT INTO favourites (user_id, kind, target_id, created_at) VALUES (:u, :k, :t, now()) ON CONFLICT DO NOTHING"),
                {"u": user, "k": kind, "t": target})
        brand, last4 = city["card"]
        await self.db.execute(text("""
            INSERT INTO payment_methods (id, user_id, provider, provider_token, brand, last4, exp_month, exp_year, is_default, created_at)
            VALUES (:id, :u, :provider, :token, :brand, :last4, 12, :year,
                    NOT EXISTS (SELECT 1 FROM payment_methods WHERE user_id = :u AND is_default), now())
            ON CONFLICT DO NOTHING"""), {
            # US pays through Stripe (test mode on QA): its documented test card pm_card_visa, so the
            # saved card really charges there; other countries keep the fake (no provider keys yet).
            "id": sid("payment_method", key, "demo"), "u": user, "brand": brand,
            "provider": "stripe" if city["city_code"].startswith("US-") else "fake",
            "token": "pm_card_visa" if city["city_code"].startswith("US-") else f"pm_fake_demo_{key}",
            "last4": last4, "year": date.today().year + 3})

    # ── orders ───────────────────────────────────────────────────────────────
    def cart(self, slug: str, lines: list) -> list:
        from core_api.modules.pricing.schemas import CartItem, OptionPick

        dishes = {d[0]: d for items in self.kitchens[slug]["menu"].values() for d in items}
        out = []
        for name, qty, picks in lines:
            groups = dishes[name][4]
            options = []
            for grp in groups:
                chosen = picks.get(grp["name"]) or (grp["options"][0]["name"] if grp.get("required") else None)
                if chosen:
                    options.append(OptionPick(group=grp["name"], option=chosen))
            out.append(CartItem(menu_item_id=sid("item", slug, name), quantity=qty, options=options))
        return out

    async def price(self, key: str, customer: str, slug: str, lines: list, tip: str,
                    times: list[datetime]) -> tuple[dict | None, datetime | None, Exception | None]:
        """The first of ``times`` the kitchen was open: the stored quote (lines, split, snapshot context)."""
        from core_api.modules.orders.service.order import OrderService
        from core_api.modules.pricing.schemas import QuoteRequest, Where
        from core_api.modules.pricing.service.quotes import QuoteError, QuoteService, _key
        from shared.redis import get_redis

        req = QuoteRequest(restaurant_id=sid("restaurant", slug), items=self.cart(slug, lines),
                           deliver_to=Where(address_id=self.addresses[customer]), tip=Decimal(tip))
        qs = QuoteService(self.db)
        last: Exception | None = None
        for at in times:
            try:
                out = await qs.quote(self.users[customer], req, now=at)
            except QuoteError as e:
                last = e
                continue
            q = await qs.get(self.users[customer], out.quote_id)
            await (await get_redis()).delete(_key(str(out.quote_id)))
            await OrderService(self.db)._add_payment_fees(q, DEMO[key]["method"])
            return q, at, None
        return None, None, last

    async def order(self, key: str, oid: uuid.UUID, customer: str, slug: str, lines: list, times: list[datetime],
                    active: bool = False, review: tuple | None = None, review_after: timedelta = timedelta(hours=2),
                    history: bool = False) -> bool:
        """Write one demo order (and its rating). False if it couldn't be priced (history only)."""
        tally = "history" if history else "orders"
        now = datetime.now(UTC)
        exists = (await self.db.execute(text("SELECT 1 FROM orders WHERE id = :id"), {"id": oid})).first()
        if exists and not active:
            self.counts[f"{tally}_kept"] += 1
            return True
        if exists:  # the order on its way: on its way now again
            await self.db.execute(text("DELETE FROM order_pricing_snapshots WHERE order_id = :id"), {"id": oid})
            await self.db.execute(text("DELETE FROM payment_intents WHERE order_id = :id"), {"id": oid})
            await self.db.execute(text("DELETE FROM orders WHERE id = :id"), {"id": oid})
        city = DEMO[key]
        q, priced_at, why = await self.price(key, customer, slug, lines, city["tip"], times)
        if q is None or priced_at is None:
            if history:
                self.counts["history_skipped"] += 1
                print(f"demo seed: skipped a past order at {slug} for {customer}: {why}")
                return False
            raise SystemExit(f"demo seed: couldn't price an order at {slug}: {why}")
        k = self.kitchens[slug]
        ctx = q["context"]
        km = float(ctx["distance"]) * (1.609344 if ctx.get("distance_unit") == "mi" else 1)
        ride = max(8, round(km * 3) + 4)
        jitter = int(oid.hex[:2], 16) % 9 if history else 0  # kitchens aren't equally quick every day
        start = now - timedelta(minutes=34) if active else priced_at
        t = {"pending_payment": start, "placed": start + timedelta(minutes=1), "accepted": start + timedelta(minutes=3),
             "preparing": start + timedelta(minutes=4), "rider": start + timedelta(minutes=16 + jitter),
             "ready": start + timedelta(minutes=24 + jitter), "picked_up": start + timedelta(minutes=27 + jitter),
             "delivered": start + timedelta(minutes=27 + jitter + ride)}
        steps = ["placed", "accepted", "preparing", "ready", "picked_up"] + ([] if active else ["delivered"])
        by = {"placed": "system", "accepted": "restaurant", "preparing": "restaurant", "ready": "restaurant",
              "picked_up": "rider", "delivered": "rider"}
        history_rows = [{"status": "pending_payment", "at": start.isoformat()}]
        history_rows += [{"status": s, "at": t[s].isoformat(), "by": by[s]} for s in steps]

        def line_sum(*codes: str) -> Decimal:
            return sum((Decimal(ln["amount"]) for ln in q["lines"] if ln["code"] in codes), Decimal(0)).quantize(Decimal("0.01"))

        market = next(m for m in MARKETS if m["key"] == key)
        cust = self.people[customer]
        address = {"street": f"{cust[2]}, {cust[3]}", "city": market["city"], "state": market["state"], "zip": cust[4],
                   "country": market["country"], "lat": cust[5], "lng": cust[6], "landmark": cust[3]}
        pin = delivery_pin()  # random, as for any order (R27)
        pi = f"fake_pay_demo_{oid.hex[:16]}"
        await self.db.execute(INSERT_ORDER, {
            "id": oid, "customer_id": self.users[customer], "restaurant_id": k["id"], "restaurant_name": q["restaurant_name"],
            "driver_id": self.users[active_rider(key) if active else f"rider.{key}"],
            "items": json.dumps([{**i, "unit_price": float(i["unit_price"]),
                                  "total": float(Decimal(i["unit_price"]) * i["quantity"])} for i in q["items"]]),
            "status": "picked_up" if active else "delivered", "market_city": ctx.get("city"),
            "zone_id": uuid.UUID(ctx["zone_id"]) if ctx.get("zone_id") else None,
            "payment_due_at": start + timedelta(minutes=10), "placed_at": t["placed"], "rider_assigned_at": t["rider"],
            "picked_up_at": t["picked_up"], "pin": pin,
            "proof": None if active else json.dumps({"method": "pin", "at": t["delivered"].isoformat()}),
            "pickup_lat": k["lat"], "pickup_lng": k["lng"], "delivery_lat": cust[5], "delivery_lng": cust[6],
            "subtotal": Decimal(q["food_subtotal"]),
            "delivery_fee": line_sum("delivery_fee", "platform_fee", "service_fee", "small_order_fee", "packaging", "surge", "late_night_fee"),
            "taxes": line_sum("tax"), "tip": line_sum("tip"), "discount": -line_sum("promotion"), "total": Decimal(q["total"]),
            "currency": q["currency"], "platform_fee": Decimal(q["split"]["platform"]),
            "restaurant_payout": Decimal(q["split"]["restaurant"]), "card_fee": Decimal(q["split"].get("card_fee", "0")), "prep": 20, "accepted_at": t["accepted"],
            "ready_at": t["ready"], "distance": Decimal(ctx["distance"]), "history": json.dumps(history_rows),
            "address": json.dumps(address), "eta": t["delivered"], "delivered_at": None if active else t["delivered"],
            "method": city["method"], "pi": pi, "created_at": start, "updated_at": t["picked_up"] if active else t["delivered"],
        })
        await self.db.execute(INSERT_SNAPSHOT, {
            "id": sid("snapshot", str(oid)), "order_id": oid, "quote_id": uuid.UUID(q["quote_id"]), "currency": q["currency"],
            "total": Decimal(q["total"]), "lines": json.dumps(q["lines"]), "rules": json.dumps(q["rules_used"]),
            "split": json.dumps(q["split"]), "context": json.dumps({**ctx, "tax_calculation": q.get("tax_calculation")}),
            "fee_settings": json.dumps(q.get("fee_settings")), "created_at": start})
        minor = 100  # INR and USD both have two decimals
        await self.db.execute(INSERT_PAYMENT, {
            "id": sid("payment", str(oid)), "order_id": oid, "user_id": self.users[customer], "ppid": pi,
            "amount": int(Decimal(q["total"]) * minor), "currency": q["currency"], "key": f"demo-{oid}",
            "created_at": t["placed"]})
        if review and not active:
            rating, comment = review
            # Rated by the customer after delivery (ratings.py: one rating per delivered order).
            rated_at = max(min(t["delivered"] + review_after, now - timedelta(minutes=5)), t["delivered"] + timedelta(minutes=1))
            await self.db.execute(text("""
                INSERT INTO reviews (id, restaurant_id, order_id, customer_id, customer_name, rating, comment, created_at)
                VALUES (:id, :r, :o, :c, :n, :rating, :comment, :at) ON CONFLICT (order_id) DO NOTHING"""), {
                "id": sid("review", str(oid)), "r": k["id"], "o": oid, "c": self.users[customer],
                "n": cust[1].split()[0] + " " + cust[1].split()[-1][0] + ".", "rating": float(rating), "comment": comment,
                "at": rated_at})
        self.counts[tally] += 1
        return True

    async def paid_out(self, key: str) -> list[tuple[date, date]]:
        """Periods a payout run already covers in this city's country: no new past order
        is written into one (it would be owed to the kitchen and rider but never paid)."""
        country = next(m["country"] for m in MARKETS if m["key"] == key)
        rows = (await self.db.execute(text("SELECT period_start, period_end FROM payout_runs WHERE country = :c"),
                                      {"c": country})).all()
        return [(r[0], r[1]) for r in rows]

    async def orders(self, key: str) -> None:
        tz = TZ[key]
        local_now = datetime.now(tz)
        today = local_now.date()
        now = datetime.now(UTC)
        # 1. Each kitchen's past orders and ratings, oldest first (demo_history.py).
        paid_out = await self.paid_out(key)
        started = clock.monotonic()
        for p in demo_history.plan_city(key, today, local_now.replace(tzinfo=None)):
            oid = history_id(key, p.kitchen, p.n)
            if any(a <= p.local.date() < b for a, b in paid_out) and not (
                    await self.db.execute(text("SELECT 1 FROM orders WHERE id = :id"), {"id": oid})).first():
                self.counts["history_skipped"] += 1
                continue
            await self.order(key, oid, p.customer, p.kitchen, p.lines, [p.local.replace(tzinfo=tz).astimezone(UTC)],
                             review=p.review, review_after=p.review_after, history=True)
        print(f"Demo {DEMO[key]['city_code']}: order history written in {clock.monotonic() - started:.0f}s")
        # 2. The demo customer's own recent orders (demo_data.ORDERS).
        for n, (customer, slug, days, hhmm, lines, review) in enumerate(ORDERS[key]):
            at = time.fromisoformat(hhmm)
            # that day, or a day either side if the kitchen was closed (a weekly day off);
            # always finished well before now
            times = [datetime.combine(today - timedelta(days=days + shift), at, tz).astimezone(UTC) for shift in (0, 1, -1, 2)]
            await self.order(key, sid("order", "demo", key, str(n)), customer, slug, lines,
                             [t for t in times if t < now - timedelta(hours=3)], review=review)
        # 3. One order on its way, placed now.
        customer, slug, lines = ACTIVE[key]
        # Priced now if the kitchen is open now, else at the last lunch or dinner it was open.
        fallback = [datetime.combine(today - timedelta(days=d), time(h, 0), tz).astimezone(UTC)
                    for d in range(3) for h in (20, 13)]
        await self.order(key, active_id(key), customer, slug, lines, [now] + [f for f in fallback if f < now], active=True)
        await self.ratings(key)

    async def ratings(self, key: str) -> None:
        """Each demo kitchen's rating and review_count, recomputed from its ratings by the
        ratings service's own code. Ratings an older demo seed wrote with no order behind
        them are removed first: every rating belongs to a delivered order."""
        from core_api.modules.catalog.repository.cache import cache_delete_pattern
        from core_api.modules.catalog.repository.restaurant import RestaurantRepository

        for k in DEMO[key]["kitchens"]:
            rid = self.kitchens[k["slug"]]["id"]
            await self.db.execute(text("""
                DELETE FROM reviews v WHERE v.restaurant_id = :r
                  AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.id = v.order_id AND o.status = 'delivered')"""), {"r": rid})
            await RestaurantRepository(self.db).update_rating(rid)
            await cache_delete_pattern(f"restaurants:{rid}")


async def demo(database_url: str) -> tuple[list, dict]:
    refuse_production()  # every entry point, before the first connection
    for m in ("catalog.models", "identity.models.account", "identity.models.address", "identity.models.admin_role",
              "identity.models.rider", "identity.models.user", "markets.models", "rules.models", "pricing.models",
              "orders.models", "payments.models"):
        __import__(f"core_api.modules.{m}")
    engine = create_async_engine(database_url)
    session = async_sessionmaker(engine, expire_on_commit=False)
    d = None
    async with session() as db:
        d = Demo(db)
        for key in DEMO:
            await d.run(key)
        await db.commit()
        for key in DEMO:
            await d.orders(key)
        await db.commit()
        counts = {}
        for key, city in DEMO.items():
            row = (await db.execute(text("""
                SELECT (SELECT count(*) FROM restaurants r WHERE r.city = :city AND r.status = 'active'),
                       (SELECT count(*) FROM restaurants r WHERE r.slug = ANY(:slugs)),
                       (SELECT count(DISTINCT r.address->>'landmark') FROM restaurants r WHERE r.slug = ANY(:slugs)),
                       (SELECT count(*) FROM menu_items i JOIN restaurants r ON r.id = i.restaurant_id WHERE r.slug = ANY(:slugs)),
                       (SELECT count(*) FROM menu_items i JOIN restaurants r ON r.id = i.restaurant_id
                         WHERE r.slug = ANY(:slugs) AND i.image_url IS NOT NULL),
                       (SELECT count(*) FROM restaurants r WHERE r.slug = ANY(:slugs) AND r.cover_url IS NOT NULL),
                       (SELECT count(*) FROM orders o WHERE o.market_city = :code AND o.id::text = ANY(CAST(:ids AS text[]))),
                       (SELECT count(*) FROM zones z JOIN cities c ON c.id = z.city_id WHERE c.code = :code AND z.status = 'live'),
                       (SELECT count(*) FROM orders o JOIN restaurants r ON r.id = o.restaurant_id
                         WHERE r.slug = ANY(:slugs) AND o.status = 'delivered'),
                       (SELECT count(*) FROM reviews v JOIN restaurants r ON r.id = v.restaurant_id WHERE r.slug = ANY(:slugs)),
                       (SELECT count(*) FROM restaurants r WHERE r.slug = ANY(:slugs) AND r.review_count < 5),
                       (SELECT min(r.rating) || '-' || max(r.rating) FROM restaurants r WHERE r.slug = ANY(:slugs) AND r.review_count >= 5)
            """), {"city": next(m["city"] for m in MARKETS if m["key"] == key), "code": city["city_code"],
                   "slugs": [k["slug"] for k in city["kitchens"]],
                   "ids": [str(sid("order", "demo", key, str(n))) for n in [*range(len(ORDERS[key])), 999]]})).one()
            counts[city["city_code"]] = dict(zip(
                ("kitchens_in_city", "demo_kitchens", "demo_areas", "demo_dishes", "demo_dishes_with_photo",
                 "demo_kitchens_with_cover", "demo_orders", "live_zones", "delivered_at_demo_kitchens", "ratings",
                 "kitchens_new", "rated_range"), row))
    await engine.dispose()
    return d.logins, counts | {"written": d.counts}


def main() -> None:
    refuse_production()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logins, counts = asyncio.run(demo(url))
    for code, c in counts.items():
        print(f"Demo {code}: {c}")
    if base.RANDOM_PASSWORDS:
        out = os.environ.get("SEED_LOGINS_FILE")
        if not out:
            sys.exit("SEED_PASSWORDS=random needs SEED_LOGINS_FILE (the base seed's logins file, outside the repo)")
        path = Path(out)
        # Added to the base seed's file (one file of logins for QA); the demo's own rows replaced.
        rows = path.read_text(encoding="utf-8").splitlines() if path.exists() else ["where\twho\temail\tpassword"]
        mine = {e for _, _, e, _ in logins}
        rows = [r for r in rows if r.split("\t")[2:3] not in ([e] for e in mine)]
        rows += ["\t".join(row) for row in logins]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        os.chmod(out, 0o600)
        print(f"{len(logins)} demo logins with random passwords added to {out} (passwords not printed).")
        return
    print("\nDemo logins (local only; seed phones sign in with OTP 123456):")
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
