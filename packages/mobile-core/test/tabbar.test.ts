// node --test: the room every tab screen leaves for the floating tab bar (pure
// numbers, no React Native). The Maestro flow apps/customer/.maestro/tabbar-clearance.yaml
// checks the same thing on a phone.
import assert from "node:assert/strict";
import test from "node:test";

import {
  aboveTabBar, TAB_BAR_BREATHING, TAB_BAR_GAP, TAB_BAR_HEIGHT, TAB_BAR_INSET_GAP, TAB_BAR_LIFT, tabBarBottom, tabBarClearance,
} from "../src/tabbar.ts";

test("the bar floats at the design's lift, higher only where the system navigation needs it", () => {
  assert.equal(tabBarBottom(0), TAB_BAR_LIFT);
  assert.equal(tabBarBottom(16), TAB_BAR_LIFT); // gesture navigation: 16 + 8 < 24
  assert.equal(tabBarBottom(48), 48 + TAB_BAR_INSET_GAP); // three-button navigation
  assert.equal(tabBarBottom(Number.NaN), TAB_BAR_LIFT);
  assert.equal(tabBarBottom(-5), TAB_BAR_LIFT);
});

test("the clearance is the bar's top edge plus breathing room, so the last row ends above the bar", () => {
  for (const inset of [0, 16, 24, 34, 48]) {
    const barTop = tabBarBottom(inset) + TAB_BAR_HEIGHT; // distance of the bar's top from the bottom edge
    const clearance = tabBarClearance(inset);
    assert.equal(clearance, barTop + TAB_BAR_BREATHING);
    assert.ok(clearance > barTop, `inset ${inset}: the end of the scroll sits above the bar`);
  }
  assert.equal(tabBarClearance(0), 24 + 64 + 24);
});

test("floating buttons stacked above the bar add their height and a gap", () => {
  assert.equal(tabBarClearance(0, [48]), tabBarClearance(0) + 48 + TAB_BAR_GAP);
  assert.equal(tabBarClearance(0, [48, 40]), tabBarClearance(0) + 48 + 40 + 2 * TAB_BAR_GAP);
  assert.equal(tabBarClearance(0, [0, Number.NaN]), tabBarClearance(0)); // nothing showing adds nothing
});

test("a floating button above the bar sits clear of it and inside the clearance", () => {
  for (const inset of [0, 24, 48]) {
    const pill = 48;
    const pillBottom = aboveTabBar(inset);
    assert.equal(pillBottom, tabBarBottom(inset) + TAB_BAR_HEIGHT + TAB_BAR_GAP);
    assert.ok(pillBottom + pill <= tabBarClearance(inset, [pill]), "the pill's top is within the room the scroll leaves");
  }
});
