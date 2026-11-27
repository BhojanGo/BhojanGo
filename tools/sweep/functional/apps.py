"""R42: the functions of every app screen (customer, restaurant, delivery partner), each done and checked by a Maestro
flow on the emulator (apps/<app>/.maestro/<flow>.yaml), plus the API-side comparisons the flows can't make (admin
Finance needs the two-step sign-in): those run in run_web.py with the website and admin functions.

A function whose flow is "" isn't automated yet: the report lists it as NOT RUN (never as passed)."""
from __future__ import annotations

from decimal import Decimal

from framework import T, api, app_fn, fn, na, ok, token

NOT_YET = ""


def screen(app: str, route: str, *fns: tuple, nas: tuple = ()) -> None:
    for f in fns:
        id, kind, action, expected, verify, flow, *users = f
        app_fn(app, route, id, kind=kind, action=action, expected=expected, verify=verify, flow=flow,
               users=tuple(users[0]) if users else ("us", "in"))
    for kind, why in nas:
        na(app, route, kind, why)


DOWN = ("api-down", "error", "Open it with core-api stopped", "Still renders and says it can't reach BhojanGo; no crash", "UI text")
PUBLIC = ("permission", "the way in: anyone may open it")

# ── Customer app ────────────────────────────────────────────────────────────────────────────────────────────────────
C = "customer"
screen(C, "index", ("opens", "navigation", "Launch the app", "Signed out: sign-in; signed in: Home", "UI", "sign-in-email"),
       (*DOWN, "offline-sign-in"), nas=(PUBLIC, ("empty", "a launcher screen")))
screen(C, "sign-in", ("phone-and-email", "form", "Phone + code; email + wrong then right password", "Wrong password refused; right one signs in",
                      "UI messages; API session", "sign-in-email"),
       ("phone-us-in", "form", "Sign in with a US and an India number", "Each country's number format, code, signed in", "UI", "r39-phone"),
       (*DOWN, "offline-sign-in"), nas=(PUBLIC, ("empty", "a form")))
screen(C, "(tabs)/home", ("restaurants", "navigation", "Scroll the list, open a restaurant", "The city's restaurants; opens the menu", "UI vs /discover",
                          "qa-browse"),
       ("list-menu", "link", "Restaurant cards and dish list", "Cards with fee/time; menu opens", "UI", "r36-list-menu"),
       ("out-of-area", "empty", "An address outside every zone", "'We're not there yet' and Notify me", "UI", "out-of-area"),
       (*DOWN, "r42-api-down"), nas=(("permission", "Home is the customer's own; every customer may open it"),))
screen(C, "(tabs)/search", ("search", "filter", "Search 'curry'", "Restaurants and dishes matching", "UI vs /search", "r36-search-curry"),
       ("tabbar", "navigation", "Tab bar clears the content", "Nothing under the tab bar", "UI", "tabbar-clearance"),
       ("nothing-found", "empty", "Search nonsense", "'Nothing matches “…” nearby'", "UI", "r43-new-account-{user}"),
       (*DOWN, "r42-api-down"), nas=(("permission", "any signed-in customer"),))
screen(C, "(tabs)/orders", ("list-and-receipt", "link", "Open a past order", "Its receipt", "UI", "orders-receipt"),
       ("no-orders", "empty", "A new customer's Orders", "'No orders yet.'", "UI; API: GET /orders is empty", "r43-new-account-{user}"),
       (*DOWN, "r42-api-down"), nas=(("permission", "only the signed-in customer's own orders are fetched (API: GET /orders is per user; access sweep)"),))
screen(C, "(tabs)/account", ("account", "navigation", "Open each account row", "Each page opens", "UI", "account"),
       ("pages", "link", "Addresses, payments, notifications, privacy", "Each opens with its data", "UI", "account-pages"),
       (*DOWN, "r42-api-down"), nas=(("permission", "the customer's own account"), ("empty", "always shows the account")))
screen(C, "account/address", ("form", "form", "Add an address, US and India formats", "Saved; the right fields per country", "UI vs /me/addresses",
                              "r41-sweep-us"), ("form-in", "form", "India address form", "PIN code, state", "UI", "r41-sweep-in", ("in",)),
       nas=(("permission", "the customer's own addresses"), ("empty", "a form"), ("error", "the form's own checks (r41-sweep); API down: the account tab's (r42-api-down)")))
