// node --test: R37, the app's fair bill to the paisa (useI18n().bill = formatMoney without `whole`). Every bill
// fixture (packages/ui/test/fixtures/bills.json, US and India) adds up to the printed total.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { formatMoney } from "../src/locale.ts";

interface Line { code: string; amount: string }
interface Bill { name: string; currency: string; locale: string; lines: Line[]; total: string }

const BILLS: Bill[] = JSON.parse(readFileSync(new URL("../../ui/test/fixtures/bills.json", import.meta.url), "utf8"));
const cents = (shown: string) => {
  const negative = shown.startsWith("−") || shown.startsWith("-");
  const [whole, frac = ""] = shown.replace(/[^0-9.]/g, "").split(".");
  return (negative ? -1 : 1) * (Number(whole) * 100 + Number((frac + "00").slice(0, 2)));
};

for (const b of BILLS) {
  test(`${b.name}: the app's fair bill adds up to its total`, () => {
    const shown = b.lines.filter((l) => Math.abs(Number(l.amount)) >= 0.005).map((l) => formatMoney(l.amount, b.currency, b.locale));
    assert.equal(shown.reduce((s, x) => s + cents(x), 0), cents(formatMoney(b.total, b.currency, b.locale)), shown.join(" + "));
  });
}

test("India in the app: the bill in paise, a menu price whole", () => {
  assert.equal(formatMoney("385.80", "INR", "en-IN"), "₹385.80");
  assert.equal(formatMoney("289.40", "INR", "en-IN", { whole: true }), "₹289");
});
