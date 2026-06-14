# IP.PR.07 — Reliable Beta Product

## 1. Target Score Level: 7/10

## 2. Score Meaning

APIs are faster and resilient, auth/roles are consistent, checkout/order state is safer, observability/logging exists, and common edge cases are handled. The product feels reliable to beta users.

## 3. Current → Target Transition

**From PR.06 (three-sided marketplace with basic dashboards, real-time notifications, driver assignment):**
- Customer, restaurant owner, delivery partner, and admin flows exist at a basic level.
- Search, filters, address, availability, cancellation, and order status are functional.
- The marketplace has three sides operating with real-time order notifications to owners, Haversine-based driver assignment, basic order pooling/batching, role-based route guards, and live order status timelines.

**However, PR.06 is still "functionally basic":**
- Frontend data fetching has no caching: every navigation triggers a fresh API call, causing flicker and unnecessary load.
- Inter-service calls (order→payment, order→restaurant) fail instantly on network blips with no retries.
- No circuit breaker: if payment-svc is down, order creation fails immediately rather than degrading gracefully.
- Rate limiting may block test automation; development users hit 429s during rapid testing.
- Auth consistency gaps: JWT validation may vary across services, token refresh is not uniformly wired, and role claim verification is not enforced on every protected endpoint.
- Password security: bcrypt dependency conflict (bcrypt 5.0 / passlib incompatibility) prevents boot on fresh install.
- SQL injection risk: not all endpoints use parameterized queries exclusively; some search paths may use f-string SQL.
- DB queries are slow on large datasets: no indexes on `orders(user_id, status)`, `orders(restaurant_id, status)`, `order_status_history(order_id)`, etc.
- No request correlation: debugging a failed order requires manually correlating logs across 4–6 services.
- API errors are inconsistent: some services return `{detail: "..."}`, others return `{error: "..."}`, making frontend error handling fragile.
- Input validation is loose: unknown fields are silently ignored, enum values are not strictly validated, and Pydantic schemas accept extra fields.
- Order idempotency: payment creation lacks `Idempotency-Key` enforcement; duplicate submissions may create double charges.
- Cancellation/refund is basic: cancellation from `preparing` or `picked_up` may not be supported, partial refund calculation is missing, and wallet credit is not atomic with transaction record.
- Serviceability radius is not enforced server-side at checkout: frontend may block, but backend does not verify.
- Open/closed enforcement: server-side does not reject orders to closed restaurants (relies on frontend guard).
- ETA is static: `avg_prep_minutes` from DB is not combined with real-time queue size.
- Guest tracking uses mock OTP but no formal in-memory or Redis-backed OTP store for guests.
- Image URLs are not validated: broken Unsplash links show blank spaces with no fallback.
- Payment webhooks are not testable locally: no mock Stripe/Razorpay webhook simulation exists for dev testing.
- Order status updates are synchronous: order-svc directly calls notification-svc, creating tight coupling and failure cascades.
- Reviews have no moderation: users cannot report reviews; admins cannot see reported content.
- Address validation is weak: no regex/postal code validation per country; addresses stored as flat strings.
- No performance baseline: no load test script exists to measure p95 latency under concurrent users.

**Target at score 7:**
- Frontend uses TanStack Query with stale-while-revalidate, retries, error boundaries, and loading states for all data fetching.
- Server-side inter-service calls retry 3× with exponential backoff (tenacity).
- Circuit breaker (pybreaker) on payment-svc calls prevents cascade failures.
- Rate limiting is properly configured with SlowAPI, including a test-user whitelist for development.
- JWT validation middleware is consistent across all 7 services with role claim verification and token refresh mechanism.
- bcrypt<5.0 pinned across all services; password strength requirements enforced.
- 100% SQLAlchemy parameterized queries; all raw SQL audited and hardened.
- DB indexes added on high-traffic query paths.
- Every request carries `X-Request-ID`; every service logs it to stdout.
- Consistent API error format `{error, message, request_id, details}` across all services.
- Pydantic validators reject unknown fields and validate enums strictly.
- Payment creation enforces `Idempotency-Key`; duplicate keys return same response.
- Robust cancellation from any valid status with partial refund calculation and atomic wallet credit.
- Server-side Haversine distance check blocks checkout if address outside restaurant radius.
- Server-side check rejects orders to closed restaurants.
- ETA dynamically calculated from DB: `prep_time = avg_prep_minutes + (queue_size × 5 min)`.
- Guest OTP tracking uses mock SMS (console.log or in-memory code) so guests can track orders via `order_id + phone`.
- Image URLs validated for reachability with fallback to placeholder.
- Mock payment webhook simulation runs locally via cron or seed script.
- Event-driven status updates use in-memory pub/sub (or Redis) decoupling order-svc from notification-svc.
- Review report button surfaces reported reviews to admin dashboard.
- Address validation uses regex/postal code per country (IN: 6 digits, US: ZIP) and stores structured JSON.
- Load testing baseline established with `k6` or `locust` hitting core endpoints.

## 4. Implementation Objective

Harden the entire platform so it behaves reliably under real usage. Add caching, retries, validation, indexes, logging, and edge-case handling. No new user-facing features except safety improvements. The goal is beta-user trust: the app does not break under normal load, data is consistent, failures are handled gracefully, and developers can debug issues from logs.

## 5. Scope

### In Scope

1. **Client-side caching (TanStack Query):**
   - Wrap all frontend data fetching in `useQuery` / `useMutation`.
   - Stale-while-revalidate strategy: data refreshes in background while showing cached data.
   - Retries: 3 attempts with exponential backoff on network errors.
   - Error boundaries: catch API errors and show fallback UI with retry button.
   - Loading states: skeletons integrated with TanStack Query `isLoading` / `isFetching`.
   - Mutation invalidation: after order creation, invalidate `orders` and `wallet` queries.
   - Query keys structured by entity: `['orders', userId]`, `['restaurant', id]`, `['menu', restaurantId]`.

2. **Server-side retries (tenacity):**
   - Add `@retry` decorator to all inter-service HTTP clients (order-svc → payment-svc, order-svc → restaurant-svc, delivery-svc → order-svc).
   - 3 attempts, exponential backoff starting at 1s, max 10s.
   - Retry only on `ConnectError`, `TimeoutException`, `HTTPStatusError(status >= 500)`.
   - Do NOT retry on 4xx errors (client fault).
   - Log retry attempts with correlation ID.

3. **Circuit breaker (pybreaker):**
   - Wrap payment-svc calls in `CircuitBreaker` with threshold 5 failures, timeout 60s, expected exception `HTTPStatusError(status >= 500)`.
   - When open: return 503 with message "Payment service temporarily unavailable. Please retry in 60 seconds."
   - When half-open: allow 1 test request before closing.
   - Expose `/health` endpoint that reports breaker state.

4. **Rate limiting (SlowAPI):**
   - Configure per-endpoint limits: auth endpoints 5/min, order creation 10/min, search 30/min, admin endpoints 60/min.
   - Add `APP_ENV=development` bypass or test-user whitelist (email patterns like `test-*@bhojango.local`).
   - Return consistent rate-limit error format with `Retry-After` header.
   - Apply to all 6 Python services.

5. **Auth consistency:**
   - JWT validation middleware on every protected endpoint across all services.
   - Role claim verification: `require_role` dependency that checks `role` in JWT payload against allowed roles.
   - Token refresh mechanism: `POST /api/v1/auth/refresh` returns new access token; refresh token rotated and stored in Redis with TTL.
   - Logout invalidates both access and refresh tokens in Redis blacklist.
   - Kong gateway validates JWT at edge; services also validate independently (defense-in-depth).

