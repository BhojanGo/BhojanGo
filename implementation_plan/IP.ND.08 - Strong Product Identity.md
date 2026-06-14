# IP.ND.08 — Strong Product Identity

## 1. Target Differentiation Score: 8/10

## 2. Score Meaning

App has a distinct food-ordering experience: tailored UI, trust system, freshness/speed cues, smart bundles, contextual deals, and memorable ordering flows. At score 8, BhojanGo is unmistakably itself — every screen, every interaction, every piece of data reinforces a unique food-ordering identity. Users can describe the app in one sentence: "It's the food app that shows me exactly how fresh my food is, guarantees delivery speed, bundles my meal smartly, and feels like it was built by people who love food." Trust is visual and omnipresent (FSSAI → Restaurant → Rider). Freshness is a currency ("Made 8 minutes ago"). Speed is a promise with consequences ("30 min or free"). Deals feel alive and aware (rainy day soup discounts, cricket match combos). Ordering is gamified (challenges, badges). The app has a voice ("Yum incoming!"), a sound (unique chime), a feel (custom haptics), and a soul (signature empty states). Competitors feel transactional; BhojanGo feels personal, intentional, and alive.

## 3. Current → Target Transition

**From ND.07 (smart personalization):**
- The app has AI meal suggestions based on history, time, weather, cuisine preference, budget, distance, and veg preference.
- Predictive ordering pre-fills carts at usual times ("1 PM Tuesday = biryani day").
- Advanced dietary goal tracking shows weekly protein intake dashboard.
- Personalized deal notifications arrive based on nutrition preferences.
- Real-time WebSocket replaces polling for group cart updates.
- Loyalty tiers, smart reorder, favorites, saved preferences, and transparent fees are all functional from ND.05 and ND.06.
- Group ordering, office lunch, meal rescue, home chefs, nutritional transparency, fee calculator, sustainability scores, and batching preview are all live from ND.06.
- **No signature ordering flow exists.** There is no one-tap reorder from lock screen widget or PWA shortcut. Users must open the app, navigate to history, and tap reorder.
- **No trust architecture is visible.** Restaurant cards show ratings but no FSSAI badge, no restaurant verification shield, no rider verification check. Trust is implicit, not explicit.
- **No freshness currency.** Menu items show name, price, and description. No "Made X minutes ago" indicator. No real-time countdown since preparation. No "Still hot" status.
- **No speed promises.** Delivery time is an estimate ("35-45 min") with no guarantee. No countdown timer on order tracking. No late delivery apology or compensation mechanism.
- **No smart bundles at checkout.** Cart shows individual items. No "Complete your meal" suggestion. No bundle builder UI to add drink + dessert for a discount.
- **No contextual deals engine.** Deals are static promo codes (WELCOME20). No location + time + weather driven offers. No rainy day soup discount, no cricket match pizza combo.
- **No gamified ordering.** Loyalty points exist but no challenges, no badges, no "Chef's Challenge" (order 3 cuisines in a week). No "Explorer Badge" for trying new restaurants. Profile is plain text.
- **No BhojanGo Sound.** Order update notifications use the default browser/system sound. No unique, brand-owned chime.
- **No signature empty states.** Empty cart shows "Your cart is empty" in plain text. Empty orders shows "No orders yet." No animations, no food-themed illustrations, no personality.
- **No haptic design.** All interactions are silent. No vibration on add-to-cart, place order, or order confirmation.
- **No micro-copy voice.** Copy is generic ("Item added", "Order placed"). No friendly, food-loving tone. No "Yum incoming!", "Almost there...", "Hot and on the way!"

**Target at score 8:**
- **Signature ordering flow is functional:** A PWA install prompt offers "Add BhojanGo to Home Screen." Once installed, the user can long-press the app icon and see "Reorder Butter Chicken from Spice Garden" as a quick action. Tapping it opens the app directly to checkout with the item pre-filled. A lock screen widget (mock/demo via PWA manifest shortcuts) shows "Tap to reorder your usual."
- **Trust architecture is visible everywhere:** Every restaurant card shows a three-layer trust stack: FSSAI Verified badge (orange shield) → Restaurant Verified badge (green check) → Rider Verified badge (blue helmet). On restaurant detail, tapping a badge opens a tooltip explaining what it means. Rider verification shows on order tracking: "Rider Arjun — Verified, 4.9 rating, 1,240 deliveries."
- **Freshness currency is real-time:** Every menu item card shows "Made 8 min ago" with a small pulsing green dot. Items over 30 minutes old show "Made 32 min ago — still fresh" with a yellow dot. The time updates in real-time (client-side countdown from `prepared_at` timestamp). Order tracking shows "Still hot" indicator with a thermometer icon when delivery ETA is under 15 minutes.
- **Speed promises are guaranteed:** Qualifying restaurants (under 5km, AVG prep time <20 min, rating >4.0) show a "Delivery in 30 min or free" gold badge on their card. Order tracking page shows a live countdown timer from confirmed → delivered. If delivery exceeds the promise, an auto-generated apology coupon ("Sorry we're late! ₹50 off your next order") appears in the user's wallet within 1 minute of late delivery.
- **Smart bundles appear at checkout:** When a cart contains only a main dish (biryani, curry, pizza), a "Complete your Meal" suggestion appears: "Add a drink + dessert for ₹50 less than individual." The bundle builder UI shows three cards: Drink options, Dessert options, Combo savings. One-tap adds the bundle.
- **Contextual deals feel alive:** A backend cron (or admin trigger for demo) checks current weather (mock: rainy = true/false), local events (mock: cricket match scheduled), time of day, and user location. Homepage banner updates: "It's raining! Hot soup 20% off at Soup Kitchen." "India vs Pakistan today — Pizza + Wings combo at Mike's Pizza." Deals are time-boxed and disappear when the context changes.
- **Gamified ordering drives engagement:** "Chef's Challenge: Order from 3 different cuisines this week and get free delivery on your next 3 orders." Progress shows 2/3 with cuisine icons. "Explorer Badge: Try 5 new restaurants and unlock Gold Explorer status." Badges (Bronze, Silver, Gold) are visible on the user's profile page with unlock dates. Completing challenges auto-credits rewards.
- **BhojanGo Sound is brand-owned:** A short, pleasant chime (Web Audio API generated, ~800ms, ascending major third) plays on every order status update push notification. Not the default browser notification sound. The sound is defined as a base64-encoded AudioBuffer and played via a custom `playBhojanGoChime()` utility.
- **Signature empty states have personality:** Empty cart shows an animated SVG illustration of a sad, empty plate with a wandering fly. Text: "Your plate is waiting..." with a subtle floating animation. CTA: "Browse restaurants." Empty orders shows a confetti-burst animation (CSS keyframes) with a chef character holding a covered platter. Text: "First meal magic awaits!" CTA: "Find your first bite."
- **Haptic design is mapped:** Subtle vibration patterns for key actions via the Vibration API (mobile) or visual haptic proxy on desktop. Custom haptic chart: add-to-cart (single 50ms pulse), place order (double 30ms pulse), order confirmed (triple 20ms pulse ascending intensity). A "Haptic Feedback" toggle in settings lets users disable it.
- **Micro-copy voice is consistent:** Every user-facing message uses a friendly, food-loving tone. Order confirmation: "Yum incoming! Your order is confirmed." Preparing: "Almost there... {restaurant} is cooking up something delicious." Picked up: "Hot and on the way! {rider} has your order and is speeding to you." Delivered: "Enjoy your meal! Don't forget to rate your experience." Cart empty: "Hungry? Your plate is waiting." Error states: "Oops, our kitchen got too hot. Try again?"

## 4. Implementation Objective

Create a cohesive, unmistakable product identity. This is not about individual features but about the overall experience feeling intentional, distinctive, and consistently BhojanGo. Every pixel, vibration, sound, word, and badge must reinforce that this is a food app built by people who care about food, trust, and joy. The goal is emotional differentiation — users should feel something when they use BhojanGo, not just transact. All features are demo-safe: mock weather data, simulated countdowns, Web Audio API sounds, CSS animations, and client-side haptics. No ML, no IoT, no blockchain, no real-time map tracking required.

## 5. Scope

### 5.1 Signature Ordering Flow — "BhojanGo Express"
- **PWA Shortcuts:** The web app manifest (`manifest.json`) includes `shortcuts` array: "Reorder Usual" → opens `/express-reorder` with the user's most frequent item pre-selected. A second shortcut: "Browse Near Me" → opens `/restaurants`.
- **Express Reorder Page (`/express-reorder`):** Dedicated fast-path page. Shows the user's top 3 most-ordered items as large cards with one-tap "Order Again" buttons. Tapping skips the menu, skips the cart, goes straight to checkout with last-used address and payment method pre-filled. "Express checkout in 2 taps."
- **Quick Action Simulation:** Mock lock screen widget using PWA share target API. A "Share to BhojanGo" action that pre-fills an item from shared text (demo-safe: parses generic text into mock item).
- **One-tap from history:** Order history cards have a prominent "Reorder in 1 Tap" button that bypasses cart entirely.

