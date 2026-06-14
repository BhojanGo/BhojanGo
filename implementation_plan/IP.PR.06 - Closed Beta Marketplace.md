# IP.PR.06 — Closed Beta Marketplace

## 1. Target Score Level: 6/10

## 2. Score Meaning

Customer, restaurant owner, delivery partner, and admin flows exist at a basic level. Search, filters, address, availability, cancellation, and order status are functional. The marketplace has three sides operating.

## 3. Current → Target Transition

**From PR.05 (stable customer core loop, basic profile, seed data, favorites/reorder, coupons):**
- The customer ordering loop is fully stable: browse → menu → cart → checkout → confirmation → tracking, with favorites, reorder, coupons, open/closed logic, prep-time, serviceability radius, password reset, address CRUD, cancellation, guest tracking, and backend search all working.
- Design system (BhojanGo palette, Manrope + Inter, Lucide icons, 4px grid, skeletons, toasts, empty states, error boundaries, responsive layout, dark mode) is applied globally across all customer-facing pages.
- Seed data is rich: 8-10 realistic reviews per restaurant, 10-15 orders per demo user, 5-8 wallet transactions per user, realistic Unsplash food images, combo items for thali builder.
- Guest checkout and order tracking by order number + phone OTP work without login.
- Backend search endpoint with ILIKE on `name` and `cuisine_types` is integrated into the frontend search bar.

**However, PR.05 is still "customer-only":**
- No restaurant owner dashboard: owners cannot log in, manage their restaurant, view orders, or update menu availability.
- No delivery partner dashboard: drivers cannot log in, accept deliveries, track earnings, or update order status.
- No super admin approval flow: new restaurants sit in pending state with no UI for admins to approve or reject.
- Order notifications to restaurant owners are missing: a new order placement does not alert the owner in real time.
- Driver assignment is manual/admin-only: no automatic nearest-driver matching algorithm.
- Order status timeline on customer tracking page is static/mock: it does not update when owners or drivers change status.
- Role-based route guards are not enforced on frontend routes: any logged-in user can theoretically navigate to `/admin` or `/owner` pages (even if API rejects).
- Batch engine exists in codebase but lacks driver integration and route recalculation on order removal.
- Order pooling/batching is not visible to any user role.

**Target at score 6:**
- Restaurant owners have a functional dashboard (`/owner`): login, view today's orders and revenue, accept/reject orders, mark preparing/ready for pickup, toggle item availability, update prices, toggle open/closed, view availability schedule.
- Delivery partners have a functional dashboard (`/driver`): login, view available orders (assigned or unassigned), accept/reject delivery, mark picked up/delivered, view mock earnings summary.
- Super admins have a functional dashboard (`/admin`): login, view restaurant approval queue with approve/reject, user list, order monitoring with filters, basic stats (total restaurants, orders, users, revenue).
- Real-time order notifications reach owners: SSE endpoint or 5-second polling on owner dashboard; new order shows toast + badge increment.
- Driver assignment is automated: basic Haversine nearest-driver algorithm via POST endpoint; driver location mock endpoint for demo.
- Basic order pooling/batching: batch engine groups nearby orders into a single delivery batch for one driver; batch visible in admin/driver UI.
- Role-based route guards protect frontend routes: `/owner`, `/driver`, `/admin` check JWT role claim before rendering.
- Order status timeline is driven by real owner/driver status updates: customer tracking page shows live transitions as owners mark "preparing" and drivers mark "picked up."
- All new dashboards follow the BhojanGo design system, with loading skeletons, error boundaries, empty states, responsive layout, and dark mode.

## 4. Implementation Objective

Add the three remaining roles (owner, driver, admin) with basic operational dashboards. Restaurant owners can manage their restaurant and menu. Delivery partners can accept and complete deliveries. Admins can approve restaurants and monitor the marketplace. Order notifications reach owners in real-time (SSE or polling). Build basic driver assignment and order pooling so the three-sided marketplace is demonstrable in a closed beta.

## 5. Scope

### In Scope

1. **Restaurant Owner Dashboard** (`/owner`):
   - Login as owner (reuse existing auth with `restaurant_owner` role claim).
   - Dashboard landing: today's order count, today's revenue (sum of confirmed+ orders), pending orders count, quick-action cards.
   - Order list: all orders for restaurants owned by this user, with status badges, customer name/phone, total amount, timestamp. Filter by status (pending, confirmed, preparing, ready_for_pickup, picked_up, delivered, cancelled).
   - Order detail: items list with quantities and customizations, delivery address, customer phone, payment method, status timeline.
   - Order actions: "Accept Order" (pending → confirmed), "Reject Order" (pending → cancelled with reason), "Mark Preparing" (confirmed → preparing), "Mark Ready for Pickup" (preparing → ready_for_pickup). Each action is a PATCH to order-svc with role validation.
   - Basic menu management: list all menu items per restaurant with toggle for `is_available`. Inline price edit (no add/delete for MVP — those remain manual via admin or DB seed).
   - Open/closed toggle: switch `is_open` boolean on restaurant. When toggled off, restaurant immediately shows as closed to customers.
   - Availability schedule view: read-only display of `opens_at` / `closes_at` for each day (seeded data). No editing for MVP.

2. **Delivery Partner Dashboard** (`/driver`):
   - Login as driver (reuse existing auth with `delivery_partner` role claim).
   - Dashboard landing: current shift status (online/offline toggle), today's earnings (mock/static for MVP), active delivery count.
   - Available orders list: orders with status `ready_for_pickup` that are either unassigned or assigned to this driver. Shows pickup restaurant name, delivery address, distance (Haversine from driver to pickup), estimated earnings.
   - Order detail: pickup restaurant name + address, delivery customer address, items summary, customer phone, special instructions, map placeholder (static coordinates or simple text).
   - Delivery actions: "Accept Delivery" (ready_for_pickup → picked_up + assign driver_id), "Reject Delivery" (unassign, return to pool), "Mark Picked Up" (picked_up confirmed), "Mark Delivered" (picked_up → delivered). Each action PATCH to order-svc with role validation.
   - Earnings summary: static/mock table of past deliveries with date, order number, earnings, tip. No real payout calculation for MVP.

3. **Super Admin Dashboard** (`/admin`):
   - Login as admin/super_admin (reuse existing auth with role claim).
   - Restaurant approval queue: table of restaurants with `status = 'pending_approval'`. Columns: name, owner email, cuisine types, submitted at. Action buttons: "Approve" (status → active), "Reject" (status → rejected with reason textarea). Admin already has order management from PR.04.
   - User management: list all users with pagination, search by email/name. Columns: name, email, role, phone, created at. Action: "View Details" modal showing addresses, orders count, wallet balance.
   - Order monitoring: list all orders across all restaurants with filters (status, date range, restaurant, payment method). Columns: order number, restaurant, customer, total, status, timestamp.
   - Basic stats: cards showing total restaurants, total orders (today/this week/all time), total users, total revenue (sum of all completed orders). Fetched from `GET /api/v1/admin/summary`.

4. **Real-time Order Notifications to Owner**:
   - SSE endpoint: `GET /api/v1/orders/sse?restaurant_id={id}` streams `order.created` events as JSON. OR short-polling fallback: `GET /api/v1/orders/pending?restaurant_id={id}` polled every 5s.
   - Owner dashboard subscribes to SSE on mount. On new order event: toast "New order #BG-12345 — ₹450", increment pending orders badge counter.
   - Connection recovery: if SSE disconnects, fallback to polling with exponential backoff.

