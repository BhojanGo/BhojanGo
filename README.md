# BhojanGo

Production-ready food delivery platform for **USA** and **India** — built like Uber Eats / DoorDash.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Web App | Next.js (App Router, TypeScript, Tailwind): 14 today, 16 from P20 |
| Mobile | Expo SDK 58 (React Native 0.88, React 19.3) + EAS; customer, rider and partner apps |
| Admin | Next.js admin console: 14 today, 16 from P21 |
| Backend | Python 3.12 FastAPI — 3 deployables (core_api, realtime, worker), one uv project |
| Database | PostgreSQL 16 + Redis 7 |
| Cloud | AWS (ECS Fargate, RDS, ElastiCache, SQS/SNS) |
| Auth | Custom RS256 JWT + JWKS, phone OTP, Apple + Google (P5; ADR-007): no Cognito |
| Payments | Stripe (USA) + Razorpay (India) + wallet |
| Real-time | WebSockets + AWS Location Service |
| Search | PostgreSQL full-text + pg_trgm + PostGIS (ADR-009); OpenSearch until P4 |
| API Gateway | None locally (direct calls to :8001/:8004/:8006); AWS ALB + WAF from P4 |
| IaC | Terraform (15 modules) |
| CI/CD | GitHub Actions |
| Observability | CloudWatch + X-Ray + Sentry |

Pinned versions and the reasons behind them: [ADR-011](docs/adr/ADR-011-tech-stack.md).

## Run it locally

Everything runs in Docker: Postgres 16 + PostGIS, Redis, LocalStack, the three
backend services (core_api, realtime, worker) and the web and admin apps, with
migrations applied and Hyderabad + Boise seed data loaded.

**You need:** Git, Docker, and GNU make.

| OS | Docker | make |
| --- | --- | --- |
| macOS | Docker Desktop | built in (`xcode-select --install` if missing) |
| Linux | Docker Engine with the Compose v2 plugin | `sudo apt install make` (or your distro's package) |
| Windows | Docker Desktop (WSL 2 backend) | **WSL 2** (recommended): run everything in an Ubuntu shell with `sudo apt install make`. **Git Bash** also works: `winget install ezwinports.make`, then open a new Git Bash window |

**Steps** (tested from a clean clone on Windows 11 + Git Bash, Nov 2026):

```bash
git clone https://github.com/BhojanGo/BhojanGo.git
cd BhojanGo
make dev
```

The first run builds the images (several minutes); later runs take seconds. When it
finishes it prints the test logins and:

```
core_api   http://localhost:8001/docs
realtime   http://localhost:8004/docs
worker     http://localhost:8006/docs
web        http://localhost:3000
admin      http://localhost:3001
```

**Check it works:** sign in as a seeded customer and load restaurants through core_api:

```bash
curl -s -X POST http://localhost:8001/api/v1/auth/login   -H 'Content-Type: application/json'   -d '{"email":"customer1.hyd@example.com","password":"BhojanGo123"}'
curl -s 'http://localhost:8001/api/v1/restaurants?limit=20'   # 10 restaurants, Hyderabad + Boise
```

| Command | What it does |
| --- | --- |
| `make dev` | Build and start everything, run migrations, load seed data |
| `make seed` | Reload the seed data (safe to run again; no duplicates) |
| `make test` | Backend pytest + JS lint/typecheck/test, inside Docker |
| `make ci` | Everything GitHub CI runs (adds migrations up/down/up, `alembic check`, image builds, Terraform validate). **The merge gate.** |
| `make down` | Stop everything (data is kept) |
| `make reset` | Wipe the data volumes and run `make dev` again |
| `make logs` / `make ps` | Follow logs / list containers |

**Ports already in use?** Override any host port, e.g.
`POSTGRES_PORT=15432 REDIS_PORT=16379 make dev` (also `CORE_API_PORT`, `REALTIME_PORT`,
`WORKER_PORT`, `WEB_PORT`, `ADMIN_PORT`, `LOCALSTACK_PORT`).

**Used the old `docker compose` setup before Nov 2026?** Its Postgres volume holds the
pre-P1 schema. Run `make reset` once to start clean.

**Seed logins** (all `BhojanGo123`): `customer1..5.hyd@example.com`,
`rider1..3.hyd@example.com`, `partner.hyd@example.com`, the same with `.boi` for Boise.
Customers can also sign in by phone (`POST /api/v1/auth/send-otp`, then `/auth/phone`):
seed phones `+9190000101..105` and `+120855500101..105` always get code **123456**.
Markets: India ▸ Telangana ▸ Hyderabad (`IN-TG-HYD`) and USA ▸ Idaho ▸ Boise (`US-ID-BOI`).

**Admin logins** (all `BhojanGoAdmin1`), one per role and scope (`shared/authz.py`):
`admin@` super admin · `cm.in@`, `cm.us@` country managers · `ops.hyd@`, `ops.boi@` city ops ·
`support.hyd@`, `support.boi@` support agents · `finance.in@`, `finance.us@` finance ·
`viewer@` read-only (India and USA), all `@example.com`.

**Markets (P6):** countries, states, cities and zones (PostGIS polygons), each draft / beta /
live / paused, with settings that inherit country → state → city. Admin console:
http://localhost:3001/markets (overview, country page with state chips and a city picker, city
page with zone drawing on an OpenStreetMap map). Apps ask `GET /api/v1/markets/locate?lat=&lng=`
whether an address is served. Seeded: Hyderabad (live, 8 zones), Boise (beta, 5 zones), and
Warangal, Visakhapatnam and Vijayawada in setup.