### 5.2 Trust Architecture — Three-Layer Trust
- **Database:** Extend `restaurants` table: `fssai_license_number` VARCHAR, `fssai_verified` BOOLEAN, `restaurant_verified` BOOLEAN, `restaurant_verified_at` TIMESTAMP. Extend `delivery_partners` table (or mock rider profile): `rider_verified` BOOLEAN, `verification_documents` JSONB (license, vehicle registration mock), `total_deliveries` INT.
- **Backend:** `GET /api/v1/restaurants/{id}` returns full trust stack: `fssai_verified`, `restaurant_verified`, `rider_verified` on the assigned rider (if any active order). `GET /api/v1/deliveries/{order_id}/rider` returns rider profile with verification status and stats.
- **Frontend:**
  - Restaurant card: three small badges in a row (FSSAI orange shield, Verified green check, Rider blue helmet). Only visible badges are shown (if not verified, that badge is hidden).
  - Restaurant detail: trust section with expandable cards. "FSSAI Verified — License #{number}" with link to verify (mock). "Restaurant Verified — Hygiene inspected on {date}." "Rider Verified — {name} has completed {N} deliveries with a {rating} rating."
  - Order tracking: rider card shows verification badge prominently.

### 5.3 Freshness Currency — Real-Time Countdown
- **Database:** Extend `menu_items` table: `prepared_at` TIMESTAMP (nullable, set by restaurant when marking item ready). Extend `orders` table: `items_freshness` JSONB storing `{menu_item_id, prepared_at, freshness_status}`.
- **Backend:** On order status transition to `preparing`, restaurant app (mock) sets `prepared_at` for each item. `GET /api/v1/orders/{id}` returns freshness data.
- **Frontend:**
  - Menu item card: small badge overlay on image. "Made {N} min ago" with pulsing dot (green <15 min, yellow 15-30 min, orange >30 min). Countdown updates every 60 seconds client-side.
  - Restaurant detail: items sorted by freshness (newest first) as default.
  - Order tracking: "Still hot" indicator (thermometer icon + flame) shown when ETA <15 min. "Cooling down" shown when ETA >30 min.

### 5.4 Speed Promises — "30 Min or Free"
- **Database:** Extend `restaurants` table: `qualifies_for_speed_promise` BOOLEAN (true if avg_delivery_time <30 min, rating >4.0, distance <5km). Extend `orders` table: `speed_promise_minutes` INT (default 30), `speed_promise_met` BOOLEAN, `apology_coupon_generated` BOOLEAN.
- **Backend:** Order creation checks if restaurant qualifies. If yes, sets `speed_promise_minutes = 30`. A background check (or admin trigger for demo) compares `delivered_at - confirmed_at`. If >30 min and `speed_promise_met` is false, auto-generates coupon: inserts into `offers` table with code `SORRY{ORDER_ID_LAST4}`, type `fixed`, value 50, `expires_at` = now + 7 days.
- **Frontend:**
  - Restaurant card: gold "30 min or free" badge on qualifying restaurants.
  - Order tracking: live countdown timer showing minutes:seconds from confirmed state. Below it: "Promise: 30 min or free." Timer turns red when approaching 30 min.
  - Late delivery: in-app banner + wallet notification: "Sorry we're late! ₹50 off your next order. Code: SORRY7X2P."

### 5.5 Smart Bundles — "Complete Your Meal"
- **Database:** New `bundles` table (`id`, `restaurant_id`, `name`, `description`, `trigger_item_id` UUID FK → menu_items, `bundle_items` JSONB array of `{menu_item_id, quantity}`). `bundle_price` DECIMAL (total of individual items minus discount). `is_active` BOOLEAN.
- **Backend:** `GET /api/v1/restaurants/{id}/bundles` returns active bundles for the restaurant. `POST /api/v1/cart/apply-bundle` adds bundle items to cart at bundle price.
- **Frontend:**
  - Cart page: when cart contains a main dish that matches a `trigger_item_id`, a "Complete Your Meal" card appears below the cart items. Shows: "Add Garlic Naan + Mango Lassi for ₹89 (save ₹41)."
  - Bundle builder UI: three side-by-side mini cards (Drink, Dessert, Combo) with + buttons. Tapping adds both supplemental items to cart at the discounted bundle price. Original prices shown struck through.
  - Checkout page: bundle savings shown as a line item: "Bundle savings: -₹41."

### 5.6 Contextual Deals Engine
- **Database:** New `contextual_deals` table (`id`, `title`, `description`, `discount_percent` INT, `trigger_type` ENUM('weather_rainy', 'weather_hot', 'event_cricket', 'time_lunch', 'time_dinner', 'location_near_office'), `trigger_params` JSONB, `restaurant_id` UUID FK, `starts_at`, `expires_at`, `is_active` BOOLEAN, `image_url` VARCHAR).
- **Backend:** `GET /api/v1/deals/contextual` returns active deals matching current context. Context is determined by mock/demo-safe heuristics: time of day (12-2 PM = lunch, 7-10 PM = dinner), mock weather API (random rain flag for demo), mock event API ( cricket match flag). `POST /api/v1/admin/trigger-contextual` admin endpoint to force-generate deals for demo.
- **Frontend:**
  - Homepage banner: large hero section showing the active contextual deal. "It's raining — Warm yourself up! Hot soup 20% off at Soup Kitchen." Banner has weather icon (rain cloud), restaurant image, CTA button.
  - Deal card on restaurant list: qualifying restaurants show a contextual deal pill: "Match Day Special — Pizza + Wings combo."
  - Time-boxed expiry: countdown timer on deal banner ("Expires in 2h 14m"). Deals auto-hide when `expires_at` passes.

### 5.7 Gamified Ordering — Challenges and Badges
- **Database:** New `user_challenges` table (`id`, `user_id`, `challenge_type` ENUM('cuisine_explorer', 'restaurant_explorer', 'streak_master'), `progress` INT, `target` INT, `status` ENUM('in_progress', 'completed', 'claimed'), `completed_at`, `reward_type`, `reward_value`). New `user_badges` table (`id`, `user_id`, `badge_type`, `badge_tier` ENUM('bronze', 'silver', 'gold'), `unlocked_at`, `display_order`).
- **Backend:** `GET /api/v1/users/me/challenges` returns active challenges with progress. `POST /api/v1/users/me/challenges/{id}/claim` claims reward when status = completed. `GET /api/v1/users/me/badges` returns badge list. Challenge progress is updated inline during order creation: order-svc increments relevant counters.
- **Frontend:**
  - Profile page: new "Challenges & Badges" tab. Shows active challenges with progress bars: "Chef's Challenge — Order from 3 cuisines this week (2/3)." Tapping shows cuisine icons (Indian, Chinese, Italian) with checkmarks.
  - Badge gallery: grid of badge cards. Locked badges are grayscale. Unlocked badges are colorful with unlock date. "Explorer Badge — Bronze: Tried 5 new restaurants." "Gold: Tried 25 new restaurants."
  - Reward claim: on completion, a confetti animation plays and reward is auto-credited (free delivery coupon, discount code, loyalty points).
  - Homepage: small "Active Challenge" widget below the greeting: "2/3 cuisines — you're almost there!"

### 5.8 BhojanGo Sound — Unique Notification Chime
- **Frontend:** Custom Web Audio API sound generator. Defined as a synthesized chime (not an audio file to avoid hosting/copyright issues). Oscillator: sine wave, ascending from C5 to E5 to G5 over 800ms with exponential decay envelope. Encapsulated in `playBhojanGoChime()` utility.
- **Trigger points:** Order status update notification (in-app toast or mock push), order confirmation after checkout, challenge completion, badge unlock.
- **Settings:** "Sound" toggle in user settings. When disabled, all chimes are suppressed. Default: ON.

### 5.9 Signature Empty States — Animated Personality
- **Frontend:**
  - Empty cart (`/cart` with 0 items): Full-screen illustration. SVG of a sad empty plate with a tiny wandering fly (CSS animation, fly moves in a figure-8 path over 8s). Text: "Your plate is waiting..." with gentle floating up-down animation. CTA button: "Browse Restaurants" with saffron background.
  - Empty orders (`/orders` with 0 orders): Full-screen illustration. SVG chef character holding a covered platter with a small puff of steam (CSS animation, steam rises and fades). Confetti burst animation (30 colored dots falling from top, CSS keyframes) plays once on load. Text: "First meal magic awaits!" CTA: "Find Your First Bite."
  - Empty search results: "No restaurants match your craving. Try different filters?" with a shrug emoji-style illustration.

### 5.10 Haptic Design — Custom Vibration Patterns
- **Frontend:** Vibration API integration (`navigator.vibrate`) for mobile devices. Desktop shows a subtle visual haptic proxy (brief button scale pulse + ripple effect).
- **Haptic chart mapped to actions:**
  - Add to cart: single 50ms pulse.
  - Remove from cart: single 30ms pulse (shorter = destructive).
  - Place order: double 30ms pulse with 50ms gap (serious = double confirmation).
  - Order confirmed: triple 20ms pulse ascending (celebratory).
  - Error (e.g., max quantity reached): long 100ms pulse (warning).
  - Challenge complete: pattern 50-30-50-30-50ms (fanfare).
- **Settings:** "Haptic Feedback" toggle in user settings. Default: ON on mobile, OFF on desktop.