6. **Password security:**
   - Pin `bcrypt<5.0.0` in all service `pyproject.toml` files.
   - Enforce password strength: minimum 8 chars, at least 1 uppercase, 1 lowercase, 1 digit, 1 special character.
   - Reject common passwords (top 1000 list) at registration.
   - Hash with bcrypt work factor 12.
   - Fail service startup if bcrypt version is incompatible (catch ImportError and exit).

7. **SQL injection hardening:**
   - Audit all raw SQL across 6 Python services.
   - Convert any f-string or `.format()` SQL to SQLAlchemy `text()` with bound parameters.
   - Enforce 100% parameterized queries in code review checklist.
   - Add `sqlmap` scan to CI security pipeline (dry-run for detection).

8. **DB indexes:**
   - `orders(user_id, status)` — customer order history queries.
   - `orders(restaurant_id, status)` — owner dashboard order list queries.
   - `order_status_history(order_id)` — tracking page history queries.
   - `menu_items(restaurant_id, category_id)` — menu detail page queries.
   - `reviews(restaurant_id)` — restaurant review listing queries.
   - `favorites(user_id)` — customer favorites page queries.
   - `restaurants(status, is_active)` — public restaurant list queries.
   - Add Alembic migration for each index.

9. **Request correlation ID:**
   - Kong gateway generates `X-Request-ID` UUID for every incoming request.
   - Pass header to all downstream services.
   - Every service logs `request_id` in every log line via structlog context variable.
   - Frontend includes `X-Request-ID` on all API calls (generate UUID in request interceptor).
   - Simple stdout JSON logs are enough; no need for Loki/Jaeger in PR.07.

10. **Consistent API error format:**
    - Standard envelope: `{error: "ERROR_CODE", message: "Human-readable", request_id: "uuid", details: {}}`.
    - Map all FastAPI HTTPException to this format via custom exception handler.
    - Map all Pydantic ValidationError to this format with `details` containing field errors.
    - Map all rate-limit 429, circuit breaker 503, auth 401/403 to this format.
    - Apply to all 6 Python services.
    - Frontend interceptor parses this format and shows `message` in toast.

11. **Strict input validation:**
    - Pydantic v2 `model_config = ConfigDict(extra='forbid')` on all request schemas.
    - Enum validation: use `Literal[...]` or `Enum` types; reject invalid values with 400.
    - Custom validators on `email`, `phone`, `price`, `quantity` fields.
    - Reject negative prices, zero quantities, malformed emails.
    - Validate `country_code` against allowed list (`US`, `IN`).

12. **Order idempotency:**
    - `POST /api/v1/payments/initiate` and `POST /api/v1/orders` require `Idempotency-Key` header.
    - Store key → response mapping in Redis with TTL 24h.
    - Duplicate key within TTL returns cached response (same HTTP status, same body).
    - Key is a UUID v4 generated by frontend per user action.
    - Invalidate idempotency cache on order cancellation or refund.

13. **Robust cancellation/refund:**
    - Allow cancellation from `pending`, `confirmed`, or `preparing` statuses.
    - Reject cancellation from `picked_up` or `delivered` with 400.
    - Partial refund calculation: if `preparing`, refund 80% (20% kitchen penalty); if `confirmed`, refund 95% (5% platform fee); if `pending`, refund 100%.
    - Refund amount credited to wallet atomically: `BEGIN; UPDATE wallets SET balance = balance + ?; INSERT INTO wallet_transactions ...; COMMIT`.
    - Wallet transaction record includes `reference_type = 'order_cancellation'` and `reference_id = order_id`.

14. **Serviceability enforcement at checkout:**
    - Server-side Haversine check in `POST /api/v1/orders`: calculate distance between customer address lat/lng and restaurant lat/lng.
    - If distance > `restaurant.delivery_radius_km`, return 400 with error code `OUT_OF_SERVICE_AREA` and message "This restaurant does not deliver to your address.".
    - Include `nearest_restaurants: [...]` in error details (3 closest restaurants within radius).

15. **Open/closed enforcement:**
    - Server-side check in `POST /api/v1/orders`: verify `restaurant.is_open = true` and current time is within `opens_at` / `closes_at` for today.
    - If closed, return 400 with error code `RESTAURANT_CLOSED` and message "This restaurant is currently closed. Opens at {time}.".
    - Frontend already blocks; this is defense-in-depth.

16. **ETA calculation from DB:**
    - `GET /api/v1/restaurants/{id}` and `GET /api/v1/orders/{id}` compute dynamic ETA.
    - Query: `SELECT COUNT(*) FROM orders WHERE restaurant_id = ? AND status IN ('confirmed', 'preparing')` → `queue_size`.
    - Formula: `eta_minutes = avg_prep_minutes + (queue_size * 5) + delivery_time_minutes`.
    - `delivery_time_minutes` = Haversine distance / 25 km/h * 60.
    - Cache result in Redis for 60s per restaurant.

17. **OTP guest tracking:**
    - Mock SMS via `console.log` (frontend) or in-memory store (backend) for demo.
    - `POST /api/v1/guest/otp/send` accepts `{phone}`. Generates 6-digit code, stores in Redis with TTL 10m, logs to stdout: `[MOCK SMS] OTP 123456 sent to +91-9876543210`.
    - `POST /api/v1/guest/otp/verify` accepts `{phone, code, order_id}`. Verifies code and returns order status.
    - No real Twilio call for guest OTP (to save cost in beta).

18. **Image URL validation:**
    - Before rendering image in frontend, `HEAD` request to URL with 3s timeout.
    - If 404/timeout/5xx, replace with placeholder image (`/images/placeholder-food.jpg`).
    - Backend `POST /api/v1/restaurants` and `PATCH /api/v1/menu-items` validate `image_url` is HTTPS and returns 200 on HEAD.
    - Add placeholder image asset to `apps/web/public/images/`.

19. **Mock payment webhook simulation:**
    - Seed script or cron job (every 60s) simulates Stripe/Razorpay webhook POST to `POST /api/v1/payments/webhooks/{provider}`.
    - Payload includes realistic event structure (`payment_intent.succeeded` or `order.paid`).
    - Signature generated with test secret so webhook handler validates successfully.
    - Configurable via env `MOCK_WEBHOOKS_ENABLED=true` for dev/demo only.

20. **Event-driven status updates:**
    - Decouple order-svc from notification-svc using Redis pub/sub or in-memory event bus.
    - On status change, order-svc publishes `order.status_changed` event with `{order_id, old_status, new_status, timestamp}`.
    - Notification-svc subscribes and dispatches push/SMS/email based on event type.
    - If notification-svc is down, events remain in Redis stream for 24h and are consumed on restart.

21. **Review moderation flags:**
    - Add `is_reported` BOOLEAN default false and `report_reason` TEXT to `reviews` table.
    - `POST /api/v1/reviews/{id}/report` accepts `{reason}`. Sets `is_reported = true`.
    - Admin dashboard shows "Reported Reviews" tab with review text, reporter, reason, and actions (dismiss or remove).
    - Reported reviews are hidden from customer view after 3+ reports (auto-moderation threshold).

22. **Address validation:**
    - Regex validation per country:
      - IN: postal code `/^\d{6}$/`, phone `/^\+91\d{10}$/`.
      - US: ZIP `/^\d{5}(-\d{4})?$/`, phone `/^\+1\d{10}$/`.
    - Store address as structured JSON: `{street, city, state, postal_code, country, lat, lng, label}`.
    - Pydantic model validates structure and rejects malformed addresses.
    - Migration converts existing flat string addresses to JSONB.

