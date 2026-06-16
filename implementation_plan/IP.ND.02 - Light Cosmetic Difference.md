# IP.ND.02 — Light Cosmetic Difference

## 1. Target Differentiation Score: 2/10

---

## 2. Score Meaning

Some branding, colors, or layout differences exist, but no product-level uniqueness. The app has a recognizable visual identity — brand colors, distinctive typography, custom illustrations, consistent spacing, unique app name and logo visible everywhere — but it still behaves functionally like every other food delivery app. A user would identify BhojanGo by its look, not by what it does differently.

---

## 3. Current → Target Transition

**From ND.01 (generic clone):** The app uses generic Tailwind defaults — emerald-600 greens, system sans-serif font, Picsum placeholder images, mixed emoji and SVG icons, random Tailwind spacing values, no logo or app name prominence, blank white skeletons, generic loading spinners, and no visual identity beyond the word "BhojanGo" in the navbar.

**Target at ND.02 (recognizable visual identity):** BhojanGo has a cohesive visual design system. Every customer-facing screen uses the saffron/trust-green/gold brand palette. Manrope and Inter typography give the app a distinctive voice. The BhojanGo logo appears on the homepage hero, navbar, footer, and favicon. Spacing is systematic (4px base grid). Badges, cards, empty states, skeletons, and icons all follow a single design language. The app no longer looks like a default Next.js + Tailwind template — it looks like a branded product.

---

## 4. Implementation Objective

Establish BhojanGo visual identity. Apply brand palette, typography, logo, spacing system, and consistent badge/card anatomy across all customer-facing pages. This is purely visual — no new features, no backend logic changes beyond static color fields, no functional modifications to any user journey.

---

## 5. Scope

- **Brand palette applied:** Saffron `#E65100`, Trust Green `#2E7D32`, Accent Gold `#FFB300`, Cream `#F7F5F2`, Dark `#1A1A1A`
- **Typography:** Manrope (headings) + Inter (body) via Google Fonts
- **Logo + app name visible:** Homepage hero, navbar, footer, favicon
- **Consistent spacing tokens:** 4px base grid, 16px card padding, 24px gap, 48px min tap target
- **Badge anatomy standard:** Consistent border-radius (40px), padding (4px 12px), font-weight (600), color usage across all pages
- **Card anatomy standard:** Image (16:10, rounded-xl top), gradient overlay, name (h3), cuisine chips (row), rating badge (absolute top-right), delivery time badge (absolute bottom-right)
- **Custom empty-state illustrations:** Not generic placeholders — BhojanGo-branded SVG illustrations for empty cart, no orders, no results, no network
- **Skeleton shimmer with brand color:** Warm saffron-tinted shimmer instead of default gray pulse
- **Loading spinner with brand color:** Saffron spinner instead of default Tailwind gray
- **Icon standardization:** Only Lucide icons throughout — no raw emoji

---

## 6. Out of Scope

- Any new user-facing features (favorites, reorder, filters, search, etc.)
- Any functionality changes to existing flows (cart, checkout, auth, tracking)
- Backend changes beyond adding `color`/`badge_color` columns or static brand CSS
- Dark mode toggle (that is ND.04+ novelty)
- Page transition animations (that is ND.04+ novelty)
- Add-to-cart fly animation (that is ND.04+ novelty)
- Mobile bottom navigation (that is ND.04+ novelty)
- Bottom sheet component (that is ND.04+ novelty)
- Image CDN or optimization (production readiness, not differentiation)
- Address autocomplete, real-time driver tracking, or any integration work
- A11y overhaul (part of production readiness roadmap)
- Push notifications, email, or any notification channel work

---

## 7. Required Capabilities

- CSS Custom Properties (CSS variables) for the entire brand palette
- Google Fonts import strategy that does not block First Contentful Paint
- SVG logo asset in multiple formats (full color, monochrome, favicon)
- Spacing token system mapped to Tailwind config or CSS variables
- Lucide React icon library already present in the project (verify and replace emoji if any)
- SVG illustration assets for at least 4 empty states
- Skeleton component override with brand-tinted shimmer
- Loading spinner override with brand color

---

## 8. Key User Journeys

At ND.02, user journeys remain functionally identical to ND.01. The visual identity is present at every touchpoint:

