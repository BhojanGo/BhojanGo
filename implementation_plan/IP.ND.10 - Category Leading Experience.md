# IP.ND.10 — Category Leading Experience

## 1. Target Differentiation Score: 10/10

## 2. Score Meaning

Product feels meaningfully different from generic delivery apps, with strong personalization, trust, speed, community, retention, and marketplace intelligence. Category-leading experience. The app is not just different — it is the best-in-class experience for its target market. Every interaction feels optimized. The product sets a standard.

## 3. Current → Target Transition

**From ND.09 (defensible, operationally rich differentiation):**
- Group ordering, office lunch mode, meal rescue, home-chef marketplace, nutrition transparency, fee calculator, sustainability scores, and order batching preview are functional.
- Restaurant cards show cuisine chips, ratings, delivery times, fees, trust badges, eco-badges, and open/closed status.
- Users can filter by dietary goal (High Protein, Low Calorie, Keto, Vegan), price, rating, delivery time, eco-friendly, and rescue-deal availability.
- Nutritional macro fields (calories, protein, carbs, fat), allergen tags, and dietary tags are displayed on menu items.
- Homepage has sections: "Featured," "Popular," "Fastest Near You," "Home Chefs Near You," "Rescue Meals."
- Loyalty points, favorites, smart reorder, and saved preferences are operational.
- Rule-based personalization is active: "Recommended for You," time-aware sections, budget badges, cross-sell associations, sort toggle, and smart search ranking all work.
- Order frequency alerts fire based on detected patterns.
- The app is a complete, differentiated product, but lacks the final aspirational touches that make it category-leading.

**Target at score 10:**
- **Predictive ordering:** The app knows the user's habits so well it offers to place their "usual" order before they ask. A notification at the user's regular order time: "We're placing your usual Thursday order from Spice Garden in 10 min — approve?" One-tap approve. Learns from 4+ weeks of order history.
- **Voice ordering:** A mic button on the homepage lets users speak their order: "Order 2 Paneer Tikka Masala and 1 Butter Naan from Spice Garden." The app parses quantity, item, and restaurant using rule-based NLP over the Web Speech API. Fallback to manual if confidence < 80%.
- **Community tab:** A "Community Tab" on the homepage shows local food events, new chef spotlights, user-generated photos, and a neighborhood leaderboard ("Most Adventurous Eater"). Users can post photos with reviews.
- **Hyper-local micro-marketplaces:** Apartment complex sections show "Your building's top picks this week." Building-specific group orders with concierge delivery (drop at reception).
- **Full sustainability ecosystem:** Carbon footprint per order, monthly carbon report, offset purchase integration, "Green delivery" option (bicycle delivery for <2km), and bicycle rider badge.
- **Family plans:** Family account (up to 5 members) with shared payment method, parental controls (spending limit, approved restaurants), and kids mode (simple UI, large buttons).
- **Health integration:** Connect to Apple Health / Google Fit. Suggest healthy options based on daily calorie budget. Fun message: "You've burned 400 cal today — treat yourself to a biryani!"
- **AR menu preview:** Camera overlay showing approximate portion size on the user's table (mock using fixed image size). "This thali serves 2 people." Fun, not critical.
- **Smart reorder from smartwatch:** Apple Watch / Wear OS app. "Reorder last meal" complication. Basic order status glance.
- **Influencer / food blogger integration:** Verified food blogger profiles. "Chef's recommendation" badge. Collaboration menu items with restaurants.

## 4. Implementation Objective

Add final category-leading touches: predictive ordering, full ecosystem integration, voice/AI interfaces, and hyper-local community features. These are aspirational but technically feasible with lightweight ML and browser APIs. The goal is to make BhojanGo feel like the most thoughtful food delivery platform on the market — not through gimmicks, but through genuinely useful features that respect user habits, community, health, and the environment.

## 5. Scope

### 5.1 Predictive Ordering Engine
- **Data inputs:** 4+ weeks of order history per user. Pattern detection: (restaurant_id, day_of_week, hour_bucket) frequency. Minimum 3 occurrences of the same pattern to trigger prediction.
- **Trigger timing:** 15 minutes before the user's typical order time for that day/hour pattern.
- **Notification content:** "We're placing your usual {day} order from {restaurant_name} in {n} min — approve?"
- **One-tap approve:** Tapping "Approve" pre-fills the cart with the exact same items and quantities from the last matching order, skips to checkout with saved address and payment method pre-selected, and places the order after a 3-second countdown (cancelable).
- **One-tap decline:** Tapping "Not today" dismisses the notification and suppresses the same pattern for 7 days.
- **Frontend:** In-app banner (not push notification — demo-safe). Banner appears on homepage load when conditions match. Uses existing toast/banner component.
- **Backend:** `GET /api/v1/users/{id}/predictive-order` returns the predicted order (restaurant, items, next predicted time) or null. `POST /api/v1/orders/predictive` accepts a predictive order ID and places it with pre-filled data.

### 5.2 Voice Ordering (Web Speech API + Rule-Based NLP)
- **Mic button:** Floating mic button on homepage and restaurant listing. Pulsing animation when listening.
- **Speech capture:** Uses browser `SpeechRecognition` API (Web Speech API). Captures transcript in real-time.
- **Rule-based NLP parser:**
  - Extracts quantity: regex for numbers ("2", "two").
  - Extracts item name: fuzzy match against all menu item names in the user's city (cached locally or fetched via lightweight API).
  - Extracts restaurant name: fuzzy match against restaurant names.
  - Handles common patterns: "Order {qty} {item} from {restaurant}", "Get me {qty} {item} and {qty} {item}", "Reorder my last meal."
- **Confidence scoring:** Parser returns confidence 0.0-1.0 based on match quality. If < 0.8, show disambiguation modal: "Did you mean 'Paneer Tikka Masala' from 'Spice Garden'?"
- **Fallback:** If Web Speech API is unsupported (Firefox, some mobile browsers), hide the mic button. If parsing fails, show "Sorry, I didn't catch that. Please type your order."
- **Actions:** Successful parse → add items to cart → navigate to cart with toast "Added from voice command."

### 5.3 Community Tab
- **Tab placement:** Fifth tab in bottom navigation (mobile) or top nav row (desktop): Home | Search | Community | Cart | Profile.
- **Content sections:**
  - **Local Food Events:** "Dosa Festival at Krishna Hall this Sunday." Admin-curated or restaurant-posted events with date, location, and RSVP.
  - **New Chef Spotlight:** Featured home chef or restaurant chef of the week. Photo, bio, signature dish, link to restaurant.
  - **User-Generated Photos:** Grid of photos tagged to restaurants/dishes. Users upload via "Add Photo" button on order confirmation or restaurant detail. Photos link to the dish/restaurant.
  - **Neighborhood Leaderboard:** "Most Adventurous Eater" (most unique cuisines ordered), "Top Contributor" (most photos/reviews), "Green Champion" (most eco deliveries). Weekly refresh.
- **Posting flow:** User taps "Share your experience" → uploads photo (max 5MB) → writes caption (max 280 chars) → tags restaurant and dish → posts. Moderation: auto-approve for demo; flag for review in production.
- **Backend:** New `community_posts` table. Endpoints: `GET /api/v1/community/feed`, `POST /api/v1/community/posts`, `GET /api/v1/community/leaderboard`.