23. **Load testing baseline:**
    - `k6` or `locust` script hitting core endpoints: `GET /restaurants`, `GET /restaurants/{id}/menu`, `POST /orders`, `GET /orders/{id}`.
    - Simulate 50 concurrent virtual users for 5 minutes.
    - Measure and record p50, p95, p99 latency and error rate.
    - Script saved in `tests/load/` directory.
    - Baseline report included in PR.07 evidence.

### Out of Scope

- Real payment webhooks (Stripe/Razorpay production)
- Real push/email/SMS dispatch (FCM/SendGrid/Twilio production wiring)
- CDN / S3 production setup
- Full observability stack (Prometheus and CloudWatch exist but Grafana/Loki/Jaeger dashboard polish deferred)
- CI/CD pipeline improvements
- Group ordering, loyalty activation, meal rescue, smart lockers
- AI/ML recommendations
- Blockchain / carbon neutral features
- Real-time map with moving driver pin (Mapbox/Leaflet deferred)
- Advanced route optimization
- Onboarding flow after signup
- Social login frontend wiring

## 6. Out of Scope (Summary)

- Real production payment webhooks, FCM push, SendGrid email, Twilio SMS.
- CDN/S3 for images, image optimization pipeline.
- Full observability dashboard polish (Grafana/Loki/Jaeger).
- CI/CD improvements.
- Group ordering, loyalty activation, meal rescue, smart lockers.
- AI/ML recommendations.
- Real-time map tracking, advanced route optimization.
- Onboarding flow, social login frontend wiring.

## 7. Required Capabilities

- Frontend data fetching uses TanStack Query with caching, retries, error boundaries, and loading states for all endpoints.
- Inter-service HTTP calls retry 3× with exponential backoff on 5xx/connection errors.
- Circuit breaker on payment-svc calls prevents cascade failures; returns 503 when open.
- Rate limiting is configured per endpoint with development whitelist; 429 errors use consistent format.
- JWT validation middleware runs on every protected endpoint across all 6 Python services with role claim verification.
- Token refresh mechanism issues new access tokens and rotates refresh tokens in Redis.
- bcrypt<5.0 pinned; password strength requirements enforced at registration.
- 100% SQLAlchemy parameterized queries; no f-string SQL remains in codebase.
- DB indexes added on high-traffic columns; query latency measurably improves.
- Every request carries `X-Request-ID` and every service logs it.
- All API errors return consistent `{error, message, request_id, details}` format.
- Pydantic schemas reject unknown fields and strictly validate enums.
- Order and payment creation enforce `Idempotency-Key`; duplicates return cached response within 24h.
- Cancellation supported from `pending`, `confirmed`, `preparing` with partial refund logic and atomic wallet credit.
- Server-side serviceability check blocks checkout for out-of-radius addresses.
- Server-side open/closed check blocks checkout for closed restaurants.
- Dynamic ETA calculated from `avg_prep_minutes + (queue_size * 5) + delivery_time`.
- Guest OTP tracking works via mock SMS for order tracking without login.
- Broken image URLs fall back to placeholder.
- Mock payment webhooks simulate provider callbacks locally for dev testing.
- Order status updates use event bus decoupling order-svc from notification-svc.
- Review report button surfaces reported content to admin.
- Addresses validated by country-specific regex and stored as structured JSON.
- Load test baseline establishes p95 latency for core endpoints.

## 8. Key User Journeys

### Journey 8.1 — Customer Orders with Cached Data
1. Customer logs in and browses restaurant list.
2. First load fetches from API; TanStack Query caches results for 5 minutes.
3. Customer navigates to restaurant detail, adds items, goes to cart.
4. Customer returns to restaurant list — data loads instantly from cache, background refresh updates any changes.
5. If API fails on refresh, customer sees cached data with subtle "offline" indicator.
6. Customer proceeds to checkout; server-side serviceability check confirms address is within radius.
7. Customer places order; `Idempotency-Key` prevents double-charge on retry.

### Journey 8.2 — Owner Receives Real-Time Update via Event Bus
1. Customer places order (status `pending`).
2. Order-svc publishes `order.status_changed` event to Redis pub/sub.
3. Notification-svc consumes event and sends SSE push to owner's dashboard.
4. Owner dashboard toast appears within 2 seconds.
5. Owner accepts order (status `confirmed`).
6. Event bus propagates update to customer tracking page (via polling or WebSocket).
7. If notification-svc is temporarily down, event remains in Redis stream and is delivered on recovery.

### Journey 8.3 — Guest Tracks Order via OTP
1. Guest places order without login; checkout captures phone number.
2. System generates 6-digit OTP, logs to stdout: `[MOCK SMS] OTP 123456 sent to +91-9876543210`.
3. Guest navigates to `/track` and enters `order_id` + phone.
4. Guest requests OTP; mock SMS logged again.
5. Guest enters OTP; backend verifies against Redis.
6. Guest sees order status timeline without creating an account.

### Journey 8.4 — Cancellation with Partial Refund
1. Customer places order and it is confirmed by restaurant.
2. Customer opens order detail and taps "Cancel Order".
3. Backend checks status is `confirmed`; calculates 95% refund (5% platform fee retained).
4. Wallet credited atomically: `BEGIN; UPDATE wallets ...; INSERT INTO wallet_transactions ...; COMMIT`.
5. Customer sees confirmation: "Order cancelled. ₹570 refunded to wallet.".
6. If status were `preparing`, refund would be 80% (20% kitchen penalty).

### Journey 8.5 — Admin Moderates Reported Review
1. Customer views restaurant reviews and sees inappropriate content.
2. Customer taps "Report" and selects reason "Offensive language".
3. `POST /api/v1/reviews/{id}/report` sets `is_reported = true`.
4. Admin navigates to `/admin/reviews/reported` tab.
5. Admin sees reported review with text, reporter, reason, and action buttons.
6. Admin clicks "Remove Review"; review is soft-deleted (`is_active = false`).
7. Customer view updates; review no longer visible.

## 9. Technical Coverage

### Backend
- **user-svc:**
  - Update `pyproject.toml` to pin `bcrypt<5.0.0`.
  - Add password strength validator to registration schema.
  - Ensure `POST /api/v1/auth/refresh` rotates refresh token in Redis.
  - Add `X-Request-ID` logging via structlog context.
  - Apply consistent error format handler.
  - Add `ConfigDict(extra='forbid')` to all Pydantic request schemas.
  - Add rate limit config with dev whitelist.
  - Add correlation ID middleware.
- **restaurant-svc:**
  - Add tenacity retries to OpenSearch client calls.
  - Add fallback to DB query on OpenSearch connection error.
  - Add `HEAD` validation for `image_url` on create/update.
  - Add dynamic ETA calculation endpoint.
  - Add DB indexes via Alembic migration.
  - Audit all SQL for parameterized queries.
  - Add correlation ID logging.
  - Apply consistent error format.
- **order-svc:**
  - Add tenacity retries to payment-svc and restaurant-svc HTTP clients.
  - Add pybreaker circuit breaker around payment-svc calls.
  - Add `Idempotency-Key` middleware for `POST /api/v1/orders`.
  - Add server-side serviceability Haversine check.
  - Add server-side open/closed check.
  - Add robust cancellation with partial refund logic.
  - Add Redis pub/sub publisher for status changes.
  - Add correlation ID logging.
  - Apply consistent error format.
  - Add strict Pydantic validation.
- **delivery-svc:**
  - Add tenacity retries to order-svc HTTP client.
  - Add correlation ID logging.
  - Apply consistent error format.
  - Add driver location validation (lat/lng bounds).
- **payment-svc:**
  - Add `Idempotency-Key` middleware for `POST /api/v1/payments/initiate`.
  - Add mock webhook simulation script (cron or seed).
  - Add correlation ID logging.
  - Apply consistent error format.
  - Add webhook signature validation for test mode.
