// node --test: R19 ordering blocks and the checkout's payment mode (lib/ordering.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { isFreeOrder, orderingBlock, payMode } from "../lib/ordering.ts";

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

test("only a quote of exactly nothing skips payment (R20 review orders)", () => {
  assert.equal(isFreeOrder("0.00"), true);
  assert.equal(isFreeOrder(0), true);
  assert.equal(isFreeOrder("0.01"), false);
  assert.equal(isFreeOrder("12.40"), false);
  assert.equal(isFreeOrder(""), false);
  assert.equal(isFreeOrder(null), false);
  assert.equal(isFreeOrder(undefined), false);
  assert.equal(isFreeOrder("not a number"), false);
});