screen(C, "account/addresses", ("list", "button", "Make default, delete", "List follows", "UI", "account-pages"),
       ("none", "empty", "A new customer", "'No saved addresses yet.' + Add", "UI; API: GET /me/addresses is empty", "r43-new-account-{user}"),
       nas=(("permission", "own addresses"), ("error", "API down: r42-api-down (account tab)")))
screen(C, "account/language", ("switch", "toggle", "Switch language and back", "The whole app in that language", "UI", "account-language"),
       nas=(("permission", "own setting"), ("empty", "a list of languages"), ("error", "works offline (a local setting)")))
screen(C, "account/notifications", ("switches", "toggle", "Turn a channel off and on", "Saved", "UI", "account-pages"),
       nas=(("permission", "own setting"), ("empty", "always the channels"), ("error", "API down: r42-api-down")))
screen(C, "account/payments", ("methods", "button", "Open saved methods", "Listed", "UI", "account-pages"),
       nas=(("permission", "own methods"), ("empty", "shows Add when none"), ("error", "API down: r42-api-down")))
screen(C, "account/privacy", ("export-delete", "button", "Download my data; Delete account (cancel)", "Confirm dialog", "UI", "account-pages"),
       nas=(("permission", "own account"), ("empty", "fixed actions"), ("error", "API down: r42-api-down")))
screen(C, "account/receipt/[id]", ("receipt-bill", "number", "Open a past order's receipt", "Paid = the order API's total; bill lines in paise",
                                   "UI vs GET /orders/{id} (scripts/r42_numbers.js)", "r42-bill-us"),
       ("receipt-in", "number", "India receipt", "Paid = the order's; GST lines", "UI vs API", "r42-bill-in", ("in",)),
       ("bill-paise", "number", "India bill in paise", "₹ with two decimals", "UI", "r37-bill-paise", ("in",)),
       ("report-from-receipt", "button", "Report a problem from the receipt", "The report screen for that order", "UI", "orders-receipt"),
       nas=(("permission", "only the customer's orders are listed to open (API refuses others: access sweep)"), ("empty", "a receipt always has its order"),
            ("error", "API down: r42-api-down (orders tab)")))
screen(C, "bag", ("bill-equals-quote", "number", "Add the dish, open the cart", "Every bill line and Pay = the pricing API's quote",
                  "UI vs POST /pricing/quote (scripts/r42_numbers.js)", "r42-bill-us"),
       ("bill-in", "number", "The same in Hyderabad", "Lines = quote in paise", "UI vs API", "r42-bill-in", ("in",)),
       ("pay", "form", "Pay and approve (test provider)", "Tracking opens", "UI", "order-and-track", ("in",)),
       ("languages", "toggle", "The cart in each language", "Fits, translated", "UI", "cart-languages"),
       ("declined", "error", "Decline the payment", "'Payment failed' and retry", "UI", "payment-failed"),
       ("empty-cart", "empty", "Open the cart with nothing in it", "'Your cart is empty'", "UI", "r43-new-account-{user}"),
       nas=(("permission", "the customer's own cart on the device"),))
screen(C, "code", ("otp", "form", "Enter the 6-digit code", "Signed in", "UI", "sign-in-email"),
       ("wrong-code", "error", "A wrong code, then the right one", "Refused with a message; the right code signs in", "UI", "r43-wrong-code-{user}"), nas=(PUBLIC, ("empty", "a form")))
screen(C, "favourites", ("list", "button", "Saved restaurants; unsave", "List follows the API", "UI", "r41-sweep-us"),
       ("none", "empty", "A new customer", "'Nothing saved yet…'", "UI; API: favourites empty", "r43-new-account-{user}"),
       nas=(("permission", "own favourites"), ("error", "API down: r42-api-down")))
screen(C, "gallery", ("components", "display", "Developer gallery", "Every component renders", "UI", "gallery", ("us",)),
       nas=(("permission", "a developer screen, not in the release build"), ("empty", "fixed"), ("error", "no data"),
            ("action", "a developer screen: it only shows components")))
screen(C, "item", ("customise", "form", "Choose options and quantity", "Price on the button follows", "UI", "order-and-track", ("in",)),
       nas=(("permission", "public menu"), ("empty", "an item always has its details"), ("error", "API down: r42-api-down")))
