# IP.ND.06 — Marketplace Specific Differentiation

## 1. Target Differentiation Score: 6/10

## 2. Score Meaning

Group ordering, office lunch mode, meal rescue deals, home-chef/community kitchen, nutrition/allergen info, and transparent fees are meaningfully integrated. At score 6, BhojanGo is no longer just a convenient food delivery app — it is a marketplace with social ordering, supply-side innovation, and transparency features that change how people order. Group ordering turns individual consumption into a social activity. Office lunch mode captures B2B demand. Meal rescue reduces waste while creating urgency-driven deals. Community kitchens unlock a new supply category. Nutritional transparency and fee calculators build trust. Sustainability scores and order batching previews signal a values-driven platform. These features are defensible — they require operational coordination, not just UI polish — and competitors either lack them or charge for them.

## 3. Current → Target Transition

**From ND.05 (retention-focused uniqueness):**
- The app has favorites, reorder, loyalty points (earned and visible), smart reorder suggestions, personalized homepage sections, and saved preferences.
- Filters, veg/non-veg visibility, category tabs, bestseller badges, and quick-add are all functional.
- Restaurant cards show cuisine chips, rating, delivery time, fee, trust badges, and open/closed status.
- Users can filter by dietary goal, price, rating, and delivery time.
- Loyalty tiers are visible but redemption is basic (delivery fee waivers only).
- **No group ordering exists.** Orders are strictly individual. There is no shareable cart link, no real-time collaborative cart, no split bill mechanism.
- **No office lunch mode.** No corporate group order, no budget limit enforcement, no recurring daily orders, no consolidated invoicing.
- **No meal rescue / end-of-day deals.** Unsold inventory is not discounted. No automatic flash sales before closing. No "Closing soon — X items at 50% off" badge.
- **No community kitchen / home chef marketplace.** All restaurants are commercial. There is no separate onboarding flow for home chefs, no lower commission tier, no chef profile with specialty and hygiene badge.
- **No nutritional transparency.** Menu items show name, price, description, and veg/non-veg status only. No calories, protein, carbs, fat. No allergen tags. No dietary goal filters (High Protein, Low Calorie, Keto, Vegan).
- **No transparent fee calculator.** Checkout shows a single total with no breakdown. No interactive distance slider. No "Why am I charged this?" explanation for platform fee or GST.
- **No sustainability score.** Restaurants have no eco-rating. No green leaf badge. No "Eco-friendly" filter.
- **No order batching preview.** Users do not know their order will be batched with nearby orders. No savings transparency. No emissions reduction messaging.

**Target at score 6:**
- **Group ordering is fully functional:** Host starts a group order, gets a shareable link with an 8-character invite code. Friends open the link, join the group cart, and add items in real-time (short polling 3s). Each item shows attribution: "John added Paneer Tikka." Split bill option at checkout: equal split or item-by-item split. Host pays via single checkout. Everyone gets an order confirmation notification (in-app toast or mock push).
- **Office lunch mode is functional:** Corporate admin sets a group order, sets a per-person budget limit, and invites colleagues. Auto-suggests popular items from the office's order history and location. One-click repeat for recurring daily orders. Consolidated invoice receipt generated as a printable summary.
- **Meal rescue deals are live:** 1 hour before a restaurant's closing time, a backend cron job automatically identifies unsold inventory and creates "Rescue Meal — 50% off" deals. UI shows a badge on the restaurant card: "Closing soon — 3 items at 50% off." Nearby users receive a mock push notification (in-app banner) about the deal.
- **Community kitchen / home chef marketplace is live:** Separate onboarding for home chefs with lower commission (10% vs 20%). Home chefs appear in a dedicated section: "Home Chefs Near You." Chef profile shows photo, specialty, hygiene badge (FSSAI or self-certified), and rating. Chef has a mini-dashboard: orders today, revenue, simple menu management (add/edit/disable items).
- **Nutritional transparency is mandatory:** Every menu item shows calories, protein (g), carbs (g), fat (g). Expandable nutrition panel on item card and detail modal. Dietary goal filters: High Protein (>20g), Low Calorie (<400 kcal), Keto (<20g net carbs), Vegan. Allergen tags: Contains Dairy, Nuts, Gluten, Shellfish. Filters work on restaurant menu and search.
- **Transparent fee calculator is interactive:** Cart and checkout show a detailed fee breakdown: Items Subtotal, Delivery Fee (with distance slider showing fee change), Platform Fee, GST (18% / 5%), Discount, Grand Total. Each line item has an expandable "?" tooltip: "Why am I charged this?" with plain-language explanation. Slider for delivery distance simulates fee scenarios.
- **Sustainability score is visible:** Every restaurant has an eco-score (0-100) based on packaging type (biodegradable vs plastic), local sourcing claim, and veg menu ratio. Green leaf badge on cards for scores >= 70. "Eco-friendly" filter on restaurant list. Eco-score detail page explains the breakdown.
- **Order batching preview is transparent:** Before checkout, a banner shows: "Your order will be batched with ~2 nearby orders. This saves you ₹15 and reduces emissions by ~180g CO₂." Toggle to opt out: "Deliver mine first (no savings)." Batching context is mock/demo-safe — no real ML required.

## 4. Implementation Objective

Add social ordering, supply-side innovation, and transparency features that competitors either lack or charge for. These features make BhojanGo a marketplace, not just a middleman. Group ordering and office lunch mode create social lock-in and B2B revenue. Meal rescue and community kitchens unlock new supply categories and reduce waste. Nutritional transparency, fee calculators, and sustainability scores build trust and differentiate BhojanGo as a values-driven platform. Order batching preview educates users about efficiency and sets the stage for the full batch engine integration (ND.08+). All features are demo-safe: they work locally with seed data, mock notifications, and simulated cron jobs.

## 5. Scope

