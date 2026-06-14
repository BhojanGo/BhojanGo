# IP.PR.02 — Browsable Prototype

## 1. Target Score Level

Score 2 / 10. App opens, shows homepage and restaurant listing, but menu/cart/checkout/order tracking is broken or mocked poorly.

---

## 2. Score Meaning

At score 2/10, the app is **navigable but not transactional**. A user can:
- Open the app and see a populated homepage.
- Browse a restaurant list with real seeded data.
- Tap into a restaurant detail page and see a menu that loads from the database.
- See loading states, error states, and empty states instead of blank white screens.
- Search and filter restaurants client-side.
- Toggle dark mode.
- Remain authenticated across page refreshes.

However, the user **cannot** reliably add items to cart, check out, place an order, or track delivery. Those flows remain broken or mocked and are the target of PR.03 and PR.04.

---

## 3. Current → Target Transition

**Current (PR.01 complete):**
- All 8 services boot successfully via `start-all.sh`.
- Bcrypt conflict resolved; Python services install cleanly.
- Batch-engine migration ordering fixed; fresh DB initializes without SQL errors.
- PostgreSQL seeded with 96 restaurants, menu categories, and menu items.
- OpenSearch container added to docker-compose.
- Menu endpoint 500 root cause documented: OpenSearch connection failure with no DB fallback.
- Frontend auth session loss documented: missing `GET /api/v1/me` plus no token persistence strategy.
- API health check matrix exists documenting failing endpoints.

**Target at score 2:**
- Menu endpoint returns real menu data from PostgreSQL when OpenSearch is unavailable (graceful degradation).
- Restaurant list page renders real data with cuisine chips, rating badges, and trust indicators.
- Restaurant detail page has error boundary + skeleton loader + real menu items.
- Homepage uses skeleton-first landing ( Next.js SSR/ISR) so first paint shows content, not spinners.
- Client-side search and filter chips (rating, veg-only) work on the restaurant list.
- Category-specific Unsplash images replace generic Picsum placeholders.
- Frontend JWT tokens persist in httpOnly cookies or localStorage; `GET /api/v1/me` returns current user.
- Bottom navigation visible on mobile viewports.
- Dark mode toggle functional across all pages.
- No blank white screens on any critical page.

---

## 4. Implementation Objective

Make the primary browse-and-discover screens navigable and data-rich: homepage, restaurant listing, and restaurant detail must render real data from the seeded database, survive API errors gracefully, and provide intuitive client-side discovery tools (search, filters, cuisine chips). Fix auth persistence so the frontend knows who is logged in. Lay UI/UX groundwork (skeletons, empty states, dark mode, mobile nav) that later tiers will inherit.

---

## 5. Scope

### In Scope

1. **Backend — Menu Endpoint Resilience**
   - Add DB fallback query (`menu_categories` + `menu_items`) when OpenSearch client throws `ConnectionError` or returns no results.
   - Wrap OpenSearch calls in try/except with structured log warning.

2. **Backend — Auth Me Endpoint**
   - Add `GET /api/v1/me` to `user-svc` decoding JWT `sub` claim, querying DB, returning `{id, email, full_name, role, phone, is_verified}`.

3. **Backend — Restaurant List Filters (API layer)**
   - Extend `GET /api/v1/restaurants` to accept optional query params: `?cuisine=Indian&min_rating=4.0&veg_only=true&sort=rating`.
   - These params are optional; default behavior (no params) returns full list for backward compatibility.

4. **Frontend — Auth Persistence**
   - Store JWT access token in `httpOnly` cookie (preferred) or `localStorage` (fallback) after login.
   - On app bootstrap, call `GET /api/v1/me` to rehydrate auth state in Zustand / React context.
   - Add Axios / fetch interceptor to attach `Authorization: Bearer <token>` header.

5. **Frontend — Homepage Skeleton-First Landing**
   - Convert homepage featured-restaurants section to use Next.js `generateStaticParams` or ISR (revalidate 60s) so first paint includes restaurant names.
   - Skeleton cards used only for client-side hydration deltas, not initial blank load.

6. **Frontend — Restaurant Listing Enhancements**
   - Add sticky debounced search bar (200ms) filtering client-side by restaurant name + cuisine.
   - Add horizontal scrollable cuisine category chips (Indian, Chinese, Pizza, Burger, etc.) filtering client-side.
   - Add filter chips: ⭐ 4+ rating, veg-only toggle.
   - Add infinite scroll or "Load More" pagination UI (intersection observer).

