# IP.PR.10 — Mature Marketplace Platform

## 1. Target Score Level: 10/10

## 2. Score Meaning

Product is stable, trusted, distinctive, operationally manageable, scalable, and strong enough to compete with serious food-delivery platforms. AI-driven personalization, predictive logistics, deep ecosystem integrations (B2B, franchise, community kitchens), and sustainability positioning create genuine defensibility. The app feels like a category-leading experience — not a clone — with memorable differentiation in personalization, operational intelligence, environmental consciousness, and marketplace breadth.

## 3. Current → Target Transition

**From PR.09 (production-grade with real providers, observability, CI/CD, group ordering):**
- Real Stripe/Razorpay webhooks process payments end-to-end.
- FCM push notifications, SendGrid email, and Twilio SMS are wired to event bus.
- CI/CD pipeline with path-based detection, security scanning, and automated tests.
- Prometheus + Grafana observability dashboard with per-service metrics.
- Centralized logging (Loki) and distributed tracing (Jaeger) with correlation IDs.
- Group ordering with shareable links and split payment works.
- Loyalty points are earned but basic; no tier system or redemption UI.
- Meal rescue / end-of-day deals exist but are manual.
- Onboarding wizard post-signup is functional.
- Real-time driver tracking with Mapbox/Leaflet is live.
- CDN/S3 image pipeline with WebP generation is operational.
- Dark mode toggle, onboarding wizard, and advanced search are live.
- Core customer loop and three-sided marketplace are fully operational.

**Target at score 10:**
- AI-driven meal recommendations on homepage and post-order, using collaborative filtering (ALS/matrix factorization) with numpy/scikit-learn. Personalized by time of day, weather, cuisine affinity, and order history.
- Predictive prep-time ML model using historical data achieves ±5 min accuracy.
- Demand forecasting predicts hourly order volume per restaurant, helping owners prep ingredients.
- Full loyalty + gamification program: points earning, tier system (Bronze/Silver/Gold/Platinum), level-up badges, rewards redemption (free delivery, discounts), progress dashboard.
- Meal rescue / end-of-day flash sales: automated 1h-before-close discount on unsold inventory. Push/email notification to nearby users.
- Community kitchen / home chef marketplace: separate onboarding flow for home chefs, lower commission, separate listing section, basic KYC (identity verification, food safety certificate upload).
- Smart locker network: partner with co-working spaces/apartment complexes. Generate QR code. Temperature-controlled locker simulation. Pickup flow.
- Nutritional transparency: full macros, allergens, calories on every item. Health score. Filter by dietary goals (keto, vegan, high-protein).
- Office lunch program (B2B): corporate accounts, bulk ordering, invoicing, scheduled recurring orders, expense management integration.
- Franchise management: white-label multi-tenant dashboard. Each franchisee sees their own restaurants. Central admin sees all.
- Advanced batch engine: ML-based route optimization (OR-Tools), dynamic batching based on real-time demand, predictive ETAs per stop.
- Sustainability program: carbon offset calculation per delivery. Green badge for eco-friendly restaurants. Biodegradable packaging verified.
- Full multi-language: Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, Gujarati, plus English.
- Advanced analytics: cohort analysis, LTV prediction, churn prediction, NPS trending.
- A/B testing framework: feature flags, experiment tracking, conversion metrics.
- Voice ordering: Web Speech API + rule-based NLP. "Order 2 Paneer Tikka and 1 Naan from Spice Garden."

## 4. Implementation Objective

Add AI-driven personalization, advanced operational tools, franchise/white-label capabilities, and deep ecosystem integrations. Make the product meaningfully different from generic food delivery clones. Achieve category-leading experience through operational intelligence (predictive prep time, demand forecasting, ML routing), personalization (AI recommendations, voice ordering), marketplace breadth (community kitchens, B2B, smart lockers), and values alignment (sustainability, nutritional transparency, multi-language inclusivity). The goal is structural differentiation: features that create virtuous cycles (better recommendations → more orders → better data → better recommendations) and operational moats (demand forecasting → lower waste → better margins → competitive pricing).

## 5. Scope

### In Scope

1. **AI meal recommendations engine:**
   - Collaborative filtering using ALS (Alternating Least Squares) or matrix factorization via `implicit` library or scikit-learn `NMF`.
   - Feature engineering: order history (item frequency, cuisine preference, price band), time of day (morning/afternoon/evening/night affinity), day of week, weather API integration (rainy → soup/biryani affinity), veg/non-veg preference.
   - Build user-item interaction matrix from `orders.items` JSONB + `menu_items` cuisine tags.
   - Train model offline (batch job) every 6 hours. Store user embeddings and item embeddings in Redis or PostgreSQL `user_recommendations` table.
   - Inference: `GET /api/v1/recommendations/personalized` returns top-10 items with explanation ("Because you ordered North Indian last week").
   - Homepage "For You" section and post-order "Order Again" + "You Might Like" carousels.
   - Cold-start handling: new users see trending items + cuisine preference from onboarding.
   - No external AI service required — built entirely with numpy/scikit-learn/implicit.

2. **Predictive prep-time ML:**
   - Feature extraction: restaurant `avg_prep_minutes`, current queue size, time of day (rush hour vs. off-peak), day of week (weekend vs. weekday), item complexity (number of items, customizations), historical actual prep time vs. estimated.
   - Model: scikit-learn `RandomForestRegressor` or `GradientBoostingRegressor`.
   - Training data: `order_status_history` with `changed_at` timestamps for `confirmed` → `ready_for_pickup` intervals.
   - Target accuracy: ±5 minutes for 80% of predictions.
   - Endpoint: `GET /api/v1/restaurants/{id}/predicted-prep-time` returns `{estimated_minutes, confidence_interval, factors}`.
   - Used in checkout ETA calculation and restaurant dashboard.

3. **Demand forecasting:**
   - Predict hourly order volume per restaurant for next 24h and next 7 days.
   - Features: historical order counts by hour/day, seasonality, local events (weekend, holidays), weather, marketing campaigns.
   - Model: scikit-learn `RandomForestRegressor` or `Prophet` (lightweight time-series).
   - Endpoint: `GET /api/v1/restaurants/{id}/demand-forecast` returns hourly predictions.
   - Restaurant dashboard shows forecast chart with recommended prep quantities.
   - Helps owners reduce waste and stockouts.

4. **Loyalty + gamification full program:**
   - Points earning: 10 points per ₹100 spent (or $1 spent). Bonus points for first order, review submission, referral.
   - Tier system: Bronze (0-999 pts), Silver (1000-4999), Gold (5000-9999), Platinum (10000+).
   - Tier benefits: Bronze = base; Silver = 5% discount; Gold = free delivery + 10% discount; Platinum = priority support + 15% discount + exclusive deals.
   - Badges: "First Bite" (first order), "Explorer" (order from 5 cuisines), "Regular" (5 orders), "Feast Master" (20 orders), "Reviewer" (3 reviews), "Eco Warrior" (10 batched orders).
   - Rewards redemption UI in wallet page: redeem points for free delivery (500 pts), ₹50 off (300 pts), ₹100 off (500 pts).
   - Level-up animation when tier changes.
   - Backend: `user_loyalty` table with `tier`, `total_points`, `lifetime_points`. `user_badges` table with `badge_type`, `awarded_at`.

5. **Meal rescue / end-of-day flash sales:**
   - Cron job runs every 15 minutes. Identifies restaurants closing within 1 hour with unsold inventory (menu items with high stock count and low sales).
   - Automatically creates "Rescue Meal" offer: 30-50% off select items.
   - Push notification + email to users within 3km: "Spice Garden has 5 Paneer Tikka meals at 50% off — 45 min left!"
   - Frontend: "Flash Deals" carousel on homepage. Countdown timer.
   - Backend: `flash_sales` table with `restaurant_id`, `menu_item_id`, `discount_percent`, `starts_at`, `ends_at`, `max_quantity`, `sold_count`.
   - Integrates with batch engine for efficient last-mile delivery.

6. **Community kitchen / home chef marketplace:**
   - Separate onboarding flow: `POST /api/v1/home-chefs/register` with KYC fields.
   - Required uploads: government ID (Aadhaar/PAN), food safety certificate (FSSAI), kitchen photo.
   - Lower commission: 10% vs. 20% for commercial restaurants.
   - Separate listing section: "Home Chefs Near You" on homepage and dedicated `/home-chefs` page.
   - Menu items tagged `source: home_chef`. Profile shows chef story, specialties, hygiene badge.
   - Backend: `home_chefs` table with `user_id`, `verification_status`, `commission_rate`, `kitchen_photo_url`, `bio`. Extends `restaurants` table with `type: commercial | home_chef`.
   - Ratings and reviews work same as commercial restaurants.

7. **Smart locker network:**
   - `smart_lockers` table: `id`, `name`, `location_address`, `lat`, `lng`, `partner_type` (coworking/apartment/office), `total_compartments`, `available_compartments`, `temperature_controlled` (bool).
   - At checkout, user selects "Pickup at Smart Locker" and chooses nearest locker from map/list.
   - On order ready, system assigns compartment, generates QR code (`uuid`), sends to user via push/email.
   - User scans QR at locker (simulated: enter code in app to "unlock"). Compartment marked available after 30 min pickup window.
   - Frontend: locker selector component, QR code display page, pickup confirmation.
   - Backend: `locker_assignments` table with `order_id`, `locker_id`, `compartment_number`, `qr_code`, `expires_at`, `picked_up_at`.
   - Simulation mode for demo: no real hardware required.

