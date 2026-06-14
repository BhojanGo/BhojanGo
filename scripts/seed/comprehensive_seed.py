#!/usr/bin/env python3
"""
Comprehensive data seeding script for BhojanGo.
Generates SQL file then executes it against the database.
Stdlib only: random, uuid, json, urllib.request, subprocess, os, time, hashlib.
"""

import hashlib
import json
import os
import random
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timedelta

# ─── Deterministic seed ───────────────────────────────────────────────────────
random.seed(42)

# ─── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = "/Users/raghuram/PycharmProjects/BhojanGo/BhojanGo"
IMAGES_DIR = os.path.join(PROJECT_ROOT, "apps/web/public/images")
SQL_FILE = os.path.join(PROJECT_ROOT, "scripts/seed/comprehensive_seed.sql")
DB_URL = "postgresql://bhojango:bhojango_dev@localhost:5432/bhojango"

# ─── User IDs (from existing seed) ───────────────────────────────────────────
CUSTOMERS = [
    "11111111-1111-1111-1111-111111111101",
    "11111111-1111-1111-1111-111111111102",
    "11111111-1111-1111-1111-111111111103",
    "11111111-1111-1111-1111-111111111104",
    "11111111-1111-1111-1111-111111111105",
]
OWNER_IN  = "22222222-2222-2222-2222-222222222201"   # owner1 – India
OWNER_US  = "22222222-2222-2222-2222-222222222202"   # owner2 – USA
DRIVERS = [
    "33333333-3333-3333-3333-333333333301",
    "33333333-3333-3333-3333-333333333302",
    "33333333-3333-3333-3333-333333333303",
]
RR_ADMIN = "0518056d-1509-4b63-867b-08a2e3424467"
ALL_USERS = CUSTOMERS + [OWNER_IN, OWNER_US, DRIVERS[0], DRIVERS[1], DRIVERS[2], RR_ADMIN]

# ─── City → lat/lng (approximate) ────────────────────────────────────────────
CITY_COORDS = {
    # IN cities
    "Bengaluru": (12.9716, 77.5946),
    "Mumbai":    (19.0760, 72.8777),
    "Delhi":     (28.6139, 77.2090),
    "Chennai":   (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Pune":      (18.5204, 73.8567),
    "Kolkata":   (22.5726, 88.3639),
    "Kochi":     (9.9312,  76.2673),
    "Jaipur":    (26.9124, 75.7873),
    # US cities
    "New York":      (40.7128,  -74.0060),
    "Los Angeles":   (34.0522, -118.2437),
    "Chicago":       (41.8781,  -87.6298),
    "Houston":       (29.7604,  -95.3698),
    "Phoenix":       (33.4484, -112.0740),
    "Philadelphia":  (39.9526,  -75.1652),
    "San Antonio":   (29.4241,  -98.4936),
    "San Diego":     (32.7157, -117.1611),
    "Dallas":        (32.7767,  -96.7970),
    "Austin":        (30.2672,  -97.7431),
    "Seattle":       (47.6062, -122.3321),
    "Miami":         (25.7617,  -80.1918),
    "Boston":        (42.3601,  -71.0589),
    "Atlanta":       (33.7490,  -84.3880),
}

IN_CITIES  = ["Bengaluru", "Mumbai", "Delhi", "Chennai", "Hyderabad", "Pune", "Kolkata", "Kochi", "Jaipur"]
US_CITIES  = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
              "San Antonio", "San Diego", "Dallas", "Austin", "Seattle", "Miami", "Boston", "Atlanta"]

# ─── Chains ───────────────────────────────────────────────────────────────────
US_CHAINS = [
    ("Domino's Pizza",    "dominos-pizza",     ["Pizza", "American"]),
    ("KFC",               "kfc",               ["American", "Fast Food"]),
    ("McDonald's",        "mcdonalds",         ["American", "Fast Food"]),
    ("Burger King",       "burger-king",       ["American", "Burgers"]),
    ("Pizza Hut",         "pizza-hut",         ["Pizza", "American"]),
    ("Starbucks",         "starbucks",         ["Cafe", "Bakery"]),
    ("Subway",            "subway",            ["American", "Sandwiches"]),
    ("Taco Bell",         "taco-bell",         ["Mexican", "Fast Food"]),
    ("Dunkin' Donuts",    "dunkin-donuts",     ["Cafe", "Bakery", "Desserts"]),
]
IN_CHAINS = [
    ("Haldiram's",       "haldirams",        ["Indian", "Snacks", "Bakery"]),
    ("Saravana Bhavan",  "saravana-bhavan",  ["South Indian", "Vegetarian"]),
    ("Biryani House",    "biryani-house",    ["Indian", "Biryani"]),
    ("Dosa Express",     "dosa-express",     ["South Indian", "Vegetarian"]),
    ("Hatti Kaapi",      "hatti-kaapi",      ["South Indian", "Cafe"]),
    ("Kathi Junction",   "kathi-junction",   ["Indian", "Street Food"]),
]

# ─── Independent restaurant templates ─────────────────────────────────────────
IN_INDEPENDENT_NAMES = [
    "Spice Garden", "Taj Palace", "Royal Punjab", "Maharaja's Kitchen", "Chennai Chaat House",
    "Kerala Spice", "Amritsar Dhaba", "Punjabi Tadka", "Coastal Catch", "Curry House",
    "Chaat Corner", "Bengaluru Bites", "Hyderabad Dum", "Mysore Palace", "Rajasthani Rasoi",
    "Gujarati Thali", "Maharashtrian Misal", "Tamil Nadu Delights", "Awadhi Kitchen",
    "Peshawar Grill", "Nizam's Kitchen", "Bangalore Express", "Mumbai Spice", "Kolhapuri Spice",
    "Uttar Pradesh Kitchen", "Bengali Baabu", "Pune Punjabi", "Delhi Darbar", "Jaipur Junction",
    "Goan Flavors", "Lucknowi Corner", "Chettinad House", "Andhra Spice", "Mughal Darbar",
    "North Indian Junction", "South Indian Sambar", "Kashmir Kitchen", "Sindhi Sweets",
    "Maharashtrian Kitchen", "Punjabi Junction", "Gujarat Griddle", "Tamil Taste",
    "Karnataka Kitchen", "Telangana Bites",
]