### 5.1 Group Ordering (Full)
- **Database:** New `group_orders` table (`id`, `host_user_id`, `restaurant_id`, `invite_code` VARCHAR(8) UNIQUE, `status` ENUM('open', 'locked', 'placed', 'cancelled'), `split_type` ENUM('equal', 'itemized'), `created_at`, `expires_at`). New `group_order_items` table (`id`, `group_order_id`, `user_id`, `menu_item_id`, `quantity`, `customizations` JSONB, `added_by_name`, `created_at`).
- **Backend:**
  - `POST /api/v1/group-orders` — host creates group order for a restaurant. Returns `{group_order_id, invite_code, shareable_link}`.
  - `GET /api/v1/group-orders/{invite_code}` — anyone with the code sees the group cart, restaurant info, and list of participants.
  - `POST /api/v1/group-orders/{invite_code}/items` — participant adds an item. Body: `{menu_item_id, quantity, customizations}`. Returns updated group cart.
  - `DELETE /api/v1/group-orders/{invite_code}/items/{item_id}` — participant removes their own item.
  - `POST /api/v1/group-orders/{invite_code}/lock` — host locks the cart, preventing further additions.
  - `POST /api/v1/group-orders/{invite_code}/checkout` — host places the order. Creates a single `orders` record with `group_order_id` FK. Payment is mock/simulated.
  - `GET /api/v1/group-orders/{invite_code}/split` — returns split summary: equal (grand_total / participant_count) or itemized (sum of each person's items + proportional fees).
- **Frontend:**
  - "Start Group Order" button on restaurant detail page. Opens modal: "Invite friends to order from {restaurant_name}."
  - Shareable link screen: shows 8-character code (e.g., `BG7X9K2P`), copy link button, WhatsApp/Share API mock.
  - Group cart page (`/group-order/{invite_code}`): live-updating cart (short polling every 3s) showing items with attribution: "{name} added {item_name} x{qty}". Participant list sidebar.
  - Split bill UI at checkout: toggle between "Split Equally" and "Split by Item". Shows what each person owes.
  - Host controls: "Lock Cart" button, "Place Order" button. Non-hosts cannot lock or checkout.
  - Real-time feel: optimistic UI on add, polling refreshes cart state.

### 5.2 Office Lunch Mode
- **Database:** New `office_groups` table (`id`, `admin_user_id`, `name`, `office_address`, `budget_limit_per_person` DECIMAL, `created_at`). New `office_orders` table (`id`, `office_group_id`, `restaurant_id`, `order_date`, `status`, `created_at`).
- **Backend:**
  - `POST /api/v1/office-groups` — create an office group.
  - `POST /api/v1/office-groups/{id}/orders` — admin starts a daily office order.
  - `GET /api/v1/office-groups/{id}/suggestions` — returns popular items from this office group's order history and nearby restaurants.
  - `POST /api/v1/office-groups/{id}/orders/{order_id}/repeat` — one-click repeat previous office order.
  - `GET /api/v1/office-groups/{id}/orders/{order_id}/invoice` — consolidated receipt with all participants, items, and totals. Printable HTML/PDF mock.
- **Frontend:**
  - "Office Lunch" section in profile/nav. Admin dashboard: create group, invite colleagues (email mock), set budget limit.
  - Daily order flow: admin picks restaurant, sees auto-suggestions ("Most ordered by your office: Butter Chicken, Veg Biryani"), invites colleagues to add items.
  - Budget enforcement: per-item addition checks running total against `budget_limit_per_person`. Warns: "This brings your total to ₹450/₹500 budget."
  - Recurring toggle: "Repeat every weekday" checkbox. Creates future `office_orders` records.
  - Consolidated invoice: printable summary page with company header, date, itemized list, participant names, and totals.

### 5.3 Meal Rescue / End-of-Day Deals
- **Backend:**
  - Cron job (simulated via `/api/v1/admin/trigger-rescue` for demo or actual cron every 15 min): scans restaurants where `closes_at` is within 60 minutes of current time. For each, checks `menu_items` with `daily_inventory > 0` and `rescue_deal_active = false`. Creates a "rescue deal": sets `rescue_price = price * 0.5`, `rescue_deal_active = true`, `rescue_deal_expires_at = closes_at`.
  - `GET /api/v1/restaurants?has_rescue_deals=true` — filters to restaurants with active rescue deals.
  - `GET /api/v1/restaurants/{id}/rescue-deals` — lists rescue menu items with original and discounted price.
- **Frontend:**
  - Restaurant card badge: "Closing soon — {N} items at 50% off" (orange pulsing badge).
  - Rescue deals section on homepage: "Rescue Meals Near You" horizontal scroll.
  - Mock push notification banner (in-app, top banner): "{Restaurant} has 3 unsold meals at 50% off — 45 min left!"
  - Restaurant detail: "Rescue Deals" tab showing discounted items with strike-through original price and red discount tag.

### 5.4 Community Kitchen / Home Chef Marketplace
- **Database:** Extend `restaurants` table: `restaurant_type` ENUM('commercial', 'home_chef'), `chef_name`, `chef_photo_url`, `chef_specialty`, `chef_hygiene_badge`, `chef_rating`, `chef_story` (text). Commission rate stored per restaurant (default 20% commercial, 10% home chef).
- **Backend:**
  - Separate onboarding endpoint: `POST /api/v1/chefs/register` — simplified flow: name, photo, specialty, hygiene certification upload (mock), menu items.
  - `GET /api/v1/chefs` — lists home chefs only, with profile summary.
  - Chef mini-dashboard endpoints: `GET /api/v1/chefs/me/orders-today`, `GET /api/v1/chefs/me/revenue`, `PATCH /api/v1/chefs/me/menu/{item_id}` (enable/disable, edit price).
- **Frontend:**
  - "Home Chefs Near You" section on homepage, below "Popular Restaurants."
  - Chef profile page: photo, name, specialty, hygiene badge (shield icon), rating, story text, menu items.
  - Chef dashboard (`/chef/dashboard`): simple cards — "Orders Today: 5", "Today's Revenue: ₹1,240", menu list with toggle switches (Active/Inactive) and edit buttons.
  - Restaurant list filter: "Commercial Only" / "Home Chefs Only" / "All".
  - Chef card anatomy: photo (circular, 64px), name, specialty tag, hygiene badge, rating, "View Menu" CTA.

### 5.5 Nutritional Transparency
- **Database:** Extend `menu_items` table: `calories` (INT), `protein_g` (DECIMAL), `carbs_g` (DECIMAL), `fat_g` (DECIMAL), `allergens` TEXT[] (e.g., `{dairy, nuts, gluten}`), `dietary_tags` TEXT[] (e.g., `{high_protein, low_calorie, keto, vegan}`).
- **Backend:** Ensure `GET /api/v1/restaurants/{id}/menu` returns all nutrition fields. Add `?dietary_goal=high_protein|low_calorie|keto|vegan` filter param.
- **Frontend:**
  - Nutrition panel on menu item card: collapsed by default. Expand icon (chevron) reveals: Calories, Protein, Carbs, Fat. Circular progress bars or simple bar charts for visual impact.
  - Allergen tags: small pills below item name: "Contains Dairy", "Contains Nuts", "Gluten-Free" (green if safe, red if contains). Uses Lucide icons: `Milk`, `Nut`, `WheatOff`.
  - Dietary goal filter chips on restaurant detail: "High Protein", "Low Calorie (<400)", "Keto", "Vegan". Clicking filters menu client-side.
  - Nutrition badge on item image: "320 kcal" small pill (optional, if not too cluttered).

### 5.6 Transparent Fee Calculator
- **Frontend (cart and checkout):**
  - Detailed fee breakdown card:
    - Items Subtotal: ₹{sum}
    - Delivery Fee: ₹{fee} — with small info icon tooltip: "Based on {distance} km. We pay riders for fuel and time."
    - Platform Fee: ₹{fee} — tooltip: "Helps us keep the app running and support our team."
    - GST (18% on food, 5% on delivery): ₹{tax} — tooltip: "Government-mandated tax. We collect and remit this."
    - Discount: -₹{amount} (if applicable)
    - Grand Total: ₹{total}
  - Interactive distance slider in cart: "Simulate delivery distance" slider from 1km to 10km. Dragging updates delivery fee in real-time. Shows formula: "₹25 base + ₹8/km."
  - "Why am I charged this?" expandable section at bottom of breakdown. Plain-language explanation for each fee type. Example: "Platform fee? That's how we pay engineers to keep the app from crashing at 1 PM."

### 5.7 Sustainability Score
- **Database:** Extend `restaurants` table: `eco_score` (INT, 0-100), `packaging_type` ENUM('biodegradable', 'recyclable', 'plastic'), `local_sourcing_percent` (INT), `veg_menu_ratio` (DECIMAL).
- **Backend:** `GET /api/v1/restaurants` includes `eco_score`. `?eco_friendly=true` filter for scores >= 70.
- **Frontend:**
  - Green leaf badge (`Lucide Leaf`) on restaurant cards with score >= 70. Badge tooltip: "Eco-Score: {score}/100 — {packaging_type} packaging, {local_sourcing_percent}% local sourcing."
  - "Eco-friendly" filter chip on restaurant list.
  - Eco-score detail on restaurant detail page: small section with score breakdown (packaging, local sourcing, veg ratio) and a progress bar.

### 5.8 Order Batching Preview
- **Frontend:**
  - Pre-checkout banner in cart: "Your order will be batched with ~2 nearby orders. This saves you ₹15 and reduces emissions by ~180g CO₂."
  - Toggle switch: "Deliver mine first (no savings)" — when ON, banner updates to show standard delivery fee (no batch discount).
  - Savings breakdown in fee calculator: "Batch savings: -₹15" line item when batching is active.
  - Mock batching logic: based on time of day (12 PM - 2 PM = high density, show 2-3 nearby orders; other times = 1 order or none). No real ML or geo-computation required for demo.
  - Emissions copy: "You've saved 180g CO₂ — that's like planting 0.01 trees!" (playful, gamified).

## 6. Out of Scope

- **AI / ML recommendations:** Personalized meal suggestions based on history, weather, or time. Deferred to ND.07+.
- **Real-time tracking map:** Live driver GPS with Mapbox/Leaflet. Deferred to PR.07+.
- **Observability stack:** Prometheus, Grafana, distributed tracing. Deferred to PR.07+.
- **CDN / S3 image hosting:** Local/images remain in Next.js public folder or local filesystem. Deferred to PR.08+.
- **FCM push notifications (real):** All notifications are in-app banners, toasts, or mock push UI. Real FCM integration is deferred to PR.06+.
- **Smart lockers / pickup points:** QR code, locker network, IoT integration. Deferred to ND.07+.
- **Voice ordering:** Web Speech API, NLP parsing. Deferred to ND.08+.
- **Real-time WebSocket for group cart:** Short polling (3s) is sufficient for demo. WebSocket upgrade deferred to PR.08+.
- **Actual payment split (multi-party payment intents):** Split bill is calculated and displayed, but payment is mocked/host-paid only. Real split payment deferred to PR.09+.
- **Real cron job infrastructure:** Meal rescue cron is either an admin trigger endpoint (`POST /api/v1/admin/trigger-rescue`) or a lightweight setInterval in dev. Production cron deferred to PR.08+.
- **Real hygiene certification verification:** Chef hygiene badge is self-reported/uploaded (mock). Third-party verification deferred to PR.09+.
- **Blockchain / carbon credit verification:** Eco-score is calculated from seed data, not verified on-chain.
- **Advanced batch engine integration:** Order batching preview is a UI mock with simple heuristics. Real batch engine wiring (delivery-svc, driver assignment) is deferred to ND.08+.

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.04 or PR.05 complete).
- Auth persistence must work. Group ordering requires logged-in host; participants can be guests or logged-in.
- Restaurant list API must support filtering by `restaurant_type`, `eco_score`, `has_rescue_deals`.
- Menu items API must return nutrition fields and allergen data.
- Cart Zustand store must support programmatic manipulation (for group order pre-fill, reorder, and batching toggle).
- Frontend short-polling infrastructure must exist (or be built) for group cart real-time updates.
- Design system (BhojanGo palette, typography, spacing, Lucide icons) must be applied across all new UI.
- Toast/snackbar component must exist for confirmations and notifications.
- Modal/bottom sheet component must exist for group order creation, split bill, and fee explanations.
- Seed data must include nutrition values, allergen lists, eco-scores, and home chef records.

