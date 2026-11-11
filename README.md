# BhojanGo

Production-ready food delivery platform for **USA** and **India** — built like Uber Eats / DoorDash.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Web App | Next.js (App Router, TypeScript, Tailwind): 14 today, 16 from P20 |
| Mobile | Expo + EAS (React Native): SDK 51 today, latest SDK from P16–P19; customer + rider apps |
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
| `make down` | Stop everything (data is kept) |
| `make reset` | Wipe the data volumes and run `make dev` again |
| `make logs` / `make ps` | Follow logs / list containers |

**Ports already in use?** Override any host port, e.g.
`POSTGRES_PORT=15432 REDIS_PORT=16379 make dev` (also `CORE_API_PORT`, `REALTIME_PORT`,
`WORKER_PORT`, `WEB_PORT`, `ADMIN_PORT`, `LOCALSTACK_PORT`).

**Used the old `docker compose` setup before Nov 2026?** Its Postgres volume holds the
pre-P1 schema. Run `make reset` once to start clean.

**Seed logins** (all `BhojanGo123`; admin `BhojanGoAdmin1`): `customer1..5.hyd@example.com`,
`rider1..3.hyd@example.com`, `partner.hyd@example.com`, the same with `.boi` for Boise,
and `admin@example.com`. Markets: India ▸ Telangana ▸ Hyderabad and USA ▸ Idaho ▸ Boise.

**Mobile apps** run on your machine with Expo (Node 24 + pnpm): copy
`apps/customer/.env.example` (or `apps/rider/`) to `.env`, set your computer's LAN IP, then
`pnpm install && pnpm --filter @bhojango/customer start`.

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
| worker | 8006 | Push (FCM) + SMS (Twilio) + email (SendGrid), SQS consumer (was notification-svc) |
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
│   ├── web/              Next.js 14 customer web
│   └── admin/            Next.js 14 admin console
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

The `infra/terraform/` directory contains 15 modules for AWS deployment:

| Module | Resources |
|--------|-----------|
| vpc | VPC, 3 AZs, public/private/database subnets, NAT gateways |
| security_groups | ALB, ECS, RDS, Redis, OpenSearch security groups |
| kms | KMS key with rotation for encryption at rest |
| ecr | Container registries per service (still 7; trimmed to 3 in P4) |
| rds | PostgreSQL 16 (Multi-AZ in prod) |
| redis | ElastiCache Redis 7 (cluster mode in prod) |
| opensearch | OpenSearch with VPC deployment |
| sqs_sns | Event queues + topics + DLQs |
| s3 | Uploads, assets (CloudFront CDN), logs (Glacier lifecycle) |
| cognito | User pool + Google/Apple identity providers |
| secrets | Secrets Manager for all API keys |
| iam | ECS execution + task roles (least-privilege) |
| alb | ALB + target groups + path-based routing |
| ecs | Fargate cluster + task definitions + auto-scaling |
| cloudwatch | Log groups, dashboard, CPU/5xx/RDS alarms |

```bash
# Deploy infrastructure
cd infra/terraform
terraform init
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

- **ci.yml** — Runs on push to `main`: lint, test, build Docker images, push to ECR, deploy to ECS
- **pr-checks.yml** — Runs on PRs: change detection, targeted lint/test/terraform validate, Docker build check

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
10. **Deliver** — Driver updates status through `preparing` -> `picked_up` -> `delivered`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy and PR guidelines.

## License

Proprietary — BhojanGo Inc.