7. **Frontend — Restaurant Cards with Real Data**
   - Card anatomy: 16:10 image, gradient overlay, name (h3), cuisine chip row, rating badge (absolute top-right), delivery time badge (absolute bottom-right).
   - Trust badges: "FSSAI Verified", "Freshly Prepared", "Under 30 min".
   - Show real fields from DB: `name`, `cuisine_types`, `rating`, `delivery_time_min`, `is_active`.

8. **Frontend — Category-Specific Real Food Images**
   - Replace Picsum with deterministic Unsplash category images (e.g., cuisine type maps to a curated Unsplash photo ID).
   - Images load from Unsplash source URLs; no S3/CDN dependency.

9. **Frontend — Restaurant Detail Error Boundary + Skeleton**
   - Wrap restaurant detail page in React Error Boundary showing "Menu temporarily unavailable. Please try again." with retry button.
   - Add skeleton loader for menu items while API inflight.
   - Add skeleton loader for restaurant header (name, rating, cuisine).

10. **Frontend — Empty State for No Restaurants**
    - Custom SVG illustration + message "No restaurants found" + CTA "Clear filters" when search/filter yields zero results.

11. **Frontend — Dark Mode Toggle**
    - Add sun/moon toggle in navbar. Persist preference in `localStorage`. Respect `prefers-color-scheme`.
    - Ensure Tailwind `dark:` classes activate correctly across all pages scoped in this PR.

12. **Frontend — Bottom Navigation (Mobile)**
    - Show on viewports <640px: Home, Search, Cart, Orders, Profile.
    - Active tab highlighted. Cart badge shows item count from Zustand cart store.

13. **Frontend — Loading Skeletons Reusable Component**
    - Create `<SkeletonCard />`, `<SkeletonMenuItem />`, `<SkeletonText />` in `packages/ui` for use across web app.

### Out of Scope (do NOT include)

- Real payment processing (simulated only in PR.03).
- Cart persistence across sessions (localStorage cart save/restore — PR.03).
- Order placement, checkout flow, or order tracking (PR.03–PR.04).
- Admin dashboard, restaurant owner portal, driver flows (PR.06+).
- Push notifications, SMS, email dispatch (optional, later tiers).
- CDN, S3 image hosting, image optimization pipeline (future infra).
- Real-time driver tracking map (PR.04+).
- Address autocomplete, map pin selection, geolocation permission flow.
- Order cancellation, refund flow, password reset.
- Social login (Google OAuth) — backend exists but frontend wiring is PR.05+.
- WebSocket reconnection logic, circuit breakers, retry logic.
- Integration tests, E2E tests, load tests.
- OpenSearch menu index creation (menu loads from DB fallback; search indexing is PR.05+).
- Review listing endpoint or seeded reviews (PR.05+).
- Loyalty points activation, favorites, reorder, group ordering (PR.05+).

---

## 6. Out of Scope (do NOT include)

(See detailed list in Section 5 above. Summarized here for quick reference.)

- Payment processing, cart persistence, checkout, order placement.
- Admin/owner/driver flows.
- Push notifications.
- CDN/S3 production image infrastructure.
- Real-time tracking.
- Address autocomplete / geolocation.
- Order cancellation / refund.
- Social login frontend wiring.
- WebSocket reconnection.
- Integration / E2E / load tests.
- OpenSearch menu indexing.
- Review listing / seeded reviews.
- Loyalty, favorites, reorder, group order.

---

## 7. Required Capabilities

- Menu endpoint serves real data regardless of OpenSearch state.
- `GET /api/v1/me` returns authenticated user profile.
- FrontendAuth survives page refresh via cookie/localStorage + me endpoint.
- Restaurant list page shows real DB data with client-side search, cuisine chips, rating/veg filters.
- Restaurant cards display trust badges and deterministic category images.
- Restaurant detail page renders menu with skeleton loader and error boundary.
- Homepage first paint includes content (ISR/SSR skeleton-first).
- Dark mode toggle functional and persisted.
- Mobile bottom navigation visible and interactive.
- Zero blank white screens on homepage, restaurant list, restaurant detail.

---

## 8. Key User Journeys

### Journey 8.1 — Browse Restaurants
1. User opens app at `/`.
2. Homepage renders featured restaurants immediately (ISR).
3. User taps "Find Food" or navigates to `/restaurants`.
4. Restaurant list loads with skeleton cards, then populates with real data.
5. User types "biryani" in search bar → list filters to matching restaurants.
6. User taps "Indian" cuisine chip → list filters further.
7. User taps "4+" rating filter → list filters to `rating >= 4.0`.
8. User sees cards with real images, names, ratings, delivery time, trust badges.
9. User taps a restaurant card.

