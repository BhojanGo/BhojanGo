# Security review (Round 21)

**Date:** 2026-11-19. **Scope:** the website, the admin console, core_api, realtime and the worker (code and config), every way money leaves us, and secrets in the repo, GitHub and Railway.
**How:** we read the code, extended the access sweep, and ran gitleaks over the full history. Nothing was sent to QA or production and no live host was tested. The tests run in CI on a throwaway database.
**Earlier work:** the automated scans from 2026-11-12 (ZAP, semgrep, trivy, dependency audits) are in [docs/security/report.md](../security/report.md). This review doesn't repeat them.

Ranks:

- **High:** anyone with an ordinary account, or nobody at all, can get money, food or someone else's account.
- **Medium:** needs an insider, a second step, or a mistake by us, or the harm is bounded.
- **Low:** hardening.

Every High finding is fixed in this PR, and each fix has a test that fails without it.

## Findings

| ID | Rank | Area | Finding | Status |
|---|---|---|---|---|
| S1 | High | Website | Stored XSS on public kitchen and city pages. A kitchen's name or dish text could close the JSON-LD `<script>` tag and run script for every visitor, and tokens are kept in localStorage. | Fixed in this PR |
| S2 | High | Payments webhooks | The Razorpay webhook checked signatures against an empty secret, and production sets no Razorpay keys. Also, a provider's event could settle another provider's payment. Either way, any customer could have an order placed without paying. | Fixed in this PR |
| S3 | High | Money out | `POST /wallet/topup` credited any amount without taking a payment, and the wallet then paid for real orders. | Fixed in this PR |
| S4 | High | Access | A kitchen owner could set their own `status` through `PUT /restaurants/{id}`. That let them go live without approval or undo a suspension. | Fixed in this PR |
| S5 | Medium | Access sweep | Five id routes were swept with made-up ids (offers, tier changes, ordering pauses, bulk refunds, chat messages), so their ownership checks were never really tested. Kitchen-to-kitchen id swaps weren't tested either. | Fixed in this PR |
| S6 | Medium | Money out (review orders) | A country manager could make any live city review-only and add their own account through the markets API. That account's orders would then cost nothing, and the change wasn't audited. | Fixed in this PR |
| S7 | Medium | Rate limits | Quotes had no limit per person. A US quote calls Stripe Tax, so a loop would use up its rate limit and cost money. | Fixed in this PR |
| S8 | Medium | Web, admin | Access and refresh tokens are kept in localStorage, so any XSS takes over the account. | Plan |
| S9 | Medium | Headers | The CSP allows `script-src 'unsafe-inline'` in production, so it doesn't stop injected inline script. | Plan |
| S10 | Medium | Realtime | A WebSocket's token is checked only when it connects. A socket outlives the token's 15 minutes, a sign-out and a removed role. There's no per-user cap on sockets. | Plan |
| S11 | Medium | Money out (offers) | A kitchen's own offer has no ceiling on `flat_off` or `weekly_cap`. A kitchen working with a customer can push its statement below zero, and we carry the loss. | Plan |
| S12 | Medium | Money out (bulk refunds) | A bulk refund runs with no second admin when every order is under `auto_refund_limit`. The batch total isn't capped (up to 500 orders × the limit). | Plan |
| S13 | Medium | Uploads, menus | `image_url`, `logo_url` and `cover_url` accept any string, including outside hosts and `javascript:`, and customers are shown them. | Plan |
| S14 | Low | Web | Open redirect after sign-in: `?next=/<tab>/evil.com` got past `safeNext`. | Fixed in this PR |
| S15 | Low | Internal endpoints | The default `INTERNAL_SERVICE_SECRET` was refused only when `APP_ENV=production`, not when only Railway's environment name says production. | Fixed in this PR |
| S16 | Low | Audit | Item refunds and kitchen approve/reject write a row and a log line, but no audit-log entry. | Plan |
| S17 | Low | Uploads | The type check trusts the client's Content-Type (no magic bytes). PDFs open inline for admins. There's no per-user upload quota. | Plan |
| S18 | Low | Rate limits | Per-IP limits are in process memory (slowapi), so they reset on every deploy. That's fine with one process; it won't be after scaling out. | Plan |
| S19 | Low | CORS | `CORS_ORIGINS` isn't checked in production. The default is localhost, and `*` would be accepted alongside credentials. | Plan |
| S20 | Low | Realtime | The WebSocket token can go in `?token=`, which ends up in proxy logs. Internal signatures can be replayed for 5 minutes, but those endpoints are idempotent. | Plan |

