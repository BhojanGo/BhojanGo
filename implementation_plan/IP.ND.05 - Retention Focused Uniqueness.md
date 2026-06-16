# IP.ND.05 — Retention Focused Uniqueness

## 1. Target Differentiation Score: 5/10

## 2. Score Meaning

Favorites, reorder, loyalty, saved preferences, personalized homepage sections, and better offers make repeat usage easier. The app starts to build user habits. At score 5, BhojanGo is no longer just a competent ordering app — it becomes a platform that actively rewards users for coming back. The homepage adapts to each user. Coupons feel personal. Reordering a favorite meal takes two taps. The loyalty program creates a visible sense of progress. These features do not require AI/ML or complex infrastructure, but they collectively form the "behavioral scaffolding" that turns occasional users into regulars.

## 3. Current → Target Transition

**From ND.04 (demo-visible differentiators):**
- The app has visual polish: add-to-cart fly animation, fastest-near-you lane, meal tags (spice level, dietary badges), loyalty preview (points visible but not redeemable), smart reorder suggestions, better trust badges (freshness score, delivery confidence), and local-first discovery.
- The core ordering loop is stable and demo-ready.
- Favorites and reorder work (from ND.03).
- Loyalty points column exists in the database and is visible on the profile page, but there is no earn/redeem logic, no tier system, no rewards catalog, and no dashboard.
- Saved preferences do not exist. Users must re-enter dietary choices, spice level, and budget every session.
- The homepage is the same for everyone. There are no "Because you loved..." sections, no quick reorder lane, no budget-based filtering.
- Offers/coupons are generic (e.g., "WELCOME20"). There is no behavioral offer generation.
- Order streaks do not exist. Users are not rewarded for consistency.
- Birthday and anniversary dates are not collected or used for rewards.
- Packaging preferences (no cutlery, eco-friendly) are not stored or applied.

**Target at score 5:**
- Full loyalty program is active: users earn 10% of order value as points. Four tiers (Bronze, Silver, Gold, Platinum) with visible badges on profile and cart. Dashboard shows points history, tier progress bar, and rewards catalog. Rewards are redeemable: free delivery (100 pts), ₹50 off (200 pts), ₹100 off (500 pts).
- Saved preferences are persisted: preferred cuisines, spice level, veg preference, max delivery time, price range. These filter/sort restaurant list and menu by default on every session.
- Personalized homepage sections adapt per user: "Because you loved North Indian" shows top matching restaurants; "Quick Reorder" shows last 3 orders as horizontal cards; "New near you" shows recently added restaurants in same locality; "Under your budget" filters by user's preferred max price.
- Intelligent offers are generated from user behavior: "Back after 7 days" = 20% off; "Frequent orderer" = free delivery; "First order from new cuisine" = discount. Coupons are auto-applied at checkout when conditions match.
- Order streaks track consecutive orders: visual counter on profile, "5 orders in a row!" badge, reset if >7 days gap.
- Birthday rewards trigger automatically: on user's birthday, homepage shows special banner and birthday offer (₹100 off + free dessert). Anniversary offer triggers on account creation anniversary.
- Packaging preferences are stored and applied by default: "no cutlery" and "eco-friendly packaging" selections persist across orders and are pre-selected at checkout.

## 4. Implementation Objective

Build retention mechanics that make users return to BhojanGo not because they have to, but because the app remembers them, rewards them, and makes reordering trivial. These features are not one-time novelties — they are ongoing engagement drivers that compound with each visit. The goal is to create habit-forming loops: loyalty points → redemption → satisfaction → repeat order. Personalized homepage → discovery → order → better personalization. Saved preferences → faster filtering → less friction → higher conversion.

## 5. Scope

### 5.1 Full Loyalty Program
- **Points earning:** 10% of every order's subtotal (before discounts, after taxes) is credited as loyalty points. Rounded down to nearest integer. Points credited immediately on order status = `delivered`.
- **Tier thresholds:**
  - Bronze: 0–999 lifetime points earned (default).
  - Silver: 1,000–4,999 lifetime points earned.
  - Gold: 5,000–9,999 lifetime points earned.
  - Platinum: 10,000+ lifetime points earned.
- **Tier badge:** Visible on profile page, cart page, and checkout page. Badge uses tier-specific color: Bronze = brown, Silver = gray, Gold = amber, Platinum = violet.
- **Tier benefits:**
  - Silver: 5% bonus points on every order (15% total).
  - Gold: 10% bonus points + priority customer support.
  - Platinum: 15% bonus points + exclusive early access to new restaurants.
- **Rewards catalog:**
  - Free delivery on next order (100 pts).
  - ₹50 off on next order (200 pts).
  - ₹100 off on next order (500 pts).
- **Dashboard:** Accessible at `/loyalty` or `/profile/loyalty`. Shows: current points balance, lifetime points earned, tier badge with progress bar to next tier, points history table (date, order, points earned, points redeemed), rewards catalog with redeem buttons, redeemed rewards list (status: active, used, expired).
- **Redemption flow:** User taps "Redeem" on a reward → confirmation modal → reward added to user's active coupons → auto-applied at next checkout if valid.

### 5.2 Saved Preferences
- **Preference object:** Stored as JSONB in `users` table under `preferences` column, or separate `user_preferences` table.
- **Fields:**
  - `preferred_cuisines[]`: array of cuisine strings (e.g., ["North Indian", "Chinese", "Italian"]).
  - `spice_level`: "mild" | "medium" | "spicy".
  - `veg_preference`: "veg_only" | "non_veg_ok".
  - `max_delivery_time_min`: integer (default 45).
  - `price_range_max`: integer (default 500).
- **Onboarding capture:** After signup, users are prompted to set preferences in a 2-step onboarding modal: Step 1 = pick cuisines (multi-select chips), Step 2 = spice level (radio), veg preference (toggle), max delivery time (slider), max price (slider).
- **Application:**
  - Restaurant list defaults to filtering by `preferred_cuisines` and `price_range_max`.
  - "Veg Only" toggle defaults to match `veg_preference`.
  - Sort order defaults to favor preferred cuisines (boost in ranking).
  - Homepage "Because you loved..." section uses `preferred_cuisines` to select restaurants.
  - Menu items matching `spice_level` can be highlighted or sorted higher.
- **Edit UI:** Profile page has "Food Preferences" section with edit button. Opens modal to update all fields. Changes apply immediately to homepage and restaurant list.

### 5.3 Personalized Homepage Sections
- **"Because you loved [Cuisine]":** Horizontal scroll section below hero. Shows top 6 restaurants whose `cuisine_types` overlap with user's `preferred_cuisines`. Sorted by rating, then distance. Title dynamically uses first preferred cuisine: "Because you loved North Indian". If no preferences set, section hidden.
- **"Quick Reorder":** Horizontal scroll section showing last 3 delivered orders as compact cards. Each card shows: restaurant image, name, date, item count, "Reorder" button. Tapping "Reorder" pre-fills cart (same behavior as order history reorder). Hidden if user has <1 delivered order.
- **"New near you":** Shows restaurants added to platform in last 14 days within user's saved locality/detected city. Sorted by distance. Badge: "New". Hidden if no new restaurants.
- **"Under your budget":** Shows restaurants with average per-person price < user's `price_range_max`. Sorted by rating. Title: "Under ₹{max}". Hidden if no restaurants match.
- **Default state (no preferences):** If user has no saved preferences and no order history, homepage shows generic sections (featured, trending) instead of personalized ones. No empty-state gaps.