8. **Nutritional transparency:**
   - Add columns to `menu_items`: `calories`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `allergens` (JSONB array: `["nuts", "dairy", "gluten"]`), `dietary_tags` (JSONB array: `["keto", "vegan", "high-protein", "gluten-free"]`).
   - Health score: algorithm based on calorie density, protein ratio, fiber content (0-100 scale).
   - Frontend: collapsible nutrition panel on every menu item. Macro breakdown bar chart (protein/carbs/fats). Allergen warning icons.
   - Filter chips on restaurant detail: "Keto", "Vegan", "High Protein", "Under 500 cal", "Gluten-Free".
   - Backend migration for all existing menu items (seed data or manual entry). Admin dashboard allows editing nutritional info.

9. **Office lunch program (B2B):**
   - Corporate account entity: `corporate_accounts` table with `company_name`, `tax_id`, `billing_address`, `admin_user_id`, `credit_limit`, `payment_terms`.
   - Bulk ordering: corporate admin selects restaurant, sets budget per person, invites employees to add items.
   - Scheduled recurring orders: "Every Monday-Friday at 12:30 PM from Spice Garden for 25 people."
   - Invoicing: monthly invoice generated with itemized breakdown. PDF generation (weasyprint or similar).
   - Expense management integration: export to CSV (QuickBooks, SAP Concur format).
   - Employee portal: employees see day's lunch menu, add preferences, dietary restrictions auto-filtered.
   - Backend: `corporate_orders` table, `corporate_order_items`, `invoices` table.

10. **Franchise management / white-label:**
    - Multi-tenant architecture: `franchises` table with `id`, `name`, `subdomain`, `theme_config` (JSONB: primary_color, logo_url).
    - Franchisee dashboard: sees only their assigned restaurants, orders, drivers, revenue. Logos and colors reflect their brand.
    - Central admin dashboard: sees all franchises, aggregated KPIs, cross-franchise analytics.
    - Tenant isolation enforced at middleware level: `X-Franchise-ID` header or JWT claim `franchise_id`.
    - White-label API: `GET /api/v1/franchise/config` returns theme, colors, logo for dynamic frontend theming.
    - Franchise onboarding wizard: create franchise → add restaurants → invite staff.
    - At scale, this requires row-level security or schema-per-tenant. For demo: schema-level filtering with `franchise_id` column on restaurants table.

11. **Advanced batch engine ML routing:**
    - Replace heuristic scoring with ML-based composite score.
    - OR-Tools integration: use Google OR-Tools `routing` library for vehicle routing problem (VRP) with time windows.
    - Features: real-time traffic (mock/simulated), driver capacity, pickup time windows, dropoff time windows, batch size limit.
    - Dynamic batching: instead of fixed 30s cycle, batch formation triggered by demand threshold (e.g., 3+ orders in pool within 5 min) or time trigger (whichever comes first).
    - Predictive ETAs per stop: ML model estimates arrival time at each pickup/dropoff with confidence intervals.
    - Backend: new TypeScript module `ml-scorer.ts` and `ort-router.ts`. Train model on historical batch data (delivery times, distances, order counts).

12. **Sustainability program:**
    - Carbon offset calculation: per delivery, estimate grams of CO₂ based on distance, vehicle type (bike/scooter/car), and batching savings.
    - Formula: `gCO₂ = distance_km × emission_factor_g_per_km × (1 - batch_savings_percent)`.
    - Green badge for restaurants: `is_eco_friendly` flag + `packaging_type` (biodegradable/compostable/plastic). FSSAI + eco badge shown together.
    - Customer-facing: order confirmation shows "You saved 120g CO₂ by choosing batched delivery." Wallet shows total CO₂ saved, trees planted equivalent.
    - Eco leaderboard: "Top 10 eco-conscious customers this month."
    - Backend: `restaurant_sustainability` table with `carbon_offset_g`, `packaging_type`, `certified_by`. `user_eco_stats` table.

13. **Full multi-language support:**
    - Add 7 Indian languages: Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn), Marathi (mr), Bengali (bn), Gujarati (gu) + English (en).
    - `messages/{locale}.json` for each language in `apps/web` and `apps/mobile`.
    - Admin dashboard for translating UI strings: key-value editor with approval workflow.
    - Restaurant menu translation: `menu_item_translations` table with `menu_item_id`, `locale`, `name`, `description`.
    - Automatic machine translation fallback: integrate Google Cloud Translation API (optional, 🟡) or LibreTranslate (self-hosted, 🟢) for menu item descriptions.
    - Language detection based on device/browser settings. Language switcher in navbar/footer.
    - RTL support not required (all target languages are LTR).

14. **Advanced analytics:**
    - Cohort analysis: group users by first-order month, track retention rates (1-month, 3-month, 6-month) for each cohort.
    - LTV prediction: regression model predicting customer lifetime value based on order frequency, AOV, tenure.
    - Churn prediction: classification model flagging users at risk of churning (no order in 30 days, declining order frequency).
    - NPS trending: Net Promoter Score survey after delivery. Track NPS over time, by restaurant, by driver.
    - Admin dashboard: cohort retention heatmap, LTV distribution histogram, churn risk list, NPS line chart.
    - Backend: `user_cohorts`, `ltv_predictions`, `churn_predictions`, `nps_surveys` tables.

15. **A/B testing framework:**
    - Feature flags: `feature_flags` table with `name`, `enabled`, `target_percentage`, `target_segments` (JSONB).
    - Experiment tracking: `experiments` table with `name`, `variant_a` (control), `variant_b` (treatment), `start_date`, `end_date`, `success_metric`.
    - Assignment: user hash-based bucketing (consistent hash of user_id + experiment_name) to ensure same user always sees same variant.
    - Conversion metrics: track per-experiment conversions (order placed, AOV, retention).
    - Frontend: `useFeatureFlag('new_homepage_carousel')` hook. `useExperiment('checkout_flow_v2')` hook returning variant.
    - Admin dashboard: create experiment, view real-time results (conversion rate, statistical significance).