5. **Driver Assignment**:
   - POST endpoint `POST /api/v1/deliveries/assign` accepts `{order_id}` and assigns nearest available driver using Haversine distance between restaurant lat/lng and driver last-known lat/lng.
   - Driver location stored in Redis (key: `driver:location:{driver_id}`, value: JSON `{lat, lng, updated_at}`) with 5-minute TTL.
   - `PATCH /api/v1/deliveries/location` for driver app to update location (mock driver location increments lat/lng by small fixed amount every 30s for demo).
   - If no driver within `restaurant.delivery_radius_km`, return 409 with message "No driver available nearby."

6. **Order Pooling / Batching (Basic)**:
   - Batch engine service already exists (Node.js/TypeScript). Expose its batch formation results via `GET /api/v1/batch-engine/deliveries` endpoint.
   - Batch creation logic (existing): groups `ready_for_pickup` orders by pickup proximity (within 2 km), scores combinations on distance + time + detour, greedily selects best batch.
   - Admin dashboard shows active batches: batch ID, driver assigned, orders in batch, route sequence.
   - Driver dashboard shows "Batch Delivery" card if assigned to a batch, with route order (Pickup A → Pickup B → Drop A → Drop B).
   - No route optimization UI (just list sequence). No recalculation on order removal (known gap, deferred to PR.07).

7. **Role-Based Route Guards**:
   - Frontend: Next.js middleware or HOC checks JWT `role` claim. `/owner/*` requires `restaurant_owner`. `/driver/*` requires `delivery_partner`. `/admin/*` requires `admin` or `super_admin`.
   - Unauthorized role → redirect to `/unauthorized` page with "You do not have access to this page" message and link to appropriate dashboard based on role.
   - Backend: existing FastAPI `require_restaurant_owner` and `require_driver` dependencies are wired into all owner/driver endpoints. JWT middleware rejects with 403 if role mismatch.

8. **Order Status Timeline (Real Data)**:
   - Customer order tracking page (`/orders/[id]`) no longer uses static mock timeline.
   - Fetches real `order_status_history` entries from `GET /api/v1/orders/{id}/history`.
   - Timeline updates reactively: when owner marks "preparing," SSE or WebSocket pushes status update to customer tracking page. If no WebSocket, poll every 10s while on tracking page.
   - Shows timestamp per step. Current step highlighted. Completed steps green, upcoming gray, cancelled step red with reason.

### Out of Scope

- Real push notifications (FCM) to owner/driver apps (templates exist in notification-svc but dispatch not wired end-to-end; deferred to PR.07).
- Real-time map with moving driver pin (Mapbox/Leaflet integration deferred to PR.07).
- Advanced route optimization (batch engine has heuristic scoring; no Google Routes API).
- Payment gateway webhooks (Stripe/Razorpay already simulated in PR.05; real webhooks deferred to PR.08).
- Email/SMS dispatch to owners/drivers (SendGrid/Twilio templates exist but not wired; deferred to PR.07).
- CDN/S3 image hosting for owner-uploaded menu images (Unsplash URLs remain for demo).
- Image optimization pipeline (deferred to PR.08).
- Full observability stack (Prometheus/Grafana exist but dashboard polish deferred to PR.08).
- CI/CD improvements (deferred to PR.08).
- Group ordering (novelty — deferred to PR.07+).
- Loyalty/gamification activation (deferred to PR.07+).
- Smart lockers / IoT (deferred to PR.09+).
- Full menu CRUD for owners (add/delete categories/items deferred to PR.07; only toggle availability and price edit in PR.06).
- Onboarding flow after signup (deferred to PR.07).
- Social login frontend wiring (Google OAuth backend ready; frontend deferred to PR.07).
- Address autocomplete with Nominatim/Google Places (deferred to PR.07).

## 6. Out of Scope (Summary)

- Real FCM push/SMS/email dispatch to owner/driver (templates exist but not wired).
- Real-time map with moving driver pin (map integration deferred to PR.07+).
- Advanced route optimization with traffic data (Google Routes API deferred).
- Payment gateway webhooks, real refunds via Stripe/Razorpay.
- CDN/S3 for owner-uploaded images, image optimization pipeline.
- Full observability dashboard polish, CI/CD improvements.
- Group ordering, loyalty activation, meal rescue, smart lockers.
- Full menu CRUD (add/delete), onboarding flow, social login frontend.

## 7. Required Capabilities

- Restaurant owner can log in, view dashboard, accept/reject orders, mark preparing/ready, toggle item availability, edit prices, toggle open/closed.
- Delivery partner can log in, view available orders, accept/reject deliveries, mark picked up/delivered, view mock earnings.
- Super admin can log in, view pending restaurant approval queue, approve/reject restaurants, list all users, monitor all orders, view basic marketplace stats.
- New order triggers real-time notification to owner within 2 seconds (SSE or polling).
- Driver assignment uses Haversine nearest-driver algorithm and stores locations in Redis.
- Basic order pooling/batching groups nearby orders and displays batch to admin and driver.
- Frontend routes `/owner`, `/driver`, `/admin` are protected by role-based guards.
- Customer order tracking page shows live status updates driven by owner/driver actions, not static mock.
- All new role dashboards follow the BhojanGo design system with loading, error, empty, and success states.
- Responsive layout and dark mode work on all new dashboards.

## 8. Key User Journeys

### Journey 8.1 — Owner Accepts Order, Marks Preparing, Marks Ready
1. Owner navigates to `/owner` and logs in with `restaurant_owner` credentials.
2. Dashboard shows "Today's Orders: 5", "Revenue: ₹2,340", "Pending: 2".
3. A toast appears: "New order #BG-20240614-9102 — ₹620". Pending badge increments to 3.
4. Owner taps "View Orders" → order list with filter "Pending" showing 3 cards.
5. Owner taps order #BG-9102 → detail page with items (2× Paneer Tikka, 1× Butter Naan), address, phone.
6. Owner taps "Accept Order". Status updates to `confirmed`. Timeline shows "Confirmed at 12:05 PM".
7. Owner taps "Mark Preparing". Status updates to `preparing`. Timeline updates.
8. Owner taps "Mark Ready for Pickup". Status updates to `ready_for_pickup`. Customer tracking page now shows "Ready for Pickup" step active.
9. Driver gets notification/assignment for this order.

### Journey 8.2 — Driver Accepts Delivery, Picks Up, Delivers
1. Driver navigates to `/driver` and logs in with `delivery_partner` credentials.
2. Dashboard shows online toggle (ON), "Today's Earnings: ₹340 (mock)", "Active Deliveries: 1".
3. "Available Orders" list shows 2 orders: #BG-9102 (Spice Garden, 1.2 km away, ₹45 earnings) and #BG-9105 (Biryani House, 2.8 km away, ₹60 earnings).
4. Driver taps #BG-9102 → detail with pickup address, delivery address, customer phone.
5. Driver taps "Accept Delivery". Order status changes to `picked_up` (driver assigned). Order disappears from available list.
6. Driver navigates to "Active Deliveries" → taps #BG-9102 → "Mark Picked Up" (confirms pickup from restaurant).
7. Driver travels (mock location updates every 30s). Customer tracking page shows "Picked Up" active.
8. Driver taps "Mark Delivered". Status changes to `delivered`. Order moves to "Completed" tab. Driver earnings mock increments.