US_INDEPENDENT_NAMES = [
    "The Burger Joint", "Szechuan Palace", "Mama's Italian", "Tokyo Ramen", "Thai Orchid",
    "Mexico Lindo", "Greek Taverna", "BBQ Smokehouse", "Seoul Kitchen", "Mediterranean Grill",
    "Fish & Chips Co", "Ember Pizza", "Rainbow Salad Bar", "Crepe Station", "Noodle Nirvana",
    "Patty Melt", "The Taco Truck", "Dim Sum House", "Ramen Yama", "Poke Bowl Paradise",
    "Burrito Blaze", "Falafel King", "Wok & Roll", "Bangkok Basil", "Milan Express",
    "The Wing Spot", "Ribs & Rubs", "Sushi Zen", "Tandoori Oven", "Cajun Kitchen",
    "Philly Steaks", "Hawaiian Poke", "Pizza Primo", "Green Garden Vegan", "BBQ Brothers",
    "Chipotle Fresh", "Pho Saigon", "Korean BBQ House", "Canton Dim Sum", "Cairo Kitchen",
]

# ─── Menu item templates per cuisine ──────────────────────────────────────────
STARTER_NAMES  = ["Spring Rolls", "Samosas (2)", "Chicken Wings (6pc)", "Paneer Tikka",
                  "Crispy Calamari", "Garlic Bread", "Onion Rings", "Hummus Platter",
                  "Aloo Tikki", "Pav Bhaji", "Chicken 65", "Fish Amritsari", "Mirchi Vada"]
MAIN_NAMES     = ["Butter Chicken", "Palak Paneer", "Chicken Biryani", "Lamb Rogan Josh",
                  "Fish Curry", "Dal Makhani", "Shahi Paneer", "Mutton Korma",
                  "Kung Pao Chicken", "Beef Broccoli", "Orange Chicken", "Mapo Tofu",
                  "Pasta Bolognese", "Chicken Parmesan", "Grilled Salmon", "Ribeye Steak"]
BREAD_RICE     = ["Butter Naan", "Garlic Naan", "Roti", "Jeera Rice", "Biryani Rice",
                  "Steamed Basmati", "Lachha Paratha", "Pulao", "Naan", "Kulcha"]
DESSERT_NAMES  = ["Gulab Jamun", "Rasmalai", "Ice Cream Sundae", "Cheesecake",
                  "Chocolate Lava Cake", "Gajar Ka Halwa", "Tiramisu", "Brownie Sundae"]
BEVERAGE_NAMES = ["Masala Chai", "Filter Coffee", "Mango Lassi", "Fresh Lime Soda",
                  "Cold Coffee", "Green Tea", "Rose Sharbat", "Jaljeera", "Buttermilk"]
COMBO_NAMES    = ["Family Feast", "Lunch Special", "Dinner for Two", "Student Combo",
                  "Kids Meal", "Party Pack", "Couple's Delight", "Value Lunch"]

US_PRICE_RANGE   = (3.0, 25.0)
IN_PRICE_RANGE   = (50.0, 800.0)

PLATFORMS = ["ios", "android", "web"]
NOTIF_TYPES = ["order_confirmed", "driver_assigned", "order_delivered", "promo", "payment_received"]
NOTIF_CHANNEL = "push"

# ═══════════════════════════════════════════════════════════════════════════════
# IMAGE DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

def download_with_retry(url: str, dest: str) -> bool:
    """Download image, retry once on failure."""
    for attempt in range(2):
        try:
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception:
            if attempt == 0:
                time.sleep(1)
    return False


def download_images(restaurant_slugs: list[str], all_restaurant_slugs: list[str]):
    """Download restaurant cover images and 30 menu template images."""
    restaurant_dir = os.path.join(IMAGES_DIR, "restaurants")
    menu_dir       = os.path.join(IMAGES_DIR, "menu")
    os.makedirs(restaurant_dir, exist_ok=True)
    os.makedirs(menu_dir, exist_ok=True)

    downloaded = 0

    # Restaurant cover images (unique slugs only)
    for slug in all_restaurant_slugs:
        dest = os.path.join(restaurant_dir, f"{slug}.jpg")
        if os.path.exists(dest):
            continue
        url = f"https://picsum.photos/seed/{slug}/800/600"
        if download_with_retry(url, dest):
            downloaded += 1
        time.sleep(2)

    # Menu template images
    for i in range(1, 31):
        dest = os.path.join(menu_dir, f"food_{i}.jpg")
        if os.path.exists(dest):
            continue
        url = f"https://picsum.photos/seed/menu_{i}/400/300"
        if download_with_retry(url, dest):
            downloaded += 1
        time.sleep(2)

    return downloaded


