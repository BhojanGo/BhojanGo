// node --test: Markets -> Kitchen offer ceiling (R22 security review, S11): what applies to a
// city (country -> state -> city, key by key) and what the form saves.
import assert from "node:assert/strict";
import test from "node:test";

import { CEILING_FIELDS, ceilingPatch, effectiveCeiling, ownCeiling } from "../src/lib/offerCeiling.ts";

test("a level's own ceiling keeps only amounts above 0", () => {
  assert.deepEqual(ownCeiling({ kitchen_offer_ceiling: { flat_off: "100", weekly_cap: 0, junk: "5", max_discount: "x" } }), { flat_off: "100" });
  assert.deepEqual(ownCeiling({}), {});
  assert.deepEqual(ownCeiling(null), {});
  assert.deepEqual(ownCeiling({ kitchen_offer_ceiling: ["100"] }), {});
});

test("each key comes from the nearest level that sets it, else the currency's default", () => {
  const got = effectiveCeiling([
    { name: "India", settings: { kitchen_offer_ceiling: { flat_off: "150", weekly_cap: "20000" } } },
    { name: "Telangana", settings: { kitchen_offer_ceiling: { weekly_cap: "15000" } } },
  ], "INR");
  assert.deepEqual(got, {
    flat_off: { value: "150", source: "India" },
    max_discount: { value: "200", source: "BhojanGo's default" },
    weekly_cap: { value: "15000", source: "Telangana" },
  });
  assert.deepEqual(effectiveCeiling([{ name: "New Zealand", settings: {} }], "NZD"), {});
});

test("the form saves what's filled in, null when empty, and refuses nonsense", () => {
  assert.deepEqual(ceilingPatch({ flat_off: " 120 ", weekly_cap: "" }), { flat_off: "120" });
  assert.equal(ceilingPatch({}), null);
  assert.ok("error" in (ceilingPatch({ flat_off: "0" }) as object));
  assert.ok("error" in (ceilingPatch({ weekly_cap: "abc" }) as object));
});

test("the boxes' labels say what each caps (R23: the percent-off cap names itself)", () => {
  assert.deepEqual(CEILING_FIELDS.map((f) => [f.key, f.label]), [
    ["flat_off", "Amount off, per order"],
    ["max_discount", "Most a %-off offer can take off one order"],
    ["weekly_cap", "Weekly cap"],
  ]);
});
