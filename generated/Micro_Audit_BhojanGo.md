# BhojanGo — Micro-Level Production & UI/UX Audit

**Scored:** 1 / 10  
**Verdict:** Not demo-ready. A polished homepage masks a fundamentally broken core loop. No user can browse a menu, add to cart, or place an order. Auth works at API level but is forgotten by the frontend. The entire backend foundation exists but lacks critical integration, error handling, and production hardening. UI is a generic Tailwind template with zero product-specific design language.

---

PROTOCOL: If at any point the AI identifies that an ID within a roadmap is technically impossible or high-risk due to a hidden dependency not listed here, it must FLAG the issue for my review BEFORE attempting to solve it. Do not attempt to self-solve architectural blockers

---

Implementation Status column must be one of: [TODO, IN-PROGRESS, BLOCKED, COMPLETED]. If set to BLOCKED, the item must contain a sub-bullet explaining the specific dependency missing.

---

# Production Readiness Scale

| Score | High-Level Target                | What the user should expect                                                                                                                                                                           |
| ----: | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|     1 | Broken shell                     | App opens, but core food-ordering flow is unusable or disconnected.                                                                                                                                   |
|     2 | Browsable prototype              | User can see homepage/listing screens, but menu/cart/checkout/order flow is still broken or mocked poorly.                                                                                            |
|     3 | Core flow partially working      | User can browse restaurants and menus, but cart/checkout/order tracking has major gaps or unreliable behavior.                                                                                        |
|     4 | Internal demo-ready core loop    | User can login or continue as guest → browse restaurants → open restaurant → see menu → add item → view cart → checkout with simulated payment → see order confirmation → see mock tracking timeline. |
|     5 | Usable closed-demo app           | Core loop is stable, key empty/loading/error states exist, seed data looks real, and basic profile/order history works.                                                                               |
|     6 | Closed beta-ready marketplace    | Customer, restaurant owner, delivery partner, and admin flows exist at basic level. Search, filters, address, availability, cancellation, and order status are functional.                            |
|     7 | Reliable beta product            | APIs are faster and resilient, auth/roles are consistent, checkout/order state is safer, observability/logging exists, and common edge cases are handled.                                             |
|     8 | Early production-ready           | App is polished across mobile/tablet/desktop, accessible, secure enough for limited users, performant, and has strong demo + beta credibility.                                                        |
|     9 | Production-grade competitive app | Real payment/provider integrations, robust admin operations, scalable flows, strong monitoring, recovery paths, and professional UX across major journeys.                                            |
|    10 | Mature marketplace platform      | Product is stable, trusted, distinctive, operationally manageable, scalable, and strong enough to compete with serious food-delivery platforms.                                                       |

# Novelty / Uniqueness Scale

| Score | High-Level Target                    | What the user should expect                                                                                                                                         |
| ----: | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|     1 | Generic clone                        | Looks and behaves like a basic Swiggy/Zomato template with no meaningful differentiation.                                                                           |
|     2 | Light cosmetic difference            | Some branding, colors, or layout differences exist, but no product-level uniqueness.                                                                                |
|     3 | Small convenience features           | Basic favorites, reorder, better filters, veg/non-veg visibility, and cleaner menu discovery start to differentiate the app.                                        |
|     4 | Demo-level differentiation           | User can see practical unique touches: fastest-near-you lane, meal tags, loyalty preview, smart reorder, better trust badges, and local-first discovery.            |
|     5 | Retention-focused uniqueness         | Favorites, reorder, loyalty, saved preferences, personalized homepage sections, and better offers make repeat usage easier.                                         |
|     6 | Marketplace-specific differentiation | Group ordering, office lunch mode, meal rescue deals, home-chef/community kitchen, nutrition/allergen info, and transparent fees are meaningfully integrated.       |
|     7 | Smart personalization                | Recommendations adapt to user history, time, cuisine preference, budget, distance, veg preference, and repeat behavior without needing heavy AI infrastructure.     |
|     8 | Strong product identity              | App has a distinct food-ordering experience: tailored UI, trust system, freshness/speed cues, smart bundles, contextual deals, and memorable ordering flows.        |
|     9 | Defensible differentiation           | Novel features are operationally useful, not gimmicks: group carts, meal rescue, loyalty tiers, restaurant insights, delivery confidence, and customer trust loops. |
|    10 | Category-leading experience          | Product feels meaningfully different from generic delivery apps, with strong personalization, trust, speed, community, retention, and marketplace intelligence.     |

---

# Part 1 — Micro-Level Gaps (Category: BG.B = Backend)

## BG.B.S001 — user-svc (Identity Service)

### BG.B.S001.001 — Missing `GET /api/v1/me`
- **Gap:** No endpoint returning current auth user.
- **Impact:** Frontend cannot display user name, avatar, or role after login.
- **Scope:** Add 15-line endpoint decoding JWT sub claim, querying user by ID.
- **Evidence:** Backend tests returned 404. Frontend auth broken because no profile data source.
- **AC:** `GET /api/v1/me` returns `{id, email, full_name, role, phone, is_verified}` with 200.

### BG.B.S001.002 — Rate Limiter Blocks Test Automation
- **Gap:** SlowAPI limiter returns 429 after 5 sequential logins in <3s.
- **Impact:** Developers cannot run automated tests.
- **Scope:** Add env-based whitelist (`APP_ENV=development` → no rate limit) or increase burst to 20 for test users.
- **Evidence:** 3 login tests skipped due to 429.
- **AC:** Running `pytest` without artificial delays passes all login tests.

### BG.B.S001.003 — No Password Reset Flow
- **Gap:** Users cannot recover forgotten passwords.
- **Impact:** Customer churn.
- **Scope:** `POST /api/v1/auth/forgot-password` → OTP email → `POST /api/v1/auth/reset-password`.
- **Evidence:** Not tested because endpoint doesn't exist.
- **AC:** User can reset password end-to-end.

### BG.B.S001.004 — No Social Login (OAuth)
- **Gap:** Email/password only.
- **Impact:** High-friction onboarding.
- **Scope:** Add Google OAuth 2.0 PKCE flow, store `provider` and `provider_id` in users table.
- **AC:** One-click Google signup available.

