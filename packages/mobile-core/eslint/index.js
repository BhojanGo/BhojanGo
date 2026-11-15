// Local ESLint plugin for the Expo apps and mobile-core (round 6: the type scale).
//
//   // apps/<app>/eslint.config.js
//   module.exports = [...require("@bhojango/config/eslint/expo"), require("@bhojango/mobile-core/eslint").recommended];
//
// The token file (src/ui/type.ts) is the one place a number may be a font size.
"use strict";

const noRawFontSize = require("./no-raw-font-size");

const plugin = {
  meta: { name: "bhojango-native" },
  rules: { "no-raw-font-size": noRawFontSize },
};

/** Flat config: the rule as an error everywhere but the token file. */
plugin.recommended = {
  files: ["**/*.{js,jsx,ts,tsx}"],
  ignores: ["**/mobile-core/src/ui/type.ts", "src/ui/type.ts"],
  plugins: { "bhojango-native": plugin },
  rules: { "bhojango-native/no-raw-font-size": "error" },
};

module.exports = plugin;
