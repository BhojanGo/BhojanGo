// @ts-check
// Local ESLint plugin "bhojango" for the website and the admin console.
//
//   bhojango/no-raw-font-size: the type scale (packages/ui tokens) is the only
//   source of font sizes. Use text-display, text-h1, text-h2, text-h3,
//   text-body-lg, text-body, text-label, text-small or text-caption. Fails on:
//     - Tailwind size utilities: text-xs, text-sm, text-base, text-lg, text-xl,
//       text-2xl ... text-9xl (any variant prefix, any /line-height suffix);
//     - arbitrary sizes: text-[13px], text-[0.8rem], text-[length:...], text-[clamp(...)];
//     - inline styles and props: fontSize, "font-size", font: "12px ...",
//       font: { size: 11 } and ctx.font = "12px ..." (canvas charts), <text fontSize=...>;
//     - font-size in CSS (the `css` processor turns each line of a .css file
//       into a string, so the same rule reads it).
//   Colour, alignment and other text-* classes (text-white, text-center,
//   text-[#111418], text-peacock) are fine. The tokens are fluid (packages/ui
//   tailwind-preset.js: clamp() from 360 to 1440 px, e.g. text-h1 28 to 36 px), so a
//   raw size, fixed or clamp(), is always off the scale. Nothing readable is under
//   13 px because the only token under 13 is text-caption (12), which sets
//   uppercase itself.

const TOKENS = ["display", "h1", "h2", "h3", "body-lg", "body", "label", "small", "caption"];
const NAMED = /^text-(?:xs|sm|base|lg|xl|[2-9]xl)(?:\/\S+)?$/;
const ARBITRARY = /^text-\[([^\]]+)\](?:\/\S+)?$/;
const LENGTH = /^(?:\d|\.\d|length:|calc\(|clamp\(|min\(|max\()/;
const CSS_FONT_SIZE = /(?:^|[\s;{"'])font-size\s*:/i;
const CSS_FONT_SHORTHAND = /(?:^|[\s;{"'])font\s*:\s*[^;]*\d(?:px|rem|em|pt|%)/i;
const FONT_SHORTHAND_VALUE = /\d(?:px|rem|em|pt|%)/;

/** The utility part of a class: "md:hover:!text-sm" -> "text-sm" (colons inside [] are kept). */
function utility(cls) {
  let depth = 0;
  let start = 0;
  for (let i = 0; i < cls.length; i++) {
    const c = cls[i];
    if (c === "[") depth++;
    else if (c === "]") depth--;
    else if (c === ":" && depth === 0) start = i + 1;
  }
  let u = cls.slice(start);
  if (u.startsWith("!")) u = u.slice(1);
  if (u.endsWith("!")) u = u.slice(0, -1);
  return u;
}

/** Problems in a string: raw Tailwind sizes and CSS font-size declarations. */
function scanString(value) {
  const found = [];
  for (const raw of value.split(/[\s"'`]+/)) {
    if (!raw.includes("text-")) continue;
    const u = utility(raw);
    if (NAMED.test(u)) found.push({ cls: raw, kind: "named" });
    else {
      const m = ARBITRARY.exec(u);
      if (m && LENGTH.test(m[1])) found.push({ cls: raw, kind: "arbitrary" });
    }
  }
  if (CSS_FONT_SIZE.test(value) || CSS_FONT_SHORTHAND.test(value)) found.push({ cls: "font-size", kind: "css" });
  return found;
}

function keyName(node) {
  if (!node) return null;
  if (node.type === "Identifier") return node.name;
  if (node.type === "Literal" && typeof node.value === "string") return node.value;
  return null;
}

/** @type {import("eslint").Rule.RuleModule} */
const noRawFontSize = {
  meta: {
    type: "problem",
    docs: { description: "Font sizes come from the type scale tokens only (text-display ... text-caption)." },
    schema: [],
    messages: {
      named: "Raw font size '{{cls}}': use a type-scale class ({{tokens}}).",
      arbitrary: "Raw font size '{{cls}}': use a type-scale class ({{tokens}}).",
      css: "font-size outside the token files: use a type-scale class ({{tokens}}).",
      style: "Inline font size '{{key}}': use a type-scale class ({{tokens}}).",
    },
  },
  create(context) {
    const tokens = TOKENS.map((t) => `text-${t}`).join(", ");
    function checkString(node, value) {
      for (const f of scanString(value)) context.report({ node, messageId: f.kind, data: { cls: f.cls, tokens } });
    }
    return {
      Literal(node) {
        if (typeof node.value !== "string") return;
        // Object keys are checked by Property below.
        if (node.parent && node.parent.type === "Property" && node.parent.key === node) return;
        if (node.parent && node.parent.type === "ImportDeclaration") return;
        checkString(node, node.value);
      },
      TemplateElement(node) {
        checkString(node, node.value.cooked ?? node.value.raw);
      },
      Property(node) {
        const key = keyName(node.key);
        if (key === "fontSize" || key === "font-size") {
          context.report({ node, messageId: "style", data: { key, tokens } });
        } else if (key === "font") {
          const v = node.value;
          if (v.type === "ObjectExpression" && v.properties.some((p) => p.type === "Property" && keyName(p.key) === "size"))
            context.report({ node, messageId: "style", data: { key: "font.size", tokens } });
          else if (v.type === "Literal" && typeof v.value === "string" && FONT_SHORTHAND_VALUE.test(v.value))
            context.report({ node, messageId: "style", data: { key: "font", tokens } });
        }
      },
      AssignmentExpression(node) {
        // canvas: ctx.font = "12px sans-serif"
        const l = node.left;
        if (l.type === "MemberExpression" && keyName(l.property) === "font" && node.right.type === "Literal" && typeof node.right.value === "string" && FONT_SHORTHAND_VALUE.test(node.right.value))
          context.report({ node, messageId: "style", data: { key: "font", tokens } });
      },
      JSXAttribute(node) {
        const name = node.name && node.name.type === "JSXIdentifier" ? node.name.name : null;
        if (name === "fontSize" || name === "font-size") context.report({ node, messageId: "style", data: { key: name, tokens } });
      },
    };
  },
};

// CSS files: each line becomes a string statement on the same line, so line
// numbers match and no-raw-font-size reads the declarations.
const css = {
  meta: { name: "bhojango-css" },
  preprocess(text) {
    const code = text
      .split(/\r?\n/)
      .map((line) => `${JSON.stringify(line)};`)
      .join("\n");
    return [{ text: code, filename: "styles.js" }];
  },
  postprocess(messages) {
    return messages.flat().map((m) => ({ ...m, column: Math.max(1, m.column - 1), endColumn: undefined, fix: undefined }));
  },
  supportsAutofix: false,
};

const plugin = {
  meta: { name: "bhojango", version: "1.0.0" },
  rules: { "no-raw-font-size": noRawFontSize },
  processors: { css },
};

/**
 * Flat-config entries for an app: the rule on its code and on its CSS.
 * Usage (eslint.config.mjs): `...typeScaleLint` after the app's other configs.
 */
const typeScaleLint = [
  {
    files: ["**/*.{js,jsx,mjs,cjs,ts,tsx}"],
    ignores: ["**/*.css/**"],
    plugins: { bhojango: plugin },
    rules: { "bhojango/no-raw-font-size": "error" },
  },
  { files: ["**/*.css"], plugins: { bhojango: plugin }, processor: "bhojango/css" },
  {
    files: ["**/*.css/**"],
    plugins: { bhojango: plugin },
    rules: { "bhojango/no-raw-font-size": "error" },
  },
];

module.exports = { plugin, typeScaleLint, scanString, TOKENS };
