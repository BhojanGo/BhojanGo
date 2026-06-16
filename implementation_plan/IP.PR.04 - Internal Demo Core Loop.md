# IP.PR.04 — Internal Demo Core Loop

## 1. Target Score Level: 4/10

## 2. Score Meaning

At score 4/10, the app is **internally demo-ready**. A user can:
- Login or continue as guest without session loss.
- Browse restaurants with search, filters, cuisine chips, infinite scroll, and real food images.
- Open a restaurant detail page and see a categorized menu with veg-only toggle, bestseller badges, item customization, and a delivery fee banner.
- Add items to cart (guest or logged-in), view cart with quantity steppers and full fee breakdown, and see a polished empty state.
- Proceed to checkout with saved address selection, payment method radio, order summary, and inline validation.
- Place an order with simulated payment (no real gateway), see order confirmation with order number and ETA, and view the order in order history.
- See a mock tracking timeline (confirmed → preparing → ready → picked up → delivered) with contact support and ETA text.
- View profile data, addresses, order history, and wallet balance (P1, conditional on wallet endpoint reliability).

Every screen has correct loading, error, empty, and success states. Navigation is smooth. Data feels realistic. No dead-ends. The design system (BhojanGo palette, Inter/Manrope font, consistent spacing/badge/card anatomy) is applied across all pages. The app is responsive across phone, tablet, laptop, and TV. Indian food delivery specifics (veg/non-veg dots, Jain tag, spice level, thali builder, ₹ pricing) are visible.

## 3. Current → Target Transition

**Current (PR.03 complete):**
- Guest cart persists in `localStorage` and survives refresh.
- Cart page shows items with quantity steppers, veg/non-veg indicators, and totals.
- Cross-restaurant cart guard triggers and replaces cart correctly.
- Checkout form validates required address fields inline.
- Payment method radio selector shows Card, UPI, Wallet, COD with appropriate mock states.
- Order creation endpoint validates restaurant, menu items, quantities, and prices server-side.
- Simulated payment marks order as `paid` (non-COD) or `pending` (COD) without external gateway calls.
- Order state machine rejects invalid transitions with 400.
- Order confirmation page renders with order summary and CTAs.
- Authenticated order list page shows past orders with status badges.
- Order detail page shows item list, fee breakdown, address, and mock tracking timeline.
- Cancellation API allows cancelling `pending` or `confirmed` orders; rejects `delivered` cancellations.
- Frontend cancellation flow shows confirmation modal and updates UI on success.
- Delivery fee is calculated and displayed (flat or threshold-based).
- Fee/tax breakdown visible on cart, checkout, confirmation, and detail pages.

**However, PR.03 is "transactional but shaky":**
- Some screens have blank white loading states instead of skeletons.
- Empty cart shows nothing or a bare text line, not a designed empty state with illustration.
- No toast/snackbar feedback for user actions (add-to-cart, login error, order placed).
- Design system is not applied — generic Tailwind colors (`emerald-600`), system fonts, inconsistent spacing.
- No Indian food-specific UI (veg dots, Jain tag, spice level, thali builder).
- Responsive layout is incomplete — no tablet layout, no TV breakpoints, bottom nav may not highlight correctly.
- Dark mode CSS exists but no toggle; pages may have black-on-black text.
- No error boundaries on checkout or order detail — API failure can crash the page.
- Profile page may redirect to login instead of showing real data.
- Reviews section is blank because no reviews are seeded.
- "Find Food" button on homepage may be non-functional.
- No location auto-detection on homepage.

**Target at score 4:**
- Every screen in the core loop has correct loading (skeleton), error (boundary + retry), empty (illustration + CTA), and success states.
- Design system is fully applied: BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, consistent 4px grid spacing, Lucide icons only, badge anatomy standard, card anatomy standard.
- Indian food delivery specifics: mandatory veg/non-veg dot on every menu item and cart row, Jain tag where applicable, 1-5 chili icons for spice level, thali/combo builder UI, regional cuisine labels, delivery fee in ₹.
- Responsive across all breakpoints: mobile-first with bottom nav (<640px), tablet layout (md: 2-col, lg: 3-col), laptop (xl: 4-col), TV (2xl: 5-col, 3xl: 6-col).
- Toast/snackbar component provides feedback for every action.
- Dark mode toggle works and persists.
- Error boundaries prevent page crashes on all pages.
- Profile page displays real data from `/api/v1/me` without redirect loops.
- Reviews are seeded with realistic text so every restaurant shows 3-5 reviews.
- Homepage "Find Food" CTA navigates to restaurant list; location auto-detects via `navigator.geolocation`.
- The core loop is traversable reliably end-to-end with no broken primary CTA and no blank critical pages.

## 4. Implementation Objective

Make the complete core ordering loop robust and demo-ready. Every screen in the journey — homepage → restaurant list → restaurant detail → cart → checkout → confirmation → order history → order tracking → profile — must have correct loading, error, empty, and success states. Navigation must be smooth. Data must feel realistic. No dead-ends. Apply the BhojanGo design system and Indian food delivery UX standards. Ensure responsiveness across phone, tablet, laptop, and TV.

## 5. Scope

### In Scope