### Journey 8.2 — View Restaurant Menu
1. User lands on `/restaurants/[id]`.
2. Header skeleton shows while restaurant metadata loads.
3. Menu skeleton rows show while menu API is in flight.
4. Menu items appear with name, price, veg/non-veg indicator, description.
5. If menu API fails, error boundary shows friendly message with retry button.
6. User can scroll through menu categories (flat list at PR.02; tabs in PR.03).

### Journey 8.3 — Auth Persistence
1. User logs in at `/login`.
2. Token stored in httpOnly cookie (or localStorage fallback).
3. `GET /api/v1/me` called on app bootstrap.
4. User refreshes page — still logged in, profile data visible in navbar.
5. User navigates to `/profile` — profile data renders without re-login.

---

## 9. Technical Coverage

### Backend
- `restaurant-svc`: Menu endpoint fallback to DB when OpenSearch unavailable.
- `restaurant-svc`: Query param filters on restaurant list (optional, backward-compatible).
- `user-svc`: `GET /api/v1/me` endpoint with JWT sub claim decoding.
- Structured logging on all fallback paths (warning level).
- Graceful degradation: OpenSearch failures do not propagate as 500s.

### Frontend
- Next.js App Router pages: `/`, `/restaurants`, `/restaurants/[id]`.
- ISR/SSR for homepage featured restaurants section (`revalidate: 60`).
- Client-side filtering: debounced search, cuisine chips, rating filter, veg-only toggle.
- Axios interceptor for Bearer token injection.
- Zustand auth store with hydration from `/api/v1/me`.
- React Error Boundary on restaurant detail (`error.tsx` or custom boundary).
- Tailwind `dark:` class activation via class strategy + localStorage.
- CSS breakpoint-aware bottom nav (`sm:hidden` or equivalent).
- Shared UI package extended with skeleton components.

### Data
- Seeded restaurants (96 records) provide real list data.
- Seeded menu_categories + menu_items provide real menu data.
- No new migrations required; existing schema sufficient.

---

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for restaurant list, skeleton rows for menu, skeleton text for profile/header. No spinners on first paint for homepage.
- **Error states:** Error boundary on restaurant detail with retry CTA. API failure messages inline (not console-only).
- **Empty states:** "No restaurants found" illustration + "Clear filters" CTA when filters yield zero results.
- **Trust signals:** FSSAI Verified, Freshly Prepared, Under 30 min badges on cards.
- **Cuisine discovery:** Horizontal scrollable chip bar below search.
- **Mobile-first nav:** Bottom tab bar on <640px viewports.
- **Dark mode:** Toggle in navbar, persisted preference, respects OS setting.
- **Typography & color:** Introduce BhojanGo brand palette (CSS custom properties) — primary `#E65100` (Warm Saffron), secondary `#2E7D32` (Trust Green), accent `#FFB300` (Nugget Gold), neutral `#F7F5F2` (Cream), dark `#1A1A1A`. Use Manrope (headings) + Inter (body) via Google Fonts. No raw emoji — Lucide icons only.
- **Card anatomy standard:** Image 16:10, rounded-xl, gradient overlay bottom, name h3, cuisine chips row, rating badge absolute top-right, delivery time absolute bottom-right.
- **Page transitions:** Subtle fade via Next.js / CSS (optional, lightweight).

---

## 11. Data / Model Coverage

- Uses existing `restaurants`, `menu_categories`, `menu_items` tables (no schema changes).
- Uses existing `users` table for `GET /api/v1/me`.
- No new tables needed.
- No seed data changes needed.

---

## 12. Role / Permission Coverage

- `GET /api/v1/me` returns role field (`customer`, `restaurant_owner`, `delivery_partner`, `admin`, `super_admin`, `support`).
- Frontend uses role to conditionally show/hide nav items (e.g., driver-only tabs hidden for customers).
- No new RBAC enforcement in this tier — existing middleware sufficient.

---

## 13. Performance / Reliability / Security Coverage

### Performance
- Homepage ISR: `revalidate: 60` seconds reduces API load and improves TTFB.
- Client-side filtering avoids refetching from server on every keystroke.
- Unsplash images loaded via `next/image` with `sizes` prop for responsive optimization.

### Reliability
- Menu endpoint DB fallback ensures menu is never unavailable due to OpenSearch.
- Error boundary prevents entire page crash on menu API failure.
- Skeleton loaders prevent layout shift and perceived slowness.

