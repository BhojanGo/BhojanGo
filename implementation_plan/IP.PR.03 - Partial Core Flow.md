# IP.PR.03 — Partial Core Flow

## 1. Target Score Level: 3/10

## 2. Score Meaning

At score 3/10, the app is **transactional but shaky**. A user can:
- Browse restaurants and menus (inherited from PR.02).
- Add items to cart as a logged-in user or as a guest (localStorage cart).
- View the cart with quantities, item details, and a running total.
- Proceed to a checkout form that collects address and a mock payment method.
- Place an order that creates a row in the `orders` table with `order_items` JSONB and a traversable status.
- See an order confirmation page and a list of their past orders.
- View a mock tracking timeline with static steps (not real-time).
- Cancel a pending order.

However, flows are **not fully polished**: payment is simulated locally (no real gateway calls), fee breakdowns are basic, the cart may not sync perfectly between guest and logged-in states, and tracking is mock only. Some edge cases (empty cart, network failure during checkout) are handled minimally or not at all.

## 3. Current → Target Transition

**Current (PR.02 complete):**
- Menu endpoint returns real data (OpenSearch + DB fallback).
- Auth persists across refresh via `/api/v1/me` + cookie/localStorage.
- Restaurant list and detail pages are navigable, data-rich, and resilient.
- Homepage renders with ISR, skeleton loaders exist, dark mode and mobile nav are functional.
- Cart UI does not exist or is a non-functional placeholder.
- Checkout page may render but submitting fails or creates no order.
- Order table exists in DB but no frontend order list or detail pages.
- No guest cart; unauthenticated users are redirected to login.
- Order state machine exists in code but transition enforcement is weak or inconsistent.

**Target at score 3:**
- Guest cart persists in `localStorage`; logged-in cart persists via API or hybrid sync.
- Cart page displays items with quantity steppers, veg/non-veg indicators, and totals.
- Checkout form collects delivery address (manual text entry) and shows a mock payment method selector (Card / UPI / Wallet / COD).
- Simulated payment marks order as `paid` locally without calling Stripe/Razorpay.
- Order creation endpoint validates items against current menu, calculates subtotal + delivery fee + tax, and writes `order_items` JSONB.
- Order state machine transitions are validated server-side (invalid transitions rejected with 400).
- Order confirmation page shows order ID, items, and estimated delivery time.
- Order list page shows authenticated user's past orders with status badges.
- Order detail page shows mock tracking timeline (Confirmed → Preparing → Picked Up → Delivered).
- Basic cancellation API allows cancelling `pending` or `confirmed` orders.
- Fee/tax breakdown is visible in cart and checkout.
- Delivery fee is calculated per restaurant (flat or distance-based, mock logic).

## 4. Implementation Objective

Wire the transactional core loop end-to-end: cart → checkout → simulated payment → order creation → confirmation → order list → mock tracking → cancellation. This is the first tier where the app demonstrates a full food-ordering journey, even if payment and tracking are mocked. Every screen must show real data at some point; no purely static placeholders.

## 5. Scope (local/demo-safe only)

1. **Guest/localStorage cart persistence** — Cart saved to `localStorage` for unauthenticated users. Survives refresh.
2. **Logged-in cart persistence (hybrid)** — On login, localStorage cart optionally syncs to backend (or remains local until checkout). At minimum, checkout attaches `user_id` when authenticated.
3. **Quantity stepper in cart** — + / - buttons per item. Minimum 1, remove item when quantity reaches 0.
4. **Cart total breakdown** — Subtotal, delivery fee, platform fee, tax (GST 5% mock), grand total.
5. **Veg/non-veg indicator on cart item** — Green dot / red dot icon per item.
6. **Checkout form + address fields** — Manual text inputs: street, city, pincode, phone, landmark. No autocomplete, no map pin.
7. **Payment method radio mock** — Card, UPI, Wallet, Cash on Delivery. No real payment SDK calls. Selecting "Card" or "UPI" shows a disabled mock form. Selecting "COD" or "Wallet" proceeds immediately.
8. **Simulated payment processing** — On "Place Order", frontend calls backend with `payment_method`. Backend marks `payment_status = 'paid'` (or `pending` for COD) without calling external gateway.
9. **Order creation validation** — Backend validates `restaurant_id` exists, each `menu_item_id` exists and belongs to restaurant, `quantity > 0`, and prices match current DB prices (prevent tampering).
10. **Order state machine server-side enforcement** — Valid transitions only: `pending → confirmed → preparing → ready_for_pickup → picked_up → delivered`. `cancelled` allowed only from `pending` or `confirmed`. Invalid transition returns 400 with message.
11. **Order confirmation page** — `/orders/confirmation/[id]` or modal showing order summary, estimated delivery time, and CTA to "Track Order" or "Order More".
12. **Order list page (authenticated)** — `/orders` shows list of past orders with restaurant name, total, status badge, date. Sorted by `created_at DESC`.
13. **Order detail with mock timeline** — `/orders/[id]` shows order items, address, payment method, and a vertical stepper timeline with static steps. Current step highlighted based on `status`.
14. **Fee breakdown display** — Itemized lines visible in cart and checkout: Items total, Delivery Fee, Platform Fee, Tax, Discount (if any), Grand Total.
15. **Basic cancellation API** — `PATCH /api/v1/orders/{id}/cancel` with optional `reason`. Allowed only for `pending` or `confirmed`. Updates status to `cancelled`.
16. **Delivery fee calculation** — Flat ₹30 per restaurant (mock) or simple distance-based multiplier. Displayed in cart and checkout.
17. **Cross-restaurant cart guard** — If user adds items from Restaurant A then Restaurant B, show alert: "Your cart contains items from another restaurant. Replace cart?" with Cancel / Confirm.

