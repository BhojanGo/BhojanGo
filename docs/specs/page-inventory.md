# Page inventory

Every page of the website and the admin console and every screen of the three apps,
who it is for, and its status against [page-checklist.md](page-checklist.md)
(item numbers in brackets).

**Status: end of Round 8, QA on 2026-11-16** (dev at 656a07c, QA reset with the new
seed). The baseline before Round 8 (2026-11-15, dev at fbe0432) is kept in the last
column so the change is visible.

How each status was reached:
- **Layout** [3.1–3.3, 4.3]: `tools/web/page_audit.py` on QA at 360, 390, 768, 1024,
  1280, 1366, 1536, 1920 px and 1366 / 1920 screens at 125 % and 150 % scaling (12
  sizes per page): sideways scroll, anything past the edge, clipped text, text under
  13 px. Result: **55 page views, 0 layout problems** (baseline: 8 of 44 failed).
- **Review** [1, 2, 4.4, 5, 6]: a person looked at the page's sheet in
  `docs/screenshots/round8/sheets/<page>.jpg` (390 · 1366 @125 % · 1920) and, where
  noted, the workstream's screenshots of other states (errors, applicant steps,
  languages). "Reviewed" means the lead looked; the PR's own review is not counted.
- **Tests** [5.2, 6.3, 8]: Playwright e2e (web 172 checks, admin 70 checks) and the
  backend integration suites on every PR; all green on the final merges.
- Accessibility [7] is checked by the e2e (labels, keyboard on sign-in tabs, roles) but
  there is no automated contrast/axe scan yet: **7.3 is not verified on any page**.

**Pass** = every checklist item that applies holds, as far as the methods above show.
**Fail** = an item does not hold (listed). Nothing is marked Pass without a review.

Who: V visitor, C customer, K kitchen partner, D delivery partner, A admin.

## Website (apps/web)