# ═══════════════════════════════════════════════════════════════════════════════
# DATA GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def make_uuid(base: str, suffix: str) -> str:
    h = hashlib.sha256(f"{base}:{suffix}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def generate_restaurants() -> tuple[list[dict], list[str]]:
    """Generate 95 restaurants (45 IN + 50 US). Returns (restaurants, all_slugs)."""
    restaurants = []
    all_slugs = []

    # Helper to pick rating
    def rating(): return round(random.uniform(3.5, 4.9), 1)
    def review_count(): return random.randint(15, 800)

    # ── India: 45 restaurants ──────────────────────────────────────────────
    # 9 chains × 3 cities each ≈ 27 chain + 18 independent
    in_cities_sample = random.sample(IN_CITIES, 9)

    # Chain restaurants (3 locations each for IN chains)
    for chain_name, chain_slug, cuisines in IN_CHAINS:
        for city in in_cities_sample[:3]:
            slug = f"{chain_slug}-{city.lower().replace(' ', '-')}"
            lat, lng = CITY_COORDS[city]
            lat += random.uniform(-0.05, 0.05)
            lng += random.uniform(-0.05, 0.05)
            r = {
                "id": str(uuid.uuid4()),
                "name": chain_name,
                "slug": slug,
                "owner_id": OWNER_IN,
                "description": f"Popular {chain_name} outlet in {city}",
                "cuisine_types": cuisines,
                "address": {"street": f"{random.randint(1,999)} Main Road", "city": city,
                            "state": "", "zip": "", "country": "IN"},
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "rating": rating(),
                "review_count": review_count(),
                "is_open": True,
                "delivery_time_min": random.randint(20, 35),
                "delivery_time_max": random.randint(40, 55),
                "minimum_order_amount": random.choice([100, 150, 200]),
                "delivery_fee": random.choice([20, 30, 40]),
                "currency": "INR",
                "country": "IN",
                "city": city,
                "status": "active",
                "is_active": True,
                "pricing_model": random.choice(["percentage_commission", "flat_fee_per_order"]),
                "commission_rate": 0.15,
                "flat_fee_per_order": 20.0,
                "monthly_subscription_fee": 0.0,
                "delivery_radius_km": random.uniform(3.0, 8.0),
                "avg_prep_minutes": random.randint(20, 40),
            }
            restaurants.append(r)
            all_slugs.append(slug)

    # Independent IN restaurants
    in_indep = random.sample(IN_INDEPENDENT_NAMES, 18)
    for i, name in enumerate(in_indep):
        city = random.choice(IN_CITIES)
        _sn = name.lower().replace(' ', '-').translate(str.maketrans('', '', "'"))
        _sc = city.lower().replace(' ', '-')
        slug = f"{_sn}-{_sc}"
        cuisines = random.sample([["Indian", "North Indian"], ["South Indian"], ["Indian", "Biryani"],
                                   ["Chinese"], ["Indian", "Street Food"], ["Bakery", "Desserts"]], 1)[0]
        r = {
            "id": str(uuid.uuid4()),
            "name": name,
            "slug": slug,
            "owner_id": OWNER_IN,
            "description": f"Authentic {cuisines[0]} cuisine in {city}",
            "cuisine_types": cuisines,
            "address": {"street": f"{random.randint(1,999)} Food Street", "city": city,
                        "state": "", "zip": "", "country": "IN"},
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "rating": rating(),
            "review_count": review_count(),
            "is_open": True,
            "delivery_time_min": random.randint(25, 40),
            "delivery_time_max": random.randint(45, 65),
            "minimum_order_amount": random.choice([100, 150, 200, 250]),
            "delivery_fee": random.choice([20, 30, 40, 50]),
            "currency": "INR",
            "country": "IN",
            "city": city,
            "status": "active",
            "is_active": True,
            "pricing_model": random.choice(["percentage_commission", "flat_fee_per_order", "monthly_subscription"]),
            "commission_rate": random.choice([0.12, 0.15, 0.18]),
            "flat_fee_per_order": random.choice([15.0, 20.0, 25.0]),
            "monthly_subscription_fee": random.choice([0.0, 499.0, 999.0]),
            "delivery_radius_km": random.uniform(3.0, 7.0),
            "avg_prep_minutes": random.randint(25, 45),
        }
        restaurants.append(r)
        all_slugs.append(slug)

    # ── USA: 50 restaurants ────────────────────────────────────────────────
    # US chains: 9 chains × 2-5 cities (total ~30 chain), 20 independent
    for chain_name, chain_slug, cuisines in US_CHAINS:
        num_locs = random.randint(2, 5)
        cities = random.sample(US_CITIES, num_locs)
        for city in cities:
            slug = f"{chain_slug}-{city.lower().replace(' ', '-')}"
            lat, lng = CITY_COORDS[city]
            lat += random.uniform(-0.05, 0.05)
            lng += random.uniform(-0.05, 0.05)
            r = {
                "id": str(uuid.uuid4()),
                "name": chain_name,
                "slug": slug,
                "owner_id": OWNER_US,
                "description": f"{chain_name} in {city}",
                "cuisine_types": cuisines,
                "address": {"street": f"{random.randint(1,9999)} Main St", "city": city,
                            "state": "", "zip": "", "country": "US"},
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "rating": rating(),
                "review_count": review_count(),
                "is_open": True,
                "delivery_time_min": random.randint(15, 30),
                "delivery_time_max": random.randint(30, 50),
                "minimum_order_amount": random.choice([10, 12, 15, 18, 20]),
                "delivery_fee": random.choice([2.99, 3.49, 3.99, 4.99]),
                "currency": "USD",
                "country": "US",
                "city": city,
                "status": "active",
                "is_active": True,
                "pricing_model": random.choice(["percentage_commission", "flat_fee_per_order", "monthly_subscription"]),
                "commission_rate": random.choice([0.15, 0.18, 0.20]),
                "flat_fee_per_order": random.choice([2.0, 3.0, 4.0]),
                "monthly_subscription_fee": random.choice([0.0, 499.0, 999.0]),
                "delivery_radius_km": random.uniform(4.0, 10.0),
                "avg_prep_minutes": random.randint(15, 35),
            }
            restaurants.append(r)
            all_slugs.append(slug)

    # Independent US restaurants
    us_indep = random.sample(US_INDEPENDENT_NAMES, 20)
    for i, name in enumerate(us_indep):
        city = random.choice(US_CITIES)
        _sn = name.lower().replace(' ', '-').translate(str.maketrans('', '', "'"))
        _sc = city.lower().replace(' ', '-')
        slug = f"{_sn}-{_sc}"
        lat, lng = CITY_COORDS[city]
        lat += random.uniform(-0.04, 0.04)
        lng += random.uniform(-0.04, 0.04)
        cuisines = random.sample([["American"], ["Chinese", "Asian"], ["Italian"], ["Mexican"],
                                   ["Japanese", "Sushi"], ["Thai"], ["Mediterranean"],
                                   ["Healthy", "Salads"], ["BBQ"], ["Seafood"]], 1)[0]
        r = {
            "id": str(uuid.uuid4()),
            "name": name,
            "slug": slug,
            "owner_id": OWNER_US,
            "description": f"{name} – {cuisines[0]} cuisine in {city}",
            "cuisine_types": cuisines,
            "address": {"street": f"{random.randint(1,9999)} Broadway", "city": city,
                        "state": "", "zip": "", "country": "US"},
            "lat": round(lat, 6),
            "lng": round(lng, 6),
            "rating": rating(),
            "review_count": review_count(),
            "is_open": True,
            "delivery_time_min": random.randint(20, 35),
            "delivery_time_max": random.randint(35, 55),
            "minimum_order_amount": random.choice([10, 12, 15, 18, 20, 25]),
            "delivery_fee": random.choice([2.99, 3.49, 3.99, 4.99, 5.99]),
            "currency": "USD",
            "country": "US",
            "city": city,
            "status": "active",
            "is_active": True,
            "pricing_model": random.choice(["percentage_commission", "flat_fee_per_order", "monthly_subscription"]),
            "commission_rate": random.choice([0.15, 0.18, 0.20]),
            "flat_fee_per_order": random.choice([2.0, 3.0, 4.0, 5.0]),
            "monthly_subscription_fee": random.choice([0.0, 499.0, 999.0]),
            "delivery_radius_km": random.uniform(5.0, 12.0),
            "avg_prep_minutes": random.randint(20, 40),
        }
        restaurants.append(r)
        all_slugs.append(slug)

    return restaurants, all_slugs


def generate_menu_categories(restaurants: list[dict]) -> list[dict]:
    """Generate 5-7 menu categories per restaurant."""
    DEFAULT_CATEGORIES = ["Starters", "Main Course", "Breads & Rice", "Desserts", "Beverages", "Combos"]
    categories = []
    for r in restaurants:
        num_cats = random.randint(5, 7)
        cats = random.sample(DEFAULT_CATEGORIES, min(num_cats, len(DEFAULT_CATEGORIES)))
        for sort_order, name in enumerate(cats):
            cat = {
                "id": str(uuid.uuid4()),
                "restaurant_id": r["id"],
                "name": name,
                "sort_order": sort_order,
            }
            categories.append(cat)
    return categories


def generate_menu_items(restaurants: list[dict], categories: list[dict]) -> list[dict]:
    """Generate 15-22 menu items per restaurant (~1900 total)."""
    items = []
    item_counter = 0
    for r in restaurants:
        cats = [c for c in categories if c["restaurant_id"] == r["id"]]
        num_items = random.randint(15, 22)
        for i in range(num_items):
            cat = random.choice(cats)
            item_counter += 1
            is_veg = random.random() > 0.4
            currency = r["currency"]
            if currency == "INR":
                price = round(random.uniform(50, 800), 2)
                price = round(price / 5) * 5  # round to nearest 5
            else:
                price = round(random.uniform(3, 25), 2)

            # Pick name based on category
            if cat["name"] == "Starters":
                name = random.choice(STARTER_NAMES)
                if not is_veg and name in STARTER_NAMES[:4]:
                    name = random.choice(STARTER_NAMES[2:])
            elif cat["name"] == "Main Course":
                name = random.choice(MAIN_NAMES)
            elif cat["name"] == "Breads & Rice":
                name = random.choice(BREAD_RICE)
            elif cat["name"] == "Desserts":
                name = random.choice(DESSERT_NAMES)
            elif cat["name"] == "Beverages":
                name = random.choice(BEVERAGE_NAMES)
                is_veg = True
            elif cat["name"] == "Combos":
                name = random.choice(COMBO_NAMES)
                # Discounted combo price
                price = round(price * 0.85, 2) if currency == "INR" else round(price * 0.9, 2)
            else:
                name = f"Special Item {i+1}"

            # Image URL: reuse 30 template images
            img_idx = ((item_counter - 1) % 30) + 1
            image_url = f"/images/menu/food_{img_idx}.jpg"

            item = {
                "id": str(uuid.uuid4()),
                "category_id": cat["id"],
                "restaurant_id": r["id"],
                "name": name,
                "description": f"Delicious {name.lower()} – fresh ingredients",
                "price": price,
                "category": cat["name"],
                "is_veg": is_veg,
                "is_available": True,
                "sort_order": i,
                "image_url": image_url,
            }
            items.append(item)
    return items


def generate_orders(restaurants: list[dict], num_orders: int = 60) -> tuple[list[dict], list[dict]]:
    """
    Generate orders using new restaurant IDs.
    Returns (orders, order_ids_list).
    """
    now = datetime.utcnow()
    statuses = ["delivered"] * 6 + ["preparing"] + ["picked_up"] + ["pending"] + ["confirmed"] + ["cancelled"]
    orders = []
    order_ids = []

    IN_ADDRESSES = [
        {"street": "123 MG Road", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560001",
         "lat": 12.975, "lng": 77.605},
        {"street": "45 Koramangala", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560095",
         "lat": 12.934, "lng": 77.626},
        {"street": "100 Brigade Road", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560001",
         "lat": 12.960, "lng": 77.600},
        {"street": "50 Indiranagar", "city": "Bengaluru", "state": "Karnataka", "postal_code": "560038",
         "lat": 12.978, "lng": 77.640},
    ]
    US_ADDRESSES = [
        {"street": "350 5th Avenue", "city": "New York", "state": "NY", "postal_code": "10118",
         "lat": 40.748, "lng": -73.985},
        {"street": "200 Broadway", "city": "New York", "state": "NY", "postal_code": "10038",
         "lat": 40.710, "lng": -74.007},
        {"street": "500 S Grand", "city": "Los Angeles", "state": "CA", "postal_code": "90071",
         "lat": 34.052, "lng": -118.255},
        {"street": "233 S Wacker Dr", "city": "Chicago", "state": "IL", "postal_code": "60606",
         "lat": 41.878, "lng": -87.635},
    ]

    for i in range(num_orders):
        order_id = f"eeee{1001+i:04d}-0001-0001-0001-000000000001"
        order_ids.append(order_id)
        rest = random.choice(restaurants)
        currency = rest["currency"]
        cust_id = random.choice(CUSTOMERS)
        driver_id = random.choice(DRIVERS)
        status = random.choice(statuses)

        if currency == "INR":
            subtotal = round(random.uniform(200, 1800), 2)
            delivery_fee = round(random.uniform(20, 50), 2)
            tax_rate = 0.18
            addresses = IN_ADDRESSES
        else:
            subtotal = round(random.uniform(10, 70), 2)
            delivery_fee = round(random.uniform(2, 5), 2)
            tax_rate = 0.08
            addresses = US_ADDRESSES

        taxes = round(subtotal * tax_rate, 2)
        tip = round(random.uniform(0, subtotal * 0.15), 2)
        total = round(subtotal + delivery_fee + taxes + tip, 2)

        created_at = now - timedelta(days=random.randint(0, 60),
                                     hours=random.randint(0, 23),
                                     minutes=random.randint(0, 59))

        payment_method = random.choice(["card", "upi", "wallet", "cash_on_delivery"]) if currency == "INR" \
            else random.choice(["card", "wallet"])

        items = json.dumps([
            {"menu_item_id": str(uuid.uuid4()), "name": "Item A",
             "quantity": random.randint(1, 3), "unit_price": round(subtotal * 0.6, 2), "total": round(subtotal * 0.6, 2)},
            {"menu_item_id": str(uuid.uuid4()), "name": "Item B",
             "quantity": random.randint(1, 2), "unit_price": round(subtotal * 0.4, 2), "total": round(subtotal * 0.4, 2)},
        ])
        delivery_addr = json.dumps(random.choice(addresses))

        actual_time = (created_at + timedelta(minutes=random.randint(25, 55))).isoformat() if status == "delivered" else None
        cancel_reason = random.choice(["changed_mind", "restaurant_closed"]) if status == "cancelled" else None
        assigned_driver = driver_id if status in ("picked_up", "delivered", "preparing", "ready_for_pickup") else None
        est_delivery = (created_at + timedelta(minutes=35)).isoformat()

        order = {
            "id": order_id,
            "customer_id": cust_id,
            "restaurant_id": rest["id"],
            "restaurant_name": rest["name"],
            "driver_id": assigned_driver,
            "items": items,
            "status": status,
            "subtotal": subtotal,
            "delivery_fee": delivery_fee,
            "taxes": taxes,
            "tip": tip,
            "discount": 0.0,
            "total": total,
            "currency": currency,
            "delivery_address": delivery_addr,
            "payment_method": payment_method,
            "estimated_delivery_time": est_delivery,
            "actual_delivery_time": actual_time,
            "cancellation_reason": cancel_reason,
            "created_at": created_at.isoformat(),
            "estimated_prep_minutes": rest.get("avg_prep_minutes", 30),
        }
        orders.append(order)

    return orders, order_ids


def generate_payment_intents(orders: list[dict], customers: list[str]) -> list[dict]:
    """Generate payment_intents for each order."""
    intents = []
    statuses = ["succeeded"] * 7 + ["pending"] * 2 + ["failed"]
    for i, order in enumerate(orders):
        currency = order["currency"]
        provider = "razorpay" if currency == "INR" else "stripe"
        intent = {
            "id": str(uuid.uuid4()),
            "order_id": order["id"],
            "user_id": order["customer_id"],
            "provider": provider,
            "provider_payment_id": f"pi_{uuid.uuid4().hex[:16]}",
            "amount": int(order["total"] * 100),
            "currency": currency,
            "status": random.choice(statuses),
            "idempotency_key": f"{order['id']}-{i}",
            "metadata": "{}",
        }
        intents.append(intent)
    return intents


def generate_wallets() -> list[dict]:
    """Generate wallet for each user."""
    wallets = []
    user_currency = {
        OWNER_IN: "INR", RR_ADMIN: "USD",
        CUSTOMERS[0]: "INR", CUSTOMERS[1]: "INR", CUSTOMERS[2]: "INR",
        CUSTOMERS[3]: "USD", CUSTOMERS[4]: "USD",
        OWNER_US: "USD",
        DRIVERS[0]: "INR", DRIVERS[1]: "USD", DRIVERS[2]: "USD",
    }
    for user_id, currency in user_currency.items():
        balance = round(random.uniform(500, 5000), 2)
        wallets.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "balance": balance,
            "currency": currency,
        })
    return wallets