## 6. Out of Scope

- Real payment gateway calls (Stripe, Razorpay, UPI deep linking).
- Real-time driver tracking or map integration.
- Push notifications, SMS, email dispatch.
- Favorites, reorder, loyalty points redemption.
- Offers, coupons, promo codes.
- Admin / owner / driver flows.
- Full refund logic (wallet creditback).
- Group ordering or multi-restaurant checkout.
- Address autocomplete, geolocation, map pin selection.
- WebSocket reconnection logic for live tracking.
- Review listing, review submission post-delivery.
- Order editing after placement.
- Prep-time estimation, serviceability radius enforcement.
- Open/closed logic for restaurants.
- E2E tests, integration tests, load tests.
- Advanced animations (fly-to-cart, page transitions).

## 7. Required Capabilities

- Guest cart persists and survives page refresh.
- Authenticated user can checkout and create an order.
- Backend validates order creation against live menu data.
- Order state machine rejects invalid transitions.
- Fee/tax breakdown is calculated and displayed at cart and checkout.
- Order confirmation, list, and detail pages render real order data.
- Mock tracking timeline reflects current order status.
- Cancellation works for pending/confirmed orders.
- Payment is simulated locally (no external provider dependency for demo).
- Cross-restaurant cart guard prevents accidental mixing.

## 8. Key User Journeys

### Journey 8.1 — Guest Browses and Checks Out
1. User opens app without logging in.
2. User browses restaurants, taps a restaurant, views menu.
3. User taps "Add" on a menu item. Item added to cart. Cart badge updates.
4. User navigates to `/cart`. Items visible with quantity steppers and totals.
5. User taps "Proceed to Checkout". Redirected to `/checkout`.
6. User enters address manually (street, city, pincode, phone).
7. User selects "Cash on Delivery" radio button.
8. User taps "Place Order". Backend creates order with `payment_status = 'pending'`.
9. User sees order confirmation page with order ID.
10. (Guest cannot view order list; user is prompted to sign up to track.)

### Journey 8.2 — Logged-In User Places Order
1. User logs in. Auth persists.
2. User adds 2 items from Restaurant A to cart. Cart persists to `localStorage`.
3. User navigates to `/cart`, changes quantity from 1 → 2 using stepper. Total recalculates.
4. User taps "Proceed to Checkout". Address form pre-filled from last order (if any) or empty.
5. User selects "Pay with Wallet" (mock). Place Order button active.
6. User taps "Place Order". Backend validates items, calculates fees, creates order, marks `payment_status = 'paid'`.
7. User sees order confirmation with summary and "Track Order" CTA.
8. User navigates to `/orders`. Order appears in list with status badge "Confirmed".
9. User taps order. Sees detail page with mock timeline: Confirmed (active), Preparing (upcoming), etc.
10. User taps "Cancel Order" (status is still `confirmed`). Order status changes to `cancelled`.

### Journey 8.3 — Cross-Restaurant Cart Guard
1. User adds Paneer Tikka from Restaurant A.
2. User browses Restaurant B, taps "Add" on a pizza.
3. Frontend detects different `restaurant_id` in cart vs new item.
4. Alert modal appears: "Your cart has items from Spice Garden. Start a new cart for Pizza Palace?"
5. User taps "Start New Cart". Previous cart cleared; pizza added.
6. Cart badge shows 1 item.

### Journey 8.4 — Order State Machine Enforcement
1. Admin attempts to PATCH order status from `delivered` → `pending` via API.
2. Server rejects with 400: "Invalid status transition: delivered → pending".
3. Frontend API client surfaces error toast.

## 9. Technical Coverage

### Backend
- `order-svc`: Order creation endpoint with validation (`restaurant_id`, `menu_item_id`, price integrity, `quantity > 0`). Fee calculation (subtotal, delivery_fee, platform_fee, tax). `order_items` JSONB schema enforcement.
- `order-svc`: `GET /api/v1/orders` (list for authenticated user), `GET /api/v1/orders/{id}` (detail), `PATCH /api/v1/orders/{id}/cancel`.
- `order-svc`: State machine validation function. Valid transitions hardcoded. Invalid transition returns 400.
- `order-svc`: Simulated payment endpoint or integrated into create order: accepts `payment_method`, sets `payment_status` locally.
- `restaurant-svc`: Menu item price validation endpoint (or order-svc queries restaurant-svc / DB directly for current prices during creation).
- `user-svc`: Auth token validation for protected order endpoints (existing middleware).
- `payment-svc` / `wallet-svc` (if exists): Mock wallet deduction for "Wallet" payment method (local only, no real provider).

