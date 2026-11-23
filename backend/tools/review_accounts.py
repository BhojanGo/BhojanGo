"""Store review accounts (R19): what Apple and Google reviewers sign in with.

Run ONCE, in production, at go-live (it may also run on a dev stack to try it; it
refuses on QA). Inside the core-api container:

    python tools/review_accounts.py --email-domain <your domain>

It creates, in one transaction:

- a city "App Review" (code <region>-REV, or --code) in a live country (--country,
  default US), in the region of one of its live cities (else a beta one; or --region). Its one
  delivery zone is a small square of open sea (default for US: the North Pacific
  around 30N 140W, about 2,000 km from any coast), so no real address is ever in
  it. The city is *review-only* (settings ``review_only``; markets.service.review):
  hidden from every public list, locate, discover and kitchen page, except for the
  three accounts below (settings ``review_accounts``).
- review.customer@<domain>: a customer with a saved "Home" address inside the zone;
- review.kitchen@<domain>: a kitchen owner with an approved, open kitchen there
  ("BhojanGo Review Restaurant") and a small menu;
- review.delivery@<domain>: an approved delivery partner (phone step, licence,
  insurance and background check done; no documents are stored).

Each account gets a random password, printed once at the end and nowhere else
(not in a file, not in the logs): put them straight into App Store Connect, Play
Console and the team's password manager. Running it again refuses (the city or an
email already exists); to start over, delete those rows first.

Only the review accounts can price or order there (R20). The review customer's
orders there cost $0.00 and are placed with no payment provider; with REVIEW_SIM=1
the worker's review simulator (worker app/demo_sim/review.py) plays the review
kitchen and delivery partner up to delivered. No real delivery partner is ever near
the zone, so an order placed there is not offered to anyone real.
"""
import argparse
import asyncio
import json
import os
import re
import secrets
import sys
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# The backend: backend/ on a checkout, /srv in the core-api container (this file is <it>/tools/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CITY_NAME = "App Review"
KITCHEN_NAME = "BhojanGo Review Restaurant"
HALF_SIDE = 0.05  # degrees: the zone is a square about 11 km across
# Open sea, far from any coast, per country. Others: pass --centre LAT,LNG.
CENTRES = {"US": (30.0, -140.0)}
CODE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}-[A-Z0-9]{2,4}$")  # markets.schemas.CityCreate
DOMAIN = re.compile(r"^(?=.{3,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
ACCOUNTS = (  # (key, role, full name)
    ("customer", "customer", "Review Customer"),
    ("kitchen", "restaurant_owner", "Review Restaurant"),
    ("delivery", "driver", "Review Delivery"),
)
MENU = {  # category -> (name, price, veg, description)
    "Mains": [("Paneer butter masala", "11.50", True, "Cottage cheese in a tomato and butter sauce"),
              ("Chicken biryani", "13.00", False, "Basmati rice layered with spiced chicken"),
              ("Dal tadka", "9.00", True, "Yellow lentils tempered with cumin and garlic")],
    "Breads": [("Butter naan", "3.00", True, "From the tandoor"),
               ("Garlic naan", "3.50", True, "With garlic and coriander")],
    "Drinks": [("Mango lassi", "4.50", True, "Yoghurt and mango")],
}


class Refused(Exception):
    """Why the command won't run (printed as is, exit 1)."""


def environment_problem(env: Mapping[str, str]) -> str | None:
    """It never runs on QA: QA has its own seeded test accounts."""
    for var in ("APP_ENV", "RAILWAY_ENVIRONMENT_NAME", "ENVIRONMENT"):
        if env.get(var, "").strip().lower() == "qa":
            return f"{var}={env[var]!r}: review accounts are made in production at go-live (or on a dev stack), never on QA"
    return None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create the app store review accounts in a hidden review-only city.")
    p.add_argument("--email-domain", required=True, help="Domain of the review emails, e.g. one the team owns")
    p.add_argument("--country", default="US", help="A live country (default US)")
    p.add_argument("--region", help="Region code for the city (default: the region of one of the country's live cities)")
    p.add_argument("--code", help="City code (default <region>-REV)")
    p.add_argument("--centre", help="LAT,LNG of the zone's centre: open sea (default for US: 30,-140)")
    p.add_argument("--postal-code", default="00000",
                   help="Postal code on the review addresses (a real one of the region if sales tax needs it)")
    a = p.parse_args(argv)
    a.email_domain = a.email_domain.strip().lower()
    if not DOMAIN.match(a.email_domain):
        p.error(f"--email-domain {a.email_domain!r} is not a domain name")
    a.country = a.country.strip().upper()
    a.region = a.region.strip().upper() if a.region else None
    a.code = a.code.strip().upper() if a.code else None
    if a.centre:
        try:
            lat, lng = (float(x) for x in a.centre.split(","))
        except ValueError:
            p.error("--centre is LAT,LNG, e.g. 30,-140")
        if not (-85 <= lat <= 85 and -179 <= lng <= 179):
            p.error("--centre is outside the map")
        a.centre = (lat, lng)
    return a


def emails(domain: str) -> dict[str, str]:
    return {key: f"review.{key}@{domain}" for key, _, _ in ACCOUNTS}


def city_code(region_code: str, code: str | None) -> str:
    out = code or f"{region_code}-REV"
    if not CODE.match(out) or not out.startswith(region_code + "-"):
        raise Refused(f"City code {out!r} must look like {region_code}-XXX (2 to 4 letters or digits)")
    return out


def centre_for(country: str, centre: tuple[float, float] | None) -> tuple[float, float]:
    if centre:
        return centre
    if country not in CENTRES:
        raise Refused(f"Pass --centre LAT,LNG: a spot of open sea for the {country} review zone (no real address may be in it)")
    return CENTRES[country]


def square(lat: float, lng: float, half: float = HALF_SIDE) -> dict:
    """The zone: a GeoJSON square around (lat, lng)."""
    s, n, w, e = lat - half, lat + half, lng - half, lng + half
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def inside(polygon: dict, lat: float, lng: float) -> bool:
    ring = polygon["coordinates"][0]
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return min(xs) < lng < max(xs) and min(ys) < lat < max(ys)


@dataclass
class Login:
    who: str
    email: str
    password: str


async def create(db, args: argparse.Namespace) -> list[Login]:  # type: ignore[no-untyped-def]
    """Everything in one transaction (the caller commits)."""
    from sqlalchemy import func, select, text

    from core_api.modules.catalog.models.menu import MenuCategory, MenuItem
    from core_api.modules.catalog.models.restaurant import Restaurant
    from core_api.modules.identity.models.address import Address
    from core_api.modules.identity.models.rider import RiderDocument, RiderProfile
    from core_api.modules.identity.models.user import User
    from core_api.modules.identity.service.passwords import hash_password
    from core_api.modules.legal import service as legal
    from core_api.modules.markets.models import City, Country, Region
    from core_api.modules.markets.service import review

    country = (await db.execute(select(Country).where(Country.code == args.country))).scalar_one_or_none()
    if country is None or country.status not in ("live", "beta"):
        raise Refused(f"Country {args.country} isn't live in Markets")
    if (country.settings or {}).get("fssai_required"):
        raise Refused(f"{args.country} needs a food licence per restaurant; the review restaurant would be hidden. Use a country without one.")
    ref = None
    if args.region:
        region = (await db.execute(select(Region).where(Region.code == args.region, Region.country_id == country.id))).scalar_one_or_none()
        if region is None:
            raise Refused(f"No region {args.region} in {args.country}")
    else:
        # A live city's region (production: Boise); a beta one when none is live yet (a dev or CI stack).
        ref = (await db.execute(select(City).where(City.country_id == country.id, City.status.in_(("live", "beta")))
                                .order_by(City.status != "live", City.name))).scalars().first()
        if ref is None:
            raise Refused(f"{args.country} has no live or beta city: pass --region")
        region = await db.get(Region, ref.region_id)
    code = city_code(region.code, args.code)
    lat, lng = centre_for(country.code, args.centre)
    zone = square(lat, lng)

    # Idempotent by refusing: never a second review city, never a reused email.
    cities = (await db.execute(select(City).where(City.country_id == country.id))).scalars().all()
    if any(c.code == code or review.is_review_only(c.settings) or c.name.lower() == CITY_NAME.lower() for c in cities):
        raise Refused(f"A review city already exists in {country.code} (or the code {code} is taken): nothing was changed")
    wanted = emails(args.email_domain)
    taken = (await db.execute(select(User.email).where(func.lower(User.email).in_(list(wanted.values()))))).scalars().all()
    if taken:
        raise Refused(f"These accounts already exist: {', '.join(sorted(taken))}. Nothing was changed.")
    slug = f"bhojango-review-kitchen-{code.lower()}"
    if (await db.execute(select(Restaurant.id).where(Restaurant.slug == slug))).first():
        raise Refused(f"A restaurant with the slug {slug} already exists. Nothing was changed.")

    now = datetime.now(UTC)
    logins: list[Login] = []
    users: dict[str, User] = {}
    for key, role, name in ACCOUNTS:
        password = secrets.token_urlsafe(18)
        u = User(email=wanted[key], full_name=name, hashed_password=hash_password(password), role=role,
                 country=country.code, preferred_currency=country.currency, preferred_locale=country.locales[0],
                 is_active=True, is_verified=True, is_phone_verified=role == "driver", password_changed_at=now)
        db.add(u)
        users[key] = u
        logins.append(Login({"customer": "BhojanGo", "kitchen": "BhojanGo Restaurant", "delivery": "BhojanGo Delivery"}[key],
                            wanted[key], password))
    await db.flush()

    tz = (ref.timezone if ref else None) or region.timezone or country.timezone
    city = City(country_id=country.id, region_id=region.id, code=code, name=CITY_NAME, timezone=tz, service_hours=None,
                center_lat=lat, center_lng=lng, status="live",
                settings={review.REVIEW_ONLY: True, review.REVIEW_ACCOUNTS: [str(u.id) for u in users.values()]})
    db.add(city)
    await db.flush()
    await db.execute(text(
        "INSERT INTO zones (id, city_id, name, polygon, min_order, color, status, settings) "
        "VALUES (:id, :city, 'Review zone', ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326), NULL, '#0B5D66', 'live', '{}'::jsonb)"),
        {"id": uuid.uuid4(), "city": city.id, "g": json.dumps(zone)})

    home = (lat + 0.01, lng)  # about a kilometre from the kitchen
    assert inside(zone, *home) and inside(zone, lat, lng)
    db.add(Address(user_id=users["customer"].id, label="Home", street="1 Review Way", city=CITY_NAME, state=region.name,
                   postal_code=args.postal_code, country=country.code, lat=home[0], lng=home[1], is_default=True))

    kitchen = Restaurant(
        name=KITCHEN_NAME, slug=slug, owner_id=users["kitchen"].id,
        description="A restaurant for app store review. It isn't shown to customers.",
        cuisine_types=["Indian"], tags=[], currency=country.currency, country=country.code, city=CITY_NAME,
        address={"street": "2 Review Way", "city": CITY_NAME, "state": region.name, "zip": args.postal_code, "country": country.code,
                 "lat": lat, "lng": lng, "landmark": "Review zone"},
        lat=lat, lng=lng, is_open=True, status="active", is_active=True, delivery_radius_km=Decimal("10"),
        delivery_time_min=25, delivery_time_max=40, minimum_order_amount=Decimal("0"), delivery_fee=Decimal("0"))
    db.add(kitchen)
    await db.flush()
    for c_order, (category, items) in enumerate(MENU.items()):
        cat = MenuCategory(restaurant_id=kitchen.id, name=category, sort_order=c_order)
        db.add(cat)
        await db.flush()
        for i_order, (name, price, veg, desc) in enumerate(items):
            db.add(MenuItem(restaurant_id=kitchen.id, category_id=cat.id, name=name, description=desc, price=Decimal(price),
                            category=category, is_veg=veg, sort_order=i_order))

    rider = users["delivery"]
    db.add(RiderProfile(user_id=rider.id, date_of_birth=date(1990, 1, 1), vehicle="car"))
    for kind in ("licence", "insurance", "background_check"):  # approved, with no stored file
        db.add(RiderDocument(rider_id=rider.id, kind=kind, status="approved", file_key=None, reviewed_at=now,
                             note="App store review account"))

    for key, role, _ in ACCOUNTS:
        await legal.record_acceptance(db, users[key].id, country.code, legal.ROLE_KINDS[role],
                                      language=country.locales[0], source="app")
    await db.flush()
    return logins


async def run(args: argparse.Namespace) -> list[Login]:
    from shared.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            logins = await create(db, args)
            await db.commit()
        except BaseException:
            await db.rollback()
            raise
    return logins


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    problem = environment_problem(os.environ if env is None else env)
    if problem:
        print(f"review_accounts: REFUSED: {problem}", file=sys.stderr)
        return 1
    args = parse_args(argv)
    try:
        logins = asyncio.run(run(args))
    except Refused as e:
        print(f"review_accounts: REFUSED: {e}", file=sys.stderr)
        return 1
    print(f"Review city {CITY_NAME!r} created. These passwords are shown once; copy them into the store consoles now:\n")
    for row in logins:
        print(f"  {row.who:<18} {row.email:<40} {row.password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
