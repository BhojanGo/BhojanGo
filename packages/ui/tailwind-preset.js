// Tailwind preset from the design tokens: `presets: [require("@bhojango/ui/tailwind-preset")]`.
const { color, dark, radius, shadow, font } = require("./tokens");

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
        display: ["var(--font-display)", `'${font.display}'`, "system-ui", "sans-serif"],
        sans: ["var(--font-text)", `'${font.text}'`, "system-ui", "sans-serif"],
      },
      maxWidth: { content: "1280px" },
    },
  },
};