def generate_wallet_transactions(wallets: list[dict]) -> list[dict]:
    """Generate 2-3 wallet transactions per user."""
    transactions = []
    tx_types = ["credit", "debit", "refund"]
    for wallet in wallets:
        num_tx = random.randint(2, 3)
        balance = wallet["balance"]
        for j in range(num_tx):
            tx_type = random.choice(tx_types)
            amount = round(random.uniform(10, min(balance, 500)), 2)
            if tx_type == "credit":
                balance = round(balance + amount, 2)
            elif tx_type == "debit":
                balance = round(balance - amount, 2)
            else:
                balance = round(balance + amount, 2)
            tx = {
                "id": str(uuid.uuid4()),
                "user_id": wallet["user_id"],
                "type": tx_type,
                "amount": amount,
                "currency": wallet["currency"],
                "balance_after": balance,
                "description": f"{tx_type.capitalize()} transaction",
                "reference_id": f"ref_{uuid.uuid4().hex[:12]}",
                "reference_type": random.choice(["order", "topup", "refund"]),
            }
            transactions.append(tx)
    return transactions


def generate_device_tokens() -> list[dict]:
    """Generate one device token per user."""
    tokens = []
    for user_id in ALL_USERS:
        token = uuid.uuid4().hex + uuid.uuid4().hex[:16]
        tokens.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "token": token,
            "platform": random.choice(PLATFORMS),
        })
    return tokens


