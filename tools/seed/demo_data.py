"""Demo data (tools/seed/demo.py): a city that looks lived in, on top of the base seed.

For make dev and QA only, never CI or production. Every kitchen, person, address
and phone number is fictional; phones use the seed ranges (+91 90000 00xxx,
+1 208 555 0xxx), which sign in with the fixed OTP outside production.

Each city: 16 kitchens across at least six areas (zones; the ones the base seed
doesn't have are added here), full menus with option groups, opening hours
(a few are closed at most times of day: breakfast-only, evenings-only, a weekly
day off), offers paid for by the kitchen or by BhojanGo, demo customers 1-5 km
from the kitchens with saved default addresses, favourites, a test card, and an
order history with one order on its way. Neighbourhood regulars (REGULARS) order
from the kitchens near them for months; ratings come only from those delivered
orders (tools/seed/demo_history.py), so a couple of kitchens new this week have
fewer than five and show "New".
"""

# ── Option groups ─────────────────────────────────────────────────────────────


def g(name: str, options: list[tuple[str, float]], required: bool = False, max: int = 1) -> dict:  # noqa: A002
    return {"name": name, "required": required, "max": max, "options": [{"name": n, "price": p} for n, p in options]}


SPICE = g("Spice level", [("Mild", 0), ("Medium", 0), ("Hot", 0)], True)
SPICE_US = g("Spice level", [("Mild", 0), ("Medium", 0), ("Hot", 0)], True)
BIRYANI_SIZE = g("Size", [("Regular · serves 1", 0), ("Family · serves 3", 480)], True)
BIRYANI_ADDONS = g("Add-ons", [("Extra raita", 40), ("Mirchi ka salan", 30), ("Boiled egg", 25)], max=3)
HALF_FULL = g("Size", [("Half", 0), ("Full", 120)], True)
PIZZA_SIZE_IN = g("Size", [('Regular 10"', 0), ('Large 12"', 180)], True)
PIZZA_SIZE_US = g("Size", [('12"', 0), ('16"', 6)], True)
CRUST = g("Crust", [("Classic", 0), ("Thin", 0), ("Gluten-free", 3)], True)
BOWL_BASE = g("Base", [("Quinoa", 0), ("Brown rice", 0), ("Greens only", 0)], True)
PROTEIN_TH = g("Protein", [("Tofu", 0), ("Chicken", 0), ("Shrimp", 3)], True)
MOMO_STYLE = g("Style", [("Steamed", 0), ("Fried", 1), ("Jhol (in soup)", 2)], True)
INDO_STYLE = g("Style", [("Dry", 0), ("Gravy", 0)], True)

DAILY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def daily(opens: str, closes: str) -> list:
    return [(DAILY, opens, closes)]


# Kitchens that joined BhojanGo last week: a handful of orders, fewer than five
# ratings, so they show "New". Every other kitchen has months of order history.
# Ratings are never typed in: tools/seed/demo_history.py makes each kitchen's
# past orders and rates a share of them; demo.py recomputes rating and
# review_count from those rows as the ratings service does.
NEW_KITCHENS = frozenset({"mithaas-sweets-kukatpally", "green-bowl-co-hitec-city",
                          "hyde-park-pancake-house-north-end", "himalayan-curry-house-east-end"})


def kitchen(slug, name, area, street, zip_, lat, lng, cuisines, description, eta, fee, min_order,  # type: ignore[no-untyped-def]
            tags, hours, menu, radius_km=7.0):
    return {"slug": slug, "name": name, "area": area, "street": street, "zip": zip_, "lat": lat, "lng": lng,
            "cuisines": cuisines, "description": description, "new": slug in NEW_KITCHENS, "eta": eta,
            "delivery_fee": fee, "min_order": min_order, "tags": tags, "hours": hours, "menu": menu,
            "radius_km": radius_km}


# ── Hyderabad ─────────────────────────────────────────────────────────────────
# Menu entries: (name, price, veg, description, option groups), as in data.py.