### Security
- JWT access token in `httpOnly` cookie prevents XSS token theft (preferred over localStorage).
- If localStorage fallback used, document the trade-off and plan httpOnly migration in PR.05.
- `GET /api/v1/me` validates JWT signature and expiry before returning user data.
- No sensitive data logged on fallback paths.

---

## 14. Novelty / Differentiation Coverage

At score 2, novelty is minimal but groundwork is laid:
- **Brand palette and typography** distinguish BhojanGo from generic Tailwind templates.
- **Trust badges** (FSSAI Verified, Freshly Prepared) create food-specific credibility early.
- **Veg-only filter chip** addresses Indian market preference immediately.
- **Category-specific real food images** replace random abstract placeholders — first impression improves dramatically.
- **Dark mode** is table-stakes for modern apps but still counts as polish.

Novelty scores are intentionally limited at this tier; full differentiation (loyalty, meal rescue, group ordering, etc.) begins at PR.05+.

---

## 15. Implementation Work Items

### IP.PR.02.001 — Add DB Fallback to Menu Endpoint When OpenSearch Unavailable
- **Category:** Backend
- **Implementation Scope:** In `restaurant-svc` menu route handler, wrap the OpenSearch query in a `try/except` block catching `opensearchpy.exceptions.ConnectionError` and generic `Exception`. On any exception, log a structured warning and fall back to a direct SQLAlchemy query joining `menu_categories` and `menu_items` filtered by `restaurant_id`. Return the same response shape as the OpenSearch path so the frontend is unaware of the fallback.
- **Acceptance Criteria:**
  1. Menu endpoint returns 200 with real items when OpenSearch container is running.
  2. Menu endpoint returns 200 with real items when OpenSearch container is stopped/killed.
  3. Response shape is identical in both paths.
  4. Structured log warning emitted on fallback path.
- **Evidence Required:** Terminal output of `curl` against menu endpoint with OpenSearch up, then with OpenSearch down, both returning 200 with items array.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE (PR.01 fixed OpenSearch in docker-compose)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.002 — Add `GET /api/v1/me` Endpoint to User Service
- **Category:** Backend
- **Implementation Scope:** In `user-svc`, add a new route `GET /api/v1/me` protected by existing auth middleware. Decode JWT `sub` claim to get user ID. Query PostgreSQL `users` table by ID. Return JSON: `{id, email, full_name, role, phone, is_verified}`. Return 401 if token missing/invalid. Return 404 if user not found (edge case: deleted user with valid token).
- **Acceptance Criteria:**
  1. Authenticated request returns 200 with user profile JSON.
  2. Missing/invalid token returns 401.
  3. Response shape matches frontend auth store interface.
- **Evidence Required:** `curl` with valid Bearer token returns user object. `curl` without token returns 401.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.003 — Implement Frontend Auth Persistence (Cookie or localStorage)
- **Category:** Frontend
- **Implementation Scope:** After successful login, store JWT access token in an `httpOnly` cookie (preferred path: set via backend response `Set-Cookie` header) or in `localStorage` (fallback if backend cookie setting requires more infra). On app bootstrap (layout or root provider), read token and call `GET /api/v1/me`. Hydrate Zustand auth store with returned user. Attach `Authorization: Bearer <token>` header via Axios request interceptor. On logout, clear cookie/localStorage and reset auth store.
- **Acceptance Criteria:**
  1. User logs in, refreshes page, remains authenticated.
  2. Navbar shows user name/avatar after refresh without re-login.
  3. Logout clears auth state and redirects to `/login`.
  4. API calls include Bearer token header automatically.
- **Evidence Required:** Screen recording or test log: login → refresh → `/profile` renders user data → logout → `/login` shown.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.02.002 (`/api/v1/me` must exist)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.004 — Convert Homepage to Skeleton-First ISR Landing
- **Category:** Frontend
- **Implementation Scope:** In the web app's homepage (`/`), refactor the featured restaurants section to fetch data server-side via Next.js ISR (`revalidate: 60`). Use `fetch` in a Server Component (or `getStaticProps` equivalent in App Router) to call `GET /api/v1/restaurants?limit=8`. Render restaurant cards directly in HTML so first paint includes content. Use skeleton cards only for client-side interactive elements (e.g., "Near You" section that depends on geolocation). Ensure no full-page spinner on initial load.
- **Acceptance Criteria:**
  1. Viewing page source (Ctrl+U) shows restaurant names in raw HTML.
  2. No spinner covers the entire page on first load.
  3. ISR revalidates every 60 seconds; stale-while-revalidate behavior observed.