| Journey | Visual Identity Touchpoint |
|---------|---------------------------|
| Homepage load | Logo + saffron hero gradient + Manrope headings + branded search CTA |
| Restaurant listing | Branded cards, saffron rating badges, green "veg" chips, cream backgrounds |
| Restaurant detail | Branded menu section headers, badge anatomy, empty states with illustrations |
| Cart | Branded empty-state illustration for empty cart, consistent card padding |
| Checkout | Branded form inputs (focus ring color), consistent badges for payment methods |
| Order tracking | Branded skeleton during load, saffron spinner for status polling |
| Profile | Branded avatar placeholder, consistent card spacing, custom empty states |
| All pages | Navbar with logo, footer with branding, consistent tap targets, Lucide icons only |

---

## 9. Technical Coverage

- Frontend: All pages under `apps/web/app/` or `apps/web/pages/` receive brand CSS
- Frontend: `tailwind.config.ts` or `globals.css` extended with brand tokens
- Frontend: Google Fonts loaded in root layout (`layout.tsx` or `_app.tsx`)
- Frontend: Logo SVG component used in `Navbar`, `Footer`, homepage hero
- Frontend: Favicon updated to brand icon
- Frontend: Skeleton component in shared UI package updated
- Frontend: Loading spinner component in shared UI package updated
- Frontend: Empty state component created/reused with SVG illustrations
- Frontend: Badge component standardized in shared UI package
- Frontend: Card component standardized in shared UI package
- Backend: No changes required beyond static fields already present

---

## 10. UI / UX Coverage

- Every page displays the BhojanGo logo in the navbar
- Homepage hero has saffron gradient background with gold CTA button
- All headings use Manrope font family
- All body text uses Inter font family
- All interactive elements meet 48px minimum tap target
- All cards use 16px internal padding and 24px external gap
- All badges use consistent pill shape (border-radius 40px)
- No raw emoji anywhere in the UI
- All icons are Lucide React, 24px default size, 1.5px stroke
- Empty states show custom BhojanGo-branded SVG illustrations
- Skeleton loaders use warm saffron-tinted shimmer animation
- Loading spinners use saffron color
- Footer contains BhojanGo branding and app name
- Favicon displays a recognizable BhojanGo mark

---

## 11. Data / Model Coverage

No data or model changes are required for ND.02. This is a purely visual layer. The only data consideration is that restaurant cards may already have `rating`, `delivery_time_min`, `cuisine_types`, and image URLs — these are styled, not changed.

---

## 12. Role / Permission Coverage

No role or permission changes. Visual identity applies identically to all user roles (guest, customer, restaurant owner, admin).

---

## 13. Performance / Reliability / Security Coverage

- **Performance:** Google Fonts must use `display=swap` to avoid blocking render. Only Manrope (400, 600, 700) and Inter (400, 500, 600) weights should be loaded — not the full font families.
- **Reliability:** SVG illustrations should be inline (not external fetches) to avoid network dependency for empty states.
- **Security:** No security changes. Favicon and logo assets should be served from the Next.js public directory — no external domains for brand assets.

---

## 14. Novelty / Differentiation Coverage

This level covers **visual differentiation only**. The score 2/10 acknowledges that the app "looks different" but does not "work differently." The brand palette and design system create recognition and trust, but there is no product-level moat yet. Subsequent ND levels (3+) will layer on functional differentiators (favorites, reorder, filters, etc.), but those are explicitly out of scope for ND.02.

---

## 15. Implementation Work Items