## 8. Key User Journeys

### Journey 8.1 — Friends Order Lunch Together (Group Ordering)
1. Priya opens BhojanGo, browses to "Spice Garden" restaurant.
2. Taps "Start Group Order" on restaurant detail page.
3. Modal shows: "Group order created! Share this link with friends." Code: `BG7X9K2P`. Link: `/group-order/BG7X9K2P`.
4. Priya copies the link and shares it in her friends' WhatsApp group (mock).
5. Rahul opens the link. Sees the group cart (currently empty) and "Add Items" section.
6. Rahul adds "Paneer Tikka Masala x1" and "Garlic Naan x2". Group cart updates in real-time (polling).
7. On Priya's screen, she sees: "Rahul added Paneer Tikka Masala x1" and "Rahul added Garlic Naan x2."
8. Ananya joins and adds "Veg Biryani x1". All three see the updated cart with attribution.
9. Priya taps "Lock Cart" — no more items can be added.
10. Priya taps "Split Bill" — selects "Equal Split". Each person owes ₹187.
11. Priya taps "Place Order" — single checkout, mock payment. Order confirmation screen shows: "Group order placed! 3 people, 4 items."
12. Rahul and Ananya see in-app toast: "Priya placed the group order from Spice Garden."

### Journey 8.2 — Office Admin Sets Up Daily Lunch (Office Lunch Mode)
1. Ravi, office admin, navigates to "Office Lunch" in profile menu.
2. Creates "Acme Corp Bangalore" office group. Sets budget limit: ₹500 per person. Adds office address.
3. Ravi starts today's order, picks "Biryani House" from suggestions.
4. System auto-suggests: "Your office often orders: Chicken Biryani, Veg Biryani, Raita."
5. Ravi invites 5 colleagues via shareable link. Each colleague opens the link and adds items.
6. Colleague 2 tries to add a ₹550 item — warning appears: "This exceeds the ₹500/person budget. Remove an item or proceed at your own cost."
7. Ravi enables "Repeat every weekday" toggle.
8. At checkout, Ravi sees consolidated total: "6 people, 8 items, ₹2,840 total."
9. Order placed. Ravi navigates to "Invoices" and downloads today's invoice: PDF mock with company header, date, itemized list, participant names, totals.
10. Next day at 11 AM, Ravi gets an in-app reminder: "Today's office lunch from Biryani House is ready to repeat. Tap to confirm."

### Journey 8.3 — User Discovers Meal Rescue Deal
1. User opens BhojanGo at 8:45 PM. Homepage shows "Rescue Meals Near You" section.
2. Card: "Domino's — Closing soon — 3 items at 50% off!" with pulsing orange badge.
3. User taps the card. Restaurant detail shows a "Rescue Deals" tab.
4. Tab lists: "Margherita Pizza — was ₹299, now ₹150", "Garlic Bread — was ₹149, now ₹75".
5. User adds Margherita to cart. Standard checkout applies. Total reflects rescue price.
6. At 9:30 PM (after closing), rescue deals disappear from the UI. Cart items keep rescue price if already added.

### Journey 8.4 — Health-Conscious User Filters by Nutrition
1. User navigates to a restaurant detail page. Sees "High Protein", "Low Calorie", "Keto", "Vegan" filter chips above the menu.
2. Taps "High Protein" — menu filters to items with >20g protein. Paneer dishes, chicken items, dal remain.
3. User opens "Paneer Tikka Masala" item card. Sees "Contains Dairy" and "Contains Nuts" allergen pills in red.
4. Taps expand on nutrition panel: "Calories: 420 | Protein: 24g | Carbs: 18g | Fat: 28g".
5. User taps "Vegan" filter — paneer disappears, only plant-based items remain.
6. User adds a vegan item to cart with confidence.

### Journey 8.5 — User Explores Home Chef Section
1. User scrolls homepage, sees "Home Chefs Near You" section with 4 chef cards.
2. Taps "Asha's Kitchen" — chef profile shows: circular photo of Asha, "Specialty: North Indian Thalis", hygiene badge "Self-Certified Clean Kitchen", rating 4.7.
3. Chef story: "I cook with love using ingredients from my own garden."
4. Menu shows Thali options at lower prices than commercial restaurants.
5. User adds "Veg Thali" to cart. Checkout shows 10% commission note (vs 20% for commercial).
6. Taps a different chef profile. Sees "Orders Today: 8 | Revenue: ₹1,840" in a mini-dashboard preview.

### Journey 8.6 — User Checks Fee Breakdown Before Paying
1. User has 3 items in cart. Opens `/cart`.
2. Sees detailed breakdown:
   - Items Subtotal: ₹640
   - Delivery Fee: ₹45 — user taps "?" → tooltip: "Based on 4.2 km. We pay riders for fuel and time."
   - Platform Fee: ₹15 — tooltip: "Helps us keep the app running."
   - GST: ₹32 — tooltip: "18% on food, 5% on delivery. Government-mandated."
   - Discount (WELCOME20): -₹128
   - Grand Total: ₹604
3. User drags "Simulate distance" slider from 4km to 8km. Delivery fee updates from ₹45 to ₹77 in real-time.
4. User taps "Why am I charged this?" — expandable section shows plain-language explanations for each fee.
5. User feels informed and taps "Proceed to Checkout."

### Journey 8.7 — Eco-Conscious User Filters by Sustainability
1. User on restaurant list, taps "Eco-friendly" filter chip.
2. List filters to 12 restaurants with green leaf badges.
3. Taps a restaurant card, sees badge tooltip: "Eco-Score: 82/100 — Biodegradable packaging, 60% local sourcing."
4. On restaurant detail, scrolls to "Sustainability" section: score breakdown with progress bars for packaging, sourcing, and veg ratio.
5. User chooses this restaurant partly because of its eco-credentials.

### Journey 8.8 — User Sees Batching Preview and Saves Money
1. User adds items to cart at 12:30 PM. Cart banner appears: "Your order will be batched with ~2 nearby orders. This saves you ₹15 and reduces emissions by ~180g CO₂."
2. User is curious, toggles "Deliver mine first (no savings)." Banner updates: "Standard delivery — no batch discount. Delivery fee: ₹60."
3. User toggles back to batching. Delivery fee drops to ₹45. New line item in breakdown: "Batch savings: -₹15."
4. User proceeds to checkout, sees the savings applied, and feels good about the eco-benefit.

## 9. Technical Coverage