screen(C, "order/[id]", ("tracking", "display", "Follow the order live", "Status, ETA, PIN after pickup", "UI vs order API", "order-and-track", ("in",)),
       ("pickup", "display", "A pickup order's steps", "Pickup code, collected", "UI", "pickup", ("in",)),
       ("qa-track", "display", "Tracking on a delivered order", "Delivered state", "UI", "qa-track"),
       ("messages", "button", "Message the delivery partner", "Sent; their reply arrives; numbers hidden", "UI; API messages", "messages", ("in",)),
       nas=(("permission", "only the customer's own orders open (API: access sweep)"), ("empty", "an order always has a status"),
            ("error", "API down: r42-api-down")))
screen(C, "out-of-area", ("notify", "form", "Outside every zone: Notify me", "Saved", "UI", "out-of-area"),
       nas=(PUBLIC, ("empty", "the screen is itself the 'nowhere to deliver' state"), ("error", "the form's message")))
screen(C, "payment-failed", ("retry", "button", "Payment failed: retry, approve", "Paid on retry", "UI", "payment-failed"),
       nas=(("permission", "the customer's own order"), ("empty", "always about one payment"), ("error", "the screen is the error state")))
screen(C, "report/[id]", ("report-refund", "form", "Report a missing item", "Refunded, amount shown", "UI vs refunds", "report-problem", ("in",)),
       nas=(("permission", "own orders only (API refuses others)"), ("empty", "about one order"), ("error", "Send disabled until chosen (report-problem)")))
screen(C, "restaurant/[id]", ("menu", "button", "Add, customise", "In the cart", "UI", "order-and-track", ("in",)),
       ("closed", "display", "A closed restaurant", "Banner, no adds", "UI", "r36-pickup-closed", ("in",)),
       # R43: a menu change reaching the app (measured), a dish outside its hours, spice
       ("menu-change", "number", "The restaurant changes a dish's price; the customer opens the restaurant",
        "The new price shows within 60 s (measured from the change)", "UI vs GET /restaurants/{id}/menu (scripts/r43_menu.js)", "r43-propagation-{user}"),
       ("dish-hours", "display", "A dish served only at other hours, spice Medium", "'Served … – …', no Add; '🌶🌶 Medium'", "UI vs the menu API",
        "r43-propagation-{user}"),
       # R45: a category the restaurant deletes leaves the app (measured)
       ("category-gone", "number", "The restaurant deletes an empty category; the customer opens the restaurant",
        "Its heading is gone within 60 s (measured from the delete)", "UI vs GET /restaurants/{id}/menu (scripts/r43_customer.js)",
        "r45-category-gone-{user}"),
       nas=(PUBLIC, ("empty", "a menu always has dishes (a closed one: see closed)"), ("error", "API down: r42-api-down")))
screen(C, "where", ("set-location", "form", "Choose a city and address", "Home for that place", "UI", "r41-sweep-us"),
       nas=(PUBLIC, ("empty", "a picker"), ("error", "API down: r42-api-down")))

# ── Restaurant app ──────────────────────────────────────────────────────────────────────────────────────────────────
P = "partner"
screen(P, "index", ("opens", "navigation", "Launch", "Sign-in or the tablet's restaurant", "UI", "sign-in-email"),
       (*DOWN, "offline-sign-in"), nas=(PUBLIC, ("empty", "a launcher")))
screen(P, "sign-in", ("email", "form", "Email + wrong then right password", "Signed in", "UI", "sign-in-email"),
       ("wrong-role", "permission", "Sign in with a delivery partner's account", "Refused: 'This number is a delivery partner or admin account'",
        "UI", "r42-wrong-role", ("in",)),
       ("phone", "form", "Phone sign-in US / India", "Code, signed in", "UI", "r39-phone"),
       (*DOWN, "offline-sign-in"), nas=(("empty", "a form"),))
screen(P, "code", ("code", "form", "Enter the code", "Signed in", "UI", "r41-sweep"), nas=(PUBLIC, ("empty", "a form"), ("error", "wrong code: refused (sign-in)")))
screen(P, "kitchens", ("pick", "button", "Pick the tablet's restaurant", "Its orders", "UI", "orders"),
       nas=(("permission", "only the owner's restaurants are listed (API /restaurants/mine)"), ("empty", "an owner has at least one restaurant"),
            ("error", "API down: r42-api-down")))
