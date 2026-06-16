# IP.ND.03 — Small Convenience Features

## 1. Target Differentiation Score: 3/10

## 2. Score Meaning

Basic favorites, reorder, better filters, veg/non-veg visibility, and cleaner menu discovery start to differentiate the app. At score 3, the product is no longer a generic clone — it has the small convenience features that repeat users expect from a competent food delivery platform. The app feels pleasant to use daily because common actions (reordering a favorite meal, filtering by dietary preference, scanning a categorized menu) are fast and obvious. These are table-stakes features in mature markets, but their absence makes an app feel unfinished. Their presence moves BhojanGo from "demo prototype" to "usable daily driver."

## 3. Current → Target Transition

**From ND.02 (distinctive visual identity applied):**
- The app has a warm saffron + trust green color palette, Manrope + Inter typography, Lucide icons, and consistent card/badge anatomy.
- The core ordering loop (browse → menu → cart → checkout → track) is functional and stable.
- Restaurant cards show basic info (name, image, rating) but lack cuisine chips, delivery time, fee, and trust badges.
- Menu items have no veg/non-veg indicators, no category tabs, no bestseller badges, and no search within menu.
- Users cannot save favorite restaurants; there is no heart toggle, no favorites section, and no quick way to reorder from a liked spot.
- Order history exists but has no "Reorder" button.
- Restaurant list has no filter chips for rating, veg-only, price range, or delivery time.
- Menu is a flat list; users must scroll through all items to find what they want.
- Adding an item to cart requires opening a detail modal; there is no quick-add button on the menu card.

**Target at score 3:**
- Favorites system is live: heart toggle on every restaurant card and detail page, "Your Favorites" section on homepage, dedicated `/favorites` page with remove option and empty state.
- Reorder works: "Reorder" button on order history cards pre-fills cart with exact items + quantities. Toast confirms. Logged-in users only.
- Better filters are available: rating filter (4+, 3+), veg-only filter, price range filter (Under ₹200, ₹200-₹500, ₹500+), delivery time filter (Under 30 min). Filters can be client-side or backend.
- Veg/non-veg visibility is mandatory: green dot for veg, red dot for non-veg on every menu item, restaurant card, cart row, and order history item. "Veg Only" filter chip on restaurant list.
- Cleaner menu discovery: sticky category tabs (Starters | Mains | Breads | Desserts | Combos), "Bestseller" badge on top 3 items per category, search-within-menu input, Combos/Thali section clearly demarcated.
- Improved restaurant cards: cuisine chips, rating, delivery time, delivery fee, trust badge (e.g., "FSSAI Verified"), and open/closed status all visible without clicking.
- Quick add: add-to-cart button (+ icon) on menu item card without opening detail modal. Minimal toast confirmation (no fly animation — that comes at score 4+).

## 4. Implementation Objective

Add small, high-frequency convenience features that make the app pleasant for repeat users. These features are not unique to BhojanGo — every competitor has them — but their absence makes the app feel amateur. Their presence raises BhojanGo from "generic clone" to "competent delivery app." The goal is speed of implementation and maximum daily usability impact. Nothing here requires new infrastructure, external APIs, or complex algorithms.

## 5. Scope

### 5.1 Favorites
- **Database:** New `favorites` table (`user_id`, `restaurant_id`, `created_at`). Unique constraint on (`user_id`, `restaurant_id`).
- **Backend:** `POST /api/v1/favorites` (toggle/upsert), `DELETE /api/v1/favorites/{restaurant_id}`, `GET /api/v1/favorites` (list with restaurant details).
- **Frontend:** Heart icon (Lucide `Heart` / `HeartOff`) on every restaurant card and restaurant detail page header. Optimistic UI: toggle heart immediately, sync with API, revert on failure with error toast. "Your Favorites" horizontal scroll section on homepage (top 6 favorites). New `/favorites` page with grid layout, remove (X) button per card, empty state with illustration (empty heart SVG) and "Browse Restaurants" CTA.

### 5.2 Reorder
- **Backend:** `POST /api/v1/orders/{id}/reorder` (or reuse `GET /api/v1/orders/{id}` and client-side pre-fill). Returns previous items with `menu_item_id`, `quantity`, `selected_add_ons`, `customizations`.
- **Frontend:** "Reorder" button on every order history card and order detail page. When tapped: (1) fetch previous order items, (2) pre-fill Zustand cart with exact same items + quantities, (3) if current cart contains items from a different restaurant, trigger cross-restaurant cart guard: "Your cart has items from {current_restaurant}. Replace with items from {new_restaurant}?", (4) on confirm, replace cart, (5) toast: "{N} items added from {restaurant_name}", (6) navigate to `/cart`. Logged-in users only; hide button for guests.

### 5.3 Better Filters
- **Backend (optional):** Extend `GET /api/v1/restaurants` with query params: `?min_rating=4.0`, `?veg_only=true`, `?price_range=1` (1=Under ₹200, 2=₹200-₹500, 3=₹500+), `?max_delivery_time=30`. OR implement client-side filtering if dataset is small.
- **Frontend:** Filter row below search bar on `/restaurants`:
  - Rating chip: "4+ ⭐" toggles `min_rating=4`.
  - Veg chip: "Veg Only" toggles veg filter.
  - Price chip: "Under ₹200" / "₹200-₹500" / "₹500+" (single-select dropdown or chip group).
  - Time chip: "Under 30 min" toggles `max_delivery_time=30`.
  - Active filters shown as removable pills. "Clear All" button when any filter is active.
  - Filter state persists in URL query params (shareable links).

### 5.4 Veg/Non-Veg Visibility
- **Backend:** Ensure `menu_items.is_veg` is populated for all items. Ensure `restaurants` has `is_pure_veg` flag (computed or stored). Return `is_veg` on every menu item response.
- **Frontend:**
  - Menu item cards: green circle (veg) or red circle (non-veg) at top-left of item image. Tooltip on hover: "Vegetarian" / "Non-vegetarian".
  - Cart rows: same dot next to item name.
  - Order history items: same dot next to item name.
  - Restaurant list: "Veg Only" filter chip. Pure-veg restaurants get a green "Pure Veg" badge on card.
  - Restaurant detail: "Veg Only" toggle switch next to category tabs. When ON, only `is_veg=true` items shown.

