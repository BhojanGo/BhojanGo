# Security review (Round 21; Medium findings fixed in Round 22)

**Date:** 2026-11-19. **Scope:** the website, the admin console, core_api, realtime and the worker (code and config), every way money leaves us, and secrets in the repo, GitHub and Railway.
**How:** we read the code, extended the access sweep, and ran gitleaks over the full history. Nothing was sent to QA or production and no live host was tested. The tests run in CI on a throwaway database.
**Earlier work:** the automated scans from 2026-11-12 (ZAP, semgrep, trivy, dependency audits) are in [docs/security/report.md](../security/report.md). This review doesn't repeat them.

Ranks:

- **High:** anyone with an ordinary account, or nobody at all, can get money, food or someone else's account.
- **Medium:** needs an insider, a second step, or a mistake by us, or the harm is bounded.
- **Low:** hardening.

Every High finding was fixed in R21, and the six Medium findings S8–S13 in R22 (PR #176, [Round 22](#round-22-the-medium-findings-s8s13)). Each fix has a test that fails without it.

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
| S8 | Medium | Web, admin | Access and refresh tokens are kept in localStorage, so any XSS takes over the account. | Fixed in R22 (#176) |
| S9 | Medium | Headers | The CSP allows `script-src 'unsafe-inline'` in production, so it doesn't stop injected inline script. | Fixed in R22 (#176) |
| S10 | Medium | Realtime | A WebSocket's token is checked only when it connects. A socket outlives the token's 15 minutes, a sign-out and a removed role. There's no per-user cap on sockets. | Fixed in R22 (#176) |
| S11 | Medium | Money out (offers) | A kitchen's own offer has no ceiling on `flat_off` or `weekly_cap`. A kitchen working with a customer can push its statement below zero, and we carry the loss. | Fixed in R22 (#176); carrying a negative statement: R23 |
| S12 | Medium | Money out (bulk refunds) | A bulk refund runs with no second admin when every order is under `auto_refund_limit`. The batch total isn't capped (up to 500 orders × the limit). | Fixed in R22 (#176) |
| S13 | Medium | Uploads, menus | `image_url`, `logo_url` and `cover_url` accept any string, including outside hosts and `javascript:`, and customers are shown them. | Fixed in R22 (#176) |
| S14 | Low | Web | Open redirect after sign-in: `?next=/<tab>/evil.com` got past `safeNext`. | Fixed in this PR |
| S15 | Low | Internal endpoints | The default `INTERNAL_SERVICE_SECRET` was refused only when `APP_ENV=production`, not when only Railway's environment name says production. | Fixed in this PR |
| S16 | Low | Audit | Item refunds and kitchen approve/reject write a row and a log line, but no audit-log entry. | Plan |
| S17 | Low | Uploads | The type check trusts the client's Content-Type (no magic bytes). PDFs open inline for admins. There's no per-user upload quota. | Plan |
| S18 | Low | Rate limits | Per-IP limits are in process memory (slowapi), so they reset on every deploy. That's fine with one process; it won't be after scaling out. | Plan |
| S19 | Low | CORS | `CORS_ORIGINS` isn't checked in production. The default is localhost, and `*` would be accepted alongside credentials. | Plan |
| S20 | Low | Realtime | The WebSocket token can go in `?token=`, which ends up in proxy logs. Internal signatures can be replayed for 5 minutes, but those endpoints are idempotent. | Plan |

## Fixes in Round 21

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

## Round 22: the Medium findings (S8–S13)

**Date:** 2026-11-20. **PR:** #176.

**How each fix was proven:**
- The throwaway branch `check/r22-security` carried a workflow that ran on push (`.github/workflows/check-r22.yml`, only on that branch).
- For each finding, it put the fix's files back as they are on `dev`, deleted the fix's new files, kept the tests, and ran that finding's tests.
- A job passed only if the tests **failed**: pytest or `node --test` exited with 1, meaning failed assertions, not a collection error.
- That covers the unit tests for every finding and the integration tests (Postgres, migrated and seeded) for S8, S11, S12 and S13.
- Run: [44709803664](https://github.com/BhojanGo/BhojanGo/actions/runs/44709803664), all 11 jobs proven, on the final tests. An earlier run on the first version of the tests, [44708549960](https://github.com/BhojanGo/BhojanGo/actions/runs/44708549960), was also all proven. The branch was deleted afterwards.
- With the fixes, the same tests pass in the PR's CI.
- Tests that only guard against regressions pass both with and without the fix: the apps' bearer sign-in, the customer keeping their socket, our own photo addresses still being accepted, and good percent offers.

### S8: sessions in httpOnly cookies, with CSRF protection (website and admin)

**Which hosts talk to which:**
- The website (`qa.bhojango.com`, later `bhojango.com`) calls core_api directly at `api.qa.bhojango.com` / `api.bhojango.com`. That's another origin but the same site (same registrable domain).
- The console (`admin.*`) calls core_api through its own Next `/api/*` rewrites, so from the browser it's same-origin.
- Live tracking opens a WebSocket to `rt.*`.

**Design (`backend/shared/session.py`):**
- **Who sets the cookies.** core_api does. When a browser client names itself with `X-Session: web` or `X-Session: admin`, every answer that issues tokens has its `access_token` and `refresh_token` replaced with `""` and comes with two cookies:
  - `bg_<client>_at`, the access token;
  - `bg_<client>_rt`, the refresh token.
  - This covers sign-in, the second step, refresh, sign-up, a password change, kitchen and rider applications, and social sign-in.
- **The cookies:**
  - Both are `HttpOnly; Secure; SameSite=Lax; Path=/`, with no `Domain`, so they belong only to the host that set it.
  - The website's cookies live on the API's host; the console's live on the console's host, through the rewrite.
  - Both last as long as the refresh token (7 days). The access JWT inside still expires after 15 minutes: the browser keeps sending it, the API answers 401, and the page refreshes.
  - The names differ so the website and the console don't overwrite each other on `localhost`, where ports share cookies.
- **Using a cookie:**
  - With no `Authorization` header, `BearerAuth` (used by core_api, realtime and the worker) reads the cookie.
  - A change (anything but GET, HEAD and OPTIONS) uses a cookie only with `X-Session`, and only from one of our origins: `Origin`, else `Referer`, must be in `CORS_ORIGINS`. Otherwise it gets 403 `CSRF`.
  - `X-Session` is a custom header, so another site's page can't send it without a CORS preflight, which only our origins pass. That's the "custom header + Origin check" defence. No double-submit token is needed, and the website couldn't read one anyway, because it's on the API's host.
  - A read (GET or HEAD) may use the website's cookie without the header. This keeps the website's reads free of a CORS preflight each.
  - A read is safe without the header because it changes nothing, another site can't read the answer (CORS), and `SameSite=Lax` keeps the cookie off other sites' images, scripts and frames.
- **The refresh token** comes from the cookie when the body has none (`POST /auth/refresh`). A failed refresh and a sign-out clear both cookies.
- **WebSockets:** the browser can't send the API host's cookie to `rt.*`. The website asks core_api for a socket ticket and opens the socket with it:
  - `POST /auth/socket-ticket` returns a JWT of type `ws` with the same person and rights as the session, which expires when the session's access token does.
  - Only the WebSockets accept it (`decode_socket_token`). Every HTTP route still requires `type: access`, so a ticket opens nothing else.
  - The ticket goes in `?token=`, as before (S20).
- **The apps** never send `X-Session`. They get tokens in the body and send `Authorization: Bearer` as before, kept in secure storage.
- **The pages:**
  - The website's session store (`apps/web/src/lib/client.ts`) and the console's (`apps/admin/src/store/auth.ts`) now keep only who is signed in.
  - Old `bhojango-session` and `bhojango-admin-auth` entries, which held tokens, are deleted when the page loads.
  - A refresh runs one at a time, because a refresh token works once and a second use ends the session.

**Decisions made for Srini (safest sensible default):**
- **No session shared across subdomains.** Every cookie is host-only, so signing in on the website doesn't sign you in to the console, and the other way round.
- **The website and core_api must share a registrable domain.** That's true for QA (`*.qa.bhojango.com`) and production (`*.bhojango.com`).
- **The old QA origins** (`*.up.railway.app`, allowed until 2026-11-26) behave differently by app:
  - On the old website origin, the API's answer is cross-site, so browsers neither store nor send the `SameSite=Lax` cookies. Signing in seems to work, but the next call is signed out. Use `qa.bhojango.com`.
  - The old console origin still works, because its cookies come through its own rewrites.
- **`CORS_ORIGINS` must list the console's origin too**, since it's now also the CSRF list. QA's already does, and so does production's plan: "the custom web and admin domains".
- **Local runs:** `Secure` cookies work on `http://localhost` in Chromium and Firefox, which treat localhost as secure.

**Tests:**
- `core_api/tests/test_session_cookies.py`, unit, with the real middleware and `BearerAuth`:
  - httpOnly, Secure, Lax cookies and no tokens for a browser;
  - the apps still get tokens;
  - a cookie counts only for its client;
  - a change needs our origin, while a bearer token needs none;
  - an expired session gets a 401;
  - sign-out clears the cookies.
- `integration/test_security_review_r22.py`, on a real database:
  - `test_the_website_session_is_in_httponly_cookies_not_the_page`: email sign-in, `/users/me` from the cookie, a change from another origin or with no origin refused, a socket ticket refused by `/users/me` and `/orders`, refresh from the cookie, then sign-out clears the cookies and ends the session.
  - `test_the_console_signs_in_with_its_second_step_into_cookies`: password, then the TOTP step, then cookies; `/admin/me` works from the console's cookie and not under the website's name.
  - `test_the_apps_sign_in_is_unchanged`.
- `apps/web/test/session.test.ts` and `apps/admin/test/session.test.ts`: no token in either store, the cookie session on every call, and no page sending a bearer token.
- Playwright (`tools/web/e2e_web.py`, `tools/admin/e2e_admin.py`): after a real sign-in, which includes the console's TOTP step:
  - no JWT is in `localStorage` or `sessionStorage`;
  - `bg_web_at` / `bg_admin_at` is httpOnly and Lax;
  - `document.cookie` can't see it.
- **Proven:** the unit job reverted `shared/auth.py`, `core_api/main.py`, `identity/api/v1/auth.py` and `identity/schemas/user.py`, and deleted `shared/session.py`. The website and console job reverted their session files. Both integration tests failed on the old code: tokens were handed to the page.

**What users notice:** everyone on the website and the console is signed out once, because the old sessions were in localStorage. After that, nothing changes.

### S9: a nonce-based CSP

**Fix:**
- `packages/ui/security-headers.js` now has `contentSecurityPolicy(options, nonce)`. Each app's `src/proxy.ts` (Next 16 middleware) makes a fresh nonce for every page and sends:
  - `script-src 'self' 'nonce-…' 'strict-dynamic'`, plus the old host list as the fallback for browsers without `'strict-dynamic'`;
  - no `'unsafe-inline'`;
  - `'unsafe-eval'` only in development.
- **How the nonce reaches the scripts:** Next reads the nonce from the request's CSP header and puts it on its own scripts. Our scripts load Stripe.js, Razorpay's checkout and Google sign-in, which `'strict-dynamic'` allows.
- **Every page is rendered per request, so each gets its own nonce:**
  - The website's root layout already reads the request.
  - The console's layout now does too (`await headers()`).
- `next.config` keeps every other header.
- **JSON-LD:** it's data, never run, and S1's escaping still keeps it from closing its tag.
- **Paths the proxy doesn't see** (`/_next/` assets, food photos, icons, robots, sitemap; the console's `/api/` rewrites) have no CSP. None of them is an HTML page.

**Tests:**
- `packages/ui/test/security-headers.test.js`:
  - a page's `script-src` has its nonce and `'strict-dynamic'` and never `'unsafe-inline'`;
  - without a nonce, scripts come only from our own origin;
  - no fixed header allows inline script;
  - nonces are new each time and 16 bytes or more;
  - both apps' proxies set the CSP on the request and the response.
- Playwright checks a page's CSP has a nonce, has no `'unsafe-inline'` script and differs on every load. The suites' pages, checkout and Google sign-in included, run under it.
- **Proven:** reverting `security-headers.js` and deleting both proxies fails all five.

### S10: WebSocket token expiry, rider changes and caps

**Fix** (`backend/realtime/app/core/sockets.py`, `api/v1/websocket.py`, `api/v1/riders.py`):
- **Expiry:** each socket keeps its token's `exp` and closes with **4401** at that moment. That applies to `/ws/track/{order}` and `/ws/rider`.
- **Rider changes:** after a `rider_assigned`, `searching_rider` or `status_change` message on an order, realtime checks `can_see` again (the order's dispatch info, at most 5 s old) before forwarding anything. A rider taken off the order is closed with **4403** and never gets the next message.
- **Caps:** each process allows at most `WS_MAX_PER_USER` sockets per account (5) and `WS_MAX_PER_IP` per address (100, because carrier NAT puts many phones behind one address). One more is refused with **4429**.
  - 0 turns a cap off: the load test's stack does, since one generator holds every socket.
  - The counts are per process; there's one realtime process today.
- **Clients:**
  - The website's `liveSocket`, and the new `liveSocket` in `packages/mobile-core`, which the customer's order screen, chat and the rider app now use, reopen a socket when it closes.
  - After 4401 they reopen at once with a fresh ticket or token. The apps refresh their token first, one refresh at a time.
  - They don't reopen after 4004, 4403 or 4429.
  - Before, the customer app's tracking and chat sockets didn't reconnect at all.

**Tests:** `realtime/tests/test_socket_limits.py`, with Starlette's test client, fake Redis and a fake order:
- tracking and rider sockets close with 4401 when a 2-second token expires;
- a rider taken off the order gets 4403;
- the customer keeps watching through the same change;
- the third socket for one account and the second for one address are refused with 4429;
- a socket ticket opens a socket, while realtime's HTTP route refuses it with 401.
- A socket that stays open fails the test by timing out (a daemon thread does the read), so a missing fix can't hang the run.

**Proven:** with `websocket.py`, `riders.py`, `core/auth.py` and `shared/auth.py` reverted and `sockets.py` deleted, 6 of 7 fail. The one that passes is "the customer keeps watching". This was run locally, then in the proof run.

**What users notice:** a tracking or rider socket reconnects every 15 minutes, which nobody sees. A 6th open socket on one account is refused.

### S11: a ceiling on kitchen-funded offers

**Fix:**
- **The setting:** a new Markets setting, `kitchen_offer_ceiling`, in the country's currency:
  - `flat_off`: the most a flat offer takes off one order;
  - `max_discount`: the most a percent offer takes off one order;
  - `weekly_cap`: the most all of a kitchen's offers together may give in a week.
- **Inheritance:** the setting is inherited country → state → city one key at a time (`effective_settings`), so a city that sets only `flat_off` keeps the country's `weekly_cap`.
- **Editing:** the admin Markets country and city pages have a "Kitchen offer ceiling" section. The API checks every save: only those keys, amounts above 0, and `null` resets to the inherited value (`markets/service/offer_ceiling.py`).
- **Enforcement:** `POST /restaurants/{id}/offers` answers 422 `OFFER_OVER_CEILING` when:
  - a flat amount is over the ceiling;
  - a percent offer's maximum is over the ceiling;
  - the new weekly cap plus the caps of the kitchen's other offers that haven't ended (paused ones included) is over the weekly ceiling.
  - A percent offer without a maximum gets the market's maximum, because the partner app sends none.
- **When nothing is set**, defaults in code apply: ₹200 / ₹200 / ₹25,000 and $15 / $15 / $1,500. A currency with neither a default nor a setting refuses kitchen offers until an admin sets one. The seed gives India and the US those values.

**Carrying a negative statement into next week: done in R23** (below). Before R23:
- Today `pay_pending` (`finance/service/payouts.py`) marks a statement at or below zero as paid ("nothing to send"), so a negative balance is written off.
- Carrying it is a cross-cutting finance change:
  - a statement state that run checks treat as settled;
  - a "carried from last week" line picked up by the next run;
  - statements for payees with no orders that week;
  - changes to the partner app's, admin's and PDF statements and to the finance invariants.
- So it isn't in this PR. Until then the ceiling limits the loss to a kitchen's `weekly_cap` per week.

**Tests:**
- `markets/tests/test_offer_ceiling.py` (7 unit tests): a well-formed save, inheritance key by key, refusing over the ceiling, the percent maximum, the combined weekly ceiling, no ceiling meaning refused, and saves being checked.
- Integration:
  - `test_a_kitchen_offer_above_its_markets_ceiling_is_refused`: a city override, then a refusal;
  - `test_more_offers_dont_get_past_the_weekly_ceiling`.
- The admin Playwright run sets Hyderabad's ceiling in the console, checks the API refuses a ₹180 offer, screenshots the section and resets it.
- **Proven:** with `markets.py` and `partner.py` reverted and `offer_ceiling.py` deleted, the unit and integration tests fail.

**Screenshot:** `08a-markets-offer-ceiling.png` in the PR's Playwright artifact `e2e-screenshots` (run [44711139194](https://github.com/BhojanGo/BhojanGo/actions/runs/44711139194), artifact 14617968066; kept 7 days).

### S11 in R23: a negative kitchen statement is carried, never written off

- **Carry:** a kitchen statement whose amount is below zero pays nothing and is marked `carried`
  (it was `paid`, "nothing to send", which wrote the balance off). The next payout run puts it on the
  kitchen's next statement as "Carried from last week" (`payout_statements.carried_in`, minor units,
  `summary.carried_from_last_week`) and nets it into that week's amount, so the week's sales cover it
  first. Still below zero: carried again. A kitchen with a balance and no orders gets a statement with
  only the carry (`payouts.create_run`, `statements.balance`).
- **Once only:** the source statement records `carried_to` (an update that only takes statements no run
  has carried, under `FOR UPDATE`), and a week can't be prepared twice; the run, retry and the payout
  day never send a statement below zero.
- **Never charged:** nothing creates a charge or a negative transfer. `negative_weeks` counts the weeks
  below zero in a row (`negative_since` the first Monday); from 4, admin Finance lists the kitchen under
  "Kitchens to collect from" (`GET /finance/to-collect`), and finance collects by arrangement.
- **Money adds up:** Reconciliation shows "Kitchens: carried from last week", "carried to next week" and
  "Kitchens are paid": paid = owed + carried in - carried on. The finance invariant test adds a carried
  balance to every week it checks and asserts the run, Reconciliation (before and after the run) and the
  statements agree on it.
- **Tests:** `finance/tests/test_carry.py` (8 unit tests), `integration/test_negative_statements.py`
  (carried and covered; still below zero after 4 weeks, flagged, then covered in part),
  `integration/test_finance_invariants.py`.
- Statements written off before R23 (amount below zero, `paid`) are left as they were.

### S12: a cap on a bulk refund's total for the automatic path

**Fix:**
- The `auto_refund_limit` business rule gets an optional `max_bulk_total`. When it's unset, the cap is 50 × `max_per_order`.
- A bulk refund now needs a second admin (`pending_approval`) when any order is over the per-order limit **or** the batch total is over the cap. `approval_reasons` returns `order_over_limit`, `total_over_limit` or both.
- The admin's preview says which ("above X per order" / "above Y in all"), and the rule's wording mentions the total.

**Tests:**
- `incidents/tests/test_bulk_refund_cap.py` (5 unit tests).
- Integration `test_many_small_refunds_over_the_total_need_a_second_admin`: two small refunds over a lowered total are left pending, where on the old code they ran to "done".
- **Proven:** with `incidents/service/__init__.py` and `rules/service/templates.py` reverted, both fail.

**What admins notice:** a large batch of small refunds now waits for a second admin.

### S13: photo addresses

**Fix:** `catalog/service/photo_urls.check` accepts only these values for `image_url`, `logo_url` and `cover_url`:
- None or `""`;
- our upload path, `/api/v1/uploads/menu-photo/<owner uuid>/<uuid>.(jpg|png|webp)`. It can be relative, or absolute on `PUBLIC_API_URL`'s exact origin; outside production, http on localhost and the emulator's host also count;
- the food library, `/food/<slug>-<width>.webp`;
- https on `AWS_CLOUDFRONT_URL`'s host or the new `PHOTO_HOSTS` list, with no port, user info, query or fragment.

It also refuses anything over 512 characters, spaces and control characters.

**Ownership:** `PUT /restaurants/{id}` and `PUT …/menu-items/{id}` also require the upload to belong to the caller or to the kitchen's owner (422 `PHOTO_URL`).

**Cleanup script:** `backend/tools/clean_photo_urls.py` lists the existing rows that fail the same check, and sets them to NULL only with `--apply`.
- It's a dry run by default.
- It refuses QA and production unless given `--i-mean-this-environment`.
- It has not been run against QA or production. Run it on each once, dry run first.

**Tests:**
- `catalog/tests/test_photo_urls.py`: refusals for `javascript:`, outside hosts, other accounts' uploads, overlong values and http photo hosts; acceptances for our own photos; and the script finding what the API refuses.
- Integration `test_a_kitchen_cant_show_a_photo_from_another_site_or_account`.
- **Proven:** with `schemas/restaurant.py` and `api/v1/restaurants.py` reverted and `photo_urls.py` and the script deleted, they fail.

**What kitchens notice:** a photo must be uploaded through the app to our own API host. A photo saved under an old API host, such as an old `*.up.railway.app` QA one, is refused if it's saved again, and the cleanup script lists it.

**Production needs:** `PUBLIC_API_URL` set to the API's real address. Photos served from a CDN also need `PHOTO_HOSTS` or `AWS_CLOUDFRONT_URL`.

## Plans for the Medium findings (R21; all done in R22)

These were the R21 plans. Round 22 did all six (above), except carrying a negative statement into the next week (S11), which Round 23 did (below, "S11 in R23").

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

- **CORS.** core_api, realtime and the worker allow only `CORS_ORIGINS`, with credentials (`core_api/main.py`, `realtime/app/main.py`). Since R22 (S8) the website and the console authenticate with httpOnly session cookies. A change made with a cookie needs the `X-Session` header and an `Origin` in `CORS_ORIGINS`, so `CORS_ORIGINS` is also the CSRF list. The apps still use bearer tokens. See S19.
- **API headers.** `nosniff`, `CORP same-site`, `X-Frame-Options DENY`, `Referrer-Policy no-referrer`, and HSTS for 1 year with subdomains (`shared/middleware/security.py`).
- **Web and admin headers.** Set on every path through `next.config.mjs` → `packages/ui/security-headers.js`:
  - a CSP with `frame-ancestors 'none'`, `object-src 'none'` and `form-action 'self'`
  - HSTS for 1 year with subdomains, no preload
  - XFO, nosniff, Referrer-Policy, Permissions-Policy, COOP and CORP
  - Since R22 (S9) the CSP comes from each app's `src/proxy.ts`, with a fresh nonce per page and no `'unsafe-inline'` script.

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
- **Photo addresses.** Since R22 (S13), a dish, cover or logo photo can only be our own upload (the caller's or the kitchen owner's), the food library or our photo host.
- **Gaps.** S17.

## Money out

| Path | Who can trigger it | Limits | Logged |
|---|---|---|---|
| Item refund `POST /payments/orders/{id}/refunds` | `refunds.issue` in the order's city: country manager, city ops, support agent, finance | Never more than what's left on the payment; per-item quantities can't be refunded twice. Support agents only: `support_refund_limit` per order (default ₹500 / $25) | A `refunds` row with `requested_by`, reason, fault and lines; `payment.refunded` outbox event; log line. No audit entry (S16) |
| Refund in full (cancellations, late payment) | System: order cancel flows and the unpaid-order sweep | What's left on the payment | Payment metadata `refunds[]`, outbox, log |
| Bulk refund `POST /incidents/refunds` | `refunds.bulk` in the city: country manager, city ops, finance | Up to 500 orders, a 7-day window, preview then `confirm: true`. A second admin (`refunds.approve`, not the requester) approves when any order is over `auto_refund_limit` (0 if unset, so every bulk refund needs approval by default) or the total is over `max_bulk_total` (default 50 × the per-order limit; S12, R22) | Audit: `bulk_refund.requested`, `.approved`/`.rejected`, `.done`; per-order results |
| Payout run `POST /finance/payout-runs/{id}/approve` | `payouts.approve` in the country (finance) | Maker-checker: the approver can't be the run's creator. Runs can't overlap. Transfers have an idempotency key per statement and attempt. On QA, every payee must have an account | Audit: `payout_run.created`, `.approved`, `.retried`; `payout.paid` outbox per statement |
| Payout account link | finance for the country, or `partners.edit` for the kitchen's city; payees set up their own | Stripe Connect onboarding; the money goes to the payee's own verified account | Audit: `payout_account.link` |
| Platform offers and money rules (`POST /rules`, promotions) | `rules.edit`, then a second admin with `rules.approve` | Maker-checker: you can't approve a version you made or submitted (`rules/service/rules.py:223`) | Rule versions and approvals; audit |
| Kitchen-funded offers `POST /restaurants/{id}/offers` | The kitchen's owner | Live at once, funded by the kitchen, with a weekly cap. Percent off is at most 60%. Since R22 (S11), the market's `kitchen_offer_ceiling` (Markets, country → state → city) caps the amount off, a percent offer's maximum, and the kitchen's weekly caps together | The rule and its version (`partner_offer_started`) |
| Commission tier change | `rules.edit`, then a second admin with `rules.approve` | Maker-checker | Audit: `restaurant.tier_change_requested`, `.tier_changed` |
| App store review $0.00 orders | Only a review account (listed in its review-only city's settings) ordering in that city | The quote is zeroed by one platform-funded line. The order is checked again before it's placed without payment (`orders/service/order.py:246`). It's never on a payout statement (`finance/service/payouts.py:106`). The review simulator (`REVIEW_SIM`) moves only such orders. The accounts and city are set only by `tools/review_accounts.py` (S6) | Log `review_order_placed_without_payment`; a `review` payment row |
| Wallet | Credited only by refunds of wallet payments (S3: top-up removed) | Debits lock the row and refuse an overdraw | `wallet_transactions` |

## Access sweep coverage

`backend/core_api/integration/test_zz_access_sweep.py` covers **all 275 core_api routes**: every route must have a policy, or the test fails. (R21's count. R22 adds `POST /auth/socket-ticket`, a signed-in user's own route, with its policy.)

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
