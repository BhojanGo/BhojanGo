# Production configuration (dry run, 2026-11-19; updated in round 19)

Every variable and secret production needs, per service. Nothing here was created, bought or deployed.
Production does not exist yet. No value is written here: only names, where each comes from, and what kind of
value QA has.

Round 19 applied Srini's decisions: production is **Boise (US) only** (India's markets are kept, switched off);
email through **Amazon SES**; phone sign-in codes through **Twilio Verify** (no sender number, no A2P 10DLC);
order updates by **push**, not SMS; **Sentry** (free plan) now; a **markets-only seed**. `railway.ts` now defines
every variable the code needs for production. What is left is values set once in Railway by hand, 12 of them from
Srini's accounts ([the list](#secrets-from-srinis-accounts)), and the app store build inputs.

How this list was made:

- the backend settings in [`backend/shared/config.py`](../../backend/shared/config.py) (one Settings class, every
  field is an environment variable of the same name) and its production checks: `refuse_fakes_in_production`
  (every service) and `core_api_production_problems` (core-api: the public https addresses, `IDENTITY_DATA_KEYS`, a
  way to send sign-in codes);
- the worker's start-up check ([`worker/app/main.py`](../../backend/worker/app/main.py) `production_missing`), the
  providers, internal auth, two-step secrets, payments;
- `process.env` reads in web and admin, `EXPO_PUBLIC_*` reads in the apps, and
  [`infra/docker/next-app.Dockerfile`](../../infra/docker/next-app.Dockerfile);
- [`.railway/railway.ts`](../../.railway/railway.ts), read as the production environment.

The checker [`tools/railway/prod_config_check.py`](../../tools/railway/prod_config_check.py) does the comparison.
It reads the repository only: no network, no Railway CLI, names only. Run it after any change to `railway.ts` or
`config.py`:

```
python tools/railway/prod_config_check.py      # exit 1 while there are gaps
```

The go-live steps are in [go-live.md](go-live.md).

## How to read the tables

- **Required:** *yes* = production refuses to start, or a launch feature breaks, without it. *Opt* = a feature
  stays off without it. *No* = leave unset.
- **From:** the account that issues it (Srini opens the account), *generated* (Claude Code makes it once, for
  production only), *Railway* (a reference Railway fills in), or *railway.ts* (a plain value in the config).
- **Sealed:** set as a Railway sealed variable. A sealed value can't be read back by anyone.
- **QA:** what kind of value QA has. Never the value.
- **railway.ts (production):** *supplied* = the config sets it; *by hand* = the config has `preserve()`, so the value
  is set once in Railway, outside the file; **missing** = the config doesn't define it for production.

## Accounts Srini needs

| Account | For | Cost note |
|---|---|---|
| Domain registrar and DNS | website, admin, API and realtime names; SES domain records (DKIM, SPF, DMARC) | readiness item 2 |
| Stripe, live mode (DeepTrics LLC) | payments, Connect payouts, Stripe Tax | per use |
| AWS (Amazon SES) | email: codes, receipts, password reset (an IAM user allowed `ses:SendEmail` only) | per email; out of the SES sandbox first |
| Twilio (Verify) | phone sign-in codes; Verify sends from Twilio's own numbers, so no 10DLC or toll-free registration | per verification |
| Expo (EAS) | store builds and push for the three apps (order updates go by push) | free tier first |
| Firebase project (Google) | the FCM V1 key that Expo push on Android needs (uploaded to EAS, not to Railway) | free |
| Apple Developer (DeepTrics LLC) | iOS builds, APNs key (uploaded to EAS), Apple Pay merchant id | $99 a year |
| Google Play Console (DeepTrics LLC) | Android builds | $25 once |
| Sentry | error tracking for the backends, website, admin and apps | free plan |
| Google Cloud OAuth client | Sign in with Google (optional) | free |
| Railway | already exists (workspace "Srinivas's Projects") | usage |

No longer needed for Boise: SendGrid (SES instead), a Twilio sender number with A2P 10DLC (Verify instead), and a
Firebase service account on the worker (the apps use Expo push tokens).

## Production domains (plan; nothing changed for production)

Srini owns `bhojango.com` at GoDaddy. QA already runs on it (`qa`, `admin.qa`, `api.qa`, `rt.qa`, 2026-11-19), so the
mechanics are proven: Railway custom domain per service, a CNAME plus a `_railway-verify` TXT record per name,
Let's Encrypt certificates issued by Railway (no CAA record on the domain, so nothing to add for that).

| Name | Service | Record |
|---|---|---|
| `bhojango.com` | web | the website's canonical address (`NEXT_PUBLIC_APP_URL`, `PUBLIC_WEB_URL`) |
| `www.bhojango.com` | web | redirects to `bhojango.com` (or a second custom domain on web) |
| `admin.bhojango.com` | admin | CNAME to Railway |
| `api.bhojango.com` | core-api | CNAME to Railway (`PUBLIC_API_URL`, Stripe live webhooks) |
| `rt.bhojango.com` | realtime | CNAME to Railway |

**The bare domain.** Railway serves a custom domain through a CNAME, and DNS doesn't allow a CNAME at the bare
domain. GoDaddy has no CNAME flattening (ALIAS), so `bhojango.com` itself can't point at Railway while DNS stays at
GoDaddy. Two options:

