// node --test: R37, India's bill to the paisa. Every bill fixture (packages/ui/test/fixtures/bills.json, US and
// India, from the quote engine), printed the way the website's fair bill prints it, adds up to the printed total;
// menus and carts keep whole rupees.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { money } from "../src/lib/format.ts";

interface Line { code: string; amount: string }
interface Bill { name: string; currency: string; locale: string; lines: Line[]; total: string }

const BILLS: Bill[] = JSON.parse(readFileSync(new URL("../../../packages/ui/test/fixtures/bills.json", import.meta.url), "utf8"));
const cents = (shown: string) => {
  const negative = shown.startsWith("−") || shown.startsWith("-");
  const [whole, frac = ""] = shown.replace(/[^0-9.]/g, "").split(".");
  return (negative ? -1 : 1) * (Number(whole) * 100 + Number((frac + "00").slice(0, 2)));
};

for (const b of BILLS) {
  test(`${b.name}: the fair bill's lines add up to the total (website)`, () => {
    const shown = b.lines.filter((l) => Math.abs(Number(l.amount)) >= 0.005).map((l) => money(l.amount, b.currency, b.locale, { exact: true }));
    assert.equal(shown.reduce((s, x) => s + cents(x), 0), cents(money(b.total, b.currency, b.locale, { exact: true })), shown.join(" + "));
  });
}

test("Hyderabad: ₹300 food, 2.50 km, UPI is ₹300.00 + ₹30.00 + ₹30.00 + GST ₹25.80 = ₹385.80", () => {
  const b = BILLS.find((x) => x.name.startsWith("Hyderabad ₹300"));
  assert.ok(b);
  const shown = b.lines.map((l) => money(l.amount, "INR", "en-IN", { exact: true }));
  assert.deepEqual(shown.slice(0, 3), ["₹300.00", "₹30.00", "₹30.00"]);
  const gst = b.lines.filter((l) => l.code === "tax").reduce((s, l) => s + cents(money(l.amount, "INR", "en-IN", { exact: true })), 0);
  assert.equal(gst, 2580);
  assert.equal(money(b.total, "INR", "en-IN", { exact: true }), "₹385.80");
  assert.equal(money("289.40", "INR", "en-IN"), "₹289"); // a menu price: whole rupees
});