HYD_KITCHENS = [
    kitchen("nawabi-dum-biryani-house-tolichowki", "Nawabi Dum Biryani House", "Tolichowki",
            "Road No. 7, Tolichowki", "500008", 17.3965, 78.4180, ["Biryani", "Hyderabadi", "Mughlai"],
            "Kachchi dum biryani, sealed with dough and cooked over coals, the way the old kitchens did.",
            (30, 40), "35.00", "199.00", ["bestseller"], daily("11:00", "23:30"), {
                "Biryani": [
                    ("Veg Dum Biryani", "249.00", True, "Basmati, vegetables and paneer, sealed and dum-cooked.", [BIRYANI_SIZE, SPICE]),
                    ("Mutton Dum Biryani", "399.00", False, "Raw marinated mutton and rice cooked together under dough.", [BIRYANI_SIZE, SPICE, BIRYANI_ADDONS]),
                    ("Chicken 65 Biryani", "319.00", False, "Dum biryani topped with fiery Chicken 65.", [SPICE]),
                    ("Egg Biryani", "239.00", False, "Two boiled eggs, masala and biryani rice.", []),
                    ("Prawns Biryani", "429.00", False, "Coastal prawns layered with saffron rice.", [SPICE]),
                ],
                "Starters": [
                    ("Chicken 65", "269.00", False, "Red, curry-leaf fried chicken.", [SPICE]),
                    ("Apollo Fish", "319.00", False, "Boneless fish tossed in chilli, garlic and curd.", []),
                    ("Paneer 65", "239.00", True, "Crisp paneer cubes, curry leaves.", []),
                ],
                "Sides": [
                    ("Mirchi Ka Salan", "79.00", True, "Green chillies in a peanut-sesame gravy.", []),
                    ("Dahi Chutney", "49.00", True, "Spiced yoghurt with mint.", []),
                ],
                "Desserts": [
                    ("Qubani Ka Meetha", "129.00", True, "Stewed apricots with fresh cream.", []),
                    ("Double Ka Meetha", "119.00", True, "Fried bread pudding with saffron milk and dry fruit.", []),
                ],
            }),
    kitchen("noor-mahal-haleem-house-old-city", "Noor Mahal Haleem House", "Old City",
            "Shah Ali Banda Rd", "500002", 17.3605, 78.4720, ["Mughlai", "Haleem", "Kebabs"],
            "Haleem pounded for eight hours, kebabs off the coals, and Old City nights.",
            (35, 45), "40.00", "199.00", ["late-night"], daily("12:00", "01:00"), {
                "Haleem": [
                    ("Hyderabadi Haleem", "289.00", False, "Mutton, wheat and lentils pounded for eight hours; fried onions and lime.", [
                        g("Size", [("Regular · 350 g", 0), ("Family · 1 kg", 420)], True),
                        g("Add-ons", [("Extra fried onions", 20), ("Boiled egg", 25), ("Sherwa", 40)], max=3)]),
                    ("Chicken Haleem", "249.00", False, "Lighter, with shredded chicken.", []),
                ],
                "Kebabs": [
                    ("Seekh Kebab (4)", "299.00", False, "Minced mutton with green chilli, off the coals.", [SPICE]),
                    ("Chicken Tikka", "289.00", False, "Boneless chicken in yoghurt and Kashmiri chilli.", [SPICE]),
                    ("Pathar Ka Gosht", "379.00", False, "Mutton seared on a hot granite stone.", []),
                    ("Shami Kebab (4)", "259.00", False, "Mutton and chana dal patties.", []),
                ],
                "Curries": [
                    ("Mutton Marag", "329.00", False, "Peppery mutton bone soup.", []),
                    ("Nihari", "349.00", False, "Shank slow-cooked overnight.", []),
                    ("Dal Gosht", "299.00", False, "Mutton with chana dal.", []),
                ],
                "Breads": [
                    ("Sheermal", "49.00", True, "Saffron-milk flatbread.", []),
                    ("Rumali Roti", "35.00", True, "Thin as a handkerchief.", []),
                ],
                "Desserts": [("Phirni", "99.00", True, "Ground rice and milk, set in a clay pot.", [])],
            }, radius_km=9.0),
    kitchen("gongura-ghar-kukatpally", "Gongura Ghar", "Kukatpally",
            "KPHB Colony, Road No. 1", "500072", 17.4870, 78.3990, ["Andhra", "Meals", "South Indian"],
            "Andhra meals with gongura everything, and tiffins in the morning.",
            (30, 40), "30.00", "149.00", ["spicy"], [(DAILY, "11:00", "15:30"), (DAILY, "19:00", "23:00")], {
                "Meals": [
                    ("Andhra Veg Meals", "199.00", True, "Rice, pappu, two curries, rasam, sambar, curd, pickle, appadam.", [
                        g("Add-ons", [("Extra ghee", 20), ("Gongura pickle", 30)], max=2)]),
                    ("Andhra Non-Veg Meals", "289.00", False, "The veg meal with chicken curry.", []),
                ],
                "Curries": [
                    ("Gongura Mutton", "349.00", False, "Mutton cooked with sour sorrel leaves.", [SPICE]),
                    ("Andhra Chicken Curry", "279.00", False, "Red chilli and coconut.", [SPICE]),
                    ("Natu Kodi Pulusu", "329.00", False, "Country chicken in tamarind gravy.", []),
                    ("Gutti Vankaya Kura", "199.00", True, "Stuffed baby brinjal.", []),
                    ("Tomato Pappu", "149.00", True, "Toor dal with tomato and garlic tempering.", []),
                ],
                "Tiffins": [
                    ("Medu Vada (2)", "69.00", True, "Crisp lentil doughnuts, chutney and sambar.", []),
                    ("Pesarattu", "99.00", True, "Green moong crêpe with ginger chutney.", [g("Add-ons", [("Upma filling", 30)])]),
                ],
                "Rice": [
                    ("Pulihora", "129.00", True, "Tamarind rice with peanuts.", []),
                    ("Curd Rice", "99.00", True, "With a mustard and curry-leaf tempering.", []),
                ],
            }),
    kitchen("udupi-tiffin-corner-madhapur", "Udupi Tiffin Corner", "Madhapur",
            "Kavuri Hills Rd", "500081", 17.4500, 78.3960, ["South Indian", "Tiffins", "Dosa"],
            "Breakfast only: idli, vada, dosa and strong filter coffee.",
            (20, 30), "25.00", "99.00", ["breakfast", "pure-veg"], daily("06:30", "11:30"), {
                "Idli & vada": [
                    ("Idli Sambar", "79.00", True, "Three idlis soaked in sambar, coconut chutney.", []),
                    ("Medu Vada (2)", "69.00", True, "With chutney and sambar.", []),
                    ("Sambar Vada", "79.00", True, "Vada soaked in hot sambar.", []),
                ],
                "Dosa": [
                    ("Masala Dosa", "109.00", True, "Potato masala, chutneys, sambar.", [
                        g("Add-ons", [("Extra potato masala", 25), ("Ghee roast", 20), ("Cheese", 40)], max=3)]),
                    ("Mysore Masala Dosa", "129.00", True, "Red chutney spread inside.", []),
                    ("Rava Onion Dosa", "119.00", True, "Lacy semolina dosa with onion.", []),
                    ("Set Dosa (3)", "99.00", True, "Soft and spongy, with vegetable sagu.", []),
                ],
                "Rice": [
                    ("Ven Pongal", "89.00", True, "Rice and moong dal with pepper and ghee.", []),
                    ("Bisi Bele Bath", "109.00", True, "Rice, lentils and vegetables, Karnataka style.", []),
                ],
                "Drinks": [
                    ("Filter Coffee", "45.00", True, "Chicory blend, frothed.", [g("Sugar", [("Regular", 0), ("Less sugar", 0), ("No sugar", 0)], True)]),
                    ("Badam Milk", "69.00", True, "Warm almond milk with saffron.", []),
                ],
            }),
    kitchen("sarson-da-dhaba-kondapur", "Sarson Da Dhaba", "Kondapur",
            "Botanical Garden Rd", "500084", 17.4660, 78.3620, ["North Indian", "Punjabi"],
            "Highway-dhaba Punjabi food: chole bhature, dal makhani and kulchas.",
            (30, 40), "35.00", "199.00", ["family"], daily("11:30", "23:30"), {
                "Mains": [
                    ("Chole Bhature", "189.00", True, "Two puffed bhature, Amritsari chole, onions and pickle.", [
                        g("Add-ons", [("Extra bhatura", 45), ("Sweet lassi (small)", 60)], max=2)]),
                    ("Dal Makhani", "229.00", True, "Black lentils simmered overnight with butter and cream.", [HALF_FULL]),
                    ("Sarson Da Saag with Makki Di Roti", "249.00", True, "Mustard greens with maize flatbread.", []),
                    ("Amritsari Kulcha", "169.00", True, "Stuffed, tandoor-baked, with chole.", []),
                    ("Rajma Chawal", "199.00", True, "Kidney beans and rice.", []),
                    ("Kadai Chicken", "319.00", False, "Chicken with peppers in a kadai masala.", [SPICE]),
                    ("Dhaba Mutton Curry", "379.00", False, "Bone-in mutton, rustic and spicy.", [SPICE]),
                ],
                "Breads": [
                    ("Butter Naan", "55.00", True, "From the tandoor.", []),
                    ("Lachha Paratha", "59.00", True, "Flaky layered paratha.", []),
                ],
                "Drinks": [
                    ("Sweet Lassi", "79.00", True, "Thick, with malai on top.", []),
                    ("Chaas", "49.00", True, "Spiced buttermilk.", []),
                ],
            }),
    kitchen("lahori-tandoor-house-begumpet", "Lahori Tandoor House", "Begumpet",
            "Prakash Nagar Main Rd", "500016", 17.4440, 78.4600, ["Tandoor", "North Indian", "Kebabs"],
            "Clay-oven chicken, kebabs and breads, fired to order.",
            (30, 45), "40.00", "249.00", ["bestseller"], daily("12:00", "23:30"), {
                "From the tandoor": [
                    ("Tandoori Chicken", "349.00", False, "24-hour yoghurt and Kashmiri chilli marinade.", [
                        g("Size", [("Half", 0), ("Full", 290)], True), SPICE]),
                    ("Chicken Tikka", "299.00", False, "Boneless thigh, charred.", [SPICE]),
                    ("Malai Tikka", "319.00", False, "Cream, cheese and cardamom.", []),
                    ("Tandoori Pomfret", "449.00", False, "Whole fish, ajwain and chilli.", []),
                    ("Paneer Tikka", "259.00", True, "Charred paneer, peppers, mint chutney.", []),
                ],
                "Curries": [
                    ("Butter Chicken", "339.00", False, "Tandoori chicken in tomato-butter gravy.", [HALF_FULL]),
                    ("Dal Makhani", "229.00", True, "Black lentils, butter and cream.", []),
                ],
                "Breads": [
                    ("Naan", "45.00", True, "Plain, from the tandoor.", []),
                    ("Garlic Naan", "65.00", True, "Garlic and coriander.", []),
                ],
                "Drinks": [("Mango Lassi", "99.00", True, "Alphonso mango and yoghurt.", [])],
            }),
    kitchen("cafe-zafraan-begumpet", "Café Zafraan", "Begumpet",
            "Sardar Patel Rd", "500003", 17.4410, 78.4560, ["Irani Cafe", "Bakery", "Snacks"],
            "An Irani café: chai, bun maska and the bakery counter, from early till late.",
            (20, 30), "25.00", "99.00", ["chai", "late-night"], daily("06:30", "00:30"), {
                "Chai & milk": [
                    ("Irani Chai", "35.00", True, "Slow-brewed with thickened milk.", []),
                    ("Pauna Chai", "30.00", True, "Three-quarter strength, three-quarter price.", []),
                    ("Badam Milk", "60.00", True, "Almond and saffron.", []),
                ],
                "Bakery": [
                    ("Osmania Biscuits (6)", "50.00", True, "Sweet-salty butter biscuits.", []),
                    ("Bun Maska", "45.00", True, "Soft bun, salted butter.", []),
                    ("Dil Khush", "40.00", True, "Coconut-filled sweet bun.", []),
                    ("Fruit Biscuits (200 g)", "90.00", True, "Tutti-frutti and cashew.", []),
                ],
                "Snacks": [
                    ("Samosa (2)", "40.00", True, "Potato and pea, mint chutney.", []),
                    ("Lukhmi (2)", "70.00", False, "Square pastries with mutton mince.", []),
                    ("Chicken Puff", "55.00", False, "Flaky puff, spiced chicken.", []),
                    ("Egg Bun", "50.00", False, "Masala omelette in a bun.", []),
                ],
            }),
    kitchen("chaat-chowk-jubilee-hills", "Chaat Chowk", "Jubilee Hills",
            "Road No. 36", "500033", 17.4320, 78.4080, ["Street Food", "Chaat"],
            "Evening chaat: pani puri, papdi chaat and kathi rolls.",
            (20, 30), "25.00", "99.00", ["snacks", "pure-veg"], daily("15:00", "23:00"), {
                "Chaat": [
                    ("Pani Puri (6)", "69.00", True, "Crisp puris, spiced potato, tangy mint water.", [
                        g("Water", [("Spicy pudina", 0), ("Sweet imli", 0), ("Both", 0)], True)]),
                    ("Dahi Puri (6)", "89.00", True, "Puris filled with yoghurt and chutneys.", []),
                    ("Sev Puri", "79.00", True, "Flat puris, potato, sev.", []),
                    ("Bhel Puri", "69.00", True, "Puffed rice, onions, chutneys.", []),
                    ("Papdi Chaat", "89.00", True, "Crisp papdi, yoghurt, tamarind.", []),
                    ("Aloo Tikki Chaat", "99.00", True, "Potato patties with chole.", []),
                ],
                "Rolls": [
                    ("Paneer Kathi Roll", "149.00", True, "Paneer tikka in a paratha.", [SPICE]),
                    ("Chicken Kathi Roll", "169.00", False, "Chicken tikka, onions, green chutney.", [SPICE]),
                ],
                "Sweet": [
                    ("Jalebi (200 g)", "99.00", True, "Hot and crisp.", []),
                    ("Rabri Falooda", "149.00", True, "Vermicelli, basil seeds, rabri.", []),
                ],
            }),
    kitchen("mithaas-sweets-kukatpally", "Mithaas Sweets", "Kukatpally",
            "JNTU Rd", "500085", 17.4900, 78.4050, ["Desserts", "Sweets"],
            "Mithai, kulfi and falooda. New on BhojanGo; closed on Tuesdays.",
            (25, 35), "30.00", "149.00", ["sweets"],
            [(["mon", "wed", "thu", "fri", "sat", "sun"], "10:00", "22:30")], {
                "Sweets": [
                    ("Gulab Jamun (2)", "69.00", True, "Warm, in cardamom syrup.", [g("Add-ons", [("Vanilla ice cream", 40)])]),
                    ("Rasmalai (2)", "99.00", True, "Chenna discs in saffron milk.", []),
                    ("Kaju Katli", "299.00", True, "Cashew fudge with silver leaf.", [g("Box", [("250 g", 0), ("500 g", 290)], True)]),
                    ("Motichoor Laddu (4)", "129.00", True, "Tiny boondi, ghee and cardamom.", []),
                    ("Kalakand (250 g)", "199.00", True, "Milk cake.", []),
                    ("Double Ka Meetha", "119.00", True, "Hyderabadi bread pudding.", []),
                ],
                "Kulfi & falooda": [
                    ("Malai Kulfi", "79.00", True, "On a stick.", []),
                    ("Kesar Pista Kulfi", "89.00", True, "Saffron and pistachio.", []),
                    ("Royal Falooda", "149.00", True, "Rose syrup, ice cream, nuts.", []),
                ],
                "Savouries": [
                    ("Kachori (2)", "59.00", True, "Moong dal kachori, tamarind chutney.", []),
                    ("Dhokla", "89.00", True, "Steamed gram flour cake.", []),
                ],
            }),
    kitchen("red-lantern-wok-gachibowli", "Red Lantern Wok", "Gachibowli",
            "Gachibowli Main Rd", "500032", 17.4400, 78.3550, ["Chinese", "Indo-Chinese"],
            "Indo-Chinese from a roaring wok: chilli chicken, Manchurian, Hakka noodles.",
            (25, 35), "30.00", "149.00", ["spicy"], daily("12:00", "23:30"), {
                "Starters": [
                    ("Chilli Chicken", "259.00", False, "Wok-tossed with peppers and green chilli.", [INDO_STYLE, SPICE]),
                    ("Gobi Manchurian", "189.00", True, "Crisp cauliflower, Manchurian sauce.", [INDO_STYLE]),
                    ("Dragon Chicken", "279.00", False, "Cashews, red chilli, honey.", []),
                    ("Crispy Corn Salt & Pepper", "179.00", True, "Fried sweetcorn, pepper, spring onion.", []),
                    ("Veg Spring Rolls (4)", "169.00", True, "Cabbage and carrot.", []),
                ],
                "Noodles & rice": [
                    ("Veg Hakka Noodles", "179.00", True, "Thin noodles, vegetables, soy.", [g("Add-ons", [("Egg", 25), ("Chicken", 60)], max=2)]),
                    ("Chicken Hakka Noodles", "219.00", False, "With shredded chicken.", []),
                    ("Schezwan Fried Rice", "199.00", True, "Fiery Schezwan sauce.", []),
                    ("Egg Fried Rice", "189.00", False, "Wok-fried with egg.", []),
                    ("American Chop Suey", "229.00", False, "Crispy noodles, sweet-sour sauce, fried egg.", []),
                ],
                "Soups": [
                    ("Hot and Sour Soup", "119.00", True, "Peppery and sour.", []),
                    ("Manchow Soup", "129.00", True, "With fried noodles.", []),
                ],
            }),
    kitchen("green-bowl-co-hitec-city", "Green Bowl Co.", "Hitech City",
            "Hitech City Main Rd", "500081", 17.4480, 78.3790, ["Healthy", "Bowls", "Salads"],
            "Bowls, salads and wraps with the calories on the menu. New on BhojanGo.",
            (20, 30), "30.00", "199.00", ["healthy"], daily("10:00", "22:00"), {
                "Bowls": [
                    ("Paneer Power Bowl", "289.00", True, "Grilled paneer, quinoa, chickpeas, greens, mint yoghurt.", [
                        BOWL_BASE, g("Add-ons", [("Avocado", 80), ("Extra paneer", 60), ("Boiled egg", 30)], max=3)]),
                    ("Grilled Chicken Bowl", "319.00", False, "Herb chicken, roasted vegetables, hummus.", [BOWL_BASE]),
                    ("Teriyaki Tofu Bowl", "299.00", True, "Tofu, edamame, pickled cucumber.", [BOWL_BASE]),
                    ("Millet Khichdi Bowl", "229.00", True, "Foxtail millet and moong dal.", []),
                ],
                "Salads": [
                    ("Caesar Salad", "259.00", False, "Romaine, parmesan, croutons, anchovy dressing.", [g("Add-ons", [("Grilled chicken", 80)])]),
                    ("Greek Salad", "249.00", True, "Feta, olives, cucumber, tomato.", []),
                    ("Sprouts Chaat Salad", "179.00", True, "Moong sprouts, pomegranate, lime.", []),
                ],
                "Wraps": [
                    ("Chicken Tikka Wrap", "229.00", False, "Whole-wheat wrap, mint mayo.", []),
                    ("Falafel Wrap", "209.00", True, "Tahini and pickles.", []),
                ],
                "Drinks": [
                    ("Cold-Pressed ABC Juice", "149.00", True, "Apple, beetroot, carrot.", []),
                    ("Tender Coconut Water", "79.00", True, "Fresh.", []),
                ],
            }),
    kitchen("forno-fiamma-jubilee-hills", "Forno Fiamma", "Jubilee Hills",
            "Road No. 45", "500033", 17.4260, 78.4150, ["Pizza", "Italian"],
            "Neapolitan-style pizza from a wood-fired oven, and fresh pasta.",
            (25, 40), "35.00", "249.00", ["pizza"], daily("12:00", "23:30"), {
                "Pizza": [
                    ("Margherita Pizza", "399.00", True, "San Marzano tomato, fior di latte, basil.", [PIZZA_SIZE_IN]),
                    ("Pepperoni Pizza", "549.00", False, "Chicken pepperoni, mozzarella.", [PIZZA_SIZE_IN]),
                    ("Tandoori Paneer Pizza", "479.00", True, "Paneer tikka, onions, peppers.", [PIZZA_SIZE_IN]),
                    ("Four Cheese Pizza", "529.00", True, "Mozzarella, gorgonzola, parmesan, provolone.", [PIZZA_SIZE_IN]),
                    ("Pesto Chicken Pizza", "549.00", False, "Basil pesto, roast chicken.", [PIZZA_SIZE_IN]),
                    ("Funghi Pizza", "449.00", True, "Mushrooms, garlic, thyme.", [PIZZA_SIZE_IN]),
                ],
                "Pasta": [
                    ("Penne Arrabbiata", "349.00", True, "Spicy tomato and garlic.", []),
                    ("Spaghetti Aglio e Olio", "329.00", True, "Garlic, chilli, olive oil.", [g("Add-ons", [("Prawns", 150), ("Chicken", 90)])]),
                    ("Chicken Alfredo Pasta", "399.00", False, "Cream and parmesan.", []),
                ],
                "Sides & dessert": [
                    ("Garlic Bread", "149.00", True, "Wood-fired, garlic butter.", [g("Add-ons", [("Cheese", 50)])]),
                    ("Tiramisu", "249.00", True, "Mascarpone and espresso.", []),
                ],
            }),
    kitchen("smash-street-burgers-madhapur", "Smash Street Burgers", "Madhapur",
            "Image Gardens Rd", "500081", 17.4430, 78.3990, ["Burgers", "American"],
            "Smashed patties and loaded fries, evenings and late nights only.",
            (25, 35), "30.00", "199.00", ["late-night"], daily("18:00", "03:00"), {
                "Burgers": [
                    ("Cheeseburger", "249.00", False, "Two smashed chicken patties, cheddar, pickles, house sauce.", [
                        g("Patties", [("Double", 0), ("Triple", 90)], True),
                        g("Add-ons", [("Jalapeños", 30), ("Fried egg", 40), ("Extra cheese", 40)], max=3)]),
                    ("Crispy Paneer Burger", "219.00", True, "Fried paneer, slaw, chipotle mayo.", []),
                    ("Peri-Peri Chicken Burger", "259.00", False, "Grilled thigh, peri-peri sauce.", [SPICE]),
                    ("Aloo Tikki Burger", "149.00", True, "Spiced potato patty.", []),
                    ("Mushroom Swiss Burger", "239.00", True, "Sautéed mushrooms, Swiss cheese.", []),
                ],
                "Sides": [
                    ("French Fries", "119.00", True, "Skin-on, crisp.", [g("Seasoning", [("Salted", 0), ("Peri-peri", 20)], True)]),
                    ("Loaded Fries", "179.00", False, "Cheese sauce, chicken, jalapeños.", []),
                    ("Chicken Wings (6)", "249.00", False, "Buffalo or barbecue.", [g("Sauce", [("Buffalo", 0), ("Barbecue", 0)], True)]),
                ],
                "Shakes": [
                    ("Oreo Shake", "169.00", True, "Thick, with cookie crumbs.", []),
                    ("Cold Coffee", "139.00", True, "With a scoop of vanilla.", []),
                ],
            }),
    kitchen("royal-paneer-kitchen-kondapur", "Royal Paneer Kitchen", "Kondapur",
            "Raghavendra Colony", "500084", 17.4690, 78.3560, ["North Indian", "Pure Veg"],
            "A pure-veg kitchen: paneer five ways, dal tadka and thalis.",
            (25, 35), "30.00", "149.00", ["pure-veg"], daily("11:00", "23:00"), {
                "Paneer": [
                    ("Paneer Butter Masala", "259.00", True, "Paneer in a velvety tomato-cashew gravy.", [HALF_FULL]),
                    ("Kadai Paneer", "249.00", True, "Peppers, onions, kadai masala.", [SPICE]),
                    ("Palak Paneer", "239.00", True, "Spinach purée.", []),
                    ("Paneer Tikka Masala", "269.00", True, "Charred paneer in masala gravy.", [SPICE]),
                    ("Shahi Paneer", "259.00", True, "Mild, with cream and cashews.", []),
                ],
                "Dal & veg": [
                    ("Dal Tadka", "179.00", True, "Yellow dal, garlic and cumin tadka.", []),
                    ("Mix Veg", "199.00", True, "Seasonal vegetables.", []),
                    ("Jeera Aloo", "159.00", True, "Potatoes with cumin.", []),
                ],
                "Rice & breads": [
                    ("Jeera Rice", "149.00", True, "Basmati with cumin.", []),
                    ("Butter Naan", "55.00", True, "From the tandoor.", []),
                    ("Tandoori Roti", "30.00", True, "Whole wheat.", []),
                ],
                "Thali": [("North Indian Thali", "299.00", True, "Paneer, dal, two sabzis, rice, two rotis, raita and a sweet.", [])],
            }),
    kitchen("shubh-thali-house-begumpet", "Shubh Thali House", "Begumpet",
            "Begumpet Main Rd", "500016", 17.4480, 78.4650, ["Thali", "Gujarati", "Rajasthani"],
            "Thalis for lunch and dinner, refilled the way they would be at home.",
            (30, 40), "35.00", "199.00", ["pure-veg", "lunch"], [(DAILY, "11:30", "15:30"), (DAILY, "19:00", "22:30")], {
                "Thalis": [
                    ("North Indian Thali", "329.00", True, "Paneer, dal, two sabzis, rice, rotis, raita and a sweet.", [
                        g("Add-ons", [("Extra roti", 20), ("Extra sweet", 40)], max=2)]),
                    ("Gujarati Thali", "349.00", True, "Kadhi, dal, three shaak, farsan, rotli, rice.", []),
                    ("Rajasthani Thali", "369.00", True, "Dal baati, gatte, ker sangri, churma.", []),
                    ("Mini Thali", "219.00", True, "Dal, one sabzi, rice, two rotis.", []),
                ],
                "À la carte": [
                    ("Dal Baati Churma", "289.00", True, "Baked wheat balls, dal and sweet churma.", []),
                    ("Gatte Ki Sabzi", "219.00", True, "Gram flour dumplings in yoghurt gravy.", []),
                    ("Undhiyu", "249.00", True, "Winter vegetables and methi muthia.", []),
                    ("Khandvi", "149.00", True, "Rolled gram flour, mustard tempering.", []),
                ],
                "Sweets": [
                    ("Shrikhand", "119.00", True, "Saffron hung curd.", []),
                    ("Moong Dal Halwa", "149.00", True, "Slow-roasted in ghee.", []),
                ],
            }),
    kitchen("old-delhi-rasoi-gachibowli", "Old Delhi Rasoi", "Gachibowli",
            "Nanakramguda Rd", "500032", 17.4280, 78.3500, ["North Indian", "Mughlai"],
            "Old Delhi favourites: butter chicken, nihari, rogan josh and kulchas.",
            (30, 40), "35.00", "199.00", ["bestseller"], daily("11:00", "23:30"), {
                "Curries": [
                    ("Butter Chicken", "349.00", False, "Tandoori chicken in a buttery tomato-fenugreek gravy.", [
                        HALF_FULL, g("Add-ons", [("Extra butter", 30)])]),
                    ("Chicken Changezi", "339.00", False, "Rich, creamy, with fried onions.", []),
                    ("Mutton Rogan Josh", "399.00", False, "Kashmiri chilli and fennel.", [SPICE]),
                    ("Dal Makhani", "239.00", True, "Black lentils, butter and cream.", [HALF_FULL]),
                    ("Kadhai Mushroom", "229.00", True, "Mushrooms and peppers.", []),
                ],
                "Rice": [
                    ("Chicken Pulao", "299.00", False, "Fragrant, mildly spiced.", []),
                    ("Steamed Basmati", "129.00", True, "Plain rice.", []),
                ],
                "Breads": [
                    ("Butter Naan", "55.00", True, "From the tandoor.", []),
                    ("Garlic Naan", "65.00", True, "Garlic and coriander.", []),
                    ("Kulcha", "55.00", True, "Soft leavened bread.", []),
                ],
                "Desserts": [
                    ("Gulab Jamun (2)", "79.00", True, "Warm, in syrup.", []),
                    ("Shahi Tukda", "129.00", True, "Fried bread, rabri and pistachio.", []),
                ],
            }),
]

