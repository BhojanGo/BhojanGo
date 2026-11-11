# Restructure map (P1) — decisions, Nov 10 2026

Owner: Srini (CTO). This file settles every judgement call in P1. If something
in the repo doesn't fit a rule below, stop and ask — don't guess.

## Ground rules

1. **"Do not change behaviour" means the API contract**: same URLs, same request
   and response bodies, same status codes, same events. Pre-launch, there is no
   production traffic, so changing *how things are deployed* is allowed.
2. **Moves first, refactors later.** P1 relocates code and merges entry points.
   It does not rename endpoints, rewrite business logic, or add features.
3. Names: use **rider** (not driver/courier) and **partner** (not merchant) for
   new folders. Existing code identifiers stay as they are until later prompts.
4. Small commits, one area per commit. Tests green after every commit.
5. If any deployed database holds data that must be kept, stop and ask before
   touching migrations. (Expected answer: none — nothing is deployed.)

## Backend

| Today | Goes to | How |
| --- | --- | --- |
| `services/user-svc/app` | `backend/core_api/modules/identity/` | Code moves in |
| `services/restaurant-svc/app` | `backend/core_api/modules/catalog/` | Code moves in. OpenSearch stays for now (replaced by Postgres search later) |
| `services/order-svc/app` | `backend/core_api/modules/orders/` | Code moves in. `TAX_RATES`, commission and fee code **stay here** for now; P7–P9 move them to `rules` / `pricing` |
| `services/payment-svc/app` | `backend/core_api/modules/payments/` | Code moves in. `finance` is built in P13 |
| `services/delivery-svc/app` | `backend/realtime/app/` | Moves as-is; **stays its own deployable** (WebSocket + GPS) |
| `services/notification-svc/app` | `backend/worker/app/` | Moves as-is; **stays its own deployable** (keeps its HTTP API and SQS consumer for now) |
| `services/batch-engine` (TypeScript) | `backend/worker/batch-engine/` | Moves untouched; stays in the pnpm workspace; reference only until the Phase 5 port to Python |
| `services/*/tests` | next to their module, e.g. `backend/core_api/modules/identity/tests/` | Move; fix imports |
| `services/*/pyproject.toml` | one `backend/pyproject.toml` (uv workspace) | Merge dependencies; on version conflicts take the higher version and note it in the PR |
| `services/*/Dockerfile` | `backend/core_api/Dockerfile`, `backend/realtime/Dockerfile`, `backend/worker/Dockerfile` | Three images instead of seven |

### core_api: merge four services into one app — YES

- New `backend/core_api/main.py` creates one FastAPI app and includes every
  router from identity, catalog, orders and payments **with the same prefixes as
  today** (`/api/v1/auth`, `/api/v1/users`, `/api/v1/addresses`,
  `/api/v1/restaurants`, `/api/v1/orders`, `/api/v1/payments`, `/api/v1/wallet` …).
  Paths don't collide today; if any do (e.g. `/health`), keep one shared copy.
- Each old `main.py`'s startup/shutdown and middleware moves into a
  `register(app)` function in that module, called from `core_api/main.py`.
- Each module keeps the five-folder shape: `api/`, `service/` (today `services/`),
  `repository/` (today `repositories/`), `models/`, `schemas/`.

### backend/shared

- Code duplicated across services (`config.py` base settings, `core/security`,
  JWT verification, DB session, `middleware/`, logging) is merged into
  `backend/shared/`. Where copies differ, keep the stricter one and list the
  differences in the PR description.
- Service-specific settings become sections of one `Settings` class
  (e.g. `settings.payments.stripe_key`). Env var names stay the same.

### Modules not built yet — create nothing

`markets`, `rules`, `pricing`, `promotions`, `finance` and `audit` are **not**
created in P1. They are built by P6 (markets), P7 (rules, audit, promotions),
P8 (pricing) and P13 (finance). No empty folders.

### Migrations: one tree — YES

