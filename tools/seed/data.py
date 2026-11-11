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
        "phone_prefix": "+9190000",
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
        "phone_prefix": "+120855500",
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