1. **Auth persistence polish** — Ensure httpOnly cookie or secure localStorage strategy works reliably. No session loss on refresh. Logout clears state cleanly.
2. **Guest checkout flow** — Cart survives refresh. At checkout, guest is prompted for address (manual text entry). Order placed without forcing login. Guest order stored with `user_id = null` (or minimal guest identifier). Guest can see order confirmation but not order history.
3. **Homepage CTA wiring** — "Find Food" button navigates to `/restaurants` with city query param. Location auto-detection: on load, call `navigator.geolocation.getCurrentPosition()`, reverse-geocode to city name (mock or API), update hero subtitle to "Delivering to {city}" and pre-fill search.
4. **Restaurant list enhancements** — Sticky debounced search bar (200ms). Horizontal scrollable cuisine chips. Rating 4+ / veg-only / under-30-min filter chips. Infinite scroll via Intersection Observer. Real deterministic Unsplash food images per cuisine. Trust badges (FSSAI Verified, Freshly Prepared, Under 30 min).
5. **Restaurant detail enhancements** — Menu loads via DB fallback (no OpenSearch dependency). Sticky category tabs (Starters | Mains | Breads | Desserts | Combos) with scroll-to-section. Veg-only toggle. Bestseller badges on top 3 items per category. Item customization modal (bottom sheet on mobile) with add-ons, quantity stepper, and price. Delivery fee banner. Review section seeded with 3-5 realistic reviews per restaurant, showing star rating, reviewer name, date, and text.
6. **Cart page polish** — Guest/local cart with `localStorage` persistence. Quantity stepper (+ / -). Veg/non-veg dot per item. Full fee breakdown (items total, delivery fee, platform fee, tax, discount, grand total). Coupon input with mock validation ("WELCOME20" gives 20% off). Empty state with custom SVG illustration + "Browse Restaurants" CTA. Checkout CTA is prominent and disabled when cart is empty.
7. **Checkout page polish** — Saved address selection as radio cards (or manual entry for guests). Payment method radio group (Card / UPI / Wallet / COD) with mock sub-forms for Card/UPI. Order summary accordion. "Place Order" button disabled until address + payment + cart are valid. Inline validation errors (red text) on all required fields.
8. **Order confirmation page** — Order number, estimated delivery time, next steps ("Your order is being prepared"), and "View Orders" CTA.
9. **Order history page** — List of past orders with restaurant image, name, total, status badge (colored pill), date. Reorder button. Empty state for no orders.
10. **Order tracking page** — Static timeline: Confirmed → Preparing → Ready for Pickup → Picked Up → Delivered. Current step highlighted. Contact support button. Delivery ETA text.
11. **Profile page** — Display data from `GET /api/v1/me`: full name, email, phone, avatar. Show saved addresses. Show order history summary. Show wallet balance (if wallet endpoint reliable; otherwise hidden).
12. **Design system application** — Apply BhojanGo palette via CSS custom properties. Import Manrope (headings) + Inter (body) from Google Fonts. Define consistent spacing tokens (4px base grid, card padding 16px, card gap 24px, button min-height 48px). Standardize badge anatomy (border-radius 40px, padding 4px 12px, font-weight 600). Standardize card anatomy (image 16:10, rounded-xl, gradient overlay bottom, name h3, cuisine chips row, rating badge absolute top-right, delivery time badge absolute bottom-right). Use Lucide icons exclusively (no raw emoji).
13. **Indian food delivery UI specifics** — Mandatory green/red veg/non-veg dot on every menu item and cart row. Jain tag ("J") pill for Jain-friendly items. Spice level chili icons (1-5 red chilies). Thali/combo builder UI for combo items. Regional cuisine label (e.g., "North Indian", "South Indian"). All delivery fees and totals displayed in ₹ (Indian Rupee symbol).
14. **Responsive layout** — Mobile-first design. Bottom navigation on mobile (<640px) with active tab highlight and cart badge. Tablet layout: md:grid-cols-2, lg:grid-cols-3. Laptop: xl:grid-cols-4. TV breakpoints: 2xl:grid-cols-5, 3xl:grid-cols-6. Max content width 1920px centered.
15. **Toast/snackbar component** — Global toast system triggered on: add-to-cart, login success/error, order placed, order cancelled, validation error, network error. Auto-dismiss 3s. Position: bottom-right on desktop, bottom-center on mobile.
16. **Loading skeletons** — Skeleton cards for restaurant list, skeleton rows for menu, skeleton text for profile and order detail. No blank white screens during loading.
17. **Empty states with custom illustrations** — Empty cart (sad pizza SVG), empty orders (empty box SVG), empty restaurant search (empty plate SVG). Each has message + CTA.
18. **Dark mode toggle** — Sun/moon toggle in navbar. Persist in `localStorage`. Respect `prefers-color-scheme`. Ensure all pages render correctly in dark mode with no black-on-black text.
19. **Error boundaries** — React Error Boundary on every page (`/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/profile`). Friendly error UI with retry button and correlation ID.
20. **Review seed data generation** — Seed 3-5 reviews per restaurant with realistic text, varying star ratings (2-5), reviewer names, and dates. Reviews visible on restaurant detail page.

### Out of Scope

- Real payment gateway integration (Stripe, Razorpay, UPI deep linking) — simulated is enough for demo.
- Real-time driver tracking / map integration.
- Push notifications / SMS / email dispatch.
- Restaurant owner dashboard (PR.06).
- Delivery partner app (PR.06).
- Admin approval flows (PR.06).
- Group ordering (novelty).
- Favorites / reorder (novelty).
- Loyalty points activation (novelty).
- Offers/coupons full system (mock validation only).
- CDN / S3 / image optimization infra.
- Observability stack (Prometheus, Grafana, Loki).
- CI/CD pipeline.
- E2E tests.
- WebSocket reconnection logic (use simple polling or static timeline).
- Address autocomplete / map pin selection (manual text entry is acceptable).
- Real-time traffic data for ETA.

## 6. Out of Scope (Summary)

- Real payment gateways, real-time driver tracking/map, push/SMS/email.
- Owner/driver/admin dashboards and flows (PR.06+).
- Group ordering, favorites, reorder, loyalty activation (novelty — PR.05+).
- Full offers/coupons system, CDN/S3/image optimization.
- Observability, CI/CD, E2E tests.
- Address autocomplete, real-time traffic, WebSocket reconnection.

## 7. Required Capabilities

- Auth persists across refresh with no session loss.
- Guest cart survives refresh and can checkout without login.
- Homepage "Find Food" navigates to restaurant list; location auto-detects.
- Restaurant list supports search, cuisine chips, filters, and infinite scroll.
- Restaurant detail loads menu from DB fallback with category tabs, veg toggle, bestseller badges, customization modal, and seeded reviews.
- Cart shows quantity steppers, fee breakdown, coupon mock validation, and empty state.
- Checkout has address selection, payment radio, order summary, inline validation, and disabled Place Order until valid.
- Order confirmation shows order number, ETA, and CTA to view orders.
- Order history lists past orders with status badges and reorder button.
- Order tracking shows static timeline with correct current step.
- Profile displays real user data, addresses, order history, and wallet balance if endpoint ready.
- Design system (palette, font, spacing, badges, cards) is applied globally.
- Indian food specifics (veg dots, Jain tag, spice level, thali builder, ₹ pricing) are visible.
- Responsive layout works on mobile, tablet, laptop, and TV.
- Toast component provides feedback for all actions.
- Loading skeletons on all lists; empty states with illustrations; error boundaries on all pages.
- Dark mode toggle works and persists.

## 8. Key User Journeys

### Journey 8.1 — Guest Browses, Orders, and Tracks
1. User opens app without logging in.
2. Homepage auto-detects location: "Delivering to Hyderabad". User taps "Find Food".
3. Restaurant list loads with skeleton cards, then populates with real data, Unsplash images, trust badges.
4. User types "biryani" in search bar → list filters. User taps "Indian" cuisine chip.
5. User taps a restaurant card. Detail page loads with header skeleton, then shows menu with category tabs.
6. User toggles "Veg Only" → only veg items shown. User sees "Bestseller" badges and chili spice icons.
7. User taps "Add" on Paneer Tikka. Customization modal opens (bottom sheet on mobile). User selects "Extra Cheese +₹40" and taps "Add to Cart".
8. Toast appears: "Paneer Tikka added to cart". Cart badge updates.
9. User navigates to `/cart`. Items visible with quantity steppers, veg dots, fee breakdown. User enters "WELCOME20" coupon → mock validated, discount applied.
10. User taps "Proceed to Checkout". Address form appears (manual entry for guest). User enters street, city, pincode, phone.
11. User selects "Cash on Delivery" payment method. Place Order button becomes active.
12. User taps "Place Order". Order created with `status = 'pending'`, `payment_status = 'pending'`.
13. Confirmation page shows: "Order Placed!" with order number, ETA 35-45 min, "Track Order" CTA.
14. User taps "Track Order". Static timeline shows: Confirmed (active), Preparing, Ready for Pickup, Picked Up, Delivered.
15. (Guest cannot view order history; user is prompted to sign up.)

### Journey 8.2 — Logged-In User Places Order and Views History
1. User logs in. Auth persists across refresh.
2. User browses restaurants, adds 2 items to cart. Cart persists to `localStorage`.
3. User navigates to `/cart`, changes quantity from 1 → 3 using stepper. Total recalculates.
4. User taps "Proceed to Checkout". Saved addresses shown as radio cards. User selects "Home" address.
5. User selects "Wallet" payment method. Place Order button active.
6. User taps "Place Order". Backend validates items, calculates fees, creates order, marks `payment_status = 'paid'`.
7. Confirmation page shows order summary and "Track Order" CTA.
8. User navigates to `/orders`. Order appears in list with status badge "Confirmed" and reorder button.
9. User taps order. Detail page shows item list, fee breakdown, address, mock timeline, and "Cancel Order" button (visible because status is `confirmed`).
10. User taps "Cancel Order". Confirmation modal appears. User confirms. Toast: "Order cancelled". Status updates to `cancelled`.
11. User navigates to `/profile`. Real data from `/api/v1/me` displayed: name, email, phone, wallet balance (if reliable), saved addresses, recent orders.

