# IP.PR.05 — Usable Closed Demo

## 1. Target Score Level: 5/10

## 2. Score Meaning

Core loop is stable, key empty/loading/error states exist, seed data looks real, and basic profile/order history works. App is usable for a small closed demo with ~5-10 users.

## 3. Current → Target Transition

**From PR.04 (reliable demo core loop with P0 items working and P1 polish items incomplete):**
- The core ordering loop is fully traversable: browse → menu → cart → checkout → confirmation → tracking.
- Design system is applied across all pages: BhojanGo palette, Manrope + Inter fonts, consistent spacing, Lucide icons.
- Indian food delivery UI specifics are visible: veg/non-veg dots, Jain tags, spice levels, thali/combo builder, ₹ pricing.
- Loading skeletons, error boundaries, empty states, and toast notifications are present on all screens.
- Responsive layout works on mobile (bottom nav), tablet, laptop, and TV breakpoints.
- Dark mode toggle works and persists across sessions.
- Review data is seeded and visible on restaurant detail pages.

**However, PR.04 is still "demo-safe but thin":**
- Password reset flow is missing entirely; users cannot recover forgotten passwords.
- Address CRUD is incomplete: users can create/view addresses but cannot edit or delete them; no default address setting.
- Favorites are absent: no heart toggle on restaurant cards, no favorites section on homepage, no favorites list page.
- Reorder is only a placeholder button; it does not pre-fill the cart with previous items.
- Coupons are hardcoded mock-only; no configurable offer system, no coupon input in cart.
- Open/closed logic is not enforced: closed restaurants are shown with full interactivity, risking failed orders.
- Prep-time is static: every restaurant shows 30-40 min regardless of actual queue size or `avg_prep_minutes`.
- Serviceability radius is not enforced: users can enter addresses far beyond delivery range at checkout.
- Seed data is sparse: only 3-5 reviews per restaurant, generic user names, limited order history for demo users.
- Guest checkout lacks tracking: a guest user who places an order has no way to look it up after leaving the confirmation page.
- Search is client-side only: no backend search endpoint with ILIKE for large datasets.
- Wallet balance may be unreliable on profile page (P1 item from PR.04, not fully stabilized).
- TV responsive layout and thali/combo builder UI were P1 items deferred from PR.04.

**Target at score 5:**
- Every P1 item deferred from PR.04 is completed: location auto-detection finalized, TV responsive layout verified, thali/combo builder UI fully functional, review seed data enriched, wallet balance reliably displayed.
- Reorder flow works: user taps "Reorder" on any past order and the cart is pre-filled with the exact same items (quantities, customizations, restaurant).
- Favorites system works: heart toggle on every restaurant card, "Your Favorites" row on homepage, dedicated `/favorites` page listing bookmarked restaurants.
- Basic offers/coupons: at least one mock coupon ("WELCOME20" = 20% off) is validated server-side or client-side with real calculation, coupon input field in cart, discount shown in fee breakdown.
- Open/closed logic enforced: closed restaurants are visually dimmed, show "Opens at 8 AM" badge, and cannot be ordered from. Active restaurants show "Open" badge.
- Dynamic prep-time calculation: ETA = `avg_prep_minutes` + (estimated queue size × 5 min), shown on restaurant cards and detail page.
- Serviceability radius enforced: Haversine distance check at checkout; if address is beyond `restaurant.delivery_radius_km`, show "Does not deliver to this address" with nearest suggestions.
- Password reset flow complete: "Forgot password?" link → email/OTP → reset token → new password → auto-login.
- Address CRUD complete: create, edit, delete, and set default address. Saved addresses shown as radio cards in checkout.
- Order cancellation with simulated refund: cancel button visible on pending/confirmed orders; upon cancellation, wallet credited back (if wallet payment) or COD marked as cancelled; toast confirms.
- Enhanced seed data: 8-10 realistic reviews per restaurant with varied ratings and authentic text; real food images (deterministic Unsplash URLs); 10-15 varied orders per demo user with realistic statuses; wallet transactions seeded.
- Guest order tracking: guest user can enter order number + phone OTP (mock) on a `/track-order` page to see order status and timeline.
- Backend search endpoint: `GET /api/v1/restaurants/search?q={query}` with ILIKE on `name` and `cuisine_types`, returning paginated results.
- App is stable enough for 5-10 real users to place orders concurrently without breaking the core loop.

## 4. Implementation Objective

Stabilize the core loop completely so it never breaks under normal usage. Complete all profile, history, search, and data polish. Add reorder, favorites, basic offers, and operational basics (open/closed, prep-time, radius). Make seed data rich and believable. No new infrastructure.

## 5. Scope (local/demo-safe only)

### In Scope

1. **PR.04 P1 completion** — Location auto-detection on homepage finalized (geolocation API + mock reverse-geocode). TV responsive layout verified (2xl: 5-col, 3xl: 6-col). Thali/combo builder UI fully functional for combo items. Review seed data enriched to 8-10 realistic reviews per restaurant. Wallet balance on profile page reliably displayed (fallback to hidden if endpoint fails).
2. **Functional reorder** — "Reorder" button on order history cards pre-fills cart with exact previous items, quantities, and customizations. Cross-restaurant cart guard triggers if reorder items differ from current cart restaurant. Toast confirms reorder. Navigate to `/cart` after pre-fill.
3. **Functional favorites** — Heart toggle on every restaurant card (filled/empty state). POST `/api/v1/favorites` on toggle. "Your Favorites" horizontal scroll row on homepage. Dedicated `/favorites` page listing all bookmarked restaurants with remove option. Favorites persisted in database.
4. **Basic offers/coupons** — Mock coupon validation: "WELCOME20" applies 20% discount (max ₹100), "BH

OJAN50" applies 50% off first order (max ₹150). Coupon input field in cart with validate button. Valid coupon updates fee breakdown with discount line. Invalid coupon shows red error text. Coupon system is client-side validation + server-side mock for demo.
5. **Open/closed logic** — Compare `opens_at` / `closes_at` with current time (server-side calculated field `is_open` or client-side based on seeded hours). Closed restaurants dimmed to 60% opacity, "Opens at {time}" badge shown, menu and "Order" button disabled. Open restaurants show green "Open" badge with estimated closing time.
6. **Restaurant prep-time** — Dynamic ETA based on `avg_prep_minutes` + estimated queue size (number of pending/confirmed orders for that restaurant × 5 min). Displayed on restaurant card as "{min}-{max} min" and on detail page banner. Queue size updated every 30s or on page refresh.
7. **Serviceability radius** — Haversine distance calculation between user address lat/lng and restaurant lat/lng at checkout. If distance > `restaurant.delivery_radius_km`, show red banner: "This restaurant does not deliver to your address." Suggest 3 nearest restaurants that do deliver. Block "Place Order" until valid address selected.
8. **Password reset flow** — "Forgot password?" on login page → enter email → mock OTP sent (display OTP in toast for demo) → enter OTP → set new password → auto-login. Backend: `POST /api/v1/auth/forgot-password` generates token, `POST /api/v1/auth/reset-password` validates token and updates hash.
9. **Address CRUD** — Full address management in profile and checkout: create new address (label: Home/Work/Other, street, city, pincode, phone, landmark), edit existing address, delete address with confirmation, set default address (radio selection). Saved addresses shown as radio cards in checkout with edit/delete dropdown. Default address pre-selected.
10. **Order cancellation + refund simulation** — Cancel button visible on order detail if status is `pending` or `confirmed`. Confirmation modal: "Are you sure? Your refund will be processed within 24 hours." On confirm: PATCH `/api/v1/orders/{id}/cancel` with reason. If payment was wallet, simulate refund by adding credit to wallet balance (or showing as "Refund pending"). If COD, simply mark cancelled. Toast: "Order cancelled. Refund of ₹{amount} will be credited to your wallet." Order status updates to `cancelled`, timeline hidden, cancellation banner shown.
11. **Enhanced seed data** — 8-10 realistic reviews per restaurant with varied star ratings (2-5), authentic Indian food review text, realistic reviewer names, dates within last 6 months. Unsplash food images deterministically mapped by cuisine type. 10-15 varied orders per demo user with statuses spanning the full lifecycle. 5-8 wallet transactions per user (top-ups, order debits, refunds). More realistic restaurant descriptions and cuisine tags.
12. **Guest checkout improvements** — Guest user who places an order can track it via order number + phone OTP (mock). New `/track-order` page with input fields. Mock OTP displayed in toast for demo. Shows order status, timeline, and restaurant contact. No login required.
13. **Backend search endpoint** — `GET /api/v1/restaurants/search?q={query}&page={page}&limit={limit}` with ILIKE on `name` and `cuisine_types` (case-insensitive). Returns paginated results with same fields as list endpoint. Integrated into frontend search bar with debounce. Falls back to client-side filter if endpoint unavailable.