### 5.5 Cleaner Menu Discovery
- **Frontend (restaurant detail page):**
  - Sticky category tabs at top of menu: "All | Starters | Mains | Breads | Desserts | Combos/Thali". Scroll-to-section on tab click. Active tab highlighted.
  - "Bestseller" badge (star icon + text) on top 3 items per category by `order_count` or `is_bestseller` flag from DB.
  - Search-within-menu input above tabs. Debounce 200ms. Filters items by name and description. Empty state: "No items match '{query}'." Clear button (X) inside input.
  - Combos/Thali section: items with `item_type = 'combo'` grouped and clearly labeled. Show "Combo" pill badge.

### 5.6 Improved Restaurant Cards
- **Backend:** Ensure `GET /api/v1/restaurants` returns: `cuisine_types[]`, `rating`, `avg_delivery_time_min`, `delivery_fee`, `is_pure_veg`, `is_fssai_verified`, `is_open`, `image_url`.
- **Frontend:** Card anatomy update:
  - Image (16:10, rounded-xl top) with gradient overlay.
  - Rating badge (absolute top-right): "{rating} ⭐" with background tint.
  - Cuisine chips row below name: 2-3 cuisine types as small pills.
  - Delivery info row: "⏱ {min}-{max} min · ₹{delivery_fee}".
  - Trust badges row: "FSSAI Verified" shield icon (if verified). "Pure Veg" green leaf (if pure veg).
  - Open/closed status: green "Open" pill or gray "Opens at {time}" pill. Closed cards dimmed to 60% opacity.
  - Heart toggle (favorite) on top-right corner of image.

### 5.7 Quick Add-to-Cart
- **Frontend:** On menu item card (restaurant detail page), show a circular "+" button (Lucide `Plus`) at bottom-right of the card. Tapping it adds 1 quantity of the item to cart immediately. Toast: "{item_name} added to cart". If item has mandatory customizations, tapping "+" opens the customization modal instead (same as current behavior). If item is a combo, tapping "+" opens combo builder. Quick-add only works for items with no required customizations.
- **Backend:** Reuse existing `POST /api/v1/cart/items` or equivalent cart endpoint. No new endpoint needed.

## 6. Out of Scope

- **Loyalty / gamification:** Points, badges, tiers. Deferred to ND.05+.
- **Group ordering:** Shareable cart links, split bill. Deferred to ND.06+.
- **Meal rescue / end-of-day deals:** Flash sales, unsold inventory. Deferred to ND.06+.
- **Smart lockers / pickup points:** QR code, locker network. Deferred to ND.07+.
- **Nutritional info:** Calories, macros, allergens panel. Deferred to ND.06+.
- **Voice ordering:** Web Speech API, NLP parsing. Deferred to ND.08+.
- **AI recommendations:** Personalized suggestions, predictive ordering. Deferred to ND.07+.
- **Add-to-cart fly animation:** Complex image-flying-to-cart-icon animation. Deferred to ND.04.
- **Real-time menu search indexing (OpenSearch):** Client-side or simple SQL search is sufficient for score 3.
- **Backend pagination for filters:** Client-side filtering is acceptable if restaurant dataset is <200 records.
- **Push notifications for favorites/restock:** Notification system not required for score 3.

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.04 or PR.05 complete).
- Auth persistence must work so favorites and reorder are available to logged-in users.
- Guest cart must work (localStorage/Zustand) but favorites and reorder are hidden/disabled for guests.
- Restaurant list API must return sufficient fields for filters and improved cards.
- Menu items must have `is_veg`, `category`, `item_type`, `order_count` (or `is_bestseller`) populated.
- Zustand cart store must support programmatic pre-filling (for reorder).
- Cross-restaurant cart guard must exist (or be built as part of this scope).
- Design system (BhojanGo palette, typography, spacing, Lucide icons) must be applied across all new UI.
- Toast/snackbar component must exist for confirmations.

## 8. Key User Journeys

### Journey 8.1 — First-Time User Finds Vegetarian Food Fast
1. User opens app, sees homepage with "Delivering to {city}".
2. Taps "Find Food" → `/restaurants`.
3. Taps "Veg Only" filter chip → list filters to pure-veg and veg-friendly restaurants.
4. Taps "4+ ⭐" → further narrows to top-rated veg options.
5. Taps a restaurant card. Card already showed green "Pure Veg" badge, "FSSAI Verified" trust mark, "30-35 min" delivery time, and "₹30" delivery fee.
6. On detail page, "Veg Only" toggle is ON by default because user had "Veg Only" filter active.
7. Sees sticky category tabs: "Starters | Mains | Breads | Desserts | Combos".
8. Taps "Mains" → scrolls to main-course section.
9. Sees "⭐ Bestseller" badge on Paneer Tikka Masala.
10. Taps "+" quick-add on Paneer Butter Masala → toast "Paneer Butter Masala added to cart".
11. Cart badge on navbar updates.

### Journey 8.2 — Returning User Reorders from History
1. User logs in, auth persists, navbar shows name.
2. Navigates to `/orders`, sees 8-10 past orders with status badges and dates.
3. Finds a previous biryani order from "Spice Garden" and taps "Reorder" button on the card.
4. Toast: "3 items added to your cart from Spice Garden".
5. Cart icon in navbar updates to 3 items.
6. Navigates to `/cart` → exact same items, quantities, and customizations pre-filled.
7. Proceeds to checkout with saved address, places order.