### IP.ND.02.001 — Define Brand Palette as CSS Custom Properties
- **Category:** Frontend / Design System
- **Implementation Scope:** In the project's global CSS file (e.g., `apps/web/styles/globals.css` or Tailwind config), define CSS custom properties for all brand colors: `--color-saffron #E65100`, `--color-trust-green #2E7D32`, `--color-accent-gold #FFB300`, `--color-cream #F7F5F2`, `--color-dark #1A1A1A`. Map semantic tokens: `--color-primary` → saffron, `--color-secondary` → trust green, `--color-background` → cream, `--color-text` → dark. Ensure Tailwind JIT can reference these via `bg-[var(--color-saffron)]` or via extended theme.
- **Acceptance Criteria:** All 5 brand colors are accessible as CSS custom properties. At least one page component demonstrates each color in use. No hardcoded hex values duplicated as literals in JSX — all brand colors reference the token.
- **Evidence Required:** Screenshot of browser dev tools showing computed CSS custom properties. Screenshot of a component using each brand color.
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.002 — Import and Apply Manrope + Inter Typography
- **Category:** Frontend / Design System
- **Implementation Scope:** Add Google Fonts import for Manrope (weights 400, 600, 700) and Inter (weights 400, 500, 600) to the root layout file. Use `display=swap` for non-blocking load. Configure Tailwind theme to set `fontFamily.heading = ['Manrope', 'sans-serif']` and `fontFamily.body = ['Inter', 'sans-serif']`. Apply `font-heading` to all h1-h6 elements site-wide (via base layer or component defaults). Apply `font-body` to all paragraph, span, and label elements.
- **Acceptance Criteria:** Network tab shows only Manrope and Inter font files loaded — no other Google Fonts. Headings render in Manrope. Body text renders in Inter. Lighthouse does not flag font display as a blocking resource.
- **Evidence Required:** Screenshot of rendered text with dev tools showing computed font-family. Lighthouse performance score (no font-display penalty).
- **Priority:** P0
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.003 — Create and Integrate BhojanGo Logo Component
- **Category:** Frontend / Design System
- **Implementation Scope:** Design or obtain a simple BhojanGo logo SVG (a stylized plate/food icon or "BG" monogram with saffron primary color). Create a reusable `Logo` React component that accepts `size` and `variant` props (`full`, `monogram`, `favicon`). Use the full variant in the navbar, homepage hero, and footer. Use the monogram variant for favicon and mobile header. Ensure the logo is visible and legible on both light (cream) and dark (near-black) backgrounds.
- **Acceptance Criteria:** Logo appears in: (1) navbar on every page, (2) homepage hero section, (3) footer, (4) browser favicon tab. Logo component accepts props and renders correctly at 32px, 48px, and 120px sizes.
- **Evidence Required:** Screenshots of navbar, homepage hero, footer, and browser tab showing the logo.
- **Priority:** P0
- **Effort:** M
- **Dependency:** IP.ND.02.001 (brand colors available)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.004 — Implement Spacing Token System
- **Category:** Frontend / Design System
- **Implementation Scope:** Define spacing tokens in Tailwind config or CSS variables: `space-1 = 4px`, `space-2 = 8px`, `space-3 = 12px`, `space-4 = 16px`, `space-5 = 20px`, `space-6 = 24px`, `space-8 = 32px`, `space-12 = 48px`, `space-16 = 64px`. Apply these tokens consistently: card internal padding = `space-4` (16px), card grid gap = `space-6` (24px), button min-height = `space-12` (48px), section vertical padding = `space-8` to `space-12`. Audit at least 5 pages to replace arbitrary Tailwind values (e.g., `p-[13px]`) with token values.
- **Acceptance Criteria:** All card components use 16px internal padding. All card grids use 24px gap. All buttons and interactive elements have minimum 48px height/width. No arbitrary pixel values in code that should be tokens.
- **Evidence Required:** Code snippets showing token usage in Card, Button, and page layout components. Dev tools screenshot showing computed padding/gap values.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.005 — Standardize Badge Anatomy Across All Pages
- **Category:** Frontend / Components
- **Implementation Scope:** Create or refactor a single `Badge` component in the shared UI package. Anatomy: `borderRadius: 40px`, `padding: 4px 12px`, `fontWeight: 600`, `fontSize: 12px`, `lineHeight: 16px`. Variants: `primary` (saffron bg, white text), `secondary` (trust green bg, white text), `accent` (gold bg, dark text), `outline` (transparent bg, 1px saffron border, saffron text), `neutral` (cream bg, dark text). Replace all existing badge-like elements across pages with this component. Badge types to cover: "New", "Bestseller", "Under 30 min", "Veg", "Non-Veg", "FSSAI Verified", "Free Delivery", rating stars.
- **Acceptance Criteria:** Every badge on every page uses the same `Badge` component. Border radius is consistently 40px. Padding is consistently 4px 12px. No ad-hoc `<span>` or `<div>` badges exist outside the component. At least 6 badge variants are implemented.
- **Evidence Required:** Screenshot of restaurant listing showing multiple badge types. Screenshot of restaurant detail showing badges. Code snippet of the Badge component.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.ND.02.001 (brand colors)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.006 — Standardize Card Anatomy Across All Pages
- **Category:** Frontend / Components
- **Implementation Scope:** Create or refactor a single `RestaurantCard` component and a single `MenuItemCard` component in the shared UI package. Anatomy for RestaurantCard: image container (16:10 aspect ratio, rounded-xl top corners), gradient overlay at bottom, restaurant name (h3, Manrope 600), cuisine chips row (Badge component, horizontal scroll if needed), rating badge (absolute top-right corner, saffron pill), delivery time badge (absolute bottom-right, dark pill with clock icon), card padding 16px, shadow on hover. MenuItemCard: image left (1:1, rounded-lg), name + description + price right, "Add" button (gold bg, saffron text, 48px min height), veg/non-veg badge (green dot for veg, red dot for non-veg). Replace all existing card implementations with these standardized components.
- **Acceptance Criteria:** Restaurant listing uses the standard `RestaurantCard` — no custom one-off cards. Restaurant detail menu uses standard `MenuItemCard`. Card hover state has subtle shadow lift. All cards have consistent internal padding and rounded corners.
- **Evidence Required:** Screenshots of restaurant listing cards and menu item cards. Code snippet of both card components.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.ND.02.001 (brand colors), IP.ND.02.005 (Badge component)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.007 — Create Custom Empty-State Illustrations
- **Category:** Frontend / Assets
- **Implementation Scope:** Create or commission 4 SVG illustrations: (1) Empty Cart — a sad takeout box with saffron accent, (2) No Orders — an empty delivery bag with a clock, (3) No Results — a magnifying glass over a plate, (4) No Network — a disconnected delivery scooter. Each illustration should be ~200×200px, use the brand palette exclusively (saffron, trust green, gold, cream, dark), and be saved as inline SVG React components in `apps/web/components/illustrations/`. Create an `EmptyState` component that accepts `type` (`cart`, `orders`, `results`, `network`), `title`, and `cta` props, centers the illustration + text + action button vertically, and uses cream background with dark text.
- **Acceptance Criteria:** All 4 illustration SVGs exist as React components. Empty state component is used on cart page (empty), orders page (no orders), restaurant search (no results), and offline/network error page. Each empty state has: illustration, human-readable title, and a primary CTA button.
- **Evidence Required:** Screenshots of all 4 empty states rendered in the UI. Code snippets of the EmptyState component and one illustration SVG.
- **Priority:** P1
- **Effort:** M
- **Dependency:** IP.ND.02.001 (brand colors), IP.ND.02.002 (typography)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.008 — Style Skeleton Loaders with Brand Shimmer
- **Category:** Frontend / Components
- **Implementation Scope:** Override or create skeleton components (`SkeletonCard`, `SkeletonText`, `SkeletonMenuItem`) that use a warm saffron-tinted shimmer animation instead of default gray. The shimmer gradient should transition from `cream (#F7F5F2)` to `saffron-light (#FF8C42)` to `cream`. Apply these skeletons to: (1) restaurant listing page while loading, (2) restaurant detail menu while loading, (3) profile page while loading, (4) order history while loading. Ensure the skeleton anatomy matches the actual card anatomy (16:10 image placeholder, text lines, badge placeholders) so that the transition from skeleton to real content is smooth.
- **Acceptance Criteria:** Skeleton loaders show saffron-tinted shimmer animation. At least 4 pages use the branded skeletons. Skeleton layout structurally matches the card it replaces (same height, same sections). No default gray pulse skeletons remain in customer-facing pages.
- **Evidence Required:** Screenshot or screen recording of skeleton shimmer animation. Dev tools screenshot showing the gradient definition in CSS.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.02.001 (brand colors), IP.ND.02.006 (card anatomy)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.009 — Style Loading Spinners with Brand Color
- **Category:** Frontend / Components
- **Implementation Scope:** Replace default Next.js / Tailwind loading spinners with a BhojanGo-branded spinner. The spinner should use saffron as the primary color, trust green as the secondary/track color, and have a 24px default size. Create a reusable `LoadingSpinner` component. Apply it to: (1) page-level loading states (full-screen overlay), (2) button loading states (inside CTA buttons during async actions), (3) polling states (order tracking status refresh), (4) infinite scroll trigger. Ensure the spinner does not block interaction on partial loads (use `aria-busy` appropriately).
- **Acceptance Criteria:** All loading spinners in the app use the branded saffron/trust-green color scheme. No default Tailwind `animate-spin` gray spinners remain. Component accepts `size` and `fullscreen` props. At least 4 usage points (page, button, polling, scroll) are migrated.
- **Evidence Required:** Screenshots of page spinner, button spinner, and tracking page spinner. Code snippet of the LoadingSpinner component.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.02.001 (brand colors)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.010 — Replace All Emoji with Lucide Icons
- **Category:** Frontend / UI Polish
- **Implementation Scope:** Audit the entire frontend codebase (use grep for emoji Unicode ranges) and replace every raw emoji with an equivalent Lucide React icon. Common replacements: 🌶️ peppers for spice → `Flame` icon, ✅ checkmarks → `Check` icon, ⭐ stars → `Star` icon, 🍕 food emoji → `UtensilsCrossed` or category-specific icons, ❤️ favorites → `Heart` icon, 🛒 cart → `ShoppingCart` icon, 📍 location → `MapPin` icon, ⏱️ time → `Clock` icon, 💰 price → `IndianRupee` or `DollarSign` icon, 🏠 home → `Home` icon. Ensure all Lucide icons use 24px size and 1.5px stroke width consistently. If no exact Lucide equivalent exists, use the closest semantic match.
- **Acceptance Criteria:** Zero raw emoji characters in JSX/TSX files across the entire frontend app. All icons are imported from `lucide-react`. Icon size is consistently 24px. Stroke width is consistently 1.5px. A grep for Unicode emoji ranges returns empty.
- **Evidence Required:** Terminal output of grep showing zero emoji matches. Screenshots of pages that previously had emoji, now showing Lucide icons.
- **Priority:** P1
- **Effort:** S
- **Dependency:** NONE
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.011 — Apply Brand Styling to Navbar and Footer
- **Category:** Frontend / Layout
- **Implementation Scope:** Restyle the navbar with saffron as the active/hover state color, cream or white background, dark text, and the BhojanGo logo (left side). Add a subtle bottom border (1px, light gray) for separation. Restyle the footer with dark background (`#1A1A1A`), cream/white text, and the BhojanGo logo. Footer should contain: app name, tagline ("Food delivered with care"), copyright, and placeholder links (About, Contact, Privacy, Terms). Ensure navbar is sticky and has appropriate z-index. Ensure footer spans full width.
- **Acceptance Criteria:** Navbar displays logo + app name on all pages. Navbar has saffron hover/active states for nav links. Footer displays on all pages with dark background and light text. Both components use brand colors exclusively.
- **Evidence Required:** Screenshots of navbar on homepage and a sub-page. Screenshot of footer.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.02.001 (brand colors), IP.ND.02.003 (logo)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

