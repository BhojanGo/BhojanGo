# SPR-01 Closure Summary — v4 (Corrected)

**Sprint ID:** SPR-01
**Scope IDs:** IP.PR.01.001 – IP.PR.01.010
**Date:** 2026-06-15
**Branch:** rr_testing
**Status:** PARTIAL (honest assessment)

---

## Scope Status Table

| Scope ID | Title | Status | Honest Rationale |
|---|---|---|---|
| IP.PR.01.001 | Service Boot Matrix | PASS | All 7 backend services + web running; health checks OK |
| IP.PR.01.002 | Pin bcrypt Dependency | PARTIAL | Only user-svc pins bcrypt. Other services don't reference it. seed_users.py still uses passlib. No runtime failure, but scope not fully satisfied. |
| IP.PR.01.003 | Fix Batch Migration Ordering | PASS | Migration already correct. batches created before order_pool. No change needed. |
| IP.PR.01.004 | Verify Seed Data | PASS | 96 restaurants, 521 categories, 1669 items, 12 users, 110 orders. reviews=0 (gap). |
| IP.PR.01.005 | API Health Check Catalog | PASS | All /health endpoints return 200. Latencies logged. |
| IP.PR.01.006 | Document Blockers | PASS | BLOCKERS.md with 4 blockers. Web path corrected to `apps/web/...` in v4. |
| IP.PR.01.007 | Add OpenSearch to docker-compose | PARTIAL | opensearch service present in docker-compose.yml. Not validated live (Docker missing). Skipped. |
| IP.PR.01.008 | Frontend Blank-Page Audit | PARTIAL | All routes return HTTP 200. No browser/screenshot audit. No console errors verified. |
| IP.PR.01.009 | Verify start-all.sh | PASS | Script exits 0 when required services already running. Distinguishes already-running/started/launched-unverified/skipped/failed. Clears stale PIDs. Health checks launched services. Docker optional. |
| IP.PR.01.010 | Menu Endpoint Root Cause | PASS | Root cause proven with source grounding: `menu_items.deleted_at` defined in ORM model but missing from migration. Stack trace, route, repository, model, and migration files included. |

---

## Source Files Included in Zip

### Changed during SPR-01 (2)
- `scripts/start-all.sh`
- `BLOCKERS.md`

### Relevant unchanged source/config files (34)
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

### Additional restaurant-svc grounding files (7)
- `services/restaurant-svc/app/models/menu.py`
- `services/restaurant-svc/app/models/restaurant.py`
- `services/restaurant-svc/app/repositories/restaurant.py`
- `services/restaurant-svc/app/api/v1/restaurants.py`
- `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py`
- `services/restaurant-svc/app/db/migrations/versions/0002_money_to_numeric.py`
- `services/restaurant-svc/app/db/migrations/versions/0003_pain_point_pricing_radius.py`

### Evidence artifacts (13)
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

---

## Missing Expected Files

| File | Reason |
|---|---|
| `comprehensive_seed.sql` | Generated file (24K+ lines); excluded from source-grounded closure. The generator `comprehensive_seed.py` is included instead. |
| `restaurant_svc.log` (full) | Raw log is 46K+ lines; excerpt saved to `tests/results/evidence/logs/restaurant-svc-menu-error.log`. Full log excluded. |
| `docs/folder_structure.md` | Read for context but excluded from source-grounded closure. |
| Browser screenshots | Not captured; frontend audit is HTTP-only. |

---

## Validation Commands Run

```bash
# Docker availability
docker --version && docker-compose --version && docker compose version

# Health checks
for port in 8001 8002 8003 8004 8005 8006 8007 3000; do
  curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health
done

# Seed counts
psql -h localhost -U bhojango -d bhojango -c "SELECT ... COUNT(*) ..."

# Menu endpoint
curl -s http://localhost:8002/api/v1/restaurants/{id}/menu

# Frontend routes
for path in / /restaurants /cart /checkout /orders /profile /wallet /login /signup; do
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000$path
done

# Start script
bash scripts/start-all.sh
```

All command outputs saved to `tests/results/evidence/logs/`.

---

## Remaining Blockers

1. **Menu endpoint 500** — `menu_items.deleted_at` column missing. Hard blocker for core loop.
2. **Docker unavailable** — optional per local-first policy.
3. **reviews table empty** — 0 records. Soft blocker.
4. **web no /health endpoint** — monitoring gap. Soft blocker.
5. **bcrypt pinning incomplete** — only user-svc pins. Soft blocker.

---

## Browser Screenshots Captured?

**No.** Frontend audit is HTTP-only. Browser render/console/screenshot audit is NOT complete.

---

## Closure Zip Path

`review_exports/SPR-01_scope_review_v4.zip`
