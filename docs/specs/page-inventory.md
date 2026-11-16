# Page inventory

Every page of the website and the admin console and every screen of the three apps,
who it is for, and its status against [page-checklist.md](page-checklist.md)
(item numbers in brackets). Screenshot sheets: `docs/screenshots/round8/<page>.jpg`
(390 px · 1366 px at 125 % · 1920 px).

**Baseline: QA on 2026-11-15, before Round 8** (dev at fbe0432). Layout items were
measured by `tools/web/page_audit.py` at 360–1920 px and 125 % / 150 % scaling on
44 page views; the rest is a person's review of the sheets and of the app
screenshots in `docs/screenshots/type-v1/`. "Review pending" means nobody has
looked at that page against the whole checklist yet: it is not a pass.
The **Fix** column names the Round 8 workstream that owns the fix (A checklist,
B type and layout, C location, D accounts, E wording, F7 kitchen landing,
F8 delivery landing, F9 help, F10 legal, P polish of what no other item covers).

Who: V visitor (signed out), C customer, K kitchen partner, D delivery partner, A admin.

## Website (apps/web)

| Page | Route | Who | Status (baseline) | What fails | Fix |
|---|---|---|---|---|---|
| Landing | `/` | V | **Fail** [3.3, 3.4, 2.5] | Sideways scroll at 360 px; at 1024 px the "Who gets your money" card hangs off the right edge; the address input cuts its own placeholder at 390 and on a 1366 px laptop at 125 %; hero does not stack under 1024 px; "Rider + tip" | B, E, C |
| Home, signed in | `/` | C | **Fail** [3.3, 2.1] | Cuisine row widens the page at 768 px and 1366 @150 %; kitchens without a photo show initials | B, P |
| Sign in | `/signin` | V | **Fail** [3.3, 5.2] | 360 px scrolls sideways; photo grid cut off at 1366 @125 %; phone only (no email) | B, D |
| Sign-in code | `/signin/code` | V | **Fail** [3.3] | As sign in | B, D |
| Forgot / reset password | `/signin/reset` | V | **Missing** [5.2] | Does not exist | D |
| Where we deliver | `/cities` | V C | **Fail** [3.3, 2.1, 2.2] | 360 px scrolls sideways; coming-soon cards show an empty image box; every country listed; no waiting-list count | C |
| City | `/[country]/[city]` | V C | Layout pass · review pending | — | B |
| Kitchen | `/[country]/[city]/[kitchen]` | V C | **Fail** [3.3, 3.4] | At 1366 @125 % the cover photo fills the first screen (no menu above the fold); the bag is a side panel at every width (no bottom bar under 1024 px) | B |
| Checkout | `/checkout` | C | **Fail** [3.4] · empty state pass | Summary beside the form at every width; full checkout not audited (bag lives in the browser) | B |
| Orders | `/account/orders` | C | **Fail** [3.3, 2.1] | Kitchen initials drawn on top of the kitchen name in the order header (1366 @125 %, 1920); initials instead of photos | B, P |
| Report a problem | `/account/orders/[id]/report` | C | Layout pass · review pending | — | — |
| Profile | `/account/profile` | C | **Fail** [5.2] | "To change your mobile number or email, contact support" (no linking) | D |
| Favourites | `/account/favourites` | C | Layout pass · review pending | — | — |
| Receipt | `/orders/[id]` | C | **Fail** [2.5] | Payee labels and wording ("rider", "US") | E |
| Tracking | `/orders/[id]/track` | C | **Fail** [2.1, 2.5] | The drawn route leaves the kitchen in the wrong direction and ends in empty map; "Your rider" | P, E |
| Report (tracking) | `/orders/[id]/report` | C | Review pending | — | — |
| Add your kitchen | `/partner` | V K | **Fail** [1.1–1.4, 2.2, 2.3] | A sign-in wall; its only button links to `/sign-in` (does not exist); no commission, documents, steps or FAQ | F7 |
| Deliver with BhojanGo | `/ride` → `/deliver` | V D | Built in F8 · review pending (was **Fail** [1.2, 1.3, 2.2]) | Pay from the city's rules (GET /delivery/terms), requirements from Markets, sign-up with phone + code, QR code to the app; screenshots `docs/screenshots/round8/deliver-*.png` | F8, E |
| Get BhojanGo Delivery | `/deliver/app` | V D | Built in F8 · review pending | Store links from Markets once published; until then says plainly the app isn't in the stores | F8 |
| Help | `/help` | all | **Fail** [2.3, 1.2, 6] | A wall of text; says the rider gets only the tip (wrong since round 7); no search, topics, articles or contact | F9 |
| Terms | `/terms` | all | **Pass** (F10, lead review) | Per country from Content → Legal, versions + `/terms/history`, key points, contents, print; draft banner outside production. [Screens](../screenshots/round8/legal/) | F10 |
| Privacy | `/privacy` | all | **Pass** (F10, lead review) | As terms; India: Grievance Officer (name and address placeholders until appointed), DPDP rights; US: CCPA and state rights. [Screens](../screenshots/round8/legal/) | F10 |
| Photo credits | `/credits` | all | Layout pass · review pending | — | — |
| Not found | any unknown URL | all | **Fail** [1.3, 6.3] | Next.js default "404 · This page could not be found", unbranded, no way back | P |

## Admin console (apps/admin)

