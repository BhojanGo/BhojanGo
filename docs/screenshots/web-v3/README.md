# Website v3 on QA: viewport screenshots and side-by-sides

Taken on 2026-11-15 from the QA website (`web-qa-3fd3b3f8.up.railway.app`) on the demo data (QA reset with the
base seed and `tools/seed/demo.py`), after #82. Tool: [`tools/web/screens_v3.py`](../../../tools/web/screens_v3.py).

## What is here

- `raw/<Page>-<width>-<top|middle|bottom>.jpg`: each page as a person sees it in the window (not full-page captures,
  which break on the sticky header and the phone tab bar): the top, the middle and the bottom of the page, at
  **1440 px** (desktop, 900 px tall) and **390 px** (phone, 844 px tall). `WebCustomise` is one view: the dish sheet is
  fixed to the window.
- `<Page>-<width>.jpg`: the side-by-side. Left: the design (`docs/design/web/r_<Page>.png`; at 390 px
  `r_MWeb<Page>.png` where the design has a phone version, else "Design: none at this width"). Right: the three
  website views.
- `github/`: two things QA's read-only demo can't show, taken from the GitHub runs on a throwaway stack:
  - `e2e-rider-on-map.jpg` (#81): the rider marker on the live map. The rider sends GPS fixes the way the rider app
    does, and the marker moves. On QA no rider phone is sending GPS for the demo order, so QA's tracking page shows
    the kitchen, home and route but no rider dot. This image is a full-page capture, so the sticky header is offset.
  - `third-country-*.jpg` (#79): New Zealand added in admin Markets (NZD, GST, +64), and Wellington's directory
    entry, city page and kitchen page priced in NZD.

## Pages

| Page | Signed in | State |
|---|---|---|
| WebLanding, WebSignIn, WebOTP, WebCities | no | first visit |
| WebCity | no | Hyderabad: 21 kitchens in 9 areas, FAQ from the city's rules |
| WebComingSoon | no | a coming-soon city with Notify me (0 people waiting after the reset, so no count is shown) |
| WebNotInArea | no | an address outside every zone (Twin Falls, Idaho) |
| WebHome | Ananya (demo1.hyd) | home address; her order on its way (rider's name and PIN in the bar) |
| WebTracking | Ananya | that order on the map (MapLibre GL, OpenFreeMap tiles, OSM credited) |
| WebCustomise, WebKitchen | Ananya | a kitchen near home, a dish with choices, two dishes in the bag |
| WebCheckout | Ananya | tips from the `tip_presets` rule (₹10, ₹20 preselected, ₹30), a saved test card |
| WebOrders, WebProfile, WebFavourites | Ananya | her order history, profile, saved kitchens and dishes |

## How it was taken (read-only on QA)

The tool signs in as the demo customer and only browses: the bag lives in the browser, and checkout asks for a
price quote like any visitor's checkout. Nothing is ordered, saved or changed. Tests never write to QA
(`tools/target_guard.py`).

```sh
QA_WEB=https://web-... QA_CORE=https://core-api-... E2E_LOGINS_FILE=/outside/the/repo/BhojanGo_QA_Logins.txt \
  python tools/web/screens_v3.py            # needs playwright and pillow; CHROMIUM= an installed Chrome, optional
```
