# IP.ND.04 — Demo Level Differentiation

## 1. Target Differentiation Score: 4/10

## 2. Score Meaning

User can see practical unique touches: fastest-near-you lane, meal tags, loyalty preview, smart reorder, better trust badges, and local-first discovery. At score 4, the app has visible, demonstrable differences that can be shown in a 5-minute demo. These are lightweight features that make the app feel thoughtful and tailored — not table-stakes utilities, but small moments of intelligence and locality that stick in the user's memory. The app no longer feels like a generic clone; in a side-by-side comparison with a basic Swiggy/Zomato demo, a user can point to specific UI elements and say "this app does that differently."

## 3. Current → Target Transition

**From ND.03 (Small Convenience Features):**
- Favorites, reorder, filters, veg/non-veg visibility, menu category tabs, bestseller badges, search-within-menu, quick add-to-cart, and improved restaurant cards are all implemented.
- The core ordering loop is stable and pleasant for repeat users.
- The app is a competent daily driver but still looks and behaves like many other delivery apps at first glance.
- The homepage is largely a static hero + restaurant grid with no intelligence about time, location, or user behavior.
- Restaurant cards show basic trust signals (FSSAI, Pure Veg) but nothing about freshness, speed, or temperature.
- There is no visible loyalty program despite points being stored in the database.
- Reorder exists but is a manual button press; the app never proactively suggests "you usually order biryani on Saturdays."
- The "fastest near you" concept is absent — users must scroll to discover quick options.
- There are no trending indicators, no "what's hot" social proof, and no temperature-based freshness cues.

**Target at score 4:**
- Homepage feels alive: "Fastest Near You" horizontal carousel sorts top 5 restaurants by (distance + speed score) with an "Under 30 min" badge.
- Meal mood banner greets the user contextually — "Good morning — craving idli?" based on time of day and day of week.
- Restaurant cards display 3 trust badges: FSSAI Verified, Freshly Prepared in X min, Under 30 min Delivery.
- Wallet page shows a loyalty preview — points bar, "Start ordering to earn!" CTA, and visible "+45 BhojanGo Points" in cart.
- Smart reorder suggestion appears on the homepage if the user's last order was <30 days ago — "Same as last time?" with item thumbnails.
- Homepage sections for "Near You Today" and "Trending in [Locality]" create local-first discovery.
- "What's Hot" trending section highlights restaurants with the highest order volume in the last 24h.
- Temperature indicator badge — "Warm when it arrives" — signals high-prep + low-distance restaurants.
- All features are lightweight, demo-safe, and require no ML/AI infrastructure, real-time analytics pipelines, or external APIs beyond what ND.03 already provides.

## 4. Implementation Objective

Add 6–8 lightweight, demo-visible differentiators that are easy to build but memorable in a 5-minute demo. Focus on four emotional anchors: **speed** (fastest near you, under-30 badges, temperature indicator), **trust** (three trust badges per card, freshness score), **locality** (near-you today, trending in locality, local-first discovery), and **intelligence cues** (meal mood banner, smart reorder suggestion, loyalty preview). Nothing here requires new infrastructure, external APIs, complex algorithms, or backend services beyond extending existing queries with simple computed fields.

## 5. Scope

### 5.1 "Fastest Near You" Lane
- **Homepage horizontal carousel:** Top 5 restaurants sorted by composite score `(distance_km / speed_score)` where `speed_score` = `10 / avg_delivery_time_min`.
- **Badge:** "Under 30 min" primary-color pill if `avg_delivery_time_min <= 30`.
- **One-tap reorder shortcut:** Each card in the "Fastest Near You" lane has a small "Reorder" button if the user has ordered from this restaurant before (reuse reorder logic from ND.03).
- **Data source:** Extend `GET /api/v1/restaurants` with `?sort=fastest_near_me&lat={lat}&lng={lng}&limit=5`. Compute `distance_km` via Haversine on the backend using saved address lat/lng or browser geolocation.
- **Frontend:** New `<FastestNearYouLane />` component below hero on homepage. Horizontal scroll, snap-x. Cards are compact (image left, info right). Title: "🚀 Fastest Near You — Under 30 min".

### 5.2 Meal Tags / Meal Mood
- **Contextual banner on homepage:** Based solely on client-side time of day + day of week.
- **6 presets with Indian-food examples:**
  - **Breakfast (7–11am, Mon–Sun):** "Good morning! Start your day right." + chips: Idli, Dosa, Poha, Paratha, Upma, Vada
  - **Lunch (11am–3pm, Mon–Fri):** "Lunch break? Quick meals under 30 min." + chips: Thali, Biryani, Curry, Roti, Dal
  - **Lunch (11am–3pm, Sat–Sun):** "Weekend lunch — feast mode on!" + chips: Thali, Biryani, Tandoori, Combos
  - **Snacks (3–6pm, Mon–Sun):** "Tea-time cravings?" + chips: Samosa, Chaat, Vada Pav, Pakora, Kulcha
  - **Dinner (6–11pm, Mon–Sun):** "Dinner is served." + chips: North Indian, South Indian, Chinese, Biryani, Combos
  - **Late Night (11pm–2am, Fri–Sat):** "Late night munchies?" + chips: Pizza, Burger, Rolls, Biryani, Desserts
- **Behavior:** Tapping a chip navigates to `/restaurants?cuisine={chip_value}` or performs a search.
- **Frontend:** `<MealMoodBanner />` sticky below navbar on homepage. Background: gradient from primary to accent. Lucide `Sun`, `Moon`, `Coffee`, `UtensilsCrossed` icons per mood.
- **No backend needed:** Pure client-side logic using `new Date().getHours()` and `new Date().getDay()`.

### 5.3 Trust Badge System (3 Badges Per Restaurant Card)
- **Three badges per card:**
  1. **FSSAI Verified:** Shield icon + "FSSAI" text (already exists from ND.03 via `is_fssai_verified`).
  2. **Freshly Prepared in X min:** Clock icon + text showing `avg_prep_time_min` (new field). Computed from `menu_items` or stored on restaurant.
  3. **Under 30 min Delivery:** Rocket icon + "Under 30 min" (computed from `avg_delivery_time_min`). Only shown if `avg_delivery_time_min <= 30`.