### 5.4 Intelligent Offers
- **Behavioral triggers:**
  - "Back after 7 days": If user's last order was >7 days ago, generate offer code "COMEBACK20" (20% off, max ₹100) on next login. Auto-applies at checkout. Expires 48h after generation.
  - "Frequent orderer": If user has >=3 orders in last 7 days, generate offer code "LOYALFREE" (free delivery on next order). Expires 7 days.
  - "First order from new cuisine": If user orders from a cuisine not in their order history, generate offer code "NEWCUISINE15" (15% off). Auto-applies. Expires 7 days.
  - "Birthday offer": On user's birthday (from profile `dob`), generate "BIRTHDAY100" (₹100 off + free dessert item). Auto-applies. Active for 3 days.
- **Offer engine:** Simple rule-based engine in `order-svc` or `user-svc`. Checks user conditions on login, order placement, or daily cron. Generates personalized `coupons` record with `user_id` and `trigger_reason`.
- **UI:** Auto-applied coupons shown in cart/checkout with badge: "Applied: COMEBACK20 — You save ₹80". User can remove auto-applied coupon and enter manual code instead.

### 5.5 Order Streaks
- **Counter:** Tracks consecutive weeks with at least one delivered order. Stored in `users` table: `order_streak_count` (integer), `order_streak_last_date` (date). Reset to 0 if gap between last order and new order is >7 days.
- **Visual:** Profile page shows flame icon + "{N} week streak!". Cart page shows small streak badge. Homepage banner when streak reaches milestones: "5-week streak! You're on fire!"
- **Badges:**
  - 3 weeks: "Rising Star" badge.
  - 5 weeks: "Regular" badge.
  - 10 weeks: "BhojanGo Champion" badge.
- **Rewards for streaks:** At 5-week streak, auto-grant "LOYALFREE" free delivery coupon. At 10-week streak, auto-grant "CHAMP100" ₹100 off coupon.

### 5.6 Birthday / Anniversary Rewards
- **Birthday:** User provides `dob` during onboarding or profile edit. On birthday (local time), homepage shows decorative banner: "Happy Birthday, {name}!" with confetti animation (CSS-only). Cart/checkout auto-applies "BIRTHDAY100" (₹100 off + one free dessert item from cart restaurant, if available). Free dessert applied as line item: "Birthday treat: Gulab Jamun — ₹0".
- **Anniversary:** Account creation anniversary. Homepage banner: "Celebrating {N} year with BhojanGo!". Auto-applies "ANNIV50" (₹50 off). For 1-year anniversary, bonus: "ANNIV100" (₹100 off).
- **Notification:** Toast on first app open on birthday/anniversary day: "It's your birthday! We've added a special treat to your cart."

### 5.7 Packaging Preference
- **Options:**
  - "No cutlery" (default: false).
  - "Eco-friendly packaging" (default: false).
- **Storage:** In `users.preferences` JSONB or `user_preferences` table.
- **Application:**
  - At checkout, packaging options shown as checkboxes pre-selected based on saved preference.
  - Order payload includes `packaging_options` object.
  - Restaurant dashboard sees packaging preference on order detail.
  - Profile page shows current packaging preference with edit option.
- **Eco impact tracking (lightweight):** If eco-friendly packaging selected, order confirmation shows: "You've saved ~15g plastic with this order." Cumulative eco savings shown in profile.

## 6. Out of Scope

- **AI / ML recommendation engine (ND.07):** Collaborative filtering, predictive ordering, or deep learning-based suggestions. Rule-based personalization only.
- **Group ordering (ND.06):** Shareable cart links, split bill, group carts.
- **Meal rescue / end-of-day deals (ND.06):** Flash sales for unsold inventory.
- **Community kitchens / home chefs (ND.06):** Separate section for home-cooked meals.
- **Smart lockers / pickup points (ND.07):** QR code locker delivery.
- **Voice ordering (ND.08):** Web Speech API, NLP parsing.
- **Real-time traffic / dynamic ETA (ND.07):** Google Routes API integration.
- **Nutritional info panel (ND.06):** Calories, macros, allergens.
- **Social login (PR.06+):** Google OAuth.
- **Push notification delivery:** FCM integration for offer notifications. Offer generation happens but notification is deferred.

## 7. Required Capabilities

- Core ordering loop must be stable (PR.04 or PR.05 complete).
- Auth persistence must work so preferences, favorites, and order history are available.
- Favorites and reorder must be functional (ND.03 complete).
- Restaurant list API must support filtering by cuisine, price, rating, and delivery time.
- Menu items must have `cuisine_type`, `price`, `is_veg`, `spice_level` populated.
- Orders table must track `user_id`, `order_date`, `status`, `total_amount`, `items` for history-based personalization.
- Cart Zustand store must support coupon application and removal.
- Design system must be applied (BhojanGo palette, typography, Lucide icons, badges).
- Toast/snackbar component must exist for confirmations.
- User profile must support `dob` field.
- Coupon/offers infrastructure must exist (basic `coupons` table with code, type, value, expiry, user_id).

## 8. Key User Journeys

### Journey 8.1 — New User Onboards and Sets Preferences
1. User signs up, completes basic registration.
2. Onboarding modal appears: "Let's personalize your experience."
3. Step 1: Multi-select cuisine chips — user taps "North Indian", "Chinese", "Italian".
4. Step 2: Spice level radio — user selects "Medium". Veg toggle — ON.
5. Step 3: Slider for max delivery time — 30 min. Slider for max price — ₹400.
6. Onboarding complete. Homepage now shows:
   - "Because you loved North Indian" section with 6 matching restaurants.
   - "Under your budget" section with restaurants under ₹400.
7. User taps "Find Food" → restaurant list pre-filtered by preferred cuisines and veg-only.

