// node --test: R36, customers in India read whole rupees (₹289), rounded half up for display only.
import assert from "node:assert/strict";
import test from "node:test";

import { halfUpWhole, money } from "../src/lib/format.ts";

test("half up to whole rupees, away from zero, without float noise", () => {
  assert.deepEqual([289, 289.4, 289.49, 289.5, 558.54, 1.005, -48.5, -48.4].map(halfUpWhole), [289, 289, 289, 290, 559, 1, -49, -48]);
});

test("India: whole rupees by default, the paise when asked (restaurant pages)", () => {
  assert.equal(money("289.40", "INR", "en-IN"), "₹289");
  assert.equal(money("124050.50", "INR", "en-IN"), "₹1,24,051");
  assert.equal(money("-48.50", "INR", "en-IN"), "−₹49");
  assert.equal(money("289.40", "INR", "en-IN", { exact: true }), "₹289.40");
});

test("dollars keep cents", () => {
  assert.equal(money("14.5", "USD", "en-US"), "$14.50");
});