- **Badge anatomy:** Small pill with Lucide icon, font-weight 600, background tinted with badge-specific color (green for FSSAI, amber for prep time, primary for under-30). Border-radius 40px, padding 4px 10px, font-size 11px.
- **Backend:** Add `avg_prep_time_min` to `restaurants` table (migrating if needed). Compute as weighted average of `prep_time_min` from `menu_items`. Return in restaurant list response.
- **Frontend:** Update `<RestaurantCardV2 />` trust badges row to always show up to 3 badges. If fewer than 3 apply, show only applicable ones. Empty badge row hidden.

### 5.4 Loyalty Preview
- **Wallet page update:** Shows "You have {points} points" with a progress bar toward the first reward tier (e.g., "500 pts = Free Delivery"). If 0 points, show "Start ordering to earn BhojanGo Points!" with illustration.
- **Cart points indicator:** On the cart page, below the order total, show "+{points} BhojanGo Points" with a small star icon. Points calculated as `Math.floor(order_total * 0.1)` (10% of order value).
- **Backend:** `loyalty_points` already exists on `users` table per v2 audit (BG.N002). Add `GET /api/v1/users/loyalty` returning `{current_points, next_tier_points, next_tier_name, progress_percent}`.
- **Frontend:** Extend wallet page with `<LoyaltyCard />` — circular progress indicator, tier labels (Starter → Bronze → Silver → Gold), and points history (mock or real). Cart page gets `<CartPointsPreview />`.
- **No redemption yet:** Points are visible and motivating but not yet spendable. Redemption deferred to ND.05+.

### 5.5 Smart Reorder
- **Proactive suggestion on homepage:** If the user is logged in and has placed an order within the last 30 days, show a "Same as last time?" pecked card below the hero banner. Card shows: restaurant thumbnail, item thumbnails (up to 3), restaurant name, total price, "Reorder Now" button.
- **Intelligence:** Not just a button in order history — the app *suggests* reordering before the user even navigates to history. Uses `GET /api/v1/orders?limit=1&user_id={id}` to fetch most recent order.
- **Frontend:** `<SmartReorderCard />` component. Appears conditionally. Dismissible with an X button (stored in localStorage for 24h). Tapping "Reorder Now" pre-fills cart exactly like ND.03 reorder.
- **Guest behavior:** Hidden for guests. No data, no suggestion.
- **Backend:** Reuse existing `GET /api/v1/orders` endpoint. No new endpoint needed.

### 5.6 Local-First Discovery
- **"Near You Today" section:** Homepage horizontal carousel of restaurants within 3 km of the user's saved/default address. Title: "Near You Today" with a location pin icon.
- **"Trending in [Locality]" section:** Homepage horizontal carousel of top-rated restaurants filtered by locality (e.g., "Koramangala", "MG Road", "Banjara Hills"). Locality derived from saved address `locality` field or reverse geocode of `lat/lng`.
- **Backend:** Extend `GET /api/v1/restaurants` with `?near_lat={lat}&near_lng={lng}&radius_km=3&limit=10`. Return `distance_km` computed via Haversine. Add `locality` field to `addresses` or derive from `restaurants.locality`.
- **Frontend:** Two new homepage sections: `<NearYouTodaySection />` and `<TrendingInLocalitySection />`.
- **Fallback:** If no saved address, show city-level trending instead. If geolocation is denied, don't show these sections (graceful degradation).

### 5.7 "What's Hot" Trending Section
- **Trending restaurants based on order volume last 24h:** Dynamic calculation using existing `orders` table.
- **Backend:** New endpoint `GET /api/v1/restaurants/trending` or extend list with `?sort=trending&period=24h`. Query: `SELECT restaurant_id, COUNT(*) as order_count FROM orders WHERE created_at >= NOW() - INTERVAL '24 hours' GROUP BY restaurant_id ORDER BY order_count DESC LIMIT 10`. Join with `restaurants` for details.
- **Frontend:** Homepage section `<WhatsHotSection />`. Horizontal carousel. Badge: "🔥 Trending" (flame icon). Shows order count or "X orders today". Card is compact.
- **Seed data:** Ensure seed data has enough orders in the last 24h window for demo. If running demo after seed, insert mock recent orders or use a fixed "demo date" window.

### 5.8 Temperature Indicator
- **"Warm when it arrives" badge:** For restaurants with high prep score + low distance score. Computed as `temp_score = avg_prep_time_min / distance_km`. If `temp_score > threshold` (e.g., >5.0), badge appears on restaurant card.
- **Icon:** Thermometer or Flame icon. Text: "Warm when it arrives" or "Hot & Fresh".
- **Why:** Signals that the restaurant is close enough and preps fast enough that food arrives at optimal temperature. Purely computed from existing fields.
- **Backend:** No new field needed. Compute on the fly in API response.
- **Frontend:** Add to trust badges row on restaurant card. Only shown when threshold is met.

## 6. Out of Scope

- **AI / ML recommendation engine:** No collaborative filtering, no neural nets, no prediction models. All intelligence is rule-based or computed from simple aggregates.
- **Real-time analytics pipeline:** No Kafka, no ClickHouse, no streaming analytics. Trending is computed from SQL `COUNT(*)` on existing orders table.
- **Personalization based on order history:** Smart reorder is time-based (<30 days), not cuisine-preference-based. No "you liked biryani, try this" logic.
- **Gamification tiers:** Loyalty preview shows points and progress, but no badges, levels, streaks, or leaderboards. Gamification deferred to ND.05+.
- **Group ordering:** Shareable cart links, split bill. Deferred to ND.06+.
- **Meal rescue / end-of-day deals:** Flash sales, unsold inventory. Deferred to ND.06+.
- **Community kitchens / home chefs:** No new restaurant types. Deferred to ND.06+.
- **Add-to-cart fly animation:** Visual delight animation. Deferred to ND.05.
- **Real-time driver tracking / batch engine UI:** Batch engine is backend-only for now. Customer-visible batch features deferred to ND.07+.
- **Nutritional info panel:** Calories, macros, allergens. Deferred to ND.06+.
- **Voice ordering:** Web Speech API. Deferred to ND.08+.
- **Dynamic surge pricing:** Rain-day pricing, demand-based fees. Deferred to ND.09+.
- **Subscription plans:** Restaurant subscription tiers, customer meal plans. Deferred to ND.07+.
- **Smart lockers / pickup points:** QR code, locker network. Deferred to ND.07+.
- **Push notifications:** FCM integration for trending alerts. Deferred to PR.06+.

