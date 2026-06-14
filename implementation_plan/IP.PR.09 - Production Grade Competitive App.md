# IP.PR.09 — Production Grade Competitive App

## 1. Target Score Level: 9/10

## 2. Score Meaning: Real payment/provider integrations, robust admin operations, scalable flows, strong monitoring, recovery paths, and professional UX across major journeys.

At score 9/10, the platform is no longer a polished demo or beta. It is a production-grade application that can credibly handle real transactions, real drivers, real restaurants, and real customers at limited scale. Key external providers (Stripe, Razorpay, FCM, SendGrid, Twilio, S3, CDN) are integrated with sandbox or production credentials stored securely. The observability stack provides actionable insights. The batch delivery engine is fully wired into the order and delivery lifecycle. Advanced marketplace features (group ordering, multi-restaurant cart, dynamic pricing) create genuine competitive differentiation. Recovery paths exist for payment failures, webhook timeouts, and service degradation. The UX is professional across web, mobile, and admin surfaces.

## 3. Current → Target Transition

**From PR.08 (polished, accessible, performant, secure, PWA-ready):**
- Accessibility: axe-core zero critical violations, keyboard-only order flow, screen reader tested, focus trapping, ARIA labels, color contrast >= 4.5:1.
- Performance: Lighthouse Performance > 80, Accessibility > 90, Best Practices > 90, SEO > 90. Next.js `<Image>` with lazy loading. Code split bundles. `next/font` preloaded.
- Security: CSRF tokens, XSS sanitization, brute force login lockout, secure cookies, CSP headers, self-signed HTTPS.
- PWA: Valid manifest, service worker, offline indicator, install prompt. Offline cart syncs on reconnect.
- Animations: Framer Motion page transitions, add-to-cart fly, cart badge wobble, toast slide-in, skeleton shimmer.
- SEO: Dynamic `<title>`, `<meta>`, Open Graph tags, JSON-LD structured data on restaurant pages.
- Social login: Google OAuth wired end-to-end with provider/provider_id storage.
- Advanced search: Postgres trigram/tsvector with GIN index, combined restaurant+menu search, autocomplete.
- Admin charts: Recharts bar/line/pie charts for orders, revenue, cuisine popularity.
- i18n: English + Hindi full extraction, language switcher, browser detection.
- Review photos: Upload 1-3 photos per review, thumbnail display, lightbox.
- Address autocomplete: Nominatim/Places API with structured fields and lat/lng.
- Design system: Brand tokens, Lucide icons, card/badge anatomy, trust markers.

**However, PR.08 is still "production-content, beta-finishing":**
- Payment gateways use mock/simulated flows. No real Stripe/Razorpay API calls. No webhook signature verification in production. No real refund processing.
- Push notifications: FCM device tokens stored but never dispatched from order events.
- Email notifications: SendGrid templates exist but email channel not wired to event dispatcher.
- SMS notifications: Twilio mock mode only. Real OTP and order status SMS not dispatched.
- Driver tracking: WebSocket endpoint exists but no moving map with real GPS updates on the customer web tracking page. Mobile driver app posts location but no persistent route view.
- Route optimization: Batch engine has an algorithm but is not integrated into delivery-svc for real driver assignment.
- Images: Served from local filesystem or DB BLOB. No S3 + CDN pipeline. No WebP optimization.
- Observability: stdout JSON logs only. No Prometheus metrics, no Grafana dashboards, no Loki log aggregation, no Jaeger distributed tracing.
- CI/CD: GitHub Actions exist but missing batch-engine. `|| true` bypasses test failures. No Docker Swarm or ECS staging deployment.
- SSL: Self-signed only for local dev. No Let's Encrypt automation.
- Inter-service auth: Services trust each other implicitly. No `X-Internal-Token` validation.
- Rate limiting: Per-endpoint SlowAPI only. No distributed Redis-backed rate limiting across service instances.
- Admin analytics: Charts exist but no deep analytics (retention, cohorts, driver performance, hourly volume).
- Group ordering: Not implemented.
- Multi-restaurant cart: Cross-restaurant guard exists; cart rejects mixed-restaurant items. No split delivery fee.
- Dynamic pricing: Static delivery fees. No surge multiplier during peak.
- Customer support: No in-app chat.
- Feedback/NPS: No post-delivery rating prompt or NPS survey.
- Batch engine: Not deployed in CI/CD, docker-compose, or Terraform ECS. No driver assignment integration. Route recalculation TODO remains.

**Target at score 9:**
- Real payment gateway integration: Stripe and Razorpay real APIs with sandbox credentials. Secure credential storage. Dual currency support (INR via Razorpay, USD via Stripe).
- Payment webhook handlers: Secure endpoints verifying Stripe signatures and Razorpay HMAC. Update `payment_intents.status`. Handle idempotency via Redis `processed_webhook_events`.
- Refund processing: Full and partial refunds via provider API. Store refund reason and status. Wallet credit on successful refund.
- Push notifications: FCM production integration. Device token registration. Send push on order status changes. Support Android and iOS.
- Email notifications: SendGrid free tier wired to order events. Order confirmation, cancellation, refund, and promotional emails. HTML templates with BhojanGo branding.
- SMS notifications: Twilio (or MSG91 for India). OTP for password reset. Order status SMS.
- Real-time driver tracking: WebSocket server broadcasting driver location every 10s. Driver mobile web app posts geolocation. Customer tracking page shows map with moving pin (Mapbox/Leaflet).
- Route optimization: Basic nearest-neighbor or 2-opt algorithm for batch delivery routes, integrated into batch-engine and delivery-svc.
- CDN for images: CloudFront or Cloudflare. Images uploaded to S3. Served via CDN URL. Sharp/ImageMagick pipeline generating thumbnails (200x200, 400x400, 800x800).
- Observability stack: Prometheus metrics (requests, latency, errors). Grafana dashboards per service. Loki for log aggregation. Jaeger for distributed tracing (X-Request-ID propagation).
- CI/CD: GitHub Actions workflow — lint, test, build, deploy to staging. Docker Compose for local dev. Docker Swarm or ECS for staging.
- SSL / Let's Encrypt: Automatic certificate provisioning. Force HTTPS. HSTS headers.
- Inter-service authentication: Shared HMAC secret for internal API calls. `X-Internal-Token` header validation via middleware on every non-public endpoint.
- Rate limiting with Redis: Distributed rate limiting across service instances using Redis sliding window.
- Admin dashboard full analytics: Daily/weekly/monthly revenue charts. Top restaurants. Order volume by hour. Driver performance metrics. Customer retention rate.
- Group ordering: Shareable invite link. Friends add items from their devices. Host pays and splits bill.
- Multi-restaurant cart: Cart accepts items from multiple restaurants. Split delivery fees per restaurant. Separate checkout confirmation.
- Dynamic pricing: Surge multiplier during peak hours / rain. Transparent badge explaining fee increase.
- Customer support chat: In-app chat widget (Intercom or Crisp free tier, or custom WebSocket chat). Ticket creation from chat.
- Feedback / NPS: Post-delivery rating prompt (1-5 stars + text). Net Promoter Score survey 24h after delivery.
- Advanced batch engine: Order pool active, batch creation triggers on order.confirmed, batch assignment calls delivery-svc, route stops with ETA per stop.

## 4. Implementation Objective

Integrate real payment providers, enable real-time driver tracking, add observability, build CI/CD, and add advanced features like group ordering and multi-restaurant cart. Transform BhojanGo from a polished beta into a production-grade competitive app that can handle real transactions, real driver movements, and real operational analytics.

## 5. Scope

### In Scope

1. **Real payment gateway integration:**
   - Stripe and Razorpay real APIs with sandbox credentials.
   - Store provider credentials securely (env vars / AWS Secrets Manager, never in code).
   - Support both INR (Razorpay) and USD (Stripe).
   - Implement payment method selection: card, UPI (India), wallet, COD.

2. **Payment webhook handlers:**
   - Secure endpoints verifying Stripe signature (`stripe.webhooks.constructEvent`).
   - Razorpay HMAC verification (`crypto.createHmac`).
   - Update `payment_intents.status` to `succeeded`/`failed`.
   - Handle webhook idempotency via Redis `processed_webhook_events:{event_id}` TTL 24h.

3. **Refund processing:**
   - Full and partial refunds via provider API (`stripe.refunds.create`, Razorpay refunds).
   - Store refund reason and status in `refunds` table.
   - Credit wallet on successful refund. Publish SNS `refund.completed`.

4. **Push notifications:**
   - Firebase Cloud Messaging (FCM) production integration.
   - Device token registration (`POST /api/v1/notifications/devices`).
   - Send push on order status change (confirmed, preparing, picked up, delivered).
   - Support Android and iOS payloads with data + notification keys.

5. **Email notifications:**
   - SendGrid integration (free tier, 100 emails/day).
   - Order confirmation, cancellation, refund, and promotional emails.
   - HTML templates with BhojanGo branding (saffron header, logo, structured order table).

6. **SMS notifications:**
   - Twilio integration (or Indian provider like MSG91 for OTP cost optimization).
   - OTP for password reset and guest tracking.
   - Order status SMS (confirmed, picked up, delivered).

7. **Real-time driver tracking:**
   - WebSocket server (or Socket.io) broadcasting driver location every 10s.
   - Driver mobile web app posts geolocation (`navigator.geolocation.watchPosition`).
   - Customer tracking page shows map with moving pin (Mapbox GL JS or Leaflet).
   - Map tile CDN for fast loading.

8. **Route optimization:**
   - Basic nearest-neighbor or 2-opt algorithm for batch delivery routes.
   - Integrate route optimizer into `delivery-svc` for batch assignments.
   - ETA per stop calculated from route segment distances.

9. **CDN for images:**
   - CloudFront or Cloudflare CDN distribution.
   - Upload images to S3 via presigned POST.
   - Serve via CDN URL with cache headers.
   - Image optimization pipeline (Sharp or ImageMagick) generating thumbnails (200x200, 400x400, 800x800).