### Journey 8.3 — Cross-Restaurant Cart Guard
1. User adds Paneer Tikka from Restaurant A.
2. User browses Restaurant B, taps "Add" on a pizza.
3. Frontend detects different `restaurant_id` in cart vs new item.
4. Alert modal appears: "Your cart has items from Spice Garden. Start a new cart for Pizza Palace?"
5. User taps "Start New Cart". Previous cart cleared; pizza added.
6. Cart badge shows 1 item. Toast: "Cart updated".

### Journey 8.4 — Order State Machine Enforcement
1. Admin attempts to PATCH order status from `delivered` → `pending` via API.
2. Server rejects with 400: "Invalid status transition: delivered → pending".
3. Frontend API client surfaces error toast.

### Journey 8.5 — Responsive Usage on Mobile
1. User opens app on phone (<640px).
2. Bottom nav visible: Home, Search, Cart, Orders, Profile. Active tab highlighted.
3. User taps Search → restaurant list. Horizontal scrollable cuisine chips. Cards in single column.
4. User taps restaurant → detail page. Menu items in single column. Veg-only toggle prominent.
5. User taps "Add" → customization bottom sheet slides up from bottom 70% of screen.
6. User taps Cart → bottom nav cart badge reflects item count. Checkout form scrolls smoothly. Tap targets >= 48px.

## 9. Technical Coverage

### Backend
- `user-svc`: `GET /api/v1/me` (inherited from PR.02) must return all profile fields reliably.
- `restaurant-svc`: Menu endpoint DB fallback (inherited from PR.02) must serve real menu data with `menu_categories` + `menu_items` join. `GET /api/v1/restaurants` with optional query params for filtering (inherited from PR.02).
- `order-svc`: Order creation with validation, simulated payment, state machine, cancellation (all inherited from PR.03). No new backend endpoints required for PR.04 unless review listing endpoint is missing.
- `restaurant-svc`: Add `GET /api/v1/restaurants/{id}/reviews` if missing (required for review section).
- `payment-svc`: Mock wallet balance endpoint for checkout display.
- `user-svc`: Address listing endpoint for checkout saved addresses.

### Frontend
- Next.js App Router pages: `/`, `/restaurants`, `/restaurants/[id]`, `/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/orders/confirmation/[id]`, `/profile`.
- Zustand cart store with `localStorage` persistence (inherited from PR.03).
- Zustand auth store with hydration from `/api/v1/me` (inherited from PR.02).
- Axios interceptor for Bearer token injection (inherited from PR.02).
- React Error Boundary on every page (`error.tsx` in App Router or custom boundary).
- Tailwind `dark:` class activation via class strategy + `localStorage`.
- Toast system: global `<ToastProvider />` with imperative `toast.show()` API.
- Skeleton components: `<SkeletonCard />`, `<SkeletonMenuItem />`, `<SkeletonText />` (create or reuse from PR.02).
- Custom SVG empty state illustrations.
- Category tabs with scroll-to-section using `scrollIntoView`.
- Veg-only toggle: client-side filter on `is_veg` field.
- Bestseller badge: client-side flag on top 3 items per category (or `is_bestseller` field if seeded).
- Spice level: render 1-5 chili icons based on `spice_level` field (1-5 integer).
- Jain tag: render "J" pill if `is_jain = true`.
- Thali/combo builder: special UI for items with `item_type = 'combo'` showing constituent items.
- Responsive breakpoints: `sm:`, `md:`, `lg:`, `xl:`, `2xl:`, `3xl:` grid columns and layout shifts.
- Bottom nav: fixed bottom-0, z-50, active route highlight via `usePathname`.
- Intersection Observer for infinite scroll on restaurant list.
- `navigator.geolocation.getCurrentPosition()` for location auto-detection.

### Data
- Uses existing `restaurants`, `menu_categories`, `menu_items`, `users`, `orders`, `order_status_history` tables.
- Uses existing `reviews` table (seeded with realistic data for PR.04).
- No new migrations required for core schema.
- Seed data: add 3-5 reviews per restaurant with realistic text.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for restaurant list, skeleton rows for menu, skeleton text for profile/order detail. Skeletons match real content dimensions (no layout shift).
- **Error states:** Error boundary on every page with friendly message, retry button, and correlation ID. API failure toasts with actionable messages.
- **Empty states:** Custom SVG illustrations + message + CTA for empty cart, empty orders, empty search results. No blank white screens.
- **Success states:** Order confirmation page with checkmark icon, order number, ETA. Toast on add-to-cart, order placed, cancellation.
- **Design system:** BhojanGo palette applied globally. Manrope + Inter typography. Consistent 4px spacing grid. Lucide icons only. Badge anatomy: rounded-full, px-3, py-1, font-semibold. Card anatomy: 16:10 image, rounded-xl, gradient overlay, name h3, cuisine chips, rating badge, delivery time badge.
- **Indian food specifics:** Green dot (veg), red dot (non-veg) on every menu item and cart row. Jain "J" pill. 1-5 chili icons for spice. Thali/combo builder. Regional cuisine label. ₹ symbol for all prices.
- **Responsive:** Mobile-first. Bottom nav on <640px. Tablet: 2-3 columns. Laptop: 4 columns. TV: 5-6 columns. Max width 1920px centered.
- **Dark mode:** Toggle in navbar. Persisted in `localStorage`. Respects `prefers-color-scheme`. No black-on-black text.
- **Accessibility:** Radio groups have `role="radiogroup"`. Form inputs have associated labels. Buttons have clear focus states. Tap targets >= 48px on mobile.
- **Toast/snackbar:** Bottom-right desktop, bottom-center mobile. Auto-dismiss 3s. Actionable messages.

## 11. Data / Model Coverage

- `orders` table (existing): all fields inherited from PR.03.
- `order_status_history` table (existing): inherited from PR.03.
- `reviews` table (existing): `id`, `restaurant_id`, `user_id`, `rating`, `comment`, `created_at`. Seed 3-5 reviews per restaurant for PR.04.
- `menu_items` table (existing): ensure `is_veg`, `is_jain`, `spice_level`, `item_type` fields are present and seeded.
- `users` table (existing): `full_name`, `email`, `phone`, `avatar_url`, `loyalty_points`.
- `addresses` table (existing): `user_id`, `label`, `street`, `city`, `pincode`, `phone`, `is_default`.
- `wallet` table (existing): `user_id`, `balance`.
- No new tables required.

## 12. Role / Permission Coverage

- `customer` role: Can browse, add to cart, checkout, view own orders, cancel own pending/confirmed orders, view profile, view wallet.
- Guest (unauthenticated): Can browse, add to cart, checkout with manual address, view order confirmation, but cannot view order history or profile.
- `restaurant_owner`, `delivery_partner`, `admin`, `super_admin`, `support`: Not involved in customer ordering flow for PR.04.
- Order endpoints enforce ownership: `GET /api/v1/orders` returns only current user's orders. Order detail validates ownership.