### Journey 8.3 — User Saves Favorites and Revisits Them
1. User browses `/restaurants`, sees 3 restaurants they like.
2. Taps heart on each card → hearts fill, toast: "Saved to favorites".
3. Returns to homepage → "Your Favorites" horizontal scroll section shows all 3 restaurants.
4. Navigates to `/favorites` → grid layout with all 3 cards, each with remove (X) button.
5. Removes one restaurant → toast: "Removed from favorites".
6. Returns to homepage → "Your Favorites" now shows 2 restaurants.
7. Empty state: user removes all favorites → `/favorites` shows empty heart illustration + "Browse Restaurants" CTA.

### Journey 8.4 — User Filters and Discovers New Restaurants
1. User on `/restaurants`, sees 96 unfiltered cards.
2. Taps "4+ ⭐" → list filters to 42 restaurants.
3. Taps "Under 30 min" → list filters to 18 restaurants.
4. Taps "₹200-₹500" → list filters to 9 restaurants.
5. Active filters shown as pills: "4+ ⭐" · "Under 30 min" · "₹200-₹500".
6. Taps "X" on "₹200-₹500" pill → filters update to 18 restaurants.
7. Taps "Clear All" → returns to all 96 restaurants.
8. URL updates to `/restaurants?min_rating=4&max_time=30&price=2`.

### Journey 8.5 — User Searches Within a Restaurant Menu
1. User opens a restaurant detail page with 30+ menu items.
2. Sees "Search within menu" input above category tabs.
3. Types "naan" → menu filters to show Garlic Naan, Butter Naan, Cheese Naan.
4. Category tabs still visible but only relevant categories shown (e.g., "Breads").
5. Taps "X" in search input → search clears, full menu restored.
6. Taps "Mains" tab → scrolls to Mains section, search filter still active if query remains.

## 9. Technical Coverage

### Backend
- **user-svc or restaurant-svc:** `favorites` table CRUD: `POST /api/v1/favorites` (body: `{restaurant_id}`), `DELETE /api/v1/favorites/{restaurant_id}`, `GET /api/v1/favorites` (returns restaurant details joined from `restaurants` table). Unique constraint on (`user_id`, `restaurant_id`). Index on `user_id` for fast lookup.
- **restaurant-svc:** Extend `GET /api/v1/restaurants` response to include: `cuisine_types[]`, `rating`, `avg_delivery_time_min`, `delivery_fee`, `is_pure_veg`, `is_fssai_verified`, `is_open`, `opens_at`, `closes_at`.
- **restaurant-svc:** Ensure `GET /api/v1/restaurants/{id}/menu` returns `is_veg`, `category` (string), `item_type` ('single' | 'combo'), `is_bestseller` (boolean), `order_count` (integer) for every menu item.
- **order-svc:** Ensure `GET /api/v1/orders/{id}` returns full item details including `menu_item` object with `name`, `is_veg`, `image_url`, `price`, `quantity`, and `customizations` for reorder pre-fill.
- **order-svc:** `POST /api/v1/orders/{id}/reorder` endpoint (optional — can be client-side only by reusing existing order detail endpoint and pre-filling cart).

### Frontend
- **Zustand store extensions:** `favoritesStore` (array of `restaurant_id`s, add/remove/toggle actions, optimistic updates). `filterStore` (active filters state, URL sync via `useSearchParams`).
- **Components:**
  - `<FavoriteButton />` — heart toggle with optimistic UI.
  - `<FavoritesSection />` — horizontal scroll on homepage.
  - `<FavoritesPage />` — `/favorites` grid with empty state.
  - `<FilterBar />` — chip row with active filter pills and "Clear All".
  - `<VegIndicator />` — green/red dot with tooltip.
  - `<MenuCategoryTabs />` — sticky tabs with scroll-to-section.
  - `<MenuSearch />` — debounced input with clear button.
  - `<BestsellerBadge />` — star icon + "Bestseller" text.
  - `<QuickAddButton />` — "+" circle, conditional modal opening for customizations.
  - `<RestaurantCardV2 />` — updated card with cuisine chips, delivery info, trust badges, open status, heart toggle.
- **Hooks:** `useFavorites()` (fetch, mutate, optimistic), `useMenuSearch(items[], query)` (client-side filter), `useFilters()` (URL-persisted filter state).

### Data
- New table: `favorites` (`id` UUID PK, `user_id` UUID FK → `users.id`, `restaurant_id` UUID FK → `restaurants.id`, `created_at` TIMESTAMP, UNIQUE (`user_id`, `restaurant_id`)).
- Extended columns on `restaurants`: verify `is_pure_veg` (BOOLEAN, computed from menu items or stored), `is_fssai_verified` (BOOLEAN), `avg_delivery_time_min` (INTEGER), `delivery_fee` (DECIMAL), `opens_at` (TIME), `closes_at` (TIME).
- Extended columns on `menu_items`: verify `is_veg` (BOOLEAN), `category` (VARCHAR), `item_type` (VARCHAR), `is_bestseller` (BOOLEAN), `order_count` (INTEGER, default 0).
- Seed data updates: ensure all `menu_items` have `is_veg` populated. Set `is_bestseller=true` for top 3 items per restaurant by `order_count`. Seed `category` values consistently.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for `/favorites`, skeleton tabs for menu categories during menu load.
- **Error states:** Error boundary on `/favorites`. API failure toasts for favorite toggle failures ("Could not save favorite. Try again."). Reorder failure toast if order items no longer available.
- **Empty states:** Empty `/favorites` with heart illustration + "Browse Restaurants" CTA. Empty menu search: "No items match '{query}'." Filtered restaurant list with no results: "No restaurants match your filters. Try adjusting."
- **Success states:** Toast on add-to-favorites, remove-from-favorites, reorder, quick-add, filter clear.
- **Design system:** All new components follow BhojanGo palette (`#E65100` primary, `#2E7D32` trust green, `#FFB300` accent, `#F7F5F2` cream, `#1A1A1A` dark), Manrope + Inter typography, 4px grid, Lucide icons, badge/card anatomy from ND.02.
- **Indian food specifics:** Veg dots are green (not generic gray). Pure Veg badge uses trust green. Non-veg dots are red. Jain items get "J" pill in addition to veg dot. Spice level shown with chili icons.
- **Responsive:** Filter chips wrap on mobile (2 rows). Category tabs horizontally scrollable on mobile. Favorites grid: 1 col mobile, 2 col tablet, 3 col laptop, 4 col desktop. Quick-add button is 44px tap target on mobile.
- **Dark mode:** Veg dots remain green, non-veg dots remain red (color has meaning). Cards, badges, and pills render correctly. No black-on-black text.
- **Accessibility:** Filter chips have `role="button"` and `aria-pressed`. Favorite heart has `aria-label="Add {restaurant} to favorites"`. Menu category tabs use `role="tablist"`. Veg/non-veg dots have `aria-label`. Search input has `aria-label="Search within menu"`. Toast uses `role="status"`.

