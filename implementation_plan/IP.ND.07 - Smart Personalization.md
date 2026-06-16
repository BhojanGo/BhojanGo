# IP.ND.07 — Smart Personalization

## 1. Target Differentiation Score: 7/10

## 2. Score Meaning

Recommendations adapt to user history, time, cuisine preference, budget, distance, veg preference, and repeat behavior without needing heavy AI infrastructure. The app surfaces "Recommended for you," time-aware meal sections, budget-aligned badges, cross-sell associations, and contextual order reminders using rule-based scoring and simple statistical aggregations that run entirely in application code. The user experience feels personal because results shift predictably based on known context — not because of opaque ML magic. This differentiates from generic clones (score 1-3), cosmetic tweaks (score 4-5), and marketplace features (score 6) by making the platform feel like it knows the user.

## 3. Current → Target Transition

**From ND.06 (marketplace-specific differentiation):**
- Group ordering, office lunch mode, meal rescue, home-chef marketplace, nutrition transparency, fee calculator, sustainability scores, and order batching preview are functional.
- Restaurant cards show cuisine chips, ratings, delivery times, fees, trust badges, eco-badges, and open/closed status.
- Users can filter by dietary goal (High Protein, Low Calorie, Keto, Vegan), price, rating, delivery time, eco-friendly, and rescue-deal availability.
- Nutritional macro fields (calories, protein, carbs, fat), allergen tags, and dietary tags are displayed on menu items.
- Homepage has sections: "Featured," "Popular," "Fastest Near You," "Home Chefs Near You," "Rescue Meals."
- Loyalty points, favorites, smart reorder, and saved preferences are operational.
- No AI/ML personalization exists. Homepage recommendations are static or manually curated.
- No time-aware sections (breakfast, lunch, dinner, late night).
- No cross-sell associations ("Because you ordered X, try Y").
- No per-user restaurant scoring (all users see the same restaurant list).
- Search results are text-match only, not ranked by personal relevance.
- No order frequency alerts or habit-based nudges.
- No budget-aware default ordering (restaurants sorted by generic criteria, not user's typical spend).
- No distance-priority toggle preference stored in user profile.

**Target at score 7:**
- **Restaurant recommendation engine:** Every user gets a personalized top-10 restaurant list on the homepage. Scoring is rule-based (cuisine match 40%, price match 20%, distance 15%, veg preference 10%, repeat order rate 10%, rating 5%). Recomputed on each login, cached 5 minutes.
- **Menu item recommendations:** Opening a restaurant detail shows a "Recommended for you" section at the top of the menu. Items scored by: past orders from this restaurant, cuisine affinity, price preference, and veg preference.
- **Time-aware suggestions:** Homepage shows contextual sections based on current time — "Breakfast Picks" (7-11am), "Lunch Cravings" (11am-3pm), "Dinner Tonight" (6pm-11pm), "Late Night Bites" (11pm-2am), and "Weekend Brunch" (Saturday/Sunday 9am-2pm).
- **"Because you ordered X" cross-sell:** After ordering biryani, the user sees suggestions for raita and dessert. Associations are mined from order history pairs (frequency of item B ordered within 30 min of item A), displayed on cart/checkout and order confirmation.
- **Budget-aware filtering:** Default restaurant list is re-ranked by how close each restaurant's average item price is to the user's typical order value ±20%. A "Within your budget" badge appears on qualifying restaurant cards.
- **Distance-priority toggle:** Users can select "Show closest first" or "Show highest rated first" as a persistent default. This preference is stored in `users.preferred_sort_mode` and applied to every restaurant listing.
- **Order frequency alerts:** On homepage load, a toast/alert appears: "You usually order from Spice Garden on Thursdays — they're open now!" Based on most frequent restaurant-day-time pattern from order history (min 2 past orders for the pattern).
- **Smart search ranking:** Search results are reranked by a personal relevance score combining text match (exact > partial), cuisine affinity, past order frequency, and budget alignment — not just database ILIKE ordering.

## 4. Implementation Objective

Build a lightweight personalization engine using existing data (order history, user preferences, current time, addresses). Score items and restaurants based on user history, preferences, and context using rule-based weighted formulas and simple statistical aggregations. Display personalized sections and contextual recommendations without any external AI services, deep learning, or heavy ML infrastructure. All scoring runs in the application layer (Python/TypeScript) with minimal database queries. The result makes the app feel like it knows the user while remaining fully demo-safe and local.

## 5. Scope

### 5.1 Restaurant Recommendation Engine (Rule-Based Scoring)
- **Data inputs:**
  - User's past orders (restaurants ordered from, frequency, recency).
  - User's saved preferences (veg_only boolean, typical price range from median order value, favorite cuisines from favorites table).
  - Current user's primary address (lat/lng for distance calculation).
  - Restaurant fields: cuisine_types, average_item_price, lat/lng, veg_menu_ratio, rating.
- **Scoring algorithm:**
  ```python
  score = (cuisine_match * 0.40) +
          (price_match * 0.20) +
          (distance_score * 0.15) +
          (veg_match * 0.10) +
          (repeat_score * 0.10) +
          (normalized_rating * 0.05)
  ```
  - `cuisine_match`: 1.0 if any cuisine overlaps with user's favorite cuisines (from favorites or past orders), 0.5 if partial overlap, 0.0 if none.
  - `price_match`: 1.0 if restaurant avg price is within ±20% of user's median order value, 0.5 within ±50%, 0.0 otherwise.
  - `distance_score`: 1.0 if <= 2km, 0.7 if <= 5km, 0.4 if <= 10km, 0.1 otherwise. Haversine formula.
  - `veg_match`: 1.0 if user prefers veg and restaurant `veg_menu_ratio > 0.7`, 0.5 if veg_menu_ratio > 0.3, 0.0 otherwise. Non-veg users get 1.0.
  - `repeat_score`: 1.0 if user ordered from this restaurant >=3 times, 0.6 if >=2 times, 0.3 if >=1 time, 0.0 otherwise.
  - `normalized_rating`: `rating / 5.0`.
- **Output:** Top 10 restaurants by score for homepage "Recommended for You" section.
- **Cache:** Per-user result cached in Redis (or in-memory dict for demo) with 5-minute TTL. Recomputed on login or cache miss.
- **Backend endpoint:** `GET /api/v1/restaurants/recommendations` (uses existing auth middleware, reads user ID from JWT).

### 5.2 Menu Item Recommendation
- **Data inputs:**
  - User's past orders from this specific restaurant (menu items ordered, liked=ordered more than once).
  - User's cuisine affinity (favorite cuisines based on past orders globally).
  - User's typical price range (median item price from all past orders).
  - User's veg preference.
- **Scoring algorithm:**
  ```python
  item_score = (past_order_bonus * 0.40) +
               (cuisine_affinity * 0.25) +
               (price_preference * 0.20) +
               (veg_match * 0.15)
  ```
  - `past_order_bonus`: 1.0 if item ordered >=2 times from this restaurant, 0.7 if ordered once, 0.0 otherwise.
  - `cuisine_affinity`: 1.0 if item's category matches user's top-2 cuisines, 0.5 if top-5, 0.0 otherwise.
  - `price_preference`: 1.0 within ±15% of user's median item price, 0.5 within ±40%, 0.0 otherwise.
  - `veg_match`: 1.0 if veg user + item is veg, or non-veg user + item is non-veg. 0.5 for neutral. 0.0 for mismatch.
- **Output:** Top 5 items displayed as "Recommended for you" section at the top of the restaurant menu page, above category tabs.
- **Backend:** Extend `GET /api/v1/restaurants/{id}/menu` to include `recommended_items[]` sub-array, or add `GET /api/v1/restaurants/{id}/recommendations`.

### 5.3 Time-Aware Suggestions
- **Time buckets:**
  - Breakfast: 7:00 AM - 11:00 AM
  - Lunch: 11:00 AM - 3:00 PM
  - Dinner: 6:00 PM - 11:00 PM
  - Late Night: 11:00 PM - 2:00 AM
  - Weekend Brunch: Saturday or Sunday, 9:00 AM - 2:00 PM (overrides breakfast/lunch)
- **Menu item tagging:**
  - New optional field on `menu_items`: `time_tags` TEXT[] — values in `{breakfast, lunch, dinner, late_night, brunch}`.
  - If field is missing, infer from item name/category regex (e.g., "Dosa", "Idli" → breakfast; "Biryani" → lunch/dinner; "Burger" → all times).
- **Frontend behavior:**
  - Homepage shows one contextual section based on current time: e.g., "Late Night Bites" after 11 PM.
  - Section contains restaurants that have at least 2 items tagged for the current time bucket.
  - Items within the section are filtered by user's personal relevance score.
  - No backend changes needed — frontend reads all restaurants, filters by `time_tags` overlap, and applies client-side scoring using cached user profile data.

### 5.4 "Because You Ordered X" Cross-Sell
- **Association mining:**
  - Background job (or on-demand API): scans all completed orders. For each item pair (A, B) that appears in the same order, count frequency.
  - Filter to pairs where `frequency >= 2` and `confidence >= 0.3` (30% of orders containing A also contain B).
  - Result stored in `cross_sell_rules` table (see Section 11).
  - For demo, seed 15-20 hand-curated associations (e.g., Biryani → Raita, Pizza → Garlic Bread, Dosa → Sambar + Chutney, Burger → Fries + Shake).
- **Display locations:**
  - Cart page: below cart items, "Frequently ordered together with [Item X]" with one-tap add.
  - Order confirmation page: "Next time, you might also like [Item Y]."
  - Restaurant menu: subtle "Goes great with" badge on item cards.
- **API:** `GET /api/v1/cross-sell?item_id={id}` returns list of associated items with confidence score.

### 5.5 Budget-Aware Filtering / Badging
- **Data:**
  - Compute user's `typical_order_value` = median of all past order grand totals (fallback to ₹300 if no orders).
  - Compute restaurant `avg_order_value` = average of all item prices at that restaurant.
- **Behavior:**
  - Default restaurant list sort applies a budget-fit boost: restaurants with avg_order_value within ±20% of user's typical_order_value get a +0.15 boost to their display score.
  - This is NOT a hard filter — it's a soft ranking signal.
  - Restaurant cards show a "Within your budget" badge (green pill) when `avg_order_value` is within ±20% of `typical_order_value`.
  - Badge tooltip: "Your typical order is ~₹{typical}. This restaurant averages ~₹{avg}."

### 5.6 Distance-Priority Toggle
- **User preference:** New field `users.preferred_sort_mode` ENUM('distance', 'rating', 'recommended').
  - Default: 'recommended' (uses the recommendation engine score).
- **Frontend:** Small toggle bar above restaurant list: "Recommended" | "Closest" | "Top Rated". Active mode stored in Zustand and persisted to user profile via `PATCH /api/v1/me/preferences`.
- **Backend:** `GET /api/v1/restaurants` reads `preferred_sort_mode` and applies the appropriate ORDER BY clause:
  - `distance` → `ORDER BY distance_km ASC`
  - `rating` → `ORDER BY rating DESC, review_count DESC`
  - `recommended` → uses the rule-based scoring engine (Section 5.1).

### 5.7 Order Frequency Alerts
- **Pattern detection:**
  - For each user, compute: (restaurant_id, day_of_week, hour_bucket) frequency across all past orders.
  - Hour bucket is 3-hour windows: `0-3`, `3-6`, `6-9`, `9-12`, `12-15`, `15-18`, `18-21`, `21-24`.
  - Identify the pattern with `count >= 2` and highest frequency.
- **Alert trigger:**
  - On homepage load, check if current day_of_week + hour_bucket matches the user's strongest pattern.
  - If yes AND the restaurant is currently open, show a toast:
    - "You usually order from {restaurant_name} on {day}s around this time — they're open now!"
  - Max 1 alert per session. Dismissable.
- **Mock push (demo-safe):** Toast is sufficient. No FCM integration.

### 5.8 Smart Search Ranking
- **Current behavior:** Search returns results ordered by database row order (or generic `name ILIKE '%q%'`).
- **Enhanced behavior:**
  - Step 1: Get candidate results via `name ILIKE '%q%' OR cuisine ILIKE '%q%'`.
  - Step 2: Re-rank each result using the same rule-based scoring engine (Section 5.1) with an additional text-match boost:
    - `text_boost = 2.0` if exact name match, `1.0` if partial name match, `0.5` if cuisine match only.
  - Step 3: Final score = `personal_score * text_boost`.
  - Step 4: Return top 20 results sorted by final score descending.
- **Backend:** Extend `GET /api/v1/restaurants/search?q=...` to accept authenticated users and apply personal relevance scoring.

## 6. Out of Scope

- Deep learning / neural networks / embedding models (e.g., transformer-based recommenders, two-tower models).
- External AI APIs (OpenAI, Cohere, Anthropic, Google Vertex AI, AWS Personalize).
- Real-time collaborative filtering at scale (e.g., user-user or item-item similarity matrices, matrix factorization).
- Reinforcement learning for recommendation optimization.
- Content-based filtering using image recognition or NLP on descriptions.
- Real-time WebSocket-based recommendations updates.
- A/B testing infrastructure for recommendation variants.
- Predictive ordering (pre-filling cart before user action) — too aggressive for demo context.
- Weather API integration for "rainy day comfort food" suggestions.
- GPS-based contextual recommendations (e.g., "You're near a restaurant you like") — requires location permissions and geo-fencing.
- Personalized push notifications via FCM — all alerts are in-app toasts.
- Real-time analytics dashboard for recommendation effectiveness.

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.04 or PR.05 complete).
- Auth persistence must work. Recommendations are user-specific and require a logged-in user.
- Order history must be queryable per user (at minimum: `orders` table with `user_id`, `restaurant_id`, `total`, `status`, `created_at`; `order_items` table with `menu_item_id`, `quantity`).
- `favorites` table must exist and be populated (from ND.03+).
- `users` table must support new preference columns (`preferred_sort_mode`, `veg_only`, `typical_order_value`).
- Address table must store lat/lng for distance calculations.
- Restaurant list API must support time-range filtering and sorting modes.
- Menu API must return or be extensible to include recommended items subset.
- Cart Zustand store must support programmatic addition of cross-sell items.
- Homepage must be composable (sections can be added dynamically).
- Toast/snackbar component exists for frequency alerts.
- Design system (BhojanGo palette, typography, spacing, Lucide icons) applied across new UI.
- Seed data must include sufficient order history to demonstrate personalization (at least 10-15 past orders per demo user across 4+ restaurants).