### 5.11 Micro-Copy Voice — Friendly, Food-Loving Tone
- **Frontend:** Systematic micro-copy replacement across all user-facing strings. No generic "Success" or "Error." Every message gets a food-themed voice.
- **Copy mapping examples:**
  - Order confirmation toast: "Yum incoming! Your order is confirmed."
  - Preparing status: "Almost there... {restaurant} is cooking up something delicious."
  - Picked up status: "Hot and on the way! {rider} has your order."
  - Delivered status: "Enjoy your meal! Rate your experience?"
  - Cart empty state: "Hungry? Your plate is waiting."
  - Add to cart toast: "Added to your feast!"
  - Remove from cart: "Removed — more room for something else?"
  - Error retry: "Oops, our kitchen got too hot. Try again?"
  - Loading state: "Whipping up something good..."
  - Payment success: "Paid! The kitchen has been notified."
  - Payment failure: "Payment didn't go through. Check your details?"
- **Implementation:** All copy stored in a centralized `copy.json` or TypeScript object, organized by screen. Hindi and English versions for India market. Easy to adjust tone globally.
- **Tone guidelines documented:** Friendly, never corporate. Food metaphors encouraged. Exclamation marks welcome. Emojis used sparingly (only in empty states, not in functional copy). Always address user directly ("your order", "your meal").

## 6. Out of Scope

- **AI/ML heavy features:** No ML model for contextual deal prediction. Mock heuristics only.
- **Smart lockers / IoT:** No physical smart locker integration. No temperature sensors, no Bluetooth LE, no IoT hardware.
- **Blockchain:** No blockchain-verified trust badges, no on-chain credential storage.
- **Real-time map tracking with full detail:** Mapbox/Leaflet driver GPS is deferred to PR.07+. Order tracking shows status timeline + ETA but no live map.
- **Real FCM push notifications:** BhojanGo Sound plays on in-app toasts and mock push UI only. Real FCM integration is deferred to PR.06+.
- **Real weather API integration:** Contextual deals use mock weather flags (admin trigger or random demo state). Real OpenWeatherMap integration is deferred to PR.08+.
- **Real event API integration:** Sports match data is mock/demo only. Real API integration deferred to PR.08+.
- **PWA background sync/service worker:** No background fetch, no offline ordering. PWA features limited to manifest + shortcuts.
- **Real haptic feedback on iOS Safari:** Safari Vibration API support is limited. Desktop visual proxy is the fallback. Full cross-platform haptics deferred to PR.08+.
- **Audio file hosting:** BhojanGo Sound is synthesized via Web Audio API. No MP3/OGG files to host.
- **Accessibility screen reader cooky weirdness:** Micro-copy voice is optimized for visual reading. Screen reader versions use plain language.

## 7. Required Capabilities

- Core ordering loop (browse → menu → cart → checkout → track) must be stable (PR.04 or PR.05 complete).
- Auth persistence must work. Express reorder and profile badges require logged-in users.
- Order history must exist and be queryable for express reorder and challenge progress.
- Restaurant list API must return trust badge fields (`fssai_verified`, `restaurant_verified`, `rider_verified`).
- Menu items API must support `prepared_at` timestamp.
- Order status history/timeline must exist (from PR.04 or ND.06) for freshness and speed promise tracking.
- Cart Zustand store must support programmatic bundle application.
- Frontend animation system (Framer Motion or CSS keyframes) must exist for empty states, confetti, and micro-interactions.
- Toast/snackbar component must exist for confirmation messages.
- Design system (BhojanGo palette, typography, spacing, Lucide icons) must be applied across all new UI.
- Web Audio API support in target browser (all modern browsers support this).
- Vibration API support on Android mobile (primary target; iOS fallback handled gracefully).

## 8. Key User Journeys

### Journey 8.1 — User Reorders in 2 Taps (Signature Ordering Flow)
1. Priya has ordered from BhojanGo 12 times. Her usual is Butter Chicken from Spice Garden.
2. She opens her phone, long-presses the BhojanGo PWA icon. A shortcut appears: "Reorder Butter Chicken."
3. She taps it. BhojanGo opens directly to `/express-reorder` with Butter Chicken as the top card.
4. She taps "Order Again" — checkout opens with her saved address and payment method pre-filled.
5. She taps "Place Order." Done. Total taps from home screen: 2.
6. Confirmation screen: "Yum incoming! Your order is confirmed." BhojanGo chime plays.
7. Haptic triple pulse confirms the order.

### Journey 8.2 — User Sees Trust Badges and Feels Safe
1. Rahul opens BhojanGo, browses restaurants. Every card has three small badges at the bottom: orange FSSAI shield, green verified check, blue rider helmet.
2. He taps "Biryani House." Detail page has a "Trust & Safety" section.
3. He expands "FSSAI Verified" — sees license number. "Restaurant Verified" — shows last hygiene inspection date. "Rider Verified" — shows assigned rider stats (if order active).
4. He sees a "30 min or free" gold badge on the card. He feels confident ordering.
5. After placing, order tracking shows rider card: "Arjun — Verified, 4.9 rating, 1,240 deliveries." Trust reinforced at every step.

### Journey 8.3 — User Orders Fresh Food with Confidence
1. User opens a restaurant menu. Item cards show "Made 12 min ago" with a pulsing green dot.
2. An older item shows "Made 35 min ago — still fresh" with a yellow dot.
3. User adds a fresh item to cart. "Added to your feast!" toast appears.
4. After checkout, order tracking shows "Still hot" with thermometer icon.
5. As delivery approaches, "Still hot" fades when ETA passes 15 min.
6. User receives food and it is indeed hot. Trust in freshness is validated.

### Journey 8.4 — User Gets a Speed Promise and Late Apology
1. User sees "30 min or free" badge on "Dosa Point" restaurant card.
2. User orders. Order tracking shows countdown timer: "29:45 remaining... Promise: 30 min or free."
3. Timer turns red at 5:00 remaining. User watches nervously.
4. Delivery arrives at 32 minutes. Timer shows "-2:00 — Late."
5. Within 60 seconds, an in-app banner appears: "Sorry we're late! Your next order gets ₹50 off. Code: SORRY7X2P."
6. Coupon is auto-added to wallet. User is annoyed but impressed by the response.

### Journey 8.5 — User Completes a Smart Bundle at Checkout
1. User has Paneer Tikka Masala in cart. Cart page shows a "Complete Your Meal" card below items.
2. Card: "Add Garlic Naan + Mango Lassi for ₹89 (save ₹41)."
3. User taps "Add Bundle." Cart updates: Naan and Lassi added at ₹89 total (original prices ₹65 + ₹65 = ₹130 shown struck through).
4. Fee breakdown shows: "Bundle savings: -₹41." Grand total reduced.
5. User proceeds to checkout. Satisfied with the value.

### Journey 8.6 — User Discovers a Contextual Deal
1. It's 8 PM on a rainy evening (demo: admin triggers rainy context).
2. User opens BhojanGo. Homepage banner: "It's raining! Warm yourself up — Hot soup 20% off at Soup Kitchen. Expires in 2h 14m."
3. User taps banner. Goes to Soup Kitchen detail with "Rainy Day Special" badge.
4. Menu shows discounted soup prices with original prices struck through.
5. User orders. Discount auto-applied at checkout.
6. Next day (sunny), banner is gone. Deal has expired. User checks back for new context.

### Journey 8.7 — User Completes a Challenge and Earns a Badge
1. User's profile shows "Active Challenges" tab. "Chef's Challenge: Order from 3 different cuisines this week (1/3)."
2. User orders Chinese on Monday. Progress updates to 2/3. Cuisine icons show Indian (check), Chinese (check), Italian (empty).
3. User orders Italian on Wednesday. Progress hits 3/3. Confetti animation plays. "Challenge Complete!" toast appears.
4. Reward auto-credited: "Free delivery on your next 3 orders."
5. Badge unlocked: "Cuisine Explorer — Bronze" appears in badge gallery.
6. User sees new challenge: "Restaurant Explorer — Try 5 new restaurants (2/5)."

### Journey 8.8 — Empty States Delight the User
1. New user opens BhojanGo, goes to cart without adding anything.
2. Sees animated sad plate with wandering fly. Text: "Your plate is waiting..." CTA: "Browse Restaurants."
3. User smiles at the animation. Taps CTA. Discovers restaurants.
4. Later, user checks orders (none yet). Sees confetti burst + chef with covered platter. Text: "First meal magic awaits!"
5. User feels invited, not rejected. Emotional connection forms.

### Journey 8.9 — Haptics and Sound Confirm Every Action
1. User on Android phone adds item to cart. Phone vibrates with single 50ms pulse.
2. User places order. Double pulse. BhojanGo chime plays (ascending three-note melody).
3. Order confirmed. Triple pulse (celebratory). Chime plays again.
4. In settings, user toggles "Haptic Feedback" OFF. Subsequent actions are silent.
5. User toggles "Sound" OFF. Chime stops. But keeps haptics ON. Customizes experience.