### 5.4 Hyper-Local Micro-Marketplaces
- **Building detection:** User can optionally associate their profile with a building name (free-text or dropdown from popular buildings in the city). Stored in `users.building_name`.
- **Building-specific section on homepage:** If `building_name` is set, show "Top Picks in {building_name}" — restaurants most ordered from by users in the same building.
- **Building group orders:** "Start a {building_name} group order" — generates a building-scoped group order link (vs. general group order). Only users with the same `building_name` can join.
- **Concierge delivery:** At checkout, if user selects "Drop at Reception / Concierge" as a delivery instruction, the order is tagged `concierge_drop = true`. Driver app shows "Drop at reception of {building_name}." No signature required.
- **Backend:** Lightweight aggregation query: `SELECT restaurant_id, COUNT(*) FROM orders WHERE user_id IN (SELECT id FROM users WHERE building_name = ?) GROUP BY restaurant_id ORDER BY count DESC LIMIT 5`.

### 5.5 Full Sustainability Ecosystem
- **Carbon footprint per order:**
  - Calculate estimated CO₂ per order based on: delivery distance (km) × vehicle emissions factor (g CO₂/km). Bicycle = 0 g. Electric scooter = 20 g/km. Petrol bike = 80 g/km.
  - Show on order confirmation: "This order generated ~{X}g CO₂."
  - Batched orders get a discount factor: batched order = 60% of solo delivery emissions (shared trip).
- **Monthly carbon report:**
  - Analytics card in profile: "Your June impact: {X}kg CO₂ from {N} orders. You saved {Y}kg by choosing eco delivery."
  - Equivalent comparison: "That's like driving a car for {Z} km."
- **Offset purchase integration:**
  - At checkout, optional toggle: "Offset {X}g CO₂ for ₹{Y}" (price computed at ₹0.05 per 100g CO₂).
  - Toggled on by default for users who previously opted in. Stored in `users.auto_offset = true`.
  - Funds tracked in a virtual "carbon offset wallet" (optional demo step: show as collected, no real purchase needed).
- **Green delivery option:**
  - At checkout, if delivery distance < 2km, show "Green delivery" option: bicycle delivery, no extra cost, +10 loyalty points bonus.
  - Tagged on order as `green_delivery = true`.
- **Bicycle rider badge:** Riders who complete 50+ green deliveries get a "Green Rider" badge on their profile.

### 5.6 Family Plans
- **Family account creation:**
  - Primary user (parent) creates a "Family" from profile settings. Generates an invite code (6-character alphanumeric).
  - Up to 4 additional members join via code. Stored in `family_members` table.
- **Shared payment method:**
  - Family admin sets a default payment method for all members. Members can optionally use their own.
  - Family orders are billed to the admin's payment method by default.
- **Parental controls:**
  - Spending limit per member per week (e.g., ₹1,000 for teen). Enforced at checkout.
  - Approved restaurant list: admin selects which restaurants each member can order from. Checkout blocked if cart contains unapproved restaurant.
- **Kids mode:**
  - Toggle in profile: "Switch to Kids Mode."
  - UI simplifies: large buttons (min 72px tap target), high-contrast colors, emoji icons, limited menu (only approved restaurants), price hidden (or shown as "Coins" abstracted from real currency).
  - Locked behind PIN (4-digit) to exit kids mode.
- **Backend:** `family_groups` table, `family_members` table, new endpoints for CRUD and validation.

### 5.7 Health Integration
- **Platform connections:**
  - Apple Health (iOS): request read permission for `activeEnergyBurned` and `dietaryEnergyConsumed`. Uses HealthKit API (or mocked for demo with manual input).
  - Google Fit (Android): request read permission for `com.google.active_minutes` and `com.google.calories.expended`. Uses Fitness REST API (or mocked for demo).
  - Web fallback: manual input daily calorie budget and burned calories.
- **Healthy option suggestions:**
  - If connected, read today's `activeEnergyBurned` (calories burned).
  - Suggest menu items based on remaining calorie budget: `budget = daily_goal - consumed_so_far`.
  - Items tagged with calorie data from ND.06 nutrition panel.
  - "Light & Fresh" filter badge on restaurant list when health data shows low remaining budget.
- **Fun messaging:**
  - If burned > 300 cal today: "You've been active today — treat yourself to a biryani!"
  - If no activity: "Fuel up with a healthy bowl — only 350 cal!"
- **Privacy:** Health data is read-only, stored locally in browser/app, never sent to backend. Backend only receives "calorie_budget_remaining" integer if user opts in.

### 5.8 AR Menu Preview (Lightweight)
- **Camera overlay:**
  - On menu item detail, an "AR Preview" button opens device camera (via `getUserMedia`).
  - Overlays a fixed-size plate image (PNG with transparency) on the camera feed using absolute positioning.
  - The plate image is proportioned to represent the actual dish size (e.g., thali plate = large, single naan = small).
  - Text overlay: "This thali serves 2 people." or "Approx. 8-inch diameter."
- **Fallback:** If camera permission denied or not supported, show a static popup with the same plate image on a transparent background.
- **Scope:** Purely visual, no actual 3D model or depth sensing. Uses CSS `position: absolute` over `<video>` element.

### 5.9 Smartwatch Companion
- **Apple Watch app:**
  - Complication: "Reorder Last Meal" — one-tap reorder from the watch face.
  - Glance: Current order status (Confirmed → Preparing → Out for Delivery → Delivered) with emoji status icons.
  - Notification: Order status change pings the watch (demo: simulated in watch emulator).
- **Wear OS app:**
  - Tile: Order status at a glance.
  - Button: "Reorder last meal."
- **Backend:** Existing order status WebSocket or polling endpoint reused. Minimal new API: `GET /api/v1/orders/last` returns the most recent order summary.
- **Demo approach:** Build as a responsive web view or PWA optimized for watch screen sizes if native watch development is out of scope. Alternatively, mock screenshots in documentation.

### 5.10 Influencer / Food Blogger Integration
- **Verified blogger profiles:**
  - Admin can mark users as `role = 'food_blogger'` and add `verified_badge = true`.
  - Blogger profile page: photo, bio, follower count, favorite restaurants, "Top 5 must-try dishes" list.
- **"Chef's Recommendation" badge:**
  - Bloggers can tag menu items with "Recommended" from their profile. Tagged items show a "Recommended by {blogger_name}" badge on the menu.
  - Limited to 5 recommendations per blogger per month to prevent spam.
- **Collaboration menu items:**
  - Restaurants can create "{Blogger_name} Special" menu items. Shown with a purple "Collaboration" badge.
  - Revenue split tracked (out of scope for actual payment; tracked in analytics only).
- **Backend:** Extend `users` table for blogger fields. New `blogger_recommendations` table. New `collaboration_items` table.

## 6. Out of Scope

- Blockchain / carbon-neutral verification (overkill for demo).
- Autonomous delivery drones (not technically or legally feasible for a demo).
- Full metaverse dining (gimmick, no real value).
- Heavy computer vision models for AR (the AR preview is a fixed image overlay, not ML-based).
- Native smartwatch app store submission (mock/watch-optimized web view is sufficient).
- Real carbon offset purchase transactions (mock integration, show as "tracked" only).
- Full NLP pipeline with training data (rule-based regex only).
- Automatic family payment splitting between members (all bills to admin for simplicity).
- Real-time health data sync from wearable devices to backend (privacy-preserving local read only).
- Restaurant kitchen IoT integration (temperature sensors, etc.).
- Full social network features (DMs, following, stories — community tab is food-focused only).

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.05 or PR.06 complete).
- Auth persistence must work. Predictive ordering, family plans, and community features require authenticated users.
- Order history must be queryable per user (4+ weeks of data for predictive ordering).
- `users` table must support new columns: `building_name`, `auto_offset`, `role` (blogger), `verified_badge`.
- `family_groups` and `family_members` tables must be created.
- `community_posts` table must be created.
- `blogger_recommendations` and `collaboration_items` tables must be created.
- Cart Zustand store must support programmatic addition (for voice ordering and predictive order pre-fill).
- Homepage must be composable (community tab, predictive banner, building section can be added).
- Toast/snackbar component exists for predictive order alerts and voice confirmation.
- Web Speech API support in target browser (Chrome/Edge for demo).
- Camera access via `getUserMedia` for AR preview.
- Design system (BhojanGo palette, typography, spacing, Lucide icons) applied across new UI.
- Order status WebSocket or polling endpoint must be functional (for smartwatch glance).
- Carbon calculation constants configured (emissions factors per vehicle type).

