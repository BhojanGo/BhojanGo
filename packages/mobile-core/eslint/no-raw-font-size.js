// bhojango-native/no-raw-font-size: in the Expo apps a font size comes only from
// the type scale (packages/mobile-core/src/ui/type.ts, the one file exempt).
//
//   fontSize: 13                       error: raw size, and under 14
//   fontSize: big ? 52 : 20            error: raw size
//   fontSize: Math.round(size * 0.4)   error: raw size
//   <SvgText fontSize={18}>            error: raw size (JSX attribute)
//   fontSize: type.h3.fontSize         ok (a token)
//   style={[type.small, { color }]}    ok (the usual way: no fontSize at all)
//
// Sizes under 14 are reported separately ("tooSmall"): only type.caption
// (uppercase labels and badges) may be smaller than 14.
"use strict";

const MIN_READABLE = 14;

/** Roots that hold the type tokens: type.h3.fontSize, field.body.fontSize, TYPE_SCALE.h3.size. */
const DEFAULT_TOKENS = ["type", "field", "TYPE_SCALE"];

function rootName(node) {
  let n = node;
  while (n && n.type === "MemberExpression") n = n.object;
  if (n && n.type === "ChainExpression") return rootName(n.expression);
  return n && n.type === "Identifier" ? n.name : null;
}

/** The literal sizes an expression can take (14, cond ? 18 : 12, "9px"); not the numbers inside arithmetic. */
function numbers(node, out = []) {
  if (!node) return out;
  if (node.type === "Literal" && typeof node.value === "number") out.push(node.value);
  else if (node.type === "Literal" && typeof node.value === "string" && /^\s*\d+(\.\d+)?(px)?\s*$/.test(node.value)) out.push(parseFloat(node.value));
  else if (node.type === "ConditionalExpression") { numbers(node.consequent, out); numbers(node.alternate, out); }
  else if (node.type === "LogicalExpression") { numbers(node.left, out); numbers(node.right, out); }
  else if (node.type === "TSAsExpression" || node.type === "TSNonNullExpression" || node.type === "ChainExpression") numbers(node.expression, out);
  return out;
}

module.exports = {
  meta: {
    type: "problem",
    docs: { description: "Font sizes in the Expo apps come only from the type scale (type.* tokens); nothing readable under 14." },
    schema: [{ type: "object", properties: { tokens: { type: "array", items: { type: "string" } } }, additionalProperties: false }],
    messages: {
      raw: "Raw font size: use a type token (style={[type.small, ...]}, type.h3.fontSize); sizes come only from packages/mobile-core/src/ui/type.ts.",
      tooSmall: "Font size {{size}} is under 14: readable text is at least type.small (14); only type.caption (uppercase labels, badges) is smaller.",
    },
  },
  create(context) {
    const tokens = new Set((context.options[0] && context.options[0].tokens) || DEFAULT_TOKENS);

    function allowed(value) {
      if (!value) return false;
      if (value.type === "MemberExpression") return tokens.has(rootName(value));
      if (value.type === "ChainExpression") return allowed(value.expression);
      if (value.type === "ConditionalExpression") return allowed(value.consequent) && allowed(value.alternate);
      if (value.type === "LogicalExpression") return allowed(value.left) && allowed(value.right);
      if (value.type === "TSAsExpression" || value.type === "TSNonNullExpression") return allowed(value.expression);
      return false;
    }

    function check(value, node) {
      if (allowed(value)) return;
      const small = numbers(value).filter((n) => n < MIN_READABLE);
      if (small.length) context.report({ node, messageId: "tooSmall", data: { size: String(Math.min(...small)) } });
      else context.report({ node, messageId: "raw" });
    }

    function isFontSizeKey(prop) {
      if (prop.computed) return prop.key.type === "Literal" && prop.key.value === "fontSize";
      return (prop.key.type === "Identifier" && prop.key.name === "fontSize") || (prop.key.type === "Literal" && prop.key.value === "fontSize");
    }

    return {
      Property(node) {
        if (node.kind !== "init" || !isFontSizeKey(node)) return;
        check(node.value, node);
      },
      JSXAttribute(node) {
        if (node.name.type !== "JSXIdentifier" || node.name.name !== "fontSize" || !node.value) return;
        check(node.value.type === "JSXExpressionContainer" ? node.value.expression : node.value, node);
      },
    };
  },
};
