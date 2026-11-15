# Website v2 against the design

Every designed page (`docs/design/web/r_<Page>.png`) next to the website on seed
data. `raw/<Page>.png` is the website's full-page screenshot; `<Page>.png` is the
side by side (design left, website right) made by `tools/web/design_compare.py`.

## Regenerate

With the stack up (`make dev`, or any compose project):

    COMPOSE_PROJECT_NAME=bhojango sh tools/web/screens_v2.sh

It opens Hyderabad and Boise around the clock for the run, places an order for
`customer1.hyd` through the APIs (kitchen accepts, ops assigns a rider, the rider
picks it up), saves a kitchen and a dish, takes the 19 screenshots
(`tools/web/screens_v2.py`, Playwright image on the compose network), then
delivers the order, removes the favourites, and prints the score table below.

## Scores (2026-11-15)

The score compares blurred 96 px thumbnails (layout and colour, not pixels);
above 0.11 is marked for a person to look at.

| page | score | verdict |
|---|---|---|
| MWebCheckout | 0.130 | NOTICEABLY DIFFERENT |
| MWebHome | 0.241 | NOTICEABLY DIFFERENT |
| MWebMenu | 0.215 | NOTICEABLY DIFFERENT |
| MWebSignIn | 0.147 | NOTICEABLY DIFFERENT |
| MWebTracking | 0.046 | close |
| WebCheckout | 0.032 | close |
| WebCities | 0.017 | close |
| WebCity | 0.110 | close |
| WebCustomise | 0.054 | close |
| WebFavourites | 0.072 | close |
| WebHome | 0.147 | NOTICEABLY DIFFERENT |
| WebKitchen | 0.032 | close |
| WebLanding | 0.104 | close |
| WebNotInArea | 0.064 | close |
| WebOrders | 0.027 | close |
| WebOTP | 0.085 | close |
| WebProfile | 0.005 | close |
| WebSignIn | 0.105 | close |
| WebTracking | 0.024 | close |

## What differs, and why

Common to all pages: the design shows Bengaluru-sized data (42 kitchens, eight
cuisines, three offers); the seed has 2 kitchens delivering to Madhapur, 5 in
the city and one offer, so grids are shorter and photos differ. Website pages
also carry the site footer (the phone designs have none), and a fixed bar
(phone "View bag", "Pay") is drawn where the viewport ended when Playwright
stitches a full-page screenshot.

- **MWebHome** (0.241): the design is an app-like phone home (no greeting, a
  bottom tab bar, no footer); the website keeps the greeting with the number of
  kitchens and the filter chips on phones, offers near you, and the site footer
  instead of a tab bar. The order bar now wraps to two lines with the minutes
  (fixed); the design's second line "PIN · rider" needs the PIN and rider on
  the order list, which `GET /orders` doesn't return. The header now has the
  logo before "Deliver to" (fixed).
- **MWebMenu** (0.215): same layout (cover, name, chips, tabs, dishes, bag bar);
  the website keeps the site header (address and search) above the cover, the
  seed menu has 7 dishes in 3 sections with section headings, plus Saved/Share
  buttons and the footer.
- **MWebSignIn** (0.147): the site header and footer frame the page (the "Sign
  in" button is now hidden on the sign-in pages — fixed); "Continue with
  Apple/Google" are not shown because the backend has phone sign-in only; the
  Send code button is pale until a number is typed (the design shows a typed
  number).
- **MWebCheckout** (0.130): same cards in the same order; the website adds the
  site header, the country's second way to pay (Card, from Markets), the rider
  note and promo code fields, and the footer; the Pay bar is fixed.
- **WebHome** (0.147): same layout; data (2 kitchens, 4 cuisines, one offer,
  one past order) makes it shorter. The bag button only shows with something in
  the bag; the order bar's second line (rider, PIN) needs those on the order list.
- **WebCity** (0.110, borderline): the website has cuisine filter chips and an
  "Offers in Hyderabad" section the design doesn't; kitchen cards show no
  "from ₹25 delivery" without an address (the fee depends on the address). The
  design's heading wraps because it was rendered with a wider fallback font.
- **WebLanding**, **WebSignIn**, **WebOTP** (0.08–0.105): header and footer
  as on every page; locally there is no IP-based "Looks like you're near…" hint,
  so that row only offers "Use my location"; no Apple/Google sign-in.
- **WebNotInArea** (0.064): the visitor has an address, so the header is the
  address header rather than the first-visit one; "Notify me" is a card with the
  consent box (the consent is required); the website lists the nearest live
  cities instead of the design's "Run a kitchen in …?" card and the "412 people
  asked" badge (per-city demand is admin-only data, not public).
- **WebFavourites** (0.072): one saved kitchen and dish (seeded by the run);
  the kitchen card has no open/closed badge.
- **WebKitchen, WebCustomise, WebCheckout, WebTracking, WebOrders, WebProfile,
  WebCities, MWebTracking** (≤ 0.054): same layout, type and colours; only data
  differs.
