// node --test: the apps' type scale (src/ui/type.ts) and the lint rule that keeps
// every font size on it (eslint/no-raw-font-size.js).
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { describe, it, test } from "node:test";

import { RuleTester } from "eslint";

import {
  face, familyFor, field, num, scriptFor, setTypeScript, textStyles, type, TYPE_ROLES, TYPE_SCALE, TYPE_SIZES, typeScript, typeStyleFor,
} from "../src/ui/type.ts";

const require = createRequire(import.meta.url);
const rule = require("../eslint/no-raw-font-size.js");
const plugin = require("../eslint/index.js");

test("the phone column of the scale, and nothing else", () => {
  const sizes = Object.fromEntries(TYPE_ROLES.map((r) => [r, TYPE_SCALE[r].size]));
  assert.deepEqual(sizes, { display: 44, h1: 30, h2: 22, h3: 18, bodyLg: 17, body: 16, label: 15, small: 14, caption: 12 });
  assert.deepEqual([...TYPE_SIZES], [12, 14, 15, 16, 17, 18, 22, 30, 44]);
  const weights = Object.fromEntries(TYPE_ROLES.map((r) => [r, TYPE_SCALE[r].weight]));
  assert.deepEqual(weights, {
    display: "600", h1: "600", h2: "600", h3: "600", bodyLg: "400", body: "400", label: "600", small: "400", caption: "700",
  });
});

test("Familjen Grotesk for display, h1, h2; Hanken Grotesk for the rest; caption is uppercase", () => {
  setTypeScript("latin");
  assert.equal(type.display.fontFamily, "FamiljenGrotesk_600SemiBold");
  assert.equal(type.h1.fontFamily, "FamiljenGrotesk_600SemiBold");
  assert.equal(type.h2.fontFamily, "FamiljenGrotesk_600SemiBold");
  assert.equal(type.h3.fontFamily, "HankenGrotesk_600SemiBold");
  assert.equal(type.label.fontFamily, "HankenGrotesk_600SemiBold");
  assert.equal(type.body.fontFamily, "HankenGrotesk_400Regular");
  assert.equal(type.small.fontFamily, "HankenGrotesk_400Regular");
  assert.equal(type.caption.fontFamily, "HankenGrotesk_700Bold");
  assert.equal(type.caption.textTransform, "uppercase");
  assert.ok((type.caption.letterSpacing ?? 0) > 0);
  for (const r of TYPE_ROLES) {
    const s = type[r];
    assert.equal(s.fontSize, TYPE_SCALE[r].size, r);
    assert.ok((s.lineHeight ?? 0) >= (s.fontSize ?? 0), `${r} line height`);
    if (r !== "caption") assert.ok((s.fontSize ?? 0) >= 14, `${r} is readable`);
  }
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
  assert.equal(familyFor("telugu", "600", true), "NotoSansTelugu_600SemiBold");

  setTypeScript("devanagari");
  try {
    assert.equal(typeScript(), "devanagari");
    assert.equal(type.h1.fontFamily, "NotoSansDevanagari_600SemiBold");
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
  assert.equal(s.title.fontSize, 18);
  assert.deepEqual(s.amount.fontVariant, ["tabular-nums"]);
  setTypeScript("tamil");
  try {
    assert.equal(s.title.fontFamily, "NotoSansTamil_600SemiBold");
  } finally {
    setTypeScript("latin");
  }
  assert.equal(s.title.fontFamily, "HankenGrotesk_600SemiBold");
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
    { code: "const a = <Text style={{ fontSize: 13 }} />;", errors: [{ messageId: "tooSmall", data: { size: "13" } }] },
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