# ── Boise ─────────────────────────────────────────────────────────────────────

BOI_KITCHENS = [
    kitchen("ridgeline-pizza-kitchen-west-boise", "Ridgeline Pizza Kitchen", "West Boise",
            "1450 N Milwaukee St", "83704", 43.6110, -116.2780, ["Pizza", "Italian"],
            "New York-style pies by the slice-load, with a West Boise crowd.",
            (25, 40), "2.99", "15.00", ["pizza"], daily("11:00", "22:00"), {
                "Pizza": [
                    ("Pepperoni Pizza", "17.50", False, "Cup-and-char pepperoni, whole-milk mozzarella.", [PIZZA_SIZE_US, CRUST]),
                    ("Sausage & Peppers Pizza", "18.50", False, "Fennel sausage, roasted peppers, onions.", [PIZZA_SIZE_US, CRUST]),
                    ("BBQ Chicken Pizza", "18.50", False, "Smoked chicken, red onion, cilantro.", [PIZZA_SIZE_US, CRUST]),
                    ("Veggie Garden Pizza", "16.50", True, "Mushrooms, peppers, olives, spinach.", [PIZZA_SIZE_US, CRUST]),
                    ("White Pie", "17.00", True, "Ricotta, garlic, mozzarella, basil.", [PIZZA_SIZE_US, CRUST]),
                ],
                "Starters": [
                    ("Garlic Knots (6)", "6.50", True, "With marinara.", []),
                    ("Wings (8)", "13.00", False, "Crispy wings.", [g("Sauce", [("Buffalo", 0), ("Honey BBQ", 0), ("Garlic Parmesan", 0)], True)]),
                ],
                "Salads & dessert": [
                    ("House Salad", "8.00", True, "Greens, tomato, cucumber, Italian dressing.", []),
                    ("Cannoli (2)", "7.00", True, "Ricotta and chocolate chips.", []),
                ],
            }, radius_km=8.0),
    kitchen("sawtooth-smash-burgers-downtown", "Sawtooth Smash Burgers", "Downtown",
            "812 W Bannock St", "83702", 43.6175, -116.2005, ["Burgers", "American"],
            "Smashed burgers, crinkle fries and huckleberry shakes.",
            (20, 30), "2.49", "12.00", ["late-night"], daily("11:00", "23:00"), {
                "Burgers": [
                    ("Bacon Cheeseburger", "14.50", False, "Two smashed patties, bacon, American cheese, pickles, Sawtooth sauce.", [
                        g("Patties", [("Double", 0), ("Triple", 3.5)], True),
                        g("Add-ons", [("Jalapeños", 1), ("Fried egg", 1.5), ("Avocado", 2)], max=3)]),
                    ("Cheeseburger", "12.50", False, "Two smashed patties, American cheese.", [g("Patties", [("Double", 0), ("Triple", 3.5)], True)]),
                    ("Mushroom Swiss Burger", "13.50", False, "Sautéed mushrooms, Swiss cheese.", []),
                    ("Crispy Chicken Sandwich", "12.00", False, "Buttermilk-fried, slaw, pickles.", []),
                    ("Black Bean Burger", "12.00", True, "House black bean patty, chipotle mayo.", []),
                ],
                "Sides": [
                    ("French Fries", "4.50", True, "Crinkle-cut.", [g("Size", [("Regular", 0), ("Large", 1.5)], True)]),
                    ("Onion Rings", "5.50", True, "Beer-battered.", []),
                    ("Tater Tots", "5.00", True, "With fry sauce.", []),
                ],
                "Shakes": [
                    ("Huckleberry Shake", "7.50", True, "Wild huckleberry, vanilla ice cream.", []),
                    ("Chocolate Shake", "6.50", True, "Thick.", []),
                ],
            }),
    kitchen("taqueria-rio-azul-boise-bench", "Taqueria Río Azul", "Boise Bench",
            "3110 W Overland Rd", "83705", 43.5890, -116.2380, ["Mexican", "Tacos"],
            "Street tacos on fresh corn tortillas, birria on weekends and every day.",
            (20, 35), "2.99", "12.00", ["bestseller"], daily("10:30", "22:00"), {
                "Tacos": [
                    ("Street Tacos", "11.50", False, "Three corn tortillas, onion, cilantro, salsa verde.", [
                        g("Filling", [("Carne asada", 0), ("Al pastor", 0), ("Pollo", 0), ("Carnitas", 0)], True),
                        g("Add-ons", [("Guacamole", 1.5), ("Queso fresco", 1)], max=2)]),
                    ("Birria Tacos", "14.00", False, "Three, with consommé for dipping.", []),
                    ("Baja Fish Tacos", "13.50", False, "Beer-battered cod, cabbage, crema.", []),
                    ("Veggie Tacos", "10.50", True, "Roasted peppers, black beans, cotija.", []),
                ],
                "Burritos & bowls": [
                    ("Carne Asada Burrito", "13.50", False, "Steak, rice, beans, pico.", [g("Style", [("Regular", 0), ("Wet (enchilada sauce)", 1.5)], True)]),
                    ("Chicken Burrito Bowl", "12.50", False, "Rice, beans, pico, crema.", []),
                    ("Bean & Cheese Burrito", "9.50", True, "Refried beans, cheddar.", []),
                ],
                "Sides & drinks": [
                    ("Chips & Guacamole", "6.50", True, "Made to order.", []),
                    ("Elote", "5.00", True, "Street corn, mayo, cotija, chilli.", []),
                    ("Horchata", "3.50", True, "Rice and cinnamon.", []),
                ],
            }, radius_km=8.0),
    kitchen("kawa-sushi-east-end", "Kawa Sushi", "East End",
            "1515 E Warm Springs Ave", "83712", 43.6110, -116.1760, ["Sushi", "Japanese"],
            "Rolls, nigiri and platters by the river.",
            (30, 45), "3.49", "20.00", ["date-night"], daily("11:30", "21:30"), {
                "Rolls": [
                    ("California Roll", "9.00", False, "Crab, avocado, cucumber.", []),
                    ("Spicy Tuna Roll", "10.50", False, "Tuna, chilli mayo, scallion.", [SPICE_US]),
                    ("Salmon Avocado Roll", "10.50", False, "Fresh salmon and avocado.", []),
                    ("Dragon Roll", "15.50", False, "Shrimp tempura, eel, avocado.", []),
                    ("Vegetable Roll", "8.00", True, "Cucumber, avocado, carrot, pickled radish.", []),
                ],
                "Platters & nigiri": [
                    ("Sushi Platter", "32.00", False, "Twelve pieces of nigiri and a California roll, chef's choice.", []),
                    ("Sashimi Plate", "26.00", False, "Fifteen slices: salmon, tuna, yellowtail.", []),
                    ("Salmon Nigiri (2)", "7.00", False, "", []),
                    ("Tuna Nigiri (2)", "7.50", False, "", []),
                ],
                "Sides": [
                    ("Miso Soup", "3.50", True, "Tofu, wakame, scallion.", []),
                    ("Edamame", "5.00", True, "Sea salt.", []),
                    ("Seaweed Salad", "6.00", True, "Sesame dressing.", []),
                ],
            }),
    kitchen("morning-ridge-bakery-north-end", "Morning Ridge Bakery", "North End",
            "1607 N 15th St", "83702", 43.6335, -116.2090, ["Coffee", "Bakery", "Breakfast"],
            "Coffee and pastries baked before sunrise; closes after lunch.",
            (15, 25), "1.99", "8.00", ["breakfast", "coffee"], daily("06:30", "14:00"), {
                "Coffee": [
                    ("Latte", "5.25", True, "Double shot, steamed milk.", [
                        g("Size", [("12 oz", 0), ("16 oz", 0.75)], True),
                        g("Milk", [("Whole", 0), ("Oat", 0.75), ("Almond", 0.75)], True),
                        g("Add-ons", [("Vanilla", 0.75), ("Extra shot", 1.25)], max=2)]),
                    ("Cappuccino", "4.75", True, "Equal parts espresso, milk and foam.", []),
                    ("Drip Coffee", "3.00", True, "Today's single origin.", []),
                    ("Chai Latte", "5.00", True, "House chai concentrate.", []),
                    ("Cold Brew", "4.75", True, "Steeped 18 hours.", []),
                ],
                "Bakery": [
                    ("Butter Croissant", "4.25", True, "Laminated over three days.", []),
                    ("Almond Croissant", "5.25", True, "Frangipane, toasted almonds.", []),
                    ("Huckleberry Scone", "4.50", True, "Wild Idaho huckleberries.", []),
                    ("Cinnamon Roll", "5.00", True, "Cream cheese icing.", []),
                ],
                "Breakfast": [
                    ("Avocado Toast", "10.50", True, "Sourdough, chilli flakes, lemon.", [g("Add-ons", [("Poached egg", 2)])]),
                    ("Breakfast Sandwich", "9.50", False, "Egg, cheddar, bacon, brioche.", []),
                ],
            }),
    kitchen("hyde-park-pancake-house-north-end", "Hyde Park Pancake House", "North End",
            "1609 N 13th St", "83702", 43.6380, -116.2020, ["Breakfast", "American"],
            "Pancakes, waffles and big breakfasts until mid-afternoon. New on BhojanGo.",
            (20, 30), "2.49", "12.00", ["breakfast"], daily("07:00", "14:30"), {
                "Pancakes & waffles": [
                    ("Honey Walnut Pancakes", "11.50", True, "Three buttermilk pancakes, honey, toasted walnuts.", [
                        g("Stack", [("Short stack (3)", 0), ("Tall stack (5)", 3)], True),
                        g("Add-ons", [("Bacon", 3), ("Huckleberry compote", 2), ("Whipped cream", 1)], max=3)]),
                    ("Buttermilk Pancakes", "10.00", True, "With maple syrup and butter.", []),
                    ("Huckleberry Pancakes", "12.50", True, "Wild huckleberries cooked in.", []),
                    ("Belgian Waffle", "10.50", True, "Crisp, with strawberries.", []),
                ],
                "Eggs & more": [
                    ("Two-Egg Breakfast", "11.00", False, "Eggs, hash browns, bacon or sausage, toast.", [
                        g("Eggs", [("Scrambled", 0), ("Over easy", 0), ("Sunny side up", 0)], True)]),
                    ("Denver Omelette", "12.50", False, "Ham, peppers, onions, cheddar.", []),
                    ("Biscuits & Gravy", "10.00", False, "Sausage gravy.", []),
                    ("Chicken Fried Steak", "14.50", False, "With country gravy and eggs.", []),
                ],
                "Sides & drinks": [
                    ("Hash Browns", "4.00", True, "Idaho russets.", []),
                    ("Fresh Orange Juice", "4.50", True, "Squeezed to order.", []),
                ],
            }),
    kitchen("smokestack-bbq-southeast-boise", "Smokestack BBQ", "Southeast Boise",
            "2950 S Federal Way", "83716", 43.5780, -116.1900, ["BBQ", "American"],
            "Hickory-smoked ribs, brisket and pulled pork, sold until it runs out.",
            (30, 45), "3.99", "18.00", ["smoked"], daily("11:00", "21:00"), {
                "Smoked meats": [
                    ("BBQ Ribs", "24.00", False, "Half rack of St. Louis ribs, hickory-smoked, house sauce.", [
                        g("Size", [("Half rack", 0), ("Full rack", 12)], True),
                        g("Sauce", [("House", 0), ("Spicy", 0), ("Carolina gold", 0)], True)]),
                    ("Brisket Plate", "21.00", False, "Half pound of sliced brisket, two sides.", [
                        g("Sides", [("Mac & cheese", 0), ("Coleslaw", 0), ("Baked beans", 0), ("Cornbread", 0)], True, max=2)]),
                    ("Pulled Pork Sandwich", "13.50", False, "With slaw on a brioche bun.", []),
                    ("Smoked Half Chicken", "17.00", False, "Dry-rubbed.", []),
                    ("Burnt Ends", "16.00", False, "Brisket point, caramelised.", []),
                ],
                "Sides": [
                    ("Mac & Cheese", "5.00", True, "Three cheeses.", []),
                    ("Coleslaw", "3.50", True, "Vinegar slaw.", []),
                    ("Baked Beans", "4.00", False, "With burnt ends.", []),
                    ("Cornbread", "3.50", True, "Honey butter.", []),
                ],
                "Dessert": [("Banana Pudding", "6.00", True, "Vanilla wafers.", [])],
            }, radius_km=8.0),
    kitchen("ramen-kaze-downtown", "Ramen Kaze", "Downtown",
            "405 S 8th St", "83702", 43.6125, -116.2060, ["Ramen", "Japanese"],
            "Shoyu, tonkotsu and miso bowls; closed on Mondays.",
            (25, 35), "2.99", "15.00", ["noodles"],
            [(["tue", "wed", "thu", "fri", "sat", "sun"], "11:30", "22:00")], {
                "Ramen": [
                    ("Shoyu Ramen", "15.50", False, "Clear soy-chicken broth, chashu pork, narutomaki, scallions, menma.", [
                        g("Noodles", [("Regular", 0), ("Extra noodles", 2.5)], True),
                        g("Add-ons", [("Ajitama egg", 2), ("Extra chashu", 4), ("Corn butter", 1.5)], max=3)]),
                    ("Tonkotsu Ramen", "16.50", False, "Rich pork-bone broth, chashu, black garlic oil.", []),
                    ("Spicy Miso Ramen", "16.50", False, "Miso broth, ground pork, chilli.", [SPICE_US]),
                    ("Veggie Miso Ramen", "14.50", True, "Mushroom-kombu broth, tofu, corn.", []),
                ],
                "Small plates": [
                    ("Pork Gyoza (6)", "8.00", False, "Pan-fried.", []),
                    ("Karaage", "9.50", False, "Japanese fried chicken, lemon, kewpie.", []),
                    ("Edamame", "5.00", True, "Sea salt.", []),
                    ("Takoyaki (6)", "8.50", False, "Octopus, bonito flakes.", []),
                ],
                "Rice & drinks": [
                    ("Chashu Rice Bowl", "10.00", False, "Torched chashu over rice.", []),
                    ("Ramune", "3.50", True, "Japanese soda.", []),
                ],
            }),
    kitchen("greenhouse-salads-boise-state", "Greenhouse Salads", "Boise State",
            "1010 W University Dr", "83706", 43.5990, -116.2010, ["Salads", "Healthy"],
            "Big salads, grain bowls and soups near campus.",
            (15, 25), "2.49", "12.00", ["healthy"], daily("10:30", "21:00"), {
                "Salads": [
                    ("Caesar Salad", "11.00", False, "Romaine, parmesan, croutons, anchovy dressing.", [
                        g("Protein", [("None", 0), ("Grilled chicken", 4), ("Salmon", 6)], True)]),
                    ("Cobb Salad", "14.00", False, "Chicken, bacon, egg, avocado, blue cheese.", []),
                    ("Harvest Kale Salad", "12.50", True, "Kale, squash, apple, pecans, cider vinaigrette.", []),
                    ("Mediterranean Quinoa Salad", "12.50", True, "Quinoa, feta, olives, cucumber.", []),
                    ("Asian Sesame Chicken Salad", "13.50", False, "Cabbage, wontons, sesame-ginger.", []),
                ],
                "Bowls & wraps": [
                    ("Chicken Pesto Wrap", "11.50", False, "Grilled chicken, pesto, tomato.", []),
                    ("Falafel Bowl", "12.00", True, "Hummus, tabbouleh, tahini.", []),
                ],
                "Soups & drinks": [
                    ("Tomato Basil Soup", "5.50", True, "With a grilled-cheese crouton.", []),
                    ("Chicken Tortilla Soup", "6.00", False, "Avocado, tortilla strips.", []),
                    ("Green Smoothie", "7.00", True, "Spinach, mango, banana.", []),
                ],
            }),
    kitchen("saffron-lane-indian-kitchen-west-boise", "Saffron Lane Indian Kitchen", "West Boise",
            "7700 W Fairview Ave", "83704", 43.6050, -116.2650, ["Indian", "Tandoor"],
            "Tandoor grills, curries and biryani in West Boise.",
            (30, 45), "3.49", "18.00", ["indian"], daily("11:00", "21:30"), {
                "Tandoor": [
                    ("Tandoori Chicken", "16.50", False, "Yoghurt and Kashmiri chilli marinade.", [g("Size", [("Half", 0), ("Full", 9)], True), SPICE_US]),
                    ("Chicken Tikka", "15.00", False, "Boneless, charred.", [SPICE_US]),
                    ("Paneer Tikka", "14.00", True, "With mint chutney.", []),
                ],
                "Curries": [
                    ("Chicken Tikka Masala", "17.00", False, "Tomato-cream sauce.", [SPICE_US]),
                    ("Lamb Rogan Josh", "19.00", False, "Kashmiri chilli and fennel.", [SPICE_US]),
                    ("Chana Masala", "13.00", True, "Chickpeas, onion-tomato masala.", []),
                    ("Dal Makhani", "13.50", True, "Black lentils, butter and cream.", []),
                ],
                "Rice & bread": [
                    ("Chicken Biryani", "17.00", False, "Basmati, chicken, raita.", []),
                    ("Naan", "3.00", True, "Plain, from the tandoor.", []),
                    ("Garlic Naan", "4.00", True, "Garlic and cilantro.", []),
                ],
                "Drinks": [("Mango Lassi", "4.50", True, "Mango and yoghurt.", [])],
            }, radius_km=8.0),
    kitchen("himalayan-curry-house-east-end", "Himalayan Curry House", "East End",
            "2200 E Parkcenter Blvd", "83706", 43.6170, -116.1650, ["Nepalese", "Indian", "Momos"],
            "Momos, Nepali curries and thukpa. New on BhojanGo.",
            (30, 40), "3.49", "15.00", ["new"], daily("11:00", "21:30"), {
                "Momos": [
                    ("Chicken Momos (8)", "12.00", False, "Hand-pleated, tomato-sesame achar.", [MOMO_STYLE]),
                    ("Veg Momos (8)", "11.00", True, "Cabbage, paneer, ginger.", [MOMO_STYLE]),
                ],
                "Curries": [
                    ("Paneer Butter Masala", "15.00", True, "Paneer in a tomato-butter gravy.", []),
                    ("Nepali Chicken Curry", "16.00", False, "Bone-in, timur pepper.", [SPICE_US]),
                    ("Goat Curry", "19.00", False, "Slow-cooked.", [SPICE_US]),
                    ("Aloo Tama", "13.00", True, "Potato, bamboo shoot and black-eyed peas.", []),
                ],
                "Noodles": [
                    ("Chicken Chow Mein", "13.00", False, "Nepali-style stir-fried noodles.", []),
                    ("Thukpa", "13.50", False, "Noodle soup with chicken and vegetables.", []),
                ],
                "Rice, bread & chai": [
                    ("Basmati Rice", "3.00", True, "Steamed.", []),
                    ("Butter Naan", "3.50", True, "From the tandoor.", []),
                    ("Masala Chai", "3.50", True, "Spiced milk tea.", []),
                ],
            }),
    kitchen("bench-fried-chicken-boise-bench", "Bench Fried Chicken", "Boise Bench",
            "2525 S Vista Ave", "83705", 43.5870, -116.2210, ["Fried Chicken", "American", "Comfort"],
            "Buttermilk fried chicken, classic or Nashville hot, with all the sides.",
            (20, 30), "2.49", "12.00", ["comfort"], daily("11:00", "22:00"), {
                "Chicken": [
                    ("Fried Chicken (3 pc)", "12.50", False, "Buttermilk-brined, pressure-fried.", [g("Spice", [("Classic", 0), ("Nashville hot", 0.5)], True)]),
                    ("Chicken Tenders (4)", "11.00", False, "With a dip.", [g("Dip", [("Ranch", 0), ("Honey mustard", 0), ("Fry sauce", 0)], True)]),
                    ("Hot Chicken Sandwich", "12.50", False, "Nashville hot, slaw, pickles.", []),
                    ("Wings (10)", "15.00", False, "Dry-rubbed or sauced.", []),
                ],
                "Sides": [
                    ("French Fries", "4.00", True, "Idaho russets, skin-on.", []),
                    ("Mashed Potatoes & Gravy", "4.50", True, "Idaho potatoes.", []),
                    ("Biscuit with Honey Butter", "3.00", True, "Flaky.", []),
                    ("Mac & Cheese", "5.00", True, "Baked.", []),
                    ("Coleslaw", "3.50", True, "Creamy.", []),
                ],
                "Drinks": [("Sweet Tea", "2.75", True, "Southern-style.", [])],
            }),
    kitchen("lucky-lotus-noodle-bar-southeast-boise", "Lucky Lotus Noodle Bar", "Southeast Boise",
            "1820 E Boise Ave", "83706", 43.5720, -116.1980, ["Chinese", "Noodles"],
            "Wok-fried noodles and Chinese-American classics.",
            (25, 40), "2.99", "15.00", [], daily("11:00", "21:30"), {
                "Noodles": [
                    ("Beef Chow Fun", "14.50", False, "Wide rice noodles, wok hei.", []),
                    ("Dan Dan Noodles", "13.00", False, "Sichuan pepper, pork, chilli oil.", [SPICE_US]),
                    ("Vegetable Lo Mein", "11.50", True, "Egg noodles, vegetables.", []),
                ],
                "Mains": [
                    ("Orange Chicken", "13.50", False, "Crispy chicken, orange glaze.", []),
                    ("Kung Pao Chicken", "13.50", False, "Peanuts, dried chillies.", [SPICE_US]),
                    ("Mapo Tofu", "12.50", True, "Silken tofu, fermented bean sauce.", [SPICE_US]),
                    ("Broccoli Beef", "14.00", False, "Flank steak, oyster sauce.", []),
                ],
                "Rice & starters": [
                    ("Pork Fried Rice", "11.00", False, "With egg and scallion.", []),
                    ("Pork Potstickers (6)", "8.00", False, "Pan-fried.", []),
                    ("Crab Rangoon (6)", "7.50", False, "Cream cheese and crab.", []),
                    ("Hot and Sour Soup", "5.00", True, "Tofu and mushrooms.", []),
                ],
            }, radius_km=8.0),
    kitchen("olive-and-zaatar-boise-state", "Olive & Za'atar", "Boise State",
            "1200 S Broadway Ave", "83706", 43.5960, -116.1950, ["Mediterranean", "Middle Eastern"],
            "Shawarma, falafel and mezze, with za'atar flatbread from the oven.",
            (20, 30), "2.49", "12.00", ["healthy"], daily("11:00", "21:00"), {
                "Plates": [
                    ("Chicken Shawarma Plate", "14.50", False, "Rice, salad, hummus, garlic toum.", []),
                    ("Falafel Plate", "12.50", True, "Six falafel, hummus, salad, pita.", []),
                    ("Lamb Kofta Plate", "16.50", False, "Grilled kofta, rice, tahini.", []),
                ],
                "Wraps": [
                    ("Chicken Shawarma Wrap", "11.00", False, "Pickles, fries, toum.", [g("Sauce", [("Garlic toum", 0), ("Tahini", 0), ("Spicy harissa", 0)], True)]),
                    ("Falafel Wrap", "10.00", True, "Tahini, tomato, pickles.", []),
                ],
                "Mezze": [
                    ("Hummus & Pita", "7.00", True, "Olive oil, paprika.", []),
                    ("Baba Ghanoush", "7.50", True, "Smoked aubergine.", []),
                    ("Tabbouleh", "6.50", True, "Parsley, bulgur, lemon.", []),
                    ("Fattoush", "7.50", True, "Crisp pita, sumac.", []),
                ],
                "Dessert": [("Baklava (2)", "5.00", True, "Pistachio and honey.", [])],
            }),
    kitchen("basil-leaf-thai-downtown", "Basil Leaf Thai", "Downtown",
            "1110 W Jefferson St", "83702", 43.6195, -116.2110, ["Thai"],
            "Thai curries, noodles and street-food starters, as hot as you like.",
            (25, 40), "2.99", "15.00", ["spicy"], daily("11:00", "21:30"), {
                "Curries": [
                    ("Green Curry", "15.00", False, "Coconut milk, Thai eggplant, basil.", [PROTEIN_TH, SPICE_US]),
                    ("Red Curry", "15.00", False, "Bamboo shoots, bell pepper, basil.", [PROTEIN_TH, SPICE_US]),
                    ("Panang Curry", "15.50", False, "Rich, with kaffir lime.", [PROTEIN_TH]),
                ],
                "Noodles & rice": [
                    ("Pad Thai", "14.50", False, "Rice noodles, tamarind, peanuts.", [PROTEIN_TH]),
                    ("Pad See Ew", "14.50", False, "Wide noodles, Chinese broccoli.", [PROTEIN_TH]),
                    ("Drunken Noodles", "14.50", False, "Holy basil, chilli.", [PROTEIN_TH, SPICE_US]),
                    ("Pineapple Fried Rice", "14.00", False, "Cashews, curry powder.", []),
                ],
                "Starters": [
                    ("Fresh Spring Rolls (2)", "7.00", True, "Rice paper, herbs, peanut sauce.", []),
                    ("Chicken Satay (4)", "9.00", False, "With peanut sauce.", []),
                    ("Tom Yum Soup", "6.50", False, "Shrimp, lemongrass, lime.", []),
                ],
                "Dessert & drinks": [
                    ("Mango Sticky Rice", "7.50", True, "Coconut cream.", []),
                    ("Thai Iced Tea", "4.50", True, "Sweet and creamy.", []),
                ],
            }),
    kitchen("riverside-burrito-co-east-end", "Riverside Burrito Co.", "East End",
            "3005 E Bergeson St", "83706", 43.6060, -116.1720, ["Mexican", "Burritos", "Bowls"],
            "Mission-style burritos and bowls, built your way.",
            (20, 30), "2.49", "12.00", [], daily("10:00", "22:00"), {
                "Burritos": [
                    ("California Burrito", "12.50", False, "Carne asada, fries, cheese, pico.", []),
                    ("Chile Verde Burrito", "12.00", False, "Pork in green chile.", []),
                    ("Veggie Burrito", "10.50", True, "Fajita vegetables, black beans, rice.", []),
                    ("Breakfast Burrito", "10.00", False, "Egg, potato, chorizo, cheese.", []),
                ],
                "Bowls": [
                    ("Carnitas Bowl", "12.50", False, "Slow-cooked pork.", [
                        g("Base", [("Cilantro rice", 0), ("Greens", 0)], True),
                        g("Add-ons", [("Guacamole", 2), ("Queso", 1.5), ("Extra meat", 3)], max=3)]),
                    ("Sofritas Bowl", "11.50", True, "Spiced tofu.", [g("Base", [("Cilantro rice", 0), ("Greens", 0)], True)]),
                ],
                "Quesadillas": [
                    ("Chicken Quesadilla", "11.00", False, "Jack cheese, pico.", []),
                    ("Cheese Quesadilla", "8.50", True, "Jack and cheddar.", []),
                ],
                "Sides & drinks": [
                    ("Chips & Salsa", "3.50", True, "Roasted tomato salsa.", []),
                    ("Queso Dip", "5.00", True, "With chips.", []),
                    ("Agua Fresca", "3.50", True, "Ask for today's flavour.", []),
                ],
            }),
]