### Out of Scope

- Restaurant owner dashboard (PR.06).
- Delivery partner dashboard (PR.06).
- Super admin dashboard (PR.06).
- Real payment gateway webhooks (Stripe/Razorpay integration is simulated).
- Push/SMS/email notifications (templates exist but dispatch infrastructure is deferred).
- CDN / S3 image hosting (Unsplash URLs used for demo).
- Group ordering (novelty — deferred to PR.07+).
- Loyalty points activation (novelty — deferred to PR.07+).
- Meal rescue / end-of-day deals (novelty — deferred to PR.07+).
- Real-time driver tracking with map (map integration deferred to PR.06+).
- Observatory / monitoring stack (Prometheus/Grafana exist but dashboard polish deferred).

## 6. Out of Scope (Summary)

- Restaurant owner, delivery partner, and super admin dashboards (PR.06+).
- Real payment gateway webhooks, real-time driver tracking with map.
- Push/SMS/email notification dispatch ( templates exist but not wired end-to-end ).
- CDN / S3 image hosting, CI/CD improvements, E2E tests.
- Group ordering, loyalty points activation, meal rescue, advanced AI personalization.
- Multi-region deployment, WAF, Terraform state locking.

## 7. Required Capabilities

- Core loop is stable under normal usage: no blank screens, no crashes on standard paths.
- Password reset flow works end-to-end without manual database intervention.
- Address CRUD is fully functional: create, edit, delete, set default, all persisted to DB.
- Reorder pre-fills cart with exact previous order contents, respecting cross-restaurant guard.
- Favorites heart toggle persists to DB; favorites section on homepage and dedicated page work.
- Coupon "WELCOME20" applies 20% discount correctly in cart and checkout fee breakdown.
- Open/closed logic dims closed restaurants and blocks ordering from them.
- Prep-time calculation uses `avg_prep_minutes` + queue estimate and updates dynamically.
- Serviceability radius blocks checkout with out-of-range addresses and suggests alternatives.
- Order cancellation with refund simulation credits wallet and shows confirmation.
- Enhanced seed data makes the app look populated and realistic for demo users.
- Guest order tracking by order number + mock OTP allows non-logged-in users to check status.
- Backend search endpoint with ILIKE returns relevant results for restaurant name and cuisine queries.
- All P1 items from PR.04 (location auto-detection, TV layout, thali builder, review seed, wallet) are completed.

## 8. Key User Journeys

### Journey 8.1 — New User Onboarding + First Order
1. User opens app, sees dark-mode-aware homepage with "Delivering to {city}" auto-detected.
2. User taps "Find Food" → `/restaurants` with infinite scroll, real Unsplash food images, trust badges.
3. User sees open restaurants with green "Open" badges, closed ones dimmed with "Opens at 8 AM".
4. User searches "biryani" via backend search endpoint → results filter in <300ms.
5. User taps a restaurant card. Detail page shows dynamic ETA "35-40 min" based on prep-time calc.
6. User toggles "Veg Only" → sees items with green dots, Jain "J" pills, chili spice icons.
7. User taps heart on restaurant → "Added to favorites" toast. Homepage now shows this restaurant in "Your Favorites".
8. User adds Paneer Tikka with Extra Cheese +₹40 via customization modal.
9. User navigates to `/cart`, enters "WELCOME20" → 20% discount applied, fee breakdown updates.
10. User enters address. Checkout runs Haversine check → address is within radius → "Place Order" active.
11. User selects UPI (mock), taps Place Order. Confirmation page shows order number, dynamic ETA.
12. User taps "Track Order" → static timeline shows Confirmed (active), Preparing, Ready, Picked Up, Delivered.

### Journey 8.2 — Returning User Reorders from History
1. User logs in, auth persists, navbar shows name and avatar.
2. User navigates to `/orders`, sees 10-15 past orders with realistic status badges and dates.
3. User taps "Reorder" on a past biryani order. Toast: "Cart pre-filled with your previous order."
4. Cart shows exact same items, quantities, customizations. Cross-restaurant guard not triggered (same restaurant).
5. User proceeds to checkout, saved "Home" address pre-selected. Places order. Confirmation shown.

### Journey 8.3 — Password Reset + Address Management
1. User taps "Forgot password?" on login. Enters email. Mock OTP shown in toast: "Your OTP is 123456."
2. User enters OTP, sets new password, auto-logged in.
3. User goes to `/profile` → "Manage Addresses" → adds new "Work" address with landmark.
4. User edits existing "Home" address, updates pincode. Sets "Work" as default.
5. User deletes old address with confirmation modal. Toast: "Address deleted."
6. User checks out → "Work" address pre-selected as default.

### Journey 8.4 — Order Cancellation + Refund
1. User places order with Wallet payment. Status: `confirmed`.
2. User navigates to `/orders/[id]`. Timeline shows Confirmed (active), Preparing pending.
3. User taps "Cancel Order". Modal: "Are you sure? Refund of ₹450 will be credited to your wallet within 24h."
4. User confirms. Order status updates to `cancelled`. Timeline hidden. Cancellation banner shown with refund amount.
5. User checks `/wallet` → sees "Refund - ₹450" transaction with pending status.

### Journey 8.5 — Guest Order Tracking
1. Guest user places order with COD. Gets order number "BG-20240614-7392" and phone number on confirmation.
2. Guest returns later (no login), navigates to `/track-order`.
3. Guest enters order number and phone number. Mock OTP shown in toast: "123456".
4. Guest enters OTP. Sees order status (`preparing`), timeline, and restaurant contact.
5. Guest cannot see order history or profile — only this single order's status.

### Journey 8.6 — Serviceability + Open/Closed Enforcement
1. User browses restaurant list at 11 PM. Several restaurants show "Opens at 8 AM" and are dimmed.
2. User taps a dimmed restaurant → menu visible but "Order" button disabled. Banner: "Restaurant is closed. Opens at 8:00 AM."
3. User finds an open restaurant, proceeds to checkout, enters address in a different city.
4. Haversine check fails: "This restaurant does not deliver to your address." Suggests 3 nearest alternatives.
5. User selects suggested restaurant, address now valid, checkout proceeds.

