// node --test: the fluid type scale (tokens.js) and the classes the Tailwind preset makes from it.
const { test } = require("node:test");
const assert = require("node:assert/strict");

const { typeScale, fontSizeAt, fontSizeRanges, minReadable, color, layout } = require("../tokens");
const preset = require("../tailwind-preset");

/** Evaluate a clamp(min rem, a rem + b vw, max rem) the way a browser does, at a viewport width (16 px root). */
function px(css, width) {
  if (!css.startsWith("clamp(")) return parseFloat(css) * 16;
  const [lo, mid, hi] = css.slice(6, -1).split(/,\s*/);
  const [a, b] = mid.split(" + ");
  return Math.min(parseFloat(hi) * 16, Math.max(parseFloat(lo) * 16, parseFloat(a) * 16 + (parseFloat(b) * width) / 100));
}

function classes() {
  const out = {};
  const api = { addComponents: (r) => Object.assign(out, r), addBase: () => {} };
  for (const plugin of preset.plugins) plugin(api);
  return out;
}

test("the scale: each role's range, weights, tracking", () => {
  assert.deepEqual(fontSizeRanges, {
    display: [36, 52], h1: [28, 36], h2: [22, 28], h3: [17, 20], "body-lg": [16, 18], body: [15, 16], label: [14, 15], small: [13, 14], caption: [12, 12],
  });
  assert.deepEqual(Object.fromEntries(Object.entries(typeScale).map(([r, t]) => [r, t.weight])), {
    display: "700", h1: "700", h2: "700", h3: "600", "body-lg": "400", body: "400", label: "600", small: "400", caption: "700",
  });
  assert.equal(typeScale.display.tracking, -0.8);
  assert.equal(typeScale.h1.tracking, -0.4);
  assert.equal(minReadable, 13);
  assert.equal(color.muted, "#3D4A4E");
  assert.equal(layout.page.maxWidth, 1200);
});

test("the preset's classes are fluid: min at 360 px, max at 1440 px, linear between", () => {
  const c = classes();
  for (const role of Object.keys(typeScale)) {
    const css = c[`.text-${role}`].fontSize;
    for (const w of [320, 360, 390, 768, 1024, 1093, 1280, 1440, 1920]) {
      assert.ok(Math.abs(px(css, w) - fontSizeAt(role, w)) < 0.05, `${role} at ${w}: ${px(css, w)} vs ${fontSizeAt(role, w)}`);
    }
  }
  assert.equal(c[".text-caption"].textTransform, "uppercase");
  assert.equal(c[".text-caption"].letterSpacing, "0.06em");
  assert.equal(c[".text-display"].letterSpacing, "-0.8px");
  assert.equal(c[".container-page"].maxWidth, "1296px", "1200 px of content plus the 48 px desktop gutters");
});