### BG.B.S001.005 — JWT Secret is Placeholder
- **Gap:** `JWT_SECRET=dev-secret-key-change-in-production-min32chars`.
- **Impact:** In production, trivial token forgery.
- **Scope:** Fail startup if secret <32 chars or matches the placeholder.
- **AC:** `uvicorn` refuses to start with placeholder secret.

### BG.B.S001.006 — bcrypt 5.0 / passlib Incompatibility
- **Gap:** Dependency conflict prevents boot on default install.
- **Impact:** Fresh clone fails.
- **Scope:** Pin `bcrypt<5.0.0` in all service pyproject.toml, document in README.
- **AC:** `poetry install` on fresh machine starts service without manual pip fix.

### BG.B.S001.007 — Missing Admin Summary Endpoint
- **Gap:** No dashboard stats API for super_admin.
- **Impact:** Admin panel blind.
- **Scope:** `GET /api/v1/admin/summary` returning total users, orders, revenue.
- **AC:** Returns JSON with counts.

---

## BG.B.S002 — restaurant-svc (Discovery Service)

### BG.B.S002.001 — `GET /api/v1/restaurants/{id}/menu` Returns 500
- **Gap:** OpenSearch connection failure kills menu fetch.
- **Impact:** **CORE LOOP BROKEN.** User cannot see menu, cannot add to cart.
- **Scope:** (1) Start OpenSearch locally with Docker, OR (2) Add fallback to direct DB query on `menu_categories` + `menu_items` when OpenSearch unavailable.
- **Evidence:** Backend test returned 500. Playwright confirms blank menu.
- **AC:** Menu loads with <500ms latency regardless of OpenSearch state.

### BG.B.S002.002 — OpenSearch Graceless Degradation
- **Gap:** No try/catch around OpenSearch client.
- **Impact:** Any OpenSearch outage = total menu outage.
- **Scope:** Wrap search calls in try/except. On ConnectionError, log.warning and fallback to direct SQL.
- **AC:** Kill OpenSearch container, menu still loads.

### BG.B.S002.003 — No Search Endpoint
- **Gap:** Restaurant list cannot be searched by name or cuisine.
- **Impact:** Terrible discovery UX.
- **Scope:** `GET /api/v1/restaurants/search?q=biryani` → case-insensitive ILIKE on `name` and `cuisine_types`.
- **AC:** Returns filtered list matching query.

### BG.B.S002.004 — No Filter / Sort Params
- **Gap:** No `?cuisine=Indian&min_rating=4.0&sort=rating`.
- **Impact:** User scrolls through 96 undifferentiated cards.
- **Scope:** Extend list query with WHERE filters and ORDER BY param.
- **AC:** URL params filter and sort correctly.

### BG.B.S002.005 — No Image CDN
- **Gap:** Images served from local filesystem via Next.js public.
- **Impact:** Slow load, no caching, storage bloat.
- **Scope:** Keep local images for dev. In production, upload to S3 + CloudFront. Store `image_url` as absolute CloudFront URL.
- **AC:** Images load in <100ms with cache TTL.

### BG.B.S002.006 — Restaurant Status Not Enforced
- **Gap:** `status='pending_approval'` restaurants still appear in public list.
- **Impact:** Users see unapproved restaurants.
- **Scope:** Add `WHERE status = 'active' AND is_active = true` to list query.
- **AC:** Pending restaurants hidden from public list.

---

## BG.B.S003 — order-svc (Transaction Service)

### BG.B.S003.001 — Order Creation Tests Skipped
- **Gap:** Authenticated POST `/api/v1/orders` failed in tests.
- **Impact:** Core transaction flow unverified.
- **Scope:** Debug auth middleware. Ensure request body validation accepts `items[]` JSONB with `menu_item_id`, `quantity`, `unit_price`.
- **AC:** Backend test creates order with 200.

### BG.B.S003.002 — No Order Cancellation Endpoint
- **Gap:** Cannot cancel an order after placing.
- **Impact:** User frustration.
- **Scope:** `PATCH /api/v1/orders/{id}/cancel` with `reason`. Refund via payment-svc.
- **AC:** Order status changes to `cancelled`, wallet credited back.

### BG.B.S003.003 — No Order Timeline / History
- **Gap:** Status transitions (pending → confirmed → preparing → picked_up → delivered) are opaque.
- **Impact:** No visibility for user or restaurant.
- **Scope:** New table `order_status_history` (id, order_id, status, changed_at). Return in GET order detail.
- **AC:** UI shows timeline: "12:00 - Confirmed", "12:05 - Preparing", etc.

### BG.B.S003.004 — No Restaurant Order Webhook
- **Gap:** New order does not notify restaurant owner in real-time.
- **Impact:** Delayed prep, cold food.
- **Scope:** On order creation, send SSE or WebSocket event to restaurant owner session.
- **AC:** Owner dashboard receives order notification within 2s.

---

## BG.B.S004 — delivery-svc (Fulfillment Service)

### BG.B.S004.001 — Driver Assignment Logic Missing
- **Gap:** No algorithm for matching orders to nearest driver.
- **Impact:** Manual assignment, slow delivery.
- **Scope:** Implement Haversine distance query. POST `/api/v1/deliveries/{order_id}/assign` assigns nearest available driver.
- **AC:** Assigned driver is within 5km pickup radius.

### BG.B.S004.002 — No Real-Time Driver Location
- **Gap:** Driver GPS not tracked.
- **Impact:** User cannot see "driver is 2 minutes away."
- **Scope:** Driver app POSTs lat/lng every 10s to Redis. User GETs location from `/api/v1/deliveries/{order_id}/location`.
- **AC:** Map pin moves in real-time on order tracking page.

### BG.B.S004.003 — ETA Calculation Missing
- **Gap:** No estimated delivery time.
- **Impact:** User uncertainty.
- **Scope:** Calculate ETA = (Haversine prep→pickup distance / 25 km/h * 60) + prep_time_min + dwell_min.
- **AC:** ETA shown in UI ±3 min accuracy.

