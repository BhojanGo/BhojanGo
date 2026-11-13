# Deploy to Railway

Railway hosts the pilot: one project with a `staging` environment (built from `dev`) and a `production` environment
(built from `main`). Everything is described as code in [`.railway/railway.ts`](../../.railway/railway.ts) (Railway
Infrastructure as Code). **Nothing has been created yet:** no account, no project, no resources. The AWS Terraform
(`infra/terraform`, [aws-setup.md](aws-setup.md)) stays as the path to scale up later.

What's ready and tested without an account:

- **The config** type-checks against Railway's SDK (`railway` 3.17.0), and both environments evaluate to the
  resources below.
- **`make ci-railway`** runs on every `make ci`. It starts the backend the way Railway runs it, then runs G1 (the
  Phase 1 gate, an order from payment to payouts and messages in both countries) against it:
  - Railway's Postgres image with PostGIS added, and no init script;
  - migrations as a separate step before the services start;
  - events on Redis Streams instead of SNS/SQS;
  - the same start commands as on Railway.

## What gets created

| Resource | What | Notes |
|---|---|---|
| `postgres` | Postgres 16 + PostGIS ([`infra/railway/postgis.Dockerfile`](../../infra/railway/postgis.Dockerfile)), volume `postgres-data` (2 GB staging, 10 GB prod) | Railway's managed Postgres has no PostGIS, so this is a service built from Railway's own Postgres image. Staging gets a TCP proxy for seeding and backups |
| `redis` | Railway Redis | Databases: 0 core_api (sessions, OTP, caches), 3 realtime (dispatch, rider positions), 5 the event bus |
| `core-api` | `backend/core_api`, port 8001 | **Runs migrations before each deploy** (`alembic upgrade head` as the pre-deploy command). If a migration fails, the deploy stops and the old version keeps serving |
| `realtime` | `backend/realtime`, port 8004 | WebSockets for tracking and rider offers |
| `worker` | `backend/worker`, port 8006 | Outbox relay, notifications |
| `uploads` | Railway bucket (S3 API) | Delivery and problem photos, documents. Not a volume: volumes are owned by root, and our services run as a non-root user |
| `web`, `admin` | Next.js, port 3000 | `infra/docker/next-app.Dockerfile` |

**Health checks.** Railway sends no traffic to a new deploy until its health check passes, within 120 s:

- **Backends:** `/health/ready`.
  - core_api checks the database and Redis.
  - realtime checks Redis.
  - worker checks the database and that the event bus is set.
- **Web and admin:** `/`.

**Events.** On AWS, the outbox goes to SNS topics, which feed SQS queues. Railway has neither, so `EVENT_BUS=redis`
sends events through one Redis stream instead ([`backend/shared/bus.py`](../../backend/shared/bus.py)). It behaves the
same way:

- Each event is delivered at least once and acknowledged only after it's handled.
- Unacknowledged events are retried after 30 s.
- After 3 deliveries, an event goes to the dead-letter stream `bhojango:events:dlq`.
- The worker gets every event; realtime gets every event except payments.

## Going live: the steps

Steps 1–4 are once per project; 5–8 are once per environment. Allow about an hour for staging.

1. **Account.** Sign up at railway.com with the GitHub account that owns `BhojanGo/BhojanGo`. Pick the Hobby or Pro
   plan; usage-based billing starts here. Install the CLI (`npm i -g @railway/cli`, version 5.49.1 or newer).
2. **Project.** `railway login`, then `railway init --name bhojango` in the repo root. Create the `staging`
   environment (`railway environment new staging`); `production` exists already.
3. **Connect GitHub.** In the dashboard, give Railway access to `BhojanGo/BhojanGo` (Settings → GitHub).
4. **The bucket.** `railway bucket create uploads --region iad`, then `railway bucket credentials --bucket uploads`.
   Keep the output for step 6.
5. **Plan.** `railway link --project bhojango --environment staging`, then `railway config plan`.
   - Expect: 7 services, 1 volume, 1 bucket, 3 groups, all "to add".
   - Check that each backend's Dockerfile path resolved under `backend/`.
