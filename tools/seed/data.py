"""Seed data: India ▸ Telangana ▸ Hyderabad and USA ▸ Idaho ▸ Boise.

Restaurants, dishes and prices marked "board" come from the design board
(docs/specs/README.md, "Screen designs"); the rest are plausible placeholders.
Markets don't have their own tables yet (P6), so each record carries country,
state and city.
"""
import re

PASSWORD = "BhojanGo123"  # every seeded account; local and staging only
ADMIN_PASSWORD = "BhojanGoAdmin1"
# Seeded admins sign in with two-step codes (Round 8, D5). Outside production the
# seed gives them an authenticator key: this fixed one locally and in CI (the
# tests and e2e compute codes from it; backend/core_api/modules/identity/tests/signin.py),
# a random one per admin on hosted QA (written to the logins file only). Never in production.
SEED_TOTP_SECRET = "BHOJANGOSEEDADMINTOTPKEY234567AB"  # gitleaks:allow (non-production seed key)

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
                "pickup": True,  # R32: takes pickup orders
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
                "pickup": True,  # R32: takes pickup orders
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
                "pickup": True,  # R32: takes pickup orders
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
                "min_order": "15.00",  # R36: Boise Bowl's own minimum ($14.50 Teriyaki bowl: "Add $0.50 more")
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
    # R27: one read-only viewer per country (R26: one viewer for both read US Finance as "Viewer (IN)")
    ("viewer@example.com", "Read-only Viewer", "IN", [("viewer", "IN")]),
    ("viewer.us@example.com", "USA Read-only Viewer", "US", [("viewer", "US")]),
]