---

## BG.B.S005 — payment-svc (Payment Service)

### BG.B.S005.001 — No Razorpay Webhook
- **Gap:** `POST /api/v1/payments/webhooks/razorpay` does not exist.
- **Impact:** Payments remain "pending" forever.
- **Scope:** Implement webhook endpoint verifying Razorpay signature, updating `payment_intents.status` to succeeded.
- **AC:** Real Razorpay payment completes end-to-end.

### BG.B.S005.002 — No Stripe Webhook
- **Gap:** Same as above for Stripe.
- **Scope:** Implement stripe webhook handler.
- **AC:** Real Stripe payment completes end-to-end.

### BG.B.S005.003 — No Refund Endpoint
- **Gap:** Cannot refund cancelled orders.
- **Scope:** POST `/api/v1/payments/refund` with `order_id`. Call provider refund API. Credit wallet.
- **AC:** Cancellation refunds money within 24h.

---

## BG.B.S006 — notification-svc (Notification Service)

### BG.B.S006.001 — No Push Notification Delivery
- **Gap:** Device tokens stored but never used.
- **Impact:** No order updates.
- **Scope:** Integrate Firebase Cloud Messaging (FCM). POST `/api/v1/notifications/send` with FCM payload.
- **AC:** Mobile device receives push on order status change.

### BG.B.S006.002 — No Email Notifications
- **Gap:** No email channel.
- **Impact:** No receipt, no marketing.
- **Scope:** Integrate SendGrid. Send order confirmation email.
- **AC:** Email received with order summary.

---

## BG.B.S007 — batch-engine (Batched Delivery Service)

### BG.B.S007.001 — Migration SQL Ordering Bug
- **Gap:** `CREATE TABLE order_pool` references `batches(id)` but `batches` created after.
- **Impact:** Service crashes on first start.
- **Scope:** Fix `001_create_batch_tables.sql` — create batches first. **(Done)** Verify in CI.
- **AC:** Fresh `npm run dev` succeeds on empty DB.

### BG.B.S007.002 — SQS Consumer Not Configured
- **Gap:** `SQS_QUEUE_URL_BATCH` empty.
- **Impact:** Batch engine never sees new orders.
- **Scope:** Use local SQS (ElasticMQ) or Redis pub/sub for dev. Configure real SQS for staging.
- **AC:** Order.placed event triggers batch cycle.

---

## BG.B.D001 — Data / Model Gaps

### BG.B.D001.001 — No Foreign Key from `orders` → `menus`
- **Gap:** `orders.items` JSONB stores menu_item_id but no DB FK.
- **Impact:** Orphaned references if menu_item deleted.
- **Scope:** Add `menu_item_id` FK or keep JSONB but add DB-level validation function.
- **AC:** Cannot insert order with non-existent menu_item_id.

### BG.B.D001.002 — No `order_cancellations` Table
- **Gap:** Cancellation reason stored as nullable string in orders.
- **Impact:** No audit trail.
- **Scope:** New table: id, order_id, reason, cancelled_by, created_at.
- **AC:** Every cancellation logged with user attribution.

### BG.B.D001.003 — `users` Missing `avatar_url` Handling
- **Gap:** Field exists but always NULL.
- **Impact:** Every profile shows generic placeholder.
- **Scope:** Add upload endpoint or Gravatar fallback.
- **AC:** User with no avatar sees Gravatar or initials.

### BG.B.D001.004 — Missing `offers` / `coupons` Table
- **Gap:** No discount/promo infrastructure.
- **Impact:** Cannot run marketing campaigns.
- **Scope:** Create `offers` (id, code, type, value, min_order, expires_at, max_uses, used_count).
- **AC:** "WELCOME20" applies 20% off at checkout.

### BG.B.D001.005 — Missing `favorites` Table
- **Gap:** No user restaurant/bookmark tracking.
- **Impact:** No "reorder from this restaurant" feature.
- **Scope:** `favorites` (user_id, restaurant_id, created_at).
- **AC:** User sees "Favorites" section on homepage.

### BG.B.D001.006 — Missing `reviews` Submitted Data
- **Gap:** `reviews` table exists but no seeded reviews.
- **Impact:** Every restaurant shows 0 reviews.
- **Scope:** Seed 3-5 reviews per restaurant with varying ratings.
- **AC:** Restaurant detail shows realistic review distribution.

---

## BG.B.X001 — Cross-Cutting Concerns

### BG.B.X001.001 — No API Gateway / Router
- **Gap:** Frontend calls 4 separate backend ports (8001, 8002, 8003, 8005).
- **Impact:** CORS complexity, auth duplication, single points of failure.
- **Scope:** Add nginx reverse proxy or Kong. Route `/api/{service}/*` to internal services.
- **AC:** Frontend talks to single origin `localhost:8080/api/`.

### BG.B.X001.002 — No Inter-Service Auth
- **Gap:** Services trust each other implicitly.
- **Impact:** Order-svc can call payment-svc without verification.
- **Scope:** Add internal JWT signing with HMAC secret shared between services.
- **AC:** Internal requests carry `X-Internal-Token` header.

### BG.B.X001.003 — No Centralized Logging
- **Gap:** Each service logs to stdout.
- **Impact:** Debugging distributed failures is impossible.
- **Scope:** Forward JSON logs to OpenSearch or Loki via Fluentd.
- **AC:** Single dashboard shows all service traces for one request_id.

### BG.B.X001.004 — No Monitoring / Alerting
- **Gap:** No Prometheus metrics exposed.
- **Impact:** Outages discovered by users.
- **Scope:** Instrument FastAPI with prometheus-fastapi-instrumentator. Alert on error rate > 5%.
- **AC:** Grafana dashboard shows request rate, latency, error rate per endpoint.

### BG.B.X001.005 — No Retry / Circuit Breaker
- **Gap:** If payment-svc is down, order creation fails instantly.
- **Impact:** Cascade failures.
- **Scope:** Add tenacity retries and circuit breakers (pybreaker) to inter-service clients.
- **AC:** Order creation retries payment 3x with exponential backoff.

