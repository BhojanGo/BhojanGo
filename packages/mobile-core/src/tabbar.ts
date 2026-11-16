// The floating tab bar's geometry, in one place (pure numbers, no React Native,
// so node --test checks it). The bar floats over the tab screens; every tab
// screen ends its scroll with tabBarClearance() of empty room, so the last row
// always scrolls fully above the bar (and above anything floating on top of it).

/** The dark pill's height (TabBar in ui/components uses it). */
export const TAB_BAR_HEIGHT = 64;
/** How far the bar floats above the bottom edge (the design's 24). */
export const TAB_BAR_LIFT = 24;
/** At least this much between the bar and the system navigation (the safe-area inset). */
export const TAB_BAR_INSET_GAP = 8;
/** Room between the bar (or a floating button) and whatever sits above it. */
export const TAB_BAR_GAP = 16;
/** Breathing room under the last row once it has scrolled clear of the bar. */
export const TAB_BAR_BREATHING = 24;

const px = (n: number | null | undefined) => (typeof n === "number" && Number.isFinite(n) && n > 0 ? n : 0);

/** The bar's bottom offset: the design's lift, or more where the system navigation needs it. */
export function tabBarBottom(insetBottom: number): number {
  return Math.max(TAB_BAR_LIFT, px(insetBottom) + TAB_BAR_INSET_GAP);
}

/** Where a floating button above the bar sits (its bottom offset), e.g. the bag pill on home. */
export function aboveTabBar(insetBottom: number): number {
  return tabBarBottom(insetBottom) + TAB_BAR_HEIGHT + TAB_BAR_GAP;
}

/**
 * The paddingBottom every tab screen's scroll ends with: the bar, its offset and
 * the safe area, plus each floating thing stacked above the bar (their heights,
 * each with its gap), plus breathing room.
 */
export function tabBarClearance(insetBottom: number, stacked: readonly number[] = []): number {
  const above = stacked.map(px).filter((h) => h > 0).reduce((sum, h) => sum + h + TAB_BAR_GAP, 0);
  return tabBarBottom(insetBottom) + TAB_BAR_HEIGHT + above + TAB_BAR_BREATHING;
}

// R8: the bar no longer floats over content at rest. Tab screens end above a band
// at the bottom (tabBarZone) that the bar floats in, so nothing (a heading, a
// cuisine label) ever sits under the bar when the screen opens. Inside that
// shorter screen, the scroll ends with sceneEndSpace() and a floating button
// (the bag pill) sits TAB_BAR_GAP above the screen's bottom edge, i.e. above the bar.

/** The band at the bottom of the window the bar floats in (its offset and its height); tab screens end above it. */
export function tabBarZone(insetBottom: number): number {
  return tabBarBottom(insetBottom) + TAB_BAR_HEIGHT;
}

/** The paddingBottom a tab screen's scroll ends with inside a screen that already ends above the bar. */
export function sceneEndSpace(stacked: readonly number[] = []): number {
  return tabBarClearance(0, stacked) - tabBarZone(0);
}
