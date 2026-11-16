# Type scale v1: evidence (Round 6, item 5)

Viewport screenshots of every website and admin page and of the main app screens, all
taken on QA on 2026-11-15, and every font size found on screen. The allowed sizes
(desktop / phone): display 64/44 · h1 40/30 · h2 28/22 · h3 20/18 · body-lg 18/17 ·
body 16 · label 15 · small 14 · caption 12 (uppercase labels and badges only).

## What was measured, and how

- **Website and admin**: `tools/web/font_sizes.py` (Playwright, read-only) visits every
  page at 1440 px and 390 px (admin at 1440 px), signed out, signed in as the Hyderabad
  and the Boise demo customers, and as the demo admin. It reads the computed size of
  every visible text node and form field, fails on any size off the scale or any 12 px
  text that is not uppercase, and with `SHOTS_DIR` saves the viewport screenshot.
  Result: **82 page views, 0 text nodes off the scale.** Screenshots: [web/](web/).
- **Apps**: each app built with `EXPO_PUBLIC_FONT_AUDIT=1` logs, per screen, the font
  sizes it renders (`FONT_AUDIT <route> <sizes>` in Metro); `tools/mobile/font_sizes.py`
  collects them while the QA Maestro flows walk the app on an Android emulator.
  Screenshots from those flows: [customer/hyderabad/](customer/hyderabad/),
  [customer/boise/](customer/boise/), [rider/](rider/), [partner/](partner/).

## Apps: every font size found on screen

The phone scale is display 44 · h1 30 · h2 22 · h3 18 · body-lg 17 · body 16 · label 15 ·
small 14 · caption 12. Every size below is one of those nine.


### customer (18 screens)

| Screen | Sizes (px:token) |
|---|---|
| `/` | 12:caption |
| `/account` | 14:small 15:label 18:h3 22:h2 |
| `/account/address` | 14:small 15:label 16:body 18:h3 |
| `/account/addresses` | 14:small 15:label 16:body 18:h3 |
| `/account/notifications` | 14:small 15:label 18:h3 |
| `/account/payments` | 14:small 15:label 18:h3 |
| `/account/privacy` | 14:small 15:label 16:body 18:h3 22:h2 |
| `/account/receipt/<id>` | 12:caption 14:small 15:label 16:body 18:h3 22:h2 |
| `/bag` | 12:caption 14:small 15:label 22:h2 |
| `/code` | 12:caption 14:small 15:label 16:body 22:h2 30:h1 |
| `/favourites` | 15:label 16:body 22:h2 |
| `/home` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 30:h1 44:display |
| `/item` | 12:caption 14:small 15:label 16:body 18:h3 22:h2 30:h1 44:display |
| `/orders` | 12:caption 14:small 15:label 18:h3 22:h2 |
| `/report/<id>` | 14:small 15:label 16:body 18:h3 |
| `/restaurant/<id>` | 12:caption 14:small 15:label 22:h2 30:h1 |
| `/search` | 12:caption 14:small 15:label 16:body 18:h3 22:h2 44:display |
| `/sign-in` | 12:caption 14:small 15:label 16:body 17:bodyLg 22:h2 44:display |

**All sizes in the customer app: 12, 14, 15, 16, 17, 18, 22, 30, 44** (9 of 9 allowed, nothing else).

### partner (8 screens)

| Screen | Sizes (px:token) |
|---|---|
| `/` | 12:caption |
| `/code` | 12:caption 14:small 15:label 17:bodyLg 22:h2 30:h1 |
| `/help` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 30:h1 |
| `/kitchens` | 14:small 18:h3 30:h1 |
| `/menu` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 |
| `/orders` | 12:caption 14:small 15:label 16:body 17:bodyLg 22:h2 30:h1 44:display |
| `/payouts` | 12:caption 14:small 15:label 16:body 18:h3 22:h2 |
| `/sign-in` | 12:caption 14:small 15:label 17:bodyLg 22:h2 30:h1 |

**All sizes in the partner app: 12, 14, 15, 16, 17, 18, 22, 30, 44** (9 of 9 allowed, nothing else).

### rider (7 screens)