### Backend
- **order-svc or new group-order-svc:** `group_orders` and `group_order_items` table CRUD. Endpoints: create, join-by-code, add item, remove item, lock, checkout, split summary. Auth: host must be logged-in; participants can be guests (tracked by session ID) or logged-in (tracked by user ID).
- **restaurant-svc:** Extend `GET /api/v1/restaurants` with filters: `?restaurant_type=home_chef`, `?eco_friendly=true`, `?has_rescue_deals=true`. Extend response to include `restaurant_type`, `eco_score`, `packaging_type`, `chef_name`, `chef_photo_url`, etc.
- **restaurant-svc:** `GET /api/v1/restaurants/{id}/rescue-deals` endpoint. `POST /api/v1/admin/trigger-rescue` admin endpoint to simulate cron.
- **restaurant-svc:** Extend menu item response to include `calories`, `protein_g`, `carbs_g`, `fat_g`, `allergens`, `dietary_tags`.
- **user-svc or new office-svc:** `office_groups` and `office_orders` table CRUD. Endpoints: create group, start order, get suggestions, repeat order, get invoice.
- **chef-svc or extend restaurant-svc:** `POST /api/v1/chefs/register`, `GET /api/v1/chefs`, `GET /api/v1/chefs/me/orders-today`, `GET /api/v1/chefs/me/revenue`, `PATCH /api/v1/chefs/me/menu/{item_id}`.
- **order-svc:** Extend order creation to support `group_order_id` FK. On group checkout, create single order with aggregated items.

### Frontend
- **Zustand store extensions:** `groupOrderStore` (invite code, cart items, participants, polling state, lock status). `officeLunchStore` (office group, active order, budget tracking). `batchingStore` (toggle state, mock nearby order count, savings calculation).
- **Components:**
  - `<GroupOrderModal />` — start group order, show invite code and link.
  - `<GroupCartPage />` — `/group-order/{code}` with live polling, attribution, participant list.
  - `<SplitBillModal />` — equal vs itemized toggle, per-person totals.
  - `<OfficeLunchDashboard />` — admin view for creating/managing office groups and orders.
  - `<OfficeOrderPage />` — daily order flow with budget enforcement.
  - `<RescueDealsSection />` — homepage horizontal scroll of rescue deals.
  - `<RescueBadge />` — pulsing orange "Closing soon" badge on restaurant cards.
  - `<ChefCard />` — circular photo, specialty, hygiene badge, rating.
  - `<ChefDashboard />` — orders today, revenue, menu management.
  - `<NutritionPanel />` — expandable calories, protein, carbs, fat with bars.
  - `<AllergenTags />` — red/green pills for allergens.
  - `<DietaryFilterChips />` — High Protein, Low Calorie, Keto, Vegan.
  - `<FeeBreakdown />` — line items with tooltips and expandable explanations.
  - `<DistanceSlider />` — interactive slider for delivery fee simulation.
  - `<EcoBadge />` — green leaf with score tooltip.
  - `<EcoScoreDetail />` — score breakdown with progress bars.
  - `<BatchingBanner />` — pre-checkout banner with toggle.
- **Hooks:** `useGroupOrderPolling(code, interval=3000)`, `useOfficeLunch(groupId)`, `useRescueDeals()`, `useNutritionFilter(items[], goal)`, `useBatchingPreview()`.

### Data
- New tables: `group_orders`, `group_order_items`, `office_groups`, `office_orders`.
- Extended `restaurants` table: `restaurant_type`, `eco_score`, `packaging_type`, `local_sourcing_percent`, `veg_menu_ratio`, `chef_name`, `chef_photo_url`, `chef_specialty`, `chef_hygiene_badge`, `chef_rating`, `chef_story`.
- Extended `menu_items` table: `calories`, `protein_g`, `carbs_g`, `fat_g`, `allergens`, `dietary_tags`, `daily_inventory`, `rescue_deal_active`, `rescue_price`, `rescue_deal_expires_at`.
- Seed data: add 3-5 home chef restaurants, populate nutrition fields for all items, set allergen arrays, assign eco-scores, configure `closes_at` for meal rescue demos.

## 10. UI / UX Coverage

- **Loading states:** Skeleton loaders for group cart, office lunch dashboard, chef profile, rescue deals section.
- **Error states:** "Invalid or expired group code" page with "Start New Group Order" CTA. "Office group not found" error. "No rescue deals available" empty state. Nutrition data missing: "Nutrition info not yet available for this item."
- **Empty states:** Empty group cart: "No items yet. Invite friends to add food!" with share CTA. Empty chef dashboard: "No orders today yet." Empty rescue deals: "No rescue deals right now. Check back after 8 PM!"
- **Success states:** Toast on group item add: "{item_name} added to group cart." Toast on group order placed: "Group order placed for {N} people!" Toast on rescue item add: "Rescue deal added — you saved ₹{amount}!"
- **Design system:** All new components follow BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons.
- **Responsive:** Group cart: stacked layout on mobile (cart above, participants below). Office lunch: full-width admin cards on mobile. Chef cards: 1 col mobile, 2 col tablet, 4 col desktop. Nutrition panel: full-width on mobile, inline on desktop. Fee breakdown: always full-width for readability.
- **Dark mode:** Rescue badge remains orange (semantic). Eco leaf remains green. Nutrition bars use distinct colors. Fee breakdown lines use muted borders.
- **Accessibility:** Group cart attribution uses `aria-label`: "{name} added {item}". Split bill toggle has `role="radiogroup"`. Nutrition panel uses `aria-expanded`. Fee tooltips use `role="tooltip"`. Allergen tags use `aria-label`: "Contains {allergen}".

## 11. Data / Model Coverage

- `group_orders` table (new): `id` UUID PK, `host_user_id` UUID FK → `users.id`, `restaurant_id` UUID FK → `restaurants.id`, `invite_code` VARCHAR(8) UNIQUE, `status` VARCHAR (open, locked, placed, cancelled), `split_type` VARCHAR (equal, itemized), `created_at` TIMESTAMP, `expires_at` TIMESTAMP (default created_at + 2 hours).
- `group_order_items` table (new): `id` UUID PK, `group_order_id` UUID FK, `user_id` UUID FK (nullable for guests), `session_id` VARCHAR (for guest tracking), `menu_item_id` UUID FK, `quantity` INT, `customizations` JSONB, `added_by_name` VARCHAR, `created_at` TIMESTAMP.
- `office_groups` table (new): `id` UUID PK, `admin_user_id` UUID FK → `users.id`, `name` VARCHAR, `office_address` TEXT, `budget_limit_per_person` DECIMAL(10,2), `created_at` TIMESTAMP.
- `office_orders` table (new): `id` UUID PK, `office_group_id` UUID FK, `restaurant_id` UUID FK, `order_date` DATE, `status` VARCHAR, `is_recurring` BOOLEAN, `created_at` TIMESTAMP.
- `restaurants` table (extended): `restaurant_type` VARCHAR (default 'commercial'), `eco_score` INT (default 50), `packaging_type` VARCHAR, `local_sourcing_percent` INT (default 0), `veg_menu_ratio` DECIMAL (default 0.5), `chef_name` VARCHAR, `chef_photo_url` VARCHAR, `chef_specialty` VARCHAR, `chef_hygiene_badge` VARCHAR, `chef_rating` DECIMAL(2,1), `chef_story` TEXT.
- `menu_items` table (extended): `calories` INT, `protein_g` DECIMAL(5,2), `carbs_g` DECIMAL(5,2), `fat_g` DECIMAL(5,2), `allergens` TEXT[], `dietary_tags` TEXT[], `daily_inventory` INT (default 100), `rescue_deal_active` BOOLEAN (default false), `rescue_price` DECIMAL(10,2), `rescue_deal_expires_at` TIMESTAMP.
- Seed data requirements: 3-5 home chef restaurants with complete chef profiles. Nutrition data for 100% of menu items. Allergen arrays for 100% of items. Eco-scores for 100% of restaurants. `closes_at` set for all restaurants to enable rescue deal demos.

## 12. Role / Permission Coverage

