// Which environment a build runs in (APP_ENV: production, staging, qa, test, development).
// Shared by web and admin; no DOM, no React. Everything that is not production
// shows the test-site banner (and is noindex): only production is real.

/** True only for APP_ENV=production (case and spaces ignored); unset counts as not production. */
function isProduction(appEnv) {
  return String(appEnv ?? "").trim().toLowerCase() === "production";
}

/** The "Test site: demo kitchens, no real orders or payments" banner: everywhere but production. */
function showTestBanner(appEnv) {
  return !isProduction(appEnv);
}

module.exports = { isProduction, showTestBanner };
