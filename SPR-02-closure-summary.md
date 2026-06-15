# SPR-02 Closure Summary — Targeted Correction

**Sprint ID:** SPR-02 — Browsable Prototype
**Date:** 2026-06-15
**Branch:** rr_testing
**Zip:** `review_exports/SPR-02_scope_review_v2.zip`

---

## Implemented Corrections

1. **`/api/v1/me` 401 fix** — Set `HTTPBearer(auto_error=False)`, manually handle missing credentials → returns 401 not 403
2. **Restaurant list cache key fix** — Now includes all filter params: city, cuisine, country, min_rating, max_delivery_fee, is_open, page, limit
3. **Mobile bottom navigation** — `MobileBottomNav.tsx` created, visible `<640px`, fixed bottom, Home/Search/Cart/Orders/Profile tabs, cart badge
4. **Trust badges on RestaurantCard** — FSSAI Verified, Freshly Prepared, Under 30 min
5. **Explicit 4+ rating filter chip** — Added "⭐ 4+" toggle chip on restaurant list
6. **Local image policy preserved** — No Unsplash calls; deterministic local images
7. **Focused validation test** — `tests/backend/test_spr02_contracts.py`
8. **Evidence logs created** — menu, me, opensearch-fallback, frontend-routes, unit-tests, zip-listing
9. **Screenshots captured** — 7 screenshots including mobile bottom nav

---

## IP.PR.02.015 Status: PARTIAL

Backend `veg_only` query param is NOT implemented because:
- `Restaurant` model has no `is_veg_friendly` or `is_veg_only` field
- Implementing it would require a schema migration to add such a field
- This is deferred to a future sprint

Frontend `vegOnly` filter chip still works client-side on `is_veg` data from menu items.

---

## Files Changed

| File | Scope ID |
|---|---|
| `services/user-svc/app/core/dependencies.py` | IP.PR.02.002 |
| `services/restaurant-svc/app/api/v1/restaurants.py` | IP.PR.02.015 |
| `apps/web/src/app/layout.tsx` | IP.PR.02.014 |
| `apps/web/src/app/restaurants/page.tsx` | IP.PR.02.010, IP.PR.02.015 |
| `apps/web/src/components/restaurant/RestaurantCard.tsx` | IP.PR.02.012 |
| `apps/web/src/components/layout/MobileBottomNav.tsx` | IP.PR.02.014 |

---

## New Files Created

| File | Scope ID |
|---|---|
| `apps/web/src/components/layout/MobileBottomNav.tsx` | IP.PR.02.014 |
| `tests/backend/test_spr02_contracts.py` | validation |
| `services/restaurant-svc/app/db/migrations/versions/0004_add_deleted_at.py` | IP.PR.02.001 (from prior session) |

---

## Validation Commands Run

```bash
# Menu endpoint
curl -s -w "\nHTTP_CODE: %{http_code}\n" http://localhost:8002/api/v1/restaurants/${RID}/menu

# /api/v1/me unauthenticated → 401
curl -s -w "\nHTTP_CODE: %{http_code}\n" http://localhost:8001/api/v1/me

# /api/v1/me authenticated → 200
curl -s -w "\nHTTP_CODE: %{http_code}\n" -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/v1/me

# Restaurant list with filters
curl -s -w "\nHTTP_CODE: %{http_code}\n" "http://localhost:8002/api/v1/restaurants?cuisine=indian&min_rating=4.0&limit=5"

# Frontend routes
for route in "/" "/restaurants" "/restaurants/${RID}" "/login" "/signup"; do
  curl -s -o /dev/null -w "Route $route: %{http_code}\n" http://localhost:3000$route
done

# Zip listing
unzip -l review_exports/SPR-02_scope_review_v2.zip
```

---

## Screenshots Captured

| Screenshot | Path |
|---|---|
| Homepage | `tests/results/frontend/customer/screenshots/homepage.png` |
| Restaurant list | `tests/results/frontend/customer/screenshots/restaurants-list.png` |
| Restaurant detail | `tests/results/frontend/customer/screenshots/restaurant-detail.png` |
| Login | `tests/results/frontend/customer/screenshots/login.png` |
| Authenticated homepage | `tests/results/frontend/customer/screenshots/authenticated-homepage.png` |
| Mobile restaurant list | `tests/results/frontend/customer/screenshots/restaurants-list-mobile.png` |
| Mobile bottom nav | `tests/results/frontend/customer/screenshots/mobile-bottom-nav.png` |

---

## Open Gaps

1. Dedicated skeleton UI components in `packages/ui` (IP.PR.02.005) — use animate-pulse inline
2. Homepage ISR (IP.PR.02.004) — client-side fetch used instead
3. Backend `veg_only` filter (IP.PR.02.015) — requires schema change
4. httpOnly cookie auth (IP.PR.02.003) — deferred to PR.05

---

## SPR-02 Status: PARTIAL

SPR-02 remains PARTIAL due to:
- IP.PR.02.004 (ISR) — PARTIAL
- IP.PR.02.005 (skeleton components) — PARTIAL
- IP.PR.02.011 (Unsplash) — PARTIAL (intentionally adapted)
- IP.PR.02.015 (backend veg_only) — PARTIAL (schema change required)

SPR-02 is NOT approved as complete. Do NOT proceed to SPR-03.

---

## Zip Structure Confirmed

All files in `review_exports/SPR-02_scope_review_v2.zip` use exact repo-relative paths.
No flattening into `changed/`, `reference/`, or `evidence/` generic folders.