## 8. Key User Journeys

### Journey 8.1 — Predictive Ordering Saves Time
1. Priya has ordered from "Spice Garden" every Thursday at 1 PM for the past 6 weeks.
2. On Thursday at 12:45 PM, she opens BhojanGo.
3. A banner appears: "We're placing your usual Thursday order from Spice Garden in 10 min — approve?"
4. The banner shows the items: Butter Chicken (1), Garlic Naan (2), Raita (1).
5. Priya taps "Approve."
6. The app shows a 3-second countdown: "Placing order... 3... 2... 1..." with a cancel button.
7. Order is placed. Confirmation screen shows. She did not have to browse, add to cart, or enter payment details.

### Journey 8.2 — Voice Ordering While Driving
1. Raj is driving home. He taps the mic button on the BhojanGo homepage.
2. He says: "Order two Paneer Tikka Masala and one Butter Naan from Spice Garden."
3. The app transcribes, parses, and shows a confirmation card: "2 × Paneer Tikka Masala, 1 × Butter Naan from Spice Garden — ₹640. Add to cart?"
4. Raj taps "Yes."
5. Items are added to cart. He can checkout when he parks.

### Journey 8.3 — Community Tab Discovery
1. Ankit opens the Community tab.
2. He sees a "New Chef Spotlight" on Home Chef Lakshmi, who makes authentic Chennai-style idli.
3. He browses her photo gallery, taps her profile, and orders her "Special Ghee Podi Idli."
4. After eating, he posts a photo with a review. His photo appears in the community feed.
5. He checks the neighborhood leaderboard and sees he's #3 "Most Adventurous Eater" this week.

### Journey 8.4 — Building Group Order
1. Maya lives in "Sunrise Apartments." She starts a building group order at 12:30 PM.
2. A link is shared in her building WhatsApp group: "Join the Sunrise Apartments lunch order."
3. Three neighbors join. They add items from "Biryani House."
4. Maya checks out. The delivery instruction is pre-set: "Drop at Sunrise Apartments reception."
5. The driver drops the bag at reception. Maya gets a notification: "Your order is at reception."

### Journey 8.5 — Eco-Conscious Ordering
1. Ravi places an order at 7 PM. Distance is 1.5 km.
2. At checkout, he sees: "Green delivery available — bicycle delivery, +10 points."
3. He selects it. Order confirmation shows: "This order generated 0g CO₂. Great choice!"
4. At month-end, his profile shows: "Your May impact: 0.4 kg CO₂. You saved 1.2 kg by choosing eco delivery. That's like not driving for 8 km."
5. He toggles "Auto-offset my CO₂" on. Future orders automatically include a ₹2 offset.

### Journey 8.6 — Family Plan with Parental Controls
1. Sneha (parent) creates a family plan and adds her son Arjun (age 14).
2. She sets Arjun's weekly spending limit to ₹800 and approves only 5 restaurants.
3. Arjun opens the app in Kids Mode. Large buttons, emoji icons, only 5 approved restaurants visible.
4. He adds a pizza to cart. At checkout, a message appears: "₹200 of ₹800 weekly budget used."
5. He tries to order from an unapproved restaurant. The app blocks him: "Ask your parent to approve this restaurant."
6. Sneha gets a notification and approves it from her profile.

### Journey 8.7 — Health-Aware Suggestion
1. Divya has connected Apple Health. She burned 450 calories on her morning run.
2. She opens BhojanGo at 1 PM. The homepage banner says: "You've been active today — treat yourself!"
3. She browses restaurants. The "Light & Fresh" filter is suggested because her remaining calorie budget is low.
4. She orders a grilled chicken bowl (450 cal). The app shows: "This fits your day perfectly."

### Journey 8.8 — AR Menu Preview
1. Karthik is ordering a "Maharaja Thali" for a family dinner.
2. On the item detail page, he taps "AR Preview."
3. His camera opens. A plate overlay appears on his dining table showing the approximate size.
4. Text reads: "This thali serves 2-3 people. Approx. 12-inch diameter."
5. He realizes one thali is enough for his family of three. He adjusts his order.

### Journey 8.9 — Smartwatch Reorder
1. During a meeting, Vikram glances at his Apple Watch.
2. The BhojanGo complication shows: "Lunch status: Preparing."
3. He taps the complication → sees his order details and ETA.
4. He long-presses and taps "Reorder Last Meal." His usual order is placed from his watch.

### Journey 8.10 — Blogger Recommendation Drives Discovery
1. Shreya follows food blogger "SpicySid" on BhojanGo.
2. She sees his "Chef's Recommendation" badge on "Mirchi Ka Salan" at Biryani House.
3. She orders it. The item page shows: "Recommended by SpicySid — 'The best salan in Hyderabad.'"
4. She later sees a "SpicySid Special" collaboration menu item: "Sid's Extra Spicy Biryani."
5. She orders it and leaves a review.

## 9. Technical Coverage

### Backend
- **user-svc:**
  - Extend `users` table: `building_name` VARCHAR, `auto_offset` BOOLEAN DEFAULT false, `role` VARCHAR (enum: customer, restaurant_owner, delivery_partner, admin, food_blogger), `verified_badge` BOOLEAN DEFAULT false.
  - `GET /api/v1/users/{id}/predictive-order` — returns predicted order or null.
  - `POST /api/v1/family` — create family group.
  - `POST /api/v1/family/join` — join family via invite code.
  - `GET /api/v1/family` — get family details and members.
  - `PATCH /api/v1/family/members/{id}/limits` — update spending limit and approved restaurants.
  - `GET /api/v1/bloggers` — list verified bloggers.
  - `GET /api/v1/bloggers/{id}/recommendations` — get blogger's recommended items.
- **order-svc:**
  - `POST /api/v1/orders/predictive` — place an order using predictive pre-fill.
  - `GET /api/v1/orders/last` — get most recent order for smartwatch.
  - Carbon calculation helper: `calculate_carbon_footprint(distance_km, vehicle_type, is_batched)`.
- **restaurant-svc:**
  - `GET /api/v1/restaurants/building-top-picks?building={name}` — aggregate top restaurants per building.
  - `GET /api/v1/community/feed` — paginated community posts.
  - `POST /api/v1/community/posts` — create a community post.
  - `GET /api/v1/community/leaderboard` — weekly leaderboard data.
  - `GET /api/v1/menu-items/search` — lightweight name search for voice ordering fuzzy match.
- **payment-svc (mock):**
  - Track carbon offset as a line item in order totals. No real external payment needed.

### Frontend
- **Zustand store extensions:**
  - `voiceStore` — recording state, transcript, parsed command, confidence.
  - `predictiveStore` — predicted order data, banner visibility, countdown state.
  - `communityStore` — feed posts, leaderboard, posting form state.
  - `familyStore` — family group, members, limits, kids mode state.
  - `healthStore` — connected platform, daily calories burned/consumed, budget remaining.
  - `sustainabilityStore` — carbon per order, monthly stats, offset toggle.
