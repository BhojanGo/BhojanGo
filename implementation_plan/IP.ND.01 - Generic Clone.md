# IP.ND.01 — Generic Clone

> **Document Type:** Novelty / Differentiator Implementation Plan
> **Target Differentiation Score:** 1/10
> **Score Meaning:** Looks and behaves like a basic Swiggy/Zomato template with no meaningful differentiation.
> **Date:** 2026-06-14
> **Sources:** `Micro_Audit_BhojanGo.md`, `Micro_Audit_BhojanGo_v2.md`, `BhojanGo_Novel_Delivery_Engine_Ideas.md`, `BhojanGo_Unique_Value_Assessment.md`

---

## 1. Target Score Level

**1/10** — Generic Clone

---

## 2. Score Meaning

At score 1/10, BhojanGo looks and behaves like a basic Swiggy/Zomato template with no meaningful differentiation. The app has zero unique identity, no distinctive design language, no novel features visible to end users, and no product-level uniqueness that would compel a customer, restaurant, or driver to choose BhojanGo over an incumbent platform.

**Why 1/10 and not 0/10:**
- The codebase is clean, well-architected (microservices, async patterns)
- Multi-market support (US + India) with locale-aware features is competent engineering
- Restaurant pricing flexibility (%, flat, subscription) is a backend difference from competitors, though not customer-visible
- The batch engine algorithm is sound and would be genuinely novel if integrated
- These foundations earn a point for "has potential"

**Why not 2/10:**
- No customer, restaurant, or driver can perceive any difference between BhojanGo and an incumbent
- There is no light cosmetic difference, no small convenience feature, no demo-level unique touch
- The app is functionally indistinguishable from a Swiggy/Zomato template
- "There is **no reason** for a customer to switch from Uber Eats to BhojanGo today" — Unique Value Assessment

---

## 3. Current → Target Transition

**Current State (Score 1/10):**
The app is a plain food delivery clone with zero unique identity. There is no BhojanGo-specific design language, no novel features, no unique user experience. It looks like every other generic delivery app.

**Evidence from codebase audit:**
- UI is a "generic Tailwind template with zero product-specific design language" (Micro Audit v1)
- "Default Tailwind colors everywhere" — no brand palette defined (Micro Audit v2, BG.F.C003.001)
- `font-sans` with system defaults — no custom typography (Micro Audit v2, BG.F.C003.002)
- Mix of emoji and SVGs for icons — no icon style standard (Micro Audit v2, BG.F.C003.004)
- "Zero trust signals" on restaurant cards (Micro Audit v2, BG.F.C003.007)
- Restaurant cards use generic Picsum placeholder images, not food photography (Micro Audit v1, BG.F.P002.004)

**Target State (Score 1/10 — Baseline Locked):**
This plan does not aim to increase the score. The objective is to **acknowledge, document, and baseline** the generic state so that subsequent ND plans (ND.02 through ND.10) have a clear starting point and measurable delta.

**Transition Summary:**
At the completion of IP.ND.01, BhojanGo will have a documented inventory of every generic element, a scorecard showing zero measurable differentiators, and a verified benchmark against competitor features. The differentiation score remains **1/10** by design.

---

## 4. Implementation Objective

Acknowledge the generic state. Document what makes BhojanGo indistinguishable from competitors. Set a rigorous foundation so that ND.02+ can add differentiation with clear before/after measurement.

Specific objectives:
1. Inventory every feature that is functionally identical to Swiggy/Zomato/Uber Eats/DoorDash
2. Identify every design/UX element that uses default/generic patterns
3. Document current feature parity gaps versus established competitors
4. Lock the baseline measurable differentiators at **zero**
5. Create a reference scorecard that future ND plans will update

---

## 5. Scope

### In Scope
- Audit and inventory of all generic features across frontend, backend, and user flows
- Identification of undifferentiated design elements (colors, typography, icons, spacing, badges, cards)
- Competitor feature parity benchmarking (Swiggy, Zomato, Uber Eats, DoorDash)
- Baseline differentiation scorecard creation
- Documentation of the batch engine's current unintegrated state (it exists in code but is not a visible differentiator)
- Catalog of all "documented but not implemented" aspirational features from design docs
- Verification that no customer-facing novelty feature is operational today

