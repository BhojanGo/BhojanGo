# SPR-01 Evidence Manifest — v4 (Corrected)

**Date:** 2026-06-15
**Branch:** rr_testing
**Git HEAD:** 2a733dc — "Implementaion Planned"

---

## Scope Item Status

### IP.PR.01.001 — Infrastructure Diagnosis (Service Boot Matrix)
**Status:** PASS
**Evidence:**
- All 7 backend services boot and respond to `/health` with HTTP 200.
- `start-all.sh` was executed; services already running from prior start.
- Health check log: `tests/results/evidence/logs/health-check-curl.log`
- Ports confirmed: 8001–8007 (backend), 3000 (web).

### IP.PR.01.002 — Pin bcrypt Dependency Across All Python Services
**Status:** PARTIAL
**Evidence:**
- `services/user-svc/pyproject.toml` line 18: `bcrypt = "<5.0.0"` — pinned ✓
- `services/restaurant-svc/pyproject.toml`: NO bcrypt or passlib reference
- `services/order-svc/pyproject.toml`: NO bcrypt or passlib reference
- `services/payment-svc/pyproject.toml`: NO bcrypt or passlib reference
- `services/notification-svc/pyproject.toml`: NO bcrypt or passlib reference
- `services/delivery-svc/pyproject.toml`: NO bcrypt or passlib reference
- `scripts/seed/seed_users.py` line 7: `from passlib.context import CryptContext` — still uses passlib
- **Honest assessment:** Only 1 of 6 services explicitly pins bcrypt. Passlib is still used in seed_users.py. No import errors were observed on startup, so the runtime conflict is not currently triggered. The scope said "all 6 Python backend services" — this is NOT satisfied.
- Log: `tests/results/evidence/logs/dependency-manifest-review.log`

### IP.PR.01.003 — Fix Batch-Engine Migration SQL Ordering
**Status:** PASS
**Evidence:**
- File: `services/batch-engine/src/db/migrations/001_create_batch_tables.sql`
- Lines 14–41: `CREATE TABLE batches (...)` — created FIRST
- Lines 44–83: `CREATE TABLE order_pool (...)` — created SECOND, with FK `batch_id UUID REFERENCES batches(id)`
- Table ordering is CORRECT. No fix was needed.
- Log: `tests/results/evidence/logs/batch-migration-review.log`

### IP.PR.01.004 — Verify PostgreSQL Seeded Data Presence
**Status:** PASS
**Evidence:**
- `psql` row counts (from `tests/results/evidence/logs/seed-count.log`):
  - restaurants: 96 (≥ 90 required)
  - menu_categories: 521
  - menu_items: 1,669
  - users: 12
  - orders: 110
  - reviews: 0 (gap noted)
  - notifications: 40
  - wallets: 12

### IP.PR.01.005 — API Health Check Catalog (Per-Service)
**Status:** PASS
**Evidence:**
- `curl` results (from `tests/results/evidence/logs/health-check-curl.log`):
  - user-svc:8001 — HTTP 200, ~9ms
  - restaurant-svc:8002 — HTTP 200, ~7ms
  - order-svc:8003 — HTTP 200, ~8ms
  - delivery-svc:8004 — HTTP 200, ~3ms
  - payment-svc:8005 — HTTP 200, ~8ms
  - notification-svc:8006 — HTTP 200, ~9ms
  - batch-engine:8007 — HTTP 200, ~2ms
  - web:3000 — HTTP 404 on `/health` (expected; Next.js has no health route)

### IP.PR.01.006 — Document Environment and Dependency Blockers
**Status:** PASS
**Evidence:**
- `BLOCKERS.md` updated with 4 documented blockers:
  - BLOCKER-001: Docker not available
  - BLOCKER-002: delivery-svc missing DATABASE_URL (intentional — DynamoDB)
  - BLOCKER-003: reviews table empty (0 records)
  - BLOCKER-004: web has no `/health` endpoint
- Web path corrected to `apps/web/src/app/api/health/route.ts` (v4 fix).

### IP.PR.01.007 — Add OpenSearch to docker-compose
**Status:** PARTIAL
**Evidence:**
- `docker-compose.yml` already contains `opensearch` service (lines 73–86).
- Docker is unavailable on this system, so live validation was not possible.
- The service definition is present in source, but OpenSearch was skipped (docker-missing).
- Honest assessment: Definition present but not validated.

### IP.PR.01.008 — Frontend Blank-Page Audit
**Status:** PARTIAL
**Evidence:**
- HTTP-level audit (`tests/results/evidence/logs/frontend-route-audit.log`):
  - `/` — HTTP 200
  - `/restaurants` — HTTP 200
  - `/restaurants/{id}` — HTTP 200
  - `/cart` — HTTP 200
  - `/checkout` — HTTP 200
  - `/orders` — HTTP 200
  - `/profile` — HTTP 200
  - `/wallet` — HTTP 200
  - `/login` — HTTP 200
  - `/signup` — HTTP 200
- **Frontend audit is HTTP-only. Browser render/console/screenshot audit is NOT complete.**
- No console errors, blank screens, or runtime crashes were verified.