### Journey 8.7 — Favorites Discovery
1. User browses restaurant list, taps heart on 3 restaurants.
2. User navigates to `/favorites` → sees all 3 restaurants with remove (X) buttons.
3. User removes one restaurant. Toast: "Removed from favorites."
4. User returns to homepage → "Your Favorites" row shows remaining 2 restaurants.
5. User taps a favorite restaurant → detail page opens, heart is filled.

## 9. Technical Coverage

### Backend
- `user-svc`: `POST /api/v1/auth/forgot-password` (generate reset token), `POST /api/v1/auth/reset-password` (validate + update). Address CRUD: `PUT /api/v1/addresses/{id}`, `DELETE /api/v1/addresses/{id}`, `PATCH /api/v1/addresses/{id}/set-default`.
- `restaurant-svc`: `GET /api/v1/restaurants/search?q=&page=&limit=` with ILIKE on `name` and `cuisine_types`. `opens_at`/`closes_at` fields returned in list/detail. `avg_prep_minutes` and `delivery_radius_km` included in response. `is_open` flag calculated server-side or hours serialized for client calculation.
- `restaurant-svc` or `user-svc`: `POST /api/v1/favorites`, `DELETE /api/v1/favorites/{restaurant_id}`, `GET /api/v1/favorites`.
- `order-svc`: `PATCH /api/v1/orders/{id}/cancel` with `reason` body. Cancellation triggers simulated refund: if `payment_method = 'wallet'`, create wallet credit transaction (or mock it). `GET /api/v1/orders/{id}/track` for guest tracking (order number + phone hash match).
- `order-svc`: Server-side calculation of queue size per restaurant (count of `pending` + `confirmed` orders) for prep-time estimation.
- `restaurant-svc`: Haversine helper function for distance check between lat/lng pairs (reuse existing geo utility if available).

### Frontend
- Next.js App Router pages: `/favorites`, `/track-order`, `/profile/addresses`.
- Favorites: heart toggle component, Zustand `favoritesStore`, optimistic UI updates.
- Reorder: `POST /api/v1/orders/{id}/reorder` or client-side cart pre-fill from order detail data.
- Coupon: coupon input component with validate button, fee breakdown recalculation, error state.
- Open/closed: `isOpen()` helper using current time + `opens_at`/`closes_at` + timezone. Visual dimming via opacity CSS.
- Prep-time: `calculateETA(avgPrepMinutes, queueSize)` helper. Displayed as "{min}-{max} min" range.
- Serviceability: `calculateDistance()` Haversine formula in client or API call. Checkout validation before enabling Place Order.
- Password reset: 3-step form (email → OTP → new password) with validation and error states.
- Address CRUD: modal forms for create/edit, confirmation modal for delete, radio card selection in checkout.
- Guest tracking: `/track-order` page with order number + phone + OTP input. Mock OTP displayed via toast.
- Search: backend search endpoint with debounced query, loading skeleton, empty state for no results.
- Enhanced seed data: deterministic Unsplash URLs by cuisine type, realistic Indian review text templates, order statuses spanning lifecycle, wallet transaction types.

### Data
- Reuses existing tables: `users`, `restaurants`, `menu_categories`, `menu_items`, `orders`, `order_status_history`, `addresses`, `wallet`, `reviews`.
- New table: `favorites` (`user_id`, `restaurant_id`, `created_at`, unique constraint on user+restaurant composite).
- New/extended columns: `restaurants.opens_at`, `restaurants.closes_at`, `restaurants.avg_prep_minutes`, `restaurants.delivery_radius_km` (verify existing or add via migration).
- Seed data extensions: 8-10 reviews per restaurant, 10-15 orders per demo user, 5-8 wallet transactions per user, order cancellation records in `order_status_history`.
- No new infrastructure services or external dependencies.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for `/favorites`, skeleton form for `/track-order`. Existing skeleton patterns from PR.04 reused.
- **Error states:** Error boundaries on `/favorites`, `/track-order`, `/profile/addresses`. API failure toasts with actionable retry messages.
- **Empty states:** Empty favorites page with custom illustration (empty heart SVG), "Browse Restaurants" CTA. Empty search results with "Try a different term" message.
- **Success states:** Toast on add-to-favorites, remove-from-favorites, reorder, coupon applied, password reset complete, address saved, order cancelled.
- **Design system:** All new pages (`/favorites`, `/track-order`, password reset flow, address CRUD modals) follow BhojanGo palette, Manrope + Inter typography, 4px grid, Lucide icons, badge/card anatomy standards from IP.PR.04.011.
- **Indian food specifics:** Veg/non-veg dots, Jain tags, spice chilies, ₹ pricing continue on all relevant pages. Reorder respects original item customizations.
- **Responsive:** `/favorites` and `/track-order` support mobile bottom nav, tablet 2-3 column, laptop 4 column, TV 5-6 column. Address CRUD modal adapts to mobile bottom sheet.
- **Dark mode:** All new pages and components render correctly in dark mode. No black-on-black text.
- **Accessibility:** Form inputs have associated labels. Buttons have clear focus states. Tap targets >= 48px on mobile. Toast messages use `role="status"`.

## 11. Data / Model Coverage

- `favorites` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `restaurant_id` UUID FK → `restaurants.id`, `created_at` timestamp. Unique constraint on (`user_id`, `restaurant_id`). Index on `user_id` for fast lookup.
- `restaurants` table (extended): verify `opens_at` (TIME), `closes_at` (TIME), `avg_prep_minutes` (INTEGER, default 20), `delivery_radius_km` (DECIMAL, default 5.0) exist. Add via migration if missing.
- `orders` table (existing): cancellation sets `status = 'cancelled'`. `cancelled_at` timestamp (add if missing). `cancellation_reason` VARCHAR (add if missing).
- `wallet_transactions` table (existing): simulated refunds create `type = 'refund'` records with `status = 'pending'` or `'completed'`.
- `reviews` table (existing): seed 8-10 per restaurant. Fields: `id`, `restaurant_id`, `user_id`, `rating` (2-5), `comment` (TEXT), `created_at` (TIMESTAMP).
- `addresses` table (existing): `is_default` BOOLEAN (verify exists). `label` VARCHAR (Home/Work/Other). `phone` VARCHAR. `landmark` VARCHAR.
- `order_status_history` table (existing): new entries for `cancelled` transitions with `changed_at` and `changed_by`.
- No other schema changes.

## 12. Role / Permission Coverage

- `customer` role: Full access to all PR.05 features: favorites CRUD, reorder, coupon application, address CRUD, password reset, order cancellation, wallet refund viewing, guest order tracking (for own orders only).
- Guest (unauthenticated): Can browse, add to cart, checkout, track order via `/track-order` with order number + phone. Cannot access `/favorites`, `/profile`, `/orders` (login prompt shown). Cannot cancel orders (no auth to prove ownership).
- `restaurant_owner`, `delivery_partner`, `admin`, `super_admin`, `support`: Not involved in customer ordering flow for PR.05. Admin already has order management from PR.04.

## 13. Performance / Reliability / Security Coverage

### Performance
- Backend search endpoint uses indexed ILIKE on `name` and `cuisine_types` with `pg_trgm` extension if available, or simple B-tree index on lowercased name.
- Favorites list is a single indexed query by `user_id`.
- Prep-time queue size calculation is a count query on `orders` with `status IN ('pending', 'confirmed')` and `restaurant_id = ?`, likely <10ms.
- Haversine distance calculation is client-side or a single lightweight SQL function; no external API call.
- Enhanced seed data does not affect runtime performance (seeded once at setup).