# ── Documents a kitchen needs (Markets country setting kitchen_documents) ─────
# Shown on the website's "Add your kitchen" page in the visitor's language; admins
# edit them in Markets -> country. English is required, other languages optional.
IN_KITCHEN_DOCUMENTS = [
    {"key": "fssai",
     "title": {"en": "FSSAI licence", "hi": "FSSAI लाइसेंस", "te": "FSSAI లైసెన్స్", "ta": "FSSAI உரிமம்",
               "kn": "FSSAI ಪರವಾನಗಿ", "mr": "FSSAI परवाना", "bn": "FSSAI লাইসেন্স"},
     "why": {"en": "Every kitchen that sells food in India needs one. Customers see it on your page.",
             "hi": "भारत में खाना बेचने वाली हर किचन के लिए ज़रूरी है। ग्राहक इसे आपके पेज पर देखते हैं।",
             "te": "భారత్‌లో ఆహారం అమ్మే ప్రతి కిచెన్‌కు ఇది తప్పనిసరి. కస్టమర్లు దీన్ని మీ పేజీలో చూస్తారు.",
             "ta": "இந்தியாவில் உணவு விற்கும் ஒவ்வொரு சமையலறைக்கும் இது தேவை. வாடிக்கையாளர்கள் இதை உங்கள் பக்கத்தில் பார்ப்பார்கள்.",
             "kn": "ಭಾರತದಲ್ಲಿ ಆಹಾರ ಮಾರುವ ಪ್ರತಿ ಕಿಚನ್‌ಗೂ ಇದು ಬೇಕು. ಗ್ರಾಹಕರು ಇದನ್ನು ನಿಮ್ಮ ಪುಟದಲ್ಲಿ ನೋಡುತ್ತಾರೆ.",
             "mr": "भारतात अन्न विकणाऱ्या प्रत्येक किचनला हा लागतो. ग्राहक तो तुमच्या पानावर पाहतात.",
             "bn": "ভারতে খাবার বিক্রি করা প্রতিটি কিচেনের এটি লাগে। গ্রাহকরা এটি আপনার পাতায় দেখেন।"}},
    {"key": "gstin",
     "title": {"en": "GST registration (GSTIN)", "hi": "GST पंजीकरण (GSTIN)", "te": "GST నమోదు (GSTIN)", "ta": "GST பதிவு (GSTIN)",
               "kn": "GST ನೋಂದಣಿ (GSTIN)", "mr": "GST नोंदणी (GSTIN)", "bn": "GST নিবন্ধন (GSTIN)"},
     "why": {"en": "Your GSTIN goes on customers' bills, so the GST on your food is charged and filed correctly.",
             "hi": "आपका GSTIN ग्राहकों के बिल पर आता है, ताकि आपके खाने पर GST सही लगे और सही भरा जाए।",
             "te": "మీ GSTIN కస్టమర్ల బిల్లులపై ఉంటుంది, దాంతో మీ ఆహారంపై GST సరిగ్గా వసూలై, సరిగ్గా దాఖలవుతుంది.",
             "ta": "உங்கள் GSTIN வாடிக்கையாளர் பில்களில் வரும், அதனால் உங்கள் உணவுக்கான GST சரியாக வசூலிக்கப்பட்டு தாக்கல் செய்யப்படும்.",
             "kn": "ನಿಮ್ಮ GSTIN ಗ್ರಾಹಕರ ಬಿಲ್‌ಗಳಲ್ಲಿ ಬರುತ್ತದೆ, ಹೀಗಾಗಿ ನಿಮ್ಮ ಆಹಾರದ GST ಸರಿಯಾಗಿ ವಸೂಲಾಗಿ ಸಲ್ಲಿಕೆಯಾಗುತ್ತದೆ.",
             "mr": "तुमचा GSTIN ग्राहकांच्या बिलावर येतो, त्यामुळे तुमच्या अन्नावरचा GST बरोबर आकारला आणि भरला जातो.",
             "bn": "আপনার GSTIN গ্রাহকদের বিলে থাকে, যাতে আপনার খাবারের GST ঠিকমতো নেওয়া ও জমা হয়।"}},
    {"key": "pan",
     "title": {"en": "PAN", "hi": "PAN", "te": "PAN", "ta": "PAN", "kn": "PAN", "mr": "PAN", "bn": "PAN"},
     "why": {"en": "Our payments partner checks it before your first payout.",
             "hi": "आपके पहले भुगतान से पहले हमारा पेमेंट पार्टनर इसे जांचता है।",
             "te": "మీ మొదటి చెల్లింపుకు ముందు మా పేమెంట్స్ భాగస్వామి దీన్ని తనిఖీ చేస్తుంది.",
             "ta": "உங்கள் முதல் பணப்பரிமாற்றத்துக்கு முன் எங்கள் கட்டணக் கூட்டாளர் இதைச் சரிபார்க்கிறார்.",
             "kn": "ನಿಮ್ಮ ಮೊದಲ ಪಾವತಿಗೆ ಮೊದಲು ನಮ್ಮ ಪಾವತಿ ಪಾಲುದಾರರು ಇದನ್ನು ಪರಿಶೀಲಿಸುತ್ತಾರೆ.",
             "mr": "तुमच्या पहिल्या पेआउटपूर्वी आमचा पेमेंट पार्टनर तो तपासतो.",
             "bn": "আপনার প্রথম পেআউটের আগে আমাদের পেমেন্ট পার্টনার এটি যাচাই করে।"}},
    {"key": "bank",
     "title": {"en": "Bank account", "hi": "बैंक खाता", "te": "బ్యాంక్ ఖాతా", "ta": "வங்கிக் கணக்கு", "kn": "ಬ್ಯಾಂಕ್ ಖಾತೆ",
               "mr": "बँक खाते", "bn": "ব্যাঙ্ক অ্যাকাউন্ট"},
     "why": {"en": "In the kitchen's or the owner's name: where your weekly payout lands.",
             "hi": "किचन या मालिक के नाम पर: आपका साप्ताहिक भुगतान यहीं आता है।",
             "te": "కిచెన్ పేరు మీద లేదా యజమాని పేరు మీద: మీ వారపు చెల్లింపు ఇక్కడికే వస్తుంది.",
             "ta": "சமையலறை அல்லது உரிமையாளர் பெயரில்: உங்கள் வாராந்திரப் பணம் இங்கே வரும்.",
             "kn": "ಕಿಚನ್ ಅಥವಾ ಮಾಲೀಕರ ಹೆಸರಿನಲ್ಲಿ: ನಿಮ್ಮ ವಾರದ ಪಾವತಿ ಇಲ್ಲಿಗೆ ಬರುತ್ತದೆ.",
             "mr": "किचन किंवा मालकाच्या नावावर: तुमचे साप्ताहिक पेआउट इथे जमा होते.",
             "bn": "কিচেন বা মালিকের নামে: আপনার সাপ্তাহিক পেআউট এখানেই আসে।"}},
]
US_KITCHEN_DOCUMENTS = [
    {"key": "health_permit",
     "title": {"en": "Food establishment or health permit", "es": "Permiso sanitario o de establecimiento de alimentos"},
     "why": {"en": "Issued by your city or county health department. We may ask to see it during review.",
             "es": "Lo emite el departamento de salud de tu ciudad o condado. Podemos pedirlo durante la revisión."}},
    {"key": "ein",
     "title": {"en": "EIN (or SSN for a sole proprietor)", "es": "EIN (o SSN si eres propietario único)"},
     "why": {"en": "Your tax ID. Our payments partner verifies it before your first payout.",
             "es": "Tu identificación fiscal. Nuestro socio de pagos la verifica antes de tu primer pago."}},
    {"key": "bank",
     "title": {"en": "Bank account", "es": "Cuenta bancaria"},
     "why": {"en": "In the business's or the owner's name: where your weekly payout lands.",
             "es": "A nombre del negocio o del dueño: ahí llega tu pago semanal."}},
]


