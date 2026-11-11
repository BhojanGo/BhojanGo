# BhojanGo — Structure spec (markets, rules, repo layout)

Nov 2026 · Owner: Srini. Full doc with diagrams:
https://claude.ai/artifact/V5tV6KSmgxf3C3jksbn8fW

**Every country, city, fee, tax and rule is data that admins set in the console,
not code.** Engineers build the rule engine once; ops launch a city or change a
GST rate without a deploy.

## 1. Repo layout (target)

```text
bhojango/
├── apps/
│   ├── customer/        Expo · customer app (iOS, Android)      com.bhojango.app
│   ├── rider/           Expo · delivery partner app               com.bhojango.rider
│   ├── partner/         Expo · restaurant tablet app (from P19)   com.bhojango.partner
│   ├── web/             Next.js · customer web + marketing site
│   └── admin/           Next.js · admin console
├── backend/             Python 3.12 · one uv workspace
│   ├── core_api/        deployable 1 · FastAPI
│   │   └── modules/
│   │       ├── identity/    users, auth, admin roles + scopes
│   │       ├── catalog/     restaurants, menus, modifiers, hours
│   │       ├── orders/      order saga, state machine
│   │       ├── payments/    Stripe, Stripe Tax, Razorpay, wallet, refunds
│   │       ├── markets/     countries, regions, cities, zones        (P6)
│   │       ├── rules/       rule store, templates, resolver, approvals (P7)
│   │       ├── pricing/     quote engine, simulator, price snapshot  (P8)
│   │       ├── promotions/  offers, budgets, who funds them          (P7)
│   │       ├── finance/     payouts, ledger, reconciliation          (P13)
│   │       └── audit/       audit log                                (P7)
│   ├── realtime/        deployable 2 · rider GPS, tracking WebSocket, dispatch, ETA
│   ├── worker/          deployable 3 · outbox relay, notifications, payouts, batching
│   ├── shared/          db session, config, auth middleware, money, events, logging
│   └── migrations/      one Alembic history for the whole database
├── packages/            TypeScript · pnpm + Turborepo
│   ├── api-client/      typed client generated from core_api OpenAPI (replaces types/)
│   ├── mobile-core/     auth, API hooks, theme, components for the 3 Expo apps
│   ├── ui/              component kit for admin + web
│   ├── i18n/            en-US, en-IN, hi-IN, te-IN
│   └── config/          eslint, tsconfig, prettier
├── infra/
│   ├── terraform/       modules/ + envs/staging + envs/prod
│   └── docker/          compose.yaml with profiles: infra, backend, all
├── tools/seed/          Hyderabad + Boise markets, rules, restaurants, test users
├── docs/                adr/, specs/ (this folder), runbooks/
└── .github/             CI per area, CODEOWNERS
```

**Rules that keep it clean**

- Every backend module has the same five folders: `api/`, `service/`,
  `repository/`, `models/`, `schemas/`. A module reads another module only through
  its `service`, never its tables; an import-linter check blocks violations in CI.
- API types come from one place: generated from the backend OpenAPI into
  `packages/api-client`.
- Only `markets/` and `rules/` know currencies, tax rates and fees. Every other
  module asks the resolver.
- Tooling: uv + ruff + mypy + pytest for Python; pnpm + Turborepo + ESLint +
  Vitest for TypeScript; one `make dev` brings everything up.
- Branching: `main` always deployable to staging; short feature branches with PRs;
  release tags for prod. `dev` merges into `main` once, then retires.

How today's code moves into this layout: see `02-restructure-map.md`.

## 2. Markets: how settings inherit

Six levels; the most specific level that has a value wins:
**Platform → Country → State/Region → City → Zone → Restaurant.**

| Level | Admin sets here | Example |
| --- | --- | --- |
| Platform | Defaults, languages, rule templates, admin roles | Cancellation window 2 min |
| Country | Currency, languages, timezone(s), mi/km, phone format, payment providers, tax regime, legal docs, KYC rules, SMS provider | India: INR, en-IN + hi-IN, Razorpay, UPI + card, GST, FSSAI required |
| State / Region | Tax that differs inside a country, labour rules, rider pay minimums | Idaho sales tax |
| City | Launch status (draft, beta, live, paused), service hours, fee plans, surge windows, rider pay plan, dispatch settings, promos | Hyderabad live, 7:00–23:30, surge 19:00–21:30 |
| Zone (map polygon) | Delivery area, min order, extra fee or surge, temporary pause | Hitech City: min order ₹149 |
| Restaurant | Commission plan, packaging levy, prep time, radius, hours, own free-delivery offer | Tier B: 15%, ₹10 packaging |

Money rules (tax, commission, rider pay) are set by country or city managers only.
Restaurants change only their own menu, hours, prep time and offers.

First markets: **India ▸ Telangana ▸ Hyderabad** and **USA ▸ Idaho ▸ Boise**.

## 3. Rules

Admins build rules from fixed templates, never free-form formulas.

| Family | Templates | Scopes |
| --- | --- | --- |
| Delivery fee | Flat · Distance slabs · Free above order value · Restaurant tier base | City, Zone, Restaurant |
| Other customer fees | Service fee (% with min/max) · Small-order fee · Packaging levy · Surge levy · Late-night fee | City, Zone, Restaurant |
| Tax | Rate on a target line · Who collects · Inclusive or added · Source: Stripe Tax (US), GST table (India) | Country, State, City |
| Commission | % of food subtotal by tier · Optional flat per order · Payout schedule | Country, City, Restaurant |
| Rider pay | Base + per km + per waiting minute · Hourly floor · Batch bonus · Peak bonus | Country, State, City |
| Business rules | Accept timeout · Unpaid auto-cancel · Cancel/refund windows · COD limit · Tip presets · Max radius · Dispatch offer timeout | Platform, Country, City |
| Promotions | % off, flat off, free delivery, first order, referral · Budget cap · Funded by platform or restaurant | Country, City, Restaurant |