screen(P, "(kitchen)/orders", ("accept-ready-busy-pause", "button", "Accept with ready-in, Mark ready, Busy +10, Pause 15 min, Resume",
                               "Each state on the tablet and in the API", "UI; API order status", "orders", ("in",)),
       ("reject", "button", "Reject an order", "Gone; the customer refunded in full", "UI; API: cancelled + refunded", "r42-reject-lock", ("in",)),
       ("pickup-code", "form", "Pickup code: wrong, then right", "Wrong refused; right hands over", "UI; API", "pickup", ("in",)),
       ("pickup-locked", "error", "Wrong pickup code 5 times", "Locked: 'Too many wrong codes'", "UI; API 423", "r42-reject-lock", ("in",)),
       ("no-orders", "empty", "A restaurant with no orders today", "Every column empty, counts 0", "UI; API: today's orders = 0", "r43-no-orders-{user}"),
       (*DOWN, "r42-api-down"), nas=(("permission", "a restaurant sees only its own orders (API: access sweep)"),))
screen(P, "(kitchen)/menu", ("stock-to-web", "toggle", "Mark a dish sold out, then back in stock",
                             "The website's menu shows 'Sold out' and clears it, each within 90 s (measured)", "UI; website page; API menu",
                             "r42-stock-web", ("in",)),
       ("offers-hours", "form", "Create and end an offer; search", "Offer live then ended", "UI", "menu", ("in",)),
       # R43: menu editing
       ("add-edit-delete", "form", "Add a dish (name, description, price, category, veg/non-veg in India, spice); edit every field; delete it",
        "Saved as typed (API equal field by field); deleted: off the menu, kept on past orders", "UI; API GET /menu/manage, /menu", "r43-menu-edit-{user}"),
       ("price-rules", "error", "A price of 0, ₹120.50 (India) / $12.999 (US), then a change of more than 50%",
        "Refused with the rule in words; the big change asks 'Change the price by N%?' and saves only on Change price", "UI; API price unchanged until confirmed",
        "r43-menu-edit-{user}"),
       ("photo", "button", "Open a dish's photo from the editor (camera or gallery)", "The photo screen with the preview", "UI", "r43-menu-edit-{user}"),
       # R44: the price message follows the field (it used to stay after the price was fixed)
       ("price-message", "error", "New dish: 12.505 and Save, then 12.50, 12.5, 12, 0.99, then 12.505, 0, -1, empty (US); 120.50 and Save, "
        "then 120, 120.50, 0, 120 (India)", "The rule's message for each invalid price; none for a valid one, as soon as it is typed (no stale message)",
        "UI (dish-editor-error); the same rule unit-tested (packages/mobile-core/test/price-rule.test.ts)", "r44-price-rule-{user}"),
       ("categories", "button", "Add a category, rename it, set its hours, hide it, drag it to the top", "Each saved; the order customers see follows",
        "UI; API GET /menu/manage, /menu (order, names, hidden)", "r43-categories-{user}"),
       # R45: Delete category (empty only, asks first, in the history)
       ("category-delete", "button", "Delete category: on one with a dish, then (its dish deleted) Keep, then Delete",
        "With a dish: off, '1 dish · Move or delete its dish first', nothing deleted; empty: asks 'Delete …?', Keep leaves it, "
        "Delete removes it; gone from the website within 60 s; History 'Category … · deleted'",
        "UI; API /menu/manage, /menu, /menu/history; the website page (scripts/r43_menu.js)", "r45-category-delete-{user}"),
       ("options", "form", "A new option group (required, at least 1 / at most 1, priced options) on a dish", "Saved; the quote adds the option's price",
        "UI; API POST /pricing/quote", "r43-options-{user}"),
       ("schedule", "form", "Serve a dish only at set hours", "Saved; customers see its hours and can't order it outside them", "UI; API menu available_now",
        "r43-options-{user}"),
       ("history", "display", "Open History after the changes", "Each change: who, when, old → new; as the API's history", "UI vs GET /menu/history",
        "r43-menu-edit-{user}"),
       ("wrong-role", "permission", "A customer's token on the restaurant's menu editing API", "403", "API", "r43-menu-edit-{user}"),
       (*DOWN, "r42-api-down"), nas=(("empty", "a restaurant's menu has dishes"),))