1. **GoDaddy forwarding:** forward `bhojango.com` to `https://www.bhojango.com` (301) and make `www` the website.
   Free and nothing moves, but the canonical address becomes `www.bhojango.com`, the forward is GoDaddy's service
   (its https handling and uptime are outside our control), and every link we've written as `bhojango.com` redirects.
2. **Cloudflare's free plan for DNS only:** move the nameservers to Cloudflare (GoDaddy stays the registrar), which
   flattens a CNAME at the bare domain, so `bhojango.com` points at Railway directly and Railway issues its
   certificate. Records stay **DNS only** (grey cloud, no Cloudflare proxy) so Railway's certificates and websockets
   work unchanged. Free, faster DNS, DNSSEC available.

**Recommendation: option 2, Cloudflare DNS only.** The bare domain is the address on the website, emails, receipts and
the store listings; it should be served by us over https with our certificate, not by a registrar's forwarding service.
How: add `bhojango.com` to Cloudflare, check that it imported every existing record (the eight QA records, and any MX,
SES DKIM, SPF and DMARC records by then), lower nothing else, then change the two nameservers at GoDaddy. QA keeps
working through the switch as long as its records were copied first. Then add the production custom domains in
Railway and their records in Cloudflare (CNAME at the bare domain, flattened).

Note (found on QA): once a service has a custom domain, Railway's `RAILWAY_PUBLIC_DOMAIN` reference resolves to the
custom domain, not the `*.up.railway.app` one. So production's `NEXT_PUBLIC_CORE_URL` / `NEXT_PUBLIC_REALTIME_URL`
references will give `api.bhojango.com` / `rt.bhojango.com` once those domains are added; set the custom domains
before the first production frontend build.

## All three backends (core-api, realtime, worker)

`backendEnv` in `railway.ts` gives these to all three.

