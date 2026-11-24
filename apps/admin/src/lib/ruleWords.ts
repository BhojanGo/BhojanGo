// Every rule's settings in plain words (Pricing & Rules, approvals, history):
// "0–3 km: ₹25 · 3–6 km: ₹35 · 6–10 km: ₹50 · beyond 10 km: not delivered".
// No raw JSON or "null" ever reaches the page.
// The currency, how money is written (the country's first locale) and km or mi all
// come from the rule's country in Markets, never from a table here.
// Pure (no React): `node --test` covers it (test/ruleWords.test.ts).
import { money } from "./money.ts";
import { word } from "./count.ts";

type P = Record<string, unknown>;

/** The Markets country fields a rule's words need (lib/markets Country has them all). */
export interface UnitsCountry { code: string; currency: string; locales: string[]; distance_unit: string }

/** How a rule's amounts and distances read in its country. */
export interface Units {
  /** An amount: whole amounts without ".00" unless `decimals` is given. */
  money: (v: number, decimals?: number) => string;
  /** "km" or "mi"; empty when the scope has no country (platform rules) or Markets hasn't loaded. */
  dist: string;
}

/** The units for a rule scope ("IN", "US-ID-BOI", "*") from the Markets countries. */
export function unitsFor(scope: string, countries: UnitsCountry[] | undefined): Units {
  const code = scope.split("-")[0];
  const c = (countries ?? []).find((x) => x.code === code);
  const plain = (v: number, decimals?: number) => (decimals != null ? v.toFixed(decimals) : String(Number.isInteger(v) ? v : Number(v.toFixed(2))));
  if (!c?.currency) return { money: plain, dist: c?.distance_unit ?? "" };
  return {
    money: (v, decimals) => money(v, c.currency, decimals ?? (Number.isInteger(v) ? 0 : 2), c.locales[0]),
    dist: c.distance_unit ?? "",
  };
}

function m(v: unknown, cur: Units): string {
  const n = Number(v);
  if (v == null || v === "" || Number.isNaN(n)) return "not set";
  return cur.money(n);
}

/** "3 km"; just "3" when there is no unit. */
function d(v: unknown, dist: string): string {
  return dist ? `${n(v)} ${dist}` : n(v);
}

/** "per km"; "per unit of distance" when there is no unit. */
function per(dist: string): string {
  return dist ? `per ${dist}` : "per unit of distance";
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
  food: "food", delivery_fee: "delivery fee", platform_fee: "platform fee", service_fee: "service fee", small_order_fee: "small-order fee",
  packaging: "packaging", surge: "busy-hour fee", late_night_fee: "late-night fee", tip: "tip",
};

