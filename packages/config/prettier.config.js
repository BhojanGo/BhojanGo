/** @type {import('prettier').Config} */
module.exports = {
  semi: true,
  singleQuote: false,
  quoteProps: "as-needed",
  trailingComma: "es5",
  printWidth: 100,
  tabWidth: 2,
  useTabs: false,
  bracketSpacing: true,
  bracketSameLine: false,
  arrowParens: "always",
  endOfLine: "lf",
  plugins: ["prettier-plugin-tailwindcss"],
  overrides: [
    {
      files: "*.json",
      options: { printWidth: 80 },
    },
    {
      files: "*.md",
      options: { proseWrap: "always" },
    },
  ],
};