---

# Part 2 — Micro-Level Gaps (Category: BG.F = Frontend)

## BG.F.P001 — Homepage (/)

### BG.F.P001.001 — "Find Food" Button Non-Functional
- **Gap:** Click does nothing.
- **Impact:** Primary CTA broken.
- **Scope:** Navigate to `/restaurants?city={input.value}` on click.
- **AC:** Entering "Mumbai" and clicking navigates to filtered restaurant list.

### BG.F.P001.002 — Featured Restaurants Show Skeleton Loading During First Paint
- **Gap:** Section shows spinner for 1-2s before content.
- **Impact:** Feels slow.
- **Scope:** Use Next.js ISR or SSR for initial restaurant data. Skeleton only used on client-side hydration.
- **AC:** First paint includes restaurant names (no spinner flicker).

### BG.F.P001.003 — No Location Permission Flow
- **Gap:** Homepage asks for city input but no location detection.
- **Impact:** User types manually.
- **Scope:** On load, call `navigator.geolocation.getCurrentPosition()`, reverse-geocode to city, update hero subtitle to "Delivering to {city}" and auto-navigate.
- **AC:** User sees auto-detected city within 2s of page load.

---

## BG.F.P002 — Restaurant Listing (/restaurants)

### BG.F.P002.001 — No Search Bar
- **Gap:** No real-time filtering.
- **Impact:** Users scroll through 96 unfiltered cards.
- **Scope:** Add sticky search input above grid. Debounce 200ms. Filter client-side by name + cuisine.
- **AC:** Typing "dosa" filters to 8 dosa restaurants instantly.

### BG.F.P002.002 — No Rating / Price / Delivery Time Filters
- **Gap:** No filter chips.
- **Impact:** No way to find top-rated or fast-delivery options.
- **Scope:** Add filter row: ⭐ 4+ ⏱️ <30min ₹₹ Price. Client-side filter.
- **AC:** Clicking "4+ ⭐" filters list to restaurants with rating >= 4.0.

### BG.F.P002.003 — No Cuisine Category Chips
- **Gap:** No "Indian / Chinese / Pizza / Burger" quick filters.
- **Impact:** Poor discovery.
- **Scope:** Horizontal scrollable chip list below search bar.
- **AC:** Clicking "Pizza" filters to cuisine containing "Pizza".

### BG.F.P002.004 — Restaurant Cards Use Generic Placeholder Images
- **Gap:** Picsum photos are random abstract images, not food.
- **Impact:** Looks like a cheap template, kills trust.
- **Scope:** Replace with category-specific Unsplash images or AI-generated food photos.
- **AC:** Pizza restaurant shows actual pizza photo.

### BG.F.P002.005 — No Infinite Scroll / Pagination UI
- **Gap:** Only shows 24 restaurants.
- **Impact:** Hidden restaurants unreachable.
- **Scope:** Add Intersection Observer triggered `fetchMore` loading more cards.
- **AC:** Scroll down → 24 more restaurants load seamlessly.

---

## BG.F.P003 — Restaurant Detail (/restaurants/[id])

### BG.F.P003.001 — Menu Completely Blank
- **Gap:** Menu API returns 500, page shows nothing.
- **Impact:** **CORE FLOW COMPLETELY BROKEN.** Cannot order.
- **Scope:** (1) Fix backend menu endpoint (see BG.B.S002.001). (2) Add error boundary showing "Menu temporarily unavailable. Please try again." with retry button. (3) Add skeleton loader for menu while loading.
- **AC:** Menu loads with items, prices, veg/non-veg indicators, Add button.

### BG.F.P003.002 — No Menu Category Tabs
- **Gap:** If menu loaded, all items in one flat list.
- **Impact:** Hard to navigate 15-30 items.
- **Scope:** Sticky tabs: Starters | Mains | Breads | Desserts | Combos. Scroll-to-section on click.
- **AC:** Clicking "Mains" scrolls to items in that category.

### BG.F.P003.003 — No "Veg Only" Toggle
- **Gap:** Indian market strongly prefers veg filtering.
- **Impact:** Vegetarians cannot easily find items.
- **Scope:** Add toggle switch next to category tabs. Client-side filter `is_veg = true`.
- **AC:** Toggle ON → only veg items shown.

### BG.F.P003.004 — No Item Customization Modal
- **Gap:** Cannot add extras (say " Extra Cheese" on pizza).
- **Impact:** Reduced cart value.
- **Scope:** Clicking menu item opens bottom sheet with price, description, add-ons, quantity stepper.
- **AC:** User can select "Extra Cheese +₹40" before adding to cart.

### BG.F.P003.005 — No Bestseller / Popular Tags
- **Gap:** No visual hierarchy on menu.
- **Impact:** User skips best items.
- **Scope:** Add "⭐ Bestseller" badge to top 3 items per category.
- **AC:** Top sellers visually flagged.

### BG.F.P003.006 — No Estimated Delivery Time Banner
- **Gap:** Restaurant detail doesn't show estimated time.
- **Impact:** User uncertainty.
- **Scope:** Add fixed banner: "Delivery in 35-45 min · ₹30 fee".
- **AC:** Time and fee visible without scrolling.

### BG.F.P003.007 — No Reviews Section
- **Gap:** Reviews table empty/unrendered.
- **Impact:** No social proof.
- **Scope:** Add "Reviews" tab with 5-star rating distribution, written reviews with user names + dates.
- **AC:** Visible reviews with photos and verified badges.

---

## BG.F.P004 — Cart (/cart)

### BG.F.P004.001 — Cart Requires Login (Redirects)
- **Gap:** Unauthenticated users cannot view cart.
- **Impact:** Guest users abandoned immediately.
- **Scope:** Store cart in `localStorage` or `zustand` + `persist`. Cart survives refresh, survives guest.
- **AC:** Add 3 items as guest → navigate to `/cart` → items visible.

### BG.F.P004.002 — No Coupon / Offer Input
- **Gap:** No promo code field.
- **Impact:** Cannot apply discounts.
- **Scope:** Add input field above total. Call `POST /api/v1/offers/validate` on blur.
- **AC:** Typing "WELCOME20" reduces total by 20%.

