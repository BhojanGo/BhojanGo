# IP.PR.08 — Early Production Ready

## 1. Target Score Level: 8/10

## 2. Score Meaning

App is polished across mobile/tablet/desktop, accessible, secure enough for limited users, performant, and has strong demo + beta credibility. All major surface areas (a11y, Lighthouse, PWA, animations, real OAuth, address autocomplete, charts, i18n, offline cart) are intentionally designed and functional. The product feels like a real production product to investors, beta users, and stakeholders.

## 3. Current → Target Transition

**From PR.07 (resilient, consistent, observable, edge-case hardened):**
- Frontend uses TanStack Query with caching, retries, error boundaries, and loading states.
- Server-side inter-service calls retry 3× with exponential backoff; circuit breaker on payment-svc.
- Rate limiting is configured with development whitelist; 429 errors use consistent format.
- JWT validation middleware is consistent across all services with role claim verification.
- Token refresh mechanism rotates refresh tokens in Redis.
- bcrypt is pinned, password strength is enforced, SQL injection is eliminated.
- DB indexes are added on high-traffic columns; query latency is measurably improved.
- Every request carries `X-Request-ID`; every service logs it.
- All API errors return consistent `{error, message, request_id, details}` format.
- Pydantic schemas reject unknown fields and validate enums strictly.
- Order and payment creation enforce `Idempotency-Key` with 24h Redis cache.
- Robust cancellation from `pending`, `confirmed`, `preparing` with partial refund logic.
- Server-side serviceability and open/closed checks block checkout violations.
- Dynamic ETA calculated from real queue size.
- Guest OTP tracking works via mock SMS.
- Broken image URLs fall back to placeholder.
- Mock payment webhooks simulate provider callbacks locally.
- Event bus decouples order-svc from notification-svc via Redis pub/sub.
- Review moderation surfaces reported content to admin.
- Addresses validated by country-specific regex and stored as structured JSON.
- Load test baseline establishes p95 latency for core endpoints.

**However, PR.07 is still "production-content, beta-finishing":**
- No accessibility audit: keyboard navigation fails in modals, ARIA labels missing on cart, screen reader users cannot complete an order flow.
- No performance optimization: 800×600 hero images served as-is, no WebP, no lazy loading, generic system fonts, large JS bundles due to no code splitting.
- No CSRF tokens on state-changing endpoints; XSS risk on rendered user input (reviews, restaurant names).
- No brute force rate limiting on login beyond SlowAPI per-endpoint limits.
- No HTTPS for local development; mixed-content warnings during demos.
- No touch gesture support on mobile web; no haptic feedback, no pull-to-refresh.
- No PWA: no manifest, no service worker, no install prompt, no offline capability.
- Search is basic ILIKE only; no text ranking, no combined restaurant+menu search, no autocomplete.
- Admin dashboard shows only gradient divs for analytics; no real bar/line/pie charts.
- No animation system: page transitions are instant, add-to-cart has no visual feedback, toasts are abrupt.
- Generic Next.js 404/500 pages; no branded error pages with CTA.
- SEO meta tags are minimal; no Open Graph tags for social sharing, no structured data (JSON-LD) for restaurants.
- Google OAuth backend exists but no frontend wiring or "Sign in with Google" button.
- Address entry is manual only; no autocomplete, no map pin, no geocoding.
- Reviews are text-only; no photo upload capability.
- UI strings are partially hardcoded in English; no Hindi i18n on frontend, no language switcher.
- Cart lost when offline; no service worker caching or sync-on-reconnect.

**Target at score 8:**
- Accessibility: axe-core zero critical violations. Keyboard navigation for all interactive elements. Focus trapping in modals. ARIA labels on cart, search, navigation. Screen reader tested. Color contrast ratios >= 4.5:1.
- Performance: Next.js `<Image>` with proper sizes and priority. Lazy load below-fold images. Code splitting for admin/owner/driver pages. Preload critical fonts. `next/font` for Manrope + Inter. JS bundle size reduced.
- Security: CSRF tokens on all state-changing endpoints. XSS sanitization on rendered user input. Brute force rate limiting on login (max 5/min then lockout 15min). Secure cookies (`SameSite=Lax`, `HttpOnly` for auth token). Input sanitization on WYSIWYG. CSP headers.
- HTTPS: Self-signed certificate for local dev. nginx reverse proxy config documented for future staging. Force HTTPS redirect.
- Responsive polish: Swipe to dismiss cart item. Pull-to-refresh on mobile. Haptic feedback on add-to-cart. Smooth scroll for category tabs.
- PWA: Web app manifest with icons, theme color, display standalone. Service worker for offline indicator and basic caching. Install prompt on mobile.
- Advanced search: Backend text ranking with postgres `tsvector` or trigram. Combined search across restaurant name, cuisine, menu items. Autocomplete dropdown.
- Admin charts: Bar chart for daily orders, revenue line chart, pie chart for cuisine popularity. Lightweight chart library (Recharts or Chart.js).
- Animation system: Framer Motion page transitions (slide/fade). Add-to-cart fly animation. Cart badge wobble. Toast slide-in. Skeleton shimmer gradient.
- Error pages: Custom 404 with illustration and CTA. Custom 500 with retry button and support contact.
- SEO: `<title>`, `<meta name="description">`, `<meta property="og:*">` for all public pages. JSON-LD structured data for restaurants.
- Social login: Google OAuth 2.0 PKCE flow wired to frontend "Sign in with Google" button. Store `provider` and `provider_id` in users table.
- Address autocomplete: Google Places API (dev key) or OpenStreetMap Nominatim free API. Dropdown with formatted address selection.
- Review photos: Allow users to upload review photos (base64 or local file upload, stored in DB BLOB for demo).
- i18n: English + Hindi. `next-intl` with all UI strings in JSON. Language switcher in navbar.
- Offline cart: Cart operations work offline. Sync when back online.

## 4. Implementation Objective

Make the app feel like a real production product. Pass accessibility audits. Achieve good Lighthouse scores (>80 Performance, >90 Accessibility, >90 Best Practices, >90 SEO). Add self-signed HTTPS for local testing. Polish animations. Add social login. Improve search. Enable offline capability. The goal is demo credibility: when an investor, stakeholder, or beta user opens the app on any device, it feels polished, trustworthy, and complete.

## 5. Scope

### In Scope

1. **Accessibility full audit:**
   - Run axe-core (`@axe-core/playwright` or `@axe-core/react`) on every page.
   - Fix all critical and serious violations.
   - Ensure keyboard navigation for all interactive elements (tab order, focus states, escape key on modals).
   - Focus trapping in modals and bottom sheets.
   - ARIA labels on cart button (`aria-label="Cart, 3 items"`), search input (`role="search"`), navigation menu (`role="navigation"`).
   - Screen reader testing: order confirmation announces with `role="status"`, errors with `role="alert"`.
   - Color contrast ratios >= 4.5:1 for normal text, >= 3:1 for large text.

2. **Performance optimization:**
   - Replace all `<img>` with Next.js `<Image>` component with `sizes` prop and `priority` for above-fold images.
   - Lazy load below-fold images using `loading="lazy"` via Next.js Image.
   - Code split admin, owner, and driver pages using `dynamic()` import with `ssr: false` where appropriate.
   - Preload critical fonts using `<link rel="preload">` or `next/font`.
   - Use `next/font` for Manrope (headings) and Inter (body).
   - Reduce JS bundle size by tree-shaking unused imports and splitting heavy packages (chart library, map library).
   - Add `next-bundle-analyzer` to identify largest chunks.
   - Target Lighthouse Performance score > 80.

3. **Security hardening:**
   - CSRF tokens on all state-changing endpoints: `POST /api/v1/orders`, `POST /api/v1/payments/initiate`, `PATCH /api/v1/orders/{id}/cancel`, `POST /api/v1/reviews`.
   - XSS sanitization: use `bleach` (Python) or `DOMPurify` (frontend) on all rendered user input (review text, restaurant names, menu descriptions).
   - Brute force rate limiting on login: max 5 attempts per minute, then 15-minute lockout per IP+username. Store attempt counts in Redis.
   - Secure cookies: `SameSite=Lax`, `HttpOnly` for auth token cookie, `Secure` flag when HTTPS enabled.
   - Input sanitization: strip HTML tags from WYSIWYG fields. Reject `<script>`, `javascript:` protocols.
   - Content Security Policy (CSP) headers: `default-src 'self'`, `script-src 'self' 'unsafe-inline'`, `img-src 'self' https: data:`, `connect-src 'self' https://*.bhojango.local`.

4. **HTTPS / SSL for local dev:**
   - Generate self-signed certificate (`openssl req -x509 -nodes -days 365`).
   - Configure Next.js dev server to use HTTPS on `https://localhost:3000`.
   - Document nginx reverse proxy config for future staging (SSL termination, upstream to Next.js).
   - Force HTTPS redirect: detect `X-Forwarded-Proto` and redirect HTTP to HTTPS.