### Frontend
- Next.js App Router pages: `/cart`, `/checkout`, `/orders`, `/orders/[id]`, `/orders/confirmation/[id]`.
- Zustand cart store with `localStorage` persistence for guest users. Cart schema: `{ items: [{ menuItemId, name, price, quantity, isVeg, restaurantId, imageUrl }], restaurantId, restaurantName }`.
- Cart page component with quantity stepper, item row, fee breakdown, and "Proceed to Checkout" CTA.
- Checkout page with address form fields, payment method radio group, order summary sidebar/column, and "Place Order" button with disabled state until address + payment selected.
- Order confirmation page showing order summary.
- Order list page fetching from `GET /api/v1/orders`.
- Order detail page fetching from `GET /api/v1/orders/{id}` + rendering mock timeline.
- Cross-restaurant cart guard modal.
- Axios call to `POST /api/v1/orders` and `PATCH /api/v1/orders/{id}/cancel`.
- Error toast on failed order creation (validation error, network error).
- Loading states (skeletons inherited from PR.02) on order list/detail.

### Data
- Uses existing `orders`, `order_items` (JSONB), `order_status_history` tables.
- Uses existing `menu_items`, `restaurants` tables for validation.
- Uses existing `users`, `addresses` tables for authenticated checkout.
- No new migrations required for core schema; existing schema already supports orders + status history.

## 10. UI / UX Coverage

- **Cart page:** Clean item list with image thumbnail, name, price, quantity stepper (+/-), veg/non-veg dot, remove button. Sticky footer with total and "Proceed" CTA.
- **Checkout page:** Two-column layout on desktop (form left, summary right). Address form with labels and validation errors (red text). Payment method radio cards with icons. Order summary collapsible on mobile.
- **Order confirmation:** Centered card with checkmark icon, order number, estimated time, and primary CTA.
- **Order list:** Card list with restaurant image, name, total amount (bold), status badge (colored pill), date. Empty state with illustration if no orders.
- **Order detail:** Header with status badge and date. Itemized list. Address block. Timeline: vertical line with dots, current step filled, past steps green, future steps gray. Static estimated times per step.
- **Fee transparency:** Every total screen shows breakdown. Builds user trust.
- **Dark mode:** All new pages (`/cart`, `/checkout`, `/orders/*`) support `dark:` variants (inherited from PR.02 tokens).
- **Mobile:** Bottom nav cart badge reflects item count. Checkout form scrolls smoothly. Tap targets >= 48px.
- **Accessibility:** Radio groups have `role="radiogroup"`. Form inputs have associated labels. Buttons have clear focus states.

## 11. Data / Model Coverage

- `orders` table (existing): `id`, `user_id` (nullable for guest — but guest orders not listed; consider guest checkout limitation), `restaurant_id`, `status`, `payment_status`, `payment_method`, `total_amount`, `subtotal`, `delivery_fee`, `platform_fee`, `tax_amount`, `discount_amount`, `delivery_address` (JSONB), `order_items` (JSONB), `created_at`, `updated_at`.
- `order_status_history` table (existing): `id`, `order_id`, `status`, `changed_at`, `changed_by`.
- `order_cancellations` — if not existing, cancellation reason stored in `orders` as nullable `cancellation_reason` (acceptable for PR.03).
- `menu_items` validation fields: `id`, `restaurant_id`, `price`, `is_veg`, `is_active`.
- No new tables required. Existing schema is sufficient.

## 12. Role / Permission Coverage

- `customer` role: Can create orders (own user_id), list own orders, view own order detail, cancel own pending/confirmed orders.
- `restaurant_owner`: Cannot create customer orders (UI not scoped), but can view orders for their restaurant (admin dashboard scope, not PR.03).
- `delivery_partner`, `admin`, `super_admin`, `support`: Not involved in customer ordering flow.
- Order endpoints enforce ownership: `GET /api/v1/orders` returns only `user_id = current_user.id`. Order detail validates `user_id` matches.
- Cancellation endpoint validates order belongs to current user.

## 13. Performance / Reliability / Security Coverage

### Performance
- Order creation is a single POST with inline validation. No N+1 queries; use `select` + `where id in (...)` for menu item validation.
- Order list paginated (default 20 items). Cursor-based or offset pagination acceptable.
- Cart operations are client-side (Zustand + localStorage); instant UI response.

### Reliability
- Order creation wrapped in DB transaction. If validation fails, return 422 with field-level errors.
- If menu item price mismatch detected (frontend tampering), reject order with 422 and clear message: "Item prices have changed. Please refresh your cart."
- Network failure during checkout: show error toast, keep form state, allow retry.
- Guest cart survives refresh via localStorage. Survives app crash if browser storage intact.

