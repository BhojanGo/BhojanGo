# BhojanGo

Production-ready food delivery platform for **USA** and **India** — built like Uber Eats / DoorDash.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Monorepo | Turborepo + pnpm workspaces |
| Web App | Next.js 14 (App Router, TypeScript, Tailwind) |
| Mobile | Expo 51 (React Native, NativeWind) |
| Admin | Next.js 14 dashboard |
| Backend | Python FastAPI microservices |
| Database | PostgreSQL 16 + Redis 7 |
| Cloud | AWS (ECS Fargate, RDS, ElastiCache, SQS/SNS) |
| Auth | AWS Cognito + JWT + Google + Apple + OTP |
| Payments | Stripe (USA) + Razorpay (India) + wallet |
| Real-time | WebSockets + AWS Location Service |
| Search | OpenSearch |
| API Gateway | Kong (declarative config) |
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

# 3. Start all services via Docker Compose
docker compose up -d

# 4. Run database migrations (wait for Postgres to be healthy first)
cd services/user-svc && alembic upgrade head && cd ../..
cd services/restaurant-svc && alembic upgrade head && cd ../..
cd services/order-svc && alembic upgrade head && cd ../..
cd services/payment-svc && alembic upgrade head && cd ../..
cd services/notification-svc && alembic upgrade head && cd ../..

# 5. Start frontend development servers
pnpm dev
```

## Architecture

```
                        ┌───────────────┐
                        │   Kong API    │
                        │   Gateway     │
                        │   :8888       │
                        └───────┬───────┘
                                │
          ┌─────────┬───────────┼───────────┬──────────┐
          │         │           │           │          │
     ┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼────┐
     │user-svc│ │rest-svc│ │ord-svc │ │pay-svc │ │notif-  │
     │ :8001  │ │ :8002  │ │ :8003  │ │ :8005  │ │svc     │
     └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ │ :8006  │
         │          │          │          │      └───┬────┘
         │     ┌────▼────┐     │          │          │
         │     │OpenSearch│    │          │     ┌────▼────┐
         │     │ :9200   │    │          │     │  SQS    │
         │     └─────────┘    │          │     └─────────┘
     ┌───▼─────────────────────▼──────────▼───┐
     │           PostgreSQL 16                │
     │              :5432                     │
     └────────────────────────────────────────┘
                        │
                   ┌────▼────┐     ┌──────────────┐
                   │ Redis 7 │     │ delivery-svc │
                   │  :6379  │     │    :8004     │
                   └─────────┘     │  WebSocket   │
                                   └──────┬───────┘
                                          │
                                   ┌──────▼───────┐
                                   │DynamoDB Local │
                                   │    :8000      │
                                   └──────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| user-svc | 8001 | Auth, profiles, loyalty |
| restaurant-svc | 8002 | Menus, vendors, ratings, search |
| order-svc | 8003 | Order lifecycle + state machine |
| delivery-svc | 8004 | GPS tracking, WebSockets, ETA |
| payment-svc | 8005 | Stripe + Razorpay + wallet |
| notification-svc | 8006 | Push (FCM) + SMS (Twilio) + email (SendGrid) |
| web | 3000 | Customer web app (Next.js) |
| admin | 3001 | Admin dashboard (Next.js) |
| mobile | 8081 | Expo dev server |
| **Kong** | **8888** | **API Gateway (all routes)** |

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

Each service exposes Swagger UI at `/docs`:

- User Service: http://localhost:8001/docs
- Restaurant Service: http://localhost:8002/docs
- Order Service: http://localhost:8003/docs
- Delivery Service: http://localhost:8004/docs
- Payment Service: http://localhost:8005/docs
- Notification Service: http://localhost:8006/docs

Via Kong gateway: `http://localhost:8888/api/v1/{service}/...`

## Project Structure

```
bhojango/
├── apps/
│   ├── web/              Next.js 14 customer app
│   ├── mobile/           Expo React Native app
│   └── admin/            Next.js 14 admin dashboard
├── services/
│   ├── user-svc/         Auth & profiles (FastAPI :8001)
│   ├── restaurant-svc/   Menus & search (FastAPI :8002)
│   ├── order-svc/        Order lifecycle (FastAPI :8003)
│   ├── delivery-svc/     GPS & WebSockets (FastAPI :8004)
│   ├── payment-svc/      Stripe + Razorpay (FastAPI :8005)
│   └── notification-svc/ Push/SMS/email (FastAPI :8006)
├── packages/
│   ├── types/            Shared TypeScript interfaces
│   ├── ui/               Shared React component library
│   └── config/           Shared ESLint/TS/Prettier config
├── infra/
│   ├── terraform/        AWS IaC (15 modules: VPC, ECS, RDS, etc.)
│   ├── kong/             Kong API Gateway declarative config
│   ├── db/               PostgreSQL init script
│   └── localstack/       LocalStack init (SQS, SNS, S3)
├── .github/
│   └── workflows/        CI/CD pipelines (ci.yml, pr-checks.yml)
├── docker-compose.yml    Full local dev stack
└── .env.example          All environment variables documented
```

## Infrastructure (Terraform)

The `infra/terraform/` directory contains 15 modules for AWS deployment:

| Module | Resources |
|--------|-----------|
| vpc | VPC, 3 AZs, public/private/database subnets, NAT gateways |
| security_groups | ALB, ECS, RDS, Redis, OpenSearch security groups |
| kms | KMS key with rotation for encryption at rest |
| ecr | Container registries per service |
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

1. **Register** — `POST /api/v1/auth/register` (user-svc)
2. **Login** — `POST /api/v1/auth/login` (returns JWT)
3. **Browse** — `GET /api/v1/restaurants?city=NYC` (restaurant-svc)
4. **View Menu** — `GET /api/v1/restaurants/:id/menu`
5. **Create Order** — `POST /api/v1/orders` (order-svc, publishes `order.created`)
6. **Pay** — `POST /api/v1/payments/initiate` (routes to Stripe/Razorpay)
7. **Webhook** — Payment gateway confirms -> publishes `payment.succeeded`
8. **Confirm** — order-svc receives event, updates to `confirmed`
9. **Track** — `WS /ws/track/:orderId` (delivery-svc streams GPS)
10. **Deliver** — Driver updates status through `preparing` -> `picked_up` -> `delivered`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch strategy and PR guidelines.

## License

Proprietary — BhojanGo Inc.
