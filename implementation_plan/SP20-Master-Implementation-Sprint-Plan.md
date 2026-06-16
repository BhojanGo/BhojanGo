# SP — Master Implementation Sprint Plan

**Document name:** `SP - Master Implementation Sprint Plan.md`  
**Document type:** Anchor implementation-control document  
**Repository root:** `/Users/raghuram/PycharmProjects/BhojanGo/BhojanGo`  
**Plan source folder:** `implementation_plan/`  
**Execution model:** Production Readiness is the spine. Novel Differentiation is an overlay only after the required Production Readiness foundation exists.

---

## 1. Purpose

This document defines the master implementation sprint sequence for BhojanGo.

It does **not** duplicate the implementation-plan document contents. Each sprint references the relevant implementation-plan file path and scope ID only. The detailed work items, dependencies, acceptance criteria, and self-audit scoring remain inside the referenced `implementation_plan/*.md` files.

This anchor document exists to control execution order, reduce token waste, prevent scope drift, define validation/evidence expectations, and ensure every sprint closes with a bounded review package.

---

## 2. Source Implementation Plan Documents

Use these files as the only planning source for sprint execution:

```text
implementation_plan/IP.PR.01 - Broken Shell.md
implementation_plan/IP.PR.02 - Browsable Prototype.md
implementation_plan/IP.PR.03 - Partial Core Flow.md
implementation_plan/IP.PR.04 - Internal Demo Core Loop.md
implementation_plan/IP.PR.05 - Usable Closed Demo.md
implementation_plan/IP.PR.06 - Closed Beta Marketplace.md
implementation_plan/IP.PR.07 - Reliable Beta Product.md
implementation_plan/IP.PR.08 - Early Production Ready.md
implementation_plan/IP.PR.09 - Production Grade Competitive App.md
implementation_plan/IP.PR.10 - Mature Marketplace Platform.md

implementation_plan/IP.ND.01 - Generic Clone.md
implementation_plan/IP.ND.02 - Light Cosmetic Difference.md
implementation_plan/IP.ND.03 - Small Convenience Features.md
implementation_plan/IP.ND.04 - Demo Level Differentiation.md
implementation_plan/IP.ND.05 - Retention Focused Uniqueness.md
implementation_plan/IP.ND.06 - Marketplace Specific Differentiation.md
implementation_plan/IP.ND.07 - Smart Personalization.md
implementation_plan/IP.ND.08 - Strong Product Identity.md
implementation_plan/IP.ND.09 - Defensible Differentiation.md
implementation_plan/IP.ND.10 - Category Leading Experience.md
```

---

## 3. Execution Rules

### 3.1 Core sequencing rule

```text
PR.01 → PR.04 first.
Then ND starts as an overlay.
PR remains the implementation spine.
ND must never block core Production Readiness.
```

### 3.2 Scope rule

For each sprint:

- Read only the referenced sprint scope documents and directly required code files.
- Do not reread the entire repo from scratch.
- Use existing cache/context where available.
- If a code file must be read, update the local analysis/cache note for that file so future tasks can reuse it.
- Implement only the current sprint scope.
- Do not implement future sprint scope unless it is a required dependency for the current sprint and is small/local.
- Do not add external services unless the sprint explicitly allows them.
- If external service setup, paid infrastructure, hardware, or broad repo restructuring is needed, stop and ask for confirmation.
- If missing local modules, missing local endpoints, missing local components, or missing local tests are required for the current sprint, implement them without asking.

### 3.3 Token/cost control rule

The implementation agent must optimize for low token burn and high code output.

Required behavior:

- Emit code changes, tests, evidence, and concise status only.
- Do not produce long thinking logs.
- Do not narrate every file read.
- Do not loop endlessly on the same error.
- Maximum retry count per failing issue: **3**.
- If still failing after 3 attempts, document the blocker and continue with remaining sprint work unless the blocker prevents all sprint execution.
- Do not run broad repo-wide searches unless required.
- Prefer targeted file reads based on the current sprint’s scope IDs.
- Prefer patching and validating over discussion.
- Ask the user only for true blockers:
  - paid/external service required
  - large repo task not scoped
  - destructive migration/data loss risk
  - unclear product decision that changes acceptance criteria

### 3.4 Validation rule

Unit tests are support evidence, not final acceptance.

Each sprint must close with:

1. Relevant unit tests.
2. Relevant backend live API tests when backend/runtime behavior is touched.
3. Relevant frontend/manual or Playwright live tests when UI behavior is touched.
4. Screenshots for frontend-visible changes.
5. A bounded closure zip limited to current sprint scope.

---

## 4. Standard Sprint Stage Model

Each sprint may use up to **3 substages + 1 final reconcile/closure stage**.

Do not create more than these stages.

### Stage A — Scope extraction + targeted implementation

- Read the sprint’s referenced implementation-plan documents.
- Extract only in-scope work item IDs.
- Read only directly affected source files.
- Implement the highest-priority P0/P1 local/demo-safe items first.
- Update or create code, migrations, seed data, scripts, and UI components as required by the sprint.

### Stage B — Local tests + focused integration

- Add/update unit tests for changed backend/frontend logic.
- Add/update component tests or route-level tests where practical.
- Run focused tests only.
- Fix failures up to 3 retries per issue.
- Continue remaining scope if a non-hard blocker remains.

### Stage C — Live validation + screenshots

Use this stage only when the sprint touches runtime behavior or UI.

- Start required backend services.
- Start frontend.
- Execute live API checks.
- Execute manual or Playwright UI flows.
- Capture minimum required screenshots for changed frontend flows.
- Store evidence under the shared evidence folder structure defined in Section 5.

### Final Reconcile — Closure, evidence zip, and implementation audit

Every sprint must end with this stage.

- Reconcile implemented work against the sprint scope IDs.
- Confirm what was completed, skipped, deferred, or blocked.
- Create a bounded zip containing only:
  - changed code files
  - changed tests
  - changed scripts/configs/migrations
  - evidence logs
  - frontend screenshots
  - sprint closure summary
- Do not include broad repo files.
- Do not include unrelated generated files.
- Do not include virtual environments, node_modules, DB files, build artifacts, cache folders, or old zips.

---

## 5. Evidence Folder Structure

Do not organize evidence by sprint ID or plan ID. Organize by application area so it remains reusable long term.

Use this structure:

```text
tests/results/
  backend/
    api/
    unit/
    integration/
    migrations/
    service-startup/
  frontend/
    customer/
      discovery/
      restaurant-detail/
      cart/
      checkout/
      orders/
      tracking/
      profile/
      screenshots/
    marketplace/
      restaurant-owner/
      delivery-partner/
      admin/
      screenshots/
    differentiation/
      discovery/
      loyalty/
      group-order/
      personalization/
      trust/
      screenshots/
  e2e/
    customer-core-loop/
    marketplace-roles/
    regression/
  evidence/
    logs/
    summaries/
    manifests/
```

Minimum evidence expectations:

- Backend API logs: `tests/results/backend/api/`
- Backend unit test logs: `tests/results/backend/unit/`
- Frontend/manual screenshots: `tests/results/frontend/**/screenshots/`
- End-to-end flow evidence: `tests/results/e2e/<app-area>/`
- Closure manifest: `tests/results/evidence/manifests/`
- Sprint summary: `tests/results/evidence/summaries/`

---

## 6. Standard Commands

Run commands from repository root:

```bash
cd /Users/raghuram/PycharmProjects/BhojanGo/BhojanGo
```

### 6.1 Start backend and local dependencies

Primary command:

```bash
./start-all.sh
```

If the script location differs, use the repository-provided startup script documented by `IP.PR.01`. Do not invent a new long-running orchestration path unless `start-all.sh` is missing or broken and the current sprint explicitly includes fixing it.

### 6.2 Start frontend

Primary command:

```bash
pnpm --filter web dev
```

If the workspace name differs, use the actual web app package name from the repo and record the exact command in the sprint closure summary.

### 6.3 Run focused backend tests

Use service-local tests where possible. Example pattern:

```bash
pytest services/<service-name>/tests -q
```

If the repo uses a different path or runner, record the actual command in the sprint closure summary.

### 6.4 Run focused frontend checks

Example pattern:

```bash
pnpm --filter web lint
pnpm --filter web test
```

If test scripts are missing, add the smallest appropriate test script only when required by the sprint.

### 6.5 Manual test sequence — high level

For customer-facing PR.02–PR.04+ sprints, manually verify:

```text
Open app
→ browse restaurants
→ open restaurant detail
→ view menu
→ add item to cart
→ view cart
→ proceed to checkout
→ simulate payment
→ see confirmation
→ open order tracking
```

Expected result by PR.04:

```text
No blank critical pages.
No broken primary CTA.
No unhandled frontend crash.
No backend 500 on core loop.
Confirmation and mock tracking are reachable.
Screenshots captured for critical states.
```

---

## 7. Master Sprint Sequence

| Sprint ID | Title | Scope IDs / Source Paths | Rationale / Expectations | Acceptance Criteria |
|---|---|---|---|---|
| **SPR-01** | Broken Shell Stabilization | `IP.PR.01` — `implementation_plan/IP.PR.01 - Broken Shell.md` | Make the app start reliably. Resolve boot, dependency, seed, migration, service-health, and root-cause blockers. No product feature work yet. | All required local services start or failures are explicitly documented. Dependency blockers are fixed or scoped. Seed data is verified. Core failing endpoints are cataloged. Closure zip contains only startup/dependency/seed/migration evidence and touched files. |
| **SPR-02** | Browsable Prototype | `IP.PR.02` — `implementation_plan/IP.PR.02 - Browsable Prototype.md` | Make the app navigable but not transactional. User can open app, browse restaurants, open restaurant detail, and see real menu data. | Restaurant list and detail page render. Menu endpoint returns data with DB fallback. Auth persistence and `/me` behavior work if scoped. No blank homepage/list/detail. Screenshots captured for homepage, listing, restaurant detail, loading/error/empty states. |
| **SPR-03** | Shaky Transactional Core | `IP.PR.03` — `implementation_plan/IP.PR.03 - Partial Core Flow.md` | Add cart, local/guest persistence, checkout form, simulated payment, order creation, confirmation, order list, cancellation, and mock tracking. | User can traverse cart → checkout → simulated order → confirmation → mock tracking. Backend validates order creation. Cart persists. Order state transitions reject invalid transitions. Evidence includes live API calls and frontend screenshots. |
| **SPR-04** | Internal Demo Core Loop | `IP.PR.04` — `implementation_plan/IP.PR.04 - Internal Demo Core Loop.md` | Make the full demo loop reliable and polished: login/guest → browse → menu → cart → checkout simulation → confirmation → mock tracking. | Full core loop passes manually/live. Loading/error/empty states exist. Design system and key Indian food UI elements are visible. No broken primary CTA. Screenshots cover each critical customer step. |
| **SPR-05** | Basic Product Differentiation Overlay | `IP.ND.01`, `IP.ND.02`, `IP.ND.03` — `implementation_plan/IP.ND.01 - Generic Clone.md`; `implementation_plan/IP.ND.02 - Light Cosmetic Difference.md`; `implementation_plan/IP.ND.03 - Small Convenience Features.md` | Add only light, low-risk differentiation after the core loop works: branding, trust cues, better discovery, veg/non-veg clarity, favorites/reorder visibility if scoped. No heavy novelty. | Differentiation does not break PR.04 core loop. Brand/trust/convenience features are visible and locally testable. Any nonfunctional or future-only differentiator is clearly disabled or marked as coming later. |
| **SPR-06** | Usable Closed Demo | `IP.PR.05` — `implementation_plan/IP.PR.05 - Usable Closed Demo.md` | Improve closed-demo quality: profile/order history stability, realistic seed data, saved preferences, stronger empty/loading/error states, cleaner UX. | Closed-demo personas can complete the customer flow with realistic data. Profile/order history are stable. Demo seed data is credible. Error/empty/loading states are acceptable. |
| **SPR-07** | Retention Features | `IP.ND.04`, `IP.ND.05` — `implementation_plan/IP.ND.04 - Demo Level Differentiation.md`; `implementation_plan/IP.ND.05 - Retention Focused Uniqueness.md` | Add practical retention differentiators: favorites, functional reorder, loyalty visibility, offers, saved preferences, personalized homepage sections. | Favorites/reorder/loyalty or equivalent scoped features work without destabilizing checkout. Repeat-user journey is visibly better than generic clone behavior. |
| **SPR-08** | Closed Beta Marketplace Foundation | `IP.PR.06` — `implementation_plan/IP.PR.06 - Closed Beta Marketplace.md` | Add basic marketplace roles and operational flows: customer, restaurant owner, delivery partner, and admin at minimum usable level. | Role-based pages and permissions work at beta-baseline level. Owner/driver/admin flows are minimally usable. Availability, cancellation, address, search/filter, and order-status completeness are verified. |
| **SPR-09** | Marketplace Differentiators | `IP.ND.06` — `implementation_plan/IP.ND.06 - Marketplace Specific Differentiation.md` | Add marketplace-specific features that make BhojanGo more than a clone: group ordering, office lunch mode, meal rescue, nutrition/allergen info, transparent fees, or scoped equivalent. | At least the scoped marketplace differentiators are functional/local-demo-safe. They integrate with customer/marketplace flows without bypassing permissions or breaking order flow. |
| **SPR-10** | Reliable Beta Product | `IP.PR.07` — `implementation_plan/IP.PR.07 - Reliable Beta Product.md` | Harden auth/roles, order state safety, API reliability, validation, indexes, logging/request trace basics, and edge-case handling. | Live backend and frontend tests show stable behavior under common failures. No major unhandled 500s in scoped flows. Logs/evidence show traceable request handling. |
| **SPR-11** | Smart Personalization | `IP.ND.07` — `implementation_plan/IP.ND.07 - Smart Personalization.md` | Add non-heavy personalization based on user history, time, cuisine, budget, distance, veg preference, and repeat behavior. No large AI infrastructure. | Personalization is rule-based or lightweight. User sees relevant recommendations. No external AI infra is required unless explicitly approved. |
| **SPR-12** | Early Production Readiness | `IP.PR.08` — `implementation_plan/IP.PR.08 - Early Production Ready.md` | Polish across mobile/tablet/desktop, accessibility, security, performance, responsive layouts, and beta-grade user trust. | Accessibility, responsiveness, security checks, and performance validations meet scoped acceptance. Limited-user launch threshold is credible. |
| **SPR-13** | Strong Product Identity | `IP.ND.08` — `implementation_plan/IP.ND.08 - Strong Product Identity.md` | Make the app feel distinct: smart bundles, trust system, freshness/speed cues, contextual deals, restaurant confidence signals, memorable ordering flow. | Product identity is visibly differentiated. Trust/speed/freshness cues are integrated into real flows, not isolated mock sections. |
| **SPR-14** | Production-Grade Competitive App | `IP.PR.09` — `implementation_plan/IP.PR.09 - Production Grade Competitive App.md` | Add real integrations and operational robustness where scoped: payment providers, webhooks, stronger admin operations, monitoring, recovery paths, professional cross-role UX. | Real integrations are validated only if credentials/services are available and approved. Otherwise use documented local mocks and mark external integration as deferred. Monitoring/recovery/admin improvements meet scoped evidence. |
| **SPR-15** | Defensible Differentiation | `IP.ND.09` — `implementation_plan/IP.ND.09 - Defensible Differentiation.md` | Add differentiators that are operationally useful, not gimmicks: group carts, meal rescue, loyalty tiers, restaurant insights, delivery confidence, trust loops. | Differentiators produce measurable user/restaurant/driver value in scoped flows. Gimmicks are excluded or downgraded. Evidence shows integration with marketplace operations. |
| **SPR-16** | Mature Marketplace Platform | `IP.PR.10` — `implementation_plan/IP.PR.10 - Mature Marketplace Platform.md` | Reach stable, trusted, scalable marketplace maturity. App should be operationally manageable and credible against serious delivery platforms. | Mature-platform features are either implemented locally, validated with approved integrations, or clearly deferred as Future Infrastructure. No hardware/large-ops assumptions are treated as complete without evidence. |
| **SPR-17** | Category-Leading Experience | `IP.ND.10` — `implementation_plan/IP.ND.10 - Category Leading Experience.md` | Add top-tier differentiation: personalization, marketplace intelligence, speed/freshness guarantees, community loops, and high-retention mechanics. | Category-leading features are scoped to software/app/service capabilities. Experimental items are P2/optional unless local-demo-safe and validated. |
| **SPR-18** | Final Hardening + Regression Pass | `IP.PR.01–IP.PR.10`, `IP.ND.01–IP.ND.10` — all files under `implementation_plan/` | Full end-to-end validation. Confirm every accepted feature works together without breaking core flows. Remove dead code, stale mocks, incomplete UI, and invalid assumptions. | Full regression evidence exists. Core customer flow, role flows, payment/tracking/mocked or real integrations, and differentiators are validated. Closure zip contains only regression-relevant changed files and evidence. |
| **SPR-19** | Demo / Beta Packaging | `IP.PR.04`, `IP.PR.08`, `IP.ND.04–IP.ND.08` — referenced implementation-plan files | Prepare demo scripts, seed personas, screenshots, test flows, known limitations, and acceptance evidence for stakeholders or beta users. | Demo package is reproducible. User can run exact commands, follow manual test sequence, and see expected screenshots/flows. Known limitations are explicit. |
| **SPR-20** | Launch Readiness Review | `IP.PR.09–IP.PR.10`, `IP.ND.09–IP.ND.10` — referenced implementation-plan files | Final GO/NO-GO review for production-style release. Confirm security, reliability, role flows, payments, monitoring, and differentiators are stable. | Final readiness summary gives GO/NO-GO. Open risks, blocked items, future infra, and unresolved external dependencies are explicit. No false production claim without live evidence. |