- **notification-svc:**
  - Add Redis pub/sub consumer for `order.status_changed` events.
  - Add correlation ID logging.
  - Apply consistent error format.
  - Add retry with backoff for failed push/email/SMS sends.
- **batch-engine:**
  - Add correlation ID propagation in SQS/SNS messages.
  - Apply consistent error format.

### Frontend
- **apps/web:**
  - Install and configure `@tanstack/react-query`.
  - Wrap all `fetch` calls in `useQuery` with structured query keys.
  - Add `QueryClient` with `staleTime: 5 * 60 * 1000`, `retry: 3`, `retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000)`.
  - Add React Error Boundary component around route segments.
  - Add request interceptor to generate `X-Request-ID` UUID.
  - Add response interceptor to parse consistent error format and show toast.
  - Add image validation hook (`useImageValidation`) that falls back to placeholder.
  - Add guest OTP tracking UI (`/track` page).
  - Wire cancellation button with partial refund display.
  - Add review report button and modal.
- **apps/admin:**
  - Add TanStack Query for all admin data fetching.
  - Add "Reported Reviews" tab with table and actions.
  - Add address validation display (structured JSON viewer).
- **apps/mobile:**
  - Add TanStack Query (or equivalent caching) for API calls.
  - Add guest OTP tracking screen.
  - Add image placeholder fallback.

### Data
- Alembic migrations:
  - Add indexes: `orders(user_id, status)`, `orders(restaurant_id, status)`, `order_status_history(order_id)`, `menu_items(restaurant_id, category_id)`, `reviews(restaurant_id)`, `favorites(user_id)`, `restaurants(status, is_active)`.
  - Add `reviews.is_reported` BOOLEAN default false, `reviews.report_reason` TEXT.
  - Convert `addresses.address_line` (or equivalent flat field) to structured JSONB if not already.
- Seed data updates:
  - Ensure test users match whitelist pattern for rate limit bypass.
  - Add placeholder food image to `public/images/`.

## 10. UI / UX Coverage

- **Loading states:** TanStack Query `isLoading` triggers skeletons; `isFetching` triggers subtle pull-to-refresh or indicator.
- **Error states:** Error boundaries catch React render errors; API errors show toast with retry button. Offline indicator banner when `navigator.onLine` is false.
- **Empty states:** Unchanged from PR.06.
- **Success states:** Toast on cache invalidation success, order cancellation confirmation with refund amount.
- **Design system:** Unchanged from PR.06. No new UI components except error boundary and offline indicator.
- **Responsive:** Unchanged.
- **Dark mode:** Unchanged.
- **Accessibility:** Error toasts have `role="alert"`. Retry buttons have clear focus states.

## 11. Data / Model Coverage

- `orders` table: indexes on `(user_id, status)`, `(restaurant_id, status)`.
- `order_status_history` table: index on `(order_id)`.
- `menu_items` table: index on `(restaurant_id, category_id)`.
- `reviews` table: new columns `is_reported` BOOLEAN default false, `report_reason` TEXT; index on `(restaurant_id)`.
- `favorites` table: index on `(user_id)`.
- `restaurants` table: index on `(status, is_active)`.
- `addresses` table: migrate to structured JSONB if flat string.
- Redis: `idempotency:{key}` keys with TTL 86400. `guest:otp:{phone}` keys with TTL 600.
- No new PostgreSQL tables required.

## 12. Role / Permission Coverage

- `customer`: Can cancel own orders within valid statuses. Can report reviews. Can track guest orders via OTP. Subject to rate limits.
- `restaurant_owner`: Can view and manage own restaurant orders. Can toggle menu availability. Cannot cancel customer orders (only reject pending). Subject to rate limits.
- `delivery_partner`: Can accept/mark deliveries. Can update location. Cannot cancel orders. Subject to rate limits.
- `admin` / `super_admin`: Can view reported reviews and take action (dismiss/remove). Can view all user data. Can bypass rate limits (or have higher limits). Subject to rate limits on admin endpoints.
- Guest (unauthenticated): Can track orders via OTP. Can browse restaurants. Subject to lower rate limits.
- **Cross-role enforcement:** JWT middleware + role claim verification on every protected endpoint. Unmatched roles return 403 with consistent error format.

## 13. Performance / Reliability / Security Coverage

### Performance
- TanStack Query client-side caching reduces API call volume by ~60% for repeat navigations.
- DB indexes reduce order list, history, and menu query latency by 50–80% on large datasets.
- Redis caching for ETA calculation avoids repeated `COUNT(*)` queries.
- Rate limiting prevents resource exhaustion from accidental or malicious traffic.

### Reliability
- Tenacity retries on inter-service calls absorb transient network failures (3× backoff).
- Circuit breaker isolates payment-svc failures, preventing order-svc threads from hanging.
- Event bus decouples order-svc from notification-svc: notification downtime does not block orders.
- Idempotency keys prevent duplicate orders/payments on client retries.
- Mock webhook simulation ensures payment webhook handler is testable in local dev.
- Image URL validation prevents broken image UI states.

### Security
- JWT validation on every endpoint + role claim verification.
- Token refresh rotation in Redis mitigates token theft.
- bcrypt<5.0 pin prevents passlib incompatibility and ensures consistent hashing.
- Password strength requirements reduce credential stuffing success.
- SQL injection hardening: 100% parameterized queries, no f-string SQL.
- Rate limiting per endpoint prevents brute-force attacks.
- `Idempotency-Key` prevents replay attacks on payment creation.
- Request correlation IDs aid forensic analysis of security incidents.

## 14. Novelty / Differentiation Coverage

At score 7, novelty is not the focus — reliability is. However, some differentiation naturally emerges:
- **Transparent fee breakdown + partial refund policy** — Users see exactly how much is refunded and why (kitchen penalty, platform fee). Builds trust.
- **Dynamic ETA from real queue size** — ETA is not static; it reflects actual kitchen load. More accurate than competitors' static estimates.
- **Guest OTP tracking without app install** — No-account users can track orders via SMS OTP. Reduces friction for first-time users.
- **Review moderation transparency** — Users can report bad reviews; admins act. Creates a cleaner, more trustworthy review ecosystem.

Differentiators deferred: group ordering, loyalty activation, meal rescue, smart lockers, AI suggestions, voice ordering, real-time map tracking — all moved to PR.08+.

## 15. Implementation Work Items

### IP.PR.07.001 — TanStack Query Integration + Caching
- **Category:** Frontend
- **Implementation Scope:** Install `@tanstack/react-query` in `apps/web`, `apps/admin`, and `apps/mobile`. Create `QueryClient` instance with `staleTime: 5m`, `retry: 3`, `retryDelay` exponential. Wrap all existing `fetch`/`axios` calls in `useQuery` / `useMutation` with structured query keys (`['orders', userId]`, `['restaurant', id]`, etc.). Add mutation invalidation: after `createOrder`, invalidate `['orders']` and `['wallet']`. Add `isLoading` / `isFetching` states to all pages (skeletons already exist from PR.06). Add React Error Boundary component in `apps/web` catching render errors and showing retry UI.
- **Acceptance Criteria:**
  1. Restaurant list loads from cache on second visit within 5 minutes (no API call visible in Network tab).
  2. Failed API calls retry 3× before showing error toast.
  3. Mutation invalidation refreshes related queries automatically.
  4. Error boundary catches component crashes and shows fallback UI with reload button.
