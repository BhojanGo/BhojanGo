// BhojanGo design tokens (P16). The one source for web (Tailwind preset), the
// Expo apps (mobile-core) and anything else that draws. Values come from the
// design pack: docs/design/README.md, screens/Main.html and Spacing.html.
// Never use red, orange, green or purple as brand colours.

const color = {
  peacock: "#0B5D66", // brand, actions
  peacockDeep: "#083F46",
  peacockTint: "#DDEBEC",
  peacockMist: "#EFF6F6",
  kohl: "#111418", // text
  kesar: "#D4932A", // seasoning: offers, stars, never a full button
  kesarBright: "#E8A93C", // rider CTA
  porcelain: "#F4F6F6", // app ground
  white: "#FFFFFF",
  line: "#E2E7E8",
  lineStrong: "#C9D3D4",
  divider: "#EEF1F1",
  muted: "#4C5A5E", // secondary text
  faint: "#7A878A", // struck-through prices
  chili: "#B3261E", // alerts only
  plate: "#F6E7CC", // food image ground
  mapGround: "#E9EEEE",
};

// Rider app (dark theme).
const dark = {
  ground: "#0C1416",
  surface: "#142225",
  raised: "#1B2C2F",
  line: "#24383B",
  lineStrong: "#2E4447",
  text: "#F2F5F5",
  muted: "#A9B8BA",
  link: "#7FCFD4",
};

// 4-point grid. Names say what they're for (Spacing.html).
const space = {
  1: 4, // icon to label
  2: 8, // label to field, chip gap
  3: 12, // between list cards, heading to content
  4: 16, // card padding (mobile)
  5: 20, // screen edge (phone)
  6: 24, // card padding (tablet, web), group gap
  8: 32, // between sections
  12: 48, // page top (web)
};

const radius = { chip: 8, card: 16, sheet: 24, pill: 999 };

// Minimum touch targets: 48 any control, 56 primary actions, 64 rider actions.
const touch = { min: 48, primary: 56, rider: 64 };

const font = {
  display: "Familjen Grotesk", // display, h1, h2 (weight 600)
  text: "Hanken Grotesk", // everything else (400, 600, 700), tabular figures for money
  // Indian scripts fall back to Noto Sans <script> (Marathi uses Devanagari).
  scripts: {
    devanagari: "Noto Sans Devanagari",
    telugu: "Noto Sans Telugu",
    tamil: "Noto Sans Tamil",
    kannada: "Noto Sans Kannada",
    bengali: "Noto Sans Bengali",
  },
};

// The type scale (Round 6): the ONLY font sizes allowed on the web, admin and
// the apps. px values; `phone` applies below 768 px on the web and always in the
// apps. Weights: display, h1, h2, h3, label 600; body 400; caption 700.
// caption is for uppercase labels and badges only; nothing readable under 14.
// Web: Tailwind classes text-display ... text-caption (tailwind-preset.js).
const typeScale = {
  display: { desktop: 64, phone: 44, weight: "600", family: "display", lineHeight: 1.05, tracking: -0.02 },
  h1: { desktop: 40, phone: 30, weight: "600", family: "display", lineHeight: 1.1, tracking: -0.015 },
  h2: { desktop: 28, phone: 22, weight: "600", family: "display", lineHeight: 1.2, tracking: -0.01 },
  h3: { desktop: 20, phone: 18, weight: "600", family: "text", lineHeight: 1.3, tracking: 0 },
  "body-lg": { desktop: 18, phone: 17, weight: "400", family: "text", lineHeight: 1.5, tracking: 0 },
  body: { desktop: 16, phone: 16, weight: "400", family: "text", lineHeight: 1.5, tracking: 0 },
  label: { desktop: 15, phone: 15, weight: "600", family: "text", lineHeight: 1.4, tracking: 0 },
  small: { desktop: 14, phone: 14, weight: "400", family: "text", lineHeight: 1.45, tracking: 0 },
  caption: { desktop: 12, phone: 12, weight: "700", family: "text", lineHeight: 1.3, tracking: 0.06, uppercase: true },
};

/** Every allowed font size in px (what the page checks and the lint rule enforce). */
const fontSizes = [...new Set(Object.values(typeScale).flatMap((t) => [t.desktop, t.phone]))].sort((a, b) => b - a);

// Legacy app scale, still read by packages/mobile-core until it moves to typeScale.
// Do not use on the web.
const type = {
  hero: { size: 34, weight: "600", tracking: -1, family: "display" },
  h1: { size: 24, weight: "600", tracking: -0.5, family: "display" },
  h2: { size: 22, weight: "600", tracking: -0.4, family: "display" },
  title: { size: 20, weight: "600", tracking: -0.3, family: "display" },
  body: { size: 16, weight: "400", tracking: 0, family: "text" },
  label: { size: 14, weight: "700", tracking: 0, family: "text" },
  small: { size: 13, weight: "400", tracking: 0, family: "text" },
  tag: { size: 11, weight: "700", tracking: 0.4, family: "text" },
  eyebrow: { size: 12, weight: "700", tracking: 1.2, family: "text" },
};

const shadow = {
  float: "0 1px 2px rgba(17, 20, 24, 0.06), 0 8px 24px rgba(17, 20, 24, 0.08)",
  sheet: "0 -8px 40px rgba(17, 20, 24, 0.12)",
  bar: "0 12px 32px rgba(17, 20, 24, 0.28)",
};

const layout = {
  phone: { columns: 4, edge: 20, gap: 12 },
  tablet: { columns: 8, edge: 24, gap: 16 },
  web: { columns: 12, edge: 32, gap: 24, maxWidth: 1280, sideMenu: 248 },
};

module.exports = { color, dark, space, radius, touch, font, typeScale, fontSizes, type, shadow, layout };