## Fixes in this PR

### S1: JSON-LD stored XSS (High)

- **The hole.** `JSON.stringify` leaves `<` alone. The kitchen page put the kitchen's name, category names and dish names and descriptions into `<script type="application/ld+json">` through `dangerouslySetInnerHTML`:
  - `apps/web/src/app/[country]/[city]/[kitchen]/page.tsx:135`
  - the city page, which uses kitchen names (`apps/web/src/app/[country]/[city]/page.tsx:101`)
- **Who could use it.** Anyone can sign up as a kitchen partner (`POST /kitchens/apply`), and dish text is free text (`backend/core_api/modules/catalog/schemas/restaurant.py`). A description of `</script><script>…` would run on our own origin.
- **The damage.** The CSP allows inline script (S9), and the session lives in localStorage (`apps/web/src/lib/client.ts:61`). The script could read every visitor's tokens.
- **Fix.** `apps/web/src/lib/jsonLd.ts` escapes `<`, `>`, `&`, U+2028 and U+2029. Both pages use it.
- **Test.** `apps/web/test/jsonLd.test.ts` checks the escaping, and also fails if any file puts `JSON.stringify` straight into `__html`. That second check fails on the old pages.

### S2: payment webhooks (High)

- **Empty secret.**
  - `razorpay_svc.verify_webhook_signature` computed `HMAC(RAZORPAY_WEBHOOK_SECRET, body)`. With the secret empty, anyone can compute that.
  - Production lists no `RAZORPAY_*` variables ([production-config.md](production-config.md)), and neither does QA (the lead's inventory below). So the route was live with an empty key.
- **Cross-provider settle.** `apply_payment_event` looked the payment up by provider id only. A forged `payment.captured` naming a Stripe `pi_…` id would mark that payment paid and place the order. The customer can see the id in their own `client_secret`.
- **What an attacker got.** Food without paying, while we still paid the kitchen and the rider.
- **Fix.**
  - No secret means the webhook is refused (`backend/core_api/modules/payments/service/razorpay_svc.py:35`).
  - A provider only settles its own payments (`backend/core_api/modules/payments/api/v1/payments.py:241`).
- **Tests.**
  - `test_security_review.py::test_razorpay_webhook_without_a_secret_is_refused`
  - `::test_one_providers_webhook_cant_settle_another_providers_payment`
  - the unit test `payments/tests/test_checkout.py::test_razorpay_webhook_needs_its_secret`
- **Already fine.**
  - Stripe: `construct_event` refuses an empty secret (stripe 16.1, checked), keeps Stripe's 300 s replay window, and every event id is applied once (`processed_webhook_events`).
  - Connect and payouts webhooks (`finance/api/v1/finance.py:489`): the same Stripe check, applied once per event.
  - The fake gateway's webhook: refused in production (`payments.py`, `fake_webhook`), and its provider is refused at start in any environment named production.
  - Alertmanager's webhook: a token, and refused when the token is empty.

### S3: free wallet top-up (High)

- **The hole.**
  - `POST /api/v1/wallet/topup` credited `amount` straight away. The `payment_method_id` it took was never charged.
  - `POST /payments/initiate` with `payment_method_type: "wallet"` then debited that balance and placed the order (`payments.py:107`).
  - No client uses either one. "Wallet" in the apps means Razorpay's wallets.
- **Fix.** The route is gone. A wallet now gets money only from refunds of wallet payments. The OpenAPI and the TypeScript client are regenerated.
- **Tests.**
  - `test_there_is_no_free_wallet_top_up`
  - `test_an_empty_wallet_cant_pay_for_an_order`
- **Sweep.** The sweep's entry for the route is removed.

### S4: an owner setting their kitchen's status (High)

- **The hole.** `RestaurantUpdateRequest.status` (`catalog/schemas/restaurant.py:79`) was saved as-is behind `access.manage`, which lets the owner through. Approve and reject (`access.administer`, `partners.edit` in the city) could be skipped.
- **Fix.** Any `status` in an update now needs `access.administer` (`catalog/api/v1/restaurants.py:304`). Owners still edit everything else, and no client sends `status`.
- **Test.** `test_an_owner_cant_approve_or_unsuspend_their_own_kitchen`.

### S5: access sweep extension (Medium)

See [Access sweep coverage](#access-sweep-coverage).

### S6: review-only cities through the API (Medium)

- **The hole.** `review_only` and `review_accounts` were ordinary city settings. Anyone with `markets.edit` for that country could set them with `PATCH /markets/cities/{code}`, and the change wasn't audited.
- **What it would do.**
  - The named account's orders in that city cost nothing (pricing engine `review`, `orders/service/order.py:246`).
  - The city disappears for everyone else.
  - Review orders are left off every statement (`finance/service/payouts.py:106`). So no money leaves us, but the real kitchens would cook for free.
- **Fix.** The API refuses both keys (`markets/service/rules.py:153`). Only `backend/tools/review_accounts.py` sets them, and it writes to the database directly.
- **Test.** `markets/tests/test_rules.py::test_review_accounts_are_never_set_through_the_api`.

### S7: quote rate limit (Medium)

- **Fix.** `POST /pricing/quote` allows 60 a minute and 2,000 a day per person, counted in Redis. Past that it answers 429 `TOO_MANY_QUOTES` with `Retry-After`.
- **Settings.** `QUOTE_LIMIT_PER_MINUTE` and `QUOTE_LIMIT_PER_DAY`. 0 turns a limit off, but never in production.
  - Load runs that share a few seed accounts (`tools/load/pilot.js` quotes about once a second at scale 1) should set `QUOTE_LIMIT_PER_MINUTE=0` on the target.
- **Tests.**
  - `pricing/tests/test_quote_limits.py`
  - `test_quotes_are_limited_per_person`

### S14: open redirect (Low) and S15: internal secret (Low)

- **S14.** `safeNext` now refuses control characters and backslashes, and resolves the path the way a browser does (`apps/web/src/app/signin/next.ts`; test `apps/web/test/next.test.ts`).
- **S15.** `shared/internal_auth.py:26` now also checks `production_named`; test `core_api/tests/test_internal_auth.py`.

## Plans for the Medium findings

| ID | Plan | Size |
|---|---|---|
| S8 | Move the web and admin sessions to httpOnly, `Secure`, `SameSite=Lax` cookies set by a small Next route handler. The browser no longer holds the refresh token. Do the admin first, because its token carries admin roles. The apps keep secure storage. | 2–3 days |
| S9 | A nonce-based CSP in Next middleware, which drops `'unsafe-inline'` from `script-src`. Cached pages need the nonce added at the edge. Until then, S1's escaping is what keeps JSON-LD safe. | 2 days |
| S10 | Store each socket's token `exp` and close the socket at expiry with code 4401. The clients already reconnect with a fresh token. Re-check `can_see` when an order's rider changes. Cap sockets per user (say 5) and per IP. | 1 day |
| S11 | Cap `flat_off` at a share of `min_subtotal` (and require `min_subtotal > 0` for it). Cap `weekly_cap` at the kitchen's previous 4 weeks' average sales. Carry a negative statement into the next week, never to zero. | 1 day |
| S12 | Add a cap on a bulk refund's total for the automatic path (a business rule, say 50 × the per-order limit). Above it, a second admin approves even when every order is small. | half a day |
| S13 | Accept only our own upload paths (`/api/v1/uploads/menu-photo/<own id>/…`) or `https://` on our photo host for `image_url`, `logo_url` and `cover_url`, with a length limit. Clean existing rows once with a script. | half a day |

Low findings, when there's time:

- **S16:** `audit.record` for item refunds and kitchen approve/reject.
- **S17:** check the magic bytes and serve `Content-Disposition: attachment` from `/uploads/view`; add a per-user daily upload count.
- **S18:** keep slowapi in Redis (`storage_uri`) before running more than one core_api process.
- **S19:** make `core_api_production_problems` refuse `*` and non-https entries in `CORS_ORIGINS`.
- **S20:** stop the clients sending `?token=` once the subprotocol path echoes its protocol.

## Area notes

### Access control

- **Kinds of check.**
  - Every core_api route depends on `get_current_user` or `require_permission(...)` (an admin with the permission and a two-step sign-in token). Otherwise it's in the sweep's public list, with a reason for each.
  - Admin scope is checked with `admin.require(permission, city|country)` on the resource's own city.
  - Kitchens go through `catalog/service/access.py` (`manage`: owner or `partners.edit`; `administer`: admins only).
- **Internal endpoints.**
  - `orders/api/v1/internal.py` and `realtime/app/api/v1/batches.py` take an HMAC of timestamp, method, path and body, with a 300 s window and a constant-time compare (`shared/internal_auth.py`).
  - The review simulator's step (`/internal/review/orders/{id}/step`) also refuses any order that isn't a review account's in a review-only city (`orders/service/review_sim.py:48`).
- **Tokens.** Refresh tokens rotate, and reusing one kills its family (`identity/service/auth.py:140`). Admin tokens need `mfa=true` (`shared/auth.py:77`; swept by `test_admin_routes_need_the_second_step`).

### Rate limits and lockouts

| What | Limit | Where |
|---|---|---|
| Password sign-in | 30/min and 300/h per IP (ceiling); account locks for 15 min after 5 wrong tries | `identity/api/v1/auth.py:43`, `service/guard.py` |
| Sending SMS and email codes | 1 per 30 s, 5 per hour, 10 per day per number or address | `service/guard.py` `code_send_wait` |
| Checking a code | 5 wrong tries, then the code is burnt; two-step: 5 per challenge, then the account locks | `service/otp.py`, `service/email_codes.py`, `service/mfa.py` |
| Password reset; phone and social sign-in | 5/min per IP plus the per-address send limit; 30/min per IP | `auth.py:115,135,176`, `email_auth.py` |
| Kitchen sign-up; Help votes, contact form, signed-in messages | 30/min per IP; 10/min, 3/min and 5/min per IP, with daily caps | `kitchens.py:177`, `help_public.py:124,161,197` |
| Quotes | 60/min and 2,000/day per person (new, S7) | `pricing/api/v1/pricing.py` |

### CORS and headers

- **CORS.** core_api, realtime and the worker allow only `CORS_ORIGINS`, with credentials (`core_api/main.py:93`, `realtime/app/main.py:48`). The APIs authenticate with bearer tokens, not cookies, so cross-site requests carry no credentials. See S19.
- **API headers.** `nosniff`, `CORP same-site`, `X-Frame-Options DENY`, `Referrer-Policy no-referrer`, and HSTS for 1 year with subdomains (`shared/middleware/security.py`).
- **Web and admin headers.** Set on every path through `next.config.mjs` → `packages/ui/security-headers.js`:
  - a CSP with `frame-ancestors 'none'`, `object-src 'none'` and `form-action 'self'`
  - HSTS for 1 year with subdomains, no preload
  - XFO, nosniff, Referrer-Policy, Permissions-Policy, COOP and CORP
  - S9 is the gap.

### File uploads

- **One handler.** All uploads go through `POST /api/v1/uploads` (`identity/api/v1/riders.py:69`).
  - Each purpose belongs to one role.
  - 5 MB limit; JPEG, PNG, WebP or PDF only (no SVG or HTML).
  - The server picks the key: `{purpose}/{user id}/{uuid}.{ext}`.
  - Production uses S3 (local disk is refused).
- **Attaching a key.** Rider documents, FSSAI and problem photos only take keys under your own id.
- **Public reads.** The public `menu-photo` read accepts only `menu_photo/<uuid>/<uuid>.<ext>`.
- **Private files.** They're read through `/uploads/view`, which checks the reviewer's permission in the owner's city or country.
- **Help centre.** Markdown text only; no uploads.
- **Gaps.** S13 and S17.

## Money out

| Path | Who can trigger it | Limits | Logged |
|---|---|---|---|
| Item refund `POST /payments/orders/{id}/refunds` | `refunds.issue` in the order's city: country manager, city ops, support agent, finance | Never more than what's left on the payment; per-item quantities can't be refunded twice. Support agents only: `support_refund_limit` per order (default ₹500 / $25) | A `refunds` row with `requested_by`, reason, fault and lines; `payment.refunded` outbox event; log line. No audit entry (S16) |
| Refund in full (cancellations, late payment) | System: order cancel flows and the unpaid-order sweep | What's left on the payment | Payment metadata `refunds[]`, outbox, log |
| Bulk refund `POST /incidents/refunds` | `refunds.bulk` in the city: country manager, city ops, finance | Up to 500 orders, a 7-day window, preview then `confirm: true`. A second admin (`refunds.approve`, not the requester) approves when any order is over `auto_refund_limit`, which is 0 if unset, so every bulk refund needs approval by default. S12: no cap on the total | Audit: `bulk_refund.requested`, `.approved`/`.rejected`, `.done`; per-order results |
| Payout run `POST /finance/payout-runs/{id}/approve` | `payouts.approve` in the country (finance) | Maker-checker: the approver can't be the run's creator. Runs can't overlap. Transfers have an idempotency key per statement and attempt. On QA, every payee must have an account | Audit: `payout_run.created`, `.approved`, `.retried`; `payout.paid` outbox per statement |
| Payout account link | finance for the country, or `partners.edit` for the kitchen's city; payees set up their own | Stripe Connect onboarding; the money goes to the payee's own verified account | Audit: `payout_account.link` |
| Platform offers and money rules (`POST /rules`, promotions) | `rules.edit`, then a second admin with `rules.approve` | Maker-checker: you can't approve a version you made or submitted (`rules/service/rules.py:223`) | Rule versions and approvals; audit |
| Kitchen-funded offers `POST /restaurants/{id}/offers` | The kitchen's owner | Live at once, funded by the kitchen, with a weekly cap. Percent off is at most 60%. S11: flat-off and cap have no ceiling | The rule and its version (`partner_offer_started`) |
| Commission tier change | `rules.edit`, then a second admin with `rules.approve` | Maker-checker | Audit: `restaurant.tier_change_requested`, `.tier_changed` |
| App store review $0.00 orders | Only a review account (listed in its review-only city's settings) ordering in that city | The quote is zeroed by one platform-funded line. The order is checked again before it's placed without payment (`orders/service/order.py:246`). It's never on a payout statement (`finance/service/payouts.py:106`). The review simulator (`REVIEW_SIM`) moves only such orders. The accounts and city are set only by `tools/review_accounts.py` (S6) | Log `review_order_placed_without_payment`; a `review` payment row |
| Wallet | Credited only by refunds of wallet payments (S3: top-up removed) | Debits lock the row and refuse an overdraw | `wallet_transactions` |

## Access sweep coverage

`backend/core_api/integration/test_zz_access_sweep.py` covers **all 275 core_api routes**: every route must have a policy, or the test fails.

**What it runs:**

- 210 protected routes are refused without a token.
- 100 admin routes are refused to an admin token made without the second step.
- 4 signed internal routes refuse user tokens.
- 799 wrong-role or someone-else's-resource cases are refused, including:
  - another customer's order, address, card, quote, chat and refunds
  - another kitchen's menu, hours, offers, payouts and statements
  - another rider's delivery and statement
  - another city's or country's admin
- 3 canaries prove the sweep catches planted holes.

**What changed this round:**

- **Real resources instead of made-up ids.** These five ids now point at real rows: a kitchen offer, a pending tier change, an ended Hyderabad ordering pause, a rejected Hyderabad bulk refund, and a chat message on the order.
  - Previously, a missing row answered 404 whatever the check did, so these entries proved nothing.
  - Another city's and another country's admins are now also checked on ending a pause, reading a bulk refund, and approving or rejecting one (6 new cases).
- **Kitchen id swaps.** A new test, `test_security_review.py::test_a_kitchen_cant_reach_another_kitchens_menu_or_offers_through_its_own_path`, has kitchen B put kitchen A's dish, option group and offer ids under its own restaurant's path. The policy table can't express this.
- `POST /wallet/topup` is removed (S3).

**Not in this sweep, and why:**

- **Public routes (65).** They're public by design, each with a reason in the table. The public kitchen pages also hide review-only cities (`test_review_accounts.py`).
- **realtime's 22 routes and the worker's 4.** These are other apps, with their own sweeps: `backend/realtime/tests/test_access_sweep.py` and `backend/worker/tests/integration/test_access_sweep.py`.
  - The WebSocket order channel allows only the customer, the assigned rider, the kitchen's owner or an admin for the city (`realtime/app/api/v1/delivery.py` `can_see`).
  - `/ws/rider` uses the token's own rider id.

## Secrets

**gitleaks, full history.** Command: `gitleaks detect --redact --log-opts="--all"`; 515 commits; repo config.

- **0 leaks.**
- `.gitleaksignore` holds 56 historical findings, all dead:
  - The 55 reviewed on 2026-11-12 ([docs/security/report.md](../security/report.md)):
    - 52 are expired dev-key test JWTs in `docs/load/summary-2026-11-12.json` (26 tokens, each found by two rules).
    - 2 are an HS256 Playwright login state, retired with HS256.
    - 1 is a `sk_test_placeholder` in an old `docker-compose.yml`.
  - 1 more: a `generic-api-key` match on a test fixture in `identity/tests/test_account.py`.

**The same scan without the path allowlist** (docs, `.env.example`, seed files):

- 4 hits, all placeholders:
  - 2 `private-key` in `.env.example`, which are `-----BEGIN … KEY-----\n...\n-----END` templates
  - 2 `stripe-access-token` in `docs/PROGRESS.md` and `docs/security/report.md`, which are the text `sk_test_placeholder`
- No real value.

**GitHub (names only).**

- Repository secrets: `RAILWAY_QA_TOKEN`.
- Repository variables: none.
- Deployment environments: `BhojanGo / QA` and `divine-nourishment / production` (Railway's deployments), each with no secrets or variables.
- CI never holds payment keys: the Stripe tests mock Stripe.

### Railway variables (names only)

Read from QA on 2026-11-20 through Railway's API by the lead agent; values were never printed. "secret" means secret by its name. The Stripe keys were sealed in R10; sealed status for the others wasn't checked. Railway's own `RAILWAY_*` variables are left out. Production doesn't exist yet; its planned list is in [production-config.md](production-config.md).

**core-api:**

- **Secrets:**
  - `ALERT_WEBHOOK_TOKEN`
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - `FAKE_PAYMENT_WEBHOOK_SECRET`
  - `INTERNAL_SERVICE_SECRET`
  - `JWT_PRIVATE_KEY`
  - `STRIPE_CONNECT_WEBHOOK_SECRET` (sealed)
  - `STRIPE_PAYOUTS_WEBHOOK_SECRET` (sealed)
  - `STRIPE_SECRET_KEY` (sealed, test mode)
  - `STRIPE_WEBHOOK_SECRET` (sealed)
- **References:** `DATABASE_URL`, `EVENT_BUS_REDIS_URL`, `REDIS_URL`.
- **Public by design:** `STRIPE_PUBLISHABLE_KEY`.
- **Others:**
  - `APP_ENV`, `AWS_ENDPOINT_URL`, `AWS_REGION`, `CLIENT_IP_HEADER`
  - `CORE_API_URL`, `CORS_ORIGINS`, `EMAIL_PROVIDER`, `EVENT_BUS`
  - `FAKE_PAYMENT_AUTO_COMPLETE_SECONDS`, `FAKE_PAYMENT_WEBHOOK_URL`, `GEOIP`, `JWKS_URL`
  - `LOG_FORMAT`, `PAYMENT_PROVIDER`, `PAYOUT_PROVIDER`, `PORT`
  - `PUBLIC_API_URL`, `PUBLIC_WEB_URL`, `PUSH_PROVIDER`, `ROUTING_PROVIDER`
  - `S3_ADDRESSING_STYLE`, `SERVICE_NAME`, `SMS_PROVIDER`, `STORAGE_PROVIDER`
  - `TAX_PROVIDER`, `UPLOADS_BUCKET`

**realtime:**

- **Secrets:** `INTERNAL_SERVICE_SECRET`.
- **References:** `DATABASE_URL`, `EVENT_BUS_REDIS_URL`, `REDIS_URL`.
- **Others:**
  - `APP_ENV`, `CLIENT_IP_HEADER`, `CORE_API_URL`, `CORS_ORIGINS`
  - `EMAIL_PROVIDER`, `EVENT_BUS`, `JWKS_URL`, `LOG_FORMAT`
  - `PAYMENT_PROVIDER`, `PAYOUT_PROVIDER`, `PORT`, `PUSH_PROVIDER`
  - `ROUTING_PROVIDER`, `SERVICE_NAME`, `SMS_PROVIDER`

**worker:** the same as realtime, plus `DB_POOL_SIZE`, `DEMO_RIDER_SIM` and `REALTIME_INTERNAL_URL`.

**web** (no secrets):

- `APP`, `APP_DIR`, `APP_ENV`, `CORE_API_INTERNAL_URL`, `CORE_API_URL`
- `NEXT_PUBLIC_APP_URL`, `NEXT_PUBLIC_CORE_URL`, `NEXT_PUBLIC_REALTIME_URL`, `PORT`, `REALTIME_URL`

**admin** (no secrets):

- `APP`, `APP_DIR`, `APP_ENV`, `CORE_API_URL`
- `NEXT_PUBLIC_CORE_URL`, `NEXT_PUBLIC_REALTIME_URL`, `PORT`, `REALTIME_URL`

**postgres:** `PGDATA`, `POSTGRES_DB`, `POSTGRES_PASSWORD` (secret), `POSTGRES_USER`. No TCP proxy (private). It has no volume backups; that's covered in the restore-drill PR #167.

**redis:** `REDISHOST`, `REDISPASSWORD` (reference), `REDISPORT`, `REDISUSER`, `REDIS_PASSWORD` (secret), `REDIS_URL` (reference).

**What this shows:**

- QA sets no `RAZORPAY_*` variable either, so S2's empty-secret webhook was reachable on QA too. QA payments are Stripe test mode, so no real money was at risk.
- QA's `INTERNAL_SERVICE_SECRET` is its own (not the local default), as S15 assumes.
- No `QUOTE_LIMIT_*` is needed; the defaults apply.
