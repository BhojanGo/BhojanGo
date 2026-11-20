# Go-live runbook: Boise

From "accounts ready" to the first real order, and the first week after it. Boise is the first live city. The US
operator is DeepTrics LLC. Commission is 15%.

This is a plan. Nothing in it has been done. Production does not exist yet. Creating it, and every account below,
costs money: nothing starts until Srini says go.

Read with:

- [production-config.md](production-config.md): every variable, where it comes from, and the gaps found on 2026-11-19;
- [boise-readiness.md](boise-readiness.md): accounts, legal, insurance, people;
- [incident-plan.md](incident-plan.md): who is called, pausing, refunds, customer messages;
- [`docs/runbooks/railway-deploy.md`](../runbooks/railway-deploy.md): how QA was built (the same steps, with the
  corrections learned there);
- [`docs/runbooks/backup-restore.md`](../runbooks/backup-restore.md) and
  [`docs/11_Integration_Setup_Guide.md`](../11_Integration_Setup_Guide.md);
- [store/README.md](store/README.md): app store listings.

**Who:** *Srini* (accounts, money, legal, people, approvals) or *Claude Code* (code, config, checks, runbooks).
Claude Code never sees a secret value: Srini pastes secrets into Railway, or Claude Code moves them with a script
that reads a file outside the repo and seals them without printing (as on QA, round 10).

**Rules for every step:**

- Use a Railway project token scoped to the **production** environment only. QA's token never touches production,
  and the production token never touches QA.
- Read every `railway config plan` before applying. Stop if it changes or deletes anything outside production.
- Tests never write to production ([`tools/target_guard.py`](../../tools/target_guard.py)). Only people place
  orders there, in the rehearsal (step 17).
- Write down each step's time and result in the launch log (a dated section at the end of this file, or a new file).

## Before step 1: what must be true