/** One line of plain words for a rule's settings. */
export function describe(template: string, params: P, units: Units): string {
  const cur = units;
  const { dist } = units;
  const p = params ?? {};
  switch (template) {
    case "distance_slabs": {
      const slabs = (p.slabs as { up_to: unknown; fee: unknown }[] | undefined) ?? [];
      let from = 0;
      const parts = slabs.map((s) => {
        const part = `${from}–${d(s.up_to, dist)}: ${m(s.fee, cur)}`;
        from = Number(s.up_to);
        return part;
      });
      parts.push(`beyond ${d(from, dist)}: ${p.beyond_per_unit != null ? `${m(p.beyond_per_unit, cur)} ${dist ? `per extra ${dist}` : "per extra unit of distance"}` : "not delivered"}`);
      return parts.join(" · ");
    }
    case "flat": return `${m(p.amount, cur)} per order`;
    case "base_per_distance": return `${m(p.base, cur)} + ${m(p.per_unit, cur)} per ${dist === "mi" ? "mile" : "km"}, all of it to the delivery partner`;
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
        + ` · collected by ${p.collected_by === "restaurant" ? "the restaurant" : "BhojanGo"}${p.inclusive ? " · included in prices" : ""}`
        // R17: who funds a discount decides whether it lowers the tax base (R16)
        + (p.platform_discounts_reduce_base === false ? " · discounts BhojanGo pays for don't reduce it" : "");
    case "commission_tax": return `${String(p.label ?? "Tax on commission")}: ${n(p.rate_percent)}% of BhojanGo's commission, taken from the restaurant's payout`;
    case "payout_tds": return Number(p.rate_percent) > 0
      ? `${String(p.label ?? "TDS")}: ${n(p.rate_percent)}% of the restaurant's food and packaging sales, taken from its payout`
      : `${String(p.label ?? "TDS")}: none deducted (0%)`;
    case "external": return "Worked out by Stripe Tax for the delivery address · collected by BhojanGo"
      // R33: the state's taxable lines (Idaho: food and the platform fee; not the delivery fee or the tip)
      + (Array.isArray(p.taxable_lines) ? ` · taxable: ${(p.taxable_lines as string[]).map((l) => LINE_NAMES[l] ?? l).join(", ")}; everything else isn't` : "");
    case "platform_fee_pct": return `${n(p.percent)}% of the food subtotal, paid by the customer to BhojanGo`;
    case "min_platform_fee": return `At least ${m(p.amount, cur)} (when the percentage comes to less)`;
    case "card_fee_estimate": {
      // R30: a rate per payment method (card, UPI, wallet, net banking); the R29 single rate reads as the card rate
      const rate = (r: { percent?: unknown; fixed?: unknown }) => (Number(r.fixed ?? 0) > 0 ? `${n(r.percent)}% + ${m(r.fixed, cur)}` : `${n(r.percent)}%`);
      const methods = p.card ? ([["card", "card"], ["upi", "UPI"], ["wallet", "wallet"], ["net_banking", "net banking"]] as const)
        .filter(([k]) => p[k]).map(([k, label]) => `${label} ${rate(p[k] as { percent?: unknown; fixed?: unknown })}`) : [`card ${rate(p)}`];
      return `${methods.join(" · ")} of the charge less the tip, taken from the restaurant's payout; cash: none`;
    }
    case "percent": return `${n(p.percent)}% of food, whatever the tier`;
    case "percent_by_tier": return tiers(p.tiers, (v) => `${n(v)}%`, p.default_tier) + " of food";
    case "flat_per_order": return `${m(p.amount, cur)} per order on top of the percentage`;
    case "payout_schedule": return `Paid ${p.frequency === "biweekly" ? "every two weeks" : "weekly"} on ${DAYS[String(p.day)] ?? p.day}, ${n(p.hold_days)} ${word(p.hold_days, "day")} after the week ends`;
    case "base_distance_wait":
      return `${m(p.base, cur)} per delivery + ${m(p.per_unit, cur)} ${per(dist)} + ${m(p.per_wait_minute, cur)} per minute waiting after ${n(p.free_wait_minutes)} free ${word(p.free_wait_minutes, "minute")}`;
    case "hourly_floor": return `At least ${m(p.per_active_hour, cur)} per active hour (topped up weekly)`;
    case "batch_bonus": return `${m(p.per_extra_order, cur)} for each extra order in a batch`;
    case "peak_bonus": return `${m(p.per_order, cur)} per order during ${((p.windows as unknown[]) ?? []).map(window).join(", ")}`;
    case "accept_timeout": return `Restaurants have ${n(p.seconds)} ${word(p.seconds, "second")} to accept`;
    case "unpaid_auto_cancel": return `Unpaid orders cancel after ${n(p.minutes)} ${word(p.minutes, "minute")}`;
    case "cancel_window": return `Customers can cancel for free for ${n(p.minutes)} ${word(p.minutes, "minute")}`;
    case "refund_window": return `Refunds can be asked for up to ${n(p.hours)} ${word(p.hours, "hour")} after delivery`;
    case "cod_limit": return Number(p.max_amount) > 0 ? `Cash on delivery up to ${m(p.max_amount, cur)}` : "Cash on delivery is off";
    case "tip_presets": {
      const amounts = (p.amounts as unknown[]) ?? [];
      return `Tips offered: ${amounts.map((a) => m(a, cur)).join(", ")}${p.default_index != null ? ` · ${m(amounts[Number(p.default_index)], cur)} picked by default` : " · none picked by default"}`;
    }
    case "max_radius": return `Deliver up to ${d(p.distance, dist)} from the restaurant`;
    case "dispatch_offer_timeout": return `Delivery partners have ${n(p.seconds)} seconds to accept an offer`;
    case "dispatch_offer_exclusion": return Number(p.seconds) > 0
      ? `A delivery partner who passes or lets an offer time out isn't offered that order again for ${n(p.seconds)} seconds (other orders at once)`
      : "A delivery partner who passes can be offered that order again at once";
    case "no_partner_alert": return `An order without a delivery partner after ${n(p.minutes)} minutes alerts Operations, and the customer gets a later arrival time`;
    case "batching": return p.live
      ? "Live: delivery partners can be offered two orders from the same restaurant at once (they see both drop-offs and the total pay)"
      : "Off: the batch engine only suggests pairs in the background; delivery partners get one order at a time";
    case "support_refund_limit": return `Support agents can refund up to ${m(p.max_per_order, cur)} per order`;
    case "payment_fees": {
      const methods = (p.methods ?? {}) as Record<string, { percent?: unknown; fixed?: unknown }>;
      const name: Record<string, string> = { card: "Cards", wallet: "Wallets", upi: "UPI", net_banking: "Net banking" };
      const each = Object.entries(methods).map(([k, v]) => `${name[k] ?? k} ${Number(v.percent) === 0 && !Number(v.fixed) ? "free" : `${n(v.percent)}%${Number(v.fixed) ? ` + ${m(v.fixed, cur)}` : ""}`}`);
      return `The payment provider keeps: ${each.join(" · ")}${Number(p.tax_service_percent) ? ` · tax service ${n(p.tax_service_percent)}% where it calculates the tax` : ""}`;
    }
    case "auto_refund_limit": return `Customers' problem reports are refunded automatically up to ${m(p.max_per_order, cur)} per order; a bulk refund over ${p.max_bulk_total != null && p.max_bulk_total !== "" ? m(p.max_bulk_total, cur) : m(Number(p.max_per_order) * 50, cur)} in all needs a second admin`;
    case "percent_off": case "first_order": case "flat_off": case "free_delivery": case "referral": {
      const what = template === "free_delivery" ? "Free delivery" : template === "flat_off" || template === "referral" ? `${m(p.amount, cur)} off`
        : `${n(p.percent)}% off${p.max_discount != null ? `, up to ${m(p.max_discount, cur)}` : ""}`;
      const who = template === "first_order" ? " a first order" : template === "referral" ? " for a referral" : "";
      const bits = [`${what}${who}`, `paid by ${p.funded_by === "restaurant" ? "the restaurant" : "BhojanGo"}`];
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
