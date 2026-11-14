"""Seed data: India ▸ Telangana ▸ Hyderabad and USA ▸ Idaho ▸ Boise.

Restaurants, dishes and prices marked "board" come from the design board
(docs/specs/README.md, "Screen designs"); the rest are plausible placeholders.
Markets don't have their own tables yet (P6), so each record carries country,
state and city.
"""

PASSWORD = "BhojanGo123"  # every seeded account; local and staging only
ADMIN_PASSWORD = "BhojanGoAdmin1"

MARKETS = [
    {
        "key": "hyd",
        "country": "IN",
        "country_name": "India",
        "state": "Telangana",
        "city": "Hyderabad",
        "currency": "INR",
        "locale": "en-IN",
        "phone_prefix": "+919000000",  # +91 90000 00101: 10-digit mobiles, as the apps require
        "scope": "IN-TG-HYD",  # market code: country-state-city (shared/authz.py)
        "partner": "Hyderabad Partner",
        "customers": [
            ("Srini Rao", "Flat 302, Ayyappa Society", "Madhapur", "500081", 17.4483, 78.3915),
            ("Priya Sharma", "12-2-41, Road No. 36", "Jubilee Hills", "500033", 17.4307, 78.4072),
            ("Arjun Reddy", "Plot 88, Kondapur Main Rd", "Kondapur", "500084", 17.4600, 78.3640),
            ("Meera Iyer", "Tower B, DLF Cyber City", "Gachibowli", "500032", 17.4401, 78.3489),
            ("Farhan Ali", "8-1-293, Tolichowki", "Tolichowki", "500008", 17.3990, 78.4130),
        ],
        "riders": ["Ravi Kumar", "Imran Shaikh", "Lakshmi Reddy"],  # "Ravi K." is on the board
        # A kitchen applying to join (P19 board "Partner application", step 2: FSSAI): business details done.
        "applicant": {"name": "Anil Varma", "restaurant": "Kesar Kitchen", "slug": "kesar-kitchen-kondapur",
                      "area": "Kondapur", "street": "Plot 21, Botanical Garden Rd", "zip": "500084",
                      "lat": 17.4610, "lng": 78.3660, "cuisines": ["Andhra", "Thali"]},
        "restaurants": [
            {
                "name": "Spice Route Kitchen",  # board
                "slug": "spice-route-kitchen-madhapur",
                "area": "Madhapur",
                "street": "Plot 14, 100 Feet Rd",
                "zip": "500081",
                "lat": 17.4486,
                "lng": 78.3908,
                "cuisines": ["Hyderabadi", "Biryani"],
                "description": "Dum biryani sealed and slow-cooked the Hyderabadi way.",
                "rating": 4.6,  # board
                "eta": (25, 30),  # board
                "delivery_fee": "35.00",  # board (kitchen-funded free delivery in the pilot)
                "min_order": "149.00",
                "tags": ["bestseller", "free-delivery"],
                "menu": {
                    "Biryani": [
                        # name, price, veg, description, customizations (board)
                        ("Chicken Dum Biryani", "300.00", False, "Saffron basmati and chicken, sealed and steamed for two hours.", [
                            {"name": "Size", "required": True, "max": 1, "options": [{"name": "Regular · serves 1", "price": 0}, {"name": "Family · serves 3", "price": 480}]},
                            {"name": "Spice", "required": True, "max": 1, "options": [{"name": "Mild", "price": 0}, {"name": "Medium", "price": 0}, {"name": "Hot", "price": 0}]},
                            {"name": "Add-ons", "required": False, "max": 3, "options": [{"name": "Extra raita", "price": 40}, {"name": "Mirchi ka salan", "price": 30}]},
                        ]),
                        ("Mutton Dum Biryani", "420.00", False, "Tender mutton, aged basmati, dum-cooked.", []),
                        ("Veg Dum Biryani", "240.00", True, "Seasonal vegetables and paneer, dum-cooked.", []),
                        ("Egg Biryani", "260.00", False, "Contains egg.", []),
                        ("Family Pack Biryani", "980.00", False, "Chicken dum biryani that serves 4.", []),
                    ],
                    "Starters": [
                        ("Paneer Tikka", "220.00", True, "Charred paneer, mint chutney.", []),
                    ],
                    "Desserts": [
                        ("Double Ka Meetha", "120.00", True, "Bread pudding with saffron and dry fruit.", []),  # dish on board, price placeholder
                    ],
                },
            },
            {
                "name": "Curry Leaf",  # named in the P3 prompt
                "slug": "curry-leaf-gachibowli",
                "area": "Gachibowli",
                "street": "Survey 115, Financial District Rd",
                "zip": "500032",
                "lat": 17.4239,
                "lng": 78.3444,
                "cuisines": ["Kerala", "South Indian"],
                "description": "Kerala home cooking: appam, stew and Malabar curries.",
                "rating": 4.5,
                "eta": (30, 40),
                "delivery_fee": "30.00",
                "min_order": "199.00",
                "tags": ["south-indian"],
                "menu": {
                    "Mains": [
                        ("Appam with Vegetable Stew", "180.00", True, "Two lace appams, coconut milk stew.", []),
                        ("Malabar Fish Curry", "320.00", False, "Kingfish in tamarind and coconut.", []),
                        ("Kerala Chicken Roast", "280.00", False, "Slow-roasted with shallots and curry leaves.", []),
                    ],
                    "Breads": [("Kerala Parotta", "60.00", True, "Flaky layered flatbread.", [])],
                    "Desserts": [("Palada Payasam", "90.00", True, "Rice ada in sweetened milk.", [])],
                },
            },
            {
                "name": "Charminar Chai House",
                "slug": "charminar-chai-house-old-city",
                "area": "Old City",
                "street": "Near Charminar, Pathergatti",
                "zip": "500002",
                "lat": 17.3616,
                "lng": 78.4747,
                "cuisines": ["Irani Cafe", "Snacks"],
                "description": "Irani chai, Osmania biscuits and late-night snacks.",
                "rating": 4.4,
                "eta": (20, 30),
                "delivery_fee": "25.00",
                "min_order": "99.00",
                "tags": ["late-night"],
                "menu": {
                    "Chai": [
                        ("Irani Chai", "30.00", True, "Slow-brewed, creamy.", []),
                        ("Osmania Biscuits (6)", "40.00", True, "Sweet-salty butter biscuits.", []),
                    ],
                    "Snacks": [
                        ("Bun Maska", "50.00", True, "Soft bun, salted butter.", []),
                        ("Keema Samosa (2)", "60.00", False, "Spiced minced mutton.", []),
                    ],
                },
            },
            {
                "name": "Banjara Dosa Co.",
                "slug": "banjara-dosa-co-banjara-hills",
                "area": "Banjara Hills",
                "street": "Road No. 12, Banjara Hills",
                "zip": "500034",
                "lat": 17.4138,
                "lng": 78.4398,
                "cuisines": ["South Indian", "Dosa"],
                "description": "Crisp dosas, podi and filter coffee.",
                "rating": 4.3,
                "eta": (25, 35),
                "delivery_fee": "30.00",
                "min_order": "149.00",
                "tags": ["breakfast"],
                "menu": {
                    "Dosa": [
                        ("Masala Dosa", "110.00", True, "Potato masala, chutneys, sambar.", []),
                        ("Ghee Podi Dosa", "140.00", True, "Gunpowder podi, ghee.", []),
                    ],
                    "Tiffin": [("Idli (3)", "70.00", True, "Steamed rice cakes.", [])],
                    "Drinks": [("Filter Coffee", "50.00", True, "Chicory blend, frothed.", [])],
                },
            },
            {
                "name": "Hitech Thali",
                "slug": "hitech-thali-hitec-city",
                "area": "HITEC City",
                "street": "Cyber Towers Rd",
                "zip": "500081",
                "lat": 17.4435,
                "lng": 78.3772,
                "cuisines": ["Andhra", "Thali"],
                "description": "Unlimited-style thalis for the office crowd.",
                "rating": 4.2,
                "eta": (30, 40),
                "delivery_fee": "35.00",
                "min_order": "199.00",
                "tags": ["lunch"],
                "menu": {
                    "Thalis": [
                        ("Veg Thali", "220.00", True, "Rice, two curries, dal, rasam, curd, sweet.", []),
                        ("Andhra Meals", "260.00", True, "Spicy Andhra-style full meal.", []),
                        ("Non-Veg Thali", "320.00", False, "Chicken curry, egg, rice and sides.", []),
                    ],
                },
            },
        ],
    },
    {
        "key": "boi",
        "country": "US",
        "country_name": "USA",
        "state": "Idaho",
        "city": "Boise",
        "currency": "USD",
        "locale": "en-US",
        "phone_prefix": "+12085550",  # +1 208 555 0101: 10-digit numbers, as the apps require
        "scope": "US-ID-BOI",
        "partner": "Boise Partner",
        "customers": [
            ("Emily Carter", "1510 N 13th St", "North End", "83702", 43.6290, -116.2070),
            ("Noah Johnson", "220 W Main St", "Downtown", "83702", 43.6150, -116.2023),
            ("Olivia Brown", "3015 W Overland Rd", "Boise Bench", "83705", 43.5900, -116.2350),
            ("Liam Davis", "4880 W Emerald St", "West Boise", "83706", 43.6080, -116.2700),
            ("Sofia Garcia", "2200 S Broadway Ave", "Boise State", "83706", 43.6000, -116.1990),
        ],
        "riders": ["Jake Miller", "Ana Torres", "Sam Nguyen"],
        # Signing up (P18 board "Almost ready to ride, Jordan"): licence checked and payouts set up,
        # insurance still to upload, background check after that. Can't go online yet.
        "new_riders": ["Jordan Lee"],
        "restaurants": [
            {
                "name": "Boise Bowl Co.",  # board ("near Hyde Park")
                "slug": "boise-bowl-co-hyde-park",
                "area": "Hyde Park",
                "street": "1520 N 13th St",
                "zip": "83702",
                "lat": 43.6295,
                "lng": -116.2008,
                "cuisines": ["Bowls", "Healthy"],
                "description": "Grain and poke bowls made to order.",
                "rating": 4.7,
                "eta": (20, 30),
                "delivery_fee": "2.99",
                "min_order": "12.00",
                "tags": ["healthy"],
                "menu": {
                    "Bowls": [
                        ("Teriyaki Chicken Bowl", "14.50", False, "Grilled chicken, rice, greens, teriyaki.", []),
                        ("Salmon Poke Bowl", "16.00", False, "Salmon, edamame, cucumber, sesame.", []),
                        ("Crispy Tofu Bowl", "13.00", True, "Tofu, quinoa, roasted vegetables.", []),
                    ],
                    "Sides": [("Miso Soup", "4.00", True, "Tofu, scallion, wakame.", [])],
                },
            },
            {
                "name": "Basque Corner Kitchen",
                "slug": "basque-corner-kitchen-downtown",
                "area": "Downtown",
                "street": "608 W Grove St",
                "zip": "83702",
                "lat": 43.6142,
                "lng": -116.1990,
                "cuisines": ["Basque", "Spanish"],
                "description": "Chorizo, croquetas and paella from the Basque Block.",
                "rating": 4.6,
                "eta": (25, 35),
                "delivery_fee": "3.49",
                "min_order": "15.00",
                "tags": ["local"],
                "menu": {
                    "Pintxos": [
                        ("Chorizo Sandwich", "12.00", False, "Grilled chorizo, pimiento, bread.", []),
                        ("Ham Croquetas (4)", "9.00", False, "Serrano ham, béchamel.", []),
                    ],
                    "Mains": [
                        ("Seafood Paella", "22.00", False, "Saffron rice, shrimp, mussels.", []),
                        ("Solomo", "15.00", False, "Marinated pork loin, peppers.", []),
                    ],
                },
            },
            {
                "name": "Treasure Valley Tandoor",
                "slug": "treasure-valley-tandoor-bench",
                "area": "Boise Bench",
                "street": "2950 W Overland Rd",
                "zip": "83705",
                "lat": 43.5905,
                "lng": -116.2330,
                "cuisines": ["Indian", "Tandoor"],
                "description": "North Indian curries and tandoor breads.",
                "rating": 4.5,
                "eta": (30, 45),
                "delivery_fee": "3.99",
                "min_order": "15.00",
                "tags": ["indian"],
                "menu": {
                    "Curries": [
                        ("Butter Chicken", "17.00", False, "Tandoori chicken in tomato-butter gravy.", []),
                        ("Paneer Tikka Masala", "15.00", True, "Paneer in spiced tomato cream.", []),
                        ("Chicken Biryani", "16.00", False, "Basmati, chicken, raita.", []),
                    ],
                    "Breads": [("Garlic Naan", "4.00", True, "From the tandoor.", [])],
                },
            },
            {
                "name": "Foothills Pizza Co.",
                "slug": "foothills-pizza-co-north-end",
                "area": "North End",
                "street": "1706 N 18th St",
                "zip": "83702",
                "lat": 43.6320,
                "lng": -116.2110,
                "cuisines": ["Pizza", "Italian"],
                "description": "Wood-fired pies with Idaho toppings.",
                "rating": 4.4,
                "eta": (25, 40),
                "delivery_fee": "2.49",
                "min_order": "15.00",
                "tags": ["pizza"],
                "menu": {
                    "Pizza": [
                        ("Margherita", "15.00", True, "Tomato, mozzarella, basil.", []),
                        ("Pepperoni", "17.00", False, "Cup-and-char pepperoni.", []),
                        ("Idaho Potato Pizza", "18.00", True, "Russet, rosemary, garlic cream.", []),
                    ],
                    "Salads": [("Caesar Salad", "9.00", False, "Romaine, parmesan, anchovy dressing.", [])],
                },
            },
            {
                "name": "Spud & Sage",
                "slug": "spud-and-sage-downtown",
                "area": "Downtown",
                "street": "105 S 6th St",
                "zip": "83702",
                "lat": 43.6145,
                "lng": -116.2035,
                "cuisines": ["American", "Comfort"],
                "description": "Idaho potatoes every way, finger steaks and huckleberry shakes.",
                "rating": 4.3,
                "eta": (20, 35),
                "delivery_fee": "2.99",
                "min_order": "10.00",
                "tags": ["comfort"],
                "menu": {
                    "Mains": [
                        ("Loaded Baked Potato", "11.00", True, "Cheddar, sour cream, chives.", []),
                        ("Finger Steaks", "14.00", False, "Battered sirloin strips, fry sauce.", []),
                    ],
                    "Sides": [("Fry Sauce Fries", "6.00", True, "Hand-cut, with Idaho fry sauce.", [])],
                    "Drinks": [("Huckleberry Shake", "7.00", True, "Wild huckleberry, vanilla ice cream.", [])],
                },
            },
        ],
    },
]

