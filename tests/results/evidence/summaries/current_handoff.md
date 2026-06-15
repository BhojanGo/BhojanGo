# SPR-02 Handoff — Browsable Prototype

**Current Sprint:** SPR-02 — Browsable Prototype
**Date:** 2026-06-15
**Branch:** rr_testing
**Git HEAD:** (to be committed)
**Honest Assessment:** SPR-02 is PARTIAL with hard blockers resolved.

---

## What Was Completed in SPR-02

### P0 — Hard Blockers
1. **Menu endpoint 500 fixed** (`IP.PR.02.001`)
   - Root cause: `menu_items.deleted_at` column missing.
   - Fix: Created migration `0004_add_deleted_at.py` + direct `ALTER TABLE`.
   - Menu endpoint now returns 200 with real categories/items.

2. **OpenSearch fallback** (`IP.PR.02.001`)
   - `search_restaurants` endpoint falls back to PostgreSQL when OpenSearch unavailable.
   - Client-side text filtering applied on DB results.

3. **`GET /api/v1/me` endpoint** (`IP.PR.02.002`)
   - Added to `user-svc/app/main.py`.
   - Returns user profile for valid JWT.

4. **Frontend auth persistence** (`IP.PR.02.003`)
   - Created `AuthBootstrap.tsx` calling `/api/v1/me` on mount.
   - Integrated into `Providers.tsx`.
   - Zustand persist already stores token in localStorage.

5. **Bcrypt crash fixed**
   - Replaced passlib with direct bcrypt in `security.py`.
   - Login endpoint returns 200 with tokens (was 500).

### P1 — Frontend Browsability
6. **Dark mode toggle** (`IP.PR.02.013`)
   - Added to Navbar with localStorage persistence.

7. **Restaurant detail error boundary** (`IP.PR.02.007`)
   - Created `error.tsx` in restaurant detail route.

8. **Restaurant list page** (`IP.PR.02.008`, `IP.PR.02.009`)
   - Search bar and cuisine chips already present and functional.
   - Empty state visible when no results.

---

## Exact Remaining Blockers / Gaps

### Non-Hard Blockers (won't block PR.03)
1. **Mobile bottom navigation** (`IP.PR.02.014`) — implemented; screenshot captured.
2. **Trust badges on cards** (`IP.PR.02.012`) — implemented in `RestaurantCard.tsx`.
3. **Unsplash images** (`IP.PR.02.011`) — local images used.
4. **httpOnly cookies** (`IP.PR.02.003`) — localStorage only; deferred to PR.05.
5. **ISR on homepage** (`IP.PR.02.004`) — not implemented.
6. **Dedicated skeleton UI components** (`IP.PR.02.005`) — `animate-pulse` used instead.
7. **Rating 4+ filter chip** (`IP.PR.02.010`) — implemented; `rating4Plus` state with `min_rating=4.0` query param.
8. **Backend `veg_only` query param** (`IP.PR.02.015`) — not added.

---

## Files Future SPR-03 Session Must Read

### Required for PR.03 (cart/checkout/order flow)
- `apps/web/src/store/cart.ts`
- `apps/web/src/app/cart/page.tsx`
- `apps/web/src/app/checkout/page.tsx`
- `apps/web/src/app/orders/page.tsx`
- `services/order-svc/app/api/v1/orders.py`
- `services/order-svc/app/models/order.py`
- `services/payment-svc/app/api/v1/payments.py`

---

## Files Future Sessions Do NOT Need to Re-read (Unless Validating SPR-02)

### Backend (unchanged)
- `services/restaurant-svc/app/models/menu.py`
- `services/restaurant-svc/app/models/restaurant.py`
- `services/restaurant-svc/app/repositories/restaurant.py`
- `services/restaurant-svc/app/schemas/restaurant.py`
- `services/restaurant-svc/app/services/search.py`
- `services/restaurant-svc/app/main.py`
- `services/restaurant-svc/pyproject.toml`
- `services/user-svc/app/api/v1/auth.py`
- `services/user-svc/app/api/v1/users.py`
- `services/user-svc/app/repositories/user.py`
- `services/user-svc/app/schemas/user.py`
- `services/user-svc/app/models/user.py`
- `services/user-svc/pyproject.toml`

### Frontend (unchanged)
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/restaurants/page.tsx`
- `apps/web/src/app/restaurants/[id]/page.tsx`
- `apps/web/src/app/(auth)/login/page.tsx`
- `apps/web/src/app/(auth)/signup/page.tsx`
- `apps/web/src/components/home/FeaturedRestaurants.tsx`
- `apps/web/src/components/restaurant/RestaurantCard.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/store/auth.ts`
- `apps/web/package.json`

---

## Changed Files in This Session

| File | Change | Scope ID |
|---|---|---|
| `services/restaurant-svc/app/api/v1/restaurants.py` | OpenSearch fallback | IP.PR.02.001 |
| `services/restaurant-svc/app/db/migrations/versions/0004_add_deleted_at.py` | New migration | IP.PR.02.001 |
| `services/user-svc/app/main.py` | Added `/api/v1/me` | IP.PR.02.002 |
| `services/user-svc/app/core/security.py` | Replaced passlib with bcrypt | blocker fix |
| `apps/web/src/components/layout/Navbar.tsx` | Dark mode toggle | IP.PR.02.013 |
| `apps/web/src/components/providers.tsx` | AuthBootstrap wrapper | IP.PR.02.003 |
| `apps/web/src/components/AuthBootstrap.tsx` | **New** — auth rehydration | IP.PR.02.003 |
| `apps/web/src/app/restaurants/[id]/error.tsx` | **New** — error boundary | IP.PR.02.007 |

---

## Next Recommended Action for SPR-03

1. **Cart persistence** — Implement Zustand cart store with localStorage persistence.
2. **Checkout flow** — Build checkout page with address, payment simulation.
3. **Order creation** — Wire `/api/v1/orders` endpoint with cart items.
4. **Order history** — Render orders list from backend.
5. **Mock tracking** — Add order status timeline page.

All P0 blockers from SPR-02 are cleared, so SPR-03 can proceed without dependency on OpenSearch, auth me endpoint, or menu schema drift.