5. **Responsive polish — touch gestures:**
   - Swipe to dismiss cart item on mobile (touch gesture library or Framer Motion drag).
   - Pull-to-refresh on mobile restaurant list and order history (touch gesture or native pull-to-refresh simulation).
   - Haptic feedback simulation on mobile: ` navigator.vibrate(50)` on add-to-cart (only on supported devices).
   - Smooth scroll for category tabs on restaurant detail (CSS `scroll-behavior: smooth` + active tab indicator).

6. **PWA basics:**
   - Create `manifest.json` with `name: "BhojanGo"`, `short_name: "BhojanGo"`, `start_url: "/"`, `display: "standalone"`, `theme_color: "#E65100"`, `background_color: "#F7F5F2"`, icons at 192px and 512px.
   - Generate PWA icons from logo (or use placeholder saffron-colored icons).
   - Service worker using `next-pwa` or custom Workbox config: cache CSS/JS assets, show offline indicator banner when `navigator.onLine` is false.
   - Install prompt on mobile: detect `beforeinstallprompt` event, show "Add to Home Screen" button.
   - Offline indicator banner: top bar "You are offline. Some features unavailable." with reconnect detection.

7. **Advanced search backend:**
   - Add postgres text search: `tsvector` column on `restaurants(name, cuisine_types)` or trigram index (`pg_trgm`).
   - Combined search endpoint: `GET /api/v1/search?q=biryani` returns restaurants AND menu items matching query, ranked by relevance.
   - Search suggestions / autocomplete: `GET /api/v1/search/suggest?q=bir` returns `["Biryani", "Biryani House", "Biryani Bowl"]`.
   - Use GIN index on `tsvector` or trigram for fast prefix matching.

8. **Admin dashboard with charts:**
   - Install lightweight chart library: `recharts` (React) or `chart.js` with `react-chartjs-2`.
   - Daily orders bar chart: last 7 days, grouped by date.
   - Revenue line chart: last 30 days, cumulative + daily.
   - Cuisine popularity pie chart: order count by cuisine type.
   - Replace existing gradient divs in admin KPI dashboard with real charts.
   - Data sourced from existing admin analytics endpoints.

9. **Animation system:**
   - Install `framer-motion`.
   - Page transitions: `AnimatePresence` wrapping route segments. Fade + slight slide (x: 20 → 0, opacity: 0 → 1) on navigation.
   - Add-to-cart fly animation: item thumbnail shrinks and animates to cart icon position in navbar (FLIP or absolute positioned motion.div).
   - Cart badge wobble: `scale: [1, 1.3, 0.9, 1]` spring animation when item count changes.
   - Toast slide-in: toast container slides up from bottom-right with `y: 100 → 0`, auto-dismiss with fade out.
   - Skeleton shimmer: CSS gradient animation (`bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200`) on skeleton loaders.

10. **Custom error pages:**
    - Custom 404 page (`not-found.tsx`): illustrated food-themed graphic (e.g., empty plate), message "Looks like this page took a lunch break.", CTA button "Back to Restaurants".
    - Custom 500 page (`error.tsx`): message "Something went wrong in the kitchen.", retry button (`reset()` for error boundary), support contact link.
    - Both pages branded with BhojanGo colors and typography.

11. **SEO meta tags:**
    - `<title>`: dynamic per page — "Restaurants in {city} | BhojanGo", "Order from {restaurant_name} | BhojanGo", "Your Orders | BhojanGo".
    - `<meta name="description">`: unique, 150-160 chars per page.
    - `<meta property="og:title">`, `<meta property="og:description">`, `<meta property="og:image">` for restaurant detail and homepage.
    - `<meta name="twitter:card" content="summary_large_image">`.
    - `robots.txt` and sitemap.xml already exist; ensure dynamic pages are indexed.
    - JSON-LD structured data for restaurants: `@type: "Restaurant"`, `name`, `address`, `telephone`, `aggregateRating`, `servesCuisine`, `openingHours`, `image`.

12. **Google OAuth social login:**
    - Frontend: add "Sign in with Google" button using `@react-oauth/google` or Google Identity Services.
    - OAuth 2.0 PKCE flow: frontend gets authorization code, exchanges for access token + ID token.
    - Backend `POST /api/v1/auth/google` verifies ID token signature, creates user if not exists, generates JWT pair.
    - Store `provider = 'google'` and `provider_id` (Google `sub`) in `users` table.
    - If user already exists with same email but different provider, link accounts or prompt merge.
    - Show Google avatar in profile/navbar.

13. **Address autocomplete:**
    - Integrate OpenStreetMap Nominatim free API (no API key required for demo) OR Google Places API (free tier with dev key).
    - Autocomplete dropdown: as user types address, debounce 200ms, call API, show formatted suggestions.
    - On selection: populate structured fields (street, city, state, postal_code, lat, lng).
    - Show map pin preview with selected coordinates.
    - Store selected address in DB with lat/lng.

14. **Review photos:**
    - Allow users to upload 1-3 photos per review.
    - Frontend: file input `<input type="file" accept="image/*">`, preview thumbnails before submit.
    - Convert image to base64 string OR store as local file in `apps/web/public/uploads/reviews/` (demo-safe).
    - Backend: accept `review_photos` array of base64 strings, store in `review_photos` table (id, review_id, image_data TEXT for base64, or file_path).
    - Display photos in review cards as small thumbnails with lightbox on click.
    - Limit file size to 2MB per photo, max 3 photos per review.

15. **Multi-language i18n:**
    - Use `next-intl` (already installed for 3 locales).
    - Extract ALL hardcoded UI strings to `messages/en.json` and `messages/hi.json`.
    - Add Hindi translations for all customer-facing strings (use DeepL or manual translation).
    - Language switcher in navbar: EN / हिंदी toggle button.
    - Detect browser language preference (`navigator.language`) on first visit, default to detected language.
    - Persist language choice in `localStorage`.
    - RTL not required (English and Hindi are both LTR).

16. **PWA offline cart:**
    - Service worker intercepts cart-related API calls when offline.
    - Store cart mutations in IndexedDB queue (`pending_cart_actions`).
    - Show offline indicator on cart page.
    - On reconnect (`navigator.onLine` + `online` event), replay queued actions: sync cart with server, show "Cart synced" toast.
    - If offline during checkout, show "Connect to internet to place order" with retry button.

### Out of Scope

- CDN / S3 / image optimization pipeline (production scaling, deferred to PR.09).
- Real payment gateway webhooks (production Stripe/Razorpay webhooks, deferred to PR.09).
- Push / SMS / email production dispatch (FCM/SendGrid/Twilio production wiring, deferred to PR.09).
- Prometheus / Grafana / Loki / Jaeger observability stack (PR.07 has stdout JSON logs; dashboard polish deferred to PR.09).
- CI/CD improvements (deferred to PR.09).
- Group ordering (deferred to PR.09+).
- Smart lockers / IoT (deferred to PR.09+).
- AI / ML recommendations (deferred to PR.09+).
- Blockchain / carbon neutral (deferred to PR.10).
- Real-time driver tracking map with Mapbox/Leaflet (deferred to PR.09).
- Onboarding flow after signup (3-step wizard deferred to PR.09).
- Meal rescue / end-of-day deals (deferred to PR.09).
- Loyalty points full activation and redemption (deferred to PR.09).
- Grocery vertical (deferred to PR.10).

## 6. Out of Scope (Summary)

- CDN/S3 production image pipeline, real payment webhooks, FCM/SendGrid/Twilio production wiring.
- Full observability dashboard (Grafana/Loki/Jaeger), CI/CD improvements.
- Group ordering, loyalty full activation, meal rescue, smart lockers, onboarding wizard.
- AI/ML recommendations, real-time Mapbox tracking, grocery vertical.
- Blockchain / carbon neutral features.

## 7. Required Capabilities

- Accessibility: axe-core zero critical violations on all pages. Keyboard-only navigation can complete an order.
- Performance: Lighthouse Performance > 80, Accessibility > 90, Best Practices > 90, SEO > 90.
- Security: CSRF tokens on all state-changing endpoints. XSS sanitization on rendered user input. Brute force login lockout (5/min then 15min). Secure cookies with `HttpOnly`, `SameSite=Lax`. CSP headers active.
- HTTPS: Self-signed cert for local dev; nginx config documented; HTTPS redirect active.
- Touch gestures: Swipe to dismiss cart item. Pull-to-refresh on mobile lists. Haptic feedback on add-to-cart.
- PWA: Valid manifest.json. Service worker caches assets. Offline indicator banner. Install prompt on mobile.
- Advanced search: Postgres tsvector or trigram backend. Combined restaurant+menu search. Autocomplete dropdown.
- Admin charts: Recharts or Chart.js bar/line/pie charts for orders, revenue, cuisine popularity.
- Animation system: Framer Motion page transitions, add-to-cart fly animation, cart badge wobble, toast slide-in, skeleton shimmer.
- Custom 404/500 pages with brand illustration and CTA/retry.
- SEO: Dynamic `<title>`, `<meta description>`, `<meta og:*>` on all public pages. JSON-LD structured data for restaurants.
- Google OAuth: "Sign in with Google" button wired end-to-end. User creation/linking with `provider`/`provider_id`.
- Address autocomplete: Typeahead dropdown with formatted suggestions. Map pin preview. Structured address storage.
- Review photos: Upload 1-3 photos per review. Thumbnail display with lightbox. Base64 storage for demo.
- i18n: English + Hindi. All UI strings in JSON. Navbar language switcher. Browser language detection.
- Offline cart: Cart operations queue in IndexedDB when offline. Sync on reconnect. Offline indicator.
- Core customer loop and three-sided marketplace remain stable (no regression from PR.07).