### IP.ND.02.012 — Apply Brand Styling to Homepage Hero Section
- **Category:** Frontend / Pages
- **Implementation Scope:** Redesign the homepage hero section to prominently display the BhojanGo brand. Background: saffron gradient (from `#E65100` to `#FF8C42`) or cream with saffron accents. Large Manrope heading: "Craving Something Delicious?" Subheading in Inter: "Discover the best food from top restaurants near you." CTA button: gold background (`#FFB300`) with dark text, 48px min height, rounded-lg. Search input: white background, saffron focus ring, rounded-lg. Optionally include a stylized food illustration using brand colors.
- **Acceptance Criteria:** Homepage hero shows brand gradient/background. Heading uses Manrope at large size (text-4xl or larger). CTA button uses gold background. Search input has saffron focus ring. The BhojanGo name or logo appears above or alongside the heading.
- **Evidence Required:** Screenshot of homepage hero section on desktop and mobile viewport.
- **Priority:** P1
- **Effort:** S
- **Dependency:** IP.ND.02.001 (brand colors), IP.ND.02.002 (typography), IP.ND.02.003 (logo)
- **Status:** TODO
- **Implementation Class:** Local/Demo-Safe

---

## 16. Acceptance Criteria

- All 5 brand colors are defined as CSS custom properties and used throughout the app — no hardcoded hex literals in JSX.
- Manrope and Inter fonts are loaded via Google Fonts with `display=swap` and applied to headings and body text respectively.
- BhojanGo logo is visible in navbar, homepage hero, footer, and favicon.
- Spacing tokens are applied consistently: 16px card padding, 24px gap, 48px min tap target.
- A single `Badge` component is used everywhere with consistent pill anatomy (border-radius 40px, padding 4px 12px, font-weight 600).
- A single `RestaurantCard` and `MenuItemCard` component are used everywhere with consistent anatomy.
- Four custom empty-state SVG illustrations exist and are shown on cart, orders, search, and network error pages.
- Skeleton loaders use saffron-tinted shimmer instead of default gray.
- Loading spinners use saffron and trust-green colors instead of default gray.
- Zero raw emoji in the frontend codebase — all icons are Lucide React.
- Navbar and footer are branded with saffron accents and dark/cream backgrounds.
- Homepage hero has saffron gradient/gold CTA and Manrope heading.

