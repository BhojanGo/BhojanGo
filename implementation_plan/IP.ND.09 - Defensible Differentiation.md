# IP.ND.09 — Defensible Differentiation

## 1. Target Differentiation Score: 9/10

## 2. Score Meaning

Novel features are operationally useful, not gimmicks: group carts, meal rescue, loyalty tiers, restaurant insights, delivery confidence, and customer trust loops. At score 9, BhojanGo is not merely a feature-rich food delivery app — it is a platform with operational moats. Competitors cannot copy these features easily because they require operational integration, data depth, and ecosystem lock-in. Restaurant insights require aggregate transactional data. Delivery confidence scoring requires real-time operational metrics. The trust loop requires regulatory verification infrastructure and admin oversight. Advanced loyalty tiers create switching costs. Multi-restaurant group carts require complex fee-splitting and order orchestration. Predictive ETAs with confidence bands require historical pattern analysis. Meal rescue as a sustainability program creates brand authenticity. Rule-based support AI reduces operational overhead. These features are defensible because they compound: more orders generate better insights, which improve confidence scoring, which builds trust, which increases retention through loyalty, which generates more orders.

## 3. Current → Target Transition

**From ND.08 (strong product identity):**
- The app has a distinct visual identity: BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons, consistent badge and card anatomy.
- Trust badges (FSSAI Verified, Freshly Prepared, Under 30 min) are visible on restaurant cards.
- Loyalty points are earned and visible. Basic tier (Bronze/Silver/Gold/Platinum) labels may be visible but full tier benefits are not implemented.
- Group ordering works for single-restaurant sessions with shareable links, attribution, split bill, and host checkout.
- Office lunch mode works with budget enforcement, recurring orders, and consolidated invoices.
- Meal rescue deals exist as end-of-day flash sales with 50% off badges.
- Nutritional transparency, fee calculator, sustainability scores, and order batching preview are all functional.
- **No restaurant insights dashboard exists.** Restaurant owners cannot view analytics: peak hours, most ordered items, customer retention rate, average order value trend, cuisine preference breakdown, or repeat customer percentage. No CSV export.
- **No delivery confidence score exists.** Customers see static ETAs (e.g., "35-45 min") with no predictive scoring. No factor-based confidence (driver availability, queue size, weather, distance, traffic). No "95% confidence — your order will arrive on time" messaging.
- **No customer trust loop exists.** No triple verification: (1) FSSAI license verified and visible to customer, (2) kitchen photo verification every 30 days, (3) customer review sentiment analysis with <3.5 rating flagging for admin audit. No admin trust dashboard.
- **Loyalty tiers lack full depth.** Bronze/Silver/Gold/Platinum labels may exist but benefits are basic or unimplemented. No auto-calculation of tier thresholds. No Silver monthly ₹20 off. No Gold free delivery + priority support. No Platinum 5% cashback + surprise rewards.
- **Meal rescue is a discount feature, not a sustainability program.** No CO2 saved per rescue order. No "You've saved 12 kg of food waste this month" leaderboard. No shareable sustainability badge for social media.
- **Group cart is single-restaurant only.** No true multi-restaurant group ordering in one session. No split delivery fees per restaurant. No consolidated receipt showing items from multiple restaurants.
- **ETAs are static single numbers.** No predictive ETAs with confidence bands (e.g., "28-35 min"). Confidence band does not narrow as order progresses.
- **No rule-based customer support AI.** No FAQ bot on order detail page. No "Where is my order?" → driver location + ETA. No "Wrong item received" → refund flow automation.

**Target at score 9:**
- **Restaurant insights dashboard is live:** Restaurant owners see a private analytics dashboard with: (1) Peak hours chart (orders by hour of day), (2) Most ordered items table with rank, (3) Customer retention rate (repeat customers / total customers), (4) Average order value trend line (7-day, 30-day), (5) Cuisine preference breakdown (pie chart of cuisine types ordered), (6) Repeat customer percentage. All data is computed from order history. One-click export to CSV. Data updates daily.
- **Delivery confidence score is live:** Before checkout, every order shows a "Delivery Confidence" score (0-100). Score is computed from: (a) current driver availability count within 3km, (b) restaurant queue size (orders ahead), (c) current weather condition (rain/snow/clear), (d) straight-line distance from restaurant to customer, (e) time-of-day traffic factor (peak vs off-peak). Score >= 85 shows green badge: "Delivery Confidence: 95% — Your order will arrive on time." Score 60-84 shows yellow: "Delivery Confidence: 72% — Possible 5-10 min delay." Score <60 shows red: "Delivery Confidence: 45% — High demand, expect delays." All factors are rule-based; no ML model required.
- **Customer trust loop is enforced:** Every restaurant detail page shows three trust indicators: (1) "FSSAI Verified" badge with license number visible in tooltip. (2) "Kitchen Verified" badge with a thumbnail of the latest kitchen photo, date-stamped "Verified 12 days ago." (3) "Customer Rating Audit" — if rating >= 4.0, green check; if 3.5-3.9, yellow "Under Review"; if <3.5, red "Audit Scheduled." Admin sees a trust dashboard at `/admin/trust` listing all restaurants with trust status, flagged restaurants, and kitchen photo upload reminders.
- **Loyalty tiers have full depth:** Auto-calculated tiers based on rolling 90-day spend. Bronze (₹0-999): no benefits. Silver (₹1,000-4,999): ₹20 off monthly coupon auto-applied. Gold (₹5,000-14,999): free delivery on all orders + priority support ("Gold Member — response within 2 hours" badge). Platinum (₹15,000+): 5% cashback on every order as wallet credit + monthly "surprise reward" (random free item, double points day, or exclusive restaurant access). Tier badge visible on profile, cart, and checkout. Tier progress bar: "Spend ₹340 more to reach Gold."
- **Meal rescue is a full sustainability program:** Each rescue order shows "You saved 0.4 kg of food waste and 180g CO₂." Monthly leaderboard in profile: "You've saved 12 kg of food waste this month." Share badge button generates a social-friendly image: "I rescued 12 kg of food with BhojanGo this month." CO₂ calculation is rule-based: (food waste kg × 2.5 kg CO₂/kg food) + (delivery miles saved via batching × 0.12 kg CO₂/mile).
- **Group cart supports multi-restaurant:** A single group order session can include items from multiple restaurants. Each restaurant has its own sub-cart. Delivery fees are split per restaurant. One consolidated receipt shows all restaurants, all items, per-restaurant subtotals, per-restaurant delivery fees, and one grand total. Host places a single order that spawns multiple restaurant orders behind the scenes, or a single multi-restaurant order record.
- **Predictive ETAs with confidence bands:** ETA is shown as a range: "28-35 min" instead of "32 min." As order progresses (confirmed → preparing → picked up), the range narrows: "28-35 min" → "30-33 min" → "31-32 min." Confidence band is computed from historical prep time variance, driver speed variance, and current status. For demo, variance is simulated from seed data patterns.
- **Rule-based support AI is active:** An expandable "Help" panel on every order detail page. Common intents: "Where is my order?" → shows driver location card + ETA. "Wrong item received" → opens refund flow with item selector and reason dropdown. "Cancel my order" → shows cancel button if status allows, with refund estimate. "Contact support" → opens a simple ticket form. All responses are rule-based (keyword matching or simple condition checks). No external AI API.

## 4. Implementation Objective

Add defensible, operationally integrated features that are hard to replicate: deep restaurant insights, delivery confidence scoring, comprehensive trust loop, advanced loyalty tiers, full meal rescue ecosystem, multi-restaurant group carts, predictive ETAs with confidence bands, and rule-based support AI. These features create operational moats because they require (a) aggregate data that only accumulates with order volume, (b) multi-party operational coordination (restaurant + platform + driver + customer), (c) regulatory integration (FSSAI verification), and (d) ecosystem lock-in (loyalty tiers, group cart social graphs). All features are demo-safe: they work locally with seed data, rule-based calculations, simulated historical patterns, and mock integrations.

## 5. Scope

### 5.1 Restaurant Insights Dashboard (For Owners)
- **Database:** Analytics are computed on-demand from existing `orders`, `order_items`, `restaurants`, `users`, and `reviews` tables. No new analytics tables required for demo. Optional: `restaurant_analytics_snapshots` table for caching daily aggregates (id, restaurant_id, date, metric_name, metric_value).
- **Backend:**
  - `GET /api/v1/restaurants/{id}/insights` — returns aggregated analytics for the authenticated owner's restaurant:
    - `peak_hours`: array of `{hour: 0-23, order_count}` for last 30 days.
    - `top_items`: array of `{menu_item_id, name, total_ordered, revenue}` for last 30 days.
    - `customer_retention_rate`: float (repeat_customers / unique_customers) for last 90 days.
    - `aov_trend`: array of `{date, aov}` for last 30 days.
    - `cuisine_preference_breakdown`: object `{cuisine_type: order_count}` derived from customer orders at this restaurant.
    - `repeat_customer_percentage`: float (repeat_customers / total_customers) for last 30 days.
  - `GET /api/v1/restaurants/{id}/insights/export?format=csv` — returns CSV download with all metrics.
