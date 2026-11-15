// node --test: the test-site banner shows everywhere except production.
const test = require("node:test");
const assert = require("node:assert/strict");
const { isProduction, showTestBanner } = require("../environment");

test("production hides the test-site banner", () => {
  assert.equal(showTestBanner("production"), false);
  assert.equal(showTestBanner(" Production "), false);
  assert.equal(isProduction("production"), true);
});

test("every other environment shows it, unset included", () => {
  for (const env of ["qa", "staging", "test", "development", "", undefined, null, "prod"]) {
    assert.equal(showTestBanner(env), true, String(env));
    assert.equal(isProduction(env), false, String(env));
  }
});
