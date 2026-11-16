// node --test packages/config/test: the type-scale lint rule fires on every raw
// font-size pattern and leaves the tokens and colour/alignment classes alone.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { RuleTester, Linter } = require("eslint");

const { plugin, typeScaleLint } = require("../eslint-rules");

const rule = plugin.rules["no-raw-font-size"];

const tester = new RuleTester({
  languageOptions: { ecmaVersion: "latest", sourceType: "module", parserOptions: { ecmaFeatures: { jsx: true } } },
});

test("rule: tokens pass, every raw size pattern fails", () => tester.run("no-raw-font-size", rule, {
  valid: [
    `<p className="text-display text-h1 text-h2 text-h3 text-body-lg text-body text-label text-small text-caption" />`,
    `<p className="text-white text-center text-left text-right text-kohl text-peacock-deep text-[#111418] text-ellipsis" />`,
    `<p className="md:text-h1 hover:text-white text-[var(--ink)] text-[rgb(1,2,3)] tabular-nums" />`,
    "const c = `flex ${on ? 'text-white' : 'text-muted'} text-label`;",
    `const s = { color: "red", lineHeight: 1.5 };`,
    `const t = "context: text is small";`,
    `const label = "The total is $12 for 2 items";`,
    `<svg><circle r={4} /></svg>`,
  ],
  invalid: [
    { code: `<p className="text-sm" />`, errors: [{ messageId: "named" }] },
    { code: `<p className="text-xs text-base text-lg text-xl text-2xl text-9xl" />`, errors: 6 },
    { code: `<p className="md:text-[15px] hover:!text-sm" />`, errors: [{ messageId: "arbitrary" }, { messageId: "named" }] },
    { code: `<p className="text-[13px]" />`, errors: [{ messageId: "arbitrary" }] },
    { code: `<p className="text-[0.8rem] text-[length:var(--x)] text-[clamp(1rem,2vw,2rem)]" />`, errors: 3 },
    { code: `<p className="text-sm/6" />`, errors: [{ messageId: "named" }] },
    { code: "const c = `flex ${x} text-[11px] font-bold`;", errors: [{ messageId: "arbitrary" }] },
    { code: `cn("a", on && "text-lg")`, errors: [{ messageId: "named" }] },
    { code: `<p style={{ fontSize: 12 }} />`, errors: [{ messageId: "style" }] },
    { code: `const s = { "font-size": "12px" };`, errors: [{ messageId: "style" }] },
    { code: `const o = { plugins: { legend: { labels: { font: { size: 11 } } } } };`, errors: [{ messageId: "style" }] },
    { code: `ctx.font = "12px sans-serif"; const o = { font: "bold 11px Inter" };`, errors: 2 },
    { code: `<svg><text fontSize={10}>x</text></svg>`, errors: [{ messageId: "style" }] },
    { code: `el.innerHTML = '<span style="font-size:11px">x</span>';`, errors: [{ messageId: "css" }] },
  ],
}));

function lintCss(text) {
  const linter = new Linter({ configType: "flat" });
  return linter.verify(text, typeScaleLint, "app/globals.css");
}

test("CSS: font-size and raw @apply sizes fail, with the right line", () => {
  const messages = lintCss(".a {\n  color: red;\n  font-size: 13px;\n}\n.b { @apply text-sm text-kohl; }\n");
  assert.deepEqual(
    messages.map((m) => [m.ruleId, m.line]),
    [
      ["bhojango/no-raw-font-size", 3],
      ["bhojango/no-raw-font-size", 5],
    ],
  );
});

test("CSS: tokens and other declarations pass", () => {
  assert.deepEqual(lintCss("@tailwind base;\n.a { @apply text-body text-kohl; line-height: 1.5; }\n"), []);
});