10. **Observability stack:**
    - Prometheus metrics via `prometheus-fastapi-instrumentator` or Node.js `prom-client`.
    - Grafana dashboards per service: request rate, p50/p95/p99 latency, error rate, goroutine/thread count.
    - Loki for log aggregation (structured JSON logs scraped from stdout).
    - Jaeger for distributed tracing with `X-Request-ID` propagation across all services.

11. **CI/CD:**
    - GitHub Actions workflow: lint (flake8, ESLint) → test (pytest, jest) → build Docker images → deploy to staging ECS/Swarm.
    - Docker Compose for local dev with all 7 services + Kong + Redis + PostgreSQL + OpenSearch.
    - Docker Swarm or ECS for staging with service discovery.

12. **SSL / Let's Encrypt:**
    - Automatic certificate provisioning via Certbot or ACM.
    - Force HTTPS redirect on ALB/nginx.
    - HSTS headers (`Strict-Transport-Security: max-age=31536000; includeSubDomains`).

13. **Inter-service authentication:**
    - Shared HMAC secret (32+ chars, env var) for internal API calls.
    - `X-Internal-Token` header with HMAC-SHA256 of request path + timestamp.
    - Validation middleware rejects requests without valid internal token (except public routes).

14. **Rate limiting with Redis:**
    - Distributed sliding-window rate limiting using Redis.
    - Per-IP and per-user limits. Different tiers for public/auth/internal endpoints.
    - 429 response with `Retry-After` header.

15. **Admin dashboard full analytics:**
    - Daily/weekly/monthly revenue charts (Recharts or Chart.js with date range picker).
    - Top restaurants by order volume and revenue.
    - Order volume by hour heatmap.
    - Driver performance: on-time rate, earnings, delivery count.
    - Customer retention rate (cohort analysis: users who ordered in week N and again in week N+1).

16. **Group ordering:**
    - Shareable invite link (`/group-order/{invite_code}`).
    - Friends add items from their own devices (WebSocket or polling sync).
    - Host pays and splits bill equally or by item.
    - Group cart expiration (30 min idle).

17. **Multi-restaurant cart:**
    - Cart accepts items from multiple restaurants.
    - Separate mini-carts per restaurant with individual subtotals.
    - Split delivery fees per restaurant.
    - Separate checkout confirmation per restaurant or unified checkout with restaurant sections.

18. **Dynamic pricing:**
    - Surge multiplier during peak hours (lunch 12-2pm, dinner 7-10pm) and weather events (rain API).
    - Transparent badge: "Peak hour — ₹15 extra for faster delivery" or "Rainy day — ₹10 rider safety fee."
    - Stored in `dynamic_pricing` table with `multiplier`, `reason`, `start_time`, `end_time`.

19. **Customer support chat:**
    - In-app chat widget (Intercom free tier or Crisp free tier, or custom WebSocket chat).
    - Ticket creation from chat with order context pre-filled.
    - Admin support view for open tickets.

20. **Feedback / NPS:**
    - Post-delivery rating prompt: 1-5 stars + text review.
    - Net Promoter Score survey sent 24h after delivery ("How likely are you to recommend BhojanGo?" 0-10).
    - Store NPS responses and calculate rolling average.

21. **Advanced batch engine:**
    - Order pool actively ingests `order.confirmed` events.
    - Batch creation runs every 30s with composite scoring.
    - Batch assignment calls `delivery-svc` driver assignment endpoint.
    - Route stops generated with ETA per stop.
    - Batch status tracking and customer-visible batch group on tracking page.

## 6. Out of Scope

- Smart lockers / IoT integration (PR.10 / novelty).
- Voice ordering NLP (PR.10).
- Blockchain / carbon neutral features (DO NOT IMPLEMENT NOW — deferred to PR.10 as marketing novelty).
- AI/ML predictive models for recommendations or demand forecasting (PR.10).
- White-label / franchise management (PR.10).
- Drone delivery (PR.10 / novelty).
- Real-time traffic data via Google Routes API (PR.10 / requires paid API).
- Multi-region deployment with cross-region replication (PR.10 / requires significant infra).
- Advanced fraud detection / ML chargeback prevention (PR.10).
- Subscription meal plans / Blue Apron-style recurring meals (PR.10 / novelty).
- Kitchen tablet POS integration (PR.10).

## 7. Required Capabilities

- **Payments:** Real Stripe and Razorpay sandbox/production API calls. Webhook signature verification. Idempotent webhook processing. Full and partial refunds with wallet credit.
- **Notifications:** FCM push production dispatch. SendGrid email dispatch from SQS events. Twilio SMS dispatch for OTP and order status.
- **Tracking:** WebSocket server broadcasting GPS every 10s. Moving map pin on customer tracking page. Driver geolocation capture.
- **Batching:** Order pool ingestion. Batch creation + scoring. Driver assignment integration. Route stops with ETA per stop.
- **Images:** S3 presigned upload. Sharp/ImageMagick thumbnail generation. CloudFront/Cloudflare CDN serving.
- **Observability:** Prometheus `/metrics` endpoint on every service. Grafana dashboard JSON. Loki log scraping. Jaeger span collection.
- **DevOps:** GitHub Actions CI/CD with Docker build + push. Docker Compose full stack. ECS or Swarm staging deployment.
- **Security:** Let's Encrypt SSL. HSTS. Inter-service HMAC auth. Distributed Redis rate limiting.
- **Advanced features:** Group order shareable link + sync. Multi-restaurant cart with split fees. Dynamic pricing with transparent badges. Support chat widget. NPS survey.
- **Admin analytics:** Revenue by period. Top restaurants. Hourly volume heatmap. Driver performance. Customer retention cohorts.

## 8. Key User Journeys

### Journey 9.1 — Customer Pays with Real Payment Gateway
1. Customer proceeds to checkout with items in cart.
2. Selects payment method: Card (Stripe) or UPI (Razorpay) or Wallet.
3. Backend calls Stripe `PaymentIntent.create` or Razorpay `Order.create` with real sandbox key.
4. Customer enters test card (Stripe test card `4242 4242 4242 4242`) or UPI ID.
5. Payment provider processes transaction. Webhook fires to BhojanGo.
6. Webhook handler verifies signature, updates `payment_intents.status` to `succeeded`.
7. Order status transitions to `confirmed`. Customer receives push notification and email receipt.
8. Wallet balance remains unchanged (unless wallet payment selected).

### Journey 9.2 — Driver Delivers Batch with Real-Time Tracking
1. Driver logs into mobile app and toggles online.
2. Delivery-svc assigns a batch of 2 orders (Restaurant A and B) based on batch-engine scoring.
3. Driver sees route with stops: Pickup A → Pickup B → Dropoff 1 → Dropoff 2.
4. Driver moves toward Pickup A. GPS posts lat/lng every 10s via WebSocket.
5. Customer 1 opens order tracking page. Map shows driver pin moving in real-time with ETA "2 min away."
6. Driver picks up from A, marks "picked up." Status push sent to both customers.
7. Driver proceeds to Pickup B, then drops off in order. Route optimized by nearest-neighbor.
8. Both customers receive "delivered" push + SMS. Batch complete.

### Journey 9.3 — Group Order with Friends
1. Customer starts group order from a restaurant. Generates shareable link: `bhojango.com/group/abc123`.
2. Customer shares link via WhatsApp. 3 friends open link on their phones.
3. Each friend adds items to the shared group cart (synced via WebSocket or polling every 3s).
4. Host sees live updates: "Rahul added Butter Naan x2." Group cart subtotal updates.
5. After 10 minutes, host locks the cart. Chooses split: equal (₹150 each) or by item.
6. Host pays via Stripe. Order placed. Each friend receives confirmation with their items.
7. Group order tracked as a single order with sub-order items per person.

### Journey 9.4 — Admin Monitors Operations with Full Observability
1. Admin opens Grafana dashboard. Sees real-time request rate, error rate, and p95 latency for all 6 services.
2. Admin switches to Loki. Queries `service="order-svc" {request_id="abc"}` to trace a single order across services.
3. Admin opens Jaeger. Searches trace for `request_id=abc`. Sees spans: web → Kong → order-svc → payment-svc → notification-svc.
4. Admin dashboard shows revenue line chart (last 7 days), hourly order heatmap, and driver on-time rate.
5. Admin notices error rate spike on payment-svc at 12:05 PM. Drills into Loki logs — reveals Stripe webhook timeout. Escalates to on-call.

### Journey 9.5 — Multi-Restaurant Cart Checkout
1. Customer browses restaurants. Adds Pizza from Restaurant A. Adds Biryani from Restaurant B.
2. Cart page shows two mini-carts: "Pizza Palace" and "Biryani House."
3. Each mini-cart shows its own subtotal, delivery fee, and restaurant-specific taxes.
4. Customer proceeds to unified checkout. Page shows order summary split by restaurant.
5. Customer places order. Backend creates TWO separate orders (one per restaurant) linked by `multi_order_id`.
6. Customer sees both orders in order history. Tracking pages are separate but linked.
7. Two delivery fees charged (or batched if both restaurants are close and customer opted for eco batch).

## 9. Technical Coverage

### Backend

- **user-svc:**
  - Wire Twilio SMS dispatch for password reset OTP (replace mock mode).
  - Wire SendGrid email dispatch for password reset and promotional emails.
  - Add `POST /api/v1/notifications/devices` for FCM token registration.
  - Add distributed Redis rate limiting middleware.
  - Add inter-service HMAC auth middleware (`X-Internal-Token` validation).

- **restaurant-svc:**
  - Add S3 presigned upload endpoint for menu/restaurant images.
  - Integrate Sharp/ImageMagick thumbnail generation pipeline.
  - Return CDN URLs in restaurant/menu responses.
  - Add inter-service HMAC auth.
  - Add Prometheus metrics endpoint.

- **order-svc:**
  - Add dynamic pricing calculation at checkout: query `dynamic_pricing` table for active multipliers.
  - Add group order endpoints: `POST /api/v1/group-orders`, `GET /api/v1/group-orders/{code}`, `POST /api/v1/group-orders/{code}/items`, `POST /api/v1/group-orders/{code}/lock`.
  - Add multi-restaurant cart support: `multi_order_id` linkage, split delivery fees.
  - Add NPS survey trigger endpoint: `POST /api/v1/orders/{id}/feedback`.
  - Publish `order.confirmed` event for batch-engine consumption.
  - Add inter-service HMAC auth.