- **Components:**
  - `<PredictiveOrderBanner />` — homepage banner with approve/decline buttons and countdown.
  - `<VoiceOrderButton />` — floating mic button with listening animation.
  - `<VoiceConfirmationModal />` — disambiguation/confirmation after voice parse.
  - `<CommunityTab />` — tab page with events, chef spotlight, photo feed, leaderboard.
  - `<CommunityPostCard />` — photo, caption, user, tagged restaurant, like count.
  - `<LeaderboardRow />` — rank, avatar, name, score, badge.
  - `<BuildingSection />` — homepage section for building-specific top picks.
  - `<GreenDeliveryToggle />` — checkout toggle for bicycle delivery.
  - `<CarbonReportCard />` — profile card with monthly CO₂ stats.
  - `<FamilyPlanManager />` — profile page section for creating/managing family.
  - `<KidsModeToggle />` — profile toggle with PIN entry modal.
  - `<KidsModeLayout />` — simplified wrapper with large buttons and emoji icons.
  - `<HealthConnectButton />` — Apple Health / Google Fit connection flow.
  - `<HealthBanner />` — homepage banner with activity-based message.
  - `<ARPreviewButton />` — menu item detail button opening camera overlay.
  - `<AROverlay />` — `<video>` + `<img>` overlay component.
  - `<BloggerBadge />` — "Recommended by {name}" badge on menu items.
  - `<BloggerProfileCard />` — blogger profile preview on community tab.
- **Hooks:**
  - `usePredictiveOrder()` — fetches and manages predictive order banner state.
  - `useVoiceOrder()` — handles SpeechRecognition lifecycle and parser.
  - `useCommunityFeed()` — fetches and paginates community posts.
  - `useFamilyPlan()` — CRUD for family group and limits.
  - `useHealthData()` — reads/writes health platform connection and calorie data.
  - `useCarbonFootprint()` — computes and displays order-level carbon.
  - `useARPreview()` — manages camera permission and overlay state.

### Data
- New tables:
  - `family_groups` (id, admin_user_id, invite_code, created_at).
  - `family_members` (id, family_group_id, user_id, spending_limit_weekly, approved_restaurants JSONB, is_active).
  - `community_posts` (id, user_id, image_url, caption, restaurant_id, menu_item_id, created_at, likes_count).
  - `blogger_recommendations` (id, blogger_user_id, menu_item_id, comment, created_at, is_active).
  - `collaboration_items` (id, restaurant_id, name, description, price, blogger_user_id, badge_text, created_at).
- Extended tables:
  - `users`: add `building_name`, `auto_offset`, `role`, `verified_badge`.
  - `orders`: add `green_delivery` BOOLEAN, `carbon_g` INT, `offset_amount` DECIMAL(10,2), `concierge_drop` BOOLEAN.
- Seed data:
  - 2-3 verified blogger users with recommendations.
  - 5-10 community posts with images and captions.
  - 1 demo family group with 2 members and limits.
  - Carbon emissions constants in config.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for community feed, skeleton rows for leaderboard, shimmer for predictive banner, mic button pulsing animation while listening.
- **Error states:**
  - "Couldn't access microphone. Please check permissions." (voice ordering).
  - "Camera access denied. Showing static preview instead." (AR preview).
  - "Not enough order history for predictions. Order a few more times!" (predictive ordering).
  - "No posts yet. Be the first to share!" (community tab empty state).
  - "Health data unavailable. Enter calories manually." (health integration).
- **Empty states:**
  - Community tab shows illustration + CTA when no posts exist.
  - Leaderboard hidden until at least 3 users have activity.
  - Building section hidden if user has no `building_name` set — show prompt: "Add your building to see top picks."
  - Kids mode shows only approved restaurants; if none approved, show "Ask your parent to add restaurants."
- **Success states:**
  - Toast on predictive order approve: "Order placed! Spice Garden will start preparing soon."
  - Toast on voice order add: "Added 2 items from Spice Garden to your cart."
  - Toast on community post: "Your photo is live!"
  - Toast on family invite: "Arjun joined your family plan."
- **Design system:** All new components follow BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons.
- **Responsive:**
  - Community tab: 1 col mobile, 2 col tablet, 3 col desktop for photo grid.
  - Predictive banner: full-width on all breakpoints, compact on mobile.
  - Family plan manager: stacked cards on mobile, side-by-side on desktop.
  - AR preview: fullscreen on mobile, modal on desktop.
  - Voice button: fixed bottom-right on mobile, inline on desktop.
- **Dark mode:** Community cards use dark cream backgrounds. Predictive banner uses dark saffron tint. Voice button uses gold glow. Sustainability cards use dark green accents.
- **Accessibility:**
  - Mic button: `aria-label="Order with voice"`, `role="button"`.
  - Predictive banner: `aria-live="polite"` for countdown updates.
  - Community photos: `alt` text from caption.
  - Kids mode: all buttons have `aria-label`, high contrast enforced.
  - Voice confirmation: focus trapped in modal, escape key dismisses.

## 11. Data / Model Coverage

- `users` table (extended): `building_name` VARCHAR(100), `auto_offset` BOOLEAN DEFAULT false, `role` VARCHAR(20) DEFAULT 'customer', `verified_badge` BOOLEAN DEFAULT false.
- `orders` table (extended): `green_delivery` BOOLEAN DEFAULT false, `carbon_g` INT DEFAULT 0, `offset_amount` DECIMAL(10,2) DEFAULT 0.00, `concierge_drop` BOOLEAN DEFAULT false.
- `family_groups` table (new): `id` UUID PK, `admin_user_id` UUID FK → `users.id`, `invite_code` VARCHAR(6) UNIQUE, `created_at` TIMESTAMP.
- `family_members` table (new): `id` UUID PK, `family_group_id` UUID FK → `family_groups.id`, `user_id` UUID FK → `users.id`, `spending_limit_weekly` DECIMAL(10,2) DEFAULT 0.00, `approved_restaurants` JSONB DEFAULT '[]', `is_active` BOOLEAN DEFAULT true, `created_at` TIMESTAMP.
- `community_posts` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `image_url` VARCHAR(500), `caption` VARCHAR(280), `restaurant_id` UUID FK → `restaurants.id` (nullable), `menu_item_id` UUID FK → `menu_items.id` (nullable), `likes_count` INT DEFAULT 0, `created_at` TIMESTAMP.
- `blogger_recommendations` table (new): `id` UUID PK, `blogger_user_id` UUID FK → `users.id`, `menu_item_id` UUID FK → `menu_items.id`, `comment` VARCHAR(280), `created_at` TIMESTAMP, `is_active` BOOLEAN DEFAULT true.
- `collaboration_items` table (new): `id` UUID PK, `restaurant_id` UUID FK → `restaurants.id`, `name` VARCHAR(100), `description` TEXT, `price` DECIMAL(10,2), `blogger_user_id` UUID FK → `users.id`, `badge_text` VARCHAR(50), `created_at` TIMESTAMP.
- Seed data requirements:
  - 2-3 verified blogger users with bios and recommendations.
  - 5-10 community posts with realistic captions and image URLs.
  - 1 demo family group with admin + 1 member, spending limit set, approved restaurants list populated.
  - Emissions factors in config: bicycle = 0, e-scooter = 20, petrol = 80 (g CO₂/km).
  - Predictive order patterns: seed 4+ orders for a demo user at the same restaurant/day/time.

## 12. Role / Permission Coverage

- `customer` (logged-in):
  - Full access to predictive ordering, voice ordering, community tab (post, like, view), health integration, sustainability features.
  - Can join a family via invite code. Cannot create family unless they are the admin/parent.
  - Can view blogger recommendations and collaboration items.