## 11. Data / Model Coverage

- `favorites` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `restaurant_id` UUID FK → `restaurants.id`, `created_at` TIMESTAMP. Unique constraint on (`user_id`, `restaurant_id`). Index on `user_id`.
- `restaurants` table (extended): `is_pure_veg` BOOLEAN (default NULL, computed or stored), `is_fssai_verified` BOOLEAN (default false), `avg_delivery_time_min` INTEGER (default 30), `delivery_fee` DECIMAL(10,2) (default 30.00), `opens_at` TIME, `closes_at` TIME. Add via migration if missing.
- `menu_items` table (extended): `is_veg` BOOLEAN (default true), `category` VARCHAR (default 'Mains'), `item_type` VARCHAR (default 'single'), `is_bestseller` BOOLEAN (default false), `order_count` INTEGER (default 0). Add via migration if missing.
- `orders` table (existing): `items` JSONB already stores `menu_item_id`, `quantity`, `customizations` — sufficient for reorder pre-fill.
- `order_items` or equivalent (if exists): must expose `is_veg` so order history shows veg dots.
- Seed data: populate `is_veg` for all menu items (default true for Indian cuisine majority). Set `is_bestseller=true` on 3 items per restaurant. Ensure `category` values are consistent across all restaurants.

## 12. Role / Permission Coverage

- `customer` (logged-in): Full access to all ND.03 features — favorites CRUD, reorder, all filters, veg toggle, menu search, quick-add.
- Guest (unauthenticated): Can use all filters, veg toggle, menu search, quick-add. Cannot use favorites (heart hidden or prompts login on tap). Cannot reorder (button hidden).
- `restaurant_owner`, `delivery_partner`, `admin`: Not involved in ND.03 (customer-facing features only).

## 13. Performance / Reliability / Security Coverage

### Performance
- Favorites list is a single indexed query by `user_id` — <10ms.
- Menu search is client-side (filtering <50 items) — instant, no API call.
- Restaurant filters: if dataset >100 records, backend filtering with indexed WHERE clauses. If <100 records, client-side filtering is sufficient and faster for interactivity.
- Reorder pre-fill reads from existing order detail endpoint — no new heavy query.
- Quick-add reuses existing cart mutation — no new endpoint.

### Reliability
- Favorite toggle uses optimistic UI: heart fills immediately, API call in background. On failure, heart reverts and toast shows error. Prevents perceived lag.
- Reorder gracefully handles items that no longer exist: if a `menu_item_id` from a previous order is not found in current menu, skip that item with toast: "{item_name} is no longer available."
- Filter state synced to URL: refreshing the page preserves active filters. Sharing `/restaurants?min_rating=4&veg_only=true` works.
- Menu category tabs use smooth scroll behavior (`scroll-behavior: smooth`). Intersection Observer can highlight active tab as user scrolls.
- Quick-add for items with required customizations opens the modal instead of silently adding incomplete item — prevents invalid orders.

### Security
- Favorites endpoints verify authenticated user matches `user_id` in token. Users cannot query or modify other users' favorites.
- Reorder endpoint verifies order belongs to current user. Users cannot reorder someone else's order.
- Filter params in URL are sanitized before use in SQL. No injection risk if using SQLAlchemy parameterized queries.
- No PII exposure in filter state or menu search.

## 14. Novelty / Differentiation Coverage

At score 3, differentiation is about **competence and usability**, not uniqueness. These are standard features that every competitor has, but their absence signals a low-quality product. Their presence signals that BhojanGo is a serious, usable platform.

- **Favorites + Reorder:** Core retention loops. Favorites create a personal relationship with the app. Reorder reduces friction for the most common action (eating the same thing again). Together they make repeat usage effortless.
- **Better Filters:** Discovery speed. A user who can find "4+ star veg restaurants under 30 minutes" in 3 taps will prefer this app over one that requires scrolling.
- **Veg/Non-Veg Visibility:** Cultural necessity for the Indian market. Swiggy and Zomato both have prominent veg filtering. BhojanGo's mandatory dots and "Veg Only" toggle make dietary preference a first-class citizen.
- **Cleaner Menu Discovery:** Category tabs, bestseller badges, and search within menu reduce cognitive load. Users find what they want faster, order more confidently.
- **Improved Restaurant Cards:** Information density without clutter. Users make decisions without clicking into detail pages. Trust badges (FSSAI, Pure Veg) reduce anxiety.
- **Quick Add:** Micro-optimization that removes one tap from the most frequent action. The difference between "tap +" and "tap card → tap modal → tap add" is meaningful at scale.

**Differentiators deferred to higher scores:**
- Add-to-cart fly animation (ND.04 — visual delight).
- AI-powered "Order Again" suggestions (ND.07 — smart personalization).
- Nutritional info panel (ND.06 — health differentiation).
- Group ordering (ND.06 — social differentiation).
- Meal rescue (ND.06 — sustainability differentiation).

## 15. Implementation Work Items

