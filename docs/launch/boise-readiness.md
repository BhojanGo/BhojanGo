# Boise launch readiness

Where BhojanGo stands before the first real order in Boise, Idaho (round 38, 2026-11-24). The US business is
DeepTrics LLC; commission is 15%. Production does not exist yet: everything marked READY is built and tested in CI
and on QA (Railway), and waits only for an account, a decision or a payment. (This replaces the round 23 checklist;
its costs are carried into "What must be paid for at launch".)

**Marks:** **READY**: built and tested; nothing left but switching it on. **GAP**: missing or partial, but it doesn't
stop the first order (or has a workaround). **BLOCKER**: no real Boise order can go through until it's done.

## Payments

| Item | Mark | Evidence |
|---|---|---|
| Stripe live mode | BLOCKER | Test mode passes 9/9 (`tools/stripe_e2e`, CI job "Payments e2e (Stripe test mode)"); DeepTrics LLC's live account isn't activated, so there are no live keys (`STRIPE_SECRET_KEY` "not set" in [production-config.md](production-config.md)). |
| Stripe Connect payouts to restaurants and delivery partners | READY | Express onboarding and payout runs through Connect (`backend/core_api/integration/test_connect_payouts.py`, `test_payout_providers.py`); needs live mode above. |
| Payout schedule | READY | Weekly, Monday to Sunday in the payout time zone (admin Markets ▸ Payout provider; `finance/service/payouts.py`; `test_payouts.py::test_payout_run_end_to_end`). |
| Refunds | READY | Full, per item and per amount, with limits per role (`payments/service/refunds.py`, `test_payments_refunds.py`); a BhojanGo-funded offer's cost goes back to its budget (R38, `test_r38_offer_returns.py`). |
| Disputes (chargebacks) | GAP | No `charge.dispute.*` webhook handling in `payments/`: a dispute would only show in the Stripe dashboard. Needs a handler that flags the order and holds the restaurant's share. |

## Tax

| Item | Mark | Evidence |
|---|---|---|
| Idaho seller's permit / marketplace facilitator registration | BLOCKER | Not registered; BhojanGo collects and remits Idaho sales tax as the marketplace facilitator. The permit is free. |
| Stripe Tax live configuration | BLOCKER | The engine asks Stripe Tax for every US bill (`tax:external` rule, `pricing/service/quotes.py` `_with_tax`) with Idaho's taxable lines (R33, `test_tax.py`); the Idaho registration in Stripe Tax can only be added after the permit, in live mode. |

## Routing

| Item | Mark | Evidence |
|---|---|---|
| OSRM in production | READY | `ROUTING_PROVIDER=osrm`, `OSRM_URL=http://osrm.railway.internal:5000` in [production-config.md](production-config.md) (R32); the same service runs on QA. |
| Fallback alerting | READY | When OSRM doesn't answer, prices use straight-line distance x the road factor and an ops alert fires above the threshold (`pricing/service/routing_stats.py` `raise_alert`, R32). |

## Delivery partners

| Item | Mark | Evidence |
|---|---|---|
| Sign-up | READY | Website "Deliver with BhojanGo" and the app (`/riders/apply`, `test_signup.py` `test_rider_signs_up_and_lands_in_onboarding`; Maestro rider `signup`, `onboarding`). |
| Identity and background check | BLOCKER | Onboarding asks for a `background_check` document (`markets/service/delivery.py`), but no check vendor is connected (Checkr, Certn or Sterling): an admin can only look at an upload. |
| Driving record (MVR) | BLOCKER | A driving licence upload only (`driving_licence`); no motor vehicle record check through a vendor. Comes with the background-check vendor. |
| Vehicle insurance proof | READY | `vehicle_insurance` document, reviewed in admin Partners ▸ Delivery partner documents (`test_deliver.py`). |
| 1099 tax information | GAP | Stripe Connect collects payees' tax details and can file 1099-NEC/1099-K (about $3 federal + $1.50 state per form a year), but it isn't switched on, and nothing in our code checks a payee's tax info is complete before paying. |
| SOS | READY | In-app SOS with the location to ops (Maestro rider `sos`, 10/10 in R34). |

