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
- **US commission was 15%** (superseded in round 29: commission 0%, the customer pays a platform fee),
  changed in admin as a new rule version approved by a second admin; past orders keep
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
- **India commission:** the Hyderabad applicant's 15% came from India's commission rule (tiers A 18%,
  B 15%, C 12%; default B), not code. (Superseded in round 29: 0% for every restaurant unless it has its own deal.)

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

## Pilot blockers from R27: the idle bag, offers, location, keep-awake (round 28, 2026-11-22)

PRs #208-#220, each merged only after every check was green.

- **The bag after ~15 idle minutes (#208, #218): root cause found on QA, not guessed.** Request IDs now go
  from the apps (`X-Request-ID`, logged on failure as `[api] <id> <method> <path> <status|error> <ms>`)
  into the API logs. With a 17-minute idle on QA, the tip tap's quote got 401, the token refresh 200 and
  the retried quote 200 (same request id + `-r`) - so the request reached the API and succeeded - yet the
  app showed "Can't reach". Cause: on React Native the retry's answer is not `instanceof Response`, and
  openapi-fetch 0.17 throws "onResponse: must return new Response()". A second cause: the 10-minute
  price hold ran out with no re-quote, leaving Pay off ("Price held 0:00"). Fix: the retry's answer is
  copied into a real Response; a network error retries once on a fresh connection (only for safe
  requests: GET, idempotency-keyed, quotes); an expired hold re-quotes silently; a temporary provider
  lookup error shows "Couldn't check payments. Tap to try again." and retries (2, 5, 15 s) - "Payments aren't available in this city yet"
  only when the country's provider really isn't live. The keep-alive and provider lookup were checked
  and were not the cause. Proven on QA: after 17 min "Price held 2:47", Pay live; after 30 min the API
  log shows quote 401 -> refresh 200 -> retried quote 200, the tip re-priced and Pay opened the test sheet.
- **Delivery offers (#214).** A timed-out or passed offer excludes that partner from that order only,
  and from its new offers for at most 2 min (was 24 h). Admin rules per city: `dispatch_offer_exclusion`
  (0-120 s, default 120) and `no_partner_alert` (1-60 min, default 8). No partner after N minutes: an
  Operations alert (resolved when someone accepts) and the customer sees "Finding a delivery partner is taking longer than usual" with the
  new arrival time. Test: two partners, the first misses the offer, the second gets it.
- **Partner location (#216).** Online partners send a fix every 5 s (distance filter off, background
  allowed while online; a task started with old options restarts). No fix for 60 s: "Location lost" on
  the partner's screen and the server drops them from offers (location TTL 60 s). Emulator, 60 min
  online on a moving route: 352 checks, 0 nulls, newest fix at most 5.3 s old; location off for 80 s
  showed the banner, which cleared when it came back.
- **Kitchen tablet keep-awake (#215).** Held while signed in, retried on error (no more
  `ExpoKeepAwake` toast). Emulator, screen-off timeout 15 s, 2 hours: 119 checks, always awake, never
  "Not taking orders".
- **P1:** tracking says "<Name> is heading to the kitchen" as soon as a partner accepts (#209);
  adding a dish or Order again from another kitchen asks "Start a new bag?" (#210, #219: the home
  Order again card on the app and web, and the web receipt, were missed in #210 and found on the
  journey); the orders list shows what was paid after refunds, and $0.00 for an order cancelled before
  it was paid (#211, #220); receipt PDF dates follow the country ("Nov 22, 2026" in the US) and the
  tablet's outage note says "for a few seconds" for a short gap (#212); Dependabot: 0 open alerts on dev (#213).
- **QA journey (Boise, Sun 22 Nov, one order with a test card, two partners online).**
  07:55 both partners online (the scripted one at the kitchen, rider1 in the app ~2 km away) ·
  08:00:50 bag built (Morning Ridge, $21.54) · idle 20 min · 08:21:10 bag still "Price held 9:49",
  Pay live · 08:22:33 paid $24.54 with 4242 ($3 tip) · order #846C20 on the tablet at once, accepted
  08:23:04 · almost ready 08:23:15 · 08:23:16 offer to the first partner, left to time out at 08:23:47
  (never offered to them again) · ~08:23:49 offer to rider1, accepted 08:24:04 · customer: "Jake is
  heading to the kitchen" · ready 08:24:33 · picked up 08:24:49 · delivered with the PIN 08:25:59.
  Receipt PDF "Date: Nov 22, 2026". Screenshots: `Claude outputs/review/r28/qa/journey/`.
- **Still open:** the server side of "Location lost" (dropped from offers after 60 s) is unit-tested
  but not watched live on QA; QA has no rows yet for the two new rules, so the defaults apply; the
  commission invoice PDF date is unchanged; the tablet's "Not receiving" sound needs a native build.

## Fee model v2 (round 29, 2026-11-22) and its follow-up (round 30, 2026-11-22)

PR #222 (R29) and PR #223 (R30), each merged only after every check was green.

- **Who pays what (R29, #222).** The customer pays a platform fee of 10% of the food subtotal (food only),
  at least $0.99, to BhojanGo. Restaurant commission defaults to 0%. The payment processing fee comes off
  the restaurant's payout: an estimate at placement; in production, the gateway's actual fee from the
  payment webhook. The delivery fee and the tip go 100% to the delivery partner. Tax comes from the tax
  provider (Stripe Tax) or India's tax rules; the platform fee is its own taxable line. All the money math
  runs in integer cents, rounded half-up per line. Migration `0045_fee_model_v2`.
- **Settings at every level (R29).** In admin, Pricing → Fees: Country → State → City → Restaurant. The
  most specific value wins and an unset level inherits. The page shows each value and where it comes from
  ("Inherited from: United States"), its start and end dates, changes waiting for a second admin, and
  the history (who, when, old → new). Every order keeps a snapshot of the settings that priced it, so a
  later change never alters a past order.
- **R30 follow-up (#223), migration `0046_fee_model_v2_fix` (data only).**
  India's minimum platform fee is ₹15 (was ₹85): ₹100 of food → ₹15, ₹300 → ₹30. The minimum, like every
  fee, is set per level on the Fees page. The delivery fee is distance-based: base + per mile (per km in
  India), configurable per country, state, city and restaurant. Seed: Boise $3.00 + $1.00/mile, Hyderabad
  ₹20 + ₹6/km. The partner gets the delivery fee + 100% of the tip, nothing else: the R29 guaranteed-pay
  top-up out of the platform fee is gone, and so are the seeded delivery-partner pay rules (base +
  distance + waiting, the hourly floor and the batch bonus). The platform fee is never reduced by partner
  pay. The payment fee estimate is set per method (card, UPI, wallet, net banking; cash has none), and in
  production Razorpay's reported fee replaces it per payment, as Stripe's already did. Restaurant
  sign-up terms say "You receive your dine-in menu price minus the payment processing fee. Commission:
  0%." in every language. Spice Route's 15% commission deal stays in the dev/QA seed only; the
  production seed has no restaurant-level rule (tested).
- **"Restaurant", never "kitchen" (R30).** Every text a customer or restaurant reads, in all 8 languages:
  website, apps, admin, push/SMS/email texts, help articles, legal drafts and the app's name
  (BhojanGo Restaurant). `tools/i18n/kitchen_scan.py` runs in `make ci-i18n` and fails on any hit.
  Code names stay (KitchenCard, `kitchen_join` keys, `/kitchens/join` routes, help slugs). So do
  demo restaurants' own names (Spice Route Kitchen, Basque Corner Kitchen, Kesar Kitchen).
- **Tests (R30).** New unit tests: ₹100 → ₹15 and ₹300 → ₹30; Boise 3 miles → delivery fee $6.00, partner
  $6.00, platform fee unchanged and never reduced by partner pay; payment fee per method (UPI, wallet, net banking,
  cash 0); the rider statement pays only the delivery fee + tip. Migration 0046 proven up → down → up on a
  database seeded as R29 left it (13 audited changes, then the exact R29 rules back). Local: backend unit 850,
  realtime 194, worker 397, seed 20, integration 1958 passed / 6 skipped, JS (admin 133, web 53, mobile-core 82,
  customer 32, ui 32, i18n 28, partner 15, rider 1). Screenshots (local-fresh): `qa-artifacts/pricing-v2-fix/`.
- **Still open:** QA's legal documents are published versions: their "kitchen" wording changes only when
  an admin publishes the new drafts. The app store listing name changes with the next store build. The
  hourly-floor code stays for a city that legally needs one (no city has one now).

## Delivery bands, road distance, GST per line (round 31, 2026-11-23)

PR #224, merged only after every check was green. Migration `0047_delivery_bands` (data only).

- **Delivery fee = distance bands.** 100% to the delivery partner, plus 100% of the tip; BhojanGo never adds to or
  takes from it. Bands and the max delivery distance are set per country, state, city and restaurant (admin
  Pricing → Fees; the most specific wins, maker-checker, audited). Seed: Boise 0–2 mi $3.50, >2–4 $4.50, >4–6 $5.50,
  >6–8 $6.50, max 8 mi; Hyderabad 0–3 km ₹30, >3–5 ₹40, >5–7 ₹50, max 7 km. R30's base + per mile stays in the
  rules engine as a template, unused. A restaurant past the max shows "Too far to deliver" in the list and on its
  page, and its menu can't be ordered (BhojanGo has no pickup orders).
- **Road distance.** Until R31 every distance was straight-line × 1.3. Now quotes and the listing use OSRM, a
  free self-hosted router on OpenStreetMap roads of the live cities (`infra/docker/osrm`, compose service `osrm`;
  QA service `osrm`). If OSRM can't answer, the straight-line × 1.3 estimate (`ROAD_FACTOR`) is used and each
  fallback is logged (`routing_fallback`). Production keeps the straight-line estimate until a router is chosen
  for it. The bill and the delivery partner's statement show the distance to 2 decimals.
- **Payment fee:** an order paid from the BhojanGo wallet has no fee (no gateway); only a wallet inside the
  gateway's checkout uses the wallet estimate.
- **GST per bill line (India, rates unchanged):** the bill shows each line's share under the GST line, e.g.
  ₹300 food at 2.50 km: GST on food ₹15.00 (5%); GST on platform fees ₹10.80 = 18% on delivery ₹5.40 + 18% on the
  platform fee ₹5.40. BhojanGo collects it (e-commerce operator); the restaurant gets ₹300.
- **CI:** the markets-only seed tests are no longer collected (and skipped) in the main integration run; they run
  in their own step against a markets-only database.

## Pickup orders, GST offer setting, production routing (round 32, 2026-11-23)

Migration `0048_pickup_orders` (adds columns, none dropped or renamed; plus rules).

- **Pickup orders.** At checkout (web and app) the customer picks Delivery or Pickup when the restaurant takes pickup
  orders (it turns this on and off on its tablet; seed: Boise Bowl Co., Spice Route Kitchen, Hitech Thali). Pickup
  has no delivery fee, no tip, no delivery partner and no distance limit; it is priced and taxed at the restaurant's
  address, which checkout shows with "Open in Maps". Its platform fee is its own setting, 5% of food with the same
  minimum ($0.99 / ₹15), at country, state, city or restaurant level (admin Pricing → Fees). The busy-hour fee
  doesn't apply (it is about delivery demand). The payment fee comes out of the restaurant's payout, as for
  delivery. Flow: the restaurant accepts and marks it ready; the customer gets a push (SMS if no app) with a
  4-digit pickup code and sees it on the order; the restaurant enters it to hand the order over. A wrong code is
  refused; the 5th wrong code locks the order and the restaurant calls support (an admin can complete it).
  Boise pickup 3.99 + 10.99 + 22.00, 6% tax on food, card: platform 1.85, total 41.05, card fee 1.49, restaurant
  35.49, nothing to a delivery partner. Hyderabad pickup ₹300, UPI: platform ₹15, GST ₹15.00 + ₹2.70, total
  ₹332.70, restaurant ₹300.
- **GST on platform-funded offers (India).** New country setting "Platform-funded offers reduce GST base", off by
  default (today's behaviour). ₹480 food with a ₹48 BhojanGo offer: off → GST on food ₹24.00; on → ₹21.60.
- **Road distance in production (prepared, not deployed).** `.railway/railway.ts` declares the osrm service and
  `ROUTING_PROVIDER=osrm` for production too (the same image as QA, Boise and Hyderabad roads); the steps are in
  [runbooks/railway-deploy.md](runbooks/railway-deploy.md) ("Road distance in production"). The API checks OSRM at
  start-up (`routing_health`). Every delivery quote counts road vs fallback per hour; above 5% fallback (at least
  20 quotes) admin Operations gets an alert, resolved by a later healthy hour. Admin Overview has a Routing tile:
  the last 24 hours' orders priced by road vs fallback.
- **US tax (no change):** the local stand-in taxes food, delivery fee and platform fee (and the other fees) at
  Idaho's 6%; the tip is never sent for tax. Production uses Stripe Tax with a tax code per line; Stripe decides
  per jurisdiction. See the round 32 report for the table and the open question on fees in Idaho.

## Idaho tax lines, the cart, busy-hour fee to the partner, pickup steps (round 33, 2026-11-23)

Migration `0049_idaho_tax_lines` (rules only: nothing added, dropped or renamed).

- **Idaho tax (Tax Commission guidance).** Which bill lines are taxable is now a per-state setting on the tax rule
  (`tax:external` `taxable_lines`, rules at state level; admin shows it in plain words). Idaho: food and the platform
  fee (a service charge) are taxable, plus packaging and the other service charges; a separately stated delivery
  fee, the busy-hour fee (a delivery charge) and the tip are not. A state with no list keeps the old behaviour
  (Stripe Tax decides by tax code). Both providers follow the rule: the local/CI stand-in taxes exactly the listed
  lines; Stripe Tax gets the delivery fee as a separately stated shipping line (non-taxable code where the rule
  says so), a taxed fee as part of the meal, and any other line as non-taxable (reported, not taxed).
  Boise delivery 3.00 mi (3.99 + 10.99 + 22.00, card): platform 3.70, delivery 4.50 untaxed, tax 2.44, total
  47.62, card fee 1.68, restaurant 35.30, partner 4.50. Boise pickup: platform 1.85, tax 2.33, total 41.16, card
  fee 1.49, restaurant 35.49.
  Stripe Tax test mode, Boise (the payments e2e case `stripe_tax_idaho_taxable_lines`): with each line's own code,
  food is taxed 6% ($2.22), the delivery fee as shipping is not taxed, and the platform fee as "general services"
  is not taxed either (`product_exempt`). With the mapping from Idaho's rule the platform fee is taxed ($0.22) and
  delivery still isn't: tax $2.44, the same as the local stand-in.
- **Cart, not bag.** Every customer-facing "Bag / Add to bag / basket" is now "Cart / Add to cart / View cart" in
  all 8 languages (app, website, backend messages, help, privacy). The delivery partner's and restaurant's
  insulated delivery bags stay bags. `tools/i18n/kitchen_scan.py` is now `tools/i18n/wording_scan.py` and also
  fails on bag/basket in every language (`make ci-i18n`).
- **Busy-hour fee.** Off (0) in every seed (only Hyderabad had one: ₹15, 19:00–21:30). If it is turned on, all
  of it goes to the delivery partner (with the delivery fee), never BhojanGo; before this round it went to BhojanGo.
- **Pickup tracking.** Web and app: Placed → Preparing → Ready for pickup → Picked up (no "On the way", no Home).
- `packages/i18n/REVIEW.md`: the round 32 pickup strings are listed as needing native review.

## SOS flow, pickup countdown, cart icon (round 34, 2026-11-23)

No migration.

- **SOS Maestro flow (delivery partner app).** The SOS alert itself always went through; the flow failed one step
  later, tapping "Payouts" after closing the SOS screen. Cause: the flow scrolled up only until "Safety" showed, and
  Payouts is the row directly above it, so whether Payouts was on screen depended on how far the last swipe went.
  The flow now scrolls to Payouts by id and taps rows by id (`account-safety`, `sos-close`, `account-payouts`).
  The app is unchanged. 10 runs in a row on the emulator, all passed.
- **Pickup countdown.** A pickup order never says "Arriving": "Ready in about N min" until it's ready, then "Ready
  for pickup" with the restaurant's name and address, and "Picked up" once collected (web and app; Playwright in
  `e2e_web.py`, Maestro in `pickup.yaml`). The estimate behind it is now the ready time: when the restaurant
  accepted a pickup order, its estimate used to add a ride and handover time as if it were delivered.
- **Icons.** No shopping bags in the customer app or website: the "View cart" bar and the website's cart button
  use a cart; the Orders tab uses a receipt; Account > Payments uses a card.
- `packages/i18n/REVIEW.md`: the round 33 cart strings and the new `track.ready_in_about` are listed as needing
  native review.

## Live chat race fixed, list screens captured (round 35, 2026-11-24)

No migration.

- **Live chat, 1 in 50 rounds failed (several branches).** Cause: the chat list is refreshed by fetches (a poll,
  a status change, a quick message). A fetch that started before the customer pressed Send could finish after the
  sent message was on screen; it replaced the whole list, and the message was already marked as seen, so it
  vanished until the next 20 s poll (the check waits 10 s; the CI screenshot showed the input cleared, no error,
  the message missing). Fix: a fetch is merged into what's shown (messages are never deleted); a closed chat still
  replaces it, and after a block only my own messages carry over. Same fix in the apps' shared chat hook
  (`packages/mobile-core/src/chat.tsx`). Proof: the live chat check 200 rounds in a row, 200/200.
- **List screens (before any redesign):** home list, search, menus and cart on the website (desktop and phone)
  and the customer app, Boise and Hyderabad, with a long name, too far to deliver, closed, and a pickup
  restaurant that is too far to deliver (`qa-artifacts/r35/lists/`, local stack). Findings: there is no
  "pickup only" state (delivery can't be switched off; a too-far restaurant that takes pickup only shows "Too far
  to deliver" on the website and nothing at all on the app's menu); the website's search page at phone width is
  wider than the screen (515 px at 390); a cart under the area's minimum shows the minimum note instead of the bill.

## List and menu redesign (round 36, 2026-11-24)

Migration `0050_no_zone_minimum` (data only: every zone's minimum order 0; Boise Bowl Co.'s own minimum $15).

- **Restaurant list (app and website).** Compact cards: a wide 2.4:1 photo (heart and offer on it), the full
  name on up to two lines (the rating moved off its line), "★4.4 (9) · Thai · 0.9 mi", then "25–40 min · $3.50
  delivery", "Pickup only" or "Closed · opens 11:00 am". Order: open and deliverable, pickup only (too far to
  deliver, takes pickup), closed, then too far without pickup. The website's city page now uses the address's
  facts (can it deliver, pickup only) and the same order. "Free delivery" filter only where a restaurant funds a
  free-delivery offer.
- **Unique photos.** 8 new credited photos (CC0, CC BY, CC BY-SA; /credits); every kitchen in a city has its own
  cover, one of its own dishes. `tools/seed/demo_test.py` fails on a missing or shared cover.
- **Menu.** Under the name: rating · distance · time, then Delivery / Pickup ("$3.50 delivery" / "Pickup · 5%
  fee"; the cart keeps the choice). Every dish has a "+" (on its photo's corner, or round), "− 1 +" once added.
  Too far but pickup: "Too far to deliver · Pickup available", locked to Pickup. Too far, no pickup, or closed: a
  banner, adds off, the menu still readable.
- **India in whole rupees** for customers: app, website, receipts, customer messages (half up, display only;
  amounts and charges stay exact). Restaurant and delivery-partner pages and statements keep paise.
- **Search** (`/discover/search`): restaurants by name, cuisine or tag, then dishes by name with their restaurant,
  price and add. The cuisine circles hide once you type.
- **Minimums.** No platform (zone) minimum. A restaurant's own minimum shows the whole bill, "Add $0.50 more to
  order from <restaurant>" and a progress bar; Pay is off and the API refuses the order (BELOW_MINIMUM) until met.
- **Phones.** No page is wider than the screen at 360, 390 and 414 px (Playwright).

## BhojanGo offer budgets and India's bill to the paisa (round 37, 2026-11-24)

Migration `0051_platform_offer_budget` (one new table, `platform_offer_spend`; no data written).

- **Offers BhojanGo pays for are off by default.** Every seed (base, demo, markets-only) adds them paused ("Off
  by default ... set a monthly offer budget, then resume it"); restaurants' own offers are unchanged.
- **A monthly budget per country, state or city** (admin: Pricing & Rules, Offers: "BhojanGo offer budgets";
  setting one needs rules.approve). The nearest level with a budget is the pool an order spends from; none
  anywhere is 0, so those offers don't run. A quote gives a BhojanGo-funded offer only when the whole of it fits
  in what's left (budget $10, offer $3: three orders, not the fourth); placing the order checks again under a
  lock (OFFER_ENDED: the bag prices again). Spend per pool and month (market time). Operations get an alert at
  80% and at 100% (spent, or too little left to give the offer again). Home screens hide offers the budget can't
  pay for.
- **What an offer costs.** On each offer in admin: the most it can cost an order next to the platform fee
  BhojanGo earns on that order (at the order size where the gap is largest), a warning when it can cost more,
  and its budget (spent, left, running or not). Approvers can pause and resume BhojanGo's offers.
- **India's bill to the paisa.** Menus, cards, search and cart item lines keep whole rupees (₹289). The fair
  bill, Pay, receipts, order totals, refunds and customer messages show exact paise again (₹385.80), so the
  printed lines add up to the total charged (R36 had rounded them). Checked on 8 engine bills, US and India, by
  the shared bill rows, the website, the app and the receipt (`packages/ui/test/fixtures/bills.json`).
- **Fixed on the way:** the "Who gets your money" example for a city with no paid orders yet counted the card
  fee as tax (the simulator's split left it out).

## Two-column bill, phone numbers by country, offer budget refunds (round 38, 2026-11-24)

Migration `0052_offer_budget_returns` (one new table, `platform_offer_returns`; no data written).

- **The bill in two columns everywhere** (checkout, cart, order details, receipts on the website and in the app, the
  receipt PDF, the example bills): the label on the left with who gets it under it ("Restaurant", "100% to your
  delivery partner", "BhojanGo", "Government"; an offer says who pays), the amount on the right, never wrapped. Checked
  at 1440, 390 and 360 px (Playwright) and in the app (Maestro). Emails carry only the total, no lines.
- **Phone numbers by country** with libphonenumber-js (`packages/i18n/phone.js`, replacing R22's own table) and
  `phonenumbers` (`backend/shared/phone.py`): validated, stored as E.164, shown "+1 (208) 555-0123" / "+91 98765
  43210"; placeholders and examples follow the country (the address's, else the market's); a real number from
  another country is accepted (PHONE_COUNTRY_MISMATCH is gone; an invalid number is PHONE_INVALID, worded in the
  person's language). Sign-in (website and the three apps), the account's phone, delivery partner and restaurant
  sign-up, the waiting list, admin views.
- **Offer budget refunds:** a cancelled order (also one whose payment failed and expired) or a full refund gives its
  BhojanGo-funded offer cost back to the budget it came from; a partial refund gives back its share.
- **"GST on fees"** (was "GST on platform fees") in 8 languages, app, website and receipts; older orders read the new
  label too.
- **Admin wording:** no "kitchen" in the console's words ("paid by the restaurant"); `wording_scan.py` now also reads
  text between JSX expressions and strings inside template literals, so it really covers the admin app: 0.
- **Boise launch readiness** rewritten: [launch/boise-readiness.md](launch/boise-readiness.md).

## Pay button, phones as you type, chargebacks, US food permits, monitoring (round 39, 2026-11-24)

Migration `0053_disputes_permits` (one new table, `payment_disputes`, and eight nullable `restaurants.food_permit_*`
columns; no data written).

- **Nothing behind the Pay button on a phone.** Checkout below 768 px fills the screen under the header: its content
  scrolls inside and the Pay bar sits under it, never over it (was a floating button over the page). A restaurant's
  "View cart" bar reserves its own height at the bottom of the page. Playwright at 360, 390 and 414 px: the last
  content ends above the button, and no text is under it at any scroll position.
- **Phone numbers formatted as they are typed** (libphonenumber's AsYouType, `typePhone` / `reformatPhone` in
  `packages/i18n/phone.js`): US "(208) 555-01", India "98765 43210"; changing the country re-formats; backspace over a
  bracket or space deletes the digit before it. Website (sign-in, account, delivery partner and restaurant sign-up)
  and the three apps' sign-in.
- **Readiness report corrected:** the money model is commission 0%, a 10% (delivery) / 5% (pickup) platform fee paid
  by the customer (at least $0.99), the card fee paid by the restaurant, the delivery fee by distance band and 100%
  to the delivery partner. Old "15% commission" wording fixed in the go-live runbook, the specs, the design mock-up,
  the markets seed's notes and two older entries here.
- **Chargebacks** (Stripe `charge.dispute.created/updated/closed`, `payments/service/disputes.py`): the dispute is
  recorded against its order, ops are alerted (Operations page and paging), and the restaurant's share is held from
  its next payout run; admin Finance > Chargebacks takes evidence (files and a note) and sends it to Stripe. Won: the
  hold comes back. Lost: the restaurant bears the food amount for a food-quality reason (`product_unacceptable`),
  BhojanGo the rest and everything else (a country may list other restaurant reasons: Markets
  `dispute_restaurant_reasons`).
- **US food permits** (`catalog/service/permits.py`): where Markets `food_permit_required` is on (the US, from the
  seed), a restaurant gives its health-district permit (number, expiry, a photo or PDF) in "Add your restaurant" or
  the Restaurant app; an admin approves it (Partners > Applications > Food permits); no going live without one; a
  reminder 30 days before it expires (push and email); an expired permit pauses the listing until a renewed one is
  approved. QA gets the setting at its next seed run (nothing is written to QA by this round).
- **Monitoring ready:** only the Sentry DSNs and `PAGING_WEBHOOK_URL` are left to paste
  ([launch/monitoring.md](launch/monitoring.md)). Critical Alertmanager alerts, chargebacks and a used-up offer budget
  page through the webhook; admin Settings > Monitoring > "Send test alert" says which channels took it.
- **Fixed on the way:** no file could be uploaded from the Restaurant app (Expo's `fetch` refuses React Native's
  file parts: "Unsupported FormDataPart implementation"); uploads now go through XMLHttpRequest (licence, permit,
  dish photos). Found by the new permit flow on the tablet.

## Finance correctness (round 40, 2026-11-24)

No migration. The model and the audit of every finance number: [launch/finance-model.md](launch/finance-model.md).

- **Card fees are the restaurants'**, on the whole charge (tip included), and never BhojanGo's: Contribution no longer
  takes "Payment fees" from what BhojanGo keeps, and Reconciliation shows "Card fees (paid by restaurants)" as its own
  line instead of "Payment fees" and "Platform after payment fees" (which counted the restaurants' card fees as
  BhojanGo's). "Platform revenue" / "Platform keeps" are now "BhojanGo keeps".
- **Owed vs paid** for the same week is labelled: "Not in this payout yet: $X (N orders) — delivered after this
  payout run was prepared" (and money held for open chargebacks); carried balances keep their own lines.
- **US commission:** the seed has none (0%); the $0.44/order came from the admin e2e's 12% Boise override test order.
- **Chargeback hold** only when the restaurant would bear the loss: food quality or not received (now the
  restaurant's too). Fraud and every other reason: BhojanGo bears it, nothing is held.
- **Reconciliation test** to the cent and the paisa (US and India; delivery, pickup, tip, offer, refunds,
  cancellation, chargeback) and the worked Boise example (`tools/finance/worked_example.py`).

## Payout weeks and the validation sweep (round 41, 2026-11-24)

Migration `0054_payout_weeks` (a new table `payout_run_orders` and a NOT VALID check on `payout_runs`; no row changed;
it logs any existing run that isn't Monday to Monday, overlaps another, or shares an order).

- **Week labels say the year.** "Mon 15 Dec" was 15 Dec 2008 (a Monday: the round 40 worked example's own old week)
  and "Mon 25 Oct – Sun 31 Oct" an India test run in an earlier year; shown without a year they read as 2026's. The
  weeks themselves were right: Monday 00:00 to the next Monday 00:00 in the payout zone (America/Boise,
  Asia/Kolkata). Labels now read "Mon 16 Nov – Sun 22 Nov 2026".
- **An order is paid by one run only:** `payout_run_orders` (the order is the key), written when a run is prepared;
  runs from before it are checked through their statements. A run must be a Monday-to-Monday week (database check).
- **No delivery in the future:** an order's delivered time is the server's clock; a later one is refused.
- **One order count:** Contribution and Reconciliation both count orders delivered in the week by delivered time in
  the payout zone (review orders left out), and say so on screen.
- **Realistic test data:** the negative-balance test uses ₹45,000 (was ₹10,00,000); the access sweep's chargeback is
  ₹450 for food quality (was ₹1 "Other"); a test keeps recent weeks within ±₹50,000 / ±$1,000 and disputes at
  least ₹100 / $5. (Neither was seed data: both came from tests run on the local stack.)
- `tools/finance/check_payout_weeks.py` lists misaligned or overlapping runs, orders on two runs and future
  deliveries, read-only.
- **Validation sweep:** every website and admin page as a US and an India user at 1440 and 390 px
  (`tools/sweep/sweep_web.py`, in CI), and new Maestro sweep flows for the app screens no flow opened: see
  `qa-artifacts/r41/sweep/index.md`.

## Test isolation and functional validation (round 42, 2026-11-25)

No migration.

- **Tests never touch the dev database.** Integration tests run on `bhojango_test_<id>`, made, migrated, seeded and
  dropped per run (`tools/test_db.py`, `make test-integration`, CI's Migrations job); `--prove-untouched` counts the
  dev database (orders, refunds, payout runs, statements, balances, disputes, tickets, users) before and after and
  fails if anything changed. `tools/target_guard.py` refuses a database without "test" in its name and an API whose
  `/health` doesn't say `test_database: true`. Proof: qa-artifacts/r42/isolation-proof.md (2,174 tests, every count +0).
- **Every route has a functional spec** (`tools/sweep/routes.py --check` in `make ci-guard`): 98 routes from the
  Next.js and expo-router directories; specs in `tools/sweep/functional/<app>/<route>.json` (action → expected → how
  it's verified). Round 41's sweep missed the admin root `/`.
- **Page by page:** `tools/sweep/functional/run.sh` (website and admin, US and India users, numbers against the API
  answers and the database, then every page with core-api stopped) and the r42 Maestro flows; CI job "Functional
  pages (R42)". Report: qa-artifacts/r42/functional/index.md.
- **Fixed:** checkout said a promo code was "applied" when it took nothing off; a restaurant page without an address
  showed the old `delivery_fee` column ($2.99) while the bill charged the band ($3.50); admin Fees and the simulator
  ignored the picked place; an admin role could be granted at a place that doesn't exist; the app didn't preselect
  the city's default tip as the website does.
- **QA (approved):** India's restaurant documents say "restaurant" (14 texts; qa-artifacts/r42/qa-documents-change.md).

## Menu editing (round 43, 2026-11-25)

Migration `0055_menu_editing` (adds columns and a table; changes no row).

- **The restaurant edits its menu on the tablet** (BhojanGo Kitchen → Menu): add a dish; change its name, description,
  price, photo, category, veg/non-veg (India), spice level, on the menu, sold out today and its hours; delete it (a soft
  delete: past orders and statements keep its name and price). Categories: add, rename, hide, hours, drag to reorder.
  Option groups with their own prices, required or optional, at least / at most.
- **Price rules** (API and app): more than 0, cents at most (US), whole rupees (India); a change of more than 50% asks
  first (409 `PRICE_CONFIRM` until confirmed).
- **Hours:** a dish or category served only between two local times shows "Served 7:00 am – 11:00 am" and can't be
  ordered outside them (the quote refuses it).
- **History:** every change (who, when, old → new) in `menu_changes`; the tablet's History and admin Partners → the
  restaurant → Menu history (`GET /restaurants/{id}/menu/history`).
- **Propagation:** the website no longer caches a menu (core-api's own menu cache is versioned): a change shows on the
  next page view (measured 0.8 s on the local stack); the app reloads the menu when the restaurant opens.
- **Held price:** a quote holds its prices 10 minutes (the order is charged them even if the restaurant raises one);
  after the hold the cart is priced again and says "Price changed: <dish> <old> → <new>" above Pay (website and app).
- **r42 gaps closed:** Maestro flows for the empty states of a new customer, a wrong sign-in code, a restaurant with no
  orders, payouts Set up, a rider with no trips; the statement check reads every line's date and delivered time in
  the payout zone (the admin statement showed the viewer's zone); website server-side calls give up after 2.5 s
  (`apps/web/src/lib/coreFetch.ts`); a full US path on real Stripe test mode (`tools/stripe_e2e/test_r43_full_path.py`).
- Report: qa-artifacts/r43/functional/index.md. New strings in 8 languages (packages/i18n/REVIEW.md, round 43).

## Fixes, clean tests and one full fresh run (round 44, 2026-11-26)

No migration.

- **Price message on the tablet:** after one refused Save (12.505), a valid 12.50 still said "A price has at most
  2 decimals (12.99)": the editor set its message on Save only. Now the message follows the fields from the first
  Save and a save's server answer goes on any edit. The rule is `priceRule` in mobile-core (unit-tested: 12.50, 12.5,
  12, 0.99 valid; 12.505, 0, -1, empty not; India 120 valid, 120.50 not); Maestro `r44-price-rule-us/-in`.
- **Order status never goes backwards** (app order screen, website tracking; `packages/ui/order-status.js`): a late
  `eta_update` for "preparing" after "ready" made a ready pickup order say "Ready in about 20 min" and Cooking next to
  its pickup code, until the next socket message. Found by the full run (customer/pickup failed once).
- **Tests clean up:** `DELETE /restaurants/{id}/categories/{c}` (empty categories only, in the history); Maestro
  flows remove their test dishes, option groups and categories on `onFlowComplete` (pass or fail); sign-up flows and
  web functions delete the accounts they make (`tools/mobile/maestro/forget.js`, `framework.forget`); the admin help
  draft is removed. `tools/sweep/functional/leftovers.py` snapshots the stack before a run and fails it if anything the
  run made is still live or any row has a test name ("R4x …"); in `run.sh`, so CI's functional job runs it.
- **One full fresh run:** 553 rows (98 pages and screens, 326 functions, US and India), 553 PASS, 0 FAIL, 0 not run,
  none carried from an earlier round, no flaky rows, no leftovers; 2 h 41 min on a fresh local stack. Failed web
  functions and Maestro flows are tried once more and reported FLAKY. Report: qa-artifacts/r44/functional/index.md.

## Delete category on the tablet (round 45, 2026-11-26)

No migration.

- **Delete category** (restaurant tablet, Categories): for a category with no dishes, after "Delete <name>?" (Keep /
  Delete category); uses `DELETE /restaurants/{id}/categories/{c}` (round 44) and shows in History as "Category <name>
  · deleted". A category with dishes keeps the button off and says "N dishes · Move or delete its dishes first".
  New strings in 8 languages (packages/i18n/REVIEW.md, round 45).
- **Tests:** Maestro `r45-category-delete-us/-in` (refused with a dish; the dish deleted; Keep; Delete; gone from the
  API, customers' menu and the website page within 60 s; History) and customer app `r45-category-gone-us/-in` (an
  empty category's heading leaves the app within 60 s of the delete, measured). The website never shows an empty
  category; the app shows its heading until it's deleted.
- **Test fixes from the first two full runs:** `tools/mobile/hours.py` opens every restaurant (country manager's token; the
  demo order stopped at Hyderabad night), the categories and language flows scroll to what they check, re-offer
  waits by time, the /deliver vehicle choice is clicked by its label (its hidden radio now stays inside the label),
  the cart and order-list flows wait longer on a slow emulator.
- **Full fresh run** (the third; runs 1 and 2 found the test problems above): 557 rows (98 pages and screens, 328
  functions, US and India), 557 PASS, 0 FAIL, 0 not run, none carried from an earlier round, no flaky rows, no
  leftovers; 2 h 47 min. A deleted category left the website in 2-2.5 s and the app in 19-24 s. CI's layout check
  found the restaurant page's delivery/pickup switch clipped at 360 px (fixed). Report:
  qa-artifacts/r45/functional/index.md, notes in qa-artifacts/r45/notes.md.

## Category hours and empty categories (round 46, 2026-11-27)

No migration, no data change.

- **The "07:00 – 11:00" on every category was placeholder text** in the tablet's time fields, not data: no category
  had hours (QA public menus: 0 of 133; a fresh seed with demo data: 0 of 133). Now a category without hours shows
  "✓ All day" chosen and empty fields ("--:--"); with hours, "07:00 – 11:00" and "Clear (all day)". Strings in 8
  languages (packages/i18n/REVIEW.md, round 46).
- **Customers:** a category with hours is on the menu only inside them, on the restaurant's clock (it used to be listed
  with its dishes "later"); all-day categories always. Dish-level hours are unchanged (listed, "Served …", no Add).
- **Customer app:** empty categories are hidden, as on the website.
- **Tests:** integration (Boise and Hyderabad clocks), Maestro `r46-category-hours-us/-in` on the tablet and in the
  customer app, website function `category-hours`; the round 45 app flow empties its category before deleting it.
- **"Use my current location" no longer spins forever:** the customer app used to ask for a GPS fix with no time limit;
  now a fix from the last 2 minutes is used at once, otherwise it waits at most 15 s and says it couldn't find you
  (found as the run's one flaky row; after the fix the flow passed 3 of 3).
- **Full fresh run:** 563 rows (98 pages and screens, 331 functions, US and India), 563 PASS, 0 FAIL, 0 not run, none
  carried from an earlier round, 1 flaky (the location wait above), no leftovers; 3 h 11 min. Report:
  qa-artifacts/r46/functional/index.md, notes in qa-artifacts/r46/notes.md.

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