- **Evidence Required:** Lighthouse or DevTools screenshot showing First Contentful Paint < 1.5s with content visible. Page source showing restaurant names.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.005 — Add Loading Skeletons for Restaurant List and Menu
- **Category:** Frontend
- **Implementation Scope:** Create reusable skeleton components in `packages/ui`: `<SkeletonCard />` (image placeholder + text lines), `<SkeletonMenuItem />` (row with avatar placeholder + title + price lines), `<SkeletonText />` (shimmer paragraph lines). Use these in `/restaurants` page while `useQuery` is in `isLoading` state. Use in `/restaurants/[id]` menu section while menu API is loading. Use Tailwind `animate-pulse` or custom shimmer animation.
- **Acceptance Criteria:**
  1. Restaurant list shows 6 skeleton cards before data loads.
  2. Menu shows 8 skeleton rows before data loads.
  3. Skeletons match the layout dimensions of real content (no layout shift).
  4. No blank white screen during loading.
- **Evidence Required:** Screenshot of loading state for both pages. DevTools network throttled to 3G showing skeletons for >2s.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.006 — Add Empty State for No Restaurants
- **Category:** Frontend
- **Implementation Scope:** In `/restaurants` page, when client-side search + filters yield zero results, show a centered empty state: custom SVG illustration (sad pizza or empty plate), heading "No restaurants found", subtext "Try adjusting your search or filters", and a "Clear all filters" button that resets search text and filter chips to default. Hide pagination/"Load More" when empty.
- **Acceptance Criteria:**
  1. Typing nonsense in search bar shows empty state within 200ms.
  2. "Clear all filters" resets search and chips, restoring full list.
  3. Empty state has illustration + message + CTA (not just "No results" text).
- **Evidence Required:** Screenshot of empty state. Video showing filter → empty → clear → restore.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.02.005 (skeleton component exists for layout reference)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.007 — Add Error Boundary on Restaurant Detail Page
- **Category:** Frontend
- **Implementation Scope:** Create a React Error Boundary component (class component or `react-error-boundary` if already in deps) wrapping the restaurant detail page content. On menu API failure (or any unhandled exception in the detail page subtree), render: heading "Menu temporarily unavailable", subtext "We're having trouble loading this menu. Please try again.", and a "Retry" button that calls `window.location.reload()` or re-fetches query. Log error to console with correlation ID. Ensure the restaurant header (name, rating, cuisine) still renders if only the menu section fails.
- **Acceptance Criteria:**
  1. Simulating menu API 500 shows error boundary UI, not blank page.
  2. Retry button re-attempts menu fetch.
  3. Restaurant header info still visible even if menu fails.
  4. Error logged to console with actionable message.
- **Evidence Required:** Screenshot of error boundary UI. DevTools showing console error with retry action.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.008 — Add Client-Side Debounced Search Bar
- **Category:** Frontend
- **Implementation Scope:** Add a sticky search input above the restaurant grid on `/restaurants`. Debounce input by 200ms using `useDeferredValue` or a custom debounce hook. Filter client-side by `restaurant.name` (case-insensitive contains) and `restaurant.cuisine_types` array. Highlight matching text if feasible (optional). Show clear (X) button when input non-empty.
- **Acceptance Criteria:**
  1. Typing "dosa" filters list within 200ms.
  2. Clearing input restores full list.
  3. Search is case-insensitive.
  4. No server refetch on every keystroke.
- **Evidence Required:** Screen recording showing search typing and real-time filtering.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.009 — Add Cuisine Chips on Restaurant Listing
- **Category:** Frontend
- **Implementation Scope:** Below the search bar, add a horizontally scrollable row of chip buttons representing distinct cuisines found in the seeded data (e.g., Indian, Chinese, Italian, Pizza, Burger, South Indian, Biryani, Desserts). Each chip is toggle-able (click to filter, click again to clear). Use client-side filtering on `restaurant.cuisine_types`. Chips have active state styling (filled vs outlined). Scrollable via touch drag or arrow buttons on desktop.
- **Acceptance Criteria:**
  1. Clicking "Pizza" filters to restaurants with "Pizza" in cuisine_types.
  2. Clicking again clears the filter.
  3. Multiple chips can be active simultaneously (OR logic).
  4. Active chips visually distinct from inactive.