### Journey 8.10 — Micro-Copy Makes the App Feel Human
1. User adds item to cart. Toast: "Added to your feast!" (not "Item added successfully.")
2. User checks order status. "Almost there... Spice Garden is cooking up something delicious."
3. Rider picks up. "Hot and on the way! Arjun has your order."
4. Delivered. "Enjoy your meal! Rate your experience?"
5. User encounters error. "Oops, our kitchen got too hot. Try again?" (not "An error occurred.")
6. Every message feels like it was written by a friendly food lover, not a corporate legal team.

## 9. Technical Coverage

### Backend
- **user-svc:** Extend `GET /api/v1/users/me/profile` to return active challenges and badges. `GET /api/v1/users/me/challenges` and `GET /api/v1/users/me/badges`. `POST /api/v1/users/me/challenges/{id}/claim`. Update order creation to increment challenge counters (cuisine count, restaurant count, streak count).
- **restaurant-svc:** Extend `GET /api/v1/restaurants/{id}` and list endpoints to return `fssai_license_number`, `fssai_verified`, `restaurant_verified`, `restaurant_verified_at`. Extend `GET /api/v1/restaurants/{id}/menu` to return `prepared_at` for items. Add `GET /api/v1/restaurants/{id}/bundles` endpoint. Add `GET /api/v1/deals/contextual` endpoint. Add `POST /api/v1/admin/trigger-contextual` admin endpoint.
- **order-svc:** Extend order creation to set `speed_promise_minutes` if restaurant qualifies. Extend `GET /api/v1/orders/{id}` to return freshness data, speed promise status, and countdown. Add late-delivery apology coupon generation logic (on status transition to `delivered`, check duration > promise, create offer if not already done). Add `POST /api/v1/cart/apply-bundle` bundle application endpoint.
- **delivery-svc:** Extend `GET /api/v1/deliveries/{order_id}/rider` to return rider verification status, total deliveries, and rating.
- **Admin trigger endpoints:** `POST /api/v1/admin/trigger-contextual` to force-generate contextual deals for demo. `POST /api/v1/admin/simulate-late-delivery` to force a late apology coupon for demo.

### Frontend
- **Zustand store extensions:** `trustStore` (badge visibility preferences), `freshnessStore` (countdown timers), `speedPromiseStore` (countdown timer state, late detection), `bundleStore` (active bundle suggestion, applied bundles), `contextualDealStore` (active deals, expiry timers), `challengeStore` (active challenges, progress, completed), `settingsStore` (sound toggle, haptic toggle).
- **New Components:**
  - `<ExpressReorderPage />` — `/express-reorder` with top 3 usual items.
  - `<TrustBadgeStack />` — three-layer badge on restaurant cards.
  - `<TrustDetail />` — expandable trust section on restaurant detail.
  - `<FreshnessBadge />` — "Made N min ago" with pulsing dot.
  - `<StillHotIndicator />` — thermometer icon on order tracking.
  - `<SpeedPromiseBadge />` — gold "30 min or free" badge.
  - `<SpeedPromiseTimer />` — live countdown on order tracking.
  - `<LateApologyBanner />` — auto-appearing apology coupon banner.
  - `<SmartBundleCard />` — "Complete Your Meal" suggestion in cart.
  - `<BundleBuilder />` — side-by-side drink/dessert/combo cards.
  - `<ContextualDealBanner />` — homepage hero banner for active deals.
  - `<ContextualDealPill />` — small deal pill on restaurant cards.
  - `<ChallengeWidget />` — active challenge progress on profile/homepage.
  - `<BadgeGallery />` — grid of earned badges.
  - `<BhojanGoChime />` — Web Audio API sound utility.
  - `<EmptyCartState />` — animated sad plate illustration.
  - `<EmptyOrdersState />` — confetti + chef illustration.
  - `<HapticProvider />` — context for vibration patterns.
  - `<MicroCopyProvider />` — centralized copy with tone.
- **New Hooks:** `useExpressReorder()` (fetches top 3 frequent items), `useFreshnessCountdown(preparedAt)` (client-side timer), `useSpeedPromiseTimer(orderId)`, `useContextualDeals()`, `useChallenges()`, `useBadges()`, `useBhojanGoSound()`, `useHaptic(actionType)`.

### Data
- Extended `restaurants` table: `fssai_license_number`, `fssai_verified`, `restaurant_verified`, `restaurant_verified_at`, `qualifies_for_speed_promise`.
- Extended `menu_items` table: `prepared_at`.
- Extended `orders` table: `speed_promise_minutes`, `speed_promise_met`, `apology_coupon_generated`, `items_freshness` JSONB.
- Extended `delivery_partners` table: `rider_verified`, `verification_documents` JSONB, `total_deliveries`.
- New `bundles` table: `id`, `restaurant_id`, `name`, `trigger_item_id`, `bundle_items` JSONB, `bundle_price`, `is_active`.
- New `contextual_deals` table: `id`, `title`, `description`, `discount_percent`, `trigger_type`, `trigger_params`, `restaurant_id`, `starts_at`, `expires_at`, `is_active`, `image_url`.
- New `user_challenges` table: `id`, `user_id`, `challenge_type`, `progress`, `target`, `status`, `completed_at`, `reward_type`, `reward_value`.
- New `user_badges` table: `id`, `user_id`, `badge_type`, `badge_tier`, `unlocked_at`, `display_order`.
- Seed data: populate trust badges for 100% of restaurants, set `prepared_at` for demo items, seed 3-5 bundles per restaurant, seed contextual deal templates, create default challenges for all users, seed rider verification data.

## 10. UI / UX Coverage

- **Loading states:** Express reorder page shows skeleton for usual items. Trust badges show shimmer while verification status loads. Freshness badge shows "--" while `prepared_at` loads. Challenge widget shows skeleton progress bar.
- **Error states:** Express reorder fails: "We couldn't find your usual — browse restaurants instead." Trust badge missing data: badge hidden (graceful degradation). Freshness countdown fails: badge hidden. Speed promise timer error: badge hidden, order proceeds normally. Contextual deal API fails: banner hidden. Challenge API fails: widget hidden.
- **Empty states:** Signature empty states for cart and orders (see 5.9). Empty challenges: "No active challenges. Start ordering to earn rewards!" Empty badges: "No badges yet. Complete challenges to unlock!" Empty bundles: "No bundles available for this restaurant."
- **Success states:** Toast on express reorder: "Yum incoming!" with chime. Toast on bundle add: "Bundle added — great choice!" Toast on challenge complete: confetti + chime. Toast on badge unlock: "Badge earned!" with chime.
- **Design system:** All new components follow BhojanGo palette (saffron `#E65100`, trust green `#2E7D32`, accent gold `#FFB300`, cream `#F7F5F2`, dark `#1A1A1A`), Manrope + Inter typography, 4px grid, Lucide icons. Trust badges use semantic colors (FSSAI = orange, Verified = green, Rider = blue). Speed promise badge uses gold. Freshness dots use green/yellow/orange gradient.
- **Responsive:** Express reorder: 1-column cards on mobile, 3-column on desktop. Trust badges: stacked vertically on mobile, horizontal row on desktop. Freshness badge: absolute position on image (all breakpoints). Speed promise timer: full-width on mobile, inline on desktop. Bundle builder: stacked on mobile, side-by-side on desktop. Contextual deal banner: full-width hero on all sizes. Challenge widget: compact on mobile, expanded on desktop.
- **Dark mode:** Trust badges maintain semantic colors. Freshness dots glow slightly in dark mode. Speed promise gold badge uses brighter gold. Contextual deal banner uses dark overlay on image. Challenge progress bars use distinct colors. Empty state illustrations adapt colors for dark backgrounds.
- **Accessibility:** Trust badges use `aria-label`: "FSSAI Verified restaurant." Freshness badge uses `aria-live="polite"` for countdown updates. Speed promise timer uses `role="timer"` with `aria-label`. Bundle builder uses `aria-pressed` for selected items. Challenge widget uses `role="progressbar"` with `aria-valuenow`. BhojanGo Sound respects `prefers-reduced-motion` and sound toggle. Haptics have visual proxy on desktop and can be disabled. All micro-copy is readable and screen-reader friendly.

## 11. Data / Model Coverage