### Journey 8.3 — Admin Approves a New Restaurant
1. Admin navigates to `/admin` and logs in with `super_admin` credentials.
2. Dashboard shows stats cards: 48 restaurants, 1,240 orders, 320 users, ₹4.5L revenue.
3. Admin clicks "Pending Restaurants" in sidebar → approval queue with 3 restaurants.
4. Admin views "Tandoori Nights" — cuisine: North Indian, owner: rajesh@email.com, submitted 2 days ago.
5. Admin clicks "Approve". Toast: "Tandoori Nights approved and is now live." Restaurant status changes to `active`.
6. Admin clicks "Reject" on "Unverified Biryani". Modal shows reason textarea: "Incomplete FSSAI documentation." Admin submits. Toast: "Unverified Biryani rejected." Status changes to `rejected`.
7. Restaurant immediately becomes invisible to customers if rejected; visible if approved.

### Journey 8.4 — Customer Places Order, Owner Receives Notification, Driver Gets Assigned
1. Customer (web or mobile) browses restaurants, adds items, checks out with COD.
2. Order created with status `pending`. Order-svc publishes SNS event `order.created`.
3. Owner SSE connection receives event. Toast: "New order #BG-20240614-9102 — ₹620". Pending badge increments.
4. Owner accepts order (status → `confirmed`). Order-svc publishes `order.confirmed`.
5. Batch engine pulls `confirmed` orders every 30s, groups nearby orders, forms batch.
6. Delivery-svc calls `POST /api/v1/deliveries/assign` for the order. Haversine query finds nearest driver (Driver-12, 0.8 km away).
7. Driver-12's `/driver` dashboard shows new available order #BG-9102.
8. Driver accepts. Status → `picked_up`. Customer tracking page updates from "Confirmed" to "Picked Up" in real time.
9. Driver marks delivered. Status → `delivered`. Customer sees "Delivered!" with timestamp.

## 9. Technical Coverage

### Backend
- `user-svc`: `GET /api/v1/me` returns `role` claim (already exists from PR.05). Ensure `restaurant_owner` and `delivery_partner` roles exist in DB seed.
- `restaurant-svc`:
  - `GET /api/v1/owner/restaurants` — list restaurants owned by authenticated user.
  - `GET /api/v1/owner/restaurants/{id}/orders` — orders for a specific restaurant (with pagination, status filter).
  - `PATCH /api/v1/owner/orders/{id}/accept` — pending → confirmed, validates owner owns the restaurant.
  - `PATCH /api/v1/owner/orders/{id}/reject` — pending → cancelled, with reason.
  - `PATCH /api/v1/owner/orders/{id}/preparing` — confirmed → preparing.
  - `PATCH /api/v1/owner/orders/{id}/ready` — preparing → ready_for_pickup.
  - `GET /api/v1/owner/restaurants/{id}/menu` — menu items with `is_available` and price.
  - `PATCH /api/v1/owner/menu-items/{id}/availability` — toggle `is_available`.
  - `PATCH /api/v1/owner/menu-items/{id}/price` — update price with Decimal validation.
  - `PATCH /api/v1/owner/restaurants/{id}/toggle-open` — toggle `is_open`.
- `order-svc`:
  - `GET /api/v1/orders/sse?restaurant_id={id}` — SSE stream for new orders (or `GET /api/v1/orders/pending?restaurant_id={id}` polled every 5s).
  - `GET /api/v1/orders/{id}/history` — returns `order_status_history` entries sorted by `changed_at`.
  - Existing PATCH endpoints extended to support `restaurant_owner` and `delivery_partner` role validation.
- `delivery-svc`:
  - `POST /api/v1/deliveries/assign` — assign nearest driver using Haversine.
  - `PATCH /api/v1/deliveries/location` — update driver location in Redis.
  - `GET /api/v1/deliveries/available` — list orders with status `ready_for_pickup` and no driver assigned.
  - `PATCH /api/v1/deliveries/{id}/accept` — driver accepts delivery.
  - `PATCH /api/v1/deliveries/{id}/pickup` — confirm pickup.
  - `PATCH /api/v1/deliveries/{id}/deliver` — confirm delivery.
- `batch-engine` (existing Node.js service):
  - `GET /api/v1/batch-engine/deliveries` — list active batches with orders and assigned driver.
  - Ensure SQS consumer is wired to `order.confirmed` SNS events (local dev: use `docker-compose` with `localstack` or direct HTTP polling for demo).
- `admin` (apps/admin Next.js app or backend endpoints in user-svc/order-svc):
  - `GET /api/v1/admin/summary` — total restaurants, orders, users, revenue.
  - `GET /api/v1/admin/restaurants?status=pending_approval` — pending approval queue.
  - `PATCH /api/v1/admin/restaurants/{id}/approve` — status → active.
  - `PATCH /api/v1/admin/restaurants/{id}/reject` — status → rejected with reason.
  - `GET /api/v1/admin/users` — paginated user list.
  - `GET /api/v1/admin/orders` — all orders with filters.

### Frontend
- **Owner Dashboard (`apps/web` or `apps/admin` — recommendation: new route in `apps/web` or dedicated owner portal):**
  - New route group `/owner/*`: `page.tsx` dashboard, `orders/page.tsx` order list, `orders/[id]/page.tsx` order detail, `menu/page.tsx` menu management.
  - Auth HOC/middleware checks `role === 'restaurant_owner'`.
  - Dashboard cards: order count, revenue, pending count fetched from owner endpoints.
  - Order list table/card hybrid with status filter dropdown.
  - Order detail with action buttons (conditionally rendered based on current status).
  - Menu management table with toggle switches for availability and inline price inputs.
  - Open/closed toggle switch in header.
- **Driver Dashboard (`apps/web` or `apps/mobile` — recommendation: new route in `apps/web` for MVP, mirror in mobile later):**
  - New route group `/driver/*`: `page.tsx` dashboard, `available/page.tsx` available orders, `active/page.tsx` active deliveries, `history/page.tsx` completed deliveries, `earnings/page.tsx` earnings mock.
  - Auth HOC/middleware checks `role === 'delivery_partner'`.
  - Online/offline toggle (static/mock for MVP; no real shift tracking required).
  - Available orders list with distance badge (from driver location mock).
  - Active delivery detail with action buttons.
  - Earnings table with static mock data.
- **Admin Dashboard (`apps/admin` — existing Next.js app extended):**
  - New pages/routes: `/admin/restaurants/pending`, `/admin/users`, `/admin/orders`, `/admin/stats`.
  - Auth middleware checks `role === 'admin' || role === 'super_admin'`.
  - Pending restaurants table with approve/reject buttons.
  - User list table with pagination and search.
  - Order monitoring table with filters.
  - Stats cards fetching from admin summary endpoint.
- **Customer Order Tracking Updates (`apps/web/orders/[id]`):**
  - Replace static timeline with real data from `GET /api/v1/orders/{id}/history`.
  - Poll every 10s while on tracking page, or use existing WebSocket if already implemented.
  - Status badge updates dynamically without page refresh.

### Data
- Reuses existing tables: `users`, `restaurants`, `menu_categories`, `menu_items`, `orders`, `order_status_history`, `addresses`, `wallet`, `batches`, `batch_orders`.
- New/extended columns (verify existence, add via migration if missing):
  - `restaurants.owner_id` → `users.id` FK (verify exists; if not, add migration).
  - `orders.driver_id` → `users.id` FK (nullable, for assignment).
  - `orders.batch_id` → `batches.id` FK (nullable, for pooling).
  - `menu_items.is_available` BOOLEAN (default true).
  - `users.shift_status` ENUM ('offline', 'online', 'on_delivery') for drivers (optional for MVP; can mock).