- Guest (unauthenticated):
  - No predictive ordering (requires history).
  - No voice ordering (requires cart session but can be allowed — parse adds to guest cart).
  - Community tab visible as read-only. Cannot post.
  - No family plan, health integration, or sustainability tracking.
- `food_blogger` (verified):
  - Can create recommendations (max 5 active). Can have collaboration items.
  - Community posts from bloggers get a "Verified" checkmark.
- `restaurant_owner`:
  - Can approve/manage collaboration items on their restaurant.
  - Can view building-specific analytics (top picks in buildings near them).
- `admin`:
  - Can grant `food_blogger` role and `verified_badge`.
  - Can moderate community posts (hide/delete).
  - Can view all family plans and override limits.
  - Can configure carbon offset pricing and emissions factors.
- `delivery_partner`:
  - Sees `concierge_drop` and `green_delivery` flags on assigned orders.
  - Green delivery orders tagged for bicycle riders only.

## 13. Performance / Reliability / Security Coverage

### Performance
- Predictive order lookup: single query on `orders` table filtered by `user_id`, ordered by `created_at DESC`, limited to last 30 days. Pattern aggregation in app code. <20ms.
- Voice ordering fuzzy match: client-side or lightweight API call. If client-side, cache menu item names in IndexedDB (max ~500 items per city). <100ms parse time.
- Community feed: paginated API, 10 posts per page. Image lazy loading. <50ms per page.
- Building aggregation: single indexed query with subquery. <30ms.
- Carbon calculation: arithmetic in app code. <1ms.
- Family validation: lookup `family_members` by `user_id` on checkout. <5ms.
- Smartwatch data: reuses existing order status endpoint. No extra load.

### Reliability
- Predictive ordering fallback: if pattern is weak (<3 occurrences) or user declines twice, suppress for 14 days. Never spam.
- Voice ordering fallback: if `SpeechRecognition` is unsupported, hide mic button gracefully. If parse confidence < 0.8, show disambiguation — never guess incorrectly.
- AR preview fallback: if camera denied, show static modal with plate image. No broken experience.
- Health data fallback: if Apple Health / Google Fit permission denied, prompt for manual input. Store locally; no backend dependency.
- Family plan enforcement: spending limit checked server-side at checkout (not client-side). Approved restaurant list validated server-side.
- Community moderation: auto-approve for demo. In production, flag posts with forbidden words for review.
- Carbon offset: mock only. No real payment processing. Toggle state saved to user profile.

### Security
- Predictive order placement: requires re-authentication or PIN for orders > ₹500 (configurable). Prevents accidental placement if phone is unlocked by someone else.
- Family plan: invite codes are single-use and expire in 7 days. Admin can revoke members anytime.
- Kids mode exit: requires 4-digit PIN set by admin. PIN is hashed (bcrypt) server-side.
- Community posts: image upload restricted to 5MB, validated MIME type (jpg/png/webp). Stored in S3 or local with UUID filename (no raw user input in path).
- Health data: read-only from device. Never transmitted to backend except anonymized `calorie_budget_remaining` integer if user explicitly opts in.
- Voice transcript: processed locally in browser. No audio sent to server. Only parsed structured data (item_id, qty) is transmitted.
- Rate limiting: community post creation limited to 5 posts per hour per user. Voice parse API limited to 30 requests per minute.

## 14. Novelty / Differentiation Coverage

At score 10, differentiation is about **category leadership** — the app doesn't just have features, it has the *right* features integrated thoughtfully.

- **Predictive Ordering:** No competitor pre-fills and offers to place a user's "usual" order before they ask. This is the ultimate retention feature — it removes all friction from repeat ordering. The 3-second cancelable countdown respects user agency while enabling zero-tap ordering.
- **Voice Ordering:** While some apps have voice search, rule-based NLP that parses quantity + item + restaurant and adds directly to cart is rare. The Web Speech API keeps it lightweight, local, and demo-safe. The disambiguation modal prevents the frustration of "sorry, I didn't understand."
- **Community Tab:** Food delivery apps are transactional. Adding a community layer (chef spotlights, photo sharing, leaderboards) creates emotional engagement and discovery that drives orders from social inspiration, not just hunger.
- **Hyper-Local Micro-Marketplaces:** Building-specific discovery and group orders create network density. "Your building's top picks" leverages social proof at the closest possible level. Concierge delivery solves the "I'm not home" problem for apartment dwellers.
- **Sustainability Ecosystem:** Carbon footprint per order, monthly reports, green delivery, and offset integration make BhojanGo the environmentally conscious choice. The bicycle rider badge gamifies eco behavior for both customers and drivers.
- **Family Plans:** Parental controls, spending limits, approved restaurants, and kids mode make BhojanGo the only family-safe food delivery app. This targets a completely underserved segment: parents who want to let teens order independently but within boundaries.
- **Health Integration:** Connecting to Apple Health / Google Fit and suggesting food based on calorie budget adds a wellness dimension. The tone is fun ("treat yourself") rather than restrictive, making it inviting rather than judgmental.
- **AR Menu Preview:** While lightweight (fixed image overlay), it addresses a real problem: users don't know portion sizes. "This thali serves 2" prevents over-ordering and increases satisfaction.
- **Smartwatch Companion:** Reorder from the watch face and glance at order status. This is the definition of convenience — ordering without taking your phone out.
- **Influencer Integration:** Verified blogger recommendations and collaboration items create a content-commerce loop. Bloggers drive discovery; restaurants get credibility; users get trusted suggestions.

**Differentiators deferred (out of scope):**
- Blockchain carbon verification (overkill).
- Autonomous drones (not feasible).
- Metaverse dining (gimmick).
- Heavy ML for AR (fixed overlay is sufficient).
- Real offset payments (mock is demo-safe).

## 15. Implementation Work Items

### IP.ND.10.001 — Predictive Ordering Engine
- **Category:** Backend + Frontend
- **Implementation Scope:** Build `GET /api/v1/users/{id}/predictive-order` endpoint. Query last 30 days of orders. Aggregate `(restaurant_id, day_of_week, hour_bucket)` frequencies. Return the pattern with >=3 occurrences and earliest next predicted time. Build `<PredictiveOrderBanner />` component: appears on homepage when current time is within 15 min of predicted time. Shows items from last matching order. "Approve" triggers `POST /api/v1/orders/predictive` with 3-second countdown (cancelable). "Decline" suppresses pattern for 7 days. Invalidate banner on decline or successful placement.
- **Acceptance Criteria:**
  1. Banner appears only when user has >=3 orders of the same restaurant/day/time pattern.
  2. Banner shows correct restaurant name, items, and countdown.
  3. Tapping "Approve" places the order with pre-filled address and payment.
  4. Tapping "Decline" hides banner and suppresses same pattern for 7 days.
  5. 3-second countdown allows cancellation before order is placed.
- **Evidence Required:** Screenshot of banner. Screen recording: approve → countdown → confirmation. API curl for GET predictive-order.
- **Priority:** P0
- **Effort:** M
- **Dependency:** ND.07 (order history), PR.05 (stable checkout)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.002 — Voice Ordering (Web Speech API + Rule-Based NLP)
- **Category:** Frontend + Backend
- **Implementation Scope:** Add `<VoiceOrderButton />` floating button on homepage. Uses `SpeechRecognition` API (or `webkitSpeechRecognition`). On result, send transcript to `POST /api/v1/voice/parse` endpoint. Backend parser uses regex to extract quantity (numbers/words), item name (fuzzy match against `menu_items.name`), and restaurant name (fuzzy match against `restaurants.name`). Returns parsed result with confidence score. If confidence >= 0.8, show `<VoiceConfirmationModal />` with parsed items. User confirms → add to cart. If confidence < 0.8, show disambiguation: "Did you mean X from Y?" If API unsupported, button is hidden.
- **Acceptance Criteria:**
  1. Mic button is visible on supported browsers (Chrome/Edge).
  2. Voice command "Order 2 Paneer Tikka from Spice Garden" parses correctly.
  3. Confirmation modal shows exact items and restaurant before adding to cart.
  4. Low confidence triggers disambiguation, not silent failure.
  5. Unsupported browsers hide the button gracefully.
