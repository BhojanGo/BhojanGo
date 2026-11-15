// node --test: "Who gets your money" (R6) shows whole percentages of a real bill
// that add up to exactly 100, with each line counted for whoever gets it.
import assert from "node:assert/strict";
import test from "node:test";

import { fairSplit } from "../src/lib/fairSplit.ts";

const sum = (s: { percent: number }[]) => s.reduce((a, b) => a + b.percent, 0);

test("a bill's shares, in payee order, adding up to 100", () => {
  // food 480 + packaging 20 -> kitchen 500; delivery 40 + service 18 -> us 58; tax 25; tip 20
  const split = fairSplit([
    { code: "food", amount: "480.00" },
    { code: "packaging", amount: "20.00" },
    { code: "delivery_fee", amount: "40.00" },
    { code: "service_fee", amount: "18.00" },
    { code: "tax", amount: "25.00" },
    { code: "tip", amount: "20.00" },
  ])!;
  assert.deepEqual(split.map((p) => p.payee), ["kitchen", "rider", "tax", "us"]);
  assert.deepEqual(split.map((p) => p.amount), [500, 20, 25, 58]);
  assert.deepEqual(split.map((p) => p.percent), [83, 3, 4, 10]);
  assert.equal(sum(split), 100);
});

test("rounding never loses or adds a point", () => {
  for (const amounts of [[1, 1, 1, 0], [10, 10, 10, 1], [638.22, 0, 0, 0], [33.33, 33.33, 33.34, 0], [7, 0.01, 0.01, 0.01]]) {
    const [kitchen, rider, tax, us] = amounts as [number, number, number, number];
    const split = fairSplit([
      { code: "food", amount: kitchen },
      { code: "tip", amount: rider },
      { code: "tax", amount: tax },
      { code: "service_fee", amount: us },
    ])!;
    assert.equal(sum(split), 100, String(amounts));
  }
});

test("an offer lowers whoever funds it; a payee below zero counts as nothing", () => {
  const split = fairSplit([
    { code: "food", amount: "100" },
    { code: "delivery_fee", amount: "10" },
    { code: "promotion", amount: "-20", funded_by: "platform" },
    { code: "promotion", amount: "-10", funded_by: "restaurant" },
  ])!;
  assert.deepEqual(split.map((p) => [p.payee, p.amount, p.percent]), [["kitchen", 90, 100], ["rider", 0, 0], ["tax", 0, 0], ["us", 0, 0]]);
});

test("an empty or zero bill has no split", () => {
  assert.equal(fairSplit([]), null);
  assert.equal(fairSplit([{ code: "food", amount: "0" }]), null);
});