# ── Cities ────────────────────────────────────────────────────────────────────
# Zones the base seed doesn't have (south, west, north, east boxes, like data.py's).
# Customers: (key, name, street, area, postal, lat, lng, delivery notes); the first
# is "the" demo customer (favourites, saved card, the order on its way).
DEMO = {
    "hyd": {
        "city_code": "IN-TG-HYD",
        "zones": [
            ("Kukatpally", (17.475, 78.385, 17.500, 78.420), "99", "live", "#3F8F96"),
            ("Begumpet", (17.435, 78.445, 17.455, 78.475), "149", "live", "#A9772F"),
        ],
        "kitchens": HYD_KITCHENS,
        "fssai_base": 13626010000200,
        "partner": ("partner.demo.hyd@example.com", "Hyderabad Demo Partner", "910"),
        "rider": ("rider.demo.hyd@example.com", "Venkat Rao", "250"),
        "customers": [
            ("demo1.hyd", "Ananya Desai", "Flat 504, Cyber Residency, Ayyappa Society Rd", "Hitech City", "500081",
             17.4560, 78.3870, "Gate 2; call when you're at the lift"),
            ("demo2.hyd", "Rahul Verma", "8-2-293, Road No. 10", "Jubilee Hills", "500033", 17.4150, 78.4250, None),
            ("demo3.hyd", "Sana Fatima", "12-1-45, Paramount Colony", "Tolichowki", "500008", 17.3880, 78.4060, None),
        ],
        "phones": {"demo1.hyd": "301", "demo2.hyd": "302", "demo3.hyd": "303"},
        # the demo customer's second address (not the default)
        "work": ("Tower 3, Mindspace IT Park", "Hitech City", "500081", 17.4430, 78.3770),
        "card": ("visa", "4242"),
        "favourites": {"restaurants": ["sarson-da-dhaba-kondapur", "forno-fiamma-jubilee-hills", "udupi-tiffin-corner-madhapur"],
                       "items": [("old-delhi-rasoi-gachibowli", "Butter Chicken"), ("green-bowl-co-hitec-city", "Paneer Power Bowl")]},
        "tip": "30", "method": "upi",
    },
    "boi": {
        "city_code": "US-ID-BOI",
        "zones": [
            ("East End", (43.600, -116.185, 43.625, -116.150), "15", "live", "#3F8F96"),
            ("Southeast Boise", (43.555, -116.215, 43.590, -116.160), "15", "live", "#A9772F"),
        ],
        "kitchens": BOI_KITCHENS,
        "fssai_base": None,
        "partner": ("partner.demo.boi@example.com", "Boise Demo Partner", "910"),
        "rider": ("rider.demo.boi@example.com", "Casey Morgan", "250"),
        "customers": [
            ("demo1.boi", "Hannah Mitchell", "1201 N 3rd St, Apt 4B", "Downtown", "83702", 43.6230, -116.1900,
             "Blue door at the back; ring 4B"),
            ("demo2.boi", "Marcus Reed", "2860 W Kootenai St", "Boise Bench", "83705", 43.5960, -116.2300, None),
            ("demo3.boi", "Isabella Cruz", "2410 N 19th St", "North End", "83702", 43.6420, -116.2150, None),
        ],
        "phones": {"demo1.boi": "301", "demo2.boi": "302", "demo3.boi": "303"},
        "work": ("850 W Front St, Suite 300", "Downtown", "83702", 43.6140, -116.2040),
        "card": ("visa", "4242"),
        "favourites": {"restaurants": ["sawtooth-smash-burgers-downtown", "kawa-sushi-east-end", "morning-ridge-bakery-north-end"],
                       "items": [("ramen-kaze-downtown", "Shoyu Ramen"), ("taqueria-rio-azul-boise-bench", "Street Tacos")]},
        "tip": "3", "method": "card",
    },
}