**Rules (P7):** every fee, tax, commission, rider-pay, business rule and promotion is data
built from fixed templates (`GET /api/v1/rules/templates`), scoped to platform, country, state,
city, zone or restaurant. Rules are versioned with start dates; money rules need a second admin
to approve (`cm.in@` makes, `finance.in@` approves); every change is in the audit log.
`GET /api/v1/rules/resolve?country=IN&region=IN-TG&city=IN-TG-HYD` shows what applies where.

**Quotes (P8):** `POST /api/v1/pricing/quote` prices a bag in 8 steps (locate, food, promotions,
fees, taxes, tip, total, split) and returns every bill line plus a token valid for 10 minutes;
`POST /api/v1/orders` with `quote_token` charges exactly that and stores the order's pricing
snapshot (lines, rule versions, who gets what). The Hyderabad worked example (₹638.22) is a unit
test. Admin price simulator (live vs drafts): http://localhost:3001/pricing/simulator.

**Payouts (P13):** restaurants and riders set up payouts (`POST /finance/payout-accounts`: Stripe
Connect Express in the US, Razorpay Route in India, fake locally). Each week a draft payout run is
prepared (or finance makes one); a second finance admin approves and pays it. Restaurant
statements: food + packaging − commission − offers they funded − item refunds that were the
restaurant's fault. Support picks a reason for every item refund: wrong_item, missing_item or
quality (restaurant's fault, comes off its payout less commission); late, damaged_in_transit or
rider_issue (delivery) and goodwill (the platform pays). Every refund is listed on the statement
with its reason. Rider statements: base, distance, waiting and tips per delivery, plus a top-up to
the hourly floor over engaged time (from accepting the offer to drop-off, including the drive to
the restaurant and waiting there). `GET /finance/reconciliation` (JSON or CSV).

**Dispatch and live tracking (P14, realtime):** riders go online (`POST /api/v1/riders/me/online`)
and send GPS to `POST /api/v1/delivery/driver/location`; positions are in a Redis GEO set. When
the restaurant marks an order almost ready (or ready), realtime offers it to the nearest available
rider within 6 km whose GPS is fresh, over `WS /ws/rider`, for the `dispatch_offer_timeout` business
rule (30 s). Pass (`POST /api/v1/offers/{id}/pass`) or a timeout re-offers it to the next nearest;
with nobody free it retries every 15 s. Accept (`POST /api/v1/offers/{id}/accept`) assigns the rider
in core_api through a signed internal call (`/api/v1/internal/orders/...`, HMAC with
`INTERNAL_SERVICE_SECRET`); only the assigned rider can pick up and deliver. Customers (and the
rider, and admins for the city) watch `WS /ws/track/{order_id}`: a snapshot with the trail, then
rider assigned, location + ETA (routing provider), status changes. The TypeScript batch engine runs
in shadow mode (`SHADOW_MODE=true`: publishes nothing, batches can't be accepted); realtime logs the
batches it would have made at `GET /api/v1/dispatch/shadow-batches`.

**Payments and refunds (P12):** `POST /payments/initiate` returns what the app's payment SDK needs:
Stripe PaymentSheet (cards, Apple Pay, Google Pay) in the US, Razorpay Checkout (UPI, cards,
wallets; `POST /payments/razorpay/verify`) in India, a fake equivalent locally. A failed payment
keeps the order's price held and can be retried (`GET /payments/orders/{id}/status`). Admins
refund by item (`POST /payments/orders/{id}/refunds`): each item's price, its discount share and
its matching tax; support agents up to a per-order limit (₹500 / $25, a business rule).
Customers can't refund themselves.

**Order flow (P11):** `pending_payment → placed → accepted → preparing → almost_ready → ready →
picked_up → delivered` (or `cancelled`). An order needs a quote and is placed only when its
payment succeeds (`POST /api/v1/payments/initiate` takes the amount from the order). Unpaid
orders cancel after 10 minutes and orders the restaurant doesn't accept within 3 minutes are
cancelled and refunded (business rules; core_api's sweeper). Events go through a transactional
outbox that the worker relays to SNS → SQS. Webhooks are idempotent (by event id and status).

**Menu and hours (P10):** option groups with min/max picks and prices (Size 1..1, Add-ons
0..3), weekly store hours (lunch/dinner splits, past midnight) with holiday overrides, "sold out
today", default prep time, and FSSAI licences for India (an expired licence pauses the listing
automatically). Quotes refuse closed restaurants, out-of-hours cities and sold-out items, so
outside 07:00–23:30 IST / 08:00–23:00 Boise a local quote says when deliveries run.

**Tax (P9):** India GST comes from rules (5% on food and packaging, 18% on platform fees). US
sales tax comes from the tax provider: Stripe Tax when `STRIPE_SECRET_KEY` is set, otherwise a
local stand-in with illustrative state rates (Idaho 6%; not tax advice). Every tax line in a
quote and in the customer's bill (`GET /api/v1/pricing/orders/{id}/bill`) shows its rate and
what it was charged on.

**Sign-in (P5):** email + password, phone OTP, Sign in with Apple and Google (ID tokens
verified against the providers' keys; set `GOOGLE_CLIENT_IDS` / `APPLE_CLIENT_IDS`).
Tokens are RS256: 15-minute access tokens and rotating refresh tokens (a reused refresh
token ends that session). Public keys: `GET /.well-known/jwks.json`. Locally a signing
key is created on first start and kept on the `jwt_keys` volume; production reads
`JWT_PRIVATE_KEY` from Secrets Manager. Delete account: `DELETE /api/v1/users/me`.

**No accounts needed.** Every external provider has a local stand-in, so nothing
needs a card or a sign-up (`backend/shared/providers`, `payments/service/gateways.py`):

| Provider | Locally | How to see it |
| --- | --- | --- |
| Payments (Stripe, Razorpay) | Fake gateway with signed webhooks | Payments succeed after 2 s; `payment_method_id` `pm_card_chargeDeclined` fails; or `POST /api/v1/payments/fake/{id}/complete` |
| SMS / OTP | Printed in the worker log | `make logs` → `[SMS to +91…] Your BhojanGo verification code is: …`. Seed phones (`+9190000…`, `+120855500…`) always get **123456** |
| Email | Mailpit | http://localhost:8025 |
| Push | Printed in the worker log | `[PUSH to 1 device(s)] …` |
| US sales tax (Stripe Tax) | Local stand-in with illustrative state rates (Idaho 6%) | "Idaho sales tax" line on Boise quotes |
| Maps / ETA | Straight-line distance × 1.3 road factor, 25 km/h | `GET /api/v1/delivery/{order_id}/eta` on realtime |
| Storage, queues | LocalStack (S3, SQS, SNS) | http://localhost:4566 |

Real keys plug in later through env vars (`PAYMENT_PROVIDER=live`, `SMS_PROVIDER=live` (Twilio US, MSG91 India),
`EMAIL_PROVIDER=sendgrid`, `PUSH_PROVIDER=live` (Expo, FCM or APNs per device)); `APP_ENV=production` refuses the local stand-ins.

**Messages (P15, worker):** order, payment and payout events become messages in the person's
language (`preferred_locale`: English, Hindi or Telugu), in the brand voice (plain, specific, warm;
times and amounts, no emoji). Push goes to every registered device (`POST /api/v1/notifications/device-token`
with `provider` expo | fcm | apns, or worked out from the token); dead tokens are dropped. Email
(Mailpit locally, SendGrid live) for the confirmation, receipt, cancellations, refunds and payouts.
SMS only as a fallback when push reached no device, for the moments that matter (rider on the way,
cancellation, failed payment, a new order for a restaurant without the app); India SMS uses a DLT
template per message and language (`MSG91_TEMPLATE_IDS`, keys like `order_picked_up_hi`). Each
message is sent once per event, person and channel, and kept in the in-app inbox.

**Mobile apps** are Expo development builds (not Expo Go):

1. `make apk APP=customer` builds the Android debug APK in Linux (Docker), into `.apk/`. Windows path limits and OneDrive locks break React Native's native build on the host. Rebuild only when native packages change.
2. `adb -s emulator-5554 install -r .apk/customer-debug.apk`, then `adb -s emulator-5554 reverse tcp:8081 tcp:8081` (do the same for 8001, 8004 and 8006 to reach the backend).
3. `pnpm --filter @bhojango/customer start --dev-client` serves the JavaScript.
4. Maestro flows are in `apps/<app>/.maestro/`: `maestro --device emulator-5554 test apps/customer/.maestro`.
5. iOS: `pnpm turbo export:check` bundles both platforms (also in `make ci`). Device testing waits for a Mac.

**Design system (P16):** the tokens in `@bhojango/ui/tokens` are the one source. `@bhojango/ui` holds the web components and Tailwind preset; `@bhojango/mobile-core` holds the same components in React Native. Galleries: http://localhost:3000/design and `bhojango://gallery` in the customer app. App icons, splash screens and favicons come from `docs/design/logo` via `pnpm brand:assets`.

For hot reload on the backend or web apps, see CONTRIBUTING (run the databases in
Docker and the code on your machine). There is no API gateway locally: apps and tests
call core_api (:8001), realtime (:8004) and worker (:8006) directly.

## Architecture

```
        apps (customer, rider, web, admin) call each service directly;
        in AWS an ALB + WAF routes by path (P4)
              │                  │                  │
      ┌───────▼────────┐  ┌──────▼───────┐  ┌───────▼───────┐
      │   core_api     │  │   realtime   │  │    worker     │
      │    :8001       │  │    :8004     │  │    :8006      │
      │ identity       │  │ rider GPS,   │  │ notifications │
      │ catalog        │  │ tracking WS, │  │ (HTTP + SQS   │
      │ orders         │  │ ETA,         │  │  consumer)    │
      │ payments       │  │ earnings     │  │               │
      └───────┬────────┘  └──────┬───────┘  └───────┬───────┘
              │                  │                  │
      ┌───────▼──────────────────▼──────────────────▼───────┐
      │   PostgreSQL 16 (one Alembic history)   Redis 7     │
      │   OpenSearch (catalog search)   SQS/SNS   DynamoDB  │
      └─────────────────────────────────────────────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| core_api | 8001 | identity (auth, profiles, addresses), catalog (restaurants, menus, search), orders (state machine, fees), payments (Stripe, Razorpay, wallet) |
| realtime | 8004 | Rider GPS, tracking WebSocket, ETA, earnings (was delivery-svc) |
| worker | 8006 | Messages in en/hi/te: push (Expo/FCM/APNs), SMS (Twilio US, MSG91 India), email (SendGrid); outbox relay; SQS consumer |
| web | 3000 | Customer web app (Next.js) |
| admin | 3001 | Admin dashboard (Next.js) |
| customer | 8081 | Expo dev server — BhojanGo app (`com.bhojango.app`) |
| rider | 8081 | Expo dev server — BhojanGo Rider app (`com.bhojango.rider`) |

All `/api/v1/...` URLs are the same as before the restructure; only the process
serving them changed.

## Development Tools (Docker)

| Tool | URL | Purpose |
|------|-----|---------|
| PostgreSQL 16 + PostGIS | localhost:5432 (`bhojango` / `bhojango_dev`) | Database |
| Redis 7.4 | localhost:6379 | Cache, tokens, rider locations |
| LocalStack | http://localhost:4566 | SQS + SNS + S3 (local AWS) |
| Mailpit | http://localhost:8025 (SMTP :1025) | Inbox for every email the backend sends |

## API Documentation

Each deployable exposes Swagger UI at `/docs`:

- core_api (identity, catalog, orders, payments): http://localhost:8001/docs
- realtime: http://localhost:8004/docs
- worker: http://localhost:8006/docs

There is no gateway locally; call the services directly.

## Project Structure

Target layout and the rules behind it: [docs/specs/01-structure.md](docs/specs/01-structure.md).

```
bhojango/
├── apps/
│   ├── customer/         Expo · BhojanGo customer app
│   ├── rider/            Expo · BhojanGo Rider app
│   ├── web/              Next.js 16 customer web
│   └── admin/            Next.js 16 admin console
├── backend/              Python 3.12 · one uv project (pyproject.toml, uv.lock)
│   ├── core_api/         deployable 1 · FastAPI
│   │   └── modules/      identity, catalog, orders, payments
│   │                     (each: api/ service/ repository/ models/ schemas/)
│   ├── realtime/         deployable 2 · GPS, tracking WebSocket, ETA
│   ├── worker/           deployable 3 · notifications + SQS; batch-engine/ (TS, reference)
│   ├── shared/           config, DB session, Redis, auth, events, logging, middleware
│   └── migrations/       one Alembic history (alembic.ini in backend/)
├── packages/
│   ├── mobile-core/      Auth store, API client, cart for the Expo apps
│   ├── types/            Shared TypeScript interfaces (replaced by api-client in P17)
│   ├── ui/               Shared React component library
│   └── config/           Shared ESLint/TS/Prettier config
├── infra/
│   ├── terraform/        AWS IaC
│   └── docker/           compose.yaml (profiles infra/backend/all), Dockerfiles, db/, localstack/
├── tools/seed/           Hyderabad + Boise seed data (idempotent; make seed)
├── docs/                 adr/, specs/ (source of truth for P1–P24)
├── .github/workflows/    CI/CD pipelines (ci.yml, pr-checks.yml, security.yml)
├── Makefile              make dev / seed / test / down / reset
├── docker-compose.yml    Includes infra/docker/compose.yaml
└── .env.example          All environment variables documented
```

### Backend tests

```bash
cd backend
uv run pytest core_api
uv run pytest realtime   # realtime and worker each have an `app` package,
uv run pytest worker     # so run them as separate invocations

# Migrations: models and migrations must match (CI fails otherwise)
uv run alembic check
# API against a migrated + seeded Postgres and Redis (what CI runs)
RUN_MIGRATED_DB_TESTS=1 uv run pytest core_api/integration
```

## Infrastructure (Terraform)

AWS per ADR-011, in `infra/terraform/`:

```
envs/staging, envs/prod   one root per environment (S3 state + DynamoDB lock)
modules/platform          everything an environment needs, built from:
  vpc · security_groups · kms · ecr · rds · redis · sqs_sns · s3
  secrets · iam · alb (+ WAF) · ecs · cloudwatch
bootstrap/                one-time: state bucket, lock table, GitHub OIDC roles
```

| Piece | What |
|--------|-----------|
| Compute | ECS Fargate: core-api :8001, realtime :8004, worker :8006 |
| Edge | ALB + AWS WAF; `/ws`, `/api/v1/delivery`, `/api/v1/drivers`, `/api/v1/riders`, `/api/v1/offers`, `/api/v1/dispatch` → realtime, `/api/v1/notifications` → worker, everything else → core-api |
| Data | RDS PostgreSQL 16 + PostGIS (Multi-AZ in prod), ElastiCache Redis 7 (TLS + AUTH) |
| Messaging / storage | SQS + SNS, S3 (+ CloudFront for assets) |
| Secrets | Secrets Manager; third-party keys are set by hand, never in Terraform state |
| Observability | CloudWatch logs, dashboard, alarms |

First-time setup (accounts, state bucket, OIDC roles, GitHub variables) is in
[docs/runbooks/aws-setup.md](docs/runbooks/aws-setup.md). Infrastructure changes go through
a PR (`terraform plan` runs on it) and the **Terraform apply** workflow.

## CI/CD

GitHub Actions in `.github/workflows/`, authenticating to AWS with GitHub OIDC (no stored keys):

| When | What runs |
| --- | --- |
| Pull request | Only the areas that changed: frontend lint/typecheck/test, backend tests, migrations + Docker builds (`backend-checks.yml`), Terraform fmt/validate, and `terraform plan` per environment |
| Merge to `dev` | All checks, then build and push images to ECR, run migrations as a one-off ECS task, deploy to **staging** (`ci.yml` → `deploy.yml`) |
| Tag `v*` | Deploy that commit to **prod** after a manual approval in the `production` environment (`release.yml`) |
| Manual | **Terraform apply** for staging or prod (`terraform-apply.yml`) |

Until AWS is connected (runbook steps 1–4), the AWS jobs are skipped, not failed.

## E2E Flow

1. **Register** — `POST /api/v1/auth/register` (core_api · identity)
2. **Login** — `POST /api/v1/auth/login` (returns JWT)
3. **Browse** — `GET /api/v1/restaurants?city=NYC` (core_api · catalog)
4. **View Menu** — `GET /api/v1/restaurants/:id/menu`
5. **Create Order** — `POST /api/v1/orders` (core_api · orders, publishes `order.created`)
6. **Pay** — `POST /api/v1/payments/initiate` (routes to Stripe/Razorpay)
7. **Webhook** — Payment gateway confirms -> publishes `payment.succeeded`
8. **Confirm** — orders receives event, updates to `confirmed`
9. **Track** — `WS /ws/track/:orderId` (realtime streams GPS)
10. **Dispatch** — almost ready → offered to the nearest rider (`WS /ws/rider`), accept assigns them
11. **Deliver** — the assigned rider moves it `picked_up` -> `delivered`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy and PR guidelines.

## License

Proprietary — BhojanGo Inc.
