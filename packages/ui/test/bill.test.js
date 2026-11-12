// node --test: the fair bill rows (shared by web and the apps).
const test = require("node:test");
const assert = require("node:assert/strict");
const { billRows, money, billTotal } = require("../bill");

test("money in rupees and dollars", () => {
  assert.equal(money(596.92, "INR"), "₹596.92");
  assert.equal(money(124050, "INR"), "₹1,24,050.00");
  assert.equal(money(-50, "INR"), "−₹50.00");
  // Whole amounts can drop ".00"; cents are never rounded away (P22: "$14.50" showed as "$15").
  assert.equal(money(240, "INR", { decimals: 0 }), "₹240");
  assert.equal(money(14.5, "USD", { decimals: 0 }), "$14.50");
  assert.equal(money(3, "USD", { decimals: 0 }), "$3");
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
    ["Food", "KITCHEN", "₹560.00"], ["Code BHOJAN10", "US", "−₹50.00"], ["Packaging", "KITCHEN", "₹10.00"],
    ["Service fee", "US", "₹11.20"], ["GST", "GOVT", "₹30.72"], ["Tip", "RIDER", "₹20.00"],
  ]);
  assert.equal(billRows(lines, "INR")[1].accent, true);
});

test("free delivery the kitchen pays is one row, struck through", () => {
  const lines = [
    { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
    { code: "promotion", label: "Free delivery", amount: "-35.00", funded_by: "restaurant" },
  ];
  assert.deepEqual(billRows(lines, "INR"), [
    { label: "Delivery · 4.2 km", payee: "KITCHEN'S TREAT", amount: "₹0", struck: "₹35" },
  ]);
  assert.equal(billTotal(lines), 0);
});

test("the delivery fee is ours, not the rider's: only the tip is RIDER", () => {
  const lines = [
    { code: "delivery_fee", label: "Delivery · 4.2 km", amount: "35.00" },
    { code: "tip", label: "Tip for your rider", amount: "20.00" },
  ];
  assert.deepEqual(billRows(lines, "INR").map((r) => r.payee), ["US", "RIDER"]);
});