# ── Offers ────────────────────────────────────────────────────────────────────
# Rules like the base seed's: (template, key, name, scope_level, scope_id, params).
# A restaurant's scope_id is its slug. Kitchen-funded ones have a weekly cap.
PROMOTIONS = {
    "hyd": [
        ("percent_off", "demo_nawabi_20", "20% off, up to ₹100", "restaurant", "nawabi-dum-biryani-house-tolichowki",
         {"percent": 20, "max_discount": 100, "min_subtotal": 299, "funded_by": "restaurant", "weekly_cap": 5000}),
        ("flat_off", "demo_smash_75", "₹75 off orders over ₹399", "restaurant", "smash-street-burgers-madhapur",
         {"amount": 75, "min_subtotal": 399, "funded_by": "restaurant", "weekly_cap": 3000}),
        ("free_delivery", "demo_mithaas_free", "Free delivery over ₹199", "restaurant", "mithaas-sweets-kukatpally",
         {"min_subtotal": 199, "funded_by": "restaurant", "weekly_cap": 2000}),
        ("free_delivery", "demo_greenbowl_free", "Free delivery", "restaurant", "green-bowl-co-hitec-city",
         {"funded_by": "platform", "budget_cap": 20000}),
        ("percent_off", "demo_noormahal_15", "15% off, up to ₹75", "restaurant", "noor-mahal-haleem-house-old-city",
         {"percent": 15, "max_discount": 75, "funded_by": "platform", "budget_cap": 25000}),
        ("flat_off", "demo_feast100", "₹100 off orders over ₹499 with FEAST100", "city", "IN-TG-HYD",
         {"amount": 100, "min_subtotal": 499, "code": "FEAST100", "funded_by": "platform", "budget_cap": 50000}),
    ],
    "boi": [
        ("free_delivery", "demo_rioazul_free", "Free delivery over $20", "restaurant", "taqueria-rio-azul-boise-bench",
         {"min_subtotal": 20, "funded_by": "restaurant", "weekly_cap": 150}),
        ("flat_off", "demo_sawtooth_3", "$3 off orders over $25", "restaurant", "sawtooth-smash-burgers-downtown",
         {"amount": 3, "min_subtotal": 25, "funded_by": "restaurant", "weekly_cap": 120}),
        ("percent_off", "demo_kawa_15", "15% off, up to $8", "restaurant", "kawa-sushi-east-end",
         {"percent": 15, "max_discount": 8, "min_subtotal": 30, "funded_by": "restaurant", "weekly_cap": 200}),
        ("free_delivery", "demo_greenhouse_free", "Free delivery", "restaurant", "greenhouse-salads-boise-state",
         {"funded_by": "platform", "budget_cap": 1500}),
        ("percent_off", "demo_himalayan_20", "20% off, up to $6", "restaurant", "himalayan-curry-house-east-end",
         {"percent": 20, "max_discount": 6, "funded_by": "platform", "budget_cap": 1000}),
        ("flat_off", "demo_boise5", "$5 off orders over $30 with BOISE5", "city", "US-ID-BOI",
         {"amount": 5, "min_subtotal": 30, "code": "BOISE5", "funded_by": "platform", "budget_cap": 2500}),
    ],
}