- `customer` (logged-in): Can host group orders, join group orders, create office groups, be office admin, add rescue deals to cart, use all filters, view all transparency features.
- Guest (unauthenticated): Can join group orders by invite code, add items to group cart, view rescue deals, use nutrition filters, view fee breakdown. Cannot host group orders, cannot create office groups, cannot be office admin.
- `restaurant_owner`: Can view group orders placed at their restaurant (if notified). Cannot manage group orders directly.
- `home_chef`: Has access to chef dashboard (`/chef/dashboard`). Can manage their own menu items. Cannot manage other chefs' menus.
- `delivery_partner`: Not involved in ND.06 features.
- `admin`: Can trigger rescue deals manually via `/api/v1/admin/trigger-rescue`. Can view all group orders, office orders, and chef registrations.

## 13. Performance / Reliability / Security Coverage

### Performance
- Group cart polling: 3-second interval is lightweight. Each poll is a single indexed query by `invite_code`. Expected <20ms. Polling stops when tab is hidden (using `document.visibilityState`).
- Nutrition filters are client-side (filtering <50 menu items) — instant, no API call.
- Rescue deal queries use indexed `rescue_deal_active` boolean + `closes_at` range — <10ms.
- Fee calculator is entirely client-side arithmetic — no network calls.
- Batching preview uses client-side heuristics (time-based) — no API call.

### Reliability
- Group order expiry: `expires_at` is 2 hours after creation. Expired codes return 410 with "This group order has expired." CTA to start a new one.
- Group order race conditions: item additions are independent inserts; no quantity conflicts since group cart is not inventory-reserved until checkout.
- Rescue deal expiry: `rescue_deal_expires_at` is checked on every read. Expired deals are auto-hidden. Cart items already added at rescue price keep that price.
- Office lunch budget enforcement: client-side warning + server-side validation on checkout. Server validation is authoritative.
- Chef menu management: edits apply immediately to `menu_items` table. In-flight orders use a snapshot of prices at order creation time (stored in `order_items` JSONB).
- Nutrition data fallback: if any nutrition field is NULL, panel shows "Nutrition info coming soon" instead of broken values.

### Security
- Group order invite codes are 8-character alphanumeric (e.g., `BG7X9K2P`). 36^8 combinations = ~2.8 trillion — unguessable by brute force in demo context.
- Only the host (matching `host_user_id`) can lock the cart and place the order. Server validates on every lock/checkout request.
- Participants can only delete their own items. Server validates `user_id` or `session_id` on delete.
- Office group admin: only `admin_user_id` can create orders, set budget, and generate invoices.
- Chef endpoints: chef can only modify `menu_items` where `restaurant_id` matches their own. Server enforces this via JWT claim or query filter.
- All new endpoints use existing auth middleware. No new auth patterns introduced.
- Fee calculator is client-side only — no sensitive payment data transmitted.

## 14. Novelty / Differentiation Coverage

At score 6, differentiation is about **marketplace-level features** that change the structure of ordering, not just convenience.

- **Group Ordering:** Social lock-in. Once a group of friends uses BhojanGo for group lunch, switching platforms requires everyone to agree. Item attribution adds social fun. Split bill removes the awkward "who owes what" conversation. No competitor has seamless in-app split billing for group food orders.
- **Office Lunch Mode:** B2B revenue stream. Corporate meal programs are high-value, high-frequency, and sticky. Budget enforcement and consolidated invoicing are operational necessities that competitors lack. Recurring orders create habit formation.
- **Meal Rescue:** Sustainability + urgency. Reduces food waste (environmental win) while creating flash-sale urgency (business win). The "closing soon" badge drives conversion. No major competitor has automated end-of-day rescue deals.
- **Community Kitchen / Home Chefs:** Supply-side differentiation. Home chefs offer unique, authentic food at lower prices. Lower commission (10% vs 20%) attracts supply that commercial kitchens can't match. Chef profiles and stories create emotional connection. This is not a feature — it's a new marketplace category.
- **Nutritional Transparency:** Trust + health. Health-conscious users are a growing segment. Competitors show calories at best; few show full macros, allergens, and dietary filters. This positions BhojanGo as a health-aware platform.
- **Transparent Fee Calculator:** Trust through education. Most platforms hide fee breakdowns or make them non-interactive. BhojanGo's distance slider and "Why am I charged this?" explanations turn a point of friction into a trust builder.
- **Sustainability Score:** Values-based filtering. Eco-conscious consumers actively seek sustainable options. The green leaf badge and filter make sustainability a discoverable, searchable attribute — not just marketing copy.
- **Order Batching Preview:** Efficiency education. Users see the tangible benefit of batching (₹15 savings, 180g CO₂ reduction). This sets the stage for the full batch engine (ND.08+) and creates positive associations with efficiency.

**Differentiators deferred to higher scores:**
- Real-time WebSocket group cart (ND.08+ — infrastructure upgrade).
- AI-powered group order suggestions ("John usually orders biryani — suggest it?") (ND.07+).
- Real multi-party payment split (ND.09+ — payment infrastructure).
- Advanced batch engine with ML (ND.08+).
- Real FCM push notifications (PR.06+).

## 15. Implementation Work Items

### IP.ND.06.001 — Group Order Tables + API
- **Category:** Backend + Data
- **Implementation Scope:** Create `group_orders` table (`id` UUID PK, `host_user_id` UUID FK, `restaurant_id` UUID FK, `invite_code` VARCHAR(8) UNIQUE, `status`, `split_type`, `created_at`, `expires_at`). Create `group_order_items` table (`id` UUID PK, `group_order_id` UUID FK, `user_id` UUID FK nullable, `session_id` VARCHAR, `menu_item_id` UUID FK, `quantity`, `customizations` JSONB, `added_by_name`, `created_at`). Add endpoints: `POST /api/v1/group-orders` (host creates, returns invite_code), `GET /api/v1/group-orders/{invite_code}` (view cart + participants), `POST /api/v1/group-orders/{invite_code}/items` (add item), `DELETE /api/v1/group-orders/{invite_code}/items/{item_id}` (remove own item), `POST /api/v1/group-orders/{invite_code}/lock` (host only), `POST /api/v1/group-orders/{invite_code}/checkout` (host only, creates single order), `GET /api/v1/group-orders/{invite_code}/split` (equal or itemized). Auth: host must be logged-in; participants can be guests (session_id) or logged-in (user_id).
- **Acceptance Criteria:**
  1. Host can create a group order and receives an 8-character invite code.
  2. Anyone with the code can view the group cart.
  3. Participants can add items; host sees attribution.
  4. Participants can remove only their own items.
  5. Only host can lock cart and place order.
  6. Split bill endpoint returns correct equal and itemized totals.
  7. Expired codes return 410.
- **Evidence Required:** `curl` outputs for all endpoints. DB query: `SELECT * FROM group_orders WHERE invite_code = 'BG7X9K2P'`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.002 — Group Order Frontend (Create, Share, Cart, Split)
- **Category:** Frontend
- **Implementation Scope:** "Start Group Order" button on restaurant detail page. Modal generates invite code and shareable link (`/group-order/{code}`). Group cart page: live-updating via `useGroupOrderPolling` (3s interval, stops on tab hidden). Shows items with attribution "{name} added {item}". Participant list sidebar. Host-only "Lock Cart" and "Place Order" buttons. Split bill modal: toggle between "Split Equally" and "Split by Item", shows per-person totals. Checkout creates single order. All participants see toast on order placed.
- **Acceptance Criteria:**
  1. Group order creation modal shows 8-char code and copyable link.
  2. Group cart updates in real-time when items are added by others.
  3. Item attribution shows who added each item.
  4. Host can lock cart and place order; non-hosts cannot.
  5. Split bill modal calculates equal and itemized splits correctly.
  6. All participants receive confirmation toast after checkout.
