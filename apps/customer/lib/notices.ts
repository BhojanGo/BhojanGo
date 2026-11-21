// What the out-of-area and payment-failed screens say (R27), as pure functions.
// No React Native here: test/notices.test.ts runs them with `node --test`.

/** The drop point as the out-of-area screen knows it (lib/where.ts DropPoint). */
export interface PointLike {
  label?: string | null;
  city?: string | null;
}

/**
 * The place the out-of-area screen may name ("We're not in <place> yet"): only when
 * GET /markets/locate said this very point is outside every delivery zone. A point
 * inside a zone (a served neighbourhood), one not located yet, or no point at all (the
 * screen opened by a link) gets the generic "your area" wording: never a served
 * neighbourhood. The most specific name wins: "Home · <area>" -> "<area>".
 */
export function outOfAreaPlace(point: PointLike | null | undefined,
                               market: { serviceable?: boolean | null } | null | undefined): string | null {
  if (!point || market?.serviceable !== false) return null;
  const label = (point.label ?? "").trim();
  return label.split("· ")[1]?.trim() || label || point.city?.trim() || null;
}

export type PayFailedKey = "checkout.bank_not_confirmed" | "app.payment_failed.declined_upi" | "app.payment_failed.declined_card";

/**
 * The one sentence on the payment-failed screen: what the payment provider said on
 * the last try (it replaces ours, so the same news isn't told twice), else why
 * the bank stopped it, else the method's usual wording. The "not charged" note follows it.
 */
export function payFailedLine(o: { error?: string | null; reason?: string | null; method?: string | null }):
    { text: string } | { key: PayFailedKey } {
  if (o.error && o.error.trim()) return { text: o.error.trim() };
  if (o.reason === "authentication") return { key: "checkout.bank_not_confirmed" };
  return { key: o.method === "upi" ? "app.payment_failed.declined_upi" : "app.payment_failed.declined_card" };
}