### Journey 8.2 — Returning User Reorders and Earns Points
1. User opens app, logged in. Homepage shows "Quick Reorder" section with last 3 orders.
2. User taps "Reorder" on biryani order from 3 days ago → cart pre-filled with 3 items.
3. Cart page shows loyalty badge: "Gold Member" with gold icon.
4. At checkout, "COMEBACK20" auto-applied (user hadn't ordered in 9 days): "You save ₹80".
5. User places ₹420 order. After delivery, notification: "+42 points earned! New balance: 1,242."
6. User navigates to `/loyalty` → sees points history, tier progress bar (Gold → Platinum: 7,758 pts to go), rewards catalog.
7. User taps "Redeem" on "Free delivery" (100 pts) → confirmation modal → reward added to active coupons.

### Journey 8.3 — User Builds a Streak and Gets Rewarded
1. User places an order on Monday. Profile shows "1 week streak!".
2. Following Monday, places another order within 7 days → streak increments to 2.
3. Week 3: places order → streak 3. Badge "Rising Star" appears on profile.
4. Week 5: places order → streak 5. Homepage banner: "5-week streak! You're on fire!" Free delivery coupon "LOYALFREE" auto-granted.
5. User orders again next week but on day 9 (gap >7 days) → streak resets to 1. Profile shows "Streak reset. Start again!"

### Journey 8.4 — Birthday Experience
1. User has `dob` set to today in profile.
2. Opens app. Homepage shows birthday banner with confetti: "Happy Birthday, Priya!".
3. Toast: "It's your birthday! We've added a special treat to your cart."
4. User browses restaurants, adds items to cart.
5. Cart shows auto-applied "BIRTHDAY100" (₹100 off). Free dessert line item appears: "Birthday treat: Gulab Jamun — ₹0".
6. User checks out, enjoys birthday discount and free dessert.

### Journey 8.5 — User Updates Preferences and Homepage Adapts
1. User goes to profile → "Food Preferences" section.
2. Taps "Edit". Changes preferred cuisines from ["North Indian"] to ["South Indian", "Chinese"].
3. Changes spice level from "Medium" to "Spicy". Increases max price from ₹400 to ₹600.
4. Saves changes. Toast: "Preferences updated."
5. Returns to homepage. "Because you loved North Indian" is replaced with "Because you loved South Indian".
6. "Under your budget" now shows restaurants under ₹600.
7. Goes to restaurant list — veg-only toggle still ON, but cuisine filter now shows South Indian and Chinese restaurants.

## 9. Technical Coverage

### Backend
- **user-svc:**
  - Extend `users` table: add `dob` (DATE), `preferences` (JSONB), `order_streak_count` (INTEGER, default 0), `order_streak_last_date` (DATE), `lifetime_loyalty_points` (INTEGER, default 0), `current_loyalty_points` (INTEGER, default 0), `loyalty_tier` (VARCHAR, default 'bronze').
  - `GET /api/v1/me` must return all new fields.
  - `PUT /api/v1/me/preferences` to update preferences JSONB.
  - `GET /api/v1/me/loyalty` — points history, tier info, rewards catalog.
  - `POST /api/v1/me/loyalty/redeem` — redeem reward, deduct points, create coupon.
  - `POST /api/v1/me/loyalty/calculate` — triggered by order-svc on delivery to credit points.
- **restaurant-svc:**
  - `GET /api/v1/restaurants` must support filtering by `cuisine_types[]`, `price_range_max`, `is_veg`, and sort by preference match score.
  - `GET /api/v1/restaurants?new_near_you=true&days=14` — return recently added restaurants in user's locality.
  - Add `avg_price_per_person` or compute from menu items for budget filtering.
- **order-svc:**
  - On order status change to `delivered`, call user-svc to credit loyalty points (10% of subtotal + tier bonus).
  - On order creation, check and reset streak logic (gap >7 days → reset; else increment).
  - `GET /api/v1/orders/recent?limit=3` — last 3 delivered orders for Quick Reorder section.
- **offers-svc (new or order-svc extension):**
  - Rule engine: evaluate user conditions on login / order / cron.
  - Generate personalized coupons in `coupons` table with `user_id`, `trigger_reason`, `auto_apply` flag.
  - Check birthday/anniversary dates daily and generate offers.

### Frontend
- **Zustand store extensions:**
  - `loyaltyStore`: points balance, tier, rewards catalog, redeem action.
  - `preferencesStore`: cuisine, spice, veg, time, price preferences; update action.
  - `offersStore`: active coupons, auto-applied coupon, apply/remove actions.
- **Components:**
  - `<LoyaltyBadge />` — tier icon + name for cart, checkout, profile.
  - `<LoyaltyDashboard />` — `/loyalty` page with history, progress, catalog.
  - `<PreferencesModal />` — onboarding + edit modal with cuisine chips, spice radio, sliders.
  - `<PersonalizedSection />` — reusable horizontal scroll section for homepage.
  - `<QuickReorderCard />` — compact card for last orders.
  - `<StreakBadge />` — flame icon + count for profile.
  - `<BirthdayBanner />` — confetti banner for homepage.
  - `<PackagingOptions />` — checkboxes for checkout.
  - `<CouponAutoApply />` — shows auto-applied coupon in cart/checkout.
- **Hooks:**
  - `useLoyalty()` — fetch points, tier, rewards.
  - `usePreferences()` — fetch/update preferences, apply to filters.
  - `usePersonalizedHomepage()` — fetch sections data based on preferences + history.
  - `useOffers()` — fetch active coupons, evaluate auto-apply.

### Data
- `users` table (extended): `dob`, `preferences` JSONB, `order_streak_count`, `order_streak_last_date`, `lifetime_loyalty_points`, `current_loyalty_points`, `loyalty_tier`.
- `loyalty_history` table (new): `id`, `user_id`, `order_id`, `points_earned`, `points_redeemed`, `balance_after`, `reason`, `created_at`.
- `rewards_catalog` table (new, seed data): `id`, `name`, `description`, `points_cost`, `reward_type` ('free_delivery' | 'flat_discount'), `reward_value`, `is_active`.
- `user_rewards` table (new): `id`, `user_id`, `reward_id`, `status` ('active' | 'used' | 'expired'), `coupon_code`, `expires_at`, `used_at`.
- `coupons` table (extended): add `user_id` (nullable), `trigger_reason` (nullable), `auto_apply` (boolean, default false).
- `restaurants` table (extended): add `created_at` (verify exists), `avg_price_per_person` (computed or stored).

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for personalized homepage sections, loyalty dashboard skeleton, preferences modal skeleton.
- **Error states:** Loyalty API failure → retry button + fallback to cached data. Preferences save failure → toast "Could not save preferences. Try again." Homepage section API failure → section hidden gracefully, no blank gaps.
- **Empty states:**
  - "Quick Reorder" hidden if no order history.
  - "Because you loved..." hidden if no preferences set.
  - "New near you" hidden if no new restaurants.
  - "Under your budget" hidden if no restaurants match.
  - `/loyalty` rewards catalog: if user has 0 points, show "Start ordering to earn points!" with CTA to browse.
- **Success states:** Toast on points earned, reward redeemed, preference saved, streak milestone reached, birthday offer applied.
- **Design system:** All new components follow BhojanGo palette (primary `#E65100`, trust green `#2E7D32`, accent `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, Lucide icons, badge/card anatomy. Tier badges use distinct colors: Bronze `#8D6E63`, Silver `#90A4AE`, Gold `#FFB300`, Platinum `#7E57C2`.
- **Responsive:**
  - Personalized sections: horizontal scroll on all breakpoints, cards snap on mobile.
  - Loyalty dashboard: single column on mobile, 2-col on tablet, 3-col on desktop.
  - Preferences modal: full-screen on mobile (<640px), centered modal on desktop.
  - Streak badge: small pill on mobile, larger card on desktop.
- **Dark mode:** Tier badge colors remain distinct in dark mode. Birthday banner uses dark-friendly confetti colors. Loyalty progress bar uses primary color. Cards, badges, pills render correctly.
- **Accessibility:**
  - Loyalty tier badge has `aria-label="{tier} member, {N} points"`.
  - Preferences modal fields have `aria-labelledby` and `aria-describedby`.
  - Birthday banner uses `role="banner"` and `aria-live="polite"`.
  - Reward redeem buttons have `aria-label="Redeem {reward_name} for {points} points"`.
  - Coupon auto-apply section uses `role="status"` for screen reader announcements.

## 11. Data / Model Coverage

- `users` table (extended):
  - `dob` DATE (nullable).
  - `preferences` JSONB (nullable, default `{}`).
  - `order_streak_count` INTEGER (default 0).
  - `order_streak_last_date` DATE (nullable).
  - `lifetime_loyalty_points` INTEGER (default 0).
  - `current_loyalty_points` INTEGER (default 0).
  - `loyalty_tier` VARCHAR (default 'bronze').
- `loyalty_history` table (new):
  - `id` UUID PK.
  - `user_id` UUID FK → `users.id`.
  - `order_id` UUID FK → `orders.id` (nullable, for redemptions without order).
  - `points_earned` INTEGER (default 0).
  - `points_redeemed` INTEGER (default 0).
  - `balance_after` INTEGER.
  - `reason` VARCHAR (e.g., "order_delivered", "reward_redeemed", "streak_bonus").
  - `created_at` TIMESTAMP.
  - Index on `user_id`, `created_at`.
- `rewards_catalog` table (new, seed data):
  - `id` UUID PK.
  - `name` VARCHAR (e.g., "Free Delivery").
  - `description` VARCHAR.
  - `points_cost` INTEGER.
  - `reward_type` ENUM ('free_delivery', 'flat_discount').
  - `reward_value` INTEGER (discount amount or delivery flag).
  - `is_active` BOOLEAN (default true).
- `user_rewards` table (new):
  - `id` UUID PK.
  - `user_id` UUID FK → `users.id`.
  - `reward_id` UUID FK → `rewards_catalog.id`.
  - `status` ENUM ('active', 'used', 'expired').
  - `coupon_code` VARCHAR (unique, generated on redemption).
  - `expires_at` TIMESTAMP.
  - `used_at` TIMESTAMP (nullable).
  - `created_at` TIMESTAMP.
- `coupons` table (extended):
  - Add `user_id` UUID FK → `users.id` (nullable; NULL = global coupon).
  - Add `trigger_reason` VARCHAR (nullable, e.g., "back_after_7_days").
  - Add `auto_apply` BOOLEAN (default false).
  - Add `generated_at` TIMESTAMP.
- `restaurants` table (extended):
  - Verify `created_at` TIMESTAMP exists.
  - Add `avg_price_per_person` DECIMAL(10,2) (computed from menu item prices + average order size, or stored and updated periodically).
- Seed data:
  - Populate `rewards_catalog` with 3 rewards (free delivery 100pts, ₹50 off 200pts, ₹100 off 500pts).
  - Seed demo users with `dob`, `preferences`, `loyalty_tier`, and `current_loyalty_points`.
  - Ensure demo users have enough order history for Quick Reorder and streak demonstration.

## 12. Role / Permission Coverage

- `customer` (logged-in): Full access to all ND.05 features — loyalty dashboard, preferences CRUD, personalized homepage, offers, streaks, birthday rewards, packaging options.
- Guest (unauthenticated): Personalized homepage falls back to generic sections. No loyalty, no preferences, no streaks, no birthday rewards, no offers. Packaging options shown as unchecked checkboxes at checkout but not persisted.
- `restaurant_owner`: Sees packaging preference on order detail page.
- `delivery_partner`: Not affected by ND.05.
- `admin`: Can view `loyalty_history`, `user_rewards`, and `rewards_catalog` tables. Can adjust user points manually via admin dashboard (optional, deferred).

## 13. Performance / Reliability / Security Coverage

### Performance
- Personalized homepage sections: fetch in parallel (Promise.all). Each section <200ms. If one section fails, others still render.
- Loyalty dashboard: points history paginated (20 records per page). Rewards catalog is small (<10 items) — no pagination needed.
- Preferences stored as JSONB — single row fetch/update, <10ms.
- Offer generation: evaluated lazily on login or order placement, not on every page load. Pre-generated coupons fetched with single query.
- Streak check: single date comparison on order creation, negligible overhead.

### Reliability
- Loyalty points credit is idempotent: if order-svc retries credit call, user-svc checks if points already credited for this order_id and skips.
- Preference JSONB schema is versioned: if new fields added later, missing fields default sensibly.
- Birthday/anniversary cron: runs once daily at local midnight. Generating duplicate offers for same day is prevented by unique constraint on (`user_id`, `trigger_reason`, `DATE(generated_at)`).
- Coupon auto-apply: if multiple auto-apply coupons exist, highest value wins. User can manually override.
- Streak reset: computed on order creation, not on login. Prevents reset if user opens app but doesn't order.
- Graceful degradation: if personalization API fails, homepage shows generic sections. No blank homepage.

### Security
- Favorites, preferences, loyalty data endpoints verify authenticated user matches token. No cross-user data access.
- Coupon generation endpoints must verify internal service auth (order-svc → user-svc) to prevent malicious point crediting.
- `preferences` JSONB is sanitized before storage. No arbitrary keys accepted. Whitelist: `preferred_cuisines`, `spice_level`, `veg_preference`, `max_delivery_time_min`, `price_range_max`, `packaging`.
- Birthday rewards: `dob` is sensitive PII. Store securely, expose only to self. Do not include in admin-visible lists without masking.
- Loyalty points modification (admin/ manual adjustment): requires admin role. Deferred to admin dashboard scope.

## 14. Novelty / Differentiation Coverage

At score 5, differentiation shifts from "visible novelty" to "behavioral scaffolding." The features in ND.05 are designed to form habits and emotional connections:

- **Loyalty program:** Most competitors have points, but BhojanGo's tier system (Bronze → Platinum) with visible badges, progress bars, and redeemable rewards creates a game-loop. The 10% earn rate + tier bonuses gives users a tangible reason to order again. Rewards are simple but meaningful: free delivery and flat discounts are what users actually want.
- **Saved preferences:** Competitors require users to filter every time. BhojanGo remembers and applies preferences automatically, reducing friction on every visit. The onboarding modal makes preference capture fast (<60 seconds).
- **Personalized homepage:** Rule-based but effective. "Because you loved..." uses explicit preferences rather than black-box AI, making it transparent and trustworthy. "Quick Reorder" reduces the most common action (reordering) to one tap.
- **Intelligent offers:** Rule-based behavioral triggers create surprise and delight. "Back after 7 days" acknowledges absence and tempts return. "First order from new cuisine" encourages exploration. These are not generic blast coupons — they react to individual behavior.
- **Order streaks:** Gamification without complexity. The visual flame counter and milestone badges create social proof and pride. Streak-reset mechanics (7-day gap) are forgiving enough to be achievable, strict enough to matter.
- **Birthday/anniversary rewards:** Emotional moments create brand affinity. The free dessert + discount combo feels generous and personal. Confetti animation makes it memorable.
- **Packaging preference + eco tracking:** Appeals to conscious consumers. The "plastic saved" metric is small but authentic. It aligns with BhojanGo's broader sustainability narrative (batched delivery efficiency).

**Differentiators deferred to higher scores:**
- AI-powered recommendations (ND.07) — collaborative filtering, time-based suggestions.
- Nutritional transparency panel (ND.06) — calories, macros, allergens.
- Group ordering (ND.06) — shareable carts, split bill.
- Meal rescue / flash sales (ND.06) — end-of-day deals.
- Smart lockers (ND.07) — pickup points, QR codes.
- Voice ordering (ND.08) — Web Speech API.
- Predictive ordering (ND.08) — "It's Friday, order biryani?"

## 15. Implementation Work Items

### IP.ND.05.001 — User Schema Extension for Loyalty + Preferences + Streaks
- **Category:** Backend + Data
- **Implementation Scope:** Extend `users` table with: `dob` (DATE, nullable), `preferences` (JSONB, nullable, default `{}`), `order_streak_count` (INTEGER, default 0), `order_streak_last_date` (DATE, nullable), `lifetime_loyalty_points` (INTEGER, default 0), `current_loyalty_points` (INTEGER, default 0), `loyalty_tier` (VARCHAR, default 'bronze'). Update `GET /api/v1/me` to return all new fields. Update user profile update endpoint to allow `dob` and `preferences` changes. Add migration script.
- **Acceptance Criteria:**
  1. `GET /api/v1/me` returns `dob`, `preferences`, `order_streak_count`, `order_streak_last_date`, `lifetime_loyalty_points`, `current_loyalty_points`, `loyalty_tier`.
  2. Profile update accepts `dob` and `preferences` JSONB.
  3. All fields have sensible defaults for existing users (0 points, bronze tier, 0 streak).
  4. Migration applies cleanly on existing DB without data loss.
- **Evidence Required:** `curl` output for `GET /api/v1/me` showing new fields. DB query confirming columns exist.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.002 — Loyalty Points History Table + Rewards Catalog
- **Category:** Backend + Data
- **Implementation Scope:** Create `loyalty_history` table (`id` UUID PK, `user_id` UUID FK, `order_id` UUID FK nullable, `points_earned` INTEGER default 0, `points_redeemed` INTEGER default 0, `balance_after` INTEGER, `reason` VARCHAR, `created_at` TIMESTAMP). Index on (`user_id`, `created_at`). Create `rewards_catalog` table (`id` UUID PK, `name`, `description`, `points_cost`, `reward_type` ENUM, `reward_value`, `is_active` BOOLEAN). Seed with 3 rewards: Free Delivery (100 pts, type=free_delivery), ₹50 Off (200 pts, type=flat_discount, value=50), ₹100 Off (500 pts, type=flat_discount, value=100). Create `user_rewards` table (`id` UUID PK, `user_id` UUID FK, `reward_id` UUID FK, `status` ENUM, `coupon_code` VARCHAR unique, `expires_at`, `used_at`, `created_at`).
- **Acceptance Criteria:**
  1. `loyalty_history` table created with all columns and indexes.
  2. `rewards_catalog` seeded with 3 active rewards.
  3. `user_rewards` table created with foreign keys and unique `coupon_code`.
  4. Can insert and query loyalty history records.
- **Evidence Required:** DB schema dump showing tables. Seed data query results.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.05.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.003 — Points Earning Logic + Tier Calculation
- **Category:** Backend
- **Implementation Scope:** Implement points earning in order-svc or user-svc: when order status changes to `delivered`, calculate points = FLOOR(subtotal * 0.10). Apply tier bonus: Bronze = 0%, Silver = 5%, Gold = 10%, Platinum = 15%. Credit to `users.current_loyalty_points` and `users.lifetime_loyalty_points`. Insert record into `loyalty_history`. Recalculate `users.loyalty_tier` based on lifetime points thresholds. Endpoint must be idempotent (skip if already credited for this order_id). `POST /api/v1/loyalty/credit` (internal) or webhook from order-svc.
- **Acceptance Criteria:**
  1. ₹420 order → 42 points credited for Bronze user.
  2. Same ₹420 order → 44 points for Silver user (42 + 5% bonus, rounded).
  3. Points idempotent: retrying credit for same order does not double-count.
  4. Tier auto-upgrades when lifetime points cross threshold.
  5. `loyalty_history` record created with correct fields.
- **Evidence Required:** API call output showing points credited. DB query showing `users.current_loyalty_points` and `loyalty_history` row. Retry test showing no duplicate.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.002
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.004 — Loyalty Dashboard Page
- **Category:** Frontend
- **Implementation Scope:** New `/loyalty` page. Sections: (1) Tier badge card — large tier icon, name, color. Progress bar showing points to next tier (e.g., "1,242 / 5,000" with percentage). (2) Points balance — large number, "+42 this week" subtitle. (3) Points history table — paginated, columns: date, order ID, points earned, reason. (4) Rewards catalog — cards for each reward showing name, description, points cost, "Redeem" button. (5) Active rewards — list of redeemed but unused rewards with expiry dates. (6) Streak badge — flame icon + "{N} week streak". Loading: skeleton dashboard. Empty: "Start ordering to earn points!" CTA.
- **Acceptance Criteria:**
  1. `/loyalty` page loads with all 6 sections.
  2. Tier badge shows correct tier + color.
  3. Progress bar accurately shows progress to next tier.
  4. Points history table shows records with pagination.
  5. Rewards catalog shows all 3 rewards with correct point costs.
  6. Redeeming a reward creates active coupon and deducts points.
- **Evidence Required:** Screenshots: `/loyalty` populated, empty state, mobile view. Screen recording: redeem reward → points deducted → coupon created.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.003
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.005 — Loyalty Badge on Profile, Cart, Checkout
- **Category:** Frontend
- **Implementation Scope:** Add `<LoyaltyBadge />` component showing tier icon + name. Render on: (1) profile page header, (2) cart page near total, (3) checkout page near order summary. Badge color matches tier: Bronze brown, Silver gray, Gold amber, Platinum violet. Tooltip on hover: "{tier} Member — {N} points". Cart badge also shows "Earn {N} pts on this order" estimate before checkout.
- **Acceptance Criteria:**
  1. Badge visible on profile, cart, and checkout.
  2. Badge color matches user's tier.
  3. Tooltip shows tier name and points on hover.
  4. Cart shows estimated points for current order subtotal.
- **Evidence Required:** Screenshots: badge on profile, cart, checkout. Mobile view.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.05.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.006 — Saved Preferences Schema + API
- **Category:** Backend
- **Implementation Scope:** Define preferences schema in `users.preferences` JSONB with whitelist validation: `preferred_cuisines` (string[]), `spice_level` (enum: mild/medium/spicy), `veg_preference` (enum: veg_only/non_veg_ok), `max_delivery_time_min` (integer), `price_range_max` (integer), `packaging` (`no_cutlery` boolean, `eco_friendly` boolean). `GET /api/v1/me/preferences` returns parsed JSON. `PUT /api/v1/me/preferences` accepts partial updates, validates against whitelist, sanitizes input. Reject unknown keys.
- **Acceptance Criteria:**
  1. `GET /api/v1/me/preferences` returns valid preferences object.
  2. `PUT /api/v1/me/preferences` updates partial fields without overwriting others.
  3. Unknown keys rejected with 400.
  4. Missing fields default sensibly (empty cuisines, medium spice, non_veg_ok, 45 min, ₹500).
- **Evidence Required:** `curl` outputs for GET and PUT. DB query showing stored JSONB.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.05.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.007 — Preferences Onboarding Modal + Profile Edit
- **Category:** Frontend
- **Implementation Scope:** Onboarding modal triggered after signup (or skip if user closes). 3-step flow: Step 1 = cuisine chips (multi-select, 8 options), Step 2 = spice level radio (3 options) + veg toggle, Step 3 = max delivery time slider (15-90 min) + max price slider (₹100-₹2000). Progress indicator (dots). "Skip" button on each step. "Save" on final step calls `PUT /api/v1/me/preferences`. Profile page has "Food Preferences" section showing current preferences with "Edit" button opening same modal. Toast on save: "Preferences saved!"
- **Acceptance Criteria:**
  1. Onboarding modal appears after signup.
  2. 3-step flow with progress indicator.
  3. Skip button dismisses modal, sets defaults.
  4. Save persists preferences to API.
  5. Profile page shows current preferences and edit option.
- **Evidence Required:** Screen recording: signup → onboarding → save → profile edit. Screenshots: each step, mobile view.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.006
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.008 — Personalized Homepage Sections
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** `GET /api/v1/home/personalized` returns sections based on user preferences and order history:
  - `because_you_loved`: top 6 restaurants matching `preferred_cuisines`, sorted by rating.
  - `quick_reorder`: last 3 delivered orders with restaurant image, name, date, item count.
  - `new_near_you`: restaurants with `created_at` > now - 14 days, in user's city.
  - `under_budget`: restaurants with `avg_price_per_person` < `price_range_max`.
  - If any section has 0 results, omit it from response.
  **Frontend:** Homepage renders personalized sections as horizontal scroll cards. Each section has title, "See All" link, and card layout. "Quick Reorder" cards have "Reorder" button. "Because you loved" title dynamically uses first preferred cuisine. Fallback to generic sections if user has no preferences/history.
- **Acceptance Criteria:**
  1. Homepage shows personalized sections when user has preferences and/or history.
  2. "Because you loved" title reflects first preferred cuisine.
  3. "Quick Reorder" shows last 3 orders with Reorder button.
  4. Empty sections hidden, no blank gaps.
  5. Fallback to generic sections for new users.
- **Evidence Required:** Screenshots: homepage with all 4 sections, mobile view. Screen recording: reorder from Quick Reorder → cart pre-filled.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.006, working order history
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.009 — Intelligent Offers Engine
- **Category:** Backend
- **Implementation Scope:** Rule-based engine in order-svc or user-svc. Evaluate conditions:
  - **Back after 7 days:** On login, if `last_order_date` is >7 days ago and no existing "COMEBACK20" coupon, generate coupon `COMEBACK20-{user_id}` (20% off, max ₹100, expiry 48h, auto_apply=true).
  - **Frequent orderer:** On order placement, if order count in last 7 days >=3 and no existing "LOYALFREE", generate "LOYALFREE" (free delivery, expiry 7d, auto_apply).
  - **New cuisine:** On order placement, if restaurant cuisine not in user's order history, generate "NEWCUISINE15" (15% off, expiry 7d, auto_apply).
  - **Birthday:** Daily cron checks `dob`. On match, generate "BIRTHDAY100" (₹100 off + free dessert, expiry 3d, auto_apply).
  - **Anniversary:** Daily cron checks account creation date. On match, generate "ANNIV50" (₹50 off, 1yr) or "ANNIV100" (₹100 off, 2yr+).
  Store in `coupons` table with `user_id`, `trigger_reason`, `auto_apply`. Prevent duplicates via unique constraint on (`user_id`, `trigger_reason`, `DATE(generated_at)`).
- **Acceptance Criteria:**
  1. "COMEBACK20" generated for user returning after 8 days.
  2. "LOYALFREE" generated after 3rd order in 7 days.
  3. "NEWCUISINE15" generated on first Chinese order for a North-Indian-only user.
  4. Birthday coupon generated on user's birthday.
  5. No duplicate coupons for same trigger on same day.
- **Evidence Required:** DB query showing generated coupons. API output for login/order showing active coupons. Cron log output.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.001, coupons table
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.010 — Coupon Auto-Apply in Cart / Checkout
- **Category:** Frontend
- **Implementation Scope:** Cart and checkout pages fetch user's active coupons via `GET /api/v1/me/coupons`. If any coupon has `auto_apply=true` and is valid, automatically apply it. Show applied coupon in a highlighted row: "Applied: {code} — You save ₹{amount}". Allow user to remove auto-applied coupon. Show input field for manual coupon code. Validate manual coupon via `POST /api/v1/coupons/validate`. On validation failure, show inline error. Recalculate totals when coupon changes.
- **Acceptance Criteria:**
  1. Auto-applied coupon visible in cart/checkout with savings amount.
  2. Removing auto-applied coupon restores full total.
  3. Manual coupon input validates and applies correctly.
  4. Invalid manual coupon shows error message.
  5. Total breakdown updates in real-time.
- **Evidence Required:** Screen recording: cart loads with auto-applied coupon → remove → enter manual code → apply. Screenshots: applied coupon UI, error state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.05.009
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.011 — Order Streaks Counter + Badges
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** On order creation (status = `placed`), check `order_streak_last_date`. If gap >7 days, set `order_streak_count = 1`, `order_streak_last_date = today`. Else increment `order_streak_count`. On milestone (3, 5, 10 weeks), grant coupon automatically (e.g., "RISINGSTAR" at 3, "LOYALFREE" at 5, "CHAMP100" at 10). **Frontend:** Profile page shows `<StreakBadge />` — flame icon + "{N} week streak!" text. Color intensifies with streak (orange → red). Milestone banners: "5-week streak! You're on fire!" on homepage when streak hits 5. Badges displayed in loyalty dashboard.
- **Acceptance Criteria:**
  1. Consecutive weekly orders increment streak.
  2. Gap >7 days resets streak to 1.
  3. Milestone badges appear at 3, 5, 10 weeks.
  4. Milestone coupons auto-granted.
  5. Streak badge visible on profile with flame icon.
- **Evidence Required:** Screenshots: streak badge on profile, milestone banner on homepage. DB queries showing streak count changes.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.05.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.012 — Birthday / Anniversary Rewards Banner + Coupon
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Daily cron (already in IP.ND.05.009) generates birthday/anniversary coupons. **Frontend:** On app load, if user has active "BIRTHDAY100" or "ANNIV*" coupon, show decorative banner on homepage: "Happy Birthday, {name}!" or "Celebrating {N} years with BhojanGo!". Banner uses CSS confetti animation (particle dots, no canvas/perf hit). Auto-applies coupon at checkout. Birthday checkout adds free dessert line item (first dessert item from cart restaurant, or generic "Birthday treat: Gulab Jamun — ₹0"). Toast on first load: "It's your birthday! Special treat added."
- **Acceptance Criteria:**
  1. Birthday banner shows on homepage with confetti animation.
  2. Anniversary banner shows with year count.
  3. Birthday checkout shows free dessert line item.
  4. Coupon auto-applies at checkout.
  5. Banners disappear after coupon expires.
- **Evidence Required:** Screenshots: birthday banner, anniversary banner, checkout with free dessert line item. Mobile view.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.ND.05.009, IP.ND.05.010
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.013 — Packaging Preference Storage + Checkout Application
- **Category:** Frontend + Backend
- **Implementation Scope:** **Backend:** Extend `users.preferences` JSONB with `packaging.no_cutlery` and `packaging.eco_friendly` booleans. **Frontend:** Checkout page shows packaging options as checkboxes: "No cutlery" and "Eco-friendly packaging". Pre-selected based on saved preference. User can toggle. On order placement, include `packaging_options` in order payload. Profile page "Food Preferences" section shows current packaging choices with edit option. Order confirmation shows: "You've saved ~15g plastic with eco-friendly packaging" if eco selected.
- **Acceptance Criteria:**
  1. Packaging checkboxes pre-selected based on saved preference.
  2. Toggling at checkout persists to user preferences.
  3. Order payload includes packaging options.
  4. Eco-friendly selection shows plastic saved message.
  5. Profile page shows and allows editing packaging preferences.
- **Evidence Required:** Screenshots: checkout with packaging options, profile preferences, order confirmation with eco message.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.05.006
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.05.014 — Seed Data for ND.05
- **Category:** Data
- **Implementation Scope:** Ensure seed data supports all ND.05 features:
  1. Seed `rewards_catalog` with 3 rewards.
  2. Seed demo users with `dob`, `preferences`, `loyalty_tier`, and `current_loyalty_points`.
  3. Ensure demo users have at least 5 delivered orders for Quick Reorder and streak demo.
  4. Pre-generate some `loyalty_history` records for demo users.
  5. Seed some `user_rewards` (active and used) for dashboard demo.
  6. Set one demo user's `dob` to today for birthday banner demo.
  7. Set one demo user's `created_at` to 1 year ago for anniversary demo.
  8. Ensure restaurants have `avg_price_per_person` and `created_at` populated.
- **Acceptance Criteria:**
  1. All demo users have preferences and loyalty data.
  2. At least one user has birthday today, one has anniversary today.
  3. Rewards catalog seeded with 3 items.
  4. Restaurants have `avg_price_per_person` and `created_at`.
- **Evidence Required:** DB query outputs confirming seed data.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.05.001, IP.ND.05.002
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] User schema extended with `dob`, `preferences`, `order_streak_count`, `order_streak_last_date`, `lifetime_loyalty_points`, `current_loyalty_points`, `loyalty_tier`.
- [ ] `GET /api/v1/me` returns all new user fields.
- [ ] `loyalty_history`, `rewards_catalog`, and `user_rewards` tables created and seeded.
- [ ] Points earning works: 10% of order subtotal credited on delivery, tier bonuses applied.
- [ ] Points credit is idempotent (no double-counting on retry).
- [ ] Tier auto-upgrades when lifetime points cross thresholds.
- [ ] `/loyalty` dashboard page shows tier badge, progress bar, points balance, history, rewards catalog, active rewards, streak badge.
- [ ] Reward redemption deducts points and creates active coupon.
- [ ] Loyalty badge visible on profile, cart, and checkout with correct tier color.
- [ ] Cart shows estimated points for current order.
- [ ] Preferences API supports GET and PUT with whitelist validation.
- [ ] Onboarding modal captures preferences in 3 steps with skip option.
- [ ] Profile page shows and allows editing food preferences.
- [ ] Homepage shows personalized sections: "Because you loved...", "Quick Reorder", "New near you", "Under your budget".
- [ ] Personalized sections hidden when no results; fallback to generic sections for new users.
- [ ] Quick Reorder cards pre-fill cart on tap.
- [ ] Intelligent offers generated based on behavior: comeback, frequent orderer, new cuisine, birthday, anniversary.
- [ ] No duplicate coupons for same trigger on same day.
- [ ] Auto-applied coupons visible in cart/checkout with savings amount.
- [ ] Manual coupon input validates and applies correctly.
- [ ] Order streak increments on weekly order, resets after >7 days gap.
- [ ] Milestone badges and coupons granted at 3, 5, 10 weeks.
- [ ] Streak badge visible on profile with flame icon.
- [ ] Birthday banner shows on homepage with confetti animation.
- [ ] Anniversary banner shows on homepage with year count.
- [ ] Birthday checkout includes free dessert line item.
- [ ] Packaging preferences stored and pre-selected at checkout.
- [ ] Eco-friendly packaging shows plastic saved message on confirmation.
- [ ] All new UI follows BhojanGo design system, responsive, dark mode compatible.
- [ ] Seed data fully supports all ND.05 demo scenarios.

## 17. Evidence Required

- Screenshots:
  - `/loyalty` dashboard: tier badge, progress bar, points balance, history table, rewards catalog, active rewards.
  - Loyalty badge on profile, cart, checkout.
  - Preferences onboarding modal: all 3 steps.
  - Profile page showing food preferences with edit option.
  - Homepage with all 4 personalized sections.
  - Homepage fallback for new user (no preferences).
  - "Quick Reorder" section with Reorder button.
  - Cart with auto-applied coupon and savings.
  - Checkout with manual coupon input and validation.
  - Order streak badge on profile (3-week, 5-week, reset state).
  - Birthday banner with confetti on homepage.
  - Anniversary banner on homepage.
  - Checkout with birthday free dessert line item.
  - Checkout with packaging options pre-selected.
  - Order confirmation with eco-friendly plastic saved message.
- Screen recordings:
  - Signup → onboarding modal → set preferences → homepage personalized.
  - Place order → points earned notification → `/loyalty` dashboard updated.
  - Redeem reward → points deducted → coupon created → apply at checkout.
  - Reorder from Quick Reorder → cart pre-filled.
  - 3 orders in a week → streak badge increments → milestone banner appears.
  - Birthday login → banner appears → add items → checkout with free dessert.
- API evidence:
  - `curl` output for `GET /api/v1/me` showing new fields.
  - `curl` output for `PUT /api/v1/me/preferences`.
  - `curl` output for `GET /api/v1/home/personalized`.
  - `curl` output for loyalty points credit and history.
  - `curl` output showing generated coupons.
- DB evidence:
  - Query results confirming `users` columns, `loyalty_history` records, `user_rewards` records, `rewards_catalog` seed data.

## 18. Dependencies

### External Tools
- PostgreSQL (for new tables and JSONB preferences).
- Node.js + pnpm (frontend build).
- Lucide React (icon library).
- Existing coupon/offers infrastructure (coupons table must exist).

### Internal Dependencies
- **PR.04 or PR.05 must be complete:** Stable core ordering loop is prerequisite.
- **ND.03 (Small Convenience Features) must be complete:** Favorites, reorder, filters, veg visibility, restaurant cards, quick-add are required foundations.
- **ND.04 (Demo-Level Differentiation) must be complete:** Visual polish, animation, trust badges, fastest-near-you lane, meal tags, loyalty preview.
- **Auth persistence must work:** `GET /api/v1/me` must be functional for all user data retrieval.
- **Order history must be functional:** Required for Quick Reorder, streaks, and offer triggers.
- **Cart Zustand store** must support coupon application and removal.
- **Coupons/offers table** must exist with basic fields (code, type, value, expiry).
- **Design system** must be applied for consistent badges, cards, and modals.

## 19. Risks / Blockers

- **Coupons table may not exist yet.** If basic coupon infrastructure is missing, IP.ND.05.009 and IP.ND.05.010 are blocked. Mitigation: create minimal `coupons` table as a prerequisite work item.
- **User `dob` field may require privacy consideration.** Storing and exposing date of birth is PII. Ensure field is only visible to self and handled securely. Mitigation: expose only to authenticated owner, mask in admin views.
- **Points credit idempotency requires order-svc retry safety.** If order-svc calls credit endpoint multiple times (network retry), duplicate points must be prevented. Mitigation: unique constraint on (`order_id`, reason='order_delivered') in `loyalty_history`.
- **Personalized homepage requires multiple API calls.** If any call fails, section may be blank. Mitigation: parallel fetch with individual error boundaries; omit failed sections, show generic fallback.
- **Offer generation cron timing.** Birthday/anniversary cron must run at user's local midnight, not server UTC. Mitigation: store user timezone or use 24h window (server midnight ±12h) for simplicity in demo.
- **Streak logic edge case:** User places order at 11:59 PM on day 7 vs 12:01 AM on day 8. Mitigation: use date-only comparison (ignore time), so 7 days = 7 calendar days.
- **Tier auto-upgrade may be jarring.** If user is at 999 lifetime points and gets 50 points, they jump from Bronze to Silver mid-session. Mitigation: show upgrade toast/celebration animation on next app load.

## 20. Exit Criteria

- All P0 work items (IP.ND.05.001 through IP.ND.05.010, IP.ND.05.014) implemented and verified.
- All P1 work items (IP.ND.05.005, IP.ND.05.011, IP.ND.05.012, IP.ND.05.013) implemented and verified.
- Loyalty program complete: points earning, tier system, rewards catalog, redemption flow, dashboard.
- Saved preferences complete: schema, API, onboarding modal, profile edit, applied to restaurant list and homepage.
- Personalized homepage shows relevant sections based on preferences and history.
- Intelligent offers generate and auto-apply correctly for all 5 behavioral triggers.
- Order streaks track, reset, and reward milestone achievements.
- Birthday/anniversary banners and rewards trigger automatically.
- Packaging preferences persist and pre-select at checkout.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.05 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.04)

