// node --test: R19 ordering blocks and the checkout's payment mode (lib/ordering.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { orderingBlock, payMode } from "../lib/ordering.ts";

test("a pause or a closed kitchen blocks adding dishes, the pause named first", () => {
  assert.equal(orderingBlock({ paused: false, closedForNow: false, isOpen: true }), null);
  assert.equal(orderingBlock({ paused: false }), null); // open unless told otherwise
  assert.equal(orderingBlock({ paused: true, closedForNow: true, isOpen: false }), "kitchen.bag_paused");
  assert.equal(orderingBlock({ paused: false, closedForNow: true, isOpen: true }), "kitchen.bag_closed_for_now");
  assert.equal(orderingBlock({ paused: false, closedForNow: false, isOpen: false }), "kitchen.bag_closed_for_now");
});

test("production never opens the test payment sheet", () => {
  assert.equal(payMode("stripe", true), "stripe");
  assert.equal(payMode("fake", true), "unavailable");
  assert.equal(payMode("razorpay", true), "unavailable"); // no in-app Razorpay checkout yet
  assert.equal(payMode("error", true), "unavailable");
  assert.equal(payMode(null, true), "loading");
});

test("test builds use the test sheet, but not when the provider can't be looked up", () => {
  assert.equal(payMode("fake", false), "test");
  assert.equal(payMode("razorpay", false), "test");
  assert.equal(payMode("stripe", false), "stripe");
  assert.equal(payMode("error", false), "unavailable");
});
