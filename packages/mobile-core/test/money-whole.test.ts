// node --test: R36, India in whole rupees for customers, rounded half up for display only.
import assert from "node:assert/strict";
import test from "node:test";

import { formatMoney, halfUpWhole, wholeForCustomers } from "../src/locale.ts";

test("half up to whole rupees, away from zero, without float noise", () => {
  assert.equal(halfUpWhole(289), 289);
  assert.equal(halfUpWhole(289.4), 289);
  assert.equal(halfUpWhole(289.49), 289);
  assert.equal(halfUpWhole(289.5), 290);
  assert.equal(halfUpWhole(558.54), 559);
  assert.equal(halfUpWhole(1.005), 1);
  assert.equal(halfUpWhole(-48.5), -49);
  assert.equal(halfUpWhole(-48.4), -48);
});

test("₹289 for customers, the exact amount otherwise", () => {
  assert.equal(formatMoney("289.40", "INR", "en-IN", { whole: true }), "₹289");
  assert.equal(formatMoney("124050.50", "INR", "en-IN", { whole: true }), "₹1,24,051");
  assert.equal(formatMoney("-48.50", "INR", "en-IN", { whole: true }), "−₹49");
  assert.equal(formatMoney("289.40", "INR", "en-IN"), "₹289.40");
});

test("only rupees are whole; dollars keep cents", () => {
  assert.equal(wholeForCustomers("INR"), true);
  assert.equal(wholeForCustomers("USD"), false);
  assert.equal(formatMoney("14.50", "USD", "en-US", { whole: wholeForCustomers("USD") }), "$14.50");
});