- **Evidence Required:** Screenshot of cuisine chip row. Video showing chip click → filter → clear.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.010 — Add Filter Chips (Rating 4+, Veg-Only)
- **Category:** Frontend
- **Implementation Scope:** Add filter chip row below cuisine chips: "⭐ 4+" (rating >= 4.0), "🟢 Veg Only" (restaurant `is_veg_only = true` or menu has veg flag — use `is_veg_friendly` field if exists, else filter by veg-only restaurants). These are toggle chips. Combine filters with search + cuisine chips (AND logic within category, OR across categories as appropriate). Show active filter count badge.
- **Acceptance Criteria:**
  1. "4+" filter shows only restaurants with rating >= 4.0.
  2. "Veg Only" filter shows only veg-friendly restaurants.
  3. Filters combine correctly with search and cuisine chips.
  4. Clear all filters button resets everything.
- **Evidence Required:** Screenshot showing filtered results with multiple active filters.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.02.008, IP.PR.02.009
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.011 — Add Category-Specific Deterministic Unsplash Images
- **Category:** Frontend
- **Implementation Scope:** Replace all Picsum placeholder URLs with deterministic Unsplash category images. Create a mapping: `cuisine_type → Unsplash photo ID`. For example: "Pizza" → `photo-1565299624946-b28f40a0ae38`, "Biryani" → `photo-1589302168068-964664d93dc0`, "Burger" → `photo-1568901346375-23c9450c58cd`, generic fallback → `photo-1504674900247-0877df9cc836`. Use `https://images.unsplash.com/photo-id?w=800&q=80` format. Store mapping in a constants file. Apply to restaurant card images and restaurant detail header image.
- **Acceptance Criteria:**
  1. Every restaurant card shows a relevant food image, not abstract placeholder.
  2. Same restaurant always shows same image (deterministic).
  3. If cuisine not in mapping, fallback to generic food image.
  4. Images load within 2s on 3G.
- **Evidence Required:** Screenshots of restaurant list and detail showing specific food images (pizza, biryani, etc.).
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.012 — Update Restaurant Cards with Real Data and Trust Badges
- **Category:** Frontend
- **Implementation Scope:** Refactor restaurant card component to show real fields from API: `name`, `cuisine_types` (array joined with " · "), `rating` (with star icon), `delivery_time_min` (with clock icon), `price_for_two` (₹ symbol), `is_active`. Add trust badges as small pills: "FSSAI Verified" (shield icon), "Freshly Prepared" (leaf icon), "Under 30 min" (bolt icon) if applicable. Use brand color tokens defined in Section 10. Cards follow the anatomy standard: 16:10 image, gradient overlay bottom, name h3, cuisine chips row, rating badge absolute top-right, delivery time badge absolute bottom-right.
- **Acceptance Criteria:**
  1. Card displays all real fields from DB for every restaurant.
  2. At least 3 trust badges visible on applicable cards.
  3. Card layout is consistent (no variation between cards).
  4. Typography uses Manrope (headings) + Inter (body).
- **Evidence Required:** Screenshot of restaurant list showing 4+ cards with real data and badges.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.02.011 (images)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.013 — Add Dark Mode Toggle
- **Category:** Frontend
- **Implementation Scope:** Add a sun/moon icon toggle button in the navbar (top-right). On toggle, add/remove `dark` class on `<html>` element (Tailwind class strategy). Persist preference in `localStorage` under key `bhojango-theme`. On initial load, check `localStorage` first, then fall back to `prefers-color-scheme: dark`. Ensure all pages in scope (`/`, `/restaurants`, `/restaurants/[id]`) render correctly in dark mode — no black-on-black text, no missing dark variants. Update Tailwind config if `darkMode: 'class'` is not already set.
- **Acceptance Criteria:**
  1. Toggle switches between light and dark modes across all pages.
  2. Preference persists across browser sessions.
  3. Respects OS dark mode preference on first visit.
  4. No visual regressions (contrast, readability) in dark mode.
- **Evidence Required:** Side-by-side screenshots of `/restaurants` in light and dark mode. Screen recording of toggle action.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.014 — Add Bottom Navigation for Mobile
- **Category:** Frontend
- **Implementation Scope:** Create a `<MobileBottomNav />` component visible only on viewports below 640px (`sm:hidden` or `md:hidden`). Tabs: Home (`/`), Search (`/restaurants`), Cart (`/cart`), Orders (`/orders`), Profile (`/profile`). Each tab has an icon (Lucide: Home, Search, ShoppingCart, ClipboardList, User) and label. Active tab highlighted with brand primary color. Cart tab shows badge with item count from Zustand cart store. Position fixed bottom-0, z-50. Safe area padding for notched devices (padding-bottom: env(safe-area-inset-bottom)).
- **Acceptance Criteria:**
  1. Bottom nav visible on mobile viewport (<640px).
  2. Hidden on desktop viewport.
  3. Active tab highlighted correctly per current route.
  4. Cart badge updates when items added.
  5. Tapping tab navigates to correct route.