## 13. Performance / Reliability / Security Coverage

### Performance
- Restaurant list infinite scroll fetches in batches (default 24 items). No front-loading of all 96 restaurants at once.
- Menu DB fallback query uses indexed `restaurant_id` join on `menu_categories` + `menu_items`.
- Cart operations are client-side (Zustand + localStorage); instant UI response.
- Skeleton loaders prevent layout shift and perceived slowness.
- Unsplash images loaded with `next/image` and `sizes` prop for responsive optimization.

### Reliability
- Menu endpoint DB fallback ensures menu is never unavailable due to OpenSearch.
- Error boundaries prevent entire page crash on any API failure.
- Guest cart survives refresh via localStorage. Schema versioned for future migration.
- Network failure during checkout: show error toast, keep form state, allow retry.

### Security
- JWT access token in `httpOnly` cookie prevents XSS token theft (preferred). If localStorage fallback used, document trade-off.
- `GET /api/v1/me` validates JWT signature and expiry.
- No raw payment credentials transmitted (mock only).
- `user_id` on order set server-side from JWT `sub`, not from request body.

## 14. Novelty / Differentiation Coverage

At score 4, novelty is present in demo-visible touches:
- **Indian food-specific UI** — Veg/non-veg dots, Jain tag, spice level chilies, thali builder, regional cuisine labels. These are visible differentiators for the Indian market.
- **Trust badges** — FSSAI Verified, Freshly Prepared, Under 30 min on restaurant cards.
- **Fee transparency** — Full breakdown visible in cart and checkout.
- **Design system** — Distinctive BhojanGo palette and typography separate it from generic Tailwind templates.
- **Bestseller badges** — Visual hierarchy on menu.
- **Cross-restaurant cart guard** — Prevents accidental mixing.
- **Mock tracking timeline** — Static steps give users a sense of progress.

Full novelty differentiators (loyalty, meal rescue, group ordering, nutrition info) remain deferred to PR.05+.

## 15. Implementation Work Items

### IP.PR.04.001 — Auth Persistence Polish (httpOnly Cookie or Secure localStorage)
- **Category:** Frontend
- **Implementation Scope:** Audit existing auth persistence from PR.02/03. Ensure the token storage strategy (httpOnly cookie preferred, localStorage fallback) works reliably across all page refreshes and route navigations. On app bootstrap (root layout or provider), call `GET /api/v1/me` and hydrate Zustand auth store. If the call fails with 401, clear storage and redirect to `/login` only for protected routes. On logout, unconditionally clear cookie/localStorage and reset auth store. Ensure no redirect loops on `/profile` or `/orders`.
- **Acceptance Criteria:**
  1. User logs in, refreshes page, remains authenticated on all routes.
  2. Navbar shows user name/avatar after refresh without re-login.
  3. Logout clears auth state and redirects to `/`.
  4. No redirect loops on protected pages.
- **Evidence Required:** Screen recording: login → refresh → `/profile` renders user data → navigate to `/orders` → logout → `/` shown.
- **Priority:** P0
- **Effort:** S
- **Dependency:** PR.02 auth persistence, PR.03 `/api/v1/me`
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.002 — Guest Cart Flow End-to-End
- **Category:** Frontend + Backend
- **Implementation Scope:** Ensure guest cart persists in `localStorage` and survives page refresh. On checkout, if user is unauthenticated, show manual address form (no saved addresses). Allow placing order without `user_id` (stored as null in DB). After order placement, show confirmation page with order number. Guest user cannot view `/orders` (show login prompt with CTA). On login, optionally merge localStorage cart to backend or keep local. Cart badge in navbar and bottom nav reflects persisted count on reload.
- **Acceptance Criteria:**
  1. Add 3 items as guest → refresh page → cart still contains 3 items.
  2. Guest can proceed to checkout, enter address, select COD, place order.
  3. Guest sees order confirmation but cannot view order history.
  4. Login prompt shown on `/orders` for guest users with "Login to track orders" CTA.
