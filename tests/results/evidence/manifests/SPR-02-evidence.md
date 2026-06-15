# SPR-02 Evidence Manifest — CORRECTED v3

**Date:** 2026-06-15
**Branch:** rr_testing
**Scope:** IP.PR.02.* — Browsable Prototype (Targeted Correction)
**Zip:** `review_exports/SPR-02_scope_review_v3.zip`

---

## Scope Item Status After Corrections

### IP.PR.02.001 — Add DB Fallback to Menu Endpoint When OpenSearch Unavailable
**Status:** PASS
**Evidence:**
- `curl http://localhost:8002/api/v1/restaurants/{id}/menu` → HTTP 200 with real categories/items
- Log: `tests/results/evidence/logs/spr02-menu-endpoint.log`
- Schema drift fixed via `0004_add_deleted_at.py` migration

### IP.PR.02.002 — Add `GET /api/v1/me` Endpoint to User Service
**Status:** PASS (with correction)
**Evidence:**
- `/api/v1/me` now returns 401 for missing/invalid token (was 401)
- Fixed by setting `HTTPBearer(auto_error=False)` and manually handling `credentials=None`
- Authenticated request returns 200 with `UserResponse`
- Log: `tests/results/evidence/logs/spr02-me-endpoint.log`

### IP.PR.02.003 — Implement Frontend Auth Persistence
**Status:** PASS
**Evidence:**
- `AuthBootstrap.tsx` calls `/api/v1/me` on mount
- `Providers.tsx` wraps app with `AuthBootstrap`
- Zustand persist middleware stores token in localStorage
- httpOnly cookie deferred to PR.05 (documented)

### IP.PR.02.004 — Convert Homepage to Skeleton-First ISR Landing
**Status:** PARTIAL
**Evidence:**
- Homepage renders with content (not blank)
- `revalidate: 60` not explicitly configured
- Client-side `useQuery` used instead of ISR

### IP.PR.02.005 — Add Loading Skeletons
**Status:** PARTIAL
**Evidence:**
- `animate-pulse` divs used as skeleton placeholders
- No dedicated `<SkeletonCard />` shared UI component

### IP.PR.02.006 — Add Empty State for No Restaurants
**Status:** PASS
**Evidence:**
- Restaurant list shows centered message when filters yield zero results

### IP.PR.02.007 — Add Error Boundary on Restaurant Detail Page
**Status:** PASS
**Evidence:**
- `apps/web/src/app/restaurants/[id]/error.tsx` created
- Shows friendly message with retry button

### IP.PR.02.008 — Add Client-Side Debounced Search Bar
**Status:** PASS
**Evidence:**
- Sticky search input filters client-side by name + cuisine

### IP.PR.02.009 — Add Cuisine Chips on Restaurant Listing
**Status:** PASS
**Evidence:**
- Horizontal scrollable cuisine chip row exists

### IP.PR.02.010 — Add Filter Chips (Rating 4+, Veg-Only)
**Status:** PASS (with correction)
**Evidence:**
- "Veg Only" toggle chip functions client-side
- "⭐ 4+" rating filter chip explicitly added
- `rating4Plus` state → `min_rating=4.0` query param

### IP.PR.02.011 — Add Category-Specific Deterministic Unsplash Images
**Status:** PARTIAL (intentionally adapted)
**Evidence:**
- Local deterministic images used under `apps/web/public/images/restaurants/`
- No Unsplash calls per local-first policy

### IP.PR.02.012 — Update Restaurant Cards with Real Data and Trust Badges
**Status:** PASS (with correction)
**Evidence:**
- Cards show real fields: name, cuisine_types, rating, delivery_time, delivery_fee
- Trust badges added: FSSAI Verified, Freshly Prepared, Under 30 min

### IP.PR.02.013 — Add Dark Mode Toggle
**Status:** PASS
**Evidence:**
- Sun/moon toggle in Navbar
- Persisted in `localStorage` key `bhojango-theme`