### Scope Boundaries
- This plan covers **audit and documentation only** — no code changes
- The output is a set of inventories, scorecards, and gap analyses
- All findings must be traceable to one of the four allowed source documents

---

## 6. Out of Scope

- Any new feature implementation (covered by ND.02+)
- Any design changes or branding work
- Any novelty ideas or differentiation concepts
- Any code modifications, schema changes, or API additions
- Any fix of the broken core loop (covered by PR.01+)
- Any production readiness improvements (covered by existing production roadmaps)
- Marketing or go-to-strategy documents

---

## 7. Required Capabilities

At score 1/10, BhojanGo requires only the basic capabilities found in every generic food delivery platform:

| Capability | Status | Notes |
|---|---|---|
| Restaurant browsing | ✅ Operational | Generic list/grid view |
| Menu display | ⚠️ Partial | 500 errors on some menu endpoints |
| Cart management | ⚠️ Partial | Auth persistence issues |
| Checkout flow | ✅ Operational | Card/UPI/COD supported |
| Order tracking | ⚠️ Partial | Real-time updates incomplete |
| User authentication | ⚠️ Partial | Guest checkout blocked |
| Multi-language support | ✅ Operational | 3 locales implemented |
| Wallet | ✅ Operational | Functionally identical to competitors |
| Review submission | ⚠️ Partial | Can submit, cannot properly list |

No unique or differentiated capabilities are required at this score level.

---

## 8. Key User Journeys

At score 1/10, all user journeys are generic and identical to incumbent platforms:

### Customer Journey
1. Browse restaurants → View menu → Add to cart → Checkout → Track order
2. No differentiation at any step — identical to Swiggy/Zomato flow

### Restaurant Journey
1. Register → Upload menu → Receive orders → Manage fulfillment
2. No unique POS integration, no batch-specific UI, no analytics differentiation

### Driver Journey
1. Accept assignment → Pick up orders → Deliver to customer
2. Single-order assignment only — no batching UI, no route optimization exposure

All journeys lack distinctive BhojanGo touchpoints, unique interactions, or differentiated value props.

---

## 9. Technical Coverage

### Generic Technical Stack
- Microservices architecture (competitor-parity, not differentiated)
- Async patterns with message queues (standard engineering practice)
- PostgreSQL + OpenSearch backend (common stack)
- React + Tailwind frontend (ubiquitous choice)

### Competitor Parity Analysis

| Feature | BhojanGo Current | Swiggy/Zomato | Uber Eats | DoorDash | Parity Status |
|---|---|---|---|---|---|
| Browse restaurants | ✅ Implemented | ✅ | ✅ | ✅ | **Parity** |
| Search by name/cuisine | ❌ No endpoint | ✅ | ✅ | ✅ | **Gap** |
| Filter by rating/time/price | ❌ No UI | ✅ | ✅ | ✅ | **Gap** |
| Menu browsing | ❌ 500 error | ✅ | ✅ | ✅ | **Critical Gap** |
| Add to cart | ⚠️ Broken/auth issues | ✅ | ✅ | ✅ | **Gap** |
| Guest checkout | ❌ Requires login | ✅ | ✅ | ✅ | **Gap** |
| Multiple payment methods | ✅ Card/UPI/COD | ✅ | ✅ | ✅ | **Parity** |
| Real-time tracking | ⚠️ Partial | ✅ | ✅ | ✅ | **Gap** |
| Order cancellation | ❌ Not implemented | ✅ | ✅ | ✅ | **Gap** |
| Reviews display | ⚠️ Partial | ✅ | ✅ | ✅ | **Gap** |
| Favorites | ❌ Not implemented | ✅ | ✅ | ✅ | **Gap** |
| Reorder | ❌ Not implemented | ✅ | ✅ | ✅ | **Gap** |
| Loyalty program | ❌ DB field unused | ✅ | ✅ | ✅ | **Gap** |
| Nutritional info | ❌ Not implemented | ⚠️ Partial | ⚠️ Partial | ❌ | **Parity (none)** |
| Group ordering | ❌ Not implemented | ❌ | ❌ | ❌ | **Parity (none)** |
| AI recommendations | ❌ Not implemented | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | **Gap** |
| Dark mode | ❌ Toggle missing | ✅ | ✅ | ✅ | **Gap** |
| Multi-language | ✅ 3 locales | ✅ | ✅ | ✅ | **Parity** |
| Wallet | ✅ Implemented | ✅ | ✅ | ✅ | **Parity** |