---

## 8. Sprint Complexity and Stage Split Guidance

Use the smallest stage split needed.

| Sprint Type | Stage Split |
|---|---|
| Small/local sprint | Stage A → Stage B → Final Reconcile |
| UI/runtime sprint | Stage A → Stage B → Stage C → Final Reconcile |
| Marketplace/role sprint | Stage A → Stage B → Stage C → Final Reconcile |
| Final regression/release sprint | Stage A → Stage B → Stage C → Final Reconcile |

Large sprints must not exceed:

```text
3 substages + 1 final reconcile/closure stage
```

---

## 9. Closure Zip Requirements

At the end of every sprint, create one bounded review zip.

Recommended location:

```text
review_exports/
```

Recommended name pattern:

```text
review_exports/SPR-XX_scope_review.zip
```

The zip must include only current sprint scope:

```text
changed code files
changed tests
changed migrations / configs / scripts
tests/results/** evidence created or updated for the sprint
frontend screenshots created or updated for the sprint
sprint closure summary
```

The zip must exclude:

```text
node_modules/
.venv/
__pycache__/
.next/
dist/
build/
coverage/
runtime DB files
old zips
unrelated implementation_plan files
broad repo dumps
.env files
secrets
```

The sprint closure summary must include:

```md
# Sprint Closure Summary

## Sprint ID
## Scope IDs
## Implemented
## Updated Files
## Tests Run
## Live Backend Evidence
## Live Frontend Evidence
## Screenshots Captured
## Acceptance Criteria Result
## Open Gaps
## Issues / Risks
## Opportunities
## What Went Well
## Lessons Learned
## User Manual Test Instructions
## Exact Commands Used
## Zip Manifest
```

