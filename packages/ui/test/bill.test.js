// node --test: the fair bill rows (shared by web and the apps).
const test = require("node:test");
const assert = require("node:assert/strict");
const { billRows, money, billTotal } = require("../bill");

test("money in rupees and dollars", () => {
  assert.equal(money(596.92, "INR"), "₹596.92");
  assert.equal(money(124050, "INR"), "₹1,24,050.00");
  assert.equal(money(-50, "INR"), "−₹50.00");
  // One format everywhere (R12): always two decimals.
  assert.equal(money(300, "INR"), "₹300.00");
  assert.equal(money(29, "USD"), "$29.00");
  assert.equal(money(1240.5, "USD"), "$1,240.50");
});

test("each row says who gets the money", () => {
  const lines = [
    { code: "food", label: "Food", amount: "560.00" },
    { code: "promotion", label: "Code BHOJAN10", amount: "-50.00", funded_by: "platform" },
    { code: "packaging", label: "Packaging", amount: "10.00" },
    { code: "service_fee", label: "Service fee", amount: "11.20" },
    { code: "tax", label: "GST", amount: "30.72" },
    { code: "tip", label: "Tip", amount: "20.00" },
  ];
  assert.deepEqual(billRows(lines, "INR").map((r) => [r.label, r.payee, r.amount]), [
    ["Food", "Restaurant", "₹560.00"], ["Code BHOJAN10", "BhojanGo", "−₹50.00"], ["Packaging", "Restaurant", "₹10.00"],
    ["Service fee", "BhojanGo", "₹11.20"], ["GST", "Government", "₹30.72"], ["Tip", "100% to your delivery partner", "₹20.00"],
  ]);
  assert.equal(billRows(lines, "INR")[1].accent, true);
});

test("free delivery the kitchen pays is one row, struck through", () => {
  const lines = [
    { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
    { code: "promotion", label: "Free delivery", amount: "-35.00", funded_by: "restaurant" },
  ];
  assert.deepEqual(billRows(lines, "INR"), [
    { label: "Delivery · 4.2 km", payee: "Restaurant's treat", amount: "₹0.00", struck: "₹35.00" },
  ]);
  assert.equal(billTotal(lines), 0);
});

test("the delivery fee is BhojanGo's, not the delivery partner's: only the tip is DELIVERY PARTNER", () => {
  const lines = [
    { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
    { code: "tip", label: "Tip for your delivery partner", amount: "20.00" },
  ];
  assert.deepEqual(billRows(lines, "INR").map((r) => r.payee), ["BhojanGo", "100% to your delivery partner"]);
});

test("a line of 0 is not shown, and the total still counts every line (R12: Ada sales tax $0.00)", () => {
  const lines = [
    { code: "food", label: "Food", amount: "29.00" },
    { code: "tax", label: "Ada sales tax", amount: "0.00" },
    { code: "service_fee", label: "Service fee", amount: "0" },
  ];
  assert.deepEqual(billRows(lines, "USD").map((r) => [r.label, r.amount]), [["Food", "$29.00"]]);
  assert.equal(billTotal(lines), 29);
});

// R27: refunds on the receipt (R26: neither the receipt nor the PDF said a refund was made).
test("a receipt names each refund and what was paid after them", () => {
  const { receiptRefunds } = require("../bill");
  const partial = receiptRefunds({ total: "17.50", paid: "12.99", refunds: [{ amount: "4.51", kind: "items", reason: "missing_item", items: ["Butter Croissant"] }] }, false);
  assert.deepEqual(partial, { refunds: [{ amount: 4.51, reason: "missing_item", items: ["Butter Croissant"] }], refunded: 4.51, paid: 12.99 });
  const cancelled = receiptRefunds({ total: "17.50", paid: "0.00", refunds: [{ amount: "17.50", kind: "full", reason: "full" }] }, true);
  assert.deepEqual(cancelled.refunds.map((r) => r.reason), ["cancelled"]);
  assert.equal(cancelled.paid, 0);
  // A whole-order refund on a delivered order (an incident) stays "full refund"; an unknown reason is "other".
  assert.equal(receiptRefunds({ total: "10", refunds: [{ amount: "10", reason: "full" }] }, false).refunds[0].reason, "full");
  assert.equal(receiptRefunds({ total: "10", refunds: [{ amount: "1", reason: "weird" }] }, false).refunds[0].reason, "other");
  // An older API without "paid": the total less the refunds.
  assert.equal(receiptRefunds({ total: "17.50", refunds: [{ amount: "4.51", reason: "quality" }] }, false).paid, 12.99);
  assert.deepEqual(receiptRefunds({ total: "17.50" }, false), { refunds: [], refunded: 0, paid: 17.5 });
});

test("R29 fee model v2: who gets your money (food, delivery, tip, platform fee, tax)", () => {
  const lines = [
    { code: "food", label: "Food", amount: "36.98" },
    { code: "delivery_fee", label: "Delivery fee", amount: "3.99" },
    { code: "platform_fee", label: "Platform fee", amount: "3.70" },
    { code: "tax", label: "Idaho sales tax", amount: "2.22" },
    { code: "tip", label: "Tip for your delivery partner", amount: "2.00" },
  ];
  assert.deepEqual(billRows(lines, "USD").map((r) => [r.label, r.payee, r.amount]), [
    ["Food", "Restaurant", "$36.98"],
    ["Delivery fee", "100% to your delivery partner", "$3.99"],
    ["Platform fee", "BhojanGo", "$3.70"],
    ["Idaho sales tax", "Government", "$2.22"],
    ["Tip for your delivery partner", "100% to your delivery partner", "$2.00"],
  ]);
  // A bill from before R29 (no platform fee line): the delivery fee was BhojanGo's.
  assert.equal(billRows([{ code: "delivery_fee", label: "Delivery fee", amount: "1.99" }], "USD")[0].payee, "BhojanGo");
  const { payeeOf } = require("../bill");
  assert.equal(payeeOf({ code: "delivery_fee" }, lines), "DELIVERY PARTNER");
  assert.equal(payeeOf({ code: "platform_fee" }, lines), "BHOJANGO");
});
