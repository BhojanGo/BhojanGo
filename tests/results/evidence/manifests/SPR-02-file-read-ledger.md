# SPR-02 File Read Ledger — CORRECTED v3

**Date:** 2026-06-15
**Session:** SPR-02 — Browsable Prototype (Targeted Correction)
**Zip:** `review_exports/SPR-02_scope_review_v3.zip`

---

## Plans / Evidence Files (all read end-to-end)

| File Path | Exists | Read End-to-End | Changed | In Zip | Scope IDs |
|---|---|---|---|---|---|
| `implementation_plan/SP20-Master-Implementation-Sprint-Plan.md` | yes | yes | no | no | — |
| `implementation_plan/IP.PR.02 - Browsable Prototype.md` | yes | yes | no | no | — |
| `tests/results/evidence/summaries/current_handoff.md` | yes | yes | no | no | — |
| `tests/results/evidence/manifests/SPR-02-evidence.md` | yes | yes | no | no | — |
| `tests/results/evidence/manifests/SPR-02-file-read-ledger.md` | yes | yes | **yes** | yes | — |

---

## Backend — User Service Files

| File Path | Exists | Read End-to-End | Changed | In Zip | Scope IDs |
|---|---|---|---|---|---|
| `services/user-svc/app/main.py` | yes | yes | **yes** | yes | IP.PR.02.002 |
| `services/user-svc/app/core/dependencies.py` | yes | yes | **yes** | yes | IP.PR.02.002 |
| `services/user-svc/app/core/security.py` | yes | yes | **yes** | yes | IP.PR.02.002 |
| `services/user-svc/app/api/v1/auth.py` | yes | yes | no | yes | reference |
| `services/user-svc/app/api/v1/users.py` | yes | yes | no | yes | reference |
| `services/user-svc/app/models/user.py` | yes | yes | no | yes | reference |
| `services/user-svc/app/schemas/user.py` | yes | yes | no | yes | reference |
| `services/user-svc/app/repositories/user.py` | yes | yes | no | yes | reference |

---

## Backend — Restaurant Service Files

| File Path | Exists | Read End-to-End | Changed | In Zip | Scope IDs |
|---|---|---|---|---|---|
| `services/restaurant-svc/app/api/v1/restaurants.py` | yes | yes | **yes** | yes | IP.PR.02.001, IP.PR.02.015 |
| `services/restaurant-svc/app/repositories/restaurant.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/models/menu.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/models/restaurant.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/schemas/restaurant.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/services/search.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/db/migrations/versions/0002_money_to_numeric.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/db/migrations/versions/0003_pain_point_pricing_radius.py` | yes | yes | no | yes | reference |
| `services/restaurant-svc/app/db/migrations/versions/0004_add_deleted_at.py` | yes | yes | **yes** | yes | IP.PR.02.001 |
| `services/restaurant-svc/app/main.py` | yes | yes | no | yes | reference |

---

## Frontend Web App Files

| File Path | Exists | Read End-to-End | Changed | In Zip | Scope IDs |
|---|---|---|---|---|---|
| `apps/web/next.config.mjs` | yes | yes | no | yes | reference |
| `apps/web/package.json` | yes | yes | no | yes | reference |
| `apps/web/src/lib/api.ts` | yes | yes | no | yes | reference |
| `apps/web/src/store/auth.ts` | yes | yes | no | yes | reference |
| `apps/web/src/components/providers.tsx` | yes | yes | **yes** | yes | IP.PR.02.003 |
| `apps/web/src/components/AuthBootstrap.tsx` | yes | yes | **yes** | yes | IP.PR.02.003 |
| `apps/web/src/components/layout/Navbar.tsx` | yes | yes | **yes** | yes | IP.PR.02.013 |
| `apps/web/src/components/layout/MobileBottomNav.tsx` | yes | yes | **yes** | yes | IP.PR.02.014 |
| `apps/web/src/components/restaurant/RestaurantCard.tsx` | yes | yes | **yes** | yes | IP.PR.02.012 |
| `apps/web/src/components/home/FeaturedRestaurants.tsx` | yes | yes | no | yes | reference |
| `apps/web/src/app/page.tsx` | yes | yes | no | yes | reference |
| `apps/web/src/app/restaurants/page.tsx` | yes | yes | **yes** | yes | IP.PR.02.008, IP.PR.02.009, IP.PR.02.010, IP.PR.02.015 |
| `apps/web/src/app/restaurants/[id]/page.tsx` | yes | yes | no | yes | reference |
| `apps/web/src/app/restaurants/[id]/error.tsx` | yes | yes | **yes** | yes | IP.PR.02.007 |
| `apps/web/src/app/(auth)/login/page.tsx` | yes | yes | no | yes | reference |
| `apps/web/src/app/(auth)/signup/page.tsx` | yes | yes | no | yes | reference |
| `apps/web/src/app/layout.tsx` | yes | yes | **yes** | yes | IP.PR.02.014 |
| `apps/web/src/store/cart.ts` | yes | yes | no | yes | reference |