16. **Voice ordering:**
    - Web Speech API (`SpeechRecognition`) on mobile and desktop web.
    - Rule-based NLP parser: tokenizes transcript, extracts quantity, item name, restaurant name.
    - Example: "Order 2 Paneer Tikka and 1 Naan from Spice Garden" → `{items: [{qty: 2, name: "Paneer Tikka"}, {qty: 1, name: "Naan"}], restaurant: "Spice Garden"}`.
    - Fuzzy matching: item names matched against menu using Levenshtein distance or trigram similarity.
    - Frontend: floating mic button on homepage and restaurant detail. Voice wave animation while listening. Transcript displayed for confirmation.
    - Backend: `POST /api/v1/voice/parse` accepts transcript, returns structured order intent.
    - Confirmation step: user reviews parsed order before adding to cart (don't auto-add without confirmation).
    - Accessibility: voice ordering helps users with motor disabilities.

### Out of Scope

- Blockchain / carbon-neutral delivery verification (⚫ DO NOT IMPLEMENT NOW — overkill for current stage).
- Full autonomous delivery drones (⚫ DO NOT IMPLEMENT NOW — regulatory and hardware complexity).
- AR/VR dining experience (⚫ DO NOT IMPLEMENT NOW — gimmick, not core marketplace value).
- Real-time traffic data via paid Google Routes API (deferred to scale phase — use simulated traffic for demo).
- True multi-region deployment (deferred — keep single-region for demo).
- 3D Secure / SCA full compliance (keep basic webhook handling as-is).
- Real IoT smart locker hardware integration (simulation only for demo).

## 6. Out of Scope (Summary)

- Blockchain / carbon-neutral delivery verification.
- Autonomous delivery drones.
- AR/VR dining experience.
- Paid Google Routes API for real-time traffic.
- Multi-region deployment.
- Full 3D Secure/SCA compliance.
- Real IoT smart locker hardware.

## 7. Required Capabilities

- AI recommendations engine: Collaborative filtering (ALS/matrix factorization) trained on order history. Inference <100ms via Redis-stored embeddings. Cold-start fallback to trending. Homepage + post-order personalization.
- Predictive prep-time ML: RandomForest/GradientBoosting on historical `confirmed` → `ready_for_pickup` intervals. ±5 min accuracy for 80% of predictions. Real-time inference on checkout.
- Demand forecasting: Hourly order volume prediction per restaurant for next 24h/7d. Prophet or RandomForest. Visualized in restaurant dashboard with prep recommendations.
- Loyalty + gamification: Tiered system (Bronze/Silver/Gold/Platinum) with escalating benefits. Badge system with level-up animations. Point redemption at checkout. Progress dashboard.
- Meal rescue flash sales: Automated cron job detects closing-soon + unsold inventory. Creates time-bound discount offers. Push/email to nearby users. Countdown UI.
- Community kitchen marketplace: Separate KYC onboarding for home chefs. Lower commission (10%). Separate listing section. Identity verification + food safety certificate upload.
- Smart locker network: Locker directory with geo search. QR code generation for pickup. Compartment assignment simulation. Temperature-controlled flag.
- Nutritional transparency: Full macro breakdown (calories, protein, carbs, fat, fiber) per item. Allergen warnings. Dietary filter chips. Health score (0-100).
- Office lunch B2B: Corporate accounts with billing/tax details. Bulk ordering with per-employee selection. Recurring scheduled orders. Monthly invoicing (PDF). Expense export (CSV).
- Franchise management: Multi-tenant dashboard with `franchise_id` isolation. White-label theming (colors, logo). Central admin oversight. Franchise onboarding wizard.
- Advanced batch engine ML routing: OR-Tools VRP solver. ML-based composite scoring. Dynamic batching trigger (demand threshold + time). Predictive ETAs per stop.
- Sustainability program: CO₂ calculation per delivery. Green badge for eco-friendly restaurants. Biodegradable packaging flag. Customer eco stats + leaderboard.
- Full multi-language: 8 locales (en + 7 Indian languages). JSON message files. Menu item translations. Machine translation fallback.
- Advanced analytics: Cohort retention analysis. LTV prediction. Churn prediction. NPS surveys and trending.
- A/B testing framework: Feature flags with percentage rollouts. Experiment tracking with hash-based variant assignment. Real-time conversion metrics dashboard.
- Voice ordering: Web Speech API capture. Rule-based NLP parser. Fuzzy item/restaurant matching. Confirmation before add-to-cart.

## 8. Key User Journeys

### Journey 10.1 — Customer Receives AI-Personalized Homepage
1. Customer opens app. System loads `GET /api/v1/recommendations/personalized`.
2. Homepage shows "Good evening, Rahul! How about some Paneer Tikka?" based on evening North Indian preference from order history.
3. "For You" carousel shows 6 personalized items: 3 from previously ordered restaurants, 3 new items matching cuisine affinity.
4. Customer scrolls down. "Trending Near You" section visible (cold-start fallback for new users).
5. Customer taps recommended item. Goes to restaurant detail with item highlighted.
6. Post-order, confirmation page shows "You Might Like" carousel with dessert recommendations from same cuisine.
7. Over time, recommendations adapt: rainy days suggest soups; weekends suggest party platters.

### Journey 10.2 — Restaurant Owner Uses Demand Forecast
1. Restaurant owner logs into owner dashboard.
2. Navigates to "Demand Forecast" tab. Sees line chart: predicted orders per hour for next 24 hours.
3. Chart shows peak at 12:30 PM (45 orders predicted) and 7:30 PM (38 orders).
4. System recommends: "Prep 18 kg rice, 12 kg chicken, 8 L curry base for tomorrow."
5. Owner adjusts prep quantities in their kitchen. Next day, actual orders match prediction within ±8%.
6. Owner reduces food waste by 25% and stockouts by 40%.

### Journey 10.3 — Customer Uses Loyalty Program
1. Customer places ₹800 order. Earns 80 points. Total: 1,050 points.
2. Notification: "You leveled up to Silver Member! Enjoy 5% off all orders."
3. Customer visits wallet page. Sees tier badge, progress bar to Gold (3,950 pts needed), and badge collection.
4. Customer redeems 500 points for free delivery on next order.
5. Customer places 5 more orders, earns "Explorer" badge (5 cuisines tried).
6. Customer reaches Gold tier. Notification: "Welcome to Gold! Free delivery + 10% discount activated."

### Journey 10.4 — Meal Rescue Flash Sale
1. At 9:00 PM, Spice Garden closes at 10:00 PM with 8 unsold Paneer Tikka meals.
2. Cron job detects low inventory + closing soon. Creates flash sale: 50% off, 8 qty, expires 10:00 PM.
3. Push notification sent to 45 users within 3km: "Rescue Meal! Spice Garden Paneer Tikka 50% off — 1 hour left!"
4. Customer sees "Flash Deals" carousel on homepage with countdown timer: "59:23 remaining."
5. Customer orders 2 meals at ₹120 each (was ₹240). Order is batched with nearby order for efficient delivery.
6. Restaurant sells 6 of 8 meals. Customer saves money. Food waste reduced.

### Journey 10.5 — Home Chef Onboards and Sells
1. Home chef Priya registers at `/home-chef/register`. Uploads Aadhaar, FSSAI certificate, kitchen photo.
2. Admin reviews KYC. Approves within 24h. Priya receives approval email.
3. Priya creates menu: "Priya's Home Kitchen" — Homestyle Thali, Dal Tadka, Gobi Paratha.
4. Menu appears in "Home Chefs Near You" section on customer homepage.
5. Customer orders Homestyle Thali. Commission is 10% (vs. 20% for commercial).
6. Priya prepares food, driver picks up, customer reviews: "Tastes just like home! 5 stars."
7. Priya sees earnings in dashboard: ₹450 after 10% commission.

### Journey 10.6 — Smart Locker Pickup
1. Customer at WeWork office building orders lunch. At checkout, selects "Pickup at Smart Locker" instead of delivery.
2. Customer chooses "WeWork MG Road — Locker A" from map/list.
3. Order confirmed. Notification: "Your order will be ready at Locker A by 12:45 PM."
4. At 12:40 PM, kitchen marks order ready. System assigns compartment #3, generates QR code.
5. Customer receives QR code via app + email.
6. Customer goes to locker, opens app, shows QR code to camera (simulated: taps "Unlock Compartment").
7. Compartment #3 unlocks (simulated). Customer retrieves meal. System marks picked up.

### Journey 10.7 — Health-Conscious Customer Filters by Nutrition
1. Customer on keto diet opens app. Goes to restaurant detail.
2. Taps "Filters" → selects "Keto" + "High Protein" + "Under 600 cal."
3. Menu items filter in real-time. Paneer Tikka shows: 450 cal, 32g protein, 8g carbs, 28g fat. Health score: 82.
4. Item card shows allergen icons: dairy, nuts. Customer has nut allergy — item flagged with warning.
5. Customer adds to cart with confidence that item fits dietary goals.
6. Checkout shows nutrition summary for entire cart: total calories, macros.

### Journey 10.8 — Corporate Admin Orders Office Lunch
1. Corporate admin for TechCorp logs into B2B portal.
2. Creates weekly recurring order: "Mon-Fri lunch from Spice Garden, ₹200/person budget, 25 people."
3. Employees receive link: "Add your lunch for Monday." Each selects item within budget.
4. Admin reviews aggregate selection. 18 choose Thali, 7 choose Biryani. Adjusts quantities.
5. Order auto-places at 11:00 AM daily. Invoice generated monthly.
6. End of month: Admin exports CSV for SAP Concur. Total: ₹1,10,000 for 22 working days.

### Journey 10.9 — Franchisee Manages White-Label Instance
1. Franchisee "FoodieMax Bengaluru" logs into `https://foodiemax.bhojango.com` (or subdomain simulation).
2. Dashboard shows FoodieMax logo (orange variant), brand colors. Only Bengaluru restaurants visible.
3. Franchisee adds new restaurant "Biryani Bowl" to their network.
4. Restaurant appears on FoodieMax-branded customer app with their logo.
5. Central admin sees FoodieMax in franchise list: 12 restaurants, ₹4.2L monthly revenue, 4.3 avg rating.

### Journey 10.10 — Driver Gets ML-Optimized Multi-Restaurant Batch
1. Driver goes online at 12:00 PM. 4 orders in pool from 3 nearby restaurants.
2. Batch engine ML router evaluates combinations using OR-Tools VRP.
3. Optimal batch: Pick up Order A (Spice Garden), Order B (Biryani House), Order C (Taco Bell) — all within 800m pickup radius.
4. Route: Spice Garden → Biryani House → Taco Bell → Drop A → Drop B → Drop C. Total distance: 4.2 km. ETA per stop: ±3 min confidence.
5. Driver app shows optimized route with turn-by-turn. Predicted earnings: ₹180 (batch complexity bonus included).
6. Driver completes all 3 deliveries in 28 minutes vs. estimated 45 minutes for individual runs.

### Journey 10.11 — Customer Uses Voice Ordering
1. Customer driving home taps mic button on homepage.
2. Voice wave animation plays. Customer says: "Order two Paneer Tikka and one butter naan from Spice Garden."
3. App parses: 2 × Paneer Tikka, 1 × Butter Naan, restaurant = Spice Garden.
4. Fuzzy match confirms items exist in Spice Garden menu.
5. Confirmation card appears: "Add to cart: 2 × Paneer Tikka (₹320), 1 × Butter Naan (₹60) from Spice Garden?"
6. Customer taps "Confirm." Items added to cart. Cart badge updates.
7. Customer proceeds to checkout normally.

## 9. Technical Coverage

### Backend

- **user-svc:**
  - Add `user_loyalty` table endpoint: `GET /api/v1/users/loyalty`, `GET /api/v1/users/badges`.
  - Add `POST /api/v1/users/redeem-points` for reward redemption.
  - Add churn prediction endpoint: `GET /api/v1/admin/users/churn-risk` (admin only).
  - Add NPS survey endpoint: `POST /api/v1/orders/{id}/nps`.
- **restaurant-svc:**
  - Add `menu_items` nutrition columns migration.
  - Add `GET /api/v1/menu-items/{id}/nutrition` endpoint.
  - Add `home_chefs` table and CRUD endpoints: `POST /api/v1/home-chefs`, `GET /api/v1/home-chefs`, `PATCH /api/v1/home-chefs/{id}/verify`.
  - Add `GET /api/v1/restaurants/{id}/demand-forecast` endpoint.
  - Add `GET /api/v1/restaurants/{id}/predicted-prep-time` endpoint.
  - Add `flash_sales` CRUD endpoints.
  - Add `smart_lockers` CRUD and search endpoints with geo query.
  - Add `franchises` table and multi-tenant middleware.
  - Add menu item translation endpoints: `GET /api/v1/menu-items/{id}/translations`.
- **order-svc:**
  - Add meal rescue flash sale integration: apply discount code from flash sale.
  - Add corporate order endpoints: `POST /api/v1/corporate-orders`, `GET /api/v1/corporate-orders/{id}`.
  - Add scheduled recurring order cron job.
  - Add sustainability CO₂ tracking to order creation.
  - Add `feature_flags` middleware integration for A/B experiments.
- **delivery-svc:**
  - Add ML batch router integration: receive OR-Tools optimized routes.
  - Add predictive ETA per stop endpoint.
  - Add smart locker QR code validation endpoint.
- **payment-svc:**
  - Add corporate invoicing endpoints: `GET /api/v1/invoices`, `POST /api/v1/invoices/{id}/generate-pdf`.
  - Add points redemption as payment method (treat as wallet credit).
- **notification-svc:**
  - Add flash sale push/email templates (all 8 languages).
  - Add tier upgrade notification templates.
  - Add eco stats monthly digest template.
- **batch-engine:**
  - Add OR-Tools VRP module.
  - Add ML-based scorer (load sklearn model from file).
  - Add dynamic batching trigger logic.
  - Add predictive ETA module.
  - Route recalculation on order removal (complete TODO).

### Frontend — apps/web
- Add "For You" carousel component with personalized recommendations.
- Add AI recommendation explanation tooltip ("Because you ordered North Indian").
- Add loyalty dashboard page: tier badge, progress bar, badges grid, redeem section.
- Add flash sales carousel with countdown timer.
- Add "Home Chefs Near You" section on homepage.
- Add home chef onboarding flow (file upload, KYC form).
- Add smart locker selector on checkout (map + list). Add QR code display page.
- Add nutrition panel component (collapsible macro bars, allergen icons, health score).
- Add dietary filter chips on restaurant detail.
- Add B2B corporate portal pages: create order, employee invite, invoice list, recurring schedule.
- Add franchise admin dashboard with white-label theming.
- Add analytics pages: cohort chart, LTV histogram, churn risk table, NPS chart.
- Add A/B experiment admin UI: create experiment, view results.
- Add voice ordering mic button + wave animation + confirmation modal.
- Add multi-language switcher with all 8 languages.

### Frontend — apps/admin
- Add demand forecast chart for restaurant owners.
- Add predicted vs. actual prep time chart.
- Add loyalty analytics: tier distribution, points redemption rate.
- Add flash sale management: create/edit/expire sales.
- Add home chef KYC review queue with document viewer.
- Add corporate accounts list and invoice management.
- Add franchise management: create franchise, assign restaurants, view aggregated stats.
- Add sustainability metrics: total CO₂ offset, green restaurant count.
- Add A/B test results dashboard with statistical significance indicators.
- Add NPS survey results by restaurant/driver.

### Frontend — apps/mobile
- Add loyalty tier badge to profile screen.
- Add flash sale notification cards.
- Add voice ordering mic button.
- Add nutrition summary in menu item detail.
- Add dietary preference filters in search.
- Add smart locker QR scanner (simulated).
- Add multi-language selection in settings.
- Add eco stats card in wallet screen.

### Data
- Migration: `menu_items` add `calories`, `protein_g`, `carbs_g`, `fat_g`, `fiber_g`, `allergens`, `dietary_tags`.
- Migration: `user_loyalty` table (`user_id`, `tier`, `total_points`, `lifetime_points`, `redeemed_points`).
- Migration: `user_badges` table (`user_id`, `badge_type`, `awarded_at`).
- Migration: `flash_sales` table (`id`, `restaurant_id`, `menu_item_id`, `discount_percent`, `starts_at`, `ends_at`, `max_quantity`, `sold_count`).
- Migration: `home_chefs` table (`id`, `user_id`, `verification_status`, `kitchen_photo_url`, `id_document_url`, `food_safety_cert_url`, `bio`, `commission_rate`).
- Migration: `smart_lockers` table (`id`, `name`, `address`, `lat`, `lng`, `partner_type`, `total_compartments`, `available_compartments`, `temperature_controlled`).
- Migration: `locker_assignments` table (`id`, `order_id`, `locker_id`, `compartment_number`, `qr_code`, `expires_at`, `picked_up_at`).
- Migration: `corporate_accounts` table (`id`, `company_name`, `tax_id`, `billing_address`, `admin_user_id`, `credit_limit`, `payment_terms`).
- Migration: `corporate_orders` table (`id`, `corporate_account_id`, `restaurant_id`, `schedule`, `budget_per_person`, `status`).
- Migration: `franchises` table (`id`, `name`, `subdomain`, `theme_config`).
- Migration: `restaurants` add `franchise_id`, `type` (commercial/home_chef), `is_eco_friendly`, `packaging_type`.
- Migration: `feature_flags` table (`name`, `enabled`, `target_percentage`, `target_segments`).
- Migration: `experiments` table (`id`, `name`, `variant_a_config`, `variant_b_config`, `start_date`, `end_date`, `success_metric`).
- Migration: `user_cohorts` table (`user_id`, `first_order_month`, `retention_1m`, `retention_3m`, `retention_6m`).
- Migration: `nps_surveys` table (`id`, `order_id`, `user_id`, `score`, `comment`, `created_at`).
- Migration: `menu_item_translations` table (`menu_item_id`, `locale`, `name`, `description`).
- Redis: user recommendation embeddings (`rec:user:{id}`), item embeddings (`rec:item:{id}`).
- Redis: feature flags cache (`feature_flag:{name}`).
- Model files: `prep_time_model.pkl`, `demand_forecast_model.pkl` (pickled scikit-learn models).

## 10. UI / UX Coverage

- **Loading states:** Skeleton loaders for recommendations carousel, nutrition panel, loyalty dashboard, forecast charts.
- **Error states:** ML model not loaded → fallback to heuristic. Recommendation service down → show trending items. Flash sale expired → disable with "Sale Ended" badge.
- **Empty states:** No recommendations yet (new user) → show onboarding cuisine selector. No badges earned → show locked badges with "How to earn" tooltips. No flash sales active → hide carousel.
- **Success states:** Tier upgrade animation (confetti/slide-in). Badge unlock animation. Points redeemed toast. QR code generated with checkmark. Voice order parsed successfully → confirmation card.
- **Design system:** Use BhojanGo brand palette consistently. Nutritional bars use traffic-light colors (green/yellow/red). Loyalty tiers use metallic colors (bronze/copper, silver, gold, platinum). Green badge uses leaf icon 🌿 (Lucide `Leaf`).
- **Responsive:** All new components work on mobile, tablet, desktop. Nutrition panel collapses to accordion on mobile. Loyalty dashboard stacks vertically on mobile. Franchise admin uses collapsible sidebar.
- **Accessibility:** Voice ordering button has `aria-label="Order by voice"`. Nutrition info has `aria-expanded` on toggle. Flash sale countdown announces via `aria-live="polite"`. Locker QR code has alt text.
- **Animations:** Tier upgrade confetti (canvas-confetti or CSS). Badge unlock pulse. Recommendation carousel swipe. Countdown timer smooth tick. Voice wave bars animate while listening.

## 11. Data / Model Coverage

- `menu_items`: new columns `calories` (INT), `protein_g` (DECIMAL), `carbs_g` (DECIMAL), `fat_g` (DECIMAL), `fiber_g` (DECIMAL), `allergens` (JSONB), `dietary_tags` (JSONB). Index on `dietary_tags` using GIN for fast filtering.
- `users` ↔ `user_loyalty`: one-to-one. `tier` ENUM ('bronze','silver','gold','platinum'). `total_points` INT, `lifetime_points` INT.
- `users` ↔ `user_badges`: one-to-many. `badge_type` ENUM.
- `restaurants` → `franchises`: many-to-one via `franchise_id`. NULL allowed for independent restaurants.
- `restaurants` → `home_chefs`: one-to-one or polymorphic via `type` + `home_chef_id`.
- `flash_sales` → `restaurants` and `menu_items`: foreign keys. Time-bounded offers.
- `smart_lockers` → `locker_assignments` → `orders`: one locker has many assignments; one order has one assignment.
- `corporate_accounts` → `corporate_orders` → `orders`: corporate order generates one or more regular orders.
- `menu_item_translations` → `menu_items`: many translations per item.
- `feature_flags`: application-level configuration. Cached in Redis.
- `experiments` + `experiment_conversions`: track A/B test results.
- `nps_surveys` → `orders`: one-to-one post-delivery survey.
- Pickled ML models stored on filesystem or S3: `prep_time_model.pkl`, `demand_forecast_model.pkl`, `recommendation_embeddings.npz`.

## 12. Role / Permission Coverage

- `customer`: Full access to recommendations, loyalty, flash sales, home chefs, smart lockers, nutrition filters, voice ordering, multi-language. Can participate in corporate orders as employee.
- `restaurant_owner`: Access to demand forecast, predicted prep time, flash sale creation (for their restaurant), nutritional info editing, sustainability settings. Cannot see other restaurants' data unless franchise admin.
- `home_chef`: Same as restaurant owner but limited to their home kitchen profile. Lower commission visibility.
- `delivery_partner`: Access to ML-optimized routes, batch details, smart locker QR validation. Can view earnings including complexity bonus.
- `corporate_admin`: Full B2B portal access: create bulk orders, invite employees, view invoices, manage recurring schedules. Cannot access consumer-facing admin features.
- `franchisee`: Admin dashboard scoped to their `franchise_id`. Can add/manage restaurants within franchise. Sees franchise-branded UI.
- `admin`: Full access to all features including KYC review, franchise management, A/B test creation, feature flag editing, advanced analytics.
- `super_admin`: Same as admin plus system configuration, model retraining triggers, global feature flags.
- **Cross-role enforcement:** All endpoints check `franchise_id` claim for franchise-scoped data. Corporate endpoints check `corporate_account_id`. ML inference endpoints are read-only and accessible to all authenticated users.

## 13. Performance / Reliability / Security Coverage

### Performance
- AI recommendation inference <100ms via precomputed embeddings in Redis. Batch compute every 6h using background Celery/ cron job.
- Predictive prep-time inference <50ms (lightweight RandomForest with <20 features).
- Demand forecast compute <200ms for 168 hourly predictions.
- OR-Tools VRP solver capped at 500ms for <=5 orders. Fallback to heuristic if timeout.
- Nutritional filter queries use GIN index on `dietary_tags` — <100ms.
- Multi-language JSON files code-split by locale; only active locale loaded.
- Voice ordering NLP parser runs client-side (rule-based) or <100ms server-side.

### Reliability
- ML models versioned with pickle hash. Fallback to heuristic scoring if model file missing or corrupt.
- Flash sale cron job is idempotent: checks before creating duplicate sale.
- Smart locker QR codes have 30-minute expiry with cleanup cron.
- Corporate recurring orders use transactional outbox: schedule entry → order creation → notification.
- A/B experiment bucketing is deterministic (consistent hash) — user always sees same variant.
- Voice ordering has confirmation gate — never auto-place without user review.
- Batch engine route recalculation on removal completed (fix TODO).

### Security
- Home chef KYC documents stored encrypted at rest (S3 SSE). Access restricted to admin role.
- Corporate account billing data encrypted. Tax IDs hashed in logs.
- Franchise isolation: strict `franchise_id` filtering on all queries. No cross-franchise data leakage.
- Feature flags and experiments: only admin/super_admin can create/modify.
- Voice ordering NLP: strict allow-list parsing. Reject commands that don't match expected patterns.
- QR codes are single-use and time-bound. Brute force prevention on QR scan endpoint.
- ML models loaded from trusted path only; no pickle deserialization from user input.

## 14. Novelty / Differentiation Coverage

At score 10, BhojanGo achieves genuine category-leading differentiation:

- **AI-driven personalization** — Collaborative filtering with time/weather context creates a "Netflix for food" experience. No generic food app offers this level of personalization without external AI services.
- **Predictive logistics** — ±5 min prep time accuracy and demand forecasting turn restaurant operations from reactive to proactive. Directly reduces waste and stockouts.
- **Community kitchen marketplace** — Home chefs with verified KYC create supply-side differentiation. Lower commission attracts home chefs unavailable on commercial platforms.
- **Smart locker network** — Contactless pickup at co-working spaces solves the "delivery to office" problem uniquely. QR-based retrieval feels modern and frictionless.
- **Nutritional transparency + dietary filtering** — Full macros, allergens, and health scores on every item. Keto/vegan/high-protein filters make BhojanGo the health-conscious choice.
- **Office lunch B2B** — Corporate accounts with recurring orders and invoicing create a second revenue stream. Food delivery platforms rarely serve B2B well.
- **Franchise white-label** — Multi-tenant dashboard enables regional operators to run their own branded instance. Scalable business model beyond direct operation.
- **ML batch routing** — OR-Tools VRP with predictive ETAs per stop makes multi-restaurant batching operationally viable. Competitors batch same-restaurant only.
- **Sustainability program** — Real CO₂ calculations + gamified eco leaderboard. Green badges for verified eco-friendly restaurants. Authentic environmental positioning, not greenwashing.
- **Full Indian language support** — 7 Indian languages plus English. Inclusive design for India's diverse linguistic landscape.
- **Voice ordering** — Web Speech API + rule-based NLP makes ordering accessible while driving or for users with motor disabilities.
- **A/B testing framework** — Built-in experimentation culture. Platform continuously improves via data-driven decisions.
- **Structural moats:**
  - Better recommendations → more orders → more data → better recommendations (virtuous cycle).
  - Demand forecasting → lower waste → better margins → competitive pricing.
  - Community kitchens → unique supply → unique customers → network effects.
  - B2B recurring orders → predictable revenue → sustainable unit economics.

## 15. Implementation Work Items

### IP.PR.10.001 — AI Recommendations Engine (Collaborative Filtering)
- **Category:** Backend + Frontend
- **Implementation Scope:** Build user-item interaction matrix from `orders.items` + `menu_items`. Install `implicit` (ALS) or use scikit-learn `NMF` for matrix factorization. Feature engineering: encode time-of-day (morning/afternoon/evening/night), day-of-week, weather (API mock for demo), veg preference, cuisine affinity. Train model in background job every 6h. Store user embeddings (`rec:user:{id}`) and item embeddings (`rec:item:{id}`) in Redis as JSON arrays. Endpoint `GET /api/v1/recommendations/personalized` computes dot product of user embedding with item embeddings, returns top 10 with explanation string. Cold-start: show trending items + onboarding cuisine preference. Frontend: "For You" carousel on homepage. Post-order "You Might Like" carousel. Explanation tooltip on hover.
- **Acceptance Criteria:**
  1. Recommendations endpoint returns 10 items in <100ms.
  2. Results change based on order history (test user with North Indian orders sees more North Indian).
  3. Cold-start user sees trending items, not empty.
  4. Explanation string is meaningful ("Because you ordered North Indian last week").
  5. Model retraining job completes without error and updates Redis embeddings.
- **Evidence Required:** Screenshot of "For You" carousel. `curl` showing recommendation response with explanations. Redis `GET rec:user:{id}` showing embedding vector.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.09 (stable order history data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.002 — Predictive Prep-Time ML Model
- **Category:** Backend
- **Implementation Scope:** Extract training data from `order_status_history`: compute `confirmed` → `ready_for_pickup` duration in minutes. Features: `avg_prep_minutes` (restaurant), current queue size (pending orders), hour-of-day (0-23), day-of-week (0-6), item count, customization count. Train scikit-learn `RandomForestRegressor` or `GradientBoostingRegressor`. Save as `prep_time_model.pkl`. Endpoint `GET /api/v1/restaurants/{id}/predicted-prep-time` loads model, computes features from current state, returns `{estimated_minutes, confidence_low, confidence_high, factors}`. Integrate into checkout ETA calculation: `ETA = predicted_prep + delivery_time`. Show in restaurant owner dashboard as "Predicted vs. Actual" chart.
- **Acceptance Criteria:**
  1. Model achieves ±5 min accuracy on 80% of test set predictions.
  2. Endpoint returns prediction in <50ms.
  3. Checkout ETA uses predicted prep time instead of static `avg_prep_minutes`.
  4. Restaurant owner dashboard shows predicted vs. actual prep time chart.
  5. Fallback to `avg_prep_minutes` if model file missing.
- **Evidence Required:** Model evaluation report (RMSE, MAE). Screenshot of predicted vs. actual chart. `curl` showing prediction with confidence interval.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.09 (order status history data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.003 — Demand Forecasting
- **Category:** Backend + Frontend
- **Implementation Scope:** Aggregate historical order count by hour by restaurant. Features: hour, day_of_week, is_weekend, is_holiday, avg_orders_last_4_weeks_same_hour, weather (mock). Train scikit-learn `RandomForestRegressor` or `Prophet` for time-series. Predict next 24h (hourly) and next 7d (daily). Save model as `demand_forecast_model.pkl`. Endpoint `GET /api/v1/restaurants/{id}/demand-forecast` returns `{hourly: [...], daily: [...]}`. Frontend: restaurant owner dashboard shows line chart with forecast + recommended prep quantities ("Prep 18 kg rice for tomorrow's lunch rush").
- **Acceptance Criteria:**
  1. Forecast accuracy within ±15% for next-day hourly predictions.
  2. Endpoint returns 24h + 7d forecasts in <200ms.
  3. Dashboard chart shows predicted vs. actual for past 7 days.
  4. Prep recommendations are calculated from forecasted item popularity.
  5. Cron job retrains model weekly.
- **Evidence Required:** Screenshot of forecast chart. `curl` showing hourly predictions. Accuracy report on holdout test set.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.10.002 (ML infrastructure established)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.004 — Loyalty + Gamification Full Program
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Create `user_loyalty` and `user_badges` tables. Points earning: 10 pts per ₹100 spent. Bonus: +50 first order, +20 per review, +100 per referral. Tier thresholds: Bronze 0, Silver 1000, Gold 5000, Platinum 10000. Tier benefits stored in config. `POST /api/v1/users/redeem-points` accepts reward type (free_delivery, discount_50, discount_100), validates points balance, applies reward. **Frontend:** Wallet page shows tier badge (metallic color), progress bar to next tier, badges grid (locked/unlocked), redeemable rewards list. Level-up animation on tier change. Badge unlock animation. Points added to wallet transaction list.
- **Acceptance Criteria:**
  1. Points awarded correctly per order (10 per ₹100).
  2. Tier upgrades automatically at threshold crossing with notification.
  3. Badge earned after completing criteria (e.g., 5 cuisines = Explorer badge).
  4. Redemption reduces points balance and applies reward to next order.
  5. Dashboard displays all loyalty data accurately.
- **Evidence Required:** Screenshot of loyalty dashboard. DB query showing `user_loyalty` row. Screen recording of tier upgrade animation.
- **Priority:** P0
- **Effort:** L
- **Dependency:** IP.PR.09 (basic loyalty points stored)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.005 — Meal Rescue / End-of-Day Flash Sales
- **Category:** Backend + Frontend
- **Implementation Scope:** Cron job (`flash_sale_cron.py`) runs every 15 min. Query: restaurants closing within 1h (`closes_at - NOW() < 1h`) with menu items having `daily_stock > sold_count` and low sales velocity. Create `flash_sales` record with 30-50% discount, quantity = unsold stock, 1h expiry. Send push/email via notification-svc to users within 3km. Frontend: "Flash Deals" carousel on homepage with countdown timer (MM:SS). Discount badge on item card. Checkout applies flash sale price automatically if item in cart. Backend: `GET /api/v1/flash-sales/active` returns current deals.
- **Acceptance Criteria:**
  1. Cron job creates flash sale when restaurant has unsold inventory and closing within 1h.
  2. Users within 3km receive push notification.
  3. Homepage carousel displays active flash sales with live countdown.
  4. Flash sale price applied at checkout.
  5. Sale auto-expires and becomes unavailable after `ends_at`.
- **Evidence Required:** Screenshot of flash sale carousel. DB query showing `flash_sales` row. Push notification screenshot. Screen recording of countdown and purchase.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.09 (notification dispatch wired)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.006 — Community Kitchen / Home Chef Marketplace
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Create `home_chefs` table with KYC fields. `POST /api/v1/home-chefs/register` accepts profile + file uploads (ID, FSSAI cert, kitchen photo). Store files in S3/local. Admin reviews via `PATCH /api/v1/home-chefs/{id}/verify`. On approval, create `restaurants` row with `type='home_chef'` and `commission_rate=0.10`. **Frontend:** Home chef registration wizard (3 steps: profile, documents, menu). "Home Chefs Near You" section on homepage. Dedicated `/home-chefs` page. Chef profile shows bio, kitchen photo, hygiene badge, specialties. Lower commission badge visible to chef in dashboard.
- **Acceptance Criteria:**
  1. Home chef can register, upload KYC documents, and create menu.
  2. Admin can review and approve/reject with reason.
  3. Approved chef appears in "Home Chefs Near You" section.
  4. Commission rate is 10% (vs. 20% commercial).
  5. Customer can order from home chef same as commercial restaurant.
- **Evidence Required:** Screenshot of home chef registration. Admin KYC review queue. Customer view of home chef menu. DB showing `commission_rate=0.10`.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.09 (restaurant CRUD + S3 uploads)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.007 — Smart Locker Network
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `smart_lockers` table with geo fields. `GET /api/v1/smart-lockers/nearby?lat=&lng=&radius=` returns nearest lockers. At checkout, if user selects locker, create `locker_assignment` with QR code (`uuid`), compartment number (auto-increment within capacity), expiry (+30 min). `POST /api/v1/smart-lockers/{id}/validate` accepts QR code, marks picked up. **Frontend:** Checkout: "Pickup at Locker" option. Map showing nearby lockers. Post-order: QR code display page with timer. Simulated unlock button. Admin: locker management page.
- **Acceptance Criteria:**
  1. User can select smart locker at checkout from nearby list/map.
  2. QR code generated and displayed after order is ready.
  3. QR validation marks order picked up.
  4. Assignment expires after 30 min with notification reminder.
  5. Locker availability updates correctly after assignment/pickup.
- **Evidence Required:** Screenshot of locker selector. QR code display page. DB query showing `locker_assignments`.
- **Priority:** P2
- **Effort:** M
- **Dependency:** IP.PR.09 (checkout flow stable)
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (smart locker hardware partners)

### IP.PR.10.008 — Nutritional Transparency
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Migration adds nutrition columns to `menu_items`. `GET /api/v1/menu-items/{id}/nutrition` returns full breakdown. Health score algorithm: weighted score based on protein ratio, fiber, calorie density. **Frontend:** Menu item card has "Nutrition Info" toggle. Expand shows macro bar chart (protein/carbs/fats), calorie count, allergen icons (Lucide `AlertTriangle`). Dietary filter chips: "Keto", "Vegan", "High Protein", "Under 500 cal", "Gluten-Free". Filter state managed client-side or via query param. Admin: nutritional info editor in menu management.
- **Acceptance Criteria:**
  1. Every menu item shows calories and macros when expanded.
  2. Allergen warnings display as icons with tooltip.
  3. Health score visible (0-100 scale).
  4. Dietary filters reduce menu to matching items.
  5. Admin can edit nutrition data per item.
- **Evidence Required:** Screenshot of nutrition panel. Filtered menu view. DB query showing nutrition columns populated.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.09 (menu CRUD exists)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.009 — Office Lunch Program (B2B)
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `corporate_accounts`, `corporate_orders`, `corporate_order_items` tables. `POST /api/v1/corporate-orders` creates bulk order with schedule. Recurring orders: cron job reads `schedule` (cron expression), generates regular orders at scheduled time. `GET /api/v1/invoices` returns monthly invoice list. PDF generation using `weasyprint` or `pdfkit`. `GET /api/v1/invoices/{id}/export` returns CSV (QuickBooks format). **Frontend:** Corporate portal: create order, set budget, invite employees via email/link, view aggregate selections, download invoice PDF, export CSV. Employee view: see today's lunch, add item within budget, dietary restrictions auto-applied.
- **Acceptance Criteria:**
  1. Corporate admin can create recurring bulk order.
  2. Employees can select items within per-person budget.
  3. Order auto-places on schedule.
  4. Monthly invoice generated with itemized breakdown.
  5. CSV export matches QuickBooks/SAP Concur format.
- **Evidence Required:** Screenshot of corporate portal. PDF invoice sample. CSV export file. DB showing `corporate_orders`.
- **Priority:** P1
- **Effort:** XL
- **Dependency:** IP.PR.09 (order creation + payment stable)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.010 — Franchise Management / White-Label
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `franchises` table with `subdomain`, `theme_config`. Add `franchise_id` to `restaurants`. Middleware extracts `X-Franchise-ID` or `franchise_id` from JWT claim and filters all queries. `GET /api/v1/franchise/config` returns theme colors, logo URL. **Frontend:** Franchisee dashboard: scoped to franchise restaurants, franchise logo, brand colors. White-label theming: dynamic CSS variables from `/api/v1/franchise/config`. Central admin: franchise list, create franchise, assign restaurants, view cross-franchise KPIs. Onboarding wizard: 3-step franchise creation.
- **Acceptance Criteria:**
  1. Franchisee sees only their restaurants and orders.
  2. Central admin sees all franchises with aggregated stats.
  3. Frontend theming reflects franchise config (colors, logo).
  4. No cross-franchise data leakage via API.
  5. Franchise onboarding wizard creates franchise + assigns restaurants.
- **Evidence Required:** Screenshot of franchisee dashboard. Screenshot of central admin franchise list. API test confirming data isolation. DB showing `franchise_id` filtering.
- **Priority:** P2
- **Effort:** XL
- **Dependency:** IP.PR.09 (admin dashboard + restaurant CRUD)
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (multi-tenancy at scale)

### IP.PR.10.011 — Advanced Batch Engine ML Routing
- **Category:** Backend (batch-engine)
- **Implementation Scope:** Install Google OR-Tools (`ortools` Python package or `@google-cloud/optimization` for TS — use Python microservice or TS wrapper). Build `ort-router.ts` module: define VRP with pickup/dropoff nodes, time windows, driver capacity constraints. Use `routing` library to solve. Build `ml-scorer.ts`: load pickled sklearn model, predict batch quality score based on features (distance, time, traffic, capacity utilization). Replace greedy heuristic with ML + OR-Tools hybrid. Dynamic batching: trigger when `pool_size >= min_batch_size` (configurable, default 3) OR `max_wait_time` elapsed (default 5 min). Predictive ETA: `predicted_eta_minutes` per stop with confidence interval. Route recalculation on order removal (complete existing TODO). Expose metrics: batch_size_avg, savings_per_batch, solver_time_ms.
- **Acceptance Criteria:**
  1. OR-Tools produces valid route for 2-5 orders within 500ms.
  2. ML scorer ranks batches higher than heuristic on historical validation set.
  3. Dynamic batching triggers on pool size OR time, whichever comes first.
  4. Route recalculation works when order removed from batch.
  5. Predictive ETA per stop displayed in driver app.
- **Evidence Required:** Route optimization output comparison (heuristic vs. OR-Tools). Solver timing metrics. Driver app screenshot showing multi-stop route with ETAs.
- **Priority:** P2
- **Effort:** XL
- **Dependency:** IP.PR.09 (batch engine operational)
- **Status:** TODO
- **Implementation Class:** 🔴 FUTURE INFRA (OR-Tools VRP at scale)

### IP.PR.10.012 — Sustainability Program
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `restaurant_sustainability` table with `packaging_type`, `is_eco_friendly`, `certified_by`. `user_eco_stats` table with `co2_saved_g`, `trees_equivalent`, `batched_order_count`. CO₂ formula: `distance_km × emission_factor × (1 - batch_savings)`. Batch savings = (individual_delivery_distance_sum - batched_distance) / individual_delivery_distance_sum. **Frontend:** Order confirmation shows CO₂ saved. Wallet/Profile shows eco stats card with tree equivalent. Leaderboard: "Top Eco Warriors this month." Restaurant card shows green leaf badge if `is_eco_friendly`. Filter for "Green Restaurants." Admin: sustainability metrics dashboard.
- **Acceptance Criteria:**
  1. Every order shows CO₂ saved in confirmation and wallet.
  2. Green badge visible on eco-friendly restaurant cards.
  3. Eco leaderboard ranks top customers by CO₂ saved.
  4. Batch delivery shows higher CO₂ savings than individual delivery.
  5. Admin dashboard shows total platform CO₂ offset.
- **Evidence Required:** Screenshot of order confirmation with CO₂ saved. Eco stats card. Leaderboard. DB showing `user_eco_stats`.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.10.011 (batch engine operational for savings calc)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.013 — Full Multi-Language Support (8 Locales)
- **Category:** Frontend + Backend
- **Implementation Scope:** Add `messages/ta.json`, `messages/te.json`, `messages/kn.json`, `messages/mr.json`, `messages/bn.json`, `messages/gu.json` alongside existing `en.json` and `hi.json`. Translate all UI strings (~300 keys per locale). Use machine translation (LibreTranslate or DeepL API) for first pass, manual review for food terms. `menu_item_translations` table: store translated name + description per locale. `GET /api/v1/menu-items/{id}/translations` returns translations. Frontend: language switcher dropdown with all 8 languages. Detect browser language on first visit. Admin: translation management UI for editing menu translations. RTL not required.
- **Acceptance Criteria:**
  1. All 8 languages have complete JSON message files.
  2. Language switcher changes UI instantly without reload.
  3. Menu items display translated names when locale matches.
  4. First-time visitor gets language auto-detected from browser.
  5. Admin can edit menu translations and publish.
- **Evidence Required:** Screenshots of same page in 4+ languages. Language switcher demo. DB showing `menu_item_translations`.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.08 (i18n infrastructure)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE (JSON files)

### IP.PR.10.014 — Advanced Analytics (Cohort, LTV, Churn, NPS)
- **Category:** Backend + Frontend
- **Implementation Scope:** **Cohort analysis:** Group users by `DATE_TRUNC('month', first_order_date)`. Compute retention: % of cohort with order in month 1, 3, 6. **LTV prediction:** Train regression model on order_frequency, AOV, tenure. **Churn prediction:** Classifier flagging users with no order in 30 days + declining frequency. **NPS:** `POST /api/v1/orders/{id}/nps` survey 24h after delivery. Score 0-10. Store in `nps_surveys`. **Frontend:** Admin dashboard shows cohort retention heatmap (HTML table or chart), LTV histogram, churn risk list (sorted, with action buttons), NPS line chart by month and by restaurant.
- **Acceptance Criteria:**
  1. Cohort retention heatmap shows monthly retention rates.
  2. LTV predictions display per user with confidence band.
  3. Churn risk list flags users with >70% churn probability.
  4. NPS survey sends 24h post-delivery; scores aggregated in dashboard.
  5. All analytics update daily via cron job.
- **Evidence Required:** Screenshot of cohort heatmap. Churn risk list. NPS trend chart. DB queries showing analytics tables populated.
- **Priority:** P1
- **Effort:** L
- **Dependency:** IP.PR.09 (order history + user data)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.015 — A/B Testing Framework
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** `feature_flags` table: `name`, `enabled` (bool), `target_percentage` (0-100), `target_segments` (JSONB). `experiments` table: `name`, `variant_a`, `variant_b`, `start_date`, `end_date`, `success_metric`. Assignment: `hash(user_id + experiment_name) % 100` for deterministic bucketing. `GET /api/v1/feature-flags/{name}` returns enabled + variant for user. `POST /api/v1/experiments/{id}/conversion` records conversion event. **Frontend:** `useFeatureFlag(name)` hook. `useExperiment(name)` hook returning variant. Admin UI: create/edit experiments, view conversion rates, statistical significance (z-test p-value).
- **Acceptance Criteria:**
  1. Feature flag can enable/disable feature for X% of users.
  2. Same user always sees same experiment variant.
  3. Conversion events tracked per experiment.
  4. Admin dashboard shows conversion rate and p-value.
  5. Nonsignificant experiments (p > 0.05) flagged clearly.
- **Evidence Required:** Screenshot of experiment admin UI. API response showing variant assignment. Conversion rate chart.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.09 (auth + user IDs stable)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.10.016 — Voice Ordering (Web Speech API + NLP)
- **Category:** Frontend + Backend
- **Implementation Scope:** **Frontend:** Floating mic button on homepage and restaurant detail. Web Speech API `SpeechRecognition` with `continuous: false`, `lang: 'en-IN'`. Voice wave animation (CSS animated bars). Display transcript. Confirmation modal: "Add to cart: [parsed order]?" **Backend:** `POST /api/v1/voice/parse` accepts transcript string. Rule-based NLP: regex extract quantity (`(\d+)`), item name (fuzzy match against menu using Levenshtein or trigram), restaurant name (fuzzy match). Return `{intent: 'add_to_cart', items: [...], restaurant: {...}, confidence: 0.85}`. If confidence < 0.7, return `{intent: 'clarification', message: 'Did you mean...?'}`. Fuzzy match fallback: suggest closest item names.
- **Acceptance Criteria:**
  1. Voice button activates browser speech recognition.
  2. "Order 2 Paneer Tikka and 1 Naan from Spice Garden" parses correctly.
  3. Low confidence parses show clarification, not auto-add.
  4. Parsed order shows in confirmation modal before adding to cart.
  5. Works in Chrome/Edge (Web Speech API support).
- **Evidence Required:** Screen recording of voice ordering flow. API response showing parsed intent. Screenshot of confirmation modal.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.09 (search + menu data available)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] AI recommendations return personalized top-10 items in <100ms with explanation.
- [ ] Predictive prep-time model achieves ±5 min accuracy on 80% of predictions.
- [ ] Demand forecast predicts hourly volume per restaurant within ±15% for next 24h.
- [ ] Loyalty tier system (Bronze/Silver/Gold/Platinum) with automatic upgrades and benefits.
- [ ] Badge system awards and displays achievements with unlock animations.
- [ ] Points redemption works at checkout for free delivery and discounts.
- [ ] Flash sales auto-create 1h before closing with push/email to nearby users.
- [ ] Homepage shows flash deals carousel with live countdown.
- [ ] Home chef onboarding with KYC document upload and admin review works end-to-end.
- [ ] Home chefs appear in separate "Home Chefs Near You" section with 10% commission.
- [ ] Smart locker checkout option, QR code generation, and simulated pickup work.
- [ ] Nutritional info (calories, macros, allergens, health score) visible on every menu item.
- [ ] Dietary filter chips (Keto, Vegan, High Protein, etc.) filter menu items.
- [ ] Corporate B2B portal supports bulk ordering, recurring schedules, invoicing, CSV export.
- [ ] Franchise management isolates data by `franchise_id` with white-label theming.
- [ ] Batch engine uses OR-Tools VRP for route optimization with ML-based scoring.
- [ ] Dynamic batching triggers on demand threshold or time limit.
- [ ] Predictive ETA per stop displayed to driver.
- [ ] Sustainability CO₂ calculation shown per order with eco leaderboard.
- [ ] Green badge visible on eco-friendly restaurants.
- [ ] Full multi-language: 8 locales with complete JSON message files and menu translations.
- [ ] Advanced analytics: cohort heatmap, LTV prediction, churn risk list, NPS trend chart.
- [ ] A/B testing framework: feature flags, experiment tracking, conversion metrics with p-values.
- [ ] Voice ordering parses natural language orders with confirmation before adding to cart.
- [ ] Core customer loop and three-sided marketplace remain stable (no regression from PR.09).

## 17. Evidence Required

- Screenshot of "For You" recommendation carousel with explanation tooltips.
- `curl` showing `GET /api/v1/recommendations/personalized` response with embeddings.
- Model evaluation report for prep-time model (RMSE, MAE, accuracy distribution).
- Screenshot of restaurant owner dashboard with demand forecast chart + prep recommendations.
- Screenshot of loyalty dashboard: tier badge, progress bar, badges grid, rewards.
- Screen recording of tier upgrade animation + badge unlock.
- Screenshot of flash sale carousel with countdown timer.
- Push notification screenshot for meal rescue.
- Screenshot of home chef registration and KYC review queue.
- Screenshot of smart locker selector + QR code display.
- Screenshot of nutrition panel with macro bars and allergen icons.
- Screenshot of dietary filter chips in action.
- Screenshot of corporate B2B portal: bulk order creation, employee selection, invoice.
- Sample PDF invoice and CSV export file.
- Screenshot of franchisee dashboard with white-label branding.
- API test confirming cross-franchise data isolation (403 or filtered results).
- Screenshot of driver app showing OR-Tools optimized multi-stop route with ETAs.
- Screenshot of order confirmation showing CO₂ saved.
- Screenshot of eco leaderboard.
- Screenshots of same page in 4+ languages.
- Screenshot of cohort retention heatmap, LTV histogram, churn risk list, NPS chart.
- Screenshot of A/B experiment admin UI with conversion rates and p-values.
- Screen recording of voice ordering: tap mic → speak → parse → confirm → add to cart.
- DB queries confirming all new tables populated: `user_loyalty`, `flash_sales`, `home_chefs`, `smart_lockers`, `corporate_accounts`, `franchises`, `nps_surveys`, `menu_item_translations`.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, Kong, OpenSearch).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- numpy, scikit-learn, implicit (Python ML stack — pip-installable).
- Google OR-Tools (`ortools` Python package — pip-installable).
- Prophet (`fbprophet` or `prophet` — optional, pip-installable).
- weasyprint or pdfkit (Python PDF generation for invoices).
- Web Speech API (built into Chrome/Edge, no install required).
- LibreTranslate (optional, self-hosted) or DeepL API (optional, free tier) for machine translation.
- canvas-confetti or CSS animations (for tier upgrade, badge unlock).

### Internal Dependencies
- **PR.09 must be complete:** Real payment webhooks, FCM/email/SMS dispatch, CI/CD, observability, group ordering, Mapbox tracking, onboarding wizard, loyalty points basic, CDN/S3 images.
- ML training jobs require `order_status_history` data (PR.09 stable).
- Batch engine OR-Tools integration requires existing batch-engine service operational (PR.09).
- Franchise multi-tenancy requires admin dashboard with role checks (PR.09).
- Voice ordering requires search + menu endpoints (PR.09).
- Corporate B2B requires order creation + payment + invoice generation (PR.09).

## 19. Risks / Blockers

- **ML model accuracy:** Predictive prep-time may not achieve ±5 min without sufficient historical data. Mitigation: start with heuristic baseline, collect data during PR.09, retrain when dataset >500 samples.
- **OR-Tools integration complexity:** VRP solver may be slow or produce infeasible routes. Mitigation: cap solver time at 500ms, fallback to heuristic. Validate routes before assignment.
- **Multi-language translation quality:** Machine translation of food terms may be inaccurate. Mitigation: manual review of menu item names. Allow restaurant owners to edit translations.
- **Franchise data isolation:** Row-level filtering bugs could leak cross-franchise data. Mitigation: comprehensive integration tests for every franchise-scoped endpoint. Use query-level `franchise_id` filters, not application-level.
- **Voice ordering accuracy:** Speech recognition accuracy varies by accent/background noise. Mitigation: restrict to Chrome/Edge where API is best. Show transcript for confirmation. Low confidence triggers clarification.
- **Flash sale cron job load:** Running every 15 min with complex inventory queries could spike DB. Mitigation: cache inventory levels in Redis. Use lightweight query with indexed columns.
- **Home chef KYC storage:** Uploading government IDs raises privacy concerns. Mitigation: encrypt at rest (S3 SSE). Auto-delete after verification. Access limited to admin role with audit log.
- **Corporate invoice PDF generation:** PDF libraries have heavy system dependencies (cairo for weasyprint). Mitigation: use `pdfkit` (wkhtmltopdf) or pre-built Docker image with dependencies.
- **B2B scope creep:** Corporate ordering can expand into expense approvals, multi-location management. Mitigation: keep MVP focused on bulk ordering + invoicing + CSV export.
- **Pickle model security:** Loading sklearn models from pickle files is safe only if files are trusted. Mitigation: load from internal S3/path only, never from user uploads. Use `joblib` with integrity hash check.

## 20. Exit Criteria

- All P0 work items (IP.PR.10.001, IP.PR.10.002, IP.PR.10.004, IP.PR.10.008, IP.PR.10.011) implemented and verified.
- All P1 work items implemented and verified.
- AI recommendations load in <100ms and adapt to user history.
- Predictive prep-time achieves ±5 min accuracy target on validation set.
- Loyalty tiers, badges, and redemption fully functional with animations.
- Flash sales auto-create and notify nearby users correctly.
- Home chef marketplace operational with KYC and separate listing.
- Smart locker pickup flow complete (selection → QR → simulated unlock).
- Nutritional transparency on all menu items with dietary filters.
- B2B corporate portal supports bulk orders, recurring schedules, and invoicing.
- Franchise management isolates data and supports white-label theming.
- Batch engine uses OR-Tools with ML scoring and dynamic batching.
- Sustainability CO₂ calculations visible per order and in leaderboard.
- All 8 languages have complete translations and menu item localization.
- Advanced analytics dashboards display cohorts, LTV, churn, and NPS.
- A/B testing framework supports feature flags and experiment tracking.
- Voice ordering parses natural language with confirmation step.
- Core customer loop and three-sided marketplace remain stable.
- Evidence screenshots/recordings captured per Section 17.
- PR.10 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.09)