- **Evidence Required:** Screen recording: navigate to restaurant list → reload page → navigate away and back → instant load from cache. Network tab showing cache hit.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06 (functional dashboards exist)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.002 — Server-Side Retries + Circuit Breaker
- **Category:** Backend
- **Implementation Scope:** Add `tenacity` to all Python service `pyproject.toml` files. Create shared `RetryableClient` wrapper around `httpx`/`aiohttp` with `@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))` for 5xx/connection errors. Apply to: order-svc → payment-svc, order-svc → restaurant-svc, delivery-svc → order-svc. Add `pybreaker` circuit breaker around payment-svc calls in order-svc: threshold 5 failures, timeout 60s. When open: return 503 with consistent error format. Add `/health` endpoint reporting breaker state.
- **Acceptance Criteria:**
  1. Inter-service HTTP call with 500 response retries 3× before failing.
  2. After 5 consecutive payment-svc failures, circuit breaker opens and returns 503.
  3. After 60s, breaker half-opens and allows test request.
  4. No retry on 4xx errors.
- **Evidence Required:** `curl` output showing retry logs. Forced payment-svc shutdown → order creation returns 503. Logs show circuit breaker state transitions.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.003 — Rate Limiter Config
- **Category:** Backend
- **Implementation Scope:** Configure SlowAPI in all 6 Python services with per-endpoint limits: auth 5/min, orders 10/min, search 30/min, admin 60/min. Add environment-based whitelist: if `APP_ENV=development` or email matches `test-*@bhojango.local`, bypass rate limit. Return consistent 429 format with `Retry-After` header. Ensure rate limit does not block `pytest` test suite (whitelist test client or use separate test env).
- **Acceptance Criteria:**
  1. Rapid sequential API calls beyond limit return 429 with `Retry-After`.
  2. Test users bypass rate limit in development.
  3. All 6 services have rate limiting configured.
  4. `pytest` passes without artificial delays.
- **Evidence Required:** `curl` loop showing 429 after limit. Test user bypassing limit. `pytest` output.
- **Priority:** P0
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.004 — Auth Consistency + Token Refresh
- **Category:** Backend + Frontend
- **Implementation Scope:** Ensure every protected endpoint in all 6 Python services uses JWT validation middleware that checks `Authorization: Bearer` header and decodes payload. Add `require_role` dependency that accepts allowed roles and returns 403 if JWT `role` claim mismatches. Ensure `POST /api/v1/auth/refresh` in user-svc: validates refresh token, generates new access token, rotates refresh token (deletes old from Redis, stores new with TTL), returns new pair. Frontend: intercept 401 responses, call refresh endpoint silently, retry original request. If refresh fails, redirect to login.
- **Acceptance Criteria:**
  1. Every protected endpoint rejects requests without valid JWT (401).
  2. Role mismatch returns 403 with consistent error format.
  3. Token refresh returns new access token and rotates refresh token in Redis.
  4. Frontend silently refreshes expired tokens and retries failed requests.
  5. Logout blacklists both tokens in Redis.
- **Evidence Required:** `curl` without token → 401. Wrong role → 403. Token refresh response. Redis CLI showing old refresh deleted, new stored.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06 (auth exists but needs hardening)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.005 — Password Security + bcrypt Pinning
- **Category:** Backend
- **Implementation Scope:** Pin `bcrypt<5.0.0` in all 6 Python service `pyproject.toml` files. Add password strength validator: min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char. Reject common passwords (top 1000 list loaded from file or hardcoded subset). Use bcrypt work factor 12. At service startup, catch `ImportError` from passlib/bcrypt incompatibility and exit with clear error message.
- **Acceptance Criteria:**
  1. `poetry install` on fresh clone works without manual pip fix.
  2. Weak passwords ("password123", "12345678") rejected at registration.
  3. Strong password accepted and hashed with bcrypt.
  4. Service refuses to start if bcrypt version is incompatible.
- **Evidence Required:** `poetry install` output. Registration attempt with weak password → 400. Registration with strong password → success. Hash verification in DB.
- **Priority:** P0
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.006 — SQL Injection Audit
- **Category:** Backend
- **Implementation Scope:** grep all `.py` files across 6 services for `.format(` and `f"` in SQL context. Audit every raw SQL query. Convert any remaining string-interpolated SQL to SQLAlchemy `text(...)` with bound parameters or ORM queries. Add `sqlmap` scan to CI security pipeline (dry-run mode). Document in `SECURITY.md` that all queries are parameterized.
- **Acceptance Criteria:**
  1. Zero f-string or `.format()` SQL queries in backend codebase.
  2. All raw SQL uses `text()` with `:param` bindings.
  3. `sqlmap` scan returns no injection vectors.
  4. `SECURITY.md` documents SQL injection prevention policy.
- **Evidence Required:** `grep` output showing zero f-string SQL. `sqlmap` scan report. `SECURITY.md` excerpt.
- **Priority:** P0
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.007 — DB Indexes
- **Category:** Backend
- **Implementation Scope:** Create Alembic migration adding indexes: `orders(user_id, status)`, `orders(restaurant_id, status)`, `order_status_history(order_id)`, `menu_items(restaurant_id, category_id)`, `reviews(restaurant_id)`, `favorites(user_id)`, `restaurants(status, is_active)`. Verify index usage with `EXPLAIN ANALYZE` on representative queries. Document expected latency improvement.
- **Acceptance Criteria:**
  1. All 7 indexes created successfully via migration.
  2. `EXPLAIN ANALYZE` shows index scans (not sequential scans) on representative queries.
  3. Order list query latency <200ms with 10k+ rows.
- **Evidence Required:** `EXPLAIN ANALYZE` output before and after index creation. Migration file.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.008 — Correlation ID Logging
- **Category:** Backend + Frontend + Gateway
- **Implementation Scope:** Kong gateway config: inject `X-Request-ID` header (UUID v4) if not present from client. Frontend: generate `X-Request-ID` UUID in API client interceptor and include on all requests. Backend: middleware extracts `X-Request-ID` from headers and binds to structlog context (`structlog.contextvars.bind_contextvars(request_id=...)`). Every log line includes `request_id` field. Propagate header in all inter-service HTTP calls.
- **Acceptance Criteria:**
  1. Every API request includes `X-Request-ID` header.
  2. Every service log line contains matching `request_id`.
  3. Inter-service calls preserve the same `request_id`.
  4. Single `grep` on `request_id` across all service logs shows full request trace.
- **Evidence Required:** `curl -v` showing `X-Request-ID`. Log output from 3 services with same `request_id`.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.009 — Consistent API Error Format
- **Category:** Backend
- **Implementation Scope:** Create `ApiError` class and custom FastAPI exception handler in each Python service. Handler catches `HTTPException`, `ValidationError`, and generic `Exception`. Returns JSON: `{error: "ERROR_CODE", message: "...", request_id: "...", details: {}}`. Map common errors: `UNAUTHORIZED`, `FORBIDDEN`, `VALIDATION_ERROR`, `RATE_LIMITED`, `SERVICE_UNAVAILABLE`, `NOT_FOUND`. Update all manual `raise HTTPException` calls to use `ApiError`. Ensure frontend interceptor parses this format.
- **Acceptance Criteria:**
  1. All error responses across all 6 services follow the same JSON structure.
  2. `ValidationError` includes field-level `details`.
  3. Rate limit 429 includes `error: "RATE_LIMITED"`.
  4. Circuit breaker 503 includes `error: "SERVICE_UNAVAILABLE"`.