### BG.F.P004.003 — No Quantity Stepper
- **Gap:** Cannot change item quantity.
- **Impact:** Must remove + re-add.
- **Scope:** + / - buttons per item row. Local state + debounced sync.
- **AC:** Tapping + increases quantity, total recalculates.

---

## BG.F.P005 — Checkout (/checkout)

### BG.F.P005.001 — Form Submit Without Auth Fails
- **Gap:** Requires auth + items in cart.
- **Impact:** Broken if either condition violated.
- **Scope:** If guest, show inline login modal instead of redirect. If cart empty, show "Your cart is empty, browse restaurants" with CTA.
- **AC:** Guest checkout shows login form in modal.

### BG.F.P005.002 — No Saved Address Book
- **Gap:** Manual address entry every time.
- **Impact:** Friction.
- **Scope:** POST `/api/v1/addresses` during checkout. Show saved addresses as radio cards.
- **AC:** Second order shows "Use saved address".

### BG.F.P005.003 — No Payment Method Selection UI
- **Gap:** No card/UPI/wallet/cod options.
- **Impact:** User doesn't know how they'll pay.
- **Scope:** Radio group: 💳 Card / 📱 UPI / 👛 Wallet / 💵 Cash. Conditionally show UPI ID input or card form.
- **AC:** User selects UPI, enters UPI ID, places order.

### BG.F.P005.004 — No Order Summary Before Confirm
- **Gap:** No itemization before placing order.
- **Impact:** User uncertainty.
- **Scope:** Collapsible order summary above Place Order: item × qty = ₹total, subtotal, delivery fee, GST, discounts, grand total.
- **AC:** Total breakdown visible before confirming.

### BG.F.P005.005 — No "Place Order" Button Disabled State
- **Gap:** Button always active.
- **Impact:** User clicks, gets validation errors after submit.
- **Scope:** Disable button until address, payment method, and cart items are valid. Show inline validation.
- **AC:** Button disabled until all fields valid.

---

## BG.F.P006 — Order Tracking (/orders/[id])

### BG.F.P006.001 — No Order Status Timeline
- **Gap:** Status shown as plain text.
- **Impact:** No sense of progress.
- **Scope:** Vertical stepper: Confirmed → Preparing → Ready → Picked Up → Delivered. Current step highlighted. Completed steps green, upcoming gray.
- **AC:** Visual timeline with estimated times per step.

### BG.F.P006.002 — No Driver Tracking Map
- **Gap:** No real-time map.
- **Impact:** "Where is my food?" anxiety.
- **Scope:** Embed Mapbox/Leaflet (free for dev) with driver location marker. Poll `/api/v1/deliveries/{id}/location` every 10s.
- **AC:** Pin moves on map as driver approaches.

### BG.F.P006.003 — No Contact Driver / Restaurant Button
- **Gap:** No way to call driver or restaurant.
- **Impact:** User helpless on delays.
- **Scope:** Floating action buttons: "Call Driver" and "Chat Support".
- **AC:** Tapping "Call Driver" triggers `tel:` link.

---

## BG.F.P007 — Profile (/profile)

### BG.F.P007.001 — Profile Shows Nothing But Skeleton
- **Gap:** All profile data redirecting to login.
- **Impact:** User cannot manage account.
- **Scope:** Fix auth persistence. Display `full_name`, `email`, `phone`, `addresses`, `loyalty_points`.
- **AC:** Real data visible, editable fields with save.

### BG.F.P007.002 — No Saved Addresses Section
- **Gap:** No address management.
- **Scope:** CRUD addresses: Home, Work, Other with labels, map preview, default selection.
- **AC:** User can manage 3+ addresses.

### BG.F.P007.003 — No Order History
- **Gap:** /orders page redirects to login.
- **Scope:** List past orders with images, status, reorder button.
- **AC:** Shows order cards with status badges.

---

## BG.F.P008 — Wallet (/wallet)

### BG.F.P008.001 — Wallet Balance Not Shown
- **Gap:** Page redirects to login.
- **Scope:** Show balance prominently, transaction list (credit/debit), top-up button.
- **AC:** Shows ₹2,450.00 balance with 5 recent transactions.

---

## BG.F.C001 — Component Gaps

### BG.F.C001.001 — Missing Toast / Snackbar Component
- **Gap:** No ephemeral feedback.
- **Impact:** User doesn't know if action succeeded.
- **Scope:** Add `<Toast />` component. Triggers on add-to-cart, login error, order placed.
- **AC:** "Item added to cart" slides in bottom-right, auto-dismiss 3s.

### BG.F.C001.002 — Missing Loading Skeletons
- **Gap:** Blank pages during API fetch.
- **Impact:** Feels broken.
- **Scope:** Skeleton cards for restaurant list, skeleton rows for menu, skeleton text for profile.
- **AC:** No blank white screens during loading.

### BG.F.C001.003 — Missing Empty State Illustrations
- **Gap:** "No orders" shows blank white.
- **Impact:** User confusion.
- **Scope:** Custom SVG illustrations per empty state: sad pizza for empty cart, empty box for no orders.
- **AC:** Empty states have illustration + message + CTA.

### BG.F.C001.004 — Missing Bottom Navigation (Mobile)
- **Gap:** Mobile relies on hamburger menu.
- **Impact:** Thumb-unfriendly.
- **Scope:** Add mobile bottom nav: 🏠 Home / 🔍 Search / 🛒 Cart / 📋 Orders / 👤 Profile. Active tab highlighted.
- **AC:** Bottom nav visible on screen <640px.

### BG.F.C001.005 — Missing Bottom Sheet (Mobile Actions)
- **Gap:** Modals cover whole screen on mobile.
- **Impact:** Poor UX.
- **Scope:** Use Radix Dialog or custom bottom sheet for "Customize item", "Add address".
- **AC:** Bottom sheet slides up from bottom 70% of screen.