| Screen | Sizes (px:token) |
|---|---|
| `/` | 12:caption |
| `/account` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 44:display |
| `/code` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 30:h1 44:display |
| `/drive` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 22:h2 44:display |
| `/earnings` | 12:caption 14:small 15:label 18:h3 22:h2 44:display |
| `/payouts` | 14:small 15:label 18:h3 22:h2 |
| `/sign-in` | 12:caption 14:small 15:label 16:body 17:bodyLg 18:h3 44:display |

**All sizes in the rider app: 12, 14, 15, 16, 17, 18, 22, 30, 44** (9 of 9 allowed, nothing else).

## Website and admin: every font size found on screen

- **website 1440**: 64 (display), 40 (h1), 28 (h2), 20 (h3), 18 (h3), 16 (body), 15 (label), 14 (small), 12 (caption)
- **website 390**: 44 (display), 30 (h1), 22 (h2), 18 (h3), 17 (body-lg), 16 (body), 15 (label), 14 (small), 12 (caption)
- **admin (1440)**: 40 (h1), 28 (h2), 22 (h2), 20 (h3), 16 (body), 15 (label), 14 (small), 12 (caption)

| Page view | Sizes (px) | |
|---|---|---|
| `web 1440 /` | 64 40 28 20 18 16 15 14 12 | ok |
| `web 1440 /signin` | 40 28 20 18 16 15 14 12 | ok |
| `web 1440 /signin/code?phone=%2B10000000000&next=%2F` | 40 28 20 18 16 15 14 12 | ok |
| `web 1440 /cities` | 40 28 20 18 16 15 14 12 | ok |
| `web 1440 /ride` | 40 28 20 18 16 15 14 12 | ok |
| `web 1440 /partner` | 64 28 20 18 16 15 12 | ok |
| `web 1440 /help` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /privacy` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /terms` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /credits` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /in/hyderabad` | 64 28 20 18 16 15 14 12 | ok |
| `web 1440 /in/vijayawada` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /in/visakhapatnam` | 64 28 20 18 16 15 14 | ok |
| `web 1440 /in/hyderabad/banjara-dosa-co-banjara-hills` | 40 28 20 16 15 14 12 | ok |
| `web 1440 /in/hyderabad/cafe-zafraan-begumpet` | 40 28 20 16 15 14 | ok |
| `web 1440 /us/boise` | 64 28 20 18 16 15 14 12 | ok |
| `web 1440 /us/boise/basil-leaf-thai-downtown` | 40 28 20 16 15 14 | ok |
| `web 1440 /us/boise/basque-corner-kitchen-downtown` | 40 28 20 16 15 14 12 | ok |
| `web 390 /` | 44 30 22 18 17 16 15 14 12 | ok |
| `web 390 /signin` | 30 22 18 17 16 15 14 12 | ok |
| `web 390 /signin/code?phone=%2B10000000000&next=%2F` | 30 22 18 17 16 15 14 12 | ok |
| `web 390 /cities` | 30 22 18 17 16 15 14 12 | ok |
| `web 390 /ride` | 30 22 18 17 16 15 14 12 | ok |
| `web 390 /partner` | 44 22 18 17 16 15 14 12 | ok |
| `web 390 /help` | 44 22 18 17 16 15 14 | ok |
| `web 390 /privacy` | 44 22 18 17 16 15 14 | ok |
| `web 390 /terms` | 44 22 18 17 16 15 14 | ok |
| `web 390 /credits` | 44 22 18 17 16 15 14 | ok |
| `web 390 /in/hyderabad` | 44 22 18 17 16 15 14 12 | ok |
| `web 390 /in/vijayawada` | 44 22 18 17 16 15 14 | ok |
| `web 390 /in/visakhapatnam` | 44 22 18 17 16 15 14 | ok |
| `web 390 /in/hyderabad/banjara-dosa-co-banjara-hills` | 30 22 18 16 15 14 12 | ok |
| `web 390 /in/hyderabad/cafe-zafraan-begumpet` | 30 22 18 16 15 14 | ok |
| `web 390 /us/boise` | 44 22 18 17 16 15 14 12 | ok |
| `web 390 /us/boise/basil-leaf-thai-downtown` | 30 22 18 16 15 14 | ok |
| `web 390 /us/boise/basque-corner-kitchen-downtown` | 30 22 18 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /` | 64 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /checkout` | 40 28 20 16 15 | ok |
| `web 1440 signed-in demo1.hyd /account/orders` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /account/profile` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /account/favourites` | 40 28 20 16 15 14 | ok |
| `web 1440 signed-in demo1.hyd /orders/<id>/track` | 64 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /account/orders?order=<id>` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.hyd /account/orders/<id>/report` | 40 28 20 16 15 14 | ok |
| `web 390 signed-in demo1.hyd /` | 44 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.hyd /checkout` | 30 18 16 15 | ok |
| `web 390 signed-in demo1.hyd /account/orders` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.hyd /account/profile` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.hyd /account/favourites` | 30 22 18 16 15 14 | ok |
| `web 390 signed-in demo1.hyd /orders/<id>/track` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.hyd /account/orders?order=<id>` | 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.hyd /account/orders/<id>/report` | 30 18 16 15 14 | ok |
| `web 1440 signed-in demo1.boi /` | 64 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.boi /checkout` | 40 28 20 16 15 | ok |
| `web 1440 signed-in demo1.boi /account/orders` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.boi /account/profile` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.boi /account/favourites` | 40 28 20 16 15 14 | ok |
| `web 1440 signed-in demo1.boi /orders/<id>/track` | 64 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.boi /account/orders?order=<id>` | 40 28 20 16 15 14 12 | ok |
| `web 1440 signed-in demo1.boi /account/orders/<id>/report` | 40 28 20 16 15 14 | ok |
| `web 390 signed-in demo1.boi /` | 44 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.boi /checkout` | 30 18 16 15 | ok |
| `web 390 signed-in demo1.boi /account/orders` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.boi /account/profile` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.boi /account/favourites` | 30 22 18 16 15 14 | ok |
| `web 390 signed-in demo1.boi /orders/<id>/track` | 30 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.boi /account/orders?order=<id>` | 22 18 16 15 14 12 | ok |
| `web 390 signed-in demo1.boi /account/orders/<id>/report` | 30 18 16 15 14 | ok |
| `admin /login` | 28 22 16 15 | ok |
| `admin 1440 /overview` | 40 20 16 15 14 12 | ok |
| `admin 1440 /operations` | 40 20 15 14 12 | ok |
| `admin 1440 /partners` | 40 20 15 14 12 | ok |
| `admin 1440 /pricing` | 40 20 16 15 14 12 | ok |
| `admin 1440 /pricing/simulator` | 40 20 16 15 14 12 | ok |
| `admin 1440 /markets` | 40 28 20 15 14 12 | ok |
| `admin 1440 /finance` | 40 20 16 15 14 12 | ok |
| `admin 1440 /settings` | 40 20 16 15 14 12 | ok |
| `admin 1440 /operations?scope=*&tab=live` | 40 20 15 14 12 | ok |
| `admin 1440 /partners?scope=*&tab=kitchens` | 40 20 15 14 12 | ok |
| `admin 1440 /pricing?scope=*&tab=delivery_fee` | 40 20 16 15 14 12 | ok |
| `admin 1440 /markets/IN` | 40 20 16 15 14 12 | ok |
| `admin 1440 /markets/IN/IN-AP-VJA` | 40 22 20 16 15 14 12 | ok |

## Notes

- The crawler ran from a US address, so the signed-out home shows Boise ("Boise, US ·
  Change city", dollars, EN/ES). India's pages are covered by the Hyderabad city and
  kitchen pages and the signed-in Hyderabad customer.
- `customer/boise/qa-04-bag-minimum.jpg`: one dish under Boise's minimum shows
  "The minimum order in Downtown is $15" (not "USD 15") and the US tips ($2, $3, $5);
  `qa-04-bag.jpg` is the bill once the bag is over the minimum.
- Admin at 1440 px shows 22 px on `/login` (the logo wordmark, sized from the mark and
  snapped to the nearest size on the scale) and twice on a city page. 22 is on the scale
  (h2 on a phone) but is not a desktop role; worth a look if the admin should use only
  desktop sizes.
- Hyderabad's customer flows that need an open city (browse, track) were run with the
  Boise demo customer instead: Hyderabad is closed at night on QA.