- **Evidence Required:** `curl` outputs for 400, 401, 403, 404, 429, 503 showing identical envelope structure.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.010 — Strict Input Validation
- **Category:** Backend
- **Implementation Scope:** Add `model_config = ConfigDict(extra='forbid')` to all Pydantic v2 request schemas across 6 services. Replace loose string fields with constrained types: `EmailStr`, `PhoneStr` (custom), `PositiveInt`, `Decimal` with bounds. Use `Literal[...]` or `Enum` for all enum-like fields (status, role, payment_method). Add custom validators for `country_code` (must be `US` or `IN`), `postal_code` (matches country regex), `image_url` (must be HTTPS). Reject requests with unknown fields (400).
- **Acceptance Criteria:**
  1. Request with extra unknown fields returns 400 with `VALIDATION_ERROR`.
  2. Invalid enum value returns 400 with allowed values in `details`.
  3. Negative price or zero quantity returns 400.
  4. Malformed email returns 400.
- **Evidence Required:** `curl` with extra field → 400. Invalid enum → 400. Negative price → 400.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.011 — Order Idempotency Keys
- **Category:** Backend
- **Implementation Scope:** Middleware in order-svc and payment-svc: check `Idempotency-Key` header on `POST /api/v1/orders` and `POST /api/v1/payments/initiate`. If key exists in Redis and TTL not expired, return cached response (same status code, same body). If key is new, process request, store response in Redis with TTL 24h, return response. Include `Idempotency-Key` in frontend order creation and payment initiation flows. Invalidate cache on order cancellation or refund.
- **Acceptance Criteria:**
  1. Duplicate `Idempotency-Key` within 24h returns identical response (same order_id or payment_id).
  2. No duplicate order or payment created on double-submit.
  3. Cache invalidated on cancellation.
  4. Missing key returns 400 `IDEMPOTENCY_KEY_REQUIRED`.
- **Evidence Required:** `curl` with same key twice → identical response. DB query confirming single order.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.012 — Robust Cancellation/Refund
- **Category:** Backend + Frontend
- **Implementation Scope:** Backend: `PATCH /api/v1/orders/{id}/cancel` validates status is `pending`, `confirmed`, or `preparing`. Calculates refund: pending = 100%, confirmed = 95%, preparing = 80%. Uses DB transaction to atomically update `orders.status = 'cancelled'`, insert `order_status_history`, credit wallet, insert `wallet_transaction`. Frontend: order detail page shows "Cancel Order" button only for valid statuses. Displays calculated refund amount in confirmation modal. Shows success toast with refund details.
- **Acceptance Criteria:**
  1. Cancellation from `pending` refunds 100% to wallet.
  2. Cancellation from `confirmed` refunds 95%.
  3. Cancellation from `preparing` refunds 80%.
  4. Cancellation from `picked_up` returns 400.
  5. Wallet credit and transaction record are atomic (no partial updates).
- **Evidence Required:** Screen recording: cancel confirmed order → see 95% refund → wallet balance updates. DB query showing `wallet_transactions` entry.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.05 (cancellation basic flow)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.013 — Serviceability Enforcement
- **Category:** Backend
- **Implementation Scope:** In `POST /api/v1/orders`, after validating restaurant exists, calculate Haversine distance between customer address (lat/lng) and restaurant (lat/lng). If distance > `restaurant.delivery_radius_km`, return 400 with error code `OUT_OF_SERVICE_AREA`, message, and `nearest_restaurants` array (3 closest within radius). Query uses Haversine formula in SQL or Python with existing geo utility.
- **Acceptance Criteria:**
  1. Order to address outside radius returns 400 `OUT_OF_SERVICE_AREA`.
  2. Error response includes 3 nearest restaurants that do deliver.
  3. Order to address inside radius proceeds normally.
  4. Distance calculation uses accurate Haversine formula.
- **Evidence Required:** `curl` with out-of-range address → 400 with nearest restaurants. In-range address → 201.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.05 (serviceability basic logic)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.014 — Open/Closed Enforcement
- **Category:** Backend
- **Implementation Scope:** In `POST /api/v1/orders`, verify `restaurant.is_open = true` and current time is within today's `opens_at` / `closes_at`. If closed, return 400 with error code `RESTAURANT_CLOSED` and message "Opens at {time}". Use timezone-aware comparison (store times as `TIME WITH TIME ZONE` or UTC). Frontend already blocks; this is defense-in-depth.
- **Acceptance Criteria:**
  1. Order to closed restaurant returns 400 `RESTAURANT_CLOSED`.
  2. Error message includes opening time.
  3. Order to open restaurant proceeds normally.
  4. Time comparison respects restaurant timezone.
- **Evidence Required:** `curl` to closed restaurant → 400. Open restaurant → 201.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.05 (open/closed basic logic)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.015 — ETA Calculation from DB
- **Category:** Backend
- **Implementation Scope:** `GET /api/v1/restaurants/{id}` and `GET /api/v1/orders/{id}` compute dynamic ETA. Query `SELECT COUNT(*) FROM orders WHERE restaurant_id = ? AND status IN ('confirmed', 'preparing')` for `queue_size`. Formula: `eta_minutes = avg_prep_minutes + (queue_size * 5) + (distance_km / 25 * 60)`. Cache result in Redis for 60s per restaurant. Frontend displays dynamic ETA on restaurant detail and order tracking.
- **Acceptance Criteria:**
  1. ETA increases by ~5 min per item in queue.
  2. ETA cached for 60s; repeated queries hit Redis.
  3. ETA shown on restaurant detail and order tracking pages.
  4. ETA is non-negative and capped at 120 min.
- **Evidence Required:** Screenshot of restaurant detail showing dynamic ETA. Redis `GET eta:{restaurant_id}` showing cached value.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.016 — OTP Guest Tracking (Mock SMS)
- **Category:** Backend + Frontend
- **Implementation Scope:** Backend: `POST /api/v1/guest/otp/send` accepts `{phone}`. Generate 6-digit code, store in Redis `guest:otp:{phone}` with TTL 10m, log to stdout: `[MOCK SMS] OTP {code} sent to {phone}`. `POST /api/v1/guest/otp/verify` accepts `{phone, code, order_id}`. Verify code, return order status and timeline. Frontend: `/track` page has form for `order_id` + `phone`. "Send OTP" button triggers mock SMS log. "Verify" button shows order status.
- **Acceptance Criteria:**
  1. Mock OTP logged to stdout within 1s of request.
  2. Correct OTP + order_id returns order status.
  3. Incorrect OTP returns 400.
  4. Expired OTP (after 10m) returns 400.
- **Evidence Required:** Screen recording: guest enters order_id + phone → requests OTP → mock log visible → enters OTP → sees tracking.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.05 (guest tracking basic flow)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.017 — Image URL Validation
- **Category:** Backend + Frontend
- **Implementation Scope:** Backend: validate `image_url` on restaurant and menu item create/update. `HEAD` request to URL with 3s timeout; must return 200 and use HTTPS scheme. Frontend: custom hook `useImageValidation` attempts to load image; on `onError`, replace `src` with `/images/placeholder-food.jpg`. Add placeholder image to `apps/web/public/images/placeholder-food.jpg`.
- **Acceptance Criteria:**
  1. Invalid/broken image URL falls back to placeholder in UI.
  2. Backend rejects non-HTTPS image URLs at creation.
  3. Backend rejects unreachable URLs with 400.
  4. Placeholder image displays correctly.
- **Evidence Required:** Screenshot showing broken URL → placeholder. `curl` with bad URL → 400.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.018 — Mock Payment Webhook Simulation
- **Category:** Backend
- **Implementation Scope:** Create `scripts/mock_webhooks.py` that runs as cron or one-shot. Every 60s (or on demand), generates fake Stripe/Razorpay webhook payload for `payment_intent.succeeded` or `order.paid`. Signs payload with test secret. POSTs to `POST /api/v1/payments/webhooks/{provider}`. Configurable via `MOCK_WEBHOOKS_ENABLED=true`. Logs sent events to stdout. Excluded from production by env check.
- **Acceptance Criteria:**
  1. Running script successfully delivers webhook to payment-svc.
  2. Payment-svc processes webhook and updates payment status.
  3. Signature validation passes with test secret.
  4. Script is disabled when `MOCK_WEBHOOKS_ENABLED=false`.
