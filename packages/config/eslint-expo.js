// Flat ESLint config for the Expo apps and mobile packages (ESLint 9).
const { defineConfig, globalIgnores } = require("eslint/config");
const expoConfig = require("eslint-config-expo/flat");

module.exports = defineConfig([
  expoConfig,
  globalIgnores(["dist/**", ".expo/**", "android/**", "ios/**", "babel.config.js", "metro.config.js", "tailwind.config.js"]),
]);