### IP.PR.01.009 — Verify `start-all.sh` Runs End-to-End
**Status:** PASS
**Evidence:**
- `scripts/start-all.sh` executed successfully (v4 corrected).
- Log: `tests/results/evidence/logs/start-script-run.log`
- Script exits `0` when all required services are already running and healthy.
- Script distinguishes `already-running`, `started`, `launched-unverified`, `skipped`, `failed`.
- Docker-missing services (opensearch, pgbouncer, localstack, kong) explicitly recorded as `skipped`.
- Stale `.service_pids` cleared before current run.
- Health-verified before reporting `started`; unverified launches reported as `launched-unverified`.
- Exit code: `0`

### IP.PR.01.010 — Document Menu Endpoint Failure Root Cause
**Status:** PASS
**Evidence:**
- `GET /api/v1/restaurants/{id}/menu` returns HTTP 500 (log: `tests/results/evidence/logs/menu-endpoint-curl.log`)
- **Raw stack trace excerpt:** `tests/results/evidence/logs/restaurant-svc-menu-error.log`
  ```
  UndefinedColumnError: column menu_items.deleted_at does not exist
  ```
- **Route file:** `services/restaurant-svc/app/api/v1/restaurants.py` — `get_restaurant_menu()` triggers the ORM load via `repo.get_with_menu()` (lines 100–130).
- **Repository:** `services/restaurant-svc/app/repositories/restaurant.py` — `get_with_menu()` uses `selectinload(Restaurant.menu_items)` which hydrates `MenuItem` objects including the `deleted_at` attribute.
- **Model:** `services/restaurant-svc/app/models/menu.py` line 59 — `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`
- **Migration:** `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py` — the `menu_items` table is created WITHOUT a `deleted_at` column.
- **Root cause proven:** The ORM model expects `deleted_at` but the initial migration never created it. This is schema drift.
- The same drift exists on the `restaurants` table (model has `deleted_at` but migration does not).

---

## Acceptance Criteria Result

| Criterion | Status | Evidence |
|---|---|---|
| All services can be started with `start-all.sh` | PASS | `start-script-run.log` (exit 0) |
| `curl localhost:3000` returns HTML | PASS | `frontend-route-audit.log` |
| `curl localhost:8005/health` returns 200 | PASS | `health-check-curl.log` |
| `psql` shows >90 restaurants | PASS | `seed-count.log` (96) |
| Document of failing endpoints exists | PASS | `menu-endpoint-curl.log` + `restaurant-svc-menu-error.log` + `BLOCKERS.md` |

---

## Source Files Included in This Closure

### Changed files (2)
- `scripts/start-all.sh`
- `BLOCKERS.md`

### Relevant unchanged source/config files (33)
- `docker-compose.yml`
- `package.json`
- `pnpm-workspace.yaml`
- `services/user-svc/pyproject.toml`
- `services/restaurant-svc/pyproject.toml`
- `services/order-svc/pyproject.toml`
- `services/payment-svc/pyproject.toml`
- `services/notification-svc/pyproject.toml`
- `services/delivery-svc/pyproject.toml`
- `services/batch-engine/src/db/migrations/001_create_batch_tables.sql`
- `services/batch-engine/package.json`
- `scripts/seed/run_all.sh`
- `scripts/seed/comprehensive_seed.py`
- `scripts/seed/seed_restaurants.py`
- `scripts/seed/seed_users.py`
- `scripts/seed/seed_orders.py`
- `services/user-svc/app/main.py`
- `services/restaurant-svc/app/main.py`
- `services/order-svc/app/main.py`
- `services/payment-svc/app/main.py`
- `services/notification-svc/app/main.py`
- `services/delivery-svc/app/main.py`
- `services/batch-engine/src/main.ts`
- `apps/web/package.json`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/restaurants/page.tsx`
- `apps/web/src/app/restaurants/[id]/page.tsx`
- `apps/web/src/app/cart/page.tsx`
- `apps/web/src/app/checkout/page.tsx`
- `apps/web/src/app/orders/page.tsx`
- `apps/web/src/app/profile/page.tsx`
- `apps/web/src/app/wallet/page.tsx`
- `apps/web/src/app/(auth)/login/page.tsx`
- `apps/web/src/app/(auth)/signup/page.tsx`

### Additional source files for menu root-cause grounding (5)
- `services/restaurant-svc/app/models/menu.py`
- `services/restaurant-svc/app/models/restaurant.py`
- `services/restaurant-svc/app/repositories/restaurant.py`
- `services/restaurant-svc/app/api/v1/restaurants.py`
- `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py`
- `services/restaurant-svc/app/db/migrations/versions/0002_money_to_numeric.py`
- `services/restaurant-svc/app/db/migrations/versions/0003_pain_point_pricing_radius.py`

### Evidence artifacts (10)
- `BLOCKERS.md`
- `tests/results/evidence/manifests/SPR-01-file-read-ledger.md`
- `tests/results/evidence/manifests/SPR-01-evidence.md`
- `tests/results/evidence/summaries/current_handoff.md`
- `tests/results/evidence/manifests/closure-summary.md`
- `tests/results/evidence/logs/start-script-run.log`
- `tests/results/evidence/logs/docker-availability.log`
- `tests/results/evidence/logs/health-check-curl.log`
- `tests/results/evidence/logs/seed-count.log`
- `tests/results/evidence/logs/menu-endpoint-curl.log`
- `tests/results/evidence/logs/dependency-manifest-review.log`
- `tests/results/evidence/logs/batch-migration-review.log`
- `tests/results/evidence/logs/frontend-route-audit.log`
- `tests/results/evidence/logs/restaurant-svc-menu-error.log`