## 7. Required Capabilities

- ND.03 must be complete: favorites, reorder, filters, veg/non-veg, menu discovery, improved cards, quick-add all functional.
- Core ordering loop stable (PR.04 or PR.05 complete).
- Auth persistence working so favorites, order history, and loyalty points are available to logged-in users.
- `GET /api/v1/restaurants` must return sufficient fields: `lat`, `lng`, `avg_delivery_time_min`, `avg_prep_time_min`, `is_fssai_verified`, `locality`.
- `orders` table must have `created_at`, `restaurant_id`, `user_id`, `total_amount` populated for loyalty and trending calculations.
- `users` table must have `loyalty_points` column populated (existing per v2 audit BG.N002).
- Zustand cart store must support programmatic pre-fill (for smart reorder).
- Design system (BhojanGo palette, typography, spacing, Lucide icons) applied across all new UI.
- Toast/snackbar component must exist for confirmations.
- Geolocation API or saved address must provide lat/lng for local-first discovery.

## 8. Key User Journeys

### Journey 8.1 — Morning User Gets Contextual Meal Suggestion
1. User opens app at 8:30 AM on a Tuesday.
2. Homepage shows meal mood banner: "☀️ Good morning! Start your day right." with chips: Idli, Dosa, Poha, Paratha, Upma, Vada.
3. User taps "Dosa" chip → navigates to `/restaurants?search=dosa`.
4. Restaurant list shows dosa places, sorted by relevance.
5. User sees "Fastest Near You" lane at top of homepage with "Under 30 min" badges.

### Journey 8.2 — Returning User Sees Smart Reorder
1. User logged in, last ordered 5 days ago from "Spice Garden" (3 items).
2. Homepage shows smart reorder card: "🔄 Same as last time?" with thumbnails of Butter Chicken, Garlic Naan, Raita, total ₹485.
3. User taps "Reorder Now" → cart pre-filled with same 3 items.
4. Toast: "3 items added from Spice Garden."
5. Cart page shows "+48 BhojanGo Points" below total.

### Journey 8.3 — User Trusts Faster, Fresher Options
1. User on `/restaurants`, scrolls through cards.
2. Each card shows 3 trust badges row: "🛡️ FSSAI", "⏱️ Fresh in 12 min", "🚀 Under 30 min".
3. User taps a card with all 3 badges + "🔥 Warm when it arrives".
4. On detail page, trust banner repeats. User feels confident ordering.

### Journey 8.4 — Local Discovery on Weekend
1. User opens app at 2 PM Saturday.
2. Meal mood banner: "Weekend lunch — feast mode on!" with chips: Thali, Biryani, Tandoori, Combos.
3. Scrolls down to "Near You Today" → sees 6 restaurants within 3 km.
4. Scrolls to "🔥 Trending in Koramangala" → sees top 5 trending places.
5. Scrolls to "🚀 Fastest Near You" → sees 5 quick options.
6. Taps "Biryani" chip from mood banner → filtered restaurant list.

### Journey 8.5 — Loyalty Motivates First Order
1. New user signs up, wallet page shows "You have 0 points. Start ordering to earn!" with empty progress bar toward 500 pts (Free Delivery).
2. User browses, adds ₹350 of items to cart.
3. Cart shows subtotal, delivery fee, and "+35 BhojanGo Points".
4. User places order. Wallet page now shows "35 points — 465 to go for Free Delivery!"

## 9. Technical Coverage

### Backend
- **restaurant-svc:**
  - Extend `GET /api/v1/restaurants` to support new query params: `?sort=fastest_near_me&lat={lat}&lng={lng}&limit=5`, `?near_lat={lat}&near_lng={lng}&radius_km=3`, `?sort=trending&period=24h`.
  - Add Haversine distance calculation in SQL (using `earth_distance` extension or raw formula).
  - Add `avg_prep_time_min` column to `restaurants` table (migration). Compute from menu item prep times or seed directly.
  - Add `locality` column to `restaurants` table if not present.
  - Compute `temp_score` on the fly: `avg_prep_time_min / distance_km`.
- **order-svc:**
  - Extend `GET /api/v1/orders` to support `?limit=1` for most recent order lookup.
  - New lightweight endpoint `GET /api/v1/restaurants/trending` (or reuse extended restaurant list). Query counts orders in last 24h grouped by restaurant.
- **user-svc:**
  - Add `GET /api/v1/users/loyalty` returning `{current_points, next_tier_points, next_tier_name, progress_percent}`.
  - Ensure `loyalty_points` column exists and is populated in seed data.
- **Addresses:** Ensure saved addresses have `lat`, `lng`, and `locality` fields populated.

### Frontend
- **Zustand store extensions:** Add `discoveryStore` for homepage sections (fastest near you, near you today, trending, smart reorder). Cache for 5 minutes.
- **Components:**
  - `<FastestNearYouLane />` — horizontal scroll carousel, compact cards, under-30 badge, reorder shortcut.
  - `<MealMoodBanner />` — time-based contextual banner with horizontal chip scroll.
  - `<TrustBadgeRow />` — up to 3 badges: FSSAI, Freshly Prepared, Under 30 min.
  - `<TemperatureBadge />` — conditional "Warm when it arrives" badge.
  - `<LoyaltyCard />` — progress bar, tier labels, points history.
  - `<CartPointsPreview />` — inline points preview on cart page.
  - `<SmartReorderCard />` — conditional card with thumbnails, restaurant name, total, reorder button.
  - `<NearYouTodaySection />` — horizontal carousel filtered by distance.
  - `<TrendingInLocalitySection />` — horizontal carousel with locality name in title.
  - `<WhatsHotSection />` — trending restaurants with flame badge.
- **Hooks:** `useMealMood()` (returns current mood preset + chips), `useLocalDiscovery(lat, lng)` (fetches near-you and trending data), `useSmartReorder()` (fetches most recent order), `useLoyalty()` (fetches points data).