# ── Markets (P6) ──────────────────────────────────────────────────────────────
# Zones are simple boxes (south, west, north, east) drawn so every seeded
# restaurant and customer address falls inside an open zone. Admins redraw
# them on the map in the admin console.
COUNTRIES = [
    {
        "code": "IN", "name": "India", "currency": "INR", "locales": ["en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN", "mr-IN", "bn-IN"],
        # R27: a country's zone is the default for a new city; payout weeks are counted in payout_timezone.
        "timezone": "Asia/Kolkata", "payout_timezone": "Asia/Kolkata", "distance_unit": "km", "phone_code": "+91",
        "payment_providers": ["razorpay"], "tax_regime": "gst", "status": "live",
        "payout_provider": "razorpay_route",  # who pays kitchens and riders (Markets; fake when no keys: providers.py)
        "settings": {"fssai_required": True, "sms_dlt_required": True, "payment_methods": ["upi", "card", "wallet"],
                     # R15: who operates BhojanGo here (Srini's decision). The rest (address, support,
                     # CIN, GSTIN, grievance officer) is filled in admin before launch: never invented.
                     "legal": {"name": "DeepTrics Software Solutions Pvt Ltd"},
                     # the website's landing hero (Markets -> India -> Hero dish): a photo library slug
                     "hero_photo": "south-indian-thali",
                     "emergency_number": "112",  # the rider app's SOS button
                     # R22 (S11): the most a kitchen's own offer may give (Markets -> India -> Kitchen offer ceiling)
                     "kitchen_offer_ceiling": {"flat_off": "200", "max_discount": "200", "weekly_cap": "25000"},
                     # the website's /deliver page (Markets -> India -> Delivery partners); documents are
                     # the delivery app's onboarding steps (markets/service/delivery.py APP_STEP)
                     "delivery_partner": {"min_age": 18, "vehicles": ["motorcycle", "scooter", "electric_scooter"],
                                          "documents": ["driving_licence", "vehicle_rc_insurance", "bank_account",
                                                        "background_check"],
                                          "example_trip": {"distance": 3}, "app_links": {"android": None, "ios": None}},
                     "kitchen_documents": IN_KITCHEN_DOCUMENTS},
        "regions": [
            {
                "code": "IN-TG", "name": "Telangana", "status": "live", "settings": {},
                "cities": [
                    {
                        "code": "IN-TG-HYD", "name": "Hyderabad", "timezone": "Asia/Kolkata", "status": "live", "center": (17.4126, 78.4071),
                        "service_hours": {"open": "07:00", "close": "23:30"}, "settings": {},
                        "zones": [
                            ("Hitech City", (17.440, 78.370, 17.460, 78.388), "0", "live", "#0B5D66"),
                            ("Madhapur", (17.440, 78.388, 17.460, 78.405), "0", "live", "#5BA3AA"),
                            ("Kondapur", (17.460, 78.350, 17.475, 78.370), "0", "live", "#2E7D86"),
                            ("Gachibowli", (17.415, 78.335, 17.455, 78.370), "0", "live", "#D4932A"),
                            ("Jubilee Hills", (17.405, 78.395, 17.440, 78.445), "0", "live", "#7FB7BD"),
                            ("Tolichowki", (17.385, 78.400, 17.405, 78.430), "0", "live", "#B5762A"),
                            ("Old City", (17.350, 78.460, 17.375, 78.490), "0", "live", "#8C6A2E"),
                            ("Kokapet", (17.390, 78.320, 17.410, 78.345), "0", "draft", "#4C5A5E"),
                        ],
                    },
                    {"code": "IN-TG-WGL", "name": "Warangal", "timezone": "Asia/Kolkata", "status": "draft", "center": (17.9689, 79.5941),
                     "service_hours": None, "settings": {}, "zones": []},
                ],
            },
            {
                "code": "IN-AP", "name": "Andhra Pradesh", "status": "draft", "settings": {},
                "cities": [
                    {"code": "IN-AP-VSKP", "name": "Visakhapatnam", "timezone": "Asia/Kolkata", "status": "soon", "center": (17.6868, 83.2185),
                     "service_hours": None, "settings": {}, "zones": []},
                    {"code": "IN-AP-VJA", "name": "Vijayawada", "timezone": "Asia/Kolkata", "status": "soon", "center": (16.5062, 80.6480),
                     "service_hours": None, "settings": {}, "zones": []},
                ],
            },
        ],
    },
    {
        "code": "US", "name": "United States", "currency": "USD", "locales": ["en-US", "es-US"],
        # R27: every US city has its own zone (Boise: America/Boise); payout weeks run on Boise's clock for now.
        "timezone": "America/New_York", "payout_timezone": "America/Boise", "distance_unit": "mi", "phone_code": "+1",
        "payment_providers": ["stripe"], "tax_regime": "us_sales_tax", "status": "live",
        "payout_provider": "stripe_connect",
        "settings": {"payment_methods": ["card", "apple_pay", "google_pay"], "hero_photo": "pepperoni-pizza",
                     "legal": {"name": "DeepTrics LLC"},  # R15 (Srini's decision); the rest is filled in admin
                     "emergency_number": "911",
                     "kitchen_offer_ceiling": {"flat_off": "15", "max_discount": "15", "weekly_cap": "1500"},  # R22 (S11)
                     "delivery_partner": {"min_age": 18, "vehicles": ["car", "motorcycle", "scooter"],
                                          "documents": ["drivers_license", "vehicle_insurance", "payout_account",
                                                        "background_check"],
                                          "example_trip": {"distance": 2}, "app_links": {"android": None, "ios": None}},
                     "kitchen_documents": US_KITCHEN_DOCUMENTS},
        "regions": [
            {
                "code": "US-ID", "name": "Idaho", "status": "live", "timezone": "America/Boise", "settings": {},
                "cities": [
                    {
                        # R27: live (R26: admin Markets said beta while the website listed it live)
                        "code": "US-ID-BOI", "name": "Boise", "timezone": "America/Boise", "status": "live", "center": (43.6150, -116.2023),
                        "service_hours": {"open": "08:00", "close": "23:00"}, "settings": {},
                        "zones": [
                            ("Downtown", (43.605, -116.215, 43.625, -116.185), "0", "live", "#0B5D66"),
                            ("North End", (43.625, -116.225, 43.645, -116.195), "0", "live", "#5BA3AA"),
                            ("Boise Bench", (43.580, -116.250, 43.605, -116.215), "0", "live", "#D4932A"),
                            ("West Boise", (43.598, -116.290, 43.620, -116.250), "0", "live", "#2E7D86"),
                            ("Boise State", (43.590, -116.215, 43.605, -116.185), "0", "live", "#7FB7BD"),
                        ],
                    },
                    # Coming soon: listed on the website's directory and collects "Notify me" sign-ups.
                    {"code": "US-ID-NMP", "name": "Nampa", "timezone": "America/Boise", "status": "soon", "center": (43.5407, -116.5635),
                     "service_hours": None, "settings": {}, "zones": []},
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
IDAHO_TAXABLE = ["food", "packaging", "platform_fee", "service_fee", "small_order_fee", "late_night_fee"]  # R33

RULES = [
    # India
    ("tax", "rate_on_lines", "gst_food", "GST on food and packaging", "country", "IN",
     # R16: a discount the platform funds doesn't lower the GST base (to confirm with a CA).
     {"label": "GST on food", "rate_percent": 5, "target_lines": ["food", "packaging"], "collected_by": "platform",
      "platform_discounts_reduce_base": False, "ca_confirmed": False}),
    ("tax", "rate_on_lines", "gst_fees", "GST on platform fees", "country", "IN",
     {"label": "GST on platform fees", "rate_percent": 18,
      "target_lines": ["delivery_fee", "platform_fee", "service_fee", "surge", "small_order_fee", "late_night_fee"], "collected_by": "platform",
      "platform_discounts_reduce_base": False, "ca_confirmed": False}),
    # R16: GST on our commission (deducted from the kitchen's payout, owed by us) and TDS under section
    # 194-O on kitchen payouts. Values to confirm with a CA; admin says so until ca_confirmed.
    ("business", "commission_tax", None, "GST on commission", "country", "IN",
     {"label": "GST on commission", "rate_percent": 18, "ca_confirmed": False}),
    ("business", "payout_tds", None, "TDS on restaurant payouts (194-O)", "country", "IN",
     {"label": "TDS (section 194-O)", "rate_percent": 0, "base": "gross_sales", "ca_confirmed": False}),
    # R29 fee model v2: commission defaults to 0%; the customer pays a platform fee instead.
    ("commission", "percent", None, "Restaurant commission", "country", "IN", {"percent": 0}),
    ("fee", "platform_fee_pct", None, "Platform fee", "country", "IN", {"percent": 10}),
    # R30: ₹15 (₹100 of food -> ₹15, ₹300 -> ₹30); configurable per country, state, city and restaurant in admin
    # (Pricing -> Fees).
    ("fee", "min_platform_fee", None, "Minimum platform fee", "country", "IN", {"amount": 15}),
    # R32: pickup orders: 5% of food (same minimum); platform-funded offers don't lower the GST base (default)
    ("fee", "pickup_platform_fee_pct", None, "Pickup platform fee", "country", "IN", {"percent": 5}),
    ("business", "gst_offer_base", None, "Platform-funded offers reduce GST base", "country", "IN",
     {"platform_offers_reduce_base": False}),
    # R30: per payment method (Razorpay's standard rates; UPI free); cash has none. Production uses the fee
    # Razorpay reports for each payment.
    ("fee", "card_fee_estimate", None, "Payment fee estimate (Razorpay)", "country", "IN",
     {"card": {"percent": 2, "fixed": 0}, "upi": {"percent": 0, "fixed": 0}, "wallet": {"percent": 2, "fixed": 0},
      "net_banking": {"percent": 2, "fixed": 0}}),
    ("commission", "payout_schedule", None, "Weekly payouts", "country", "IN", {"frequency": "weekly", "day": "mon", "hold_days": 2}),
    # R30: the delivery partner gets the delivery fee + the whole tip, nothing else: no rider_pay rules (base,
    # hourly floor, batch bonus) and nothing topped up out of the platform fee. R31: the delivery fee comes from
    # distance bands (road km, whole rupees), up to the max delivery distance; beyond it a restaurant doesn't deliver.
    # Country default: a city launched in admin prices orders from day one (Hyderabad's own rule wins there).
    ("delivery_fee", "distance_slabs", None, "India delivery fee", "country", "IN",
     {"slabs": [{"up_to": 3, "fee": 30}, {"up_to": 5, "fee": 40}, {"up_to": 7, "fee": 50}]}),
    ("delivery_fee", "distance_slabs", None, "Hyderabad delivery fee", "city", "IN-TG-HYD",
     {"slabs": [{"up_to": 3, "fee": 30}, {"up_to": 5, "fee": 40}, {"up_to": 7, "fee": 50}]}),
    ("customer_fee", "small_order_fee", None, "Small order fee", "city", "IN-TG-HYD", {"below": 99, "fee": 15}),
    # R33: the busy-hour fee is off (0) everywhere; if it is ever turned on, all of it goes to the delivery partner.
    ("customer_fee", "surge_levy", None, "Busy-hour fee (off)", "city", "IN-TG-HYD",
     {"windows": [{"start": "19:00", "end": "21:30"}], "amount": 0}),
    ("customer_fee", "packaging_levy", None, "Packaging", "restaurant", "spice-route-kitchen-madhapur", {"amount": 10}),
    # R29: a restaurant's own commission deal (restaurant level beats the country's 0%), so the demo shows an
    # override. Dev/QA seed only: the production seed (markets_data.rules) takes no restaurant-level rule (R30).
    ("commission", "percent", None, "Commission deal", "restaurant", "spice-route-kitchen-madhapur", {"percent": 15}),
    ("promotion", "percent_off", "hyd_launch", "10% off, up to ₹50", "city", "IN-TG-HYD",
     {"percent": 10, "max_discount": 50, "funded_by": "platform", "budget_cap": 100000}),
    ("business", "max_radius", None, "Max delivery distance", "country", "IN", {"distance": 7}),  # R31: the last band
    ("business", "tip_presets", None, "Tip presets", "country", "IN", {"amounts": [10, 20, 30], "default_index": 1}),
    ("business", "cod_limit", None, "Cash on delivery limit", "country", "IN", {"max_amount": 1000}),
    ("business", "support_refund_limit", None, "Support refund limit", "country", "IN", {"max_per_order": 500}),
    ("business", "auto_refund_limit", None, "Automatic refunds for problem reports", "city", "IN-TG-HYD", {"max_per_order": 100}),
    # USA
    ("tax", "external", None, "Sales tax (Stripe Tax)", "country", "US", {"provider": "stripe_tax"}),
    # R33: Idaho (Tax Commission guidance): food and the platform fee (a service charge) are taxable; a
    # separately stated delivery fee and the tip are not. The busy-hour fee is a delivery charge (the partner's).
    ("tax", "external", None, "Idaho sales tax: taxable lines", "region", "US-ID",
     {"provider": "stripe_tax", "taxable_lines": IDAHO_TAXABLE}),
    ("business", "commission_tax", None, "Tax on commission", "country", "US", {"label": "Tax on commission", "rate_percent": 0, "ca_confirmed": False}),
    ("business", "payout_tds", None, "Tax withheld from kitchen payouts", "country", "US",
     {"label": "Tax withheld", "rate_percent": 0, "base": "gross_sales", "ca_confirmed": False}),
    # R29 fee model v2 (Idaho and Boise inherit): 0% commission; 10% platform fee on food, at least $0.99;
    # the card fee (estimate 2.9% + $0.30 of the charge less the tip) comes off the kitchen's payout.
    ("commission", "percent", None, "Restaurant commission", "country", "US", {"percent": 0}),
    ("fee", "platform_fee_pct", None, "Platform fee", "country", "US", {"percent": 10}),
    ("fee", "min_platform_fee", None, "Minimum platform fee", "country", "US", {"amount": "0.99"}),
    ("fee", "pickup_platform_fee_pct", None, "Pickup platform fee", "country", "US", {"percent": 5}),  # R32
    ("fee", "card_fee_estimate", None, "Payment fee estimate (Stripe)", "country", "US", {"card": {"percent": "2.9", "fixed": "0.30"}}),
    ("commission", "payout_schedule", None, "Weekly payouts", "country", "US", {"frequency": "weekly", "day": "mon", "hold_days": 2}),
    # R31: delivery fee from distance bands (road miles), all of it (and the tip) to the delivery partner.
    ("delivery_fee", "distance_slabs", None, "United States delivery fee", "country", "US",
     {"slabs": [{"up_to": 2, "fee": "3.50"}, {"up_to": 4, "fee": "4.50"}, {"up_to": 6, "fee": "5.50"}, {"up_to": 8, "fee": "6.50"}]}),
    ("delivery_fee", "distance_slabs", None, "Boise delivery fee", "city", "US-ID-BOI",
     {"slabs": [{"up_to": 2, "fee": "3.50"}, {"up_to": 4, "fee": "4.50"}, {"up_to": 6, "fee": "5.50"}, {"up_to": 8, "fee": "6.50"}]}),
    ("customer_fee", "small_order_fee", None, "Small order fee", "city", "US-ID-BOI", {"below": 12, "fee": 2}),
    ("business", "max_radius", None, "Max delivery distance", "country", "US", {"distance": 8}),  # R31: the last band
    ("business", "tip_presets", None, "Tip presets", "country", "US", {"amounts": [2, 3, 5], "default_index": 1}),
    ("business", "cod_limit", None, "Cash on delivery off", "country", "US", {"max_amount": 0}),
    ("business", "support_refund_limit", None, "Support refund limit", "country", "US", {"max_per_order": 25}),
    ("business", "auto_refund_limit", None, "Automatic refunds for problem reports", "city", "US-ID-BOI", {"max_per_order": 5}),
    # Platform defaults (docs/specs/01-structure.md section 3, business rules)
    ("business", "accept_timeout", None, "Restaurant accept timeout", "platform", "*", {"seconds": 180}),
    ("business", "unpaid_auto_cancel", None, "Unpaid orders cancel", "platform", "*", {"minutes": 10}),
    ("business", "cancel_window", None, "Free cancellation window", "platform", "*", {"minutes": 2}),
    ("business", "refund_window", None, "Refund requests", "platform", "*", {"hours": 72}),
    ("business", "dispatch_offer_timeout", None, "Delivery partner offer timeout", "platform", "*", {"seconds": 30}),
    # R28: a pass or a timed-out offer keeps that partner off that order for 2 minutes (never 24 hours);
    # an order with no partner after 8 minutes alerts Operations and tells the customer. Per city in admin.
    ("business", "dispatch_offer_exclusion", None, "Delivery partner pass: off that order for", "platform", "*", {"seconds": 120}),
    ("business", "no_partner_alert", None, "No delivery partner yet: alert after", "platform", "*", {"minutes": 8}),
    # What payment providers keep (item 1): Stripe in the US (2.9% + $0.30, Stripe Tax 0.5%),
    # Razorpay in India (2% on cards, wallets and net banking; UPI free). Editable in admin.
    ("business", "payment_fees", None, "Payment fees (Stripe)", "country", "US",
     {"methods": {"card": {"percent": 2.9, "fixed": 0.30}, "wallet": {"percent": 2.9, "fixed": 0.30}}, "tax_service_percent": 0.5}),
    # R15: the expected rate, used while the provider doesn't report its fees (Razorpay is faked): 2% on every method.
    ("business", "payment_fees", None, "Expected payment fees (Razorpay)", "country", "IN",
     {"methods": {"card": {"percent": 2, "fixed": 0}, "wallet": {"percent": 2, "fixed": 0},
                  "net_banking": {"percent": 2, "fixed": 0}, "upi": {"percent": 2, "fixed": 0}}, "tax_service_percent": 0}),
    # Task 43: live batching is a per-city switch, off; the engine runs in shadow everywhere.
    ("business", "batching", None, "Batching (one delivery partner, two orders)", "city", "IN-TG-HYD", {"live": False}),
    ("business", "batching", None, "Batching (one delivery partner, two orders)", "city", "US-ID-BOI", {"live": False}),
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


# ── Photos (web v2) ───────────────────────────────────────────────────────────
# The food photo library (docs/design/photos/LICENSES.md), served by the website
# from /food/<slug>-<width>.webp. A dish gets a picture only when it IS the
# library's dish: its name, ignoring case and a trailing count such as "(2)",
# equals one of that photo's names below (true equivalents only: a mutton
# biryani never borrows the chicken biryani's photo). Everything else has no
# image_url. A kitchen's cover is the photo of one of its own dishes, and no two
# kitchens in a city share one (covers()); a kitchen with no such dish has none.
PHOTO_DISHES = {
    # R36: the 8 kitchens that had no cover of their own (each is one of their dishes)
    "andhra-meals": ["Andhra Meals"],
    "cheese-quesadilla": ["Cheese Quesadilla"],
    "chilli-chicken": ["Chilli Chicken"],
    "dan-dan-noodles": ["Dan Dan Noodles"],
    "falafel-plate": ["Falafel Plate"],
    "kerala-chicken-roast": ["Kerala Chicken Roast"],
    "loaded-baked-potato": ["Loaded Baked Potato"],
    "pad-thai": ["Pad Thai"],
    "bbq-ribs": ["BBQ Ribs", "Barbecue Ribs"],
    "butter-chicken": ["Butter Chicken", "Chicken Makhani", "Murgh Makhani"],
    "caesar-salad": ["Caesar Salad"],
    "cheeseburger": ["Cheeseburger", "Bacon Cheeseburger"],
    "chole-bhature": ["Chole Bhature", "Chole Bhatura"],
    "dal-makhani": ["Dal Makhani"],
    "filter-coffee": ["Filter Coffee", "South Indian Filter Coffee"],
    "fries": ["Fries", "French Fries"],
    "gulab-jamun": ["Gulab Jamun"],
    "haleem": ["Haleem", "Hyderabadi Haleem"],
    "hyderabadi-chicken-biryani": ["Hyderabadi Chicken Biryani", "Hyderabadi Chicken Dum Biryani", "Chicken Dum Biryani"],
    "idli-sambar": ["Idli Sambar", "Sambar Idli"],
    "irani-chai": ["Irani Chai"],
    "latte": ["Latte", "Caffe Latte", "Café Latte"],
    "mango-lassi": ["Mango Lassi"],
    "margherita-pizza": ["Margherita", "Margherita Pizza"],
    "masala-dosa": ["Masala Dosa"],
    "naan-basket": ["Naan", "Plain Naan", "Naan Basket"],
    "north-indian-thali": ["North Indian Thali"],
    "pancakes": ["Pancakes", "Honey Walnut Pancakes"],
    "paneer-butter-masala": ["Paneer Butter Masala", "Paneer Makhani"],
    "pani-puri": ["Pani Puri", "Golgappa"],
    "pepperoni-pizza": ["Pepperoni Pizza", "Pepperoni"],
    "poke-bowl": ["Poke Bowl", "Salmon Poke Bowl"],
    "ramen": ["Ramen", "Shoyu Ramen"],
    "samosa": ["Samosa", "Veg Samosa"],
    "seafood-paella": ["Seafood Paella", "Paella Marinera"],  # R27: Boise's Basque Corner Kitchen
    "south-indian-thali": ["South Indian Thali"],
    "sushi": ["Sushi", "Sushi Platter"],
    "tacos": ["Tacos", "Street Tacos"],
    "tandoori-chicken": ["Tandoori Chicken"],
    "vada": ["Vada", "Medu Vada"],
    "veg-dum-biryani": ["Veg Dum Biryani", "Vegetable Dum Biryani"],
}
_PHOTO_BY_NAME = {n.lower(): slug for slug, names in PHOTO_DISHES.items() for n in names}
_COUNT = re.compile(r"\s*\(\d+(\s*(pc|pcs|pieces))?\)$", re.IGNORECASE)


def photo_url(slug: str | None, width: int = 800) -> str | None:
    return f"/food/{slug}-{width}.webp" if slug else None


def dish_slug(name: str) -> str | None:
    """The library photo that is exactly this dish, or None."""
    return _PHOTO_BY_NAME.get(_COUNT.sub("", name.strip()).lower())


def dish_photo(name: str) -> str | None:
    return photo_url(dish_slug(name))


def covers(kitchens: list[tuple[str, list[str]]], taken: set[str] | None = None) -> dict[str, str | None]:
    """One city's kitchens, in order, as (slug, dish names in menu order): each
    gets the photo of its first dish with an exact library match that no kitchen
    before it took. Returns slug -> photo slug (None: no cover)."""
    used = set(taken or ())
    out: dict[str, str | None] = {}
    for slug, dishes in kitchens:
        pick = next((p for p in map(dish_slug, dishes) if p and p not in used), None)
        if pick:
            used.add(pick)
        out[slug] = pick
    return out


def menu_dishes(menu: dict) -> list[str]:
    return [d[0] for items in menu.values() for d in items]
