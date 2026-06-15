# BhojanGo — Audit Findings & Prioritized Action Plan

**Date:** 2026-06-14
**Auditor:** Kimchi AI Agent
**Scoring:** Strict, honest, production-readiness based

---

## Critical Findings Summary

| Finding | Impact | Score |
|---------|--------|-------|
| **Restaurant menu endpoint returns 500** | Blocks entire ordering flow | 0/10 |
| **Frontend auth state not persisted** | No user can access cart/orders/profile | 0/10 |
| **Batch engine unstable** | Crashed during test run | 1/10 |
| **Zero screenshots in Playwright** | Zero visual test evidence | 1/10 |
| **56% backend tests skipped** | Majority of API never verified | 2/10 |
| **No production infrastructure** | Cannot deploy | 0/10 |
| **OpenSearch = single point of failure** | Menu dies if OpenSearch down | 1/10 |

---

## Prioritized Action Plan

### Module A — Frontend Auth & Core Flow (Priority: P0 – BLOCKING)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| A-1 | **Fix frontend auth state persistence** | Critical — All authenticated pages break | Replace storageState with httpOnly cookie-based session or properly load stored auth state in browser context. Ensure `/orders`, `/profile`, `/wallet` work post-login. |
| A-2 | **Add error boundary for restaurant detail page** | High — Blank screen on menu 500 | Wrap menu fetch in try/catch. Show "Menu temporarily unavailable" with retry button instead of blank page. |
| A-3 | **Implement offline/local cart state** | High — Cart requires auth + empty on refresh | Use Zustand + localStorage or react-query caching. Cart should persist without login. |
| A-4 | **Fix Playwright screenshot capture** | High — Zero visual evidence in tests | Add explicit `page.screenshot({ fullPage: true, path: ... })` after every meaningful action. Store in `tests/results/playwright/screenshots/`. |
| A-5 | **Implement homepage search** | Medium — "Find Food" button is dead | Wire search input to `/api/v1/restaurants/search?q=` or client-side filter by city/cuisine. |
| A-6 | **Add loading skeletons & empty states** | Medium — Poor perceived performance | Add Tailwind skeleton loaders for restaurant cards, menu items, orders. Add empty state illustrations. |

### Module B — Restaurant Service (Priority: P0 – BLOCKING)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| B-1 | **Fix `GET /api/v1/restaurants/{id}/menu` 500 error** | Critical — Entire ordering flow broken | OpenSearch connection fails. Either start OpenSearch locally (`docker run opensearchproject/opensearch`) OR implement a fallback query directly from `menu_items` / `menu_categories` tables when OpenSearch is unavailable. |
| B-2 | **Add graceful OpenSearch degradation** | High — Single point of failure | If `AsyncOpenSearch` client throws `ConnectionError`, silently fall back to direct DB query. Log warning but return 200. |
| B-3 | **Add real restaurant + menu images** | Medium — Picsum placeholders look fake | Replace stored image URLs with real food/restaurant photos from Unsplash or generated AI images. At minimum, use category-appropriate images. |
| B-4 | **Add cuisine/rating filters** | Medium — Cannot refine search | Add query params `?cuisine=Indian&min_rating=4.0` to restaurant list API and UI. |
| B-5 | **Add search endpoint** | Medium — No search capability | Implement `GET /api/v1/restaurants/search?q=kfc` using direct ILIKE on `name` and `cuisine_types`. |

### Module C — User Service (Priority: P1 – HIGH)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| C-1 | **Implement `GET /api/v1/me`** | High — Frontend needs user profile | Return `{id, email, full_name, role, phone}` from JWT token. Should be a 10-line endpoint. |
| C-2 | **Add rate limit test bypass** | Medium — Tests fail with 429 | Add env-based rate limit bypass (`APP_ENV=development`) or whitelist localhost in SlowAPI config. |
| C-3 | **Add password reset flow** | Medium — Basic user feature | POST `/api/v1/auth/forgot-password` generates OTP, POST `/api/v1/auth/reset-password` verifies OTP + new password. |
| C-4 | **Add social login** | Low — Nice-to-have | OAuth 2.0 integration with Google. Store `provider` and `provider_id` in users table. |

### Module D — Order Service (Priority: P1 – HIGH)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| D-1 | **Fix LIVE authenticated order tests** | High — Order listing untested | Debug why auth tokens caused skipped tests. Add debug logging. Verify order creation accepts valid request body. |
| D-2 | **Add order status webhook** | High — Restaurant needs order updates | POST webhook to restaurant owner URL on status change. Or use SSE/polling. |
| D-3 | **Add order cancellation flow** | Medium — User can cancel within 5 min | PATCH `/api/v1/orders/{id}/cancel` updates status to `cancelled` with reason. Refund via payment-svc. |
| D-4 | **Add order timeline/tracking** | Medium — Users track delivery | Store status history in new table `order_status_history`. Return on GET order detail. |

### Module E — Payment Service (Priority: P1 – HIGH)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| E-1 | **Fix wallet/payment live tests** | High — Wallet endpoints untested | Debug 401 failures. Ensure auth middleware is properly wired. Verify wallet top-up and payment initiation work. |
| E-2 | **Implement Razorpay webhook** | High — Must handle real payments | Endpoint `/api/v1/payments/webhooks/razorpay` validates signature and updates payment_intent status. |
| E-3 | **Implement Stripe webhook** | High — Must handle real payments | Endpoint `/api/v1/payments/webhooks/stripe` validates secret and updates payment_intent status. |
| E-4 | **Add refund endpoint** | Medium — Order cancellation needs refund | POST `/api/v1/payments/refund` creates refund via Stripe/Razorpay and updates wallet. |

