# Deploy to Railway

Railway hosts BhojanGo. Project **BhojanGo** has three environments:

- **QA** (built from `dev`): live since 2026-11-14.
- **staging** (from `dev`): not created yet.
- **production** (from `main`): not created yet.

Everything is described as code in [`.railway/railway.ts`](../../.railway/railway.ts) (Railway Infrastructure as Code).
The AWS Terraform (`infra/terraform`, [aws-setup.md](aws-setup.md)) stays as the path to scale up later.

This runbook was checked against Railway's docs and CLI 5.54.1 on 2026-11-14, while QA was built. Steps that differed
from the first draft are marked **(corrected)**. Lessons 45–55 in the [PLAYBOOK](../PLAYBOOK.md) explain why.

## What gets created

| Resource | What | Notes |
|---|---|---|
| `postgres` | Postgres 16 + PostGIS ([`infra/railway/postgis.Dockerfile`](../../infra/railway/postgis.Dockerfile)) on volume `postgres-data` (2 GB; 10 GB in production, region pinned) | Railway's Postgres template has no PostGIS, and Railway doesn't add extensions to it. So Postgres is a service built from Railway's own image. No public port in QA or production; staging gets a TCP proxy |
| `redis` | Railway Redis | Databases: 0 core_api (sessions, OTP, caches), 3 realtime (dispatch, rider positions), 5 the event bus. No TCP proxy |
| `core-api` | `backend/core_api`, port 8001, public domain | **Runs migrations before each deploy** (`alembic upgrade head`, pre-deploy). The pre-deploy runs in its own container with the service's variables and the private network. If it fails, the deploy stops and the old version keeps serving |
| `realtime` | `backend/realtime`, port 8004, public domain | WebSockets for tracking and rider offers |
| `worker` | `backend/worker`, port 8006, **private only** **(corrected)** | Outbox relay, notifications, batching. No app calls it from outside |
| `uploads` | Railway bucket (S3 API), region `sjc` **(corrected: a region is required)** | Delivery and problem photos, documents. Private (Railway buckets can't be public); the API hands out presigned URLs. Reached over the public endpoint (buckets aren't on the private network) |
| `web`, `admin` | Next.js, port 3000, public domains | `infra/docker/next-app.Dockerfile`. Outside production they **sleep when idle** (Railway "Serverless") |

**Health checks.** Railway sends no traffic to a new deploy until its health check passes, within 120 s. The check
is used only at deploy time; Railway doesn't watch it after that.

- **Backends:** `/health/ready`.
  - core_api checks the database and Redis.
  - realtime checks Redis.
  - worker checks the database and that the event bus is set.
- **Web:** `/`.
- **Admin:** `/login` **(corrected)**. Admin's `/` redirects to sign-in (307), and only a 200 counts as healthy.

**Networking.** Only web, admin, core-api and realtime have public domains. Service-to-service traffic uses
`<service>.railway.internal`, which is encrypted (WireGuard), so it's `http://`.

- The backends listen on **`0.0.0.0`** **(corrected)**. The first draft used `--host ::`, but asyncio sets `IPV6_V6ONLY`
  on a socket bound to `::`. uvicorn then takes IPv6 only, and Railway's health check and edge (IPv4) can't reach it.
- Environments created after 2025-10-16 resolve `*.railway.internal` to IPv4 as well as IPv6. QA is one of them. An
  older, IPv6-only environment would need a dual-stack socket instead.

**The client's address** **(corrected)**. Behind Railway, every request reaches the app from Railway's proxy
(`100.64.x.x`, `10.x`), and `X-Forwarded-For` ends in Railway edge hops, not the client.

- Rate limits keyed on the socket address (sign-in 10 a minute, OTP 3 a minute) were therefore shared by every user.
- Railway's edge puts the client's address in **`X-Real-IP`** and overwrites any the client sends.
- So the backends set `CLIENT_IP_HEADER=X-Real-IP` ([`shared/client_ip.py`](../../backend/shared/client_ip.py)).
- Leave it unset anywhere the app can be reached other than through such a proxy.