## 8. Key User Journeys

### Journey 8.1 — Returning User Gets Personalized Homepage
1. Maya opens BhojanGo at 1:15 PM on Thursday.
2. Homepage loads. The first section below the hero is "Recommended for You" — 10 restaurants scored by her preferences.
3. "Spice Garden" (North Indian, ₹250 avg, 2.1 km, she's ordered 4 times) is ranked #1.
4. Below that, the "Lunch Cravings" section shows restaurants with biryani, thali, and curry items tagged for lunch.
5. A toast appears: "You usually order from Spice Garden on Thursdays around lunchtime — they're open now!"
6. Maya taps "Spice Garden" card (which shows a "Within your budget" green badge).

### Journey 8.2 — Menu Item Recommendations Work
1. On the "Spice Garden" detail page, above the category tabs, a horizontal scroll shows "Recommended for you."
2. "Butter Chicken" is #1 (she's ordered it 3 times). "Paneer Tikka" is #2 (same cuisine, within her price range). "Garlic Naan" is #3 (ordered 2 times).
3. Maya scrolls down to the full menu. "Butter Chicken" also has a small "Goes great with" chip: "Garlic Naan + Raita."
4. She adds Butter Chicken to cart. The cart page shows a cross-sell section:
   - "People who ordered Butter Chicken also got: Garlic Naan, Raita, Gulab Jamun."
5. With one tap, she adds Garlic Naan and Raita.

### Journey 8.3 — Budget and Sort Preferences Are Respected
1. A new user, Ravi, has never ordered. His default sort is "Recommended."
2. Ravi taps the sort toggle and selects "Closest."
3. Restaurant list reorders by distance ascending. His preference is saved to his profile.
4. Next time he opens the app, the list defaults to "Closest."
5. Ravi sees no "Within your budget" badges (no order history yet). After his first order of ₹320, badges appear on restaurants averaging ₹260-₹390.

### Journey 8.4 — Time-Aware Discovery Works
1. Ankit opens BhojanGo at 7:30 AM on Saturday.
2. Homepage shows "Weekend Brunch" section with dosa, idli, and brunch-special restaurants.
3. Tapping a brunch restaurant shows a "Brunch Specials" filter chip on the menu.
4. That evening at 8:00 PM, the homepage updates to "Dinner Tonight" with biryani, curry, and BBQ sections.
5. Ankit searches "biryani." Results are re-ranked: his most-ordered biryani restaurant (#1), highest-rated biryani spot within 3 km (#2), a new biryani place matching his price range (#3).

### Journey 8.5 — Cross-Sell Drives Larger Orders
1. Priya adds "Chicken Biryani" to her cart.
2. Cart cross-sell row appears: "Frequently ordered with Chicken Biryani: Raita (₹60), Mirchi Ka Salan (₹80), Double Ka Meetha (₹90)."
3. Priya taps the "+ Raita" quick-add button. Raita is added to cart at ₹60. Cart total updates.
4. At checkout, Priya sees her order total with the additional items included.
5. After order confirmation, a "Next time, try" card shows "Mirchi Ka Salan — it pairs perfectly with biryani."

### Journey 8.6 — Smart Search Ranking Surfaces Relevant Results
1. User searches "South Indian" (a cuisine they order every week).
2. Search results are re-ranked:
   - #1: "Dosa Point" (ordered 5 times, 1.2 km, rating 4.6)
   - #2: "Swamy's Idli House" (ordered 1 time, 0.8 km, rating 4.5)
   - #3: "New Dosa Place" (never ordered, 3.5 km, rating 4.8)
3. Text match alone would have ranked #3 higher because "Dosa" appears in the name. Personal relevance pushes ordered and nearby restaurants higher.

## 9. Technical Coverage

### Backend
- **restaurant-svc or new recommendation-svc:**
  - `GET /api/v1/restaurants/recommendations` — returns top 10 restaurants scored per user using the rule-based engine.
  - `GET /api/v1/restaurants/{id}/menu` extended with `recommended_items[]` sub-array scored per user.
  - `GET /api/v1/restaurants/search?q={query}&personalize=true` — returns text-matched candidates reranked by personal relevance.
  - `GET /api/v1/cross-sell?item_id={id}` — returns associated items from `cross_sell_rules` table.
  - `GET /api/v1/users/{id}/patterns` — returns detected order frequency pattern for alert logic.
- **user-svc:**
  - `PATCH /api/v1/me/preferences` — update `preferred_sort_mode` (distance, rating, recommended).
  - `GET /api/v1/me/preferences` — returns current sort mode, veg preference, and typical order value.
  - Ensure `GET /api/v1/me` returns `typical_order_value` (computed on read or cached).
- **order-svc:**
  - Statistics aggregation endpoints or pre-computed fields: `GET /api/v1/users/{id}/order-stats` returns `median_order_value`, `top_cuisines[]`, `top_restaurants[]`, `frequent_pattern` (day/hour/restaurant).
  - Optionally compute stats on login and cache in Redis (or in-memory dict for demo).
- **Data:**
  - Pre-compute `cross_sell_rules` table from order history (either via script or simple aggregation query).
  - Script or scheduled function to refresh `user_preferences` cached values (median order, top cuisines, etc.) after each completed order.

### Frontend
- **Zustand store extensions:**
  - `recommendationStore` — cached homepage recommendations, last fetched timestamp, TTL check.
  - `userPreferenceStore` — `preferred_sort_mode`, `veg_only`, `typical_order_value`. Persists to API.
  - `timeAwareStore` — current time bucket detection, active contextual section.
- **Components:**
  - `<RecommendedRestaurantsSection />` — homepage horizontal/vertical list of scored restaurant cards.
  - `<RecommendedMenuItems />` — horizontal scroll at top of restaurant menu detail.
  - `<TimeAwareSection />` — contextual section label + restaurant sub-list ("Lunch Cravings", "Dinner Tonight", etc.).
  - `<CrossSellRow />` — cart page row of associated items with quick-add buttons.
  - `<CrossSellBadge />` — "Goes great with" chip on menu item cards.
  - `<SortModeToggle />` — three-state toggle bar: Recommended / Closest / Top Rated.
  - `<BudgetBadge />` — green "Within your budget" pill on restaurant cards.
  - `<FrequencyAlertToast />` — dismissible toast with habit-based message.
  - `<SmartSearchResults />` — enhanced search results component that displays personal relevance as subtle badges or reordered list.
- **Hooks:**
  - `useRecommendations()` — fetches `/api/v1/restaurants/recommendations`, caches for 5 min.
  - `useMenuRecommendations(restaurantId)` — fetches recommended items for a restaurant.
  - `useCrossSell(itemId)` — fetches associated items.
  - `useTimeBucket()` — returns current time bucket string and whether weekend brunch is active.
  - `useOrderPattern()` — fetches user's detected pattern for alert logic.
  - `useSortMode()` — reads/writes `preferred_sort_mode`, syncs with API.

### Data
- Extended `users` table: `preferred_sort_mode` VARCHAR (default 'recommended'), `typical_order_value` DECIMAL(10,2) (computed, NULLable initially), `top_cuisines` TEXT[] (computed, cached), `veg_only` BOOLEAN (default false).
- New `cross_sell_rules` table: `id` UUID PK, `source_item_id` UUID FK → `menu_items.id`, `target_item_id` UUID FK → `menu_items.id`, `frequency` INT, `confidence` DECIMAL(3,2), `created_at` TIMESTAMP.
- Extended `menu_items` table: `time_tags` TEXT[] (optional, values in `{breakfast, lunch, dinner, late_night, brunch}`).
- Materialized view or API-computed: `user_order_stats` containing `user_id`, `median_order_value`, `top_restaurants` JSONB, `top_cuisines` TEXT[], `frequent_pattern` JSONB (e.g., `{"restaurant_id": "uuid", "day": "Thursday", "hour_bucket": "12-15"}`).
- Seed data: 15-20 `cross_sell_rules` records (hand-curated). `time_tags` populated for all menu items (inferred or manual). Order history seeded for 2-3 demo users across 5-8 restaurants.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for recommended restaurants, skeleton pills for recommended items, shimmer for cross-sell row.
- **Error states:** "We can't personalize yet — order a few meals to see recommendations!" (empty state for new users). "No matches found" in search with CTA to broaden query. Nutrition/preference API failure falls back to generic trending list.
- **Empty states:** New users see "Trending near you" instead of "Recommended for you" until order history exists. Cross-sell row hidden if no associations.
- **Success states:** Toast on sort mode change: "Showing closest restaurants first." Toast on cross-sell add: "Added Raita to your cart."
- **Design system:** All new components follow BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons.
- **Responsive:** Recommended restaurants: 1 col mobile, 2 col tablet, 3-4 col desktop. Recommended menu items: horizontal scroll on all breakpoints. Sort toggle: full-width on mobile, compact on desktop. Cross-sell row: horizontal scroll with compact cards.
- **Dark mode:** Recommended sections use cream/card backgrounds. Budget badge uses dark green. Time-aware section labels use warm saffron. Cross-sell cards use muted borders.
- **Accessibility:** Recommended items use `aria-label`: "Recommended for you: {item_name} from {restaurant_name}." Sort toggle uses `role="radiogroup"`. Cross-sell buttons use `aria-label`: "Add {item} to cart." Time section has `aria-live="polite"` for dynamic content.

## 11. Data / Model Coverage

- `users` table (extended): `preferred_sort_mode` VARCHAR (default 'recommended'), `typical_order_value` DECIMAL(10,2) (nullable, computed from order history), `top_cuisines` TEXT[] (nullable, computed), `veg_only` BOOLEAN (default false).
- `menu_items` table (extended): `time_tags` TEXT[] (nullable, values: breakfast, lunch, dinner, late_night, brunch).
- `cross_sell_rules` table (new): `id` UUID PK, `source_item_id` UUID FK → `menu_items.id`, `target_item_id` UUID FK → `menu_items.id`, `frequency` INT (min count), `confidence` DECIMAL(3,2) (0.0-1.0), `created_at` TIMESTAMP.
- `user_order_stats` (materialized view or computed API result): `user_id` UUID PK/FK, `median_order_value` DECIMAL(10,2), `top_restaurants` JSONB (array of `{restaurant_id, order_count}`), `top_cuisines` TEXT[], `frequent_pattern` JSONB (`{restaurant_id, restaurant_name, day_of_week, hour_bucket}`).
- Seed data requirements:
  - `time_tags` populated for 100% of menu items (inferred from names or manual tagging).
  - `cross_sell_rules`: 15-20 hand-curated associations with realistic `frequency` and `confidence` values.
  - Order history: at least 10-15 past orders per demo user (2-3 users), spanning 4-8 restaurants, to make recommendations visible and meaningful.
  - `users.top_cuisines` and `users.typical_order_value` pre-computed in seed profile for demo users.

## 12. Role / Permission Coverage

- `customer` (logged-in): Full access to all personalization features. Recommendations, cross-sell, sort toggles, budget badges, frequency alerts, smart search ranking all enabled.
- Guest (unauthenticated): No personalization available. Sees generic "Trending near you" instead of "Recommended." No budget badge. Search works but without personal relevance boost. Cross-sell associations still visible (item-based, not user-based), but no per-user scoring.
- `restaurant_owner`: Not directly involved in personalization features. May see aggregated "Top recommended" stats in analytics if dashboard supports it (out of scope for ND.07).
- `home_chef`: Same as restaurant_owner for personalization coverage.
- `delivery_partner`: Not involved.
- `admin`: Can view and manage `cross_sell_rules` via admin panel. Can trigger `user_order_stats` refresh for all users. Can inspect `users.top_cuisines` and `typical_order_value` for debugging.

## 13. Performance / Reliability / Security Coverage

### Performance
- Homepage recommendation query: single indexed query by `user_id` to order history (typically <20 rows per user). Scoring runs in application code over ~50-100 restaurants. Expected <50ms server-side. Cached 5 minutes to prevent repeated computation.
- Menu recommendations: single restaurant scope (typically 15-30 items). Client-side or lightweight server-side score over small dataset. Expected <10ms.
- Cross-sell lookup: indexed query by `source_item_id`. <5ms.
- Smart search: text match via `ILIKE` (or existing search if already using OpenSearch fallback). Re-ranking is client-side or on a small candidate set (<50 results). <30ms.
- Time-aware sections: entirely client-side filter using cached restaurant data. No API call.
- Budget badge computation: uses cached `typical_order_value` from user profile. No extra query.
- Memory footprint: rule-based scoring uses simple arithmetic on primitive types. No vector embeddings, no large matrices. Negligible memory impact.

### Reliability
- Fallback for new users: if `order_count < 3`, return "Trending near you" instead of personalized recommendations. No broken empty state.
- Fallback for missing data: if `top_cuisines` is NULL, use cuisine from `favorites` table. If favorites is empty, use "all cuisines equal" (1.0 for all). Never error on NULL.
- Cache invalidation: on order completion, invalidate user's recommendation cache (clear Redis key or reset timestamp).
- Distance calculation: Haversine formula works with NULL coordinates (returns 0.0 distance score). Gracefully handles missing address lat/lng.
- Sort mode persistence: if API update fails, revert to previous mode locally and show toast: "Couldn't save preference. Try again."
- Cross-sell associations: if `cross_sell_rules` has no match for an item, hide the row silently. No "not found" error.

### Security
- Recommendations are user-scoped: API endpoint reads `user_id` from JWT. Cannot request another user's recommendations.
- User preference updates (`PATCH /api/v1/me/preferences`) can only modify the authenticated user's record.
- Cross-sell rules are read-only for customers. Only `admin` role can create/modify rules.
- No PII is exposed in recommendation responses. Scores are internal calculations, never surfaced to the client.
- `typical_order_value`, `top_cuisines`, and `frequent_pattern` are returned only to the authenticated owner in `/api/v1/me`.
- No rate limiting concerns: recommendation queries are lightweight GETs. Existing rate limiter applies.

## 14. Novelty / Differentiation Coverage

At score 7, differentiation is about **intelligent adaptation** — the app feels like it learns the user without relying on heavy infrastructure.

- **Rule-Based Restaurant Recommendations:** Unlike generic apps that show the same "Popular" list to everyone, BhojanGo's homepage adapts to each user's cuisine loyalty, price comfort zone, distance tolerance, and ordering frequency. The scoring formula is transparent (documented in the spec) and fast (no model inference). This creates perceived intelligence with zero ML cost.
- **Menu Item Recommendations:** Moving personalization from the homepage into the menu surface creates serendipity. A user who always orders Butter Chicken from a restaurant sees it at the top — but the engine also surfaces Paneer Tikka as a safe variant because it matches their cuisine and price profile. This boosts average order value without feeling pushy.
- **Time-Aware Discovery:** Time-of-day sections turn the homepage into a dynamic menu rather than a static catalog. Breakfast, lunch, dinner, and late-night buckets create contextual urgency ("It's 11 PM — what are you craving?"). Weekend brunch adds a lifestyle dimension competitors lack.
- **Cross-Sell Associations:** "Because you ordered biryani" is a proven conversion driver. Using simple frequency mining from order history (not black-box ML) makes the associations explainable and trustworthy. Showing cross-sell in cart and on confirmation creates multiple touchpoints for upsell.
- **Budget Awareness:** The "Within your budget" badge removes decision friction. Users no longer have to guess if a restaurant is too expensive — the app tells them. This is especially powerful in price-sensitive markets like India.
- **Persistent Sort Preference:** Letting users choose "Closest first" vs "Top Rated" vs "Recommended" and remembering that choice makes the app feel configurable. Competitors often force one default sort and bury alternatives.
- **Order Frequency Alerts:** The habit-based toast ("You usually order from Spice Garden on Thursdays") creates emotional connection and increases order frequency through gentle nudging. It is not annoying because it only fires when the user is already on the app and the restaurant is open.
- **Smart Search Ranking:** Personal relevance in search is technically simple (text match × personal score) but productively powerful. A user searching "biryani" sees their usual spot first, not a random 5-star place 10 km away. This dramatically improves search utility.

**Differentiators deferred to higher scores:**
- Deep learning / neural recommendation models (ND.08+ — requires data volume and infrastructure).
- Real-time collaborative filtering (ND.08+ — requires many users and item interaction matrices).
- Predictive ordering / pre-filled cart (ND.08+ — aggressive UX, needs high confidence).
- Weather-based suggestions (ND.08+ — requires weather API integration).
- GPS proximity alerts (ND.08+ — requires location permissions).
- Personalized push notifications (PR.06+ — FCM integration).

## 15. Implementation Work Items

### IP.ND.07.001 — User Preference Schema + Order Stats Aggregation
- **Category:** Backend + Data
- **Implementation Scope:** Extend `users` table: `preferred_sort_mode` VARCHAR (default 'recommended'), `typical_order_value` DECIMAL(10,2), `top_cuisines` TEXT[], `veg_only` BOOLEAN. Create `user_order_stats` materialized view or computed API aggregation: `median_order_value`, `top_restaurants` (array of restaurant_id + count), `top_cuisines` (deduplicated from past orders), `frequent_pattern` (day_of_week + hour_bucket + restaurant_id). Add endpoint: `GET /api/v1/users/{id}/order-stats`. Auto-refresh stats on order completion (webhook or order-svc post-commit hook). Add `PATCH /api/v1/me/preferences` for `preferred_sort_mode` and `veg_only`.
- **Acceptance Criteria:**
  1. User profile stores sort mode, typical order value, top cuisines, and veg preference.
  2. `GET /api/v1/users/{id}/order-stats` returns accurate median, top restaurants, top cuisines, and frequent pattern based on past orders.
  3. Stats auto-update after a new completed order.
  4. `PATCH /api/v1/me/preferences` persists sort mode and veg preference.
  5. New users see NULL typical_order_value with graceful fallback.
- **Evidence Required:** `curl` output for GET order-stats showing correct aggregation. DB query confirming `users` extended fields. Screenshot of patch response.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.002 — Restaurant Recommendation Engine (Rule-Based Scoring)
- **Category:** Backend
- **Implementation Scope:** Implement `GET /api/v1/restaurants/recommendations` endpoint. Query all active restaurants. Load user's `order_stats` (cuisines, median order value, veg preference, past restaurant IDs). Compute per-restaurant score using the weighted formula (cuisine match 40%, price match 20%, distance 15%, veg match 10%, repeat score 10%, rating 5%). Haversine distance calculation from user's primary address lat/lng to restaurant lat/lng. Sort descending, return top 10. Cache result per-user for 5 minutes (Redis or in-memory dict). On cache miss, recompute. On new order completion, invalidate cache.
- **Acceptance Criteria:**
  1. Endpoint returns exactly 10 restaurants per authenticated user.
  2. Score ordering is deterministic (same inputs = same outputs).
  3. Frequently ordered restaurant appears in top 3.
  4. Far-away (>10km) restaurant with no cuisine overlap is not in top 10 (unless no better options).
  5. Cache prevents re-query within 5 minutes.
- **Evidence Required:** `curl` output for 2 different users showing different top-10 lists. Screenshot evidence that scores differ based on order history.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.07.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.003 — Menu Item Recommendation Engine
- **Category:** Backend
- **Implementation Scope:** Extend `GET /api/v1/restaurants/{id}/menu` to include `recommended_items[]` sub-array (top 5) computed per user, OR add dedicated `GET /api/v1/restaurants/{id}/menu-recommendations`. Score items using past_order_bonus (ordered before at this restaurant), cuisine_affinity (match to user's top cuisines), price_preference (match to user's median item price), veg_match. Return top 5 items with scores hidden. Filter out items already visible elsewhere if needed (no hard requirement). Lightweight — single restaurant scope means <50 items max.
- **Acceptance Criteria:**
  1. Menu API returns `recommended_items[]` with exactly 5 items.
  2. Ordered items from this restaurant rank higher than un-ordered items.
  3. Price outliers (>2× user's median) do not appear in top 5.
  4. Veg items rank higher for veg users.
  5. Menu without 5 items returns available items without error.
- **Evidence Required:** `curl` output showing `recommended_items[]` for two different users on the same restaurant. DB query confirming past orders.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.07.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.004 — Time-Aware Suggestions (Frontend)
- **Category:** Frontend
- **Implementation Scope:** Build `<TimeAwareSection />` component for homepage. Determine current time bucket client-side: compare `new Date().getHours()` to thresholds (7-11 breakfast, 11-15 lunch, 18-23 dinner, 23-2 late_night, weekend 9-14 brunch). Fetch active restaurants. Filter to those with `time_tags` matching current bucket (client-side on cached data). Display section with label ("Lunch Cravings", "Dinner Tonight", etc.) and horizontal scroll of restaurant cards. Include fallback: if no matches, hide section entirely. No backend API needed — uses existing restaurant list data.
- **Acceptance Criteria:**
  1. Homepage shows correct time section for current clock time.
  2. Weekend brunch shows on Saturday/Sunday 9am-2pm.
  3. Section contains only restaurants with matching `time_tags`.
  4. Section is hidden if zero matches.
  5. Changing device time (for demo) updates the section label and content.
- **Evidence Required:** Screenshots of homepage at 8 AM (breakfast), 1 PM (lunch), 8 PM (dinner), 12 AM (late night), and Saturday 10 AM (brunch).
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.005 — Cross-Sell Associations (Data + Backend)
- **Category:** Backend + Data
- **Implementation Scope:** Create `cross_sell_rules` table: `id`, `source_item_id`, `target_item_id`, `frequency`, `confidence`, `created_at`. Seed 15-20 hand-curated rules (e.g., Biryani → Raita, Pizza → Garlic Bread). Add endpoint: `GET /api/v1/cross-sell?item_id={id}` returning up to 3 target items ordered by confidence DESC. Include item details (name, price, image_url, veg flag). Build a simple aggregation script that mines `order_items` + `orders` tables to auto-generate candidate rules (frequency >= 2, confidence >= 0.3). Script is run manually or on deploy, not a real cron job.
- **Acceptance Criteria:**
  1. `GET /api/v1/cross-sell?item_id={id}` returns associated items with names and prices.
  2. At least 15 cross-sell rules exist in the database.
  3. Confidence values are between 0.0 and 1.0.
  4. No duplicate or circular rules (A → B and B → A both allowed, but not A → A).
  5. API handles item_id with no rules by returning empty array (200, not 404).
- **Evidence Required:** DB query: `SELECT * FROM cross_sell_rules LIMIT 5`. `curl` output for cross-sell endpoint. Screenshot of seeded rules.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.006 — Cross-Sell Frontend (Cart + Confirmation + Menu)
- **Category:** Frontend
- **Implementation Scope:** `<CrossSellRow />` on cart page: horizontal scroll of cards showing item image, name, price, "+ Add" button. Triggers `useCrossSell` hook for the first cart item (or the most frequent in cart). `<CrossSellBadge />` on menu item cards: small "Goes great with: {item}" chip below item name. `<CrossSellPostOrder />` on order confirmation page: "Next time, try: {item}" card with CTA to pre-add to cart. All components use the `crossSellStore` (Zustand) or fetch on mount. One-tap add updates cart Zustand store directly.
- **Acceptance Criteria:**
  1. Cart page shows cross-sell row when cart contains >=1 item.
  2. Tapping "+ Add" on cross-sell item adds it to cart without page reload.
  3. Menu item cards show "Goes great with" badge for items with rules.
  4. Order confirmation shows "Next time, try" suggestion.
  5. Cross-sell is hidden if no rules exist for cart items.
- **Evidence Required:** Screenshots: cross-sell row in cart, menu badge, post-order suggestion, one-tap add success toast.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.07.005
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.007 — Budget-Aware Badging + Sort Boost
- **Category:** Backend + Frontend
- **Implementation Scope:** Compute `typical_order_value` per user (median of all past order totals). Compute `avg_order_value` per restaurant (average of all item prices). In `GET /api/v1/restaurants/recommendations` and `GET /api/v1/restaurants`, apply a +0.15 soft boost to display score when `avg_order_value` is within ±20% of `typical_order_value`. Frontend: `<BudgetBadge />` component renders a green pill "Within your budget" on restaurant cards where the condition is met. Tooltip shows: "Your typical order is ~₹{typical}. This restaurant averages ~₹{avg}."
- **Acceptance Criteria:**
  1. Restaurant cards show budget badge when avg price is within ±20% of user's typical value.
  2. Badge is hidden for new users (no typical_order_value yet).
  3. Budget-fit restaurants rank slightly higher in recommended list.
  4. Tooltip shows both values on hover.
  5. Calculation uses Decimal/float-safe arithmetic.
- **Evidence Required:** Screenshots: restaurant card with budget badge, tooltip expanded, search results showing badge on some cards but not others.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.07.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.008 — Distance-Priority Toggle
- **Category:** Frontend + Backend
- **Implementation Scope:** Add `users.preferred_sort_mode` field (ENUM: 'recommended', 'distance', 'rating'). Frontend: `<SortModeToggle />` above restaurant list — three pill buttons. On click, update Zustand `sortMode` state, call `PATCH /api/v1/me/preferences`, and re-fetch restaurant list with new mode. Backend: `GET /api/v1/restaurants` reads sort mode from user profile. `recommended` → rule-based scoring (default). `distance` → `ORDER BY distance ASC`. `rating` → `ORDER BY rating DESC, review_count DESC`. Display "Recommended" as default for new users.
- **Acceptance Criteria:**
  1. Toggle shows three options and highlights active mode.
  2. Clicking "Closest" reorders list by distance ascending.
  3. Clicking "Top Rated" reorders by rating descending.
  4. Preference persists across sessions (stored in DB).
  5. New users default to "Recommended."
- **Evidence Required:** Screenshots: toggle in all three states with reordered list. Screen recording: toggle click → list reorder → refresh page → same mode retained.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.07.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.009 — Order Frequency Alert Toast
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/users/{id}/patterns` returns strongest pattern: `{"restaurant_id": "uuid", "restaurant_name": "string", "day_of_week": "Thursday", "hour_bucket": "12-15", "frequency": 4}`. Frontend: on homepage mount, call `useOrderPattern()`. If current day matches `day_of_week` AND current hour falls within `hour_bucket` AND `frequency >= 2`, show `<FrequencyAlertToast />`: "You usually order from {restaurant_name} on {day}s — they're open now!" with CTA button "Order Now" linking to the restaurant. Max 1 toast per session. Dismiss via X. Uses existing toast/snackbar component.
- **Acceptance Criteria:**
  1. Toast appears when day and time match user's strongest pattern.
  2. Toast shows correct restaurant name and day.
  3. "Order Now" button navigates to restaurant detail.
  4. Toast dismisses and does not reappear in the same session.
  5. No toast for users with <2 past orders or no pattern.
- **Evidence Required:** Screenshot of toast on homepage. Screen recording: order at pattern time → return to homepage → toast appears → dismiss → no reappear.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.07.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.010 — Smart Search Ranking
- **Category:** Backend + Frontend
- **Implementation Scope:** Extend `GET /api/v1/restaurants/search?q={query}` to support authenticated users. Backend: perform text match (`name ILIKE '%q%' OR cuisine ILIKE '%q%'`). Get candidate list (max 50). For authenticated users, compute personal relevance score per candidate using the rule-based engine (cuisine match, repeat score, price match, distance) AND a text boost: `2.0` for exact name match, `1.0` for partial name match, `0.5` for cuisine match only. Final score = `personal_score * text_boost`. Sort descending, return top 20. Frontend: `<SmartSearchResults />` displays results in reordered list. For guests, skip personal scoring and return standard text-match results.
- **Acceptance Criteria:**
  1. Authenticated user sees personally relevant restaurants ranked above generic matches.
  2. Exact name match is boosted higher than partial match.
  3. Guest users see standard text-match results (no error).
  4. Search returns max 20 results.
  5. Empty query returns 400 or empty array (not all restaurants).
- **Evidence Required:** `curl` output for same search query by two different users showing different result order. Screenshot of search UI showing result ranking.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.ND.07.001, IP.ND.07.002
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.011 — Homepage "Recommended for You" Section
- **Category:** Frontend
- **Implementation Scope:** Build `<RecommendedRestaurantsSection />` component. Fetch `GET /api/v1/restaurants/recommendations` on homepage mount (via `useRecommendations()` hook with 5-min cache). Display as horizontal scroll or responsive grid above "Popular" and below hero. Each card is a standard restaurant card (from ND.02/ND.03) but may include budget badge (IP.ND.07.007). Section label: "Recommended for You, {first_name}" (uses user profile). Empty state for new users: "Order a few meals to get personalized recommendations" with CTA to browse.
- **Acceptance Criteria:**
  1. Homepage shows "Recommended for You" section with up to 10 restaurant cards.
  2. Cards are clickable and navigate to restaurant detail.
  3. Section label includes user's first name.
  4. New users see fallback text instead of generic cards.
  5. Section refreshes on login or after cache TTL expires.
- **Evidence Required:** Screenshots: homepage with recommended section, empty state for new user, card with budget badge.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.07.002
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.012 — Recommended Menu Items Section
- **Category:** Frontend
- **Implementation Scope:** Build `<RecommendedMenuItems />` horizontal scroll component. Place at top of restaurant menu detail page, above category tabs. Fetch `GET /api/v1/restaurants/{id}/menu-recommendations` or read `recommended_items[]` from existing menu API. Display item cards with image, name, price, veg badge, and quick-add button. If no recommendations (new user or insufficient data), hide the section entirely.
- **Acceptance Criteria:**
  1. Menu detail page shows "Recommended for you" horizontal scroll with up to 5 items.
  2. Quick-add button adds item to cart.
  3. Section is hidden for guests or users with no order history.
  4. Items are visually distinct from regular menu items (slightly different background or border).
  5. Scrolling is smooth on mobile.
- **Evidence Required:** Screenshots: menu detail with recommended section, guest view without section, one item quick-add success.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.07.003
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.07.013 — Seed Data for Personalization Demo
- **Category:** Data
- **Implementation Scope:** Populate all seed data required for ND.07:
  1. `menu_items`: `time_tags` array for 100% of items (inferred from name/category or manual mapping).
  2. `users`: 2-3 demo users with 10-15 past orders each, spanning 4-8 restaurants, with varied cuisines, prices, and days/times.
  3. `cross_sell_rules`: 15-20 hand-curated associations (e.g., Biryani → Raita, Pizza → Garlic Bread, Dosa → Sambar, Burger → Fries, Thali → Lassi).
  4. Pre-compute `users.typical_order_value`, `users.top_cuisines`, and `users.veg_only` for demo users based on their order history.
  5. Ensure demo users have `favorites` entries (2-3 restaurants each).
- **Acceptance Criteria:**
  1. All menu items have at least one `time_tag`.
  2. Each demo user has 10+ past orders in seed data.
  3. Order stats aggregation produces non-NULL `median_order_value` and `top_cuisines` for all demo users.
  4. `cross_sell_rules` has >=15 rows.
  5. Favorites table has >=2 entries per demo user.
- **Evidence Required:** DB query outputs: `SELECT COUNT(*) FROM menu_items WHERE time_tags IS NULL`; `SELECT * FROM cross_sell_rules`; `SELECT user_id, COUNT(*) FROM orders GROUP BY user_id`; `SELECT * FROM user_order_stats`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] User order stats aggregation works: median order value, top cuisines, top restaurants, frequent pattern all compute correctly from past orders.
- [ ] `PATCH /api/v1/me/preferences` stores sort mode and veg preference.
- [ ] Homepage "Recommended for You" section returns 10 restaurants scored per user and updates after new orders.
- [ ] Menu detail "Recommended for you" section returns up to 5 scored items per user per restaurant.
- [ ] Time-aware section (Breakfast/Lunch/Dinner/Late Night/Weekend Brunch) appears based on current time and filters restaurants by `time_tags`.
- [ ] Cross-sell API returns associated items with confidence scores.
- [ ] Cart cross-sell row shows quick-add buttons for associated items.
- [ ] Menu item cards show "Goes great with" badge where rules exist.
- [ ] Order confirmation shows "Next time, try" cross-sell card.
- [ ] Budget badge "Within your budget" appears on restaurant cards when avg price is within ±20% of user's typical value.
- [ ] Budget-fit restaurants receive a soft ranking boost in recommendations.
- [ ] Sort toggle (Recommended / Closest / Top Rated) persists across sessions.
- [ ] "Closest" mode orders by distance; "Top Rated" mode orders by rating.
- [ ] Order frequency alert toast appears when day/time match strongest historical pattern.
- [ ] Smart search re-ranks results by personal relevance × text match boost for authenticated users.
- [ ] Guests see generic trending lists instead of personalized recommendations.
- [ ] All new UI follows BhojanGo design system, responsive, dark mode compatible.
- [ ] Seed data fully supports personalization demo (time tags, cross-sell rules, order history, user stats).

## 17. Evidence Required

- Screenshots:
  - Homepage "Recommended for You" section with 10 restaurant cards.
  - Homepage time-aware section at 8 AM (breakfast), 1 PM (lunch), 8 PM (dinner), and Saturday 10 AM (brunch).
  - Menu detail page with "Recommended for you" horizontal scroll above categories.
  - Cart page with cross-sell row showing associated items.
  - Menu item card with "Goes great with" badge.
  - Order confirmation page with "Next time, try" suggestion.
  - Restaurant card with "Within your budget" badge and tooltip.
  - Sort toggle in all three states (Recommended, Closest, Top Rated) with reordered list.
  - Order frequency alert toast on homepage.
  - Search results for same query showing different ranking for two users.
  - New user homepage showing fallback text instead of personalized recommendations.
- Screen recordings:
  - User opens homepage → sees personalized recommendations → taps a restaurant → sees menu recommendations → adds item → sees cart cross-sell → confirms order.
  - Toggle sort mode → list reorders → refresh page → same mode retained.
  - Order at pattern time → return to homepage → frequency alert appears → dismiss → no reappear.
- API evidence:
  - `curl` output for `GET /api/v1/restaurants/recommendations` for two different users.
  - `curl` output for `GET /api/v1/restaurants/{id}/menu` showing `recommended_items[]`.
  - `curl` output for `GET /api/v1/cross-sell?item_id={id}`.
  - `curl` output for `GET /api/v1/users/{id}/order-stats` showing stats.
  - `curl` output for `PATCH /api/v1/me/preferences`.
  - `curl` output for smart search comparing guest vs authenticated results.
- DB evidence:
  - Query results confirming `menu_items.time_tags` is 100% populated.
  - Query results confirming `cross_sell_rules` has >=15 rows.
  - Query results confirming demo users have >=10 past orders.
  - Query results confirming `user_order_stats` computes correct aggregates.

## 18. Dependencies

### External Tools
- PostgreSQL (for `users` extensions, `cross_sell_rules` table, `user_order_stats` view).
- Node.js + pnpm (frontend build).
- Lucide React (icon library — already used from ND.02).
- TanStack Query or SWR (for data fetching and caching).

### Internal Dependencies
- **PR.04 or PR.05 must be complete:** Stable core ordering loop is prerequisite.
- **ND.02 (Distinctive Visual Identity) must be complete:** Design system must be applied.
- **ND.03 (Small Convenience Features) must be complete:** Filters, restaurant cards, menu discovery — required as foundation.
- **ND.05 (Retention-Focused Uniqueness) must be complete:** Favorites, loyalty, smart reorder, saved preferences provide data inputs for personalization.
- **ND.06 (Marketplace-Specific Differentiation) must be complete:** Home chefs, nutrition filters, rescue deals are assumed operational. Group ordering is not a hard dependency but adds data richness.
- **Auth persistence** must work: personalization is user-scoped.
- **Order history** must be queryable: recommendations depend on past orders.
- **Cart Zustand store** must support programmatic manipulation (for cross-sell quick-add).
- **Toast/snackbar component** must exist for frequency alerts.
- **Address lat/lng** must be stored for distance calculations.

## 19. Risks / Blockers

- **Recommendation quality on sparse data:** Users with <3 orders get poor or generic recommendations. Mitigation: fallback to "Trending near you" until sufficient history exists.
- **Distance calculation accuracy:** Haversine assumes flat earth; ok for short distances but slightly inaccurate for >50km. Mitigation: acceptable for demo since delivery radius is typically <10km.
- **Performance on large restaurant lists:** If restaurant count grows to 500+, per-request scoring over all rows becomes slow. Mitigation: pre-filter to active + within 20km before scoring. For demo, score all ~50 restaurants without issue.
- **Cache invalidation race condition:** Order completes, cache is invalidated, but a concurrent request reads stale cache. Mitigation: TTL is only 5 minutes; acceptable staleness for demo. In production, use Redis cache tagging or pub/sub invalidation.
- **Sort mode API failure:** If `PATCH /api/v1/me/preferences` fails, local Zustand state may drift from server. Mitigation: optimistic update with rollback on error + toast notification.
- **Cross-sell rule maintenance:** Hand-curated rules are static and may not match new menu items. Mitigation: association mining script can be re-run after menu changes. For demo, rules are stable.
- **Time tag inference accuracy:** Regex-based inference from item names may mis-tag items. Mitigation: manual review of seed data. For demo, ~80% accuracy is acceptable.
- **User privacy perception:** Some users may be uncomfortable with "You usually order..." messaging. Mitigation: tone is friendly, not invasive. Easy to dismiss. No external data sources used.
- **Mobile horizontal scroll UX:** Recommended items and cross-sell rows on small screens may feel cramped. Mitigation: use compact card design (image + name + price + button). Test on 375px width.

## 20. Exit Criteria

- All P0 work items (IP.ND.07.001 through IP.ND.07.006, IP.ND.07.011 through IP.ND.07.013) implemented and verified.
- All P1 work items (IP.ND.07.007 through IP.ND.07.010) implemented and verified.
- User order stats aggregation complete: median, top cuisines, top restaurants, frequent pattern.
- Restaurant recommendation engine complete: returns top 10 per user, cached, falls back for new users.
- Menu item recommendations complete: top 5 per restaurant per user.
- Time-aware suggestions complete: correct sections for all 5 time buckets, visible on homepage.
- Cross-sell complete: data seeded, API working, cart row, menu badge, post-order card.
- Budget-aware badging complete: badge visible on cards, soft boost applied.
- Sort toggle complete: three modes, persisted, functional.
- Order frequency alert complete: toast at pattern time, dismissible, max 1 per session.
- Smart search ranking complete: authenticated users see re-ranked results, guests see standard results.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.07 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.06)

ND.07 directly depends on ND.06 achievements:
- **ND.06 Group Ordering:** Group order history contributes to `top_restaurants` and `top_cuisines` stats. Frequent group-order restaurants may rank higher.
- **ND.06 Office Lunch Mode:** Office order history contributes to user stats. Budget enforcement data refines `typical_order_value`.
- **ND.06 Nutritional Transparency:** Dietary tags and nutrition fields provide future input for health-based personalization (ND.08+). ND.07 uses veg preference only.
- **ND.06 Home Chef Marketplace:** Chef restaurant orders contribute to recommendation scoring. Chef items can appear in cross-sell associations.
- **ND.06 Meal Rescue:** Rescue deals may be included in time-aware sections (e.g., "Late Night Rescue Deals").
- **ND.06 Sustainability Score:** Eco-preferences are reserved for ND.08+ filtering. ND.07 does not score eco yet.
- **ND.03 + ND.05:** Favorites, reorder, loyalty, saved preferences, filters, and restaurant card anatomy are required UI foundations.

## 22. Connected Next-Level Requirements (link to ND.08)

ND.08 (Strong Product Identity, score 8/10) builds on ND.07 and requires:
- Working recommendation engine (IP.ND.07.002) as foundation for ML-enhanced scoring (collaborative filtering, embeddings).
- Working cross-sell associations (IP.ND.07.005–006) as foundation for bundle recommendations and dynamic combo deals.
- Working smart search (IP.ND.07.010) as foundation for semantic search (vector embeddings on descriptions).
- Working time-aware sections (IP.ND.07.004) as foundation for weather-aware and event-aware suggestions.
- Working budget badges (IP.ND.07.007) as foundation for dynamic deal surfacing ("Deals under your budget").
- Working order patterns (IP.ND.07.009) as foundation for predictive ordering ("Pre-fill your Thursday lunch?").

ND.08 will introduce:
- ML-enhanced recommendation scoring (collaborative filtering, item embeddings).
- Weather-based suggestions (rainy day → hot drinks, sunny day → cold beverages).
- Semantic search via OpenSearch vector search or pgvector.
- Dynamic bundle/combo engine based on cross-sell confidence + time of day.
- Personalized deal notifications ("Your favorite restaurant has a 20% off lunch deal today").
- Predictive pre-fill: "You usually order around now — want to reorder?"

ND.08 will be blocked if:
- Recommendation engine is too slow (>500ms) for ML overlay.
- Cross-sell rules table is empty or poorly structured.
- Smart search endpoint cannot handle vector reranking.
- Order pattern detection is inaccurate (false positives on alerts).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (7/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.06 + prior) described | Planner | ✅ |
| 4 | Target state (ND.07 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.07 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.07 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (6 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (1 new table, extended columns) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why personalization creates defensible differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.07.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: restaurant recommendations, menu recommendations, time-aware suggestions, cross-sell, budget badge, sort toggle, frequency alert, smart search | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks/Blockers mention sparse data, Haversine accuracy, large list perf, cache race, API drift, rule maintenance, tag inference, privacy, mobile scroll | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.06) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.08) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: user stats aggregation, restaurant recommendation engine, menu item recommendations, time-aware frontend, cross-sell data + frontend, budget-aware badging, distance-priority toggle, order frequency alert, smart search ranking, homepage recommended section, menu recommended section, and seed data completion.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in the lightweight nature of the rule-based approach (sparse data, Haversine limits, cache race conditions, inference accuracy).
- Scope is strictly LOCAL/DEMO-SAFE: no external AI APIs, no deep learning, no real-time collaborative filtering, no ML infrastructure. All scoring runs in application code with simple arithmetic.