### Data
- `restaurants` table (extended): `avg_prep_time_min` INTEGER (default NULL), `locality` VARCHAR (default NULL).
- `orders` table (existing): must have `created_at`, `restaurant_id`, `user_id`, `total_amount` indexed.
- `users` table (existing): `loyalty_points` INTEGER (default 0) — verify exists.
- Seed data updates: ensure all restaurants have `lat`, `lng`, `avg_prep_time_min`, `locality`. Add `locality` to addresses. Ensure `loyalty_points` seeded for demo users.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for all homepage carousel sections (fastest, near you, trending, what's hot). Skeleton shimmer for meal mood banner.
- **Error states:** If geolocation fails, "Near You Today" section replaced with city-level fallback. If trending query fails, section hidden with silent degradation. Smart reorder card hidden on API failure.
- **Empty states:** If no restaurants within 3 km, "Near You Today" shows "No restaurants very close by. Try our full list." CTA. If no trending data, "What's Hot" shows "Trending data coming soon."
- **Success states:** Toast on smart reorder, toast on reorder shortcut from fastest lane.
- **Design system:** All new components follow BhojanGo palette (`#E65100` primary, `#2E7D32` trust green, `#FFB300` accent, `#F7F5F2` cream, `#1A1A1A` dark), Manrope + Inter typography, 4px grid, Lucide icons, badge/card anatomy from ND.02 and ND.03.
- **Indian food specifics:** Meal mood chips use Indian breakfast/lunch/dinner/snack items (idli, dosa, thali, biryani, chaat). Vegetarian and non-veg indicators from ND.03 remain.
- **Responsive:** Meal mood chips wrap on mobile (2 rows). Carousel sections horizontally scrollable on all breakpoints. Smart reorder card stacks vertically on mobile. Loyalty card fits within wallet page layout.
- **Dark mode:** All badges, progress bars, and banner gradients invert correctly. No black-on-black text. Warm/cold badge colors (amber, primary) remain meaningful.
- **Accessibility:** Meal mood chips have `role="button"`. Carousel sections use `role="list"` with `aria-label`. Loyalty progress bar uses `role="progressbar"` with `aria-valuenow`. Trust badges have `aria-label` describing each badge.

## 11. Data / Model Coverage

- `restaurants` table (extended): `avg_prep_time_min` INTEGER (default NULL), `locality` VARCHAR (default NULL). Add via migration if missing.
- `orders` table (existing): `created_at` TIMESTAMP, `restaurant_id` UUID FK, `user_id` UUID FK, `total_amount` DECIMAL. Ensure `restaurant_id` and `created_at` are indexed for trending query performance.
- `users` table (existing): `loyalty_points` INTEGER (default 0) — verify exists per v2 audit BG.N002.
- `addresses` table (existing): ensure `lat`, `lng`, `locality` populated.
- Seed data: populate `avg_prep_time_min` for all restaurants (15–25 min range). Populate `locality` for all restaurants. Ensure demo users have `loyalty_points` (0 or small value). Ensure `orders` table has recent entries (within last 24h for trending demo).

## 12. Role / Permission Coverage

- `customer` (logged-in): Full access to all ND.04 features — smart reorder, loyalty preview, local-first discovery, fastest near you, trending.
- Guest (unauthenticated): Can see meal mood banner, fastest near you (based on browser geolocation or default city), trust badges, temperature indicator, trending section, and "What's Hot". Cannot see smart reorder (no order history). Cannot see personalized loyalty preview (shows generic "Sign up to earn points!" CTA instead).
- `restaurant_owner`, `delivery_partner`, `admin`: Not involved in ND.04 (customer-facing features only). Admin may need to view loyalty stats in dashboard — deferred to admin roadmap.

## 13. Performance / Reliability / Security Coverage

### Performance
- Trending query must use indexed `created_at` and `restaurant_id` — target <50ms for 10K orders.
- Fastest near you uses Haversine in SQL — target <100ms for 100 restaurants.
- Local discovery query radius-limited — target <100ms.
- Meal mood banner is pure client-side — instant, no API call.
- Smart reorder is a single `limit=1` query — <10ms.
- All homepage carousel data fetched in parallel on mount.

### Reliability
- Geolocation failure: gracefully degrade to city-level or hide local sections. No broken UI.
- Trending query failure on demo day: fallback to "most popular all time" (static seeded order counts) or hide section.
- Loyalty endpoint failure: cart points preview hidden silently, wallet page shows generic message.
- Smart reorder card: hidden if no orders in last 30 days, hidden for guests, dismissible with 24h localStorage.
- Meal mood banner: always works regardless of network state.

### Security
- Trending endpoint is public (no auth needed) — only aggregates, no PII.
- Fastest near you uses lat/lng from saved address or browser — no address PII exposed in API.
- Loyalty endpoint verifies authenticated user — users cannot query other users' points.
- Smart reorder requires auth — endpoint verifies order belongs to current user.
- Haversine queries are read-only — no SQL injection risk if parameterized.

## 14. Novelty / Differentiation Coverage

At score 4, differentiation is about **moments of delight and intelligence** that a user can notice in a 5-minute demo. These are not structural moats yet — they are "wow, this app gets me" touches that create emotional connection.

- **Fastest Near You Lane:** Speed as a first-class feature. Competitors bury delivery time in card details; BhojanGo elevates it to a homepage carousel. The "Under 30 min" badge creates urgency and confidence.
- **Meal Mood Banner:** Contextual intelligence without AI. Time-of-day + day-of-week + Indian food vocabulary makes the app feel culturally native. "Good morning — craving idli?" at 8 AM is more memorable than a generic "Find Food" CTA.
- **Trust Badge System:** Three badges per card triple the trust signal density from ND.03. "Freshly Prepared in 12 min" is a differentiation Swiggy/Zomato do not show prominently. "Under 30 min" is aspirational and aspirational-badged.
- **Loyalty Preview:** Surfacing dormant `loyalty_points` (v2 audit found them seeded but unused) turns invisible data into visible motivation. The cart points preview is a micro-delight that happens on every checkout.
- **Smart Reorder:** From ND.03's manual "Reorder" button to ND.04's proactive "Same as last time?" suggestion. The app remembers before the user does. Thumbnail previews make the suggestion concrete.
- **Local-First Discovery:** "Near You Today" and "Trending in [Locality]" make the app feel tied to the user's physical neighborhood. Locality-specific titles create personal relevance.
- **What's Hot Trending:** Social proof engine using existing data. "128 orders today" creates FOMO and guides discovery. Dynamic (last 24h) makes it feel alive.
- **Temperature Indicator:** A computed freshness proxy. "Warm when it arrives" is a tangible promise that no competitor makes explicitly. It signals operational intelligence without requiring real IoT sensors.

**Differentiators deferred to higher scores:**
- Add-to-cart fly animation (ND.05 — visual delight).
- Loyalty redemption, tiers, gamification (ND.05 — retention loop).
- AI meal suggestions based on history/weather/time (ND.07 — smart personalization).
- Group ordering, meal rescue, community kitchens (ND.06 — marketplace expansion).
- Batch engine customer-visible UI, eco-delivery toggle (ND.07 — structural moat).
- Voice ordering (ND.08 — accessibility).
- Dynamic surge pricing, subscription plans (ND.09 — business model).

## 15. Implementation Work Items

### IP.ND.04.001 — Fastest Near You Lane + API
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Extend `GET /api/v1/restaurants` to support `?sort=fastest_near_me&lat={lat}&lng={lng}&limit=5`. Compute Haversine distance between restaurant lat/lng and provided coordinates. Compute composite score `distance_km / (10 / avg_delivery_time_min)`. Sort ascending (lower score = faster relative to distance). Return `distance_km` in response. Only include `is_open = true` restaurants. **Frontend:** New `<FastestNearYouLane />` component on homepage below hero. Horizontal scroll with `snap-x`. Compact card layout: image left (square), info right (name, rating, delivery time, "Under 30 min" badge if applicable). Small "Reorder" button on card if user has ordered from this restaurant before (reuse ND.03 reorder logic). Section title: "🚀 Fastest Near You". Hidden if no results. Skeleton loading state.
- **Acceptance Criteria:**
  1. `GET /api/v1/restaurants?sort=fastest_near_me` returns top 5 restaurants sorted by composite speed/distance score.
  2. Each result includes computed `distance_km`.
  3. Homepage shows horizontal carousel with compact cards.
  4. "Under 30 min" badge visible on applicable cards.
  5. Reorder shortcut works for previously ordered restaurants.
- **Evidence Required:** Screenshot: homepage with Fastest Near You lane. API curl showing sorted results with distance. Screen recording: tap reorder shortcut → cart pre-filled.
- **Priority:** P0
- **Effort:** M
- **Dependency:** ND.03 (reorder logic), stable restaurant list API with lat/lng
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.002 — Meal Tags / Meal Mood Banner
- **Category:** Frontend
- **Implementation Scope:** New `<MealMoodBanner />` component, sticky below navbar on homepage. Uses client-side time (`new Date().getHours()`, `new Date().getDay()`) to determine meal preset. 6 presets: Breakfast (7-11am), Lunch weekday (11am-3pm Mon-Fri), Lunch weekend (11am-3pm Sat-Sun), Snacks (3-6pm), Dinner (6-11pm), Late Night (11pm-2am Fri-Sat). Each preset has: greeting text (e.g., "Good morning! Start your day right."), icon (Lucide `Sun`, `Moon`, `Coffee`, `UtensilsCrossed`), and 6 horizontal scrollable chips with Indian food items (idli, dosa, thali, biryani, chaat, etc.). Background: subtle gradient using primary and accent colors. Tapping a chip navigates to `/restaurants?search={chip}` or `/restaurants?cuisine={chip}`. Dismissible with X (localStorage, 24h). No backend dependency.
- **Acceptance Criteria:**
  1. Banner appears with correct preset based on current time.
  2. Chips are horizontally scrollable and tappable.
  3. Tapping a chip navigates to filtered restaurant list or search.
  4. Banner is dismissible and stays hidden for 24h.
  5. Banner renders correctly on mobile, tablet, desktop.
- **Evidence Required:** Screenshots: banner at 8 AM (breakfast), 1 PM (lunch), 8 PM (dinner). Mobile view with chip scroll.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.003 — Trust Badge System (3 Badges Per Card)
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** **Data:** Add `avg_prep_time_min` INTEGER to `restaurants` table via migration. Seed with 10-25 min values. **Backend:** Include `avg_prep_time_min` in `GET /api/v1/restaurants` response. Compute `is_under_30_min = avg_delivery_time_min <= 30`. **Frontend:** Update `<RestaurantCardV2 />` trust badges row to show up to 3 badges: (1) "FSSAI Verified" shield icon (if `is_fssai_verified`), (2) "Freshly Prepared in {X} min" clock icon (always show if `avg_prep_time_min` exists), (3) "Under 30 min" rocket icon (if `is_under_30_min`). Badge anatomy: small pill, tinted background per badge, 11px font, Lucide icon. Row hidden if no badges apply. Update all card instances (homepage sections, restaurant list, favorites).
- **Acceptance Criteria:**
  1. Every restaurant card shows up to 3 trust badges.
  2. FSSAI badge only shown for verified restaurants.
  3. Prep time badge shows "Freshly Prepared in {X} min" for all restaurants.
  4. Under-30 badge only shown for restaurants with delivery time <= 30 min.
  5. Badges render consistently across all pages using restaurant cards.
- **Evidence Required:** Screenshots: restaurant card showing all 3 badges, card with only 2 badges, card with 1 badge, mobile view.
- **Priority:** P0
- **Effort:** S
- **Dependency:** ND.03 (improved restaurant cards)
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.004 — Loyalty Preview UI
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Add `GET /api/v1/users/loyalty` (or extend existing user profile endpoint). Returns `{current_points, next_tier_points, next_tier_name, progress_percent}`. Tier logic: 0-499 = Starter (next: 500), 500-1499 = Bronze (next: 1500), 1500-2999 = Silver (next: 3000), 3000+ = Gold. **Frontend:** Update `/wallet` page to include `<LoyaltyCard />` at top. Card shows: large points number, tier name, circular/linear progress bar toward next tier, and mock or real points history (last 5 transactions). If 0 points, show "Start ordering to earn BhojanGo Points!" with illustration. Add `<CartPointsPreview />` component to `/cart` page below order total. Shows "+{points} BhojanGo Points" with star icon. Points = `Math.floor(order_subtotal * 0.1)`. Hidden for guests.
- **Acceptance Criteria:**
  1. Wallet page shows current points, tier, and progress bar.
  2. Cart page shows estimated points for current order.
  3. Points calculation is 10% of order subtotal.
  4. Tier progression is accurate based on point thresholds.
  5. Empty state shows encouraging message for new users.
- **Evidence Required:** Screenshots: wallet page with loyalty card (0 points, >0 points), cart page with points preview.
- **Priority:** P0
- **Effort:** S
- **Dependency:** ND.03 (wallet page exists), `users.loyalty_points` column
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.005 — Smart Reorder Suggestion on Homepage
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Reuse `GET /api/v1/orders?limit=1&user_id={id}` (existing endpoint). Return most recent order with restaurant details and item thumbnails. **Frontend:** New `<SmartReorderCard />` on homepage below hero banner. Conditional: only visible if user is logged in AND has an order within last 30 days. Card shows: restaurant thumbnail, up to 3 item thumbnails, restaurant name, total price, "Reorder Now" button. Dismissible X button (stores dismissal in localStorage with 24h expiry). Tapping "Reorder Now" reuses ND.03 reorder logic: fetch order items, pre-fill cart, toast confirmation, navigate to `/cart`. Hidden on API failure or if no recent orders.
- **Acceptance Criteria:**
  1. Smart reorder card appears for logged-in users with an order <30 days old.
  2. Card shows restaurant thumbnail, item thumbnails, name, total.
  3. Tapping "Reorder Now" pre-fills cart and navigates to `/cart`.
  4. Card is dismissible and stays hidden for 24h.
  5. Card is hidden for guests and users with no recent orders.
- **Evidence Required:** Screen recording: homepage → smart reorder card → tap reorder → cart pre-filled. Screenshot: card with item thumbnails.
- **Priority:** P0
- **Effort:** S
- **Dependency:** ND.03 (reorder logic, order history API), auth persistence
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.006 — Local-First Discovery Sections
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Extend `GET /api/v1/restaurants` with `?near_lat={lat}&near_lng={lng}&radius_km=3&limit=10`. Compute Haversine distance. Return `distance_km`. Add `locality` filter: `?locality={name}&limit=10`. Both endpoints should return restaurant details with `distance_km` where applicable. **Data:** Add `locality` VARCHAR to `restaurants` table. Seed with neighborhood names. Ensure saved addresses have `lat`, `lng`, `locality`. **Frontend:** Two new homepage sections: `<NearYouTodaySection />` (horizontal carousel, title "📍 Near You Today", shows 6-10 restaurants within 3 km) and `<TrendingInLocalitySection />` (horizontal carousel, title "🔥 Trending in {Locality}", shows top-rated restaurants in user's locality). Geolocation: attempt `navigator.geolocation.getCurrentPosition()` on mount. If granted, use lat/lng. If denied or fails, use saved address lat/lng. If no saved address, use default city center. If no locality data, show city-level trending. Sections hidden gracefully if no data.
- **Acceptance Criteria:**
  1. "Near You Today" shows restaurants within 3 km sorted by distance.
  2. "Trending in {Locality}" shows restaurants filtered by locality.
  3. Geolocation attempts automatically on homepage load.
  4. Fallback to saved address if geolocation denied.
  5. Sections degrade gracefully (hidden) if no data available.
- **Evidence Required:** Screenshots: homepage showing both sections. API curl with near_lat/lng params. Mobile view.
- **Priority:** P0
- **Effort:** M
- **Dependency:** ND.03 (homepage structure), restaurant lat/lng data
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.007 — "What's Hot" Trending Section
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** **Backend:** New endpoint `GET /api/v1/restaurants/trending` (or extend list endpoint with `?sort=trending&period=24h`). Query: `SELECT restaurant_id, COUNT(*) as order_count FROM orders WHERE created_at >= NOW() - INTERVAL '24 hours' GROUP BY restaurant_id ORDER BY order_count DESC LIMIT 10`. Join with `restaurants` for name, image, rating, etc. Return `order_count_24h` per restaurant. **Data:** Ensure seed data has recent orders (within last 24h). For demo stability, consider a fixed "demo date" or seed orders with `created_at` near current time. **Frontend:** New homepage section `<WhatsHotSection />` below trending-in-locality. Horizontal carousel. Title: "🔥 What's Hot". Cards show: restaurant image, name, rating, and "{N} orders today" badge. Compact card style. Tapping card navigates to restaurant detail.
- **Acceptance Criteria:**
  1. Trending endpoint returns restaurants sorted by order count in last 24h.
  2. Homepage shows "What's Hot" carousel with order counts.
  3. "{N} orders today" badge visible on each card.
  4. Tapping card navigates to restaurant detail.
  5. Section degrades gracefully if no recent orders.
- **Evidence Required:** Screenshot: homepage with What's Hot section. API curl showing trending results. Screen recording: scroll trending carousel.
- **Priority:** P0
- **Effort:** S
- **Dependency:** orders table with `created_at` and `restaurant_id`
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.008 — Temperature Indicator Badge
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** In `GET /api/v1/restaurants` response, add computed field `temperature_indicator` per restaurant. Compute only when `lat` and `lng` params are provided: `temp_score = avg_prep_time_min / distance_km`. If `temp_score > 5.0` (configurable threshold), set `temperature_indicator = true`. Otherwise `false`. **Frontend:** Update `<RestaurantCardV2 />` trust badges row to conditionally show "🔥 Warm when it arrives" (thermometer icon) when `temperature_indicator = true`. Badge appears in addition to the 3 trust badges (so row can show 4 badges max). On restaurant detail page, also show a banner: "🌡️ Your food is expected to arrive warm — high prep speed, short distance." Color: amber/orange tint.
- **Acceptance Criteria:**
  1. Temperature indicator computed correctly as `avg_prep_time_min / distance_km`.
  2. Badge appears on cards when temp_score > threshold.
  3. Restaurant detail page shows temperature banner when applicable.
  4. Badge does not appear when geolocation/address is unavailable.
  5. Thermometer icon and amber color consistent with design system.
- **Evidence Required:** Screenshots: restaurant card with temperature badge, detail page with temperature banner, API response showing temperature_indicator field.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.04.001 (fastest near you with lat/lng), IP.ND.04.003 (trust badge system)
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.009 — Seed Data Completion for ND.04
- **Category:** Data
- **Implementation Scope:** Update seed data to support all ND.04 features: (1) All `restaurants` have `avg_prep_time_min` populated (10-25 min range). (2) All `restaurants` have `locality` populated with realistic neighborhood names. (3) All `restaurants` have `lat`/`lng` within a realistic cluster (e.g., Bangalore or Hyderabad coordinates). (4) All `addresses` have `lat`/`lng`/`locality`. (5) `users` table has `loyalty_points` populated (0 for new users, 100-400 for returning demo users). (6) `orders` table has entries within last 24h for trending demo. (7) Ensure `orders` have varied `restaurant_id` values so trending has variance.
- **Acceptance Criteria:**
  1. Every restaurant has `avg_prep_time_min`, `locality`, `lat`, `lng`.
  2. Every address has `lat`, `lng`, `locality`.
  3. Demo users have `loyalty_points`.
  4. Recent orders exist for 24h trending calculation.
  5. Restaurants are clustered within ~5 km for near-you demo.
- **Evidence Required:** DB query outputs confirming 100% coverage of new fields. Count of orders in last 24h.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.04.010 — Homepage Layout Integration
- **Category:** Frontend
- **Implementation Scope:** Integrate all new ND.04 homepage sections into a cohesive layout. Order: (1) Hero banner, (2) Meal Mood Banner, (3) Fastest Near You, (4) Smart Reorder (if applicable), (5) Near You Today, (6) Trending in Locality, (7) What's Hot, (8) Your Favorites (from ND.03), (9) Featured Restaurants / All Restaurants. Ensure sections do not duplicate content (e.g., a restaurant in "Fastest Near You" should not also appear in "Near You Today" if possible, deduplicate by ID). Add section dividers or spacing consistent with design system. Ensure all sections use shared `<RestaurantCardV2 />` component.
- **Acceptance Criteria:**
  1. Homepage shows all sections in correct order.
  2. No duplicate restaurant cards between sections.
  3. Layout is responsive across mobile, tablet, desktop.
  4. Sections use consistent card component and spacing.
  5. Loading and empty states work for all sections.
- **Evidence Required:** Screenshots: full homepage desktop, full homepage mobile. Screen recording: scroll through all sections.
- **Priority:** P0
- **Effort:** S
- **Dependency:** All IP.ND.04.001–008
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Fastest Near You lane visible on homepage with top 5 restaurants sorted by composite speed/distance score.
- [ ] "Under 30 min" badge appears on applicable cards in Fastest Near You lane.
- [ ] Reorder shortcut in Fastest Near You lane works for previously ordered restaurants.
- [ ] Meal mood banner appears with correct preset based on time of day.
- [ ] Meal mood chips are tappable and navigate to filtered restaurant list.
- [ ] Trust badge system shows up to 3 badges per restaurant card: FSSAI Verified, Freshly Prepared in X min, Under 30 min.
- [ ] Prep time badge shows for all restaurants with `avg_prep_time_min` populated.
- [ ] Loyalty preview visible on wallet page with points, tier, and progress bar.
- [ ] Cart page shows "+{points} BhojanGo Points" preview calculated at 10% of subtotal.
- [ ] Smart reorder card appears on homepage for logged-in users with an order <30 days old.
- [ ] Smart reorder card shows item thumbnails and pre-fills cart on "Reorder Now" tap.
- [ ] Near You Today section shows restaurants within 3 km of user location.
- [ ] Trending in Locality section shows top restaurants in user's locality.
- [ ] What's Hot trending section shows restaurants sorted by order volume in last 24h.
- [ ] Order count badge (e.g., "128 orders today") visible on What's Hot cards.
- [ ] Temperature indicator badge appears on cards when `avg_prep_time_min / distance_km > threshold`.
- [ ] Restaurant detail page shows temperature banner when applicable.
- [ ] All homepage sections are integrated into a cohesive layout with no duplicate cards.
- [ ] Guest users see all non-personalized sections (mood banner, fastest near you, trending, what's hot) but not smart reorder or loyalty preview.
- [ ] All new UI follows BhojanGo design system (palette, typography, spacing, Lucide icons).
- [ ] All features work on mobile, tablet, and desktop breakpoints.
- [ ] All features render correctly in dark mode.
- [ ] Seed data fully supports all ND.04 features for demo.

## 17. Evidence Required

- Screenshots:
  - Homepage full layout showing all sections: hero, meal mood banner, fastest near you, smart reorder, near you today, trending in locality, what's hot, favorites.
  - Meal mood banner at breakfast time (7-11am), lunch time (11am-3pm), dinner time (6-11pm).
  - Restaurant card showing all 4 badges (FSSAI, Freshly Prepared, Under 30 min, Warm when it arrives).
  - Wallet page with loyalty card (0 points and >0 points states).
  - Cart page with points preview.
  - Smart reorder card with item thumbnails.
  - "Near You Today" carousel.
  - "Trending in [Locality]" carousel.
  - "What's Hot" carousel with order count badges.
  - Restaurant detail page with temperature banner.
  - Mobile homepage showing all sections.
- Screen recordings:
  - Scroll through homepage demonstrating all sections.
  - Tap meal mood chip → navigate to filtered restaurants.
  - Smart reorder card → tap "Reorder Now" → cart pre-filled.
  - Fastest Near You reorder shortcut → cart pre-filled.
- API evidence:
  - `curl` output for `GET /api/v1/restaurants?sort=fastest_near_me&lat=...&lng=...`.
  - `curl` output for `GET /api/v1/restaurants/trending`.
  - `curl` output for `GET /api/v1/users/loyalty`.
- DB evidence:
  - Query results confirming `restaurants.avg_prep_time_min` and `locality` are 100% populated.
  - Query results confirming `users.loyalty_points` populated.
  - Query results confirming `orders` have recent entries for trending.

## 18. Dependencies

### External Tools
- PostgreSQL (for trending query, distance calculations, loyalty data).
- Node.js + pnpm (frontend build).
- Lucide React (icon library — already used from ND.02/ND.03).
- TanStack Query or SWR (for data fetching).
- Browser Geolocation API (optional, with graceful degradation).

### Internal Dependencies
- **ND.03 must be complete:** Favorites, reorder, filters, veg/non-veg, menu discovery, improved restaurant cards, quick-add all functional. If ND.03 is incomplete, ND.04 features that depend on card anatomy or reorder will be broken.
- **PR.04 or PR.05 must be complete:** Stable core loop (browse → menu → cart → checkout → track) is prerequisite.
- **Auth persistence must work:** Smart reorder and loyalty preview require logged-in users.
- **Restaurant list API must return lat/lng:** Required for Haversine distance and local discovery.
- **Cart Zustand store must support programmatic pre-fill:** Required for smart reorder and fastest-lane reorder shortcuts.
- **Cross-restaurant cart guard must exist:** From ND.03, required for all reorder flows.
- **Design system (ND.02) must be applied:** All new UI components rely on palette, typography, spacing, and badge anatomy.
- **Wallet page must exist:** Required for loyalty preview integration.

## 19. Risks / Blockers

- **Geolocation permission denied on demo devices:** If demo device blocks geolocation, "Near You Today" and temperature indicator may not show. Mitigation: use saved address as fallback, and seed demo addresses near restaurant cluster.
- **Trending query returns empty if demo run >24h after seed:** If demo happens days after seeding, no orders will be in the 24h window. Mitigation: IP.ND.04.009 seeds orders with `created_at` near current time, or use a "demo mode" that extends the trending window.
- **`avg_prep_time_min` column may not exist in current schema:** Migration required. Mitigation: IP.ND.04.009 includes migration script instructions. Must run before dependent work items.
- **Restaurant lat/lng may be missing or scattered globally:** If restaurants have random lat/lng, Haversine sorting is meaningless. Mitigation: IP.ND.04.009 clusters restaurants within ~5 km of a demo city center.
- **Smart reorder card may conflict with homepage hero CTA:** Two prominent CTAs competing for attention. Mitigation: smart reorder appears below hero, uses compact card format (not banner), dismissible.
- **Homepage section overload:** 6+ new sections risk a very long homepage. Mitigation: use horizontal carousels (compact height), deduplicate across sections, and ensure responsive collapse on mobile.
- **Loyalty points calculation discrepancies:** If order total changes after points preview (e.g., coupon applied), points shown in cart may differ from final points. Mitigation: points preview is labeled "estimated" and recalculates on cart changes.
- **Meal mood banner may not align with actual available restaurants:** "Idli" chip at 8 AM but no idli restaurants in seed data. Mitigation: ensure seed data includes restaurants and menu items matching mood chip keywords.

## 20. Exit Criteria

- All P0 work items (IP.ND.04.001 through IP.ND.04.007, IP.ND.04.009, IP.ND.04.010) implemented and verified.
- P1 work item (IP.ND.04.008) implemented and verified.
- Fastest Near You lane complete: API sorting, carousel UI, under-30 badges, reorder shortcuts.
- Meal mood banner complete: 6 presets, chip navigation, dismissal, responsive.
- Trust badge system complete: 3 badges per card, FSSAI, prep time, under-30.
- Loyalty preview complete: wallet card, tier progress, cart points preview.
- Smart reorder complete: homepage card, item thumbnails, cart pre-fill, dismissal.
- Local-first discovery complete: Near You Today, Trending in Locality, geolocation fallback.
- What's Hot trending complete: 24h order count query, carousel, order count badges.
- Temperature indicator complete: computed score, badge, detail page banner.
- Homepage layout integration complete: all sections ordered, deduplicated, responsive.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.04 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.03)

ND.04 directly depends on ND.03 achievements:
- **ND.03 Favorites System (IP.ND.03.001–003):** "Your Favorites" section appears on the ND.04 homepage layout. Favorite data used to determine reorder shortcut eligibility in Fastest Near You lane.
- **ND.03 Reorder (IP.ND.03.004):** Reorder logic reused for ND.04 smart reorder card and Fastest Near You reorder shortcuts.
- **ND.03 Filters (IP.ND.03.005):** Filtered restaurant list is the destination for meal mood chip taps.
- **ND.03 Veg/Non-Veg Visibility (IP.ND.03.006):** Veg dots and Pure Veg badges remain on all cards in ND.04 sections.
- **ND.03 Menu Discovery (IP.ND.03.007):** Category tabs, bestseller badges, and menu search remain stable.
- **ND.03 Improved Restaurant Cards (IP.ND.03.008):** `<RestaurantCardV2 />` is the foundation for trust badges, temperature indicator, and all carousel sections.
- **ND.03 Quick-Add (IP.ND.03.009):** Quick-add button remains on menu item cards.
- **ND.02 Design System:** BhojanGo palette, typography, spacing, Lucide icons, badge/card anatomy required for all new ND.04 UI.

## 22. Connected Next-Level Requirements (link to ND.05)

ND.05 (Retention-Focused Uniqueness, score 5/10) builds on ND.04 and requires:
- Working Fastest Near You lane as foundation for route-optimized discovery.
- Working meal mood banner as foundation for AI-powered meal suggestions (time + weather + history).
- Working trust badges as foundation for expanded trust system (freshness scores, delivery confidence, sustainability badge).
- Working loyalty preview as foundation for tiered loyalty program with redemption, badges, and gamification.
- Working smart reorder as foundation for predictive "Order Again" based on patterns.
- Working local-first discovery as foundation for hyperlocal community features.
- Working trending as foundation for real-time popularity feeds and social proof.

ND.05 will introduce:
- Loyalty redemption: spend points on delivery fee, discounts, or free items.
- Gamification tiers: Bronze/Silver/Gold with associated benefits.
- Add-to-cart fly animation (visual delight deferred from ND.03).
- Personalized homepage: "Based on your love for biryani..." (simple rule-based, not ML).
- Saved preferences: dietary, spice level, cuisine defaults.
- Better offers: coupon auto-apply, combo suggestions.

ND.05 will be blocked if:
- Loyalty preview shows incorrect data or breaks wallet page.
- Smart reorder card crashes or fails to pre-fill cart.
- Trust badges are missing or inconsistent.
- Homepage sections overlap, duplicate, or cause layout shifts.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (4/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.03 done) described | Planner | ✅ |
| 4 | Target state (ND.04 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.04 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.04 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (5 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (avg_prep_time_min, locality, loyalty) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why these demo-visible touches matter | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.04.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: fastest near you, meal mood, trust badges, loyalty preview, smart reorder, local discovery, what's hot, temperature indicator | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention geolocation, trending window, schema migration, lat/lng cluster, section overload | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.03) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.05) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and >=8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: fastest near you, meal mood banner, trust badge system, loyalty preview, smart reorder, local-first discovery, what's hot trending, temperature indicator, and seed data.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known gaps from the audits: missing `avg_prep_time_min` and `locality` columns, geolocation permission uncertainty on demo devices, trending query time window sensitivity.
- The document correctly scopes LOCAL/DEMO-SAFE features, avoiding premature commitment to AI/ML, real-time analytics, or gamification.
- User journeys are specific, emotional, and memorable — designed to shine in a 5-minute demo.
