// node --test: R41 payout week labels always carry the year ("Mon 15 Dec" was 15 Dec 2008, read as 2026).
import assert from "node:assert/strict";
import test from "node:test";

import { weekLabel } from "../src/lib/weeks.ts";

test("a week label says the year", () => {
  assert.equal(weekLabel("2026-11-16", "2026-11-23"), "Mon 16 Nov – Sun 22 Nov 2026");
  assert.equal(weekLabel("2008-12-15", "2008-12-22"), "Mon 15 Dec – Sun 21 Dec 2008");
});

test("a week across new year says both years", () => {
  assert.equal(weekLabel("2026-12-28", "2027-01-04"), "Mon 28 Dec 2026 – Sun 3 Jan 2027");
});

test("a week across the US clock change is still Monday to Sunday", () => {
  assert.equal(weekLabel("2026-10-26", "2026-11-02"), "Mon 26 Oct – Sun 1 Nov 2026");
});