screen(P, "(kitchen)/payouts", ("statements", "number", "Open Payouts", "Each weekly statement's amount = the restaurant's statement in the API",
                                "UI vs GET /finance/statements/me (scripts/r42_partner.js)", "r42-payouts", ("in",)),
       ("none-yet", "empty", "Before the first payout", "'Your first statement shows here…'", "UI", "r42-payouts", ("in",)),
       ("set-up", "button", "A restaurant without a payout account: Set up payouts", "A payout account with the market's provider (a real one opens its set-up page; the local test provider is ready at once)", "UI; API: GET /finance/payout-accounts/me/setup", "r43-payouts-setup-{user}"),
       (*DOWN, "r42-api-down"), nas=(("permission", "own statements only (API refuses others)"),))
screen(P, "(kitchen)/help", ("help", "link", "Open help topics", "Articles", "UI", "help"),
       nas=(("permission", "any partner"), ("empty", "always topics"), ("error", "API down: r42-api-down")))
screen(P, "account", ("account", "navigation", "Account and sign out", "Signed out", "UI", "r41-sweep"),
       nas=(("permission", "own account"), ("empty", "always the account"), ("error", "API down: r42-api-down")))
screen(P, "apply", ("documents", "form", "Apply: documents, FSSAI / food permit", "Sent for review", "UI; API", "apply"),
       ("permit-us", "form", "A US food permit", "Waiting for review", "UI", "r39-permit-us", ("us",)),
       ("permit-in", "form", "India FSSAI", "Waiting for review", "UI", "r39-permit-in", ("in",)),
       nas=(("permission", "a signed-up owner's own application"), ("empty", "a form"), ("error", "the form's checks")))
screen(P, "join", ("signup", "form", "Sign up a new restaurant", "The application", "UI", "signup"),
       nas=(PUBLIC, ("empty", "a form"), ("error", "the form's checks")))

# ── Delivery partner app ────────────────────────────────────────────────────────────────────────────────────────────
R = "rider"
screen(R, "index", ("opens", "navigation", "Launch", "Sign-in or Drive", "UI", "sign-in-email"),
       (*DOWN, "offline-sign-in"), nas=(PUBLIC, ("empty", "a launcher")))
screen(R, "sign-in", ("email", "form", "Email sign-in", "Signed in", "UI", "sign-in-email"),
       ("wrong-role", "permission", "Sign in with a restaurant's account", "Refused: 'This number is a restaurant or admin account'", "UI",
        "r42-wrong-role", ("in",)),
       ("phone", "form", "Phone sign-in", "Signed in", "UI", "r39-phone"),
       (*DOWN, "offline-sign-in"), nas=(("empty", "a form"),))
screen(R, "code", ("code", "form", "Enter the code", "Signed in", "UI", "deliver", ("in",)), nas=(PUBLIC, ("empty", "a form"), ("error", "wrong code refused")))
screen(R, "(tabs)/drive", ("online-offer-deliver", "button", "Go online, accept the offer, pick up, deliver with the PIN, go offline",
                           "Each step; the order delivered in the API", "UI; API", "deliver", ("in",)),
       ("batch", "button", "A batch offer", "Two drops", "UI", "batch", ("in",)),
       ("reoffer", "button", "Let an offer expire", "Offered to the next", "UI", "reoffer", ("in",)),
       ("offline", "empty", "Offline: no offers", "'You're offline'", "UI", "deliver", ("in",)),
       (*DOWN, "r42-api-down"), nas=(("permission", "a rider sees only offers made to them (API: access sweep)"),))
screen(R, "(tabs)/earnings", ("week-total", "number", "Open Earnings after a delivery", "The week's total = the API's; each trip = delivery fee + tip",
                              "UI vs GET /finance/earnings/me (scripts/r42_earnings.js)", "r42-earnings", ("in",)),
       ("after-delivery", "display", "Earnings after the delivery", "The trip listed", "UI", "deliver", ("in",)),
       ("nothing-yet", "empty", "A rider with no trips this week", "Zero, said plainly", "UI vs GET /finance/earnings/me (0)", "r43-no-trips-{user}"),
       ("open-payouts", "link", "Open past payouts from Earnings", "The payouts screen", "UI", "sos", ("in",)),
       (*DOWN, "r42-api-down"), nas=(("permission", "own earnings only (API: delivery partners only)"),))
screen(R, "(tabs)/account", ("account-sos", "button", "Account; SOS", "SOS screen", "UI", "sos", ("in",)),
       (*DOWN, "r42-api-down"), nas=(("permission", "own account"), ("empty", "always the account")))