| Page | Route | Status (baseline) | What fails | Fix |
|---|---|---|---|---|
| Sign in | `/login` | **Fail** [5.2] | Email + password only; no 2FA | D |
| Overview | `/overview` | **Fail** [3.3] | On a phone the whole menu stacks above the content; country tabs wrap; at 1366 @125 % stat labels wrap to 3 lines | B |
| Operations | `/operations` | **Fail** [3.3, 2.5] | 360 px scrolls sideways (tab row, table); "Rider" column | B, E |
| Partners | `/partners` | **Fail** [3.3, 2.5] | Tables squeezed on phones; "Rider documents" | B, E |
| Pricing and rules | `/pricing` | Layout pass · review pending | — | — |
| Pricing simulator | `/pricing/simulator` | Layout pass · review pending | — | — |
| Markets | `/markets` | Layout pass · review pending | — | — |
| Country | `/markets/[country]` | Layout pass · review pending | Will hold kitchen documents and delivery requirements | F7, F8 |
| City | `/markets/[country]/[city]` | **Fail** [3.3] | 360 px: the status row overflows | B |
| Finance | `/finance` | Layout pass · review pending | — | — |
| Settings | `/settings` | **Fail** [3.3] | The admins table is 68 px too wide on a phone | B |
| Content → Help | new | **Missing** | Help articles are hard-coded | F9 |
| Content → Legal | `/content/legal` | **Pass** (F10, lead review) | Drafts, Markdown preview, publish as the next version, audit log; country managers edit their country. [Screens](../screenshots/round8/legal/) | F10 |

## BhojanGo (customer app, apps/customer)

Screens reviewed from the round 6 screenshots (phone, QA).

| Screen | Route | Status (baseline) | What fails | Fix |
|---|---|---|---|---|
| Sign in | `/sign-in` | **Fail** [3.3, 5.2] | A large empty middle; phone only | D, P |
| Code | `/code` | Review pending | — | D |
| Home | `/(tabs)/home` | **Fail** [3.3, 2.1] | ~70 px empty band under the test banner (every screen); a grey box behind the language pill; kitchens as initials; the floating tab bar covers content at rest | P, B |
| Search | `/(tabs)/search` | Review pending | — | — |
| Orders | `/(tabs)/orders` | Review pending | — | — |
| Account | `/(tabs)/account` | **Fail** [3.3, 5.2] | Empty band at the top; "contact support to change your mobile or email" | P, D |
| Kitchen | `/restaurant/[id]` | Pass (reviewed) | — | — |
| Dish | `/item` | Review pending | — | — |
| Bag | `/bag` | Pass (reviewed: minimum order "$15", US tips) | — | — |
| Tracking | `/order/[id]` | **Fail** [2.1, 2.5] | Route drawn in the wrong direction; "Your rider"; map credit crowds the back button | P, E |
| Receipt | `/account/receipt/[id]` | Review pending | "rider" wording | E |
| Report a problem | `/report/[id]` | Review pending | — | — |
| Addresses, address | `/account/addresses`, `/account/address` | Review pending | — | — |
| Payments | `/account/payments` | Review pending | — | — |
| Notifications | `/account/notifications` | Review pending | — | — |
| Privacy and data | `/account/privacy` | Review pending | — | F10 |
| Language | `/account/language` | Review pending | — | — |
| Favourites | `/favourites` | Review pending | — | — |
| Where / out of area | `/where`, `/out-of-area` | Review pending | Location rules change | C |
| Payment failed | `/payment-failed` | Review pending | — | — |
| Gallery | `/gallery` | Review pending | — | — |

## BhojanGo Kitchen (apps/partner, was BhojanGo Partner)

| Screen | Route | Status (baseline) | What fails | Fix |
|---|---|---|---|---|
| Sign in, code | `/sign-in`, `/code` | **Fail** [5.2] | Phone only; kitchens should start with email | D |
| Apply, join | `/apply`, `/join` | Review pending | Must match the web application (F7) | F7 |
| Which kitchen | `/kitchens` | Review pending | — | — |
| Orders | `/(kitchen)/orders` | Pass on tablet (reviewed, landscape) · phone review pending | — | — |
| Menu | `/(kitchen)/menu` | **Fail** [3.3] | Empty band at the top on phones | P |
| Payouts | `/(kitchen)/payouts` | Review pending | — | — |
| Help | `/(kitchen)/help` | Review pending | Should read the admin-managed help articles | F9 |
| App name | — | **Fail** [2.5] | "BhojanGo Partner" | E |

## BhojanGo Delivery (apps/rider, was BhojanGo Rider)

| Screen | Route | Status (baseline) | What fails | Fix |
|---|---|---|---|---|
| Sign in, code | `/sign-in`, `/code` | Review pending | Phone first (stays), email optional | D |
| Join, documents, document | `/join`, `/documents`, `/document` | Review pending | Must match the requirements on /deliver | F8 |
| Drive (home) | `/(tabs)/drive` | **Fail** [2.1] | The "map" is a drawing of streets, not a map | P |
| Delivery | `/delivery/[id]` | Review pending | — | — |
| Earnings | `/(tabs)/earnings` | **Fail** [3.3] | The "Paid weekly" card overlaps the "Today" heading | P |
| Payouts | `/payouts` | Review pending | — | — |
| Account | `/(tabs)/account` | Review pending | — | — |
| SOS | `/sos` | Review pending | — | — |
| App name | — | **Fail** [2.5] | "BhojanGo Rider" | E |

## Totals at baseline

- Website: 23 pages (incl. 404 and the missing reset page): 16 fail or missing, 7 review pending, 0 pass.
- Admin: 13 (incl. 2 missing): 7 fail or missing, 6 review pending.
- Apps: 41 screens: 9 fail, 2 pass on review, the rest review pending.

This table is updated as each Round 8 workstream lands; the final state is the
Round 8 report.
