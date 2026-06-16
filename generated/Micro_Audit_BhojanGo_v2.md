 → 20% off" on homepage.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not present.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Seasonal banner visible with dates.

---

## BG.F.C003 — BhojanGo Design System (NEW)

### BG.F.C003.001 — No Visual Identity / Color Palette
- **Gap:** Generic Tailwind green (`emerald-600`). No brand identity.
- **Impact:** Looks like a generic template.
- **Scope:** Define palette:
  - Primary: `#E65100` (Warm Saffron) — not corporate green
  - Secondary: `#2E7D32` (Trust Green) — veg/health assurance
  - Accent: `#FFB300` (Nugget Gold) — CTA highlights
  - Neutral: `#F7F5F2` (Cream) — backgrounds
  - Dark: `#1A1A1A` (Near Black) — text
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Default Tailwind colors everywhere.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** CSS Custom Properties define palette. All components reference tokens.

### BG.F.C003.002 — Typography is Generic
- **Gap:** `font-sans` with system defaults.
- **Impact:** No brand voice.
- **Scope:** Import Manrope (headings) + Inter (body) from Google Fonts.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** No custom font import in layout.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Typography is distinctive and readable.

### BG.F.C003.003 — No Design Tokens for Spacing
- **Gap:** Random Tailwind values.
- **Scope:** 4px base grid. Cards: 16px padding inside, 24px gap. Buttons: 48px min tap height.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Inconsistent spacing.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Design documented in `packages/ui/design.md`.

### BG.F.C003.004 — No Icon Style Standard
- **Gap:** Mix of emoji and SVGs.
- **Scope:** Use Lucide React icons (thin stroke, 1.5px). Consistent 24px size.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Emoji peppers for spice, emoji checkmarks.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** No raw emoji in UI. Only Lucide icons.

### BG.F.C003.005 — No Badge Standard
- **Gap:** No badge anatomy.
- **Scope:** Pulsing "New" pill. "Bestseller" with star. "Under 30 min" with clock. Consistent border-radius 40px, padding 4px 12px, font-weight 600.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** No badges currently.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Badges consistent across site.

### BG.F.C003.006 — No Card Anatomy Standard
- **Gap:** Restaurant cards vary wildly.
- **Scope:** Anatomy: Image (16:10, rounded-xl top), Gradient overlay bottom → Name (h3), Cuisine Chips (row), Rating Badge (absolute top-right), Delivery Time Badge (absolute bottom-right).
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Cards basic.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** All cards follow anatomy.

### BG.F.C003.007 — Trust Elements Absent
- **Gap:** No hygiene, freshness, verified badges.
- **Impact:** Low trust in an app handling food.
- **Scope:** Add "FSSAI Verified", "Freshly Prepared", "Under 30 min" trust badges on restaurant cards.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Zero trust signals.
- **Evidence Strength:** High
- **Source:** Inferred from UX best practices
- **AC:** At least 3 trust markers visible per restaurant card.

---

## BG.F.U001 — UI/UX Interaction Gaps

### BG.F.U001.001 — No Page Transitions
- **Gap:** Instant hard navigation.
- **Scope:** Framer Motion `AnimatePresence` on route changes. Subtle fade + slide.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Page switch is abrupt.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Transitions smooth.

### BG.F.U001.002 — No Add-to-Cart Fly Animation
- **Gap:** Click, nothing visible.
- **Scope:** Item image shrinks and flies to cart icon. 300ms ease-out. Cart badge wobbles.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** No visual feedback.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** Clear visual on add.

### BG.F.U001.003 — No Responsive Breakpoints for TV
- **Gap:** 4K screen shows 1 narrow column.
- **Scope:** Add `2xl:grid-cols-5 3xl:grid-cols-6`.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Only basic breakpoints.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** 4K shows 6 columns.

### BG.F.U001.004 — No Offline Indicator
- **Gap:** Network failure invisible.
- **Scope:** Top banner "You're offline. Reconnect and try again."
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Nothing.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Banner appears on offline.

---

# BG.I — Integration / Flow Gaps

### BG.I001 — Onboarding Broken
- **Gap:** No onboarding after signup.
- **Scope:** 3-step: Set location → Pick cuisines → Done. <60 seconds.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** None.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** New user completes in <60s.

### BG.I002 — Reorder Flow Missing
- **Gap:** No "Order Again".
- **Scope:** "Reorder" button on order history card → pre-fills cart.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not present.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** One-tap reorder works.

### BG.I003 — Location / Address Handling Crude
- **Gap:** Manual entry only.
- **Scope:** Address autocomplete via Free Nominatim. Map pin selection.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Simple text input.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** Address typeahead works.

### BG.I004 — Cancellation / Refund Flow Not Integrated
- **Gap:** No cancel UI.
- **Scope:** Cancel button in order detail. Simulated refund.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not present.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** Cancel triggers refund.

### BG.I005 — Order State Machine Not Enforced
- **Gap:** Any status to any status.
- **Scope:** Valid transitions:
  `pending → confirmed → preparing → ready_for_pickup → picked_up → delivered`
  `cancelled` from `pending` or `confirmed` only.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** DB allows any string.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** Invalid transition returns 400.

### BG.I006 — Fees / Taxes Not Transparent
- **Gap:** Checkout breakdown missing.
- **Scope:** Always show: items, delivery, tax, discount, total.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Simple form.
- **Evidence Strength:** High
- **Source:** Inferred
- **AC:** Breakdown visible.

### BG.I007 — Availability / Open-Closed Not Enforced
- **Gap:** Closed restaurants shown.
- **Scope:** Compare opens_at/closes_at with current time.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not enforced.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Closed dimmed.

### BG.I008 — Serviceability Radius Not Enforced
- **Gap:** Any address accepted.
- **Scope:** Haversine check. If > radius, block.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not implemented.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Invalid address blocked.

---

# BG.N — Novelty / Differentiator Gaps (Demo-Safe)

### BG.N001 — Favorites + Reorder
- **Gap:** No bookmark.
- **Scope:** Heart toggle. "Favorites" row on homepage.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** None.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Toggle persists.

### BG.N002 — Loyalty Points Activation
- **Gap:** Points exist in DB but not surfaced.
- **Scope:** Earn 10% back. Wallet shows points. "Free delivery with 500 pts."
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** `loyalty_points` column seeded but unused.
- **Evidence Strength:** High
- **Source:** Code observation
- **AC:** Points visible. Redeemable for delivery fee.

### BG.N003 — Meal Rescue / End-of-Day Deals
- **Gap:** Unsold items discarded.
- **Scope:** 1h before close, "Flash Sale — 50% off" for remaining inventory.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not implemented.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Flash sale pushed as notification.

### BG.N004 — Group Order Link
- **Gap:** Only individual orders.
- **Scope:** "Start Group Order" → shareable link. Friends add items. Host pays.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** None.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Group link works.

### BG.N005 — Multi-Restaurant Order (Cart from Multiple Places)
- **Gap:** One restaurant per order.
- **Scope:** Cart accepts items from multiple restaurants. Split delivery fee.
- **Status:** 🟢 LOCAL/DEMO-SAFE
- **Evidence:** Not implemented.
- **Evidence Strength:** Medium
- **Source:** Inferred
- **AC:** Cart shows items from 2 restaurants.

### BG.N006 — Veg / Health / Nutrition Filters
- **Gap:** Only generic cuisine filters.
- **Scope:** 