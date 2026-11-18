# Page inventory

Every page of the website and the admin console and every screen of the three apps,
who it is for, and its status against [page-checklist.md](page-checklist.md)
(item numbers in brackets).

**Status: end of Round 9, 2026-11-16.** Round 8 measured every page on QA; Round 9 closed
the gaps it listed (#134–#138): the pages nobody had looked at were reviewed, the apps got
a clear message and Retry when the API can't be reached, admin tables fit phones, and axe
runs in both end-to-end suites. Only pages changed in Round 9 were re-photographed; the
rest keep their Round 8 sheets. The baseline before Round 8 (2026-11-15, dev at fbe0432)
is kept in the last column so the change is visible.

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
- Accessibility [7]: since Round 9 axe-core (4.11.3) runs in both e2e suites on 18 website
  and 13 admin pages and fails the run on any serious or critical finding
  (`tools/a11y/axe_check.py`, report in the e2e artifact and run summary). Before the fixes:
  web 17 moderate + 1 minor, admin 12 moderate + 1 minor, nothing serious; after: **0 at
  every impact on both**. That covers colour contrast [7.3] on those pages; the apps have no
  automated contrast check (their colours are the same tokens).

**Pass** = every checklist item that applies holds, as far as the methods above show.
**Fail** = an item does not hold (listed). Nothing is marked Pass without a review.

Who: V visitor, C customer, K kitchen partner, D delivery partner, A admin.

## Website (apps/web)

| Page | Route | Who | Status | Notes | Baseline |
|---|---|---|---|---|---|
| Landing | `/` | V | **Pass** (reviewed) | Location line names the IP town as itself ("Nampa, ID · Set your delivery location · Change city"); hero stacks under 1024; "Who gets your money" only for a served place | Fail |
| Home, signed in | `/` | C | **Pass** (fixed in #133, checked on QA) | "Order again" cards cut kitchen names to 3 letters at 1366 @125 % (two-up below 1280 and a compact action, same PR); policy-update strip shows once for seeded accounts | Fail |
| Sign in (phone / email) | `/signin`, `?way=email` | V | **Pass** (reviewed) | Equal Phone / Email tabs, clear selected state; photo grid fits at every size | Fail |
| Create account (email) | `/signin?way=email&mode=create` | V | **Pass** (reviewed) | Password rule shown; 6-digit email code | Missing |
| Sign-in code | `/signin/code` | V | **Pass** (reviewed) | Phone formatted per country | Fail |
| Forgot / reset password | `/signin/forgot`, `/signin/reset` | V | **Pass** (reviewed) | Same answer for every email; expired link explained | Missing |
| Where we deliver | `/cities` | V C | **Pass** (reviewed) | Photos on every card; "N people waiting" shows when N > 0 (QA has 0) | Fail |
| Change city | `/cities?choose=1` | V C | **Pass** (reviewed, #124 shots) | Visitor's country first, search, "Other countries" | Fail |
| City | `/[country]/[city]` | V C | **Pass** (reviewed R9) | Hyderabad and Boise at 390 / 1366; the "no kitchens match" search state reads right | Review pending |
| Kitchen | `/[country]/[city]/[kitchen]` | V C | **Pass** (reviewed) | Bottom bag bar under 1024; cover photo still large at 1366 @125 % (acceptable, noted) | Fail |
| Checkout | `/checkout` | C | **Pass** (empty state reviewed; full checkout covered by e2e, B's shots) | Summary under the form below 1024 R13: the payment dialog fits 1280 × 720 and 390 × 844 (title and close stay, the inside scrolls, Pay stays reachable) [3.6]; cards only, no Link [8.5]. | Fail |
| Orders and receipt | `/account/orders` | C | **Pass** (reviewed) | Photos or branded tile, no overlapping initials; "Delivery partner" payee | Fail |
| Report a problem | `/account/orders/[id]/report` | C | **Pass** (R9: failed [5.3, 1.4], fixed in #134) | The browser's untranslatable "Choose file" became an "Add a photo" button with Remove; "Tell us more" is a text area; a hint says why Send is greyed | Review pending |
| Profile | `/account/profile` | C | **Pass** (reviewed) | Sign-in and security: link phone / email, password; formatted numbers | Fail |
| Favourites | `/account/favourites` | C | **Pass** (R9: failed [1.3, 7.4], fixed in #134) | A saved dish whose kitchen wasn't saved led nowhere: it now links to its kitchen; hearts are 44 px | Review pending |
| Tracking | `/orders/[id]/track` | C | **Pass** (reviewed, delivered state) | Route = current leg only; Cancel order while allowed (e2e) | Fail |
| Add your kitchen | `/partner` | V K | **Pass** (reviewed) | Real landing, commission from rules, documents per country, FAQ, verified email sign-up, saved application | Fail |
| Deliver with BhojanGo | `/deliver` (`/ride` redirects) | V D | **Pass** (reviewed; sign-up step re-checked R9) | Real pay numbers per city, requirements per country; sign-up asks date of birth and vehicle, both checked against the country's Markets rules by the API (#134); no "2–5 days" promise | Fail |
| Get the delivery app | `/deliver/app` | V D | **Pass** (reviewed) | Says plainly the app is not in the stores yet | Missing |
| Help centre | `/help` | all | **Pass** (reviewed) | Search, topics, popular articles, contact | Fail |
| Help topic / article | `/help/[topic]`, `/help/[topic]/[slug]` | all | **Pass** (reviewed) | Breadcrumbs, related, "Was this helpful?" | Missing |
| Terms | `/terms`, `/terms/history` | all | **Pass** (reviewed) | Per country, versions, key points, contents, print; draft banner outside production | Fail |
| Privacy | `/privacy` | all | **Pass** (reviewed) | DPDP grievance section (officer name "[To be appointed]"), US state rights; retention enforced by a worker job | Fail |
| Photo credits | `/credits` | all | **Pass** (reviewed R9) | — | Review pending |
| Not found / error | any unknown URL | all | **Pass** (reviewed) | Branded, search and three ways back | Fail |

## Admin console (apps/admin)

| Page | Route | Status | Notes | Baseline |
|---|---|---|---|---|
| Sign in | `/login` | **Pass** (reviewed, D's shots) | Password, then authenticator code; enrolment with recovery codes | Fail |
| Overview | `/overview` | **Pass** (reviewed) | Phone: menu drawer | Fail |
| Operations | `/operations` | **Pass** (R9: failed [3.3, 6.1–6.3, 7.4], fixed in #136) | Stacked rows on phones; loading no longer says "No orders"; errors have Try again; Open is 44 px | Fail |
| Partners | `/partners` | **Fail** [rule 4, minor] (most fixed in #136) | Fixed: stacked rows, states on all 3 tabs, money from the formatter, no `country === "IN"` check, "kitchen" wording. Left: the Applications panel still labels India's documents "FSSAI licence" / "GSTIN" in code instead of from the Markets kitchen documents | Fail |
| Pricing and rules | `/pricing` | **Fail** [rule 4, minor] (most fixed in #136) | Fixed: "kitchen" wording, simulator links to the first live city from Markets, states. Left: `lib/ruleWords.ts` takes the currency symbol and km/mi from the country code, not Markets | Review pending |
| Pricing simulator | `/pricing/simulator` | **Pass** (R9: failed [rule 4, 2.5], fixed in #136) | Default city, country tabs and currency from Markets; default time today 8 pm | Review pending |
| Markets | `/markets` | **Pass** (R9: failed [rule 4, 3.3], fixed in #136) | No "Open US" special case; button no longer wraps at 390 R13: a country's Payment methods are edited here (saved as its payment_methods setting). | Review pending |
| Country | `/markets/[country]` | **Pass** (reviewed R9) | Holds kitchen documents and delivery-partner requirements (min age, vehicles now enforced at sign-up); table scrolls in its card with an edge shadow | Review pending |
| City | `/markets/[country]/[city]` | **Pass** (reviewed R9) | — | Fail |
| Finance | `/finance` | **Pass** (R11: failed [6.3], fixed) | A US finance admin (no Markets permission) saw an empty runs table and no error: the page now falls back to the admin's own finance country. Checked against real Stripe test mode: a run with a paid kitchen transfer and a reversed delivery-partner transfer R12: runs only for ended weeks, reports follow the selected run; R13: an empty figure reads $0.00 [6.5]; the header shows the role once. | Reviewed (R11) |
| Settings | `/settings` | **Pass** (R9 fix in #136) | Stacked rows under 768 px, Remove buttons 44 px and visible | Fail |
| Content → Help | `/content/help` | **Pass** (R9 fix in #136) | Table from 1280 px, rows below it: "Updated" no longer cut at 1366 @125 % | Missing |
| Content → Legal | `/content/legal` | Layout pass · reviewed in F10's shots | — | Missing |

## BhojanGo (customer app), BhojanGo Kitchen, BhojanGo Delivery

Checked on the Android phone emulator (1080 × 2400) against QA with the Round 8 APKs
(GitHub run 43828466151, native code unchanged since) and the JS of dev after Round 9, through
the QA Maestro flows; font sizes from the apps' font audit (every size inside its role's fluid
range on all three apps). Screens: `docs/screenshots/round8/apps/<app>/` and, for what Round 9
changed, `docs/screenshots/round9/apps/`.

Round 9 flow results (2026-11-16):

| Flow | Result |
|---|---|
| customer: account-pages, orders-receipt, qa-language, qa-timezone, sign-in-email, tabbar-clearance | PASS (Hyderabad customer); account-pages is the first flow after Metro starts, the one that saw a black screen before the runner fix (#138) |
| customer: qa-browse, qa-track | PASS as the Boise demo customer (Hyderabad's demo kitchens were closed at that hour, which the bag shows correctly: "Closed now · opens Tue 11:00"). qa-track needs the QA simulator to have an order on its way: it passed once and found none twice later |
| delivery: sign-in-email | PASS (the keyboard no longer covers the password field) |
| all three: offline-sign-in (API at an address that never answers) | PASS: "Can't reach BhojanGo", the reason and Retry show 6.9 s (BhojanGo), 7.1 s (Kitchen) and 7.8 s (Delivery) after the sign-in screen; Retry with the API still down shows the message again, never a half-working form |

| App · screen | Status | Notes | Baseline |
|---|---|---|---|
| BhojanGo · Sign in | **Pass** (R9 fix in #135) | Phone / Email tabs; when the API can't be reached: message, reason and Retry within 8 s instead of placeholder tiles and "…" forever R12: real food photos, "BhojanGo"; R13: Terms and Privacy policy open the website's pages [8.4]. | Fail |
| BhojanGo · Home | **Pass** (reviewed) | No empty band under the banner, kitchen photos, "Delivery partner", nothing under the tab bar at rest. Cuisine names cut ("North Ind…"), minor. Offline: the same error state | Fail |
| BhojanGo · Kitchen, dish, bag | **Pass** (reviewed in flows) | A closed kitchen's bag says when it opens and offers no bill | Pass |
| BhojanGo · Tracking | **Pass** (flow) | Route = current leg; Cancel order card while allowed | Fail |
| BhojanGo · Account pages, receipt, language, time zone | **Pass** (flows) | — | Fail / review pending |
| BhojanGo · Addresses, payments, notifications, favourites | **Pass** (code review R9) | Address edit: if the address didn't load, an empty "new" form saved a duplicate; now error and Retry (#135) | Review pending |
| BhojanGo · Report a problem | **Pass** (R9: failed [6.1, 6.3, 7.4], fixed in #135) | Loading and error states for the order's dishes; 44 px steppers; upload errors in words | Review pending |
| BhojanGo · Out of area | **Pass** (R9: failed [7.4], fixed in #135) | "Try another" is a 44 px link | Review pending |
| BhojanGo · Payment failed | **Pass** (R9: failed [5.3, 1.3, 6.3], fixed in #135) | Was English only, now 8 languages; dead "Chat with support" removed; status load has error and Retry | Review pending |
| BhojanGo Kitchen · Orders, menu, rating, language, phone portrait | **Pass** (flows, reviewed) | No top band; name "BhojanGo Kitchen" | Fail |
| BhojanGo Kitchen · Apply, join, payouts | **Pass** (R11 phone: payouts failed [7.2], fixed) | Payouts on a phone against real Stripe test mode: not set up → Stripe's page → in progress → ready with the week paid. "Continue on Stripe" read as "busy" to a screen reader after the first press; buttons now always carry their title as the label | Reviewed (phone, R11) |
| BhojanGo Kitchen · Help | **Pass** (R11 phone: failed [1.2], fixed) | Offline: "Your call-back request didn't load" with Retry, which recovers (R10 #139). Retry was a second filled button next to "Request a call back"; it is now secondary (LoadError `inline`) | Reviewed (phone, R11) |
| BhojanGo Delivery · Sign in, join | **Pass** (R9) | Offline error state (#135); join asks date of birth and vehicle from the country's rules (#134) | Fail |
| BhojanGo Delivery · Drive | **Pass** (reviewed) | Real dark map (MapLibre + OpenFreeMap) with credit; offline sheet | Fail |
| BhojanGo Delivery · Earnings | **Pass** (reviewed) | "Today" no longer covered; "Paid weekly" is a footer | Fail |
| BhojanGo Delivery · Documents, document, delivery, payouts | **Pass** (R11 phone: payouts failed [7.2], fixed) | Payouts on a phone: not set up, in progress, ready, a reversed week ("Sent back by our payments partner; we'll pay it again"). Set-up and Check again read as "busy" after a press; now labelled R13: "Minimum pay top-up" (no "floor" anywhere); a returned payment says the amount and the date it is paid again. | Payouts reviewed (phone, R11) |
| BhojanGo Delivery · SOS, account, language | **Pass** (code review / flows) | — | Review pending |

Font sizes on screen (font audit, all three apps): every size inside its role's fluid range
(12, 13, 14, 15, 16.1, 17.1, 22.3, 28.4, 36.8 on a 1080 × 2400 phone); nothing readable under 13.
Round 9 single checks (one run each, not a full audit):
- **BhojanGo Kitchen on the tablet** (2560 × 1600 landscape): orders, rating summary, menu
  with photo, language: 4 of 4 flows PASS; three-column board and menu beside store hours, nothing
  clipped (`round9/apps/kitchen-tablet.jpg`).
- **Largest phone font (200 %), BhojanGo home → kitchen → bag and bill**: the flow passed, but
  the screens **failed** [4.3]: the test banner was clipped at both edges, the account initial cut
  in its circle, the search box cut its placeholder in half and "The fair bill" ran into "WHO GETS
  YOUR…". Fixed in #138 and re-run: all four fit (`largest-font-before.jpg` / `-after.jpg`). Long
  kitchen names in "Order again" end in "…" by design.

## Totals

| | Pass | Fail | Not yet reviewed |
|---|---|---|---|
| Website (25) | 25 | 0 | 0 |
| Admin (13) | 11 | 2 (minor: labels from the country code instead of Markets) | 0 |
| Apps (17 screens / groups) | 16 | 1 (minor: Kitchen help) | 0 |

"Code review" app screens were read against the checklist and fixed where they failed; they
are walked through by a flow only where one passes them.
