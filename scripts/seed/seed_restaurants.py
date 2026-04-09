"""Seed restaurants and menu items for local development."""

import json
import uuid

RESTAURANTS = [
    # Indian Cuisine (Bengaluru)
    {
        "id": "aaaa0001-0001-0001-0001-000000000001",
        "name": "Spice Garden",
        "slug": "spice-garden-bengaluru",
        "description": "Authentic South Indian cuisine with a modern twist",
        "cuisine_type": ["Indian", "South Indian"],
        "phone": "+919876543001",
        "email": "spicegarden@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "active",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "average_rating": 4.5,
        "total_ratings": 320,
        "delivery_fee": 30.0,
        "min_order_amount": 150.0,
        "estimated_delivery_time": 35,
        "is_vegetarian": False,
        "categories": [
            {
                "name": "Starters",
                "items": [
                    {"name": "Masala Dosa", "price": 120, "is_veg": True, "is_bestseller": True, "description": "Crispy rice crepe with potato filling"},
                    {"name": "Medu Vada", "price": 80, "is_veg": True, "description": "Crispy lentil fritters with sambar and chutney"},
                    {"name": "Chicken 65", "price": 220, "is_veg": False, "is_bestseller": True, "description": "Spicy deep-fried chicken"},
                    {"name": "Paneer Tikka", "price": 200, "is_veg": True, "description": "Grilled cottage cheese with tandoori spices"},
                ],
            },
            {
                "name": "Main Course",
                "items": [
                    {"name": "Butter Chicken", "price": 320, "is_veg": False, "is_bestseller": True, "description": "Creamy tomato-based chicken curry"},
                    {"name": "Paneer Butter Masala", "price": 280, "is_veg": True, "description": "Cottage cheese in rich tomato gravy"},
                    {"name": "Biryani (Chicken)", "price": 280, "is_veg": False, "description": "Aromatic basmati rice with chicken"},
                    {"name": "Dal Makhani", "price": 200, "is_veg": True, "description": "Slow-cooked black lentils in butter cream"},
                ],
            },
            {
                "name": "Breads & Rice",
                "items": [
                    {"name": "Butter Naan", "price": 50, "is_veg": True, "description": "Tandoor-baked flatbread with butter"},
                    {"name": "Garlic Naan", "price": 60, "is_veg": True, "description": "Naan with garlic and herbs"},
                    {"name": "Jeera Rice", "price": 120, "is_veg": True, "description": "Cumin-tempered basmati rice"},
                    {"name": "Roti", "price": 30, "is_veg": True, "description": "Whole wheat flatbread"},
                ],
            },
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000002",
        "name": "Tandoori Nights",
        "slug": "tandoori-nights-bengaluru",
        "description": "North Indian and Mughlai delicacies",
        "cuisine_type": ["Indian", "North Indian", "Mughlai"],
        "phone": "+919876543002",
        "email": "tandoorinights@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "active",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "average_rating": 4.3,
        "total_ratings": 180,
        "delivery_fee": 40.0,
        "min_order_amount": 200.0,
        "estimated_delivery_time": 40,
        "is_vegetarian": False,
        "categories": [
            {"name": "Kebabs", "items": [
                {"name": "Seekh Kebab", "price": 250, "is_veg": False, "is_bestseller": True, "description": "Minced meat kebabs on skewers"},
                {"name": "Tandoori Chicken", "price": 350, "is_veg": False, "description": "Clay oven roasted chicken"},
                {"name": "Paneer Shashlik", "price": 220, "is_veg": True, "description": "Grilled paneer with bell peppers"},
            ]},
            {"name": "Curries", "items": [
                {"name": "Rogan Josh", "price": 340, "is_veg": False, "description": "Kashmiri lamb curry"},
                {"name": "Shahi Paneer", "price": 260, "is_veg": True, "is_bestseller": True, "description": "Royal cottage cheese curry"},
                {"name": "Chicken Korma", "price": 300, "is_veg": False, "description": "Mild creamy chicken curry"},
            ]},
            {"name": "Biryani", "items": [
                {"name": "Hyderabadi Biryani", "price": 320, "is_veg": False, "is_bestseller": True, "description": "Layered rice and meat biryani"},
                {"name": "Veg Biryani", "price": 220, "is_veg": True, "description": "Aromatic vegetable biryani"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000003",
        "name": "Dosa Express",
        "slug": "dosa-express-bengaluru",
        "description": "Quick-service South Indian breakfast and snacks",
        "cuisine_type": ["South Indian"],
        "phone": "+919876543003",
        "email": "dosaexpress@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "active",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9850,
        "longitude": 77.6080,
        "average_rating": 4.2,
        "total_ratings": 450,
        "delivery_fee": 20.0,
        "min_order_amount": 100.0,
        "estimated_delivery_time": 25,
        "is_vegetarian": True,
        "categories": [
            {"name": "Dosas", "items": [
                {"name": "Plain Dosa", "price": 70, "is_veg": True, "description": "Classic rice and lentil crepe"},
                {"name": "Masala Dosa", "price": 90, "is_veg": True, "is_bestseller": True, "description": "Dosa filled with spiced potato"},
                {"name": "Rava Dosa", "price": 100, "is_veg": True, "description": "Crispy semolina crepe"},
                {"name": "Mysore Masala Dosa", "price": 110, "is_veg": True, "description": "Dosa with spicy red chutney and potato"},
                {"name": "Set Dosa", "price": 80, "is_veg": True, "description": "Soft spongy dosa (set of 3)"},
            ]},
            {"name": "Idli & Vada", "items": [
                {"name": "Idli (4 pcs)", "price": 60, "is_veg": True, "description": "Steamed rice cakes"},
                {"name": "Vada (2 pcs)", "price": 60, "is_veg": True, "description": "Crispy urad dal fritters"},
                {"name": "Idli Vada Combo", "price": 100, "is_veg": True, "is_bestseller": True, "description": "2 idlis + 1 vada with sambar & chutney"},
            ]},
            {"name": "Beverages", "items": [
                {"name": "Filter Coffee", "price": 40, "is_veg": True, "is_bestseller": True, "description": "Authentic South Indian filter coffee"},
                {"name": "Masala Chai", "price": 30, "is_veg": True, "description": "Spiced Indian tea"},
                {"name": "Buttermilk", "price": 40, "is_veg": True, "description": "Spiced yogurt drink"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000004",
        "name": "Curry Leaf",
        "slug": "curry-leaf-bengaluru",
        "description": "Kerala-style seafood and traditional meals",
        "cuisine_type": ["Indian", "Kerala"],
        "phone": "+919876543004",
        "email": "curryleaf@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "active",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9600,
        "longitude": 77.5800,
        "average_rating": 4.6,
        "total_ratings": 210,
        "delivery_fee": 35.0,
        "min_order_amount": 200.0,
        "estimated_delivery_time": 45,
        "is_vegetarian": False,
        "categories": [
            {"name": "Seafood", "items": [
                {"name": "Kerala Fish Curry", "price": 300, "is_veg": False, "is_bestseller": True, "description": "Coconut-based fish curry"},
                {"name": "Prawn Fry", "price": 350, "is_veg": False, "description": "Crispy fried prawns"},
                {"name": "Fish Moilee", "price": 320, "is_veg": False, "description": "Mild coconut milk fish stew"},
            ]},
            {"name": "Meals", "items": [
                {"name": "Kerala Meals (Veg)", "price": 180, "is_veg": True, "description": "Rice with sambar, rasam, thoran, avial"},
                {"name": "Kerala Meals (Non-Veg)", "price": 250, "is_veg": False, "is_bestseller": True, "description": "Rice with fish curry, chicken, and sides"},
            ]},
            {"name": "Snacks", "items": [
                {"name": "Banana Chips", "price": 80, "is_veg": True, "description": "Crispy Kerala banana chips"},
                {"name": "Appam with Stew", "price": 150, "is_veg": True, "description": "Lacy rice pancakes with vegetable stew"},
                {"name": "Parotta with Chicken", "price": 180, "is_veg": False, "description": "Layered flatbread with chicken curry"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000005",
        "name": "Biryani House",
        "slug": "biryani-house-bengaluru",
        "description": "Biryani specialists with a loyal following",
        "cuisine_type": ["Indian", "Biryani"],
        "phone": "+919876543005",
        "email": "biryanihouse@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "pending_approval",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9500,
        "longitude": 77.5700,
        "average_rating": 0,
        "total_ratings": 0,
        "delivery_fee": 25.0,
        "min_order_amount": 200.0,
        "estimated_delivery_time": 40,
        "is_vegetarian": False,
        "categories": [
            {"name": "Biryani", "items": [
                {"name": "Chicken Dum Biryani", "price": 280, "is_veg": False, "is_bestseller": True, "description": "Slow-cooked chicken biryani"},
                {"name": "Mutton Biryani", "price": 350, "is_veg": False, "description": "Rich mutton biryani"},
                {"name": "Paneer Biryani", "price": 220, "is_veg": True, "description": "Paneer biryani with saffron"},
                {"name": "Egg Biryani", "price": 200, "is_veg": False, "description": "Egg biryani with raita"},
            ]},
            {"name": "Sides", "items": [
                {"name": "Raita", "price": 50, "is_veg": True, "description": "Yogurt with onion and cucumber"},
                {"name": "Salan", "price": 60, "is_veg": True, "description": "Tangy accompaniment for biryani"},
                {"name": "Mirchi Ka Salan", "price": 80, "is_veg": True, "description": "Green chili in peanut-coconut gravy"},
            ]},
        ],
    },
    # American Cuisine (NYC)
    {
        "id": "aaaa0001-0001-0001-0001-000000000006",
        "name": "NYC Burger Co",
        "slug": "nyc-burger-co",
        "description": "Gourmet burgers and craft shakes in Manhattan",
        "cuisine_type": ["American", "Burgers"],
        "phone": "+12125551006",
        "email": "nycburger@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222202",
        "status": "active",
        "is_active": True,
        "city": "New York",
        "state": "NY",
        "country": "US",
        "latitude": 40.7580,
        "longitude": -73.9855,
        "average_rating": 4.4,
        "total_ratings": 540,
        "delivery_fee": 3.99,
        "min_order_amount": 15.0,
        "estimated_delivery_time": 30,
        "is_vegetarian": False,
        "categories": [
            {"name": "Burgers", "items": [
                {"name": "Classic Cheeseburger", "price": 12.99, "is_veg": False, "is_bestseller": True, "description": "Angus beef, cheddar, lettuce, tomato"},
                {"name": "Bacon BBQ Burger", "price": 14.99, "is_veg": False, "description": "Smoked bacon, BBQ sauce, onion rings"},
                {"name": "Veggie Burger", "price": 11.99, "is_veg": True, "description": "Black bean patty with avocado"},
                {"name": "Mushroom Swiss", "price": 13.99, "is_veg": False, "description": "Sauteed mushrooms and Swiss cheese"},
            ]},
            {"name": "Sides", "items": [
                {"name": "French Fries", "price": 4.99, "is_veg": True, "is_bestseller": True, "description": "Crispy golden fries"},
                {"name": "Onion Rings", "price": 5.99, "is_veg": True, "description": "Beer-battered onion rings"},
                {"name": "Coleslaw", "price": 3.99, "is_veg": True, "description": "Creamy coleslaw"},
            ]},
            {"name": "Shakes", "items": [
                {"name": "Vanilla Shake", "price": 6.99, "is_veg": True, "description": "Hand-spun vanilla milkshake"},
                {"name": "Chocolate Shake", "price": 6.99, "is_veg": True, "is_bestseller": True, "description": "Rich chocolate milkshake"},
                {"name": "Strawberry Shake", "price": 6.99, "is_veg": True, "description": "Fresh strawberry milkshake"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000007",
        "name": "Brooklyn Pizza",
        "slug": "brooklyn-pizza",
        "description": "Wood-fired Neapolitan-style pizza",
        "cuisine_type": ["Italian", "Pizza"],
        "phone": "+12125551007",
        "email": "brooklynpizza@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222202",
        "status": "active",
        "is_active": True,
        "city": "New York",
        "state": "NY",
        "country": "US",
        "latitude": 40.6782,
        "longitude": -73.9442,
        "average_rating": 4.7,
        "total_ratings": 780,
        "delivery_fee": 2.99,
        "min_order_amount": 12.0,
        "estimated_delivery_time": 35,
        "is_vegetarian": False,
        "categories": [
            {"name": "Pizzas", "items": [
                {"name": "Margherita", "price": 14.99, "is_veg": True, "is_bestseller": True, "description": "Fresh mozzarella, tomato, basil"},
                {"name": "Pepperoni", "price": 16.99, "is_veg": False, "is_bestseller": True, "description": "Classic pepperoni with mozzarella"},
                {"name": "BBQ Chicken", "price": 17.99, "is_veg": False, "description": "BBQ sauce, chicken, red onion"},
                {"name": "Veggie Supreme", "price": 15.99, "is_veg": True, "description": "Bell peppers, mushrooms, olives, onion"},
            ]},
            {"name": "Pasta", "items": [
                {"name": "Spaghetti Bolognese", "price": 13.99, "is_veg": False, "description": "Classic meat sauce pasta"},
                {"name": "Penne Alfredo", "price": 12.99, "is_veg": True, "description": "Creamy Alfredo sauce"},
                {"name": "Garlic Bread", "price": 5.99, "is_veg": True, "is_bestseller": True, "description": "Toasted garlic bread with herbs"},
            ]},
            {"name": "Desserts", "items": [
                {"name": "Tiramisu", "price": 8.99, "is_veg": True, "description": "Classic Italian coffee dessert"},
                {"name": "Cannoli", "price": 6.99, "is_veg": True, "description": "Crispy shell with ricotta filling"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000008",
        "name": "Dragon Wok",
        "slug": "dragon-wok-nyc",
        "description": "Szechuan and Cantonese Chinese cuisine",
        "cuisine_type": ["Chinese", "Asian"],
        "phone": "+12125551008",
        "email": "dragonwok@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222202",
        "status": "active",
        "is_active": True,
        "city": "New York",
        "state": "NY",
        "country": "US",
        "latitude": 40.7157,
        "longitude": -73.9970,
        "average_rating": 4.1,
        "total_ratings": 290,
        "delivery_fee": 3.49,
        "min_order_amount": 18.0,
        "estimated_delivery_time": 40,
        "is_vegetarian": False,
        "categories": [
            {"name": "Appetizers", "items": [
                {"name": "Spring Rolls (4)", "price": 7.99, "is_veg": True, "description": "Crispy vegetable spring rolls"},
                {"name": "Chicken Dumplings (6)", "price": 9.99, "is_veg": False, "is_bestseller": True, "description": "Steamed chicken and ginger dumplings"},
                {"name": "Hot & Sour Soup", "price": 6.99, "is_veg": False, "description": "Classic Szechuan soup"},
            ]},
            {"name": "Main Dishes", "items": [
                {"name": "Kung Pao Chicken", "price": 14.99, "is_veg": False, "is_bestseller": True, "description": "Spicy chicken with peanuts"},
                {"name": "Beef with Broccoli", "price": 15.99, "is_veg": False, "description": "Tender beef stir-fry"},
                {"name": "Mapo Tofu", "price": 12.99, "is_veg": True, "description": "Spicy Szechuan tofu"},
                {"name": "Orange Chicken", "price": 13.99, "is_veg": False, "description": "Crispy chicken in sweet orange glaze"},
            ]},
            {"name": "Noodles & Rice", "items": [
                {"name": "Lo Mein", "price": 11.99, "is_veg": True, "description": "Stir-fried egg noodles with vegetables"},
                {"name": "Fried Rice", "price": 10.99, "is_veg": True, "is_bestseller": True, "description": "Wok-fried rice with egg and vegetables"},
            ]},
        ],
    },
    # Mixed
    {
        "id": "aaaa0001-0001-0001-0001-000000000009",
        "name": "Fusion Kitchen",
        "slug": "fusion-kitchen-nyc",
        "description": "Indo-American fusion with creative flavors",
        "cuisine_type": ["Fusion", "Indian", "American"],
        "phone": "+12125551009",
        "email": "fusionkitchen@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222202",
        "status": "active",
        "is_active": True,
        "city": "New York",
        "state": "NY",
        "country": "US",
        "latitude": 40.7282,
        "longitude": -73.7949,
        "average_rating": 4.0,
        "total_ratings": 150,
        "delivery_fee": 4.99,
        "min_order_amount": 20.0,
        "estimated_delivery_time": 35,
        "is_vegetarian": False,
        "categories": [
            {"name": "Fusion Plates", "items": [
                {"name": "Tikka Tacos", "price": 13.99, "is_veg": False, "is_bestseller": True, "description": "Chicken tikka in corn tortillas"},
                {"name": "Butter Chicken Mac & Cheese", "price": 15.99, "is_veg": False, "description": "Creamy makhani mac and cheese"},
                {"name": "Samosa Sliders", "price": 11.99, "is_veg": True, "description": "Mini potato samosa burgers"},
                {"name": "Naan Pizza", "price": 14.99, "is_veg": True, "is_bestseller": True, "description": "Garlic naan with pizza toppings"},
            ]},
            {"name": "Bowls", "items": [
                {"name": "Tandoori Bowl", "price": 14.99, "is_veg": False, "description": "Rice, tandoori chicken, raita, salad"},
                {"name": "Falafel Bowl", "price": 12.99, "is_veg": True, "description": "Rice, falafel, hummus, tahini"},
            ]},
            {"name": "Drinks", "items": [
                {"name": "Mango Lassi", "price": 5.99, "is_veg": True, "is_bestseller": True, "description": "Sweet mango yogurt smoothie"},
                {"name": "Masala Lemonade", "price": 4.99, "is_veg": True, "description": "Lemonade with Indian spices"},
            ]},
        ],
    },
    {
        "id": "aaaa0001-0001-0001-0001-000000000010",
        "name": "Green Bowl",
        "slug": "green-bowl-bengaluru",
        "description": "Healthy salads, wraps, and smoothie bowls",
        "cuisine_type": ["Healthy", "Salads"],
        "phone": "+919876543010",
        "email": "greenbowl@test.com",
        "owner_id": "22222222-2222-2222-2222-222222222201",
        "status": "pending_approval",
        "is_active": True,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "IN",
        "latitude": 12.9780,
        "longitude": 77.6100,
        "average_rating": 0,
        "total_ratings": 0,
        "delivery_fee": 25.0,
        "min_order_amount": 150.0,
        "estimated_delivery_time": 25,
        "is_vegetarian": True,
        "categories": [
            {"name": "Bowls", "items": [
                {"name": "Quinoa Power Bowl", "price": 250, "is_veg": True, "is_bestseller": True, "description": "Quinoa, roasted veggies, tahini dressing"},
                {"name": "Acai Smoothie Bowl", "price": 280, "is_veg": True, "description": "Acai blend with granola and berries"},
                {"name": "Poke Bowl", "price": 300, "is_veg": False, "description": "Fresh fish, rice, edamame, avocado"},
            ]},
            {"name": "Wraps", "items": [
                {"name": "Falafel Wrap", "price": 180, "is_veg": True, "description": "Falafel, hummus, pickled onion"},
                {"name": "Grilled Chicken Wrap", "price": 220, "is_veg": False, "is_bestseller": True, "description": "Grilled chicken, lettuce, tzatziki"},
            ]},
            {"name": "Juices", "items": [
                {"name": "Green Detox", "price": 150, "is_veg": True, "description": "Spinach, apple, ginger, lemon"},
                {"name": "Mango Smoothie", "price": 130, "is_veg": True, "description": "Fresh mango with yogurt"},
            ]},
        ],
    },
]


def _make_uuid(base: str, suffix: str) -> str:
    """Create a valid UUID by hashing base+suffix."""
    import hashlib
    h = hashlib.md5(f"{base}:{suffix}".encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def generate_sql() -> str:
    lines = ["-- Seed restaurants and menu items (idempotent)"]

    for r in RESTAURANTS:
        # Build cuisine_types as PostgreSQL array literal
        cuisines = ",".join(f'"{c}"' for c in r["cuisine_type"])
        cuisine_array = "'{" + ",".join(r["cuisine_type"]) + "}'"
        # Build address JSONB
        address = json.dumps({"street": "", "city": r["city"], "state": r.get("state", ""), "zip": "", "country": r["country"]}).replace("'", "''")
        currency = "INR" if r["country"] == "IN" else "USD"
        delivery_max = r.get("estimated_delivery_time", 45) + 15

        lines.append(f"""
INSERT INTO restaurants (id, name, slug, owner_id, description, cuisine_types, address, lat, lng, rating, review_count, is_open, delivery_time_min, delivery_time_max, minimum_order_amount, delivery_fee, currency, country, city, status, is_active, created_at, updated_at)
VALUES (
    '{r["id"]}', '{r["name"].replace("'", "''")}', '{r["slug"]}', '{r["owner_id"]}',
    '{r["description"].replace("'", "''")}', {cuisine_array}, '{address}',
    {r["latitude"]}, {r["longitude"]}, {r.get("average_rating", 0)}, {r.get("total_ratings", 0)},
    true, {r.get("estimated_delivery_time", 30)}, {delivery_max},
    {r.get("min_order_amount", 0)}, {r["delivery_fee"]}, '{currency}', '{r["country"]}', '{r["city"]}',
    '{r["status"]}', {str(r["is_active"]).lower()}, NOW(), NOW()
)
ON CONFLICT (id) DO NOTHING;""")

        for cat_idx, cat in enumerate(r["categories"]):
            cat_id = _make_uuid(r["id"], f"cat-{cat_idx}")
            lines.append(f"""
INSERT INTO menu_categories (id, restaurant_id, name, sort_order, created_at)
VALUES ('{cat_id}', '{r["id"]}', '{cat["name"]}', {cat_idx}, NOW())
ON CONFLICT (id) DO NOTHING;""")

            for item_idx, item in enumerate(cat["items"]):
                item_id = _make_uuid(r["id"], f"item-{cat_idx}-{item_idx}")
                is_bs = str(item.get("is_bestseller", False)).lower()
                desc = item.get("description", "").replace("'", "''")
                lines.append(f"""
INSERT INTO menu_items (id, category_id, restaurant_id, name, description, price, category, is_veg, is_available, sort_order, created_at, updated_at)
VALUES ('{item_id}', '{cat_id}', '{r["id"]}', '{item["name"].replace("'", "''")}', '{desc}', {item["price"]}, '{cat["name"]}', {str(item["is_veg"]).lower()}, true, {item_idx}, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;""")

    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_sql())
