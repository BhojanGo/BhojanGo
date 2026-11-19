# Production configuration (dry run, 2026-11-19)

Every variable and secret production needs, per service. Nothing here was created, bought or deployed.
Production does not exist yet. No value is written here: only names, where each comes from, and what kind of
value QA has.

How this list was made:

- the backend settings in [`backend/shared/config.py`](../../backend/shared/config.py) (one Settings class, every
  field is an environment variable of the same name) and its production check `refuse_fakes_in_production`;
- the other production checks in the code (worker start-up, providers, internal auth, two-step secrets, payments);
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
| Domain registrar and DNS | website, admin, API and realtime names; email sender records | readiness item 2 |
| Stripe, live mode (DeepTrics LLC) | payments, Connect payouts, Stripe Tax | per use |
| SendGrid (or another sender) | email: codes, receipts, password reset | free tier first |
| Twilio, with a US number registered for application-to-person SMS (10DLC or toll-free verification) | sign-in codes and order SMS | per message |
| Firebase project (Google) | Android push (FCM). Expo push on Android also needs it | free |
| Apple Developer (DeepTrics LLC) | iOS builds, APNs key for push, Apple Pay merchant id | $99 a year |
| Google Play Console (DeepTrics LLC) | Android builds | $25 once |
| Expo (EAS) | store builds and push for the three apps | free tier first |
| Google Cloud OAuth client | Sign in with Google (optional) | free |
| Sentry | error tracking (optional, recommended) | free tier first |
| Railway | already exists (workspace "Srinivas's Projects") | usage |

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
| `CORS_ORIGINS` | yes (core-api, realtime) | the custom web and admin domains, as a JSON list | no (not secret) | Railway references to the web and admin domains | by hand |
| `CLIENT_IP_HEADER` | yes (`X-Real-IP`) | railway.ts | no | same | supplied |
| `LOG_FORMAT` | no (json is the production default) | railway.ts | no | `json` | supplied |
| `PAYMENT_PROVIDER` | yes, must be `live` | railway.ts | no | `fake` in railway.ts; QA's core-api has `auto` set by hand (round 10) | supplied |
| `PAYOUT_PROVIDER` | yes, not `fake` | railway.ts | no | as above | supplied (`live`) |
| `SMS_PROVIDER`, `PUSH_PROVIDER` | yes (worker), must be `live` | railway.ts | no | `log` | supplied |
| `EMAIL_PROVIDER` | yes (worker), `sendgrid` | railway.ts | no | `log` | supplied |
| `OTP_FIXED_CODE` | yes, must be `""` | railway.ts | no | default fixed code for seed phones | supplied (`""`) |
| `DELIVERY_PIN_FIXED` | yes, must be `""` | railway.ts | no | default fixed PIN for seed phones | supplied (`""`) |
| `ROUTING_PROVIDER` | yes (`straight_line`) | railway.ts | no | same | supplied |
| `SERVICE_NAME`, `PORT` | yes | railway.ts | no | same | supplied |
| `RAILWAY_ENVIRONMENT_NAME` | automatic | Railway | no | `QA` | automatic (also checked by the production guard) |
| `SENTRY_DSN` | opt (recommended) | Sentry | yes | not set | **missing**; also needs `sentry-sdk` in `backend/pyproject.toml` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | opt | a tracing vendor | no | not set | not defined |

## core-api