### BG.F.C001.006 — No Offline Indicator
- **Gap:** No visual cue when network is down.
- **Impact:** User clicks, nothing happens, blames app.
- **Scope:** Add top banner: "You are offline. Some features unavailable." using `navigator.onLine`.
- **AC:** Banner appears when `onLine` is false.

---

## BG.F.U001 — UI/UX Interaction Gaps

### BG.F.U001.001 — No Page Transitions
- **Gap:** Instant hard navigation between pages.
- **Impact:** Feels jarring.
- **Scope:** Use Next.js `<AnimatePresence>` or Framer Motion for page fade/slide transitions.
- **AC:** Navigating from /restaurants to /restaurants/123 slides content right.

### BG.F.U001.002 — No Add-to-Cart Animation
- **Gap:** Click "Add" → nothing visual happens.
- **Impact:** Uncertainty if action registered.
- **Scope:** Micro-animation: item image flies to cart icon + cart badge wobble. 300ms.
- **AC:** Visual fly animation on every add.

### BG.F.U001.003 — No Pull-to-Refresh
- **Gap:** On mobile, user cannot refresh.
- **Impact:** Stale data.
- **Scope:** Pull-down gesture reloads data.
- **AC:** Pull down lists on mobile triggers refresh.

### BG.F.U001.004 — No Pull-to-Refresh on Mobile Restaurant List
- **Gap:** Stale data.
- **Scope:** Implement touch pull-to-refresh.

### BG.F.U001.005 — TV / Large Screen Layout Missing
- **Gap:** Restaurant grid on 4K TV shows 1-column narrow strips.
- **Impact:** Unusable.
- **Scope:** Add breakpoints: `2xl:grid-cols-5 3xl:grid-cols-6`. Max content width 1920px centered.
- **AC:** 4K TV shows 6 restaurant cards per row with proper spacing.

### BG.F.U001.006 — Tablet Layout Inefficient
- **Gap:** iPad Pro shows 2-column grid with giant whitespace.
- **Impact:** Wastes screen.
- **Scope:** `md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`.
- **AC:** iPad lands in 3-column layout.

### BG.F.U001.007 — No Dark Mode Toggle
- **Gap:** Dark classes exist but no toggle.
- **Impact:** Night usage irritating.
- **Scope:** Add sun/moon toggle in navbar. Store preference in localStorage. Respect `prefers-color-scheme`.
- **AC:** Toggle switches all dark: classes.

### BG.F.U001.008 — Typography is Generic System Font
- **Gap:** Uses default `font-sans`.
- **Impact:** Looks like every other website.
- **Scope:** Import Inter, Manrope, or Poppins from Google Fonts. Apply to headings and body.
- **AC:** Distinctive font family visible.

---

# Part 3 — Micro-Level Gaps (Category: BG.I = Integration / Flow)

### BG.I001 — Onboarding Flow Broken
- **Gap:** Signup page not tested. No onboarding tutorial.
- **Impact:** New users confused.
- **Scope:** Add 3-step onboarding after signup: (1) Set location, (2) Choose cuisines, (3) Browse restaurants. Entire flow takes <60 seconds.
- **AC:** New user lands on homepage with personalized cuisine recommendation.

### BG.I002 — Favorites Not Implemented
- **Gap:** No heart icon on restaurant cards.
- **Impact:** No "reorder from my favorite" flow.
- **Scope:** Heart toggle on card. POST `/api/v1/favorites` on toggle. "Favorites" row on homepage.
- **AC:** Tapping heart persistently bookmarks restaurant.

### BG.I003 — Reorder Flow Missing
- **Gap:** Cannot reorder previous meal.
- **Impact:** Friction for repeat customers.
- **Scope:** "Reorder" button on order history card. Pre-fills cart with same items.
- **AC:** One-tap reorder from /orders page.

### BG.I004 — Location / Address Handling Crude
- **Gap:** No autocomplete, no map pin selection.
- **Impact:** Address typos, delivery failures.
- **Scope:** Integrate Google Places Autocomplete (dev key free) or OpenStreetMap Nominatim. Show map in address modal.
- **AC:** Typing "MG Road" suggests "MG Road, Bengaluru, Karnataka".

### BG.I005 — Availability / Open-Closed Logic Missing
- **Gap:** Restaurants shown even if closed.
- **Impact:** User places order that cannot be fulfilled.
- **Scope:** Compare `opens_at` / `closes_at` with current time. Dim closed restaurants, show "Opens at 8 AM" badge.
- **AC:** Closed restaurants visually distinguished.

### BG.I006 — Cancellation / Refund Flow Not Integrated
- **Gap:** No UI or API for cancel.
- **Impact:** User stuck with wrong order.
- **Scope:** "Cancel Order" button inside order detail if status in [pending, confirmed]. Show refund status.
- **AC:** Cancelled order moves to "Refunded" state, wallet credited.

### BG.I007 — Order State Machine Not Enforced
- **Gap:** Any status can transition to any status.
- **Impact:** `delivered` → `pending` is possible.
- **Scope:** State machine: `pending → confirmed → preparing → ready_for_pickup → picked_up → delivered`. `cancelled` from `pending` or `confirmed` only. Validate transitions server-side.
- **AC:** Invalid transition returns 400.

### BG.I008 — Fees / Taxes / Delivery Charges Not Transparent
- **Gap:** Checkout breakdown missing line items.
- **Impact:** User distrust.
- **Scope:** Always show: Items total, Delivery Fee, Platform Fee, GST (18% / 8%), Discount, Grand Total.
- **AC:** Fee calculator visible in both cart and checkout.

### BG.I009 — Restaurant Prep-Time Logic Missing
- **Gap:** All restaurants show static 35-45 min.
- **Impact:** Incorrect ETAs.
- **Scope:** Use `avg_prep_minutes` from DB + real-time order queue size. Formula: `prep_time = avg_prep_minutes + (queue_size × 5 min)`.
- **AC:** Busy restaurant shows 60 min, quiet one shows 25 min.