**Parity Summary:**
- Full parity on ~6 basic features (browse, payments, wallet, multi-language)
- Gaps on ~10 standard features (search, filters, cancellation, favorites, reorder, loyalty, reviews)
- Critical gaps on core loop (menu 500 error, guest checkout blocked, auth persistence broken)
- Zero differentiation features operational (batch engine, group ordering, nutritional info, AI suggestions, meal rescue, smart lockers, voice ordering, sustainability scoring)

### Architecture Documents vs. Code Reality

> "The `docs/BHOJANGO_PLATFORM_TECHNICAL_DESIGN.md` (1,136 lines) and `docs/BATCH_ENGINE_TECHNICAL_DESIGN.md` (1,318 lines) describe a far more complete system than what is actually implemented. The code implements approximately **60-65%** of what the design docs describe." — Unique Value Assessment

**Implication for Differentiation:**
A significant portion of the "unique" claims in BhojanGo's documentation are aspirational. The actual product delivered to users is a generic food delivery app with approximately **0% customer-visible differentiation.**

### Batch Engine — Differentiator on Paper Only

The batch engine is the **only potentially unique feature** in the codebase. However:

| Claim | Actual Status | Evidence |
|---|---|---|
| Cross-restaurant batching algorithm | ✅ Exists in code | `batch-engine/src/services/batch-builder.ts`, `batch-scorer.ts`, `route-optimizer.ts` |
| Driver assignment integration | ❌ Not wired | `batch-engine` does not call `delivery-svc` for driver assignment |
| Customer opt-in UI | ❌ Not implemented | No checkbox, toggle, or preference in any frontend file |
| Route recalculation on order removal | ❌ TODO only | `batch.service.ts:removeOrderFromBatch()` has `// TODO: route recalculation` |
| Driver capacity check | ❌ Not implemented | No bag volume vs. order volume verification |
| PrepSync delay notification | ❌ Not implemented | Design doc only |
| Thermal AI routing | ❌ Not implemented | Design doc only |
| Dynamic delivery tiers | ❌ Not implemented | Design doc only |

**Verdict:** The batch engine is a unique differentiator **on paper, but 40-50% unintegrated in code.** If completed, it would be genuinely novel. Right now, it is a research prototype, not a product feature. It contributes **zero** to the current differentiation score.

---

## 10. UI / UX Coverage

### Design Language & Visual Identity
**Current State: Generic**
- Primary color: default Tailwind `emerald-600` — no brand palette
- Typography: system `font-sans` — no custom font import
- Spacing: random Tailwind values — no 4px base grid or design tokens
- Icons: mix of raw emoji and ad-hoc SVGs — no standard icon library
- Badges: no badge anatomy or standard
- Cards: restaurant cards vary in structure — no defined card anatomy
- Trust elements: zero trust signals (no FSSAI, freshness, or verified badges)
- Images: generic Picsum placeholders instead of category-specific food photography

**Score: 1/10**

### User Experience (UX) Patterns
**Current State: Generic**
- Instant hard navigation between pages — no page transitions
- No add-to-cart micro-animation or visual feedback
- No pull-to-refresh on mobile
- No offline indicator
- Skeleton loaders absent on most pages — blank white screens during loading
- No empty state illustrations
- Mobile relies on hamburger menu — no bottom navigation
- Modals cover full screen on mobile — no bottom sheet pattern

**Score: 1/10**

---

## 11. Data / Model Coverage

### Current Data Model Status

| Model / Entity | Status | Differentiation Notes |
|---|---|---|
| Restaurant | ✅ Standard | Generic fields, no unique attributes |
| Menu / MenuItem | ✅ Standard | No nutritional data, no allergen fields |
| Order | ✅ Standard | Single-restaurant only, no batch metadata |
| Cart | ✅ Standard | Generic line-item pattern |
| User | ✅ Standard | `loyalty_points` column exists but completely unused |
| Payment | ✅ Standard | Card/UPI/COD — identical to competitors |
| Review | ⚠️ Partial | Missing proper listing/query support |
| Driver | ✅ Standard | No batch capacity, no route preference fields |
| Batch | ⚠️ Exists but unintegrated | Not linked to customer-facing data |