| Variable | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|
| `JWT_PRIVATE_KEY` | yes | generated (RSA 2048 PEM, new for production) | yes | sealed, QA's own key | by hand |
| `JWKS_URL` | yes, `""` (core-api signs) | railway.ts | no | `""` | supplied |
| `IDENTITY_DATA_KEYS` | yes (admins' two-step secrets; refused in production without it) | generated (Fernet key, JSON list) | yes | not in railway.ts | **missing** |
| `PUBLIC_WEB_URL` | yes (password-reset links, Stripe return URL) | the website's custom domain | no | set by hand (web's Railway domain) | **missing** (default is localhost) |
| `PUBLIC_API_URL` | yes (Stripe payout onboarding links) | the API's public address | no | set by hand (round 10) | **missing** (default is localhost) |
| `STRIPE_SECRET_KEY` | yes | Stripe live | yes | Stripe test-mode key, sealed, set by hand | **missing** |
| `STRIPE_PUBLISHABLE_KEY` | yes (handed to web and app checkouts by the API) | Stripe live | yes (not secret, kept with the rest) | test-mode key, set by hand | **missing** |
| `STRIPE_WEBHOOK_SECRET` | yes (payments endpoint) | Stripe live webhook | yes | test-mode signing secret, by hand | **missing** |
| `STRIPE_CONNECT_WEBHOOK_SECRET` | yes (Connect endpoint) | Stripe live webhook | yes | by hand | **missing** |
| `STRIPE_PAYOUTS_WEBHOOK_SECRET` | yes (transfers endpoint) | Stripe live webhook | yes | by hand | **missing** |
| `TAX_PROVIDER` | opt (`auto` picks Stripe Tax with a key; set `stripe_tax` to be explicit) | railway.ts | no | `auto`, by hand | not defined (default `auto`) |
| `STORAGE_PROVIDER` | yes (`s3`) | railway.ts | no | `s3` | supplied |
| `UPLOADS_BUCKET`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `S3_ADDRESSING_STYLE` | yes | Railway bucket credentials (production's own bucket) | no | QA bucket's | by hand |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | yes | Railway bucket credentials | yes | sealed, QA's own | by hand |
| `ALERT_WEBHOOK_TOKEN` | yes once alerts post to core-api | generated | yes | sealed | by hand |
| `GEOIP` | no (build arg: the free DB-IP file) | railway.ts | no | `1` | supplied |
| `GOOGLE_WEB_CLIENT_ID` | opt (website's Google button; hidden without it) | Google Cloud OAuth client | no | not set | not defined |
| `GOOGLE_CLIENT_IDS` | opt (only if the apps add Google sign-in; they don't today) | Google Cloud | no | not set | not defined |
| `APPLE_CLIENT_ID`, `APPLE_CLIENT_IDS` (+ team, key) | opt (Sign in with Apple) | Apple Developer | key: yes | not set | not defined |
| `FAKE_PAYMENT_WEBHOOK_URL`, `FAKE_PAYMENT_AUTO_COMPLETE_SECONDS`, `FAKE_PAYMENT_WEBHOOK_SECRET` | **no** (the fake gateway only) | — | — | set | **defined for production** (should be QA only) |
| `RAZORPAY_*` | no for Boise (India) | Razorpay | yes | not set | not defined |

## realtime

Only the shared variables above, with `REDIS_URL` on database 3. No provider keys.

## worker

The worker refuses to start in production without `SENDGRID_API_KEY`, `TWILIO_ACCOUNT_SID` and
`FIREBASE_PROJECT_ID` ([`worker/app/main.py:29`](../../backend/worker/app/main.py)). With the Redis event bus,
the worker sends every SMS, email and push (core-api only queues them), so the provider keys belong here.

| Variable | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|
| `SENDGRID_API_KEY` | yes (start-up check) | SendGrid | yes | not set (email to the log) | **missing** |
| `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME` | yes (an address on the authenticated domain) | Srini's choice | no | default | **missing** (default `noreply@bhojango.com`) |
| `TWILIO_ACCOUNT_SID` | yes (start-up check) | Twilio | yes | not set (SMS to the log) | **missing** |
| `TWILIO_AUTH_TOKEN` | yes | Twilio | yes | not set | **missing** |
| `TWILIO_PHONE_NUMBER` | yes (the US sender number) | Twilio | no | not set | **missing** |
| `FIREBASE_PROJECT_ID` | yes (start-up check) | Firebase | no | not set | **missing** |
| `FIREBASE_PRIVATE_KEY_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL` | yes for FCM tokens (a service account) | Firebase | yes | not set | **missing** |
| `EXPO_ACCESS_TOKEN` | opt (needed if Expo "enhanced push security" is on) | Expo | yes | not set | not defined |
| `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY`, `APNS_BUNDLE_ID` | opt (only for raw iOS tokens; Expo tokens don't need them) | Apple Developer | key: yes | not set | not defined |
| `APNS_SANDBOX` | no (must stay false) | — | — | default false | not defined (good) |
| `DEMO_RIDER_SIM` | **no** (refused in production) | — | — | `1` | not defined (good) |
| `DB_POOL_SIZE`, `REALTIME_INTERNAL_URL` | yes | railway.ts | no | same | supplied |
| `TWILIO_PHONE_NUMBER_IN`, `MSG91_*` | no for Boise (India) | Twilio / MSG91 | yes | not set | not defined |

## web and admin (Next.js)

`NEXT_PUBLIC_*` are baked into the browser bundle at build time. `APP_ENV` is a build argument and a run-time
variable: it turns off the test-site banner and noindex.

| Variable | Service | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|---|
| `APP`, `APP_DIR`, `PORT` | both | yes | railway.ts | no | same | supplied |
| `APP_ENV` | both | yes (`production`) | railway.ts | no | `qa` | supplied |
| `CORE_API_URL`, `REALTIME_URL` | both | yes (the image turns them into `USER_SVC_URL` etc.; admin's build fails without them) | railway.ts | no | internal URLs | supplied |
| `CORE_API_INTERNAL_URL` | web | yes | railway.ts | no | internal URL | supplied |
| `NEXT_PUBLIC_CORE_URL`, `NEXT_PUBLIC_REALTIME_URL` | both | yes | Railway reference to the services' Railway domains | no | reference | supplied, but as the Railway domains, not the custom ones (a decision below) |
| `NEXT_PUBLIC_APP_URL` | web | yes | the website's custom domain | no | reference | by hand |
| `NEXT_PUBLIC_PAYMENTS_PROVIDER` | web | yes: anything but `fake` (e.g. `stripe`) | railway.ts | no | not set (`fake`) | **missing**: production would show the fake "add a card" form |
| `NEXT_PUBLIC_WORKER_URL` | web | no (no call uses it) | — | — | image default | not defined |

## postgres, redis, bucket

| Variable | Service | Required | From | Sealed | QA | railway.ts (production) |
|---|---|---|---|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB`, `PGDATA` | postgres | yes | railway.ts | no | same | supplied |
| `POSTGRES_PASSWORD` | postgres | yes | generated (24 random bytes, hex) | yes | sealed, QA's own | by hand |
| `REDIS_URL` and the rest | redis | — | Railway's Redis template makes them | Railway's | Railway's | automatic |
| bucket credentials | uploads | — | Railway makes them; copied into core-api (above) | keys: yes | QA bucket's | automatic (region `sjc`, fixed for good) |

Not variables, but set in Railway by hand for production: custom domains (Settings → Networking) and volume
backups for `postgres-data`.

## The three app builds (customer, partner, rider)

Set at build time, outside Railway. Expo bakes `EXPO_PUBLIC_*` into the bundle. The apps get the Stripe
publishable key from the API, so no Stripe variable is needed in a build. No app offers Google sign-in today.

| Variable or input | Apps | Required | From | Secret | QA | Production today |
|---|---|---|---|---|---|---|
| `EXPO_PUBLIC_APP_ENV` | all | yes (`production`; a release build without it also counts as production) | build profile | no | `qa` (env-profile.sh) | **no production profile** |
| `EXPO_PUBLIC_CORE_URL`, `EXPO_PUBLIC_REALTIME_URL` | all | yes | the API and realtime domains | no | QA's Railway domains | **no production profile** |
| `EXPO_PUBLIC_WEB_URL` | customer, partner | yes | the website's domain | no | QA's web domain | **no production profile** |
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

`python tools/railway/prod_config_check.py`, 2026-11-19, on `r18/fixes-store-golive` (exit 1):

```
Production config dry run (names only; no values, no network)

railway.ts, production: 6 services with variables: admin, core-api, postgres, realtime, web, worker
  admin: reference 2 (NEXT_PUBLIC_CORE_URL, NEXT_PUBLIC_REALTIME_URL); set 6 (APP, APP_DIR, APP_ENV, CORE_API_URL, PORT, REALTIME_URL)
  core-api: by-hand 11 (ALERT_WEBHOOK_TOKEN, AWS_ACCESS_KEY_ID, AWS_ENDPOINT_URL, AWS_REGION, AWS_SECRET_ACCESS_KEY, CORS_ORIGINS, FAKE_PAYMENT_WEBHOOK_SECRET, INTERNAL_SERVICE_SECRET, JWT_PRIVATE_KEY, S3_ADDRESSING_STYLE, UPLOADS_BUCKET); computed 1 (PORT); empty 3 (DELIVERY_PIN_FIXED, JWKS_URL, OTP_FIXED_CODE); reference 2 (EVENT_BUS_REDIS_URL, REDIS_URL); set 17 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, DATABASE_URL, EMAIL_PROVIDER, EVENT_BUS, FAKE_PAYMENT_AUTO_COMPLETE_SECONDS, FAKE_PAYMENT_WEBHOOK_URL, GEOIP, LOG_FORMAT, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, ROUTING_PROVIDER, SERVICE_NAME, SMS_PROVIDER, STORAGE_PROVIDER)
  postgres: by-hand 1 (POSTGRES_PASSWORD); set 3 (PGDATA, POSTGRES_DB, POSTGRES_USER)
  realtime: by-hand 2 (CORS_ORIGINS, INTERNAL_SERVICE_SECRET); computed 1 (PORT); empty 2 (DELIVERY_PIN_FIXED, OTP_FIXED_CODE); reference 2 (EVENT_BUS_REDIS_URL, REDIS_URL); set 14 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, DATABASE_URL, EMAIL_PROVIDER, EVENT_BUS, JWKS_URL, LOG_FORMAT, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, ROUTING_PROVIDER, SERVICE_NAME, SMS_PROVIDER)
  web: by-hand 1 (NEXT_PUBLIC_APP_URL); reference 2 (NEXT_PUBLIC_CORE_URL, NEXT_PUBLIC_REALTIME_URL); set 7 (APP, APP_DIR, APP_ENV, CORE_API_INTERNAL_URL, CORE_API_URL, PORT, REALTIME_URL)
  worker: by-hand 2 (CORS_ORIGINS, INTERNAL_SERVICE_SECRET); computed 1 (PORT); empty 2 (DELIVERY_PIN_FIXED, OTP_FIXED_CODE); reference 2 (EVENT_BUS_REDIS_URL, REDIS_URL); set 16 (APP_ENV, CLIENT_IP_HEADER, CORE_API_URL, DATABASE_URL, DB_POOL_SIZE, EMAIL_PROVIDER, EVENT_BUS, JWKS_URL, LOG_FORMAT, PAYMENT_PROVIDER, PAYOUT_PROVIDER, PUSH_PROVIDER, REALTIME_INTERNAL_URL, ROUTING_PROVIDER, SERVICE_NAME, SMS_PROVIDER)

Code reads: 143 backend settings (config.py), 2 direct os.environ reads in the backend, 8 web and 7 admin process.env names, 7 EXPO_PUBLIC names.

1. What production needs, against railway.ts (production)
  GAP  core-api: IDENTITY_DATA_KEYS: not defined for production [needs: sealed; backend/core_api/modules/identity/service/totp.py:97]
  GAP  core-api: PUBLIC_WEB_URL: not defined for production [needs: set; backend/core_api/modules/finance/service/connect.py:123]
  GAP  core-api: PUBLIC_API_URL: not defined for production [needs: set; backend/core_api/modules/finance/service/connect.py:118]
  GAP  core-api: STRIPE_SECRET_KEY: not defined for production [needs: sealed; backend/core_api/modules/payments/service/gateways.py:240]
  GAP  core-api: STRIPE_PUBLISHABLE_KEY: not defined for production [needs: set; backend/core_api/modules/payments/service/gateways.py:100]
  GAP  core-api: STRIPE_WEBHOOK_SECRET: not defined for production [needs: sealed; backend/core_api/modules/payments/service/stripe_svc.py:75]
  GAP  core-api: STRIPE_CONNECT_WEBHOOK_SECRET: not defined for production [needs: sealed; backend/core_api/modules/finance/api/v1/finance.py:507]
  GAP  core-api: STRIPE_PAYOUTS_WEBHOOK_SECRET: not defined for production [needs: sealed; backend/core_api/modules/finance/api/v1/finance.py:518]
  GAP  worker: TWILIO_AUTH_TOKEN: not defined for production [needs: sealed; backend/shared/providers/sms.py:46]
  GAP  worker: TWILIO_PHONE_NUMBER: not defined for production [needs: set; backend/shared/providers/sms.py:44]
  GAP  worker: SENDGRID_FROM_EMAIL: not defined for production [needs: set; backend/shared/providers/email.py:21]
  GAP  worker: FIREBASE_PRIVATE_KEY_ID: not defined for production [needs: sealed; backend/worker/app/services/fcm.py:27]
  GAP  worker: FIREBASE_PRIVATE_KEY: not defined for production [needs: sealed; backend/worker/app/services/fcm.py:27]
  GAP  worker: FIREBASE_CLIENT_EMAIL: not defined for production [needs: set; backend/worker/app/services/fcm.py:29]
  GAP  web: NEXT_PUBLIC_PAYMENTS_PROVIDER: not defined for production [needs: not_fake; apps/web/src/app/account/profile/Payments.tsx:25]
  GAP  worker: SENDGRID_API_KEY: not defined for production [needs: sealed; backend/worker/app/main.py:29]
  GAP  worker: TWILIO_ACCOUNT_SID: not defined for production [needs: sealed; backend/worker/app/main.py:29]
  GAP  worker: FIREBASE_PROJECT_ID: not defined for production [needs: set; backend/worker/app/main.py:29]

2. QA-only, demo or fake settings defined for production
  WARN core-api: FAKE_PAYMENT_AUTO_COMPLETE_SECONDS is defined (set); it only serves the fake gateway, the demo or QA
  WARN core-api: FAKE_PAYMENT_WEBHOOK_SECRET is defined (by-hand); it only serves the fake gateway, the demo or QA
  WARN core-api: FAKE_PAYMENT_WEBHOOK_URL is defined (set); it only serves the fake gateway, the demo or QA

3. Optional (production starts without them; each is off until set)
  off  SENTRY_DSN: error tracking (also needs sentry-sdk in backend/pyproject.toml)
  off  OTEL_EXPORTER_OTLP_ENDPOINT: traces
  off  GOOGLE_WEB_CLIENT_ID: Sign in with Google on the website (GOOGLE_CLIENT_IDS for the apps)
  off  APPLE_CLIENT_ID: Sign in with Apple
  off  EXPO_ACCESS_TOKEN: Expo push security
  off  APNS_KEY_ID: direct APNs push (iOS tokens not from Expo)
  off  TAX_PROVIDER: explicit stripe_tax (auto picks Stripe Tax when STRIPE_SECRET_KEY is set)
  off  TWILIO_PHONE_NUMBER_IN: India SMS (not Boise)
  off  MSG91_AUTH_KEY: India SMS (not Boise)
  off  RAZORPAY_KEY_ID: India payments (not Boise)

4. Web and admin: names the code reads that production leaves to a default
  web: NEXT_PUBLIC_PAYMENTS_PROVIDER uses the code's fallback (apps/web/src/app/account/profile/Payments.tsx:25)
  web: NEXT_PUBLIC_WORKER_URL uses the image's build-arg default (apps/web/src/lib/client.ts:12)

5. Backend settings production leaves at their config.py default: 108 of 143
  direct os.environ reads with defaults: PRIORITY_ORDER_BATCHABLE
  defined for production but not read as a setting (build args or image settings): GEOIP

6. App builds (customer, partner, rider): build-time names, set outside Railway
  read by the apps: EXPO_PUBLIC_APP_ENV, EXPO_PUBLIC_CORE_URL, EXPO_PUBLIC_ENV, EXPO_PUBLIC_FONT_AUDIT, EXPO_PUBLIC_REALTIME_URL, EXPO_PUBLIC_WEB_URL, EXPO_PUBLIC_WORKER_URL
  GAP  tools/mobile/env-profile.sh has profiles qa, local; none for production (tools/mobile/env-profile.sh:25)
  GAP  apps/customer: no eas.json (no store build profile)
  GAP  apps/customer: EAS projectId is a placeholder (apps/customer/app.json:76)
  note apps/customer: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)
  GAP  apps/partner: no eas.json (no store build profile)
  GAP  apps/partner: EAS projectId is a placeholder (apps/partner/app.json:71)
  note apps/partner: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)
  GAP  apps/rider: no eas.json (no store build profile)
  GAP  apps/rider: EAS projectId is a placeholder (apps/rider/app.json:86)
  note apps/rider: ./google-services.json is not in the checkout (Firebase; app.config.js drops it, so no FCM)

Result: 25 gap(s), 3 warning(s).
```

### What production gets right today

- `APP_ENV=production`, `PAYMENT_PROVIDER=live`, `PAYOUT_PROVIDER=live`, `SMS_PROVIDER=live`, `PUSH_PROVIDER=live`,
  `EMAIL_PROVIDER=sendgrid` ([`.railway/railway.ts:76`](../../.railway/railway.ts)).
- `OTP_FIXED_CODE=""` and `DELIVERY_PIN_FIXED=""` on all three backends ([`.railway/railway.ts:81`](../../.railway/railway.ts)).
- `DEMO_RIDER_SIM` only in QA ([`.railway/railway.ts:149`](../../.railway/railway.ts)).
- Every secret it does define is `preserve()` (set by hand, sealed), never written in the file.
- Postgres has no public port in production; web and admin don't sleep in production.
- The test-site banner and noindex follow `APP_ENV`, which production sets on web and admin (build and run time).
- The demo seed refuses production ([`tools/seed/demo_guard.py:27`](../../tools/seed/demo_guard.py)).

### Gaps

Variables production needs that `railway.ts` doesn't define for production:

1. **Stripe live keys** (5): `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
   `STRIPE_CONNECT_WEBHOOK_SECRET`, `STRIPE_PAYOUTS_WEBHOOK_SECRET`. With `PAYMENT_PROVIDER=live` and no key, the
   start-up check passes but every checkout fails at Stripe
   ([`gateways.py:246`](../../backend/core_api/modules/payments/service/gateways.py)) and tax quotes are refused
   ([`tax.py:276`](../../backend/core_api/modules/payments/service/tax.py)). QA has them only because they were set
   by hand.
2. **`PUBLIC_WEB_URL` and `PUBLIC_API_URL`**: default to localhost
   ([`config.py:80`](../../backend/shared/config.py), [`config.py:147`](../../backend/shared/config.py)). Password-reset
   links and Stripe payout onboarding would point at localhost.
3. **`IDENTITY_DATA_KEYS`**: admins can't enrol two-step sign-in in production without it
   ([`totp.py:96`](../../backend/core_api/modules/identity/service/totp.py)), so no admin can sign in.
4. **Worker provider keys**: the worker refuses to start without `SENDGRID_API_KEY`, `TWILIO_ACCOUNT_SID`,
   `FIREBASE_PROJECT_ID` ([`worker/app/main.py:29`](../../backend/worker/app/main.py)). Also missing:
   `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, the Firebase service account, `SENDGRID_FROM_EMAIL` (defaults to
   `noreply@bhojango.com`, [`config.py:219`](../../backend/shared/config.py), which must match the domain bought).
5. **`NEXT_PUBLIC_PAYMENTS_PROVIDER`** on web: unset means `fake`, so production's account page offers the fake
   "add a card" form ([`Payments.tsx:25`](../../apps/web/src/app/account/profile/Payments.tsx), used at line 169).
6. **`SENTRY_DSN`**: not defined, and `sentry-sdk` isn't a dependency, so setting it alone does nothing
   ([`observability.py:64`](../../backend/shared/observability.py); not in `backend/pyproject.toml`).

QA-only or fake settings production still gets:

7. **Fake payment settings** on core-api in every environment: `FAKE_PAYMENT_WEBHOOK_URL`,
   `FAKE_PAYMENT_AUTO_COMPLETE_SECONDS`, `FAKE_PAYMENT_WEBHOOK_SECRET`
   ([`.railway/railway.ts:131`](../../.railway/railway.ts)). Harmless while the provider is `live` (the fake routes
   answer 404 in production), but they should be QA only, and the sealed fake secret is one more thing to set.
8. `DEMO_RIDER_SIM`, `OTP_FIXED_CODE`, `DELIVERY_PIN_FIXED`: correct (off / `""`) for production. The test-site
   banner: off when `APP_ENV=production` (web, admin) and `EXPO_PUBLIC_APP_ENV=production` (apps). `SEED_PASSWORDS`:
   not in `railway.ts`. Nothing in production points at a fake or `auto` provider; `TAX_PROVIDER` is left at `auto`,
   which is Stripe Tax once the key is set.

Things that are not variables but block production the same way:

9. **No seed for production without demo data.** Markets (countries, cities, zones, rules, help articles) come
   only from [`tools/seed/seed.py`](../../tools/seed/seed.py), which in the same run creates `@example.com`
   customers, partners and admins with known or random passwords ([`seed.py:379`](../../tools/seed/seed.py)), the
   seed kitchens and menus, and **fake payout accounts** ([`seed.py:429`](../../tools/seed/seed.py)). Its data makes
   Hyderabad `live` ([`data.py:433`](../../tools/seed/data.py)) and Boise `beta`
   ([`data.py:479`](../../tools/seed/data.py)). The runbook says "No seed data" for production
   ([`railway-deploy.md:155`](../runbooks/railway-deploy.md)), which leaves no markets at all.
10. **No first admin.** Admin roles are granted only by an admin
    ([`identity/api/v1/admin.py:63`](../../backend/core_api/modules/identity/api/v1/admin.py)); the only other source
    is the seed's `@example.com` admins.
11. **Push never reaches a phone.** The apps never register a push token (no `getExpoPushTokenAsync` anywhere; only
    `setNotificationHandler` in [`apps/customer/app/_layout.tsx:15`](../../apps/customer/app/_layout.tsx) and the
    rider's), and the token endpoint is on the worker
    ([`notifications.py:25`](../../backend/worker/app/api/v1/notifications.py)), which has no public domain. Also,
    with no Firebase app configured, FCM sends are counted as sent
    ([`push.py:117`](../../backend/shared/providers/push.py)).
12. **No alerting on Railway.** The alert rules run in the local Prometheus and Alertmanager
    ([`observe.md:46`](../runbooks/observe.md)); nothing in `railway.ts` runs them, so `ALERT_WEBHOOK_TOKEN` has no
    sender in production.
13. **No store builds.** No `eas.json`, placeholder EAS project ids, no production profile in
    [`env-profile.sh:25`](../../tools/mobile/env-profile.sh), and CI builds debug APKs only
    ([`tools/android/build-apk.sh:20`](../../tools/android/build-apk.sh)). Apple Pay in the iOS app also needs a merchant id
    ([`stripeSheet.ts:43`](../../apps/customer/lib/stripeSheet.ts)).
14. **Runbook drift.** [`railway-deploy.md:304`](../runbooks/railway-deploy.md) says "The config sets every variable
    below", but `PUBLIC_WEB_URL` and `IDENTITY_DATA_KEYS` (lines 316–317) aren't in `railway.ts`. QA's Stripe keys and
    `PAYMENT_PROVIDER=auto` were also set by hand, so `railway.ts` says `fake` for QA while QA runs `auto`.

### Decisions for Srini

- **Domains:** which names (e.g. `bhojango.com`, `admin.`, `api.`, `rt.`). And whether the browser and apps use the
  custom API domains (`NEXT_PUBLIC_CORE_URL` today is the Railway domain, [`railway.ts:172`](../../.railway/railway.ts)).
  Recommended: custom domains everywhere, so Stripe webhooks and app builds never change if Railway's names do.
- **Email sender** address and name (`SENDGRID_FROM_EMAIL`), on the bought domain.
- **SMS:** Twilio 10DLC or toll-free verification for the US number (takes days; start early).
- **India:** keep it out of production at launch (no Razorpay or MSG91 keys; Hyderabad not `live`). Recommended.
- **Production seed:** a markets-only seed (US, Idaho, Boise `live`, zones, rules, help articles; no users, kitchens
  or payout accounts) written by Claude Code, or everything typed in admin by hand. Recommended: the seed mode.
- **Sentry** (free tier) now, or logs only at launch.
- **Alerts:** where they go (email, SMS, a paging app), and whether to run Prometheus/Alertmanager on Railway
  (usage cost) or use simpler uptime checks plus Sentry alerts.