### IP.ND.03.001 — Favorites Table + API
- **Category:** Backend + Data
- **Implementation Scope:** Create `favorites` table with `id` UUID PK, `user_id` UUID FK, `restaurant_id` UUID FK, `created_at` TIMESTAMP, UNIQUE constraint on (`user_id`, `restaurant_id`), index on `user_id`. Add three endpoints: `POST /api/v1/favorites` (body `{restaurant_id}`) — idempotent toggle that inserts or errors if already exists, `DELETE /api/v1/favorites/{restaurant_id}` — remove, `GET /api/v1/favorites` — list with full restaurant details joined from `restaurants` table (name, image_url, rating, cuisine_types, avg_delivery_time_min). Endpoints must verify authenticated user and only operate on their own favorites.
- **Acceptance Criteria:**
  1. `POST /api/v1/favorites` with `{restaurant_id}` creates a favorite for the authenticated user.
  2. `DELETE /api/v1/favorites/{restaurant_id}` removes the favorite.
  3. `GET /api/v1/favorites` returns all favorite restaurants for the authenticated user with full details.
  4. Duplicate favorite creation returns 409 or is silently ignored.
  5. All endpoints reject unauthenticated requests with 401.
- **Evidence Required:** `curl` outputs for all three endpoints. DB query: `SELECT COUNT(*) FROM favorites WHERE user_id = ?`.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.002 — Favorite Heart Toggle + Homepage Section
- **Category:** Frontend
- **Implementation Scope:** Add heart icon to every restaurant card and restaurant detail page header. Use Lucide `Heart` (empty/outline) and `Heart` filled. Implement optimistic UI: on tap, heart toggles immediately, API call fires in background. On success, no extra toast (silent). On failure, revert heart and show toast "Could not update favorite. Try again." Add "Your Favorites" horizontal scroll section to homepage below hero, displaying up to 6 most recent favorites. Section hidden when user has 0 favorites. Heart state fetched on app mount (via `GET /api/v1/favorites`).
- **Acceptance Criteria:**
  1. Heart toggle visible on all restaurant cards and detail pages.
  2. Tapping heart fills/empties immediately (optimistic UI).
  3. Homepage shows "Your Favorites" section with bookmarked restaurants.
  4. Section hidden when no favorites exist.
  5. Heart state persists across page refreshes.
- **Evidence Required:** Screenshots: restaurant card with filled/empty heart, homepage with favorites section, detail page header with heart.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.03.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.003 — Favorites List Page
- **Category:** Frontend
- **Implementation Scope:** New `/favorites` page. Grid layout of restaurant cards (same `<RestaurantCardV2 />` component as listing). Each card has remove (X) button in top-right. Empty state: centered illustration (empty heart SVG from design system), text "No favorites yet", "Browse Restaurants" CTA button linking to `/restaurants`. Loading state: skeleton grid of 6 cards. Error state: "Could not load favorites." with retry button. Responsive: 1 col mobile, 2 col tablet, 3 col laptop, 4 col desktop.
- **Acceptance Criteria:**
  1. `/favorites` page lists all favorite restaurants as cards.
  2. Remove (X) button removes a favorite with toast confirmation.
  3. Empty state shows illustration + "Browse Restaurants" CTA.
  4. Page works on mobile, tablet, and desktop breakpoints.
- **Evidence Required:** Screenshots: populated `/favorites`, empty `/favorites`, mobile view.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.03.001, IP.ND.03.002
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.004 — Reorder Button + Cart Pre-Fill
- **Category:** Frontend + Backend
- **Implementation Scope:** "Reorder" button on every order history card and order detail page. Button visible only for logged-in users; hidden for guests. On tap: call `GET /api/v1/orders/{id}` (existing endpoint) to fetch previous items. Pre-fill Zustand cart with exact `menu_item_id`, `quantity`, `selected_add_ons`, `customizations` from order. If current cart is empty, pre-fill directly. If current cart has items from same restaurant, merge quantities (increment). If current cart has items from a different restaurant, show cross-restaurant guard modal: "Your cart has items from {current_restaurant}. Replace with items from {new_restaurant}?" with "Replace" and "Cancel" actions. On confirm, clear cart and pre-fill. Toast: "{N} items added from {restaurant_name}". Navigate to `/cart`. Handle unavailable items gracefully: skip item with toast "{name} is no longer available."
- **Acceptance Criteria:**
  1. Reorder button visible on order history and detail pages for logged-in users.
  2. Tapping pre-fills cart with exact items and quantities from previous order.
  3. Cross-restaurant guard triggers when cart has items from a different restaurant.
  4. Unavailable items are skipped with a toast.
  5. User lands on `/cart` after reorder.
- **Evidence Required:** Screen recording: `/orders` → tap Reorder → cart pre-filled.
- **Priority:** P0
- **Effort:** M
- **Dependency:** Working order history (PR.04 or PR.05 prerequisite)
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.005 — Filter System Enhancement (Rating / Veg / Price / Time)
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Extend `GET /api/v1/restaurants` to accept optional query params: `?min_rating=4.0`, `?veg_only=true`, `?price_range=1|2|3` (1=Under ₹200, 2=₹200-₹500, 3=₹500+), `?max_delivery_time=30`. Apply as WHERE clauses in SQLAlchemy query. Return filtered results with same pagination. **Frontend:** Add filter chip row below search bar on `/restaurants`: "4+ ⭐", "Veg Only", "Under ₹200", "₹200-₹500", "₹500+", "Under 30 min". Single-select for price range, toggle for others. Active chips highlighted with primary color. Active filters shown as removable pills above grid with "Clear All" button. Filter state synced to URL query params via `useSearchParams`. On page load, read URL params and pre-apply filters.
- **Acceptance Criteria:**
  1. Each filter chip correctly narrows the restaurant list.
  2. Price range is single-select; other filters are multi-toggle.
  3. Active filters displayed as removable pills.
  4. "Clear All" removes all active filters.
  5. Filter state reflected in URL and preserved on refresh.
