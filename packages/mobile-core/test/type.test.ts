// node --test: the apps' type scale (src/ui/type.ts) and the lint rule that keeps
// every font size on it (eslint/no-raw-font-size.js).
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { describe, it, test } from "node:test";

import { RuleTester } from "eslint";

import {
  DENSE_FONT_SCALE, face, familyFor, field, FLUID, MIN_READABLE, num, scriptFor, setTypeScript, setTypeWidth, sizeAt, textStyles, type,
  TYPE_RANGES, TYPE_ROLES, TYPE_SCALE, typeScript, typeStyleFor, typeWidth,
} from "../src/ui/type.ts";

const require = createRequire(import.meta.url);
const rule = require("../eslint/no-raw-font-size.js");
const plugin = require("../eslint/index.js");
const tokens = require("@bhojango/ui/tokens");

test("the scale: each role's [min, max], weights, and the same numbers as the web", () => {
  assert.deepEqual(Object.fromEntries(TYPE_ROLES.map((r) => [r, [...TYPE_RANGES[r]]])), {
    display: [36, 52], h1: [28, 36], h2: [22, 28], h3: [17, 20], bodyLg: [16, 18], body: [15, 16], label: [14, 15], small: [13, 14], caption: [12, 12],
  });
  const weights = Object.fromEntries(TYPE_ROLES.map((r) => [r, TYPE_SCALE[r].weight]));
  assert.deepEqual(weights, {
    display: "700", h1: "700", h2: "700", h3: "600", bodyLg: "400", body: "400", label: "600", small: "400", caption: "700",
  });
  assert.equal(TYPE_SCALE.display.tracking, -0.8);
  assert.equal(TYPE_SCALE.h1.tracking, -0.4);
  assert.equal(MIN_READABLE, 13);
  assert.ok(DENSE_FONT_SCALE > 1, "dense UI caps the font setting, never turns it off");
  // packages/ui tokens.js is the web's copy: the apps use the same numbers.
  for (const r of TYPE_ROLES) {
    const web = tokens.typeScale[r === "bodyLg" ? "body-lg" : r];
    assert.deepEqual([web.min, web.max, web.weight, web.lineHeight], [TYPE_SCALE[r].min, TYPE_SCALE[r].max, TYPE_SCALE[r].weight, TYPE_SCALE[r].lineHeight], r);
    assert.equal(tokens.fontSizeAt(r === "bodyLg" ? "body-lg" : r, 900), (TYPE_SCALE[r].min + TYPE_SCALE[r].max) / 2, r);
  }
  assert.deepEqual(FLUID, tokens.fluid);
});

test("sizes are fluid: the min on a 360 dp phone, the max from 1440 dp, linear between", () => {
  for (const r of TYPE_ROLES) {
    const [min, max] = TYPE_RANGES[r];
    assert.equal(sizeAt(r, 320), min, `${r} below 360`);
    assert.equal(sizeAt(r, 360), min, `${r} at 360`);
    assert.equal(sizeAt(r, 1440), max, `${r} at 1440`);
    assert.equal(sizeAt(r, 2000), max, `${r} above 1440`);
    const mid = sizeAt(r, 900);
    assert.ok(mid >= min && mid <= max, `${r} in range`);
  }
  assert.equal(sizeAt("display", 900), 44);
  assert.equal(sizeAt("body", 412), 15, "a large phone sits at the min (to 0.1 dp)");
  assert.equal(sizeAt("h1", 800), 31.3, "a tablet sits in between");
});

test("Inter for every role; caption is uppercase; the tokens follow the screen size", () => {
  setTypeScript("latin");
  assert.equal(type.display.fontFamily, "Inter_700Bold");
  assert.equal(type.h1.fontFamily, "Inter_700Bold");
  assert.equal(type.h2.fontFamily, "Inter_700Bold");
  assert.equal(type.h3.fontFamily, "Inter_600SemiBold");
  assert.equal(type.label.fontFamily, "Inter_600SemiBold");
  assert.equal(type.body.fontFamily, "Inter_400Regular");
  assert.equal(type.small.fontFamily, "Inter_400Regular");
  assert.equal(type.caption.fontFamily, "Inter_700Bold");
  assert.equal(type.caption.textTransform, "uppercase");
  assert.ok((type.caption.letterSpacing ?? 0) > 0);
  assert.equal(type.display.letterSpacing, -0.8);
  assert.equal(typeWidth(), 360);
  for (const r of TYPE_ROLES) {
    const s = type[r];
    assert.equal(s.fontSize, TYPE_SCALE[r].min, r);
    assert.ok((s.lineHeight ?? 0) >= (s.fontSize ?? 0), `${r} line height`);
    if (r !== "caption") assert.ok((s.fontSize ?? 0) >= 13, `${r} is readable`);
  }
  setTypeWidth(1440);
  try {
    for (const r of TYPE_ROLES) assert.equal(type[r].fontSize, TYPE_SCALE[r].max, r);
    const s = textStyles({ title: ["h3"] });
    assert.equal(s.title.fontSize, 20);
    assert.equal(field.h1.fontSize, 36);
  } finally {
    setTypeWidth(360);
  }
  assert.equal(type.h3.fontSize, 17);
});