### Reliability
- Password reset token expires after 15 minutes. Stored in Redis with TTL. Single-use only (deleted after validation).
- Address deletion requires confirmation modal to prevent accidental data loss.
- Default address logic: ensuring at least one address remains default when deleting the current default (fallback to oldest address or require explicit new default selection).
- Coupon validation is mock/demo-safe; no external payment provider dependency.
- Cancellation refund simulation is tracked in wallet transactions for audit trail, even if not real money.
- Guest tracking uses order number + phone hash match; does not leak other order data.

### Security
- Password reset tokens are cryptographically random (32-byte hex), stored in Redis with 15-minute TTL, not logged.
- Addresses contain PII (phone, street); ensure API endpoints return only authenticated user's own addresses.
- Guest order tracking only returns the specific order matching order number + phone; no enumeration possible.
- Coupon mock validation checks `min_order_amount` and `expires_at` to prevent abuse of demo coupons.
- No raw SQL in search endpoint; use SQLAlchemy parameterized queries with ILIKE.

## 14. Novelty / Differentiation Coverage

At score 5, novelty moves from "visible demo touches" to "functional retention features":
- **Favorites + reorder** — Core retention loops: bookmarking restaurants and one-tap reorder from history. These are standard in mature food delivery but novel at score 5 because they exist and work reliably.
- **Dynamic prep-time + open/closed logic** — Operational realism that adds trust. Users see real availability and accurate wait times.
- **Serviceability radius enforcement** — Prevents frustration from undeliverable orders. Suggests alternatives, keeping the user in the funnel.
- **Guest order tracking** — Reduces friction for non-logged-in users, a small UX differentiator.
- **Password reset + address CRUD** — Baseline features that make the app feel complete and professional, not "demo-only."
- **Enhanced seed data + real food images** — Rich demo data creates the perception of a lived-in, active platform.

Differentiators deferred: loyalty points activation (PR.07), meal rescue (PR.07), group ordering (PR.07), nutrition info (PR.07), AI suggestions (PR.08+), voice ordering (PR.08+).

## 15. Implementation Work Items

### IP.PR.05.001 — PR.04 P1 Completion: Location Auto-Detection
- **Category:** Frontend
- **Implementation Scope:** Finalize the PR.04 P1 location auto-detection item. Ensure `navigator.geolocation.getCurrentPosition()` is called on homepage mount. Use a mock reverse-geocode lookup (local city mapping from common lat/lng ranges, or a simple hardcoded fallback for demo). Update hero subtitle to "Delivering to {city}". Store detected city in `localStorage` key `bhojango-city`. Pre-fill restaurant list search or filter with detected city. Handle geolocation denial gracefully (show "Your City" with manual input). Add fallback for Safari/iOS permission delays.
- **Acceptance Criteria:**
  1. Homepage hero shows detected city within 2s of load on browsers with geolocation.
  2. Clicking "Find Food" navigates to `/restaurants` with city pre-filtered.
  3. Graceful fallback if geolocation is denied or unavailable.
  4. City preference persists across browser sessions.
- **Evidence Required:** Screen recording: load homepage → city auto-detected → click "Find Food" → restaurant list pre-filtered.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.04.003 (homepage CTA)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.002 — PR.04 P1 Completion: TV Responsive Layout
- **Category:** Frontend
- **Implementation Scope:** Verify and finalize PR.04 P1 TV responsive layout. Ensure Tailwind config includes `2xl:grid-cols-5` and `3xl:grid-cols-6` breakpoints. Add `3xl: '1920px'` to `tailwind.config.ts` screens if missing. Test all pages (`/`, `/restaurants`, `/favorites`) at 1920px+ viewport. Ensure max content width 1920px centered with `mx-auto`. Cards maintain aspect ratio, text readability, and tap target sizes at large viewports. Adjust font sizes for TV distance viewing (larger headings, slightly larger body text at 3xl breakpoint).
- **Acceptance Criteria:**
  1. Restaurant grid shows 5 columns at 1440px+ and 6 columns at 1920px+.
  2. No horizontal scroll at any breakpoint up to 2560px.
  3. Content centered within 1920px max-width container.
  4. Text and buttons remain readable and clickable at TV distance.
- **Evidence Required:** Screenshots of `/restaurants` at 1920px and 2560px viewports.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.04.013 (responsive layout)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.003 — PR.04 P1 Completion: Thali/Combo Builder UI
- **Category:** Frontend
- **Implementation Scope:** Complete the thali/combo builder UI for items with `item_type = 'combo'`. On restaurant detail page, combo items show constituent items as a list with checkboxes (all selected by default). Each constituent has a name and optional additional price. Unchecking a constituent removes it and reduces the combo price accordingly. Quantity stepper still applies to the whole combo. Customization modal supports combo builder layout. Combo items in cart show "Combo: {name}" with a collapsible list of selected constituents. Ensure veg/non-veg dot on the combo item reflects the dominant type or shows both if mixed.
- **Acceptance Criteria:**
  1. Combo items display constituent list with checkboxes in customization modal.
  2. Unchecking constituents reduces price in real-time.
  3. Cart shows combo with selected constituents in a collapsible list.
  4. Combo builder works on mobile (bottom sheet) and desktop (centered modal).
- **Evidence Required:** Screenshots: combo customization modal, cart with combo item expanded.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.04.005 (menu customization), IP.PR.04.012 (Indian food UI)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.004 — PR.04 P1 Completion: Enhanced Review Seed Data
- **Category:** Data
- **Implementation Scope:** Extend review seed data to 8-10 realistic reviews per restaurant (up from 3-5 in PR.04). Use 30+ realistic Indian food review text templates covering: praise for taste, complaint about delay, appreciation for packaging, spice level feedback, portion size comments, value-for-money ratings. Vary star ratings realistically (more 4-5 stars than 1-2, but some negative for authenticity). Use realistic Indian names for reviewers. Distribute `created_at` across last 6 months with realistic clustering. Ensure `GET /api/v1/restaurants/{id}/reviews` returns paginated results with average rating calculation.
- **Acceptance Criteria:**
  1. Every restaurant has 8-10 seeded reviews in DB.
  2. Review list endpoint supports pagination (`page`, `limit`).
  3. Average rating shown on restaurant card and detail page.
  4. Reviews have varied, realistic text and authentic Indian reviewer names.
