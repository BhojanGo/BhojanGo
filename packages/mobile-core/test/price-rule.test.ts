// node --test: R44 the tablet's price rule (US cents, India whole rupees), the same answers as the API's price_problem.
import assert from "node:assert/strict";
import test from "node:test";

import { priceRule } from "../src/price-rule.ts";

test("US: up to 2 decimals and more than 0", () => {
  for (const ok of ["12.50", "12.5", "12", "0.99", " 12.50 ", "12,50", "12.500"]) assert.equal(priceRule(ok, false), null, ok);
  assert.equal(priceRule("12.505", false), "cents");
  for (const bad of ["0", "-1", "", "  ", "abc", "12.", ".5", "0.00"]) assert.equal(priceRule(bad, false), "required", JSON.stringify(bad));
});

test("India: whole rupees", () => {
  assert.equal(priceRule("120", true), null);
  assert.equal(priceRule("120.00", true), null);
  assert.equal(priceRule("120.50", true), "whole");
  assert.equal(priceRule("0", true), "required");
});

test("an option may cost 0, never less", () => {
  assert.equal(priceRule("0", false, true), null);
  assert.equal(priceRule("-1", false, true), "required");
});