### Security
- No raw payment credentials transmitted (mock only).
- Order endpoints require valid JWT (except guest checkout if supported; if not, redirect to login).
- Price validation prevents frontend price tampering.
- `user_id` on order is set server-side from JWT `sub`, not from request body.
- Delivery address is stored as JSONB; no PII beyond what user explicitly enters.

## 14. Novelty / Differentiation Coverage

At score 3, novelty is minimal but present:
- **Veg/non-veg indicator in cart** — Indian market necessity, visible at every step.
- **Fee transparency** — Breakdown visible in cart and checkout builds trust. Not all apps show this early.
- **Mock tracking timeline** — Even static steps give users a sense of progress.
- **Cross-restaurant cart guard** — Prevents accidental mixing, a small but useful UX touch.

Full novelty differentiators (loyalty, meal rescue, group ordering, nutrition info) are explicitly deferred to PR.05+.

## 15. Implementation Work Items

### IP.PR.03.001 — Guest Cart Persistence in localStorage
- **Category:** Frontend
- **Implementation Scope:** Extend Zustand cart store in `apps/web` to persist to `localStorage` using zustand's `persist` middleware or manual `storage` sync. Key: `bhojango-cart-guest`. Schema: `{ items: array, restaurantId: string|null, restaurantName: string|null, updatedAt: ISO }`. On app bootstrap, hydrate cart from localStorage. On login, optionally migrate localStorage cart to API (or keep local until checkout). On logout, clear localStorage cart.
- **Acceptance Criteria:**
  1. Add item as guest → refresh page → cart still contains item.
  2. Cart badge in navbar and bottom nav reflects persisted count on reload.
  3. Logout clears localStorage cart.
  4. localStorage schema is versioned (e.g., `v1`) for future migration.
- **Evidence Required:** DevTools Application tab showing localStorage key. Screen recording: add item → refresh → cart still populated → logout → cart cleared.
- **Priority:** P0
- **Effort:** M
- **Dependency:** PR.02 auth persistence (Zustand store exists)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.002 — Cart Page UI with Quantity Stepper and Veg/Non-Veg Indicators
- **Category:** Frontend
- **Implementation Scope:** Create `/cart` page. Item rows: thumbnail image (48x48), name, price per unit, quantity stepper (+ / - buttons), line total (`price × qty`), veg/non-veg dot icon (green for veg, red for non-veg). Remove item when quantity reaches 0 (with confirmation toast). Sticky footer: subtotal, delivery fee, platform fee, tax, grand total. "Proceed to Checkout" primary CTA (disabled if cart empty). Empty state illustration + "Browse Restaurants" CTA if cart empty. Responsive: single column on mobile, max-w-2xl centered on desktop.
- **Acceptance Criteria:**
  1. Cart page lists all items with correct quantities and prices.
  2. Tapping "+" increases quantity; total recalculates instantly.
  3. Tapping "-" at quantity 1 triggers item removal.
  4. Veg items show green dot; non-veg show red dot.
  5. Empty cart shows illustration + browse CTA, not blank screen.
- **Evidence Required:** Screenshot of populated cart. Video showing quantity change and total update. Screenshot of empty state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.001 (localStorage cart)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.003 — Cross-Restaurant Cart Guard
- **Category:** Frontend
- **Implementation Scope:** In the "Add to Cart" handler on menu item, compare `item.restaurantId` with `cart.restaurantId`. If different and cart is not empty, show a modal (or bottom sheet on mobile): "Your cart has items from [Restaurant A]. Start a new cart for [Restaurant B]?" Options: "Cancel" (keep existing cart) and "Start New Cart" (clear cart, add new item). Use a reusable `<ConfirmModal />` component.
- **Acceptance Criteria:**
  1. Adding item from different restaurant triggers guard modal.
  2. "Cancel" keeps previous cart intact.
  3. "Start New Cart" replaces cart with new item.
  4. Guard does not trigger if cart is empty or same restaurant.
- **Evidence Required:** Video showing guard modal, cancel action, and start-new-cart action.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.03.001
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.004 — Checkout Form with Address Fields
- **Category:** Frontend
- **Implementation Scope:** Create `/checkout` page (or route). Form fields: Full Name (text), Street Address (textarea), City (text), Pincode/Zip (text), Phone Number (text), Landmark (text, optional). Each field has label, placeholder, and inline validation on blur (required fields, phone numeric, pincode length). Form state managed with React state or React Hook Form. Show validation errors in red text below fields. "Place Order" button disabled until all required fields valid and payment method selected.
- **Acceptance Criteria:**
  1. All required fields show error if left empty on blur.
  2. Phone field validates numeric and min length.
  3. Place Order button disabled until all fields valid.
  4. Form data included in order creation payload.
