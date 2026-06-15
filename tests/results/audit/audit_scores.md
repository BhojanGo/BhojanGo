# BhojanGo — Critical Honest Audit Scores

**Date:** 2026-06-14
**Auditor:** Kimchi AI Agent
**Scope:** Full stack — backend services, frontend web app, database, test coverage, production readiness
**Scoring:** 1–10 (10 = production-grade public app)

---

## Honest Assessment Summary

**Overall Application Score: 2.0 / 10**

This is a prototype tech demo with a polished homepage but a completely broken core user journey. The restaurant menu endpoint returns 500, authentication works at the API level but doesn't persist in the frontend, and the batch engine crashed during testing. No production infrastructure exists (Docker, CI/CD, monitoring). The project cannot be launched to public users in its current state.

---

## Backend Service Scores

| # | Module | Score | Verdict |
|---|--------|-------|---------|
| 1 | user-svc | 5.0 / 10 | JWT login works. Missing `/api/v1/me`. Rate limiter blocks legitimate automation (429). No password reset, no social login. |
| 2 | restaurant-svc | 1.0 / 10 | **CRITICAL**: `GET /api/v1/restaurants/{id}/menu` returns 500 Internal Server Error (OpenSearch crash). This breaks the entire ordering flow. No graceful degradation. |
| 3 | order-svc | 3.0 / 10 | Health passes. Schema exists. But order creation, listing, and timeline endpoints were mostly SKIPPED in live tests (unable to auth properly). No order editing, no cancellation flow. |
| 4 | delivery-svc | 2.0 / 10 | Health passes. Most endpoints untested. Driver location tracking has no real-time mechanism. No ETA calculation visible. |
| 5 | payment-svc | 2.0 / 10 | Health passes. Wallet schema exists but API surface is minimal. No Stripe/Razorpay webhook Integration working. No refund flow tested. |
| 6 | notification-svc | 2.0 / 10 | Health passes. Device tokens table exists. No push notification delivery tested. No email/SMS channel. |
| 7 | batch-engine | 1.0 / 10 | **Unstable**: Crashed during execution (missing `batches` table in migration ordering). Restarted successfully but only after manual fix. No SQS consumer running. |

**Backend Average: 2.3 / 10**

---

## Frontend Page Scores

| # | Page / Flow | Score | Verdict |
|---|-------------|-------|---------|
| 8 | Homepage (/) | 5.0 / 10 | Visually polished: hero gradient, 4-step explainer, featured restaurants section, footer. Responsive layout. **But** "Find Food" button is non-functional (no search implemented). |
| 9 | Auth / Login | 1.0 / 10 | API login works. **Frontend does NOT persist auth state.** After login, refreshing any page or navigating to `/orders` redirects back to login. This is a showstopper. |
| 10 | Restaurant List (/restaurants) | 4.0 / 10 | Loads and displays cards. 24 restaurants shown. Pagination exists. **But** uses random Picsum placeholder images, not real photos. No cuisine filter, no rating filter, no sort. |
| 11 | Restaurant Detail (/restaurants/[id]) | 0.0 / 10 | **Completely Broken**. The page loads but the menu API returns 500. No menu items shown. No "Add to Cart" buttons. This is THE most critical page in a food app and it fails entirely. |
| 12 | Cart (/cart) | 1.0 / 10 | Page skeleton exists. Requires authentication to view. No offline/local cart state. Cannot test end-to-end because menu is broken. |
| 13 | Checkout (/checkout) | 1.0 / 10 | Form UI loads. Requires auth + cart items. Cannot test because menu is broken. No address autocomplete, no payment method selection UI. |
| 14 | Orders (/orders) | 2.0 / 10 | Page skeleton exists. Redirects to login. If logged in, likely shows order cards. No order tracking UI visible in tests. |
| 15 | Profile (/profile) | 2.0 / 10 | Page skeleton exists. Redirects to login. No avatar upload, no preference management. |
| 16 | Wallet (/wallet) | 2.0 / 10 | Page skeleton exists. Redirects to login. Basic balance display. No top-up flow UI tested. |
| 17 | Navbar / Footer | 5.0 / 10 | Clean, sticky navbar, mobile hamburger, cart icon, links work. Footer has Explor


e / Account / Support columns. Good structure. |

**Frontend Average: 2.6 / 10**

---

## Cross-Cutting Scores

