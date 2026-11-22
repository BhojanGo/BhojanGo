# Go-live status

**As of 2026-11-20** (after round 25), against the 44 tasks in [BhojanGo_GoLive_Tracker.docx](BhojanGo_GoLive_Tracker.docx). Pull
request numbers (#nn) are on `BhojanGo/BhojanGo`; what each one did and how it was tested is in
[PROGRESS.md](PROGRESS.md). Tracker tasks are "task nn".

| Status | Count | Meaning |
|---|---|---|
| ✅ Done | **22** | The tracker's "done when" can be shown on `make dev` today, and on the QA environment |
| ⛔ Blocked on Srini | **14** | Needs money, an account or a decision only Srini can make. Where code is involved, it is written and waiting (noted) |
| ⬜ Not started | **8** | Pilot and launch work that starts once the blocked items clear |

The engineering in Phases 0–3 is done. Everything between here and the closed beta waits on the blocked items,
mostly the accounts (task 4) and the domain (task 3). What is ready and costs nothing more:

- **QA on Railway** (since 2026-11-14): the website, admin and APIs deployed from `dev`, on demo data (16 kitchens a
  city, 713 past orders with ratings), a demo rider simulator with its own riders so there is always an order on its
  way, and the "Test site" banner everywhere. Tests never write to QA; it gets read-only checks and the demo seed
  ([railway-deploy.md](runbooks/railway-deploy.md)).
- **Every `make ci` stage runs on GitHub** on each pull request, and is the merge gate (#80). The Android apps are
  built there (android-apk.yml), and the app screens that need a throwaway stack are taken there (app-screens.yml, #106).
- **Pilot dress rehearsal.** A two-hour Boise dinner rush has been run, first with 8 riders and then with 25 ([load/soak-report.md](load/soak-report.md), #50, #55).

## Product quality (rounds 6–9, 2026-11-15 → 16)

The bar since round 8 is "a real product, not a demo": every page and screen is held to
[specs/page-checklist.md](specs/page-checklist.md), and its status is in
[specs/page-inventory.md](specs/page-inventory.md).

- **Pages:** every website, admin and app page has a status; after round 9 all website pages and 11
  of 13 admin pages pass. Two admin pages still read a few labels from the country code instead of Markets
  (Partners' India document names, the rule editor's units), and a few app screens are only covered
  by flows.
- **Layout and type:** Inter with a fluid type scale; 55 page views measured at 12 sizes with no
  layout problems (#125, #133); admin tables fit phones (#136).
- **Accessibility:** axe-core runs in the website and admin end-to-end suites and fails on any
  serious or critical finding; both are at 0 findings of every impact (#136).
- **Sign-in:** phone or email with a password (Argon2id, breached-password check, lockout), admin
  two-step sign-in (#126, #132). The apps show "Can't reach BhojanGo" and Retry instead of hanging
  when the API is down (#135).
- **Delivery partners:** sign-up checks the country's minimum age and allowed vehicles from Markets (#134).
- **Content:** "Add your kitchen", "Deliver with BhojanGo", a Help centre managed in admin, and
  versioned Terms and Privacy per country with acceptance records (#127–#130). The legal text has
  placeholders until a lawyer fills them in (task 35).
- **Production builds:** a smoke test builds web and admin exactly as for production; it found and
  fixed production builds that still showed the test banner and blocked search engines (#137).
  Production must be rebuilt after #137.

## Payments (rounds 10–13, 2026-11-17)

- **Stripe in test mode on QA** (US): card payments with 3-D Secure, declines, refunds by item, Stripe Tax, and the
  webhook that places the order. Keys are sealed Railway variables only.
- **Cards only (R13):** what checkout offers is the country's `payment_methods` setting, edited in admin (Markets →
  country → Payment methods). The US is cards, Apple Pay and Google Pay (they run on cards). Stripe gets a payment
  method configuration with exactly those on and everything else off, so no Link, bank tab, Klarna or cash-back offer.
  India stays on Razorpay (faked) until its keys arrive.
- **Payouts:** Stripe Connect Express (Accounts v2). Weekly runs cover only a finished Monday-to-Sunday week, a second
  finance admin approves, and transfers go to each payee. A returned payment is paid again on the next payout day,
  and the apps say so with the amount and the date.
- **Finance adds up (R14):** Reconciliation and the contribution report use the payout run's own statements, so
  "Delivery partners are owed" is what the run pays. The minimum pay top-up counts as a platform cost: it has its own
  line, and "Platform keeps" and platform revenue are lower by it. An invariant test checks every recent week in
  every country to the cent (PLAYBOOK rule 68). The hourly finance job drafts last week's run on the payout day; on
  QA "Approve and pay" is refused until every payee who is owed money has a ready payout account.
- **Payment methods follow the provider (R14):** admin offers only what the country's payment provider takes
  (Stripe: cards, Apple Pay, Google Pay; Razorpay: cards, UPI, wallets, net banking), and the API refuses the rest.
- **CI:** `pr-checks.yml` runs the 9 real-Stripe tests on a throwaway Railway stack whenever payments code changes
  (PLAYBOOK rule 66). Express onboarding through Stripe's hosted pages stays a manual release check (a CAPTCHA).
- **Secrets (R13):** `tools/secrets/mask.py` masks every password, token and key in command output and logs; a
  project hook refuses unmasked commands that read the secrets files (PLAYBOOK rule 67). The three QA admin
  passwords that were once printed have been rotated.

## Launch decisions (round 15)

- **Boise is the first live city.** Everything between now and the first real order is in
  [launch/boise-readiness.md](launch/boise-readiness.md), with owner, status and cost.
- **US commission is 15%,** changed in admin as a new rule version approved by a second admin; past orders keep
  their rate. Commission can be set per country, city, zone and kitchen; no rate is written in code.
- **Legal entities are Markets data:** the US is operated by DeepTrics LLC, India by DeepTrics Software Solutions
  Pvt Ltd. Each country's legal entity (name, address, support contacts; CIN, GSTIN and grievance officer for India)
  is edited in admin and shown on the Terms and Privacy pages, the website footer, receipts, emails and Finance.
  Missing fields are flagged "required before launch". A build check stops any template naming a company.
- **Payment fees:** Stripe's real fee is recorded per payment. Where a provider doesn't report one (Razorpay,
  faked), the reports use the expected rate in Business rules (2%) and say "estimated".

## India tax rules (round 16)

All three are business rules per country, editable in admin and flagged **"Confirm with CA"** until Srini checks them:
- **Discounts and the tax base:** a kitchen-funded discount lowers it; a platform-funded one has its own setting
  (India: it doesn't, so the Hyderabad worked example is ₹640.72, GST on food ₹28.50 instead of ₹26.00).
- **Tax on commission:** India 18% GST on our commission, taken from the kitchen's payout and owed by the platform,
  with a commission tax invoice to the kitchen (Kitchen app and API); US 0%.
- **TDS (section 194-O)** on kitchen payouts: India 0% until confirmed, US 0%.
Reconciliation shows tax owed by type (customers, on commission, TDS), and the weekly invariant test checks them.
The old per-kitchen commission column is removed: commission comes only from rules.
Launch: [boise-readiness.md](launch/boise-readiness.md) now has costs, insurance, delivery partner checks and 1099s;
[incident-plan.md](launch/incident-plan.md) is drafted.

## Incident tools and tax follow-ups (round 17)

- **On QA:** round 16 is live there (its migration dropped the old commission column). The India rules from round 16
  are added on QA through admin by two admins (maker-checker), not by a reseed. Admin's rule form now shows every
  setting of a rule's type, including ones added after the rule was made (#157).
- **One rounding method for GST on commission:** per order, rounded to the paisa on the kitchen's statement; the
  commission tax invoice adds those amounts up and never rounds again, so its GST equals the statements' "Tax on
  commission" to the paisa. The weekly invariant test checks it for every kitchen.
- **Admin → Incidents** (the gaps round 16 listed): pause or resume a kitchen ("Closed for now" for customers, an
  optional "back at" time; the kitchen can't undo it); pause ordering for a city, a country or everywhere, with a
  note shown on the website and in the customer app; bulk refunds by kitchen, zone or time window, in full or a
  percentage, with a second admin's approval above the city's automatic refund limit; messages to a bulk refund's
  customers or a city's, by push and email in each customer's language (outside production only test accounts).
  Each needs its role, a reason and a confirmation step, and is in the audit log. Orders already placed carry on.
  [incident-plan.md](launch/incident-plan.md) now uses these tools.
- **PLAYBOOK rule 69:** in production, drop or rename a column only in a release after the code that stops using it is live.
- **Pricing models (checked, nothing built):** a flat fee per order for a kitchen can be set today: the commission
  rule "Flat per order" for that kitchen, with a 0% "Percent of food" rule for it too if the fee replaces the
  percentage (the two add up). GST on commission applies to it like any commission. A monthly subscription can't be
  expressed: rules price each order, and nothing charges a kitchen once a month. The restaurants table still has
  `pricing_model`, `flat_fee_per_order` and `monthly_subscription_fee`, saved by the kitchen pricing endpoint but
  read by nothing (the pricing engine and payouts use only rules). A subscription would need a periodic rule and a
  line on the weekly statement.

## Store and production readiness (round 18)

- **Merging:** a PR is merged once its CI is green, unless it drops or renames a column, writes to QA or costs money
  (PLAYBOOK rule 70).
- **Incidents follow-ups:** admin's bulk message picks a city from the admin's own cities (no typed area); while
  ordering is paused or a kitchen is closed for now, the bag on the website and in the app says why and its
  checkout button is disabled with the same words. Customer app screenshots of the incident states come from a
  throwaway stack (app-screens.yml, flow 04-incident-pause).
- **App stores** ([store/README.md](launch/store/README.md)): listing text, App Store privacy labels, Google Play Data
  safety answers and permission reasons for the three apps, screenshot sizes and `tools/mobile/store_shots.sh`.
  Likely rejections to fix before submitting: no in-app account deletion in BhojanGo Kitchen and BhojanGo Delivery
  (Apple 5.1.1(v)); the Delivery app's background location needs Google's prominent disclosure and declarations;
  no production build profile (`eas.json`); the test payment sheet can show outside the US; reviewers need
  password accounts (no fixed sign-in codes in production); unused microphone and "always" location strings; no
  privacy link in the partner apps; no report on quick messages; push tokens never registered. Sign in with Apple
  isn't needed (no third-party sign-in).
- **Production dry run** ([production-config.md](launch/production-config.md), [go-live.md](launch/go-live.md)):
  every variable per service and where it comes from; `tools/railway/prod_config_check.py` (names only, no network)
  finds 25 gaps in what `.railway/railway.ts` would give production: Stripe live keys and webhook secrets, the public
  web and API URLs, `IDENTITY_DATA_KEYS` (admins couldn't set up two-step sign-in), the worker's required email, SMS
  and push credentials, the web payments provider, a markets-only production seed, a way to create the first admin,
  push registration, Sentry, and store builds. The go-live runbook orders the steps from "accounts ready" to the
  first real order, each with its check and rollback, and lists when to stop.

## Store blockers and production gaps fixed (round 19)

Decisions: production is Boise only (India's markets kept, switched off); a markets-only seed; email through
Amazon SES; sign-in codes through Twilio Verify; order updates by push; Sentry on the free plan.

- **Apps (store review):** account deletion inside BhojanGo Kitchen and BhojanGo Delivery (waits while a payout is
  owed or orders are under way; deletes a delivery partner's documents; closes a departing owner's kitchen);
  background location only on shift, with Google's prominent disclosure first
  ([play-location-declaration.md](launch/store/play-location-declaration.md)); no unused microphone or "always"
  location strings; Privacy and Terms in the Kitchen and Delivery apps; report or block a chat message (reports in
  admin's support queue); push tokens registered after sign-in and removed at sign-out (Expo); checkout fails
  closed ("Payments aren't available in this city yet"); `eas.json` for the three apps with the store ids in one
  file (`config/store.json`) and a production build that refuses placeholders; reviewer accounts in a hidden city
  (`backend/tools/review_accounts.py`, run once at go-live). In the customer app a closed kitchen or paused city
  greys every dish's "+", and the paused bag shows the note and "Back to home".
- **Production config:** core-api refuses to start without https public addresses, `IDENTITY_DATA_KEYS` or a way to
  send sign-in codes (the error names the variable); the website never shows the fake card form in production;
  a tool for `IDENTITY_DATA_KEYS`; the markets-only seed (Boise live, India off, no demo data); a one-time first
  super admin command (password set by email, authenticator at first sign-in); SES and Twilio Verify with fakes
  for dev and CI; Sentry everywhere, off without a DSN; the worker no longer needs SMS credentials.
- **What is left for production** (`tools/railway/prod_config_check.py`: no gaps): 12 secrets from Srini's accounts
  (Stripe live keys and three webhook secrets, Twilio and its Verify service, the SES access key, two Sentry DSNs),
  9 store ids (three Expo project ids, three App Store Connect app ids, the Apple team id, the Apple Pay merchant
  id, the Play service account key), and the addresses once the domain is bought
  ([production-config.md](launch/production-config.md), [go-live.md](launch/go-live.md)).

## QA on bhojango.com (2026-11-19)

QA's addresses are now https://qa.bhojango.com (website), https://admin.qa.bhojango.com, https://api.qa.bhojango.com
and https://rt.qa.bhojango.com (Railway custom domains, DNS at GoDaddy, Let's Encrypt certificates). The website is
noindex on QA; Stripe's test webhooks point at the new API address. Details: [railway-deploy.md](runbooks/railway-deploy.md).

- **To do on 2026-11-26:** remove QA's old `*.up.railway.app` origins: delete `QA_OLD_ORIGINS` from
  `.railway/railway.ts` and the two old origins from QA's `CORS_ORIGINS` (core-api, realtime, worker). The old
  addresses keep serving (Railway keeps them), but browsers on them can no longer call the API after that.
- Production domains: a plan and a recommendation (Cloudflare DNS only) in
  [production-config.md](launch/production-config.md#production-domains-plan-nothing-changed-for-production).

## Location line, store review flow and app polish (round 20, 2026-11-19)

- **Location line (#164):** always "City, ST" with the state's short code from Markets ("Boise, ID",
  "Hyderabad, TG"), whether the city was guessed, picked or came from a saved address. States have a short code
  (`regions.short_code`, migration 0039, backfilled from the state code); admin Markets shows it on each state row
  and requires it when a city is added to a new state or a state without one. The customer app's home line shows
  "City, ST · Change" only for a live city.
- **"Who gets your money" card (#164):** every label sits on one line next to its percentage at 1024 and 1440
  (checked by `tools/web/e2e_web.py`).
- **Store review flow (#165):** orders by the review accounts cost $0.00 (a platform-funded "review" line on the
  quote, no Stripe call, never paid out), and the worker's `REVIEW_SIM=1` moves only review orders through
  accepted → ready → picked up → delivered, in production too. It is off (`"0"`) in production until the review
  accounts exist; switch it on for the store review ([launch/store/README.md](launch/store/README.md),
  [go-live.md](launch/go-live.md) step 14). `DEMO_RIDER_SIM` is still refused in production. CI test:
  `test_review_orders.py`.
- **Apps (#166):** BhojanGo Kitchen and BhojanGo Delivery offer the partner's country's languages from Markets, in
  Markets order; Terms and Privacy links on every sign-in screen and in the customer Account tab; no iOS background
  audio in the Kitchen app; the one dev warning (the bag opened as a modal over the dish modal) fixed, and each
  app-screens run now records the JS warnings per flow (0 in all 14 flows).
- Old agent worktrees removed.

## Pre-launch hardening (round 21, 2026-11-20)

- **Load test (#170, [launch/load-test.md](launch/load-test.md)): fail on API speed, realtime passes.** A Boise
  dinner rush at 3x launch on a throwaway stack: 300 orders an hour, 2,000 people browsing, 75 delivery partners,
  45 kitchen tablets. With one core_api process (as QA and production run today), p95 was 1-60 s and 16% of
  requests failed. Even at 1x launch, reads were 0.9-1.9 s at p95 (target 500 ms). With 3 processes: 0 errors, every
  order delivered, p95 1.1-3.2 s on a shared runner. Realtime lost 0 updates in every run. The cause is core_api's CPU
  (about 13 ms a request), not the database (1-2 active queries). Fixed: the home screen no longer runs about six
  queries per kitchen for every address. **Needs Srini:** more core_api processes in production (Railway replicas
  2-3, costs more); then a menu cache and lighter middleware.
- **Security review (#168, [launch/security-review.md](launch/security-review.md)):** 4 high findings fixed, each
  with a test that fails without its fix: script injection through kitchen names on public pages, forged Razorpay
  webhooks (an empty secret), a free wallet top-up, and kitchens setting their own status. Also fixed: the access
  sweep covers every core_api route with real rows, a per-person quote limit, review cities only through
  `review_accounts.py`, an open redirect. Six mediums are planned with estimates (tokens in localStorage, CSP,
  WebSocket token expiry, kitchen offer ceilings, bulk refund cap, image URLs). Secrets: gitleaks finds none in the
  whole history; GitHub holds one secret (`RAILWAY_QA_TOKEN`).
- **Restore drill (#167, [launch/incident-plan.md](launch/incident-plan.md#database-restore)):** back up, restore
  and check (migrations, row counts, health, finance invariants) in 12 s, on a copy built the way QA is. **QA has no
  backups**, and its private database can't be read without a change Srini approves (recommended: turn on QA's
  volume backups). Production as planned loses up to 24 hours (RPO) and is back in about 30 minutes (RTO); an
  hourly dump would bring RPO to 1 hour.
- **Apps (#169):** the Kitchen and Delivery apps no longer show the customer note "Country is separate: prices and
  kitchens follow your address." under Language. The rider-02 flow's one failure was Maestro losing its driver on
  the phone before the flow started, not the app; 70 reruns passed, and a failed flow now keeps the phone's whole log.

## Speed, backups, security mediums, phone numbers (round 22, 2026-11-20)

- **core_api is fast enough on one process (#174, [launch/load-test.md](launch/load-test.md)).** At 1x launch on one
  process: reads p95 23-86 ms, placing an order 50 ms (targets 500 ms and 1.5 s). At 3x on two processes: reads
  47-329 ms, placing an order 232 ms, 0 server errors, 0 lost realtime updates, every order delivered. Before: 0.4-1.1 s
  and 3-13 s. What changed: rules, menus, the kitchen board, availability and the home screen are cached by database
  versions (triggers bump them in the editing transaction, so an edit shows on the very next request in every
  process; migration 0040); the kitchen board's N+1 query; pure ASGI middleware; faster route matching; verified
  tokens remembered. Production: 2 core-api replicas for redundancy, uvicorn processes from the container's CPU
  (at most 2). **Railway estimate: about $37 a month at launch, $58 in a busy month at 3x, at most $106** (Pro plan,
  measured CPU and memory; formula in load-test.md). A US quote in production adds one Stripe Tax call (100-300 ms).
- **Backups (#172, #175, [launch/incident-plan.md](launch/incident-plan.md#database-restore)).** QA's volume
  backups are on (daily, kept 6 days; weekly, kept 27 days; the project was already on Pro, so no upgrade). The hourly
  `pg_dump` to its own bucket, kept 7 days, and the weekly restore test are built and pass end to end in CI (a local
  S3). Railway buckets are $0.015/GB-month, cheaper in practice than setting up R2 (both under a cent a month here).
  **Not yet on QA:** creating the `db-backups` bucket and the `db-backup` cron service in QA was stopped by Claude
  Code's safety check and waits for Srini to allow it; so the restore drill hasn't run on QA's real backup yet.
  Railway restores a volume backup only over the live volume, so that kind is not drilled on QA.
- **Security mediums fixed (#176, [launch/security-review.md](launch/security-review.md)).** Website and admin
  sessions in httpOnly, Secure, SameSite cookies with a CSRF check (the apps keep secure storage; a socket ticket for
  realtime); a nonce CSP without `unsafe-inline`; sockets close when their token expires and are capped per account and
  address; a kitchen-offer ceiling per country and city in admin Markets; a bulk-refund total cap (above it a second
  admin approves); photo URLs only from our uploads or photo hosts. Each fix has a test proven to fail without it.
  Everyone on the website and admin is signed out once. Left open: carrying a negative kitchen statement into the
  next week (done in round 23).
- **Phone numbers (#173):** shown in each country's format everywhere ("+1 208-555-0291", "+91 98765 43210") in the
  three apps, admin and the website; stored and sent as E.164.

## Backups on QA, negative statements, a steady loading test (round 23, 2026-11-20)

- **Backups on QA (#181, [launch/incident-plan.md](launch/incident-plan.md#database-restore)).** The `db-backups`
  bucket and the hourly `db-backup` cron service run on QA (Srini's approval); the bucket's keys are sealed variables
  and the GitHub secrets `BACKUP_*`, never printed. First copy 22:09 UTC: 1,362 KB, 58 tables, 10,593 rows, 12 s.
  **The restore drill on that real copy passed in 22 s** ([run 44827699088](https://github.com/BhojanGo/BhojanGo/actions/runs/44827699088),
  the job the weekly Monday schedule runs): fetch and sha256 11 s, restore 1 s, migrations at head, 57 tables /
  10,593 rows equal to the copy's own counts, `/health` and `/health/ready` healthy, finance invariants pass. QA was
  only read. QA's RPO is now 1 hour. [go-live.md](launch/go-live.md) step 3 now requires rehearsing a Railway volume
  restore on production before launch, while it's empty (it can't be practised on QA: it restores in place).
- **Negative kitchen statements are carried (#180, [launch/security-review.md](launch/security-review.md) S11).** A
  week below zero pays nothing and carries to the next statement as "Carried from last week"; next week's sales pay it
  off first. Each balance is carried once (a re-run changes nothing). Nothing ever charges the kitchen; after 4 weeks
  below zero, admin Finance lists it under "Kitchens to collect from". Shown on the kitchen's Payouts screen, the
  payout run, Reconciliation (carried in, carried on, paid = owed + carried in - carried on) and in the finance
  invariant test. Migration 0041 adds 4 columns. The core tests fail on the old code (2 failures, run 44826145341).
- **customer-01-loading is steady (#178): 20 of 20** ([run 44824744810](https://github.com/BhojanGo/BhojanGo/actions/runs/44824744810)).
  The held `/discover` is released only by the flow (no timer; no release fails the flow), and only the throwaway-stack
  build lengthens the app's 8 s GET timeout (production and QA builds keep 8 s; a production build refuses the
  setting).
- **Small fixes (#179):** admin's offer ceiling reads "Most a %-off offer can take off one order" (currency box kept);
  the website sign-in photos never leave a tile empty (kitchen covers, then the country's dish, then library dishes).

## Small fixes and checks (round 24, 2026-11-21)

- **"Soak Rider 9-25" are not on QA.** They appeared in R23's payout-run screenshot, which was taken on a local
  database left from an old load-test run (`tools/soak/setup.py`, Hyderabad riders created 2026-11-14 06:36 UTC,
  before QA existed). QA checked read-only: no Soak rider among its 15 riders with documents, and none in its India or
  US payout runs (one draft each, week of 9 Nov). Nothing was deleted. The script already refuses any database that
  isn't local (`tools/target_guard.py`). Screenshots now come from a fresh local seed.
- **Statement text (#184):** this week's result and the carried balance are separate lines: "This week came to ₹X
  below zero." and "Still ₹Y below zero from earlier weeks · carried to next week." (both when both apply; X + Y is
  the statement's total). In the kitchen app, admin and the commission invoice PDF (a "Your weekly statement" block
  when below zero), in all 8 languages (machine translations on the native review list).
- **No `next dev` on QA or production (#183):** QA runs `next build` + `next start`; the "N" in R23's screenshots came
  from a local dev server. `tools/web/dev_mode_check.py` fails on a dev page or an image that could start one; it runs
  on the production images in CI, daily against QA, and against production once `PROD_WEB_URLS` is set (go-live step 10).
- **Plurals (#183):** admin says "1 issue to look at" / "2 issues to look at", and the same on every other count
  (orders, refunds, cities, days, minutes...).
- **CI disk:** GitHub's runner ran out of disk building the stack; the heavy jobs now free unused SDKs first.

## Commission invoice, masking, India readiness (round 25, 2026-11-21)

- **Commission tax invoice (#187).** R24's invoice screenshot wasn't made by the invoice endpoint: its supplier text
  ("BhojanGo (legal entity as set in Markets)") is in no commit, and its numbers are a unit test's fixture, so its week
  didn't match the statement. The real weak spot nearby is fixed: the invoice is now built from one statement row
  only (its run's period, its own orders, commission and GST; `commission_invoice.for_statement`), and the invariant
  test checks every invoice against its statement. The supplier is the country's legal entity from Markets (India:
  DeepTrics Software Solutions Pvt Ltd); with no legal name the invoice is refused (409 `LEGAL_ENTITY_MISSING`),
  admin Finance says so with a link to Markets, and the Kitchen app says the invoice isn't ready. Never a placeholder.
  "Commission on 1 delivered order" / "4 delivered orders" in all 8 languages (the invoice itself stays English, like
  the receipt). QA's India and US already have legal names, so QA keeps issuing invoices.
- **Secret masking fails closed (#186).** `tools/secrets/config.py` says where the secrets files live (the OneDrive
  "Products" folder; `BHOJANGO_SECRETS_DIR` overrides it). If one is missing, `mask.py` stops (exit 3), names the
  folder and passes nothing through. Before, it looked in another folder and printed its input unmasked.
- **India readiness ([launch/india-readiness.md](launch/india-readiness.md), #186).** Before an India launch, not
  Boise: the GST invoice fields Rule 46 still needs (supplier and kitchen address and GSTIN, SAC, place of supply,
  CGST + SGST or IGST, signature; also a 16-character consecutive invoice number and credit notes), the questions
  for the CA, CIN and grievance officer, and FSSAI checks per kitchen. Nothing built yet.

## Kitchen tablet, PIN, hours, time zones, money words (round 27, 2026-11-21)

Everything from the R26 walkthrough, PRs #190-#203 and #205 (each merged only after every check was green).

- **The kitchen tablet can't miss an order silently (#196, #201).** R26's stall: the access token
  (15 min) expired and the token refresh hung with no timeout; every later board request waited on it.
  The refresh now gives up after 15 s and requests wait at most 20 s. The tablet gets orders over the
  kitchen socket (polling as fallback) with a heartbeat; after 15 s without one it shows a red
  "Not receiving orders: reconnecting" banner and rings. With no heartbeat for 60 s while open, the
  kitchen stops taking orders ("Not taking orders right now": quote 422, order and payment 409
  `KITCHEN_OFFLINE`) until the tablet is back. New-order push to the kitchen. Accept timer on the server's clock.
  Tested: tablet cut off locally: banner at 21 s, paused at 58 s, back 3 s after reconnecting.
  2-hour soak on a fresh local stack, an order every 10 min: 12/12 on the tablet in 0.3-1.8 s, 0 missed.
  On QA the tablet stayed open 17:58-19:58 (118 checks, no banner, never paused) before the journey order.
- **Delivery PIN (#192):** 4 random digits per order from `secrets`, weak codes (1234, 0000...) redrawn,
  no fixed PIN in any config; shown only once the order is picked up.
- **Opening hours (#199):** the next opening is inside the kitchen's hours and the city's delivery window
  (Morning Ridge 06:30, Boise delivery from 08:00: "Closed · opens Sun 8:00 am"); "+" disabled, no checkout.
- **Time zones (#194):** each city has its own zone (Boise: America/Boise); payout weeks use the
  country's payout zone (US: America/Boise). Admin times show the zone (MST).
- **Access (#193):** Viewer (IN) can't open US Finance; the sweep covers 560 role × country × page cases.
- **Money words (#198):** a week says "Waiting for approval", "Waiting for your payout account" or
  "Paid on <date>", the same in admin and the apps. Receipts (app and PDF) show each refund and the
  total paid; no $0.00 tax lines; the kitchen's "today" is net of refunds charged to it.
- **Order again (#200), refund panel (#197), city/out-of-area/payment-failed wording (#195), Documents
  Back (#190), Kitchen app portrait (#191), Boise live everywhere + Basque Corner photo (#203),
  translations and a CI gate that renders every website page in every language at 360 and 1440 px (#202).**
- **India commission:** the Hyderabad applicant's 15% comes from India's commission rule (tiers A 18%,
  B 15%, C 12%; default B), not code.

QA journey, 2026-11-21 (Boise, order #2A649D, Boise Bowl Co., customer1.boi, test card 4242, one partial
refund): paid 20:09:27, on the tablet 11 s later, accepted 20:09:52, almost ready 20:10, delivery
partner accepted 20:23:55, ready 20:24, picked up 20:24:51 (PIN 3736 shown from then), delivered 20:26:20,
Salmon Poke Bowl refunded $16.96 (missing item) 20:27; receipt: total $38.85, refunded $16.96, paid $21.89.

Found on the journey:
- **Not fixed yet: after ~15 quiet minutes the bag says "Can't reach BhojanGo"** (no price, Pay
  disabled; Retry fails too; opening another screen first makes it work). #205 fixed one real cause: on a
  401 the retry reused the sent request's body, so any POST after the access token expired failed (since
  P17; a test reproduces it, and a forced-expired token now prices fine on the emulator). But the same
  check after 17 idle minutes with #205 still failed, and the payment-provider GET failed with it, so
  there is a second cause, not yet found (suspect: the first requests after idle reuse a dead
  connection). Next round: log the real error on the device and fix it before the pilot.
  #205 also makes the Delivery app's GPS refresh the token on a 401 (it stopped sharing its position
  after 15 min online).
- Open: an offer that times out counts as declined for a day, so with one partner nearby the order waits
  until another partner comes online. Customer tracking says "Finding a delivery partner" after a partner
  has accepted (until pickup). Adding a dish from another kitchen replaces the bag without asking. The
  orders list shows the original total, not the total paid after a refund. The PDF date is day-first
  ("21 Nov 2026") on a US receipt. The tablet's outage note reads "from 2:50 pm to 2:50 pm" for a gap
  under a minute. Kitchen app (dev build): an uncaught `ExpoKeepAwake.deactivate` error toast.
- QA's demo kitchens with no tablet open (and no simulator) now show "Not taking orders right now", as
  designed. GitHub reports 10 Dependabot alerts on dev (the repo is public since R27; branches dev, main
  and QA are protected: PR required, required checks, no force-push or deletion).

## What's left before the pilot

In order. Items 1–4 are Srini's; the rest follow from them.

1. **Decisions (task 1):** the pilot city order and the team model.
2. **Domain and accounts (tasks 3, 4):** the domain; Stripe and Razorpay (free test mode first, task 18); Twilio or
   MSG91 with India DLT templates (one per message and language: `<message>_<lang>`, `otp_<lang>`, #105); SendGrid;
   Expo push; a Google OAuth web client ID (the "Continue with Google" button stays hidden until it's set); Sentry and a
   paging channel (task 31). Each one replaces a fake that is already wired; only keys are added.
3. **Production on Railway:** a production environment from the same config as QA (no demo seed: it refuses
   production), with the accounts' keys as sealed variables. Then the website can be indexed (task 27).
   Backups: the same hourly copies and weekly restore test as QA (running since round 23), plus one rehearsal of a
   Railway volume restore on production while it's empty (go-live step 3).
4. **Vendors and stores:** trademark (2), logo artwork (22), legal pack (35), outside pen test (33), app store
   accounts (36).
5. **Translations:** native speakers review the machine translations listed in
   [packages/i18n/REVIEW.md](../packages/i18n/REVIEW.md) (Hindi, Telugu, Tamil, Kannada, Marathi, Bengali, Spanish;
   app, website and every notification). CI already fails if a live country's language is missing a string (#105).
6. **Real phones:** one pass of the three apps on real Android and iOS phones (so far emulators: phone, tablet, and a
   phone set to a US time zone viewing a Hyderabad order, #104).
7. **People:** usability tests (29), sign the launch kitchens (37) and riders (38; 25 for Boise), on-call rota (34).
8. **Closed beta (39)**, then the paid pilot (40).

## What Srini needs to do, in order

1. **Task 1, decisions:** the pilot city order and the team model. The commission % is set as a rule (15% in the worked
   example) and can be changed in admin without a developer.
2. **Task 3, domain and handles**, then **task 4, accounts**. Each account replaces a local fake that's already wired; only
   keys need to be added ([11_Integration_Setup_Guide.md](11_Integration_Setup_Guide.md)). Railway is in place (QA);
   production needs the accounts' keys.
3. **Tasks 2, 22, 35 and 33** (trademark, logo artwork, legal pack, outside pen test) need outside vendors, which
   are paid.
4. **Task 5, the team.** It also sets the on-call rota (task 34).
   Plan for 25 riders in Boise: the dress rehearsal (#55) shows they carry the dinner rush, and 8 can't.
5. **Task 36, app store accounts** (Apple $99 a year, Google $25 once).
6. **Task 43, batching:** when to switch it on, per city. It's ready, and it's one checkbox in admin. The
   recommendation is off at launch, and on for nights when riders are short (#55).

## Phase 0 · Set up

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 1 | Make the open decisions | ⛔ Blocked on Srini | #27 | Phase 1 money decisions were made and coded (#27: who pays for a refund, rider floor over engaged time). Still open: the pilot city order and the team model. The commission % is a rule, 15% in the seed |
| 2 | Trademark search: name + logo C | ⛔ Blocked on Srini | — | Lawyer (money) |
| 3 | Buy domain and social handles | ⛔ Blocked on Srini | — | Money. Needed for web indexing (task 27), email sending and app store listings |
| 4 | Open vendor accounts | ⛔ Blocked on Srini | #14 | Accounts. Every provider (Stripe, Razorpay, Twilio, MSG91, SendGrid, Maps, Apple/Google sign-in, push, S3) runs as a local fake with no account (#14). Sentry has an adapter that is off (#44) |
| 5 | Line up the team | ⛔ Blocked on Srini | — | Hiring |
| 6 | Put the plan and specs in the repo | ✅ Done | #8 | `docs/specs/01-structure.md`, `02-restructure-map.md` |
| 7 | Repo restructure | ✅ Done | #8, #10 | core_api / realtime / worker; customer and rider apps |
| 8 | Lock the tech stack | ✅ Done | #11, #29 | ADR-011; ADRs 002, 006–009 updated; platform upgrade in #29 |
| 9 | One-command local setup | ✅ Done | #12 | `make dev` with Hyderabad and Boise seed data |
| 10 | CI/CD and staging | ✅ Done | #13, #43, #49, #80 | Every `make ci` stage runs on GitHub on each PR and gates the merge (#80). Staging is the QA environment on Railway, deployed from `dev` by config-as-code ([railway-deploy.md](runbooks/railway-deploy.md)). Production is the same config once the accounts exist (task 4) |

## Phase 1 · Foundation

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 11 | Sign-in and admin roles | ✅ Done | #15 | Phone OTP, Apple, Google (against local fakes), roles scoped to country / state / city |
| 12 | Markets | ✅ Done | #16 | India ▸ Telangana ▸ Hyderabad set up in admin, PostGIS zones |
| 13 | Rule engine | ✅ Done | #17 | Versioned rules with maker-checker; pause added in #40 |
| 14 | Quote engine + price simulator | ✅ Done | #18, #36 | The Hyderabad example matches ₹638.22 to the paisa |
| 15 | Tax | ✅ Done | #19 | Stripe Tax for the US (fake locally), GST rules for India |
| 16 | Menu modifiers and store hours | ✅ Done | #20 | |
| 17 | Order flow with payments | ✅ Done | #21 | Payment first, timeouts, outbox |
| 18 | Payments and refunds | ⛔ Blocked on Srini | #22, #41, #139–#151 | Stripe runs in test mode on QA (cards only, refunds, tax, Connect payouts; 9 real-Stripe tests in CI). Razorpay still needs its account (India runs on the fake) |
| 19 | Payouts | ✅ Done | #23, #27, #42 | Weekly only (#42) |
| 20 | Dispatch and live tracking | ✅ Done | #24, #45, #50, #53 | Nearest rider, 30 s offer, re-offer; holds 10× pilot load (#45); waiting orders served oldest first (#50); pair offers when batching is on (#53) |
| 21 | Notifications | ✅ Done | #25, #38, #105 | Push, SMS, email and quick chat in every language a country lists in Markets (India 7, US English and Spanish), machine translations awaiting native review; CI fails on a missing one (#105). Fakes until the accounts (task 4); India DLT templates per message and language come with the MSG91 account |

## Phase 2 · Apps

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 22 | Final logo artwork and icons | ⛔ Blocked on Srini | #30 | Icons, splash and favicons are generated from the current logo (#30). The final vector from a designer, and its approval, are paid work |
| 23 | Design tokens and shared components | ✅ Done | #30 | |
| 24 | Customer app | ✅ Done | #31, #36, #38, #41, #94, #101, #104, #135 | At parity with the website (#94); the tab bar never covers content (#101); order times in the order's city time zone (#104); a clear message and Retry when the API can't be reached (#135). Every board screen has an app screenshot ([apps-v2](screenshots/apps-v2/README.md), #98, #106). Tested on Android emulators; do a pass on real phones before task 36 |
| 25 | Rider app | ✅ Done | #32, #37, #38, #42, #96, #103 | Offer to payout with background GPS (emulator); languages from Markets (#96). The manual demo riders never get the simulator's orders (#103) |
| 26 | Partner app | ✅ Done | #33, #37, #39, #40, #97, #102 | Tablets in landscape, phones in portrait (#102); dish photos with a customer preview and the rating summary (#97) |
| 27 | Customer website | ⛔ Blocked on Srini | #34, #37, #41, #84–#88, #104 | Ordering on the web works, and city and kitchen pages are server-rendered with sitemaps and structured data; live on QA (noindex). "Indexed" needs the domain (task 3) and production |
| 28 | Admin console | ✅ Done | #35, #36, #126, #136 | Country tabs, state chips and the city picker on every page; two-step sign-in (#126); tables fit phones and every page reviewed (#136) |
| 29 | Usability tests | ⬜ Not started | — | 5 customers, 3 riders and 3 kitchens per city: real people. QA is up, so this can start once Srini lines people up (task 5) |

## Phase 3 · Harden

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 30 | Automated tests | ✅ Done | #43, #52, #80, #106, #136, #137 | Playwright, G1 and every `make ci` stage on each PR (#80). Maestro: read-only flows on QA from the emulator (customer, rider, partner phone and tablet), and the write paths on a throwaway stack on GitHub (#106). Every scanner proves itself first: gitleaks, semgrep and the access-control sweep must catch planted findings (#52). axe accessibility checks in both e2e suites (#136); a production-build smoke test (#137) |
| 31 | Monitoring and alerts | ⛔ Blocked on Srini | #44, #50 | Dashboards and alerts work locally (`make observe`); alerts reach the admin console and the logs. "Sentry" and "reach on-call phone" need a Sentry account and a paging channel |
| 32 | Load test | ✅ Done | #45, #50, #55 | 10× pilot peak, 0 failures, every p95 under 100 ms (#45). Two-hour Boise dinner rush: with 25 riders, 100% completion, max wait for a rider 0.5 min, no alerts, 0 errors (#55; the first run with 8 riders found and fixed three problems, #50) |
| 33 | Security test | ⛔ Blocked on Srini | #46, #48, #52 | The automated pass is done and every High has been fixed (#46). An outside pen test is paid |
| 34 | Backup drill and runbook | ⛔ Blocked on Srini | #47 | Database restored in the drill. The on-call rota needs the team (task 5) |
| 35 | Legal pack | ⛔ Blocked on Srini | #129 | Lawyer (money). Terms and Privacy per country are versioned and admin-managed with acceptance records (#129); their placeholders (grievance officer, legal entity, governing law, US dispute method) need the lawyer |
| 36 | App store submission | ⛔ Blocked on Srini | — | Apple and Google developer accounts (money), and the domain for privacy URLs |

## Phase 4 · Pilot and Phase 5 · Go live

| # | Task | Status | PR | Notes |
|---|---|---|---|---|
| 37 | Sign launch restaurants | ⬜ Not started | #37 | Self sign-up and the admin approval queue are ready (#37) |
| 38 | Onboard riders | ⬜ Not started | #37, #127, #134 | Delivery partner sign-up (website and app) checks the country's minimum age and vehicles (#134), and the document checklist is ready. Background checks are a paid vendor. Plan for 25 in Boise: they carry the dinner rush with a third free at the peak; 8 can't (#50, #55) |
| 39 | Closed beta | ⬜ Not started | — | Needs production (task 4 accounts) and the apps in the stores (task 36) |
| 40 | Paid pilot | ⬜ Not started | #44 | KPI dashboards are ready (#44) |
| 41 | Go / no-go review | ⬜ Not started | — | Srini's decision, after task 40 |
| 42 | Grow the city | ⬜ Not started | — | Referrals and offers exist as rules (#17) |
| 43 | Turn on batching | ⛔ Blocked on Srini | #24, #53, #54 | Ready (#53, #54): the engine is ported to Python and runs in shadow everywhere, and live pairs from one kitchen are a per-city switch in admin (off). Turning it on is a decision. In the rehearsal it paired 60% of orders and saved a third of rider trips, at about +1 min median delivery; the recommendation is off at launch, on when riders are short (#55) |
| 44 | Public launch | ⬜ Not started | — | |