PR.10 directly depends on PR.09 achievements:
- **IP.PR.09.001** — Real payment webhooks: foundation for B2B invoicing and points redemption.
- **IP.PR.09.002** — FCM/email/SMS dispatch: foundation for flash sale notifications, tier upgrades, locker QR codes.
- **IP.PR.09.003** — CI/CD pipeline: required for deploying ML models and batch engine updates.
- **IP.PR.09.004** — Observability (Prometheus/Grafana): needed for monitoring ML inference latency and batch engine solver times.
- **IP.PR.09.005** — Group ordering: social infrastructure extended by B2B corporate ordering.
- **IP.PR.09.006** — Mapbox/Leaflet tracking: foundation for smart locker map selector and driver route visualization.
- **IP.PR.09.007** — Onboarding wizard: provides cuisine preference data for cold-start recommendations.
- **IP.PR.09.008** — CDN/S3 images: foundation for home chef kitchen photos and KYC document storage.
- **IP.PR.09.009** — Advanced search: foundation for voice ordering item matching.
- **IP.PR.09.010** — Loyalty points basic: foundation for full tiered loyalty program.

## 22. Connected Next-Level Requirements (link to PR.10+ / Future)

PR.10 is the final planned production readiness level. Future enhancements (beyond score 10) could include:
- Real-time traffic integration via Google Routes API (paid).
- Drone delivery pilot program.
- AR menu visualization (scan QR code, see 3D food model).
- Blockchain-verified supply chain tracking.
- Multi-region deployment (US East + India Mumbai).
- Grocery vertical expansion.
- Driverless vehicle integration.
- Real-time video streaming from kitchen to customer.
- Social features: food photos feed, following chefs, sharing orders.
- Subscription meal plans (Blue Apron model).
- AI-powered dynamic pricing optimization.