### Module F — Delivery Service (Priority: P1 – HIGH)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| F-1 | **Implement driver assignment API** | High — Orders need drivers | POST `/api/v1/deliveries/{order_id}/assign` assigns nearest driver. Use distance calculation. |
| F-2 | **Add real-time driver location** | High — Users track orders | WebSocket endpoint or polling GET endpoint returning lat/lng. Store in Redis with TTL. |
| F-3 | **Add ETA calculation** | Medium — Show delivery time | Use Haversine + traffic estimates (simple avg speed 25 km/h). |

### Module G — Batch Engine (Priority: P1 – HIGH)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| G-1 | **Fix migration SQL ordering** | Critical — Deployment failure | Move `CREATE TABLE batches` BEFORE `CREATE TABLE order_pool` in `001_create_batch_tables.sql`. Already fixed but verify deployment scripts. |
| G-2 | **Add health check reconnect logic** | High — Service dies silently | Add restart policy or supervisor. Alert if health fails 3x. |
| G-3 | **Implement batch scoring algorithm** | Medium — Core value prop | Complete the batch scoring in `engine/batch-scorer.ts`. Score combinations by detour_min, distance saved. |
| G-4 | **Add RabbitMQ / real SQS integration** | Medium — Event-driven ordering | Replace mock consumer with real SQS consumer using `@aws-sdk/client-sqs`. |

### Module H — Notification Service (Priority: P2 – MEDIUM)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| H-1 | **Fix device token registration tests** | Medium — Token registration untested | Debug skipped tests. Verify POST endpoint accepts `{token, platform}`. |
| H-2 | **Add push notification delivery** | Medium — Actually send notifications | Integrate with Firebase Cloud Messaging (FCM) for Android/iOS and Web Push for web. |
| H-3 | **Add email notifications** | Low — Backup channel | Integrate with SendGrid/AWS SES for order confirmations. |

### Module I — Test Coverage (Priority: P2 – MEDIUM)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| I-1 | **Reduce backend test skip rate to <10%** | High — 56% skipped | Fix auth token fixtures, add rate limit bypass, ensure services are running before test collection. |
| I-2 | **Add integration tests (service-to-service)** | High — No cross-service tests | Test order creation → payment flow → delivery assignment end-to-end. |
| I-3 | **Add contract tests (OpenAPI)** | Medium — API drift risk | Generate OpenAPI spec from FastAPI and validate against frontend usage. |
| I-4 | **Add load tests (Locust/k6)** | Low — Performance unknown | Simulate 100 concurrent users browsing restaurants and placing orders. |

### Module J — DevOps / Infrastructure (Priority: P2 – MEDIUM)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| J-1 | **Add Dockerfile per service** | High — Currently no deployable unit | Create `Dockerfile` in each service root. Multi-stage for frontend. |
| J-2 | **Add docker-compose.yml** | High — Cannot boot full stack | Compose file with Postgres, Redis, OpenSearch, SQS, all 7 services, frontend, nginx. |
| J-3 | **Add GitHub Actions CI/CD** | High — No automated testing | Build → lint → test → deploy. Run backend tests and Playwright in CI. |
| J-4 | **Add Prometheus metrics** | Medium — No observability | Instrument FastAPI with `prometheus-fastapi-instrumentator`. Add custom counters for orders. |
| J-5 | **Add centralized logging** | Medium — Debug is hard | Use `structlog` JSON format + Fluentd/Vector to send logs to OpenSearch. |
| J-6 | **Add SSL/TLS** | Medium — Production requirement | Use Let's Encrypt + nginx reverse proxy with auto-renewal. |
| J-7 | **Add CDN for images** | Low — Performance | Upload images to S3 + CloudFront. Serve `/images/*` from CloudFront. |

### Module K — Frontend Polish (Priority: P3 – LOW)

| ID | Task | Impact | Scope |
|----|------|--------|-------|
| K-1 | **Add dark mode toggle** | Low — Nice UX | Use `next-themes` with Tailwind dark classes. |
| K-2 | **Add mobile app shell** | Low — Expansion | Use Capacitor or React Native for iOS/Android wrapper. |
| K-3 | **Add admin dashboard** | Low — Internal tool | Build analytics page for restaurant owners: daily revenue, top items. |
| K-4 | **Add A/B testing framework** | Low — Growth | Use GrowthBook or LaunchDarkly for feature flags. |

---

## Recommended Sprint Order

### Sprint 1 (Week 1) — Unblock Core Flow
- B-1: Fix restaurant menu 500
- A-1: Fix frontend auth persistence
- C-1: Add `GET /api/v1/me`
- G-1: Verify batch migration ordering

### Sprint 2 (Week 2) — Stability & Fallbacks
- B-2: OpenSearch graceful degradation
- A-3: Offline cart state
- A-2: Error boundaries
- C-2: Rate limit bypass for dev/tests

### Sprint 3 (Week 3) — Real Transactions
- E-2 / E-3: Webhooks for Razorpay + Stripe
- D-2: Order status webhooks
- D-3: Order cancellation
- F-1: Driver assignment

### Sprint 4 (Week 4) — Infrastructure
- J-1: Dockerfiles
- J-2: docker-compose
- J-3: GitHub Actions
- I-1: Fix test skip rate

---

## Honest Bottom Line

This project is a **strong prototype** with a beautiful landing page and a well-architected backend idea. However, it is **not production-ready**. The most critical gap is that the restaurant menu (the core of a food app) returns `500`. Secondary showstoppers are broken frontend auth, zero deployability, and extremely thin test verification. With 4 focused sprints (1 month), this can reach a closed-beta readiness level.



