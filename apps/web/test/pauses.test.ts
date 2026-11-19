// node --test: which "ordering is paused" notes a page shows (R17).
import assert from "node:assert/strict";
import test from "node:test";

import { shownPauses } from "../src/lib/pauses.ts";

const HYD = { id: "1", scope: "IN-TG-HYD", area: "Hyderabad" };
const US = { id: "2", scope: "US", area: "United States" };
const ALL = { id: "3", scope: "*", area: "BhojanGo" };

test("a place page shows its own city's, its country's and everywhere's pauses", () => {
  assert.deepEqual(shownPauses([HYD, US, ALL], "/in/hyderabad/spice-route-kitchen").map((p) => p.id), ["1", "3"]);
  assert.deepEqual(shownPauses([HYD, US], "/in/vijayawada").map((p) => p.id), []);
  assert.deepEqual(shownPauses([HYD, US], "/us/boise").map((p) => p.id), ["2"]);
  assert.deepEqual(shownPauses([HYD], "/in").map((p) => p.id), ["1"]);
});

test("pages that aren't about a place show every pause", () => {
  assert.deepEqual(shownPauses([HYD, US], "/").map((p) => p.id), ["1", "2"]);
  assert.deepEqual(shownPauses([HYD, US], "/checkout").map((p) => p.id), ["1", "2"]);
});