NOTIF_TEMPLATES = {
    "order_confirmed": ("Order Confirmed", "Your order #{short_id} has been confirmed!"),
    "driver_assigned": ("Driver Assigned", "A driver has been assigned to deliver your order."),
    "order_delivered": ("Order Delivered", "Your order has been delivered. Enjoy your meal!"),
    "promo": ("Special Offer!", "Get 20% off on your next order with code BHOJAN20"),
    "payment_received": ("Payment Received", "Payment of {amount} received for order #{short_id}"),
}


def generate_notifications() -> list[dict]:
    """Generate 3-5 notifications per user."""
    notifications = []
    for user_id in ALL_USERS:
        num_notif = random.randint(3, 5)
        for j in range(num_notif):
            ntype = random.choice(NOTIF_TYPES)
            title_tmpl, body_tmpl = NOTIF_TEMPLATES[ntype]
            short_id = uuid.uuid4().hex[:6].upper()
            title = title_tmpl
            body = body_tmpl.replace("{short_id}", short_id).replace("{amount}", "₹150")
            notifications.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": ntype,
                "channel": NOTIF_CHANNEL,
                "title": title,
                "body": body,
                "data": "{}",
                "is_read": random.random() > 0.4,
                "sent_at": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat(),
            })
    return notifications


def generate_batch_engine_data(orders: list[dict], drivers: list[str]) -> dict:
    """
    Generate batch_engine data for confirmed/preparing orders.
    Returns dict with keys: order_pool, batches, batch_orders, route_stops.
    """
    # Use ~25 confirmed/preparing orders for order_pool
    pool_candidates = [o for o in orders if o["status"] in ("confirmed", "preparing")]
    pool_orders = pool_candidates[:25]

    order_pool = []
    for i, order in enumerate(pool_orders):
        est_prep = order["estimated_prep_minutes"]
        created = datetime.fromisoformat(order["created_at"])
        ready_at = created + timedelta(minutes=est_prep)
        promised  = ready_at + timedelta(minutes=30)
        order_pool.append({
            "id": str(uuid.uuid4()),
            "order_id": order["id"],
            "restaurant_id": order["restaurant_id"],
            "restaurant_name": order["restaurant_name"],
            "pickup_lat": 12.97 + random.uniform(-0.05, 0.05),
            "pickup_lng": 77.60 + random.uniform(-0.05, 0.05),
            "delivery_lat": 12.97 + random.uniform(-0.05, 0.05),
            "delivery_lng": 77.60 + random.uniform(-0.05, 0.05),
            "prep_ready_at": ready_at.isoformat(),
            "promised_delivery_at": promised.isoformat(),
            "priority": random.choice(["standard", "standard", "priority"]),
            "item_count": random.randint(1, 4),
            "estimated_size_liters": round(random.uniform(1.0, 10.0), 1),
            "currency": order["currency"],
            "delivery_fee": float(order["delivery_fee"]),
            "status": random.choice(["waiting", "batched"]),
            "batch_id": None,
        })

    # 8 batches
    batch_statuses = ["completed", "in_progress", "assigned"]
    batches = []
    batch_ids = []
    for i in range(8):
        bid = str(uuid.uuid4())
        batch_ids.append(bid)
        status = random.choice(batch_statuses)
        created = datetime.utcnow() - timedelta(days=random.randint(0, 10))
        batches.append({
            "id": bid,
            "driver_id": random.choice(drivers) if status != "forming" else None,
            "status": status,
            "score": round(random.uniform(60, 99), 1),
            "estimated_total_distance_km": round(random.uniform(5, 25), 2),
            "estimated_total_time_min": random.randint(30, 90),
            "max_detour_min": random.randint(5, 15),
            "savings_percent": round(random.uniform(10, 35), 1),
            "created_at": created.isoformat(),
            "assigned_at": (created + timedelta(minutes=5)).isoformat() if status in ("assigned", "in_progress", "completed") else None,
            "completed_at": (created + timedelta(minutes=60)).isoformat() if status == "completed" else None,
        })

    # Link pool orders to batches (2-3 orders per batch)
    batch_orders = []
    route_stops = []
    pool_idx = 0
    for bidx, batch in enumerate(batches):
        num_orders = random.randint(2, 3)
        for seq in range(num_orders):
            if pool_idx >= len(order_pool):
                break
            po = order_pool[pool_idx]
            po["batch_id"] = batch["id"]
            po["status"] = "batched"
            pool_idx += 1

            created = datetime.fromisoformat(batch["created_at"])
            est_pickup = (created + timedelta(minutes=seq * 10)).isoformat()
            est_delivery = (created + timedelta(minutes=seq * 10 + 25)).isoformat()
            bo = {
                "id": str(uuid.uuid4()),
                "batch_id": batch["id"],
                "order_id": po["order_id"],
                "pool_order_id": po["id"],
                "sequence": seq + 1,
                "estimated_pickup_at": est_pickup,
                "estimated_delivery_at": est_delivery,
                "detour_minutes": round(random.uniform(0, 8), 1),
                "actual_pickup_at": (created + timedelta(minutes=seq*10+2)).isoformat() if batch["status"] == "completed" else None,
                "actual_delivery_at": (created + timedelta(minutes=seq*10+27)).isoformat() if batch["status"] == "completed" else None,
                "status": "delivered" if batch["status"] == "completed" else random.choice(["pending", "picked_up"]),
            }
            batch_orders.append(bo)

            # 2-4 route stops per batch: pickup + deliveries
            num_stops = random.randint(2, 4)
            for stop_seq in range(num_stops):
                stop_type = "pickup" if stop_seq == 0 else "delivery"
                route_stops.append({
                    "id": str(uuid.uuid4()),
                    "batch_id": batch["id"],
                    "sequence": stop_seq + 1,
                    "stop_type": stop_type,
                    "order_id": po["order_id"] if stop_type == "delivery" else po["order_id"],
                    "lat": po["pickup_lat"] if stop_type == "pickup" else po["delivery_lat"],
                    "lng": po["pickup_lng"] if stop_type == "pickup" else po["delivery_lng"],
                    "estimated_arrival_at": (created + timedelta(minutes=stop_seq * 8)).isoformat(),
                    "estimated_dwell_min": 2.0,
                })

    return {"order_pool": order_pool, "batches": batches,
            "batch_orders": batch_orders, "route_stops": route_stops}