- Seed data extensions:
  - At least 3 demo users with role `restaurant_owner`, each owning 1-2 restaurants.
  - At least 2 demo users with role `delivery_partner`.
  - At least 1 demo user with role `super_admin`.
  - Seed orders for owner restaurants in varied statuses to populate dashboards.
- No new external services.

## 10. UI / UX Coverage

- **Loading states:** Skeleton cards for owner dashboard stats, skeleton table rows for order lists, skeleton list for available deliveries, skeleton stats cards for admin summary.
- **Error states:** Error boundaries on all new route groups (`/owner`, `/driver`, `/admin`). API failure toasts with retry button. SSE disconnect shows "Reconnecting..." indicator with fallback to polling.
- **Empty states:** Empty order list for owner with "No orders yet" illustration. Empty available deliveries for driver with "No orders available" and "Check back soon" message. Empty pending restaurants for admin with "All restaurants approved" badge.
- **Success states:** Toast on order accept/reject, status update, menu toggle, price save, open/closed toggle, restaurant approval/rejection, driver accept/deliver.
- **Design system:** All new dashboards follow BhojanGo palette (Saffron `#E65100`, Trust Green `#2E7D32`, Gold `#FFB300`), Manrope + Inter typography, 4px grid, Lucide icons, badge/card anatomy from IP.PR.04.011.
- **Responsive:** Owner/driver dashboards support mobile (stacked cards, bottom nav if needed), tablet (2-col), laptop (sidebar + content). Admin dashboard uses existing responsive table patterns.
- **Dark mode:** All new dashboards render correctly in dark mode. Sidebar, cards, tables adapt. No black-on-black text.
- **Accessibility:** Tables use semantic `<table>` with `<th>` scope. Buttons have clear focus states. Form toggles have aria labels. Status badges use color + text (not color alone).

## 11. Data / Model Coverage

- `users` table (existing): verify `role` enum includes `'restaurant_owner'`, `'delivery_partner'`, `'admin'`, `'super_admin'`. Seed 3 owners, 2 drivers, 1 admin.
- `restaurants` table (existing): verify `owner_id` UUID FK → `users.id`. `is_open` BOOLEAN (default true). `status` ENUM ('pending_approval', 'active', 'rejected', 'suspended').
- `orders` table (existing): `driver_id` UUID FK → `users.id` (nullable). `batch_id` UUID FK → `batches.id` (nullable). `status` ENUM with valid transitions enforced (see IP.PR.05.I005).
- `menu_items` table (existing): `is_available` BOOLEAN (default true). `price` NUMERIC(12,2).
- `order_status_history` table (existing): records every owner/driver status change with `changed_at` and `changed_by` (user_id).
- `batches` table (existing): `id`, `driver_id`, `status`, `created_at`, `updated_at`.
- `batch_orders` table (existing): `batch_id`, `order_id`, `sequence_index`.
- Redis (existing): `driver:location:{driver_id}` JSON string with TTL 300s.
- No new PostgreSQL tables required for PR.06 (batch tables already exist).

## 12. Role / Permission Coverage

- `customer`: Unchanged from PR.05. Full access to browsing, cart, checkout, profile, orders, favorites, wallet.
- `restaurant_owner`: Access to `/owner/*` routes. Can view and manage only restaurants where `owner_id = self.id`. Can accept/reject/prepare/ready orders for owned restaurants only. Can toggle menu availability and edit prices for owned restaurant items. Cannot access `/driver` or `/admin`.
- `delivery_partner`: Access to `/driver/*` routes. Can view available orders with status `ready_for_pickup`. Can accept/mark picked up/mark delivered for assigned orders. Can update own location. Cannot access `/owner` or `/admin`.
- `admin` / `super_admin`: Access to `/admin/*` routes. Can approve/reject restaurants. Can view all users, all orders. Can view stats summary. Cannot access `/owner` or `/driver`.
- Guest (unauthenticated): No access to `/owner`, `/driver`, `/admin`. Redirected to login.
- **Cross-role enforcement:** API endpoints explicitly check role claims. Frontend middleware blocks route access by role. If a user with `customer` role manually navigates to `/owner`, they see unauthorized page.

## 13. Performance / Reliability / Security Coverage

### Performance
- Owner order list uses indexed query: `WHERE restaurant_id IN (SELECT id FROM restaurants WHERE owner_id = ?)` with index on `orders.restaurant_id` and `restaurants.owner_id`.
- Admin user list and order monitoring use pagination (cursor or offset) with limit of 50 per page.
- SSE endpoint keeps connection open with `text/event-stream`. Use async generator in FastAPI. Limit 1 SSE connection per restaurant_id to prevent resource exhaustion.
- Haversine driver assignment query should filter by `users.role = 'delivery_partner'` and `users.shift_status = 'online'` before distance calculation. Index on `users.role`.
- Redis driver location lookups are O(1) with TTL auto-expiry.

### Reliability
- SSE disconnects gracefully: client receives `error` event, falls back to polling. Server should handle client disconnect without crashing (try/except around yield).
- Owner dashboard actions (accept, reject, preparing, ready) are idempotent: PATCH with expected current status; if status already changed, return 409 with current state.
- Driver assignment is atomic: use DB transaction to set `orders.driver_id` and update `orders.status` together. If transaction fails, order remains unassigned and eligible for next assignment attempt.
- If batch engine fails, orders remain in `ready_for_pickup` state and can be assigned individually via driver assignment endpoint. Batching is optimization, not required for delivery.
- Menu price updates validate `price > 0` and `price < 100000` to prevent accidental corruption.

### Security
- Owner endpoints verify `restaurant.owner_id == current_user.id` before allowing any mutation. Never trust client-sent `restaurant_id` without ownership check.
- Driver endpoints verify `order.driver_id == current_user.id` or `order.driver_id IS NULL` before assignment.
- Admin endpoints verify `current_user.role IN ('admin', 'super_admin')`.
- SSE endpoint verifies that the requesting user's `restaurant_id` ownership matches. Do not allow subscribing to arbitrary restaurant IDs.
- Driver location Redis keys use predictable pattern but contain no PII (only lat/lng). In production, consider encrypting or scoping access.
- All PATCH endpoints for order status changes use SQLAlchemy parameterized queries. No raw SQL or string interpolation.
- Rate limit owner order actions (e.g., max 10 status changes per minute per order) to prevent accidental spam.

## 14. Novelty / Differentiation Coverage

At score 6, novelty comes from the three-sided marketplace actually operating:
- **Owner dashboard with real-time notifications** — Not just a mock: owners receive live order alerts, accept/reject, and manage menu. This is a real operational tool.
- **Driver dashboard with nearest assignment** — Basic but functional Haversine-based dispatch. Drivers see distance and earnings before accepting.
- **Admin approval queue** — Super admin has real operational power to gate restaurant quality before they go live.
- **Order pooling/batching visibility** — Batches are visible to admin and driver. This hints at the cost-saving differentiation BhojanGo aims for (batched delivery). Even basic grouping is novel compared to single-order dispatch demos.
- **Live status timeline** — Customer sees real updates as owner and driver act. Creates trust and transparency.

Differentiators deferred: group ordering (PR.07), loyalty activation (PR.07), meal rescue (PR.07), nutrition info (PR.07), AI suggestions (PR.08+), voice ordering (PR.08+), real-time map tracking (PR.07+).