| Item | Who | Check |
|---|---|---|
| Accounts open: domain, Stripe live (activated for DeepTrics LLC), AWS (Amazon SES), Twilio (Verify; no sender number or 10DLC needed), Firebase (only for the FCM key Expo needs), Apple Developer, Google Play, Expo, Sentry (free plan) | Srini | Each account signs in; Stripe shows "live mode" activated |
| Readiness items 6, 7, 10, 11 done or dated: Idaho permit, lawyer-reviewed Terms and Privacy, background-check vendor, insurance | Srini | [boise-readiness.md](boise-readiness.md) updated |
| The code gaps from [production-config.md](production-config.md#gaps-found-on-2026-11-19-and-what-round-19-did) are fixed, merged to `dev`, and pass `make ci` and the GitHub checks. Done in round 19: production variables in `railway.ts`, SES email, Twilio Verify codes, the markets-only seed, the first-admin command, the `IDENTITY_DATA_KEYS` tool, Sentry, the website failing closed without a payment provider. Still to merge: push token registration, `eas.json` and a production app profile, an alert path | Claude Code (Srini approves each PR) | `python tools/railway/prod_config_check.py` exits 0 (section 7 then lists only the values set by hand) |
| The release is on `main`: a PR from `dev` to `main`, approved by Srini. Production deploys from `main` | Srini merges | `main` has the release commit; QA ran it for at least a day with no new errors |

Roll back: nothing to undo; production doesn't exist yet.

## The steps

### 1. Domain, DNS and TLS

- **Who:** Srini buys the domain and gives Claude Code DNS access (or makes the records himself). Claude Code lists
  the records.
- **How:** decide the names (for example `bhojango.com` and `www` for web, `admin.`, `api.` for core-api, `rt.` for
  realtime). Lower the TTL to 300 s for the launch weeks. The records themselves are added in step 5, once Railway
  shows its targets. Turn on registrar lock and two-factor sign-in at the registrar.
- **Verify:** `nslookup` of each name answers from the registrar's DNS.
- **Roll back:** nothing is pointing anywhere yet. Delete the records.

### 2. Production environment from `railway.ts`

- **Who:** Srini creates the environment `production` in the dashboard (project BhojanGo) and a project token for
  it, kept outside the repo. Claude Code runs the plan; Srini approves the apply.
- **How:** with `RAILWAY_TOKEN` = the production token, from the repo root: `railway config plan`. Expect 7
  services, 1 volume (10 GB), 1 bucket and 3 groups, all in production, with branch `main`. Then
  `railway config apply --yes`. Commit the bucket into the environment once (`environmentPatchCommit`, as in the
  runbook's step 4).
- **Verify:** a second plan is clean. The dashboard shows production with 7 services and QA unchanged. Services may
  fail to start until step 9: that's expected.
- **Roll back:** delete the production environment (it has no data yet). QA is a separate environment and is not
  affected.

### 3. Database, bucket and backups

- **Who:** Claude Code (Srini approves anything with a cost).
- **How:** Postgres is the PostGIS image on the `postgres-data` volume (no public port). Turn on volume backups for
  `postgres-data`: daily, keep 7, plus a manual backup before every release with migrations. The bucket `uploads`
  (region `sjc`, private) gets its credentials with `railway bucket credentials --bucket uploads --json`; they go
  into core-api in step 9 without being printed.
- **Hourly copies:** apply creates the `db-backups` bucket (private, `sjc`) and the `db-backup` cron service (hourly at
  :07, keeps 7 days). Put the bucket's credentials into the GitHub secrets `BACKUP_*` without printing them (as for
  QA in R23: `bucketS3Credentials` piped into `gh secret set`), so the weekly restore test in `restore-drill.yml`
  restores production's newest copy. RPO 1 hour.
- **Verify:** the dashboard shows the backup schedule. After the first hourly run, `latest.json` is in the bucket
  and a manual `restore-drill.yml` run with `source=bucket` passes (health checks, finance invariants, row counts).
- **Required: rehearse a Railway volume restore on production before launch, while it's still empty.** Railway
  restores a volume backup only over the live volume, so this can never be practised on QA, and after launch it
  would overwrite real orders. Do it after step 10 (migrations ran, no customers yet):
  1. take a manual volume backup of `postgres-data` and note the time;
  2. write a marker (for example a row in a scratch table) and record the table counts (`tools/backup/counts.sh`);
  3. restore the manual backup over the volume from the dashboard and redeploy core-api, worker and realtime;
  4. check the marker is gone, `alembic_version` and the counts match the backup, and `/health` is green;
  5. write the time from step 3 to green into [incident-plan.md](incident-plan.md) as production's measured RTO.
  If it fails or takes over 30 minutes, stop (stop condition 4).
- **Roll back:** before launch, delete and recreate the volume. After launch, never delete it: restore per
  [backup-restore.md](../runbooks/backup-restore.md) instead.

### 4. Railway domains

- **Who:** Claude Code.
- **How:** `railway domain` for core-api (port 8001), realtime (8004), web (3000) and admin (3000), before the first
  frontend build: web and admin bake the API addresses in at build time.
- **Verify:** each Railway domain answers (a 502 before step 10 is fine).
- **Roll back:** remove the domains.

### 5. Custom domains and TLS

- **Who:** Claude Code adds them in Railway (Settings → Networking); Srini (or Claude Code with DNS access) adds the
  CNAME and verification records.
- **How:** web on the apex and `www`, admin, api, rt. Railway issues the TLS certificates.
- **Verify:** `https://` on each name shows a valid certificate and HTTP redirects to HTTPS. HSTS is sent.
- **Roll back:** remove the custom domain in Railway and the DNS record. The Railway domains keep working.

### 6. Email (Amazon SES) and sign-in codes (Twilio Verify)

**Email through Amazon SES** (worker: `EMAIL_PROVIDER=ses`, [`SesEmail`](../../backend/shared/providers/email.py)).

- **Who:** Srini (AWS account, the IAM user); Claude Code lists and checks the DNS records.
- **How:**
  1. SES console in **us-west-2** (the `SES_REGION` in `railway.ts`; if another region is used, change it there):
     Identities → Create identity → **Domain** `<domain>`, with **Easy DKIM** (RSA 2048). SES shows three CNAME
     records (`<token>._domainkey.<domain>`): add them at the registrar.
  2. Custom MAIL FROM domain `mail.<domain>`: SES shows an MX record and an SPF TXT record
     (`v=spf1 include:amazonses.com ~all`); add both, so SPF aligns with the sender domain.
  3. DMARC: TXT `_dmarc.<domain>` = `v=DMARC1; p=none; rua=mailto:<a report address>`; move to `p=quarantine`
     after two clean weeks.
  4. **Request production access** (Account dashboard → "Request production access"): a new SES account is in the
     sandbox and can only send to verified addresses. Use case: transactional (sign-in codes, receipts, password
     resets), no marketing. AWS answers within about a day.
  5. IAM → Users → `bhojango-ses-production` with an inline policy allowing only `ses:SendEmail` (resource: the
     domain identity's ARN) → Security credentials → Create access key → paste the key id and secret straight into
     Railway (worker, sealed): `SES_ACCESS_KEY_ID`, `SES_SECRET_ACCESS_KEY`.
  6. Decide the sender: `EMAIL_FROM` (for example `orders@<domain>`, by hand in Railway, worker); the name is
     `EMAIL_FROM_NAME=BhojanGo` in `railway.ts`. Optional: a configuration set for bounces and complaints
     (`SES_CONFIGURATION_SET`).
- **Verify:** SES shows the domain "Verified" and DKIM "Successful"; the account is out of the sandbox. After step
  10, "Forgot password" on the website reaches a Gmail and an Outlook inbox (not spam) with DKIM, SPF and DMARC
  "pass" in the headers.
- **Roll back:** deactivate the access key; delete the identity and the records.

**Phone sign-in codes through Twilio Verify** (core-api: `OTP_PROVIDER=twilio_verify`,
[`twilio_verify.py`](../../backend/core_api/modules/identity/service/twilio_verify.py)). Verify makes, sends and
checks the code from Twilio's own numbers: no sender number and no A2P 10DLC or toll-free registration. Order
updates go by push, so production sends no other SMS (`SMS_PROVIDER=off`).

- **Who:** Srini (Twilio account); Claude Code checks.
- **How:** Twilio console → Verify → Services → Create: friendly name `BhojanGo` (shown in the SMS), code length 6,
  SMS channel on (others off). Geo permissions: allow the United States (and nothing else for now). Paste into
  Railway (core-api, sealed): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` (Account Info) and
  `TWILIO_VERIFY_SERVICE_SID` (the service's `VA...` SID).
- **Verify:** after step 10, the app's phone sign-in sends a code to a US phone within a minute and the code signs
  in; a wrong code is refused. Twilio's Verify logs show the attempt.
- **Roll back:** delete the service (sign-in by phone stops; email sign-in keeps working) or rotate the auth token.

### 7. Stripe live

Follow [the integration guide](../11_Integration_Setup_Guide.md) section 1, in live mode.

- **Who:** Srini (the account, bank, identity, tax registration). Claude Code configures what the API allows and
  checks it.
- **How:**
  1. Business details for DeepTrics LLC, bank account, statement descriptor `BHOJANGO`, support phone and email.
  2. Live API keys: a restricted key is better than the full secret key if all calls are covered; otherwise the
     secret key. The publishable key too.
  3. Three live webhook endpoints on the **api** custom domain:
     - payments: `/api/v1/payments/stripe/webhook`, the events in `stripe_svc.WEBHOOK_EVENTS`;
     - Connect (events on connected accounts): `/api/v1/finance/stripe/connect/webhook`;
     - your account: `/api/v1/finance/stripe/webhook` (`transfer.*`).
     Each signing secret goes to its own variable.
  4. Connect: platform profile done, Express responsibilities accepted, branding. 1099 delivery through Connect on
     (readiness item 12).
  5. Stripe Tax: head office address (DeepTrics LLC's real one, not QA's placeholder), default tax behaviour
     `exclusive`, an **Idaho registration** only after the Idaho seller's permit exists (readiness item 6).
  6. Payment methods: the code makes a payment method configuration named after the country's methods (US: card,
     Apple Pay, Google Pay) the first time it's needed. Register the web domain for Apple Pay and Google Pay in Stripe.
- **Verify:** the keys are live (`sk_live`/`pk_live` prefixes, checked by a script that prints only the prefix). Each
  endpoint shows "enabled". After step 10, Stripe's "send test webhook" reaches each endpoint with 200. Stripe Tax
  shows Idaho as "collecting".
- **Roll back:** disable the webhook endpoints, roll (revoke) the keys. Payments stop: pause ordering everywhere first
  (incident plan).

### 8. Push credentials

Order updates reach people by push only (no SMS in production), through Expo's push service: the worker sends Expo
push tokens (`PUSH_PROVIDER=live`) and needs no Firebase or APNs key of its own.

- **Who:** Srini (Firebase, Apple Developer, Expo accounts); Claude Code wires them.
- **How:** one EAS project per app (`com.bhojango.app`, `.partner`, `.rider`). Firebase project with the three
  Android packages: download `google-services.json` for the builds and an **FCM V1 service account key**, uploaded
  to EAS (`eas credentials` → Android → Google Service Account Key for push), not to Railway. Apple: an APNs auth key
  (.p8) for the team, uploaded to EAS for each app. Optional: Expo "enhanced push security" with an access token
  (`EXPO_ACCESS_TOKEN`, sealed, worker).
- **Verify:** EAS shows push credentials for Android and iOS on each app. After step 14, a test push from Expo's push
  tool reaches a phone with the production build, and an order status change arrives as a push.
- **Roll back:** revoke the keys in Firebase and Apple; delete them in EAS.

### 9. Sealed variables

- **Who:** Claude Code generates what we generate and seals it without printing; Srini pastes account secrets (or
  puts them in his secrets folder outside the repo for Claude Code's sealing script).
- **How:** every variable in [production-config.md](production-config.md) marked *by hand*, with production's own
  values:
  - generated, new for production: `POSTGRES_PASSWORD`, `JWT_PRIVATE_KEY`, `INTERNAL_SERVICE_SECRET` (the same on
    core-api, realtime and worker), `ALERT_WEBHOOK_TOKEN`, and `IDENTITY_DATA_KEYS`:
    `python tools/secrets/identity_data_keys.py` prints a new key list once, to the terminal only (it refuses to
    write into a file); paste it straight into Railway as a sealed variable on core-api and clear the terminal.
    Never save it: a copy goes only into Srini's password manager. core-api refuses to start without it;
  - from Railway: the bucket credentials;
  - addresses: `CORS_ORIGINS` (the web and admin custom domains), `NEXT_PUBLIC_APP_URL`, `PUBLIC_WEB_URL`,
    `PUBLIC_API_URL` (both `https://`; core-api refuses localhost or plain http), `EMAIL_FROM` (worker);
  - accounts ([the list](production-config.md#secrets-from-srinis-accounts)): the Stripe keys and three webhook
    secrets, Twilio's account SID, auth token and Verify service SID (core-api); the SES access key (worker);
    `SENTRY_DSN` (all three backends) and `NEXT_PUBLIC_SENTRY_DSN` (web, admin; a build variable).
  Seal each one (`environmentPatchCommit` with `isSealed: true`). Keep a copy of each generated secret in Srini's
  password manager, never in the repo, chat or logs.
- **Verify:** `python tools/railway/prod_config_check.py` exits 0, and every name in its section 7 has a value in
  the dashboard. Every secret shows as sealed. Nothing secret appears in `git diff`.
- **Roll back:** replace the value (rotate). For `JWT_PRIVATE_KEY`, put the old public key in `JWT_PUBLIC_KEYS`
  while sessions move over; for `IDENTITY_DATA_KEYS`, put the new key first and keep the old one after it.

### 10. First deploy and migrations

- **Who:** Claude Code; Srini watches.
- **How:** redeploy in order: postgres → core-api (its pre-deploy runs `alembic upgrade head` on the empty
  database) → realtime, worker → web, admin.
- **Verify:**
  - every service passes its health check (`/health/ready`; web `/`; admin `/login`);
  - `GET https://api.<domain>/health` reports environment `production`;
  - core-api's log shows the migration reached head; no `ProductionConfigError` (it names the variable: a public
    address, `IDENTITY_DATA_KEYS`, the Twilio Verify values); the worker's production check passed (SES keys,
    `EMAIL_FROM`, push live, SMS off);
  - Sentry: a deliberate test error from each service appears in its project (then resolve it);
  - web and admin show **no** test-site banner and web is indexable (`robots.txt`); admin is `noindex`;
  - CORS answers only the custom web and admin origins.
- **Roll back:** a failed migration stops the deploy and nothing serves; fix forward. Before launch, the database
  can be dropped and recreated. After launch, redeploy the previous build from the Deployments tab (migrations stay:
  they are written so the previous release still runs).

### 11. Base data without demo data

- **Who:** Claude Code. The seed lives in `tools/`, outside the core-api image, so it runs from a checkout of
  `main` over a database tunnel (`railway connect postgres --tunnel-only` with the production token), or from a
  temporary runner in the environment, deleted afterwards.
- **How:** the markets-only seed, [`tools/seed/markets.py`](../../tools/seed/markets.py), with production's
  settings in the environment (`APP_ENV=production`, `PAYMENT_PROVIDER=live`, `PAYOUT_PROVIDER=live`,
  `OTP_FIXED_CODE=`, `DELIVERY_PIN_FIXED=`, `DATABASE_URL` = the tunnel):

  ```
  cd backend && uv run python ../tools/seed/markets.py
  ```

  It adds: US (DeepTrics LLC) and India (DeepTrics Software Solutions Pvt Ltd, **draft**: kept, switched off), their
  states and cities with **Boise live** and Hyderabad draft, the zones, the market rules (15% commission in the US,
  India's tax rules from round 16, payment fees, delivery fees, pay for delivery partners, refund limits; no
  promotions, no kitchen's rules), the help articles, and Terms and Privacy as **unpublished drafts** for the
  lawyer's text. No users, kitchens, menus, orders or payout accounts. It only adds what's missing (running it again
  changes nothing an admin edited). **Never** `seed.py` or `demo.py`: both refuse production.
- **Verify:** its last line: 2 countries; open cities: 1 (US-ID-BOI); **0** `@example.com` users, **0** restaurants,
  **0** fake payout accounts. The website shows Boise with no kitchens yet.
- **Roll back:** before launch, drop and recreate the schema and run it again.

### 12. Admin accounts and two-step sign-in

- **Who:** Claude Code runs the first-admin command for Srini's own email (super admin). Srini signs in and grants
  the other roles in admin.
- **How:** inside core-api (`railway ssh` into core-api with Srini's login; the command is in the image) or over the
  database tunnel of step 11:

  ```
  python -m core_api.modules.identity.first_admin --email <Srini's email> --name "<full name>"
  ```

  It refuses when any super admin exists, and prints nothing secret: the account has no password yet. Srini opens
  the website's "Forgot password" with that email (the link comes through SES, good for 30 minutes, once), sets the
  password, then signs in to the admin console, which enrols the authenticator at first sign-in: an email code,
  the QR code, and 10 recovery codes shown once (store them offline). Then grant, with real people's emails:
  country manager US, Boise city ops, Boise support, US finance. A second finance or country manager is needed for
  refunds above the limit (two-person approval).
- **Verify:** each admin signs in with password and authenticator. The role list in admin shows exactly these
  people. No `@example.com` account exists.
- **Roll back:** revoke a role in admin; delete the account if made by mistake.

### 13. Markets: Boise live

- **Who:** Srini decides; a US country manager makes the changes in admin (a second admin approves rule versions).
  Claude Code checks them with the price simulator.
- **How:**
  - United States: payment provider Stripe, payout provider `stripe_connect`, payment methods card, Apple Pay,
    Google Pay; legal entity DeepTrics LLC with its registered address, support email and phone.
  - Terms and Privacy: the seed left drafts (Content → Legal); paste the lawyer's versions over them and publish
    for the US (no "Draft" banner).
  - Rules: commission 15% (all tiers), weekly payouts, delivery fees, minimum order, minimum pay for delivery
    partners in Boise, unpaid-order timeout, automatic refund limit, tax on commission 0% in the US.
  - Boise: `live` from the seed; set zones back to `draft` where no kitchens and partners exist yet.
  - India: kept, switched off (`draft`) by the seed; it stays that way.
- **Verify:** the simulator, for a Boise address and a sample cart: the customer total, Idaho sales tax line,
  15% commission, the partner's pay and "who gets your money" all as expected. The website shows Boise as open.
- **Roll back:** set Boise back to `beta` or pause ordering in Boise (Incidents). Rule versions: end the new version;
  the previous one applies again.

### 14. App store builds with the production environment

- **Who:** Claude Code builds and submits (EAS); Srini owns the store accounts, listings and review answers (see
  [store/README.md](store/README.md)).
- **How:** the production profile in each app's `eas.json`: `EXPO_PUBLIC_APP_ENV=production`,
  `EXPO_PUBLIC_CORE_URL=https://api.<domain>`, `EXPO_PUBLIC_REALTIME_URL=https://rt.<domain>`,
  `EXPO_PUBLIC_WEB_URL=https://<domain>`, `EXPO_PUBLIC_SENTRY_DSN` (the app's Sentry project); the real EAS
  project ids; `google-services.json`; EAS-managed signing.
  Submit to TestFlight and the Play internal track first.
- **Verify:** an internal tester installs each app: no test banner; the sign-in code (Twilio Verify) arrives; the customer sees
  Boise; a push from Expo's tool arrives; the customer's payment sheet opens in live mode (don't pay yet).
- **Store review (reviewer accounts and their orders):** once, run `python tools/review_accounts.py --email-domain
  <domain>` in the core-api service's shell and put the printed passwords into App Store Connect, Play Console and the
  password manager ([store/README.md](store/README.md#reviewer-access)). Before submitting a build for review, turn the
  review simulator on: in [`.railway/railway.ts`](../../.railway/railway.ts) set the production worker's `REVIEW_SIM`
  to `"1"` and apply. Reviewers' orders in the hidden review city then cost $0.00 (no card charged, Stripe never
  called) and are taken to delivered in about six minutes by the review kitchen and delivery partner; nothing else is
  touched. **Verify:** on a production build, sign in as the review customer, place an order: the bag says "You pay
  $0.00" and "Place order", the order screen goes placed, accepted, preparing, ready, picked up, delivered; the
  worker log shows `review_sim` `on` and `review_order_step` lines. **After approval:** set `REVIEW_SIM` back to `"0"`
  and apply (on again for each new submission: every app update is reviewed). `DEMO_RIDER_SIM` stays unset; production
  refuses to start with it.
- **Roll back:** stop the rollout or remove the build from the track; the previous build stays. Store review can take
  days: start this early. `REVIEW_SIM` back to `"0"` stops the review simulator (review orders then wait and are
  cancelled by the accept timeout).

### 15. Real kitchens and delivery partners

- **Who:** Srini recruits and approves; Claude Code supports onboarding and checks the data.
- **How:**
  - Kitchens: sign-up, documents and licences, menu and photos, hours, a tablet with the Kitchen app, Stripe Express
    onboarding finished by the owner.
  - Delivery partners: sign-up with licence and insurance, the background check (readiness item 10), Stripe Express
    onboarding, the Delivery app on their phone.
  - Enough of both for the first dinner hours in the live zones (Srini sets the number).
- **Verify:** in admin each kitchen is approved with "payouts enabled"; each partner is approved with "payouts
  enabled"; the dispatch map shows partners online during a test hour.
- **Roll back:** pause a kitchen or suspend a partner in admin.

### 16. Monitoring and alerts

- **Who:** Srini (Sentry, a paging channel); Claude Code wires them.
- **How:** Sentry (free plan): a backend project (`SENTRY_DSN` on core-api, realtime, worker), a Next.js project
  for web and admin (`NEXT_PUBLIC_SENTRY_DSN`, a build variable: redeploy after setting it) and a React Native
  project for the apps (`EXPO_PUBLIC_SENTRY_DSN` in the build profile). Without a DSN nothing is initialised and
  nothing is sent. Alert rules in Sentry: a new issue, and a spike. Uptime checks (free tier of an
  uptime service) on the website, `api.../health/ready`, `rt.../health/ready` and admin `/login`. The alerts from
  [observe.md](../runbooks/observe.md) (orders without a rider, payment failures, error spikes, no orders in a dinner
  hour) on the path Srini chose. Stripe's own email alerts for failed webhooks. Railway usage alerts on the workspace.
- **Verify:** a deliberate test error appears in Sentry; stopping the uptime target (or a wrong URL) pages Srini's
  phone; the incident plan's phone numbers are filled in.
- **Roll back:** turn off a noisy alert; nothing in the app depends on it.

### 17. Launch rehearsal: internal orders and refunds

- **Who:** Srini and a few internal people with real cards; partner kitchens and delivery partners who agreed to
  take part; Claude Code watches the logs and the money.
- **How:** a dinner-rush hour with only internal customers (Boise not announced). Each kitchen gets at least one
  order; each partner delivers at least one. Cover: card, Apple Pay, Google Pay; web and app; a cancellation; a
  refund by item; a full refund; a bulk refund of a small set (with the second-admin approval above the limit); a
  kitchen pause and resume; an ordering pause in Boise with the customer note; a customer message to the test
  group. Card fees on these orders are not returned on refunds (about $20 in all).
- **Verify:**
  - every order reached "delivered" or was refunded; Stripe and admin Finance agree, order by order;
  - Stripe Tax recorded tax transactions and reversed them on refunds;
  - SMS codes, emails (receipts, codes) and pushes arrived;
  - the tracking map moved; the delivery PIN was random;
  - Sentry has no new errors; the uptime checks stayed green;
  - after the week ends, the payout run drafts kitchens' and partners' pay correctly (15% commission).
- **Roll back:** refund everything from the rehearsal; pause Boise until the problem is fixed.

### 18. First real order

- **Who:** Srini decides the moment and announces; Claude Code watches.
- **How:** open the live zones in Boise at the start of a staffed dinner hour, with kitchens and partners on shift
  and the incident roles on call.
- **Verify:** the first order is paid, accepted, cooked, picked up, delivered, receipted, and visible in Finance.
- **Roll back:** pause ordering in Boise (Incidents), with a note for customers; refund anything stuck.

### 19. Watch

- **Who:** Srini (business), Claude Code (systems).
- **How:** for the first two weeks, after every dinner hour: orders placed vs delivered, time to accept, time to
  deliver, payment failures, refunds, Sentry errors, webhook failures in Stripe, the dead-letter stream
  (`bhojango:events:dlq`), Railway usage. The first Monday: the payout run, then Stripe transfers marked paid.
- **Verify:** a short daily note in the launch log.
- **Roll back:** the incident plan.

## Stop conditions

Abort or delay the launch (and pause ordering if it's already open) when any of these is true:

1. `prod_config_check.py` reports a gap, or any service starts with `APP_ENV` other than `production`.
2. Any fake or test value in production: the fake payment provider, a fixed OTP or delivery PIN, the demo rider, a
   `pk_test`/`sk_test` key, a test-site banner, `@example.com` users, seed kitchens or `fake` payout accounts.
3. A plan or apply would change or delete anything in QA, or anything outside production.
4. A migration fails, or the restore drill or the volume restore rehearsal (step 3) fails or hasn't been done.
5. Stripe isn't fully live: account not activated, payouts to the bank not enabled, a webhook endpoint failing, or
   Stripe Tax not collecting in Idaho while orders would be taxed.
6. Idaho seller's permit, lawyer-reviewed Terms and Privacy, or insurance (general liability and delivery auto cover)
   missing.
7. Sign-in codes (Twilio Verify or email through SES) don't arrive within a minute in the rehearsal, emails land
   in spam, or SES is still in the sandbox.
8. In the rehearsal: any order paid but not placed, any refund not reaching the card, Finance not matching Stripe,
   tax not recorded, or a payout draft that's wrong.
9. Fewer kitchens or delivery partners with payouts enabled than Srini's minimum for a dinner hour.
10. No working alert to Srini's phone, or the incident plan's names and numbers are still blank.
11. A security finding rated high (secret in the repo or logs, CORS open, admin without two-step sign-in).
12. Srini or the on-call engineer is not available for the first three dinner hours.

When one fires during the launch: follow the [incident plan](incident-plan.md) (first 15 minutes: say it, pause,
look, tell, fix or roll back, refund, write up).