## Restaurants

| Item | Mark | Evidence |
|---|---|---|
| Onboarding | READY | "Add your restaurant" (`/kitchens/apply`, `test_signup.py` `test_kitchen_applies_and_waits_for_approval`), documents per country, admin approval. |
| Menu setup | READY | Restaurant app menu editor and photos (Maestro partner `menu`; `catalog` tests). |
| Tablet app | READY | Orders, accept and ready, pause, pickup (Maestro partner `orders`, `pickup`). Tablets aren't bought ($150-250 each). |
| Payout statements | READY | Weekly statements; a negative week is carried, never written off (R23; `finance` tests; restaurant app Payouts). |
| Sign-up terms (restaurant agreement) | BLOCKER | Sign-up accepts the general Terms only (`tools/seed/legal/US-terms.md`); there is no restaurant agreement (commission, payouts, food-safety duties). Needs a lawyer. |

## Customers

| Item | Mark | Evidence |
|---|---|---|
| Sign-up | READY | Phone (Twilio Verify in production), email, Google optional; US numbers checked and shown the US way (R38: `backend/shared/phone.py`, `packages/i18n/phone.js`). |
| Support chat | READY | Live chat and call-back requests to ops (Maestro `messages`; "Live chat check x50" in CI). Who answers and when isn't decided (see Operations). |
| Refunds | READY | Problem reports refund automatically up to the city's limit, else a ticket (`test_report_problem.py`, `test_support_tickets.py`). |
| Accessibility basics | READY | axe checks on every page in the Playwright runs (`tools/a11y`): no serious or critical issues; font sizes and contrast checked (R9 onwards). |

## Legal

| Item | Mark | Evidence |
|---|---|---|
| US Terms | BLOCKER | `tools/seed/legal/US-terms.md` is a draft with placeholders; a US lawyer must review it. |
| US Privacy policy | BLOCKER | `tools/seed/legal/US-privacy.md`, a draft; same review. |
| Delivery partner agreement | BLOCKER | Doesn't exist (only the general Terms): independent-contractor terms, insurance duties and pay. |
| Restaurant agreement | BLOCKER | Doesn't exist (see Restaurants). |
| Food safety | GAP | A restaurant's food-safety permit isn't a required US document (India has FSSAI); Idaho's health-district permit number should be collected at onboarding. |
| Alcohol is off | READY | "Alcohol, tobacco and other age-restricted products are not sold on BhojanGo" (`US-terms.md` line 70); the catalog has no age-restricted category or age check, so nothing can be sold as alcohol. |

## Operations