PR.10 will be blocked if:
- PR.09 payment webhooks are not operational (B2B invoicing broken).
- PR.09 notification dispatch is not wired (flash sales cannot notify users).
- PR.09 batch engine is not deployed (ML routing has no platform).
- PR.09 Mapbox tracking is not live (smart locker map and driver routes broken).
- PR.09 onboarding wizard is not collecting cuisine preferences (cold-start recommendations poor).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (10/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.09 complete) described | Planner | ✅ |
| 4 | Target state (PR.10 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.10 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.10 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty, success states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage notes structural differentiation and virtuous cycles | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.10.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover all required PR.10 areas (AI recommendations, predictive prep-time, demand forecasting, loyalty, flash sales, community kitchen, smart lockers, nutrition, B2B, franchise, advanced batch engine, sustainability, multi-language, analytics, A/B testing, voice ordering) | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention ML accuracy, OR-Tools complexity, translation quality, franchise isolation, voice accuracy, cron load, KYC privacy, PDF dependencies, B2B scope creep, pickle security | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.09) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and >=8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required PR.10 areas:
  - AI recommendations engine (IP.PR.10.001)
  - Predictive prep-time ML (IP.PR.10.002)
  - Demand forecasting (IP.PR.10.003)
  - Loyalty + gamification full (IP.PR.10.004)
  - Meal rescue flash sales (IP.PR.10.005)
  - Community kitchen marketplace (IP.PR.10.006)
  - Smart locker network (IP.PR.10.007)
  - Nutritional transparency (IP.PR.10.008)
  - Office lunch B2B (IP.PR.10.009)
  - Franchise management / white-label (IP.PR.10.010)
  - Advanced batch engine ML routing (IP.PR.10.011)
  - Sustainability program (IP.PR.10.012)
  - Full multi-language (IP.PR.10.013)
  - Advanced analytics (IP.PR.10.014)
  - A/B testing framework (IP.PR.10.015)
  - Voice ordering NLP (IP.PR.10.016)