- **Evidence Required:** Screenshot of checkout form with validation errors. Video showing valid form enabling Place Order button.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.002 (cart page exists)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.005 — Payment Method Radio Mock (Card / UPI / Wallet / COD)
- **Category:** Frontend
- **Implementation Scope:** Add radio group below address form. Four options: 💳 Card, 📱 UPI, 👛 Wallet, 💵 Cash on Delivery. Card and UPI show disabled mock sub-forms ("Card number", "UPI ID") with "Coming soon" label or placeholder text. Wallet shows current balance (mock "₹0" or fetched from `/api/v1/wallet/balance`). COD requires no extra input. Selecting any option updates state; only then is Place Order enabled. Use radio cards (not native radios) for visual polish: icon, label, selected border/highlight.
- **Acceptance Criteria:**
  1. All four payment methods selectable via radio cards.
  2. Card/UPI show mock disabled input fields.
  3. COD and Wallet selection enables Place Order immediately.
  4. Selected state visually distinct.
- **Evidence Required:** Screenshot of payment method selector. Video showing selection and Place Order enablement.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.03.004
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.006 — Order Creation Backend Endpoint with Validation
- **Category:** Backend
- **Implementation Scope:** In `order-svc`, ensure `POST /api/v1/orders` accepts: `restaurant_id`, `items[]` (each with `menu_item_id`, `quantity`), `delivery_address` (JSONB), `payment_method`. Server-side validation: (1) restaurant exists and is active, (2) each `menu_item_id` exists and belongs to `restaurant_id`, (3) `quantity > 0`, (4) `unit_price` matches current DB price (compute server-side, do not trust client price), (5) `delivery_address` has required fields. Calculate fees: `subtotal = sum(qty × unit_price)`, `delivery_fee = 30` (flat mock), `platform_fee = subtotal × 0.02`, `tax_amount = subtotal × 0.05`, `total_amount = subtotal + delivery_fee + platform_fee + tax_amount`. Write order to `orders` table with `status = 'pending'`. Write initial entry to `order_status_history` (`pending`, `changed_by = user_id` or `system`). Return 201 with order object including `id` and `total_amount`.
- **Acceptance Criteria:**
  1. Valid payload creates order with 201, correct totals, and `status = 'pending'`.
  2. Invalid `menu_item_id` returns 422 with specific field error.
  3. Price tampering (client sends wrong price) is ignored; server uses DB price.
  4. Inactive restaurant returns 422.
  5. Missing required address fields return 422.
- **Evidence Required:** `curl` outputs for valid creation, invalid menu_item, and price mismatch.
- **Priority:** P0
- **Effort:** M
- **Dependency:** PR.02 menu endpoint (to fetch live prices)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.007 — Simulated Payment Processing (No External Provider)
- **Category:** Backend
- **Implementation Scope:** Add `POST /api/v1/orders/{id}/pay` (or integrate into create order flow). Accepts `payment_method`. Logic: if `payment_method == 'cod'`, set `payment_status = 'pending'` (to be collected on delivery). If `payment_method` in `['card', 'upi', 'wallet']`, set `payment_status = 'paid'` immediately (mock success). If `wallet`, optionally decrement a mock wallet balance (if wallet service exists; if not, skip). Update order status to `confirmed` if payment is `paid`. Add `confirmed` entry to `order_status_history`. Return 200 with `{ order_id, status, payment_status }`.
- **Acceptance Criteria:**
  1. COD order has `payment_status = 'pending'` and `status = 'pending'`.
  2. Card/UPI/Wallet order has `payment_status = 'paid'` and `status = 'confirmed'`.
  3. Endpoint protected by auth middleware (JWT required).
  4. Invalid order ID returns 404.
- **Evidence Required:** `curl` outputs for COD and Wallet payment methods showing correct statuses.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.03.006 (order creation exists)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.008 — Order State Machine Server-Side Enforcement
- **Category:** Backend
- **Implementation Scope:** In `order-svc`, create a `validate_status_transition(current_status: str, new_status: str) -> bool` function. Valid transitions:
  - `pending → confirmed`
  - `pending → cancelled`
  - `confirmed → preparing`
  - `confirmed → cancelled`
  - `preparing → ready_for_pickup`
  - `ready_for_pickup → picked_up`
  - `picked_up → delivered`
  All other transitions are invalid. Apply this validation in `PATCH /api/v1/orders/{id}/status` and any internal status update paths. On invalid transition, raise HTTPException 400 with detail: `Invalid transition: {current} → {new}`. Log the attempt with warning level.
- **Acceptance Criteria:**
  1. `pending → confirmed` returns 200.
  2. `delivered → pending` returns 400 with clear message.
  3. `confirmed → cancelled` returns 200.
  4. `preparing → cancelled` returns 400.
  5. Every status change is logged in `order_status_history`.
- **Evidence Required:** `curl` outputs showing valid and invalid transitions.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.03.006
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.009 — Order Confirmation Page
- **Category:** Frontend
- **Implementation Scope:** Create `/orders/confirmation/[id]` page (or reuse `/checkout/confirmation`). Fetch order via `GET /api/v1/orders/{id}`. Display: large checkmark icon, "Order Placed!" heading, order number, restaurant name, item list with quantities, delivery address, payment method, estimated delivery time (static: "35-45 minutes"), and two CTAs: "Track Order" (links to `/orders/{id}`) and "Order More" (links to `/restaurants`). Use brand primary color for checkmark. Skeleton loader while fetching.
- **Acceptance Criteria:**
  1. Page shows all order details correctly.
  2. "Track Order" navigates to order detail.
  3. Skeleton shown while loading.
  4. Responsive layout on mobile and desktop.