---

## 10. Required End-of-Sprint Summary

Every sprint must end with this summary:

```md
## Summary of Edits / Updates / Implementations

## Open Gaps

## Issues

## Opportunities

## What Went Well

## Lessons Learned to Preserve

## What User Should Do Next

### Exact Commands

### Manual Test Sequence

### Expected Result
```

The summary must be concise, factual, and evidence-backed.

---

## 11. User Expectations After Each Sprint

The implementation agent must tell the user exactly what to do next.

Minimum user instruction format:

```md
## User Next Steps

From repo root:

```bash
cd /Users/raghuram/PycharmProjects/BhojanGo/BhojanGo
./start-all.sh
pnpm --filter web dev
```

Then manually test:

```text
1. Open the web app.
2. Follow the sprint-specific manual flow.
3. Confirm the expected result listed below.
4. Capture or review screenshots under tests/results/frontend/**/screenshots/.
5. Upload the sprint closure zip for review.
```

Expected result:

```text
<state the sprint-specific expected user-visible behavior>
```
```

---

## 12. Blocker Policy

Do not stop on the first issue.

Continue implementing remaining independent work unless there is a hard blocker.

### Hard blocker examples

- Repo cannot install or start at all.
- Required database cannot initialize.
- Required core service cannot boot and all current sprint work depends on it.
- External/paid service is required but not approved.
- Required product decision changes acceptance criteria.
- Implementation would require broad architecture change outside sprint scope.
- Migration/data-loss risk exists.

### Non-hard blocker examples

- One endpoint failing while unrelated frontend component work can continue.
- One test flaky while manual validation can still proceed.
- One optional P2 feature not possible.
- One screenshot unavailable due to unrelated local browser issue.

For non-hard blockers:

- Record the blocker.
- Continue remaining scope.
- Include blocker in closure summary.
- Do not retry more than 3 times.

---

## 13. Final Principle

This sprint plan prioritizes:

```text
less dialogue
less token burn
more bounded code
more evidence
more screenshots
better closure zips
fewer false PASS claims
```

Production Readiness unlocks capability. Novel Differentiation increases customer appeal only after the required capability is stable.