- Scope tightly bounded to score 10/10: mature marketplace with AI personalization, predictive logistics, ecosystem breadth, and operational excellence.
- Out-of-scope explicitly excludes blockchain, drones, AR/VR, and other over-engineered features.
- Data model coverage addresses all new tables: user loyalty, badges, flash sales, home chefs, smart lockers, corporate accounts, franchises, feature flags, experiments, cohorts, NPS, menu translations.
- Feasibility tags correctly applied: 🟢 LOCAL/DEMO-SAFE for lightweight ML, voice ordering, multi-language; 🟡 OPTIONAL EXTERNAL for smart locker hardware partners (simulation mode available); 🔴 FUTURE INFRA for franchise multi-tenancy at scale.
- Risks and blockers are grounded in known technical challenges from codebase analysis (ML accuracy with limited data, OR-Tools complexity, franchise isolation, voice recognition variability, KYC privacy).
- Connected previous-level and next-level requirements explicitly documented with specific work item references and blocker conditions.
- **One point deducted** because some ML implementation details (ALS vs. NMF vs. RandomForest for recommendations) are left to builder discretion, and the exact choice between `weasyprint` and `pdfkit` for invoice PDF generation is not pre-selected. Additionally, the menu translation workflow (machine translation first pass + manual review) is described but the exact tooling choice (LibreTranslate vs. DeepL) is left as optional. These are minor implementation choices that do not affect plan completeness.

The document is ready for execution.