# ── Order history ─────────────────────────────────────────────────────────────
# (customer key, kitchen slug, days ago, local time, [(dish, quantity, {group: option})], review)
# Priced by the real quote engine at that time; delivered by the city's demo rider.
# review: (rating, comment) or None. ACTIVE: one order on its way per city, placed now.
ORDERS = {
    "hyd": [
        ("demo1.hyd", "sarson-da-dhaba-kondapur", 3, "13:15",
         [("Chole Bhature", 2, {"Add-ons": "Extra bhatura"}), ("Sweet Lassi", 2, {})], (5, "Bhature were huge and still puffed up when they arrived.")),
        ("demo1.hyd", "forno-fiamma-jubilee-hills", 6, "20:10",
         [("Margherita Pizza", 1, {"Size": 'Large 12"'}), ("Garlic Bread", 1, {"Add-ons": "Cheese"})], (4, "Great crust; a little late on a rainy night.")),
        ("demo1.hyd", "green-bowl-co-hitec-city", 10, "13:00",
         [("Paneer Power Bowl", 1, {"Base": "Quinoa", "Add-ons": "Avocado"}), ("Caesar Salad", 1, {})], None),
        ("demo1.hyd", "old-delhi-rasoi-gachibowli", 16, "20:40",
         [("Butter Chicken", 1, {"Size": "Full"}), ("Garlic Naan", 3, {}), ("Dal Makhani", 1, {"Size": "Half"})], (5, "The butter chicken is the real thing.")),
        ("demo1.hyd", "udupi-tiffin-corner-madhapur", 23, "08:30",
         [("Masala Dosa", 2, {"Add-ons": "Ghee roast"}), ("Filter Coffee", 2, {"Sugar": "Less sugar"})], None),
        ("demo1.hyd", "red-lantern-wok-gachibowli", 35, "21:00",
         [("Chilli Chicken", 1, {"Style": "Dry", "Spice level": "Hot"}), ("Veg Hakka Noodles", 1, {})], None),
        ("demo2.hyd", "forno-fiamma-jubilee-hills", 4, "19:30", [("Pepperoni Pizza", 1, {}), ("Tiramisu", 1, {})], None),
        ("demo2.hyd", "chaat-chowk-jubilee-hills", 9, "18:00", [("Pani Puri (6)", 2, {"Water": "Both"}), ("Papdi Chaat", 1, {})], None),
        ("demo2.hyd", "nawabi-dum-biryani-house-tolichowki", 14, "13:30", [("Mutton Dum Biryani", 1, {"Size": "Family · serves 3"})], None),
        ("demo3.hyd", "nawabi-dum-biryani-house-tolichowki", 5, "20:00", [("Veg Dum Biryani", 2, {}), ("Chicken 65", 1, {})], None),
        ("demo3.hyd", "noor-mahal-haleem-house-old-city", 12, "21:30", [("Hyderabadi Haleem", 2, {"Add-ons": "Extra fried onions"}), ("Sheermal", 2, {})], None),
    ],
    "boi": [
        ("demo1.boi", "sawtooth-smash-burgers-downtown", 4, "19:00",
         [("Bacon Cheeseburger", 2, {"Add-ons": "Jalapeños"}), ("French Fries", 1, {"Size": "Large"}), ("Huckleberry Shake", 1, {})],
         (5, "Best smash burger downtown, and the fries were still crisp.")),
        ("demo1.boi", "kawa-sushi-east-end", 8, "19:30",
         [("Sushi Platter", 1, {}), ("Spicy Tuna Roll", 1, {"Spice level": "Medium"}), ("Miso Soup", 2, {})], (4, "Fresh fish, beautiful platter.")),
        ("demo1.boi", "morning-ridge-bakery-north-end", 12, "09:00",
         [("Latte", 2, {"Milk": "Oat"}), ("Almond Croissant", 2, {})], None),
        ("demo1.boi", "basil-leaf-thai-downtown", 17, "18:30",
         [("Green Curry", 1, {"Protein": "Chicken", "Spice level": "Medium"}), ("Pad Thai", 1, {"Protein": "Shrimp"})], (5, "Thai hot means Thai hot.")),
        ("demo1.boi", "smokestack-bbq-southeast-boise", 25, "18:00",
         [("BBQ Ribs", 1, {"Size": "Full rack"}), ("Mac & Cheese", 1, {}), ("Cornbread", 2, {})], None),
        ("demo1.boi", "ramen-kaze-downtown", 31, "12:30",
         [("Shoyu Ramen", 2, {"Add-ons": "Ajitama egg"}), ("Pork Gyoza (6)", 1, {})], None),
        ("demo2.boi", "taqueria-rio-azul-boise-bench", 3, "12:30", [("Street Tacos", 2, {"Filling": "Al pastor"}), ("Horchata", 2, {})], None),
        ("demo2.boi", "bench-fried-chicken-boise-bench", 9, "18:45", [("Fried Chicken (3 pc)", 2, {"Spice": "Nashville hot"}), ("French Fries", 2, {})], None),
        ("demo2.boi", "saffron-lane-indian-kitchen-west-boise", 15, "19:15", [("Chicken Tikka Masala", 1, {}), ("Garlic Naan", 2, {}), ("Mango Lassi", 1, {})], None),
        ("demo3.boi", "morning-ridge-bakery-north-end", 2, "08:20", [("Latte", 2, {}), ("Huckleberry Scone", 2, {})], None),
        ("demo3.boi", "hyde-park-pancake-house-north-end", 6, "09:30", [("Honey Walnut Pancakes", 2, {"Add-ons": "Bacon"}), ("Fresh Orange Juice", 2, {})], None),
    ],
}
ACTIVE = {
    "hyd": ("demo1.hyd", "royal-paneer-kitchen-kondapur", [("Paneer Butter Masala", 1, {"Size": "Full"}), ("Butter Naan", 3, {}), ("Jeera Rice", 1, {})]),
    "boi": ("demo1.boi", "riverside-burrito-co-east-end", [("California Burrito", 2, {}), ("Chips & Salsa", 1, {})]),
}