- One Alembic tree at `backend/migrations/` with one `env.py` that loads every
  model's metadata (core_api modules + realtime + worker).
- **Keep the per-service Postgres schemas** exactly as `infra/db/init.sql`
  creates them (`user_svc`, `restaurant_svc`, `order_svc`, `payment_svc`,
  `delivery_svc`, `notification_svc`). Schema names don't change in P1.
- Replace the old per-service histories with a single baseline revision
  `0001_baseline` generated from the current models. Delete the old
  `alembic.ini` / `alembic/` folders (git history keeps them).
- Prove it: on an empty database, `alembic upgrade head` must produce the same
  tables, columns and indexes as running the five old trees. Diff the
  `pg_dump --schema-only` output and attach it to the PR.

## Apps

| Today | Goes to | How |
| --- | --- | --- |
| `apps/mobile/app/(tabs)` + customer screens (`cart`, `checkout`, `order`, `restaurant`, `wallet`) | `apps/customer/` | New Expo app, bundle id `com.bhojango.app` |
| `apps/mobile/app/(driver-tabs)` | `apps/rider/` | New Expo app, bundle id `com.bhojango.rider` |
| `apps/mobile/app/(auth)` | into both apps | Each app gets its own `(auth)` routes; shared logic goes to `mobile-core` |
| `apps/mobile/src/lib`, `apps/mobile/src/store` | `packages/mobile-core/` | Shared by customer and rider |
| `apps/mobile` | deleted after the split | Both new apps must start in Expo Go and reach the same screens as before |
| — | `apps/partner/` | **Not in P1.** Created by P19 |
| `apps/web`, `apps/admin` | stay | No change |

## Packages

| Package | P1 action |
| --- | --- |
| `packages/config`, `packages/ui` | Stay |
| `packages/types` | **Stays for now.** Retired when P17 switches the apps to the generated `api-client` |
| `packages/mobile-core` | **Created in P1** (needed for the mobile split) |
| `packages/api-client` | Not in P1. Created in P16/P17 from the core_api OpenAPI |
| `packages/i18n` | Not in P1. Created in P15/P16 |

## Infra, scripts, root files

| Today | Goes to |
| --- | --- |
| `infra/terraform` | Stays (trimmed in P4) |
| `docker-compose.yml` | `infra/docker/compose.yaml`, running 3 backend images instead of 7 services. Keep a root `docker-compose.yml` that only `include:`s it, so old commands still work |
| `infra/db/init.sql` | `infra/docker/db/init.sql` |
| `infra/localstack/init-aws.sh` | `infra/docker/localstack/init-aws.sh` |
| `infra/kong/` | `infra/docker/kong/`. Point every route at core_api, except delivery → realtime and notifications → worker. Kong is removed in P4 |
| `scripts/seed` | `tools/seed` (rewritten in P3) |
| `pnpm-workspace.yaml`, `turbo.json`, CI workflows, README, CONTRIBUTING | Updated for the new paths |

## Before branching (housekeeping)

- `apps/mobile/tsconfig.json`: the change swaps the `@bhojango/config` import for
  a relative path and drops `expo-env.d.ts`. **Discard it**
  (`git checkout -- apps/mobile/tsconfig.json`); the app is replaced by the split.
- `infra/kong/kong.local.yml`: holds only `${JWT_SECRET:-changeme…}`
  placeholders, no real secrets. **Commit it** with the move to `infra/docker/kong/`.
- `docs/BhojanGo_GoLive_Tracker.docx` and `docs/specs/`: **commit them**.
- Branch `restructure` from `dev` (the default branch), not from `bugfixes`.

## Done when

- `services/` and `apps/mobile` no longer exist; the layout matches `01-structure.md`.
- `pytest` passes for core_api, realtime and worker; `pnpm turbo test lint typecheck` passes.
- Every old endpoint, called through Kong, returns the same result as before
  (smoke list in the PR).
- The schema diff from the migration check is empty.