- **delivery-svc:**
  - Integrate batch-engine SNS events: assign driver to batch.
  - Add route optimization endpoint: `POST /api/v1/deliveries/{batch_id}/route` using nearest-neighbor or 2-opt.
  - Add WebSocket server for broadcasting driver location every 10s.
  - Store driver location history with 10s granularity.
  - Add inter-service HMAC auth.

- **payment-svc:**
  - Replace mock payment flows with real Stripe/Razorpay API calls using sandbox keys.
  - Implement `POST /api/v1/payments/webhooks/stripe` with signature verification (`stripe.webhooks.constructEvent`).
  - Implement `POST /api/v1/payments/webhooks/razorpay` with HMAC verification (`crypto.createHmac`).
  - Add webhook idempotency: Redis `processed_webhook_events:{event_id}` TTL 24h.
  - Add refund endpoint: `POST /api/v1/payments/refund` calling provider refund API.
  - Add `refunds` table migration.
  - Add inter-service HMAC auth.

- **notification-svc:**
  - Wire FCM production dispatch: read order events from SQS, send push via `firebase-admin`.
  - Wire SendGrid email dispatch: read events from SQS, send via `sendgrid` library.
  - Wire Twilio SMS dispatch: read events from SQS, send via `twilio` library.
  - Add retry with exponential backoff for failed dispatches (max 3 retries, then DLQ).
  - Add inter-service HMAC auth.

- **batch-engine:**
  - Consume SQS `order.confirmed` events to populate order pool.
  - Call `delivery-svc` batch assignment endpoint after batch creation.
  - Implement route stop generation with ETA per stop.
  - Add Prometheus metrics endpoint.
  - Add to Docker Compose, CI/CD, and Terraform ECS.

- **API Gateway (Kong):**
  - Add rate limiting plugin with Redis backend for distributed limits.
  - Add bot-detection plugin.
  - Force HTTPS redirect.

### Frontend — apps/web

- Add Mapbox GL JS or Leaflet to order tracking page with real moving pin.
- Add group order UI: create group, share link modal, live cart sync indicator, split bill selector.
- Add multi-restaurant cart UI: mini-carts per restaurant, split fees, unified checkout.
- Add dynamic pricing badge on checkout: "Peak hour +₹15" with tooltip explaining surge.
- Add Intercom/Crisp chat widget or custom WebSocket chat component.
- Add post-delivery rating modal (1-5 stars + text) and NPS survey toast 24h later.
- Add onboarding flow after signup: 3-step wizard (set location → pick cuisines → done).

### Frontend — apps/mobile

- Integrate Stripe/Razorpay mobile SDK for in-app payment (Expo `stripe-react-native` or Razorpay SDK).
- Add real-time driver tracking map with `react-native-maps` and moving marker.
- Add push notification tap handling: navigate to order tracking on tap.
- Add cart persistence with Zustand + `expo-secure-store` or `AsyncStorage`.

### Frontend — apps/admin

- Add Grafana/Loki/Jaeger embed links or iframe dashboards.
- Add full analytics pages: revenue by period, hourly heatmap, driver performance, customer retention.
- Add support ticket management view.
- Add batch monitoring: active pools, batches, routes.

### Data

- Migration: `refunds` table — `id`, `payment_intent_id`, `order_id`, `amount`, `currency`, `reason`, `status`, `provider_refund_id`, `created_at`.
- Migration: `group_orders` table — `id`, `invite_code`, `host_user_id`, `restaurant_id`, `status`, `expires_at`, `split_type`, `created_at`.
- Migration: `group_order_items` table — `id`, `group_order_id`, `user_id`, `menu_item_id`, `quantity`, `customizations`, `price`, `created_at`.
- Migration: `dynamic_pricing` table — `id`, `region`, `multiplier`, `reason`, `start_time`, `end_time`, `is_active`.
- Migration: `feedback` table — `id`, `order_id`, `user_id`, `rating`, `review_text`, `nps_score`, `created_at`.
- Migration: `support_tickets` table — `id`, `user_id`, `order_id`, `subject`, `status`, `created_at`, `resolved_at`.
- Migration: `processed_webhook_events` Redis set (no SQL table needed).
- Redis: `processed_webhook_events:{event_id}` TTL 86400s.
- Redis: distributed rate limit keys `rate_limit:{endpoint}:{identifier}` TTL sliding window.
- OpenSearch: index `menu_items` for combined restaurant+menu search.

## 10. UI / UX Coverage

- **Loading states:** Skeleton shimmer on map tiles, batch route calculation.
- **Error states:** Payment failure modal with retry button. WebSocket disconnect indicator. Map load failure fallback.
- **Empty states:** No active batches for driver. No group orders. No support tickets.
- **Success states:** Push notification toast. Email sent confirmation. Group order locked confirmation.
- **Design system:** Brand tokens applied consistently. Surge pricing badge uses saffron with warning icon.
- **Responsive:** Map tracking works on mobile web and native. Group order UI works on mobile.
- **Dark mode:** Not activated in PR.09 (deferred to PR.10).
- **Accessibility:** Map has ARIA labels for pin status. Chat widget is keyboard accessible. NPS modal traps focus.
- **Animations:** Map pin smooth interpolation (CSS `transition`). Group order item addition slides in.

## 11. Data / Model Coverage

- `refunds` table: `id` UUID PK, `payment_intent_id` UUID FK, `order_id` UUID FK, `amount` NUMERIC(12,2), `currency` VARCHAR(3), `reason` VARCHAR(200), `status` VARCHAR(20), `provider_refund_id` VARCHAR(100), `created_at` TIMESTAMP.
- `group_orders` table: `id` UUID PK, `invite_code` VARCHAR(20) UNIQUE, `host_user_id` UUID FK, `restaurant_id` UUID FK, `status` VARCHAR(20), `expires_at` TIMESTAMP, `split_type` VARCHAR(20), `created_at` TIMESTAMP.
- `group_order_items` table: `id` UUID PK, `group_order_id` UUID FK, `user_id` UUID FK, `menu_item_id` UUID FK, `quantity` INT, `customizations` JSONB, `price` NUMERIC(12,2), `created_at` TIMESTAMP.
- `dynamic_pricing` table: `id` UUID PK, `region` VARCHAR(50), `multiplier` NUMERIC(3,2), `reason` VARCHAR(100), `start_time` TIMESTAMP, `end_time` TIMESTAMP, `is_active` BOOLEAN.
- `feedback` table: `id` UUID PK, `order_id` UUID FK, `user_id` UUID FK, `rating` INT CHECK (1-5), `review_text` TEXT, `nps_score` INT CHECK (0-10), `created_at` TIMESTAMP.
- `support_tickets` table: `id` UUID PK, `user_id` UUID FK, `order_id` UUID FK, `payment_intent_id` UUID FK, `subject` VARCHAR(200), `status` VARCHAR(20), `created_at` TIMESTAMP, `resolved_at` TIMESTAMP.
- `users` table: add `fcm_token` TEXT (device token for push).
- `orders` table: add `multi_order_id` UUID (nullable, links split orders from multi-restaurant cart).
- `orders` table: add `batch_id` UUID (nullable, links to batch-engine batch).
- Redis keys:
  - `processed_webhook_events:{event_id}` — set member, TTL 86400s.
  - `rate_limit:{endpoint}:{ip_or_user_id}` — sliding window counter, TTL window size.
  - `group_cart:{invite_code}` — serialized group cart state, TTL 1800s (30 min).

## 12. Role / Permission Coverage

- `customer`: Full access to real payments, group ordering, multi-restaurant cart, dynamic pricing, map tracking, support chat, feedback/NPS. Subject to distributed rate limits.
- `restaurant_owner`: Access to S3 image uploads, thumbnail generation, restaurant-specific analytics (orders by hour). Cannot view other restaurants' data.
- `delivery_partner`: Access to batch assignment, route optimization, GPS tracking WebSocket. Can view assigned batch stops and ETAs. Cannot access customer payment data.
- `admin` / `super_admin`: Full access to Grafana, Loki, Jaeger, admin analytics, support tickets, batch monitoring, refund processing, dynamic pricing configuration. Exempt from standard rate limits but logged.
- `guest` (unauthenticated): Can browse restaurants, view group order link (read-only), use support chat. Cannot place real orders, create group orders, or submit feedback.
- **Cross-role enforcement:** Inter-service HMAC auth ensures internal APIs cannot be called by external clients. JWT middleware on public routes unchanged. New endpoints (group order, feedback) protected by existing role checks.

## 13. Performance / Reliability / Security Coverage

### Performance
- Prometheus metrics expose request rate, latency histograms, and error rates per endpoint for capacity planning.
- Redis distributed rate limiting prevents any single IP/user from overwhelming services.
- CDN serves images from edge locations, reducing latency to <100ms globally.
- Sharp/ImageMagick thumbnails reduce image payload by 60-80% vs original.
- WebSocket GPS updates every 10s balance real-timeliness with battery/bandwidth.
- Batch-engine scoring runs every 30s (not per-request) to control CPU usage.

### Reliability
- Payment webhook idempotency prevents duplicate order confirmations on retry.
- Notification-svc retry with exponential backoff (max 3) and DLQ ensures no event is silently lost.
- WebSocket server has heartbeat/ping-pong to detect stale connections.
- Inter-service HMAC auth prevents cascade failures from unauthorized internal calls.
- Let's Encrypt auto-renewal ensures SSL certs never expire.
- Docker Compose full stack enables reproducible local dev environments.

### Security
- Payment provider credentials stored in env vars / AWS Secrets Manager, never committed.
- Stripe and Razorpay webhook signatures verified cryptographically before processing.
- `processed_webhook_events` Redis set prevents replay attacks.
- Inter-service HMAC with shared secret + timestamp prevents internal API spoofing.
- Distributed Redis rate limiting stops DDoS and brute force at the edge.
- HSTS headers prevent SSL stripping attacks.
- Force HTTPS redirect on ALB/nginx blocks unencrypted traffic.
- Refund endpoint requires admin or order owner role. Partial refunds capped at payment amount.

