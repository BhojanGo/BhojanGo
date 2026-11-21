// R19: when a dish can't go in the bag, and how checkout may take payment.
// Pure (no React Native): test/ordering.test.ts.

/** Why nothing can be added now: an incident pause first, then a closed kitchen, then (R27) a
 *  kitchen whose tablet isn't connected ("Not taking orders right now"). Message keys. */
export type BlockKey = "kitchen.bag_paused" | "kitchen.bag_closed_for_now" | "kitchen.not_taking_orders";

export function orderingBlock(k: { paused: boolean; closedForNow?: boolean | null; isOpen?: boolean | null; notTaking?: boolean | null }): BlockKey | null {
  if (k.paused) return "kitchen.bag_paused";
  if (k.closedForNow || k.isOpen === false) return "kitchen.bag_closed_for_now";
  if (k.notTaking) return "kitchen.not_taking_orders";
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

/**
 * R20: an order with nothing to pay (an app store review order in its review city: the
 * server prices it at 0 and places it as soon as it is made). No checkout opens: the
 * button places the order. Anything above zero, or no price yet, goes through payment.
 */
export function isFreeOrder(total: string | number | null | undefined): boolean {
  if (total === null || total === undefined || total === "") return false;
  const n = Number(total);
  return Number.isFinite(n) && Math.abs(n) < 0.005;
}