- **Evidence Required:** Screenshot of confirmation page. Video showing navigation from checkout → confirmation → tracking.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.03.006, IP.PR.03.007
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.010 — Order List Page (Authenticated)
- **Category:** Frontend
- **Implementation Scope:** Create `/orders` page. Fetch from `GET /api/v1/orders?page=1&limit=20`. Display cards: restaurant image (Unsplash deterministic), restaurant name, order total, status badge (pill with color: pending = yellow, confirmed = blue, preparing = orange, delivered = green, cancelled = red), order date. Sort by `created_at DESC`. Empty state: "No orders yet" illustration + "Browse Restaurants" CTA. Tap/click card navigates to `/orders/[id]`. loading skeletons (reuse `<SkeletonCard />` from PR.02).
- **Acceptance Criteria:**
  1. Page lists all user orders with correct data.
  2. Status badges are color-coded.
  3. Empty state shown for new users.
  4. Unauthenticated user redirected to `/login`.
- **Evidence Required:** Screenshot of order list with multiple statuses. Screenshot of empty state.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.006
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.011 — Order Detail Page with Mock Timeline
- **Category:** Frontend
- **Implementation Scope:** Create `/orders/[id]` page. Fetch order detail. Sections: (1) Header — restaurant name, status badge, order date. (2) Items list — image, name, qty, price. (3) Fee breakdown — subtotal, delivery fee, platform fee, tax, total. (4) Address block — delivery address. (5) Payment block — method, status. (6) Timeline — vertical stepper with 5 steps: Confirmed, Preparing, Ready for Pickup, Picked Up, Delivered. Current step highlighted (filled circle + bold text). Past steps green with checkmark icon. Future steps gray. Steps are static; only `status` field determines which step is current. If `cancelled`, show cancellation banner instead of timeline.
- **Acceptance Criteria:**
  1. Timeline shows correct current step based on order status.
  2. All past steps are visually marked complete.
  3. Cancelled order shows cancellation banner, not timeline.
  4. Fee breakdown matches order creation calculation.
- **Evidence Required:** Screenshots of order detail for statuses: confirmed, preparing, delivered, cancelled.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.03.010
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.012 — Basic Cancellation API
- **Category:** Backend
- **Implementation Scope:** Add `PATCH /api/v1/orders/{id}/cancel` to `order-svc`. Accepts optional `{ "reason": "string" }`. Validates: (1) order belongs to current user, (2) current status is `pending` or `confirmed`. If valid, update `status = 'cancelled'`, set `cancellation_reason = reason` (or JSONB field), add `cancelled` entry to `order_status_history`. If `payment_status == 'paid'`, set `payment_status = 'refund_pending'` (mock; no real refund call). Return 200 with updated order. If invalid status, return 400. If not owner, return 403.
- **Acceptance Criteria:**
  1. Cancelling `pending` order succeeds with 200 and `status = 'cancelled'`.
  2. Cancelling `delivered` order returns 400.
  3. Cancelling another user's order returns 403.
  4. Cancellation reason stored and returned in order detail.
- **Evidence Required:** `curl` outputs for valid cancellation, invalid status cancellation, and unauthorized cancellation.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.03.008 (state machine)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.013 — Frontend Cancellation Flow
- **Category:** Frontend
- **Implementation Scope:** Add "Cancel Order" button to order detail page. Visible only if `status` is `pending` or `confirmed`. On tap, show confirmation modal: "Are you sure you want to cancel this order?" with "Keep Order" and "Cancel Order" buttons. On confirm, call `PATCH /api/v1/orders/{id}/cancel`. On success, show toast "Order cancelled" and update UI status to `cancelled` (badge turns red, timeline replaced with cancellation banner). On error, show toast with error message.
- **Acceptance Criteria:**
  1. Cancel button visible only for pending/confirmed orders.
  2. Confirmation modal prevents accidental cancellation.
  3. Success updates UI immediately without page reload.
  4. Error shows toast.
- **Evidence Required:** Video showing cancel flow: tap cancel → confirm modal → success → status updated.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.03.011, IP.PR.03.012
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.014 — Delivery Fee Calculation and Display
- **Category:** Backend + Frontend
- **Implementation Scope:** Backend: in order creation (IP.PR.03.006), compute `delivery_fee` as flat ₹30 (or ₹50 if `subtotal < 200`). Store in `orders.delivery_fee`. Frontend: display `delivery_fee` in cart footer and checkout summary. If cart subtotal < 200, show note: "Add ₹{200 - subtotal} more for free delivery" (optional upsell, mock logic).
- **Acceptance Criteria:**
  1. Orders under ₹200 have delivery fee ₹50; orders over ₹200 have ₹30.
  2. Fee displayed in cart and checkout.
  3. Backend calculation is source of truth; frontend does not override.