---

## New Files Created in SPR-02 Correction

| File Path | In Zip | Scope IDs |
|---|---|---|
| `apps/web/src/components/AuthBootstrap.tsx` | yes | IP.PR.02.003 |
| `apps/web/src/app/restaurants/[id]/error.tsx` | yes | IP.PR.02.007 |
| `apps/web/src/components/layout/MobileBottomNav.tsx` | yes | IP.PR.02.014 |
| `services/restaurant-svc/app/db/migrations/versions/0004_add_deleted_at.py` | yes | IP.PR.02.001 |
| `tests/backend/test_spr02_contracts.py` | yes | test artifact |

---

## Evidence Logs

| Log Path | In Zip |
|---|---|
| `tests/results/evidence/logs/spr02-menu-endpoint.log` | yes |
| `tests/results/evidence/logs/spr02-me-endpoint.log` | yes |
| `tests/results/evidence/logs/spr02-opensearch-fallback.log` | yes |
| `tests/results/evidence/logs/spr02-frontend-routes.log` | yes |
| `tests/results/evidence/logs/spr02-unit-or-focused-tests.log` | yes |
| `tests/results/evidence/logs/spr02-v3-zip-listing.log` | no — generated by packager after zip creation; exists in repo but excluded from self-reference |

---

## Screenshots

| Screenshot | In Zip |
|---|---|
| `tests/results/frontend/customer/screenshots/homepage.png` | yes |
| `tests/results/frontend/customer/screenshots/restaurants-list.png` | yes |
| `tests/results/frontend/customer/screenshots/restaurant-detail.png` | yes |
| `tests/results/frontend/customer/screenshots/login.png` | yes |
| `tests/results/frontend/customer/screenshots/authenticated-homepage.png` | yes |
| `tests/results/frontend/customer/screenshots/restaurants-list-mobile.png` | yes |
| `tests/results/frontend/customer/screenshots/mobile-bottom-nav.png` | yes |

---

## Summary

- **Total required files read end-to-end:** 38
- **Files changed in this session:** 10
- **New files created:** 5
- **Files missing from required list:** 0
- **Zip path:** `review_exports/SPR-02_scope_review_v3.zip`
- **Zip structure uses repo-relative paths:** YES

<!-- AUTO_ZIP_MEMBERSHIP_AUDIT_START -->
## Automated Zip Membership Audit

Generated by `fix_spr02_v3_evidence_docs_v2.py`.

- Stage zip: `review_exports/SPR-02_scope_review_v3.zip`
- Zip entries checked: `74`
- Ledger paths found: `57`
- Missing from zip: `2`

