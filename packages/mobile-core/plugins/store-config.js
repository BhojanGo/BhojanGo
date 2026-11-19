// Store ids and the production build guard (R19), used by all three apps' app.config.js.
//
// config/store.json (repo root) holds every store id: EAS project ids, iOS bundle ids and
// App Store Connect app ids, the Apple team, Android packages, the Play service account key
// path and the Apple Pay merchant id. Values written {LIKE_THIS} are placeholders.
//
// A production build (EAS build profile "production", or EXPO_PUBLIC_APP_ENV=production)
// throws here, before anything is built, when:
//   - EXPO_PUBLIC_APP_ENV is not "production" (a QA .env.local left on the machine),
//   - an API or web address is missing, not https, localhost/an emulator address, or a placeholder,
//   - a store id the app needs is still a placeholder.
// Other builds (development, preview, expo start) take whatever ids are real and skip the rest.
"use strict";

const fs = require("fs");
const path = require("path");

const STORE_FILE = path.join(__dirname, "..", "..", "..", "config", "store.json");
const URL_VARS = ["EXPO_PUBLIC_CORE_URL", "EXPO_PUBLIC_REALTIME_URL", "EXPO_PUBLIC_WEB_URL"];
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0", "10.0.2.2", "[::1]"]);

function loadStore(file = STORE_FILE) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

/** A placeholder ({LIKE_THIS}, the old "your-..." value) or nothing at all. */
function isPlaceholder(value) {
  if (typeof value !== "string" || !value.trim()) return true;
  const v = value.trim();
  return /[{}]/.test(v) || /^your-/i.test(v) || /REPLACE|CHANGE_?ME|TODO/i.test(v);
}

function isProductionBuild(env) {
  return env.EAS_BUILD_PROFILE === "production" || String(env.EXPO_PUBLIC_APP_ENV || "").trim().toLowerCase() === "production";
}

/** Why an address can't ship in a store build, or null. */
function urlProblem(name, value) {
  if (!value) return `${name} is not set`;
  if (/[{}]/.test(value)) return `${name} is a placeholder (${value})`;
  let u;
  try {
    u = new URL(value);
  } catch {
    return `${name} is not a valid address (${value})`;
  }
  if (u.protocol !== "https:") return `${name} must be https (${value})`;
  if (LOCAL_HOSTS.has(u.hostname) || u.hostname.endsWith(".local")) return `${name} points at this computer (${value})`;
  return null;
}

/** The ids one app needs from the store file: [label, value]. */
function idsFor(store, appKey) {
  const app = (store.apps || {})[appKey];
  if (!app) throw new Error(`config/store.json has no apps.${appKey}`);
  const apple = store.apple || {};
  const ids = [
    [`apps.${appKey}.easProjectId`, app.easProjectId],
    [`apps.${appKey}.iosBundleId`, app.iosBundleId],
    [`apps.${appKey}.ascAppId`, app.ascAppId],
    [`apps.${appKey}.androidPackage`, app.androidPackage],
    ["apple.teamId", apple.teamId],
    ["google.serviceAccountKeyPath", (store.google || {}).serviceAccountKeyPath],
  ];
  if (app.applePay) ids.push(["apple.applePayMerchantId", apple.applePayMerchantId]);
  return ids;
}

/** Everything that stops a production build of this app (empty: it may build). */
function productionProblems(store, appKey, env) {
  const problems = [];
  const appEnv = String(env.EXPO_PUBLIC_APP_ENV || "").trim().toLowerCase();
  if (appEnv !== "production") problems.push(`EXPO_PUBLIC_APP_ENV is "${env.EXPO_PUBLIC_APP_ENV || ""}", not "production"`);
  for (const name of URL_VARS) {
    const p = urlProblem(name, env[name]);
    if (p) problems.push(p);
  }
  for (const [label, value] of idsFor(store, appKey)) {
    if (isPlaceholder(value)) problems.push(`config/store.json ${label} is a placeholder (${value})`);
  }
  return problems;
}

/**
 * Apply the store ids to an app's Expo config (real ids only) and refuse a production build
 * that isn't ready. `appKey`: customer | partner | rider.
 */
function applyStoreConfig(config, appKey, { env = process.env, store = loadStore() } = {}) {
  if (isProductionBuild(env)) {
    const problems = productionProblems(store, appKey, env);
    if (problems.length) {
      throw new Error(`Production build of ${config.name || appKey} stopped (config/store.json, eas.json):\n  - ${problems.join("\n  - ")}`);
    }
  }
  const app = store.apps[appKey];
  const apple = store.apple || {};
  const real = (v) => !isPlaceholder(v);
  const ios = { ...(config.ios || {}) };
  const android = { ...(config.android || {}) };
  if (real(app.iosBundleId)) ios.bundleIdentifier = app.iosBundleId;
  if (real(apple.teamId)) ios.appleTeamId = apple.teamId;
  // Only HTTPS and the system's standard encryption: no export compliance question on each upload.
  ios.config = { ...(ios.config || {}), usesNonExemptEncryption: false };
  if (real(app.androidPackage)) android.package = app.androidPackage;
  const extra = { ...(config.extra || {}) };
  if (real(app.easProjectId)) extra.eas = { ...(extra.eas || {}), projectId: app.easProjectId };
  let plugins = config.plugins || [];
  if (app.applePay && real(apple.applePayMerchantId)) {
    plugins = plugins.map((p) => {
      const [name, options] = Array.isArray(p) ? p : [p, {}];
      return name === "@stripe/stripe-react-native" ? [name, { ...options, merchantIdentifier: apple.applePayMerchantId }] : p;
    });
  }
  return { ...config, ios, android, extra, plugins };
}

module.exports = { applyStoreConfig, isPlaceholder, isProductionBuild, loadStore, productionProblems, urlProblem, STORE_FILE };