## 14. Novelty / Differentiation Coverage

At score 9, novelty moves from "demo features" to "integrated competitive advantages":

- **Cross-restaurant batch delivery** — The core differentiator. Fully integrated: order pool → batch creation → driver assignment → route optimization → ETA per stop. Competitors (Uber Eats, DoorDash, Swiggy, Zomato) only batch same-restaurant orders. BhojanGo's multi-restaurant batching is defensible if operational.
- **Eco-delivery customer opt-in** — Transparent batch savings passed to customer as lower delivery fee. "You saved ₹20 by choosing eco delivery." No competitor makes batching visible to the customer.
- **Group ordering with real-time sync** — Shareable link, friends add from own devices, host splits bill. Integrated into the order flow, not a separate hack.
- **Multi-restaurant cart** — One checkout for two restaurants with split fees. Competitors force separate orders. BhojanGo links them under `multi_order_id`.
- **Transparent dynamic pricing** — Customers see WHY fees increased ("Rainy day — ₹10 rider safety fee"), not just a higher number. Builds trust vs. opaque surge.
- **Kitchen Radar prep visibility** — (Deferred to PR.10 but foundation laid in PR.09 via batch ETA per stop).
- **Driver shift auction** — (Deferred to PR.10 but batch assignment + earnings reporting in PR.09 creates foundation).
- **NPS + feedback loop** — Rolling NPS score tracked per restaurant and platform. Data feeds into PR.10 ML recommendations.
- **Real observability** — Not a customer feature, but enables the team to iterate faster than competitors guessing at issues.

Novelty deferred to PR.10: AI meal suggestions, voice ordering NLP, smart lockers, meal rescue, subscription boxes, carbon offset gamification, kitchen tablet POS.

## 15. Implementation Work Items

### IP.PR.09.001 — Real Stripe Payment Integration
- **Category:** Backend
- **Implementation Scope:** Replace mock Stripe flow with real `stripe` Python SDK calls. `POST /api/v1/payments/stripe/initiate` calls `stripe.PaymentIntent.create(amount, currency='usd', automatic_payment_methods={'enabled': True})`. Return `client_secret` to frontend. Frontend uses Stripe Elements or React Native SDK to confirm payment. Store `stripe_payment_intent_id` in `payment_intents` table. Support saved payment methods (`setup_future_usage='off_session'`). Use Stripe test mode keys from `STRIPE_SECRET_KEY` env var. Never log key.
- **Acceptance Criteria:**
  1. Test card `4242 4242 4242 4242` successfully creates a PaymentIntent and returns `client_secret`.
  2. PaymentIntent status stored as `requires_confirmation` then `succeeded` after webhook.
  3. Stripe dashboard shows successful test transaction.
  4. Invalid card `4000 0000 0000 9995` returns `card_declined` error handled gracefully.
- **Evidence Required:** Stripe dashboard screenshot of test payment. `curl` showing PaymentIntent creation. Frontend payment confirmation success toast.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.011 (wallet and payment schema)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Stripe sandbox API)

### IP.PR.09.002 — Real Razorpay Payment Integration
- **Category:** Backend
- **Implementation Scope:** Replace mock Razorpay flow with real `razorpay` Python SDK. `POST /api/v1/payments/razorpay/initiate` calls `razorpay_client.order.create({'amount': amount_paise, 'currency': 'INR', 'payment_capture': 1})`. Return `order_id` to frontend. Frontend uses Razorpay Checkout SDK. Store `razorpay_order_id` in `payment_intents`. Support UPI via Razorpay. Use `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` env vars.
- **Acceptance Criteria:**
  1. Razorpay test order created successfully with INR amount in paise.
  2. UPI test payment (`success@razorpay`) completes and webhook fires.
  3. Razorpay dashboard shows test order.
  4. Failed UPI (`failure@razorpay`) returns error handled gracefully.
- **Evidence Required:** Razorpay dashboard screenshot. `curl` showing order creation. Frontend UPI checkout success.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.011
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Razorpay sandbox API)

### IP.PR.09.003 — Stripe Webhook Handler with Signature Verification
- **Category:** Backend
- **Implementation Scope:** Implement `POST /api/v1/payments/webhooks/stripe`. Read `Stripe-Signature` header. Verify with `stripe.webhooks.constructEvent(payload, signature, STRIPE_WEBHOOK_SECRET)`. Handle events: `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`. On `succeeded`: update `payment_intents.status = 'succeeded'`, publish SNS `payment.succeeded`. On `failed`: update status = `failed`, publish SNS `payment.failed`. On `refunded`: update `refunds` table, publish SNS `refund.completed`. Store processed event IDs in Redis `processed_webhook_events:{event_id}` TTL 24h to prevent replays.
- **Acceptance Criteria:**
  1. Webhook without valid signature returns 400.
  2. `payment_intent.succeeded` updates DB and publishes SNS.
  3. Duplicate event ID (replay) is idempotently ignored via Redis check.
  4. Webhook returns 200 within 2s to avoid Stripe retry storms.
- **Evidence Required:** `curl` with fake signature → 400. Stripe CLI trigger `payment_intent.succeeded` → DB updated. Redis `SMEMBERS` showing event ID stored.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09.001
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Stripe webhook API)

### IP.PR.09.004 — Razorpay Webhook Handler with HMAC Verification
- **Category:** Backend
- **Implementation Scope:** Implement `POST /api/v1/payments/webhooks/razorpay`. Read `X-Razorpay-Signature` header. Verify HMAC-SHA256 of payload with `RAZORPAY_WEBHOOK_SECRET` using `hmac.compare_digest`. Handle events: `order.paid`, `payment.failed`, `refund.processed`. Update `payment_intents` and publish SNS analogously to Stripe. Use same Redis idempotency key pattern.
- **Acceptance Criteria:**
  1. Invalid HMAC signature returns 400.
  2. `order.paid` event updates payment status to `succeeded`.
  3. Duplicate event ID ignored via Redis.
  4. Webhook responds 200 within 2s.
- **Evidence Required:** `curl` with fake signature → 400. Razorpay test webhook → DB updated.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09.002
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Razorpay webhook API)

### IP.PR.09.005 — Refund Processing with Provider API
- **Category:** Backend
- **Implementation Scope:** Add `POST /api/v1/payments/refund`. Accept `order_id`, `amount` (optional, defaults to full), `reason`. Find payment intent for order. Call provider refund API: `stripe.Refund.create(payment_intent=pi_id, amount=amount_cents)` or Razorpay equivalent. Store result in `refunds` table with `status = pending`. On webhook confirmation, update to `succeeded` and credit wallet if applicable. Return refund ID. Admin can initiate refund from admin dashboard.
- **Acceptance Criteria:**
  1. Full refund creates Stripe/Razorpay refund and updates `refunds` table.
  2. Partial refund creates refund for specified amount <= original.
  3. Refund reason stored and visible in admin dashboard.
  4. Wallet credited on successful refund completion.
- **Evidence Required:** Stripe/Razorpay dashboard showing refund. DB query showing `refunds` row. Wallet balance increased.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09.003, IP.PR.09.004
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Stripe/Razorpay refund API)

### IP.PR.09.006 — FCM Push Notification Production Dispatch
- **Category:** Backend
- **Implementation Scope:** Wire notification-svc SQS consumer to dispatch FCM pushes via `firebase-admin`. Load `FIREBASE_SERVICE_ACCOUNT_JSON` env var (or path to service account file). On `order.status_updated` event, query `user_devices` for FCM tokens. Send multicast if multiple devices. Payload: `notification: {title, body}` + `data: {order_id, status, screen: 'tracking'}`. Handle token unregistration on `messaging/registration-token-not-registered` error. Add retry 3x with exponential backoff. Failed pushes to DLQ after max retries.
- **Acceptance Criteria:**
  1. Order status change triggers push notification to customer's registered device.
  2. Push payload includes order_id and target screen for tap navigation.
  3. Invalid/expired tokens are removed from DB.
  4. Failed push retried 3x then moved to DLQ.
- **Evidence Required:** Screenshot of push on Android/iOS device. Firebase Console messaging report showing sent/delivered. DLQ message count visible in SQS console.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.015 (device token storage)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (FCM production API)

### IP.PR.09.007 — SendGrid Email Notification Dispatch
- **Category:** Backend
- **Implementation Scope:** Wire notification-svc SQS consumer to dispatch emails via `sendgrid` Python library. Use `SENDGRID_API_KEY` env var. On events: `order.placed` → order confirmation email with HTML template. `order.cancelled` → cancellation email. `payment.succeeded` → receipt email. `refund.completed` → refund confirmation. Use existing i18n templates (en, hi). Attach BhojanGo logo via CID or CDN URL. Track email opens/clicks via SendGrid tracking (optional). Send from `noreply@bhojango.com`.
- **Acceptance Criteria:**
  1. Order placement triggers order confirmation email within 30s.
  2. Email contains itemized order summary, total, and tracking link.
  3. Hindi locale sends Hindi email template.
  4. Invalid API key fails gracefully with logged error and DLQ.
- **Evidence Required:** Screenshot of received email in Gmail/Outlook inbox. SendGrid activity log showing delivered. DLQ check for failures.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.014 (email templates)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (SendGrid free tier API)

### IP.PR.09.008 — Twilio SMS Notification Dispatch
- **Category:** Backend
- **Implementation Scope:** Wire notification-svc SQS consumer to dispatch SMS via `twilio` Python library. Use `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` env vars. Events: `user.otp_requested` → OTP SMS. `order.status_updated` (confirmed, picked_up, delivered) → status SMS. Keep messages under 160 chars for single-segment delivery. For India, optionally use MSG91 with `MSG91_AUTHKEY` for lower cost. Add retry 3x. Failed SMS to DLQ.
- **Acceptance Criteria:**
  1. Password reset OTP arrives via SMS within 10s in sandbox.
  2. Order status SMS sent at confirmed, picked_up, delivered.
  3. SMS contains order number and status with short URL to tracking page.
  4. Failed SMS retried and eventually DLQ'd.
