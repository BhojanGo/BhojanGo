// R19: when a dish can't go in the bag, and how checkout may take payment.
// Pure (no React Native): test/ordering.test.ts.

/** Why nothing can be added now: an incident pause first, then a closed kitchen. Message keys. */
export type BlockKey = "kitchen.bag_paused" | "kitchen.bag_closed_for_now";

export function orderingBlock(k: { paused: boolean; closedForNow?: boolean | null; isOpen?: boolean | null }): BlockKey | null {
  if (k.paused) return "kitchen.bag_paused";
  if (k.closedForNow || k.isOpen === false) return "kitchen.bag_closed_for_now";
  return null;
}

/** What GET /payments/provider said: a provider, "error" (no answer or refused), null (still asking). */
export type ProviderAnswer = "stripe" | "razorpay" | "fake" | "error" | null;

/**
 * How checkout takes the payment. Production fails closed: only a live provider the app
 * can open (Stripe PaymentSheet) pays; the test sheet never shows there. Anywhere, a
 * provider that can't be looked up means payments aren't available (never the test sheet).
 */
export type PayMode = "stripe" | "test" | "unavailable" | "loading";

export function payMode(answer: ProviderAnswer, production: boolean): PayMode {
  if (answer === null) return "loading";
  if (answer === "stripe") return "stripe";
  if (answer === "error" || production) return "unavailable";
  return "test"; // local and QA: the app's test sheet stands in for the provider
}