- **Frontend:**
  - Restaurant owner dashboard (`/owner/insights`): tabbed analytics page.
    - Peak hours: bar chart (x=hour, y=order count). Uses Recharts or simple CSS bars.
    - Top items: ranked table with order count and revenue.
    - Retention rate: large KPI card with percentage and trend arrow.
    - AOV trend: line chart (7-day and 30-day toggle).
    - Cuisine breakdown: pie chart or donut chart.
    - Repeat customers: KPI card + table of top repeat customers.
    - Export button: "Download CSV" triggers `GET /export`.
  - Time range selector: "Last 7 days" / "Last 30 days" / "Last 90 days" (computed client-side from returned data).

### 5.2 Delivery Confidence Score
- **Database:** Uses existing `orders`, `restaurants`, `deliveries` tables. No new tables.
- **Backend:**
  - `GET /api/v1/orders/confidence?restaurant_id={id}&distance_km={d}` — returns confidence score (0-100) and factor breakdown.
    - Algorithm (rule-based, no ML):
      - `driver_factor` = min(100, active_drivers_within_3km × 20). If 0 drivers, factor = 10.
      - `queue_factor` = max(0, 100 - (queue_size × 15)). Queue size = orders in `confirmed` or `preparing` status for this restaurant.
      - `weather_factor` = 100 (clear), 70 (rain), 40 (storm/snow). Weather is mock/simulated for demo (can be set via query param or seed data).
      - `distance_factor` = max(0, 100 - (distance_km × 8)).
      - `traffic_factor` = 100 (off-peak), 75 (peak: 12-2 PM, 7-9 PM).
      - `score = (driver_factor × 0.25) + (queue_factor × 0.25) + (weather_factor × 0.20) + (distance_factor × 0.15) + (traffic_factor × 0.15)`.
    - Response: `{score, factors: {driver, queue, weather, distance, traffic}, message, color: green|yellow|red}`.
- **Frontend:**
  - On restaurant detail page and cart page: "Delivery Confidence" badge with color-coded shield icon.
  - Tooltip/bottom sheet on tap: shows score breakdown with 5 progress bars (one per factor).
  - Dynamic update: score recalculates when user changes delivery address (distance changes).

### 5.3 Customer Trust Loop
- **Database:**
  - Extend `restaurants` table: `fssai_license_number` VARCHAR, `fssai_verified` BOOLEAN, `kitchen_photo_url` VARCHAR, `kitchen_photo_uploaded_at` TIMESTAMP, `trust_status` VARCHAR (verified, review, audit, suspended).
  - New `trust_audits` table: `id`, `restaurant_id`, `audit_type` (rating_flag, photo_missing, license_expired), `status` (open, resolved), `created_at`, `resolved_at`.
- **Backend:**
  - `GET /api/v1/restaurants/{id}/trust` — returns trust indicators: `{fssai_verified, license_number, kitchen_photo_url, kitchen_photo_age_days, customer_rating, trust_status, audit_flags}`.
  - `POST /api/v1/admin/trust-audits` — admin creates an audit for a restaurant.
  - `PATCH /api/v1/admin/trust-audits/{id}/resolve` — admin resolves an audit.
  - `GET /api/v1/admin/trust-dashboard` — admin view: list all restaurants with trust status, filter by `audit_scheduled`, `photo_overdue` (>30 days), `rating_flag`.
  - Sentiment analysis is rule-based: if avg rating < 3.5 → `audit_scheduled`. If 3.5-3.9 → `review`. If >= 4.0 → `verified`. No NLP model.
- **Frontend:**
  - Restaurant detail page: trust section with three badges in a row:
    - FSSAI Verified: shield checkmark + "License: {number}" tooltip.
    - Kitchen Verified: camera icon + thumbnail + "Verified {N} days ago".
    - Rating Audit: star icon + status pill (green "Verified", yellow "Under Review", red "Audit Scheduled").
  - Admin trust dashboard (`/admin/trust`): table of restaurants with sortable columns (name, trust status, photo age, rating, audit count). Actions: "Schedule Audit", "Send Photo Reminder", "Resolve Audit".

### 5.4 Loyalty Tiers — Full Depth
- **Database:**
  - Extend `users` table: `loyalty_tier` VARCHAR (bronze, silver, gold, platinum), `loyalty_tier_calculated_at` TIMESTAMP.
  - New `loyalty_benefits` table: `id`, `tier`, `benefit_type` (monthly_discount, free_delivery, cashback, surprise_reward), `value`, `used_at`.
- **Backend:**
  - `GET /api/v1/users/loyalty` — returns current tier, benefits, progress to next tier, history.
  - `POST /api/v1/users/loyalty/recalculate` — recalculates tier based on rolling 90-day spend. Called on every order completion or daily via cron.
  - Tier thresholds: Bronze (₹0-999), Silver (₹1,000-4,999), Gold (₹5,000-14,999), Platinum (₹15,000+).
  - Benefits logic:
    - Silver: monthly ₹20 off coupon. Auto-generated on 1st of month. Applied automatically if valid.
    - Gold: free delivery on all orders (delivery_fee = 0 at checkout). Priority support flag in user profile.
    - Platinum: 5% cashback on every order added to wallet. Monthly surprise reward (randomly selected from a small pool and added to wallet).
- **Frontend:**
  - Profile page: loyalty card with current tier badge, progress bar ("Spend ₹340 more to reach Gold"), benefit list.
  - Cart/checkout: tier badge displayed. If Gold, delivery fee line shows "₹0 (Gold Member Free Delivery)". If Silver, discount line shows "-₹20 (Silver Monthly Reward)".
  - Tier change toast: "Congratulations! You've reached Gold. Free delivery unlocked!"

### 5.5 Meal Rescue — Full Ecosystem
- **Database:**
  - Extend `orders` table: `is_rescue_order` BOOLEAN, `food_waste_saved_kg` DECIMAL(5,2), `co2_saved_g` INT.
  - New `user_sustainability_stats` table: `id`, `user_id`, `total_rescue_orders`, `total_food_waste_saved_kg`, `total_co2_saved_g`, `current_month_kg`, `current_month_co2_g`.
- **Backend:**
  - On rescue order completion: compute `food_waste_saved_kg = (item_count × 0.15 kg avg per item)` and `co2_saved_g = (food_waste_saved_kg × 2500) + (batch_miles_saved × 120)`. Update `user_sustainability_stats`.
  - `GET /api/v1/users/sustainability` — returns user's stats and monthly leaderboard rank.
  - `GET /api/v1/sustainability/leaderboard` — top 10 users by `current_month_kg`.
- **Frontend:**
  - Order confirmation (rescue): "You saved 0.4 kg of food waste and 180g CO₂."
  - Profile sustainability card: monthly stats, progress ring, "Share Your Impact" button.
  - Share badge modal: generates a social card image (CSS-based or canvas-based) with text: "I rescued {X} kg of food with BhojanGo this month. #BhojanGoRescue". One-click copy/download.
  - Homepage section: "Sustainability Leaders" horizontal scroll of top 3 users.

### 5.6 Group Cart — Multi-Restaurant
- **Database:**
  - Extend `group_orders` table: `is_multi_restaurant` BOOLEAN (default false).
  - New `group_order_restaurants` table: `id`, `group_order_id`, `restaurant_id`, `subtotal`, `delivery_fee`, `status`.
- **Backend:**
  - `POST /api/v1/group-orders` — support `is_multi_restaurant=true`. Host selects first restaurant, then can "Add Another Restaurant" before checkout.
  - `POST /api/v1/group-orders/{code}/restaurants/{restaurant_id}/items` — add items to a specific restaurant's sub-cart.
  - `GET /api/v1/group-orders/{code}` — returns grouped items by restaurant. Each restaurant has its own subtotal and delivery fee.
  - `POST /api/v1/group-orders/{code}/checkout` — validates all restaurant sub-carts, creates either (a) one order per restaurant with `group_order_id` linkage, or (b) a single order with multi-restaurant items.
  - Split bill: splits per-restaurant fees proportionally.
- **Frontend:**
  - Group cart page shows restaurant tabs or accordion sections. Each section has its own item list, subtotal, and delivery fee.
  - "Add Another Restaurant" button opens restaurant list modal. Selected restaurant appears as a new tab/section.
  - Consolidated receipt: lists all restaurants, per-restaurant items, per-restaurant delivery fees, one grand total.
  - Checkout: single "Place Order" button. Order confirmation shows all restaurants with individual ETAs.

### 5.7 Predictive ETAs with Confidence Bands
- **Database:**
  - Extend `orders` table: `eta_confidence_low` INT, `eta_confidence_high` INT, `eta_variance_factor` DECIMAL.
  - `delivery_eta_history` table (optional for demo): `id`, `restaurant_id`, `distance_km`, `actual_prep_minutes`, `actual_delivery_minutes`, `created_at`.
- **Backend:**
  - `GET /api/v1/orders/{id}/eta` — returns `{low, high, current_estimate, confidence_pct}`.
    - Base ETA = `avg_prep_minutes + (distance_km / 25 × 60) + queue_penalty`.
    - Variance = `base_ETA × variance_factor`. Variance factor is 0.20 for "pending", 0.12 for "confirmed", 0.08 for "preparing", 0.05 for "picked_up", 0.02 for "out_for_delivery".
    - Range: `low = base_ETA × (1 - variance)`, `high = base_ETA × (1 + variance)`.
    - As status progresses, variance shrinks, range narrows.
  - For demo, variance factors are hardcoded. Historical data can be simulated from seed orders.