### BG.I010 — Serviceability / Radius Logic Not Enforced
- **Gap:** Any address accepted regardless of distance.
- **Impact:** Undeliverable orders.
- **Scope:** Haversine check on checkout. If distance > restaurant.delivery_radius_km, show "Does not deliver to this address." with nearest suggestions.
- **AC:** Impossible address blocked before payment.

---

# Part 4 — Micro-Level Gaps (Category: BG.N = Novelty / Differentiator)

### BG.N001 — AI Smart Meal Suggestions
- **Gap:** No personalized recommendations.
- **Impact:** Generic experience.
- **Scope:** Based on order history, time of day, weather API. Show "Good evening! How about Paneer Tikka?" peeked card.
- **AC:** Homepage shows 3 personalized suggestions.

### BG.N002 — Nutritional Transparency Panel
- **Gap:** No calories / macros / allergens on menu.
- **Impact:** Health-conscious users cannot decide.
- **Scope:** Add `calories`, `protein_g`, `carbs_g`, `fat_g`, `allergens[]` to `menu_items`. Render collapsible nutrition panel on item card.
- **AC:** User can expand "Nutrition Info" on any dish.

### BG.N003 — Community Kitchen / Home Chef Section
- **Gap:** Only commercial restaurants.
- **Impact:** Misses home-cooked meal trend.
- **Scope:** Add `restaurant_type: commercial | home_chef`. Separate section: "Home Chefs Near You."
- **AC:** Dedicated section with home-style food.

### BG.N004 — Zero-Waste Meal Rescue (End-of-Day)
- **Gap:** Unsold food discarded.
- **Impact:** Waste and lost revenue.
- **Scope:** 1 hour before closing, automatically push "Rescue Meal — 50% off" for remaining inventory.
- **AC:** Push notification: "Domino's has 3 unsold pizzas at 50% off."

### BG.N005 — Group / Office Ordering
- **Gap:** Individual orders only.
- **Impact:** Office lunch logistics painful.
- **Scope:** "Start Group Order" → generates shareable link → colleagues add items → one person pays → split bill.
- **AC:** 4 people add items to shared cart, one checkout.

### BG.N006 — Smart Locker / Pickup Point Network
- **Gap:** Only home delivery.
- **Impact:** Misses users who prefer no-contact pickup.
- **Scope:** "Pickup at Smart Locker" option. Generate QR code. Locker unlocks on scan.
- **AC:** User selects locker location, gets QR, retrieves meal.

### BG.N007 — AI Voice Ordering
- **Gap:** Typing-heavy.
- **Impact:** Accessibility, driving users.
- **Scope:** Mic button triggers Web Speech API. Parses "Order 2 Paneer Tikka and 1 Naan from Spice Garden."
- **AC:** Voice command adds items directly to cart.

### BG.N008 — Loyalty & Gamification
- **Gap:** `loyalty_points` stored but unused.
- **Impact:** No retention.
- **Scope:** Points = 10% of order value. "Level up" badges. Rewards dashboard.
- **AC:** User sees "Gold Member · 2,450 pts · Free delivery eligible."

### BG.N009 — Dynamic Surge-Demand Pricing (Transparent)
- **Gap:** Static delivery fees.
- **Impact:** Not optimizing capacity.
- **Scope:** Multiply delivery fee by 1.2x during rain / peak hours. Show badge: "Rainy day — ₹10 extra for rider safety." User sees why.
- **AC:** Transparent dynamic pricing.

### BG.N010 — Sustainability Score (Green Badge)
- **Gap:** No eco-messaging.
- **Impact:** Miss conscious consumers.
- **Scope:** Restaurants with biodegradable packaging get 🌿 badge. Filters for "Eco-friendly."
- **AC:** 12 restaurants show green leaf badge.

---

# Part 5 — Micro-Level Gaps (Category: BG.X = Cross-Cutting)

### BG.X001 — Accessibility (a11y) Gaps
- **Gap:** No keyboard nav, no ARIA labels on cart button, no focus trapping in modals.
- **Evidence:** Playwright tests rely on text selectors, not roles.
- **Scope:** Add `role`, `aria-label`, `aria-expanded` to all interactive elements. Test with aXe (`@axe-core/playwright`).
- **AC:** axe-core returns 0 critical violations.

### BG.X002 — Performance: No Image Optimization
- **Gap:** 800×600 hero images served as-is.
- **Impact:** 2MB+ page weight.
- **Scope:** Use Next.js `<Image>` with `sizes` prop. Serve WebP from S3.
- **AC:** Lighthouse Performance score > 70.

### BG.X003 — Security: SQL Injection Risk in Search
- **Gap:** Search params passed raw to SQL.
- **Evidence:** Not explicitly parameterized in all endpoints.
- **Scope:** Use SQLAlchemy parameterized queries exclusively. No f-string SQL.
- **AC:** SQLMap scan returns no injection vectors.

### BG.X004 — Reliability: No Retry Logic
- **Gap:** Network blip = failed order.
- **Scope:** Client-side retry using `tanstack-query` with `retry: 3`. Server-side idempotency keys for payments.
- **AC:** Brief 5s outage does not destroy order.

### BG.X005 — Observability: No Request Tracing
- **Gap:** Cannot trace request across 4 services.
- **Scope:** Inject `X-Request-ID` header. Log correlation ID in every service. View in Jaeger or Zipkin.
- **AC:** Single ID traces path: frontend → order-svc → payment-svc → notification-svc.

### BG.X006 — Seed Data: No Reviews
- **Gap:** 0 reviews seeded.
- **Impact:** Blank reviews section.
- **Scope:** Generate 3-5 reviews per restaurant with realistic text, star variance.
- **AC:** Every restaurant shows >=3 reviews.

---

# Production Readiness Roadmaps

## Tier 1: 1 → 4 (Unblock the Core Loop)
> Goal: Make the app demo-able. Fix the 1/10 blockers.