- **Evidence Required:** Screenshot of restaurant detail showing 8+ reviews. `curl` output of reviews endpoint with `X-Total-Count` header.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.04.017 (review seed data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.005 — PR.04 P1 Completion: Wallet Balance on Profile
- **Category:** Frontend + Backend
- **Implementation Scope:** Stabilize wallet balance display on profile page. Ensure `GET /api/v1/wallets/me` (or equivalent) returns `{balance: number, currency: string}` reliably. If endpoint returns 200, display balance prominently in profile header with ₹ formatting. If endpoint returns 500 or timeout, hide wallet section gracefully (no error UI, just omit the section). Add `wallet_balance` to `GET /api/v1/me` response if feasible to reduce round-trips. Show recent 3-5 wallet transactions (debits, credits, refunds) below balance. Mock transaction descriptions: "Order #BG-123", "Top-up", "Refund for cancelled order".
- **Acceptance Criteria:**
  1. Profile page shows wallet balance with ₹ formatting when endpoint is healthy.
  2. Wallet section hidden gracefully if endpoint fails.
  3. Recent transactions list shows 3-5 items with type icons.
  4. No redirect loops or crashes on profile page.
- **Evidence Required:** Screenshot of profile page with wallet balance and transactions.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.04.010 (profile page)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.006 — Functional Reorder Flow
- **Category:** Frontend + Backend
- **Implementation Scope:** Implement end-to-end reorder. On order history card and order detail page, "Reorder" button is visible for all delivered and some confirmed orders. When tapped: (1) Fetch previous order items from `GET /api/v1/orders/{id}` (already available). (2) Pre-fill Zustand cart with exact same items: `menu_item_id`, `quantity`, `selected_add_ons`, `customizations`. (3) If current cart contains items from a different restaurant, trigger cross-restaurant cart guard: "Your cart has items from Spice Garden. Replace with items from Pizza Palace?" (4) On confirm, replace cart contents. (5) Toast: "{N} items added to your cart from {restaurant_name}." (6) Navigate to `/cart`.
- **Acceptance Criteria:**
  1. Reorder button visible on order history and detail pages.
  2. Tapping reorder pre-fills cart with exact previous items and quantities.
  3. Cross-restaurant guard triggers if needed.
  4. User lands on `/cart` with pre-filled items.
  5. Toast confirms reorder with item count and restaurant name.
- **Evidence Required:** Screen recording: `/orders` → tap Reorder → cart pre-filled with same items → proceed to checkout.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.003 (cross-restaurant guard), IP.PR.04.008 (order history)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.007 — Favorites Flow + DB Table
- **Category:** Frontend + Backend
- **Implementation Scope:** Create `favorites` table with (`user_id`, `restaurant_id`, `created_at`) and unique constraint. Add backend endpoints: `POST /api/v1/favorites` (toggle on), `DELETE /api/v1/favorites/{restaurant_id}` (toggle off), `GET /api/v1/favorites` (list user's favorites with restaurant details). Frontend: heart icon (Lucide `Heart` filled/empty) on every restaurant card and detail page header. Optimistic UI: toggle heart immediately, sync with API, revert on failure with error toast. "Your Favorites" horizontal scroll section on homepage (top 6 favorites). New `/favorites` page with grid layout, remove (X) button per card, empty state with illustration. Heart state persists across sessions.
- **Acceptance Criteria:**
  1. Heart toggle works on restaurant cards and detail pages.
  2. Toggling updates DB via API; optimistic UI shows immediate feedback.
  3. Homepage shows "Your Favorites" section with bookmarked restaurants.
  4. `/favorites` page lists all favorites with remove option.
  5. Empty favorites page shows illustration + "Browse Restaurants" CTA.
- **Evidence Required:** Screen recording: tap heart on card → homepage favorites section updates → navigate to `/favorites` → remove favorite → toast.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE (new feature)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.008 — Coupon System (Mock)
- **Category:** Frontend + Backend
- **Implementation Scope:** Create `offers` table: `id`, `code` (VARCHAR, unique), `type` ('percentage' | 'flat'), `value` (DECIMAL), `min_order_amount` (DECIMAL), `max_discount` (DECIMAL), `expires_at` (TIMESTAMP), `is_active` (BOOLEAN). Seed with "WELCOME20" (20% off, max ₹100, min ₹200) and "BHOJAN50" (50% off first order, max ₹150, min ₹300). Backend: `POST /api/v1/offers/validate` accepts `{code, order_total}` and returns `{valid: bool, discount_amount, message}` or 400 with error. Frontend: coupon input field in cart (above fee breakdown) with "Apply" button. On valid coupon: discount shown as separate line in fee breakdown, grand total recalculated. On invalid: red text below input. Coupon state persisted in Zustand cart store. Coupon carried into checkout summary.
- **Acceptance Criteria:**
  1. "WELCOME20" applies 20% discount on orders >= ₹200, capped at ₹100.
  2. Invalid coupon shows "Invalid or expired coupon code" in red.
  3. Discount visible in cart and checkout fee breakdown.
  4. Coupon removed if cart total drops below `min_order_amount`.
  5. Backend validation prevents expired or inactive coupons.
- **Evidence Required:** Screenshots: cart with valid coupon applied, cart with invalid coupon error, checkout showing discount.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.009 — Open/Closed Logic
- **Category:** Frontend + Backend
- **Implementation Scope:** Calculate `is_open` for each restaurant by comparing current time with `opens_at` and `closes_at` (account for restaurants open past midnight). Backend: add `is_open` boolean to restaurant list/detail response. Frontend: restaurant cards show green "Open" pill or gray "Closed · Opens at {time}" pill. Closed cards dimmed to 60% opacity, hover state removed. On restaurant detail: if closed, show banner "Restaurant is closed. Opens at {time}." Menu still visible for browsing but "Add to Cart" buttons disabled with tooltip "Restaurant is closed." Checkout blocks orders from closed restaurants with error toast. `opens_at`/`closes_at` fields seeded for all restaurants with realistic hours (e.g., 7 AM - 11 PM for breakfast places, 11 AM - 11 PM for dinner places).
- **Acceptance Criteria:**
  1. Open restaurants show green "Open" badge; closed show gray "Opens at {time}" badge.
  2. Closed restaurant cards are dimmed and non-interactive for ordering.
  3. Closed restaurant detail page shows closure banner and disabled add-to-cart buttons.
  4. Checkout prevents placing orders from closed restaurants.
  5. Logic handles restaurants open past midnight correctly.
- **Evidence Required:** Screenshots: restaurant list showing open and closed states, closed detail page with disabled ordering.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.04.004 (restaurant list), IP.PR.04.005 (restaurant detail)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.010 — Prep-Time Calculation
- **Category:** Frontend + Backend
- **Implementation Scope:** Dynamic prep-time: `estimated_minutes = avg_prep_minutes + (queue_size × 5)`. Queue size = count of orders for this restaurant with status IN ('pending', 'confirmed', 'preparing'). Backend: compute queue size in `GET /api/v1/restaurants/{id}` or as a separate lightweight endpoint `GET /api/v1/restaurants/{id}/queue`. Return `estimated_prep_minutes` and `estimated_delivery_minutes` (prep + delivery buffer of 10-15 min). Frontend: display on restaurant card as "{min}-{max} min" and on detail banner as "Delivery in {min}-{max} min". Update on page refresh (no polling required for PR.05). Seed `avg_prep_minutes` per restaurant (15-40 min range based on cuisine complexity).
- **Acceptance Criteria:**
  1. Each restaurant shows dynamic ETA range on card and detail page.
  2. Busy restaurants (high queue) show longer ETAs than quiet ones.
  3. ETA calculation uses `avg_prep_minutes` + queue estimate.
  4. Order confirmation page shows the same ETA that was displayed at checkout time.
- **Evidence Required:** Screenshots: restaurant card showing "30-35 min" vs "50-55 min" for busy restaurant. API response showing `estimated_prep_minutes`.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.011 — Serviceability Radius
- **Category:** Frontend + Backend
- **Implementation Scope:** Haversine distance check at checkout. Backend: endpoint `POST /api/v1/deliveries/check-serviceability` accepting `{restaurant_id, lat, lng}` and returning `{deliverable: bool, distance_km, max_radius_km}`. Uses existing Haversine utility from `delivery-svc` or `restaurant-svc`. Frontend: on checkout address selection/entry, call serviceability check. If `deliverable = false`: show red banner "This restaurant does not deliver to your address (distance: {distance} km, max: {radius} km)." Below banner, show "Nearby restaurants that deliver here:" with up to 3 suggestions (fetched from `GET /api/v1/restaurants?near={lat},{lng}&radius={default}`). Block "Place Order" button until deliverable address selected. If address is within radius, show green "Deliverable" checkmark.
- **Acceptance Criteria:**
  1. Out-of-range address blocked at checkout with distance info.
  2. 3 nearest deliverable restaurants suggested as alternatives.
  3. Place Order button disabled until address is within radius.
  4. In-range address shows green deliverable confirmation.
- **Evidence Required:** Screenshots: checkout with blocked address + suggestions, checkout with valid address + green checkmark.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.04.007 (checkout page)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.012 — Password Reset Flow
- **Category:** Frontend + Backend
- **Implementation Scope:** Complete end-to-end password reset. Backend: `POST /api/v1/auth/forgot-password` accepts `{email}`, generates random 6-digit OTP, stores in Redis with 15-min TTL, returns 204 (no email sent in demo; OTP logged or returned in dev mode for testing). `POST /api/v1/auth/verify-otp` accepts `{email, otp}`, returns temporary reset token (JWT, 15-min expiry). `POST /api/v1/auth/reset-password` accepts `{email, reset_token, new_password}`, validates token, updates bcrypt hash, returns 204. Frontend: login page "Forgot password?" link → `/forgot-password` page with email input → mock OTP displayed in toast (for demo convenience) → `/verify-otp` page with OTP input → `/reset-password` page with new password + confirm fields → on success, auto-login and redirect to `/`. Error states: invalid email, expired OTP, mismatched passwords.
- **Acceptance Criteria:**
  1. User can request password reset, receive OTP, and set new password.
  2. After reset, user is auto-logged in and redirected to homepage.
  3. Invalid OTP shows error: "Invalid or expired OTP."
  4. Password strength validation (min 8 chars, 1 uppercase, 1 number) on new password.
  5. Redis entries expire after 15 minutes.
- **Evidence Required:** Screen recording: forgot password → OTP → new password → auto-login.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.013 — Address CRUD
- **Category:** Frontend + Backend
- **Implementation Scope:** Full address management. Backend: `PUT /api/v1/addresses/{id}` (update all fields), `DELETE /api/v1/addresses/{id}` (delete with validation: cannot delete last address if user has orders), `PATCH /api/v1/addresses/{id}/set-default` (set `is_default = true`, unset others). Frontend: profile page "Manage Addresses" section showing address cards with label, street, city, pincode. Edit button opens modal with pre-filled form. Delete button opens confirmation modal. "Set as Default" radio button. "Add New Address" button opens empty modal. All address modals use bottom sheet on mobile (<640px) and centered modal on desktop. Checkout page saved addresses shown as radio cards with edit/delete dropdown per card. Default address auto-selected. Inline validation on all fields.
- **Acceptance Criteria:**
  1. User can create, edit, delete, and set default addresses.
  2. Delete requires confirmation modal.
  3. Checkout shows saved addresses as radio cards with default pre-selected.
  4. Address modals adapt to mobile bottom sheet / desktop centered modal.
  5. At least one address must remain (prevent deleting last address).
- **Evidence Required:** Screen recording: add address → edit address → set default → delete address → checkout with new default selected.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.04.007 (checkout with saved addresses)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.014 — Order Cancellation + Simulated Refund
- **Category:** Frontend + Backend
- **Implementation Scope:** Cancellation flow. Backend: `PATCH /api/v1/orders/{id}/cancel` accepts `{reason}`. Validates order belongs to current user. Validates status is `pending` or `confirmed`. Updates `status = 'cancelled'`, sets `cancelled_at = now()`, `cancellation_reason = reason`. Inserts `order_status_history` entry. If `payment_method = 'wallet'`, creates `wallet_transactions` record: `type = 'refund'`, `amount = order.grand_total`, `status = 'pending'` (or 'completed' for demo), description = "Refund for cancelled order #{id}". Frontend: "Cancel Order" button visible on order detail if status in ['pending', 'confirmed']. Confirmation modal with refund info. On success: toast "Order cancelled. Refund of ₹{amount} will be credited to your wallet within 24 hours." Order detail updates: status badge changes to "Cancelled", timeline hidden, cancellation banner shown with reason and refund amount. `/wallet` page shows refund transaction.
- **Acceptance Criteria:**
  1. Cancel button visible only for pending/confirmed orders.
  2. Cancellation shows confirmation modal with refund amount.
  3. Order status updates to cancelled, timeline hidden, cancellation banner shown.
  4. Wallet refund transaction appears in wallet history.
  5. Delivered orders cannot be cancelled (no button).
- **Evidence Required:** Screen recording: order detail → cancel → confirm → cancelled banner → wallet shows refund.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.012 (cancellation API), IP.PR.04.009 (order tracking)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.015 — Enhanced Seed Data
- **Category:** Data
- **Implementation Scope:** Comprehensive seed data for closed demo. Reviews: 8-10 per restaurant (30+ templates, realistic Indian names, varied ratings 2-5, dates over 6 months). Orders: 10-15 per demo user with statuses: pending, confirmed, preparing, ready_for_pickup, picked_up, delivered, cancelled (mix of COD and wallet payments). Wallet transactions: 5-8 per user (top-ups ₹500-2000, order debits, refund credits). Restaurants: deterministic Unsplash food images per cuisine type (e.g., `https://images.unsplash.com/photo-{hash}` mapped to Indian/Chinese/Pizza/etc.). Realistic restaurant descriptions, Indian pin codes, phone numbers. Menu items: ensure `is_veg`, `is_jain`, `spice_level`, `item_type` fields are populated for all items. Ensure 2-3 combo items per restaurant for thali builder demo.
- **Acceptance Criteria:**
  1. Every restaurant has 8-10 reviews with realistic text and names.
  2. Every demo user has 10-15 orders with varied statuses.
  3. Every demo user has 5-8 wallet transactions.
  4. All menu items have `is_veg`, `is_jain`, `spice_level` populated.
  5. 2-3 combo items per restaurant for thali builder.
- **Evidence Required:** DB query screenshots: `SELECT COUNT(*) FROM reviews GROUP BY restaurant_id`, `SELECT status, COUNT(*) FROM orders WHERE user_id = ? GROUP BY status`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.016 — Guest Order Tracking by Order Number
- **Category:** Frontend + Backend
- **Implementation Scope:** New `/track-order` page accessible without login. Form: order number (e.g., "BG-20240614-7392"), phone number. Backend: `POST /api/v1/orders/track` accepts `{order_number, phone}` and returns order summary if match found (phone compared against order's `delivery_phone` or user's phone). If match, return `{status, restaurant_name, items, timeline, total}`. Mock OTP step: after form submit, show "Enter OTP sent to your phone" with mock OTP displayed in toast ("Your OTP is 123456" for demo). OTP input validates, then shows order status and timeline. No personal data beyond the matched order is exposed.
- **Acceptance Criteria:**
  1. Guest can navigate to `/track-order` without login.
  2. Entering valid order number + phone shows OTP step.
  3. After OTP, order status and timeline are displayed.
  4. Invalid order number or phone shows "No order found with these details."
  5. Page has error boundary and loading skeleton.
- **Evidence Required:** Screen recording: `/track-order` → enter order number + phone → OTP → see timeline.
- **Priority:** P1
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.05.017 — Backend Search Endpoint
- **Category:** Backend
- **Implementation Scope:** Create `GET /api/v1/restaurants/search?q={query}&page={page}&limit={limit}` in `restaurant-svc`. Query uses ILIKE on `name` and `cuisine_types` (array/string search depending on schema). Example: `SELECT * FROM restaurants WHERE name ILIKE '%{query}%' OR cuisine_types ILIKE '%{query}%' ORDER BY rating DESC LIMIT {limit} OFFSET {offset}`. Add `pg_trgm` extension and GIN index on `name` for performance if needed (demo-safe without it). Return same fields as list endpoint. Frontend: integrate into restaurant list search bar. Debounce 300ms. On typing, call search endpoint; if empty query, fall back to standard list. Show loading skeleton during search. Empty state: "No restaurants found for '{query}'. Try a different term."
- **Acceptance Criteria:**
  1. `/search?q=biryani` returns restaurants with "biryani" in name or cuisine.
  2. Search is case-insensitive and matches partial strings.
  3. Results are paginated with `page` and `limit` params.
  4. Frontend search bar debounces at 300ms and shows skeleton while loading.
  5. Empty search shows custom illustration + message.
- **Evidence Required:** `curl` output of search endpoint. Screenshots: search UI with results and empty state.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.04.004 (restaurant search/filter)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] All PR.04 P1 items are completed: location auto-detection works within 2s, TV layout verified at 1920px+, thali/combo builder functional, 8-10 reviews per restaurant seeded, wallet balance reliably displayed on profile.
- [ ] Reorder flow works: tapping "Reorder" on any past order pre-fills cart with exact items, respects cross-restaurant guard, navigates to `/cart` with toast confirmation.
- [ ] Favorites system works: heart toggle on cards and detail pages persists to DB, "Your Favorites" section on homepage, `/favorites` page lists all bookmarks with remove option, empty state shown.
- [ ] Coupon system works: "WELCOME20" applies 20% discount (max ₹100, min ₹200) in cart and checkout; invalid coupon shows red error; discount visible in fee breakdown; backend validates expiry and min order.
- [ ] Open/closed logic enforced: open restaurants show green "Open" badge; closed restaurants dimmed with "Opens at {time}" badge; closed restaurant detail blocks add-to-cart; checkout prevents orders from closed restaurants.
- [ ] Dynamic prep-time displayed: ETA range calculated from `avg_prep_minutes` + queue size × 5 min; shown on cards and detail page; varies by restaurant busyness.
- [ ] Serviceability radius enforced: checkout blocks out-of-range addresses with distance info; suggests up to 3 nearest deliverable alternatives; green "Deliverable" checkmark for valid addresses.
- [ ] Password reset flow complete: forgot password → email → OTP (mock, shown in toast) → new password → auto-login; invalid OTP and weak passwords show errors; Redis token expires in 15 min.
- [ ] Address CRUD complete: create, edit, delete, set default all functional; checkout shows saved addresses as radio cards with default pre-selected; delete requires confirmation; at least one address must remain.
- [ ] Order cancellation + refund simulation works: cancel button visible for pending/confirmed orders; confirmation modal with refund amount; status updates to cancelled; wallet credited with refund transaction; delivered orders cannot be cancelled.
- [ ] Enhanced seed data: 8-10 reviews per restaurant, 10-15 orders per demo user, 5-8 wallet transactions per user, deterministic Unsplash images, combo items for thali builder, all menu items have veg/Jain/spice populated.
- [ ] Guest order tracking: `/track-order` page accepts order number + phone + mock OTP; displays order status and timeline; invalid details show "No order found"; no login required.
- [ ] Backend search endpoint: `GET /api/v1/restaurants/search?q=` with ILIKE on name and cuisine; paginated; integrated into frontend search bar with debounce; empty state for no results.
- [ ] Core loop remains stable: no blank screens, no crashes on standard paths, all screens have loading/error/empty/success states, design system applied globally, responsive on all breakpoints, dark mode works.
- [ ] App is usable for 5-10 concurrent demo users placing orders without breaking the core loop or corrupting data.

## 17. Evidence Required

- Screen recording: guest opens app → location auto-detected → browse open restaurants → search backend "biryani" → open restaurant → see dynamic ETA → add item → view cart → apply "WELCOME20" → enter deliverable address → checkout → place order → track via `/track-order` with order number + phone.
- Screen recording: logged-in user browses → heart favorites 3 restaurants → view homepage favorites row → navigate to `/favorites` → reorder a past order → cart pre-filled → checkout with saved address → place order → cancel order → see refund in wallet.
- Screen recording: password reset flow → forgot password → OTP → new password → auto-login → add/edit/delete address → set default → checkout with new default.
- Screenshots: restaurant list showing open and closed states side by side; closed restaurant detail page with disabled ordering; out-of-range checkout with alternative suggestions.
- Screenshots: `/favorites` page populated and empty state; `/track-order` page with form and results; password reset flow pages.
- Screenshots: cart with valid coupon and invalid coupon; checkout fee breakdown with discount line; wallet page showing refund transaction.
- Screenshots: order detail with cancel button and confirmation modal; cancelled order with cancellation banner; delivered order without cancel button.
- Screenshots of responsive layout: `/favorites` at 375px, 768px, 1280px, 1920px.
- `curl` outputs: `GET /api/v1/restaurants/search?q=biryani`, `POST /api/v1/offers/validate`, `POST /api/v1/orders/track`.
- DB query outputs: review counts per restaurant, order counts per user, wallet transaction counts per user.
- DevTools screenshots: `localStorage` keys `bhojango-city`, `bhojango-cart-coupon`. Redis keys for password reset tokens.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- Google Fonts (Manrope + Inter) — already used from PR.04.
- Unsplash (deterministic food image URLs) — already used from PR.04.
- Lucide React (icon library) — already used from PR.04.

### Internal Dependencies
- **PR.04 must be complete:** reliable core loop, design system, loading/error/empty states, responsive layout, dark mode, toast, skeletons, auth persistence, guest cart, checkout, order tracking, profile page.
- `GET /api/v1/me` must return reliable user data.
- `GET /api/v1/orders` and `GET /api/v1/orders/{id}` must return full order details including items.
- Cart Zustand store must support programmatic pre-filling (for reorder).
- `orders` table must allow `user_id = NULL` for guest orders (verify).
- `addresses` table must support `is_default`, `label`, `landmark` fields (verify or migrate).
- `restaurants` table must support `opens_at`, `closes_at`, `avg_prep_minutes`, `delivery_radius_km` (verify or migrate).

## 19. Risks / Blockers

- **Password reset token storage requires Redis.** If Redis is not running, the reset flow cannot store/verify tokens. Mitigation: document Redis as required for PR.05; use in-memory fallback only for isolated dev testing with a TODO to remove.
- **Favorites table requires new migration.** If migration tooling (Alembic) is not configured for the target service, manual SQL migration needed. Mitigation: verify Alembic is set up for `restaurant-svc` or `user-svc`; if not, provide raw SQL migration script in work item notes.
- **Address CRUD may conflict with checkout address selection state.** If checkout form manages address state independently of profile address state, edits in one may not reflect in the other without refresh. Mitigation: invalidate address query cache (TanStack Query `queryClient.invalidateQueries(['addresses'])`) after any CRUD operation.
- **Serviceability radius may block all seeded addresses if restaurant coordinates are random.** If seeded restaurants and addresses are in different cities, Haversine check will always fail. Mitigation: ensure seed data places restaurants and demo users within the same metropolitan area (e.g., Hyderabad) with realistic lat/lng offsets.
- **Open/closed logic with timezone handling.** If server and client are in different timezones, `is_open` calculation may disagree. Mitigation: server returns `is_open` boolean based on UTC comparison with restaurant's local timezone (assume IST for demo). Client trusts server flag.
- **Coupon mock validation may be bypassed client-side.** Since this is demo-only, client-side coupon logic could be tampered with. Mitigation: backend `POST /api/v1/offers/validate` must be the source of truth for discount amount; client only displays.
- **Guest order tracking by phone number requires phone to be captured at checkout.** If guest checkout does not collect phone reliably, tracking fails. Mitigation: enforce phone number collection in guest checkout address form; store in `orders.delivery_phone`.
- **Enhanced seed data may slow down `docker-compose up` or seed scripts.** Large seed data increases startup time. Mitigation: seed reviews and orders asynchronously or in batches; document expected seed duration (~30s).

## 20. Exit Criteria

- All P0 work items (IP.PR.05.006 through IP.PR.05.015, IP.PR.05.017) implemented and verified.
- All P1 work items (IP.PR.05.001 through IP.PR.05.005, IP.PR.05.016) implemented and verified.
- Core loop is stable: no blank screens, no crashes on standard paths for both guest and logged-in users.
- App passes a "closed demo" test: 5-10 users can concurrently browse, favorite, order, reorder, cancel, and track without data corruption or UI breakage.
- All new features (reorder, favorites, coupon, open/closed, prep-time, radius, password reset, address CRUD, cancellation, guest tracking, search) have loading, error, empty, and success states.
- Design system is applied on all new pages (`/favorites`, `/track-order`, password reset flow, address CRUD modals).
- Responsive layout verified for new pages on mobile, tablet, laptop, and TV.
- Evidence screenshots/recordings captured per Section 17.
- PR.05 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.04)