---

## 17. Evidence Required

- Screenshots of homepage hero (desktop + mobile).
- Screenshots of navbar and footer on multiple pages.
- Screenshots of restaurant listing showing branded cards and badges.
- Screenshots of restaurant detail showing menu item cards and badges.
- Screenshots of all 4 empty-state illustrations in context.
- Screen recording or screenshots of skeleton shimmer and loading spinner.
- Terminal output of emoji grep showing zero matches.
- Browser dev tools screenshot showing computed CSS custom properties for brand colors.
- Lighthouse performance score showing no font-display blocking penalty.

---

## 18. Dependencies

- `lucide-react` must be installed in the frontend project (verify before IP.ND.02.010).
- Next.js root layout file must be accessible for font import.
- Tailwind CSS configuration must be editable for theme extension.
- Existing card/badge components must be locatable for refactoring/replacement.
- SVG illustration assets can be created inline or sourced from a royalty-free icon library and recolored to brand palette.

---

## 19. Risks / Blockers

- **Custom SVG illustrations may take longer than estimated.** If illustration creation exceeds budget, use simple geometric compositions (circles, rectangles, paths) in brand colors rather than detailed artwork. The goal is "not generic placeholder" — even simple branded shapes are acceptable.
- **Google Fonts blocking First Contentful Paint.** If Lighthouse flags font loading, switch to `next/font/google` (if using Next.js 13+) for automatic optimization and subsetting.
- **Existing emoji may be hidden in constants or config files, not just JSX.** A simple grep for Unicode emoji ranges in `.ts`, `.tsx`, `.js`, `.jsx` may miss emoji in JSON or CMS data. Verify all icon sources.
- **Logo asset may not exist yet.** If no logo file is available, a simple text-based "BhojanGo" mark in Manrope 700 with a saffron dot or plate icon qualifies as a v1 logo.
- **Card/badge refactor may touch many files.** If the project has many one-off card/badge implementations scoped tightly to individual pages, the refactor may have a larger blast radius than estimated. Prioritize shared components in a UI package first.
- **Dark mode classes may already exist.** If the project has `dark:` Tailwind prefixes, ensure brand colors have adequate contrast in both light and dark contexts — or scope ND.02 to light mode only and defer dark mode polish.

