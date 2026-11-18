# Page checklist: the definition of done for every page and screen

Every page on the website (`apps/web`), every page of the admin console
(`apps/admin`) and every screen of the three apps (BhojanGo, BhojanGo Kitchen,
BhojanGo Delivery) meets all of this before it ships. A page that fails an item is
listed as failing in [page-inventory.md](page-inventory.md), not hidden.

We are building a food delivery platform for kitchens, eaters and delivery partners
in many countries. The bar is a product a stranger trusts with their money, their
kitchen or their livelihood on first sight, at the level of Swiggy, Uber Eats or
DoorDash. A page that only works for the person who built it fails.

How each item is checked is in brackets: **[auto]** by a tool on every run,
**[review]** by a person looking at the page (screenshots in
`docs/screenshots/round8/`), **[test]** by an automated test in CI.

## 1. Purpose and action

- 1.1 The page has one clear purpose, said in its title (h1) in plain words. [review]
- 1.2 It has one primary action, visually first (the filled button). Secondary
  actions look secondary. [review]
- 1.3 Every link and button goes somewhere real and works: no dead ends, no 404,
  no "coming soon" button that does nothing. [auto: links crawled] [test]
- 1.4 After the primary action, the person knows what happened and what comes
  next (a confirmation, the next step, an email to expect). [review]

## 2. Real content

- 2.1 No placeholder, lorem ipsum, "TODO", sample names or empty boxes where an
  image or data should be. [review] [auto: banned strings]
- 2.2 Numbers come from data, not copy: prices, fees, commission, rider pay, cities,
  wait lists, ratings come from the API (Markets, rules, the pricing engine), so
  they are right in every country and stay right when an admin changes them. [review]
- 2.3 Text says what the product actually does (checked against the rules and the
  code), in the country's terms (FSSAI and GST in India; health permit and EIN in
  the US). [review]
- 2.4 Legal and policy text outside production carries "Draft: pending legal
  review". [test]
- 2.5 Wording: delivery people are "delivery partners", restaurants are "kitchen
  partners"; the apps are BhojanGo, BhojanGo Kitchen and BhojanGo Delivery. Never
  "rider", "partner app" or "US / GOVT" in anything a person reads. [auto: CI]

## 3. Layout at every size

- 3.1 Works at 360, 390, 768, 1024, 1280, 1366, 1536 and 1920 CSS px wide. [auto]
- 3.2 Works with display scaling 125 % and 150 % (a 1366 px laptop at 125 % lays
  out 1093 CSS px; a 1920 px screen at 150 % lays out 1280). [auto]
- 3.3 No sideways scroll, nothing past the right edge, no text cut off by its box,
  no overlapping elements, no image cut off where it matters (faces, food,
  the sign-in photo grid fits the viewport height). [auto] [review]
- 3.4 Content is at most 1200 px wide, with 16 / 32 / 48 px gutters (phone /
  tablet / desktop); grids reflow 1 → 2 → 3 → 4 columns; heroes stack under
  1024 px; the bag is a bottom bar and the checkout summary goes under the form
  under 1024 px. [review]
- 3.5 Apps: works on a 360 dp phone, a large phone and a tablet (the kitchen app
  in landscape), and with the phone's largest font setting. [review]
- 3.6 Dialogs and sheets fit the screen down to 1280 × 720 and 360 × 640: at most
  the screen's height, the inside scrolls, the title and close button stay visible,
  and the main button (Pay) is always reachable. [review]

## 4. Type

- 4.1 Only the type scale's sizes (tokens; lint fails on a raw font size). [auto: lint + font_sizes.py]
- 4.2 Inter for Latin text, Noto Sans for Indian scripts; sizes fluid between
  360 and 1440 px (display 36→52, h1 28→36, h2 22→28, h3 17→20, body-lg 16→18,
  body 15→16, label 14→15, small 13→14, caption 12 uppercase). [auto]
- 4.3 Readable text is never under 13 px; 12 px is only the uppercase caption. [auto]
- 4.4 Amounts use tabular numbers; money goes through the one formatter
  (`$15`, `₹99`, never `USD 15`). [review]

## 5. Every person, every way in

- 5.1 The page works for each person who can reach it: visitor (signed out),
  customer, kitchen partner, delivery partner, admin. A page that is not for
  someone tells them where to go instead. [review]
- 5.2 Every way in works where it applies: phone + code, email + password (and
  email code), Google. [test]
- 5.3 Every language of the visitor's country: no English left on a translated
  page, no text overflowing in longer languages, Indian scripts in Noto Sans. [auto: ci-i18n] [review]

## 6. States

- 6.1 Loading: a skeleton or spinner where content will be, never a blank page or
  a layout jump. [review]
- 6.2 Empty: says why it is empty and what to do (no orders yet → find food). [review]
- 6.3 Error: says what went wrong in plain words and how to recover (retry, go
  back, contact support); never a raw error, stack trace or code. [review] [test]
- 6.4 Offline / slow network in the apps: the screen says so and recovers. [review]
- 6.5 A money figure that is zero reads as zero ($0.00, ₹0.00), with no "—" and no
  extra line; a line of zero on a customer's bill is not shown. [review]

## 7. Accessible

- 7.1 Everything works with a keyboard; focus is visible; the order is logical. [review]
- 7.2 Every input has a label; every icon button has an accessible name; images
  have alt text (decorative ones empty). [auto: a11y scan] [review]
- 7.3 Contrast at least 4.5:1 for text (3:1 for large text and UI parts). Secondary
  text is #3D4A4E. [auto: a11y scan]
- 7.4 Touch targets at least 44 × 44 px on phones. [review]

## 8. Trust and safety

- 8.1 Sign-in and money pages never show another person's data; errors never
  reveal whether an account exists. [test]
- 8.2 Anything that costs money or can't be undone asks once, clearly. [review]
- 8.3 The test-site banner shows on every non-production page. [test]
- 8.4 Wherever "Terms" or "Privacy policy" is named (sign-in, checkout), it is a link
  to the country's page. [review]
- 8.5 Checkout offers only the country's payment methods from Markets (the US: cards,
  Apple Pay, Google Pay); nothing a provider adds on its own (Link, bank, Klarna,
  cash-back offers). [test: stripe-e2e]

## How to record a result

In [page-inventory.md](page-inventory.md), each page gets **Pass**, or **Fail** with
the item numbers that fail and a short note, plus a link to its screenshot sheet
in `docs/screenshots/round8/` (390 px, 1366 px at 125 %, 1920 px side by side).