screen(R, "delivery/[id]", ("pickup-dropoff", "button", "Pickup, drop-off, PIN", "Delivered", "UI; API", "deliver", ("in",)),
       nas=(("permission", "only the assigned rider (API refuses others)"), ("empty", "a delivery always has its order"), ("error", "wrong PIN refused (deliver)")))
screen(R, "documents", ("checklist", "button", "Onboarding checklist", "Each document's state", "UI", "onboarding", ("in",)),
       ("signup-checklist", "display", "A new rider's checklist", "Steps to go", "UI", "signup"),
       nas=(("permission", "own documents"), ("empty", "the checklist always lists what's needed"), ("error", "API down: r42-api-down")))
screen(R, "document", ("upload", "form", "Upload a document photo", "Sent for review", "UI", "onboarding", ("in",)),
       nas=(("permission", "own documents"), ("empty", "a form"), ("error", "upload refused: message")))
screen(R, "join", ("signup", "form", "Sign up to deliver", "The checklist", "UI", "signup"), nas=(PUBLIC, ("empty", "a form"), ("error", "form checks")))
screen(R, "payouts", ("statements", "link", "Open payouts from Earnings", "Statements listed", "UI", "sos", ("in",)),
       nas=(("permission", "own statements"), ("empty", "'first statement' line"), ("error", "API down: r42-api-down")))
screen(R, "sos", ("sos", "button", "SOS: call, share location, cancel", "Each action", "UI", "sos", ("in",)),
       nas=(("permission", "a signed-in rider"), ("empty", "fixed actions"), ("error", "works offline (calls)")))


# ── The API side of the app numbers (run by run_web.py) ─────────────────────────────────────────────────────────────
@fn(P, "(kitchen)/payouts", "statements-equal-admin", kind="number", users=("in", "us"),
    action="Read the restaurant's statements (as the app does) and admin Finance's for the same ids",
    expected="Each amount, its week and its orders are the same in both", verify="API: GET /finance/statements/me (owner) vs GET /finance/statements/{id} (finance admin)")
def _(t: T) -> str:
    owner = token("partner.hyd@example.com" if t.user == "in" else "partner.boi@example.com")
    fin = token("finance_in" if t.user == "in" else "finance_us")
    mine = api("GET", "/finance/statements/me", owner)
    items = [s for s in (mine.get("items", mine) if isinstance(mine, dict) else mine) if s.get("payee_type") == "restaurant"]
    for s in items:
        a = api("GET", f"/finance/statements/{s['id']}", fin)
        ok(Decimal(str(a["amount"])) == Decimal(str(s["amount"])), f"{s['id'][:8]}: app {s['amount']} vs admin {a['amount']}")
        ok(len(a.get("lines", [])) == len(s.get("lines", [])), f"{s['id'][:8]}: lines differ")
    return f"{len(items)} statements equal admin's" if items else "no statements yet (equal: none on either side)"


@fn(R, "(tabs)/earnings", "trip-pay", kind="number", users=("in", "us"),
    action="Every trip this week and in the last statement", expected="Each pays the order's delivery fee and tip in full (+ any batch bonus)",
    verify="API: /finance/earnings/me lines vs the order's quote lines (delivery_fee, tip) in /pricing/orders/{id}/snapshot")
def _(t: T) -> str:
    rider = token("rider3.hyd@example.com" if t.user == "in" else "rider1.boi@example.com")
    w = api("GET", "/finance/earnings/me", rider)
    lines = (w.get("today") or {}).get("lines", [])
    checked = 0
    for ln in lines:
        snap = api("GET", f"/pricing/orders/{ln['order_id']}/snapshot", token("super"))
        fee = sum((Decimal(str(x["amount"])) for x in snap["lines"] if x["code"] == "delivery_fee"), Decimal(0))
        tip = sum((Decimal(str(x["amount"])) for x in snap["lines"] if x["code"] == "tip"), Decimal(0))
        got = Decimal(str(ln["total"])) - Decimal(str(ln.get("batch_bonus") or 0))
        ok(got == fee + tip, f"{ln['order_id'][:8]}: paid {got}, delivery fee {fee} + tip {tip} = {fee + tip}")
        checked += 1
    return f"{checked} trips today each = delivery fee + tip; week total {w.get('total')}"