- **Evidence Required:** Screenshots: restaurant list with "4+ ⭐ + Veg Only" active, filtered results, URL with params, "Clear All" state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.006 — Veg/Non-Veg Mandatory Dots
- **Category:** Frontend + Data
- **Implementation Scope:** **Data:** Ensure `menu_items.is_veg` is populated for ALL seeded items (default true for Indian cuisine, false for non-veg items). Add `is_veg` to every menu item API response. **Frontend:** Add `<VegIndicator />` component: green circle (CSS `background-color: #2E7D32`) for veg, red circle (`#C62828`) for non-veg. Render on: (a) menu item card at top-left of image, (b) cart row next to item name, (c) order history item list next to item name, (d) customization modal next to item name. Add tooltip: "Vegetarian" / "Non-vegetarian". On restaurant list: "Veg Only" filter chip (already in IP.ND.03.005). On restaurant card: if `is_pure_veg=true`, show green "Pure Veg" badge. On restaurant detail: add "Veg Only" toggle switch next to category tabs. When ON, filter menu items client-side to show only `is_veg=true`. Toggle label: "Veg Only" with green leaf icon.
- **Acceptance Criteria:**
  1. Every menu item card displays a green or red dot.
  2. Cart rows show veg dot next to item name.
  3. Order history shows veg dot next to item name.
  4. "Veg Only" toggle on restaurant detail filters menu to veg items only.
  5. Pure-veg restaurants show green "Pure Veg" badge on cards.
- **Evidence Required:** Screenshots: menu item cards, cart, order history, restaurant card with Pure Veg badge, detail page with Veg Only toggle ON.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.03.005
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.007 — Menu Category Tabs + Bestseller Badges + Search Within Menu
- **Category:** Frontend
- **Implementation Scope:** **Sticky category tabs:** On restaurant detail page, add horizontal sticky tab bar above menu: "All | Starters | Mains | Breads | Desserts | Combos". Tabs generated dynamically from unique `category` values in menu items. "All" tab shows all items. Clicking a tab smooth-scrolls to that category section. Active tab highlighted with primary color underline. Use Intersection Observer to update active tab as user scrolls. **Bestseller badges:** Query or seed `is_bestseller` flag. Render "⭐ Bestseller" badge (yellow pill with star icon) on top 3 items per category. Badge positioned top-right of item image. **Search within menu:** Add search input above tabs with placeholder "Search within menu...". Debounce 200ms. Filters items by `name` and `description` (client-side). Empty state: "No items match '{query}'." Clear button (X) inside input. Search + category filter work together (e.g., search "naan" + click "Breads" shows only bread naans).
- **Acceptance Criteria:**
  1. Sticky tabs visible with all unique menu categories.
  2. Clicking tab scrolls to category section.
  3. Bestseller badges visible on 3 items per category.
  4. Menu search filters items by name with debounce.
  5. Search + category tabs work in combination.
- **Evidence Required:** Screenshots: category tabs, bestseller badges, menu search filtering, empty search state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.03.006
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.008 — Restaurant Card Information Density Increase
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Verify `GET /api/v1/restaurants` returns: `cuisine_types[]`, `rating` (DECIMAL), `avg_delivery_time_min` (INTEGER), `delivery_fee` (DECIMAL), `is_pure_veg` (BOOLEAN), `is_fssai_verified` (BOOLEAN), `is_open` (BOOLEAN), `opens_at`, `closes_at`, `image_url`. Add missing fields via migration if needed. **Frontend:** Update `<RestaurantCard />` component:
  - Image (16:10, rounded-xl top) with subtle gradient overlay from bottom.
  - Rating badge: absolute top-right, "{rating} ⭐" text on primary-tinted background.
  - Heart toggle: absolute top-right (left of rating badge or below it).
  - Name: h3, Manrope font, 2 lines max with ellipsis.
  - Cuisine chips: row of 2-3 small pills below name, neutral background, showing cuisine types.
  - Delivery row: "⏱ {min}-{max} min · ₹{delivery_fee}" in muted text.
  - Trust badges row: "FSSAI Verified" with shield icon (if `is_fssai_verified`), "Pure Veg" with leaf icon (if `is_pure_veg`).
  - Open/closed status: green "Open" pill or gray "Opens at {time}" pill. Closed cards: 60% opacity, no hover lift effect.
- **Acceptance Criteria:**
  1. Every restaurant card shows cuisine chips, rating, delivery time, delivery fee.
  2. Trust badges (FSSAI, Pure Veg) visible when applicable.
  3. Open/closed status clearly shown as a pill.
  4. Closed restaurant cards are dimmed.
- **Evidence Required:** Screenshots: restaurant cards showing all new fields, open and closed states side by side.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.009 — Quick Add-to-Cart Behavior
- **Category:** Frontend
- **Implementation Scope:** On menu item card (restaurant detail page), add a circular "+" button (32px desktop, 44px mobile) at bottom-right of card. Background: primary color `#E65100`, icon: white Lucide `Plus`. Tapping it: (1) if item has NO required customizations and `item_type !== 'combo'`, add 1 quantity directly to Zustand cart, toast "{item_name} added to cart", cart badge updates. (2) if item HAS required customizations OR `item_type === 'combo'`, open existing customization modal (same as current tap-on-card behavior). (3) if item is non-veg and user has "Veg Only" toggle ON, do not show quick-add button (item is already filtered out). If restaurant is closed, quick-add button is disabled (grayed out, no action). Quick-add button has `title` tooltip: "Quick add to cart".
- **Acceptance Criteria:**
  1. Quick-add button visible on menu item cards for items without required customizations.
  2. Tapping quick-add adds item directly to cart with toast.
  3. Items with required customizations open modal on tap.
  4. Closed restaurant disables quick-add.
  5. Button is touch-friendly (>=44px on mobile).
