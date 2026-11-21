// node --test: the out-of-area and payment-failed screens' wording (R27, lib/notices.ts).
import assert from "node:assert/strict";
import test from "node:test";

import { outOfAreaPlace, payFailedLine } from "../lib/notices.ts";

const NORTH_END = { label: "Home · North End", city: "Boise" };

test("out of area: a served neighbourhood is never named", () => {
  // R26: the screen opened by a link said "We're not in North End yet"; North End is in Boise's zones.
  assert.equal(outOfAreaPlace(NORTH_END, { serviceable: true }), null);
  assert.equal(outOfAreaPlace(NORTH_END, null), null); // not located yet: we don't know
  assert.equal(outOfAreaPlace(NORTH_END, {}), null);
  assert.equal(outOfAreaPlace(null, { serviceable: false }), null); // no point at all
});

test("out of area: a point outside every zone is named, most specific first", () => {
  assert.equal(outOfAreaPlace({ label: "Home · Twin Falls", city: "Twin Falls" }, { serviceable: false }), "Twin Falls");
  assert.equal(outOfAreaPlace({ label: "Nampa", city: "Nampa" }, { serviceable: false }), "Nampa"); // the phone's location
  assert.equal(outOfAreaPlace({ label: "", city: "Caldwell" }, { serviceable: false }), "Caldwell");
  assert.equal(outOfAreaPlace({ label: "", city: "" }, { serviceable: false }), null);
});

test("payment failed: one sentence, the provider's own words replacing ours", () => {
  assert.deepEqual(payFailedLine({ method: "card" }), { key: "app.payment_failed.declined_card" });
  assert.deepEqual(payFailedLine({ method: "upi" }), { key: "app.payment_failed.declined_upi" });
  assert.deepEqual(payFailedLine({ method: undefined }), { key: "app.payment_failed.declined_card" }); // opened by a link
  assert.deepEqual(payFailedLine({ method: "card", reason: "authentication" }), { key: "checkout.bank_not_confirmed" });
  assert.deepEqual(payFailedLine({ method: "card", error: " Your card was declined. " }), { text: "Your card was declined." });
  assert.deepEqual(payFailedLine({ method: "card", error: "  " }), { key: "app.payment_failed.declined_card" });
});