**Guardrails on every rule**

1. Versioned and dated — a live rule is never edited; a new version gets a start date.
2. Draft → review → publish — money rules need a second admin (maker-checker).
3. Preview first — the simulator shows the full bill before publishing.
4. Order snapshot — each order stores the rule versions and amounts it was priced with.
5. Audit log — who changed what, when, from what to what.

**Resolver:** for each family, take the active rule at the most specific scope
(Restaurant → Zone → City → Region → Country → Platform). A rule can be marked
"cannot be overridden below this level".

## 4. Quote engine (8 steps, same in every country)

1. Locate: address → zone → city → country; load active rules.
2. Food subtotal: items + modifiers.
3. Promotions: apply and record who funds them.
4. Customer fees: delivery, service, small-order, packaging, surge.
5. Taxes: each tax rule on its target lines.
6. Tip.
7. Total: signed quote valid 10 minutes; checkout charges exactly this.
8. Split: restaurant payout, rider pay, tax owed, platform revenue — saved on the order.

**Test case — Hyderabad, 4.2 km, 8 pm** (illustrative rates; confirm tax with a CA)

| Line | Rule | ₹ |
| --- | --- | --- |
| Chicken biryani + extra raita, paneer tikka | Menu prices | 560.00 |
| Promo 10% off, max ₹50 (platform-funded) | Promotion | −50.00 |
| Delivery fee | Distance slab 3–6 km | 35.00 |
| Packaging | Restaurant levy | 10.00 |
| Service fee | 2%, min ₹5, max ₹15 | 11.20 |
| Surge | City window 19:00–21:30 | 15.00 |
| GST on food + packaging | 5%, platform collects | 26.00 |
| GST on platform fees | 18% on delivery, service, surge | 11.02 |
| Tip | Customer choice | 20.00 |
| **Customer pays** | | **638.22** |

| Who gets it | How | ₹ |
| --- | --- | --- |
| Restaurant | 560 food + 10 packaging − 15% commission on 560 | 486.00 |
| Rider | ₹25 base + ₹6/km × 4.2 + tip | 70.20 |
| Government | GST collected | 37.02 |
| Platform | What remains | 45.00 |

## 5. Data tables

| Table | Holds | Key columns |
| --- | --- | --- |
| `countries` | Country settings | code, currency, locales, timezone, distance_unit, payment_providers, tax_regime, status |
| `regions` | States / provinces | country_id, code, name |
| `cities` | City settings | country_id, region_id, timezone, service_hours, launch_status |
| `zones` | Delivery areas | city_id, polygon (PostGIS), min_order, status |
| `rules` | Every fee, tax, commission, rider-pay and business rule | family, template, params (JSON validated by template), scope_level, scope_id, priority, version, status, effective_from, effective_to |
| `rule_approvals` | Maker-checker trail | rule_id, requested_by, approved_by, decided_at |
| `promotions` | Offers and budgets | scope, type, value, budget_cap, funded_by, dates |
| `feature_flags` | Features per market | key, scope_level, scope_id, enabled |
| `integration_settings` | Provider keys per country | country_id, provider, secret_ref (AWS Secrets Manager, never in the DB) |
| `order_pricing_snapshot` | What each order was charged and why | order_id, lines, rule_versions, split |
| `audit_log` | Every admin change | actor, action, entity, before, after, at |

## 6. Admin console

One scope bar on every page: **country tabs → state chips → searchable city picker
grouped by state**. Super admins also get an "All countries" overview.

| Section | Pages | Main users |
| --- | --- | --- |
| Home | Live orders, GMV, delivery time, alerts | Everyone |
| Operations | Live orders · Dispatch map · Support tickets and refunds | City ops, Support |
| Partners | Restaurants (onboarding, menus, hours, documents) · Riders | City ops |
| Customers | Search, history, credits, block/unblock | Support |
| Pricing & Rules | All rule families · Price simulator · Approvals | Country manager, Finance |
| Markets | Countries · States · Cities · Zones (draw on map) | Country manager |
| Finance | Payments · Payouts · Reconciliation · Tax reports | Finance |
| Reports | Orders, revenue, delivery times, partner performance; CSV | Everyone (scoped) |
| Settings | Admin users and roles · Integrations · Feature flags · Audit log | Super admin |

Roles: super admin (global), country manager, city ops, support agent (refunds up
to a limit), finance, viewer — each scoped to a country, state or city.

Design rules: show where each value comes from ("Inherited from India" /
"Overridden for Hyderabad" + reset link); plain words; simulator beside every
money-rule page; one list → detail → draft/review/publish pattern; changes take
effect at a chosen time and roll back in one click; local currency, time and units.

## 7. Decisions (Nov 4 2026)

| Question | Decision |
| --- | --- |
| First markets | India ▸ Hyderabad and USA ▸ Boise, seeded from day one |
| Restaurant-funded free delivery | Allowed in the pilot; cost comes off that restaurant's payout; each city sets a cap |
| US tax | Stripe Tax (external). India keeps a small GST rule table in the console |
| Service layout | 3 deployables: core_api, realtime, worker |
| Auth | Custom auth, RS256 + JWKS (not Cognito) |
| Gateway / search | AWS ALB + WAF instead of Kong; Postgres search instead of OpenSearch |
| App names | BhojanGo, BhojanGo Rider, BhojanGo Partner; admin console internal only |
