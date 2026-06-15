# SPR-01 File Read Ledger

**Date:** 2026-06-15
**Session:** SPR-01 v4 — Corrected Closure

---

## Startup / local orchestration

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `scripts/start-all.sh` | yes | yes | yes | yes | Modified: Docker-missing graceful fallback, health verification, stale PID cleanup, exit-code fix | IP.PR.01.009 |
| `docker-compose.yml` | yes | yes | no | yes | Unchanged reference file; OpenSearch already present | IP.PR.01.007 |
| `package.json` | yes | yes | no | yes | Unchanged root workspace manifest | IP.PR.01.002 |
| `pnpm-workspace.yaml` | yes | yes | no | yes | Unchanged workspace config | — |

## Python service dependency manifests

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `services/user-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; already has `bcrypt = "<5.0.0"` | IP.PR.01.002 |
| `services/restaurant-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; no bcrypt/passlib reference | IP.PR.01.002 |
| `services/order-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; no bcrypt/passlib reference | IP.PR.01.002 |
| `services/payment-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; no bcrypt/passlib reference | IP.PR.01.002 |
| `services/notification-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; no bcrypt/passlib reference | IP.PR.01.002 |
| `services/delivery-svc/pyproject.toml` | yes | yes | no | yes | Unchanged; no bcrypt/passlib reference | IP.PR.01.002 |

## Batch-engine migration

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `services/batch-engine/src/db/migrations/001_create_batch_tables.sql` | yes | yes | no | yes | Unchanged; ordering is correct (batches before order_pool) | IP.PR.01.003 |
| `services/batch-engine/package.json` | yes | yes | no | yes | Unchanged batch-engine manifest | — |

## Seed scripts

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `scripts/seed/run_all.sh` | yes | yes | no | yes | Unchanged seed orchestrator | IP.PR.01.004 |
| `scripts/seed/comprehensive_seed.py` | yes | yes | no | yes | Unchanged main seed generator | IP.PR.01.004 |
| `scripts/seed/comprehensive_seed.sql` | yes | partial (first 50 lines) | no | no | Generated file (24K+ lines); not source | IP.PR.01.004 |
| `scripts/seed/seed_restaurants.py` | yes | yes | no | yes | Unchanged restaurant seed | IP.PR.01.004 |
| `scripts/seed/seed_users.py` | yes | yes | no | yes | Unchanged user seed; still uses passlib | IP.PR.01.002, IP.PR.01.004 |
| `scripts/seed/seed_orders.py` | yes | yes | no | yes | Unchanged order seed | IP.PR.01.004 |

## Backend runtime entry points

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `services/user-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |
| `services/restaurant-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005, IP.PR.01.010 |
| `services/order-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |
| `services/payment-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |
| `services/notification-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |
| `services/delivery-svc/app/main.py` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |
| `services/batch-engine/src/main.ts` | yes | yes | no | yes | Unchanged; health check confirmed working | IP.PR.01.005 |

## Frontend route files for PR.01 blank-page audit

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `apps/web/package.json` | yes | yes | no | yes | Unchanged web app manifest | IP.PR.01.008 |
| `apps/web/src/app/page.tsx` | yes | yes | no | yes | Unchanged homepage; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/restaurants/page.tsx` | yes | yes | no | yes | Unchanged restaurant list; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/restaurants/[id]/page.tsx` | yes | yes | no | yes | Unchanged restaurant detail; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/cart/page.tsx` | yes | yes | no | yes | Unchanged cart page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/checkout/page.tsx` | yes | yes | no | yes | Unchanged checkout page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/orders/page.tsx` | yes | yes | no | yes | Unchanged orders page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/profile/page.tsx` | yes | yes | no | yes | Unchanged profile page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/wallet/page.tsx` | yes | yes | no | yes | Unchanged wallet page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/(auth)/login/page.tsx` | yes | yes | no | yes | Unchanged login page; HTTP 200 OK | IP.PR.01.008 |
| `apps/web/src/app/(auth)/signup/page.tsx` | yes | yes | no | yes | Unchanged signup page; HTTP 200 OK | IP.PR.01.008 |

## Restaurant-svc menu root-cause grounding (new in v4)

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `services/restaurant-svc/app/models/menu.py` | yes | yes | no | yes | ORM model defines `deleted_at` on MenuItem (line 59) — schema drift source | IP.PR.01.010 |
| `services/restaurant-svc/app/models/restaurant.py` | yes | yes | no | yes | ORM model defines `deleted_at` on Restaurant (line 66) — same drift pattern | IP.PR.01.010 |
| `services/restaurant-svc/app/repositories/restaurant.py` | yes | yes | no | yes | Repository uses `selectinload(Restaurant.menu_items)` which hydrates `deleted_at` field | IP.PR.01.010 |
| `services/restaurant-svc/app/api/v1/restaurants.py` | yes | yes | no | yes | Route handler `get_restaurant_menu()` triggers the failing query | IP.PR.01.010 |
| `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py` | yes | yes | no | yes | Migration creates `menu_items` WITHOUT `deleted_at` column — proves schema drift | IP.PR.01.010 |
| `services/restaurant-svc/app/db/migrations/versions/0002_money_to_numeric.py` | yes | yes | no | yes | Migration converts price columns; does NOT add `deleted_at` | IP.PR.01.010 |
| `services/restaurant-svc/app/db/migrations/versions/0003_pain_point_pricing_radius.py` | yes | yes | no | yes | Migration adds pricing fields; does NOT add `deleted_at` | IP.PR.01.010 |
| `services/restaurant-svc/restaurant_svc.log` | yes | partial (excerpt) | no | no | Raw log file (46K+ lines); excerpt saved to `tests/results/evidence/logs/restaurant-svc-menu-error.log` | IP.PR.01.010 |

## Gap File (expected but not found)

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `docs/folder_structure.md` | yes | yes | no | **no** | Present; read for context. **NOT included in closure zip** (excluded from source-grounded closure). | — |

## Evidence / config files changed or created during SPR-01

| File Path | Exists | Read End-to-End | Changed | In Closure Zip | Reason | Scope IDs |
|---|---|---|---|---|---|---|
| `BLOCKERS.md` | yes | yes | **yes** | yes | Corrected web path from `services/web/...` to `apps/web/...` | IP.PR.01.006 |
| `tests/results/evidence/manifests/SPR-01-evidence.md` | yes | yes | n/a (new) | yes | Evidence manifest v4 | — |
| `tests/results/evidence/summaries/current_handoff.md` | yes | yes | n/a (new) | yes | Handoff summary v4 | — |
| `tests/results/evidence/manifests/SPR-01-file-read-ledger.md` | yes | yes | n/a (new) | yes | File read ledger v4 | — |
| `tests/results/evidence/manifests/closure-summary.md` | yes | yes | n/a (new) | yes | Closure summary v4 | — |
| `tests/results/evidence/logs/*` | yes | yes | n/a (new) | yes | Raw validation logs (9 files) | — |

---

## Summary

- **Total files listed in requirements:** 33 source/config + 8 evidence artifacts
- **Files found and read end-to-end:** 40+ files (including restaurant-svc grounding files)
- `comprehensive_seed.sql` read partially (first 50 lines) because it is a generated artifact (24K+ lines)
- `restaurant_svc.log` read via excerpt; full 46K-line log not included in zip
- **Files changed in this session:** 2 (`scripts/start-all.sh`, `BLOCKERS.md`)
- **Files created in this session:** Evidence artifacts (manifests, logs, summaries, BLOCKERS.md)
- **Source files included in closure zip:** 40 (33 unchanged + 2 changed + 5 additional restaurant-svc grounding files)
