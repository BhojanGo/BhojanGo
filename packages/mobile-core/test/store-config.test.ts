// node --test: R19 store ids and the production build guard (plugins/store-config.js),
// and the checked-in config/store.json and apps/*/eas.json.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { applyStoreConfig, isPlaceholder, loadStore, productionProblems } = require("../plugins/store-config.js");

const REAL = {
  apple: { teamId: "AB12CD34EF", applePayMerchantId: "merchant.com.example.app" },
  google: { serviceAccountKeyPath: "./secrets/play.json" },
  apps: {
    customer: { easProjectId: "0b6c2f4e-8f1a-4c4e-9a52-3c1f0d2b7e91", iosBundleId: "com.example.app", ascAppId: "1234567890",
      androidPackage: "com.example.app", applePay: true },
  },
};
const PROD_ENV = {
  EAS_BUILD_PROFILE: "production", EXPO_PUBLIC_APP_ENV: "production",
  EXPO_PUBLIC_CORE_URL: "https://api.example.com", EXPO_PUBLIC_REALTIME_URL: "https://rt.example.com", EXPO_PUBLIC_WEB_URL: "https://www.example.com",
};
const BASE = { name: "BhojanGo", ios: { bundleIdentifier: "x" }, android: { package: "x" }, extra: { eas: { projectId: "your-eas-project-id" } },
  plugins: ["expo-router", ["@stripe/stripe-react-native", { enableGooglePay: true }]] };

test("placeholders are recognised", () => {
  for (const v of ["{APPLE_TEAM_ID}", "your-eas-project-id", "", undefined, "REPLACE_ME"]) assert.equal(isPlaceholder(v), true, String(v));
  for (const v of ["AB12CD34EF", "com.bhojango.app", "0b6c2f4e-8f1a-4c4e-9a52-3c1f0d2b7e91"]) assert.equal(isPlaceholder(v), false, v);
});

test("a ready production build gets its ids, encryption answered, the Apple Pay merchant", () => {
  const c = applyStoreConfig(BASE, "customer", { env: PROD_ENV, store: REAL });
  assert.equal(c.ios.bundleIdentifier, "com.example.app");
  assert.equal(c.ios.appleTeamId, "AB12CD34EF");
  assert.equal(c.ios.config.usesNonExemptEncryption, false);
  assert.equal(c.android.package, "com.example.app");
  assert.equal(c.extra.eas.projectId, "0b6c2f4e-8f1a-4c4e-9a52-3c1f0d2b7e91");
  assert.deepEqual(c.plugins[1], ["@stripe/stripe-react-native", { enableGooglePay: true, merchantIdentifier: "merchant.com.example.app" }]);
});

test("a production build stops on a placeholder id, an http or localhost address, or a non-production APP_ENV", () => {
  const placeholder = { ...REAL, apple: { ...REAL.apple, applePayMerchantId: "{APPLE_PAY_MERCHANT_ID}" } };
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: PROD_ENV, store: placeholder }), /applePayMerchantId is a placeholder/);
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: { ...PROD_ENV, EXPO_PUBLIC_CORE_URL: "http://api.example.com" }, store: REAL }), /must be https/);
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: { ...PROD_ENV, EXPO_PUBLIC_WEB_URL: "https://localhost:3000" }, store: REAL }), /this computer/);
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: { ...PROD_ENV, EXPO_PUBLIC_REALTIME_URL: "https://{REALTIME_HOST}" }, store: REAL }), /placeholder/);
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: { ...PROD_ENV, EXPO_PUBLIC_APP_ENV: "qa" }, store: REAL }), /not "production"/);
  const { EXPO_PUBLIC_CORE_URL: _gone, ...noCore } = PROD_ENV;
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: noCore, store: REAL }), /EXPO_PUBLIC_CORE_URL is not set/);
  // APP_ENV=production on its own (a local release build) is checked the same way.
  assert.throws(() => applyStoreConfig(BASE, "customer", { env: { EXPO_PUBLIC_APP_ENV: "production" }, store: REAL }), /not set/);
});

test("other builds take the real ids and skip placeholders without failing", () => {
  const c = applyStoreConfig(BASE, "customer", { env: { EXPO_PUBLIC_APP_ENV: "qa" }, store: loadStore() });
  assert.equal(c.ios.bundleIdentifier, "com.bhojango.app");
  assert.equal(c.extra.eas.projectId, "your-eas-project-id"); // untouched: push skips it quietly
  assert.equal(c.ios.appleTeamId, undefined);
  assert.equal(c.ios.config.usesNonExemptEncryption, false);
  assert.deepEqual(c.plugins[1], ["@stripe/stripe-react-native", { enableGooglePay: true }]);
});

test("the checked-in store file and eas.json: all three apps, production stops until filled in", () => {
  const store = loadStore();
  for (const app of ["customer", "partner", "rider"]) {
    assert.ok(productionProblems(store, app, PROD_ENV).some((p: string) => p.includes("easProjectId")), app);
    const eas = JSON.parse(readFileSync(new URL(`../../../apps/${app}/eas.json`, import.meta.url), "utf8"));
    assert.deepEqual(Object.keys(eas.build).filter((k) => k !== "base"), ["development", "preview", "production"]);
    const prod = eas.build.production.env;
    assert.equal(prod.EXPO_PUBLIC_APP_ENV, "production");
    for (const k of ["EXPO_PUBLIC_CORE_URL", "EXPO_PUBLIC_REALTIME_URL", "EXPO_PUBLIC_WEB_URL"]) assert.match(prod[k], /^https:\/\//);
  }
});