| # | Area | Score | Verdict |
|---|------|-------|---------|
| 18 | Data Seeding | 8.0 / 10 | Excellent: 96 restaurants, 1,669 menu items, 110 orders, 60 payment intents, wallets, notifications, batch data, 118 real images downloaded. |
| 19 | Database Schema | 6.0 / 10 | Reasonably normalized. Proper use of UUID PKs, JSONB for flexible data. Alembic migrations exist per service. No index tuning evident. Missing foreign key from `batch_orders` → `order_pool` ordering caused migration failure. |
| 20 | Backend Test Coverage | 2.0 / 10 | 57 tests written, but **56% were SKIPPED** (32/57). Only health checks and a few unauth tests ran reliably. Most authenticated endpoints never verified. Batch-engine entirely untested. |
| 21 | Frontend Test Coverage (Playwright) | 1.0 / 10 | Only 8 tests exist. All pass but merely verify page loads or redirect behavior. **Zero screenshots actually captured** despite the requirement. No testing of actual user interactions (adding items, placing orders). |
| 22 | API Design | 4.0 / 10 | RESTful structure is reasonable. But no versioning strategy beyond `/api/v1/`. No OpenAPI/Swagger for all services. Rate limiting is too aggressive for test automation. |
| 23 | Error Handling | 1.0 / 10 | `500 Internal Server Error` on a core endpoint with no graceful fallback. Frontend shows blank/error states for menu. No structured error codes across services. No retry logic. |
| 24 | Microservices Architecture | 3.0 / 10 | 7 services conceptually separated. But no API gateway, no service mesh, no retry/circuit breakers, no distributed tracing. Shared DB schema causes migration conflicts (multiple alembic_version tables needed). |
| 25 | DevOps / Production Readiness | 0.0 / 10 | No Docker. No CI/CD. No Kubernetes. No monitoring (Prometheus/Grafana). No centralized logging. No SSL/TLS config. No environment-specific configs. No CDN. No feature flags. |
| 26 | Security | 3.0 / 10 | JWT implemented. Password hashing correct. **But**: placeholder JWT secret used in dev (`dev-secret-key-change-in-production-min32chars`). No CORS configured properly. No input sanitization tested. No rate-limit bypass for health probes. Bcrypt 4.3 downgrade was needed just to boot. |
| 27 | Performance | 2.0 / 10 | No database connection pooling tuning evident. No Redis caching for restaurant lists. No CDN for images. No query optimization. OpenSearch connection timeout adds ~2s to restaurant detail page. |
| 28 | Accessibility (a11y) | 2.0 / 10 | Basic `aria-label` on some elements. No keyboard navigation tested. No screen reader compatibility verified. Color contrast untested. |
| 29 | Mobile Responsiveness | 4.0 / 10 | Tailwind responsive classes used. Grid switches to single column on mobile. Navbar collapses to hamburger. **But** "Find Food" button and search input may not be thumb-friendly. No mobile-specific optimizations. |
| 30 | Code Quality / Documentation | 2.0 / 10 | Code is readable with docstrings. But no architecture decision records (ADRs). No runbook for operations. No inline API documentation beyond Swagger on user-svc. |

---

## Honest Narrative

### The Good
1. The **homepage is visually competent** — it looks like a real food delivery app landing page.
2. The **backend was actually booted** on a local machine. Postgres + Redis + 7 services running.
3. **Data seeding was thorough** — 96 restaurants, 1,600+ menu items, realistic order data is great for demos.
4. **Authentication API works** — login returns JWT tokens correctly.

### The Bad
1. **The menu endpoint is broken** (`500 Internal Server Error`). This means no user can actually browse a restaurant's menu, select items, or add to cart. The app is functionally useless for ordering.
2. **Frontend auth is broken** — after logging in, the frontend immediately forgets you on the next page load.
3. **No screenshots were captured** by Playwright despite the explicit requirement. The test harness failed.
4. **Batch engine is unstable** — it crashed due to a migration bug and was dead during testing.

### The Ugly
1. **No production infrastructure at all.** Not even Docker.
2. **56% of backend tests were skipped.** This means the majority of the API surface was not verified.
3. **Error handling is non-existent.** Core endpoint throws 500, frontend shows blank.
4. **OpenSearch is a single point of failure.** If it goes down, the entire restaurant menu feature dies.
5. **bcrypt 5.0 compatibility issue with passlib.** A basic dependency conflict prevented the app from booting.

---

## Final Score Card

| Category | Weight | Score | Weighted |
|----------|--------|-------|----------|
| Backend API | 30% | 2.3/10 | 0.69 |
| Frontend UI/UX | 30% | 2.6/10 | 0.78 |
| Test Coverage | 15% | 1.5/10 | 0.22 |
| Data / Completeness | 10% | 7.0/10 | 0.70 |
| Production Readiness | 15% | 0.0/10 | 0.00 |
| **TOTAL** | **100%** | | **2.0/10** |
