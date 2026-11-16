// node --test: "Who gets your money" (R6, R7) shows whole percentages of the engine's
// split of a real bill (kitchen, rider pay + tip, tax, BhojanGo) that add up to 100.
import assert from "node:assert/strict";
import test from "node:test";

import { fairSplit } from "../src/lib/fairSplit.ts";

const sum = (s: { percent: number }[]) => s.reduce((a, b) => a + b.percent, 0);

test("Hyderabad example: the rider's share is their pay plus the tip, and the four add up to 100", () => {
  // ₹480 of food at 3.5 km with a ₹20 tip: rider pay 25 + 6 × 3.5 = ₹46, plus the tip.
  const split = fairSplit({ kitchen: "432.00", rider: "66.00", tax: "29.70", us: "12.30" })!;
  assert.deepEqual(split.map((p) => p.payee), ["kitchen", "rider", "tax", "us"]);
  assert.deepEqual(split.map((p) => p.amount), [432, 66, 29.7, 12.3]);
  assert.deepEqual(split.map((p) => p.percent), [80, 12, 6, 2]);
  assert.equal(sum(split), 100);
});

test("Boise example: no tip still pays the rider, and the four add up to 100", () => {
  // $28.00 of food at 2.5 mi, no tip: rider pay $3.00 + $1.00 × 2.5 = $5.50.
  const split = fairSplit({ kitchen: "23.80", rider: "5.50", tax: "1.84", us: "2.70" })!;
  assert.equal(split[1]!.payee, "rider");
  assert.ok(split[1]!.percent > 0, "the rider gets a share without a tip");
  assert.equal(sum(split), 100);
});

test("rounding never loses or adds a point", () => {
  for (const [kitchen, rider, tax, us] of [[1, 1, 1, 0], [10, 10, 10, 1], [638.22, 0, 0, 0], [33.33, 33.33, 33.34, 0], [7, 0.01, 0.01, 0.01]] as const) {
    assert.equal(sum(fairSplit({ kitchen, rider, tax, us })!), 100, String([kitchen, rider, tax, us]));
  }
});

test("an order that costs BhojanGo money: our share counts as nothing, still 100", () => {
  const split = fairSplit({ kitchen: "10.00", rider: "6.00", tax: "0.80", us: "-1.20" })!;
  assert.deepEqual(split.map((p) => [p.payee, p.amount]), [["kitchen", 10], ["rider", 6], ["tax", 0.8], ["us", 0]]);
  assert.equal(sum(split), 100);
});

test("no shares, or a zero bill, has no split", () => {
  assert.equal(fairSplit(null), null);
  assert.equal(fairSplit(undefined), null);
  assert.equal(fairSplit({ kitchen: 0, rider: 0, tax: 0, us: 0 }), null);
});