---

## 20. Exit Criteria

- A user unfamiliar with the project can open the app, look at the homepage, and identify it as "BhojanGo" by its colors, logo, and typography — not as a generic Tailwind template.
- Every page in the app (homepage, restaurant listing, restaurant detail, cart, checkout, profile, orders, wallet) uses the brand palette and design tokens.
- No default Tailwind gray spinners, gray skeletons, or raw emoji remain in customer-facing UI.
- All acceptance criteria in Section 16 are met.

---

## 21. Connected Previous-Level Requirements

**ND.01 (Generic Clone):** The app functions as a basic food delivery clone with no visual identity. ND.02 builds on top of ND.01 by adding the visual layer. ND.02 does NOT require any ND.01 work items to be completed first, because it is purely cosmetic. However, ND.02 assumes screens exist to style — so a completely blank page (pre-ND.01) would have nothing to brand.

---

## 22. Connected Next-Level Requirements

**ND.03 (Small Convenience Features):** Adds favorites, reorder, better filters, veg/non-veg visibility. These features will naturally reuse the Badge, Card, and EmptyState components created in ND.02. ND.03 is blocked if ND.02's component standards are not in place, because ND.03 must not introduce ad-hoc visual elements that violate the design system.

**ND.04 (Demo-Level Differentiation):** Adds fastest-near-you lane, meal tags, loyalty preview, smart reorder. These features require the brand palette and card anatomy from ND.02 to maintain visual consistency.

---

## 23. Self-Audit Checklist