PR.05 directly depends on PR.04 achievements:
- **IP.PR.04.001** — Auth Persistence Polish: required for reliable password reset, favorites, and address CRUD.
- **IP.PR.04.002** — Guest Cart Flow: foundation for guest order tracking and guest checkout improvements.
- **IP.PR.04.003** — Homepage CTA + Location: foundation for finalized location auto-detection (IP.PR.05.001).
- **IP.PR.04.004** — Restaurant Search/Filter: foundation for backend search endpoint (IP.PR.05.017).
- **IP.PR.04.005** — Menu DB Fallback + Customization: foundation for thali/combo builder completion (IP.PR.05.003).
- **IP.PR.04.006** — Cart Polish: foundation for coupon input (IP.PR.05.008) and reorder pre-fill (IP.PR.05.006).
- **IP.PR.04.007** — Checkout Polish: foundation for address CRUD (IP.PR.05.013), serviceability radius (IP.PR.05.011), and open/closed checkout enforcement (IP.PR.05.009).
- **IP.PR.04.008** — Order Confirmation + History: foundation for reorder button placement and guest tracking (IP.PR.05.016).
- **IP.PR.04.009** — Mock Tracking Timeline: foundation for cancellation banner replacing timeline (IP.PR.05.014).
- **IP.PR.04.010** — Profile Page: foundation for wallet balance (IP.PR.05.005) and address CRUD entry point (IP.PR.05.013).
- **IP.PR.04.011** — Design System: foundation for all new UI in PR.05.
- **IP.PR.04.012** — Indian Food UI: foundation for combo builder (IP.PR.05.003).
- **IP.PR.04.013** — Responsive Layout: foundation for TV layout finalization (IP.PR.05.002).
- **IP.PR.04.014** — Toast Component: reused for all new user actions in PR.05.
- **IP.PR.04.015** — Error Boundaries + Skeletons + Empty States: pattern reused for `/favorites`, `/track-order`, search results.
- **IP.PR.04.016** — Dark Mode: must work on all new PR.05 pages and components.
- **IP.PR.04.017** — Review Seed Data: foundation for enhanced review seeding (IP.PR.05.004).