test("an Indian-script language gets its Noto Sans face for every role", () => {
  assert.equal(scriptFor("hi"), "devanagari");
  assert.equal(scriptFor("mr"), "devanagari");
  assert.equal(scriptFor("te"), "telugu");
  assert.equal(scriptFor("ta"), "tamil");
  assert.equal(scriptFor("kn"), "kannada");
  assert.equal(scriptFor("bn"), "bengali");
  assert.equal(scriptFor("en"), "latin");
  assert.equal(scriptFor("es"), "latin");
  assert.equal(scriptFor(null), "latin");
  assert.equal(familyFor("telugu", "600"), "NotoSansTelugu_600SemiBold");

  setTypeScript("devanagari");
  try {
    assert.equal(typeScript(), "devanagari");
    assert.equal(type.h1.fontFamily, "NotoSansDevanagari_700Bold");
    assert.equal(type.body.fontFamily, "NotoSansDevanagari_400Regular");
    assert.equal(type.caption.fontFamily, "NotoSansDevanagari_700Bold");
    assert.equal(type.h1.letterSpacing, undefined, "no tracking on Indic scripts");
    assert.ok((type.body.lineHeight ?? 0) > (typeStyleFor("body", "latin").lineHeight ?? 0), "more leading for matras");
    assert.equal(face("700").fontFamily, "NotoSansDevanagari_700Bold");
    // textStyles and field follow the script too
    const s = textStyles({ title: ["h3", { color: "#000" }] });
    assert.equal(s.title.fontFamily, "NotoSansDevanagari_600SemiBold");
    assert.equal(s.title.color, "#000");
    assert.equal(field.body.fontFamily, "NotoSansDevanagari_400Regular");
  } finally {
    setTypeScript("latin");
  }
});

test("textStyles keeps view styles and resolves text styles at read time", () => {
  const s = textStyles({ card: { padding: 8 } }, { title: ["h3"], amount: ["label", num] });
  assert.deepEqual(s.card, { padding: 8 });
  assert.equal(s.title.fontSize, 17);
  assert.deepEqual(s.amount.fontVariant, ["tabular-nums"]);
  setTypeScript("tamil");
  try {
    assert.equal(s.title.fontFamily, "NotoSansTamil_600SemiBold");
  } finally {
    setTypeScript("latin");
  }
  assert.equal(s.title.fontFamily, "Inter_600SemiBold");
  assert.equal(field.bodyLg.lineHeight, undefined, "inputs centre their line themselves");
});

// ── the lint rule ───────────────────────────────────────────────────────────

RuleTester.describe = describe;
RuleTester.it = it;
RuleTester.itOnly = it.only;
const tester = new RuleTester({
  languageOptions: { ecmaVersion: "latest", sourceType: "module", parserOptions: { ecmaFeatures: { jsx: true } } },
});

tester.run("no-raw-font-size", rule, {
  valid: [
    "const a = <Text style={[type.small, { color: c }]} />;",
    "const s = { title: { fontSize: type.h3.fontSize, color: c } };",
    "const a = <SvgText fontSize={type.h3.fontSize} />;",
    "const s = { fontSize: big ? type.display.fontSize : type.h3.fontSize };",
    "const s = { caption: { fontSize: type.caption.fontSize } };",
    "const s = { input: { fontSize: field.body.fontSize } };",
    "const s = { lineHeight: 20, letterSpacing: 1 };",
  ],
  invalid: [
    { code: "const s = StyleSheet.create({ x: { fontSize: 16 } });", errors: [{ messageId: "raw" }] },
    { code: "const a = <Text style={[textFont('700'), { fontSize: 15, color: c }]} />;", errors: [{ messageId: "raw" }] },
    { code: "const a = <Text style={{ fontSize: 12 }} />;", errors: [{ messageId: "tooSmall", data: { size: "12" } }] },
    { code: "const a = <Text style={{ fontSize: 13 }} />;", errors: [{ messageId: "raw" }] },
    { code: "const s = { payee: { fontSize: 11, textTransform: 'uppercase' } };", errors: [{ messageId: "tooSmall" }] },
    { code: "const s = { fontSize: big ? 52 : 20 };", errors: [{ messageId: "raw" }] },
    { code: "const s = { fontSize: wide ? 18 : 12 };", errors: [{ messageId: "tooSmall", data: { size: "12" } }] },
    { code: "const s = { fontSize: Math.round(size * 0.36) };", errors: [{ messageId: "raw" }] },
    { code: "const s = { fontSize: size };", errors: [{ messageId: "raw" }] },
    { code: "const s = { 'fontSize': 18 };", errors: [{ messageId: "raw" }] },
    { code: "const s = { ['fontSize']: 18 };", errors: [{ messageId: "raw" }] },
    { code: "const a = <SvgText fontSize={18} />;", errors: [{ messageId: "raw" }] },
    { code: "const a = <SvgText fontSize=\"9\" />;", errors: [{ messageId: "tooSmall", data: { size: "9" } }] },
    { code: "const s = { fontSize: other.h3.fontSize };", errors: [{ messageId: "raw" }] },
  ],
});

test("the plugin's flat config turns the rule on and spares only the token file", () => {
  assert.equal(plugin.recommended.rules["bhojango-native/no-raw-font-size"], "error");
  assert.ok(plugin.recommended.ignores.some((g: string) => g.endsWith("src/ui/type.ts")));
  assert.equal(plugin.rules["no-raw-font-size"], rule);
});