**Events.** On AWS, the outbox goes to SNS topics, which feed SQS queues. Railway has neither, so `EVENT_BUS=redis`
sends events through one Redis stream ([`backend/shared/bus.py`](../../backend/shared/bus.py)). It behaves the same way:

- Each event is delivered at least once and acknowledged only after it's handled.
- Unacknowledged events are retried after 30 s.
- After 3 deliveries, an event goes to the dead-letter stream `bhojango:events:dlq`.

**The fakes in production.** No backend starts in an environment named production with any of these:

- a payment provider other than `live` (`auto` falls back to the fake when there are no keys);
- fake payouts;
- the fixed OTP for seed phones (`OTP_FIXED_CODE` must be set to `""`);
- the fixed delivery PIN for seed phones (`DELIVERY_PIN_FIXED` must be set to `""`).

"Named production" is checked against `APP_ENV` and Railway's own `RAILWAY_ENVIRONMENT_NAME`
([`shared/config.py`](../../backend/shared/config.py)).

## Cost control

- **Spending limits belong to the workspace, not the project (corrected).**
  - A hard limit takes *every* workload in the workspace offline.
  - The minimum is $10. Changing it needs workspace-admin rights.
  - Our workspace also runs other live projects (Pro plan; limits on 2026-11-14: soft $20, hard $50). A $20 hard
    limit would have stopped them mid-month, so it was left as it was.
  - To change it: railway.com → workspace → **Usage** → **Usage limits** (Compute).
- **QA is capped per service instead.** Each service has a CPU and memory ceiling (`limitOverride` in the config):
  - core-api and postgres: 1 vCPU, 1 GB;
  - realtime, worker, web and admin: 0.5 vCPU, 0.5 GB.
- **Web and admin sleep** after about 10 minutes without outbound traffic, and wake on the next request.
  - The first request after sleep took **2.5 s** (web) and **1.4 s** (admin).
  - The backends don't sleep: they run timers (dispatch retries, the outbox relay, payment and acceptance timeouts)
    that must keep going.
- **Measured cost** (Railway metrics, 2026-11-14, including a k6 smoke and the UI suites): about **$7 a month** for
  the seven QA services. Postgres $1.81, core-api $1.62, worker $1.14, realtime $0.89, web $0.72, admin $0.48,
  redis $0.33. The bucket and volumes are a few cents. The Pro plan's subscription is the workspace's, not QA's.
  Check the Usage page after the first week.

## Building an environment (what was done for QA)

You need:

- the Railway CLI, 5.42.1 or newer;
- Node, for the IaC SDK;
- a **project token** for the environment (project → Settings → Tokens). Keep it outside the repo.
- for usage queries only, a workspace token.

1. **Project and environment.** Create them in the dashboard. For QA: project `BhojanGo`, environment `QA`.
   Give Railway's GitHub app access to `BhojanGo/BhojanGo`.