- **Evidence Required:** Screenshots: create modal, group cart with attribution, participant list, split bill modal. Screen recording: two browser tabs adding items to same group cart.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.06.001
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.003 — Office Lunch Mode Tables + API
- **Category:** Backend + Data
- **Implementation Scope:** Create `office_groups` table (`id` UUID PK, `admin_user_id` UUID FK, `name`, `office_address`, `budget_limit_per_person`, `created_at`). Create `office_orders` table (`id` UUID PK, `office_group_id` UUID FK, `restaurant_id` UUID FK, `order_date`, `status`, `is_recurring`, `created_at`). Endpoints: `POST /api/v1/office-groups`, `POST /api/v1/office-groups/{id}/orders`, `GET /api/v1/office-groups/{id}/suggestions` (returns popular items from order history + nearby restaurants), `POST /api/v1/office-groups/{id}/orders/{order_id}/repeat`, `GET /api/v1/office-groups/{id}/orders/{order_id}/invoice` (HTML/JSON mock, printable). Budget enforcement: server validates per-person total against `budget_limit_per_person` on checkout.
- **Acceptance Criteria:**
  1. Admin can create office group with budget limit.
  2. Admin can start daily order and see auto-suggestions.
  3. Colleagues can add items; budget warnings trigger appropriately.
  4. Repeat endpoint creates a new office order with same restaurant and items.
  5. Invoice endpoint returns structured data for all participants and totals.
- **Evidence Required:** `curl` outputs for all endpoints. DB query: `SELECT * FROM office_orders WHERE office_group_id = ?`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.004 — Office Lunch Mode Frontend
- **Category:** Frontend
- **Implementation Scope:** "Office Lunch" section in profile dropdown. Admin dashboard: create group, set budget, invite colleagues (email mock, link share). Daily order page: pick restaurant, view auto-suggestions, invite colleagues via link. Running budget tracker per person. "Repeat every weekday" toggle. Consolidated invoice page: printable HTML with company header, date, itemized list, participant names, totals.
- **Acceptance Criteria:**
  1. Office lunch dashboard visible in profile menu.
  2. Admin can create group and set per-person budget.
  3. Auto-suggestions populate based on mock order history.
  4. Budget warning appears when user exceeds limit.
  5. Invoice page shows consolidated summary with printable layout.
- **Evidence Required:** Screenshots: office lunch dashboard, daily order page with suggestions, budget warning, invoice page.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.06.003
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.005 — Meal Rescue Backend (Cron + Deals API)
- **Category:** Backend + Data
- **Implementation Scope:** Extend `menu_items` table: `daily_inventory`, `rescue_deal_active`, `rescue_price`, `rescue_deal_expires_at`. Add `POST /api/v1/admin/trigger-rescue` endpoint: scans restaurants where `closes_at` <= NOW() + 60 minutes. For each, finds items with `daily_inventory > 0` and `rescue_deal_active = false`. Sets `rescue_deal_active = true`, `rescue_price = price * 0.5`, `rescue_deal_expires_at = closes_at`. Add `GET /api/v1/restaurants?has_rescue_deals=true` and `GET /api/v1/restaurants/{id}/rescue-deals`. Rescue deals are read-only for customers; only admin can trigger.
- **Acceptance Criteria:**
  1. Admin trigger endpoint identifies restaurants closing within 60 minutes.
  2. Qualifying items get `rescue_deal_active = true` and `rescue_price = 50%` of original.
  3. `GET /rescue-deals` returns only active rescue items.
  4. Expired deals (past `closes_at`) are excluded from results.
  5. Filter `?has_rescue_deals=true` correctly narrows restaurant list.
- **Evidence Required:** `curl` outputs for trigger and rescue-deals endpoints. DB query: `SELECT * FROM menu_items WHERE rescue_deal_active = true`.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.006 — Meal Rescue Frontend (Badge + Section + Mock Push)
- **Category:** Frontend
- **Implementation Scope:** Homepage "Rescue Meals Near You" horizontal scroll section. Restaurant card badge: pulsing orange "Closing soon — {N} items at 50% off". Restaurant detail: "Rescue Deals" tab with strike-through original price and red discount tag. Mock push notification banner: top in-app banner "{Restaurant} has {N} unsold meals at 50% off — {M} min left!" visible when user opens app during rescue window.
- **Acceptance Criteria:**
  1. Homepage shows rescue deals section when active deals exist.
  2. Restaurant cards display pulsing rescue badge with correct item count.
  3. Rescue Deals tab shows discounted items with original price struck through.
  4. Mock push banner appears on app open during rescue window.
  5. Adding rescue item to cart uses rescue price.
- **Evidence Required:** Screenshots: homepage rescue section, restaurant card badge, rescue tab, mock push banner.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.06.005
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.007 — Community Kitchen / Home Chef Tables + API
- **Category:** Backend + Data
- **Implementation Scope:** Extend `restaurants` table: `restaurant_type` (default 'commercial'), `chef_name`, `chef_photo_url`, `chef_specialty`, `chef_hygiene_badge`, `chef_rating`, `chef_story`. Add `POST /api/v1/chefs/register` (simplified onboarding: name, photo URL mock, specialty, hygiene badge, story, menu items). Add `GET /api/v1/chefs` (list home chefs only). Add chef dashboard endpoints: `GET /api/v1/chefs/me/orders-today`, `GET /api/v1/chefs/me/revenue`, `PATCH /api/v1/chefs/me/menu/{item_id}`. Commission rate stored per restaurant: 10% for home_chef, 20% for commercial.
- **Acceptance Criteria:**
  1. Chef registration endpoint creates a restaurant with `restaurant_type = 'home_chef'`.
  2. `GET /api/v1/chefs` returns only home chefs with profiles.
  3. Chef dashboard endpoints return correct orders today and revenue.
  4. Chef can enable/disable menu items via PATCH.
  5. Commission rate is 10% for home chefs, 20% for commercial.
- **Evidence Required:** `curl` outputs for registration, chef list, and dashboard endpoints. DB query: `SELECT * FROM restaurants WHERE restaurant_type = 'home_chef'`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.008 — Community Kitchen / Home Chef Frontend
- **Category:** Frontend
- **Implementation Scope:** Homepage "Home Chefs Near You" horizontal scroll with `<ChefCard />` components. Chef profile page: circular photo, name, specialty tag, hygiene badge, rating, story text, menu items. Chef dashboard (`/chef/dashboard`): cards showing "Orders Today" and "Today's Revenue", menu list with toggle switches (Active/Inactive) and edit buttons. Restaurant list filter: "Commercial Only" / "Home Chefs Only" / "All". Commission note on checkout: "This order supports a home chef — platform fee is only 10%."
- **Acceptance Criteria:**
  1. Homepage shows Home Chefs section with 3-5 chef cards.
  2. Chef profile page shows all profile fields and menu.
  3. Chef dashboard shows orders, revenue, and menu management.
  4. Restaurant list filter works for all three types.
  5. Checkout shows reduced commission note for home chef orders.
- **Evidence Required:** Screenshots: homepage section, chef profile, chef dashboard, restaurant list filter, checkout commission note.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.06.007
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.009 — Nutritional Transparency (Data + Backend)
- **Category:** Backend + Data
- **Implementation Scope:** Extend `menu_items` table: `calories` (INT), `protein_g` (DECIMAL), `carbs_g` (DECIMAL), `fat_g` (DECIMAL), `allergens` (TEXT[]), `dietary_tags` (TEXT[]). Populate seed data for all items. Ensure `GET /api/v1/restaurants/{id}/menu` returns all nutrition fields. Add `?dietary_goal=high_protein|low_calorie|keto|vegan` filter to menu endpoint (server-side or client-side).
- **Acceptance Criteria:**
  1. All menu items have calories, protein, carbs, fat populated.
  2. All menu items have allergen arrays populated.
  3. Menu API returns nutrition data for every item.
  4. Dietary goal filter correctly narrows items.
  5. No NULL nutrition fields in seeded data.
- **Evidence Required:** DB query: `SELECT COUNT(*) FROM menu_items WHERE calories IS NULL`. Menu API response showing nutrition fields.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.010 — Nutritional Transparency Frontend (Panel + Filters + Allergens)
- **Category:** Frontend
- **Implementation Scope:** Expandable nutrition panel on menu item card: collapsed by default, chevron to expand. Shows Calories, Protein, Carbs, Fat with horizontal bar visuals. Allergen tags: red pills for "Contains Dairy", "Contains Nuts", etc.; green pill for "Gluten-Free" if safe. Dietary goal filter chips on restaurant detail: "High Protein", "Low Calorie (<400)", "Keto", "Vegan". Client-side filter of menu items. Nutrition badge (optional): "320 kcal" small pill on item image.
- **Acceptance Criteria:**
  1. Nutrition panel expands/collapses on every menu item.
  2. Allergen tags are visible and color-coded.
  3. Dietary filter chips work client-side.
  4. Nutrition data is accurate and matches seed values.
  5. Vegan filter correctly excludes dairy-containing items.