# Admin console users (password ADMIN_PASSWORD), one per role and scope.
# (email, name, country, [(role, scope)])
ADMINS = [
    ("admin@example.com", "BhojanGo Admin", "US", [("super_admin", "*")]),
    ("cm.in@example.com", "India Country Manager", "IN", [("country_manager", "IN")]),
    ("cm.us@example.com", "USA Country Manager", "US", [("country_manager", "US")]),
    ("ops.hyd@example.com", "Hyderabad City Ops", "IN", [("city_ops", "IN-TG-HYD")]),
    ("ops.boi@example.com", "Boise City Ops", "US", [("city_ops", "US-ID-BOI")]),
    ("support.hyd@example.com", "Hyderabad Support", "IN", [("support_agent", "IN-TG-HYD")]),
    ("support.boi@example.com", "Boise Support", "US", [("support_agent", "US-ID-BOI")]),
    ("finance.in@example.com", "India Finance", "IN", [("finance", "IN")]),
    ("finance.us@example.com", "USA Finance", "US", [("finance", "US")]),
    ("viewer@example.com", "Read-only Viewer", "US", [("viewer", "IN"), ("viewer", "US")]),
]


# ── Markets (P6) ──────────────────────────────────────────────────────────────
# Zones are simple boxes (south, west, north, east) drawn so every seeded
# restaurant and customer address falls inside an open zone. Admins redraw
# them on the map in the admin console.
COUNTRIES = [
    {
        "code": "IN", "name": "India", "currency": "INR", "locales": ["en-IN", "hi-IN", "te-IN"],
        "timezone": "Asia/Kolkata", "distance_unit": "km", "phone_code": "+91",
        "payment_providers": ["razorpay"], "tax_regime": "gst", "status": "live",
        "settings": {"fssai_required": True, "sms_dlt_required": True, "payment_methods": ["upi", "card", "wallet"]},
        "regions": [
            {
                "code": "IN-TG", "name": "Telangana", "status": "live", "settings": {},
                "cities": [
                    {
                        "code": "IN-TG-HYD", "name": "Hyderabad", "status": "live", "center": (17.4126, 78.4071),
                        "service_hours": {"open": "07:00", "close": "23:30"}, "settings": {},
                        "zones": [
                            ("Hitech City", (17.440, 78.370, 17.460, 78.388), "149", "live", "#0B5D66"),
                            ("Madhapur", (17.440, 78.388, 17.460, 78.405), "99", "live", "#5BA3AA"),
                            ("Kondapur", (17.460, 78.350, 17.475, 78.370), "99", "live", "#2E7D86"),
                            ("Gachibowli", (17.415, 78.335, 17.455, 78.370), "99", "live", "#D4932A"),
                            ("Jubilee Hills", (17.405, 78.395, 17.440, 78.445), "149", "live", "#7FB7BD"),
                            ("Tolichowki", (17.385, 78.400, 17.405, 78.430), "99", "live", "#B5762A"),
                            ("Old City", (17.350, 78.460, 17.375, 78.490), "99", "live", "#8C6A2E"),
                            ("Kokapet", (17.390, 78.320, 17.410, 78.345), "149", "draft", "#4C5A5E"),
                        ],
                    },
                    {"code": "IN-TG-WGL", "name": "Warangal", "status": "draft", "center": (17.9689, 79.5941),
                     "service_hours": None, "settings": {}, "zones": []},
                ],
            },
            {
                "code": "IN-AP", "name": "Andhra Pradesh", "status": "draft", "settings": {},
                "cities": [
                    {"code": "IN-AP-VSKP", "name": "Visakhapatnam", "status": "draft", "center": (17.6868, 83.2185),
                     "service_hours": None, "settings": {}, "zones": []},
                    {"code": "IN-AP-VJA", "name": "Vijayawada", "status": "draft", "center": (16.5062, 80.6480),
                     "service_hours": None, "settings": {}, "zones": []},
                ],
            },
        ],
    },
    {
        "code": "US", "name": "United States", "currency": "USD", "locales": ["en-US"],
        "timezone": "America/New_York", "distance_unit": "mi", "phone_code": "+1",
        "payment_providers": ["stripe"], "tax_regime": "us_sales_tax", "status": "live",
        "settings": {"payment_methods": ["card", "apple_pay", "google_pay"]},
        "regions": [
            {
                "code": "US-ID", "name": "Idaho", "status": "live", "timezone": "America/Boise", "settings": {},
                "cities": [
                    {
                        "code": "US-ID-BOI", "name": "Boise", "status": "beta", "center": (43.6150, -116.2023),
                        "service_hours": {"open": "08:00", "close": "23:00"}, "settings": {},
                        "zones": [
                            ("Downtown", (43.605, -116.215, 43.625, -116.185), "15", "live", "#0B5D66"),
                            ("North End", (43.625, -116.225, 43.645, -116.195), "15", "live", "#5BA3AA"),
                            ("Boise Bench", (43.580, -116.250, 43.605, -116.215), "15", "live", "#D4932A"),
                            ("West Boise", (43.598, -116.290, 43.620, -116.250), "20", "live", "#2E7D86"),
                            ("Boise State", (43.590, -116.215, 43.605, -116.185), "15", "live", "#7FB7BD"),
                        ],
                    },
                ],
            },
        ],
    },
]


