// Phone or tablet, portrait or landscape: pure rules (no React Native) so
// `node --test` can check them (test/formFactor.test.ts). lib/layout.ts applies
// them: the screen lock at start, and the one breakpoint every screen reads.

export type Size = { width: number; height: number };
export type FormFactor = "phone" | "tablet";

/** Android's own line between phones and tablets: the shortest side under 600 dp is a phone. */
export const PHONE_MAX_DP = 600;

/** The device, from the whole screen (not the window: split-screen must not turn a tablet into a phone). */
export function formFactor(screen: Size): FormFactor {
  return Math.min(screen.width, screen.height) < PHONE_MAX_DP ? "phone" : "tablet";
}

/** Phones are held upright; a kitchen tablet stands sideways on the counter (PartnerOrders.html, 1194 × 834). */
export function lockFor(screen: Size): "portrait" | "landscape" {
  return formFactor(screen) === "phone" ? "portrait" : "landscape";
}

/**
 * The one layout breakpoint, from the window: narrow (under 600 dp wide) is the phone
 * layout (one column, the orders list then an order's detail, a bottom tab bar);
 * anything wider keeps the tablet board. A tablet in a narrow split-screen pane
 * gets the phone layout too, which is what fits there.
 */
export function isNarrow(window: Size): boolean {
  return window.width < PHONE_MAX_DP;
}