### IP.PR.02.014 — Add Bottom Navigation (Mobile)
**Status:** PASS (with correction)
**Evidence:**
- `MobileBottomNav.tsx` created
- Visible only on `<640px` viewports (`sm:hidden`)
- Fixed bottom nav with Home, Search, Cart, Orders, Profile tabs
- Cart badge shows item count from Zustand cart store
- Screenshot: `tests/results/frontend/customer/screenshots/mobile-bottom-nav.png`

### IP.PR.02.015 — Extend Restaurant List API with Optional Filter Params
**Status:** PARTIAL
**Evidence:**
- `GET /api/v1/restaurants` accepts: `city`, `cuisine`, `min_rating`, `max_delivery_fee`, `is_open`, `country`, `page`, `limit`
- Cache key fixed to include all filter params: `{city}:{cuisine}:{country}:{min_rating}:{max_delivery_fee}:{is_open}:{page}:{limit}`
- `veg_only` backend param NOT implemented — Restaurant model lacks `is_veg_friendly` field; requires schema change not feasible in this scope
- Frontend `veg_only` filter uses client-side data

---

## Screenshots Captured

| Screenshot | Status |
|---|---|
| Homepage | ✓ |
| Restaurant list | ✓ |
| Restaurant detail | ✓ |
| Login page | ✓ |
| Authenticated UI | ✓ |
| Mobile restaurant list | ✓ |
| Mobile bottom nav | ✓ |

---

## Raw Logs

| Log | Path |
|---|---|
| Menu endpoint | `tests/results/evidence/logs/spr02-menu-endpoint.log` |
| Me endpoint | `tests/results/evidence/logs/spr02-me-endpoint.log` |
| OpenSearch fallback | `tests/results/evidence/logs/spr02-opensearch-fallback.log` |
| Frontend routes | `tests/results/evidence/logs/spr02-frontend-routes.log` |
| Focused tests | `tests/results/evidence/logs/spr02-unit-or-focused-tests.log` |
| Zip listing | `tests/results/evidence/logs/spr02-v3-zip-listing.log` |

---

## Overall Status

| Category | Score |
|---|---|
| P0 blockers fixed | 4/4 |
| P1 browsability | 9/13 |
| Frontend polish | 6/7 |
| Evidence completeness | 7/7 |
| **SPR-02 Status** | **PARTIAL** |

---

## Remaining Gaps

1. Dedicated skeleton UI components in `packages/ui` (IP.PR.02.005) — deferred
2. ISR on homepage (IP.PR.02.004) — deferred
3. httpOnly cookie auth (IP.PR.02.003) — deferred to PR.05
4. Backend `veg_only` query param (IP.PR.02.015) — requires schema change, not feasible
5. Unsplash images (IP.PR.02.011) — local images used per local-first policy

---

## Files Changed This Session

| File | Change | Scope ID |
|---|---|---|
| `services/user-svc/app/core/dependencies.py` | Fixed /api/v1/me to return 401 (was 401) | IP.PR.02.002 |
| `services/restaurant-svc/app/api/v1/restaurants.py` | Fixed cache key, added filter params | IP.PR.02.015 |
| `apps/web/src/app/layout.tsx` | Added MobileBottomNav | IP.PR.02.014 |
| `apps/web/src/app/restaurants/page.tsx` | Added 4+ rating chip, fixed query params | IP.PR.02.010, IP.PR.02.015 |
| `apps/web/src/components/restaurant/RestaurantCard.tsx` | Added trust badges | IP.PR.02.012 |
| `apps/web/src/components/layout/MobileBottomNav.tsx` | New — mobile bottom nav | IP.PR.02.014 |
| `tests/results/evidence/manifests/SPR-02-file-read-ledger.md` | Updated ledger | — |
| `tests/results/evidence/manifests/SPR-02-evidence.md` | Updated evidence manifest | — |
| `tests/backend/test_spr02_contracts.py` | New test artifact | validation |