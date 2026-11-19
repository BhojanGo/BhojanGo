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
| Accounts open: domain, Stripe live (activated for DeepTrics LLC), SendGrid, Twilio (US number registered for 10DLC or toll-free), Firebase, Apple Developer, Google Play, Expo, Sentry (optional) | Srini | Each account signs in; Stripe shows "live mode" activated |
| Readiness items 6, 7, 10, 11 done or dated: Idaho permit, lawyer-reviewed Terms and Privacy, background-check vendor, insurance | Srini | [boise-readiness.md](boise-readiness.md) updated |
| The code gaps from [production-config.md](production-config.md#gaps) are fixed, merged to `dev`, and pass `make ci` and the GitHub checks: production variables in `railway.ts` (Stripe, worker providers, `PUBLIC_*`, `IDENTITY_DATA_KEYS`, `NEXT_PUBLIC_PAYMENTS_PROVIDER`; fake payment settings QA only), a markets-only seed, a first-admin script, push token registration, `eas.json` and a production app profile, `sentry-sdk`, an alert path | Claude Code (Srini approves each PR) | `python tools/railway/prod_config_check.py` exits 0 |
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
- **Verify:** the dashboard shows the backup schedule. After step 10, do the restore drill once: restore the newest
  backup into a temporary service, check `alembic_version` and the table counts (`tools/backup/counts.sh`), then
  delete it.
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

### 6. Email sender DNS

- **Who:** Srini (SendGrid account); Claude Code lists and checks the records.
- **How:** SendGrid → Sender Authentication → authenticate the domain (its CNAMEs for DKIM and the return path).
  Add SPF if SendGrid asks, and DMARC (`_dmarc`, start with `p=none` and a report address, move to `quarantine` after
  two clean weeks). Create a restricted API key (Mail Send only). Decide the sender (`SENDGRID_FROM_EMAIL`, for
  example `orders@<domain>`) and name.
- **Verify:** SendGrid shows the domain as verified. A test email from SendGrid's own page lands in the inbox, not
  spam, at Gmail and Outlook, with DKIM and SPF "pass" in the headers.
- **Roll back:** delete the API key; remove the records.

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

- **Who:** Srini (Firebase, Apple Developer, Expo accounts); Claude Code wires them.
- **How:** Firebase project with the three Android packages (`com.bhojango.app`, `.partner`, `.rider`): download
  `google-services.json` for the builds and a service account key for the worker. Apple: an APNs auth key (.p8) for
  the team. Expo: one EAS project per app; upload the FCM V1 key and the APNs key as EAS credentials. Optional: an Expo
  access token with enhanced push security on.
- **Verify:** EAS shows push credentials for Android and iOS on each app. After step 14, a test push from Expo's push
  tool reaches a phone with the production build.
- **Roll back:** revoke the keys in Firebase and Apple; delete them in EAS.

### 9. Sealed variables

- **Who:** Claude Code generates what we generate and seals it without printing; Srini pastes account secrets (or
  puts them in his secrets folder outside the repo for Claude Code's sealing script).
- **How:** every variable in [production-config.md](production-config.md) marked *by hand*, with production's own
  values:
  - generated, new for production: `POSTGRES_PASSWORD`, `JWT_PRIVATE_KEY`, `INTERNAL_SERVICE_SECRET` (the same on
    core-api, realtime and worker), `IDENTITY_DATA_KEYS`, `ALERT_WEBHOOK_TOKEN`;
  - from Railway: the bucket credentials;
  - addresses: `CORS_ORIGINS` (the web and admin custom domains), `NEXT_PUBLIC_APP_URL`, `PUBLIC_WEB_URL`,
    `PUBLIC_API_URL`;
  - accounts: the Stripe keys and three webhook secrets (core-api); SendGrid, Twilio and Firebase (worker); Sentry
    (all three, if used).
  Seal each one (`environmentPatchCommit` with `isSealed: true`). Keep a copy of each generated secret in Srini's
  password manager, never in the repo, chat or logs.
- **Verify:** `python tools/railway/prod_config_check.py` exits 0. In the dashboard every secret shows as sealed.
  Nothing secret appears in `git diff`.
- **Roll back:** replace the value (rotate). For `JWT_PRIVATE_KEY`, put the old public key in `JWT_PUBLIC_KEYS`
  while sessions move over; for `IDENTITY_DATA_KEYS`, put the new key first and keep the old one after it.

### 10. First deploy and migrations

- **Who:** Claude Code; Srini watches.
- **How:** redeploy in order: postgres → core-api (its pre-deploy runs `alembic upgrade head` on the empty
  database) → realtime, worker → web, admin.
- **Verify:**
  - every service passes its health check (`/health/ready`; web `/`; admin `/login`);
  - `GET https://api.<domain>/health` reports environment `production`;
  - core-api's log shows the migration reached head; no `ProductionConfigError`; the worker's production check
    passed;
  - web and admin show **no** test-site banner and web is indexable (`robots.txt`); admin is `noindex`;
  - CORS answers only the custom web and admin origins.
- **Roll back:** a failed migration stops the deploy and nothing serves; fix forward. Before launch, the database
  can be dropped and recreated. After launch, redeploy the previous build from the Deployments tab (migrations stay:
  they are written so the previous release still runs).

### 11. Base data without demo data

- **Who:** Claude Code runs it from inside the private network (a temporary runner, as on QA, deleted afterwards).
- **How:** the markets-only seed (one of the code gaps): US, Idaho, Boise, its zones, the rule templates and
  published rules, the help articles. No users, kitchens, menus, orders or payout accounts. **Never** `demo.py` (it
  refuses production anyway) and never the full `seed.py`.
- **Verify:** counts: 1 country, Boise only, its zones, rules, help articles; **0** users with `@example.com`,
  **0** restaurants, **0** payout accounts with provider `fake`. The website shows Boise with no kitchens yet.
- **Roll back:** before launch, drop and recreate the schema and run it again.

### 12. Admin accounts and two-step sign-in

- **Who:** Claude Code runs the first-admin script for Srini's own email (super admin). Srini signs in and grants
  the other roles in admin.
- **How:** Srini sets the password from the email link, then enrols the authenticator at first sign-in: an email
  code, the QR code, and 10 recovery codes shown once (store them offline). Then grant, with real people's emails:
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
  - Terms and Privacy: the lawyer's versions published for the US (no "Draft" banner).
  - Rules: commission 15% (all tiers), weekly payouts, delivery fees, minimum order, minimum pay for delivery
    partners in Boise, unpaid-order timeout, automatic refund limit, tax on commission 0% in the US.
  - Boise: status `live`; zones `live` only where kitchens and partners exist.
  - India: not live in production.
- **Verify:** the simulator, for a Boise address and a sample cart: the customer total, Idaho sales tax line,
  15% commission, the partner's pay and "who gets your money" all as expected. The website shows Boise as open.
- **Roll back:** set Boise back to `beta` or pause ordering in Boise (Incidents). Rule versions: end the new version;
  the previous one applies again.

### 14. App store builds with the production environment

- **Who:** Claude Code builds and submits (EAS); Srini owns the store accounts, listings and review answers (see
  [store/README.md](store/README.md)).
- **How:** the production profile in each app's `eas.json`: `EXPO_PUBLIC_APP_ENV=production`,
  `EXPO_PUBLIC_CORE_URL=https://api.<domain>`, `EXPO_PUBLIC_REALTIME_URL=https://rt.<domain>`,
  `EXPO_PUBLIC_WEB_URL=https://<domain>`; the real EAS project ids; `google-services.json`; EAS-managed signing.
  Submit to TestFlight and the Play internal track first.
- **Verify:** an internal tester installs each app: no test banner; sign-in by SMS code arrives; the customer sees
  Boise; a push from Expo's tool arrives; the customer's payment sheet opens in live mode (don't pay yet).
- **Roll back:** stop the rollout or remove the build from the track; the previous build stays. Store review can take
  days: start this early.

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
- **How:** Sentry projects for the backends (and web if added), `SENTRY_DSN` set. Uptime checks (free tier of an
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
4. A migration fails, or the restore drill (step 3) fails.
5. Stripe isn't fully live: account not activated, payouts to the bank not enabled, a webhook endpoint failing, or
   Stripe Tax not collecting in Idaho while orders would be taxed.
6. Idaho seller's permit, lawyer-reviewed Terms and Privacy, or insurance (general liability and delivery auto cover)
   missing.
7. Sign-in codes (SMS or email) don't arrive within a minute in the rehearsal, or emails land in spam.
8. In the rehearsal: any order paid but not placed, any refund not reaching the card, Finance not matching Stripe,
   tax not recorded, or a payout draft that's wrong.
9. Fewer kitchens or delivery partners with payouts enabled than Srini's minimum for a dinner hour.
10. No working alert to Srini's phone, or the incident plan's names and numbers are still blank.
11. A security finding rated high (secret in the repo or logs, CORS open, admin without two-step sign-in).
12. Srini or the on-call engineer is not available for the first three dinner hours.

When one fires during the launch: follow the [incident plan](incident-plan.md) (first 15 minutes: say it, pause,
look, tell, fix or roll back, refund, write up).