- **Frontend:**
  - Restaurant detail page: "Delivery in 28-35 min" (range instead of single number).
  - Order tracking page: ETA range updates as status progresses. Visual progress bar with range indicator.
  - Final stage (out for delivery): "Arriving in 31-32 min" (very narrow).

### 5.8 Rule-Based Customer Support AI
- **Database:**
  - New `support_tickets` table: `id`, `user_id`, `order_id`, `type` (where_is_order, wrong_item, cancel_request, other), `status`, `created_at`, `resolved_at`.
- **Backend:**
  - `POST /api/v1/support/ai-chat` — accepts `{order_id, message}`. Returns rule-based response based on keyword matching:
    - "where" or "status" or "track" → `{type: "where_is_order", response: "Your order is {status}. Driver location: {lat}, {lng}. ETA: {eta}.", actions: [{label: "View on Map", url: "/orders/{id}/track"}]}`.
    - "wrong" or "missing" or "incorrect" → `{type: "wrong_item", response: "We're sorry. Please select the incorrect item(s).", actions: [{label: "Start Refund", url: "/orders/{id}/refund"}]}`.
    - "cancel" or "stop" → `{type: "cancel_request", response: "You can cancel if the order status is {cancelable_status}.", actions: [{label: "Cancel Order", action: "cancel", order_id: id}]}`.
    - Default → `{type: "other", response: "I've forwarded your message to our support team. They'll respond within 2 hours.", actions: [{label: "Contact Human Support", url: "/support/ticket"}]}`.
  - `POST /api/v1/support/tickets` — creates a human support ticket.
- **Frontend:**
  - Order detail page: floating "Help" button or expandable bottom panel.
  - Chat-like UI with quick-action chips: "Where is my order?", "Wrong item received", "Cancel my order", "Contact support".
  - Response renders as a card with text + action button(s). "Where is my order?" shows driver location mini-map + ETA. "Wrong item" opens refund flow with item checkboxes. "Cancel" shows cancel button + refund estimate.

## 6. Out of Scope

- **Heavy neural network models / external AI APIs:** No OpenAI, Claude, or custom NLP models. All "AI" features are rule-based keyword matching and simple arithmetic formulas.
- **Blockchain:** No on-chain verification, no crypto payments, no NFT badges.
- **Autonomous delivery:** No drones, no self-driving vehicles, no robot couriers.
- **AR/VR:** No augmented reality menu previews, no virtual restaurant tours.
- **Real-time traffic API integration:** Traffic factor is time-of-day heuristic. No Google Maps / Here / Waze API calls.
- **Real weather API integration:** Weather is simulated (clear/rain/storm) via query param or simple mock data.
- **Real FSSAI license verification API:** License number is stored and displayed. No government API integration for real-time verification. Trust is based on owner submission + admin spot-check.
- **Real kitchen photo AI verification:** Photos are uploaded by owners. No computer vision model checks kitchen hygiene. Admin manually reviews or accepts on upload.
- **Advanced NLP for review sentiment analysis:** Sentiment is simple average rating threshold. No text analysis.
- **Real-time WebSocket for group cart:** Multi-restaurant group cart uses existing short-polling (3s). WebSocket upgrade is deferred.
- **Actual multi-party payment split:** Split bill is calculated and displayed, but payment is host-paid or mocked. Real split payment deferred to PR.09+.
- **Production cron infrastructure:** Loyalty recalculation and analytics snapshots use admin trigger endpoints or lightweight dev schedulers. Production cron deferred.
- **Advanced statistical ML for ETA prediction:** ETA variance is hardcoded by status. No random forest or regression model.
- **Social media API integration for share badges:** Share badge is a generated image (canvas/CSS) copied/downloaded. No direct Facebook/Twitter/Instagram API posting.

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.05+).
- Auth persistence must work. All features require logged-in users except viewing public trust badges and restaurant insights (owner-only).
- Group ordering (single-restaurant) from ND.06 must be stable. Multi-restaurant group cart builds on this.
- Restaurant list and menu APIs must support filtering and extensions.
- Cart Zustand store must support multi-restaurant item grouping.
- Order tracking page must exist and support status-based UI updates.
- Profile page must exist for loyalty and sustainability cards.
- Admin dashboard (`/admin`) must exist for trust dashboard and restaurant insights access control.
- Design system (BhojanGo palette, typography, spacing, Lucide icons) must be applied across all new UI.
- Toast/snackbar component must exist for confirmations, tier upgrades, and rescue impact.
- Modal/bottom sheet component must exist for share badges, refund flows, and support chat.
- Charting library (Recharts, Chart.js, or simple CSS bars) for analytics dashboard.
- Seed data must include historical orders for analytics computation, loyalty tier calculation, and ETA variance simulation.

## 8. Key User Journeys

### Journey 9.1 — Restaurant Owner Checks Insights
1. Ravi, owner of "Biryani House", logs in and navigates to Owner Dashboard.
2. Taps "Insights" tab. Sees Peak Hours chart: highest bar at 8 PM (42 orders).
3. Top Items table: "Chicken Biryani — 312 orders, ₹93,600 revenue" ranked #1.
4. Retention Rate KPI: "68% of customers ordered again within 30 days."
5. AOV Trend line: 30-day trend shows ₹420 → ₹445 → ₹438. Slight upward trend.
6. Cuisine Breakdown pie chart: "Biryani 85%, Kebabs 10%, Desserts 5%."
7. Ravi taps "Export CSV". Downloads a file with all raw data.
8. Ravi uses this data to plan a 8 PM special offer.

### Journey 9.2 — Customer Sees Delivery Confidence Before Ordering
1. Priya browses "Spice Garden" at 12:45 PM. Restaurant card shows "Delivery Confidence: 88%" green badge.
2. She taps the badge. Bottom sheet opens showing breakdown:
   - Driver availability: 5 nearby (100/100)
   - Restaurant queue: 3 ahead (55/100)
   - Weather: Clear (100/100)
   - Distance: 3.2 km (74/100)
   - Traffic: Peak hour (75/100)
   - Overall: 88/100
3. Message: "Delivery Confidence: 88% — Your order will arrive on time."
4. She changes address to a farther location (6.5 km). Score updates to 72 (yellow).
5. Message changes: "Delivery Confidence: 72% — Possible 5-10 min delay."
6. Priya decides the delay is acceptable and proceeds to checkout.

### Journey 9.3 — Customer Trusts a Restaurant Because of Trust Loop
1. Ananya opens "Asha's Kitchen" (home chef). Restaurant detail shows three trust badges:
   - FSSAI Verified: shield checkmark. Tooltip: "License: 11223344556677".
   - Kitchen Verified: camera thumbnail. "Verified 8 days ago."
   - Customer Rating Audit: green pill "Verified — 4.6 stars".
2. She opens a different restaurant, "Fast Curry". Trust badges show:
   - FSSAI Verified: yes.
   - Kitchen Verified: red warning "Photo overdue — 45 days ago."
   - Customer Rating Audit: red pill "Audit Scheduled — 3.2 stars".
3. Ananya feels uneasy and returns to Asha's Kitchen.
4. Admin sees "Fast Curry" flagged on `/admin/trust` and sends a photo reminder.

### Journey 9.4 — User Reaches Gold Tier and Gets Free Delivery
1. Karthik places an order worth ₹850. After order completion, a toast appears: "Congratulations! You've reached Gold! Free delivery unlocked."
2. Profile page shows Gold badge with sparkles. Progress bar at "Gold — spend ₹8,500 more to reach Platinum."
3. Karthik adds items to cart. At checkout, delivery fee line shows: "₹0 (Gold Member Free Delivery)".
4. He also sees a "Priority Support" badge on the support panel: "Gold Member — expect response within 2 hours."
5. Next month, Karthik maintains Gold tier. Free delivery continues automatically.

### Journey 9.5 — User Tracks Sustainability Impact from Meal Rescue
1. Meena orders a rescue deal from Domino's. Order confirmation: "You saved 0.4 kg of food waste and 180g CO₂."
2. She navigates to Profile → Sustainability. Card shows: "This month: 4.2 kg saved. You're #23 on the leaderboard."
3. She taps "Share Your Impact". Modal shows a generated badge: "I rescued 4.2 kg of food with BhojanGo this month. #BhojanGoRescue".
4. She taps "Download Image". Badge saves to device.
5. Homepage shows "Sustainability Leaders": #1 Raj (12.1 kg), #2 Priya (9.8 kg), #3 Anil (8.4 kg).

### Journey 9.6 — Friends Order from Multiple Restaurants in One Group Cart
1. Rahul starts a group order and selects "Multi-Restaurant" option.
2. He adds a pizza from Domino's. Cart shows "Domino's — 1 item, ₹299, delivery ₹40."
3. He taps "Add Another Restaurant", picks "Spice Garden", adds Butter Chicken.
4. Cart now has two tabs: "Domino's" and "Spice Garden". Each has its own items, subtotal, and delivery fee.
5. Friend Ananya joins via link and adds Garlic Bread under Domino's tab.
6. Split bill modal shows per-restaurant breakdown + individual totals.
7. Rahul places one order. Confirmation shows two restaurant cards with separate ETAs.
8. Behind the scenes, two orders are created (or one multi-restaurant order record).

