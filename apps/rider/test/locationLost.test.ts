// node --test: R28, an online partner's position (lib/locationLogic.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { locationLost, LOST_AFTER_MS, SEND_EVERY_MS } from "../lib/locationLogic.ts";

test("every 5 s; lost after a minute without a position BhojanGo took", () => {
  assert.equal(SEND_EVERY_MS, 5000);
  assert.equal(LOST_AFTER_MS, 60000);
  const t = 1_000_000;
  assert.equal(locationLost(true, t - 5000, t - 600000, t), false);
  assert.equal(locationLost(true, t - 61000, t - 600000, t), true);
  // nothing sent yet: counted from going online
  assert.equal(locationLost(true, null, t - 30000, t), false);
  assert.equal(locationLost(true, null, t - 61000, t), true);
  assert.equal(locationLost(false, null, t - 600000, t), false, "offline: never");
});
