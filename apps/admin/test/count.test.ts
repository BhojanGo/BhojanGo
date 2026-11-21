// node --test: counts in admin labels (R24): "1 issue to look at" / "2 issues to look at".
import assert from "node:assert/strict";
import test from "node:test";

import { count, word } from "../src/lib/count.ts";
import { describe, unitsFor } from "../src/lib/ruleWords.ts";

const US = unitsFor("US", [{ code: "US", currency: "USD", locales: ["en-US"], distance_unit: "mi" }]);

test("one is singular; zero, many and fractions are plural", () => {
  assert.equal(count(1, "issue"), "1 issue");
  assert.equal(count(2, "issue"), "2 issues");
  assert.equal(count(0, "issue"), "0 issues");
  assert.equal(count(1204, "order"), "1,204 orders");
  assert.equal(count(1, "city", "cities"), "1 city");
  assert.equal(count(3, "city", "cities"), "3 cities");
  assert.equal(word("1", "minute"), "minute");
  assert.equal(word(1.5, "hour"), "hours");
});

test("rule sentences say 1 minute, not 1 minutes", () => {
  assert.equal(describe("cancel_window", { minutes: 1 }, US), "Customers can cancel for free for 1 minute");
  assert.equal(describe("cancel_window", { minutes: 5 }, US), "Customers can cancel for free for 5 minutes");
  assert.equal(describe("refund_window", { hours: 1 }, US), "Refunds can be asked for up to 1 hour after delivery");
});