| Page | Route | Who | Status | Notes | Baseline |
|---|---|---|---|---|---|
| Landing | `/` | V | **Pass** (reviewed) | Location line names the IP town as itself ("Nampa, ID · Set your delivery location · Change city"); hero stacks under 1024; "Who gets your money" only for a served place | Fail |
| Home, signed in | `/` | C | **Fail** [3.3] → fixed in the Round 8 evidence PR | "Order again" cards cut kitchen names to 3 letters at 1366 @125 % (two-up below 1280 and a compact action, same PR); policy-update strip shows once for seeded accounts | Fail |
| Sign in (phone / email) | `/signin`, `?way=email` | V | **Pass** (reviewed) | Equal Phone / Email tabs, clear selected state; photo grid fits at every size | Fail |
| Create account (email) | `/signin?way=email&mode=create` | V | **Pass** (reviewed) | Password rule shown; 6-digit email code | Missing |
| Sign-in code | `/signin/code` | V | **Pass** (reviewed) | Phone formatted per country | Fail |
| Forgot / reset password | `/signin/forgot`, `/signin/reset` | V | **Pass** (reviewed) | Same answer for every email; expired link explained | Missing |
| Where we deliver | `/cities` | V C | **Pass** (reviewed) | Photos on every card; "N people waiting" shows when N > 0 (QA has 0) | Fail |
| Change city | `/cities?choose=1` | V C | **Pass** (reviewed, #124 shots) | Visitor's country first, search, "Other countries" | Fail |
| City | `/[country]/[city]` | V C | Layout pass · not reviewed | — | Review pending |
| Kitchen | `/[country]/[city]/[kitchen]` | V C | **Pass** (reviewed) | Bottom bag bar under 1024; cover photo still large at 1366 @125 % (acceptable, noted) | Fail |
| Checkout | `/checkout` | C | **Pass** (empty state reviewed; full checkout covered by e2e, B's shots) | Summary under the form below 1024 | Fail |
| Orders and receipt | `/account/orders` | C | **Pass** (reviewed) | Photos or branded tile, no overlapping initials; "Delivery partner" payee | Fail |
| Report a problem | `/account/orders/[id]/report` | C | Layout pass · not reviewed | — | Review pending |
| Profile | `/account/profile` | C | **Pass** (reviewed) | Sign-in and security: link phone / email, password; formatted numbers | Fail |
| Favourites | `/account/favourites` | C | Layout pass · not reviewed | — | Review pending |
| Tracking | `/orders/[id]/track` | C | **Pass** (reviewed, delivered state) | Route = current leg only; Cancel order while allowed (e2e) | Fail |
| Add your kitchen | `/partner` | V K | **Pass** (reviewed) | Real landing, commission from rules, documents per country, FAQ, verified email sign-up, saved application | Fail |
| Deliver with BhojanGo | `/deliver` (`/ride` redirects) | V D | **Pass** (reviewed) | Real pay numbers per city, requirements per country, sign-up → QR | Fail |
| Get the delivery app | `/deliver/app` | V D | **Pass** (reviewed) | Says plainly the app is not in the stores yet | Missing |
| Help centre | `/help` | all | **Pass** (reviewed) | Search, topics, popular articles, contact | Fail |
| Help topic / article | `/help/[topic]`, `/help/[topic]/[slug]` | all | **Pass** (reviewed) | Breadcrumbs, related, "Was this helpful?" | Missing |
| Terms | `/terms`, `/terms/history` | all | **Pass** (reviewed) | Per country, versions, key points, contents, print; draft banner outside production | Fail |
| Privacy | `/privacy` | all | **Pass** (reviewed) | DPDP grievance section (officer name "[To be appointed]"), US state rights; retention enforced by a worker job | Fail |
| Photo credits | `/credits` | all | Layout pass · not reviewed | — | Review pending |
| Not found / error | any unknown URL | all | **Pass** (reviewed) | Branded, search and three ways back | Fail |

## Admin console (apps/admin)

| Page | Route | Status | Notes | Baseline |
|---|---|---|---|---|
| Sign in | `/login` | **Pass** (reviewed, D's shots) | Password, then authenticator code; enrolment with recovery codes | Fail |
| Overview | `/overview` | **Pass** (reviewed) | Phone: menu drawer | Fail |
| Operations | `/operations` | Layout pass · not reviewed | — | Fail |
| Partners | `/partners` | Layout pass · not reviewed | "Delivery partner documents" | Fail |
| Pricing and rules | `/pricing` | Layout pass · not reviewed | — | Review pending |
| Pricing simulator | `/pricing/simulator` | Layout pass · not reviewed | — | Review pending |
| Markets | `/markets` | Layout pass · not reviewed | — | Review pending |
| Country | `/markets/[country]` | Layout pass · not reviewed | Holds kitchen documents and delivery-partner requirements | Review pending |
| City | `/markets/[country]/[city]` | Layout pass · not reviewed | — | Fail |
| Finance | `/finance` | Layout pass · not reviewed | — | Review pending |
| Settings | `/settings` | **Fail** [3.3, minor] | On phones the admins table scrolls inside its card; the Remove buttons start off-screen (stacked rows would read better) | Fail |
| Content → Help | `/content/help` | **Fail** [3.3, minor] | At 1366 @125 % the table's last column ("Updated") is cut at the card edge | Missing |
| Content → Legal | `/content/legal` | Layout pass · reviewed in F10's shots | — | Missing |

## BhojanGo (customer app), BhojanGo Kitchen, BhojanGo Delivery

Checked on the Android phone emulator (1080 × 2400) against QA with the Round 8 APKs
(GitHub run 43828466151) and the QA Maestro flows; font sizes from the apps' font audit
(every size inside its role's fluid range on all three apps). Screens:
`docs/screenshots/round8/apps/<app>/`. See the Round 8 report for flow results.

QA flows on the phone emulator: **customer 7 of 8 pass, kitchen 6 of 6, delivery 4 of 5**:

| Flow | Result |
|---|---|
| customer: orders-receipt, qa-browse, qa-language, qa-timezone, qa-track, tabbar-clearance | PASS |
| customer: sign-in-email (new) | PASS after two flow fixes (password lookup moved to a script; scroll to "Create an account") |
| customer: account-pages | FAIL in the software-GPU run: the first flow after Metro starts sees a black screen under Maestro's clear-state launch (dev build only; it passed in today's first run and every later flow passes). Test harness, recorded, not hidden. |
| kitchen: sign-in-email, qa/01–05 (incl. phone portrait) | PASS |
| delivery: qa/01–04 | PASS |
| delivery: sign-in-email (new) | FAIL before the keyboard fix (the keyboard covers the password field); fixed in the flow, not re-run yet |

| App · screen | Status | Notes | Baseline |
|---|---|---|---|
| BhojanGo · Sign in | **Fail** [6.3] | Phone / Email tabs work; photo collage fills the middle. But when the API can't be reached the screen shows placeholder tiles and "…" for the country code forever, with no message or retry | Fail |
| BhojanGo · Home | **Pass** (reviewed) | No empty band under the banner, no grey box behind EN, kitchen photos, "Delivery partner Srikanth", nothing under the tab bar at rest. Cuisine names cut ("North Ind…"), minor | Fail |
| BhojanGo · Kitchen, dish, bag | **Pass** (reviewed in flows) | — | Pass |
| BhojanGo · Tracking | **Pass** (flow) | Route = current leg; Cancel order card while allowed | Fail |
| BhojanGo · Account pages, receipt, language, time zone | **Pass** (flows) | — | Fail / review pending |
| BhojanGo Kitchen · Orders, menu, rating, language, phone portrait | **Pass** (flows, reviewed) | No top band; name "BhojanGo Kitchen" | Fail |
| BhojanGo Delivery · Drive | **Pass** (reviewed) | Real dark map (MapLibre + OpenFreeMap) with credit; offline sheet | Fail |
| BhojanGo Delivery · Earnings | **Pass** (reviewed) | "Today" no longer covered; "Paid weekly" is a footer | Fail |
| BhojanGo Delivery · Account, language | **Pass** (flows) | — | Review pending |
| All other app screens (addresses form, payments, notifications, favourites, report, out of area, payment failed, documents, delivery, payouts, SOS, kitchen apply/join/payouts/help) | Not reviewed | Covered only where a flow passes through them | Review pending |

Font sizes on screen (font audit, all three apps): every size inside its role's fluid range
(12, 13, 14, 15, 16.1, 17.1, 22.3, 28.4, 36.8 on a 1080 × 2400 phone); nothing readable under 13.
Not run in Round 8: the kitchen app on the tablet, the largest phone font setting, production builds.

## Totals

| | Pass | Fail | Not yet reviewed (layout pass) |
|---|---|---|---|
| Website (25) | 21 | 1 (fixed in the Round 8 evidence PR, awaiting the QA check) | 3 |
| Admin (13) | 3 | 2 (minor) | 8 |
| Apps | 9 screens / groups | 1 (sign-in error state) | the rest |

"Not yet reviewed" pages pass every automated check but nobody has looked at them
against the whole checklist; they are listed, not counted as passes.