### Journey 9.7 — User Watches ETA Confidence Band Narrow
1. Arjun places an order at 7 PM. Confirmation shows: "Estimated delivery: 32-42 min."
2. At "Confirmed" status, tracking page still shows "32-42 min".
3. At "Preparing" status, range narrows: "35-40 min".
4. At "Picked Up" status, range narrows further: "37-39 min".
5. At "Out for Delivery", range is very narrow: "38-39 min".
6. Arjun feels increasingly confident about timing as the range tightens.

### Journey 9.8 — User Gets Help from Rule-Based Support AI
1. Sara opens her active order detail. Taps "Help" panel.
2. Quick-action chips visible: "Where is my order?", "Wrong item received", "Cancel my order", "Contact support".
3. She taps "Where is my order?". Bot responds: "Your order is Out for Delivery. Driver is 1.2 km away. ETA: 38-39 min." Mini-map shows driver pin.
4. Later, she receives a wrong item. Opens Help → taps "Wrong item received".
5. Bot responds: "We're sorry. Please select the incorrect item(s)." List of items appears with checkboxes.
6. She selects "Paneer Tikka", taps "Start Refund". Refund flow opens with reason dropdown.
7. She also sees "Cancel my order" is grayed out because status is "Picked Up" — bot explains: "Orders that have been picked up cannot be cancelled."

## 9. Technical Coverage

### Backend
- **restaurant-svc or new insights-svc:** `GET /api/v1/restaurants/{id}/insights` — SQL aggregation queries over orders, order_items, users. `GET /export` — CSV generation (Python `csv` module or `pandas`). Owner-only access: validate JWT `sub` matches `restaurant.owner_id`.
- **order-svc or new confidence-svc:** `GET /api/v1/orders/confidence` — rule-based scoring function with mock weather/traffic inputs.
- **restaurant-svc:** `GET /api/v1/restaurants/{id}/trust` — returns FSSAI, kitchen photo, rating audit status. `POST /api/v1/admin/trust-audits`, `PATCH /api/v1/admin/trust-audits/{id}/resolve`, `GET /api/v1/admin/trust-dashboard`.
- **user-svc:** `GET /api/v1/users/loyalty` — tier calculation based on rolling 90-day spend query. `POST /api/v1/users/loyalty/recalculate` — triggered on order completion or admin.
- **order-svc:** Extend order completion to update `user_sustainability_stats`. `GET /api/v1/users/sustainability`, `GET /api/v1/sustainability/leaderboard`.
- **order-svc/group-order-svc:** Extend existing group order endpoints to support `is_multi_restaurant`, per-restaurant sub-carts, and multi-restaurant checkout.
- **order-svc:** `GET /api/v1/orders/{id}/eta` — dynamic range calculation based on status.
- **new support-svc or extend user-svc:** `POST /api/v1/support/ai-chat` — keyword-based response router. `POST /api/v1/support/tickets` — ticket creation.

### Frontend
- **Zustand store extensions:**
  - `insightsStore` (analytics data, time range, loading).
  - `confidenceStore` (score, factors, loading).
  - `trustStore` (trust badges, admin audits).
  - `loyaltyStore` (tier, benefits, progress, history).
  - `sustainabilityStore` (stats, leaderboard, share badge).
  - `multiRestaurantCartStore` (grouped items by restaurant, per-restaurant fees).
  - `etaStore` (range low/high, status-based updates).
  - `supportStore` (chat messages, ticket status).
- **Components:**
  - `<OwnerInsightsDashboard />` — charts, tables, KPIs, export button.
  - `<ConfidenceBadge />` — color-coded shield with score.
  - `<ConfidenceBreakdown />` — bottom sheet with 5 factor progress bars.
  - `<TrustBadges />` — FSSAI, Kitchen, Rating badges in a row.
  - `<TrustBadgeTooltip />` — detailed info on hover/tap.
  - `<AdminTrustDashboard />` — sortable table, action buttons.
  - `<LoyaltyCard />` — tier badge, progress bar, benefit list.
  - `<TierUpgradeToast />` — celebration animation on tier change.
  - `<SustainabilityCard />` — monthly stats, progress ring.
  - `<ShareBadgeModal />` — generated image preview, download/copy.
  - `<LeaderboardSection />` — horizontal scroll of top users.
  - `<MultiRestaurantCart />` — tabs/accordion by restaurant.
  - `<AddRestaurantModal />` — restaurant list for adding to group cart.
  - `<ConsolidatedReceipt />` — multi-restaurant order summary.
  - `<ETARangeDisplay />` — "28-35 min" with status-based updates.
  - `<SupportPanel />` — expandable help panel on order detail.
  - `<SupportChat />` — message bubbles + quick-action chips.
  - `<RefundFlow />` — item selector + reason dropdown.
- **Hooks:**
  - `useInsights(restaurantId, range)`
  - `useConfidence(restaurantId, distanceKm)`
  - `useTrust(restaurantId)`
  - `useLoyalty()`
  - `useSustainability()`
  - `useMultiRestaurantCart(groupCode)`
  - `useETA(orderId)`
  - `useSupportAI(orderId)`

### Data
- Extended tables: `restaurants` (FSSAI, kitchen photo, trust status), `users` (loyalty tier), `orders` (is_rescue_order, food_waste_saved_kg, co2_saved_g, eta ranges).
- New tables: `trust_audits`, `loyalty_benefits`, `user_sustainability_stats`, `group_order_restaurants`, `support_tickets`.
- Seed data: historical orders for analytics, FSSAI numbers for restaurants, kitchen photo URLs, order history with varying statuses for ETA simulation.

## 10. UI / UX Coverage

- **Loading states:** Skeleton charts for insights dashboard. Skeleton badge for confidence score. Skeleton trust badges. Skeleton loyalty card. Skeleton sustainability stats.
- **Error states:** "No insights data yet — place more orders" for new restaurants. "Confidence unavailable — try again" if calculation fails. "Trust data missing" for unverified restaurants. "Loyalty calculation pending" after first order. "No rescue orders yet" for sustainability card. "Join link expired" for group cart. "Support unavailable" fallback to human ticket form.
- **Empty states:** Empty insights: "Your first order data will appear here." Empty leaderboard: "Be the first to rescue a meal this month!" Empty multi-restaurant cart: "Add items from at least one restaurant."
- **Success states:** Toast on tier upgrade. Toast on rescue order completion with CO₂ saved. Toast on support ticket creation. Toast on CSV export download.
- **Design system:** All new components follow BhojanGo palette, typography, 4px grid, Lucide icons. Confidence badge uses semantic colors (green `#2E7D32`, yellow `#FFB300`, red `#E65100`). Trust badges use outline style. Loyalty tier badges use filled style with tier-specific color (Bronze `#8D6E63`, Silver `#90A4AE`, Gold `#FFB300`, Platinum `#7E57C2`). Sustainability uses green accent.
- **Responsive:** Insights dashboard: stacked charts on mobile, 2-column grid on tablet, 3-column on desktop. Confidence badge: always compact, breakdown in bottom sheet on mobile / tooltip on desktop. Trust badges: horizontal scroll on mobile, inline row on desktop. Loyalty card: full-width on mobile, card layout on desktop. Multi-restaurant cart: tabs on mobile, side-by-side columns on desktop. Support panel: bottom sheet on mobile, side panel on desktop.
- **Dark mode:** Charts use muted grid lines and white text on dark backgrounds. Badges maintain semantic colors. Trust badge thumbnails have subtle border. Loyalty progress bar uses distinct colors per tier.
- **Accessibility:** Insights charts use `aria-label` describing the data. Confidence breakdown progress bars use `aria-valuenow`. Trust badges use `aria-label` for each verification type. Loyalty progress bar uses `role="progressbar"`. Support chat uses `role="log"` and `aria-live="polite"` for new messages. All interactive elements have visible focus states.

## 11. Data / Model Coverage

