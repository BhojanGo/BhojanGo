// node --test: R37, every bill fixture (US and India, from the quote engine: fixtures/bills.json, also read
// by apps/web/test/billSum.test.ts, packages/mobile-core/test/bill-sum.test.ts and the backend's
// pricing/tests/test_bill_fixtures.py): the fair bill's rows, as printed, add up to the printed total.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { billRows, billTotal, money } from "../bill.js";

const BILLS = JSON.parse(readFileSync(new URL("./fixtures/bills.json", import.meta.url), "utf8"));

/** "−₹1,24,050.80" -> -124050.8 (in cents, to add without float noise). */
export function cents(shown) {
  const negative = shown.startsWith("−") || shown.startsWith("-");
  const digits = shown.replace(/[^0-9.]/g, "");
  const [whole, frac = ""] = digits.split(".");
  return (negative ? -1 : 1) * (Number(whole) * 100 + Number((frac + "00").slice(0, 2)));
}

test("there are US and India bills, with discounts, taxes, free delivery and pickup", () => {
  assert.ok(BILLS.length >= 6);
  assert.ok(BILLS.some((b) => b.currency === "INR") && BILLS.some((b) => b.currency === "USD"));
  const codes = new Set(BILLS.flatMap((b) => b.lines.map((l) => l.code)));
  for (const c of ["food", "delivery_fee", "platform_fee", "tax", "promotion"]) assert.ok(codes.has(c), c);
});

for (const b of BILLS) {
  test(`${b.name}: the printed rows add up to the printed total`, () => {
    const rows = billRows(b.lines, b.currency);
    const sum = rows.reduce((s, r) => s + cents(r.amount), 0);
    assert.equal(sum, cents(money(b.total, b.currency)), JSON.stringify(rows));
    assert.equal(Math.round(billTotal(b.lines) * 100), cents(money(b.total, b.currency)));
  });
}
