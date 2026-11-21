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

/** What GET /restaurants/{id}/availability says (R27): open now, and if not, why and when orders can next come in. */
export interface Availability {
  open_now: boolean;
  /** inactive | closed_for_now | unavailable | paused | closed | closed_today | outside_delivery_hours | not_taking_orders */
  reason_code?: string | null;
  /** The next moment an order can be placed (inside the kitchen's hours and the city's delivery hours). */
  next_open_at?: string | null;
  /** The kitchen's city zone (IANA): times are on its clock. */
  timezone?: string | null;
  closed_for_now?: boolean;
  back_at?: string | null;
  /** Open by its hours, but its tablet isn't connected ("Not taking orders right now"). */
  not_taking_orders?: boolean;
  closed_note?: string | null;
}

/** The kitchen's closing words ("Closed · opens 6:30 am", "Deliveries start 8:00 am", "This kitchen is closed now"),
 *  or null while it takes orders. `opens` is useI18n().opens (the weekday in the app's language). */
export function closedWords(
  a: Pick<Availability, "open_now" | "reason_code" | "next_open_at" | "timezone"> | null | undefined,
  opens: (iso: string | null | undefined, zone?: string | null, keys?: { today: string; day: string }) => string | null,
  t: (key: string) => string,
): string | null {
  if (!a || a.open_now || a.reason_code === "not_taking_orders") return null; // no tablet: "Not taking orders right now"
  const keys = a.reason_code === "outside_delivery_hours"
    ? { today: "kitchen.deliveries_start", day: "kitchen.deliveries_start_day" } : undefined;
  return opens(a.next_open_at, a.timezone, keys) ?? t("kitchen.bag_closed");
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