- **Evidence Required:** Screen recording: tap mic → speak → parse → confirm → cart updated. API curl for voice parse endpoint.
- **Priority:** P0
- **Effort:** M
- **Dependency:** PR.05 (stable cart), ND.03 (menu discovery)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.003 — Community Tab
- **Category:** Frontend + Backend + Data
- **Implementation Scope:** Create `community_posts` table. Build `GET /api/v1/community/feed` (paginated) and `POST /api/v1/community/posts` endpoints. Build Community tab page with 4 sections: Events, Chef Spotlight, Photo Feed (grid), Leaderboard. `<CommunityPostCard />` shows image, caption, user avatar, tagged restaurant, like count. "Share your experience" button opens form: image upload (validated, UUID filename), caption (280 chars), optional restaurant/item tags. Build `GET /api/v1/community/leaderboard` with 3 categories: Most Adventurous Eater, Top Contributor, Green Champion. Weekly refresh via simple aggregation query.
- **Acceptance Criteria:**
  1. Community tab is accessible from bottom nav (mobile) or top nav (desktop).
  2. Photo feed displays posts in reverse chronological order.
  3. User can upload a photo with caption and tag a restaurant.
  4. Leaderboard shows top 10 users per category with avatars.
  5. Empty state shows illustration + "Be the first to share!"
- **Evidence Required:** Screenshots: community tab sections, post upload flow, leaderboard, empty state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** ND.02 (design system), ND.06 (home chef marketplace for chef spotlights)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.004 — Hyper-Local Micro-Marketplaces
- **Category:** Backend + Frontend
- **Implementation Scope:** Add `users.building_name` VARCHAR. Build `GET /api/v1/restaurants/building-top-picks?building={name}` endpoint: aggregates top 5 restaurants by order count from users in the same building. Add `<BuildingSection />` to homepage: shown only if `building_name` is set. "Start Building Group Order" button generates a building-scoped group order link. Modify group order logic to accept `building_name` filter for join eligibility. Add "Drop at Reception" delivery instruction preset for users with building name. Tag order `concierge_drop = true`. Show tag in driver view.
- **Acceptance Criteria:**
  1. Homepage shows "Top Picks in {building}" when user has building_name set.
  2. Building group order link only allows same-building users to join.
  3. Delivery instruction includes "Drop at reception of {building}" option.
  4. Driver sees concierge drop tag on assigned order.
  5. Section hidden if no building name or no data.
- **Evidence Required:** Screenshots: building section, group order flow, delivery instruction, driver view tag.
- **Priority:** P1
- **Effort:** S
- **Dependency:** ND.06 (group ordering), PR.05 (checkout)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.005 — Sustainability Ecosystem Full
- **Category:** Backend + Frontend
- **Implementation Scope:** Extend `orders` table: `green_delivery` BOOLEAN, `carbon_g` INT, `offset_amount` DECIMAL, `concierge_drop` BOOLEAN. Add carbon calculation helper: `distance_km × emissions_factor × (is_batched ? 0.6 : 1.0)`. Factors: bicycle=0, e-scooter=20, petrol=80 g/km. Show `<CarbonReportCard />` in profile: monthly CO₂ total, savings from eco delivery, car-distance equivalent. `<GreenDeliveryToggle />` at checkout for <2km orders. If selected, assign to bicycle rider, award +10 loyalty points. `<OffsetToggle />` at checkout: auto-compute ₹0.05 per 100g CO₂. Store `users.auto_offset` preference. Bicycle rider badge shown on driver profile after 50 green deliveries.
- **Acceptance Criteria:**
  1. Order confirmation shows estimated CO₂ generated.
  2. Green delivery option appears only for orders <2km.
  3. Monthly carbon report shows accurate totals and savings.
  4. Offset toggle adds calculated amount to order total.
  5. Bicycle rider badge appears after 50 green deliveries.
- **Evidence Required:** Screenshots: order confirmation carbon badge, checkout green toggle, monthly report, driver badge.
- **Priority:** P0
- **Effort:** M
- **Dependency:** ND.06 (sustainability score), PR.05 (checkout)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.006 — Family Plans
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Create `family_groups` and `family_members` tables. Build endpoints: `POST /api/v1/family` (create), `POST /api/v1/family/join` (join via code), `GET /api/v1/family`, `PATCH /api/v1/family/members/{id}/limits`. Frontend: `<FamilyPlanManager />` in profile for creating, inviting, and managing members. `<KidsModeToggle />` with PIN entry (hashed server-side). `<KidsModeLayout />` wrapper: large buttons, emoji icons, approved restaurants only, abstracted prices ("Coins"). Checkout enforces spending limit and approved restaurant list server-side.
- **Acceptance Criteria:**
  1. Parent can create family and invite up to 4 members.
  2. Member join works via 6-character invite code.
  3. Spending limit blocks checkout if exceeded.
  4. Unapproved restaurant blocks checkout with clear message.
  5. Kids mode requires PIN to exit and shows simplified UI.
- **Evidence Required:** Screenshots: family creation, invite flow, member list, kids mode UI, blocked checkout message.
- **Priority:** P1
- **Effort:** M
- **Dependency:** PR.05 (checkout), ND.02 (design system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.007 — Health Integration
- **Category:** Frontend
- **Implementation Scope:** Build `<HealthConnectButton />` for Apple Health (iOS) and Google Fit (Android). Request read permissions for active calories burned. Store connection status and daily calorie budget in `healthStore` (Zustand), persisted locally. `<HealthBanner />` on homepage: if burned > 300 cal, show "You've been active — treat yourself!"; if low remaining budget, suggest "Light & Fresh" filter. "Light & Fresh" filter badge surfaced on restaurant list based on `calorie_budget_remaining`. Web fallback: manual input form for daily calories burned and consumed.
- **Acceptance Criteria:**
  1. Health connect button requests permissions on iOS/Android.
  2. Homepage banner shows activity-based message when connected.
  3. "Light & Fresh" filter suggested when remaining budget is low.
  4. Manual input fallback works when platform connection is unavailable.
  5. Health data is not sent to backend without explicit opt-in.
- **Evidence Required:** Screenshots: health connect UI, homepage banner, manual input fallback, light filter.
- **Priority:** P2
- **Effort:** S
- **Dependency:** ND.06 (nutrition panel with calorie data)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Health APIs require platform permissions; mockable)

### IP.ND.10.008 — AR Menu Preview (Lightweight)
- **Category:** Frontend
- **Implementation Scope:** On menu item detail, add "AR Preview" button. Opens `<AROverlay />` component: `<video>` element from `getUserMedia` with an overlaid `<img>` (transparent PNG plate sized proportionally to dish). Text overlay shows portion info (e.g., "Serves 2", "8-inch diameter"). Close button exits. If camera denied or unsupported, fallback to static modal with same plate image on transparent background. No 3D models, no depth sensing.
- **Acceptance Criteria:**
  1. AR Preview button visible on menu item detail.
  2. Camera feed opens with plate overlay on supported devices.
  3. Text overlay shows accurate serving size info.
  4. Fallback modal works when camera is unavailable.
  5. Component is dismissed by tapping close or outside area.