| ID | Fix | Why |
|----|-----|-----|
| B-1 | Backend menu endpoint 500 → add DB fallback | Without menu, user cannot order |
| A-1 | Frontend auth persistence → cookies | Without auth, no cart/orders/profile |
| C-1 | Add `GET /api/v1/me` | Frontend needs user data |
| G-1 | Fix batch migration ordering | Prevents crash on fresh boot |
| A-2 | Error boundary on restaurant detail | User sees friendly error, not blank page |
| D-1 | Fix order creation test + validate endpoint | Core transaction must work |
| A-3 | Offline local cart (localStorage) | Guest users can browse and add |
| B-2 | OpenSearch graceful degradation | No longer a hard dependency |
| A-4 | Playwright screenshot capture fix | Evidence of e2e test quality |
| B-3 | Category-specific real images | Replace Picsum with real food photos |
| I-7 | Order state machine enforcement | Prevent invalid statuses |
| I-8 | Checkout fee breakdown UI | Trust through transparency |
| D-3 | Order cancellation API + UI | Basic user right |
| E-2 | Payment webhook (Razorpay) | Close payment loop |
| B-4 | Search endpoint + UI filter | Discovery is core to marketplace |
| B-5 | Cuisine chips + best seller tags | Menu must be scannable |

**Expected Improvement:** Core loop works end-to-end. App becomes internally demo-able. Score: **1 → 4**

---

## Tier 2: 4 → 6 (Functional Marketplace)
> Goal: Complete feature set for a closed beta.

| ID | Fix |
|----|-----|
| C-3 | Password reset flow |
| A-5 | Homepage search + location auto-detect |
| B-4 | Rating / time / price filters |
| I-4 | Address autocomplete (Places API) |
| I-5 | Open/closed logic + badge |
| I-9 | Real prep-time calculation |
| I-10 | Serviceability radius check |
| F-1 | Driver assignment + pooling |
| F-2 | Real-time driver location |
| F-3 | ETA calculation |
| D-4 | Order timeline / tracking |
| D-2 | Restaurant order notification (SSE) |
| E-3 | Stripe webhook |
| H-1 | Push notification delivery (FCM) |
| D-3 | Order cancellation + refund |
| J-1 | Docker per service |
| J-2 | docker-compose.yml for full stack |
| I-6 | Cancel flow UI + refund status |
| A-6 | Skeleton loaders + empty states |
| N-3 | Community kitchen section |

**Expected Improvement:** Feature-complete marketplace. Users can search, order, track, cancel. Beta-ready. Score: **4 → 6**

---

## Tier 3: 6 → 8 (Production Stability)
> Goal: System is observable, scalable, and polished.

| ID | Fix |
|----|-----|
| J-3 | GitHub Actions CI/CD |
| J-4 | Prometheus + Grafana monitoring |
| J-5 | Centralized logging (Loki) |
| X-5 | Distributed tracing (Jaeger) |
| X-3 | Security audit + SQL injection hardening |
| I-1 | Comprehensive test unskip (reduce to <10%) |
| N-2 | Nutritional transparency panel |
| N-5 | Group office ordering |
| N-6 | Smart locker pickup option |
| K-1 | Dark mode toggle |
| K-2 | Mobile bottom navigation |
| N-8 | Loyalty & gamification dashboard |
| U-8 | Inter font + design system upgrade |
| U-5 | TV / 4K responsive layout |
| B-6 | Status enforcement (hide pending restaurants) |
| X-2 | Image optimization (Next.js Image + WebP) |
| X-4 | Client + server retry logic |

**Expected Improvement:** System observability, design polish, novel differentiators. Launchable to early users. Score: **6 → 8**

---

## Tier 4: 8 → 10 (Enterprise Scale)
> Goal: Resilient, delightful, competitive product.

| ID | Fix |
|----|-----|
| J-6 | SSL / HTTPS |
| J-7 | CDN for images |
| B-7 | Admin dashboard with analytics |
| N-1 | AI meal suggestions |
| N-7 | Voice ordering (Web Speech API) |
| N-4 | Zero-waste meal rescue (end-of-day promos) |
| N-9 | Transparent surge pricing |
| N-10 | Sustainability score |
| C-4 | Social login (Google OAuth) |
| H-3 | Email notifications (SendGrid) |
| X-1 | Full a11y compliance (axe-core 0 violations) |
| I-2 | Favorites + reorder |
| I-3 | Reorder from history |
| H-2 | Push notification delivery (FCM iOS/Android) |
| U-9 | Animation system (page transitions, add-to-cart) |
| B-8 | Advanced search filters |

**Expected Improvement:** Polished, unique, enterprise-ready platform. Competitive with top delivery apps. Score: **8 → 10**

---

# Novelty / Uniqueness Roadmaps

## Novelty Tier 1: 1 → 4 (Quick Differentiators)
| ID | Idea |
|----|------|
| N-2 | Nutritional transparency (calories, macros) |
| N-8 | Loyalty points activation (already stored) |
| N-3 | Community kitchen / home chef section |
| N-10 | Sustainability score badge |
| N-9 | Transparent dynamic surge pricing |

## Novelty Tier 2: 4 → 6 (Integrated Features)
| ID | Idea |
|----|------|
| N-5 | Group / office ordering with split bill |
| N-6 | Smart locker / pickup point network |
| N-7 | Voice ordering |
| N-4 | Zero-waste meal rescue (end-of-day) |
| N-1 | AI meal suggestions based on previous orders |

## Novelty Tier 3: 6 → 8 (AI & Personalization)
| ID | Idea |
|----|------|
| N-1 | AI smart recommendation engine + time/weather |
| N-7 | Voice ordering NLP (parse natural language) |
| N-5 | Group ordering real-time collaboration |
| N-4 | Automated zero-waste flash sales at 9 PM |

## Novelty Tier 4: 8 → 10 (Full Ecosystem)
| ID | Idea |
|----|------|
| N-6 | Nationwide smart locker mesh (IoT integration) |
| N-1 | Predictive health-based meal planning |
| N-5 | Corporate meal program with invoicing |
| N-9 | Blockchain-verified carbon-neutral delivery |

---

**Final Verdict:** This audit contains **~110 actionable items** across backend, frontend, integration, novelty, and cross-cutting concerns. Every item has been mapped to a module, assigned impact, and placed in a sprint roadmap. Execution should begin with **Tier 1 Unblock** immediately.