- **Evidence Required:** Script stdout showing sent webhook. Payment-svc logs showing processed event. DB showing updated payment status.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.019 — Event-Driven Status Updates
- **Category:** Backend
- **Implementation Scope:** Add Redis pub/sub or Redis Streams (if available) to order-svc. On every status change (`pending → confirmed`, `confirmed → preparing`, etc.), publish `order.status_changed` event with `{order_id, old_status, new_status, timestamp, request_id}`. Notification-svc subscribes to channel and dispatches SSE/push/email based on `new_status`. If notification-svc is down, events accumulate in Redis stream (maxlen 10000) and are consumed on restart. Replace direct HTTP calls from order-svc to notification-svc with this event bus.
- **Acceptance Criteria:**
  1. Status change publishes event to Redis within 100ms.
  2. Notification-svc receives event and dispatches notification.
  3. Notification-svc downtime does not block order status updates.
  4. Missed events are consumed on notification-svc restart.
- **Evidence Required:** `redis-cli MONITOR` showing publish/subscribe. Notification-svc log showing consumed event.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.020 — Review Moderation
- **Category:** Backend + Frontend
- **Implementation Scope:** Migration: add `is_reported` BOOLEAN default false, `report_reason` TEXT to `reviews`. Backend: `POST /api/v1/reviews/{id}/report` accepts `{reason}`, sets `is_reported = true`. `GET /api/v1/admin/reviews/reported` returns reported reviews with reporter info. Frontend: review card has "Report" button opening reason modal. Admin dashboard has "Reported Reviews" tab with dismiss/remove actions. Auto-hide review from customer view if `report_count >= 3`.
- **Acceptance Criteria:**
  1. User can report a review with reason.
  2. Reported review appears in admin "Reported Reviews" tab.
  3. Admin can dismiss or remove review.
  4. Review with 3+ reports auto-hidden from customers.
- **Evidence Required:** Screen recording: report review → admin sees it → admin removes → customer view updates.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06 (reviews exist)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.021 — Address Validation
- **Category:** Backend
- **Implementation Scope:** Create Pydantic `AddressSchema` with structured fields: `street`, `city`, `state`, `postal_code`, `country`, `lat`, `lng`, `label`. Validate `postal_code` per country regex (IN: 6 digits, US: ZIP+4). Validate `country` is `US` or `IN`. Migration: convert existing flat address strings to JSONB structured format. Update all endpoints that accept addresses to use new schema.
- **Acceptance Criteria:**
  1. Invalid postal code for country returns 400.
  2. Valid structured address accepted and stored as JSONB.
  3. Existing addresses migrated to new format.
  4. Frontend address forms validate inline.
- **Evidence Required:** `curl` with invalid postal code → 400. Valid address → 200. DB showing JSONB structure.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.07.022 — Load Testing Baseline
- **Category:** DevOps / Testing
- **Implementation Scope:** Create `tests/load/k6_script.js` or `locustfile.py` hitting: `GET /restaurants`, `GET /restaurants/{id}/menu`, `POST /orders`, `GET /orders/{id}`. Simulate 50 concurrent VUs for 5 minutes. Record p50, p95, p99 latency and error rate. Save baseline report to `tests/load/baseline_report.md`. Run against local docker-compose stack.
- **Acceptance Criteria:**
  1. Load script runs successfully against local stack.
  2. Baseline report documents p50, p95, p99, error rate.
  3. Core endpoints (list, menu, create, get) have measurable baselines.
  4. Report is reproducible (script + env documented).
- **Evidence Required:** Screenshot of k6/locust output. `baseline_report.md` with metrics.
- **Priority:** P2
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (k6/locust may need installation)

## 16. Acceptance Criteria

- [ ] TanStack Query integrated in all frontend apps with caching, retries, error boundaries, and loading states.
- [ ] Server-side tenacity retries on all inter-service HTTP calls (3× exponential backoff).
- [ ] Circuit breaker on payment-svc calls; returns 503 when open.
- [ ] Rate limiting configured per endpoint with development whitelist.
- [ ] JWT validation middleware on every protected endpoint across all 6 services.
- [ ] Role claim verification enforced; cross-role access returns 403.
- [ ] Token refresh mechanism rotates refresh tokens in Redis.
- [ ] bcrypt<5.0 pinned; password strength enforced.
- [ ] Zero f-string SQL queries; 100% parameterized queries.
- [ ] All 7 DB indexes created and verified with `EXPLAIN ANALYZE`.
- [ ] Every request carries `X-Request-ID`; all service logs include it.
- [ ] All API errors return consistent `{error, message, request_id, details}` format.
- [ ] Pydantic schemas reject unknown fields and validate enums strictly.
- [ ] Order and payment creation enforce `Idempotency-Key` with 24h Redis cache.
- [ ] Cancellation from `pending`/`confirmed`/`preparing` with correct partial refund.
- [ ] Server-side serviceability check blocks out-of-radius orders.
- [ ] Server-side open/closed check blocks orders to closed restaurants.
- [ ] Dynamic ETA calculated from `avg_prep_minutes + queue_size * 5 + delivery_time`.
- [ ] Guest OTP tracking with mock SMS works end-to-end.
- [ ] Broken image URLs fall back to placeholder.
- [ ] Mock payment webhook simulation runs locally.
- [ ] Event bus decouples order-svc from notification-svc via Redis pub/sub.
- [ ] Review report button surfaces reported reviews to admin.
- [ ] Address validation with country-specific regex and structured JSON.
- [ ] Load test baseline report created with p95 latency metrics.
- [ ] Core customer loop from PR.05 and three-sided marketplace from PR.06 remain stable.

## 17. Evidence Required

- Screen recording: customer browses restaurants → cache hit on return → order creation with idempotency key → cancellation with partial refund → wallet update.
- Screen recording: owner accepts order → event bus publishes → notification-svc dispatches → customer tracking updates.
- Screen recording: guest enters order_id + phone → mock OTP logged → verifies → sees tracking.
- Screen recording: admin views reported reviews → removes one → customer view hides it.
- `curl` outputs: retry logs, circuit breaker 503, rate limit 429, idempotency duplicate response, serviceability 400, open/closed 400.
- Log outputs: same `request_id` across user-svc, order-svc, payment-svc, notification-svc.
- `EXPLAIN ANALYZE` outputs before and after index creation.
- k6/locust screenshot and `baseline_report.md`.
- DB queries: `SELECT indexname FROM pg_indexes WHERE tablename = 'orders'` (confirm indexes).
- Redis CLI: `GET idempotency:{key}` showing cached response.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, Kong).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- k6 or Locust (for load testing; optional).
- sqlmap (for SQL injection audit; optional).

### Internal Dependencies
- **PR.06 must be complete:** owner/driver/admin dashboards, real-time notifications, driver assignment, batch pooling, role guards, live status timeline.
- `redis` must be running (used for idempotency, OTP, event bus, token blacklist).
- `kong` gateway must be configured to inject `X-Request-ID`.
- Existing Pydantic v2 schemas in all services (for strict validation updates).
- Existing structlog configuration (for correlation ID logging).
- Existing Alembic setup (for index migrations).

## 19. Risks / Blockers

