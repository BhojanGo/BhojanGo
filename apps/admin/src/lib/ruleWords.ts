// Every rule's settings in plain words (Pricing & Rules, approvals, history):
// "0–3 km: ₹25 · 3–6 km: ₹35 · 6–10 km: ₹50 · beyond 10 km: not delivered".
// No raw JSON or "null" ever reaches the page.
type P = Record<string, unknown>;

const SYM: Record<string, string> = { IN: "₹", US: "$" };

export function unitsFor(scope: string): { cur: string; dist: string } {
  const c = scope.split("-")[0] ?? "IN";
  return { cur: SYM[c] ?? "", dist: c === "US" ? "mi" : "km" };
}

function m(v: unknown, cur: string): string {
  const n = Number(v);
  if (v == null || v === "" || Number.isNaN(n)) return "not set";
  return `${cur}${Number.isInteger(n) ? n : n.toFixed(2)}`;
}

function n(v: unknown): string {
  const x = Number(v);
  return v == null || Number.isNaN(x) ? "not set" : String(Number.isInteger(x) ? x : Number(x.toFixed(2)));
}

const DAYS: Record<string, string> = { mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun" };

function window(w: unknown): string {
  const x = (w ?? {}) as { start?: string; end?: string; days?: string[] };
  const days = x.days && x.days.length && x.days.length < 7 ? ` (${x.days.map((d) => DAYS[d] ?? d).join(", ")})` : "";
  return `${x.start ?? "?"}–${x.end ?? "?"}${days}`;
}

function tiers(t: unknown, fmt: (v: unknown) => string, def: unknown): string {
  return Object.entries((t ?? {}) as P).map(([k, v]) => `tier ${k}: ${fmt(v)}`).join(" · ") + (def ? ` · tier ${String(def)} if not set` : "");
}

const LINE_NAMES: Record<string, string> = {
  food: "food", delivery_fee: "delivery fee", service_fee: "service fee", small_order_fee: "small-order fee",
  packaging: "packaging", surge: "busy-hour fee", late_night_fee: "late-night fee", tip: "tip",
};

/** One line of plain words for a rule's settings. */
export function describe(template: string, params: P, scope: string): string {
  const { cur, dist } = unitsFor(scope);
  const p = params ?? {};
  switch (template) {
    case "distance_slabs": {
      const slabs = (p.slabs as { up_to: unknown; fee: unknown }[] | undefined) ?? [];
      let from = 0;
      const parts = slabs.map((s) => {
        const part = `${from}–${n(s.up_to)} ${dist}: ${m(s.fee, cur)}`;
        from = Number(s.up_to);
        return part;
      });
      parts.push(`beyond ${from} ${dist}: ${p.beyond_per_unit != null ? `${m(p.beyond_per_unit, cur)} per extra ${dist}` : "not delivered"}`);
      return parts.join(" · ");
    }
    case "flat": return `${m(p.amount, cur)} per order`;
    case "free_above": return `Free at ${m(p.min_subtotal, cur)} of food or more · ${m(p.otherwise, cur)} below that`;
    case "tier_base": return tiers(p.tiers, (v) => m(v, cur), p.default_tier);
    case "service_fee": case "percent_of_food":
      return `${n(p.percent)}% of ${p.base === "after_promotions" ? "food after offers" : "food"} · at least ${m(p.min, cur)}, at most ${m(p.max, cur)}`;
    case "small_order_fee": return `${m(p.fee, cur)} when food is under ${m(p.below, cur)}`;
    case "packaging_levy": return `${m(p.amount, cur)} per order`;
    case "surge_levy": case "busy_hours": return `${m(p.amount, cur)} during ${((p.windows as unknown[]) ?? []).map(window).join(", ")}`;
    case "late_night_fee": return `${m(p.amount, cur)} during ${window(p.window)}`;
    case "rate_on_lines": case "rate":
      return `${String(p.label ?? "Tax")}: ${n(p.rate_percent)}% on ${((p.target_lines as string[]) ?? []).map((l) => LINE_NAMES[l] ?? l).join(", ")}`
        + ` · collected by ${p.collected_by === "restaurant" ? "the kitchen" : "BhojanGo"}${p.inclusive ? " · included in prices" : ""}`;
    case "external": return "Worked out by Stripe Tax for the delivery address · collected by BhojanGo";
    case "percent": return `${n(p.percent)}% of food, whatever the tier`;
    case "percent_by_tier": return tiers(p.tiers, (v) => `${n(v)}%`, p.default_tier) + " of food";
    case "flat_per_order": return `${m(p.amount, cur)} per order on top of the percentage`;
    case "payout_schedule": return `Paid ${p.frequency === "biweekly" ? "every two weeks" : "weekly"} on ${DAYS[String(p.day)] ?? p.day}, ${n(p.hold_days)} days after the week ends`;
    case "base_distance_wait":
      return `${m(p.base, cur)} per delivery + ${m(p.per_unit, cur)} per ${dist} + ${m(p.per_wait_minute, cur)} per minute waiting after ${n(p.free_wait_minutes)} free minutes`;
    case "hourly_floor": return `At least ${m(p.per_active_hour, cur)} per active hour (topped up weekly)`;
    case "batch_bonus": return `${m(p.per_extra_order, cur)} for each extra order in a batch`;
    case "peak_bonus": return `${m(p.per_order, cur)} per order during ${((p.windows as unknown[]) ?? []).map(window).join(", ")}`;
    case "accept_timeout": return `Kitchens have ${n(p.seconds)} seconds to accept`;
    case "unpaid_auto_cancel": return `Unpaid orders cancel after ${n(p.minutes)} minutes`;
    case "cancel_window": return `Customers can cancel for free for ${n(p.minutes)} minutes`;
    case "refund_window": return `Refunds can be asked for up to ${n(p.hours)} hours after delivery`;
    case "cod_limit": return Number(p.max_amount) > 0 ? `Cash on delivery up to ${m(p.max_amount, cur)}` : "Cash on delivery is off";
    case "tip_presets": {
      const amounts = (p.amounts as unknown[]) ?? [];
      return `Tips offered: ${amounts.map((a) => m(a, cur)).join(", ")}${p.default_index != null ? ` · ${m(amounts[Number(p.default_index)], cur)} picked by default` : " · none picked by default"}`;
    }
    case "max_radius": return `Deliver up to ${n(p.distance)} ${dist} from the kitchen`;
    case "dispatch_offer_timeout": return `Riders have ${n(p.seconds)} seconds to accept an offer`;
    case "batching": return p.live
      ? "Live: riders can be offered two orders from the same kitchen at once (they see both drop-offs and the total pay)"
      : "Off: the batch engine only suggests pairs in the background; riders get one order at a time";
    case "support_refund_limit": return `Support agents can refund up to ${m(p.max_per_order, cur)} per order`;
    case "payment_fees": {
      const methods = (p.methods ?? {}) as Record<string, { percent?: unknown; fixed?: unknown }>;
      const name: Record<string, string> = { card: "Cards", wallet: "Wallets", upi: "UPI", net_banking: "Net banking" };
      const each = Object.entries(methods).map(([k, v]) => `${name[k] ?? k} ${Number(v.percent) === 0 && !Number(v.fixed) ? "free" : `${n(v.percent)}%${Number(v.fixed) ? ` + ${m(v.fixed, cur)}` : ""}`}`);
      return `The payment provider keeps: ${each.join(" · ")}${Number(p.tax_service_percent) ? ` · tax service ${n(p.tax_service_percent)}% where it calculates the tax` : ""}`;
    }
    case "auto_refund_limit": return `Customers' problem reports are refunded automatically up to ${m(p.max_per_order, cur)} per order`;
    case "percent_off": case "first_order": case "flat_off": case "free_delivery": case "referral": {
      const what = template === "free_delivery" ? "Free delivery" : template === "flat_off" || template === "referral" ? `${m(p.amount, cur)} off`
        : `${n(p.percent)}% off${p.max_discount != null ? `, up to ${m(p.max_discount, cur)}` : ""}`;
      const who = template === "first_order" ? " a first order" : template === "referral" ? " for a referral" : "";
      const bits = [`${what}${who}`, `paid by ${p.funded_by === "restaurant" ? "the kitchen" : "BhojanGo"}`];
      if (Number(p.min_subtotal) > 0) bits.push(`on ${m(p.min_subtotal, cur)} of food or more`);
      if (p.code) bits.push(`with code ${String(p.code)}`);
      if (p.budget_cap != null) bits.push(`budget ${m(p.budget_cap, cur)}`);
      if (p.weekly_cap != null) bits.push(`up to ${m(p.weekly_cap, cur)} a week`);
      return bits.join(" · ");
    }
    default:
      return Object.entries(p).filter(([, v]) => v != null).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? "set" : String(v)}`).join(" · ");
  }
}
