// node --test: production never falls back to the fake card form or checkout (R19).
import assert from "node:assert/strict";
import test from "node:test";

import { fakeCheckoutAllowed, paymentsMode } from "../src/lib/payments.ts";

test("outside production, unset or fake is the test provider", () => {
  for (const env of [undefined, "", "development", "qa", "staging", "test"]) {
    assert.equal(paymentsMode(undefined, env), "test");
    assert.equal(paymentsMode("", env), "test");
    assert.equal(paymentsMode("fake", env), "test");
  }
});

test("production with no provider, or the fake one, is unavailable (fails closed)", () => {
  for (const env of ["production", " Production "]) {
    assert.equal(paymentsMode(undefined, env), "unavailable");
    assert.equal(paymentsMode("", env), "unavailable");
    assert.equal(paymentsMode(" FAKE ", env), "unavailable");
  }
});

test("a real provider is live everywhere", () => {
  for (const env of [undefined, "qa", "production"]) {
    assert.equal(paymentsMode("stripe", env), "live");
    assert.equal(paymentsMode("razorpay", env), "live");
  }
});

test("the fake checkout never opens in production", () => {
  assert.equal(fakeCheckoutAllowed("production"), false);
  assert.equal(fakeCheckoutAllowed("qa"), true);
  assert.equal(fakeCheckoutAllowed(undefined), true);
});
