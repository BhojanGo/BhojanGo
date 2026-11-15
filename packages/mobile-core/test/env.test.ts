// node --test: which builds show the test-site banner (pure logic, no React Native).
import assert from "node:assert/strict";
import test from "node:test";

import { isTestEnvironment, resolveAppEnv } from "../src/env.ts";

test("the env profile decides: qa and local are test sites, production is not", () => {
  assert.equal(resolveAppEnv({ appEnv: "qa" }), "qa");
  assert.equal(resolveAppEnv({ appEnv: "local", dev: true }), "local");
  assert.equal(resolveAppEnv({ appEnv: "production" }), "production");
  assert.equal(resolveAppEnv({ appEnv: "PROD" }), "production");
  assert.equal(isTestEnvironment(resolveAppEnv({ appEnv: "qa" })), true);
  assert.equal(isTestEnvironment(resolveAppEnv({ appEnv: "local" })), true);
  assert.equal(isTestEnvironment(resolveAppEnv({ appEnv: "production" })), false);
});

test("the older EXPO_PUBLIC_ENV still counts", () => {
  assert.equal(resolveAppEnv({ env: "qa" }), "qa");
  assert.equal(resolveAppEnv({ appEnv: "production", env: "qa" }), "production");
});

test("nothing set: a development build is local (banner), a release build is production (no banner)", () => {
  assert.equal(resolveAppEnv({ dev: true }), "local");
  assert.equal(isTestEnvironment(resolveAppEnv({ dev: true })), true);
  assert.equal(resolveAppEnv({ dev: false }), "production");
  assert.equal(isTestEnvironment(resolveAppEnv({ appEnv: "", dev: false })), false);
});