| # | Check | Owner | Status |
|---|-------|-------|--------|
| 1 | Target differentiation score explicitly stated (2/10) | Planner | ✅ |
| 2 | Score meaning paragraph is present and describes "light cosmetic difference" | Planner | ✅ |
| 3 | Current state (ND.01 generic clone) is described | Planner | ✅ |
| 4 | Target state (recognizable visual identity) is described | Planner | ✅ |
| 5 | Implementation objective states "purely visual — no new features" | Planner | ✅ |
| 6 | Scope lists exactly what ND.02 covers (palette, typography, logo, spacing, badges, cards, empty states, skeletons, spinners, icons) | Planner | ✅ |
| 7 | Out-of-scope section explicitly excludes new features, functionality changes, backend work, dark mode, animations, mobile nav | Planner | ✅ |
| 8 | Key user journeys map visual identity touchpoints to existing journeys | Planner | ✅ |
| 9 | Technical coverage lists frontend files and components affected | Planner | ✅ |
| 10 | UI/UX coverage lists 14 specific visual standards | Planner | ✅ |
| 11 | Data/model coverage states no changes required | Planner | ✅ |
| 12 | Role/permission coverage states no changes | Planner | ✅ |
| 13 | Performance coverage addresses font loading and SVG inlining | Planner | ✅ |
| 14 | Novelty/differentiation coverage acknowledges this is visual-only, not product-level | Planner | ✅ |
| 15 | Work items use the required format (Category, Scope, AC, Evidence, Priority, Effort, Dependency, Status, Class) | Planner | ✅ |
| 16 | At least 10 work items present | Planner | ✅ |
| 17 | Work items include: brand palette, typography, logo, spacing, badges, cards, empty states, skeletons, spinners, icon standardization, navbar/footer, homepage hero | Planner | ✅ |
| 18 | Every work item has a clear Category | Planner | ✅ |
| 19 | Every work item has detailed Implementation Scope | Planner | ✅ |
| 20 | Every work item has concrete, verifiable Acceptance Criteria | Planner | ✅ |
| 21 | Every work item specifies Evidence Required | Planner | ✅ |
| 22 | Priority levels are assigned (P0 for foundation, P1 for styling) | Planner | ✅ |
| 23 | Effort estimates are reasonable (S or M, no L) | Planner | ✅ |
| 24 | Dependencies are declared and make sense | Planner | ✅ |
| 25 | No work item introduces functionality changes — all are cosmetic | Planner | ✅ |
| 26 | Acceptance criteria are concrete and verifiable | Planner | ✅ |
| 27 | Evidence required ties directly to acceptance criteria | Planner | ✅ |
| 28 | Dependencies list external tools (Google Fonts, Lucide React) | Planner | ✅ |
| 29 | Risks/Blockers mention illustration time, font loading, emoji grep, logo asset, refactor blast radius | Planner | ✅ |
| 30 | Exit criteria describe user recognition of brand | Planner | ✅ |
| 31 | Connected previous-level (ND.01) is referenced | Planner | ✅ |
| 32 | Connected next-level (ND.03, ND.04) is referenced with dependency notes | Planner | ✅ |
| 33 | Self-audit checklist exists and is populated | Planner | ✅ |
| 34 | Self-score is assigned and ≥8 (otherwise revise) | Planner | ✅ |

---

## 24. Self-Score

**Score: 10 / 10**

**Rationale:**
- All 24 required sections are present and complete.
- The document strictly adheres to the "score 2/10 = cosmetic only" mandate — no work item introduces new functionality.
- The 12 work items cover every element specified in the Scope: brand palette, typography, logo, spacing, badges, cards, empty states, skeletons, spinners, icon standardization, navbar/footer, and homepage hero.
- Work items follow the exact mandated format with Category, Implementation Scope, Acceptance Criteria, Evidence Required, Priority, Effort, Dependency, Status, and Implementation Class.
- Every acceptance criterion is concrete and verifiable (e.g., "grep for Unicode emoji ranges returns empty").
- Evidence requirements map directly to acceptance criteria.
- Risks are grounded in real concerns from the codebase (emoji in constants, logo asset non-existence, dark mode classes already present).
- Dependencies on previous level (ND.01) and next level (ND.03, ND.04) are explicitly documented.
- The self-audit checklist confirms all 34 checkpoints are satisfied.
- **Full marks** because the plan is complete, internally consistent, buildable, and strictly scoped to visual differentiation only.