## 22. Connected Next-Level Requirements (link to PR.06)

PR.06 (Closed Beta Marketplace, score 6/10) builds on PR.05 and requires:
- Working closed-demo app from all IP.PR.05 work items.
- Favorites system (IP.PR.05.007) as foundation for personalized homepage sections.
- Coupon system (IP.PR.05.008) as foundation for real promotional campaigns.
- Address CRUD (IP.PR.05.013) as foundation for map pin selection and autocomplete.
- Order cancellation + refund (IP.PR.05.014) as foundation for real refund processing with payment providers.
- Enhanced seed data (IP.PR.05.015) as foundation for realistic analytics and admin dashboards.
- Backend search (IP.PR.05.017) as foundation for advanced filters and discovery.

PR.06 will introduce:
- Restaurant owner dashboard: menu management, order acceptance, earnings.
- Delivery partner dashboard: shift management, route navigation, earnings.
- Super admin dashboard: user/restaurant/driver oversight, analytics, commission settings.
- Real-time driver tracking with map integration (Mapbox/Leaflet).
- Address autocomplete with Nominatim or Google Places.
- WebSocket reconnection logic for order tracking.
- Onboarding flow after signup (3-step: location, cuisines, done).
- Social login frontend wiring (Google OAuth already backend-ready).
- Loyaly points full activation and redemption.
- Push notification dispatch (FCM templates exist but not wired end-to-end).
- Group ordering (novelty).
- Meal rescue / end-of-day deals (novelty).