- **Evidence Required:** Screenshots: nutrition panel expanded, allergen tags, dietary filters active, vegan filter result.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.ND.06.009
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.011 — Transparent Fee Calculator Frontend
- **Category:** Frontend
- **Implementation Scope:** Detailed fee breakdown card in `/cart` and `/checkout`: Items Subtotal, Delivery Fee (with "?" tooltip), Platform Fee (with tooltip), GST (with tooltip), Discount, Grand Total. Interactive distance slider: "Simulate delivery distance" from 1km to 10km, updates delivery fee in real-time (formula: base ₹25 + ₹8/km). "Why am I charged this?" expandable section with plain-language explanations for each fee type.
- **Acceptance Criteria:**
  1. Fee breakdown shows all line items with correct math.
  2. Each line item has an expandable tooltip explanation.
  3. Distance slider updates delivery fee in real-time.
  4. "Why am I charged this?" section expands with plain-language text.
  5. Grand total matches sum of all line items.
- **Evidence Required:** Screenshots: fee breakdown, tooltip expanded, distance slider at 4km and 8km, "Why am I charged this?" expanded.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.012 — Sustainability Score (Data + Backend + Frontend)
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Extend `restaurants` table: `eco_score` (0-100), `packaging_type`, `local_sourcing_percent`, `veg_menu_ratio`. Calculate `eco_score` in seed data: `packaging_type='biodegradable' ? 40 : packaging_type='recyclable' ? 25 : 10` + `local_sourcing_percent * 0.3` + `veg_menu_ratio * 20`. `GET /api/v1/restaurants` includes `eco_score` and supports `?eco_friendly=true` (score >= 70). Frontend: green leaf badge (`Lucide Leaf`) on cards with score >= 70. Badge tooltip shows breakdown. "Eco-friendly" filter chip. Restaurant detail: "Sustainability" section with score and progress bars for packaging, sourcing, veg ratio.
- **Acceptance Criteria:**
  1. All restaurants have `eco_score` populated.
  2. Filter `?eco_friendly=true` returns only restaurants with score >= 70.
  3. Green leaf badge visible on qualifying restaurant cards.
  4. Tooltip shows score breakdown.
  5. Sustainability section on detail page shows progress bars.
- **Evidence Required:** Screenshots: eco-friendly filter, green leaf badge with tooltip, sustainability detail section.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.013 — Order Batching Preview Frontend
- **Category:** Frontend
- **Implementation Scope:** Pre-checkout banner in cart: "Your order will be batched with ~{N} nearby orders. This saves you ₹15 and reduces emissions by ~180g CO₂." Toggle switch: "Deliver mine first (no savings)." When toggled ON, banner updates to show standard delivery fee. When OFF, batch savings line item (-₹15) appears in fee breakdown. Mock logic: 12 PM - 2 PM = 2-3 nearby orders; other times = 0-1. No real geo computation.
- **Acceptance Criteria:**
  1. Batching banner appears in cart based on time of day heuristic.
  2. Toggle switches between batched and standard delivery.
  3. Fee breakdown updates to show/hide batch savings line item.
  4. Emissions copy is visible and playful.
  5. Banner is hidden when no batching is predicted.
- **Evidence Required:** Screenshots: batching banner active, toggle ON/OFF states, fee breakdown with batch savings.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.06.014 — Seed Data Completion for ND.06
- **Category:** Data
- **Implementation Scope:** Populate all seed data required for ND.06:
  1. `menu_items`: calories, protein_g, carbs_g, fat_g for 100% of items. Allergen arrays for 100%. Dietary tags computed (vegan if no dairy/meat/egg, high_protein if protein > 20g, low_calorie if calories < 400, keto if carbs < 20g).
  2. `restaurants`: `restaurant_type` ('commercial' for 90%, 'home_chef' for 10%). `eco_score`, `packaging_type`, `local_sourcing_percent`, `veg_menu_ratio` for 100%. Chef fields for home chefs.
  3. Home chefs: 3-5 restaurants with complete `chef_name`, `chef_photo_url`, `chef_specialty`, `chef_hygiene_badge`, `chef_rating`, `chef_story`.
  4. `closes_at` set for all restaurants to enable rescue deal demos.
  5. `daily_inventory` set for all menu items (default 100).
- **Acceptance Criteria:**
  1. 100% of menu items have complete nutrition data.
  2. 100% of restaurants have eco-scores and chef fields (where applicable).
  3. 3-5 home chef records exist with complete profiles.
  4. All restaurants have `closes_at` for rescue demos.
- **Evidence Required:** DB query outputs: `SELECT COUNT(*) FROM menu_items WHERE calories IS NULL`, `SELECT COUNT(*) FROM restaurants WHERE eco_score IS NULL`, `SELECT * FROM restaurants WHERE restaurant_type = 'home_chef'`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Group order API works: create, join, add item, remove item, lock, checkout, split bill all return correct data.
- [ ] Group order frontend: invite code generation, shareable link, real-time cart polling, item attribution, host controls, split bill modal.
- [ ] Office lunch API works: create group, start order, auto-suggestions, repeat order, invoice generation.
- [ ] Office lunch frontend: admin dashboard, daily order flow, budget enforcement warnings, recurring toggle, printable invoice.
- [ ] Meal rescue backend: trigger endpoint identifies closing restaurants, creates 50% off deals for unsold inventory.
- [ ] Meal rescue frontend: homepage section, restaurant card badge, rescue deals tab, mock push banner.
- [ ] Home chef API works: registration, list, dashboard endpoints (orders today, revenue, menu management).
- [ ] Home chef frontend: homepage section, chef profile, chef dashboard, restaurant list filter, checkout commission note.
- [ ] Nutritional data is 100% populated for all menu items (calories, protein, carbs, fat, allergens, dietary tags).
- [ ] Nutrition panel is expandable on every menu item card with bar visuals.
- [ ] Allergen tags are visible and color-coded (red for contains, green for free).
- [ ] Dietary goal filters (High Protein, Low Calorie, Keto, Vegan) work client-side on restaurant menus.
- [ ] Fee breakdown shows all line items with correct math and expandable tooltips.
- [ ] Distance slider updates delivery fee in real-time from 1km to 10km.
- [ ] "Why am I charged this?" section expands with plain-language explanations.
- [ ] Eco-score is populated for 100% of restaurants.
- [ ] Green leaf badge appears on restaurant cards with score >= 70.
- [ ] Eco-friendly filter chip works on restaurant list.
- [ ] Sustainability section on restaurant detail shows score breakdown with progress bars.
- [ ] Order batching preview banner appears in cart based on time heuristic.
- [ ] Batching toggle switches between batched and standard delivery, updating fee breakdown.
- [ ] All new UI follows BhojanGo design system (palette, typography, spacing, Lucide icons).
- [ ] All new features work on mobile, tablet, and desktop breakpoints.
- [ ] All new features render correctly in dark mode.
- [ ] Seed data fully supports all ND.06 features.

## 17. Evidence Required

- Screenshots:
  - Group order creation modal with 8-char invite code.
  - Group cart page showing items with attribution and participant list.
  - Split bill modal with equal and itemized views.
  - Office lunch admin dashboard with group creation.
  - Office daily order page with auto-suggestions and budget tracker.
  - Office invoice page with company header and itemized list.
  - Homepage "Rescue Meals Near You" section.
  - Restaurant card with pulsing "Closing soon" badge.
  - Restaurant detail "Rescue Deals" tab with strike-through prices.
  - Homepage "Home Chefs Near You" section with chef cards.
  - Chef profile page with photo, specialty, hygiene badge, story.
  - Chef dashboard with orders, revenue, menu toggles.
  - Menu item with nutrition panel expanded.
  - Allergen tags (red/green pills) on menu items.
  - Dietary filter chips active (e.g., "Vegan" showing only plant-based items).
  - Cart fee breakdown with all line items and tooltips.
  - Distance slider at multiple values showing fee change.
  - "Why am I charged this?" expandable section.
  - Restaurant card with green leaf eco-badge.
  - Eco-friendly filter on restaurant list.
  - Sustainability section on restaurant detail.
  - Order batching preview banner in cart.
  - Batching toggle ON/OFF with fee breakdown updates.