| Item | Mark | Evidence |
|---|---|---|
| Admin roles | READY | Super admin, country manager, city ops, finance, support, viewer, scoped by market (`shared/authz.py`; `test_zz_access_sweep.py` checks every route). |
| Incidents | READY | Pause a restaurant, a city, a country or everywhere; bulk refunds and messages (`test_incident_tools.py`; [incident-plan.md](incident-plan.md)). |
| Monitoring and alerts | GAP | Sentry is wired in every service and app but off (`SENTRY_DSN` not set); Prometheus alert rules exist (`make ci-observe`); no paging channel. |
| Backups | READY | Daily and weekly volume backups and an hourly copy to its own bucket on QA; restore drill passed (R23, [incident-plan.md](incident-plan.md#database-restore)); production repeats it at go-live. |
| On-call | BLOCKER | Nobody is on call: [incident-plan.md](incident-plan.md) names "a Claude Code session started by Srini; later an on-call engineer", and the phone numbers aren't filled in. |

## Infrastructure: what must be paid for at launch

Under the zero-spend rule nothing is paid today (QA on Railway is the one exception). Production needs these
(rough monthly estimates; check with each vendor before buying):

| What | Why | Estimate |
|---|---|---|
| Railway Pro (production) | app servers, database, Redis, OSRM, backups | about $37 a month at launch, $58 in a busy month ([load-test.md](load-test.md#what-production-costs-on-railway-r22)) |
| Domain | website, admin and API addresses, TLS | $10-20 a year (about $1-2 a month) |
| Twilio Verify | sign-in codes by SMS | about $0.05 a code: about $25 a month at 500 sign-ins |
| Amazon SES | emails | about $0.10 per 1,000 emails: under $1 a month |
| Stripe | card payments, Connect payouts, Stripe Tax | per use: 2.9% + $0.30 a card payment; $2 a month per active payee + 0.25% + $0.25 a payout; Stripe Tax 0.5% a transaction |
| Apple Developer Program | iOS apps | $99 a year (about $8 a month) |
| Google Play Console | Android apps | $25 once |
| Background checks and MVR | delivery partner checks | per check: about $30-40 background, $5-15 MVR |
| Business insurance | general liability, delivery auto cover | about $140-425 a month (quotes vary widely) |
| Sentry | error tracking | $0 on the free tier ($26 a month on Team) |
| Map tiles | the live tracking map | $0 (OpenFreeMap, `apps/web/src/app/orders/[id]/track/LiveMap.tsx`) |

Before the first order there are also one-off costs: a US lawyer for the Terms, Privacy and the two agreements
($1,500-5,000) and a tablet per restaurant ($150-250 each). The monthly total is about $200-550, most of it
insurance, plus per-order payment fees.

## App stores

| Item | Mark | Evidence |
|---|---|---|
| iOS and Android builds | GAP | `eas.json` in all three apps; development builds run on emulators (Maestro); no store builds yet, because there are no store accounts. |
| Store listings | READY | Text, privacy answers, permissions and screenshot sizes in [store/](store/README.md) (customer, restaurant, delivery). |
| Review requirements | READY | In-app account deletion, location disclosure, privacy links, chat report and block, reviewer accounts in a review-only city (R19-R21); [store/play-location-declaration.md](store/play-location-declaration.md). |
| Apple and Google developer accounts | BLOCKER | Not opened (Apple needs a D-U-N-S number for DeepTrics LLC). |

## Top 10 blockers, in order

1. **Stripe live mode for DeepTrics LLC** (business details, bank account, live webhooks): no money moves without it. *Needs Srini.*
2. **Idaho seller's permit, then Stripe Tax's Idaho registration**: no taxed US bill can be charged. *Needs Srini* (then Claude Code can do the Stripe Tax switch and the live checks).
3. **US legal documents reviewed by a lawyer**: Terms, Privacy, and new delivery partner and restaurant agreements. *Needs Srini* (then Claude Code can do the publishing in admin and the acceptance in both sign-ups).
4. **Background check and MVR vendor** (Checkr, Certn or Sterling): pick it and open the account. *Needs Srini*; then *Claude Code can do* the integration into delivery-partner onboarding.
5. **Business insurance** (general liability and delivery auto cover). *Needs Srini.*
6. **Production on Railway**: the domain and the 12 secrets from Srini's accounts. *Needs Srini*; then *Claude Code can do* the environment, DNS, TLS, backups and the restore rehearsal ([go-live.md](go-live.md)).
7. **On-call and support hours**: who answers chat, call-backs and incidents, with phone numbers in [incident-plan.md](incident-plan.md). *Needs Srini.*
8. **Apple and Google developer accounts** (a D-U-N-S number for Apple), then store builds and submission. *Needs Srini* for the accounts; *Claude Code can do* the builds and submissions.
9. **Chargeback (dispute) handling**: a webhook that flags the order, holds the restaurant's share and tells ops. *Claude Code can do.*
10. **Monitoring switched on**: Sentry DSNs and a paging channel for the alert rules. *Needs Srini* for the accounts; *Claude Code can do* the wiring and a test alert.

After these: the first restaurants and delivery partners onboarded with a test order each, and a dinner-rush
rehearsal on production with internal orders and refunds, before the first real order.