- `restaurants` table (extended): `fssai_license_number` VARCHAR(20), `fssai_verified` BOOLEAN DEFAULT false, `kitchen_photo_url` VARCHAR, `kitchen_photo_uploaded_at` TIMESTAMP, `trust_status` VARCHAR(20) DEFAULT 'review'.
- `users` table (extended): `loyalty_tier` VARCHAR(10) DEFAULT 'bronze', `loyalty_tier_calculated_at` TIMESTAMP.
- `orders` table (extended): `is_rescue_order` BOOLEAN DEFAULT false, `food_waste_saved_kg` DECIMAL(5,2), `co2_saved_g` INT, `eta_confidence_low` INT, `eta_confidence_high` INT, `eta_variance_factor` DECIMAL(3,2).
- `trust_audits` table (new): `id` UUID PK, `restaurant_id` UUID FK → `restaurants.id`, `audit_type` VARCHAR (rating_flag, photo_missing, license_expired), `status` VARCHAR (open, resolved), `created_at` TIMESTAMP, `resolved_at` TIMESTAMP.
- `loyalty_benefits` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `tier` VARCHAR, `benefit_type` VARCHAR (monthly_discount, free_delivery, cashback, surprise_reward), `value` DECIMAL(10,2), `used_at` TIMESTAMP NULL.
- `user_sustainability_stats` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `total_rescue_orders` INT DEFAULT 0, `total_food_waste_saved_kg` DECIMAL(8,2) DEFAULT 0, `total_co2_saved_g` INT DEFAULT 0, `current_month_kg` DECIMAL(8,2) DEFAULT 0, `current_month_co2_g` INT DEFAULT 0, `updated_at` TIMESTAMP.
- `group_order_restaurants` table (new): `id` UUID PK, `group_order_id` UUID FK → `group_orders.id`, `restaurant_id` UUID FK → `restaurants.id`, `subtotal` DECIMAL(10,2), `delivery_fee` DECIMAL(10,2), `status` VARCHAR DEFAULT 'open'.
- `support_tickets` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `order_id` UUID FK → `orders.id` NULL, `type` VARCHAR, `status` VARCHAR DEFAULT 'open', `created_at` TIMESTAMP, `resolved_at` TIMESTAMP.
- Seed data requirements:
  - Historical orders: minimum 100 orders across 5 restaurants for meaningful analytics.
  - FSSAI numbers for 100% of restaurants. Kitchen photo URLs for 80% of restaurants. 2-3 restaurants with missing photos or low ratings for trust demo.
  - User order history with varying 90-day spend to demonstrate tier distribution (some Bronze, some Silver, some Gold).
  - Rescue orders in historical data for sustainability leaderboard population.
  - Order statuses in all stages for ETA variance demo.

## 12. Role / Permission Coverage

- `customer` (logged-in): Can view delivery confidence, trust badges, loyalty card, sustainability stats, participate in multi-restaurant group carts, use support AI, create support tickets.
- Guest (unauthenticated): Can view public trust badges and delivery confidence. Cannot access loyalty, sustainability, group cart participation (except via invite if supported), or support AI.
- `restaurant_owner`: Can access `/owner/insights` for their own restaurant only. Can upload kitchen photo. Cannot view other restaurants' insights.
- `home_chef`: Same as restaurant_owner for insights and trust badges.
- `delivery_partner`: Not involved in ND.09 features except driver location data used in confidence score and support AI responses.
- `admin`: Can access `/admin/trust` dashboard. Can create/resolve trust audits. Can trigger loyalty recalculation. Can view all support tickets.

## 13. Performance / Reliability / Security Coverage

### Performance
- Insights queries aggregate data over 30-90 days. With proper indexing on `orders.restaurant_id`, `orders.created_at`, `orders.status`, queries should complete in <100ms for up to 10,000 orders. For demo, aggregation is on-demand; production may cache daily snapshots.
- Confidence score calculation is entirely in-memory arithmetic with 2-3 SQL count queries (<20ms each).
- Trust badge query is a single `SELECT` on `restaurants` table (<5ms).
- Loyalty tier recalculation queries 90-day spend with indexed `orders.user_id` + `orders.created_at` (<30ms).
- Sustainability leaderboard queries top 10 with indexed `current_month_kg` (<10ms).
- Multi-restaurant group cart uses existing polling infrastructure (3s interval, stops on hidden tab).
- ETA range calculation is client-side arithmetic after single order fetch (<1ms).
- Support AI is pure keyword matching on a small dictionary (<1ms).

### Reliability
- Insights data freshness: computed from existing order data. No risk of stale data since queries are real-time.
- Confidence score fallback: if any factor query fails (e.g., driver count unavailable), use default values (driver_factor=50, queue_factor=50) and return score with a "Data Incomplete" warning.
- Trust loop reliability: if kitchen photo is missing, show "Not Verified" rather than crash. If FSSAI number is null, show "Unverified".
- Loyalty tier edge cases: if user has 0 orders, tier is Bronze. If rolling 90-day spend is exactly at threshold (e.g., ₹5,000), round down to Silver (thresholds are exclusive for upper bound of lower tier).
- Multi-restaurant checkout: if any restaurant sub-cart is empty, exclude it. If all sub-carts empty, reject checkout with 400.
- ETA range: if status is unknown, fall back to static single-number ETA. Range never shows negative or inverted values (low < high always enforced).
- Support AI: if message doesn't match any keyword, always fall back to "Contact Human Support" — never leave user without an action.

