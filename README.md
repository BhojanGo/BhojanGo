# BhojanGo

Production-ready food delivery platform for **USA** and **India** — built like Uber Eats / DoorDash.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Web App | Next.js 14 (App Router, TypeScript, Tailwind) |
| Mobile | Expo 51 (React Native, NativeWind) |
| Admin | Next.js 14 dashboard |
| Backend | Python 3.12 FastAPI — 3 deployables (core_api, realtime, worker), one uv project |
| Database | PostgreSQL 16 + Redis 7 |
| Cloud | AWS (ECS Fargate, RDS, ElastiCache, SQS/SNS) |
| Auth | AWS Cognito + JWT + Google + Apple + OTP |
| Payments | Stripe (USA) + Razorpay (India) + wallet |
| Real-time | WebSockets + AWS Location Service |
| Search | OpenSearch |
| API Gateway | Kong locally until P3 (then direct calls); AWS ALB + WAF from P4 |
| IaC | Terraform (15 modules) |
| CI/CD | GitHub Actions |
| Observability | CloudWatch + X-Ray + Sentry |

## Prerequisites

- Node.js >= 20
- pnpm >= 9
- Python >= 3.12
- Docker Desktop
- AWS CLI v2 (configured)

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-org/bhojango.git
cd bhojango
pnpm install

# 2. Set up environment
cp .env.example .env
# Edit .env with your API keys (Stripe, Twilio, etc.)

# 3. Start infrastructure (Postgres, Redis, LocalStack, Kong)
docker compose up -d
#    ...or infrastructure + the 3 backend images (core-api runs migrations on start)
docker compose --profile backend up -d --build

# 4. Or run the backend on the host instead (needs uv: https://docs.astral.sh/uv/)
cd backend
uv sync
uv run alembic upgrade head                        # one migration history
uv run uvicorn core_api.main:app --reload --port 8001
uv run uvicorn app.main:app --app-dir realtime --reload --port 8004
uv run uvicorn app.main:app --app-dir worker --reload --port 8006
cd ..

# 5. Start frontend development servers
pnpm dev
```

## Architecture

```
                         ┌───────────────┐
                         │   Kong API    │   (local only; removed in P3)
                         │   Gateway     │
                         └───────┬───────┘
              ┌──────────────────┼──────────────────┐
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
| **Kong** | **8080** | **API Gateway (all routes; `docker compose`)** |

All `/api/v1/...` URLs are the same as before the restructure; only the process
serving them changed.

## Development Tools (Docker)

| Tool | URL | Purpose |
|------|-----|---------|
| Kong Gateway | http://localhost:8888 | Unified API entry point |
| Kong Admin | http://localhost:8444 | Gateway management |
| Adminer | http://localhost:8080 | Database UI |
| LocalStack | http://localhost:4566 | SQS + SNS + S3 (local AWS) |
| OpenSearch | http://localhost:9200 | Search engine |
| DynamoDB Local | http://localhost:8000 | NoSQL for delivery history |

## API Documentation

Each deployable exposes Swagger UI at `/docs`:

- core_api (identity, catalog, orders, payments): http://localhost:8001/docs
- realtime: http://localhost:8004/docs
- worker: http://localhost:8006/docs

Via Kong gateway: `http://localhost:8080/api/v1/...`

> **Kong is on its way out.** Its JWT plugin rejects the tokens core_api issues, so
> authenticated calls through Kong return 401. It will not be fixed: P3 removes Kong
> from the local Docker setup and the apps and tests call core_api (:8001), realtime
> (:8004) and worker (:8006) directly. Production uses AWS ALB + WAF (P4).

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
│   └── docker/           compose.yaml, db/init.sql, kong/, localstack/
├── tools/seed/           Seed data (SQL generators)
├── docs/                 adr/, specs/ (source of truth for P1–P24)
├── .github/workflows/    CI/CD pipelines (ci.yml, pr-checks.yml, security.yml)
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
