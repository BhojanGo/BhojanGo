# BhojanGo design pack

Source of truth for P16–P21. Live board: https://claude.ai/artifact/9hWrw4yoyoziZeNffAQgGi

- `screens/*.html` — every screen, as HTML with inline styles. Read the styles for exact
  colours, spacing, radii, sizes and copy. (They use a board runtime that isn't included;
  read them as markup, don't try to run them.) "Rider" = old "Courier", "Partner" = old "Merchant".
- `screens/Main.html`, `Spacing.html`, `Landscape.html` — design system: tokens, type, spacing.
- `screens/Brand*.html`, `StoreShots.html` — logo, icons, names, imagery, store screenshots.
- `logo/*.svg` — logo C (steaming "b"). viewBox 0 0 40 40. icon-* are the three app icons.

Tokens: Peacock #0B5D66 (deep #083F46, tint #DDEBEC, #EFF6F6) · Kohl #111418 ·
Kesar #D4932A / #E8A93C · Porcelain #F4F6F6 · lines #E2E7E8 / #C9D3D4 · secondary text #3D4A4E (Round 8; the boards still show #4C5A5E) ·
Chili #B3261E. Rider dark theme: #0C1416, #142225, #1B2C2F, #24383B, #2E4447, text #F2F5F5 / #A9B8BA, link #7FCFD4.
Fonts (Round 8; the boards still draw the earlier Familjen / Hanken Grotesk): Inter for every
role, self-hosted (OFL), Noto Sans for Indian scripts. Fluid type scale, min px at a 360 px
viewport to max px at 1440 px: display 36-52 (700, -0.8 px) · h1 28-36 (700, -0.4 px) ·
h2 22-28 (700) · h3 17-20 (600) · body-lg 16-18 · body 15-16 · label 14-15 (600) · small 13-14 ·
caption 12 (700, uppercase, 0.06 em). The source is `packages/ui/tokens.js` (typeScale) and
`packages/mobile-core/src/ui/type.ts` (the apps scale by the screen's shorter side in dp).
Page content at most 1200 px wide, gutters 16 / 32 / 48 px (phone / tablet / desktop).
4-pt grid; screen edges 20/24/32; radii 8/16/24/pill; touch targets 48/56/64.
Never use red, orange, green or purple as brand colours (competitors own them).