| Variable | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|
| `APP_ENV` | yes (`production`) | railway.ts | no | `qa` | supplied |
| `DATABASE_URL` | yes (core-api, worker; realtime doesn't use it) | Railway reference to the postgres password | the password is sealed | reference | supplied |
| `REDIS_URL` | yes | Railway reference (`/0` core-api and worker, `/3` realtime) | no | reference | supplied |
| `EVENT_BUS`, `EVENT_BUS_REDIS_URL` | yes (`redis`, `/5`) | railway.ts / Railway reference | no | same | supplied |
| `INTERNAL_SERVICE_SECRET` | yes, the same on all three | generated (32 random bytes, hex) | yes | sealed, QA's own | by hand |
| `CORE_API_URL`, `JWKS_URL` | yes (realtime, worker) | railway.ts (private network) | no | internal URL | supplied |
| `CORS_ORIGINS` | yes (core-api, realtime) | the custom web and admin domains, as a JSON list. Since R22 it is also the CSRF list: a change made with a session cookie must come from one of these origins, so the admin domain must be in it | no (not secret) | Railway references to the web and admin domains | by hand |
| `PHOTO_HOSTS` | only if dish, cover or logo photos are served from a CDN host (R22, S13) | a JSON list of https hosts, e.g. `["photos.bhojango.com"]`; our own API (`PUBLIC_API_URL`) and `AWS_CLOUDFRONT_URL` are always accepted | no | unset | by hand |
| `CLIENT_IP_HEADER` | yes (`X-Real-IP`) | railway.ts | no | same | supplied |
| `LOG_FORMAT` | no (json is the production default) | railway.ts | no | `json` | supplied |
| `PAYMENT_PROVIDER` | yes, must be `live` | railway.ts | no | `fake` in railway.ts; QA's core-api has `auto` set by hand (round 10) | supplied |
| `PAYOUT_PROVIDER` | yes, not `fake` | railway.ts | no | as above | supplied (`live`) |
| `EMAIL_PROVIDER` | yes (worker), `ses` | railway.ts | no | `log` | supplied (`ses`) |
| `SMS_PROVIDER` | yes (worker), `off` (no SMS: order updates by push, codes by Verify) or `live` | railway.ts | no | `log` | supplied (`off`) |
| `PUSH_PROVIDER` | yes (worker), `live` (Expo push) | railway.ts | no | `log` | supplied |
| `OTP_FIXED_CODE` | yes, must be `""` | railway.ts | no | default fixed code for seed phones | supplied (`""`) |
| `ROUTING_PROVIDER` | yes (`straight_line`) | railway.ts | no | same | supplied |
| `SERVICE_NAME`, `PORT` | yes | railway.ts | no | same | supplied |
| `RAILWAY_ENVIRONMENT_NAME` | automatic | Railway | no | `QA` | automatic (also checked by the production guard) |
| `SENTRY_DSN` | yes (Srini's decision; errors only, off when unset) | Sentry, one backend project | yes | not set | by hand (`sentry-sdk` is a dependency since R19) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | opt | a tracing vendor | no | not set | not defined |

## core-api

core-api refuses to start in production (`ProductionConfigError`, naming the variable) when `PUBLIC_WEB_URL` or
`PUBLIC_API_URL` is missing, not `https://`, or points at localhost, 127.0.0.1 or the private network; when
`IDENTITY_DATA_KEYS` is empty; or when no path sends sign-in codes (`OTP_PROVIDER=twilio_verify` without its three
Twilio values, or local codes with SMS off).

| Variable | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|
| `JWT_PRIVATE_KEY` | yes | generated (RSA 2048 PEM, new for production) | yes | sealed, QA's own key | by hand |
| `JWKS_URL` | yes, `""` (core-api signs) | railway.ts | no | `""` | supplied |
| `IDENTITY_DATA_KEYS` | yes (start-up check; admins' two-step secrets) | generated: `python tools/secrets/identity_data_keys.py` | yes | not in railway.ts | by hand |
| `PUBLIC_WEB_URL` | yes (start-up check; password-reset links, Stripe return URL) | `https://<domain>` | no | set by hand (web's Railway domain) | by hand |
| `PUBLIC_API_URL` | yes (start-up check; Stripe payout onboarding links) | `https://api.<domain>` | no | set by hand (round 10) | by hand |
| `OTP_PROVIDER` | yes, `twilio_verify` | railway.ts | no | default `local` | supplied |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | yes (Verify) | Twilio | yes | not set | by hand |
| `TWILIO_VERIFY_SERVICE_SID` | yes (Verify) | Twilio Verify service (`VA...`) | yes | not set | by hand |
| `STRIPE_SECRET_KEY` | yes | Stripe live | yes | Stripe test-mode key, sealed, set by hand | by hand |
| `STRIPE_PUBLISHABLE_KEY` | yes (handed to web and app checkouts by the API) | Stripe live | yes (not secret, kept with the rest) | test-mode key, set by hand | by hand |
| `STRIPE_WEBHOOK_SECRET` | yes (payments endpoint) | Stripe live webhook | yes | test-mode signing secret, by hand | by hand |
| `STRIPE_CONNECT_WEBHOOK_SECRET` | yes (Connect endpoint) | Stripe live webhook | yes | by hand | by hand |
| `STRIPE_PAYOUTS_WEBHOOK_SECRET` | yes (transfers endpoint) | Stripe live webhook | yes | by hand | by hand |
| `TAX_PROVIDER` | yes, `stripe_tax` | railway.ts | no | `auto`, by hand | supplied |
| `STORAGE_PROVIDER` | yes (`s3`) | railway.ts | no | `s3` | supplied |
| `UPLOADS_BUCKET`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `S3_ADDRESSING_STYLE` | yes | Railway bucket credentials (production's own bucket) | no | QA bucket's | by hand |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | yes (the bucket; not SES) | Railway bucket credentials | yes | sealed, QA's own | by hand |
| `ALERT_WEBHOOK_TOKEN` | yes once alerts post to core-api | generated | yes | sealed | by hand |
| `GEOIP` | no (build arg: the free DB-IP file) | railway.ts | no | `1` | supplied |
| `GOOGLE_WEB_CLIENT_ID` | opt (website's Google button; hidden without it) | Google Cloud OAuth client | no | not set | not defined |
| `APPLE_CLIENT_ID`, `APPLE_CLIENT_IDS` (+ team, key) | opt (Sign in with Apple) | Apple Developer | key: yes | not set | not defined |
| `FAKE_PAYMENT_*` | **no** (the fake gateway only) | — | — | set | not defined for production (QA and staging only since R19) |
| `RAZORPAY_*` | no for Boise (India) | Razorpay | yes | not set | not defined |

### core-api processes and the database (R22)

Production runs **2 core-api replicas** (`replicas: 2` in `railway.ts`), so a deploy or a crashed container never
takes the API down. Each replica starts with [`core_api/start.sh`](../../backend/core_api/start.sh) (the image's
command, and Railway's start command): one uvicorn process per CPU the container may use, read from its cgroup
limit (`/sys/fs/cgroup/cpu.max`, not the host's core count), at most `WEB_CONCURRENCY_MAX`.
`WEB_CONCURRENCY` overrides the count. QA (capped at 1 vCPU) gets 1 process; staging runs 1 replica.

| Variable (core-api) | Value | Why |
|---|---|---|
| `WEB_CONCURRENCY_MAX` | `2` | a Railway container may use many vCPUs; 2 processes per replica cover 3x launch with room (load-test.md, R22) |
| `DB_POOL_SIZE` | `8` | per process |
| `DB_MAX_OVERFLOW` | `4` | per process: 12 connections at most |

Postgres allows 100 connections (`max_connections`; 3 are kept for superusers). The worst case:

```
core-api   2 replicas x 2 processes x (8 + 4)       = 48
worker     1 process  x (5 + 20, the default overflow) = 25
pre-deploy migration, a psql or backup tunnel       ~  3
                                              total = 76 of 97
```

realtime has no database pool. Since R22 a request no longer holds a connection while it queues for the CPU
for long, and the load test's peaks are in [load-test.md](load-test.md).

Not changed by this: each uvicorn process has its own Prometheus counters, so `/metrics` answers for the process
that took the scrape. Nothing scrapes production's `/metrics` today (Grafana is the local `make observe` stack).

The monthly cost of this setup, from the load test's measured CPU and memory: [load-test.md, "What production
costs on Railway"](load-test.md#what-production-costs-on-railway-r22).

## realtime

Only the shared variables above, with `REDIS_URL` on database 3. No provider keys.

## worker

With the Redis event bus the worker sends every email and push (core-api only queues them). It refuses to start in
production unless `EMAIL_PROVIDER` is `ses` (or `sendgrid`), `PUSH_PROVIDER` is `live` and `SMS_PROVIDER` is `off`
(or `live`), and the chosen providers' keys are set: for SES `SES_REGION`, `SES_ACCESS_KEY_ID`,
`SES_SECRET_ACCESS_KEY`, `EMAIL_FROM` ([`worker/app/main.py`](../../backend/worker/app/main.py)
`_REQUIRED_PROD_SETTINGS`). No SMS or Firebase credentials are needed.

| Variable | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|
| `SES_REGION` | yes | where the domain is verified in SES (`us-west-2`) | no | not set | supplied |
| `SES_ACCESS_KEY_ID`, `SES_SECRET_ACCESS_KEY` | yes | AWS IAM user allowed `ses:SendEmail` only | yes | not set (email to the log) | by hand |
| `EMAIL_FROM` | yes (an address on the SES-verified domain, e.g. `orders@<domain>`) | Srini's choice | no | not set (`SENDGRID_FROM_EMAIL` default) | by hand |
| `EMAIL_FROM_NAME` | yes | railway.ts (`BhojanGo`) | no | default | supplied |
| `SES_CONFIGURATION_SET` | opt (bounce and complaint events) | SES | no | not set | not defined |
| `EXPO_ACCESS_TOKEN` | opt (needed if Expo "enhanced push security" is on) | Expo | yes | not set | not defined |
| `APNS_*`, `FIREBASE_*` | no (only for raw device tokens; the apps register Expo tokens) | Apple / Firebase | key: yes | not set | not defined |
| `APNS_SANDBOX` | no (must stay false) | — | — | default false | not defined (good) |
| `DEMO_RIDER_SIM` | **no** (refused in production) | — | — | `1` | not defined (good) |
| `REVIEW_SIM` | no: `"0"` (off); `"1"` only while a build is in store review (R20) | railway.ts | no | not set | `"0"` (turn on and off in the file, [go-live.md](go-live.md) step 14) |
| `DB_POOL_SIZE`, `REALTIME_INTERNAL_URL` | yes | railway.ts | no | same | supplied |
| `TWILIO_*`, `SENDGRID_*`, `MSG91_*` | no (SMS off; email through SES) | — | — | not set | not defined |

## web and admin (Next.js)

`NEXT_PUBLIC_*` are baked into the browser bundle at build time (build args in the Dockerfile). `APP_ENV` is a
build argument and a run-time variable: it turns off the test-site banner and noindex, and reaches the browser as
`NEXT_PUBLIC_APP_ENV` (next.config.mjs).

| Variable | Service | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|---|
| `APP`, `APP_DIR`, `PORT` | both | yes | railway.ts | no | same | supplied |
| `APP_ENV` | both | yes (`production`) | railway.ts | no | `qa` | supplied |
| `CORE_API_URL`, `REALTIME_URL` | both | yes (the image turns them into `USER_SVC_URL` etc.; admin's build fails without them) | railway.ts | no | internal URLs | supplied |
| `CORE_API_INTERNAL_URL` | web | yes | railway.ts | no | internal URL | supplied |
| `NEXT_PUBLIC_CORE_URL`, `NEXT_PUBLIC_REALTIME_URL` | both | yes | Railway reference to the services' public domains | no | reference | supplied; the reference resolves to the custom domain once one is added (see Production domains) |
| `NEXT_PUBLIC_APP_URL` | web | yes | the website's custom domain | no | reference | by hand |
| `NEXT_PUBLIC_PAYMENTS_PROVIDER` | web | yes, `stripe` | railway.ts | no | not set (`fake`) | supplied (`stripe`). Without it production fails closed: "Payments aren't available in this city yet", never the fake card form or checkout |
| `NEXT_PUBLIC_SENTRY_DSN` | both | yes (Srini's decision; off when unset) | Sentry (a web and an admin project, or one) | yes | not set | by hand. Its host joins the CSP's connect-src |
| `NEXT_PUBLIC_WORKER_URL` | web | no (no call uses it) | — | — | image default | not defined |

## postgres, redis, bucket

| Variable | Service | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB`, `PGDATA` | postgres | yes | railway.ts | no | same | supplied |
| `POSTGRES_PASSWORD` | postgres | yes | generated (24 random bytes, hex) | yes | sealed, QA's own | by hand |
| `REDIS_URL` and the rest | redis | — | Railway's Redis template makes them | Railway's | Railway's | automatic |
| bucket credentials | uploads | — | Railway makes them; copied into core-api (above) | keys: yes | QA bucket's | automatic (region `sjc`, fixed for good) |

Not variables, but set in Railway by hand for production: custom domains (Settings → Networking) and volume
backups for `postgres-data` (daily and weekly, as on QA since 2026-11-20).

## db-backup (hourly dump, R22) and the db-backups bucket

A cron service (every hour at :07; it exits after each run): `pg_dump` of the database into its own private bucket,
kept 7 days ([incident-plan.md](incident-plan.md#database-restore)). Restored and checked every Monday by
`.github/workflows/restore-drill.yml`.

| Variable | Service | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|---|
| `PGHOST`, `PGPORT` | db-backup | yes | railway.ts | no | `postgres.railway.internal`, `5432` | supplied |
| `PGUSER`, `PGPASSWORD`, `PGDATABASE` | db-backup | yes | references to postgres | (the password is postgres's sealed one) | references | supplied |
| `BACKUP_PREFIX`, `KEEP_DAYS` | db-backup | yes | railway.ts | no | `qa`, `7` | `production`, `7` |
| `BACKUP_BUCKET`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `S3_ADDRESSING_STYLE` | db-backup | yes | the `db-backups` bucket's credentials (bucketName, endpoint, region, urlStyle) | no | waiting for Srini (below) | by hand |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | db-backup | yes | the `db-backups` bucket's credentials | yes | waiting for Srini | by hand |
| GitHub secrets `BACKUP_ENDPOINT_URL`, `BACKUP_BUCKET`, `BACKUP_REGION`, `BACKUP_ADDRESSING_STYLE`, `BACKUP_ACCESS_KEY_ID`, `BACKUP_SECRET_ACCESS_KEY` | GitHub (the weekly restore test) | yes | the same credentials | GitHub secrets | waiting for Srini | — |

The bucket's keys can write, too: Railway buckets have one key pair. GitHub only uses them in the scheduled restore test
(forks never get secrets). With Cloudflare R2 later, CI would get a read-only token instead.

## The three app builds (customer, partner, rider)

Set at build time, outside Railway. Expo bakes `EXPO_PUBLIC_*` into the bundle. The apps get the Stripe
publishable key from the API, so no Stripe variable is needed in a build. No app offers Google sign-in today.
(`eas.json`, the production profile and push token registration are another round-19 branch.)

| Variable or input | Apps | Required | From | Secret | QA | Production today |
|---|---|---|---|---|---|---|
| `EXPO_PUBLIC_APP_ENV` | all | yes (`production`; a release build without it also counts as production) | build profile | no | `qa` (env-profile.sh) | **no production profile** |
| `EXPO_PUBLIC_CORE_URL`, `EXPO_PUBLIC_REALTIME_URL` | all | yes | the API and realtime domains | no | QA's Railway domains | **no production profile** |
| `EXPO_PUBLIC_WEB_URL` | customer, partner | yes | the website's domain | no | QA's web domain | **no production profile** |
| `EXPO_PUBLIC_SENTRY_DSN` | all | yes (Srini's decision; off when unset) | Sentry (one project per app, or one for the three) | no (a DSN is public in an app) | not set | **not in a profile yet** |
| `EXPO_PUBLIC_ENV` | all | no (older name) | — | — | `qa` | — |
| `EXPO_PUBLIC_WORKER_URL`, `EXPO_PUBLIC_FONT_AUDIT` | all | no (must stay unset) | — | — | unset | — |
| EAS project id (`extra.eas.projectId`) | all | yes | Expo | no | placeholder | **placeholder** in each `app.json` |
| `eas.json` build profiles | all | yes | Claude Code writes them | no | none | **missing** |
| `google-services.json` | all | yes for Android push | Firebase | no (not secret, kept out of git) | absent | absent |
| FCM V1 service account key, uploaded to EAS | all | yes for Expo push on Android | Firebase → Expo | yes | none | none |
| APNs key, uploaded to EAS | all | yes for iOS push | Apple Developer → Expo | yes | none | none |
| Signing: Android upload key, Apple distribution certificate | all | yes | EAS-managed credentials | yes | debug builds only | none |
| Apple Pay merchant id (`merchantIdentifier`) | customer | opt (Apple Pay in the iOS app) | Apple Developer | no | none | none |

## Completeness check

### Checker output

`python tools/railway/prod_config_check.py`, 2026-11-19, after round 19 (both PRs): exit 0. No gaps; what is
left is values from Srini's accounts (Railway secrets below, and the store ids in `config/store.json`, which a
production build refuses to run without) and addresses once the domain is bought:

```
Production config dry run (names only; no values, no network)

railway.ts, production: 6 services with variables: admin, core-api, postgres, realtime, web, worker
  admin: by-hand 1 (NEXT_PUBLIC_SENTRY_DSN); reference 2 (NEXT_PUBLIC_CORE_URL, NEXT_PUBLIC_REALTIME_URL); set 6 (APP, APP_DIR, APP_ENV, CORE_API_URL, PORT, REALTIME_URL)
  core-api: by-hand 22 (ALERT_WEBHOOK_TOKEN, AWS_ACCESS_KEY_ID, AWS_ENDPOINT_URL, AWS_REGION, AWS_SECRET_ACCESS_KEY, CORS_ORIGINS, IDENTITY_DATA_KEYS, INTERNAL_SERVICE_SECRET, JWT_PRIVATE_KEY, PUBLIC_API_URL, PUBLIC_WEB_URL, S3_ADDRESSING_STYLE, SENTRY_DSN, STRIPE_CONNECT_WEBHOOK_SECRET, STRIPE_PAYOUTS_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_VERIFY_SERVICE_SID, UPLOADS_BUCKET); computed 1 (PORT); empty 2 (JWKS_URL, OTP_FIXED_CODE); reference 3 (DATABASE_URL, EVENT_BUS_REDIS_URL, REDIS_URL); set 16 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, EMAIL_PROVIDER, EVENT_BUS, GEOIP, LOG_FORMAT, OTP_PROVIDER, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, ROUTING_PROVIDER, SERVICE_NAME, SMS_PROVIDER, STORAGE_PROVIDER, TAX_PROVIDER)
  postgres: by-hand 1 (POSTGRES_PASSWORD); set 3 (PGDATA, POSTGRES_DB, POSTGRES_USER)
  realtime: by-hand 3 (CORS_ORIGINS, INTERNAL_SERVICE_SECRET, SENTRY_DSN); computed 1 (PORT); empty 1 (OTP_FIXED_CODE); reference 3 (DATABASE_URL, EVENT_BUS_REDIS_URL, REDIS_URL); set 13 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, EMAIL_PROVIDER, EVENT_BUS, JWKS_URL, LOG_FORMAT, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, ROUTING_PROVIDER, SERVICE_NAME, SMS_PROVIDER)
  web: by-hand 2 (NEXT_PUBLIC_APP_URL, NEXT_PUBLIC_SENTRY_DSN); reference 2 (NEXT_PUBLIC_CORE_URL, NEXT_PUBLIC_REALTIME_URL); set 8 (APP, APP_DIR, APP_ENV, CORE_API_INTERNAL_URL, CORE_API_URL, NEXT_PUBLIC_PAYMENTS_PROVIDER, PORT, REALTIME_URL)
  worker: by-hand 6 (CORS_ORIGINS, EMAIL_FROM, INTERNAL_SERVICE_SECRET, SENTRY_DSN, SES_ACCESS_KEY_ID, SES_SECRET_ACCESS_KEY); computed 1 (PORT); empty 1 (OTP_FIXED_CODE); reference 3 (DATABASE_URL, EVENT_BUS_REDIS_URL, REDIS_URL); set 17 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, DB_POOL_SIZE, EMAIL_FROM_NAME, EMAIL_PROVIDER, EVENT_BUS, JWKS_URL, LOG_FORMAT, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, REALTIME_INTERNAL_URL, ROUTING_PROVIDER, SERVICE_NAME, SES_REGION, SMS_PROVIDER)

Code reads: 151 backend settings (config.py), 2 direct os.environ reads in the backend, 11 web and 10 admin process.env names, 8 EXPO_PUBLIC names.

1. What production needs, against railway.ts (production)
  none

2. QA-only, demo or fake settings defined for production
  none

3. Optional (production starts without them; each is off until set)
  off  OTEL_EXPORTER_OTLP_ENDPOINT: traces
  off  GOOGLE_WEB_CLIENT_ID: Sign in with Google on the website (GOOGLE_CLIENT_IDS for the apps)
  off  APPLE_CLIENT_ID: Sign in with Apple
  off  EXPO_ACCESS_TOKEN: Expo push security
  off  APNS_KEY_ID: direct APNs push (iOS tokens not from Expo)
  off  SES_CONFIGURATION_SET: SES bounce and complaint events
  off  TWILIO_PHONE_NUMBER: SMS from our own number (SMS_PROVIDER=live; production sends none: R19)
  off  TWILIO_PHONE_NUMBER_IN: India SMS (not Boise)
  off  MSG91_AUTH_KEY: India SMS (not Boise)
  off  RAZORPAY_KEY_ID: India payments (not Boise)

4. Web and admin: names the code reads that production leaves to a default
  web: NEXT_PUBLIC_WORKER_URL uses the image's build-arg default (apps/web/src/lib/client.ts:12)

5. Backend settings production leaves at their config.py default: 100 of 151
  direct os.environ reads with defaults: PRIORITY_ORDER_BATCHABLE
  defined for production but not read as a setting (build args or image settings): GEOIP

6. App builds (customer, partner, rider): build-time names, set outside Railway
  read by the apps: EXPO_PUBLIC_APP_ENV, EXPO_PUBLIC_CORE_URL, EXPO_PUBLIC_ENV, EXPO_PUBLIC_FONT_AUDIT, EXPO_PUBLIC_REALTIME_URL, EXPO_PUBLIC_SENTRY_DSN, EXPO_PUBLIC_WEB_URL, EXPO_PUBLIC_WORKER_URL
  note apps/customer: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)
  note apps/partner: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)
  note apps/rider: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)
  store ids still to fill from Srini's accounts (config/store.json; a production build refuses until they are): 9
    apple.teamId = {APPLE_TEAM_ID}
    apple.applePayMerchantId = {APPLE_PAY_MERCHANT_ID}
    google.serviceAccountKeyPath = {PLAY_SERVICE_ACCOUNT_JSON_PATH}
    apps.customer.easProjectId = {EAS_PROJECT_ID_CUSTOMER}
    apps.customer.ascAppId = {ASC_APP_ID_CUSTOMER}
    apps.partner.easProjectId = {EAS_PROJECT_ID_KITCHEN}
    apps.partner.ascAppId = {ASC_APP_ID_KITCHEN}
    apps.rider.easProjectId = {EAS_PROJECT_ID_DELIVERY}
    apps.rider.ascAppId = {ASC_APP_ID_DELIVERY}

7. Set by hand in Railway before go-live (preserve(): the repo holds no value)
  from Srini's accounts: 12
    NEXT_PUBLIC_SENTRY_DSN (admin, web): Sentry: web (or admin) project > Client Keys (DSN)
    SENTRY_DSN (core-api, realtime, worker): Sentry: backend project > Settings > Client Keys (DSN)
    SES_ACCESS_KEY_ID (worker): AWS: IAM user with ses:SendEmail only > access key
    SES_SECRET_ACCESS_KEY (worker): AWS: the same IAM access key
    STRIPE_CONNECT_WEBHOOK_SECRET (core-api): Stripe (live mode): Webhooks > Connect endpoint > signing secret
    STRIPE_PAYOUTS_WEBHOOK_SECRET (core-api): Stripe (live mode): Webhooks > transfers endpoint > signing secret
    STRIPE_PUBLISHABLE_KEY (core-api): Stripe (live mode): Developers > API keys
    STRIPE_SECRET_KEY (core-api): Stripe (live mode): Developers > API keys (or a restricted key)
    STRIPE_WEBHOOK_SECRET (core-api): Stripe (live mode): Webhooks > payments endpoint > signing secret
    TWILIO_ACCOUNT_SID (core-api): Twilio console: Account Info
    TWILIO_AUTH_TOKEN (core-api): Twilio console: Account Info (or an API key pair)
    TWILIO_VERIFY_SERVICE_SID (core-api): Twilio console: Verify > Services > create one (VA...)
  addresses (the domain): 5
    CORS_ORIGINS (core-api, realtime, worker): ["https://<domain>","https://admin.<domain>"] once the domain is bought
    EMAIL_FROM (worker): e.g. orders@<domain>, on the domain verified in SES
    NEXT_PUBLIC_APP_URL (web): https://<domain>
    PUBLIC_API_URL (core-api): https://api.<domain>
    PUBLIC_WEB_URL (core-api): https://<domain>
  generated once (Claude Code; sealed without printing): 5
    ALERT_WEBHOOK_TOKEN (core-api): openssl rand -hex 32
    IDENTITY_DATA_KEYS (core-api): python tools/secrets/identity_data_keys.py (stdout only)
    INTERNAL_SERVICE_SECRET (core-api, realtime, worker): openssl rand -hex 32; the same on core-api, realtime and worker
    JWT_PRIVATE_KEY (core-api): openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048
    POSTGRES_PASSWORD (postgres): openssl rand -hex 24
  from Railway: 6
    AWS_ACCESS_KEY_ID (core-api): railway bucket credentials --bucket uploads
    AWS_ENDPOINT_URL (core-api): railway bucket credentials --bucket uploads
    AWS_REGION (core-api): railway bucket credentials --bucket uploads
    AWS_SECRET_ACCESS_KEY (core-api): railway bucket credentials --bucket uploads
    S3_ADDRESSING_STYLE (core-api): railway bucket credentials --bucket uploads (urlStyle)
    UPLOADS_BUCKET (core-api): railway bucket credentials --bucket uploads

Result: 0 gap(s), 0 warning(s); 28 value(s) to set by hand in Railway, 12 of them from Srini's accounts.
```

### Secrets from Srini's accounts

What only Srini can get. Each goes into Railway (production environment) as a **sealed** variable, pasted straight
from the provider's page (or into his secrets folder for Claude Code's sealing script). Never in the repo, a chat or
a log.

| Variable | Service(s) | Account | Where to get it |
|---|---|---|---|
| `STRIPE_SECRET_KEY` | core-api | Stripe, live mode | Developers → API keys: the secret key, or a restricted key (`rk_live_`) covering every call |
| `STRIPE_PUBLISHABLE_KEY` | core-api | Stripe, live mode | Developers → API keys (`pk_live_`) |
| `STRIPE_WEBHOOK_SECRET` | core-api | Stripe, live mode | Developers → Webhooks → the payments endpoint (`/api/v1/payments/stripe/webhook`) → signing secret |
| `STRIPE_CONNECT_WEBHOOK_SECRET` | core-api | Stripe, live mode | the Connect endpoint (`/api/v1/finance/stripe/connect/webhook`, events on connected accounts) → signing secret |
| `STRIPE_PAYOUTS_WEBHOOK_SECRET` | core-api | Stripe, live mode | the account endpoint (`/api/v1/finance/stripe/webhook`, `transfer.*`) → signing secret |
| `TWILIO_ACCOUNT_SID` | core-api | Twilio | Console → Account Info |
| `TWILIO_AUTH_TOKEN` | core-api | Twilio | Console → Account Info (or an API key pair in its place) |
| `TWILIO_VERIFY_SERVICE_SID` | core-api | Twilio | Verify → Services → create "BhojanGo" (code length 6, SMS channel) → Service SID (`VA...`) |
| `SES_ACCESS_KEY_ID` | worker | AWS | IAM → Users → a user for SES with a policy allowing only `ses:SendEmail` (on the domain identity) → Security credentials → access key |
| `SES_SECRET_ACCESS_KEY` | worker | AWS | the same access key (shown once) |
| `SENTRY_DSN` | core-api, realtime, worker | Sentry | a backend (Python/FastAPI) project → Settings → Client Keys (DSN) |
| `NEXT_PUBLIC_SENTRY_DSN` | web, admin | Sentry | a JavaScript/Next.js project (one for both, or one each) → Client Keys (DSN) |

Outside Railway, also from Srini's accounts: `EXPO_PUBLIC_SENTRY_DSN` (a React Native project) in the app build
profiles (each app's `eas.json`); the store ids in `config/store.json` (the three EAS project ids, the three App Store
Connect app ids, the Apple team id, the Apple Pay merchant id, the Play service account key); `google-services.json` and the FCM V1 key (Firebase → EAS); the APNs key
(Apple → EAS).

The other values set by hand need no account of Srini's: addresses once the domain is bought (`CORS_ORIGINS`,
`PUBLIC_WEB_URL`, `PUBLIC_API_URL`, `NEXT_PUBLIC_APP_URL`, `EMAIL_FROM`), generated ones (`POSTGRES_PASSWORD`,
`INTERNAL_SERVICE_SECRET`, `JWT_PRIVATE_KEY`, `IDENTITY_DATA_KEYS`, `ALERT_WEBHOOK_TOKEN`) and the bucket's
credentials from Railway. The checker's section 7 lists them all with their source.

### What production gets right today

- `APP_ENV=production`, `PAYMENT_PROVIDER=live`, `PAYOUT_PROVIDER=live`, `PUSH_PROVIDER=live`,
  `EMAIL_PROVIDER=ses`, `SMS_PROVIDER=off`, `OTP_PROVIDER=twilio_verify`, `TAX_PROVIDER=stripe_tax`
  ([`.railway/railway.ts`](../../.railway/railway.ts)).
- `OTP_FIXED_CODE=""` on all three backends. (Delivery PINs have no setting since R27: always random.)
- `DEMO_RIDER_SIM` and the fake payment settings only outside production.
- `REVIEW_SIM` on the worker `"0"`, except while a build is in store review: it then plays the review kitchen and
  delivery partner for orders in the hidden review city only ([store/README.md](store/README.md#reviewer-access)).
- Every secret is `preserve()` (set by hand, sealed), never written in the file.
- core-api and the worker refuse to start with a missing or local public address, no two-step key, no code sender,
  or a provider without its keys; the website fails closed without a payment provider.
- Postgres has no public port in production; web and admin don't sleep in production.
- The test-site banner and noindex follow `APP_ENV`, which production sets on web and admin (build and run time).
- The demo seed and the full seed refuse production; production's base data is the markets-only seed
  ([`tools/seed/markets.py`](../../tools/seed/markets.py)).

### Gaps found on 2026-11-19, and what round 19 did

1. **Stripe live keys** (5): defined for production (`preserve()`, sealed). Values: Srini's Stripe account.
2. **`PUBLIC_WEB_URL` and `PUBLIC_API_URL`**: defined; core-api now refuses to start in production when either is
   missing, not https, or local ([`config.py`](../../backend/shared/config.py) `public_url_problem`).
3. **`IDENTITY_DATA_KEYS`**: defined; generated once with
   [`tools/secrets/identity_data_keys.py`](../../tools/secrets/identity_data_keys.py) (stdout only; refuses to write
   into a file); core-api refuses to start without it.
4. **Worker provider keys**: the worker no longer needs SendGrid, Twilio or Firebase. Email is SES (`SesEmail`, the
   SES v2 API through boto3); SMS is off; sign-in codes go through Twilio Verify in core-api
   ([`twilio_verify.py`](../../backend/core_api/modules/identity/service/twilio_verify.py)). With no Firebase app, an
   FCM token now counts as not sent in production (so it isn't reported as delivered).
5. **`NEXT_PUBLIC_PAYMENTS_PROVIDER`**: `stripe` for production, and now a Dockerfile build arg (before, setting it
   in Railway wouldn't have reached the bundle). Without it production shows "Payments aren't available in this city
   yet" ([`lib/payments.ts`](../../apps/web/src/lib/payments.ts)).
6. **Sentry**: `sentry-sdk` (backends), `@sentry/nextjs` (web, admin), `@sentry/react-native` (apps); each off with
   no DSN (no init, no network).
7. **Fake payment settings**: QA and staging only.
8. `DEMO_RIDER_SIM`, `OTP_FIXED_CODE`, the test-site banner, `SEED_PASSWORDS`: were already
   right for production, unchanged.
9. **Production seed**: [`tools/seed/markets.py`](../../tools/seed/markets.py), markets only (countries, states,
   cities, zones, rules, help articles, Terms and Privacy as drafts; Boise live, India switched off; no users,
   kitchens, orders or payout accounts). It only adds what's missing, so it's safe to run again. CI runs it twice on
   a fresh database with production settings. The full seed now refuses production.
10. **First admin**: `python -m core_api.modules.identity.first_admin --email ... --name ...` (refused when any super
    admin exists); nothing secret is printed: the password is set from the website's reset email, and the
    authenticator is enrolled at first sign-in.

Still open (not this branch): 11 (push token registration in the apps), 12 (alerting on Railway), 13 (store
builds: `eas.json`, a production profile, the EAS project ids), 14 (runbook drift in
[`railway-deploy.md`](../runbooks/railway-deploy.md)).

### Decisions for Srini

Made (round 19): Boise only, India kept and switched off; markets-only seed; SES for email; Twilio Verify for
sign-in codes; push for order updates; Sentry now.

Still open:

- **Domains:** which names (e.g. `bhojango.com`, `admin.`, `api.`, `rt.`). And whether the browser and apps use the
  custom API domains (`NEXT_PUBLIC_CORE_URL` today is the Railway domain, [`railway.ts`](../../.railway/railway.ts)).
  Recommended: custom domains everywhere, so Stripe webhooks and app builds never change if Railway's names do.
- **Email sender** address and name (`EMAIL_FROM`, `EMAIL_FROM_NAME` = BhojanGo), on the domain verified in SES.
- **SES region**: `us-west-2` in `railway.ts`; change it there if the domain is verified elsewhere.
- **Sentry projects**: one per surface (backend, web, admin, each app) or fewer; the free plan's event quota is
  shared.
- **Alerts:** where they go (email, SMS, a paging app), and whether to run Prometheus/Alertmanager on Railway
  (usage cost) or use simpler uptime checks plus Sentry alerts.