- **Evidence Required:** Screen recording: tap AR → camera opens → plate overlay → close. Screenshot of fallback modal.
- **Priority:** P2
- **Effort:** S
- **Dependency:** ND.06 (menu items with portion data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.009 — Smartwatch Companion
- **Category:** Frontend + Backend
- **Implementation Scope:** Build a watch-optimized web view or PWA. `GET /api/v1/orders/last` returns most recent order summary. Screen: order status with emoji steps (Confirmed → Preparing → Out → Delivered). "Reorder Last Meal" button triggers same API as smart reorder. Backend: extend existing order status endpoint to support lightweight watch response (minimal fields). For demo, provide mock watch UI screenshots in browser developer tools with device emulation (Apple Watch 44mm / Wear OS round).
- **Acceptance Criteria:**
  1. Watch UI shows current order status with 4-step emoji timeline.
  2. "Reorder Last Meal" places the same order with one tap.
  3. UI fits 44mm Apple Watch and round Wear OS screens.
  4. No errors on slow network (minimal payload).
  5. Demo accessible via browser device emulation.
- **Evidence Required:** Screenshots: watch status screen, reorder confirmation, browser devtools emulation.
- **Priority:** P2
- **Effort:** S
- **Dependency:** ND.05 (smart reorder), PR.05 (order status)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.010 — Influencer / Food Blogger Integration
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Extend `users` table with `role` and `verified_badge`. Create `blogger_recommendations` and `collaboration_items` tables. Endpoints: `GET /api/v1/bloggers`, `GET /api/v1/bloggers/{id}/recommendations`, `POST /api/v1/restaurants/{id}/collaborations` (restaurant owner only). Frontend: `<BloggerBadge />` on menu items ("Recommended by {name}"). `<BloggerProfileCard />` on community tab. Collaboration items show purple "Collaboration" badge. Admin dashboard can grant blogger role and verify badges.
- **Acceptance Criteria:**
  1. Verified blogger profile shows badge, bio, and recommendations.
  2. Menu items display "Recommended by {blogger}" badge where applicable.
  3. Collaboration items show purple badge and blogger attribution.
  4. Restaurant owner can create collaboration items.
  5. Max 5 active recommendations per blogger enforced.
- **Evidence Required:** Screenshots: blogger profile, menu badge, collaboration item, admin verification UI.
- **Priority:** P2
- **Effort:** S
- **Dependency:** ND.02 (design system), ND.10.003 (community tab)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.ND.10.011 — Seed Data for Category-Leading Demo
- **Category:** Data
- **Implementation Scope:** Populate all seed data required for ND.10:
  1. 2-3 verified blogger users with bios, follower counts, and 3-5 recommendations each.
  2. 5-10 community posts with realistic captions, image URLs, restaurant/item tags.
  3. 1 demo family group with admin + 1 teen member, spending limit ₹800/week, 5 approved restaurants.
  4. Emissions factors in app config: bicycle=0, e-scooter=20, petrol=80 g/km.
  5. Predictive patterns: 5+ orders for a demo user at same restaurant/day/time (e.g., every Thursday 1 PM from Spice Garden).
  6. Building name set for 2-3 demo users (e.g., "Sunrise Apartments").
  7. Collaboration items: 2-3 "{Blogger} Special" dishes at restaurants.
  8. Green delivery rider user with 50+ completed green deliveries.
- **Acceptance Criteria:**
  1. Bloggers have verified badges and active recommendations.
  2. Community feed has >=5 posts on fresh seed.
  3. Family plan demo is fully functional with limits.
  4. Predictive banner appears for demo user on matching day/time.
  5. Building top-picks section shows data for seeded buildings.
- **Evidence Required:** DB query outputs for all new tables. Screenshot of seeded demo state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Predictive ordering banner appears for users with >=3 matching pattern orders and allows one-tap approve with cancelable countdown.
- [ ] Voice ordering button is visible on supported browsers, parses spoken orders with >=80% confidence, and shows confirmation before adding to cart.
- [ ] Community tab has Events, Chef Spotlight, Photo Feed, and Leaderboard sections. Users can post photos with captions and tags.
- [ ] Building-specific top picks section appears on homepage when `building_name` is set. Building group orders restrict join to same-building users.
- [ ] Green delivery option appears for orders <2km. Order confirmation shows carbon footprint. Monthly carbon report is visible in profile.
- [ ] Carbon offset toggle adds computed amount to checkout. Auto-offset preference persists across orders.
- [ ] Family plan supports creation, invite via code, up to 5 members, spending limits, approved restaurant lists, and kids mode with PIN exit.
- [ ] Kids mode displays simplified UI with large buttons, emoji icons, and approved restaurants only.
- [ ] Health integration banner appears on homepage based on connected platform data or manual input. "Light & Fresh" filter suggested when calorie budget is low.
- [ ] AR preview opens camera overlay with portion-size plate image and serving info. Fallback modal works when camera is unavailable.
- [ ] Smartwatch UI shows order status timeline and one-tap reorder. Demo accessible via browser device emulation.
- [ ] Verified blogger profiles display recommendations. Menu items show "Recommended by {blogger}" badge. Collaboration items show purple badge.
- [ ] All new UI follows BhojanGo design system, responsive, dark mode compatible.
- [ ] Seed data fully supports category-leading demo (bloggers, community posts, family plan, predictive patterns, building names, green rider).

## 17. Evidence Required

- Screenshots:
  - Predictive order banner with approve/decline buttons and item list.
  - 3-second countdown modal before order placement.
  - Voice ordering: mic button, listening state, confirmation modal, disambiguation modal.
  - Community tab: all four sections (events, chef spotlight, feed, leaderboard).
  - Community post upload flow with image, caption, tag selection.
  - Building section on homepage with "Top Picks in Sunrise Apartments."
  - Green delivery toggle at checkout, order confirmation carbon badge.
  - Monthly carbon report in profile.
  - Family plan creation, invite code, member list.
  - Kids mode UI with large buttons and simplified layout.
  - Blocked checkout: spending limit exceeded and unapproved restaurant.
  - Health banner: "You've been active today — treat yourself!"
  - AR preview: camera overlay with plate and serving text.
  - AR fallback modal when camera denied.
  - Smartwatch UI: status timeline and reorder button (browser emulation).
  - Blogger profile, menu recommendation badge, collaboration item badge.
- Screen recordings:
  - Predictive order: open app → banner appears → approve → countdown → confirmation.
  - Voice order: tap mic → speak → parse → confirm → cart updated.
  - Community post: tap share → upload → caption → tag → post appears in feed.
  - Family plan: create → invite → member joins → set limit → member orders.
- API evidence:
  - `curl` output for `GET /api/v1/users/{id}/predictive-order`.
  - `curl` output for `POST /api/v1/voice/parse` with sample transcripts.
  - `curl` output for `GET /api/v1/community/feed`.
  - `curl` output for `GET /api/v1/community/leaderboard`.
  - `curl` output for `GET /api/v1/restaurants/building-top-picks`.
  - `curl` output for `GET /api/v1/family`.
  - `curl` output for `GET /api/v1/bloggers`.
  - `curl` output for `GET /api/v1/orders/last`.
- DB evidence:
  - Query results confirming `family_groups`, `family_members`, `community_posts`, `blogger_recommendations`, `collaboration_items` tables exist and are seeded.
  - Query results confirming `orders.green_delivery`, `orders.carbon_g`, `orders.offset_amount` are populated.
  - Query results confirming demo users have `building_name` and predictive patterns.

## 18. Dependencies

### External Tools
- PostgreSQL (for new tables: family_groups, family_members, community_posts, blogger_recommendations, collaboration_items).
- Node.js + pnpm (frontend build).
- Lucide React (icon library).
- Web Speech API (Chrome/Edge browser support for voice ordering).
- getUserMedia API (camera access for AR preview).
- Apple HealthKit / Google Fit APIs (optional, with mock fallback).
- Browser developer tools device emulation (for smartwatch demo).

### Internal Dependencies
- **PR.05 or PR.06 must be complete:** Stable core ordering loop is prerequisite.
- **ND.02 (Distinctive Visual Identity) must be complete:** Design system applied.
- **ND.03 (Small Convenience Features) must be complete:** Filters, restaurant cards, menu discovery.
- **ND.05 (Retention-Focused Uniqueness) must be complete:** Favorites, loyalty, smart reorder, saved preferences.
- **ND.06 (Marketplace-Specific Differentiation) must be complete:** Group ordering, nutrition panel, sustainability score, home chefs.
- **ND.07 (Smart Personalization) must be complete:** Order stats, recommendation engine, time-aware sections, cross-sell.
- **Auth persistence** must work for all user-scoped features (predictive, family, community, health).
- **Order history** must have 4+ weeks of data for predictive ordering.
- **Cart Zustand store** must support programmatic addition (voice, predictive, watch reorder).
- **Checkout** must support green delivery toggle, offset line item, and family validation.
- **Order status pipeline** must be functional for smartwatch glance.
- **Address lat/lng** must be stored for carbon distance calculation.

## 19. Risks / Blockers

- **Predictive ordering spam:** If predictions are wrong or too frequent, users feel harassed. Mitigation: require >=3 pattern occurrences, 15-minute pre-window only, 7-day suppression on decline, never more than 1 prediction per day.
- **Voice ordering accuracy:** Fuzzy matching on Indian food names with accents can fail. Mitigation: disambiguation modal for <80% confidence, fallback to typing, seed with phonetic variants.
- **Web Speech API compatibility:** Firefox and some mobile browsers do not support `SpeechRecognition`. Mitigation: feature-detect and hide button. Document Chrome/Edge as demo browsers.
- **Camera permission denial:** Users may deny camera for AR. Mitigation: static fallback modal is always available and provides the same info.
- **Health data privacy:** Users may be uncomfortable connecting health apps. Mitigation: entirely optional, local-only storage by default, explicit opt-in for any backend transmission, manual input fallback.
- **Family plan complexity:** Parental controls add checkout friction. Mitigation: server-side enforcement is fast (<5ms). Clear error messages guide the user.
- **Community moderation:** UGC can contain inappropriate content. Mitigation: auto-approve for demo. In production, add image moderation API and keyword filter.
- **Green delivery rider availability:** Bicycle riders may not be available for all <2km orders. Mitigation: if no bicycle rider is online, hide the green option or show "Unavailable now — try again later."
- **Carbon calculation accuracy:** Emissions factors are estimates. Mitigation: clearly label as "estimated." Use conservative factors. Do not claim third-party verification.
- **Smartwatch scope:** Native watch apps are expensive to build. Mitigation: watch-optimized web view is demo-safe and proves the concept.

## 20. Exit Criteria

- All P0 work items (IP.ND.10.001, IP.ND.10.002, IP.ND.10.003, IP.ND.10.005, IP.ND.10.011) implemented and verified.
- All P1 work items (IP.ND.10.004, IP.ND.10.006) implemented and verified.
- All P2 work items (IP.ND.10.007, IP.ND.10.008, IP.ND.10.009, IP.ND.10.010) implemented and verified.
- Predictive ordering: banner appears, approve places order, decline suppresses, countdown works.
- Voice ordering: mic button, parse, confirmation, disambiguation, cart update all functional.
- Community tab: all sections visible, posting works, leaderboard populated.
- Hyper-local: building section visible, group order scoped, concierge drop tagged.
- Sustainability: carbon calculation, green toggle, monthly report, offset toggle, bicycle badge all functional.
- Family plan: creation, invite, limits, approved restaurants, kids mode all functional.
- Health integration: banner displays, filter suggests, manual fallback works.
- AR preview: camera overlay or fallback modal works.
- Smartwatch: status timeline and reorder visible in demo.
- Influencer: blogger profiles, recommendation badges, collaboration items visible.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.10 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.09)