- Screen recordings:
  - Create group order → share link → second browser joins → add items → lock → place order.
  - Office admin creates group → starts order → colleague adds item → budget warning → place order → view invoice.
  - Trigger rescue deals → homepage updates → tap rescue deal → add to cart.
  - Browse home chefs → tap chef profile → view menu → add item → checkout commission note.
  - Open menu → expand nutrition panel → toggle dietary filters → allergen visibility.
  - Adjust distance slider → watch delivery fee update → expand "Why am I charged this?"
  - Toggle eco-friendly filter → tap restaurant → view sustainability section.
  - Toggle batching preview → watch fee breakdown update.
- API evidence:
  - `curl` output for `POST /api/v1/group-orders` and `GET /api/v1/group-orders/{code}`.
  - `curl` output for group order add item, lock, checkout.
  - `curl` output for office group creation and order start.
  - `curl` output for rescue deal trigger and rescue-deals endpoint.
  - `curl` output for chef registration and chef list.
  - Menu API response showing nutrition fields.
- DB evidence:
  - Query results confirming `menu_items` nutrition fields are 100% populated.
  - Query results confirming `restaurants` eco-scores and chef fields are populated.
  - Query results confirming home chef records exist.

## 18. Dependencies

### External Tools
- PostgreSQL (for new tables: group_orders, group_order_items, office_groups, office_orders).
- Node.js + pnpm (frontend build).
- Lucide React (icon library — already used from ND.02).
- Existing TanStack Query or SWR (for data fetching and polling).

### Internal Dependencies
- **PR.04 or PR.05 must be complete:** Stable core ordering loop is prerequisite.
- **ND.02 (Distinctive Visual Identity) must be complete:** Design system must be applied.
- **ND.03 (Small Convenience Features) must be complete:** Favorites, filters, veg/non-veg visibility, category tabs, restaurant card anatomy — all required as foundation.
- **ND.05 (Retention Focused Uniqueness) must be complete:** Loyalty system, smart reorder, personalized homepage — assumed stable before adding marketplace features.
- **Auth persistence** must work for host/group/admin flows.
- **Cart Zustand store** must support programmatic manipulation (for group checkout, reorder, batching toggle).
- **Modal/bottom sheet component** must exist for group order creation, split bill, and fee explanations.
- **Toast/snackbar component** must exist for confirmations.

## 19. Risks / Blockers

- **Group order polling load:** 3-second polling across many open tabs could generate load. Mitigation: stop polling when tab is hidden (`document.visibilityState`). Use lightweight `GET` with indexed `invite_code` query.
- **Group order checkout complexity:** Converting a group cart into a single order requires careful aggregation of items, customizations, and fees. Mitigation: server-side aggregation function tested with edge cases (empty cart, single item, many customizations).
- **Office lunch budget enforcement:** Client-side warnings can be bypassed. Server must validate per-person total on checkout. Mitigation: server-side budget check before order creation.
- **Meal rescue timing:** Demo may not align with restaurant `closes_at`. Mitigation: seed data sets `closes_at` to convenient demo times (e.g., 9:00 PM, 2:00 PM). Admin trigger endpoint allows on-demand rescue creation.
- **Home chef onboarding photo upload:** Real image upload requires S3 or local file handling. Mitigation: use photo URL string (Unsplash or placeholder) instead of file upload for demo.
- **Nutrition data seeding:** Requires research or estimation for realistic values. Mitigation: use approximate values for Indian dishes (e.g., Paneer Tikka ~350 cal, Biryani ~600 cal). Accuracy is not critical for demo.
- **Allergen data completeness:** Requires knowing ingredients of every dish. Mitigation: flag common allergens (dairy in paneer, nuts in korma, gluten in naan) and default to empty array for uncertain items.
- **Fee calculator tax accuracy:** GST rates vary by state and item type. Mitigation: use simplified 18% on food + 5% on delivery for demo. Document simplification.
- **Eco-score calculation:** Requires subjective weighting. Mitigation: document formula in seed script. Score is directional, not audited.
- **Batching preview realism:** Mock heuristic (time-based) is not realistic. Mitigation: clearly label as "preview" and "estimated savings." Real batching comes at ND.08+.

## 20. Exit Criteria

- All P0 work items (IP.ND.06.001 through IP.ND.06.012, IP.ND.06.014) implemented and verified.
- All P1 work items (IP.ND.06.013) implemented and verified.
- Group ordering complete: API + create modal + share link + live cart + attribution + lock + checkout + split bill.
- Office lunch mode complete: API + admin dashboard + daily order + suggestions + budget enforcement + recurring + invoice.
- Meal rescue complete: trigger endpoint + homepage section + card badge + rescue tab + mock push banner.
- Home chef marketplace complete: API + registration + list + profile + dashboard + filter + commission note.
- Nutritional transparency complete: 100% populated data + expandable panel + allergen tags + dietary filters.
- Transparent fee calculator complete: breakdown + tooltips + distance slider + "Why am I charged this?" section.
- Sustainability score complete: 100% populated scores + green leaf badge + eco-friendly filter + detail section.
- Order batching preview complete: banner + toggle + fee update + emissions copy.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.06 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.05)

ND.06 directly depends on ND.05 achievements:
- **ND.05 Loyalty System:** Loyalty points and tiers must be visible so that group orders and office lunch orders can earn points (enhanced engagement).
- **ND.05 Smart Reorder:** Reorder functionality must work so that office lunch auto-suggestions can leverage order history.
- **ND.05 Personalized Homepage:** Homepage sections (favorites, recommendations) must exist as the foundation for adding "Home Chefs Near You" and "Rescue Meals Near You" sections.
- **ND.05 Saved Preferences:** Dietary preferences (veg only, spice level) must persist so that nutrition filters can leverage them.
- **ND.03 + ND.02:** Filters, restaurant cards, menu discovery, and design system must all be in place as UI foundations.

## 22. Connected Next-Level Requirements (link to ND.07)

ND.07 (Smart Personalization, score 7/10) builds on ND.06 and requires:
- Working group ordering (IP.ND.06.001–002) as foundation for AI-powered group suggestions ("Suggest dishes based on what the group usually orders").
- Working office lunch mode (IP.ND.06.003–004) as foundation for corporate analytics and reporting.
- Working nutritional data (IP.ND.06.009–010) as foundation for personalized health-based meal recommendations.
- Working fee calculator (IP.ND.06.011) as foundation for dynamic surge pricing display.
- Working sustainability scores (IP.ND.06.012) as foundation for carbon offset tracking and gamification.
- Working batching preview (IP.ND.06.013) as foundation for real batch engine integration.

ND.07 will introduce:
- AI meal suggestions based on history, time, weather, cuisine preference, budget, distance, veg preference.
- Predictive ordering ("You usually order at 1 PM on Tuesdays — pre-fill cart?").
- Advanced dietary goal tracking (weekly protein intake dashboard).
- Personalized deal notifications based on nutrition preferences.
- Real-time WebSocket for group cart (polishing ND.06 polling).

ND.07 will be blocked if:
- Group order checkout fails or loses items.
- Office lunch budget enforcement is bypassable.
- Nutrition data is missing or inaccurate for >10% of items.
- Fee calculator math is wrong.
- Batching preview breaks checkout flow.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (6/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.05 + prior) described | Planner | ✅ |
| 4 | Target state (ND.06 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.06 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.06 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (8 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (4 new tables, extended columns) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why marketplace features create defensible differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.06.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: group ordering, office lunch, meal rescue, home chefs, nutrition, fee calculator, sustainability, batching preview | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention polling load, checkout complexity, budget bypass, rescue timing, photo upload, nutrition seeding, allergen data, tax accuracy, eco-score subjectivity, batching realism | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.05) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.07) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: group ordering (API + frontend), office lunch (API + frontend), meal rescue (backend + frontend), home chefs (backend + frontend), nutritional transparency (data + frontend), fee calculator (frontend), sustainability score (full stack), order batching preview (frontend), and seed data completion.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known gaps from the audits (nutrition data seeding complexity, group checkout aggregation, budget enforcement, photo upload mock).
- Scope is strictly LOCAL/DEMO-SAFE: no real payment split, no real WebSocket, no real cron infrastructure, no real FCM, no ML.