- `restaurants` table (extended): `fssai_license_number` VARCHAR, `fssai_verified` BOOLEAN (default false), `restaurant_verified` BOOLEAN (default false), `restaurant_verified_at` TIMESTAMP, `qualifies_for_speed_promise` BOOLEAN (default false).
- `menu_items` table (extended): `prepared_at` TIMESTAMP (nullable).
- `orders` table (extended): `speed_promise_minutes` INT (default 30), `speed_promise_met` BOOLEAN (default true), `apology_coupon_generated` BOOLEAN (default false), `items_freshness` JSONB (default {}).
- `delivery_partners` table (extended): `rider_verified` BOOLEAN (default false), `verification_documents` JSONB (default {}), `total_deliveries` INT (default 0).
- `bundles` table (new): `id` UUID PK, `restaurant_id` UUID FK → `restaurants.id`, `name` VARCHAR, `description` TEXT, `trigger_item_id` UUID FK → `menu_items.id`, `bundle_items` JSONB (array of `{menu_item_id, quantity}`), `bundle_price` DECIMAL(10,2), `is_active` BOOLEAN (default true), `created_at` TIMESTAMP.
- `contextual_deals` table (new): `id` UUID PK, `title` VARCHAR, `description` TEXT, `discount_percent` INT, `trigger_type` VARCHAR (weather_rainy, weather_hot, event_cricket, time_lunch, time_dinner, location_near_office), `trigger_params` JSONB, `restaurant_id` UUID FK → `restaurants.id` (nullable, for restaurant-specific deals), `starts_at` TIMESTAMP, `expires_at` TIMESTAMP, `is_active` BOOLEAN (default true), `image_url` VARCHAR.
- `user_challenges` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `challenge_type` VARCHAR, `progress` INT (default 0), `target` INT, `status` VARCHAR (in_progress, completed, claimed), `completed_at` TIMESTAMP, `reward_type` VARCHAR (free_delivery, discount_code, loyalty_points), `reward_value` VARCHAR.
- `user_badges` table (new): `id` UUID PK, `user_id` UUID FK → `users.id`, `badge_type` VARCHAR (cuisine_explorer, restaurant_explorer, streak_master), `badge_tier` VARCHAR (bronze, silver, gold), `unlocked_at` TIMESTAMP, `display_order` INT.
- Seed data requirements: Trust badges populated for 100% of restaurants (80% FSSAI verified, 60% restaurant verified). `prepared_at` seeded for all menu items (random times within last 30 min). 3-5 bundles per restaurant. 3-5 contextual deal templates. Default challenges created for all seeded users. Rider verification seeded for all delivery partners.

## 12. Role / Permission Coverage

- `customer` (logged-in): Can use express reorder, view trust badges, see freshness data, benefit from speed promises, apply smart bundles, view contextual deals, participate in challenges, earn badges, customize sound/haptic settings. Can claim challenge rewards.
- Guest (unauthenticated): Can view trust badges on restaurant cards. Cannot use express reorder (requires order history). Cannot participate in challenges or earn badges. Can view contextual deals. Can apply bundles. Can see freshness data. No sound/haptic customization (uses defaults).
- `restaurant_owner`: Can update `prepared_at` for menu items (mock kitchen display). Can view trust badge status. Cannot manage bundles directly without admin help.
- `home_chef`: Same as restaurant_owner for trust and freshness.
- `delivery_partner`: Rider profile data (verification status, total deliveries) is read-only. Driver app shows verification badge.
- `admin`: Can trigger contextual deals (`POST /api/v1/admin/trigger-contextual`). Can simulate late-delivery apology coupon (`POST /api/v1/admin/simulate-late-delivery`). Can view all challenges and badges. Can manage bundle templates. Can edit `fssai_verified` and `restaurant_verified` flags.

## 13. Performance / Reliability / Security Coverage

### Performance
- Express reorder page: single indexed query on `orders` table grouped by `menu_item_id` (top 3). Expected <50ms.
- Trust badges: returned as part of existing restaurant API. No extra query.
- Freshness countdown: entirely client-side after initial `prepared_at` timestamp. No polling.
- Speed promise timer: client-side countdown from `confirmed_at` + `speed_promise_minutes`. No polling.
- Smart bundles: single query on `bundles` table by `restaurant_id` and `trigger_item_id` (indexed). Expected <10ms.
- Contextual deals: single query on `contextual_deals` with `is_active=true` and time range. Expected <10ms.
- Challenges and badges: single query per user on `user_challenges` and `user_badges`. Indexed by `user_id`. Expected <20ms.
- BhojanGo Sound: Web Audio API synthesis is instantaneous (no network fetch). No performance impact.
- Haptics: `navigator.vibrate` is hardware-level, no CPU cost.

### Reliability
- Trust badge graceful degradation: if `fssai_license_number` is NULL, the FSSAI badge is hidden. No error shown.
- Freshness countdown: if `prepared_at` is NULL, freshness badge is hidden. Item displays normally.
- Speed promise: if `speed_promise_minutes` is NULL, badge is hidden. Order proceeds without promise.
- Late delivery coupon: idempotent check (`apology_coupon_generated` flag prevents duplicate coupons). If coupon creation fails, logged but order still completes.
- Bundle application: server validates that all `bundle_items` exist and are active before adding to cart. Invalid bundle returns 400.
- Contextual deal expiry: client-side auto-hide when `expires_at` passes. Server-side filter on every request.
- Challenge progress: atomic increment on order creation. Race conditions mitigated by DB-level counter (not read-modify-write).
- Sound/haptic settings: stored in localStorage (or user profile). Default gracefully when settings missing.