ND.10 directly depends on ND.09 achievements:
- **ND.09 Defensible Differentiation:** Group carts, meal rescue, loyalty tiers, restaurant insights, delivery confidence, and customer trust loops provide the operational foundation. Predictive ordering relies on stable order history and trust.
- **ND.08 Strong Product Identity:** Tailored UI, trust system, freshness/speed cues, smart bundles, and contextual deals are assumed operational. Community tab and influencer integration extend the product identity into social proof.
- **ND.07 Smart Personalization:** Rule-based recommendations, cross-sell, time-aware sections, and order pattern detection are prerequisites for predictive ordering and health-aware suggestions.
- **ND.06 Marketplace-Specific Differentiation:** Group ordering, nutrition panel, sustainability score, and home chefs provide the data and UI patterns for family plans, hyper-local marketplaces, and eco features.
- **ND.05 Retention-Focused Uniqueness:** Favorites, smart reorder, loyalty, and saved preferences are the data inputs for predictive ordering and personalized community content.
- **PR.05/PR.06 Production Readiness:** Stable checkout, order status, and auth are required for every ND.10 feature.

## 22. Connected Next-Level Requirements (link to Post-ND.10)

ND.10 is the final novelty score. Beyond ND.10, work shifts from differentiation to:
- **Operational scale:** Multi-city expansion, real driver fleet, restaurant acquisition.
- **ML enhancement:** Replace rule-based scoring with trained models as data volume grows.
- **Platform partnerships:** Real Apple Health / Google Fit deep linking, real carbon offset APIs (e.g., Cloverly, Patch), real smartwatch app store submissions.
- **Hardware integration:** IoT temperature sensors, smart locker mesh, dual-compartment thermal bags.
- **Regulatory compliance:** Food safety certifications, FSSAI integration, data privacy audits (GDPR, DPDP).
- **Monetization:** Restaurant subscription tiers, featured placement, influencer marketplace revenue share.

ND.10 is complete when the app is a **category-leading experience** — not a clone, not a gimmick, but a thoughtfully differentiated product that users choose because it genuinely serves them better.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (10/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.09 + prior) described | Planner | ✅ |
| 4 | Target state (ND.10 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.10 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.10 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (10 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (5 new tables, extended users + orders) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why ND.10 creates category-leading differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.10.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: predictive ordering, voice ordering, community tab, hyper-local, sustainability, family plans, health, AR, smartwatch, influencer | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks/Blockers mention spam, accuracy, compatibility, privacy, moderation, rider availability | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.09) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (Post-ND.10) requirements listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all 10 required features: predictive ordering, voice ordering, community tab, hyper-local micro-marketplaces, sustainability ecosystem, family plans, health integration, AR menu preview, smartwatch companion, and influencer integration.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in the lightweight/demo-safe approach: no external AI APIs, no native watch store submission, no real carbon payments, no heavy ML.
- Scope is strictly LOCAL/DEMO-SAFE for 9/10 features. Health integration is marked OPTIONAL EXTERNAL but has a full mock fallback.
- Score kept at 10/10 as instructed. Self-score of the document quality is 9/10 due to the aspirational nature of some features (smartwatch, AR) which are implemented as lightweight mocks rather than full native integrations — appropriate for a demo-safe planning document.
