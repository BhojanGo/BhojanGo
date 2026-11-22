// node --test: R19 ordering blocks and the checkout's payment mode (lib/ordering.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { bagConflict, isFreeOrder, orderingBlock, payMode } from "../lib/ordering.ts";

test("a pause or a closed kitchen blocks adding dishes, the pause named first", () => {
  assert.equal(orderingBlock({ paused: false, closedForNow: false, isOpen: true }), null);
  assert.equal(orderingBlock({ paused: false }), null); // open unless told otherwise
  assert.equal(orderingBlock({ paused: true, closedForNow: true, isOpen: false }), "kitchen.bag_paused");
  assert.equal(orderingBlock({ paused: false, closedForNow: true, isOpen: true }), "kitchen.bag_closed_for_now");
  assert.equal(orderingBlock({ paused: false, closedForNow: false, isOpen: false }), "kitchen.bag_closed_for_now");
  // R27: open, but the kitchen's tablet isn't connected
  assert.equal(orderingBlock({ paused: false, closedForNow: false, isOpen: true, notTaking: true }), "kitchen.not_taking_orders");
  assert.equal(orderingBlock({ paused: true, notTaking: true }), "kitchen.bag_paused");
});

test("production never opens the test payment sheet", () => {
  assert.equal(payMode("stripe", true), "stripe");
  assert.equal(payMode("fake", true), "unavailable");
  assert.equal(payMode("razorpay", true), "unavailable"); // no in-app Razorpay checkout yet
  assert.equal(payMode("error", true), "retry"); // R28: a failed lookup is never "not available in this city"
  assert.equal(payMode(null, true), "loading");
});

test("test builds use the test sheet, but not when the provider can't be looked up", () => {
  assert.equal(payMode("fake", false), "test");
  assert.equal(payMode("razorpay", false), "test");
  assert.equal(payMode("stripe", false), "stripe");
  assert.equal(payMode("error", false), "retry");
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

test("R27: a kitchen closed by its hours says when orders open; outside the city's hours, when deliveries start", async () => {
  const { closedWords } = await import("../lib/ordering.ts");
  const t = (k: string) => k;
  const opens = (iso: string | null | undefined, zone?: string | null, keys?: { today: string; day: string }) =>
    iso ? `${keys?.today ?? "common.closed_opens"}@${iso}@${zone}` : null;
  assert.equal(closedWords({ open_now: true }, opens, t), null);
  assert.equal(closedWords(null, opens, t), null);
  assert.equal(closedWords({ open_now: false, reason_code: "closed", next_open_at: "2026-11-21T06:30:00-07:00", timezone: "America/Boise" }, opens, t),
    "common.closed_opens@2026-11-21T06:30:00-07:00@America/Boise");
  assert.equal(closedWords({ open_now: false, reason_code: "outside_delivery_hours", next_open_at: "2026-11-21T08:00:00-07:00", timezone: "America/Boise" }, opens, t),
    "kitchen.deliveries_start@2026-11-21T08:00:00-07:00@America/Boise");
  assert.equal(closedWords({ open_now: false, reason_code: "closed", next_open_at: null }, opens, t), "kitchen.bag_closed");
});

// R28: adding a dish from another kitchen asks before the bag is cleared (it was replaced silently).
test("bagConflict: only a bag with dishes from another kitchen asks", () => {
  const bag = { restaurantId: "k1", restaurantName: "Boise Bowl Co.", lines: [{}] };
  assert.equal(bagConflict(bag, "k2"), "Boise Bowl Co.");
  assert.equal(bagConflict(bag, "k1"), null, "same kitchen");
  assert.equal(bagConflict({ ...bag, lines: [] }, "k2"), null, "empty bag");
  assert.equal(bagConflict({ restaurantId: null, restaurantName: null, lines: [] }, "k2"), null);
});