### "Documented But Not Implemented" Inventory

From the Unique Value Assessment, the following features are described in design documents but have **zero implementation** in actual code:

| Design Doc Claim | Status |
|---|---|
| Customer batch opt-in at checkout | ❌ Zero code |
| AI/ML-based scoring for batch engine | ❌ Hardcoded weights only |
| Real-time traffic via Google Routes API | ❌ Haversine + fixed 1.4x road factor |
| UPI payment-specific UI | ❌ No UPI QR or intent flow |
| PrepSync Batching | ❌ Design doc only |
| Thermal AI Routing | ❌ Design doc only |
| Dual-Compartment Delivery Bags | ❌ Design doc only |
| Dynamic Priority Tiers | ❌ Design doc only |
| Smart Locker Relay | ❌ Design doc only |
| Temperature-Guarantee Subscriptions | ❌ Design doc only |
| Virtual Food Court | ❌ Design doc only |
| AI Predicted Batch Optimal Window | ❌ Design doc only |

---

## 12. Role / Permission Coverage

At score 1/10, role and permission coverage is generic and standard:

| Role | Capabilities | Differentiation |
|---|---|---|
| Customer | Browse, cart, checkout, track, review | Identical to all competitors |
| Restaurant | Menu management, order receipt, fulfillment | No unique analytics, no batch-specific features |
| Driver | Accept delivery, mark picked up, mark delivered | No batch assignment, no route optimization UI |
| Admin | User management, restaurant approval | Standard admin panel, no unique tooling |

No differentiated permission model, no novel role types (e.g., community kitchen operator, batch coordinator, smart locker attendant).

---

## 13. Performance / Reliability / Security Coverage

### Performance
**Current State: Undifferentiated**
- No image optimization — 800x600 hero images served as-is
- No CDN for static assets
- No WebP serving
- OpenSearch is a hard dependency (no graceful degradation until fixed)
- No client-side retry logic

**Score: 1/10**

### Reliability
- No differentiated reliability claims or SLAs
- Standard uptime expectations, no unique failover patterns visible to users

### Security
- Standard JWT-based auth (competitor-parity)
- No unique security differentiators (e.g., verifiable delivery proof, tamper-evident packaging tracking)

---

## 14. Novelty / Differentiation Coverage

### 10 Differentiation Dimensions — All Scored 1/10

#### 14.1 Product Features
**Current State: Generic**
- Browse restaurants, view menus, add to cart, checkout, track orders — identical to every incumbent platform
- No favorites, no reorder, no loyalty activation, no group ordering, no meal rescue, no nutrition info
- No voice ordering, no AI suggestions, no smart locker, no subscription boxes
- Wallet exists but is functionally identical to Swiggy/Zomato wallet implementations
- Review system is partially implemented (can submit, cannot properly list) — less functional than competitors

**Score: 1/10**

#### 14.2 Design Language & Visual Identity
*(See Section 10)*
**Score: 1/10**

#### 14.3 User Experience (UX) Patterns
*(See Section 10)*
**Score: 1/10**

#### 14.4 Trust & Transparency
**Current State: Generic**
- No nutritional transparency panel (calories, macros, allergens)
- No transparent fee breakdown at checkout
- No prep-time logic — all restaurants show static 35-45 min
- No real-time kitchen status visibility
- No sustainability or eco-messaging
- No carbon offset tracking

**Score: 1/10**

#### 14.5 Personalization & Retention
**Current State: Generic**
- No personalized homepage sections
- No AI meal suggestions based on history, time, or weather
- `loyalty_points` column exists in DB but is completely unused
- No favorites/bookmark system
- No reorder from history
- No saved cuisine preferences
- No dietary profile or allergen preferences

**Score: 1/10**