# ═══════════════════════════════════════════════════════════════════════════════
# SQL GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def sql_escape(s: str) -> str:
    return s.replace("'", "''")


def restaurants_to_sql(restaurants: list[dict]) -> list[str]:
    stmts = []
    for r in restaurants:
        cuisine_arr = "ARRAY[" + ",".join(f"'{c}'" for c in r["cuisine_types"]) + "]"
        address = json.dumps(r["address"]).replace("'", "''")
        logo_url = f"/images/restaurants/{r['slug']}.jpg"
        cover_url = f"/images/restaurants/{r['slug']}.jpg"
        stmts.append(f"""
INSERT INTO restaurants (
    id, name, slug, owner_id, description, cuisine_types, address,
    lat, lng, rating, review_count, is_open, delivery_time_min, delivery_time_max,
    minimum_order_amount, delivery_fee, currency, country, city, status, is_active,
    logo_url, cover_url, pricing_model, commission_rate, flat_fee_per_order,
    monthly_subscription_fee, delivery_radius_km, avg_prep_minutes, created_at, updated_at
) VALUES (
    '{r['id']}', '{sql_escape(r['name'])}', '{r['slug']}', '{r['owner_id']}',
    '{sql_escape(r['description'])}', {cuisine_arr}, '{address}',
    {r['lat']}, {r['lng']}, {r['rating']}, {r['review_count']}, true,
    {r['delivery_time_min']}, {r['delivery_time_max']},
    {r['minimum_order_amount']}, {r['delivery_fee']}, '{r['currency']}',
    '{r['country']}', '{r['city']}', '{r['status']}', true,
    '{logo_url}', '{cover_url}', '{r['pricing_model']}',
    {r['commission_rate']}, {r['flat_fee_per_order']},
    {r['monthly_subscription_fee']}, {r['delivery_radius_km']},
    {r['avg_prep_minutes']}, NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def categories_to_sql(categories: list[dict]) -> list[str]:
    stmts = []
    for c in categories:
        stmts.append(f"""
INSERT INTO menu_categories (id, restaurant_id, name, sort_order, created_at)
VALUES ('{c['id']}', '{c['restaurant_id']}', '{sql_escape(c['name'])}', {c['sort_order']}, NOW())
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def items_to_sql(items: list[dict]) -> list[str]:
    stmts = []
    for item in items:
        stmts.append(f"""
INSERT INTO menu_items (
    id, category_id, restaurant_id, name, description, price,
    category, is_veg, is_available, sort_order, image_url, created_at, updated_at
) VALUES (
    '{item['id']}', '{item['category_id']}', '{item['restaurant_id']}',
    '{sql_escape(item['name'])}', '{sql_escape(item['description'])}',
    {item['price']}, '{item['category']}', {str(item['is_veg']).lower()},
    true, {item['sort_order']}, '{item['image_url']}', NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def orders_to_sql(orders: list[dict]) -> list[str]:
    stmts = []
    for o in orders:
        actual_time = f"'{o['actual_delivery_time']}'" if o['actual_delivery_time'] else "NULL"
        cancel_reason = f"'{o['cancellation_reason']}'" if o['cancellation_reason'] else "NULL"
        driver_id = f"'{o['driver_id']}'" if o['driver_id'] else "NULL"
        items_json = o['items'].replace("'", "''")
        addr_json = o['delivery_address'].replace("'", "''")
        stmts.append(f"""
INSERT INTO orders (
    id, customer_id, restaurant_id, driver_id, items, status,
    subtotal, delivery_fee, taxes, tip, discount, total, currency,
    delivery_address, payment_method, estimated_delivery_time,
    actual_delivery_time, cancellation_reason, created_at, updated_at,
    estimated_prep_minutes, status_history, platform_fee, restaurant_payout
) VALUES (
    '{o['id']}', '{o['customer_id']}', '{o['restaurant_id']}', {driver_id},
    '{items_json}', '{o['status']}',
    {o['subtotal']}, {o['delivery_fee']}, {o['taxes']}, {o['tip']}, {o['discount']}, {o['total']},
    '{o['currency']}', '{addr_json}', '{o['payment_method']}',
    '{o['estimated_delivery_time']}', {actual_time}, {cancel_reason},
    '{o['created_at']}', '{o['created_at']}',
    {o['estimated_prep_minutes']}, '[]'::jsonb, 0, 0
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def payment_intents_to_sql(intents: list[dict]) -> list[str]:
    stmts = []
    for p in intents:
        stmts.append(f"""
INSERT INTO payment_intents (
    id, order_id, user_id, provider, provider_payment_id, amount, currency,
    status, idempotency_key, metadata, created_at, updated_at, refunded_amount
) VALUES (
    '{p['id']}', '{p['order_id']}', '{p['user_id']}', '{p['provider']}',
    '{p['provider_payment_id']}', {p['amount']}, '{p['currency']}',
    '{p['status']}', '{p['idempotency_key']}', '{p['metadata']}',
    NOW(), NOW(), 0
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def wallets_to_sql(wallets: list[dict]) -> list[str]:
    stmts = []
    for w in wallets:
        stmts.append(f"""
INSERT INTO wallets (id, user_id, balance, currency, updated_at)
VALUES ('{w['id']}', '{w['user_id']}', {w['balance']}, '{w['currency']}', NOW())
ON CONFLICT (user_id) DO NOTHING;""")
    return stmts


def wallet_transactions_to_sql(transactions: list[dict]) -> list[str]:
    stmts = []
    for t in transactions:
        ref_id = f"'{t['reference_id']}'" if t['reference_id'] else "NULL"
        ref_type = f"'{t['reference_type']}'" if t['reference_type'] else "NULL"
        stmts.append(f"""
INSERT INTO wallet_transactions (
    id, user_id, type, amount, currency, balance_after, description, reference_id, reference_type, created_at
) VALUES (
    '{t['id']}', '{t['user_id']}', '{t['type']}', {t['amount']}, '{t['currency']}',
    {t['balance_after']}, '{sql_escape(t['description'])}', {ref_id}, {ref_type}, NOW()
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def device_tokens_to_sql(tokens: list[dict]) -> list[str]:
    stmts = []
    for t in tokens:
        stmts.append(f"""
INSERT INTO device_tokens (id, user_id, token, platform, created_at, updated_at)
VALUES ('{t['id']}', '{t['user_id']}', '{t['token']}', '{t['platform']}', NOW(), NOW())
ON CONFLICT (token) DO NOTHING;""")
    return stmts


def notifications_to_sql(notifications: list[dict]) -> list[str]:
    stmts = []
    for n in notifications:
        is_read = str(n['is_read']).lower()
        sent_at = f"'{n['sent_at']}'" if n['sent_at'] else "NULL"
        stmts.append(f"""
INSERT INTO notifications (
    id, user_id, type, channel, title, body, data, is_read, sent_at, created_at
) VALUES (
    '{n['id']}', '{n['user_id']}', '{n['type']}', '{n['channel']}',
    '{sql_escape(n['title'])}', '{sql_escape(n['body'])}', '{n['data']}',
    {is_read}, {sent_at}, NOW()
)
ON CONFLICT (id) DO NOTHING;""")
    return stmts


def batch_engine_to_sql(be: dict) -> list[str]:
    stmts = []

    # order_pool
    for p in be["order_pool"]:
        batch_id = f"'{p['batch_id']}'" if p['batch_id'] else "NULL"
        stmts.append(f"""
INSERT INTO batch_engine.order_pool (
    id, order_id, restaurant_id, restaurant_name, pickup_lat, pickup_lng,
    delivery_lat, delivery_lng, prep_ready_at, promised_delivery_at, priority,
    item_count, estimated_size_liters, currency, delivery_fee, status, batch_id, created_at, updated_at
) VALUES (
    '{p['id']}', '{p['order_id']}', '{p['restaurant_id']}', '{sql_escape(p['restaurant_name'])}',
    {p['pickup_lat']}, {p['pickup_lng']}, {p['delivery_lat']}, {p['delivery_lng']},
    '{p['prep_ready_at']}', '{p['promised_delivery_at']}', '{p['priority']}',
    {p['item_count']}, {p['estimated_size_liters']}, '{p['currency']}', {p['delivery_fee']},
    '{p['status']}', {batch_id}, NOW(), NOW()
)
ON CONFLICT (order_id) DO NOTHING;""")

    # batches
    for b in be["batches"]:
        driver_id = f"'{b['driver_id']}'" if b['driver_id'] else "NULL"
        assigned_at = f"'{b['assigned_at']}'" if b['assigned_at'] else "NULL"
        completed_at = f"'{b['completed_at']}'" if b['completed_at'] else "NULL"
        stmts.append(f"""
INSERT INTO batch_engine.batches (
    id, driver_id, status, score, estimated_total_distance_km, estimated_total_time_min,
    max_detour_min, savings_percent, created_at, assigned_at, completed_at, updated_at
) VALUES (
    '{b['id']}', {driver_id}, '{b['status']}', {b['score']},
    {b['estimated_total_distance_km']}, {b['estimated_total_time_min']},
    {b['max_detour_min']}, {b['savings_percent']},
    '{b['created_at']}', {assigned_at}, {completed_at}, NOW()
)
ON CONFLICT (id) DO NOTHING;""")

    # batch_orders
    for bo in be["batch_orders"]:
        actual_pickup = f"'{bo['actual_pickup_at']}'" if bo['actual_pickup_at'] else "NULL"
        actual_delivery = f"'{bo['actual_delivery_at']}'" if bo['actual_delivery_at'] else "NULL"
        stmts.append(f"""
INSERT INTO batch_engine.batch_orders (
    id, batch_id, order_id, pool_order_id, sequence, estimated_pickup_at,
    estimated_delivery_at, detour_minutes, actual_pickup_at, actual_delivery_at, status, created_at
) VALUES (
    '{bo['id']}', '{bo['batch_id']}', '{bo['order_id']}', '{bo['pool_order_id']}',
    {bo['sequence']}, '{bo['estimated_pickup_at']}', '{bo['estimated_delivery_at']}',
    {bo['detour_minutes']}, {actual_pickup}, {actual_delivery}, '{bo['status']}', NOW()
)
ON CONFLICT (batch_id, order_id) DO NOTHING;""")

    # route_stops
    for rs in be["route_stops"]:
        stmts.append(f"""
INSERT INTO batch_engine.route_stops (
    id, batch_id, sequence, stop_type, order_id, lat, lng,
    estimated_arrival_at, estimated_dwell_min
) VALUES (
    '{rs['id']}', '{rs['batch_id']}', {rs['sequence']}, '{rs['stop_type']}',
    '{rs['order_id']}', {rs['lat']}, {rs['lng']},
    '{rs['estimated_arrival_at']}', {rs['estimated_dwell_min']}
)
ON CONFLICT (batch_id, sequence) DO NOTHING;""")

    return stmts


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=== Comprehensive Seed Script ===")
    print()

    # 1. Generate restaurant data
    print("Generating restaurant data...")
    restaurants, all_slugs = generate_restaurants()
    print(f"  Generated {len(restaurants)} restaurants ({len(all_slugs)} unique slugs)")

    # 2. Generate menu categories
    print("Generating menu categories...")
    categories = generate_menu_categories(restaurants)
    print(f"  Generated {len(categories)} categories")

    # 3. Generate menu items
    print("Generating menu items...")
    menu_items = generate_menu_items(restaurants, categories)
    print(f"  Generated {len(menu_items)} menu items")

    # 4. Generate orders
    print("Generating orders...")
    orders, order_ids = generate_orders(restaurants, num_orders=60)
    print(f"  Generated {len(orders)} orders")

    # 5. Generate payment intents
    print("Generating payment intents...")
    payment_intents = generate_payment_intents(orders, CUSTOMERS)
    print(f"  Generated {len(payment_intents)} payment intents")

    # 6. Generate wallets
    print("Generating wallets...")
    wallets = generate_wallets()
    print(f"  Generated {len(wallets)} wallets")

    # 7. Generate wallet transactions
    print("Generating wallet transactions...")
    wallet_transactions = generate_wallet_transactions(wallets)
    print(f"  Generated {len(wallet_transactions)} wallet transactions")

    # 8. Generate device tokens
    print("Generating device tokens...")
    device_tokens = generate_device_tokens()
    print(f"  Generated {len(device_tokens)} device tokens")

    # 9. Generate notifications
    print("Generating notifications...")
    notifications = generate_notifications()
    print(f"  Generated {len(notifications)} notifications")

    # 10. Generate batch engine data
    print("Generating batch engine data...")
    batch_data = generate_batch_engine_data(orders, DRIVERS)
    print(f"  order_pool: {len(batch_data['order_pool'])}, batches: {len(batch_data['batches'])}, "
          f"batch_orders: {len(batch_data['batch_orders'])}, route_stops: {len(batch_data['route_stops'])}")

    # 11. Download images FIRST (so paths are known for SQL)
    print()
    print("Downloading images...")
    img_dir = os.path.join(IMAGES_DIR, "restaurants")
    os.makedirs(img_dir, exist_ok=True)
    img_dir2 = os.path.join(IMAGES_DIR, "menu")
    os.makedirs(img_dir2, exist_ok=True)

    images_downloaded = download_images(all_slugs, all_slugs)
    print(f"  Downloaded {images_downloaded} images")

    # Count existing images
    existing_restaurant_imgs = len([f for f in os.listdir(os.path.join(IMAGES_DIR, "restaurants"))
                                    if f.endswith(".jpg")]) if os.path.exists(os.path.join(IMAGES_DIR, "restaurants")) else 0
    existing_menu_imgs = len([f for f in os.listdir(os.path.join(IMAGES_DIR, "menu"))
                              if f.endswith(".jpg")]) if os.path.exists(os.path.join(IMAGES_DIR, "menu")) else 0
    print(f"  Total restaurant images: {existing_restaurant_imgs}, menu images: {existing_menu_imgs}")

    # 12. Build SQL
    print()
    print("Building SQL file...")
    all_stmts = []
    all_stmts.append("-- ══════════════════════════════════════════════════════")
    all_stmts.append("-- COMPREHENSIVE SEED — generated by comprehensive_seed.py")
    all_stmts.append("-- ══════════════════════════════════════════════════════")
    all_stmts.append("")

    sections = [
        ("RESTAURANTS", restaurants_to_sql(restaurants)),
        ("MENU CATEGORIES", categories_to_sql(categories)),
        ("MENU ITEMS", items_to_sql(menu_items)),
        ("ORDERS", orders_to_sql(orders)),
        ("PAYMENT INTENTS", payment_intents_to_sql(payment_intents)),
        ("WALLETS", wallets_to_sql(wallets)),
        ("WALLET TRANSACTIONS", wallet_transactions_to_sql(wallet_transactions)),
        ("DEVICE TOKENS", device_tokens_to_sql(device_tokens)),
        ("NOTIFICATIONS", notifications_to_sql(notifications)),
        ("BATCH ENGINE", batch_engine_to_sql(batch_data)),
    ]

    for name, stmts in sections:
        all_stmts.append(f"\n-- ── {name} ──")
        all_stmts.extend(stmts)

    sql_content = "\n".join(all_stmts)

    with open(SQL_FILE, "w") as f:
        f.write(sql_content)
    print(f"  SQL written to {SQL_FILE} ({len(sql_content)} bytes)")

    # 13. Execute SQL
    print()
    print("Executing SQL against database...")
    env = os.environ.copy()
    env["PGPASSWORD"] = "bhojango_dev"
    result = subprocess.run(
        ["psql", "-h", "localhost", "-U", "bhojango", "-d", "bhojango", "-f", SQL_FILE],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  SQL ERROR (exit {result.returncode}):")
        print(result.stderr[-3000:])
    else:
        print("  SQL executed successfully")

    # 14. Verification
    print()
    print("=== Verification ===")
    env2 = os.environ.copy()
    env2["PGPASSWORD"] = "bhojango_dev"
    verify_sql = """
SELECT 'restaurants' t, COUNT(*) FROM public.restaurants
UNION ALL SELECT 'menu_items', COUNT(*) FROM public.menu_items
UNION ALL SELECT 'menu_categories', COUNT(*) FROM public.menu_categories
UNION ALL SELECT 'orders', COUNT(*) FROM public.orders
UNION ALL SELECT 'wallets', COUNT(*) FROM public.wallets
UNION ALL SELECT 'payment_intents', COUNT(*) FROM public.payment_intents
UNION ALL SELECT 'wallet_transactions', COUNT(*) FROM public.wallet_transactions
UNION ALL SELECT 'device_tokens', COUNT(*) FROM public.device_tokens
UNION ALL SELECT 'notifications', COUNT(*) FROM public.notifications
UNION ALL SELECT 'batch_engine.order_pool', COUNT(*) FROM batch_engine.order_pool
UNION ALL SELECT 'batch_engine.batches', COUNT(*) FROM batch_engine.batches
UNION ALL SELECT 'batch_engine.batch_orders', COUNT(*) FROM batch_engine.batch_orders
UNION ALL SELECT 'batch_engine.route_stops', COUNT(*) FROM batch_engine.route_stops;
"""
    vr = subprocess.run(
        ["psql", "-h", "localhost", "-U", "bhojango", "-d", "bhojango", "-c", verify_sql],
        env=env2,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(vr.stdout)

    print()
    print(f"Images: {existing_restaurant_imgs} restaurant + {existing_menu_imgs} menu")
    print("=== Done ===")


if __name__ == "__main__":
    main()