// node --test: a rule's settings in plain words (Pricing & Rules). The currency, its
// format and km/mi come from the rule's country in Markets, never from the code.
import assert from "node:assert/strict";
import test from "node:test";

import { money } from "../src/lib/money.ts";
import { withTemplateSettings } from "../src/lib/ruleSettings.ts";
import { describe, unitsFor } from "../src/lib/ruleWords.ts";

const MARKETS = [
  { code: "IN", currency: "INR", locales: ["en-IN", "hi-IN"], distance_unit: "km" },
  { code: "US", currency: "USD", locales: ["en-US", "es-US"], distance_unit: "mi" },
  // a country added from the admin console alone: no code knows it
  { code: "GB", currency: "GBP", locales: ["en-GB"], distance_unit: "mi" },
  { code: "DE", currency: "EUR", locales: ["de-DE"], distance_unit: "km" },
];
const SLABS = { slabs: [{ up_to: 3, fee: 25 }, { up_to: 6, fee: 35.5 }], beyond_per_unit: 8 };

test("money follows the locale it is given (Indian grouping, symbol after in German)", () => {
  assert.equal(money(124050, "INR", 0, "en-IN"), "₹1,24,050");
  assert.equal(money(1240.5, "USD", 2, "en-US"), "$1,240.50");
  assert.match(money(5, "EUR", 2, "de-DE"), /^5,00\s€$/);
});

test("units come from the scope's country in Markets, at any level", () => {
  const india = unitsFor("IN-TG-HYD", MARKETS);
  assert.equal(india.dist, "km");
  assert.equal(india.money(25), "₹25");
  assert.equal(india.money(1.5), "₹1.50");
  assert.equal(india.money(100000), "₹1,00,000");
  const us = unitsFor("US-ID-BOI", MARKETS);
  assert.equal(us.dist, "mi");
  assert.equal(us.money(2), "$2");
  assert.equal(us.money(1, 2), "$1.00");
  assert.equal(unitsFor("GB", MARKETS).money(3.25), "£3.25");
  assert.equal(unitsFor("GB", MARKETS).dist, "mi");
  assert.equal(unitsFor("DE-BE-BER", MARKETS).dist, "km");
});

test("a scope without a country (platform rules) or before Markets loads: plain numbers, no unit", () => {
  for (const u of [unitsFor("*", MARKETS), unitsFor("IN", undefined), unitsFor("FR", MARKETS)]) {
    assert.equal(u.dist, "");
    assert.equal(u.money(25), "25");
    assert.equal(u.money(1.5), "1.5");
    assert.equal(u.money(1, 2), "1.00");
  }
});

test("distance slabs read in the country's currency and unit", () => {
  assert.equal(describe("distance_slabs", SLABS, unitsFor("IN-TG-HYD", MARKETS)),
    "0–3 km: ₹25 · 3–6 km: ₹35.50 · beyond 6 km: ₹8 per extra km");
  assert.equal(describe("distance_slabs", SLABS, unitsFor("US", MARKETS)),
    "0–3 mi: $25 · 3–6 mi: $35.50 · beyond 6 mi: $8 per extra mi");
  assert.equal(describe("distance_slabs", { slabs: [{ up_to: 4, fee: 2 }] }, unitsFor("GB", MARKETS)),
    "0–4 mi: £2 · beyond 4 mi: not delivered");
  assert.equal(describe("distance_slabs", SLABS, unitsFor("*", MARKETS)),
    "0–3: 25 · 3–6: 35.5 · beyond 6: 8 per extra unit of distance");
});

test("pay, radius and money settings use the same units", () => {
  const us = unitsFor("US-ID-BOI", MARKETS);
  assert.equal(describe("base_distance_wait", { base: 3, per_unit: 0.6, per_wait_minute: 0.1, free_wait_minutes: 5 }, us),
    "$3 per delivery + $0.60 per mi + $0.10 per minute waiting after 5 free minutes");
  assert.equal(describe("max_radius", { distance: 8 }, us), "Deliver up to 8 mi from the kitchen");
  assert.equal(describe("max_radius", { distance: 8 }, unitsFor("*", MARKETS)), "Deliver up to 8 from the kitchen");
  assert.equal(describe("free_above", { min_subtotal: 499, otherwise: 29 }, unitsFor("IN", MARKETS)),
    "Free at ₹499 of food or more · ₹29 below that");
  assert.equal(describe("flat", { amount: null }, us), "not set per order");
  assert.equal(describe("cod_limit", { max_amount: 0 }, us), "Cash on delivery is off");
});

test("R17: India's tax settings in words, and a form that shows settings an older rule lacks", () => {
  const inr = unitsFor("IN", MARKETS);
  const gst = { label: "GST on food", rate_percent: "5", target_lines: ["food", "packaging"], collected_by: "platform" };
  assert.equal(describe("rate_on_lines", { ...gst, platform_discounts_reduce_base: false }, inr),
    "GST on food: 5% on food, packaging · collected by BhojanGo · discounts BhojanGo pays for don't reduce it");
  assert.equal(describe("rate_on_lines", gst, inr), "GST on food: 5% on food, packaging · collected by BhojanGo");
  assert.equal(describe("commission_tax", { label: "GST on commission", rate_percent: 18 }, inr),
    "GST on commission: 18% of BhojanGo's commission, taken from the kitchen's payout");
  assert.equal(describe("payout_tds", { label: "TDS (section 194-O)", rate_percent: 0 }, inr), "TDS (section 194-O): none deducted (0%)");
  const schema = {
    properties: {
      label: { default: "GST on commission", type: "string" }, rate_percent: { anyOf: [{ type: "number" }, { type: "string" }] },
      ca_confirmed: { default: false, type: "boolean" }, target_lines: { type: "array" },
    },
    required: ["rate_percent", "target_lines"],
  };
  assert.deepEqual(withTemplateSettings({}, schema), { label: "GST on commission", rate_percent: null, ca_confirmed: false });
  // a version's own values win; a missing yes/no setting comes with its default
  assert.deepEqual(withTemplateSettings({ rate_percent: "5", target_lines: ["food"] }, schema),
    { rate_percent: "5", target_lines: ["food"], label: "GST on commission", ca_confirmed: false });
  assert.deepEqual(withTemplateSettings({ a: 1 }), { a: 1 });
});
