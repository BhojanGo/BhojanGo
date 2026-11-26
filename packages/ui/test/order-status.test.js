// node --test: R44 an order's shown status never goes backwards (a late "preparing" after "ready").
import assert from "node:assert/strict";
import test from "node:test";

import { nextLiveStatus, shownStatus } from "../order-status.js";

test("a late socket status for an earlier step doesn't win over the order's", () => {
  assert.equal(shownStatus("ready", "preparing"), "ready");
  assert.equal(shownStatus("preparing", "ready"), "ready");
  assert.equal(shownStatus("picked_up", "almost_ready"), "picked_up");
  assert.equal(shownStatus("delivered", "picked_up"), "delivered");
});

test("no live status: the order's; unknown live values don't replace it", () => {
  assert.equal(shownStatus("accepted", null), "accepted");
  assert.equal(shownStatus(undefined, null), "placed");
  assert.equal(shownStatus("ready", "something_new"), "ready");
});

test("cancelled always shows", () => {
  assert.equal(shownStatus("preparing", "cancelled"), "cancelled");
  assert.equal(shownStatus("cancelled", "ready"), "cancelled");
});

test("the live status only moves forward", () => {
  assert.equal(nextLiveStatus("ready", "preparing"), "ready");
  assert.equal(nextLiveStatus("preparing", "ready"), "ready");
  assert.equal(nextLiveStatus(null, "preparing"), "preparing");
  assert.equal(nextLiveStatus("ready", undefined), "ready");
  assert.equal(nextLiveStatus("ready", "cancelled"), "cancelled");
  assert.equal(nextLiveStatus("cancelled", "ready"), "cancelled");
});