- **Evidence Required:** Screen recording: tap quick-add → toast → cart badge updates. Screenshot: quick-add buttons on menu cards.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.03.007
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.03.010 — Seed Data Completion for ND.03
- **Category:** Data
- **Implementation Scope:** Ensure seed data supports all ND.03 features:
  1. All `menu_items` have `is_veg` populated (true for ~70% of Indian items, false for chicken/mutton/egg/fish items).
  2. All `menu_items` have `category` populated consistently (Starters, Mains, Breads, Desserts, Combos).
  3. All `menu_items` have `item_type` populated ('single' or 'combo').
  4. Set `is_bestseller=true` for top 3 items per restaurant by `order_count` (or manually curated).
  5. All `restaurants` have `cuisine_types[]`, `rating`, `avg_delivery_time_min`, `delivery_fee`, `is_pure_veg` (computed: true if all menu items are veg), `is_fssai_verified` (true for ~80%), `opens_at`, `closes_at` populated.
  6. Ensure `orders` table has at least 5-10 orders per demo user with varied items so reorder is demonstrable.
- **Acceptance Criteria:**
  1. Every menu item has `is_veg`, `category`, `item_type`.
  2. Every restaurant has `cuisine_types`, `rating`, `delivery_time`, `fee`, `opens_at`, `closes_at`.
  3. 3 bestseller items per restaurant flagged.
  4. Demo users have sufficient order history for reorder demo.
- **Evidence Required:** DB query outputs: `SELECT COUNT(*) FROM menu_items WHERE is_veg IS NULL`, `SELECT COUNT(*) FROM restaurants WHERE avg_delivery_time_min IS NULL`, etc.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Favorites API works: `POST`, `DELETE`, `GET /api/v1/favorites` all return correct data with auth.
- [ ] Heart toggle on restaurant cards and detail pages uses optimistic UI and persists to DB.
- [ ] Homepage shows "Your Favorites" section with up to 6 bookmarked restaurants; hidden when empty.
- [ ] `/favorites` page lists all favorites with remove (X) button and empty state with illustration + CTA.
- [ ] Reorder button on order history cards pre-fills cart with exact items + quantities from previous order.
- [ ] Cross-restaurant cart guard triggers on reorder when current cart has items from a different restaurant.
- [ ] Unavailable items from previous order are skipped with a toast.
- [ ] Filter chips (4+ ⭐, Veg Only, price ranges, Under 30 min) correctly filter restaurant list.
- [ ] Active filters shown as removable pills with "Clear All" button.
- [ ] Filter state synced to URL query params and preserved on refresh.
- [ ] Every menu item displays green (veg) or red (non-veg) dot on cards, cart, and order history.
- [ ] "Veg Only" toggle on restaurant detail filters menu to veg items only.
- [ ] Pure-veg restaurants show green "Pure Veg" badge on cards.
- [ ] Sticky category tabs on restaurant detail: "All | Starters | Mains | Breads | Desserts | Combos".
- [ ] Clicking a category tab smooth-scrolls to that section.
- [ ] Bestseller badges (⭐) visible on top 3 items per category.
- [ ] Search-within-menu filters items by name with 200ms debounce.
- [ ] Restaurant cards show: cuisine chips, rating, delivery time, delivery fee, trust badges, open/closed status.
- [ ] Closed restaurant cards are dimmed to 60% opacity.
- [ ] Quick-add "+" button on menu item cards adds directly to cart without opening modal (for items without required customizations).
- [ ] Items with required customizations or combos open modal on quick-add tap.
- [ ] All new UI follows BhojanGo design system (palette, typography, spacing, Lucide icons).
- [ ] All new features work on mobile, tablet, and desktop breakpoints.
- [ ] All new features render correctly in dark mode.
- [ ] Seed data fully supports all ND.03 features.

## 17. Evidence Required

- Screenshots:
  - Restaurant card (new anatomy): showing cuisine chips, rating, delivery time, fee, trust badges, heart toggle, open/closed status.
  - Restaurant list with active filters: "4+ ⭐ + Veg Only + Under 30 min" and filtered results.
  - Filter pills and "Clear All" button.
  - Restaurant detail with sticky category tabs active.
  - Menu items with veg dots, bestseller badges, and quick-add buttons.
  - "Veg Only" toggle ON showing only veg items.
  - Menu search with results and empty state.
  - Homepage with "Your Favorites" section.
  - `/favorites` page populated and empty state.
  - Cart rows showing veg dots next to item names.
  - Order history with "Reorder" button visible.
- Screen recordings:
  - Tap heart on 3 restaurant cards → homepage favorites section updates → navigate to `/favorites` → remove one → toast.
  - `/orders` → tap Reorder → cart pre-filled with exact items → proceed to checkout.
  - Quick-add 3 items → toasts confirm → cart badge updates.
  - Apply "4+ ⭐ + Veg Only" filters → copy URL → paste in new tab → filters preserved.
  - Restaurant detail → click "Mains" tab → scrolls to section → search "naan" → shows filtered results.
- API evidence:
  - `curl` output for `GET /api/v1/favorites`.
  - `curl` output for `POST /api/v1/favorites` and `DELETE /api/v1/favorites/{id}`.
  - `curl` output for `GET /api/v1/restaurants?min_rating=4&veg_only=true`.
- DB evidence:
  - Query results confirming `menu_items.is_veg` and `category` are 100% populated.
  - Query results confirming `restaurants` fields (cuisine_types, rating, delivery_time, fee, opens_at, closes_at) are 100% populated.

## 18. Dependencies

### External Tools
- PostgreSQL (for favorites table and menu item fields).
- Node.js + pnpm (frontend build).
- Lucide React (icon library — already used from ND.02).
- Existing TanStack Query or SWR (for data fetching — required for optimistic UI).

### Internal Dependencies
- **PR.04 or PR.05 must be complete:** Stable core loop (browse → menu → cart → checkout → track) is prerequisite. Auth persistence must work.
- **ND.02 (Distinctive Visual Identity) must be complete:** Design system (palette, typography, spacing, badges, cards) must be applied. If ND.02 is not done, ND.03 UI will look inconsistent.
- **Cart Zustand store** must support programmatic pre-fill (for reorder) and item merging.
- **Cross-restaurant cart guard** must exist or be built as part of IP.ND.03.004.
- **Menu customization modal** must exist for quick-add fallback behavior.
- **Restaurant list API** must return sufficient fields for filters and improved cards.

