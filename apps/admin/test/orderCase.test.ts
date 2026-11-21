// node --test: the order case's refund panel and timeline (R27).
import assert from "node:assert/strict";
import test from "node:test";

import { refundState, timeline, type CaseItem, type CaseRefund } from "../src/lib/orderCase.ts";

const ITEMS: CaseItem[] = [
  { menu_item_id: "croissant", name: "Butter Croissant", quantity: 2, total: 8.5 },
  { menu_item_id: "latte", name: "Latte", quantity: 1, total: 5 },
];
const PAID = { amount: 1650, refunded_amount: 0, status: "succeeded" };

test("cancelled and refunded in full: nothing is offered (R26 #22C450)", () => {
  const full: CaseRefund = { id: "r1", amount: 1650, status: "succeeded", kind: "full", reason: "customer_cancelled", created_at: "2026-11-21T10:05:00Z", lines: [] };
  const s = refundState(ITEMS, [full], { amount: 1650, refunded_amount: 1650, status: "refunded" }, "USD", "cancelled");
  assert.equal(s.closed, true);
  assert.equal(s.closedText, "Cancelled and refunded in full: nothing left to refund.");
  assert.equal(s.leftMinor, 0);
  assert.ok(s.items.every((i) => i.left === 0));
  assert.deepEqual(s.done, ["$16.50 refunded in full (customer cancelled)"]);
});

test("a refunded payment closes the panel even before its refund rows load", () => {
  const s = refundState(ITEMS, [], { amount: 1650, refunded_amount: 1650, status: "refunded" }, "USD", "delivered");
  assert.equal(s.closed, true);
  assert.equal(s.closedText, "Refunded in full: nothing left to refund.");
});

test("items refunded already show per line, and only what's left can be picked", () => {
  const one: CaseRefund = { id: "r1", amount: 451, status: "succeeded", kind: "items", created_at: "2026-11-21T11:00:00Z",
    lines: [{ menu_item_id: "croissant", name: "Butter Croissant", quantity: 1, amount: "4.51" }] };
  const s = refundState(ITEMS, [one], { ...PAID, refunded_amount: 451, status: "partially_refunded" }, "USD", "delivered");
  assert.equal(s.closed, false);
  assert.deepEqual(s.done, ["1 × Butter Croissant refunded $4.51"]);
  assert.deepEqual(s.items.map((i) => [i.menu_item_id, i.refunded, i.left]), [["croissant", 1, 1], ["latte", 0, 1]]);
  assert.equal(s.leftMinor, 1199);
});

test("every item and the delivery fee refunded: closed", () => {
  const all: CaseRefund = { id: "r1", amount: 1400, status: "succeeded", kind: "items", created_at: "2026-11-21T11:00:00Z",
    lines: [{ menu_item_id: "croissant", name: "Butter Croissant", quantity: 2, amount: "9.02" }, { menu_item_id: "latte", name: "Latte", quantity: 1, amount: "5.30" },
      { code: "delivery_fee", name: "Delivery fee", amount: "1.99" }] };
  const s = refundState(ITEMS, [all], { ...PAID, refunded_amount: 1400, status: "partially_refunded" }, "USD", "delivered");
  assert.equal(s.closed, true);
  assert.match(s.closedText!, /nothing left/);
  assert.equal(s.deliveryRefunded, true);
});

test("never paid: nothing to refund; failed refunds don't count", () => {
  assert.equal(refundState(ITEMS, [], null, "USD", "cancelled").closedText, "Not paid: nothing to refund.");
  const failed: CaseRefund = { id: "r1", amount: 500, status: "failed", kind: "items", created_at: "2026-11-21T11:00:00Z",
    lines: [{ menu_item_id: "latte", name: "Latte", quantity: 1, amount: "5" }] };
  const s = refundState(ITEMS, [failed], PAID, "USD", "delivered");
  assert.equal(s.closed, false);
  assert.equal(s.items[1]!.left, 1);
  assert.deepEqual(s.done, []);
});

test("the timeline shows every step, paid and picked up included, then refunds, oldest first", () => {
  const history = ["pending_payment", "placed", "accepted", "preparing", "almost_ready", "ready", "picked_up", "delivered"]
    .map((status, n) => ({ status, at: `2026-11-21T10:${String(n * 5).padStart(2, "0")}:00Z` }));
  const refund: CaseRefund = { id: "r1", amount: 451, status: "succeeded", created_at: "2026-11-21T10:50:00Z" };
  const steps = timeline(history, [refund], "USD").map((s) => s.label);
  assert.deepEqual(steps, ["Ordered", "Paid", "Accepted", "Cooking", "Almost ready", "Ready", "Picked up", "Delivered", "Refunded $4.51"]);
});