# ── Rules (P7) ────────────────────────────────────────────────────────────────
# Published from 2026-01-01. Hyderabad reproduces the worked example in
# docs/specs/01-structure.md section 4 (₹638.22). Rates are illustrative
# (the spec says: confirm tax with a CA); admins change them in the console.
# (family, template, key, name, scope_level, scope_id, params)
# A restaurant scope_id is the restaurant's slug here; seed.py maps it to the id.
RULES = [
    # India
    ("tax", "rate_on_lines", "gst_food", "GST on food and packaging", "country", "IN",
     {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"], "collected_by": "platform"}),
    ("tax", "rate_on_lines", "gst_fees", "GST on platform fees", "country", "IN",
     {"label": "GST on platform fees", "rate_percent": 18,
      "target_lines": ["delivery_fee", "service_fee", "surge", "small_order_fee", "late_night_fee"], "collected_by": "platform"}),
    ("commission", "percent_by_tier", None, "Commission by tier", "country", "IN",
     {"tiers": {"A": 18, "B": 15, "C": 12}, "default_tier": "B"}),
    ("commission", "payout_schedule", None, "Weekly payouts", "country", "IN", {"frequency": "weekly", "day": "mon", "hold_days": 2}),
    ("rider_pay", "base_distance_wait", None, "Rider pay", "country", "IN",
     {"base": 25, "per_unit": 6, "per_wait_minute": 1, "free_wait_minutes": 5}),
    ("rider_pay", "hourly_floor", None, "Hourly floor", "city", "IN-TG-HYD", {"per_active_hour": 120}),
    ("rider_pay", "batch_bonus", None, "Batch bonus (each extra drop-off)", "city", "IN-TG-HYD", {"per_extra_order": 10}),
    ("delivery_fee", "distance_slabs", None, "Hyderabad delivery fee", "city", "IN-TG-HYD",
     {"slabs": [{"up_to": 3, "fee": 25}, {"up_to": 6, "fee": 35}, {"up_to": 10, "fee": 50}]}),
    ("customer_fee", "service_fee", None, "Service fee", "city", "IN-TG-HYD", {"percent": 2, "min": 5, "max": 15}),
    ("customer_fee", "small_order_fee", None, "Small order fee", "city", "IN-TG-HYD", {"below": 99, "fee": 15}),
    ("customer_fee", "surge_levy", None, "Evening surge", "city", "IN-TG-HYD",
     {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 15}),
    ("customer_fee", "packaging_levy", None, "Packaging", "restaurant", "spice-route-kitchen-madhapur", {"amount": 10}),
    ("promotion", "percent_off", "hyd_launch", "10% off, up to ₹50", "city", "IN-TG-HYD",
     {"percent": 10, "max_discount": 50, "funded_by": "platform", "budget_cap": 100000}),
    ("business", "max_radius", None, "Max delivery distance", "country", "IN", {"distance": 10}),
    ("business", "tip_presets", None, "Tip presets", "country", "IN", {"amounts": [10, 20, 30], "default_index": 1}),
    ("business", "cod_limit", None, "Cash on delivery limit", "country", "IN", {"max_amount": 1000}),
    ("business", "support_refund_limit", None, "Support refund limit", "country", "IN", {"max_per_order": 500}),
    ("business", "auto_refund_limit", None, "Automatic refunds for problem reports", "city", "IN-TG-HYD", {"max_per_order": 100}),
    # USA
    ("tax", "external", None, "Sales tax (Stripe Tax)", "country", "US", {"provider": "stripe_tax"}),
    ("commission", "percent_by_tier", None, "Commission by tier", "country", "US", {"tiers": {"A": 25, "B": 20, "C": 15}, "default_tier": "B"}),
    ("commission", "payout_schedule", None, "Weekly payouts", "country", "US", {"frequency": "weekly", "day": "mon", "hold_days": 2}),
    ("rider_pay", "base_distance_wait", None, "Rider pay", "country", "US",
     {"base": "3.00", "per_unit": "1.00", "per_wait_minute": "0.25", "free_wait_minutes": 5}),
    ("rider_pay", "hourly_floor", None, "Hourly floor", "city", "US-ID-BOI", {"per_active_hour": 15}),
    # Item 2: a later drop-off of a batch pays no base, but distance + waiting + this.
    ("rider_pay", "batch_bonus", None, "Batch bonus (each extra drop-off)", "city", "US-ID-BOI", {"per_extra_order": 1.5}),
    ("delivery_fee", "distance_slabs", None, "Boise delivery fee", "city", "US-ID-BOI",
     {"slabs": [{"up_to": 2, "fee": "1.99"}, {"up_to": 4, "fee": "3.49"}, {"up_to": 6, "fee": "4.99"}]}),
    ("customer_fee", "service_fee", None, "Service fee", "city", "US-ID-BOI", {"percent": 5, "min": 1, "max": 5}),
    ("customer_fee", "small_order_fee", None, "Small order fee", "city", "US-ID-BOI", {"below": 12, "fee": 2}),
    ("business", "max_radius", None, "Max delivery distance", "country", "US", {"distance": 6}),
    ("business", "tip_presets", None, "Tip presets", "country", "US", {"amounts": [2, 3, 5], "default_index": 1}),
    ("business", "cod_limit", None, "Cash on delivery off", "country", "US", {"max_amount": 0}),
    ("business", "support_refund_limit", None, "Support refund limit", "country", "US", {"max_per_order": 25}),
    ("business", "auto_refund_limit", None, "Automatic refunds for problem reports", "city", "US-ID-BOI", {"max_per_order": 5}),
    # Platform defaults (docs/specs/01-structure.md section 3, business rules)
    ("business", "accept_timeout", None, "Restaurant accept timeout", "platform", "*", {"seconds": 180}),
    ("business", "unpaid_auto_cancel", None, "Unpaid orders cancel", "platform", "*", {"minutes": 10}),
    ("business", "cancel_window", None, "Free cancellation window", "platform", "*", {"minutes": 2}),
    ("business", "refund_window", None, "Refund requests", "platform", "*", {"hours": 72}),
    ("business", "dispatch_offer_timeout", None, "Rider offer timeout", "platform", "*", {"seconds": 30}),
    # What payment providers keep (item 1): Stripe in the US (2.9% + $0.30, Stripe Tax 0.5%),
    # Razorpay in India (2% on cards, wallets and net banking; UPI free). Editable in admin.
    ("business", "payment_fees", None, "Payment fees (Stripe)", "country", "US",
     {"methods": {"card": {"percent": 2.9, "fixed": 0.30}, "wallet": {"percent": 2.9, "fixed": 0.30}}, "tax_service_percent": 0.5}),
    ("business", "payment_fees", None, "Payment fees (Razorpay)", "country", "IN",
     {"methods": {"card": {"percent": 2, "fixed": 0}, "wallet": {"percent": 2, "fixed": 0},
                  "net_banking": {"percent": 2, "fixed": 0}, "upi": {"percent": 0, "fixed": 0}}, "tax_service_percent": 0}),
    # Task 43: live batching is a per-city switch, off; the engine runs in shadow everywhere.
    ("business", "batching", None, "Batching (one rider, two orders)", "city", "IN-TG-HYD", {"live": False}),
    ("business", "batching", None, "Batching (one rider, two orders)", "city", "US-ID-BOI", {"live": False}),
]


# ── Store hours, FSSAI licences and tiers (P10) ───────────────────────────────
# slug -> [(days, opens, closes)]; days "daily" or "mon..sun" style lists.
# A close earlier than the open runs past midnight.
DAILY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
HOURS = {
    "spice-route-kitchen-madhapur": [(DAILY, "11:00", "23:30")],
    "curry-leaf-gachibowli": [(DAILY, "11:30", "23:00")],
    "charminar-chai-house-old-city": [(DAILY, "06:30", "23:30")],
    "banjara-dosa-co-banjara-hills": [(DAILY, "07:00", "22:30")],
    # lunch and dinner, closed in between
    "hitech-thali-hitec-city": [(DAILY, "11:00", "15:30"), (DAILY, "18:30", "23:00")],
    "boise-bowl-co-hyde-park": [(DAILY, "11:00", "22:00")],
    "basque-corner-kitchen-downtown": [(["tue", "wed", "thu", "fri", "sat", "sun"], "11:00", "21:30")],  # closed Mondays
    "treasure-valley-tandoor-bench": [(DAILY, "11:30", "22:00")],
    # open late at the weekend: runs past midnight
    "foothills-pizza-co-north-end": [(["sun", "mon", "tue", "wed", "thu"], "11:00", "23:00"), (["fri", "sat"], "11:00", "01:00")],
    "spud-and-sage-downtown": [(DAILY, "10:00", "22:00")],
}
HOLIDAYS = [("boise-bowl-co-hyde-park", "2026-12-25", "Christmas Day")]
FSSAI = {  # India: 14-digit licence numbers (placeholders) and expiry dates
    "spice-route-kitchen-madhapur": ("13626010000101", "2027-09-30"),
    "curry-leaf-gachibowli": ("13626010000102", "2027-06-30"),
    "charminar-chai-house-old-city": ("13626010000103", "2027-03-31"),
    "banjara-dosa-co-banjara-hills": ("13626010000104", "2028-01-31"),
    "hitech-thali-hitec-city": ("13626010000105", "2027-12-31"),
}
TIERS = {"spice-route-kitchen-madhapur": "B", "hitech-thali-hitec-city": "A", "boise-bowl-co-hyde-park": "B"}
