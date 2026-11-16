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
  muted: "#3D4A4E", // secondary text: 9.4:1 on white, 8.6:1 on porcelain
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
  // Inter (OFL), self-hosted: @fontsource-variable/inter on the web and admin,
  // @expo-google-fonts/inter in the apps. One family for every role.
  text: "Inter",
  display: "Inter", // kept for older imports: the same family as text
  // Indian scripts fall back to Noto Sans <script> (Marathi uses Devanagari).
  scripts: {
    devanagari: "Noto Sans Devanagari",
    telugu: "Noto Sans Telugu",
    tamil: "Noto Sans Tamil",
    kannada: "Noto Sans Kannada",
    bengali: "Noto Sans Bengali",
  },
};

// The type scale (Round 8): the ONLY font sizes allowed on the web, admin and the
// apps. Sizes are fluid: `min` px at a 360 px wide viewport, `max` px at 1440 px,
// linear in between (CSS clamp() on the web; the screen's shorter side in dp in
// the apps). Weights: display/h1/h2 700, h3/label 600, body-lg/body/small 400,
// caption 700. Tracking in px (display -0.8, h1 -0.4), caption 0.06em uppercase.
// caption is for uppercase labels and badges only; nothing readable under 13.
// Web: Tailwind classes text-display ... text-caption (tailwind-preset.js).
const fluid = { minWidth: 360, maxWidth: 1440 };
const typeScale = {
  display: { min: 36, max: 52, weight: "700", lineHeight: 1.1, tracking: -0.8 },
  h1: { min: 28, max: 36, weight: "700", lineHeight: 1.15, tracking: -0.4 },
  h2: { min: 22, max: 28, weight: "700", lineHeight: 1.2, tracking: 0 },
  h3: { min: 17, max: 20, weight: "600", lineHeight: 1.3, tracking: 0 },
  "body-lg": { min: 16, max: 18, weight: "400", lineHeight: 1.5, tracking: 0 },
  body: { min: 15, max: 16, weight: "400", lineHeight: 1.5, tracking: 0 },
  label: { min: 14, max: 15, weight: "600", lineHeight: 1.4, tracking: 0 },
  small: { min: 13, max: 14, weight: "400", lineHeight: 1.45, tracking: 0 },
  caption: { min: 12, max: 12, weight: "700", lineHeight: 1.3, tracking: 0, trackingEm: 0.06, uppercase: true },
};

/** A role's size in px at a viewport (or screen) width: min at 360, max at 1440, linear between. */
function fontSizeAt(role, width) {
  const t = typeScale[role];
  const k = Math.min(1, Math.max(0, (width - fluid.minWidth) / (fluid.maxWidth - fluid.minWidth)));
  return t.min + (t.max - t.min) * k;
}

/** Each role's [min, max] in px (what the page checks and the lint rules enforce). */
const fontSizeRanges = Object.fromEntries(Object.entries(typeScale).map(([r, t]) => [r, [t.min, t.max]]));

/** The smallest readable size (small's min); only the uppercase caption is under it. */
const minReadable = typeScale.small.min;

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
  web: { columns: 12, edge: 32, gap: 24, maxWidth: 1200, sideMenu: 248 },
  // Page content (web, admin): at most 1200 px, gutters 16 / 32 / 48 px (phone / tablet from 768 / desktop from 1024).
  page: { maxWidth: 1200, gutter: { phone: 16, tablet: 32, desktop: 48 } },
};

module.exports = { color, dark, space, radius, touch, font, fluid, typeScale, fontSizeAt, fontSizeRanges, minReadable, type, shadow, layout };