## 8. Key User Journeys

### Journey 8.1 — Customer Places Order with Full Polish
1. Customer opens app on mobile browser. PWA install prompt appears; customer adds to home screen.
2. Customer navigates restaurant list. Framer Motion fade transition plays. Images lazy-load as customer scrolls.
3. Customer types "biryani" in search bar. Autocomplete dropdown shows suggestions. Backend uses tsvector ranking.
4. Customer selects restaurant. Dynamic `<title>` and OG meta tags reflect restaurant name.
5. Customer scrolls menu. Category tabs smooth-scroll to sections.
6. Customer clicks "Add" on Paneer Tikka. Add-to-cart fly animation plays. Cart badge wobbles. Haptic feedback vibrates on mobile.
7. Customer views cart. Swipes left to dismiss an item.
8. Customer proceeds to checkout. Address field shows autocomplete as customer types.
9. Customer places order. Toast slides in: "Order placed! Tracking #12345". Order confirmation announces via `role="status"` to screen reader.
10. Customer tracks order. Page transitions smoothly. Status timeline updates with animation.

### Journey 8.2 — Guest User Signs Up with Google
1. Guest visits `/login`. Sees "Sign in with Google" button alongside email/password.
2. Guest clicks Google button. OAuth PKCE flow opens popup, user selects account.
3. Frontend receives ID token, sends to `POST /api/v1/auth/google`.
4. Backend verifies token, creates user with `provider='google'`, `provider_id='sub_value'`, `avatar_url` from Google profile.
5. Backend returns JWT pair. Frontend stores access token in httpOnly cookie + localStorage (for API headers).
6. Guest is redirected to `/restaurants`. Navbar shows Google avatar and name.
7. Guest can now place orders, view history, and earn loyalty points.
8. On next visit, if Google session is active, auto-login via refresh token.

### Journey 8.3 — Customer Uses App Offline
1. Customer adds items to cart while on subway (offline).
2. Service worker detects offline state. Cart actions queued in IndexedDB.
3. Offline indicator banner appears at top: "You are offline. Cart saved locally."
4. Customer navigates to order history (cached via TanStack Query, displayed from cache).
5. Customer exits app. Returns home and reopens when back online.
6. App detects `online` event. Replays queued cart actions. Syncs with server.
7. Toast appears: "Cart synced. Ready to checkout!"
8. Customer proceeds to checkout normally.

### Journey 8.4 — Admin Views Analytics Dashboard
1. Admin logs into admin dashboard (`/admin`).
2. KPI page loads with real charts: bar chart for daily orders (last 7 days), line chart for revenue (last 30 days), pie chart for cuisine popularity.
3. Admin hovers over bar chart; tooltip shows exact order count for that day.
4. Admin clicks "Reported Reviews" tab. Sees bar chart of reports by category.
5. Admin navigates between pages. Framer Motion page transition plays.
6. Admin page is code-split; heavy chart library loads on demand, not on initial admin login.

### Journey 8.5 — Screen Reader User Completes Order
1. User opens site with NVDA/VoiceOver. Page title announced: "Restaurants in Mumbai | BhojanGo".
2. User tabs through restaurant list. Each card announces: "Spice Garden, Indian cuisine, 4.5 stars, 30 minutes delivery, link".
3. User selects restaurant. Menu categories announced as tab list. Menu items as buttons with price.
4. User activates "Add to cart" on an item. Screen reader announces: "Paneer Tikka added to cart. Cart now has 3 items."
5. User tabs to cart button, opens cart. Focus trapped in cart drawer. Escape key closes drawer.
6. User proceeds to checkout. Form fields have `<label>` associations. Errors announced via `role="alert"`.
7. User places order. Confirmation page announces: "Order placed successfully. Your order number is 12345. Estimated delivery in 35 minutes."
8. No axe-core critical or serious violations detected throughout journey.

## 9. Technical Coverage

### Backend
- **user-svc:**
  - Add `POST /api/v1/auth/google` endpoint for OAuth token verification and user creation/linking.
  - Add brute force rate limiting on `POST /api/v1/auth/login`: Redis-based attempt counter, lockout after 5 failures.
  - Add CSRF token generation and validation middleware.
  - Add secure cookie settings (`HttpOnly`, `SameSite=Lax`, `Secure` on HTTPS).
  - Add CSP header middleware.
  - Update user model: `provider`, `provider_id`, `avatar_url` fields.
- **restaurant-svc:**
  - Add postgres `tsvector` or `pg_trgm` trigram index for full-text search on `name` and `cuisine_types`.
  - Add combined search endpoint `GET /api/v1/search` returning restaurants + menu items ranked.
  - Add autocomplete endpoint `GET /api/v1/search/suggest`.
  - Add JSON-LD generation helper for restaurant detail response.
  - Add review photo storage: `review_photos` table migration.
- **order-svc:**
  - Add CSRF token check to state-changing endpoints.
  - Add XSS sanitization on order notes, cancellation reason.
  - Ensure consistent error format for new endpoints.
- **payment-svc:**
  - Add CSRF token check to `POST /api/v1/payments/initiate`.
  - Add secure cookie handling for payment session.
- **notification-svc:**
  - No changes required for PR.08.
- **batch-engine:**
  - No changes required for PR.08.

### Frontend — apps/web
- Install `framer-motion`, `recharts` (or `chart.js`), `@axe-core/react` (dev), `next-pwa`.
- Configure `next/font` with Manrope and Inter.
- Add PWA manifest and service worker via `next-pwa`.
- Add dynamic `<title>`, `<meta>`, and JSON-LD via `next/head` or `metadata` export per page.
- Add Google Identity Services script and "Sign in with Google" button.
- Add address autocomplete component with Nominatim/Places API.
- Add review photo upload component with preview and base64 conversion.
- Add language switcher component (`next-intl`).
- Add offline indicator banner component.
- Add service worker cart sync logic.
- Add Framer Motion `AnimatePresence` page transitions.
- Add add-to-cart fly animation, cart badge wobble, toast slide-in.
- Add custom `not-found.tsx` and `error.tsx` pages.
- Add accessibility fixes: focus trapping modal, keyboard nav, ARIA labels, contrast fixes.
- Add touch gesture support: swipe handlers for cart, pull-to-refresh.

### Frontend — apps/admin
- Install `recharts` (if not already) and replace gradient divs with real charts.
- Add code splitting for heavy chart pages using `dynamic()`.
- Add Framer Motion page transitions.
- Add accessibility fixes.

### Frontend — apps/mobile
- Add haptic feedback on add-to-cart (`react-native-haptic-feedback` or `Vibration` API).
- Add pull-to-refresh on restaurant list and order history (`RefreshControl`).
- Add offline indicator (`NetInfo`).
- Add language switcher UI. Ensure `next-intl` or equivalent i18n strings loaded.
- Add review photo upload (Expo ImagePicker).

### Data
- Migration: add `provider`, `provider_id`, `avatar_url` to `users`.
- Migration: add `review_photos` table (`id`, `review_id`, `image_data TEXT` for base64, `file_path` for local storage, `created_at`).
- Migration: add GIN index on `tsvector` column or `pg_trgm` index on `restaurants(name)` and `restaurants(cuisine_types)`.
- Migration: add `search_vector` tsvector column to `restaurants` if using tsvector approach.
- Redis: brute force login attempt counters (`login_attempts:{ip}:{username}`) with TTL 15min.

## 10. UI / UX Coverage

- **Loading states:** Skeleton shimmer animation on all loading screens (restaurant list, menu, orders).
- **Error states:** Custom 404 with illustration, custom 500 with retry button. Network errors show toast with retry.
- **Empty states:** No changes from PR.07 (already have empty state illustrations).
- **Success states:** Toast slide-in with checkmark icon for add-to-cart, order placed, cart synced.
- **Design system:** Apply BhojanGo brand palette (saffron `#E65100`, trust green `#2E7D32`, nugget gold `#FFB300`, cream `#F7F5F2`, near-black `#1A1A1A`). Use Manrope + Inter fonts.
- **Responsive:** Touch gestures for mobile, PWA install prompt, haptic feedback. TV breakpoint: 6 columns for 4K.
- **Dark mode:** No dark mode toggle in PR.08 (deferred to PR.09). CSS `dark:` classes remain but not activated.
- **Accessibility:** Full keyboard navigation, focus trapping, ARIA labels, screen reader announcements, contrast >= 4.5:1.
- **Animations:** Page fade/slide transitions, add-to-cart fly, badge wobble, toast slide, skeleton shimmer.