#### 14.6 Marketplace Mechanics
**Current State: Generic**
- Single-restaurant orders only — no multi-restaurant cart
- No group ordering or office lunch mode
- No meal rescue / end-of-day deals
- No community kitchen / home chef section
- No restaurant subscription plans
- No dynamic delivery tier selection (Fast/Eco/Saver)
- No driver shift auction or dynamic pricing

**Score: 1/10**

#### 14.7 Competitive Moat & Defensibility
**Current State: None**
- The batch engine algorithm exists in code but is **not integrated** with driver assignment, customer UI, or delivery flow
- No customer can experience batch delivery today
- Restaurant pricing flexibility (%, flat, subscription) exists in backend but is not surfaced as a customer-visible differentiator
- "The only viable path is efficiency differentiation... But this only works if the batch engine is operational. Right now, it's a thesis, not a product feature." (Unique Value Assessment)
- No network effects, no data moat, no supply-side lock-in

**Score: 1/10**

#### 14.8 Accessibility & Inclusivity
**Current State: Generic / Below Par**
- No keyboard navigation
- No ARIA labels on interactive elements
- No focus trapping in modals
- No screen reader optimizations
- Playwright tests rely on text selectors, not roles
- No voice ordering accessibility feature

**Score: 1/10**

#### 14.9 Performance & Efficiency Claims
*(See Section 13)*
**Score: 1/10**

#### 14.10 Brand Voice & Messaging
**Current State: Generic**
- No distinctive brand voice in copy
- No environmental or social mission messaging
- Problem statement in original docs described as "marketing copy, not derived from code... boilerplate claims found in any food delivery pitch deck" (Unique Value Assessment)
- App could be rebranded to any other delivery brand with a color swap

**Score: 1/10**

---

## 15. Implementation Work Items

### IP.ND.01.001 — Inventory Generic Features

- Category: Audit / Documentation
- Implementation Scope: Catalog every feature that exists in BhojanGo and is functionally identical to Swiggy/Zomato/Uber Eats/DoorDash. Map every major user flow (browse, search, menu, cart, checkout, track, profile) to competitor equivalents and label each as Parity, Gap, or Critical Gap.
- Acceptance Criteria:
  - Every major user flow is mapped to competitor equivalents
  - Each flow is labeled as Parity, Gap, or Critical Gap
  - Findings traceable to Micro Audit v1/v2 source items
- Evidence Required:
  - Feature parity matrix covering minimum 15 features across 4 competitors
  - Cross-reference table linking each finding to audit item IDs (BG.B.*, BG.F.*, BG.I.*, BG.N.*)
- Priority: P0
- Effort: M
- Dependency: NONE
- Status: TODO
- Implementation Class: Local/Demo-Safe

### IP.ND.01.002 — Identify Undifferentiated Design Elements

- Category: Audit / Documentation
- Implementation Scope: Document every design/UX element that uses default or generic patterns with no BhojanGo identity. Cover color palette, typography, icon usage, spacing system, card anatomy, badge system, trust elements, and image sourcing.
- Acceptance Criteria:
  - Color palette status documented (default emerald-600, no brand tokens)
  - Typography status documented (system font, no custom import)
  - Icon usage documented (emoji + ad-hoc SVG mix, no standard library)
  - Spacing system documented (random Tailwind values, no grid)
  - Card anatomy documented (inconsistent, no standard)
  - Badge system documented (absent)
  - Trust elements documented (zero signals)
  - Image sourcing documented (Picsum placeholders, not food photography)
- Evidence Required:
  - Design element inventory document with screenshots or code references
  - List of all generic Tailwind classes used without customization
- Priority: P0
- Effort: M
- Dependency: NONE
- Status: TODO
- Implementation Class: Local/Demo-Safe

### IP.ND.01.003 — Benchmark Against Competitor Features

- Category: Audit / Documentation
- Implementation Scope: Compare BhojanGo's feature set against Swiggy, Zomato, Uber Eats, and DoorDash on a feature-by-feature basis. Verify each competitor's status via public app/documentation.
- Acceptance Criteria:
  - Minimum 15 features compared across 4 competitors
  - Each competitor's status verified via public app/documentation
  - BhojanGo gaps linked to specific audit items (BG.B.*, BG.F.*, BG.I.*, BG.N.*)
- Evidence Required:
  - Competitor parity table (see Section 9)
  - Source citations for competitor feature status
