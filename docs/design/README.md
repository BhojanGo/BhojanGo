# BhojanGo design pack

Source of truth for P16–P21. Live board: https://claude.ai/artifact/9hWrw4yoyoziZeNffAQgGi

- `screens/*.html` — every screen, as HTML with inline styles. Read the styles for exact
  colours, spacing, radii, sizes and copy. (They use a board runtime that isn't included;
  read them as markup, don't try to run them.) "Rider" = old "Courier", "Partner" = old "Merchant".
- `screens/Main.html`, `Spacing.html`, `Landscape.html` — design system: tokens, type, spacing.
- `screens/Brand*.html`, `StoreShots.html` — logo, icons, names, imagery, store screenshots.
- `logo/*.svg` — logo C (steaming "b"). viewBox 0 0 40 40. icon-* are the three app icons.

Tokens: Peacock #0B5D66 (deep #083F46, tint #DDEBEC, #EFF6F6) · Kohl #111418 ·
Kesar #D4932A / #E8A93C · Porcelain #F4F6F6 · lines #E2E7E8 / #C9D3D4 · secondary text #4C5A5E ·
Chili #B3261E. Rider dark theme: #0C1416, #142225, #1B2C2F, #24383B, #2E4447, text #F2F5F5 / #A9B8BA, link #7FCFD4.
Fonts: Familjen Grotesk (display), Hanken Grotesk (text). 4-pt grid; screen edges 20/24/32;
radii 8/16/24/pill; touch targets 48/56/64.
Never use red, orange, green or purple as brand colours (competitors own them).