- **Evidence Required:** Screen recording: guest adds items → refresh → checkout → place order → confirmation → `/orders` shows login prompt.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.001 (localStorage cart), IP.PR.03.006 (order creation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.003 — Homepage CTA Wired + Location Auto-Detection
- **Category:** Frontend
- **Implementation Scope:** Wire the "Find Food" button on the homepage to navigate to `/restaurants`. On page load, call `navigator.geolocation.getCurrentPosition()`. If permitted, use a mock reverse-geocode function (or free Nominatim API call) to get city name. Update the hero subtitle to "Delivering to {city}" and pre-fill the restaurant list search or filter. If geolocation denied or unavailable, show default city "Your City" and allow manual input. Add fallback for browsers without geolocation API.
- **Acceptance Criteria:**
  1. Clicking "Find Food" navigates to `/restaurants`.
  2. On browsers supporting geolocation, city auto-detects within 2s.
  3. Hero subtitle updates to detected city name.
  4. Graceful fallback if geolocation is denied or unavailable.
- **Evidence Required:** Screen recording: load homepage → city detected → click "Find Food" → restaurant list loads.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.04.001 (auth persistence)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.004 — Restaurant Search/Filter/Cuisine Chips + Infinite Scroll
- **Category:** Frontend
- **Implementation Scope:** Ensure the restaurant list page has all discovery tools working reliably: (1) sticky debounced search bar (200ms) filtering client-side by name + cuisine; (2) horizontal scrollable cuisine chips (Indian, Chinese, Pizza, Burger, South Indian, Biryani, Desserts) with toggle active state; (3) filter chips: "4+ Rating", "Veg Only", "Under 30 min"; (4) infinite scroll via Intersection Observer fetching next page from `GET /api/v1/restaurants?page=N&limit=24`; (5) "Clear all filters" button resetting all active filters. Ensure filters combine correctly (AND within category, OR across categories as appropriate).
- **Acceptance Criteria:**
  1. Typing "dosa" filters list within 200ms.
  2. Clicking "Pizza" chip filters to pizza restaurants.
  3. "4+" filter shows only restaurants with rating >= 4.0.
  4. Scrolling to bottom triggers infinite scroll loading next 24 restaurants.
  5. "Clear all" resets search, chips, and filters.
- **Evidence Required:** Screen recording showing search, chip filter, rating filter, infinite scroll, and clear-all.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.02.015 (API filter params), IP.PR.02.008 (search)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.005 — Menu DB Fallback + Category Tabs + Veg Toggle + Customization
- **Category:** Frontend
- **Implementation Scope:** On restaurant detail page: (1) menu must load reliably via DB fallback (already implemented in PR.02); add skeleton rows while loading and error boundary with retry on failure. (2) Add sticky category tabs (Starters | Mains | Breads | Desserts | Combos) at top of menu; clicking tab scrolls to that category section via `scrollIntoView`. (3) Add "Veg Only" toggle switch next to tabs; client-side filter on `is_veg = true`. (4) Add "Bestseller" badge (star icon + text) on top 3 items per category (client-side logic or `is_bestseller` field). (5) Tapping a menu item opens a customization modal (bottom sheet on mobile, centered modal on desktop) showing item image, description, price, add-ons list with checkboxes, quantity stepper, and "Add to Cart" button. (6) Add delivery fee banner: "Delivery in 35-45 min · ₹30 fee". (7) Add review section below menu with 3-5 seeded reviews per restaurant.
- **Acceptance Criteria:**
  1. Menu loads with skeletons, then real items with categories.
  2. Category tabs scroll to correct section on click.
  3. Veg-only toggle filters to veg items only.
  4. Bestseller badges visible on top 3 items per category.
  5. Customization modal opens with add-ons, quantity, and add-to-cart CTA.
  6. Delivery fee banner visible.
  7. Review section shows 3-5 reviews with star ratings.
- **Evidence Required:** Screenshots: menu with tabs, veg toggle, bestseller badges, customization modal, delivery banner, reviews.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.02.001 (menu fallback), IP.PR.04.017 (review seed data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.006 — Cart with Empty State + Skeleton + Fee Breakdown
- **Category:** Frontend
- **Implementation Scope:** Polish the cart page: (1) skeleton loader while cart hydrates from localStorage or API. (2) item rows with thumbnail (48x48), name, price per unit, quantity stepper (+ / - buttons, min 1, remove at 0 with confirmation toast), line total, veg/non-veg dot. (3) sticky footer with full fee breakdown: Items Total, Delivery Fee, Platform Fee, Tax, Discount, Grand Total. Numbers right-aligned, 2 decimal places, Grand Total in bold/large font. (4) coupon input field above total; mock validation: "WELCOME20" gives 20% off (client-side calculation). Invalid coupon shows red text "Invalid coupon code". (5) Empty state: custom SVG illustration (sad pizza or empty plate), heading "Your cart is empty", subtext "Looks like you haven't added anything yet", "Browse Restaurants" CTA. (6) "Proceed to Checkout" primary CTA; disabled if cart empty.
- **Acceptance Criteria:**
  1. Cart shows skeleton while hydrating.
  2. All items display with correct quantities, prices, and veg dots.
  3. Full fee breakdown visible with right-aligned numbers.
  4. "WELCOME20" coupon applies 20% discount; invalid coupon shows error.
  5. Empty cart shows illustration + message + browse CTA.
  6. Checkout CTA disabled when cart empty.
- **Evidence Required:** Screenshots: populated cart, empty cart, fee breakdown, coupon applied, coupon error.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.002 (cart page UI), IP.PR.03.015 (fee breakdown)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.007 — Checkout with Address + Payment Mock + Validation + Summary
- **Category:** Frontend
- **Implementation Scope:** Polish checkout page: (1) If authenticated, show saved addresses as radio cards (fetched from `GET /api/v1/addresses`); pre-select default address. If guest, show manual address form (street, city, pincode, phone, landmark) with inline validation on blur. (2) Payment method radio group: Card, UPI, Wallet, COD. Card and UPI show disabled mock sub-forms with "Coming soon" label. Wallet shows current balance. COD requires no extra input. (3) Order summary accordion (collapsible on mobile, sticky sidebar on desktop) showing item list, fee breakdown, and grand total. (4) "Place Order" button disabled until: address valid, payment method selected, cart non-empty. (5) Inline validation errors in red text below fields. (6) Loading spinner on button while placing order. (7) Error toast on failed order creation.
- **Acceptance Criteria:**
  1. Authenticated user sees saved address radio cards.
  2. Guest sees manual address form with inline validation.
  3. Payment method radio cards show correct mock states.
  4. Order summary visible with full breakdown.
  5. Place Order disabled until all fields valid.
  6. Error toast shown on network or validation failure.
- **Evidence Required:** Screenshots: checkout with saved addresses, checkout with validation errors, payment selector, order summary, disabled Place Order state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.004 (checkout form), IP.PR.03.005 (payment radio)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.008 — Order Confirmation + Order History
- **Category:** Frontend
- **Implementation Scope:** (1) Order confirmation page (`/orders/confirmation/[id]`): large checkmark icon, "Order Placed!" heading, order number, restaurant name, ETA (static 35-45 min), item list, delivery address, payment method. Two CTAs: "Track Order" (links to `/orders/[id]`) and "Order More" (links to `/restaurants`). Use brand primary color for checkmark. (2) Order history page (`/orders`): fetch from `GET /api/v1/orders?page=1&limit=20`. Display cards: restaurant image, name, total, status badge (colored pill), date, and "Reorder" button. Sort by `created_at DESC`. Empty state: "No orders yet" illustration + "Browse Restaurants" CTA. Reorder button pre-fills cart with same items (or shows "Coming soon" modal if reorder logic not built).
- **Acceptance Criteria:**
  1. Confirmation page shows all order details, order number, and ETA.
  2. "Track Order" navigates to order detail.
  3. Order history lists past orders with status badges.
  4. Empty state shown for new users.
  5. Reorder button visible but disabled / shows "Coming Soon". Functional reorder is out of scope for PR.04 and belongs to PR.05+.
- **Evidence Required:** Screenshots: confirmation page, order history with multiple statuses, empty state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.009 (confirmation), IP.PR.03.010 (order list)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.009 — Mock Tracking Timeline (Static)
- **Category:** Frontend
- **Implementation Scope:** On order detail page (`/orders/[id]`): replace plain text status with a vertical stepper timeline. Steps: Confirmed, Preparing, Ready for Pickup, Picked Up, Delivered. Current step highlighted (filled circle + bold text). Past steps green with checkmark icon. Future steps gray. Steps are static; only `status` field determines current step. Show estimated time per step (static mock times). Add "Contact Support" button (opens support modal or mailto link). Add delivery ETA text: "Estimated delivery: 35-45 min". If status is `cancelled`, show cancellation banner instead of timeline.
- **Acceptance Criteria:**
  1. Timeline shows correct current step based on order status.
  2. All past steps visually marked complete (green + checkmark).
  3. Future steps gray and inactive.
  4. Contact Support button visible and functional.
  5. Cancelled order shows cancellation banner, not timeline.
- **Evidence Required:** Screenshots of order detail for statuses: confirmed, preparing, delivered, cancelled.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.011 (order detail with timeline)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.010 — Profile Page with Real Data
- **Category:** Frontend
- **Implementation Scope:** Fix `/profile` page to display real data without redirect loops. Fetch from `GET /api/v1/me`. Display: full name, email, phone, avatar (or initials fallback), wallet balance (P1, from wallet endpoint if reliable; otherwise hidden), saved addresses list, recent orders summary (last 3), and loyalty points if available. Use skeleton loaders while fetching. Error boundary for API failure. Empty states for no addresses / no orders.
- **Acceptance Criteria:**
  1. Profile page shows real user data from `/api/v1/me`.
  2. Wallet balance displayed prominently.
  3. Saved addresses listed with labels (Home, Work, etc.).
  4. Recent orders shown with status badges.
  5. Skeleton loaders shown while fetching; error boundary on failure.
- **Evidence Required:** Screenshot of profile page showing all sections. Screenshot of skeleton state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.04.001 (auth persistence polish)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.011 — Design System Application (Palette, Font, Spacing, Badges, Cards)
- **Category:** Frontend
- **Implementation Scope:** Apply the BhojanGo design system across all pages: (1) Add CSS custom properties in `globals.css` or Tailwind config for: `--color-primary: #E65100` (Warm Saffron), `--color-secondary: #2E7D32` (Trust Green), `--color-accent: #FFB300` (Nugget Gold), `--color-neutral: #F7F5F2` (Cream), `--color-dark: #1A1A1A` (Near Black). Map to Tailwind theme colors. (2) Import Manrope (headings, weight 600-800) and Inter (body, weight 400-500) from Google Fonts. Apply via Tailwind `font-heading` and `font-body`. (3) Define spacing tokens: 4px base grid. Cards: 16px internal padding, 24px gap. Buttons: min-height 48px, min-width 120px, border-radius 12px. (4) Badge standard: border-radius 40px (rounded-full), padding 4px 12px, font-weight 600, font-size 12px. Variants: "New" (primary bg), "Bestseller" (accent bg + star icon), "Veg" (green bg + dot), "Under 30 min" (secondary bg + clock). (5) Card anatomy: Image 16:10 aspect ratio, rounded-xl top corners, gradient overlay from bottom (black 40% opacity), name as h3 (Manrope, semibold), cuisine types as chip row, rating badge absolute top-right (gold bg), delivery time badge absolute bottom-right (dark bg + clock icon). (6) Trust badges on cards: "FSSAI Verified" (shield icon), "Freshly Prepared" (leaf icon), "Under 30 min" (bolt icon). (7) Replace all raw emoji with Lucide React icons. Ensure consistent 24px icon size, 1.5px stroke.
- **Acceptance Criteria:**
  1. All pages use brand palette colors (no generic Tailwind emerald/green).
  2. Typography uses Manrope + Inter.
  3. Consistent spacing across all components (no random Tailwind values).
  4. All badges follow standard anatomy.
  5. All cards follow standard anatomy.
  6. No raw emoji in UI; only Lucide icons.
- **Evidence Required:** Screenshots of homepage, restaurant list, restaurant detail, cart, checkout in light mode showing design system application.
- **Priority:** P0
- **Effort:** L
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.012 — Indian Food Delivery UI Specifics (Veg Dots, Jain, Spice, Thali Builder)
- **Category:** Frontend
- **Implementation Scope:** Add Indian food-specific UI elements: (1) Mandatory veg/non-veg dot on every menu item and cart item row: green circle for veg, red circle for non-veg. Use Lucide `Circle` icon filled with brand green/red. (2) Jain tag: small "J" pill/badge for items with `is_jain = true`. (3) Spice level: 1-5 red chili icons (use Lucide `Flame` or custom chili SVG) based on `spice_level` field (1-5 integer). Show as "Mild" (1), "Medium" (2-3), "Hot" (4-5) with tooltip. (4) Thali/combo builder: for items with `item_type = 'combo'`, show constituent items as a list with checkboxes (all selected by default, unchecking reduces price). (5) Regional cuisine label: show "North Indian", "South Indian", "Street Food", etc. on restaurant cards and detail header. (6) All monetary values display with ₹ symbol. Use `NumberFormatter` or `Intl.NumberFormat('en-IN')` for Indian locale formatting. (7) Add "Veg Only" filter chip on restaurant list.
- **Acceptance Criteria:**
  1. Every menu item and cart row shows green/red veg dot.
  2. Jain items show "J" pill.
  3. Spice level shows 1-5 chili icons with mild/medium/hot label.
  4. Combo items show thali builder with selectable constituent items.
  5. All prices display in ₹ with Indian locale formatting.
  6. Regional cuisine labels visible on cards and detail.
- **Evidence Required:** Screenshots: menu with veg dots/spice/Jain, cart with veg dots, combo builder, price in ₹.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.04.011 (design system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.013 — Responsive Layout (Mobile Bottom Nav, Tablet, TV)
- **Category:** Frontend
- **Implementation Scope:** Ensure responsive layout across all breakpoints: (1) Mobile-first (<640px): single column layouts, bottom nav visible (`sm:hidden` on desktop nav), hamburger menu hidden when bottom nav present. Tap targets >= 48px. Font sizes slightly larger for thumb readability. (2) Tablet (640px-1024px): `md:grid-cols-2` for restaurant list, `lg:grid-cols-3` for larger tablets. Checkout form uses 2-column layout. (3) Laptop (1024px-1440px): `xl:grid-cols-4` for restaurant list. Two-column checkout (form left, summary right). (4) TV/Large desktop (>1440px): `2xl:grid-cols-5`, `3xl:grid-cols-6`. Max content width 1920px centered with `mx-auto`. (5) Ensure all pages (`/`, `/restaurants`, `/restaurants/[id]`, `/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/profile`) render correctly at all breakpoints. Use Chrome DevTools device toolbar to verify.
- **Acceptance Criteria:**
  1. Mobile (<640px) shows bottom nav, single column, tap targets >= 48px.
  2. Tablet (768px) shows 2-3 column grid for restaurants.
  3. Laptop (1280px) shows 4 column grid.
  4. TV (1920px+) shows 5-6 column grid, content centered.
  5. No horizontal scroll at any breakpoint.
- **Evidence Required:** Screenshots of `/restaurants` at 375px, 768px, 1280px, 1920px viewports.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.02.014 (mobile bottom nav)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.014 — Toast/Snackbar Component Integrated Globally
- **Category:** Frontend
- **Implementation Scope:** Create a global `<ToastProvider />` component using React Context or Zustand. Provide imperative API: `toast.success(message)`, `toast.error(message)`, `toast.info(message)`. Toast appears as a snackbar: colored left border (green for success, red for error, blue for info), message text, close button. Position: bottom-right on desktop (`bottom-4 right-4`), bottom-center on mobile (`bottom-4 left-1/2 -translate-x-1/2`). Max width 400px desktop, full width minus padding mobile. Auto-dismiss after 3 seconds with progress bar. Support action buttons (e.g., "Undo" for cart remove). Trigger toasts on: add-to-cart, remove-from-cart, login success, login error, order placed, order cancelled, coupon applied, coupon invalid, network error, validation error.
- **Acceptance Criteria:**
  1. Toast appears on add-to-cart with "Item added to cart" message.
  2. Toast appears on login error with red styling.
  3. Toast auto-dismisses after 3s.
  4. Mobile toast is centered and full-width.
  5. Desktop toast is bottom-right with max-width 400px.
- **Evidence Required:** Screen recording showing toasts: success (add-to-cart), error (login failure), info (coupon applied).
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.015 — Error Boundaries + Loading Skeletons + Empty States
- **Category:** Frontend
- **Implementation Scope:** (1) Add React Error Boundary to every page in the core loop: `/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/profile`, `/restaurants/[id]`. Use Next.js App Router `error.tsx` files or wrap page content in custom `<ErrorBoundary />`. Error UI: heading "Something went wrong", subtext with error message (sanitized), "Retry" button, and support contact link. Log error with correlation ID. (2) Ensure skeleton loaders exist on all list pages: restaurant list (skeleton cards), menu (skeleton rows), orders (skeleton cards), profile (skeleton text blocks). No blank white screens during loading. (3) Ensure empty states exist for: empty cart, empty orders, empty search results, empty address list. Each with custom SVG illustration, heading, subtext, and CTA button.
- **Acceptance Criteria:**
  1. Simulating API failure on any page shows error boundary UI, not blank page.
  2. All list pages show skeletons while loading.
  3. Empty cart shows illustration + "Browse Restaurants" CTA.
  4. Empty orders show illustration + "Browse Restaurants" CTA.
  5. Empty search shows illustration + "Clear filters" CTA.
- **Evidence Required:** Screenshots: error boundary UI, skeleton state for restaurant list/menu/orders, empty states for cart/orders/search.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.02.005 (skeletons), IP.PR.02.007 (error boundary)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.016 — Dark Mode Toggle
- **Category:** Frontend
- **Implementation Scope:** Add a sun/moon icon toggle button in the navbar (top-right, visible on desktop; inside bottom nav or hamburger on mobile). On toggle, add/remove `dark` class on `<html>` element (Tailwind class strategy). Persist preference in `localStorage` under key `bhojango-theme`. On initial load, check `localStorage` first, then fall back to `prefers-color-scheme: dark`. Ensure all pages in scope render correctly in dark mode: no black-on-black text, no missing `dark:` variants on backgrounds, text, borders, or cards. Update `tailwind.config.ts` if `darkMode: 'class'` is not already set. Verify brand palette has dark variants (e.g., dark mode primary is lighter saffron `#FF8A50`).
- **Acceptance Criteria:**
  1. Toggle switches between light and dark modes across all pages.
  2. Preference persists across browser sessions.
  3. Respects OS dark mode preference on first visit.
  4. No visual regressions (contrast, readability) in dark mode on any page.
  5. Brand colors adapt to dark mode (primary becomes lighter).
- **Evidence Required:** Side-by-side screenshots of `/restaurants`, `/cart`, `/checkout`, `/orders` in light and dark mode.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.04.011 (design system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.04.017 — Review Seed Data Generation
- **Category:** Data
- **Implementation Scope:** Create or extend the seed script to generate 3-5 realistic reviews per restaurant. Each review should have: `restaurant_id`, `user_id` (random from seeded users or null for anonymous), `rating` (2-5 stars, weighted toward 4-5), `comment` (realistic text about food quality, delivery time, packaging), `created_at` (random date within last 6 months). Use realistic reviewer names. Ensure `restaurant-svc` has `GET /api/v1/restaurants/{id}/reviews` endpoint returning paginated reviews. If endpoint missing, add it. Reviews display on restaurant detail page: average rating, star distribution, individual review cards with name, date, rating stars, comment text.
- **Acceptance Criteria:**
  1. Every restaurant has 3-5 seeded reviews in DB.
  2. `GET /api/v1/restaurants/{id}/reviews` returns reviews with 200.
  3. Restaurant detail page shows average rating and review list.
  4. Reviews have realistic text and varied ratings.
- **Evidence Required:** Screenshot of restaurant detail showing 3+ reviews. `curl` output of reviews endpoint.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Auth persists across refresh with no session loss; logout clears state cleanly.
- [ ] Guest cart survives refresh and can checkout without login; order confirmation shown; guest cannot view `/orders`.
- [ ] Homepage "Find Food" button navigates to `/restaurants`; location auto-detects within 2s.
- [ ] Restaurant list supports debounced search, cuisine chips, rating/veg/time filters, and infinite scroll.
- [ ] Restaurant detail loads menu from DB fallback with category tabs, veg-only toggle, bestseller badges, item customization modal, delivery fee banner, and 3-5 seeded reviews.
- [ ] Cart page shows skeleton loader, item rows with quantity steppers and veg dots, full fee breakdown, coupon mock validation, empty state with illustration, and disabled checkout CTA when empty.
- [ ] Checkout page shows saved address radio cards (or manual form for guests), payment method radio with mock sub-forms, order summary, disabled Place Order until valid, inline validation errors.
- [ ] Order confirmation page shows order number, ETA, "Track Order" and "Order More" CTAs.
- [ ] Order history page lists past orders with status badges, dates, totals, and reorder button; empty state for no orders.
- [ ] Order tracking page shows static timeline with correct current step, contact support button, and ETA text.
- [ ] Profile page displays real data from `/api/v1/me` including name, email, phone, addresses, and recent orders. Wallet balance shown only if wallet endpoint is reliable.
- [ ] Design system applied globally: BhojanGo palette, Manrope + Inter typography, consistent spacing, badge anatomy, card anatomy, Lucide icons only.
- [ ] Indian food specifics visible: green/red veg dots, Jain "J" pill, 1-5 chili spice icons, thali/combo builder, regional cuisine labels, all prices in ₹.
- [ ] Responsive layout works on mobile (bottom nav, single column), tablet (2-3 columns), laptop (4 columns), and TV (5-6 columns).
- [ ] Toast component provides feedback for add-to-cart, login, order placed, cancellation, coupon, and errors.
- [ ] Loading skeletons on all list pages; empty states with custom illustrations; error boundaries on all pages.
- [ ] Dark mode toggle works across all pages, persists in `localStorage`, respects OS preference.
- [ ] No blank white screens on any critical page.
- [ ] Core loop is traversable end-to-end reliably: login/guest → browse → restaurant → menu → add item → cart → checkout → simulated payment → confirmation → mock tracking.

## 17. Evidence Required

- Screen recording: guest opens app → auto-detects location → "Find Food" → browse restaurants → filter by cuisine → open restaurant → toggle veg only → add item with customization → view cart → apply coupon → checkout with address → COD → place order → confirmation → track order → see timeline.
- Screen recording: logged-in user logs in → browse → add items → checkout with saved address → Wallet payment → confirmation → view order history → tap order → see timeline → cancel order → toast confirmation.
- Screenshots of all pages in light mode showing design system application (palette, font, spacing, badges, cards).
- Side-by-side screenshots of `/restaurants`, `/cart`, `/checkout` in light and dark mode.
- Screenshots of responsive layout at 375px, 768px, 1280px, 1920px viewports.
- Screenshots: empty cart, empty orders, empty search results with illustrations.
- Screenshots: error boundary UI on `/cart`, `/checkout`, `/orders`.
- Screenshots: toast notifications (success, error, info).
- Screenshots: menu with veg dots, Jain tag, spice level chilies, combo builder.
- `curl` output: `GET /api/v1/restaurants/{id}/reviews` returning 3-5 reviews.
- DevTools screenshot: localStorage shows `bhojango-theme` and `bhojango-cart-guest` keys.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, OpenSearch).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- Google Fonts (Manrope + Inter).
- Unsplash (free source URLs for food images).
- Lucide React (icon library).

### Internal Dependencies
- **PR.03 must be complete:** guest cart, checkout, simulated payment, order creation, state machine, confirmation, order list, order detail with timeline, cancellation, delivery fee, fee breakdown.
- **PR.02 must be complete:** menu DB fallback, auth persistence, `/api/v1/me`, skeleton components, dark mode classes, mobile bottom nav, search, cuisine chips, Unsplash images, trust badges.
- `packages/ui` shared component package must build.
- Existing seeded data (restaurants, menu categories, menu items, users) must be present.
- `orders`, `order_status_history`, `reviews` tables must exist.

## 19. Risks / Blockers

- **Profile page redirect loop risk.** If auth persistence is flaky (PR.02/03), `/profile` may redirect to login even when authenticated. Mitigation: audit auth hydration logic; ensure `/api/v1/me` is called before route guard decisions.
- **Design system conflicts with existing Tailwind usage.** Replacing generic colors may break existing component styles. Mitigation: use CSS custom properties scoped to `:root` and `html.dark`, map to Tailwind `extend colors`, update components incrementally.
- **Review seed data requires realistic text generation.** If no seed script exists for reviews, manual SQL insert or faker script needed. Mitigation: use a small set of 20 realistic review templates and randomly assign.
- **Guest order without `user_id` may break foreign key assumptions.** Some tables or queries may assume `user_id` is non-null. Mitigation: verify `orders.user_id` allows NULL. Verify order list endpoint filters by `user_id` and handles NULL gracefully (guest orders excluded from list — this is acceptable).
- **Dark mode may have incomplete `dark:` variants.** Rapid application of dark mode may miss edge cases. Mitigation: systematic page-by-page audit with DevTools.
- **Responsive TV breakpoints may be unused in existing code.** Adding `2xl:` and `3xl:` breakpoints requires Tailwind config update. Mitigation: extend `tailwind.config.ts` with `screens: { '3xl': '1920px' }`.
- **Thali/combo builder may require `menu_items` schema changes.** If `item_type` or combo constituent fields are missing, mock the UI with static data. Mitigation: check schema first; if fields missing, use mock combo items for demo.
- **Coupon mock validation is client-side only.** Users can tamper with local coupon logic. This is acceptable for PR.04 (demo-only); real coupon system is PR.05+.

## 20. Exit Criteria

- All P0 work items (IP.PR.04.001 through IP.PR.04.015) implemented and verified.
- Core loop is traversable reliably end-to-end by a guest user without login.
- Core loop is traversable reliably end-to-end by a logged-in user.
- Every screen in the loop has loading, error, empty, and success states.
- Design system is applied across all pages.
- Indian food delivery UI specifics are visible on menu, cart, and checkout.
- Responsive layout verified on mobile, tablet, laptop, and TV breakpoints.
- Toast component provides feedback for all major actions.
- Dark mode toggle works and persists.
- No blank white screens on any critical page.
- Evidence screenshots/recordings captured per Section 17.
- PR.04 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.03)

PR.04 directly depends on PR.03 achievements:
- **IP.PR.03.001** — Guest Cart Persistence in localStorage: required for guest checkout flow.
- **IP.PR.03.002** — Cart Page UI with Quantity Stepper: foundation for cart polish (IP.PR.04.006).
- **IP.PR.03.003** — Cross-Restaurant Cart Guard: must work reliably in demo.
- **IP.PR.03.004** — Checkout Form with Address Fields: foundation for checkout polish (IP.PR.04.007).
- **IP.PR.03.005** — Payment Method Radio Mock: foundation for payment polish (IP.PR.04.007).
- **IP.PR.03.006** — Order Creation Backend Endpoint: must create orders reliably for confirmation and tracking.
- **IP.PR.03.007** — Simulated Payment Processing: order confirmation depends on mock payment success.
- **IP.PR.03.008** — Order State Machine: tracking timeline depends on valid status transitions.
- **IP.PR.03.009** — Order Confirmation Page: foundation for confirmation polish (IP.PR.04.008).
- **IP.PR.03.010** — Order List Page: foundation for order history polish (IP.PR.04.008).
- **IP.PR.03.011** — Order Detail Page with Mock Timeline: foundation for tracking timeline polish (IP.PR.04.009).
- **IP.PR.03.012** — Basic Cancellation API: cancellation flow must work in demo.
- **IP.PR.03.014** — Delivery Fee Calculation: fee breakdown must display correctly.
- **IP.PR.03.015** — Fee/Tax Breakdown Visible: foundation for cart/checkout breakdown (IP.PR.04.006, IP.PR.04.007).

PR.04 also requires PR.02 foundations:
- **IP.PR.02.001** — Menu DB Fallback: menu must load reliably for restaurant detail.
- **IP.PR.02.002** — `GET /api/v1/me`: profile page depends on this.
- **IP.PR.02.003** — Frontend Auth Persistence: auth must work reliably.
- **IP.PR.02.005** — Loading Skeletons: skeleton components reused for all lists.
- **IP.PR.02.007** — Error Boundary: pattern reused on all pages.
- **IP.PR.02.011** — Unsplash Images: real food images for restaurant cards.
- **IP.PR.02.013** — Dark Mode: dark classes must exist before toggle.
- **IP.PR.02.014** — Mobile Bottom Nav: responsive mobile navigation.

## 22. Connected Next-Level Requirements (link to PR.05)

PR.05 (Usable Closed-Demo App, score 5/10) builds on PR.04 and requires:
- Working demo-ready core loop from all IP.PR.04 work items.
- Design system from IP.PR.04.011 (foundation for all future UI).
- Indian food UI specifics from IP.PR.04.012 (foundation for market-specific features).
- Responsive layout from IP.PR.04.013 (foundation for mobile app parity).
- Toast component from IP.PR.04.014 (reused for all future notifications).
- Error boundary + skeleton + empty state patterns from IP.PR.04.015 (reused for all new screens).
- Dark mode from IP.PR.04.016 (reused for all new pages).
- Review system from IP.PR.04.017 (foundation for review submission and restaurant rating).

PR.05 will introduce:
- Real map integration on order tracking (replacing static timeline).
- Address autocomplete with Nominatim or Google Places.
- Onboarding flow after signup (3-step: location, cuisines, done).
- Open/closed logic for restaurants.
- Serviceability radius check at checkout.
- Favorites and reorder features.
- Loyalty points activation and display.
- Real-time driver assignment (batch engine integration).
- Social login (Google OAuth) frontend wiring.
- Advanced animations (page transitions, add-to-cart fly animation).
- WebSocket reconnection logic.

PR.05 will be blocked if:
- Cart loses items on refresh.
- Checkout form crashes on validation error (no error boundary).
- Design system is not applied consistently (inconsistent UI across pages).
- Profile page shows skeleton forever or redirects to login.
- Order tracking page is blank or shows plain text instead of timeline.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (4/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.03 complete) described | Planner | ✅ |
| 4 | Target state (PR.04 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.04 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.04 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms no schema changes needed | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage includes Indian food UI and design system | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.04.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover: auth persistence, guest cart, homepage CTA, restaurant search/filter, menu tabs/veg/customization, cart polish, checkout polish, confirmation/history, tracking, profile, design system, Indian food UI, responsive layout, toast, error boundaries/skeletons/empty states, dark mode, review seed data | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention auth loop, design conflicts, guest order FK, dark mode gaps, TV breakpoints | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.03) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.05) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories: auth persistence polish (IP.PR.04.001), guest cart flow (IP.PR.04.002), homepage CTA + location (IP.PR.04.003), restaurant search/filter/chips/infinite scroll (IP.PR.04.004), menu tabs/veg/customization/reviews (IP.PR.04.005), cart polish (IP.PR.04.006), checkout polish (IP.PR.04.007), confirmation + order history (IP.PR.04.008), mock tracking timeline (IP.PR.04.009), profile with real data (IP.PR.04.010), design system application (IP.PR.04.011), Indian food UI specifics (IP.PR.04.012), responsive layout (IP.PR.04.013), toast component (IP.PR.04.014), error boundaries + skeletons + empty states (IP.PR.04.015), dark mode toggle (IP.PR.04.016), and review seed data (IP.PR.04.017).
- Scope is tightly bounded to score 4/10 (reliable, polished, demo-ready core loop). Out-of-scope explicitly excludes real payment gateways, real-time tracking maps, push notifications, admin/owner/driver flows, favorites/loyalty, and production infrastructure.
- Risks and blockers are grounded in known gaps from the audits (auth redirect loops, design system conflicts, guest order FK assumptions, dark mode gaps, TV breakpoints).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references.
- Feasibility tags use the required color system (🟢 LOCAL/DEMO-SAFE throughout; no 🔴 or ⚫ tags needed since all work is local-safe and demo-based).
- **One point deducted** because exact Tailwind config file paths, exact Zustand store file paths, and exact seed script locations are assumed from PR.02/03 rather than explicitly confirmed. Minor discovery may be needed during build to locate these precisely.

The document is ready for execution.