## 19. Risks / Blockers

- **Favorites table migration requires Alembic or manual SQL.** If the service managing favorites does not have Alembic configured, a manual migration script must be provided. Mitigation: document raw SQL migration in work item notes.
- **Menu items may lack `is_veg` data in existing seed.** If `is_veg` is NULL for many items, veg filtering and dots will be unreliable. Mitigation: IP.ND.03.010 explicitly covers seed data completion — must be completed before dependent work items.
- **Cross-restaurant cart guard may not exist yet.** If PR.04 did not implement guard logic, IP.ND.03.004 will need to include guard implementation. Mitigation: scope IP.ND.03.004 to include guard if missing.
- **Restaurant card redesign may conflict with existing card usage.** If restaurant cards are used in multiple places (homepage, /restaurants, /favorites, similar restaurants), updating the anatomy requires touching all instances. Mitigation: ensure `<RestaurantCardV2 />` is a single shared component used everywhere.
- **Filter state in URL may conflict with existing search params.** If `/restaurants` already uses query params for city or search, filter params must be additive (e.g., `?city=Hyderabad&min_rating=4`). Mitigation: use unique param keys (`min_rating`, `veg_only`, `price_range`, `max_time`).
- **Menu category tabs with Intersection Observer may cause jank on mobile.** Smooth scrolling + scroll event listeners can be performance-intensive on low-end devices. Mitigation: use `IntersectionObserver` with `rootMargin` instead of scroll listeners. Debounce tab updates.
- **Quick-add for items with required customizations.** If customization data is not available client-side (e.g., fetched only on modal open), quick-add cannot determine whether customizations are required. Mitigation: include `has_required_customizations` boolean in menu item API response.

## 20. Exit Criteria

- All P0 work items (IP.ND.03.001 through IP.ND.03.008, IP.ND.03.010) implemented and verified.
- All P1 work items (IP.ND.03.009) implemented and verified.
- Favorites system complete: API + heart toggle + homepage section + `/favorites` page.
- Reorder works: button on history cards, cart pre-fill, cross-restaurant guard.
- Filters work: all 4 filter types, active filter pills, URL sync, Clear All.
- Veg/non-veg dots visible on every menu item, cart row, order history item.
- Menu discovery: category tabs, bestseller badges, search-within-menu.
- Restaurant cards show all required info: cuisine chips, rating, delivery time, fee, trust badges, open status.
- Quick-add behavior functional for items without required customizations.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.03 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.02)

ND.03 directly depends on ND.02 achievements:
- **ND.02 Design System:** BhojanGo palette (`#E65100`, `#2E7D32`, `#FFB300`, `#F7F5F2`, `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons, badge/card anatomy — required for all new UI.
- **ND.02 Component Library:** Existing button, card, pill, and badge components are foundation for filter chips, restaurant cards, and menu item cards.
- **ND.02 Responsive Layout:** Mobile, tablet, laptop, TV breakpoints must be in place for all new pages/sections.
- **ND.02 Dark Mode:** All new components must render correctly in dark mode.
- **PR.04/PR.05 Core Loop:** The browse → menu → cart → checkout → track flow must be stable before adding convenience features on top.

## 22. Connected Next-Level Requirements (link to ND.04)

ND.04 (Demo-Level Differentiation, score 4/10) builds on ND.03 and requires:
- Working favorites system (IP.ND.03.001–003) as foundation for personalized homepage sections.
- Working reorder (IP.ND.03.004) as foundation for smart reorder suggestions.
- Working filters (IP.ND.03.005) as foundation for advanced discovery (fastest-near-you lane, meal tags).
- Working veg visibility (IP.ND.03.006) as foundation for dietary preference persistence.
- Working menu discovery (IP.ND.03.007) as foundation for combo/thali builder enhancement.
- Working improved restaurant cards (IP.ND.03.008) as foundation for trust badge expansion.
- Working quick-add (IP.ND.03.009) as foundation for add-to-cart fly animation.

ND.04 will introduce:
- Add-to-cart fly animation (visual delight).
- "Fastest Near You" lane on homepage.
- Meal tags (spice level, cuisine, dietary badges).
- Loyalty preview (points visible, not yet redeemable).
- Smart reorder (AI-suggested reorder based on time/day).
- Better trust badges (freshness score, delivery confidence).
- Local-first discovery (sort by distance with live ETA).

ND.04 will be blocked if:
- Favorite toggle is broken or loses data.
- Reorder does not pre-fill cart accurately.
- Filters do not work or are not synced to URL.
- Veg/non-veg dots are missing or incorrect.
- Menu search or category tabs are non-functional.
- Restaurant cards still lack key info.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (3/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.02 + PR.04/05) described | Planner | ✅ |
| 4 | Target state (ND.03 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.03 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.03 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (5 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (favorites table, extended columns) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why these table-stakes features matter for differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.03.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: favorites API + UI + page, reorder, filters, veg dots, menu tabs/search, restaurant cards, quick-add, seed data | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention migration, seed data gaps, cart guard, URL conflicts, mobile jank, customization data | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.02) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.04) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: favorites (API + heart toggle + homepage + page), reorder, filters, veg dots, menu tabs/search/bestseller, restaurant cards, quick-add, seed data completion.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known gaps from the audits (missing `is_veg` data, missing Alembic setup, cart guard uncertainty).
- The plan strictly stays within score 3 scope: table-stakes convenience features with no production infrastructure, no AI, no gamification, no animations beyond minimal toast.
- Feasibility is LOCAL/DEMO-SAFE: all work items use existing stack (PostgreSQL, Next.js, Zustand, Lucide) with no new external dependencies.
- **One point deducted** because exact file paths for migrations and component locations are not specified from the plan stage. The build phase will need to discover these. This is expected for a planning document.

The document is ready for execution.