- **Evidence Required:** Screenshot of mobile viewport showing bottom nav. Video showing tab switch and cart badge update.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.02.015 — Extend Restaurant List API with Optional Filter Params
- **Category:** Backend
- **Implementation Scope:** Extend `GET /api/v1/restaurants` in `restaurant-svc` to accept optional query parameters: `cuisine` (string, ILIKE match against `cuisine_types`), `min_rating` (float, `rating >= min_rating`), `veg_only` (boolean, filters `is_veg_friendly = true` or similar field), `sort` (enum: `rating`, `delivery_time`, `name`, default `created_at`). These are optional — calling without params returns full list unchanged. Use SQLAlchemy `where()` clauses built conditionally. Return same paginated response shape.
- **Acceptance Criteria:**
  1. `GET /api/v1/restaurants?cuisine=Indian` returns only Indian restaurants.
  2. `GET /api/v1/restaurants?min_rating=4.0` returns only restaurants with rating >= 4.0.
  3. `GET /api/v1/restaurants?sort=rating` returns list ordered by rating desc.
  4. No params returns full list (backward compatible).
- **Evidence Required:** `curl` output for each param combination showing correct filtering/sorting.
- **Priority:** P1
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

---

## 16. Acceptance Criteria

- [ ] Menu endpoint (`GET /api/v1/restaurants/{id}/menu`) returns 200 with real items regardless of OpenSearch state.
- [ ] `GET /api/v1/me` returns 200 with user profile for valid JWT; 401 for missing/invalid token.
- [ ] Frontend auth persists across page refresh (user remains logged in after F5).
- [ ] Homepage first paint shows real restaurant content (viewable in page source) without full-page spinner.
- [ ] Restaurant list page shows skeleton cards during loading, then populates with real data.
- [ ] Client-side search bar filters restaurants by name/cuisine with 200ms debounce.
- [ ] Cuisine chips filter restaurant list by cuisine type.
- [ ] Rating 4+ and veg-only filter chips function correctly.
- [ ] Empty state (illustration + message + clear CTA) shown when filters yield zero results.
- [ ] Restaurant cards show real data (name, cuisine, rating, delivery time) + trust badges + category-specific Unsplash images.
- [ ] Restaurant detail page shows skeleton loaders for header and menu.
- [ ] Error boundary on restaurant detail shows friendly error message with retry button when menu API fails.
- [ ] Dark mode toggle works across all pages, persists in localStorage, respects OS preference.
- [ ] Bottom navigation visible on mobile (<640px) with correct active tab highlighting and cart badge.
- [ ] No blank white screens on `/`, `/restaurants`, or `/restaurants/[id]`.

---

## 17. Evidence Required

- API test logs: menu endpoint with OpenSearch up/down (2 curl outputs).
- API test log: `GET /api/v1/me` with valid/invalid token (2 curl outputs).
- Screen recording: login → refresh → profile loads → logout.
- Lighthouse or DevTools screenshot: FCP < 1.5s on homepage with content visible.
- Screenshots: loading skeletons for restaurant list and menu.
- Screenshot: empty state with illustration.
- Screenshot: error boundary on restaurant detail.
- Screen recording: search + cuisine chips + filters in action.
- Screenshots: restaurant cards with real data, trust badges, Unsplash images.
- Side-by-side screenshots: light mode vs dark mode on `/restaurants`.
- Screenshot: mobile bottom navigation with active tab and cart badge.

---

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, OpenSearch containers).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- Unsplash (free source URLs for images — no API key needed).
- Google Fonts (Manrope + Inter — loaded via CSS `@import` or `<link>`).

### Internal Dependencies
- PR.01 must be complete: services boot, dependencies install, DB seeded, OpenSearch in docker-compose.
- `packages/ui` shared component package must build successfully.
- Existing seeded data (96 restaurants, menu categories, menu items) must be present.

---

## 19. Risks / Blockers