- Priority: P0
- Effort: M
- Dependency: IP.ND.01.001
- Status: TODO
- Implementation Class: Local/Demo-Safe

### IP.ND.01.004 — Baseline Differentiation Scorecard Creation

- Category: Documentation
- Implementation Scope: Create a locked baseline scorecard showing zero measurable differentiators. This scorecard will be updated by ND.02+ plans. Lists all 10 differentiation dimensions, scores every dimension 1/10 with evidence citation, includes batch engine scored as 0 contributing points (unintegrated), and includes "Documented But Not Implemented" inventory.
- Acceptance Criteria:
  - Scorecard lists all 10 differentiation dimensions (Sections 14.1–14.10)
  - Every dimension scored 1/10 with evidence citation
  - Batch engine scored as 0 contributing points (unintegrated)
  - Scorecard includes "Documented But Not Implemented" inventory
  - Scorecard signed off as baseline reference for ND.02
- Evidence Required:
  - `ND_Scorecard_Baseline.md` document stored in `/implementation_plan/`
  - Sign-off record from Product Owner and Engineering Lead
- Priority: P0
- Effort: S
- Dependency: IP.ND.01.001, IP.ND.01.002, IP.ND.01.003
- Status: TODO
- Implementation Class: Local/Demo-Safe

### IP.ND.01.005 — Verify Zero Customer-Visible Novelty

- Category: Verification
- Implementation Scope: Confirm that no novelty/differentiator feature is operational in the current codebase. Inspect all frontend files, routes, and components for any batching UI, group ordering flow, nutritional panel, loyalty/gamification UI, AI suggestion component, voice ordering, sustainability/eco badge, meal rescue/flash sale UI, smart locker, or dynamic delivery tier selector.
- Acceptance Criteria:
  - No batching UI element in any frontend file
  - No group ordering flow in any route or component
  - No nutritional panel in menu or item components
  - No loyalty/gamification UI surfacing `loyalty_points`
  - No AI suggestion component on homepage
  - No voice ordering mic button
  - No sustainability/eco badge or messaging
  - No meal rescue or flash sale UI
  - No smart locker or pickup point selection
  - No dynamic delivery tier selector at checkout
- Evidence Required:
  - Verification checklist with file-path evidence for each item
  - Grep/search results showing zero matches for novelty keywords
- Priority: P0
- Effort: S
- Dependency: NONE
- Status: TODO
- Implementation Class: Local/Demo-Safe

### IP.ND.01.006 — Document Batch Engine Integration Gaps

- Category: Audit / Documentation
- Implementation Scope: Detail every integration point missing between the batch engine algorithm and the operational delivery flow. Cover driver assignment gap, customer opt-in gap, route recalculation TODO, driver capacity check gap, and design-doc-only features (PrepSync, Thermal AI, Dynamic Tiers).
- Acceptance Criteria:
  - Driver assignment gap documented (`batch-engine` → `delivery-svc` missing)
  - Customer opt-in gap documented
  - Route recalculation TODO flagged
  - Driver capacity check gap documented
  - PrepSync/Thermal AI/Dynamic Tiers documented as design-doc-only
  - Evidence cited from Unique Value Assessment and Novel Delivery Engine Ideas
- Evidence Required:
  - Batch engine integration gap analysis document
  - Code references for each unintegrated point
- Priority: P1
- Effort: M
- Dependency: NONE
- Status: TODO
- Implementation Class: Local/Demo-Safe

---

## 16. Acceptance Criteria

- [ ] All 6 work items (IP.ND.01.001 through IP.ND.01.006) are completed and documented
- [ ] Feature parity matrix covers minimum 15 features across 4 competitors
- [ ] Design element inventory is complete for all 7 categories (color, typography, icons, spacing, cards, badges, trust)
- [ ] Baseline scorecard is created, locked, and stored as reference
- [ ] Zero customer-visible novelty is verified with checklist
- [ ] Batch engine integration gaps are fully documented
- [ ] All findings traceable to one of the four allowed source documents
- [ ] Differentiation score remains 1/10 (no score inflation)

---

## 17. Evidence Required

