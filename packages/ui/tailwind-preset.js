// Tailwind preset from the design tokens: `presets: [require("@bhojango/ui/tailwind-preset")]`.
const { color, dark, radius, shadow, font, fluid, typeScale, layout } = require("./tokens");

// Inter is self-hosted (apps/*/src/app/fonts.ts imports @fontsource-variable/inter,
// whose @font-face family is "Inter Variable"); "Inter Fallback" is a local face
// with Inter's metrics so the swap does not move the layout. Indian scripts fall
// back to Noto Sans <script>; next/font sets the variables, the names after the
// comma cover a page without them.
const scripts = [
  ["--font-deva", font.scripts.devanagari],
  ["--font-telu", font.scripts.telugu],
  ["--font-taml", font.scripts.tamil],
  ["--font-knda", font.scripts.kannada],
  ["--font-beng", font.scripts.bengali],
].map(([v, name]) => `var(${v}, '${name}')`);

const text = ["'Inter Variable'", `'${font.text}'`, "'Inter Fallback'", ...scripts, "system-ui", "sans-serif"];

const rem = (px) => `${+(px / 16).toFixed(4)}rem`;

/**
 * A fluid size: min px at a 360 px viewport, max px at 1440 px, linear between.
 * In rem so a reader's own default font size still scales it.
 */
function fluidSize(min, max) {
  if (min === max) return rem(min);
  const slope = (max - min) / (fluid.maxWidth - fluid.minWidth); // px per px of viewport
  const intercept = min - slope * fluid.minWidth;
  return `clamp(${rem(min)}, ${rem(intercept)} + ${+(slope * 100).toFixed(4)}vw, ${rem(max)})`;
}

/**
 * The type scale as one class per role: text-display, text-h1, text-h2, text-h3,
 * text-body-lg, text-body, text-label, text-small, text-caption. Each sets a fluid
 * size (clamp between 360 and 1440 px), line height, weight and tracking.
 * Components layer, so a utility (font-bold for an active tab, leading-none in a
 * pill) still wins; colours stay separate (text-kohl, text-muted ...).
 * These are the only font sizes allowed: eslint rule bhojango/no-raw-font-size.
 */
function typeScalePlugin({ addBase, addComponents }) {
  const rules = {};
  for (const [role, t] of Object.entries(typeScale)) {
    const rule = {
      fontSize: fluidSize(t.min, t.max),
      lineHeight: String(t.lineHeight),
      fontWeight: t.weight,
      letterSpacing: t.trackingEm ? `${t.trackingEm}em` : t.tracking ? `${t.tracking}px` : "normal",
    };
    if (t.uppercase) rule.textTransform = "uppercase";
    rules[`.text-${role}`] = rule;
  }
  addComponents(rules);
  // Text without a role class reads as body.
  addBase({
    body: { fontSize: fluidSize(typeScale.body.min, typeScale.body.max), lineHeight: String(typeScale.body.lineHeight) },
    "@font-face": {
      fontFamily: "'Inter Fallback'",
      src: "local('Arial')",
      ascentOverride: "90.44%",
      descentOverride: "22.52%",
      lineGapOverride: "0%",
      sizeAdjust: "107.12%",
    },
  });
}

/**
 * Page layout helpers (web and admin):
 *   .container-page  content at most 1200 px wide, centred, gutters 16 / 32 / 48 px
 *                    (phone / from 768 px / from 1024 px)
 *   .section-page    vertical rhythm between page sections: 32 px on a phone, fluid to 64 px
 *   .section-page-tight  half of that (sections that sit close, e.g. under a hero)
 * The React versions are Container and Section in @bhojango/ui.
 */
function layoutPlugin({ addComponents }) {
  const { maxWidth, gutter } = layout.page;
  addComponents({
    ".container-page": {
      width: "100%",
      maxWidth: `${maxWidth + 2 * gutter.desktop}px`,
      marginLeft: "auto",
      marginRight: "auto",
      paddingLeft: `${gutter.phone}px`,
      paddingRight: `${gutter.phone}px`,
      "@media (min-width: 768px)": { paddingLeft: `${gutter.tablet}px`, paddingRight: `${gutter.tablet}px` },
      "@media (min-width: 1024px)": { paddingLeft: `${gutter.desktop}px`, paddingRight: `${gutter.desktop}px` },
    },
    ".section-page": {
      paddingTop: "clamp(2rem, 1.3333rem + 2.963vw, 4rem)",
      paddingBottom: "clamp(2rem, 1.3333rem + 2.963vw, 4rem)",
    },
    ".section-page-tight": {
      paddingTop: "clamp(1rem, 0.6667rem + 1.4815vw, 2rem)",
      paddingBottom: "clamp(1rem, 0.6667rem + 1.4815vw, 2rem)",
    },
  });
}

module.exports = {
  theme: {
    extend: {
      colors: {
        peacock: { DEFAULT: color.peacock, deep: color.peacockDeep, tint: color.peacockTint, mist: color.peacockMist },
        kohl: color.kohl,
        kesar: { DEFAULT: color.kesar, bright: color.kesarBright },
        porcelain: color.porcelain,
        line: { DEFAULT: color.line, strong: color.lineStrong, divider: color.divider },
        muted: color.muted,
        faint: color.faint,
        chili: color.chili,
        plate: color.plate,
        night: dark,
      },
      borderRadius: { chip: `${radius.chip}px`, card: `${radius.card}px`, sheet: `${radius.sheet}px`, pill: "999px" },
      boxShadow: { float: shadow.float, sheet: shadow.sheet, bar: shadow.bar },
      fontFamily: {
        display: text,
        sans: text,
      },
      maxWidth: { content: `${layout.page.maxWidth}px`, page: `${layout.page.maxWidth + 2 * layout.page.gutter.desktop}px` },
    },
  },
  plugins: [typeScalePlugin, layoutPlugin],
};

module.exports.fluidSize = fluidSize;
