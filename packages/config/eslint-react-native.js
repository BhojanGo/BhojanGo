// @ts-check
/**
 * Baseline lint for the Expo apps and mobile-core. They were never linted
 * before P1 (no config existed), so this starts with the non-type-aware
 * recommended rules; tighten towards ./eslint.js as screens are reworked.
 * @type {import('eslint').Linter.Config}
 */
module.exports = {
  root: true,
  env: { es2022: true, node: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module", ecmaFeatures: { jsx: true } },
  plugins: ["@typescript-eslint", "react-hooks"],
  extends: ["eslint:recommended", "plugin:@typescript-eslint/recommended", "plugin:react-hooks/recommended"],
  globals: { __DEV__: "readonly" },
  rules: {
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
    "@typescript-eslint/no-explicit-any": "warn",
    "no-console": ["warn", { allow: ["warn", "error"] }],
    eqeqeq: ["error", "always", { null: "ignore" }],
  },
};