ND.05 directly depends on ND.04 achievements:
- **ND.04 Visual Polish:** Add-to-cart fly animation, Framer Motion transitions, skeleton loaders — foundation for loyalty dashboard animations and birthday confetti.
- **ND.04 Fastest Near You:** Distance-based sorting and ETA calculation — prerequisite for "New near you" and "Under your budget" sections.
- **ND.04 Meal Tags:** Spice level, dietary badges — prerequisite for preference-based menu highlighting.
- **ND.04 Loyalty Preview:** Points visible on profile (but not redeemable) — ND.05 makes points fully functional with earning/redemption.
- **ND.04 Smart Reorder:** AI-suggested reorder based on time/day — ND.05 adds "Quick Reorder" as explicit UI section.
- **ND.04 Trust Badges:** Freshness score, delivery confidence — ND.05 adds tier badges as trust signals.
- **ND.03 Foundations:** Favorites, reorder, filters, veg visibility, restaurant cards, quick-add — all required for ND.05 personalized homepage and preference application.

## 22. Connected Next-Level Requirements (link to ND.06)

ND.06 (Marketplace-Specific Differentiation, score 6/10) builds on ND.05 and requires:
- Working loyalty program as foundation for gamification expansion (challenges, leaderboards).
- Working preferences as foundation for nutritional filtering and allergen avoidance.
- Working offers engine as foundation for restaurant-specific promos and flash sales.
- Working order history as foundation for nutrition tracking and meal planning.
- Working streaks as foundation for social sharing and referral rewards.

