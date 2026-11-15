// Tailwind preset from the design tokens: `presets: [require("@bhojango/ui/tailwind-preset")]`.
const { color, dark, radius, shadow, font, typeScale } = require("./tokens");

// Indian scripts fall back to Noto Sans <script>; next/font sets the variables
// (apps/*/src/app/fonts.ts), the names after the comma cover a page without them.
const scripts = [
  ["--font-deva", font.scripts.devanagari],
  ["--font-telu", font.scripts.telugu],
  ["--font-taml", font.scripts.tamil],
  ["--font-knda", font.scripts.kannada],
  ["--font-beng", font.scripts.bengali],
].map(([v, name]) => `var(${v}, '${name}')`);

const stacks = {
  display: [`var(--font-display, '${font.display}')`, ...scripts, "system-ui", "sans-serif"],
  text: [`var(--font-text, '${font.text}')`, ...scripts, "system-ui", "sans-serif"],
};

/**
 * The type scale as one class per role: text-display, text-h1, text-h2, text-h3,
 * text-body-lg, text-body, text-label, text-small, text-caption. Each sets size,
 * line height, weight and family; the phone size below md (768 px), the desktop
 * size from md. Components layer, so a utility (font-bold for an active tab,
 * leading-none in a pill) still wins; colours stay separate (text-kohl ...).
 * These are the only font sizes allowed: eslint rule bhojango/no-raw-font-size.
 */
function typeScalePlugin({ addComponents }) {
  const rules = {};
  for (const [role, t] of Object.entries(typeScale)) {
    const rule = {
      fontFamily: stacks[t.family].join(", "),
      fontSize: `${t.phone}px`,
      lineHeight: String(t.lineHeight),
      fontWeight: t.weight,
      letterSpacing: t.tracking ? `${t.tracking}em` : "normal",
    };
    if (t.uppercase) rule.textTransform = "uppercase";
    if (t.desktop !== t.phone) rule["@media (min-width: 768px)"] = { fontSize: `${t.desktop}px` };
    rules[`.text-${role}`] = rule;
  }
  addComponents(rules);
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
        display: stacks.display,
        sans: stacks.text,
      },
      maxWidth: { content: "1280px" },
    },
  },
  plugins: [typeScalePlugin],
};