6. **Secrets.** Set these as **sealed** variables in the dashboard. They're `preserve()` in the config, so they never
   go in git:

   | Variable | Service | Value |
   |---|---|---|
   | `POSTGRES_PASSWORD` | postgres | `openssl rand -hex 24` |
   | `JWT_PRIVATE_KEY` | core-api | `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048`, the whole PEM. Required outside development; see [security report](../security/report.md#the-local-dev-signing-key). A different key for each environment |
   | `INTERNAL_SERVICE_SECRET` | core-api, realtime, worker (the same value) | `openssl rand -hex 32` |
   | `ALERT_WEBHOOK_TOKEN` | core-api | `openssl rand -hex 24` |
   | `CORS_ORIGINS` | the three backends | `["https://<web domain>","https://<admin domain>"]` |
   | `UPLOADS_BUCKET`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_ADDRESSING_STYLE` | core-api | From step 4: `bucketName`, `endpoint`, `region`, the keys, and `urlStyle` (`virtual` or `path`) |
   | `NEXT_PUBLIC_APP_URL` | web | `https://<web domain>` |

7. **Apply.** Run `railway config apply` and review the plan it prints before confirming. Railway builds and deploys
   everything:
   - **Postgres** first.
   - **core-api:** its pre-deploy migrates the empty database to head.
   - **Then** realtime, worker, web and admin.

   Generate a public domain for core-api, realtime, worker, web and admin (Settings → Networking). Web is built with
   the backends' domains, so **redeploy web and admin once the domains exist**.
8. **Check.**
   - `curl https://<core-api domain>/health/ready` returns `healthy`.
   - Open the web domain. Sign in as a seed customer (staging only) and place an order with the fake payment.
   - Watch the order reach a rider in admin.
   - Staging seed data: run `DATABASE_URL=<the postgres TCP proxy URL, with +asyncpg> uv run python ../tools/seed/seed.py`
     from `backend/`.

**Production differs** in a few ways. Providers are `live`, so it needs the provider keys from
[11_Integration_Setup_Guide.md](../11_Integration_Setup_Guide.md) (Stripe, Razorpay, Twilio, MSG91, SendGrid,
Firebase). It has no TCP proxy and no seed data. Your custom domains are added under Settings → Networking, with DNS
at your registrar. Then **turn on Railway's Postgres backups** for the `postgres-data` volume (daily, keep 7) and do
the restore drill from [backup-restore.md](backup-restore.md) against staging once.

## Every deploy after that

**Merging to `dev` deploys staging; merging to `main` deploys production.** Railway watches the branch and rebuilds
only the services whose files changed (watch patterns in the config). Migrations run in core-api's pre-deploy. A
failed health check keeps the old version serving.

**Changing the infrastructure:** edit `.railway/railway.ts`, run `railway config plan`, review, then
`railway config apply`. Don't change services in the dashboard: the next apply would undo it.

**Rollback:** in the service's Deployments tab, pick the previous deployment and choose Redeploy. That doesn't undo a migration,
so write migrations the previous release can still run on: add a column or table in one release, remove the old one a
release later.

## Environment variables

The config sets every variable below. Values in *italics* are sealed secrets (step 6).

| Variable | Services | Staging | Production |
|---|---|---|---|
| `APP_ENV` | backends | `staging` | `production` |
| `DATABASE_URL` | backends | `postgresql+asyncpg://bhojango:${{postgres.POSTGRES_PASSWORD}}@postgres.railway.internal:5432/bhojango` | same |
| `REDIS_URL` | core-api, worker / realtime | `${{redis.REDIS_URL}}/0` / `…/3` | same |
| `EVENT_BUS`, `EVENT_BUS_REDIS_URL` | backends | `redis`, `${{redis.REDIS_URL}}/5` | same |
| `CORE_API_URL`, `JWKS_URL` | realtime, worker, web, admin | core-api's private address (`core-api.railway.internal:8001`) | same |
| `PAYMENT_PROVIDER` / `SMS_PROVIDER` / `PUSH_PROVIDER` / `EMAIL_PROVIDER` | backends | `fake` / `log` / `log` / `log` | `live` / `live` / `live` / `sendgrid` |
| `STORAGE_PROVIDER` | core-api | `s3` (the bucket) | `s3` |
| `PORT` | all | 8001 / 8004 / 8006 / 3000 | same |
| `NEXT_PUBLIC_CORE_URL`, `…_REALTIME_URL`, `…_WORKER_URL` | web, admin (build time) | `https://${{<service>.RAILWAY_PUBLIC_DOMAIN}}` | same, or your domains |
| *`JWT_PRIVATE_KEY`, `INTERNAL_SERVICE_SECRET`, `ALERT_WEBHOOK_TOKEN`, `POSTGRES_PASSWORD`, bucket keys* | see step 6 | sealed | sealed, different values |
| Provider keys (`STRIPE_*`, `RAZORPAY_*`, `TWILIO_*`, `MSG91_*`, `SENDGRID_API_KEY`, `FIREBASE_*`) | backends | not needed (fakes) | sealed; see the integration guide |

The complete list with defaults is `backend/shared/config.py`; anything not listed keeps its default.

## Not verified until there's an account

These parts can't be checked without an account. Watch them on the first staging deploy:

- **Dockerfile path** under a root directory (`backend/` + `core_api/Dockerfile`). If the plan shows it wrong, use
  the repo-relative `backend/core_api/Dockerfile`.
- **Private networking.** The backends listen on `::` (IPv6) because Railway's private network uses it. Locally they
  listen on `0.0.0.0`.
- **Bucket addressing style:** `S3_ADDRESSING_STYLE` must match the bucket's `urlStyle`.
- **References with a dash in the service name** (`${{core-api.RAILWAY_PUBLIC_DOMAIN}}`). If one doesn't resolve,
  rename the service to `api`.

## Cost (for the decision; nothing is spent)

Railway bills usage. A pilot-sized staging environment is roughly **$5–20/month**: seven small services mostly idle,
Postgres and Redis at a few hundred MB, and a bucket under 1 GB. Production at pilot load is roughly **$30–60/month**.
Check the Usage page after the first week. The AWS path (ECS, RDS Multi-AZ, ElastiCache, ALB) is several times that
before traffic, which is why it's kept for later.