- **Evidence Required:** Screenshot of received SMS. Twilio message log showing delivered. DLQ check.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.013 (SMS templates)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Twilio/MSG91 API)

### IP.PR.09.009 — Real-Time Driver Tracking WebSocket Server
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Upgrade delivery-svc WebSocket endpoint (`/ws/track/{order_id}`) to broadcast driver location to connected clients every 10s. Driver posts location via `POST /api/v1/deliveries/location` (or WebSocket message) every 10s: `{lat, lng, order_id, timestamp}`. Store in Redis with 60s TTL (`driver_location:{driver_id}`). On broadcast, read Redis and emit `location_update` JSON to all subscribers for that order. **Customer web:** Order tracking page connects to WebSocket, receives updates, interpolates pin movement. Use Mapbox GL JS or Leaflet. Show route polyline from restaurant to customer. **Driver mobile:** Use `expo-location` to post GPS every 10s via background task (or foreground while app active).
- **Acceptance Criteria:**
  1. WebSocket connection established on tracking page load.
  2. Driver location updates every 10s and map pin moves smoothly.
  3. Route polyline displayed between restaurant and customer with current driver position.
  4. Connection auto-reconnects with exponential backoff on disconnect.
- **Evidence Required:** Screen recording of customer tracking page showing moving pin. WebSocket frames in DevTools showing lat/lng updates. Driver mobile screen recording posting location.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.07.007 (WebSocket tracking foundation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE (Mapbox free tier for dev)

### IP.PR.09.010 — Batch Engine Driver Assignment Integration
- **Category:** Backend
- **Implementation Scope:** Modify batch-engine to call `delivery-svc` `POST /api/v1/deliveries/batch/{batch_id}/assign` after batch creation. Pass batch details: `batch_id`, `order_ids`, `pickup_locations`, `dropoff_locations`, `estimated_items_count`. Delivery-svc runs Haversine query to find nearest available driver within 5km of first pickup. Assign driver, publish SNS `batch.assigned`. If no driver available within 5km, expand radius to 10km, then 15km. If still none, batch remains `pending_assignment` and retries every 60s. Add driver capacity check: total item count <= driver bag capacity.
- **Acceptance Criteria:**
  1. Batch creation triggers driver assignment within 5s.
  2. Assigned driver is the nearest available within capacity.
  3. Driver receives batch notification via push.
  4. Failed assignment retries with expanded radius.
- **Evidence Required:** Log trace showing batch → assign call → driver ID. DB query showing `batches.driver_id` populated.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.07.012 (batch engine foundation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.011 — Route Optimization for Batch Deliveries
- **Category:** Backend
- **Implementation Scope:** Implement nearest-neighbor route optimizer in `delivery-svc`. Given batch stops (pickups + dropoffs), generate route order minimizing total Haversine distance. Constraint: all pickups must precede their respective dropoffs. For 2-3 order batches, evaluate all valid permutations (2-3 orders → 6-12 valid sequences). For 4+ orders, use nearest-neighbor heuristic with pickup-before-delivery constraint. Return `route_stops` array: `[{type: 'pickup', order_id, lat, lng, eta}, ...]`. Calculate ETA per stop: cumulative distance / 25 km/h * 60 + dwell_time (2 min per stop).
- **Acceptance Criteria:**
  1. Route for 2-order batch has pickups before dropoffs.
  2. Total route distance is within 10% of optimal for small batches.
  3. ETA per stop is calculated and returned.
  4. Route recalculated if an order is cancelled mid-batch.
- **Evidence Required:** Unit test showing route order. API response with `route_stops` and ETAs.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09.010
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.012 — S3 + CDN Image Pipeline
- **Category:** Backend + DevOps
- **Implementation Scope:** Add S3 bucket `bhojango-images-{env}` with lifecycle policy (transition to IA after 90 days). Create presigned POST endpoint `POST /api/v1/uploads/presign` returning bucket, key, and POST policy. Frontend uploads directly to S3. On upload complete, trigger Lambda (or backend callback) to generate thumbnails with Sharp: 200x200, 400x400, 800x800. Store thumbnails as `{key}_200x200`, `{key}_400x400`. Configure CloudFront distribution with origin as S3 bucket. Cache behavior: `Cache-Control: max-age=31536000` for images. Return CloudFront URL in API responses. Fallback to local file system if `USE_S3=false` (dev mode).
- **Acceptance Criteria:**
  1. Image uploads directly to S3 via presigned POST.
  2. Thumbnails generated automatically at 3 sizes.
  3. Images served via CloudFront URL with cache headers.
  4. Fallback to local filesystem works when S3 disabled.
- **Evidence Required:** S3 bucket screenshot. CloudFront distribution config. `curl` showing image served with `CF-Cache-Status: HIT`. Network tab showing <100ms image load.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.08.002 (Next.js Image optimization)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (AWS S3 + CloudFront)

### IP.PR.09.013 — Prometheus + Grafana Observability Stack
- **Category:** DevOps
- **Implementation Scope:** Add `prometheus-fastapi-instrumentator` to all Python services exposing `/metrics` endpoint. Add `prom-client` to batch-engine (Node.js). Metrics: `http_requests_total` (counter, labeled by method, endpoint, status), `http_request_duration_seconds` (histogram), `app_errors_total` (counter by error_type). Deploy Prometheus server (Docker container) scraping all `/metrics` every 15s. Deploy Grafana with dashboards per service. Dashboards: "Request Rate & Latency", "Error Rate", "Saturation (DB connections, Redis pool)". Configure alert rules: error_rate > 5% for 5min → alert. Store dashboard JSON in `infra/grafana/dashboards/`.
- **Acceptance Criteria:**
  1. `/metrics` endpoint returns Prometheus exposition format on every service.
  2. Grafana dashboard shows real-time request rate and latency for each service.
  3. Alert fires when error rate exceeds threshold.
  4. Dashboard JSON is version-controlled.
- **Evidence Required:** Prometheus targets page showing all services UP. Grafana dashboard screenshot. Simulated error spike triggering alert.
- **Priority:** P1
- **Effort:** L
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (Prometheus + Grafana)

### IP.PR.09.014 — Loki Log Aggregation
- **Category:** DevOps
- **Implementation Scope:** Deploy Loki (Grafana's log aggregation system) as Docker container. Configure Promtail sidecar or Docker logging driver to scrape stdout logs from all services. Services already output structured JSON logs via structlog — Loki can index these. Add labels: `service`, `env`, `level`. Grafana datasource configured for Loki. Query example: `{service="order-svc"} |= "error" | json`.
- **Acceptance Criteria:**
  1. Loki ingests logs from all services.
  2. Grafana can query logs by service, level, and free text.
  3. Log lines are parsed JSON with searchable fields.
  4. Retention policy set to 7 days for dev, 30 days for staging.
- **Evidence Required:** Grafana Explore tab showing Loki query results. LogQL query execution.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.09.013
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (Loki)

### IP.PR.09.015 — Jaeger Distributed Tracing
- **Category:** DevOps
- **Implementation Scope:** Add OpenTelemetry instrumentation to all services. Use `opentelemetry-instrumentation-fastapi` for Python and `@opentelemetry/auto-instrumentations-node` for batch-engine. Propagate `X-Request-ID` as trace ID across all HTTP calls and SNS/SQS messages. Deploy Jaeger all-in-one container. Expose traces on UI at `:16686`. Each trace shows spans: frontend → Kong → user-svc → order-svc → payment-svc → notification-svc with timing per span.
- **Acceptance Criteria:**
  1. Every request generates a trace with multiple spans across services.
  2. `X-Request-ID` is propagated and visible as trace ID in Jaeger UI.
  3. Slow spans (>500ms) are visually flagged in Jaeger.
  4. Trace includes DB query timing via SQLAlchemy instrumentation.
- **Evidence Required:** Jaeger UI screenshot showing a complete order placement trace. Span durations visible.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.07.008 (X-Request-ID logging)
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (Jaeger + OpenTelemetry)

### IP.PR.09.016 — GitHub Actions CI/CD Pipeline
- **Category:** DevOps
- **Implementation Scope:** Extend existing GitHub Actions workflows. `ci.yml`: lint (flake8, black, ESLint, prettier) → unit tests (pytest, jest) → build Docker images for all 7 services + web + admin + mobile. `deploy-staging.yml`: on merge to `main`, push images to ECR (or Docker Hub), deploy to staging ECS/Swarm. Remove `|| true` bypass from test steps. Add batch-engine to CI matrix. Add `docker-compose.yml` for full local dev stack (all services + Kong + Redis + PostgreSQL + OpenSearch + Prometheus + Grafana + Jaeger). Add `.env.example` with all required env vars.
- **Acceptance Criteria:**
  1. CI fails on lint or test failure (no bypass).
  2. All 7 backend services + 3 frontends built in CI.
  3. Staging deployment triggered automatically on merge.
  4. `docker-compose up` starts full stack on local machine within 5 minutes.
- **Evidence Required:** GitHub Actions run showing green checkmarks. Staging ECS service showing running tasks. `docker-compose up` output.
- **Priority:** P0
- **Effort:** L
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (CI/CD infrastructure)

### IP.PR.09.017 — Let's Encrypt SSL Automation
- **Category:** DevOps
- **Implementation Scope:** Configure nginx or ALB with Let's Encrypt via Certbot. Automated renewal cron job (`certbot renew`). Force HTTPS redirect. Add HSTS header: `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`. Document in `docs/SSL_SETUP.md`. For local dev, keep self-signed cert from PR.08. For staging/production, use ACM (AWS Certificate Manager) if on AWS, or Certbot if on bare metal.
- **Acceptance Criteria:**
  1. `https://staging.bhojango.com` loads with valid Let's Encrypt certificate.
  2. HTTP requests redirect to HTTPS with 301.
  3. HSTS header present on all responses.
  4. Certificate auto-renews before expiration.
- **Evidence Required:** SSL Labs test showing A+ grade. `curl -I http://...` showing 301 to HTTPS. Browser showing valid cert details.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.08.004 (self-signed HTTPS foundation)
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (Let's Encrypt / ACM)

### IP.PR.09.018 — Inter-Service HMAC Authentication
- **Category:** Backend
- **Implementation Scope:** Generate shared 32+ char HMAC secret (`INTERNAL_AUTH_SECRET` env var, same across all services). Internal requests include `X-Internal-Token` header with HMAC-SHA256 of `{method}:{path}:{timestamp}` using shared secret. Receiver middleware validates HMAC and checks timestamp within 60s to prevent replay. Apply to all internal endpoints (e.g., order-svc calling payment-svc, batch-engine calling delivery-svc). Public routes (auth, health, public restaurant list) exempt. Return 401 if token missing or invalid. Log all failed internal auth attempts.
- **Acceptance Criteria:**
  1. Internal request without `X-Internal-Token` returns 401.
  2. Request with valid token and fresh timestamp succeeds.
  3. Request with token based on expired timestamp (>60s) returns 401.
  4. All inter-service calls include the header.
- **Evidence Required:** `curl` without header → 401. `curl` with valid header → 200. `curl` with expired timestamp → 401.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.019 — Distributed Redis Rate Limiting
- **Category:** Backend
- **Implementation Scope:** Replace per-instance SlowAPI limits with Redis-backed sliding window. Use `fastapi-limiter` or custom middleware with `aioredis`. Config per endpoint tier: public (100/min/IP), auth (10/min/IP), internal (1000/min/service). Store `rate_limit:{endpoint}:{identifier}` as sorted set with timestamps. Cleanup old entries on each check. Return 429 with `Retry-After` header. Apply to Kong gateway as well using Redis-backed rate limit plugin.
- **Acceptance Criteria:**
  1. 101st request from same IP within 1 min returns 429.
  2. Rate limit is shared across all service instances (test by scaling to 2 replicas).
  3. `Retry-After` header present on 429 responses.
  4. Internal service requests have higher limits and separate counter.
- **Evidence Required:** `ab` or `k6` load test showing 429 after limit. Redis `ZRANGE` showing timestamp entries.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.003 (rate limiting foundation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.020 — Admin Full Analytics Dashboard
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Add aggregation endpoints: `GET /api/v1/admin/analytics/revenue?period=daily|weekly|monthly&from=&to=`. `GET /api/v1/admin/analytics/orders/hourly` (24-hour heatmap). `GET /api/v1/admin/analytics/drivers/performance` (on-time %, earnings, delivery count). `GET /api/v1/admin/analytics/customers/retention` (cohort table: users ordered in week N who reordered in week N+1). Use SQL window functions and CTEs for efficient aggregation. **Frontend (admin):** Add Analytics page with date range picker. Revenue line chart with period toggle. Hourly order volume bar chart (heatmap-style). Top 10 restaurants table. Driver performance leaderboard. Customer retention cohort grid.
- **Acceptance Criteria:**
  1. Revenue chart shows correct daily totals for selected date range.
  2. Hourly heatmap shows order distribution across 24 hours.
  3. Driver performance table sorts by on-time rate.
  4. Customer retention cohort shows percentage reordering per week.
- **Evidence Required:** Screenshot of admin analytics page. SQL query `EXPLAIN ANALYZE` showing index usage.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.08.008 (admin charts foundation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.021 — Group Ordering with Shareable Link
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `POST /api/v1/group-orders` — creates group order, generates short invite code (8 chars), returns `{invite_code, expires_at}`. `GET /api/v1/group-orders/{code}` — returns current group cart state. `POST /api/v1/group-orders/{code}/items` — adds item (any authenticated user with code). `POST /api/v1/group-orders/{code}/lock` — host locks cart, selects split type (`equal` or `by_item`). `POST /api/v1/group-orders/{code}/checkout` — host pays. Store group order state in PostgreSQL + Redis pub/sub for real-time sync. **Frontend:** "Start Group Order" button on restaurant page. Share modal with copyable link and WhatsApp share. Live participant list. Cart updates sync across devices (poll every 3s or WebSocket). Split bill selector. Locked state prevents further edits.
- **Acceptance Criteria:**
  1. Host generates shareable link. Friends open link and add items.
  2. Cart updates visible to all participants within 3s.
  3. Host locks cart and selects equal split. Each friend's share calculated correctly.
  4. Group order expires after 30 min of inactivity.
- **Evidence Required:** Screen recording of 3 users adding to group cart. DB query showing `group_orders` and `group_order_items`. Redis PUBLISH log showing sync events.
- **Priority:** P1
- **Effort:** L
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.022 — Multi-Restaurant Cart
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Remove cross-restaurant cart guard. Allow items from multiple restaurants in cart. `POST /api/v1/cart/items` accepts `restaurant_id` per item. Cart returns grouped by restaurant: `{restaurants: [{restaurant_id, items, subtotal, delivery_fee}, ...], total}`. `POST /api/v1/orders/multi` creates a `multi_order` parent record and 2+ child `orders` (one per restaurant). Delivery fees calculated per restaurant based on distance. **Frontend:** Cart page shows restaurant sections (mini-carts). Each section has its own subtotal and delivery fee. Checkout page shows unified summary with restaurant breakdown. Order history shows linked multi-order with expand/collapse per restaurant.
- **Acceptance Criteria:**
  1. Cart accepts items from 2+ restaurants without error.
  2. Each restaurant section shows correct subtotal and delivery fee.
  3. Checkout creates separate orders per restaurant linked by `multi_order_id`.
  4. Order history shows linked multi-order with individual tracking links.
- **Evidence Required:** Screen recording of multi-restaurant cart. DB query showing `orders` with same `multi_order_id`.
- **Priority:** P1
- **Effort:** L
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.023 — Dynamic Surge Pricing
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `dynamic_pricing` table with active rules. Cron job or in-memory check runs at checkout: if current time within peak window (12-14h, 19-22h) OR weather API reports rain, apply multiplier (1.2x, 1.5x, 2.0x). Store active multiplier in Redis with 5min TTL. `GET /api/v1/pricing/surge?lat=&lng=` returns current multiplier and reason. **Frontend:** Checkout shows transparent badge: "Peak hour — ₹15 extra for faster delivery" with info tooltip. Badge color: saffron (#E65100) for warning. Customer can see fee breakdown including surge line item.
- **Acceptance Criteria:**
  1. Ordering at 12:30 PM triggers 1.2x multiplier on delivery fee.
  2. Rainy weather triggers 1.5x multiplier.
  3. Badge explains the exact reason for fee increase.
  4. Fee breakdown shows original fee, surge amount, and total.
- **Evidence Required:** `curl` showing surge pricing at peak hour. Screenshot of checkout badge and tooltip.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (weather API)

### IP.PR.09.024 — Customer Support Chat Widget
- **Category:** Frontend + Backend
- **Implementation Scope:** **Option A (custom):** WebSocket chat server. `POST /api/v1/support/tickets` creates ticket. `WS /ws/support/{ticket_id}` for real-time chat. Messages stored in `support_tickets` + `support_messages` table. Admin dashboard shows open tickets with unread count. **Option B (external):** Embed Intercom free tier or Crisp free tier script. Configure with `INTERCOM_APP_ID` or `CRISP_WEBSITE_ID` env var. Pre-fill user name, email, and current order context. Use Option B for speed, Option A for data ownership. Include ticket status: `open`, `in_progress`, `resolved`. Escalation to email if unresolved >24h.
- **Acceptance Criteria:**
  1. Chat widget visible on all customer pages (bottom-right).
  2. Customer can send message and receive reply within app.
  3. Ticket created with user and order context pre-filled.
  4. Admin dashboard shows ticket list with status and assignee.
- **Evidence Required:** Screenshot of chat widget. Admin ticket list view. DB query showing `support_tickets`.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Intercom/Crisp) / 🟢 LOCAL/DEMO-SAFE (custom WebSocket)

### IP.PR.09.025 — Post-Delivery Feedback and NPS Survey
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `POST /api/v1/orders/{id}/feedback` accepts `rating` (1-5), `review_text`, `nps_score` (0-10). Store in `feedback` table. Trigger: 1 hour after `order.delivered` event, send push/email prompting feedback. NPS survey sent 24h after delivery via email: "How likely are you to recommend BhojanGo?" Calculate rolling NPS: `% promoters (9-10) - % detractors (0-6)`. Expose `GET /api/v1/admin/analytics/nps`. **Frontend:** Post-delivery modal: star rating + text box. Optional NPS slider 0-10. Thank you state after submission. Order history shows "Rate your order" button for unrated completed orders.
- **Acceptance Criteria:**
  1. Customer receives feedback prompt 1h after delivery.
  2. Rating 1-5 stars + text review stored and linked to order.
  3. NPS survey sent 24h after delivery, response stored.
  4. Admin dashboard shows rolling NPS score and rating distribution.
- **Evidence Required:** Screenshot of feedback modal. Email screenshot of NPS survey. Admin NPS chart.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.07.020 (review system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.026 — Mobile Payment SDK Integration
- **Category:** Frontend (Mobile)
- **Implementation Scope:** Integrate `@stripe/stripe-react-native` in Expo mobile app. Collect card details via `CardField`. Confirm payment with `confirmPayment(clientSecret)`. For India, integrate Razorpay React Native SDK (`react-native-razorpay`). Show payment method selector: Card / UPI / Wallet. Handle 3D Secure / SCA challenges. On success, navigate to order tracking. On failure, show error toast with retry.
- **Acceptance Criteria:**
  1. Mobile checkout collects card details via Stripe SDK.
  2. Test payment succeeds and navigates to tracking.
  3. UPI payment works via Razorpay SDK on Android.
  4. Payment failure shows user-friendly error with retry button.
- **Evidence Required:** Mobile screen recording of payment flow. Stripe dashboard showing mobile payment.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.09.001, IP.PR.09.002
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Stripe/Razorpay mobile SDKs)

### IP.PR.09.027 — Mobile Cart Persistence
- **Category:** Frontend (Mobile)
- **Implementation Scope:** Add Zustand persist middleware with `expo-secure-store` (sensitive) or `AsyncStorage` (non-sensitive). Persist cart items, quantities, and restaurant IDs across app restarts. On app launch, hydrate cart from storage. Sync with server when online (merge local + server cart). Handle conflicts: server wins for quantity, local additions merged.
- **Acceptance Criteria:**
  1. Add items to cart, kill app, reopen — cart items still present.
  2. Cart survives app update.
  3. Online sync merges local cart with server without duplication.
  4. Offline additions queued and synced on reconnect.
- **Evidence Required:** Mobile screen recording: add items → restart app → cart preserved.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.09.028 — Batch Engine Deployment (CI/CD + Terraform + Docker Compose)
- **Category:** DevOps
- **Implementation Scope:** Add batch-engine to GitHub Actions CI matrix (lint, test, build, push). Add batch-engine service to `docker-compose.yml` with PostgreSQL schema auto-migration. Add Terraform ECS task definition, service, and ALB target group for batch-engine. Add batch-engine to Kong gateway config (`/api/v1/batches/*` → `batch-engine:8007`). Ensure batch-engine consumes SQS `order.confirmed` events and publishes SNS `batch.formed`.
- **Acceptance Criteria:**
  1. Batch-engine builds and tests pass in CI.
  2. Docker Compose includes batch-engine and starts successfully.
  3. Terraform deploys batch-engine to staging ECS.
  4. Kong routes `/api/v1/batches/*` to batch-engine.
- **Evidence Required:** GitHub Actions green run. `docker-compose ps` showing batch-engine. ECS service count = 1.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09.016
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (ECS/Terraform)

## 16. Acceptance Criteria

- [ ] Real Stripe sandbox payment creates PaymentIntent, returns client_secret, and completes end-to-end.
- [ ] Real Razorpay sandbox order creates Order, accepts UPI test payment, and completes end-to-end.
- [ ] Stripe webhook verifies signature, updates payment status, and is idempotent (Redis dedup).
- [ ] Razorpay webhook verifies HMAC, updates payment status, and is idempotent.
- [ ] Full and partial refunds create provider refund, update `refunds` table, and credit wallet.
- [ ] FCM push sent on every order status change to customer's registered device.
- [ ] SendGrid emails dispatched for order confirmation, cancellation, refund, and promotion.
- [ ] Twilio SMS dispatched for OTP and order status updates.
- [ ] WebSocket driver tracking shows moving map pin with 10s updates and route polyline.
- [ ] Batch engine ingests orders, creates batches, assigns nearest driver, and generates route stops with ETA.
- [ ] S3 image upload + Sharp thumbnail generation + CloudFront CDN serving works.
- [ ] Prometheus `/metrics` exposed on all services; Grafana dashboard shows request rate/latency/errors.
- [ ] Loki ingests structured JSON logs; Grafana can query by service/level/text.
- [ ] Jaeger traces show cross-service spans with `X-Request-ID` propagation.
- [ ] GitHub Actions CI fails on lint/test failure (no bypass); deploys to staging on merge.
- [ ] Docker Compose starts full stack (all services + infra) within 5 minutes.
- [ ] Let's Encrypt SSL valid on staging with HTTPS redirect and HSTS.
- [ ] Inter-service HMAC auth rejects requests without `X-Internal-Token`; valid token accepted.
- [ ] Distributed Redis rate limiting returns 429 after threshold with `Retry-After` header.
- [ ] Admin analytics shows revenue charts, hourly heatmap, driver performance, and retention cohorts.
- [ ] Group ordering: shareable link, multi-device sync, lock, split bill, checkout.
- [ ] Multi-restaurant cart accepts items from 2+ restaurants, splits fees, creates linked orders.
- [ ] Dynamic pricing applies multiplier during peak/rain with transparent badge.
- [ ] Support chat widget creates tickets with order context; admin can view and respond.
- [ ] Post-delivery feedback (1-5 stars + text) and NPS survey (0-10) stored and visible in admin.
- [ ] Mobile payment SDK integrated (Stripe + Razorpay native SDKs).
- [ ] Mobile cart persists across app restarts with offline sync.
- [ ] Batch-engine deployed in CI/CD, Docker Compose, Terraform ECS, and Kong.
- [ ] Core customer loop and three-sided marketplace remain stable (no regression from PR.08).

## 17. Evidence Required

- Stripe dashboard screenshot of successful test payments (card + refund).
- Razorpay dashboard screenshot of test order and UPI payment.
- `curl` showing webhook signature verification pass and fail cases.
- Redis `SMEMBERS processed_webhook_events:*` showing deduplication.
- Screenshot of FCM push on Android/iOS device. Firebase Console delivery report.
- Screenshot of received SendGrid email (order confirmation + Hindi template).
- Screenshot of received Twilio SMS (OTP + order status).
- Screen recording of customer tracking page with moving map pin and route polyline.
- Log trace showing: order.confirmed → batch-engine → batch.assigned → delivery-svc → driver notified.
- S3 bucket + CloudFront distribution screenshots. Network tab showing image served with `CF-Cache-Status: HIT`.
- Prometheus targets page (all UP). Grafana dashboard screenshots. Loki query results. Jaeger trace screenshot.
- GitHub Actions run showing all green with batch-engine included.
- SSL Labs test showing A+ grade. `curl -I http://...` showing 301 to HTTPS.
- `curl` without `X-Internal-Token` → 401. `curl` with valid token → 200.
- `k6` or `ab` load test showing 429 after rate limit with `Retry-After`.
- Admin analytics page screenshots: revenue chart, hourly heatmap, driver leaderboard, retention grid.
- Screen recording of group order with 3 participants adding items and host checking out.
- Screen recording of multi-restaurant cart with 2 restaurants and split checkout.
- Screenshot of dynamic pricing badge on checkout with tooltip.
- Screenshot of support chat widget and admin ticket list.
- Screenshot of feedback modal and NPS survey email.
- Mobile screen recording of Stripe/Razorpay SDK payment flow.
- Mobile screen recording of cart persistence across app restart.
- ECS console screenshot showing batch-engine service running.

## 18. Dependencies

### External Tools
- Docker + docker-compose (full stack local dev).
- Node.js + pnpm (frontend builds).
- Python + Poetry (backend services).
- Stripe sandbox account + API keys (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`).
- Razorpay sandbox account + API keys (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`).
- Firebase project + service account JSON (FCM).
- SendGrid account + API key (`SENDGRID_API_KEY`).
- Twilio account + phone number (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`). Optional: MSG91 auth key for India SMS.
- AWS account (S3, CloudFront, ECS, ECR, ACM) OR Cloudflare account (CDN + SSL).
- Mapbox free tier access token (`MAPBOX_ACCESS_TOKEN`) or Leaflet (free, no key).
- Weather API key for dynamic pricing (OpenWeatherMap free tier).
- Sharp/ImageMagick for thumbnail generation.
- Prometheus, Grafana, Loki, Jaeger (Docker containers for dev/staging).
- Certbot (for Let's Encrypt) or AWS ACM.
- GitHub Actions runners.

### Internal Dependencies
- **PR.08 must be complete:** Accessibility, performance, security, PWA, animations, SEO, OAuth, search, charts, i18n, review photos, offline cart, design tokens.
- `redis` must be running (webhook idempotency, rate limiting, group cart sync, driver location).
- `kong` gateway must route to all services including batch-engine.
- PostgreSQL must have all new tables created via migrations.
- Existing SNS topics and SQS queues must be configured for event flow.
- `next-pwa` service worker must be functional (foundation for offline features).

## 19. Risks / Blockers

- **Payment provider sandbox setup:** Stripe and Razorpay require account creation and webhook endpoint registration. Mitigation: document setup in `docs/PAYMENT_SETUP.md`. Use Stripe CLI for local webhook forwarding.
- **FCM push testing:** Requires real Android/iOS device or emulator with Google Play Services. Mitigation: use Firebase test lab or physical device. Test pushes via Firebase Console first.
- **SendGrid email deliverability:** Free tier (100 emails/day) sufficient for dev. Risk of emails landing in spam. Mitigation: configure SPF/DKIM/DMARC DNS records. Use authenticated domain.
- **Twilio SMS cost:** International SMS for India can be expensive. Mitigation: use MSG91 for India OTPs, Twilio for US and order status.
- **WebSocket scaling:** Single WebSocket server won't scale beyond ~10k concurrent connections. Mitigation: use Redis pub/sub as message broker between multiple WebSocket instances. Document horizontal scaling path.
- **Batch-engine integration complexity:** Touching order-svc, delivery-svc, and batch-engine simultaneously introduces regression risk. Mitigation: feature flags for batch assignment. Rollback path via `batch.enabled=false` env var.
- **S3 + CloudFront cost:** Image storage and CDN egress incur AWS costs. Mitigation: use AWS free tier (5GB S3, 50GB CloudFront). Implement lifecycle policies.
- **Observability resource usage:** Prometheus, Grafana, Loki, Jaeger containers consume significant RAM. Mitigation: limit retention (7 days dev, 30 days staging). Use managed services in production (AWS AMP, CloudWatch, X-Ray).
- **CI/CD secrets management:** Provider API keys must not leak in CI logs. Mitigation: use GitHub Secrets + AWS Secrets Manager. Mask all keys in workflow output.
- **Let's Encrypt rate limits:** 50 certificates per domain per week. Mitigation: use staging endpoint during testing. Use wildcard cert if subdomains exceed limit.
- **Inter-service auth rollout:** Adding HMAC to all internal calls is a breaking change if any call site is missed. Mitigation: run integration tests with auth enforced. Start with `LOG_ONLY` mode before `ENFORCE`.
- **Dynamic pricing backlash:** Customers may react negatively to surge fees. Mitigation: cap multiplier at 1.5x. Always show transparent explanation. Offer eco-batch discount as offset.

## 20. Exit Criteria

- All P0 work items (IP.PR.09.001 through IP.PR.09.006, IP.PR.09.009, IP.PR.09.010, IP.PR.09.011, IP.PR.09.016, IP.PR.09.018, IP.PR.09.019, IP.PR.09.026, IP.PR.09.027, IP.PR.09.028) implemented and verified.
- All P1 work items (IP.PR.09.007, IP.PR.09.008, IP.PR.09.012 through IP.PR.09.015, IP.PR.09.017, IP.PR.09.020 through IP.PR.09.025) implemented and verified.
- Real payments: Stripe and Razorpay sandbox transactions complete end-to-end.
- Webhooks: Signature verification active, idempotency working, no duplicate processing.
- Refunds: Provider refund + wallet credit verified.
- Notifications: Push, email, SMS all dispatching from SQS events.
- Tracking: Moving map pin with 10s updates and route polyline functional.
- Batching: Order pool → batch creation → driver assignment → route stops → ETA per stop.
- Images: S3 upload, Sharp thumbnails, CloudFront serving all functional.
- Observability: Prometheus metrics, Grafana dashboards, Loki queries, Jaeger traces all operational.
- CI/CD: GitHub Actions green, no `|| true` bypass, batch-engine included, staging deployment active.
- SSL: Valid Let's Encrypt cert, HTTPS redirect, HSTS headers.
- Inter-service auth: All internal calls carry valid HMAC token.
- Rate limiting: Distributed Redis limits active, 429 with `Retry-After`.
- Admin analytics: Revenue, hourly heatmap, driver performance, retention cohorts visible.
- Group ordering: Shareable link, sync, split bill, checkout all functional.
- Multi-restaurant cart: 2+ restaurants, split fees, linked orders.
- Dynamic pricing: Peak/rain multipliers with transparent badge.
- Support chat: Widget visible, tickets created, admin responds.
- Feedback/NPS: Post-delivery prompt and 24h survey stored and visible.
- Mobile SDK: Stripe + Razorpay native payments work.
- Mobile cart: Persists across restarts.
- Core customer loop and three-sided marketplace remain stable (no regression from PR.08).
- Evidence screenshots/recordings captured per Section 17.
- PR.09 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.08)

PR.09 directly depends on PR.08 achievements:
- **IP.PR.08.001** — Accessibility audit: foundation for support chat widget keyboard accessibility and NPS modal focus trapping.
- **IP.PR.08.002** — Performance optimization: Next.js `<Image>` foundation for CDN image serving and Sharp thumbnail integration.
- **IP.PR.08.003** — Security hardening: CSRF, XSS, brute force foundation for inter-service HMAC auth and distributed rate limiting.
- **IP.PR.08.006** — PWA + service worker: foundation for offline cart sync and push notification service worker integration.
- **IP.PR.08.008** — Admin charts: foundation for full analytics dashboard (revenue, heatmap, retention).
- **IP.PR.08.011** — SEO meta tags: foundation for email template branding and JSON-LD in email receipts.
- **IP.PR.08.012** — Google OAuth: foundation for social login pass-through on mobile and group order auth.
- **IP.PR.08.015** — i18n: foundation for Hindi email/SMS/push templates.
- **IP.PR.08.016** — Offline cart sync: foundation for mobile cart persistence and server merge logic.
- **IP.PR.07.007** — WebSocket tracking: foundation for real-time driver map broadcasting.
- **IP.PR.07.011** — Payment/wallet schema: foundation for real provider integration and refund table.
- **IP.PR.07.012** — Batch engine foundation: foundation for driver assignment integration and route optimization.
- **IP.PR.07.014** — Email templates: foundation for SendGrid production dispatch.
- **IP.PR.07.015** — Device token storage: foundation for FCM push production dispatch.

## 22. Connected Next-Level Requirements (link to PR.10)

PR.10 (Mature Marketplace Platform, score 10/10) builds on PR.09 and requires:
- Working payment webhooks, refunds, and wallet as foundation for subscription billing and restaurant profit-share model.
- FCM push production as foundation for smart locker unlock notifications and meal rescue flash sales.
- Real-time tracking map as foundation for kitchen radar and driver shift auction.
- Batch engine fully operational as foundation for AI/ML scoring and predictive demand.
- Observability stack as foundation for auto-scaling and anomaly detection.
- Group ordering as foundation for family plan subscriptions and corporate meal programs.
- Dynamic pricing as foundation for driver shift auction pricing.
- NPS data as foundation for ML-based recommendation and churn prediction.

PR.10 will introduce:
- AI smart meal suggestions based on order history, time, weather.
- Voice ordering NLP (Web Speech API + natural language parsing).
- Smart lockers / IoT pickup point network with QR unlock.
- Meal rescue / end-of-day flash sales (automated 50% off push at 9 PM).
- Loyalty tiers full activation (Gold/Platinum with free delivery and exclusive deals).
- Restaurant subscription profit-share model (flat monthly fee, zero commission).
- Corporate meal program with invoicing and group billing.
- Kitchen tablet POS integration for real-time prep status.
- Carbon offset gamification (trees planted per 25 batched orders).
- Multi-region deployment with disaster recovery.
- Advanced fraud detection using ML.
- Dark mode toggle across all apps.
- Onboarding wizard after signup.
- Grocery vertical support.

PR.10 will be blocked if:
- Payment webhooks are not idempotent (duplicate charges destroy trust).
- FCM push not production-ready (no engagement for flash sales).
- Batch engine not integrated with delivery (no driver assignment = no batching).
- Observability missing (operations blind during scaling events).
- CI/CD not deploying batch-engine (feature cannot reach staging).
- Mobile payment SDK missing (cannot collect real revenue).
- Dynamic pricing not transparent (customer backlash).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (9/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.08 complete) described | Planner | ✅ |
| 4 | Target state (PR.09 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.09 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.09 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty, success states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage notes deferred differentiators | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.09.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 20 work items present | Planner | ✅ |
| 17 | Work items cover all required PR.09 areas (payments, webhooks, refunds, push, email, SMS, tracking, batching, images, observability, CI/CD, SSL, inter-service auth, rate limiting, admin analytics, group ordering, multi-restaurant cart, dynamic pricing, support chat, feedback/NPS, mobile SDK, mobile cart, batch deployment) | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention payment sandbox setup, FCM testing, SendGrid deliverability, Twilio cost, WebSocket scaling, batch integration risk, S3 cost, observability resources, CI secrets, Let's Encrypt limits, inter-service auth rollout, dynamic pricing backlash | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.08) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.10) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and >=9 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format (IP.PR.09.001 through IP.PR.09.028) and cover all required PR.09 areas: real Stripe integration (IP.PR.09.001), real Razorpay integration (IP.PR.09.002), Stripe webhook with signature verification (IP.PR.09.003), Razorpay webhook with HMAC verification (IP.PR.09.004), refund processing (IP.PR.09.005), FCM push dispatch (IP.PR.09.006), SendGrid email dispatch (IP.PR.09.007), Twilio SMS dispatch (IP.PR.09.008), real-time driver tracking WebSocket + map (IP.PR.09.009), batch engine driver assignment (IP.PR.09.010), route optimization (IP.PR.09.011), S3 + CDN image pipeline (IP.PR.09.012), Prometheus + Grafana (IP.PR.09.013), Loki (IP.PR.09.014), Jaeger tracing (IP.PR.09.015), CI/CD pipeline (IP.PR.09.016), Let's Encrypt SSL (IP.PR.09.017), inter-service HMAC auth (IP.PR.09.018), distributed Redis rate limiting (IP.PR.09.019), admin full analytics (IP.PR.09.020), group ordering (IP.PR.09.021), multi-restaurant cart (IP.PR.09.022), dynamic pricing (IP.PR.09.023), support chat (IP.PR.09.024), feedback and NPS (IP.PR.09.025), mobile payment SDK (IP.PR.09.026), mobile cart persistence (IP.PR.09.027), and batch engine deployment (IP.PR.09.028).
- Scope is tightly bounded to score 9/10 (production-grade with real providers, observability, advanced marketplace features). No premature enterprise novelty (AI, blockchain, voice, drones) — all deferred to PR.10.
- Out-of-scope explicitly excludes smart lockers, voice NLP, blockchain, AI/ML, white-label, drone delivery, real-time traffic API, multi-region deployment, advanced fraud detection, subscription meal plans, kitchen POS.
- Data model coverage addresses refunds, group orders, group order items, dynamic pricing, feedback, support tickets, multi_order_id, batch_id, fcm_token, processed webhook events, and rate limiting keys.
- Risks and blockers are grounded in known gaps from audits: payment sandbox setup friction, FCM device testing complexity, SendGrid deliverability, Twilio India cost, WebSocket horizontal scaling, batch-engine multi-service regression risk, S3/CloudFront cost, observability resource consumption, CI secrets leakage, Let's Encrypt rate limits, HMAC auth breaking missed call sites, and customer backlash on surge pricing.
- Connected previous-level and next-level requirements are explicitly documented with specific work item references and blocker conditions.
- Feasibility tags use the required color system: 🟡 OPTIONAL EXTERNAL for Stripe (IP.PR.09.001), Razorpay (IP.PR.09.002), webhooks (IP.PR.09.003/004), refunds (IP.PR.09.005), FCM (IP.PR.09.006), SendGrid (IP.PR.09.007), Twilio (IP.PR.09.008), S3/CloudFront (IP.PR.09.012), weather API (IP.PR.09.023), Intercom/Crisp (IP.PR.09.024), and mobile SDKs (IP.PR.09.026); 🔴 FUTURE INFRA for Prometheus/Grafana (IP.PR.09.013), Loki (IP.PR.09.014), Jaeger (IP.PR.09.015), CI/CD (IP.PR.09.016), ECS deployment (IP.PR.09.028), and Let's Encrypt (IP.PR.09.017); 🟢 LOCAL/DEMO-SAFE for tracking WebSocket (IP.PR.09.009), batch assignment (IP.PR.09.010), route optimization (IP.PR.09.011), HMAC auth (IP.PR.09.018), rate limiting (IP.PR.09.019), admin analytics (IP.PR.09.020), group ordering (IP.PR.09.021), multi-restaurant cart (IP.PR.09.022), support chat custom (IP.PR.09.024), feedback/NPS (IP.PR.09.025), and mobile cart persistence (IP.PR.09.027).
- **One point deducted** because the choice between Mapbox and Leaflet for tracking maps, and between Intercom/Crisp and custom WebSocket for support chat, is left to implementation discretion. Additionally, the exact weather API provider (OpenWeatherMap vs. others) for dynamic pricing is not pre-selected. These are minor implementation choices that do not affect plan completeness.

The document is ready for execution.
