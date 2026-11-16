// node --test: the padding mobile-core's SafeAreaView adds (R8). Under the test
// banner the top inset is 0 (the banner has the status bar), so a screen adds
// nothing on top; in production it adds the status bar once.
import assert from "node:assert/strict";
import test from "node:test";

import { safePadding } from "../src/ui/safe-area-pad.ts";

const PHONE = { top: 48, right: 0, bottom: 24, left: 0 };
const UNDER_BANNER = { ...PHONE, top: 0 };

test("under the test banner: no top padding, so no empty band", () => {
  assert.deepEqual(safePadding({}, UNDER_BANNER, ["top"]), { paddingTop: 0 });
});

test("production (no banner): the status bar, once", () => {
  assert.deepEqual(safePadding({}, PHONE, ["top"]), { paddingTop: 48 });
});

test("the screen's own padding is kept and the inset added to it, edge by edge", () => {
  assert.deepEqual(safePadding({ padding: 8, paddingVertical: 12, paddingTop: 4 }, PHONE, ["top", "bottom"]), { paddingTop: 52, paddingBottom: 36 });
  assert.deepEqual(safePadding({ paddingHorizontal: 16 }, PHONE), { paddingTop: 48, paddingRight: 16, paddingBottom: 24, paddingLeft: 16 });
});

test("edges not asked for are left to the style", () => {
  assert.deepEqual(safePadding({ paddingTop: 10 }, PHONE, ["left", "right", "bottom"]), { paddingLeft: 0, paddingRight: 0, paddingBottom: 24 });
});
