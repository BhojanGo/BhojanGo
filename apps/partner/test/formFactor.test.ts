// node --test: phones portrait, tablets landscape, and the one layout breakpoint
// (pure logic in lib/formFactor.ts, no React Native). Sizes are in dp.
import assert from "node:assert/strict";
import test from "node:test";

import { formFactor, isNarrow, isPortrait, lockFor } from "../lib/formFactor.ts";

test("a phone is a screen whose shortest side is under 600 dp, held either way", () => {
  assert.equal(formFactor({ width: 411, height: 914 }), "phone"); // Pixel-class phone, upright
  assert.equal(formFactor({ width: 914, height: 411 }), "phone"); // the same phone sideways
  assert.equal(formFactor({ width: 360, height: 640 }), "phone");
  assert.equal(formFactor({ width: 599, height: 960 }), "phone");
});

test("a tablet is 600 dp or more on its shortest side", () => {
  assert.equal(formFactor({ width: 600, height: 960 }), "tablet"); // 7-inch tablet
  assert.equal(formFactor({ width: 1194, height: 834 }), "tablet"); // the board's design size
  assert.equal(formFactor({ width: 800, height: 1280 }), "tablet"); // a tablet started upright
});

test("phones lock portrait, tablets turn freely (R27: no letterboxed landscape on an upright tablet)", () => {
  assert.equal(lockFor({ width: 411, height: 914 }), "portrait");
  assert.equal(lockFor({ width: 914, height: 411 }), "portrait"); // started sideways: still a phone
  assert.equal(lockFor({ width: 1194, height: 834 }), "free");
  assert.equal(lockFor({ width: 800, height: 1280 }), "free"); // started upright: stays upright
});

test("portrait: taller than wide (an upright tablet gets the tabbed board)", () => {
  assert.equal(isPortrait({ width: 800, height: 1280 }), true);
  assert.equal(isPortrait({ width: 834, height: 1194 }), true);
  assert.equal(isPortrait({ width: 1194, height: 834 }), false);
  assert.equal(isPortrait({ width: 1000, height: 1000 }), false);
});

test("the layout breakpoint follows the window: narrow is the phone layout", () => {
  assert.equal(isNarrow({ width: 411, height: 860 }), true); // phone, portrait
  assert.equal(isNarrow({ width: 599, height: 900 }), true);
  assert.equal(isNarrow({ width: 600, height: 900 }), false);
  assert.equal(isNarrow({ width: 914, height: 411 }), false); // a phone left sideways keeps the compact board
  assert.equal(isNarrow({ width: 1194, height: 834 }), false); // tablet board
  assert.equal(isNarrow({ width: 400, height: 834 }), true); // a tablet's narrow split-screen pane
});