# ── Neighbourhood regulars (the order history) ────────────────────────────────
# Demo customers behind each kitchen's past orders and ratings. Each lives 1-3 km
# from one demo kitchen, inside a live zone (tools/seed/demo_history.py places
# them), orders from the kitchens within reach of home, and rates some of those
# orders. Phones: the seed ranges, 401 and up. Not listed with the demo logins.
REGULARS = {
    "hyd": ["Priya Reddy", "Karthik Rao", "Meera Iyer", "Arjun Nair", "Divya Sharma", "Imran Khan", "Lakshmi Menon",
            "Rohit Gupta", "Sneha Kulkarni", "Vikram Singh", "Nikhil Joshi", "Pooja Agarwal", "Farhan Ali", "Kavya Raju",
            "Siddharth Bose", "Aisha Siddiqui"],
    "boi": ["Emily Carter", "Jacob Bennett", "Olivia Hayes", "Ethan Brooks", "Sophia Ramirez", "Noah Fischer", "Ava Thompson",
            "Liam O'Connor", "Mia Sullivan", "Lucas Nguyen", "Grace Patterson", "Owen Walsh", "Chloe Jensen", "Daniel Kim",
            "Zoe Martinez", "Ryan Cooper"],
}
# Street lines for the regulars' homes: (format, street names).
STREETS = {
    "hyd": ("Flat {n}, {street}", ["Sai Nagar Colony", "Vasavi Colony Rd", "Lane 4, Srinivasa Nagar", "Road No. 3",
                                   "Annapurna Enclave", "Lakshmi Residency", "Street No. 6, Prashanti Nagar", "Green Park Avenue"]),
    "boi": ("{n} {street}", ["N Elm St", "W Maple Ave", "E Cedar Ln", "S Juniper Way", "N Aspen Dr", "W Willow St",
                             "E Birch Ct", "N Sycamore Pl"]),
}
# Each zone's minimum order is at most this (a basket always clears it).
BASKET_FLOOR = {"hyd": 160, "boi": 22}

# What customers write with a rating (about half of the ratings have one).
RATING_COMMENTS = {
    5: ["Perfect, as always.", "The {dish} was outstanding.", "Hot, fresh and on time.", "Our go-to for {dish}.",
        "Packed really well; nothing spilled.", "Generous portions and great flavour.", "Better than eating in."],
    4: ["Really good {dish}; a little late.", "Tasty, would order again.", "Good food, slightly less spicy than I like.",
        "Solid {dish}, generous portion.", "Arrived warm; nicely packed."],
    3: ["The {dish} was okay, nothing special.", "Decent, but it took a while.", "Fine, a bit cold by the time it came.",
        "Average this time."],
    2: ["The {dish} was too salty.", "Late and lukewarm.", "Smaller portion than usual."],
    1: ["Missing an item and the {dish} was cold.", "Not up to the usual standard."],
}