## 15. Implementation Work Items

### IP.PR.06.001 — Owner Dashboard + Auth Guard
- **Category:** Frontend + Backend
- **Implementation Scope:** Create `/owner` route group in `apps/web` (or new owner app if preferred, but reuse `apps/web` for speed). Dashboard page with stat cards (today's orders, revenue, pending count) fetched from `GET /api/v1/owner/restaurants` and `GET /api/v1/owner/restaurants/{id}/orders`. Auth guard middleware checks JWT `role === 'restaurant_owner'`; unauthorized users redirected to `/unauthorized`. Backend: ensure `GET /api/v1/me` returns role and `GET /api/v1/owner/restaurants` filters by `owner_id`.
- **Acceptance Criteria:**
  1. `/owner` accessible only to users with `restaurant_owner` role.
  2. Dashboard shows accurate stat cards for the logged-in owner's restaurants.
  3. Unauthorized users see "Access Denied" page, not blank screen.
  4. Dark mode and responsive layout work on owner dashboard.
- **Evidence Required:** Screen recording: owner login → dashboard with stats → toggle dark mode → resize to mobile.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.05 (auth persistence, `GET /api/v1/me`, design system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.002 — Owner Order Accept/Reject + Status Update
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `PATCH /api/v1/owner/orders/{id}/accept` (pending→confirmed), `/reject` (pending→cancelled+reason), `/preparing` (confirmed→preparing), `/ready` (preparing→ready_for_pickup). Each endpoint validates owner owns the order's restaurant. Inserts `order_status_history` entry. Frontend: order detail page shows action buttons based on current status. Accept/Reject shown for pending. Mark Preparing for confirmed. Mark Ready for Preparing. Reject opens modal with reason textarea.
- **Acceptance Criteria:**
  1. Owner can accept pending order → status becomes confirmed.
  2. Owner can reject pending order with reason → status becomes cancelled.
  3. Owner can mark confirmed → preparing → ready_for_pickup sequentially.
  4. Invalid transitions (e.g., preparing → confirmed) return 400 with error message.
  5. Each status change inserts history record with timestamp.
- **Evidence Required:** Screen recording: owner views pending order → accept → mark preparing → mark ready. Customer tracking page shows status updates.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.001, IP.PR.05.I005 (state machine enforcement)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.003 — Owner Menu Management (Toggle Availability)
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/owner/restaurants/{id}/menu` returns all menu items with `is_available` and `price`. `PATCH /api/v1/owner/menu-items/{id}/availability` toggles boolean. `PATCH /api/v1/owner/menu-items/{id}/price` updates price with validation (₹1–₹99,999). Frontend: `/owner/menu` page with table listing items per category. Each row has toggle switch for availability and inline editable price field with save button. Changes reflect immediately on customer menu (items disabled when `is_available = false`).
- **Acceptance Criteria:**
  1. Owner can toggle menu item availability on/off.
  2. Toggled-off item appears as "Unavailable" on customer restaurant detail page and cannot be added to cart.
  3. Owner can edit item price; change persists in DB.
  4. Invalid price (negative, > ₹99,999) shows validation error.
- **Evidence Required:** Screenshots: owner menu management table, customer menu showing unavailable item, price edit success toast.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.06.001, IP.PR.04.005 (menu detail page)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.004 — Owner Open/Closed Toggle
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `PATCH /api/v1/owner/restaurants/{id}/toggle-open` flips `is_open` boolean. Returns new state. Frontend: prominent toggle switch on owner dashboard header or settings card. When toggled off: toast "Your restaurant is now closed. Customers cannot place orders." Customer-side: restaurant list shows "Closed" badge, detail page disables add-to-cart (already implemented in IP.PR.05.009; ensure it respects `is_open` from API).
- **Acceptance Criteria:**
  1. Owner can toggle restaurant open/closed from dashboard.
  2. Closed restaurant immediately shows as closed to customers (badge + disabled ordering).
  3. Toast confirms toggle action.
  4. Only owner of the restaurant can toggle; other owners see error.
- **Evidence Required:** Screen recording: owner toggles closed → customer list shows closed badge → owner toggles open → badge updates.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.06.001, IP.PR.05.009 (open/closed logic)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.005 — Driver Dashboard + Auth Guard
- **Category:** Frontend + Backend
- **Implementation Scope:** Create `/driver` route group in `apps/web`. Dashboard with online toggle (static/mock for MVP), today's earnings mock, active delivery count. Auth guard checks `role === 'delivery_partner'`. Backend: ensure `users` table has seeded driver accounts with `delivery_partner` role.
- **Acceptance Criteria:**
  1. `/driver` accessible only to `delivery_partner` role.
  2. Dashboard shows mock earnings and active delivery count.
  3. Unauthorized users see "Access Denied" page.
  4. Responsive and dark mode work.
- **Evidence Required:** Screen recording: driver login → dashboard → toggle online/offline → resize mobile.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.05 (auth persistence, design system)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.006 — Driver Accept/Reject + Pickup/Deliver
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/deliveries/available` lists orders with status `ready_for_pickup` and `driver_id IS NULL`. `PATCH /api/v1/deliveries/{id}/accept` sets `driver_id` and status `picked_up`. `PATCH /api/v1/deliveries/{id}/pickup` confirms pickup. `PATCH /api/v1/deliveries/{id}/deliver` sets status `delivered`. Frontend: available orders list with distance badge. Order detail with Accept/Reject buttons. Active deliveries tab with Mark Picked Up / Mark Delivered buttons.
- **Acceptance Criteria:**
  1. Driver sees orders with status `ready_for_pickup` in available list.
  2. Driver accepts → order moves to active deliveries, status `picked_up`.
  3. Driver marks delivered → status `delivered`, order moves to history.
  4. Customer tracking page updates in real time (or within 10s poll) to reflect driver actions.
  5. Only assigned driver can mark pickup/deliver; others get 403.
- **Evidence Required:** Screen recording: driver views available order → accept → mark picked up → mark delivered. Customer tracking shows live updates.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.005, IP.PR.06.002 (status update backend pattern)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.007 — Driver Earnings Mock
- **Category:** Frontend
- **Implementation Scope:** Static earnings table on `/driver/earnings`. Columns: date, order number, restaurant, earnings (mock ₹40–₹80 per delivery), tip (mock ₹0–₹20), total. Summary card: "This Week: ₹340", "This Month: ₹1,240". Data is hardcoded or lightly randomized for demo. No real payout calculation.
- **Acceptance Criteria:**
  1. Earnings page shows table with 10+ mock entries.
  2. Summary cards calculate mock totals correctly.
  3. Empty state if no entries (for fresh drivers).
  4. Responsive table with horizontal scroll on mobile.
- **Evidence Required:** Screenshot: driver earnings page with table and summary cards.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06.005
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.008 — Admin Dashboard + Auth Guard
- **Category:** Frontend + Backend
- **Implementation Scope:** Extend existing `apps/admin` dashboard. Add role guard: `role === 'admin' || role === 'super_admin'`. New sidebar items: "Pending Restaurants", "Users", "All Orders", "Stats". Backend: ensure admin login API returns role and middleware validates it.
- **Acceptance Criteria:**
  1. `/admin` accessible only to admin/super_admin roles.
  2. Sidebar shows new navigation items.
  3. Unauthorized users see "Access Denied" page.
  4. Dark mode and responsive layout work (admin already uses dark-first design).
- **Evidence Required:** Screen recording: admin login → dashboard with sidebar → navigate to pending restaurants.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.04 (existing admin app, auth)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.009 — Admin Restaurant Approval Queue
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/admin/restaurants?status=pending_approval` returns pending restaurants. `PATCH /api/v1/admin/restaurants/{id}/approve` → status active. `PATCH /api/v1/admin/restaurants/{id}/reject` → status rejected with `rejection_reason`. Frontend: table in `apps/admin` showing pending restaurants with name, owner email, cuisine, submitted date. Action buttons: Approve (green) and Reject (red, opens modal with reason textarea). Toast on success.
- **Acceptance Criteria:**
  1. Admin sees all pending restaurants in approval queue.
  2. Approve → restaurant becomes active and visible to customers.
  3. Reject → restaurant status changes to rejected, reason stored.
  4. Rejected restaurants do not appear in customer list.
  5. Only admin/super_admin can approve/reject.
- **Evidence Required:** Screen recording: admin views pending queue → approves one → rejects another with reason → customer list updates.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.008
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.010 — Admin User List
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/admin/users?page=&limit=&search=` returns paginated users with filters. Frontend: table in `apps/admin` with columns: name, email, role, phone, created at. Search input filters by name/email. "View Details" button opens modal showing addresses, order count, wallet balance.
- **Acceptance Criteria:**
  1. Admin sees paginated list of all users.
  2. Search filters users by name or email in real-time (debounced).
  3. "View Details" modal shows user-specific data.
  4. Role badges use distinct colors (owner = orange, driver = blue, admin = purple, customer = green).
- **Evidence Required:** Screenshot: user list with search, detail modal open.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06.008
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.011 — Admin Order Monitoring
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/admin/orders?page=&limit=&status=&restaurant_id=&date_from=&date_to=` returns all orders with filters. Frontend: table in `apps/admin` with columns: order number, restaurant, customer, total, status badge, timestamp. Filter dropdowns for status and date range. Sort by timestamp desc.
- **Acceptance Criteria:**
  1. Admin sees all orders across all restaurants.
  2. Filters by status and date range work correctly.
  3. Status badges are color-coded and consistent with owner/driver dashboards.
  4. Pagination works (50 per page).
- **Evidence Required:** Screenshot: order monitoring table with filters applied.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06.008
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.012 — Admin Stats Summary Endpoint
- **Category:** Backend
- **Implementation Scope:** `GET /api/v1/admin/summary` returns JSON: `{ total_restaurants, total_orders_today, total_orders_week, total_orders_all, total_users, total_revenue }`. Revenue = sum of `grand_total` for orders with status `delivered` or `completed`. Use lightweight count/sum queries with DB indexes. Cache result in Redis for 60 seconds to reduce load.
- **Acceptance Criteria:**
  1. Endpoint returns accurate counts and revenue.
  2. Response time <200ms with Redis cache.
  3. Only admin/super_admin can access.
  4. Stats update within 60 seconds of data change (cache TTL).
- **Evidence Required:** `curl` output of summary endpoint. Screenshot of admin dashboard stats cards.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06.008
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.013 — Real-time Notifications to Owner (SSE or Polling)
- **Category:** Backend + Frontend
- **Implementation Scope:** Backend: `GET /api/v1/orders/sse?restaurant_id={id}` FastAPI async generator yields `data: {"event":"order.created","order":{...}}` every time a new order is created for that restaurant. Use in-memory queue or Redis pub/sub to publish events from order-svc creation endpoint to SSE subscribers. Fallback: `GET /api/v1/orders/pending?restaurant_id={id}` polled every 5s. Frontend: owner dashboard mounts EventSource on load. On message: toast + badge increment. Handle `error` and `close` events with automatic reconnection (3 retries, then fallback to polling).
- **Acceptance Criteria:**
  1. New order triggers SSE event to owner within 2 seconds.
  2. Owner dashboard shows toast with order number and amount.
  3. Pending orders badge increments automatically.
  4. If SSE disconnects, client falls back to polling without page refresh.
  5. Owner only receives events for owned restaurants.
- **Evidence Required:** Screen recording: customer places order → owner dashboard receives toast in real time → badge increments.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.001, IP.PR.06.002
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.014 — Driver Assignment Endpoint (Haversine)
- **Category:** Backend
- **Implementation Scope:** `POST /api/v1/deliveries/assign` accepts `{order_id}`. Queries `users` table for drivers with `role = 'delivery_partner'` and `shift_status = 'online'` (or mock: all drivers). For each driver, fetches last location from Redis (`driver:location:{driver_id}`). Calculates Haversine distance between restaurant lat/lng (from `orders.restaurant_id` → `restaurants`) and driver lat/lng. Picks nearest driver within `restaurant.delivery_radius_km`. Atomically sets `orders.driver_id` and `orders.status = 'picked_up'` in DB transaction. Returns `{driver_id, distance_km, eta_minutes}`. If no driver available, returns 409.
- **Acceptance Criteria:**
  1. Assignment endpoint finds nearest online driver using Haversine.
  2. Assignment is atomic (driver_id + status updated together).
  3. Assigned driver sees order in their active deliveries within 5 seconds.
  4. If no driver in radius, returns 409 with clear message.
  5. Only callable by order-svc or admin (internal auth or role check).
- **Evidence Required:** `curl` output showing assignment with driver_id and distance. DB query confirming `orders.driver_id` set.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.006, existing delivery-svc Haversine utility
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.015 — Driver Location Mock Endpoint
- **Category:** Backend + Frontend
- **Implementation Scope:** `PATCH /api/v1/deliveries/location` accepts `{lat, lng}`. Stores in Redis with key `driver:location:{driver_id}` and TTL 300s. For demo: create a mock location updater script or frontend interval that sends small increment requests every 30s (e.g., lat += 0.0001, lng += 0.0001) simulating movement. Frontend driver dashboard shows "Last updated: 10s ago" indicator.
- **Acceptance Criteria:**
  1. Driver can update location via PATCH endpoint.
  2. Location stored in Redis with 5-minute TTL.
  3. Assignment endpoint uses this Redis location for Haversine calculation.
  4. Mock updater demonstrates location changing over time.
  5. Expired location (no update in 5 min) is ignored by assignment.
- **Evidence Required:** `curl` to update location, Redis CLI `GET driver:location:{id}` showing JSON. Screenshot of driver dashboard with location indicator.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.PR.06.014
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.016 — Basic Batch Engine Order Pooling
- **Category:** Backend + Frontend
- **Implementation Scope:** Ensure batch-engine Node.js service is running and connected to `order.confirmed` events (via SQS or direct HTTP for demo). Expose `GET /api/v1/batch-engine/batches` returning active batches with orders and assigned driver. Frontend: admin dashboard shows "Active Batches" table. Driver dashboard shows "Batch Delivery" card if assigned to a batch, displaying route sequence (Pickup A → Pickup B → Drop A → Drop B). No route optimization UI — just list order.
- **Acceptance Criteria:**
  1. Batch engine groups 2+ nearby `ready_for_pickup` orders into a batch.
  2. Admin dashboard lists active batches with order IDs and driver name.
  3. Driver assigned to batch sees route sequence in active deliveries.
  4. Batch creation happens automatically within 60 seconds of orders reaching `ready_for_pickup`.
- **Evidence Required:** Screenshot: admin active batches table. Driver dashboard showing batch with sequence. `curl` of batch endpoint.
- **Priority:** P1
- **Effort:** M
- **Dependency:** Existing batch-engine service, IP.PR.06.008, IP.PR.06.005
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.017 — Role-Based Route Guards (Frontend)
- **Category:** Frontend
- **Implementation Scope:** In `apps/web` Next.js middleware (`middleware.ts`): parse JWT from cookie/localStorage, decode payload, check `role` claim. Route mappings: `/owner/*` → requires `restaurant_owner`. `/driver/*` → requires `delivery_partner`. `/admin/*` → requires `admin` or `super_admin`. If role mismatch: redirect to `/unauthorized` page with message "You do not have access to this page." Include link to user's correct dashboard based on role. Also protect via client-side HOC on each page as defense-in-depth.
- **Acceptance Criteria:**
  1. Customer-role user navigating to `/owner` is redirected to `/unauthorized`.
  2. Owner-role user navigating to `/driver` is redirected to `/unauthorized`.
  3. Admin can access `/admin` but not `/owner` or `/driver`.
  4. `/unauthorized` page has clear message and link to appropriate home route.
  5. Manual URL entry is blocked (not just link hiding).
- **Evidence Required:** Screen recording: customer tries `/owner` → redirected to unauthorized. Owner tries `/admin` → redirected.
- **Priority:** P0
- **Effort:** S
- **Dependency:** IP.PR.05 (JWT auth, role claims in token)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.06.018 — Order Status Timeline (Real Updates)
- **Category:** Frontend + Backend
- **Implementation Scope:** Backend: `GET /api/v1/orders/{id}/history` returns array of `{status, changed_at, changed_by, note}` from `order_status_history` table. Frontend: customer `/orders/[id]` tracking page fetches history on mount and polls every 10s for updates. Replaces static mock timeline with dynamic vertical stepper. Steps: Confirmed, Preparing, Ready for Pickup, Picked Up, Delivered. Current step highlighted. Completed steps green. Cancelled step red with reason. Timestamps shown per step.
- **Acceptance Criteria:**
  1. Tracking page shows real status history with timestamps.
  2. When owner marks "preparing," customer tracking updates within 10 seconds (poll) or immediately (SSE/WebSocket).
  3. When driver marks "delivered," tracking shows "Delivered" step with timestamp.
  4. Cancelled order shows red "Cancelled" step with reason.
  5. No page refresh required for updates.
- **Evidence Required:** Screen recording: owner marks preparing → customer tracking updates. Driver marks delivered → tracking updates.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.06.002, IP.PR.06.006, IP.PR.05.009 (order tracking page)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] Owner dashboard (`/owner`) works: login as owner, view stat cards, order list, order detail, accept/reject/prepare/ready actions.
- [ ] Owner menu management works: toggle item availability, edit price, changes reflect on customer menu.
- [ ] Owner open/closed toggle works: immediate effect on customer-facing restaurant list and detail page.
- [ ] Driver dashboard (`/driver`) works: login as driver, view available orders, accept delivery, mark picked up, mark delivered.
- [ ] Driver earnings mock page shows static earnings table with summary cards.
- [ ] Admin dashboard (`/admin`) works: login as admin, view pending restaurant approval queue, approve/reject with reason.
- [ ] Admin user list works: paginated, searchable, detail modal.
- [ ] Admin order monitoring works: all orders, filterable by status and date.
- [ ] Admin stats summary endpoint returns accurate counts and revenue with Redis caching.
- [ ] Real-time owner notifications work: SSE or 5s polling triggers toast + badge increment within 2 seconds of new order.
- [ ] Driver assignment works: Haversine-based nearest driver assignment, atomic DB update, 409 if no driver available.
- [ ] Driver location mock works: Redis storage with TTL, mock updater demonstrates movement, assignment uses latest location.
- [ ] Basic batch pooling works: batch engine groups nearby orders, admin sees active batches, driver sees batch route sequence.
- [ ] Role-based route guards work: `/owner`, `/driver`, `/admin` protected by JWT role claim; unauthorized access redirected to `/unauthorized`.
- [ ] Customer order tracking shows real updates: live status timeline driven by owner/driver actions, polls every 10s or uses SSE/WebSocket.
- [ ] All new dashboards have loading skeletons, error boundaries, empty states, success toasts, responsive layout, and dark mode.
- [ ] Core customer loop from PR.05 remains stable and unaffected by new role features.

## 17. Evidence Required

- Screen recording: customer places order → owner receives real-time notification toast → owner accepts → marks preparing → marks ready → driver gets assigned → driver accepts → marks picked up → marks delivered → customer tracking shows live updates.
- Screen recording: admin logs in → views pending restaurants → approves one → rejects another with reason → approved restaurant appears in customer list, rejected does not.
- Screen recording: owner toggles menu item off → customer sees "Unavailable" → owner edits price → customer sees new price.
- Screen recording: role guard test — customer tries `/owner` → unauthorized. Owner tries `/driver` → unauthorized. Driver tries `/admin` → unauthorized.
- Screenshots: owner dashboard (stats, orders, menu), driver dashboard (available, active, earnings), admin dashboard (pending queue, users, orders, stats).
- Screenshots: customer tracking page showing real timeline with timestamps after each status change.
- `curl` outputs: `POST /api/v1/deliveries/assign`, `GET /api/v1/admin/summary`, `GET /api/v1/orders/{id}/history`, `PATCH /api/v1/deliveries/location`.
- DB query outputs: `SELECT status, COUNT(*) FROM orders WHERE restaurant_id = ?`, `SELECT * FROM order_status_history WHERE order_id = ?`.
- Redis CLI output: `GET driver:location:{driver_id}`, `KEYS driver:location:*`.
- Batch engine `curl`: `GET /api/v1/batch-engine/batches` showing active batch with orders.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, optional LocalStack for SQS/SNS).
- Node.js + pnpm (frontend build, batch-engine).
- Python + Poetry/pip (backend services).
- Existing infrastructure: Kong API Gateway, OpenSearch (optional).

### Internal Dependencies
- **PR.05 must be complete:** stable customer core loop, auth persistence, `GET /api/v1/me`, design system, responsive layout, dark mode, loading/error/empty states, order state machine enforcement (valid transitions).
- `restaurants.owner_id` must exist and be populated (seed data update needed).
- `orders.driver_id` and `orders.batch_id` columns must exist (verify or migrate).
- `menu_items.is_available` must exist (verify or migrate).
- `users` table must have seeded accounts for `restaurant_owner`, `delivery_partner`, and `super_admin` roles.
- Batch engine service must compile and run (`npm run dev` or `docker-compose` inclusion).
- Existing `delivery-svc` Haversine utility is reused for driver assignment.
- `apps/admin` Next.js app must build successfully (existing dependency).

## 19. Risks / Blockers

- **SSE scalability:** FastAPI SSE with many concurrent connections can exhaust server workers. Mitigation: for PR.06 demo, limit to 10-20 owner connections; document move to Redis pub/sub or dedicated WebSocket service for PR.07+.
- **Batch engine not wired in docker-compose:** If batch-engine is missing from `docker-compose.yml`, it won't receive events. Mitigation: verify `docker-compose.yml` includes batch-engine service and local SQS/SNS (or use direct HTTP polling fallback for demo).
- **Role claim missing from JWT:** If `GET /api/v1/me` or JWT payload does not include `role`, route guards cannot function. Mitigation: ensure JWT signing includes `role`; add migration to user-svc if needed.
- **Driver assignment without real GPS:** Haversine assignment using mock locations may assign "nearest" driver unrealistically. Mitigation: seed driver locations near restaurant clusters (e.g., same city lat/lng offsets).
- **Cross-service auth for batch-engine to delivery-svc:** Batch engine may need to call delivery-svc for driver assignment. If inter-service auth (internal JWT) is not configured, calls fail. Mitigation: use Kong gateway routing with same JWT, or add simple shared-secret header for demo.
- **Admin dashboard may conflict with existing `/admin` pages:** `apps/admin` already has orders, restaurants, drivers, users tables from PR.04. Adding new pages may cause route conflicts. Mitigation: verify existing routes in `apps/admin` and append new pages under distinct paths (e.g., `/admin/restaurants/pending`).
- **Performance of admin stats summary on large datasets:** Uncached `COUNT(*)` and `SUM()` on orders table can be slow if many rows. Mitigation: Redis cache with 60s TTL; add DB indexes on `orders.status` and `orders.created_at`.

## 20. Exit Criteria

- All P0 work items (IP.PR.06.001 through IP.PR.06.006, IP.PR.06.008, IP.PR.06.009, IP.PR.06.013, IP.PR.06.014, IP.PR.06.017, IP.PR.06.018) implemented and verified.
- All P1 work items (IP.PR.06.007, IP.PR.06.010, IP.PR.06.011, IP.PR.06.012, IP.PR.06.015, IP.PR.06.016) implemented and verified.
- Three-sided marketplace is demonstrable: at least one end-to-end flow exists for owner, driver, and admin roles.
- Role-based route guards prevent cross-role access on all protected routes.
- Real-time owner notification triggers within 2 seconds of order placement.
- Driver assignment assigns nearest mock driver successfully.
- Customer tracking page reflects live status updates from owner/driver actions.
- All new dashboards have loading, error, empty, and success states.
- Responsive layout and dark mode verified on owner, driver, and admin dashboards.
- Evidence screenshots/recordings captured per Section 17.
- PR.06 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.05)

PR.06 directly depends on PR.05 achievements:
- **IP.PR.05.001** — Location Auto-Detection: ensures customer can place orders that trigger owner notifications.
- **IP.PR.05.005** — Wallet Balance: earnings mock in driver dashboard may reference wallet pattern.
- **IP.PR.05.006** — Reorder Flow: customer reordering still works; no regression.
- **IP.PR.05.007** — Favorites Flow: customer favorites persist; no regression.
- **IP.PR.05.009** — Open/Closed Logic: owner open/closed toggle builds on existing `is_open` enforcement.
- **IP.PR.05.012** — Password Reset Flow: all roles (owner, driver, admin) can reset passwords using same flow.
- **IP.PR.05.013** — Address CRUD: customer addresses used in orders that owners/drivers see.
- **IP.PR.05.014** — Order Cancellation: owner reject action extends cancellation with reason.
- **IP.PR.05.015** — Enhanced Seed Data: seed data must now include owner/driver/admin accounts and owned restaurants.
- **IP.PR.05.I005** — Order State Machine: owner and driver status updates must respect valid transitions.
- **IP.PR.04.011** — Design System: all new dashboards reuse existing design tokens.

## 22. Connected Next-Level Requirements (link to PR.07)

PR.07 (Reliable Beta Product, score 7/10) builds on PR.06 and requires:
- Working owner, driver, and admin dashboards from all IP.PR.06 work items.
- Real-time notifications (IP.PR.06.013) as foundation for FCM push dispatch.
- Driver assignment (IP.PR.06.014) as foundation for predictive matching and shift scheduling.
- Batch pooling (IP.PR.06.016) as foundation for customer batch opt-in and route optimization.
- Role-based guards (IP.PR.06.017) as foundation for fine-grained permissions (RBAC with actions/resources).
- Live status timeline (IP.PR.06.018) as foundation for WebSocket reconnection and map integration.

PR.07 will introduce:
- Real FCM push notifications to owner and driver mobile apps.
- Real-time driver map tracking with Mapbox/Leaflet on customer tracking page.
- Address autocomplete with Nominatim or Google Places.
- Onboarding flow after signup (3-step: location, cuisines, done).
- Social login frontend wiring (Google OAuth backend ready).
- Loyalty points full activation and redemption.
- Group ordering (novelty).
- Meal rescue / end-of-day deals (novelty).
- Observability improvements (Prometheus/Grafana dashboards).
- WebSocket reconnection logic and exponential backoff.

PR.07 will be blocked if:
- Owner dashboard is broken (restaurants cannot operate).
- Driver dashboard is broken (deliveries cannot complete).
- Admin approval queue is broken (new restaurants cannot go live).
- Real-time notifications fail consistently (orders are missed).
- Driver assignment assigns wrong or no drivers.
- Role guards are bypassable (security risk).
- Customer tracking does not reflect real updates.

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (6/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.05 complete) described | Planner | ✅ |
| 4 | Target state (PR.06 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.06 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.06 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage includes batching, live timeline, three-sided marketplace | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.06.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover: owner dashboard, owner order actions, owner menu management, owner open/closed toggle, driver dashboard, driver delivery actions, driver earnings mock, admin dashboard, admin approval queue, admin user list, admin order monitoring, admin stats, real-time notifications, driver assignment, driver location mock, batch pooling, role guards, real timeline | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention SSE scalability, batch-engine docker-compose, JWT role claim, mock GPS, inter-service auth, admin route conflicts, stats performance | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.05) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.07) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required categories: owner dashboard + auth guard (IP.PR.06.001), owner order accept/reject/status update (IP.PR.06.002), owner menu management (IP.PR.06.003), owner open/closed toggle (IP.PR.06.004), driver dashboard + auth guard (IP.PR.06.005), driver accept/reject/pickup/deliver (IP.PR.06.006), driver earnings mock (IP.PR.06.007), admin dashboard + auth guard (IP.PR.06.008), admin restaurant approval queue (IP.PR.06.009), admin user list (IP.PR.06.010), admin order monitoring (IP.PR.06.011), admin stats summary endpoint (IP.PR.06.012), real-time notifications to owner (IP.PR.06.013), driver assignment endpoint with Haversine (IP.PR.06.014), driver location mock endpoint (IP.PR.06.015), basic batch engine order pooling (IP.PR.06.016), role-based route guards frontend (IP.PR.06.017), and order status timeline with real updates (IP.PR.06.018).
- Scope is tightly bounded to score 6/10 (three-sided marketplace with basic operational dashboards). Out-of-scope explicitly excludes real push notifications, real-time map with moving pin, advanced route optimization, payment webhooks, email/SMS, CDN, observability stack, CI/CD, group ordering, loyalty activation, and smart lockers.
- Data model coverage addresses schema verification: `restaurants.owner_id`, `orders.driver_id`, `orders.batch_id`, `menu_items.is_available`, `users.role` seeding. No new PostgreSQL tables required (batch tables already exist).
- Risks and blockers are grounded in known gaps from audits (SSE scalability, batch-engine docker-compose inclusion, JWT role claim presence, mock GPS proximity, inter-service auth, admin route conflicts, uncached admin stats).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references and blocker conditions.
- Feasibility tags use the required color system (🟢 LOCAL/DEMO-SAFE throughout; no 🔴 or ⚫ tags needed since all work is local-safe and demo-based).
- **One point deducted** because exact placement of owner and driver routes (within `apps/web` vs. new apps) and exact inter-service auth pattern (internal JWT vs. Kong gateway) are assumed from existing architecture conventions rather than explicitly confirmed. Minor discovery may be needed during build to locate these precisely.

The document is ready for execution.