- **Evidence Required:** Screenshot of cart showing delivery fee. `curl` output showing order creation with correct fee.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.03.006
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.03.015 — Fee / Tax Breakdown Visible in Cart and Checkout
- **Category:** Frontend
- **Implementation Scope:** Ensure cart footer and checkout summary always show line-item breakdown: Items Total (subtotal), Delivery Fee, Platform Fee (2%), Tax (5% GST), Discount (₹0 for now, placeholder row), Grand Total. Use monospaced or tabular numbers for alignment. Grand Total in bold/large font. On checkout, show breakdown in a sticky sidebar (desktop) or collapsible accordion (mobile).
- **Acceptance Criteria:**
  1. Every money screen (cart, checkout, confirmation, detail) shows full breakdown.
  2. Numbers align correctly (right-aligned, 2 decimal places).
  3. Grand total is most prominent.
- **Evidence Required:** Screenshots of cart and checkout showing breakdown.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.03.002, IP.PR.03.004
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Guest cart persists in `localStorage` and survives page refresh.
- [ ] Cart page shows items with quantity steppers, veg/non-veg indicators, and remove functionality.
- [ ] Cross-restaurant cart guard modal triggers on adding item from different restaurant.
- [ ] Checkout form validates required address fields inline.
- [ ] Payment method radio selector shows Card, UPI, Wallet, COD with appropriate mock states.
- [ ] Order creation endpoint validates restaurant, menu items, quantities, and prices server-side.
- [ ] Simulated payment marks order as `paid` (non-COD) or `pending` (COD) without external gateway calls.
- [ ] Order state machine rejects invalid transitions with 400.
- [ ] Order confirmation page renders with order summary and CTAs.
- [ ] Authenticated order list page shows past orders with status badges.
- [ ] Order detail page shows item list, fee breakdown, address, and mock tracking timeline.
- [ ] Cancellation API allows cancelling `pending` or `confirmed` orders;拒绝 `delivered` cancellations.
- [ ] Frontend cancellation flow shows confirmation modal and updates UI on success.
- [ ] Delivery fee is calculated and displayed (flat or threshold-based).
- [ ] Fee/tax breakdown visible on cart, checkout, confirmation, and detail pages.
- [ ] Unauthenticated users are redirected to login for `/orders` and `/checkout` (or guest checkout supported if cart is guest).
- [ ] No blank white screens on `/cart`, `/checkout`, `/orders`, `/orders/[id]`.

## 17. Evidence Required

- Screen recording: guest adds items → refresh → cart persists → proceeds to checkout → enters address → selects COD → places order → sees confirmation.
- Screen recording: logged-in user adds items → changes quantity → cross-restaurant guard → replaces cart → checks out → sees order in `/orders` → taps order → sees timeline → cancels order.
- `curl` output: valid order creation (201) with correct `total_amount` and `order_items` JSONB.
- `curl` output: order creation with invalid `menu_item_id` → 422.
- `curl` output: order creation with price tampering → server uses DB price, not client price.
- `curl` output: simulated payment (Wallet) → `status = 'confirmed'`, `payment_status = 'paid'`.
- `curl` output: simulated payment (COD) → `status = 'pending'`, `payment_status = 'pending'`.
- `curl` output: valid state transition (`pending → confirmed`) → 200.
- `curl` output: invalid state transition (`delivered → pending`) → 400.
- `curl` output: cancellation of pending order → 200, `status = 'cancelled'`.
- `curl` output: cancellation of delivered order → 400.
- Screenshots: cart page (populated + empty), checkout form (valid + invalid), payment selector, confirmation page, order list, order detail (multiple statuses), cancelled order detail.
- DevTools screenshot: localStorage shows `bhojango-cart-guest` with correct schema.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- Google Fonts (Manrope + Inter — inherited from PR.02).

### Internal Dependencies
- **PR.02 must be complete:** working menu endpoint, auth persistence, restaurant list/detail pages, skeleton components, dark mode, mobile bottom nav.
- `packages/ui` shared component package must build (button, card, badge, input, modal from PR.02).
- Existing seeded data (restaurants, menu items) must be present.
- Existing `orders`, `order_status_history` tables must exist (migrated in PR.01).

## 19. Risks / Blockers

- **Guest checkout vs. forced login trade-off.** If guest orders are created without `user_id`, they cannot be listed in `/orders` later. Mitigation: for PR.03, require login for checkout; guest cart is browse-only. Document this limitation. Future: add guest checkout with email capture.
- **Order creation price validation requires live menu data.** If menu endpoint is flaky (despite PR.02 fallback), order creation may fail. Mitigation: order-svc queries DB directly for prices; does not depend on restaurant-svc API.
- **Simulated payment may confuse demo viewers.** Mitigation: clearly label payment section as "Demo Mode — No real charges" in UI.
- **Wallet integration may not exist.** If wallet service is not implemented, skip wallet deduction and treat "Wallet" as mock paid. Document as known gap.
- **State machine enforcement may break existing admin flows** if admin dashboard manually patches statuses. Mitigation: add an `is_system` or `skip_validation` flag for admin transitions, or accept that PR.03 scope is customer-only and admin state changes are out of scope.
- **localStorage cart schema needs versioning.** If schema changes in PR.04/05, old carts may crash. Mitigation: include `version: 1` in localStorage and write a migration helper.
- **Fee calculation (tax, platform fee) may not match production expectations.** This is acceptable for PR.03; fee rates are mock and will be refined in PR.05.

