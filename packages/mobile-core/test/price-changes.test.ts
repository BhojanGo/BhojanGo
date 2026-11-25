// node --test: R43 "Price changed: <dish> <old> → <new>": which cart lines the quote priced differently.
import assert from "node:assert/strict";
import test from "node:test";

import { priceChanges, type BagLine } from "../src/bag.ts";

const line = (id: string, unitPrice: number, name = id): BagLine => ({ key: `${id}|`, menuItemId: id, name, unitPrice, quantity: 2, picks: [], summary: "" });

test("a dish the restaurant re-priced is listed with its old and new price", () => {
  const lines = [line("a", 10, "Bowl"), line("b", 4.5, "Soup")];
  assert.deepEqual(priceChanges(lines, [{ menu_item_id: "a", unit_price: "12.00" }, { menu_item_id: "b", unit_price: "4.50" }]),
    [{ key: "a|", name: "Bowl", was: 10, now: 12 }]);
});

test("nothing changed, a quote for another cart, or no items: no note", () => {
  const lines = [line("a", 250)];
  assert.deepEqual(priceChanges(lines, [{ menu_item_id: "a", unit_price: 250 }]), []);
  assert.deepEqual(priceChanges(lines, [{ menu_item_id: "x", unit_price: 300 }]), []);
  assert.deepEqual(priceChanges(lines, [{ menu_item_id: "a", unit_price: 300 }, { menu_item_id: "b", unit_price: 1 }]), []);
  assert.deepEqual(priceChanges(lines, undefined), []);
});