## 11. Data / Model Coverage

- `users` table: new columns `provider` VARCHAR(20), `provider_id` VARCHAR(100), `avatar_url` TEXT. Index on `(provider, provider_id)` for OAuth lookups.
- `review_photos` table: new table (`id` UUID PK, `review_id` UUID FK → `reviews.id`, `image_data` TEXT for base64 or `file_path` VARCHAR(500), `created_at` TIMESTAMP).
- `restaurants` table: new `search_vector` tsvector (if using tsvector) or rely on `pg_trgm` GIN index on `name` and `cuisine_types`.
- Redis keys:
  - `login_attempts:{ip}:{username}` — counter, TTL 900s (15min).
  - `csrf_token:{session_id}` — CSRF token, TTL 3600s (1h).
  - `offline_cart_queue:{user_id}` — serialized pending cart actions, TTL 86400s.
- No new PostgreSQL tables beyond `review_photos`.

## 12. Role / Permission Coverage

- `customer`: Full access to polished features. Can upload review photos, use address autocomplete, switch language, use PWA offline cart. Subject to brute force rate limits.
- `restaurant_owner`: Access to owner dashboard with code-split pages. Can view analytics. No admin charts.
- `delivery_partner`: Access to driver app with haptic feedback and pull-to-refresh.
- `admin` / `super_admin`: Full access to admin dashboard with charts. Can view all review photos. Not subject to brute force lockout (or has higher threshold).
- `guest` (unauthenticated): Can browse restaurants, use address autocomplete, view search results. Cannot place order (login required). Can use PWA install prompt.
- **Cross-role enforcement:** JWT middleware unchanged from PR.07. New `provider`/`provider_id` fields do not affect role checking.

## 13. Performance / Reliability / Security Coverage

### Performance
- Next.js `<Image>` with `sizes` and `priority` reduces Largest Contentful Paint (LCP) by serving appropriately sized images.
- Lazy loading below-fold images reduces initial page weight.
- `next/font` with `display: swap` eliminates font flash and reduces render-blocking.
- Code splitting admin/owner/driver pages reduces initial JS bundle for customer-facing pages.
- Bundle analyzer identifies and eliminates unused dependencies.
- Postgres GIN/trigram indexes make search queries fast (<100ms) even with large datasets.

### Reliability
- PWA service worker caches static assets; app loads even with poor connectivity.
- Offline cart queue ensures user actions are not lost during temporary disconnections.
- `navigator.onLine` + `online` event triggers sync when connectivity returns.
- Framer Motion animations are interruptible and do not block user interactions.
- Custom error pages with retry buttons prevent dead-ends.

### Security
- CSRF tokens prevent cross-site request forgery on all state-changing endpoints.
- XSS sanitization prevents script injection via reviews, restaurant names, descriptions.
- Brute force lockout prevents credential stuffing attacks (5 attempts then 15min lockout).
- Secure cookies (`HttpOnly`, `SameSite=Lax`) prevent token theft via XSS and CSRF.
- CSP headers restrict script/image sources and prevent inline script injection.
- Self-signed HTTPS for local dev prevents mixed-content warnings and trains secure-by-default practices.
- Input sanitization on WYSIWYG fields strips `<script>` tags and `javascript:` URIs.

## 14. Novelty / Differentiation Coverage

At score 8, novelty is secondary to polish, but some differentiators emerge:
- **PWA offline cart** — Users can add items on subway/plane and sync later. Most food apps require constant connectivity. Competitive edge for commuters.
- **Real accessibility** — Most food delivery apps have poor a11y. Passing axe-core zero violations is a genuine differentiator for inclusive design.
- **Review photos with lightbox** — Social proof through visual evidence. Trust-building moment before ordering.
- **Dynamic SEO + JSON-LD** — Restaurants get rich Google snippets with ratings, cuisine, opening hours. SEO benefit for BhojanGo and partner restaurants.
- **Hindi i18n** — First-class support for India's largest market. Language switcher shows cultural awareness.
- **Google OAuth one-tap** — Frictionless login reduces abandonment vs email/password.
- **Animation polish** — Add-to-cart fly + haptic feedback + page transitions create "delight" moments that generic clones lack.
- **Admin charts** — Restaurant owners see real data visualization vs raw numbers. Perceived as more professional platform.

Differentiators deferred: AI meal suggestions, voice ordering, group ordering, meal rescue, smart lockers, loyalty full activation, real-time Mapbox tracking, onboarding wizard.

## 15. Implementation Work Items

### IP.PR.08.001 — Accessibility Audit + Fixes
- **Category:** Frontend
- **Implementation Scope:** Install `@axe-core/playwright` (or `@axe-core/react` for dev). Run audit on every page: `/`, `/restaurants`, `/restaurants/[id]`, `/cart`, `/checkout`, `/orders`, `/profile`, `/wallet`, `/login`, `/signup`. Fix all critical/serious violations. Add keyboard navigation: tab order, escape key on modals/drawers, enter key on buttons. Add focus trapping in cart drawer and address autocomplete dropdown. Add ARIA labels: `aria-label` on cart button with item count, `role="search"` on search form, `role="navigation"` on navbar, `role="alert"` on error toasts, `role="status"` on success announcements. Fix color contrast: ensure all text meets WCAG 2.1 AA (4.5:1 normal, 3:1 large). Test with NVDA/VoiceOver at least one full order flow.
- **Acceptance Criteria:**
  1. axe-core reports zero critical and zero serious violations on all customer pages.
  2. Keyboard-only user can browse restaurants → add to cart → checkout → place order.
  3. Focus is trapped in modals/drawers; Escape key closes them.
  4. Screen reader announces cart count changes and order confirmation.
  5. All text meets WCAG 2.1 AA contrast ratios.
- **Evidence Required:** axe-core report screenshot. Screen recording of keyboard-only order flow. Color contrast checker screenshots (e.g., axe DevTools).
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07 (functional UI exists to audit)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.002 — Performance Optimization (Image, Font, Code Split)
- **Category:** Frontend
- **Implementation Scope:** Replace all `<img>` tags in `apps/web` and `apps/admin` with Next.js `<Image>`, specifying `sizes` (e.g., `sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"`) and `priority` for above-fold hero images. Add lazy loading for below-fold images (`loading="lazy"` is default in Next.js Image). Configure `next/font/google` for Manrope (headings, weights 400, 500, 600, 700) and Inter (body, weights 400, 500). Apply fonts via CSS variables. Add code splitting: wrap admin analytics, owner dashboard, driver dashboard in `dynamic(() => import('...'), { ssr: false })` to exclude from initial customer bundle. Install `@next/bundle-analyzer` and run analysis; document largest chunks and optimization steps. Target Lighthouse Performance score > 80.
- **Acceptance Criteria:**
  1. All images use Next.js `<Image>` with `sizes` and `placeholder="blur"` where applicable.
  2. Manrope and Inter loaded via `next/font` with no layout shift.
  3. Admin/owner/driver bundle chunks are not loaded on initial customer page load.
  4. Bundle analyzer report identifies reduction in initial JS size.
  5. Lighthouse Performance score >= 80 on `/restaurants` page (desktop + mobile).
- **Evidence Required:** Lighthouse report screenshot. Bundle analyzer screenshot showing split chunks. Network tab showing lazy-loaded images.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.003 — Security Hardening (CSRF, XSS, Brute Force, CSP)
- **Category:** Backend + Frontend
- **Implementation Scope:** **CSRF:** Backend middleware generates CSRF token per session, stores in Redis. Frontend interceptors read token from cookie and send as `X-CSRF-Token` header on POST/PATCH/DELETE. Validate on all state-changing endpoints. **XSS:** Backend uses `bleach.clean()` on review text, restaurant name, menu description before storage. Frontend uses `DOMPurify.sanitize()` before rendering user-generated HTML. **Brute force:** Redis-based attempt counter. On `POST /api/v1/auth/login`, increment `login_attempts:{ip}:{username}`. If count >= 5, return 429 with lockout message and set Redis key with TTL 900s (15min). Reset counter on successful login. **Secure cookies:** Set auth token cookie with `HttpOnly`, `SameSite=Lax`, `Secure` flag when `APP_ENV != development`. **CSP:** Add middleware setting `Content-Security-Policy` header per scope document. Allow `'unsafe-inline'` for scripts only if necessary (Next.js requires it for hydration).
- **Acceptance Criteria:**
  1. POST request without valid CSRF token returns 403.
  2. Review text containing `<script>alert(1)</script>` is sanitized before storage/display.
  3. 5 failed login attempts trigger 15-minute lockout; 6th attempt returns 429.
  4. Auth token cookie has `HttpOnly` and `SameSite=Lax` flags.
  5. CSP header is present on all responses.