2. **The IaC SDK** **(corrected: it wasn't pinned anywhere).** Run `npm install` in `.railway/`. It's pinned in
   `.railway/package.json` and kept outside the pnpm workspace.
   - On Windows, run the CLI's `railway.exe` without the `_` variable: `env -u _ railway.exe config plan`.
   - Why: the SDK checks the CLI version by running `$_`, which in Git Bash is npm's shell shim, and the check fails.
3. **Plan, then apply.** With `RAILWAY_TOKEN` set to the environment's project token, from the repo root:
   - Run `railway config plan`, then `railway config apply --yes` once the plan shows only additions.
   - Expect 7 services, 1 volume, 1 bucket and 3 groups.
4. **The bucket into the environment** **(corrected).** `config apply` creates the bucket at project level but doesn't
   deploy it into the environment, so the next plan still says "Create bucket uploads". Commit an environment patch
   once (GraphQL `environmentPatchCommit`):
   `{"buckets": {"<bucket id>": {"region": "sjc", "isCreated": true}}}`. Then the plan is clean.
5. **Public domains, before the first frontend build** **(corrected).**
   - Generate a domain for each of: `railway domain --service core-api --port 8001`, `realtime --port 8004`,
     `web --port 3000` and `admin --port 3000`.
   - Web and admin bake `NEXT_PUBLIC_*` in at build time. A build without the domains fails
     (`new URL("https://")`), so redeploy web and admin after this step.
   - CORS and the web's own URL are Railway references to these domains, not hand-set values.
6. **Secrets, as sealed variables** **(corrected: the CLI can't seal; the dashboard or the API can).**
   - Generate each value and commit it through `environmentPatchCommit` with `isSealed: true`. A sealed value can't
     be read back by anyone, including `railway variables` and `railway run`, and isn't copied to PR environments.
   - **Never** use the SDK's `ctx.randomString()` for a secret: it's a hash of the environment name and a label.

   | Variable | Service | Value |
   |---|---|---|
   | `POSTGRES_PASSWORD` | postgres | 24 random bytes, hex |
   | `JWT_PRIVATE_KEY` | core-api | an RSA 2048 PEM, a new one for each environment |
   | `INTERNAL_SERVICE_SECRET` | core-api, realtime, worker (the same value) | 32 random bytes, hex |
   | `ALERT_WEBHOOK_TOKEN`, `FAKE_PAYMENT_WEBHOOK_SECRET` | core-api | random |
   | `UPLOADS_BUCKET`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_ADDRESSING_STYLE` | core-api | `railway bucket credentials --bucket uploads --json`. `urlStyle` comes back as `virtual-host` **(corrected: not `virtual`)**; the backend maps it to boto3's `virtual` |
   | `CORS_ORIGINS`, `NEXT_PUBLIC_APP_URL` | production only | the custom domains (QA and staging use Railway references) |

7. **Redeploy in order:** postgres → core-api (its pre-deploy migrates to head) → realtime, worker → web, admin.
   After that, merging to `dev` redeploys QA by itself. Watch patterns rebuild only the services whose files changed.
8. **Seed (QA)**, from inside the private network: `tools/railway/qa-runner.sh job reset` (below) rebuilds the
   database and loads the base seed and the demo data ([`tools/seed/demo.py`](../../tools/seed/demo.py): 16 kitchens
   a city with full menus, offers, demo customers with order history and an order on its way).
   - Kitchen ratings come only from that history: each demo kitchen gets months of delivered demo orders
     ([`tools/seed/demo_history.py`](../../tools/seed/demo_history.py)), a share of them rated, and its rating and
     count are recomputed as the ratings service does (kitchens new this week have fewer than 5: "New"). Those
     orders show up in payout drafts and reconciliation like any delivered order (fake payout provider on QA); the
     seed never adds one to a week a payout run already covers. The demo seed (and the `demo` job) refuse production.
   - Every account gets a **random password**.
   - The logins go to the private bucket and from there to a file outside the repo. They're never printed or logged.
   - Seed phones (`+1208555…`, `+9190000…`) sign in with OTP `123456` in QA only.

**Production differs:**

- Providers are `live`; it needs the provider keys from
  [11_Integration_Setup_Guide.md](../11_Integration_Setup_Guide.md).
- `OTP_FIXED_CODE` and `DELIVERY_PIN_FIXED` are `""`.
- No seed data, and no sleeping.
- Custom domains (Settings → Networking).
- Postgres backups on: daily, keep 7. Do the restore drill from [backup-restore.md](backup-restore.md) once.

## QA gets demo data and read-only checks, never tests

**Tests never write to QA or production.** They run locally (`make dev`, `make ci`) and in CI. Everything that creates
data through the APIs or the database calls the shared guard [`tools/target_guard.py`](../../tools/target_guard.py)
first and refuses (a clear message, exit 3) when its target is an environment named `qa` or `production`:

- the target API's public `/health` reports `environment` (core-api, realtime and worker; `APP_ENV`, or Railway's own
  name when that is QA or production). A hosted API that doesn't say is refused too;
- a process that opens the database (the backend conftests) checks its own `APP_ENV` and `RAILWAY_ENVIRONMENT_NAME`,
  and `DATABASE_URL` must point at a local or compose host (any dotted host, such as `*.railway.internal`, is remote).

Guarded: the backend integration suites (`core_api/integration`, `worker/tests/integration`) and G1 (`backend/e2e`),
`tools/web/e2e_web.py`, `tools/web/screens_v2.py`, `tools/web/third_city.py`, `tools/admin/e2e_admin.py`,
`tools/mobile/hours.py`, k6 (`tools/load/pilot.js` stops in `setup()`), the soak (`tools/soak/setup.py`, `soak.py`,
`batching_switch.py`), `tools/railway/ws_check.py`, `restart_check.py`, `playwright-qa.sh`, `maestro-qa.sh`, and the
QA runner's `g1` and `integration` jobs. `make ci-guard` runs the guard's unit tests.

What QA gets instead: the demo data (below), and read-only checks: the `checks` job, a browser, `curl` of `/health`.

### The QA runner

Postgres and Redis have no public port, and sealed secrets can't be read back. `railway ssh` needs a personal login,
not a project token. So jobs that need the database run **inside** the environment, in a temporary service:

- `qa-runner`: [`infra/railway/qa-runner.Dockerfile`](../../infra/railway/qa-runner.Dockerfile), driven by
  [`tools/railway/qa-runner.sh`](../../tools/railway/qa-runner.sh).
- It reaches Postgres, Redis and the worker through Railway references (`${{postgres.POSTGRES_PASSWORD}}`, …).
- It runs one job per deploy, prints a result line and exits (restart policy NEVER, so it costs nothing between jobs).
- Deploy it from the commit QA runs (`dev`), so its migrations match core-api's.
- Delete it when done (`tools/railway/qa-runner.sh delete`).

| Job | What |
|---|---|
| `reset` | Rebuild QA's database from scratch: other sessions closed, the `public` schema dropped and recreated (PostGIS re-created by `infra/docker/db/init.sql`), migrations to head, Redis database 0 cleared (sessions, caches), then the base seed and the demo seed with random passwords; the logins go to the private bucket. **Refused unless `RAILWAY_ENVIRONMENT_NAME` is `QA` (any case) and `APP_ENV` is `qa`.** Everyone signs in again afterwards |
| `seed` | The base seed (Hyderabad + Boise) with random passwords |
| `demo` | The demo seed on top; its logins are added to the same bucket file |
| `checks` | Read-only: each backend's `/health` (with its `environment`) over the private network; `alembic current`/`heads`/`check` against the QA database |
| `hours` | Removed (it rewrote QA data for tests; tests never write to QA). Exits 3 |
| `g1`, `integration` | Refused (exit 3): they write test data. They run in `make ci` (`ci-e2e`, `ci-migrations`) and in CI |

The demo seed refuses production by itself (`APP_ENV` or `RAILWAY_ENVIRONMENT_NAME` named production). `make dev`
runs it after the base seed (`make seed`); CI and G1 don't.

### The demo rider (QA and `make dev` only)

The worker's demo rider simulator ([`backend/worker/app/demo_sim`](../../backend/worker/app/demo_sim)) keeps one
demo order on its way in each demo city. On QA it is on through `DEMO_RIDER_SIM=1` on the worker (QA environment
only, in `.railway/railway.ts`); `make dev` turns it on in compose. It runs only when `APP_ENV` is `local`,
`development`, `dev` or `qa`, and production refuses to start with the flag set.

- **Whose orders:** only the demo seed's customers (`demo<N>.<city>@example.com`), and of those only the order the
  demo seed left on its way and the ones the simulator placed (Redis set `demo_sim:orders`). An order you place
  yourself with a demo account is left alone.
- **How:** everything through the normal APIs, signed in like the apps (phone code; seed phones have the fixed code
  outside production). A few minutes after the last delivery, `demo1.<city>` orders a past order again from a kitchen
  that is open (reorder, quote, order, fake card payment); the kitchen's owner accepts, cooks and marks it almost
  ready; the demo rider goes online about 1.5 km away, takes realtime's offer, rides to the kitchen and on to the door
  at 18-25 km/h along a path with a few turns (no routing service), a GPS fix every 4 s to
  `/delivery/driver/location`; the kitchen hands it over as the rider arrives; the rider picks it up and delivers it
  with the PIN from the customer's tracking screen, then goes offline. Tracking, ETA and the usual order
  notifications follow on their own. Outside the kitchens' and the city's hours there is no order on its way.
- **The order the demo seed writes** (already picked up) is finished the same way; its fixes reach the tracking page
  through `/delivery/{id}/eta` (its rider was never made busy by dispatch, so no live WebSocket position for that
  first one).
- **Logs:** `demo_rider_sim` (on, off or refused, at start), `demo_order_placed`, `demo_rider_accepted`,
  `demo_order_delivered`, and `demo_rider_sim_step_failed` with the reason.
- **Don't** sign in as `rider.demo.<city>` in the rider app on QA while it runs; you'd be riding the same account.

From a workstation, against a hosted environment that is neither QA nor production (staging, once it exists):
[`tools/railway/playwright-qa.sh`](../../tools/railway/playwright-qa.sh) (web and admin Playwright),
[`tools/railway/maestro-qa.sh`](../../tools/railway/maestro-qa.sh) (Maestro; dev builds use
[`tools/mobile/env-profile.sh`](../../tools/mobile/env-profile.sh)),
[`tools/railway/ws_check.py`](../../tools/railway/ws_check.py) (live tracking through the proxy, 150 s idle),
[`tools/railway/restart_check.py`](../../tools/railway/restart_check.py) (restart every service, nothing lost) and
`SCALE=0.1 tools/load/pilot.js` (k6 at 1× pilot peak). Pointed at QA or production they stop at the guard.

Notes:

- **Maestro's partner flows need the tablet emulator** (`bhojango_tablet`); on a phone the kitchen app's forms run
  off the screen.
- **Maestro writes every `-e` value into its logs**, so `maestro-qa.sh` redacts the passwords afterwards
  (`redact_logins.py`).
- **The OTP limit is 3 a minute per client address**, now the real one. Don't run two UI suites from one machine at
  once.

### QA test results (2026-11-14)

Run once while QA was being built, before the rule above: QA no longer gets the G1, integration, Playwright,
Maestro, WebSocket, restart or k6 runs that wrote test data (`reset` clears what they left).

URLs: web https://web-qa-3fd3b3f8.up.railway.app, admin https://admin-qa-df130aa4.up.railway.app,
API https://core-api-qa-03da2a58.up.railway.app (realtime https://realtime-qa-2a1e9d2e.up.railway.app).

| Check | Result |
|---|---|
| `/health` and `/health/ready`, every service | 200 healthy: public for core-api and realtime, private for all three backends; web `/` and admin `/login` 200 |
| Migrations | `alembic current` = `0024_order_batch_position (head)`; `alembic check`: no new operations |
| G1, against the QA API | 2 passed (Hyderabad, Boise) |
| Integration suites on QA's Postgres and Redis | 771 passed (API) + 7 (worker), with migrations up/down/up and the seed twice |
| Playwright | web 34/34, admin 43/43 |
| Live tracking WebSocket | connect 0.37 s; 5 positions; 150 s idle with no client pings, not dropped; next position 0.25 s after it was sent |
| Maestro | customer 7/7, rider 6/6, partner 5/5 |
| k6, 5 min at 1× pilot peak | 2,601 requests, 0 failed; p95 menu 88 ms, kitchens 85, quote 103, order 95, payment 73, rider ping 80, web home 140, WebSocket connect 247 ms. Local `make dev` at the same load: 35, 11, 74, 46, 26, 9, 35, 49 ms. The difference is the internet round trip and TLS; core-api's own p95 on Railway is 23 ms |
| Security | HTTP → HTTPS (301) everywhere; HSTS, CSP, frame, nosniff, referrer and permissions headers. CORS allows only the QA web and admin origins. Errors are structured, with no stack traces. ZAP baseline: 0 FAIL (web 64 PASS / 4 WARN, admin 62 / 6, API 64 / 4). No TCP proxy on any service; `*.railway.internal` doesn't resolve publicly |
| Restart each service | postgres, redis, core-api, realtime, worker, web, admin: healthy within about 15 s. The order was kept, the session refreshed (refresh tokens survived Redis's restart), and a status change made during each backend restart reached the customer's tracking socket |
| Cold start (sleeping frontends) | web 2.9 s, admin 1.8 s for the first request; 0.2–0.3 s after that |
| Cost | about $7 a month for the seven services (Railway metrics); the workspace limit is unchanged (see Cost control) |

## Every deploy after that

**Merging to `dev` deploys QA (and staging); merging to `main` deploys production.** Migrations run in core-api's
pre-deploy. A failed health check keeps the old version serving.

**Changing the infrastructure:** edit `.railway/railway.ts`, run `railway config plan`, review it, then
`railway config apply`. Don't change services in the dashboard: the next apply would undo it.

**A plan deletes any service in the environment that isn't in the config**, for example a `qa-runner` left running.
Read the "Delete service" lines before applying. While the runner exists, set a variable directly
(`railway variable set`) and apply after the runner is gone.

**Rollback:** in the service's Deployments tab, pick the previous deployment and choose Redeploy. That doesn't undo
a migration, so write migrations the previous release can still run on.

## Environment variables

The config sets every variable below. Values in *italics* are sealed secrets (step 6).

| Variable | Services | QA / staging | Production |
|---|---|---|---|
| `APP_ENV` | backends | `qa` / `staging` | `production` |
| `DATABASE_URL` | backends | `postgresql+asyncpg://bhojango:${{postgres.POSTGRES_PASSWORD}}@postgres.railway.internal:5432/bhojango` | same |
| `REDIS_URL` | core-api, worker / realtime | `${{redis.REDIS_URL}}/0` / `…/3` | same |
| `EVENT_BUS`, `EVENT_BUS_REDIS_URL` | backends | `redis`, `${{redis.REDIS_URL}}/5` | same |
| `CORE_API_URL`, `JWKS_URL` | realtime, worker, web, admin | `http://core-api.railway.internal:8001` | same |
| `CORS_ORIGINS` | backends | `["https://${{web.RAILWAY_PUBLIC_DOMAIN}}","https://${{admin.RAILWAY_PUBLIC_DOMAIN}}"]` | *the custom domains* |
| `PAYMENT_PROVIDER` / `PAYOUT_PROVIDER` / `SMS_PROVIDER` / `PUSH_PROVIDER` / `EMAIL_PROVIDER` | backends | `fake` / `fake` / `log` / `log` / `log` | `live` / `live` / `live` / `live` / `sendgrid` |
| `OTP_FIXED_CODE` | backends | default (`123456`, seed phones only) | `""` |
| `DELIVERY_PIN_FIXED` | backends | default (`1234`, seed phones only) | `""` |
| `DEMO_RIDER_SIM` | worker | `1` in QA only (the demo rider); unset in staging | unset (refused if set) |
| `STORAGE_PROVIDER` | core-api | `s3` (the bucket) | `s3` |
| `NEXT_PUBLIC_CORE_URL`, `NEXT_PUBLIC_REALTIME_URL` | web, admin (build time) | `https://${{<service>.RAILWAY_PUBLIC_DOMAIN}}` | same, or the custom domains |
| `NEXT_PUBLIC_APP_URL` | web | `https://${{web.RAILWAY_PUBLIC_DOMAIN}}` | *the custom domain* |
| *`JWT_PRIVATE_KEY`, `INTERNAL_SERVICE_SECRET`, `ALERT_WEBHOOK_TOKEN`, `FAKE_PAYMENT_WEBHOOK_SECRET`, `POSTGRES_PASSWORD`, bucket keys* | see step 6 | sealed | sealed, different values |

The complete list with defaults is `backend/shared/config.py`; anything not listed keeps its default.

## The mobile apps

[`tools/mobile/env-profile.sh qa`](../../tools/mobile/env-profile.sh) points the Expo apps at QA:

- It reads core-api's and realtime's domains from Railway and writes each app's git-ignored `.env.local`.
- Restart Metro with `-c` afterwards.
- `env-profile.sh local` goes back to `make dev`.