PR.06 will be blocked if:
- Password reset flow is broken (users cannot recover accounts).
- Address CRUD is incomplete (users cannot manage delivery locations).
- Open/closed logic is not enforced (orders placed when restaurant is closed).
- Serviceability radius not enforced (undeliverable orders accepted).
- Cancellation does not work reliably (users stuck with wrong orders).
- Favorites or reorder features crash or lose data.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (5/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.04 complete) described | Planner | ✅ |
| 4 | Target state (PR.05 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.05 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.05 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage includes favorites, reorder, dynamic prep-time | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.05.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover: PR.04 P1 completion (location, TV, thali, reviews, wallet), reorder, favorites, coupon, open/closed, prep-time, radius, password reset, address CRUD, cancellation, enhanced seed, guest tracking, backend search | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention Redis for tokens, migration for favorites, address/checkout sync, seed coordinates, timezone, coupon bypass, guest phone | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.04) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.06) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories: PR.04 P1 completion (IP.PR.05.001 through IP.PR.05.005), reorder (IP.PR.05.006), favorites with DB table (IP.PR.05.007), coupon system (IP.PR.05.008), open/closed logic (IP.PR.05.009), prep-time calculation (IP.PR.05.010), serviceability radius (IP.PR.05.011), password reset (IP.PR.05.012), address CRUD (IP.PR.05.013), cancellation + refund (IP.PR.05.014), enhanced seed data (IP.PR.05.015), guest order tracking (IP.PR.05.016), and backend search (IP.PR.05.017).
- Scope is tightly bounded to score 5/10 (usable closed demo for 5-10 users). Out-of-scope explicitly excludes restaurant/driver/admin dashboards, real payment gateways, push notifications, CDN, group ordering, loyalty activation, meal rescue, and real-time map tracking.
- Data model coverage addresses schema changes: `favorites` table, extended `restaurants` fields (`opens_at`, `closes_at`, `avg_prep_minutes`, `delivery_radius_km`), `orders` cancellation fields, `wallet_transactions` refund type.
- Risks and blockers are grounded in known dependencies from audits (Redis for password tokens, Alembic for favorites migration, address/checkout state sync, seed coordinate proximity, timezone handling, guest phone collection).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references and blocker conditions.
- Feasibility tags use the required color system (🟢 LOCAL/DEMO-SAFE throughout; no 🔴 or ⚫ tags needed since all work is local-safe and demo-based).
- **One point deducted** because exact Alembic migration paths, exact Zustand store file paths for favorites, and exact seed script locations are assumed from PR.04 conventions rather than explicitly confirmed. Minor discovery may be needed during build to locate these precisely.

The document is ready for execution.