| Path | In Zip |
|---|---:|
| `apps/web/next.config.mjs` | Yes |
| `apps/web/package.json` | Yes |
| `apps/web/src/app/(auth)/login/page.tsx` | Yes |
| `apps/web/src/app/(auth)/signup/page.tsx` | Yes |
| `apps/web/src/app/layout.tsx` | Yes |
| `apps/web/src/app/page.tsx` | Yes |
| `apps/web/src/app/restaurants/[id]/error.tsx` | Yes |
| `apps/web/src/app/restaurants/[id]/page.tsx` | Yes |
| `apps/web/src/app/restaurants/page.tsx` | Yes |
| `apps/web/src/components/AuthBootstrap.tsx` | Yes |
| `apps/web/src/components/home/FeaturedRestaurants.tsx` | Yes |
| `apps/web/src/components/layout/MobileBottomNav.tsx` | Yes |
| `apps/web/src/components/layout/Navbar.tsx` | Yes |
| `apps/web/src/components/providers.tsx` | Yes |
| `apps/web/src/components/restaurant/RestaurantCard.tsx` | Yes |
| `apps/web/src/lib/api.ts` | Yes |
| `apps/web/src/store/auth.ts` | Yes |
| `apps/web/src/store/cart.ts` | Yes |
| `implementation_plan/IP.PR.02` | No |
| `implementation_plan/SP20-Master-Implementation-Sprint-Plan.md` | Yes |
| `review_exports/SPR-02_scope_review_v3.zip` | No |
| `services/restaurant-svc/app/api/v1/restaurants.py` | Yes |
| `services/restaurant-svc/app/db/migrations/versions/0001_create_restaurant_tables.py` | Yes |
| `services/restaurant-svc/app/db/migrations/versions/0002_money_to_numeric.py` | Yes |
| `services/restaurant-svc/app/db/migrations/versions/0003_pain_point_pricing_radius.py` | Yes |
| `services/restaurant-svc/app/db/migrations/versions/0004_add_deleted_at.py` | Yes |
| `services/restaurant-svc/app/main.py` | Yes |
| `services/restaurant-svc/app/models/menu.py` | Yes |
| `services/restaurant-svc/app/models/restaurant.py` | Yes |
| `services/restaurant-svc/app/repositories/restaurant.py` | Yes |
| `services/restaurant-svc/app/schemas/restaurant.py` | Yes |
| `services/restaurant-svc/app/services/search.py` | Yes |
| `services/user-svc/app/api/v1/auth.py` | Yes |
| `services/user-svc/app/api/v1/users.py` | Yes |
| `services/user-svc/app/core/dependencies.py` | Yes |
| `services/user-svc/app/core/security.py` | Yes |
| `services/user-svc/app/main.py` | Yes |
| `services/user-svc/app/models/user.py` | Yes |
| `services/user-svc/app/repositories/user.py` | Yes |
| `services/user-svc/app/schemas/user.py` | Yes |
| `tests/backend/test_spr02_contracts.py` | Yes |
| `tests/results/evidence/logs/spr02-frontend-routes.log` | Yes |
| `tests/results/evidence/logs/spr02-me-endpoint.log` | Yes |
| `tests/results/evidence/logs/spr02-menu-endpoint.log` | Yes |
| `tests/results/evidence/logs/spr02-opensearch-fallback.log` | Yes |
| `tests/results/evidence/logs/spr02-unit-or-focused-tests.log` | Yes |
| `tests/results/evidence/logs/spr02-v3-zip-listing.log` | Yes |
| `tests/results/evidence/manifests/SPR-02-evidence.md` | Yes |
| `tests/results/evidence/manifests/SPR-02-file-read-ledger.md` | Yes |
| `tests/results/evidence/summaries/current_handoff.md` | Yes |
| `tests/results/frontend/customer/screenshots/authenticated-homepage.png` | Yes |
| `tests/results/frontend/customer/screenshots/homepage.png` | Yes |
| `tests/results/frontend/customer/screenshots/login.png` | Yes |
| `tests/results/frontend/customer/screenshots/mobile-bottom-nav.png` | Yes |
| `tests/results/frontend/customer/screenshots/restaurant-detail.png` | Yes |
| `tests/results/frontend/customer/screenshots/restaurants-list-mobile.png` | Yes |
| `tests/results/frontend/customer/screenshots/restaurants-list.png` | Yes |

Missing paths, if any:
- `implementation_plan/IP.PR.02`
- `review_exports/SPR-02_scope_review_v3.zip`
<!-- AUTO_ZIP_MEMBERSHIP_AUDIT_END -->