### Security
- Express reorder: only returns user's own order history. Server filters by `user_id` from JWT.
- Trust badge data: `fssai_license_number` is public (it's a regulatory license), so no restriction needed.
- Speed promise manipulation: `speed_promise_met` is server-calculated from timestamps. Client cannot fake it.
- Apology coupon: generated server-side only on valid late delivery. Client cannot self-generate.
- Bundle pricing: `bundle_price` is server-defined. Client cannot override with custom price.
- Contextual deals: admin-only creation. Read-only for customers.
- Challenge rewards: server validates `status='completed'` before allowing claim. Client cannot claim unearned rewards.
- All new endpoints use existing auth middleware. No new auth patterns introduced.

## 14. Novelty / Differentiation Coverage

At score 8, differentiation is about **emotional and sensory identity** — making BhojanGo feel like a living product, not a transactional tool.

- **Signature Ordering Flow:** Speed as a feature. Two-tap reorder is faster than any competitor's reorder flow (which requires 4-6 taps minimum). PWA shortcuts make BhojanGo feel like a native app with deep integrations.
- **Trust Architecture:** Three-layer trust is unique. Most platforms show a rating and maybe a "verified" badge. BhojanGo makes trust a visual hierarchy: government (FSSAI) → platform (Restaurant Verified) → individual (Rider Verified). This builds confidence at every decision point.
- **Freshness Currency:** "Made X minutes ago" is rare in food delivery. Most apps show static menu items. Real-time freshness makes BhojanGo feel like a live kitchen, not a static catalog. The "Still hot" indicator promises temperature, not just timeliness.
- **Speed Promises with Consequences:** "30 min or free" exists in pizza delivery but is rare in aggregator apps. The auto-generated apology coupon turns a negative (late delivery) into a positive (surprise delight). Competitors make users complain for compensation; BhojanGo proactively apologizes.
- **Smart Bundles:** Order-level upselling that feels helpful, not pushy. "Complete your meal" is contextually triggered (only when cart lacks sides). Bundle builder UI makes it visual and tangible. Bundles increase average order value while improving customer satisfaction.
- **Contextual Deals:** Location + time + weather + event awareness makes deals feel alive and personal. Static promo codes feel corporate; contextual deals feel like a friend who knows what you need. Rainy day soup discounts and cricket match combos are culturally specific and emotionally resonant (especially for Indian market).
- **Gamified Ordering:** Challenges and badges create engagement loops beyond the transaction. "Chef's Challenge" encourages exploration. "Explorer Badge" rewards loyalty to the platform, not just a restaurant. Visible badges on profile create social signaling.
- **BhojanGo Sound:** Unique audio identity. No competitor has a brand-owned notification sound synthesized specifically for their app. The ascending chime is optimistic and appetite-inducing.
- **Signature Empty States:** Empty screens are usually dead ends. BhojanGo turns them into delight moments. The sad plate animation and confetti burst make users smile, reducing bounce rate.
- **Haptic Design:** Physical feedback creates a subconscious connection. Custom vibration patterns make the app feel tactile and responsive. It's a sensory layer most apps ignore.
- **Micro-Copy Voice:** Tone is the most underrated differentiator. Friendly, food-loving copy makes every interaction feel human. "Yum incoming!" is memorable. "Oops, our kitchen got too hot" is charming. This voice is defensible — it's not a feature competitors can copy overnight.

**Differentiators deferred to higher scores:**
- Real PWA background sync for true lock screen widgets (PR.08+).
- Real-time temperature sensors for freshness validation (ND.09+ — IoT).
- ML-driven contextual deal prediction (ND.09+).
- Multi-tier subscription challenges with real prizes (ND.09+).
- Custom ringtone downloads for BhojanGo Sound (PR.09+).
- Advanced haptic patterns for complex gestures (PR.09+).

## 15. Implementation Work Items

### IP.ND.08.001 — Express Reorder Flow (PWA + Fast Path)
- **Category:** Frontend + Backend
- **Implementation Scope:** Add PWA manifest with `shortcuts` array for "Reorder Usual" and "Browse Near Me." Create `/express-reorder` page showing user's top 3 most-ordered items as large cards with one-tap "Order Again" buttons. Backend: `GET /api/v1/users/me/express-reorder` returns top 3 frequent items with last order details. Tapping "Order Again" pre-fills checkout with item, last address, last payment method. Seed data required: ensure users have sufficient order history.
- **Acceptance Criteria:**
  1. PWA manifest includes at least 2 shortcuts.
  2. `/express-reorder` page loads and displays top 3 items.
  3. Tapping "Order Again" opens checkout with item pre-filled.
  4. Total taps from PWA shortcut to placed order is <= 3.
  5. Works on mobile and desktop.
- **Evidence Required:** Screenshot of PWA manifest shortcuts. Screenshot of `/express-reorder` page. Screen recording: tap shortcut → tap reorder → place order.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.002 — Trust Architecture (Three-Layer Badges)
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Extend `restaurants` table: `fssai_license_number`, `fssai_verified`, `restaurant_verified`, `restaurant_verified_at`. Extend `delivery_partners`: `rider_verified`, `verification_documents` JSONB, `total_deliveries`. Backend: return trust fields in restaurant and rider APIs. Frontend: `<TrustBadgeStack />` on restaurant cards (orange FSSAI shield, green verified check, blue rider helmet). `<TrustDetail />` expandable section on restaurant detail. Rider card on order tracking shows verification badge and stats. Seed: populate trust data for 100% of restaurants and riders.
- **Acceptance Criteria:**
  1. Restaurant cards show visible trust badges (at least 1 layer).
  2. Restaurant detail has expandable trust section.
  3. Order tracking shows rider verification status and delivery count.
  4. Unverified layers are gracefully hidden.
  5. Trust badge colors match semantic meaning.
- **Evidence Required:** Screenshot: restaurant card with badge stack. Screenshot: trust detail expanded. Screenshot: rider card on order tracking. DB query: `SELECT fssai_verified, restaurant_verified FROM restaurants`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.003 — Freshness Currency (Real-Time Countdown)
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Extend `menu_items` table: `prepared_at` TIMESTAMP. Backend: include `prepared_at` in menu API response. Frontend: `<FreshnessBadge />` overlay on menu item cards showing "Made {N} min ago" with pulsing dot (green <15 min, yellow 15-30 min, orange >30 min). Client-side countdown updates every 60 seconds. `<StillHotIndicator />` on order tracking (thermometer + flame when ETA <15 min). Seed: set `prepared_at` for all menu items.
- **Acceptance Criteria:**
  1. Menu item cards show freshness badge with pulsing dot.
  2. Badge color changes based on age (green/yellow/orange).
  3. Countdown updates in real-time without page refresh.
  4. Order tracking shows "Still hot" when ETA <15 min.
  5. Gracefully hidden when `prepared_at` is NULL.
- **Evidence Required:** Screenshot: menu with freshness badges. Screen recording: wait 2 min, observe badge update. Screenshot: order tracking with "Still hot."
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.004 — Speed Promises + Late Delivery Apology
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** Extend `restaurants` table: `qualifies_for_speed_promise` BOOLEAN. Extend `orders` table: `speed_promise_minutes`, `speed_promise_met`, `apology_coupon_generated`. Backend: set `speed_promise_minutes=30` on order creation for qualifying restaurants. On delivery, compare actual duration to promise. If late and no coupon generated, auto-create offer in `offers` table with code `SORRY{LAST4}`. Frontend: `<SpeedPromiseBadge />` gold badge on qualifying restaurant cards. `<SpeedPromiseTimer />` live countdown (MM:SS) on order tracking. `<LateApologyBanner />` auto-appears in wallet/order page within 1 min of late delivery. Seed: mark 30% of restaurants as qualifying.
- **Acceptance Criteria:**
  1. Qualifying restaurant cards show "30 min or free" badge.
  2. Order tracking shows live countdown timer.
  3. Timer turns red in last 5 minutes.
  4. Late delivery auto-generates apology coupon (`SORRYXXXX`).
  5. Coupon is visible in wallet with 7-day expiry.
- **Evidence Required:** Screenshot: speed promise badge. Screenshot: countdown timer on tracking. Screenshot: late apology banner. DB query: `SELECT * FROM offers WHERE code LIKE 'SORRY%'`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.005 — Smart Bundles at Checkout
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** New `bundles` table: `id`, `restaurant_id`, `name`, `trigger_item_id`, `bundle_items` JSONB, `bundle_price`, `is_active`. Backend: `GET /api/v1/restaurants/{id}/bundles` and `POST /api/v1/cart/apply-bundle`. Frontend: `<SmartBundleCard />` appears in cart when trigger item is present. Shows bundle name, items, savings. `<BundleBuilder />` side-by-side mini cards for drink/dessert/combo. One-tap adds bundle at discounted price. Checkout shows "Bundle savings" line item. Seed: create 3-5 bundles per restaurant.
- **Acceptance Criteria:**
  1. Bundle card appears when cart contains trigger item.
  2. Bundle builder shows drink/dessert/combo options.
  3. Tapping adds bundle items at discounted price.
  4. Checkout shows bundle savings as line item.
  5. Invalid bundle returns error gracefully.
- **Evidence Required:** Screenshot: bundle card in cart. Screenshot: bundle builder. Screenshot: checkout with bundle savings line item. API output: `GET /api/v1/restaurants/{id}/bundles`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.006 — Contextual Deals Engine
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** New `contextual_deals` table: `id`, `title`, `description`, `discount_percent`, `trigger_type`, `trigger_params`, `restaurant_id`, `starts_at`, `expires_at`, `is_active`, `image_url`. Backend: `GET /api/v1/deals/contextual` returns active deals. Mock heuristics: time of day (lunch/dinner), weather (admin trigger: rainy/mock), events (admin trigger: cricket/mock). `POST /api/v1/admin/trigger-contextual` admin endpoint. Frontend: `<ContextualDealBanner />` on homepage hero. `<ContextualDealPill />` on restaurant cards. Deal shows expiry countdown. Auto-hides when expired. Seed: create 5-10 contextual deal templates.
- **Acceptance Criteria:**
  1. Homepage shows contextual deal banner when active deals exist.
  2. Restaurant cards show deal pills for qualifying deals.
  3. Deals have visible expiry countdown.
  4. Admin trigger endpoint generates deals on demand.
  5. Expired deals auto-hide from all UI.
- **Evidence Required:** Screenshot: homepage contextual banner. Screenshot: restaurant card with deal pill. Screen recording: admin triggers rainy deal → homepage updates. API output: `GET /api/v1/deals/contextual`.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.007 — Gamified Ordering (Challenges + Badges)
- **Category:** Backend + Frontend + Data
- **Implementation Scope:** New `user_challenges` table: `id`, `user_id`, `challenge_type`, `progress`, `target`, `status`, `completed_at`, `reward_type`, `reward_value`. New `user_badges` table: `id`, `user_id`, `badge_type`, `badge_tier`, `unlocked_at`, `display_order`. Backend: `GET /api/v1/users/me/challenges`, `GET /api/v1/users/me/badges`, `POST /api/v1/users/me/challenges/{id}/claim`. Update order creation to increment counters. Frontend: `<ChallengeWidget />` on profile/homepage. `<BadgeGallery />` grid. Confetti animation on completion. Reward auto-credited. Seed: create default challenges for all users.
- **Acceptance Criteria:**
  1. Profile shows active challenges with progress bars.
  2. Challenge progress updates after qualifying orders.
  3. Completion triggers confetti + reward credit.
  4. Badges appear in gallery with unlock dates.
  5. Locked badges are grayscale; unlocked are colorful.
- **Evidence Required:** Screenshot: challenge widget (2/3 progress). Screenshot: badge gallery. Screen recording: place qualifying order → progress updates → complete challenge → confetti. API output: challenges and badges endpoints.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.008 — BhojanGo Sound (Unique Notification Chime)
- **Category:** Frontend
- **Implementation Scope:** Web Audio API synthesized chime: sine wave oscillator, ascending C5-E5-G5 over 800ms with exponential decay. Encapsulate in `playBhojanGoChime()` utility. Trigger on: order status update, order confirmation, challenge complete, badge unlock. Settings: "Sound" toggle in user settings (default ON). Respects `prefers-reduced-motion`.
- **Acceptance Criteria:**
  1. Chime plays on order confirmation.
  2. Chime plays on challenge completion.
  3. Sound is synthesized (no external audio file).
  4. Toggle in settings disables all chimes.
  5. Chime does not play if `prefers-reduced-motion` is set.
- **Evidence Required:** Screen recording: place order → chime plays. Settings: toggle sound OFF → place order → no chime. Code snippet of `playBhojanGoChime()`.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.009 — Signature Empty States
- **Category:** Frontend
- **Implementation Scope:** `<EmptyCartState />` — animated SVG sad plate with wandering fly (CSS keyframes, figure-8 path, 8s loop). Text: "Your plate is waiting..." with floating animation. CTA: "Browse Restaurants." `<EmptyOrdersState />` — SVG chef with covered platter + steam animation. CSS confetti burst (30 colored dots, falling keyframes). Text: "First meal magic awaits!" CTA: "Find Your First Bite." Empty search results: shrug illustration. All empty states are full-screen, center-aligned, responsive.
- **Acceptance Criteria:**
  1. Empty cart shows animated plate illustration with text and CTA.
  2. Empty orders shows confetti burst + chef illustration.
  3. Animations loop smoothly without performance issues.
  4. CTAs navigate to correct pages.
  5. Empty states render correctly in dark mode.
- **Evidence Required:** Screenshots: empty cart, empty orders. Screen recording: empty orders showing confetti burst animation.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.010 — Haptic Design (Custom Vibration Patterns)
- **Category:** Frontend
- **Implementation Scope:** Vibration API integration via `useHaptic(actionType)` hook. Haptic chart: add-to-cart (50ms pulse), remove (30ms), place order (double 30ms), confirm (triple 20ms), error (100ms), challenge complete (50-30-50-30-50ms). Desktop fallback: visual proxy (button scale pulse + ripple). Settings: "Haptic Feedback" toggle (default ON mobile, OFF desktop). Graceful fallback when Vibration API unavailable.
- **Acceptance Criteria:**
  1. Mobile device vibrates on add-to-cart, place order, order confirmed.
  2. Desktop shows visual haptic proxy (button pulse/ripple).
  3. Haptic patterns differ by action type.
  4. Toggle in settings disables all haptics.
  5. Graceful fallback when API unavailable (no console errors).
- **Evidence Required:** Screen recording on mobile: add item → vibration. Settings: toggle OFF → add item → no vibration. Code snippet of haptic chart.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.011 — Micro-Copy Voice (Food-Loving Tone)
- **Category:** Frontend
- **Implementation Scope:** Centralized `copy.ts` or `copy.json` file containing all user-facing strings, organized by screen and component. Replace all generic messages with food-themed voice. Examples: "Yum incoming!" (confirmation), "Almost there..." (preparing), "Hot and on the way!" (picked up), "Added to your feast!" (cart add), "Oops, our kitchen got too hot" (error). Hindi and English versions. Document tone guidelines. No raw strings in components — all import from copy file.
- **Acceptance Criteria:**
  1. All toasts use food-loving tone (zero generic "Success" messages).
  2. Order status messages are personalized and food-themed.
  3. Empty state copy is warm and inviting.
  4. Error messages are charming, not corporate.
  5. Copy file is centralized and easily editable.
- **Evidence Required:** Screenshot: cart add toast ("Added to your feast!"). Screenshot: order confirmation ("Yum incoming!"). Screenshot: error state ("Oops, our kitchen got too hot"). Copy file snippet showing structure.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

### IP.ND.08.012 — Seed Data Completion for ND.08
- **Category:** Data
- **Implementation Scope:** Populate all seed data required for ND.08:
  1. `restaurants`: `fssai_license_number`, `fssai_verified` (80% true), `restaurant_verified` (60% true), `restaurant_verified_at`, `qualifies_for_speed_promise` (30% true).
  2. `menu_items`: `prepared_at` for 100% of items (random times within last 30 min).
  3. `delivery_partners`: `rider_verified` (90% true), `total_deliveries` (random 50-2000), `verification_documents` JSONB mock.
  4. `bundles`: 3-5 bundles per restaurant with realistic trigger items and savings.
  5. `contextual_deals`: 5-10 deal templates with varied trigger types.
  6. `user_challenges`: default challenges for all seeded users (cuisine_explorer target=3, restaurant_explorer target=5).
  7. `user_badges`: seed 1-2 bronze badges per user for demo.
- **Acceptance Criteria:**
  1. 100% of restaurants have trust badge fields populated.
  2. 100% of menu items have `prepared_at`.
  3. 100% of delivery partners have verification data.
  4. 3-5 bundles exist per restaurant.
  5. 5-10 contextual deal templates exist.
  6. All seeded users have at least 1 active challenge.
- **Evidence Required:** DB query outputs confirming population of all extended and new tables.
- **Priority:** P0
- **Effort:** M
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Express reorder PWA shortcuts exist and work.
- [ ] `/express-reorder` page displays top 3 frequent items.
- [ ] One-tap reorder from express page opens pre-filled checkout.
- [ ] Trust badges visible on restaurant cards (FSSAI, Verified, Rider).
- [ ] Trust detail expandable on restaurant detail page.
- [ ] Rider verification visible on order tracking.
- [ ] Freshness badge shows "Made N min ago" with color-coded dot.
- [ ] Freshness countdown updates in real-time.
- [ ] "Still hot" indicator appears on order tracking when ETA <15 min.
- [ ] Speed promise badge visible on qualifying restaurant cards.
- [ ] Live countdown timer visible on order tracking.
- [ ] Late delivery auto-generates apology coupon (`SORRYXXXX`).
- [ ] Smart bundle card appears in cart when trigger item present.
- [ ] Bundle builder allows one-tap bundle addition at discounted price.
- [ ] Checkout shows bundle savings as line item.
- [ ] Contextual deal banner visible on homepage when deals active.
- [ ] Restaurant cards show contextual deal pills.
- [ ] Deals have expiry countdown and auto-hide when expired.
- [ ] Admin trigger endpoint generates contextual deals on demand.
- [ ] Active challenges visible on profile and homepage.
- [ ] Challenge progress updates after qualifying orders.
- [ ] Challenge completion triggers confetti + reward credit.
- [ ] Badge gallery shows earned badges with tiers and unlock dates.
- [ ] BhojanGo chime plays on order confirmation and challenge completion.
- [ ] Sound toggle in settings disables chime.
- [ ] Empty cart shows animated sad plate illustration.
- [ ] Empty orders shows confetti + chef illustration.
- [ ] Haptic feedback triggers on mobile for key actions.
- [ ] Haptic toggle in settings disables vibrations.
- [ ] Desktop shows visual haptic proxy.
- [ ] All user-facing copy uses food-loving tone.
- [ ] Centralized copy file exists and is used by all components.
- [ ] All new UI follows BhojanGo design system.
- [ ] All features render correctly in dark mode.
- [ ] Seed data fully supports all ND.08 features.

## 17. Evidence Required

- Screenshots:
  - PWA manifest shortcuts (browser dev tools or mobile install).
  - `/express-reorder` page with top 3 cards.
  - Pre-filled checkout after express reorder.
  - Restaurant card with three trust badges.
  - Trust detail section expanded on restaurant detail.
  - Rider verification card on order tracking.
  - Menu item with freshness badge (green dot).
  - Menu item with yellow freshness badge (>15 min).
  - Order tracking with "Still hot" indicator.
  - Restaurant card with "30 min or free" gold badge.
  - Order tracking with live countdown timer.
  - Late apology banner with coupon code.
  - Cart with smart bundle card.
  - Bundle builder with drink/dessert/combo cards.
  - Checkout with bundle savings line item.
  - Homepage contextual deal banner (rainy day mock).
  - Restaurant card with contextual deal pill.
  - Profile challenges tab with progress bars.
  - Badge gallery with bronze/silver/gold tiers.
  - Challenge completion confetti animation.
  - Settings page with Sound toggle.
  - Empty cart animated state.
  - Empty orders animated state.
  - Settings page with Haptic Feedback toggle.
  - Toast: "Yum incoming!" on confirmation.
  - Toast: "Added to your feast!" on cart add.
  - Error state: "Oops, our kitchen got too hot."
- Screen recordings:
  - PWA shortcut → express reorder → place order (with chime + haptic).
  - Browse restaurants → tap trust badges → expand trust detail.
  - Add item to cart → observe freshness badge → wait for countdown update.
  - Place order at qualifying restaurant → watch countdown timer → simulate late delivery → observe apology coupon.
  - Add main dish to cart → bundle card appears → tap bundle → checkout shows savings.
  - Admin triggers contextual deal → homepage updates → tap deal → restaurant detail.
  - Place qualifying orders → challenge progress updates → complete challenge → confetti + reward.
  - Toggle sound OFF → place order → no chime.
  - Empty cart animation loop.
  - Empty orders confetti burst.
  - Toggle haptics OFF → add to cart → no vibration.
- API evidence:
  - `curl` output for `GET /api/v1/users/me/express-reorder`.
  - `curl` output for restaurant detail showing trust fields.
  - `curl` output for menu showing `prepared_at`.
  - `curl` output for order showing speed promise fields.
  - `curl` output for `GET /api/v1/restaurants/{id}/bundles`.
  - `curl` output for `GET /api/v1/deals/contextual`.
  - `curl` output for `GET /api/v1/users/me/challenges`.
  - `curl` output for `GET /api/v1/users/me/badges`.
- DB evidence:
  - Query confirming trust badge fields populated for 100% of restaurants.
  - Query confirming `prepared_at` for 100% of menu items.
  - Query confirming bundles exist per restaurant.
  - Query confirming contextual deals seeded.
  - Query confirming challenges and badges exist for users.

## 18. Dependencies

### External Tools
- PostgreSQL (for new tables: bundles, contextual_deals, user_challenges, user_badges).
- Node.js + pnpm (frontend build).
- Lucide React (icon library — already used from ND.02).
- Web Audio API (built into modern browsers — no external library needed).
- Vibration API (built into mobile browsers — no external library needed).

### Internal Dependencies
- **PR.04 or PR.05 must be complete:** Stable core ordering loop is prerequisite.
- **ND.02 (Distinctive Visual Identity) must be complete:** Design system must be applied.
- **ND.03 (Small Convenience Features) must be complete:** Filters, restaurant cards, menu discovery — all required as foundation.
- **ND.05 (Retention Focused Uniqueness) must be complete:** Loyalty system, smart reorder, favorites, saved preferences — assumed stable.
- **ND.06 (Marketplace Specific Differentiation) must be complete:** Group ordering, nutritional transparency, fee calculator — assumed stable.
- **ND.07 (Smart Personalization) must be complete:** AI suggestions, predictive ordering, dietary tracking — assumed stable.
- **Auth persistence** must work. Express reorder and challenges require logged-in users.
- **Order history** must be queryable for express reorder and challenge progress.
- **Restaurant API** must support trust badge fields and bundle queries.
- **Order tracking page** must exist for speed promise timer and freshness indicator.
- **Cart Zustand store** must support programmatic bundle application.
- **Toast/snackbar component** must exist for confirmation messages.
- **Modal/bottom sheet component** must exist for bundle builder.
- **Settings page** must exist for sound/haptic toggles.

## 19. Risks / Blockers

- **PWA shortcut support:** PWA shortcuts are supported on Chrome/Android and Safari/iOS 16.4+, but not universally. Mitigation: express reorder page is also accessible via in-app "Quick Reorder" button on homepage.
- **Web Audio API autoplay policy:** Browsers block audio playback without user interaction. Mitigation: BhojanGo Sound only plays after explicit user actions (tap "Place Order") or in response to user-initiated page navigation. Never autoplay on page load.
- **Vibration API iOS limitation:** Safari on iOS does not support `navigator.vibrate`. Mitigation: visual haptic proxy is the primary fallback. iOS users still get feedback via button animations.
- **Speed promise accuracy:** `speed_promise_met` calculation depends on accurate `confirmed_at` and `delivered_at` timestamps. Mitigation: server uses DB timestamps, not client clocks. Demo uses admin trigger to simulate late delivery.
- **Freshness countdown drift:** Client-side countdown can drift if tab is backgrounded. Mitigation: recalculate on `visibilitychange` event. Countdown is approximate ("Made ~12 min ago").
- **Bundle pricing validation:** Client must not trust `bundle_price` from frontend. Mitigation: server recalculates bundle total on `POST /api/v1/cart/apply-bundle`.
- **Contextual deal mock realism:** Demo contextual deals rely on admin triggers or random flags. Mitigation: clearly document that weather/event APIs are mocked. Admin trigger endpoint ensures reliable demos.
- **Challenge progress race conditions:** Multiple simultaneous orders could race on counter increment. Mitigation: use DB-level `UPDATE user_challenges SET progress = progress + 1` (atomic increment).
- **Micro-copy localization:** Hindi translations require native fluency review. Mitigation: start with English only. Hindi translations can be added iteratively.
- **Empty state animation performance:** CSS animations on SVG elements can be CPU-intensive on low-end devices. Mitigation: use `transform` and `opacity` only (GPU-accelerated). Reduce animation complexity on mobile.

## 20. Exit Criteria

- All P0 work items (IP.ND.08.001 through IP.ND.08.007, IP.ND.08.011–012) implemented and verified.
- All P1 work items (IP.ND.08.008 through IP.ND.08.010) implemented and verified.
- Express reorder complete: PWA shortcuts + `/express-reorder` page + pre-filled checkout.
- Trust architecture complete: three-layer badges on cards, expandable detail, rider verification.
- Freshness currency complete: real-time countdown, color-coded dots, "Still hot" indicator.
- Speed promises complete: badge, countdown timer, late delivery apology coupon.
- Smart bundles complete: trigger detection, bundle builder, checkout savings line item.
- Contextual deals complete: engine, banner, pills, expiry, admin trigger.
- Gamified ordering complete: challenges, badges, progress, rewards, confetti.
- BhojanGo Sound complete: synthesized chime, trigger points, settings toggle.
- Signature empty states complete: animated cart and orders illustrations.
- Haptic design complete: vibration patterns, desktop proxy, settings toggle.
- Micro-copy voice complete: centralized copy file, food-loving tone across all screens.
- All new UI follows BhojanGo design system, responsive, dark mode compatible.
- Evidence screenshots/recordings/API outputs captured per Section 17.
- ND.08 declared complete.

## 21. Connected Previous-Level Requirements (link to ND.07)

ND.08 directly depends on ND.07 achievements:
- **ND.07 AI Meal Suggestions:** Personalized homepage must exist as the foundation for adding express reorder shortcuts and contextual deal banners.
- **ND.07 Predictive Ordering:** Pre-filled cart at usual times must work so that express reorder (the fast-path version) can build on the same data.
- **ND.07 Dietary Goal Tracking:** Weekly protein intake dashboard must exist so that challenges can integrate nutrition goals (e.g., "Hit your protein goal 5 days this week").
- **ND.07 Personalized Deal Notifications:** Deal notification infrastructure must exist so that contextual deals can reuse the toast/banner delivery mechanism.
- **ND.07 Real-Time WebSocket:** Group cart real-time updates must work so that challenge progress can be broadcast instantly to all user sessions.
- **ND.06 Group Ordering:** Must be functional so that express reorder can offer "Reorder last group order" as an option.
- **ND.06 Nutritional Transparency:** Nutrition data must be complete so that freshness and health can be combined in messaging ("Fresh AND healthy — made 5 min ago, 24g protein").
- **ND.05 Loyalty System:** Loyalty points and tiers must be visible so that challenge rewards can integrate with the existing loyalty wallet.
- **ND.03 + ND.02:** Filters, restaurant cards, menu discovery, and design system must all be in place as UI foundations.

## 22. Connected Next-Level Requirements (link to ND.09)

ND.09 (Defensible Differentiation, score 9/10) builds on ND.08 and requires:
- Working trust architecture (IP.ND.08.002) as foundation for verified restaurant insights and trust-based search ranking.
- Working freshness currency (IP.ND.08.003) as foundation for real-time kitchen queue visibility and prep-time prediction.
- working speed promises (IP.ND.08.004) as foundation for dynamic ETA promises based on traffic, weather, and rider load.
- Working smart bundles (IP.ND.08.005) as foundation for AI-powered bundle recommendations ("People who ordered biryani also bundled raita + gulab jamun").
- Working contextual deals (IP.ND.08.006) as foundation for ML-driven deal optimization and geofenced offers.
- Working gamified ordering (IP.ND.08.007) as foundation for loyalty tiers, subscription challenges, and corporate engagement programs.
- Working BhojanGo Sound (IP.ND.08.008) as foundation for branded audio identity across all platforms (app, web, ads).
- Working signature empty states (IP.ND.08.009) as foundation for personalized empty states ("You love biryani — here's a new biryani place near you").
- Working haptic design (IP.ND.08.010) as foundation for advanced gesture feedback and accessibility haptics.
- Working micro-copy voice (IP.ND.08.011) as foundation for AI-generated personalized copy ("Good evening, Rahul! Your usual butter chicken is calling...").

ND.09 will introduce:
- Group cart real-time collaboration with split bill integration.
- Restaurant profit-share subscription tiers with analytics dashboard.
- Delivery confidence scoring (predicted on-time probability).
- Customer trust loops (verified review badges, repeat customer recognition).
- Advanced sustainability gamification (carbon offset tracking, tree planting).
- AI-generated personalized micro-copy based on user history and mood.

ND.09 will be blocked if:
- Trust badges are missing or unpopulated for >20% of restaurants.
- Freshness countdown breaks or shows negative time.
- Speed promise timer is inaccurate or apology coupon fails to generate.
- Bundle application corrupts cart state or miscalculates savings.
- Contextual deals do not auto-expire or leak across sessions.
- Challenge progress is lost on page refresh or fails to increment atomically.
- BhojanGo Sound causes browser autoplay policy violations.
- Micro-copy file is fragmented (strings hardcoded in components).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (8/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (ND.07 + prior) described | Planner | ✅ |
| 4 | Target state (ND.08 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what ND.08 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what ND.08 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered (10 journeys) | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend + data targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes (4 new tables, extended columns) | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage explains why identity features create defensible differentiation | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.ND.08.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 8 work items present | Planner | ✅ |
| 17 | Work items cover: express reorder, trust badges, freshness, speed promise, bundles, contextual deals, gamification, sound, empty states, haptics, micro-copy | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention PWA support, autoplay policy, iOS haptics, timestamp accuracy, countdown drift, bundle validation, deal mock realism, race conditions, localization, animation performance | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (ND.07) requirements listed with specific references | Planner | ✅ |
| 24 | Connected next-level (ND.09) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and >=8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required features: express reorder (PWA + fast path), trust architecture (three-layer badges), freshness currency (real-time countdown), speed promises (badge + timer + apology coupon), smart bundles (checkout builder), contextual deals (weather/time/event engine), gamified ordering (challenges + badges + rewards), BhojanGo Sound (synthesized chime), signature empty states (animated illustrations), haptic design (custom vibration patterns + desktop proxy), micro-copy voice (centralized food-loving tone), and seed data completion.
- Acceptance criteria are concrete and verifiable.
- Evidence required directly maps to acceptance criteria.
- Risks and blockers are grounded in known technical constraints (PWA shortcut support, Web Audio autoplay policy, iOS Vibration API limitation, timestamp accuracy, race conditions).
- Scope is strictly LOCAL/DEMO-SAFE: mock weather, synthesized audio (no file hosting), CSS animations, client-side haptics, admin trigger endpoints. No ML, no IoT, no real FCM, no real event APIs.
- The document addresses emotional differentiation explicitly — sound, haptics, copy, animation — which is the core objective of score 8 (strong product identity).