| Evidence Item | Format | Owner | Due With Work Item |
|---|---|---|---|
| Feature parity matrix | Markdown table | Engineering | IP.ND.01.001 |
| Design element inventory | Markdown + code refs | Design / Engineering | IP.ND.01.002 |
| Competitor parity table | Markdown table | Product | IP.ND.01.003 |
| Baseline scorecard (`ND_Scorecard_Baseline.md`) | Markdown document | Product / Engineering | IP.ND.01.004 |
| Zero-novelty verification checklist | Markdown checklist | Engineering | IP.ND.01.005 |
| Batch engine gap analysis | Markdown document | Engineering | IP.ND.01.006 |
| Sign-off record | Comment / approval | Product Owner, Engineering Lead | IP.ND.01.004 |

---

## 18. Dependencies

This plan has **no code dependencies** — it is purely documentation. It assumes:
- The four source audit documents are available and up to date
- The codebase has been read end-to-end (299 files verified)
- No additional exploratory analysis is required

| Dependency | Type | Status |
|---|---|---|
| `Micro_Audit_BhojanGo.md` | Source document | ✅ Available |
| `Micro_Audit_BhojanGo_v2.md` | Source document | ✅ Available |
| `BhojanGo_Novel_Delivery_Engine_Ideas.md` | Source document | ✅ Available |
| `BhojanGo_Unique_Value_Assessment.md` | Source document | ✅ Available |

---

## 19. Risks / Blockers

| Risk / Blocker | Likelihood | Impact | Mitigation (for ND.02+) |
|---|---|---|---|
| Batch engine remains unintegrated | High | Critical | Prioritize driver assignment wiring in ND.02 |
| Design system never replaces Tailwind defaults | Medium | High | Mandate design token adoption before any UI changes |
| Novelty ideas stay in design docs | High | Critical | Tie every ND plan to customer-visible delivery |
| Competitors implement batching first | Medium | Critical | Accelerate batch engine integration to P1 |
| Score inflation bias (wanting to claim 2/10) | Medium | High | Enforce external review of all ND score claims |

---

## 20. Exit Criteria

- All 6 work items (IP.ND.01.001 through IP.ND.01.006) are marked complete
- Baseline scorecard is created, reviewed, and locked
- Zero customer-visible novelty is verified and documented
- All findings are traceable to one of the four allowed source documents
- Product Owner and Engineering Lead have reviewed and acknowledged the 1/10 baseline
- Document is filed in `/implementation_plan/`

---

## 21. Connected Previous-Level Requirements

ND.01 is the first novelty/differentiation implementation plan. There is no prior ND level. The baseline established here connects to:

- **PR.01 (Core Loop Fix)** — PR plans address broken functionality; ND.01 documents that even working features are generic
- **Existing production roadmaps** — ND.01 does not conflict with production readiness work; it runs in parallel as pure documentation

---

## 22. Connected Next-Level Requirements

- **IP.ND.02** — Will build on this baseline by adding the first measurable differentiator. Must reference `ND_Scorecard_Baseline.md` and show clear delta from 1/10
- **IP.ND.03–ND.10** — Each subsequent plan updates the scorecard and increments the differentiation score with customer-visible features
- **Batch engine integration** — Likely the first major differentiator; ND.02+ must address the gaps documented in IP.ND.01.006

---

## 23. Self-Audit Checklist

| Check | Result | Notes |
|---|---|---|
| Uses only allowed source files | ✅ | |
| Does not re-audit repo | ✅ | |
| Does not require forbidden repo inspection | ✅ | |
| Scope is score-specific | ✅ | |
| Scope is implementation-ready | ✅ | |
| Acceptance criteria are testable | ✅ | |
| Evidence requirements are clear | ✅ | |
| Dependencies are listed | ✅ | |
| Risks/blockers are explicit | ✅ | |
| Connects to previous/next level | ✅ | |
| Avoids premature infra/external services | ✅ | |
| No generic advice / feature dumping | ✅ | |
| Self-score is assigned and ≥8 (otherwise revise) | ✅ | |

---

## 24. Self-Score

- Completeness: 9/10
- Implementation Readiness: 9/10
- Traceability: 9/10
- Practical Feasibility: 9/10
- Score-Level Discipline: 9/10
- Overall Document Score: 9/10