## 20. Exit Criteria

- All P0 work items (IP.PR.03.001 through IP.PR.03.011) implemented and verified.
- Guest cart persists and survives refresh.
- Logged-in user can complete full flow: cart → checkout → simulated payment → confirmation → order list → order detail → mock timeline → cancellation.
- Order creation validates items and prices server-side.
- State machine rejects invalid transitions.
- No blank white screens on any new page (`/cart`, `/checkout`, `/orders`, `/orders/[id]`).
- Evidence screenshots/recordings captured per Section 17.
- PR.03 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.02)

PR.03 directly depends on PR.02 achievements:
- **IP.PR.02.001** — Menu endpoint DB fallback: ensures menu items load reliably so users can add to cart.
- **IP.PR.02.002** — `GET /api/v1/me`: required for auth persistence so checkout knows the user.
- **IP.PR.02.003** — Frontend auth persistence: token storage and hydration so `/orders` and `/checkout` are accessible.
- **IP.PR.02.005** — Skeleton loaders: reused for cart, checkout, order list, and order detail loading states.
- **IP.PR.02.007** — Error boundary pattern: reused on checkout and order detail for API failure resilience.
- **IP.PR.02.011 / IP.PR.02.012** — Category-specific Unsplash images + trust badges: reused in cart item thumbnails and order list cards.
- **IP.PR.02.013** — Dark mode: all new pages (`/cart`, `/checkout`, `/orders/*`) must support dark mode.
- **IP.PR.02.014** — Mobile bottom nav: cart badge must reflect localStorage cart count.

## 22. Connected Next-Level Requirements (link to PR.04)

PR.04 (Internal Demo-Ready Core Loop, score 4/10) builds on PR.03 and requires:
- Working simulated payment from IP.PR.03.007 (to be replaced with real Stripe/Razorpay in PR.06+).
- Order state machine from IP.PR.03.008 (enforced, ready for real driver status updates).
- Order list + detail pages from IP.PR.03.010 / IP.PR.03.011 (foundation for real-time tracking integration).
- Fee breakdown display from IP.PR.03.015 (foundation for dynamic surge pricing later).
- Address form from IP.PR.03.004 (foundation for saved address book and autocomplete in PR.05).

PR.04 will be blocked if:
- Order creation endpoint returns 500 or creates malformed `order_items` JSONB.
- Cart does not persist or loses items on refresh.
- State machine allows invalid transitions (e.g., `delivered → cancelled`).
- Checkout form does not collect or validate address data.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (3/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.02 complete) described | Planner | ✅ |
| 4 | Target state (PR.03 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.03 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.03 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms no schema changes needed | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage limited to groundwork (veg indicator, fee transparency) | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.03.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 10 work items present | Planner | ✅ |
| 17 | Work items cover: guest/localStorage cart, quantity stepper, checkout form, simulated payment, order validation, state machine, confirmation page, order list, order detail with timeline, fee breakdown, cancellation API, delivery fee, veg indicator | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention guest checkout, price validation, simulated payment confusion, wallet gap, admin state machine conflict | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.02) requirements listed | Planner | ✅ |
| 24 | Connected next-level (PR.04) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories: guest/localStorage cart persistence (IP.PR.03.001), cart UI with stepper and veg indicators (IP.PR.03.002), cross-restaurant guard (IP.PR.03.003), checkout form (IP.PR.03.004), payment method mock (IP.PR.03.005), order creation with validation (IP.PR.03.006), simulated payment (IP.PR.03.007), state machine enforcement (IP.PR.03.008), confirmation page (IP.PR.03.009), order list (IP.PR.03.010), order detail with timeline (IP.PR.03.011), cancellation API (IP.PR.03.012), frontend cancellation flow (IP.PR.03.013), delivery fee (IP.PR.03.014), and fee breakdown (IP.PR.03.015).
- Scope is tightly bounded to score 3/10 (transactional but shaky; simulated payment, mock tracking). Out-of-scope explicitly excludes real payment gateways, real-time tracking, push notifications, admin flows, favorites/loyalty, and production infrastructure.
- Risks and blockers are grounded in known gaps from the audits (guest checkout limitation, wallet service absence, admin state machine conflict).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references.
- Feasibility tags use the required color system (🟢 LOCAL/DEMO-SAFE throughout; no 🔴 or ⚫ tags needed since all work is local-safe and mock-based).
- **One point deducted** because the exact field names for `orders.delivery_address` JSONB schema and the presence of a wallet endpoint are assumed from the project report rather than explicitly confirmed in schema files. Minor discovery may be needed during build.

The document is ready for execution.
