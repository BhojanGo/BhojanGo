// node --test: "Order again" → bag lines and what changed (R27).
const test = require("node:test");
const assert = require("node:assert/strict");
const { reorderToBag } = require("../reorder");

const restaurant = { id: "k1", slug: "morning-ridge-bakery-north-end", name: "Morning Ridge Bakery", currency: "USD" };
const latte = { menu_item_id: "i1", name: "Latte", quantity: 2, price: 7.5, available: true,
  options: [{ group: "g-size", option: "o-16", name: "16 oz" }, { group: "g-milk", option: "o-whole", name: "Whole" }] };

test("the same items, options and quantities go back in the bag", () => {
  const out = reorderToBag({ restaurant, items: [latte, { menu_item_id: "i2", name: "Butter Croissant", quantity: 1, price: "4.25", options: [] }],
    unavailable: [], problems: [] });
  assert.deepEqual(out.lines, [
    { menuItemId: "i1", name: "Latte", unitPrice: 7.5, quantity: 2, picks: [{ group: "g-size", option: "o-16" }, { group: "g-milk", option: "o-whole" }], summary: "16 oz, Whole" },
    { menuItemId: "i2", name: "Butter Croissant", unitPrice: 4.25, quantity: 1, picks: [], summary: "" },
  ]);
  assert.deepEqual(out.notes, []);
  assert.equal(out.restaurant, restaurant);
});

test("an item sold out and an option no longer offered are named; the rest is still added", () => {
  const out = reorderToBag({ restaurant, items: [latte], unavailable: ["Butter Croissant"], problems: [
    { item: "Latte", reason: "option_gone", option: "Oat" }, { item: "Butter Croissant", reason: "sold_out" }] });
  assert.equal(out.lines.length, 1);
  assert.deepEqual(out.notes, [
    { key: "account.receipt.reorder.option_gone", values: { item: "Latte", option: "Oat" } },
    { key: "account.receipt.reorder.sold_out", values: { item: "Butter Croissant" } },
  ]);
});

test("an older API without problems: what it left out is still named, once", () => {
  const out = reorderToBag({ restaurant, items: [{ ...latte, available: false }], unavailable: ["Scone"] }, "home.reorder");
  assert.deepEqual(out.lines, []);
  assert.deepEqual(out.notes.map((n) => [n.key, n.values.item]), [["home.reorder.unavailable", "Scone"], ["home.reorder.unavailable", "Latte"]]);
  const twice = reorderToBag({ restaurant, items: [], unavailable: ["Scone"], problems: [{ item: "Scone", reason: "removed" }] });
  assert.deepEqual(twice.notes.map((n) => n.key), ["account.receipt.reorder.removed"]);
});

test("odd values never throw: no options, a quantity out of range, an unknown reason", () => {
  const out = reorderToBag({ restaurant, items: [{ menu_item_id: "i3", name: "Cold Brew", quantity: 0, price: "x" }],
    problems: [{ item: "Tea", reason: "mystery" }] });
  assert.deepEqual(out.lines[0], { menuItemId: "i3", name: "Cold Brew", unitPrice: 0, quantity: 1, picks: [], summary: "" });
  assert.deepEqual(out.notes, [{ key: "account.receipt.reorder.unavailable", values: { item: "Tea" } }]);
});