- **OpenSearch DB fallback may have performance issues on large menus.** The fallback is a direct SQL join; with ~30 items per restaurant this is negligible, but should be monitored. Mitigation: add simple Redis cache for menu fallback in PR.05.
- **localStorage token storage is XSS-vulnerable.** If httpOnly cookie implementation is blocked by CORS or Kong config, localStorage fallback is acceptable for PR.02 but must be migrated to httpOnly in PR.05. Document this as a known security gap.
- **Unsplash images may be slow or blocked in some networks.** Mitigation: add `next/image` with placeholder blur and optional fallback to local placeholder if Unsplash fails.
- **Brand color tokens may conflict with existing Tailwind usage.** Mitigation: use CSS custom properties scoped to `:root` and `html.dark` so existing utility classes are not broken.
- **Mobile bottom nav may clash with existing hamburger menu.** Mitigation: hide hamburger on mobile (<640px) when bottom nav is present; keep it on desktop.
- **ISR revalidation may cause stale data confusion during development.** Mitigation: use `export const dynamic = 'force-dynamic'` in dev environment if needed; keep ISR for production builds.
- **Client-side filtering on 96 restaurants is trivial, but if list grows to 500+, filtering must move server-side.** This is acceptable for PR.02; server-side filtering is already scoped in IP.PR.02.015.

---

## 20. Exit Criteria

- All P0 work items (IP.PR.02.001 through IP.PR.02.008, IP.PR.02.012) are implemented and verified.
- Menu endpoint returns data with OpenSearch both up and down.
- Auth persists across refresh.
- Homepage, restaurant list, and restaurant detail render real data with no blank screens.
- Skeleton loaders, error boundary, empty state, search, chips, filters, dark mode, and mobile nav are all functional.
- Evidence screenshots/recordings captured per Section 17.
- PR.02 declared complete.

---

## 21. Connected Previous-Level Requirements

PR.01 (Broken Shell) must be complete before PR.02 begins. Specifically:
- `start-all.sh` must boot all services without manual intervention.
- Bcrypt conflict must be resolved (Python services install cleanly).
- Batch-engine migration ordering must be fixed.
- PostgreSQL must be seeded with restaurants, menu categories, and menu items.
- OpenSearch must be in docker-compose.
- API health check matrix and blocker documentation must exist.

---

## 22. Connected Next-Level Requirements

PR.03 (Core Flow Partially Working) builds directly on PR.02. PR.03 requires:
- Working menu endpoint (real data) from IP.PR.02.001.
- Auth persistence from IP.PR.02.003.
- `/api/v1/me` from IP.PR.02.002.
- Skeleton/loading patterns from IP.PR.02.005 (reused for cart/checkout).
- Error boundary pattern from IP.PR.02.007 (reused for checkout).
- Dark mode and mobile nav from IP.PR.02.013 / IP.PR.02.014 (inherited).

PR.03 will be blocked if:
- Menu endpoint still returns 500 when OpenSearch is down.
- Auth does not persist across refresh.
- Restaurant detail page crashes on API failure (no error boundary).

---

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (2/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.01 complete) described | Planner | ✅ |
| 4 | Target state (PR.02 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.02 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.02 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms no schema changes needed | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage limited to groundwork (brand, trust, veg filter) | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.02.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 10 work items present | Planner | ✅ |
| 17 | Work items cover: menu fallback, auth me, auth persistence, ISR, skeletons, empty state, error boundary, search, chips, filters, images, cards, dark mode, mobile nav, API filters | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention OpenSearch perf, localStorage XSS, Unsplash reliability, token conflicts | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.01) requirements listed | Planner | ✅ |
| 24 | Connected next-level (PR.03) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

---

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories: backend resilience (menu fallback, `/me`), frontend UX (skeletons, empty state, error boundary, search, filters, chips), visual polish (Unsplash images, trust badges, brand palette, typography), mobile (bottom nav), and accessibility (dark mode).
- The 13 implementation work items are specific, implementation-ready, and each has clear acceptance criteria and evidence requirements.
- Scope is tightly bounded to score 2/10 (navigable browse-and-discover screens, no transactional flow). Out-of-scope explicitly excludes cart persistence, checkout, order placement, admin flows, and production infrastructure.
- Risks and blockers are grounded in known issues from PR.01 and the audits (OpenSearch dependency, auth persistence gap, localStorage XSS trade-off).
- Connected previous-level and next-level requirements are explicitly documented.
- Feasibility tags use the required color system (🟢 LOCAL/DEMO-SAFE throughout; no 🔴 or ⚫ tags needed at this tier since all work is local-safe).
- **One point deducted** because some specific implementation details (e.g., exact field names in the restaurant DB schema for veg filtering, exact Zustand store file paths) may need minor discovery during build. The plan is otherwise ready for execution.

The document is ready for execution.