### Security
- Owner insights: strictly scoped to `restaurants` where `owner_id` matches JWT `sub`. Return 404 (not 403) for unauthorized access to prevent restaurant enumeration.
- Admin trust dashboard: accessible only to users with `role=admin`. Return 403 for non-admin.
- Kitchen photo uploads: validate file type (image/*) and size (<5MB) if real upload; for demo, validate URL string format.
- FSSAI license numbers: visible to all customers (public trust signal). Admin can verify/unverify.
- Support ticket creation: validate `order_id` belongs to the authenticated user unless admin is creating on behalf.
- Loyalty recalculation: can be triggered by user (for self) or admin (for all). Users cannot trigger recalculation for other users.
- Multi-restaurant group cart: same auth rules as single-restaurant group cart. Host must be logged-in.
- CSV export: same auth as insights endpoint. No sensitive customer PII in export (anonymize user identifiers).

## 14. Novelty / Differentiation Coverage

At score 9, differentiation is about **operational moats** — features that competitors cannot replicate without significant data, integration, and operational investment.

- **Restaurant Insights Dashboard:** Data moat. Competitors need months of order history to build comparable analytics. BhojanGo's insights are restaurant-facing, not just internal — this builds restaurant loyalty. Export to CSV makes it actionable.
- **Delivery Confidence Score:** Operational transparency moat. No competitor exposes the internal operational factors affecting delivery. This builds customer trust and sets realistic expectations. The rule-based approach is demo-safe but mimics real ML scoring.
- **Customer Trust Loop:** Regulatory + social moat. FSSAI verification, kitchen photo proof, and rating audits create a three-layer verification that requires operational coordination. Admin dashboard creates ongoing enforcement. This is not a one-time badge — it's a living system.
- **Loyalty Tiers — Full Depth:** Switching cost moat. Once a user reaches Gold or Platinum, the accumulated benefits (free delivery, cashback, surprise rewards) make switching platforms economically painful. Auto-calculation removes friction. Progress bar creates goal-directed behavior.
- **Meal Rescue Ecosystem:** Brand authenticity moat. Most competitors have flash sales. BhojanGo frames it as sustainability with quantified CO₂ savings, leaderboards, and shareable badges. This creates emotional connection and organic social marketing.
- **Multi-Restaurant Group Cart:** Social + operational moat. Group ordering is already a lock-in feature (ND.06). Multi-restaurant extends it to complexity that competitors haven't solved (fee splitting, consolidated receipt, multi-restaurant coordination). Friends can order from different cravings in one session.
- **Predictive ETAs with Confidence Bands:** Expectation-setting moat. Single-number ETAs are often wrong, creating disappointment. Confidence bands set honest expectations and narrow as certainty increases. This is a UX differentiator that builds long-term trust.
- **Rule-Based Support AI:** Operational efficiency moat. Automating the top 3-4 support intents (where is my order, wrong item, cancel) reduces human support costs. It also resolves issues faster than email/ticket workflows. The rule-based approach is reliable and predictable — no hallucinations.

**Differentiators deferred to higher scores / production:**
- Real ML-based confidence scoring (ND.10 — requires production data volume).
- Real-time driver GPS in support AI responses (PR.07+ — Mapbox integration).
- Real multi-party payment split (PR.09+ — payment infrastructure).
- Advanced NLP for support (ND.10 — external AI API).
- Real-time WebSocket for multi-restaurant group cart (PR.08+).

## 15. Implementation Work Items

### IP.ND.09.001 — Restaurant Insights Dashboard (Backend + Data)
- **Category:** Backend + Data
- **Implementation Scope:** Create `GET /api/v1/restaurants/{id}/insights` endpoint. Queries:
  - Peak hours: `SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) FROM orders WHERE restaurant_id=$1 AND created_at >= NOW()-INTERVAL '30 days' GROUP BY hour`.
  - Top items: `SELECT menu_item_id, name, SUM(quantity), SUM(quantity*unit_price) FROM order_items JOIN menu_items ON ... WHERE restaurant_id=$1 GROUP BY menu_item_id ORDER BY SUM(quantity) DESC LIMIT 10`.
  - Customer retention: `COUNT(DISTINCT CASE WHEN order_count > 1 THEN user_id END) / COUNT(DISTINCT user_id)` over 90 days.
  - AOV trend: `SELECT DATE(created_at), AVG(total_amount) FROM orders WHERE restaurant_id=$1 AND created_at >= NOW()-INTERVAL '30 days' GROUP BY DATE(created_at)`.
  - Cuisine breakdown: computed from `restaurants.cuisine_types` + order counts.
  - Repeat customer percentage: `COUNT(DISTINCT repeat_users) / COUNT(DISTINCT all_users)` over 30 days.
  - `GET /api/v1/restaurants/{id}/insights/export?format=csv` — Python `csv.writer` output.
- **Acceptance Criteria:**
  1. Endpoint returns all 6 metrics for an authenticated owner's restaurant.
  2. Unauthorized access returns 404.
  3. CSV export contains all metrics in tabular form.
  4. Queries complete in <200ms with 1,000 orders.
- **Evidence Required:** `curl` output for insights endpoint. CSV file content sample. DB query timing.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.002 — Restaurant Insights Dashboard (Frontend)
- **Category:** Frontend
- **Implementation Scope:** Owner dashboard (`/owner/insights`) with:
  - Peak Hours: CSS bar chart or Recharts bar chart.
  - Top Items: ranked table.
  - Retention Rate: large KPI card.
  - AOV Trend: line chart with 7/30-day toggle.
  - Cuisine Breakdown: pie/donut chart.
  - Repeat Customers: KPI card + top customers table.
  - Export CSV button.
- **Acceptance Criteria:**
  1. All 6 metrics render with correct data from API.
  2. Charts are responsive and readable on mobile.
  3. Time range toggle works.
  4. Export button downloads a valid CSV file.
- **Evidence Required:** Screenshots: insights dashboard on desktop and mobile. CSV file opened in spreadsheet.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.09.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.003 — Delivery Confidence Score (Backend)
- **Category:** Backend
- **Implementation Scope:** Create `GET /api/v1/orders/confidence` endpoint. Compute rule-based score (0-100) from:
  - `driver_factor` = min(100, active_drivers_within_3km × 20).
  - `queue_factor` = max(0, 100 - queue_size × 15).
  - `weather_factor` = 100 (clear), 70 (rain), 40 (storm). Accept `?weather=clear|rain|storm` for demo.
  - `distance_factor` = max(0, 100 - distance_km × 8).
  - `traffic_factor` = 100 (off-peak), 75 (peak: 12-14, 19-21).
  - Weighted sum formula. Return score, factors, message, color.
- **Acceptance Criteria:**
  1. Score is 0-100 inclusive.
  2. Factor breakdown sums to score within rounding tolerance.
  3. Green message for >=85, yellow for 60-84, red for <60.
  4. Changing distance or weather param changes score appropriately.
- **Evidence Required:** `curl` outputs for multiple scenarios (clear+close, rain+far, peak+busy).
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.004 — Delivery Confidence Score (Frontend)
- **Category:** Frontend
- **Implementation Scope:** Badge on restaurant detail and cart pages. Color-coded shield with score. Tap/click opens breakdown modal/bottom sheet with 5 factor progress bars and explanatory message.
- **Acceptance Criteria:**
  1. Badge visible with correct score and color.
  2. Breakdown shows all 5 factors with progress bars.
  3. Score updates when address/distance changes.
  4. Message matches score tier.
- **Evidence Required:** Screenshots: green badge, yellow badge, red badge, breakdown modal.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.09.003
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.005 — Customer Trust Loop (Backend + Data)
- **Category:** Backend + Data
- **Implementation Scope:**
  - Extend `restaurants`: `fssai_license_number`, `fssai_verified`, `kitchen_photo_url`, `kitchen_photo_uploaded_at`, `trust_status`.
  - Create `trust_audits` table.
  - `GET /api/v1/restaurants/{id}/trust` — returns trust indicators.
  - `POST /api/v1/admin/trust-audits` — admin creates audit.
  - `PATCH /api/v1/admin/trust-audits/{id}/resolve` — admin resolves.
  - `GET /api/v1/admin/trust-dashboard` — list all restaurants with trust status, filters.
  - Auto-flag logic: avg rating <3.5 → `audit_scheduled`; 3.5-3.9 → `review`; >=4.0 → `verified`.
- **Acceptance Criteria:**
  1. Trust endpoint returns all three indicators.
  2. Admin can create and resolve audits.
  3. Dashboard filters by status and shows photo age.
  4. Auto-flag correctly categorizes restaurants by rating.
- **Evidence Required:** `curl` outputs for trust endpoint and admin dashboard. DB query showing `trust_audits`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.006 — Customer Trust Loop (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Restaurant detail: three trust badges (FSSAI, Kitchen, Rating) in a row.
  - Tooltips/thumbnails on tap.
  - Admin trust dashboard (`/admin/trust`): sortable table with filters, action buttons (schedule audit, send reminder, resolve).
- **Acceptance Criteria:**
  1. Badges visible on all restaurant detail pages.
  2. Tooltip shows license number, photo age, and rating status.
  3. Admin dashboard lists all restaurants with correct trust status.
  4. Admin actions update status in real-time.
- **Evidence Required:** Screenshots: trust badges on restaurant detail, admin trust dashboard, audit creation modal.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.09.005
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.007 — Loyalty Tiers — Full Depth (Backend + Data)
- **Category:** Backend + Data
- **Implementation Scope:**
  - Extend `users`: `loyalty_tier`, `loyalty_tier_calculated_at`.
  - Create `loyalty_benefits` table.
  - `GET /api/v1/users/loyalty` — returns tier, benefits, progress, history.
  - `POST /api/v1/users/loyalty/recalculate` — computes 90-day spend, updates tier.
  - Tier rules: Bronze (₹0-999), Silver (₹1,000-4,999), Gold (₹5,000-14,999), Platinum (₹15,000+).
  - Benefit application:
    - Silver: ₹20 monthly coupon, auto-applied.
    - Gold: delivery_fee = 0 at checkout.
    - Platinum: 5% order total cashback to wallet + monthly surprise reward.
- **Acceptance Criteria:**
  1. User tier correctly calculated from 90-day spend.
  2. Silver users see ₹20 auto-discount.
  3. Gold users see ₹0 delivery fee.
  4. Platinum users receive 5% wallet credit on order completion.
  5. Recalculation updates tier within 1 second.
- **Evidence Required:** `curl` for loyalty endpoint. DB query showing tier distribution. Checkout screenshots showing applied benefits.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.008 — Loyalty Tiers — Full Depth (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Profile loyalty card: tier badge, progress bar, benefit list, history.
  - Cart/checkout: tier badge, applied benefit line item.
  - Tier upgrade toast with celebration animation.
- **Acceptance Criteria:**
  1. Loyalty card shows correct tier and progress.
  2. Checkout reflects tier benefits (free delivery, discount, cashback).
  3. Tier upgrade triggers toast.
  4. Benefits are clearly explained.
- **Evidence Required:** Screenshots: Bronze/Silver/Gold/Platinum profile cards. Checkout with applied benefits. Tier upgrade toast.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.09.007
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.009 — Meal Rescue — Full Ecosystem (Backend + Data)
- **Category:** Backend + Data
- **Implementation Scope:**
  - Extend `orders`: `is_rescue_order`, `food_waste_saved_kg`, `co2_saved_g`.
  - Create `user_sustainability_stats` table.
  - On rescue order completion: compute `food_waste_saved_kg = item_count × 0.15`; `co2_saved_g = (food_waste_saved_kg × 2500) + (miles_saved × 120)`.
  - `GET /api/v1/users/sustainability` — returns user stats.
  - `GET /api/v1/sustainability/leaderboard` — top 10 by `current_month_kg`.
- **Acceptance Criteria:**
  1. Rescue order includes computed waste and CO₂.
  2. User stats aggregate correctly.
  3. Leaderboard returns top 10 ordered by current month.
  4. Monthly stats reset on 1st of month (or simulated via admin trigger).
- **Evidence Required:** `curl` for sustainability and leaderboard. DB query showing aggregated stats.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.010 — Meal Rescue — Full Ecosystem (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Order confirmation: waste + CO₂ saved message.
  - Profile sustainability card: stats, progress ring, share button.
  - Share badge modal: generated image with text, download/copy.
  - Homepage "Sustainability Leaders" section.
- **Acceptance Criteria:**
  1. Confirmation shows rescue impact.
  2. Sustainability card displays accurate monthly stats.
  3. Share badge generates a downloadable image.
  4. Homepage leaderboard shows top 3 users.
- **Evidence Required:** Screenshots: order confirmation with impact, sustainability card, share badge modal, leaderboard section.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.09.009
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.011 — Group Cart — Multi-Restaurant (Backend + Data)
- **Category:** Backend + Data
- **Implementation Scope:**
  - Extend `group_orders`: `is_multi_restaurant` BOOLEAN.
  - Create `group_order_restaurants` table.
  - `POST /api/v1/group-orders` — support `is_multi_restaurant=true`.
  - `POST /api/v1/group-orders/{code}/restaurants/{id}/items` — add to sub-cart.
  - `GET /api/v1/group-orders/{code}` — return grouped by restaurant.
  - `POST /api/v1/group-orders/{code}/checkout` — validates sub-carts, creates order(s).
  - Split bill: equal split (grand_total / participants) or itemized split (sum per person's items + proportional fees per restaurant).
- **Acceptance Criteria:**
  1. Host can add items from multiple restaurants.
  2. Group cart groups items by restaurant with per-restaurant subtotals.
  3. Checkout creates valid order(s) with correct totals.
  4. Split bill calculates equal and itemized splits correctly across restaurants.
- **Evidence Required:** `curl` outputs for multi-restaurant group order creation, add item, view, checkout. DB query confirming `group_order_restaurants`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.06.001 (single-restaurant group order tables)
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.012 — Group Cart — Multi-Restaurant (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Group cart page: restaurant tabs/accordion. Each section: items, subtotal, delivery fee.
  - "Add Another Restaurant" modal.
  - Consolidated receipt: all restaurants, per-restaurant fees, grand total.
  - Checkout: single place order button. Confirmation: multi-restaurant cards.
- **Acceptance Criteria:**
  1. Group cart shows items grouped by restaurant.
  2. User can add another restaurant mid-session.
  3. Consolidated receipt is accurate.
  4. Confirmation shows all restaurants with individual ETAs.
- **Evidence Required:** Screenshots: group cart with 2 restaurants, add restaurant modal, consolidated receipt, confirmation screen.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.09.011
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.013 — Predictive ETAs with Confidence Bands (Backend)
- **Category:** Backend
- **Implementation Scope:**
  - Extend `orders`: `eta_confidence_low`, `eta_confidence_high`, `eta_variance_factor`.
  - `GET /api/v1/orders/{id}/eta` — computes range:
    - Base ETA = `avg_prep_minutes + (distance_km / 25 × 60) + queue_penalty`.
    - Variance factor by status: pending=0.20, confirmed=0.12, preparing=0.08, picked_up=0.05, out_for_delivery=0.02.
    - `low = round(base × (1 - factor))`, `high = round(base × (1 + factor))`.
  - If status unknown, fallback to static ETA single number.
- **Acceptance Criteria:**
  1. Range is valid: low < high, both positive.
  2. Range narrows as status progresses (pending has widest, out_for_delivery narrowest).
  3. Range updates within 1 second of status change.
  4. Fallback works for unknown status.
- **Evidence Required:** `curl` outputs for same order at different statuses showing narrowing range.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.014 — Predictive ETAs with Confidence Bands (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Restaurant detail: "Delivery in {low}-{high} min" instead of single number.
  - Order tracking: dynamic range display. Visual indicator showing range narrowing.
- **Acceptance Criteria:**
  1. ETA shown as range on restaurant detail and tracking.
  2. Range narrows visibly as order progresses through demo.
  3. Final stage shows very narrow range (e.g., 38-39 min).
  4. Range text is readable and not confusing.
- **Evidence Required:** Screenshots: restaurant detail with range, tracking at pending vs preparing vs out_for_delivery.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.09.013
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.015 — Rule-Based Support AI (Backend)
- **Category:** Backend
- **Implementation Scope:**
  - Create `support_tickets` table.
  - `POST /api/v1/support/ai-chat` — keyword router:
    - "where", "status", "track" → where_is_order response with driver location + ETA.
    - "wrong", "missing", "incorrect" → wrong_item response with refund flow link.
    - "cancel", "stop" → cancel_request response with cancel action (if allowed).
    - Default → human support ticket creation prompt.
  - `POST /api/v1/support/tickets` — human ticket creation.
  - Responses include `type`, `response` text, and `actions` array (buttons/links).
- **Acceptance Criteria:**
  1. Keyword "where is my order" returns driver location + ETA.
  2. Keyword "wrong item" returns refund flow link.
  3. "Cancel" returns cancel action only if status is pending or confirmed.
  4. Unknown message returns human support fallback.
  5. All responses include action buttons.
- **Evidence Required:** `curl` outputs for each intent type + fallback.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.016 — Rule-Based Support AI (Frontend)
- **Category:** Frontend
- **Implementation Scope:**
  - Expandable "Help" panel on order detail page.
  - Quick-action chips: "Where is my order?", "Wrong item received", "Cancel my order", "Contact support".
  - Chat-like message bubbles. Response cards with text + action buttons.
  - "Where is my order?" shows driver mini-map + ETA card.
  - "Wrong item" opens item selector + reason dropdown + refund request.
  - "Cancel" shows cancel button + refund estimate (if allowed) or disabled state with explanation.
- **Acceptance Criteria:**
  1. Help panel opens/closes smoothly.
  2. Quick-action chips trigger correct responses.
  3. Driver location visible on "where is my order" response.
  4. Refund flow opens with item checkboxes.
  5. Cancel button respects order status rules.
- **Evidence Required:** Screenshots: help panel closed/open, each quick-action response, refund flow, cancel disabled state.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.09.015
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.09.017 — Seed Data + Historical Data for ND.09
- **Category:** Data
- **Implementation Scope:**
  - Populate `restaurants` with `fssai_license_number` (100% coverage), `kitchen_photo_url` (80% coverage), `trust_status`.
  - Generate 100+ historical orders with varying `restaurant_id`, `user_id`, `status`, `created_at` for analytics and loyalty tier distribution.
  - Seed `user_sustainability_stats` for 10-20 users with varying rescue order counts.
  - Set `orders.is_rescue_order=true` for ~10% of historical orders.
  - Create order status history across all stages for ETA demo.
  - Ensure some restaurants have avg rating <3.5 and missing kitchen photos for trust loop demo.
- **Acceptance Criteria:**
  1. All restaurants have FSSAI numbers.
  2. 80% have kitchen photos.
  3. 2-3 restaurants have missing photos and low ratings.
  4. 100+ historical orders exist for analytics.
  5. Users have distributed 90-day spend (Bronze, Silver, Gold examples).
  6. Sustainability stats populated for leaderboard.
- **Evidence Required:** DB query outputs confirming populations.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Restaurant insights API returns peak hours, top items, retention rate, AOV trend, cuisine breakdown, and repeat customer percentage.
- [ ] Restaurant insights frontend renders charts, tables, KPIs, and CSV export.
- [ ] Delivery confidence API returns 0-100 score with 5-factor breakdown.
- [ ] Delivery confidence badge is color-coded and clickable for breakdown.
- [ ] Trust loop backend exposes FSSAI, kitchen photo, and rating audit status.
- [ ] Trust loop frontend shows three badges on restaurant detail.
- [ ] Admin trust dashboard lists all restaurants with filters and actions.
- [ ] Loyalty tier API calculates tiers from 90-day spend correctly.
- [ ] Loyalty benefits apply automatically: Silver ₹20 off, Gold free delivery, Platinum 5% cashback.
- [ ] Loyalty frontend shows tier badge, progress bar, and applied benefits.
- [ ] Meal rescue backend computes food waste saved and CO₂ saved per order.
- [ ] Meal rescue frontend shows confirmation message, sustainability card, share badge, and leaderboard.
- [ ] Multi-restaurant group cart backend supports adding items from multiple restaurants.
- [ ] Multi-restaurant group cart frontend groups items by restaurant with per-restaurant fees and consolidated receipt.
- [ ] Predictive ETA backend returns narrowing confidence bands based on order status.
- [ ] Predictive ETA frontend shows range "{low}-{high} min" that narrows as order progresses.
- [ ] Rule-based support AI backend routes keywords to correct responses with actions.
- [ ] Rule-based support AI frontend shows help panel, quick actions, driver map, refund flow, and cancel logic.
- [ ] Seed data fully supports all ND.09 features (analytics, trust, loyalty, sustainability, ETA variance).
- [ ] All new UI follows BhojanGo design system, is responsive, and supports dark mode.
- [ ] All features are LOCAL/DEMO-SAFE (no external AI APIs, no blockchain, no real weather/traffic APIs).

## 17. Evidence Required

- Screenshots:
  - Owner insights dashboard with peak hours chart, top items table, retention KPI, AOV line chart, cuisine pie chart, repeat customers table.
  - Insights CSV file opened in a spreadsheet.
  - Delivery confidence green badge (>=85), yellow badge (60-84), red badge (<60).
  - Confidence breakdown modal with 5 factor progress bars.
  - Restaurant detail trust badges: FSSAI Verified, Kitchen Verified, Rating Audit.
  - Trust badge tooltips showing license number and photo age.
  - Admin trust dashboard with flagged restaurants.
  - Profile loyalty cards: Bronze, Silver, Gold, Platinum.
  - Checkout showing Gold free delivery, Silver monthly discount, Platinum cashback.
  - Tier upgrade toast.
  - Order confirmation with rescue impact message.
  - Profile sustainability card with monthly stats and progress ring.
  - Share badge modal with generated image.
  - Homepage sustainability leaderboard.
  - Multi-restaurant group cart with two restaurant tabs.
  - Add Another Restaurant modal.
  - Consolidated receipt with per-restaurant fees.
  - Restaurant detail showing "Delivery in 28-35 min".
  - Order tracking showing narrowing range: pending (32-42), preparing (35-40), out_for_delivery (38-39).
  - Support help panel with quick-action chips.
  - "Where is my order" response with driver location.
  - "Wrong item" refund flow with item checkboxes.
  - "Cancel" button enabled (pending) and disabled (picked up) states.
- Screen recordings:
  - Owner navigates to insights → views charts → exports CSV.
  - Customer changes address and watches confidence score update.
  - Customer views trust badges on two restaurants (verified vs flagged).
  - User places order, reaches Gold tier, sees upgrade toast, places second order with free delivery.
  - User places rescue order, views sustainability card, generates share badge.
  - Host starts multi-restaurant group order → adds two restaurants → friend adds item → split bill → checkout.
  - Order tracking from pending to out_for_delivery with ETA range narrowing.
  - User opens support AI, asks "where is my order", then "wrong item", then tries to cancel picked-up order.
- API evidence:
  - `curl` for `GET /api/v1/restaurants/{id}/insights`.
  - `curl` for `GET /api/v1/restaurants/{id}/insights/export`.
  - `curl` for `GET /api/v1/orders/confidence` with varying params.
  - `curl` for `GET /api/v1/restaurants/{id}/trust`.
  - `curl` for admin trust dashboard endpoints.
  - `curl` for `GET /api/v1/users/loyalty`.
  - `curl` for `POST /api/v1/users/loyalty/recalculate`.
  - `curl` for `GET /api/v1/users/sustainability`.
  - `curl` for `GET /api/v1/sustainability/leaderboard`.
  - `curl` for multi-restaurant group order creation, add item, view, checkout.
  - `curl` for `GET /api/v1/orders/{id}/eta` at multiple statuses.
  - `curl` for `POST /api/v1/support/ai-chat` with each intent.
- DB evidence:
  - `SELECT * FROM restaurants WHERE fssai_verified = true`.
  - `SELECT * FROM trust_audits`.
  - `SELECT loyalty_tier, COUNT(*) FROM users GROUP BY loyalty_tier`.
  - `SELECT * FROM user_sustainability_stats ORDER BY current_month_kg DESC LIMIT 10`.
  - `SELECT * FROM orders WHERE is_rescue_order = true`.

## 18. Dependencies

### External Tools
- PostgreSQL (for new tables and analytics queries).
- Node.js + pnpm (frontend build).
- Lucide React (icon library).
- Recharts or Chart.js (for insights charts).
- Existing TanStack Query or SWR (for data fetching).

### Internal Dependencies
- **PR.05+ must be complete:** Stable core ordering loop is prerequisite.
- **ND.06 must be complete:** Group ordering (single-restaurant), meal rescue (basic), office lunch mode, nutritional transparency, fee calculator, sustainability scores, and batching preview must be stable.
- **ND.08 must be complete:** Strong product identity (design system, trust badges, card anatomy, typography, dark mode) must be applied.
- **Auth persistence** must work for owner insights, admin dashboard, and loyalty.
- **Cart Zustand store** must support multi-restaurant grouping.
- **Order tracking page** must exist for ETA confidence bands.
- **Profile page** must exist for loyalty and sustainability cards.
- **Admin dashboard (`/admin`)** must exist for trust dashboard.
- **Toast/snackbar component** must exist for tier upgrades and rescue confirmations.
- **Modal/bottom sheet component** must exist for confidence breakdown, share badge, and refund flow.

## 19. Risks / Blockers

- **Analytics query performance:** Aggregating 90 days of orders with multiple JOINs could slow down on large datasets. Mitigation: add composite indexes on `(restaurant_id, created_at)` and `(user_id, created_at)`. For demo, data volume is small.
- **Confidence score realism:** Rule-based scoring is not truly predictive. It may not correlate with actual delivery outcomes. Mitigation: clearly label as "estimated confidence" and document the heuristic nature. Real ML scoring deferred to ND.10.
- **Trust loop enforcement:** Without real FSSAI API or kitchen photo AI, trust loop relies on owner self-reporting and admin review. This could be gamed. Mitigation: document as "demo trust system" and flag need for real verification in production.
- **Loyalty tier edge cases:** Rolling 90-day window means tier can fluctuate. A user at Gold (₹5,000+) could drop to Silver if they don't order for 90 days. This is correct behavior but may confuse users. Mitigation: show "Your Gold tier is secured until {date}" based on oldest qualifying order.
- **Multi-restaurant checkout complexity:** Creating multiple orders or a single multi-restaurant order requires careful handling of delivery assignments, fees, and status tracking. Mitigation: create one `orders` record per restaurant with a shared `group_order_id` for linking. Simple and traceable.
- **ETA range accuracy:** Hardcoded variance factors may not reflect real-world uncertainty. Mitigation: factors are tuned for demo plausibility. Document as simulated.
- **Support AI scope creep:** It's tempting to add more intents. Mitigation: strictly limit to 3 intents + fallback. No open-ended chat.
- **Seed data effort:** Creating 100+ realistic historical orders with correct statuses, amounts, and dates requires a robust seed script. Mitigation: use a Python or SQL seed generator with randomized but realistic values.

## 20. Exit Criteria

- All P0 work items (IP.ND.09.001 through IP.ND.09.017) implemented and verified.
- Restaurant insights complete: API + dashboard + CSV export.
- Delivery confidence complete: API + badge + breakdown.
- Customer trust loop complete: backend + badges + admin dashboard.
- Loyalty tiers complete: auto-calculation + benefits + frontend.
- Meal rescue ecosystem complete: CO₂ tracking + sustainability card + share badge + leaderboard.
- Multi-restaurant group cart complete: backend + frontend + consolidated receipt.
- Predictive ETAs complete: range calculation + frontend narrowing display.
- Rule-based support AI complete: backend routing + frontend panel + refund flow.
- Seed data fully supports all features.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.09 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.08)

ND.09 directly depends on ND.08 achievements:
- **ND.08 Strong Product Identity:** Design system (palette, typography, spacing, Lucide icons) must be applied to all new components (insights charts, confidence badges, trust badges, loyalty cards, sustainability UI).
- **ND.08 Trust Badges:** Basic "FSSAI Verified" and "Freshly Prepared" badges on restaurant cards must exist as the foundation for the full trust loop (license visibility, kitchen photo, rating audit).
- **ND.06 Group Ordering:** Single-restaurant group carts must be stable before multi-restaurant extension.
- **ND.06 Meal Rescue:** Basic end-of-day rescue deals must exist before adding sustainability quantification, leaderboards, and share badges.
- **ND.05 Loyalty System:** Basic loyalty points must be earned and visible before adding tier benefits and auto-calculation.
- **PR.05+ Core Loop:** Browse, menu, cart, checkout, tracking must all be functional.

## 22. Connected Next-Level Requirements (link to ND.10)

ND.10 (Category-Leading Experience, score 10/10) builds on ND.09 and requires:
- Working restaurant insights (IP.ND.09.001–002) as foundation for AI-powered predictive analytics (demand forecasting, revenue prediction).
- Working delivery confidence (IP.ND.09.003–004) as foundation for real ML-based scoring using production data.
- Working trust loop (IP.ND.09.005–006) as foundation for automated compliance monitoring and third-party verification APIs.
- Working loyalty tiers (IP.ND.09.007–008) as foundation for personalized rewards and partner integrations.
- working meal rescue ecosystem (IP.ND.09.009–010) as foundation for carbon offset partnerships and verified sustainability reporting.
- Working multi-restaurant group cart (IP.ND.09.011–012) as foundation for corporate meal programs and invoicing.
- Working predictive ETAs (IP.ND.09.013–014) as foundation for ML-driven ETA models and proactive delay notifications.
- Working support AI (IP.ND.09.015–016) as foundation for advanced NLP and full chatbot integration.

ND.10 will introduce:
- ML-based recommendation engine using order history, weather, time, and location.
- Real-time traffic and weather API integration for confidence scoring.
- Automated FSSAI verification and kitchen photo AI analysis.
- Personalized meal plans and subscription boxes.
- Full WebSocket real-time chat and group cart updates.
- Corporate meal program with invoicing and approval workflows.
- Advanced gamification with badges, streaks, and social challenges.

ND.10 will be blocked if:
- Insights queries are too slow for production data volume.
- Confidence score heuristic is visibly inaccurate.
- Trust loop lacks admin enforcement (audits not acted upon).
- Loyalty benefit application has bugs (wrong discounts applied).
- Multi-restaurant checkout loses items or miscalculates fees.
- ETA ranges are consistently wrong or confusing.
- Support AI fails to handle basic intents or leaves users stranded.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (9/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.08 + prior) described | Planner | ✅ |
| 4 | Target state (ND.09 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.09 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.09 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (8 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (7 extended/new tables) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why features create operational moats | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.09.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present (17 present) | Planner | ✅ |
| 17 | Work items cover: insights, confidence, trust, loyalty, rescue, multi-restaurant group cart, ETAs, support AI | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention query performance, score realism, trust enforcement, tier edge cases, checkout complexity, ETA accuracy, AI scope, seed effort | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.08) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.10) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: restaurant insights (API + frontend + export), delivery confidence (API + frontend), customer trust loop (backend + frontend + admin), loyalty tiers (backend + frontend), meal rescue ecosystem (backend + frontend + share badge), multi-restaurant group cart (backend + frontend), predictive ETAs (backend + frontend), rule-based support AI (backend + frontend), and seed data.
- 17 work items provide granular, independently implementable chunks.
- Acceptance criteria are concrete and verifiable with clear evidence requirements.
- Risks and blockers are grounded in known challenges: analytics query performance, heuristic scoring limitations, trust enforcement without real APIs, loyalty tier edge cases, multi-restaurant checkout complexity, ETA variance tuning, support AI scope containment, and seed data generation effort.
- Scope is strictly LOCAL/DEMO-SAFE: no external AI APIs, no blockchain, no real weather/traffic APIs, no real FSSAI verification, no production cron, no ML models, no WebSocket upgrade.
- The document maintains consistency with the ND.08 → ND.09 transition narrative and sets up ND.10 cleanly.