ND.06 will introduce:
- Group ordering / office lunch mode.
- Meal rescue / end-of-day flash sales.
- Home chef / community kitchen section.
- Nutritional transparency panel (calories, macros, allergens).
- Transparent fee breakdown and surge pricing.
- Advanced referral program.

ND.06 will be blocked if:
- Loyalty points are not crediting correctly or are easily gamed.
- Preferences are not persisting or are corrupting.
- Offers are not auto-applying or are generating duplicates.
- Homepage personalization is broken or slow.
- Streak logic is incorrect or unreliable.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (5/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.04 + prerequisites) described | Planner | ✅ |
| 4 | Target state (ND.05 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.05 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.05 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (5 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (loyalty tables, user extensions) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why retention features matter for differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.05.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present (14 total) | Planner | ✅ |
| 17 | Work items cover: loyalty points + tiers + rewards + dashboard, saved preferences + API + UI, personalized homepage sections, intelligent offers engine, order streaks, birthday/anniversary rewards, packaging preference, seed data | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention coupon table existence, PII, idempotency, API failures, cron timing, streak edge cases, tier jump UX | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.04) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.06) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: loyalty program (schema, points, tiers, rewards, dashboard, badge), saved preferences (schema, API, onboarding, profile edit), personalized homepage (4 sections, backend + frontend), intelligent offers (5 behavioral triggers, auto-apply), order streaks (counter, badges, milestones), birthday/anniversary rewards (banner, coupon, free dessert), packaging preference (storage, checkout, eco tracking), seed data.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known gaps from audits (coupon infrastructure may be missing, PII concerns, idempotency, cron timing, streak edge cases).
- Feasibility is strictly LOCAL/DEMO-SAFE — no external AI APIs, no real payment webhooks, no push notifications, no hardware.