- **TanStack Query migration scope:** Wrapping all frontend `fetch` calls may touch 30+ files. Mitigation: migrate one feature at a time (restaurants, orders, wallet, profile) and verify no regression after each.
- **Circuit breaker state persistence:** pybreaker uses in-memory state; restart resets counts. Mitigation: acceptable for PR.07 (beta). Document move to Redis-backed breaker for PR.08.
- **Rate limit whitelist in CI:** If CI environment is not whitelisted, tests may fail with 429. Mitigation: add `APP_ENV=test` bypass or whitelist `pytest` client.
- **JWT middleware consistency:** 6 services may have slight variations in JWT validation. Mitigation: extract shared middleware to a common Python package (or copy-paste with verification per service).
- **DB index creation on large datasets:** Adding indexes may lock tables briefly. Mitigation: use `CONCURRENTLY` in PostgreSQL if supported; for dev/demo, small datasets make this negligible.
- **Address migration from flat string to JSONB:** Existing data may not parse cleanly. Mitigation: write robust migration script with fallback for malformed addresses.
- **Event bus ordering:** Redis pub/sub does not guarantee ordering across multiple consumers. Mitigation: use Redis Streams (`XADD`/`XREAD`) if strict ordering needed; pub/sub is sufficient for PR.07.
- **Load test environment variance:** Local docker-compose performance differs from production. Mitigation: document that baseline is relative; rerun on staging for absolute numbers.

## 20. Exit Criteria

- All P0 work items (IP.PR.07.001 through IP.PR.07.006, IP.PR.07.009 through IP.PR.07.012) implemented and verified.
- All P1 work items (IP.PR.07.007, IP.PR.07.008, IP.PR.07.013 through IP.PR.07.021) implemented and verified.
- P2 work item (IP.PR.07.022) attempted; baseline report created if tooling available.
- Frontend uses TanStack Query for all data fetching with no raw `fetch` calls remaining.
- Server-side retries and circuit breaker are active on inter-service calls.
- All protected endpoints have consistent JWT validation and role verification.
- All API errors use the consistent envelope format.
- DB indexes are created and queries show index usage.
- Order idempotency prevents duplicate creation on double-submit.
- Cancellation with partial refund works for all valid statuses.
- Serviceability and open/closed checks are enforced server-side.
- Guest OTP tracking works end-to-end with mock SMS.
- Event bus decouples order-svc from notification-svc.
- Review moderation is functional in admin dashboard.
- Addresses are validated and stored as structured JSON.
- Core customer loop and three-sided marketplace remain stable (no regression from PR.05/PR.06).
- Evidence screenshots/recordings captured per Section 17.
- PR.07 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.06)

PR.07 directly depends on PR.06 achievements:
- **IP.PR.06.001** — Owner Dashboard: stable owner dashboard needed as foundation for event-driven notifications.
- **IP.PR.06.002** — Owner Order Actions: status updates trigger event bus and status timeline.
- **IP.PR.06.005** — Driver Dashboard: driver actions trigger event bus.
- **IP.PR.06.008** — Admin Dashboard: admin dashboard extended with reported reviews.
- **IP.PR.06.013** — Real-time Notifications: SSE/polling as fallback when event bus is not available.
- **IP.PR.06.014** — Driver Assignment: assignment logic used by ETA calculation.
- **IP.PR.06.017** — Role-Based Route Guards: JWT middleware consistency builds on existing guards.
- **IP.PR.06.018** — Order Status Timeline: event bus drives live timeline updates.
- **IP.PR.05.009** — Open/Closed Logic: server-side enforcement builds on existing logic.
- **IP.PR.05.014** — Order Cancellation: robust cancellation extends basic flow.
- **IP.PR.05.I005** — Order State Machine: cancellation validates against state machine.

## 22. Connected Next-Level Requirements (link to PR.08)

PR.08 (Early Production-Ready, score 8/10) builds on PR.07 and requires:
- Working TanStack Query caching as foundation for optimistic updates.
- Consistent error format as foundation for global error handling UI.
- Correlation ID logging as foundation for distributed tracing (Jaeger).
- Event bus as foundation for real FCM push and email/SMS dispatch.
- Idempotency keys as foundation for safe retry logic in production.
- DB indexes as foundation for scalable query performance.
- Review moderation as foundation for community features.

PR.08 will introduce:
- Real FCM push notifications to owner/driver mobile apps.
- Real-time driver map tracking with Mapbox/Leaflet on customer tracking page.
- Address autocomplete with Nominatim or Google Places.
- Onboarding flow after signup (3-step: location, cuisines, done).
- Social login frontend wiring (Google OAuth backend ready).
- Loyalty points full activation and redemption.
- Group ordering (novelty).
- Meal rescue / end-of-day deals (novelty).
- Observability improvements (Grafana dashboards, Jaeger tracing).
- WebSocket reconnection logic and exponential backoff.
- Image optimization pipeline (WebP, CDN).

PR.08 will be blocked if:
- TanStack Query migration is incomplete (frontend remains unstable).
- JWT middleware is inconsistent (security holes remain).
- API errors are still inconsistent (frontend error handling is fragile).
- No request correlation exists (debugging production issues is impossible).
- Cancellation/refund is not atomic (financial data corruption risk).
- Idempotency keys are not enforced (duplicate charges in production).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (7/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.06 complete) described | Planner | ✅ |
| 4 | Target state (PR.07 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.07 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.07 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage notes deferred differentiators | Planner | ✅ |
| 14 | Work items use exact required format with ID PR.PR.07.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover all required reliability areas | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention migration scope, breaker state, rate limit CI, JWT consistency, index locking, address migration, event ordering | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.06) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.08) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required reliability areas: TanStack Query caching (IP.PR.07.001), server-side retries + circuit breaker (IP.PR.07.002), rate limiter config (IP.PR.07.003), auth consistency + token refresh (IP.PR.07.004), password security + bcrypt pinning (IP.PR.07.005), SQL injection audit (IP.PR.07.006), DB indexes (IP.PR.07.007), correlation ID logging (IP.PR.07.008), consistent API error format (IP.PR.07.009), strict input validation (IP.PR.07.010), order idempotency keys (IP.PR.07.011), robust cancellation/refund (IP.PR.07.012), serviceability enforcement (IP.PR.07.013), open/closed enforcement (IP.PR.07.014), ETA calculation from DB (IP.PR.07.015), OTP guest tracking (IP.PR.07.016), image URL validation (IP.PR.07.017), mock payment webhook simulation (IP.PR.07.018), event-driven status updates (IP.PR.07.019), review moderation (IP.PR.07.020), address validation (IP.PR.07.021), and load testing baseline (IP.PR.07.022).
- Scope is tightly bounded to score 7/10 (reliability, resilience, observability, edge-case hardening). No new user-facing features except safety improvements.
- Out-of-scope explicitly excludes real payment webhooks, real push/email/SMS, CDN, full observability stack, CI/CD, group ordering, loyalty, smart lockers, AI/ML.
- Data model coverage addresses index additions, review moderation columns, and address JSONB migration. No new PostgreSQL tables required.
- Risks and blockers are grounded in known gaps from audits (TanStack migration scope, circuit breaker persistence, rate limit CI whitelist, JWT consistency, index locking, address migration, event ordering).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references and blocker conditions.
- Feasibility tags use the required color system: 🟢 LOCAL/DEMO-SAFE for all work items except load testing (🟡 OPTIONAL EXTERNAL since k6/locust may need installation).
- **One point deducted** because the exact Redis Streams vs pub/sub choice for the event bus is left to implementation discretion rather than mandated, and the load testing baseline tooling (k6 vs locust) is not pre-selected. These are minor implementation choices that do not affect plan completeness.

The document is ready for execution.