- **Evidence Required:** `curl` without CSRF token → 403. `curl` with XSS payload → sanitized output in DB. `curl` 6 failed logins → 429. Browser DevTools showing cookie flags. Response headers showing CSP.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.004 (consistent auth middleware)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.004 — Self-Signed HTTPS + nginx Config
- **Category:** DevOps / Frontend
- **Implementation Scope:** Generate self-signed certificate: `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout localhost.key -out localhost.crt`. Configure Next.js dev server HTTPS via `server.https` in `next.config.js` or use `local-ssl-proxy`. Add `localhost.crt` to `.gitignore`. Document in `docs/HTTPS_SETUP.md`: certificate generation, browser trust instructions (Chrome `chrome://flags/#allow-insecure-localhost`), Firefox certificate import. Create `nginx/bhojango.conf` template: reverse proxy from port 443 to Next.js 3000, SSL cert paths, `X-Forwarded-Proto` header. Add force-HTTPS redirect middleware in Next.js: if `req.headers['x-forwarded-proto'] === 'http'`, redirect to HTTPS. Mark as staging documentation (not production).
- **Acceptance Criteria:**
  1. `https://localhost:3000` loads without certificate error (after trust setup).
  2. HTTP request to port 80 redirects to HTTPS.
  3. nginx config file is documented and syntactically valid (`nginx -t`).
  4. Self-signed cert files are excluded from git.
- **Evidence Required:** Screenshot of `https://localhost:3000` with lock icon. `curl -I http://localhost` showing 301 to HTTPS. `nginx -t` output.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.005 — Touch Gestures + Pull-to-Refresh + Haptic Feedback
- **Category:** Frontend (Web + Mobile)
- **Implementation Scope:** **Web:** Implement swipe to dismiss cart item using Framer Motion `drag="x"` with drag constraints. Item slides left, reveals delete button; continue swipe past threshold deletes item with fade out. Pull-to-refresh on mobile restaurant list: detect touch drag down past threshold, trigger data refetch via TanStack Query, show spinner indicator. **Mobile (apps/mobile):** Add `RefreshControl` to `FlatList` on restaurant list and order history. Add haptic feedback on add-to-cart using `Vibration.vibrate(50)` on Android and `Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)` on iOS (Expo). Add smooth scroll for category tabs: `ScrollView` with `scrollTo` animation on tab press. **Web:** Use CSS `scroll-behavior: smooth` on menu category container.
- **Acceptance Criteria:**
  1. Swipe left on cart item reveals delete option; full swipe removes item with animation.
  2. Pull down on restaurant list triggers refresh spinner and reloads data.
  3. Mobile add-to-cart triggers haptic feedback (50ms vibration on Android, light impact on iOS).
  4. Clicking category tab smooth-scrolls to section.
  5. Touch gestures do not interfere with scrolling or other interactions.
- **Evidence Required:** Screen recording of swipe-to-dismiss and pull-to-refresh. Mobile screen recording of haptic feedback.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.08.001 (a11y audit ensures gestures don't break keyboard nav)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.006 — PWA Manifest + Service Worker + Install Prompt
- **Category:** Frontend
- **Implementation Scope:** Install `next-pwa` in `apps/web`. Configure `next.config.js` with `pwa: { dest: 'public', register: true, skipWaiting: true }`. Create `public/manifest.json` with BhojanGo branding: `name`, `short_name`, `start_url`, `display: "standalone"`, `theme_color: "#E65100"`, `background_color: "#F7F5F2"`, icons at 192px and 512px (generate saffron-colored "BG" icon). Service worker automatically caches JS/CSS assets. Add offline indicator banner component: checks `navigator.onLine`, shows/hides top banner. Add install prompt: detect `window.beforeinstallprompt`, save event, show "Add BhojanGo to Home Screen" button. On click, call `prompt()`. Handle `appinstalled` event to hide button. Ensure PWA passes Chrome DevTools Lighthouse PWA audit.
- **Acceptance Criteria:**
  1. `manifest.json` is valid and linked in `<head>`.
  2. Chrome DevTools > Application > Manifest shows all fields correctly.
  3. Service worker registers and caches static assets.
  4. Offline indicator banner appears when network disconnects.
  5. "Add to Home Screen" button appears on supported mobile browsers and triggers install prompt.
  6. Lighthouse PWA audit passes (all checks green or yellow).
- **Evidence Required:** Chrome DevTools manifest screenshot. Lighthouse PWA audit screenshot. Screen recording of install prompt on mobile.
- **Priority:** P0
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.007 — Advanced Search Backend (tsvector / trigram)
- **Category:** Backend
- **Implementation Scope:** Add `pg_trgm` extension if not present (`CREATE EXTENSION IF NOT EXISTS pg_trgm;`). Create GIN indexes: `CREATE INDEX idx_restaurants_name_trgm ON restaurants USING GIN (name gin_trgm_ops);` and `CREATE INDEX idx_cuisine_types_trgm ON restaurants USING GIN (cuisine_types gin_trgm_ops);`. Optionally add `tsvector` approach: add `search_vector` tsvector column, populate with `name || ' ' || cuisine_types`, create GIN index. Implement `GET /api/v1/search?q={query}`: queries restaurants using `name % '{query}'` (trigram similarity) or `search_vector @@ plainto_tsquery('{query}')`, ranks by similarity. Also search `menu_items` via ILIKE or trigram join. Return combined results: `{restaurants: [...], menu_items: [...], total_count}`. Implement `GET /api/v1/search/suggest?q={prefix}`: uses `SELECT DISTINCT name FROM restaurants WHERE name ILIKE '{prefix}%' LIMIT 5` (fast for demo) or trigram similarity for fuzzy matching.
- **Acceptance Criteria:**
  1. Search for "biryani" returns restaurants with "biryani" in name or cuisine, plus menu items matching.
  2. Results ranked by relevance (exact match > partial > fuzzy).
  3. Autocomplete endpoint returns suggestions within 100ms.
  4. `EXPLAIN ANALYZE` shows index scan (not sequential scan) on search query.
- **Evidence Required:** `curl` search output. `EXPLAIN ANALYZE` showing GIN index usage. Autocomplete dropdown demo.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.008 — Admin Charts Dashboard
- **Category:** Frontend
- **Implementation Scope:** Install `recharts` in `apps/admin` (or use existing `react-chartjs-2`). Replace gradient divs in admin `/dashboard` with real charts: (1) BarChart: daily orders last 7 days, data from `GET /api/v1/admin/analytics/orders/daily`. (2) LineChart: revenue last 30 days, data from `GET /api/v1/admin/analytics/revenue/daily`. (3) PieChart: cuisine popularity, data from `GET /api/v1/admin/analytics/cuisines`. Ensure data endpoints exist or create lightweight aggregations. Add responsive container (`ResponsiveContainer`) so charts resize. Add tooltips showing exact values. Use BhojanGo brand colors for chart series (saffron `#E65100`, trust green `#2E7D32`, nugget gold `#FFB300`). Code-split chart pages using `dynamic()`.
- **Acceptance Criteria:**
  1. Admin dashboard shows three charts: orders bar, revenue line, cuisine pie.
  2. Charts use real data from backend endpoints.
  3. Charts are responsive and readable on desktop and tablet.
  4. Tooltips show exact values on hover.
  5. Chart library is code-split and not loaded on non-admin pages.
- **Evidence Required:** Screenshot of admin dashboard with three charts. Network tab showing chart library loaded on demand.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (recharts/chart.js library)

### IP.PR.08.009 — Animation System (Framer Motion)
- **Category:** Frontend
- **Implementation Scope:** Install `framer-motion` in `apps/web` and `apps/admin`. Wrap page content in `AnimatePresence` with `motion.div` transitions: `initial={{ opacity: 0, x: 20 }}`, `animate={{ opacity: 1, x: 0 }}`, `exit={{ opacity: 0, x: -20 }}`, `transition={{ duration: 0.3, ease: "easeOut" }}`. Implement add-to-cart fly animation: on "Add" click, create absolute-positioned `motion.img` (thumbnail clone) that animates from item position to cart icon position in navbar using `animate` with `x`, `y`, `scale: [1, 0.5, 0]` and `opacity: [1, 1, 0]`. Implement cart badge wobble: `animate={{ scale: [1, 1.3, 0.9, 1.1, 1] }}` with `transition: { type: "spring", stiffness: 300 }` when item count changes. Implement toast slide-in: toast container enters with `y: 100 → 0`, `opacity: 0 → 1`, exits with `y: 0 → 20`, `opacity: 1 → 0`. Implement skeleton shimmer: CSS `@keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }` on skeleton loaders.
- **Acceptance Criteria:**
  1. Page transitions are smooth fade + slide on all route changes.
  2. Add-to-cart shows visible fly animation from item to cart icon.
  3. Cart badge wobbles on item count change.
  4. Toasts slide in from bottom-right and fade out on dismiss.
  5. Skeleton loaders show shimmer gradient animation.
- **Evidence Required:** Screen recording of page transition, add-to-cart fly, badge wobble, toast, skeleton shimmer.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.010 — Custom 404 / 500 Error Pages
- **Category:** Frontend
- **Implementation Scope:** Create `apps/web/app/not-found.tsx`: food-themed illustration (empty plate or spilled curry), heading "Looks like this page took a lunch break.", subtext "Let's get you back to something delicious.", CTA button "Browse Restaurants" linking to `/restaurants`. Use BhojanGo brand colors. Create `apps/web/app/error.tsx`: heading "Something went wrong in the kitchen.", subtext "Our chefs are working on it. Try again or contact support.", retry button calling `reset()` from error boundary props, support link to `/support`. Both pages include navbar and footer for consistent branding. Ensure 404/500 pages are accessible (proper heading hierarchy, alt text on images, focusable button).
- **Acceptance Criteria:**
  1. Visiting non-existent route shows branded 404 page with illustration and CTA.
  2. Clicking CTA navigates to `/restaurants`.
  3. Triggering an error (e.g., throw in test component) shows branded 500 page with retry button.
  4. Retry button re-renders the failed component.
  5. Both pages pass axe-core accessibility check.
- **Evidence Required:** Screenshots of 404 and 500 pages. Screen recording of retry button working.
- **Priority:** P1
- **Effort:** S
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.011 — SEO Meta Tags + JSON-LD Structured Data
- **Category:** Frontend + Backend
- **Implementation Scope:** Use Next.js `metadata` export (App Router) for each page: `layout.tsx` (default site metadata), `/restaurants/page.tsx` ("Restaurants in {city} | BhojanGo"), `/restaurants/[id]/page.tsx` (dynamic title, description, OG image from restaurant). Add `<meta property="og:title">`, `<meta property="og:description">`, `<meta property="og:image">`, `<meta property="og:type" content="website">`. Add Twitter card meta. Backend: enhance `GET /api/v1/restaurants/{id}` response to include JSON-LD data or generate it in frontend page. JSON-LD for restaurants: `@context: "https://schema.org"`, `@type: "Restaurant"`, `name`, `image`, `address` (structured), `telephone`, `servesCuisine`, `priceRange`, `aggregateRating` (from reviews), `openingHours`. Inject JSON-LD via `<script type="application/ld+json">` in page component. Ensure `robots.txt` and `sitemap.xml` reference all public pages.
- **Acceptance Criteria:**
  1. Every public page has unique `<title>` and `<meta name="description">`.
  2. Restaurant detail page has complete Open Graph meta tags.
  3. JSON-LD script is present on restaurant detail with all required fields.
  4. Google Rich Results Test (or schema validator) passes on restaurant page.
  5. Lighthouse SEO score >= 90.
- **Evidence Required:** View-source screenshot showing meta tags. Google Rich Results Test screenshot. Lighthouse SEO score screenshot.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.012 — Google OAuth Social Login
- **Category:** Backend + Frontend
- **Implementation Scope:** **Backend:** Add `POST /api/v1/auth/google` endpoint. Accept `id_token` in body. Verify token signature using Google's public keys (JWKS endpoint `https://www.googleapis.com/oauth2/v3/certs`). Extract `email`, `name`, `picture`, `sub` from token payload. Check if user exists by `provider_id = sub`. If not, create user with `provider='google'`, `provider_id=sub`, `avatar_url=picture`. If user exists with same email but `provider=null` (email/password), link accounts: set `provider='google'`, `provider_id=sub`, `avatar_url=picture`. Generate JWT pair (access + refresh) and return. **Frontend:** Add "Sign in with Google" button to `/login` and `/signup` pages using `@react-oauth/google` or Google Identity Services. On success, send `id_token` to backend. Store returned tokens and user data. Display Google avatar in navbar/profile. Add `provider` field to user state/context. Ensure social login button works alongside existing email/password form.
- **Acceptance Criteria:**
  1. Clicking "Sign in with Google" initiates OAuth flow and creates/links user.
  2. New Google user gets JWT pair and can browse restaurants immediately.
  3. Existing email/password user with same email gets account linked.
  4. Google avatar and name display in navbar after login.
  5. Logout clears Google session and local auth state.
- **Evidence Required:** Screen recording of Google login flow. DB query showing `provider='google'`. Navbar showing Google avatar.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.PR.07.004 (consistent auth)
- **Status:** TODO
- **Implementation Class:** 🟡 OPTIONAL EXTERNAL (Google OAuth API)

### IP.PR.08.013 — Address Autocomplete (Nominatim / Google Places)
- **Category:** Frontend + Backend
- **Implementation Scope:** Use OpenStreetMap Nominatim free API (`https://nominatim.openstreetmap.org/search?format=json&q={query}`) as default (no API key, demo-safe). Add debounced input (200ms) in address form. On input change, call Nominatim with `User-Agent: BhojanGo/1.0`. Show dropdown of formatted suggestions (`display_name`). On select: parse address components (street, city, state, postcode, country) using Nominatim response fields; set lat/lng from `lat`/`lon`. Show mini map pin preview using static map image (OpenStreetMap static tiles) or simple lat/lng display. Store structured address in DB via existing address endpoints. Alternative: use Google Places Autocomplete if dev key available (`PLACES_API_KEY` env var). Implement as generic component that accepts provider prop.
- **Acceptance Criteria:**
  1. Typing "MG Road" shows autocomplete suggestions within 200ms.
  2. Selecting a suggestion populates all address fields (street, city, state, postal, country, lat, lng).
  3. Address is stored in DB in structured JSON format.
  4. Works without API key using Nominatim (demo-safe).
  5. Optional Google Places integration works when key is configured.
- **Evidence Required:** Screen recording of address autocomplete. DB query showing structured address with lat/lng.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.07.021 (structured address validation)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE (Nominatim) / 🟡 OPTIONAL EXTERNAL (Google Places)

### IP.PR.08.014 — Review Photo Upload
- **Category:** Frontend + Backend
- **Implementation Scope:** **Frontend:** Add file input to review form (`<input type="file" accept="image/*" multiple>`). Show thumbnail previews of selected images. Validate: max 3 files, max 2MB each. Convert images to base64 strings on frontend (for demo; production would use S3). Send base64 array in `POST /api/v1/reviews` body as `photos: [...]`. **Backend:** Accept `photos` array in review creation schema. Store each photo in `review_photos` table: `review_id`, `image_data` (TEXT, base64 string for demo), or `file_path` if saving to local disk (`apps/web/public/uploads/reviews/`). Add `GET /api/v1/restaurants/{id}/reviews` to include photo URLs in response. **Frontend display:** Render review photos as thumbnails in review cards. Click opens lightbox modal with full-size image. Use Next.js `<Image>` for thumbnails.
- **Acceptance Criteria:**
  1. User can select 1-3 images when submitting a review.
  2. Thumbnails preview before submit.
  3. Oversized files (>2MB) or >3 files rejected with error message.
  4. Review displays photo thumbnails. Click opens lightbox.
  5. Photos persist in DB and display on page reload.
- **Evidence Required:** Screen recording of review photo upload + preview + lightbox. DB query showing `review_photos` rows.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.07.020 (review moderation exists)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.015 — i18n English + Hindi (next-intl)
- **Category:** Frontend
- **Implementation Scope:** Ensure `next-intl` is configured in `apps/web` and `apps/admin`. Create/complete `messages/en.json` and `messages/hi.json` with ALL UI strings. Include strings for: navbar, homepage, restaurant list/detail, cart, checkout, order tracking, profile, wallet, login/signup, error pages, toasts, confirmation messages. Add Hindi translations (use DeepL API, ChatGPT, or manual translation for ~200-300 keys). Add language switcher component to navbar: EN / हिंदी toggle. On toggle, call `router.push(pathname, { locale: newLocale })`. Store selected locale in `localStorage`. On first visit, detect `navigator.language`; if `hi` or `hi-IN`, default to Hindi. Ensure dates, currencies, and numbers format per locale (INR for Hindi, USD/INR based on selected country). RTL not needed.
- **Acceptance Criteria:**
  1. All UI strings are extracted to JSON files (zero hardcoded strings in TSX).
  2. Language switcher toggles between English and Hindi instantly.
  3. Hindi locale displays all text in Hindi including error messages.
  4. Locale preference persists across sessions.
  5. Browser language detection defaults to Hindi for `hi-IN` on first visit.
- **Evidence Required:** Screenshots of same page in English and Hindi. `localStorage` showing locale preference. Screen recording of language switch.
- **Priority:** P0
- **Effort:** M
- **Dependency:** Existing i18n infrastructure (already partial)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.016 — Offline Cart Sync
- **Category:** Frontend
- **Implementation Scope:** Implement service worker (via `next-pwa`) to intercept cart API calls (`POST /api/v1/cart/add`, `PATCH /api/v1/cart/update`, `DELETE /api/v1/cart/remove`). When `navigator.onLine === false`, queue mutations in IndexedDB (`pending_cart_actions` object store with fields: `action`, `payload`, `timestamp`). Show offline indicator banner: "You are offline. Cart saved locally." On `online` event, replay queued actions: iterate IndexedDB queue, send each request to server, remove from queue on success. Show "Cart synced" toast when complete. If replay fails (e.g., item no longer available), show error toast with details. On cart page, show "Connect to internet to place order" if offline with retry button (checks connection and replays).
- **Acceptance Criteria:**
  1. Offline add-to-cart stores action in IndexedDB.
  2. Offline indicator banner appears when network disconnects.
  3. On reconnect, queued cart actions replay and sync with server.
  4. "Cart synced" toast appears after successful replay.
  5. Checkout button disabled when offline with message to reconnect.
- **Evidence Required:** Screen recording: add to cart → disconnect wifi → add more → reconnect → sync → toast.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.PR.08.006 (PWA service worker)
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

### IP.PR.08.017 — Design System Token Application
- **Category:** Frontend
- **Implementation Scope:** Apply BhojanGo design tokens across all frontend apps: Define CSS custom properties in `globals.css` or Tailwind config: `--color-saffron: #E65100`, `--color-trust-green: #2E7D32`, `--color-nugget-gold: #FFB300`, `--color-cream: #F7F5F2`, `--color-near-black: #1A1A1A`. Replace generic Tailwind colors (`emerald-600`, `gray-500`) with brand tokens. Standardize icon usage: replace all emoji with Lucide React icons (stroke width 1.5px, size 24px). Standardize badge anatomy: border-radius 40px, padding 4px 12px, font-weight 600. Standardize card anatomy: Image 16:10, gradient overlay, name, cuisine chips, rating badge, delivery time badge. Document in `packages/ui/design.md`. Ensure trust badges ("FSSAI Verified", "Freshly Prepared", "Under 30 min") visible on restaurant cards.
- **Acceptance Criteria:**
  1. All customer-facing pages use brand color tokens consistently.
  2. Zero emoji in UI; all icons are Lucide React.
  3. Badges follow standard anatomy across all pages.
  4. Restaurant cards follow defined anatomy.
  5. At least 3 trust markers visible per restaurant card.
- **Evidence Required:** Screenshots of homepage, restaurant list, and detail showing consistent tokens. `grep` for emoji returns zero results.
- **Priority:** P1
- **Effort:** M
- **Dependency:** None
- **Status:** TODO
- **Implementation Class:** 🟢 LOCAL/DEMO-SAFE

## 16. Acceptance Criteria

- [ ] axe-core zero critical/serious violations on all customer pages.
- [ ] Keyboard-only navigation can complete full order flow.
- [ ] Lighthouse Performance > 80, Accessibility > 90, Best Practices > 90, SEO > 90.
- [ ] All images use Next.js `<Image>` with `sizes` and lazy loading.
- [ ] Manrope and Inter fonts loaded via `next/font` with no layout shift.
- [ ] Admin/owner/driver pages are code-split; initial bundle reduced.
- [ ] CSRF token validated on all state-changing endpoints.
- [ ] XSS payloads sanitized before storage and display.
- [ ] Brute force lockout active: 5 failed logins = 15min lockout.
- [ ] Auth cookies have `HttpOnly` and `SameSite=Lax` flags.
- [ ] CSP header present on all responses with reasonable policy.
- [ ] Self-signed HTTPS works on `https://localhost:3000`.
- [ ] Swipe to dismiss works in cart on mobile web.
- [ ] Pull-to-refresh works on mobile lists.
- [ ] Haptic feedback triggers on mobile add-to-cart.
- [ ] `manifest.json` valid and linked; PWA installable on mobile.
- [ ] Service worker caches assets; offline indicator banner functional.
- [ ] Advanced search returns ranked restaurant + menu results with GIN index.
- [ ] Autocomplete endpoint returns suggestions within 100ms.
- [ ] Admin dashboard displays three real charts (orders, revenue, cuisine).
- [ ] Framer Motion page transitions play on all route changes.
- [ ] Add-to-cart fly animation, cart badge wobble, toast slide-in visible.
- [ ] Custom 404 and 500 branded error pages functional.
- [ ] All public pages have unique `<title>`, `<meta description>`, OG tags.
- [ ] JSON-LD structured data present on restaurant detail pages.
- [ ] Google OAuth login button works end-to-end.
- [ ] Address autocomplete suggests addresses with structured fields and lat/lng.
- [ ] Review photo upload supports 1-3 images with preview and lightbox.
- [ ] All UI strings extracted to `en.json` and `hi.json`; language switcher works.
- [ ] Offline cart queues actions in IndexedDB and syncs on reconnect.
- [ ] Design system tokens (colors, typography, icons, badges, cards) applied consistently.
- [ ] Core customer loop and three-sided marketplace remain stable (no regression from PR.07).

## 17. Evidence Required

- axe-core report (zero critical/serious) for `/restaurants`, `/restaurants/[id]`, `/cart`, `/checkout`.
- Lighthouse report screenshots (desktop + mobile) showing scores > 80 Performance, > 90 Accessibility, > 90 Best Practices, > 90 SEO.
- Screen recording: customer browses restaurants → search autocomplete → add to cart (fly animation + haptic + badge wobble) → checkout → place order (toast slide-in).
- Screen recording: swipe to dismiss cart item, pull-to-refresh, smooth category scroll.
- Screen recording: Google OAuth login flow from button click to navbar avatar.
- Screen recording: offline add-to-cart → reconnect → sync toast.
- Screenshots: custom 404 page, custom 500 page with retry.
- Screenshots: admin dashboard with three charts.
- View-source: meta tags and JSON-LD on restaurant detail page.
- `curl`: search endpoint showing ranked results. `EXPLAIN ANALYZE` showing GIN index scan.
- `curl`: CSRF validation (without token → 403), XSS sanitized output, brute force lockout (6th attempt → 429).
- Browser DevTools: cookie flags (`HttpOnly`, `SameSite=Lax`), CSP header.
- `curl -I http://localhost` showing HTTPS redirect.
- `manifest.json` validator screenshot (Chrome DevTools Application tab).
- Lighthouse PWA audit screenshot.
- Screenshots: English and Hindi versions of same page.
- DB queries: `SELECT provider, provider_id FROM users`, `SELECT * FROM review_photos`, `SELECT * FROM pg_indexes WHERE tablename = 'restaurants'`.
- Screen recording: review with photos → click thumbnail → lightbox.

## 18. Dependencies

### External Tools
- Docker + docker-compose (PostgreSQL, Redis, Kong).
- Node.js + pnpm (frontend build).
- Python + Poetry/pip (backend services).
- `openssl` (for self-signed cert generation).
- `next-pwa` (for service worker and manifest).
- `framer-motion` (for animations).
- `recharts` or `chart.js` + `react-chartjs-2` (for admin charts).
- `@axe-core/playwright` or `@axe-core/react` (for a11y audit).
- `next/font` (built into Next.js 14).
- OpenStreetMap Nominatim API (free, no key).
- Google OAuth 2.0 API (optional, free tier with dev key).
- Google Places API (optional, free tier with dev key).

### Internal Dependencies
- **PR.07 must be complete:** TanStack Query caching, consistent auth, consistent error format, correlation ID logging, DB indexes, idempotency, cancellation, event bus, review moderation, address validation.
- `next-intl` must be installed and configured (already partial in repo).
- `redis` must be running (used for brute force lockout, CSRF tokens, offline cart queue).
- `kong` gateway must be configured (unchanged from PR.07).
- PostgreSQL must have `pg_trgm` extension available (for advanced search).
- Self-signed cert files must be excluded from git.

## 19. Risks / Blockers

- **Accessibility audit scope:** Every interactive element must be checked. Mitigation: use automated axe-core first, then manual keyboard test one journey.
- **Framer Motion performance:** Complex animations may cause jank on low-end devices. Mitigation: use `will-change: transform`, `transform: translateZ(0)` GPU acceleration. Disable animations if `prefers-reduced-motion` is set.
- **next/font vs existing font loading:** May conflict with existing CSS font imports. Mitigation: remove existing `@import` Google Fonts links from `_document.tsx` or `globals.css` before enabling `next/font`.
- **PWA service worker caching stale data:** Service worker may serve old API responses. Mitigation: use network-first strategy for API calls, cache-first for static assets. Add cache versioning.
- **Google OAuth dev key requirements:** Google OAuth requires OAuth consent screen configuration and authorized redirect URIs. Mitigation: document setup steps in `docs/OAUTH_SETUP.md`. Fallback to backend-only testing if key unavailable.
- **Nominatim rate limits:** Free Nominatim API has usage policy (1 request/sec). Mitigation: implement strict debounce (200ms) and client-side caching of recent queries.
- **CSP with Next.js:** Next.js requires `'unsafe-inline'` for script-src during dev due to inline scripts for fast refresh. Mitigation: use stricter CSP in production builds only; document policy per environment.
- **Offline cart sync complexity:** Replaying queue may cause race conditions with TanStack Query cache. Mitigation: invalidate cart query after replay completes. Use optimistic updates carefully.
- **Hindi translation completeness:** ~200-300 keys may have nuance issues. Mitigation: use professional translation tool (DeepL) for first pass, manual review for food-specific terms.
- **HTTPS trust on mobile:** Self-signed certs cause security warnings on mobile browsers. Mitigation: document trust steps. Acceptable for local demo only.

## 20. Exit Criteria

- All P0 work items (IP.PR.08.001, IP.PR.08.002, IP.PR.08.003, IP.PR.08.006, IP.PR.08.012, IP.PR.08.015) implemented and verified.
- All P1 work items (IP.PR.08.004 through IP.PR.08.005, IP.PR.08.007 through IP.PR.08.011, IP.PR.08.013 through IP.PR.08.014, IP.PR.08.016 through IP.PR.08.017) implemented and verified.
- Accessibility: axe-core zero critical/serious violations across all customer pages.
- Performance: Lighthouse scores meet targets (Performance > 80, Accessibility > 90, Best Practices > 90, SEO > 90).
- Security: CSRF, XSS, brute force, secure cookies, CSP all active and verified.
- PWA: manifest valid, service worker registered, installable on mobile, offline indicator functional.
- Animations: page transitions, add-to-cart fly, badge wobble, toast slide-in, skeleton shimmer all visible.
- i18n: English + Hindi fully functional with language switcher and browser detection.
- Offline cart: queues and syncs correctly on reconnect.
- Google OAuth and address autocomplete functional (or documented as optional if external key unavailable).
- Admin charts display real data.
- Custom 404/500 pages are branded and functional.
- SEO meta tags and JSON-LD present on all public pages.
- Core customer loop and three-sided marketplace remain stable (no regression from PR.07).
- Evidence screenshots/recordings captured per Section 17.
- PR.08 declared complete.

## 21. Connected Previous-Level Requirements (link to PR.07)

PR.08 directly depends on PR.07 achievements:
- **IP.PR.07.001** — TanStack Query caching: foundation for offline cart sync and pull-to-refresh data refetch.
- **IP.PR.07.002** — Server-side retries + circuit breaker: ensures search endpoint remains resilient.
- **IP.PR.07.003** — Rate limiting: brute force lockout extends existing SlowAPI config.
- **IP.PR.07.004** — Auth consistency + token refresh: foundation for Google OAuth integration and secure cookies.
- **IP.PR.07.008** — Correlation ID logging: debugging animation/perf issues requires request tracing.
- **IP.PR.07.009** — Consistent API error format: frontend error handling for CSRF/XSS failures.
- **IP.PR.07.010** — Strict input validation: ensures XSS payloads are caught at schema level before sanitization.
- **IP.PR.07.012** — Robust cancellation/refund: custom 500 page needs retry logic for failed cancellation.
- **IP.PR.07.020** — Review moderation: review photo upload builds on existing review system.
- **IP.PR.07.021** — Address validation: structured JSON storage enables autocomplete integration.
- **IP.PR.07.022** — Load testing baseline: performance optimizations measured against existing baseline.

## 22. Connected Next-Level Requirements (link to PR.09)

PR.09 (Production-Grade Competitive App, score 9/10) builds on PR.08 and requires:
- Working PWA with offline indicator as foundation for full offline order history.
- Animations as foundation for onboarding flow wizard and real-time map tracking.
- Google OAuth as foundation for Apple Sign-In and additional social providers.
- Admin charts as foundation for restaurant owner analytics dashboard.
- i18n infrastructure as foundation for additional languages (Tamil, Telugu, Spanish).
- SEO + JSON-LD as foundation for restaurant SEO landing pages.
- Address autocomplete as foundation for real-time ETA and delivery zones.
- Review photos as foundation for rich review system with moderation AI.

PR.09 will introduce:
- Real FCM push notifications to owner/driver mobile apps (production wiring).
- Real-time driver map tracking with Mapbox/Leaflet on customer tracking page.
- Onboarding flow after signup (3-step: location, cuisines, done).
- Loyalty points full activation and redemption at checkout.
- Group ordering with shareable link.
- Meal rescue / end-of-day deals.
- Real payment webhooks (Stripe/Razorpay production).
- CDN/S3 image pipeline with WebP generation.
- CI/CD pipeline improvements.
- Observability dashboard (Grafana/Loki/Jaeger).
- Dark mode toggle.
- WebSocket reconnection logic.

PR.09 will be blocked if:
- PWA service worker is not functional (offline experience broken).
- Accessibility is not complete (screen reader users cannot complete core flow).
- Performance Lighthouse < 80 (poor demo impression).
- Security hardening is incomplete (CSRF, XSS, CSP missing).
- i18n is not complete (cannot add more languages).
- Animations cause performance regression (jank on mobile).

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target score level explicitly stated (8/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present | Planner | ✅ |
| 3 | Current state (PR.07 complete) described | Planner | ✅ |
| 4 | Target state (PR.08 done) described | Planner | ✅ |
| 5 | Scope section lists exactly what PR.08 covers | Planner | ✅ |
| 6 | Out-of-scope section lists what PR.08 does NOT cover | Planner | ✅ |
| 7 | Key user journeys explicitly listed and numbered | Planner | ✅ |
| 8 | Technical coverage lists backend + frontend targets | Planner | ✅ |
| 9 | UI/UX coverage mentions loading, error, empty, success states | Planner | ✅ |
| 10 | Data/model coverage confirms schema changes | Planner | ✅ |
| 11 | Role/permission coverage scoped appropriately | Planner | ✅ |
| 12 | Performance/reliability/security addressed | Planner | ✅ |
| 13 | Novelty coverage notes deferred differentiators | Planner | ✅ |
| 14 | Work items use exact required format with ID IP.PR.08.XXX | Planner | ✅ |
| 15 | Every work item has Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class | Planner | ✅ |
| 16 | At least 15 work items present | Planner | ✅ |
| 17 | Work items cover all required PR.08 areas (a11y, perf, security, HTTPS, gestures, PWA, search, charts, animation, error pages, SEO, OAuth, autocomplete, review photos, i18n, offline cart) | Planner | ✅ |
| 18 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 19 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 20 | Dependencies list external tools and internal prerequisites | Planner | ✅ |
| 21 | Risks / Blockers mention a11y scope, animation perf, font conflict, SW caching, OAuth setup, Nominatim limits, CSP, offline sync, Hindi translations, HTTPS mobile trust | Planner | ✅ |
| 22 | Exit criteria are clear and minimal | Planner | ✅ |
| 23 | Connected previous-level (PR.07) requirements listed with specific work item references | Planner | ✅ |
| 24 | Connected next-level (PR.09) requirements and blockers listed | Planner | ✅ |
| 25 | Self-audit checklist exists and is populated | Planner | ✅ |
| 26 | Self-score is assigned and >=8 (otherwise revise) | Planner | ✅ |

## 24. Self-Score

**Score: 9 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- Work items follow the exact mandated format and cover all required PR.08 areas: accessibility audit + fixes (IP.PR.08.001), performance optimization (IP.PR.08.002), security hardening (IP.PR.08.003), self-signed HTTPS (IP.PR.08.004), touch gestures + pull-to-refresh + haptic (IP.PR.08.005), PWA manifest + service worker (IP.PR.08.006), advanced search backend (IP.PR.08.007), admin charts dashboard (IP.PR.08.008), animation system with Framer Motion (IP.PR.08.009), custom 404/500 pages (IP.PR.08.010), SEO meta + JSON-LD (IP.PR.08.011), Google OAuth social login (IP.PR.08.012), address autocomplete (IP.PR.08.013), review photo upload (IP.PR.08.014), i18n English + Hindi (IP.PR.08.015), offline cart sync (IP.PR.08.016), and design system token application (IP.PR.08.017).
- Scope is tightly bounded to score 8/10 (polished, accessible, performant, secure, PWA-ready, multi-device smooth, with real external integrations). No premature scaling or enterprise features.
- Out-of-scope explicitly excludes CDN/S3, real payment webhooks, real push/email/SMS, full observability stack, CI/CD, group ordering, loyalty full activation, meal rescue, smart lockers, AI/ML, blockchain, real-time Mapbox tracking, onboarding wizard.
- Data model coverage addresses OAuth fields, review photos table, search indexes, Redis keys for brute force and CSRF. No unnecessary PostgreSQL table additions.
- Risks and blockers are grounded in known gaps from audits (animation performance on low-end devices, next/font conflict, PWA service worker stale cache, Google OAuth setup steps, Nominatim rate limits, CSP Next.js dev conflict, offline cart sync race conditions, Hindi translation completeness, HTTPS mobile trust issues).
- Connected previous-level and next-level requirements are explicitly documented with specific work item references and blocker conditions.
- Feasibility tags use the required color system: 🟢 LOCAL/DEMO-SAFE for all work items except Google OAuth (IP.PR.08.012, 🟡 OPTIONAL EXTERNAL) and admin charts (IP.PR.08.008, 🟡 OPTIONAL EXTERNAL due to chart library dependency).
- **One point deducted** because the exact choice between `pg_trgm` and `tsvector` for search is left to implementation discretion, and the chart library (Recharts vs Chart.js) is not pre-selected. Additionally, the Nominatim vs Google Places provider for address autocomplete is left as a configuration option rather than mandated. These are minor implementation choices that do not affect plan completeness.

The document is ready for execution.
