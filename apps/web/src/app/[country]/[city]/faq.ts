// "Delivery in {city}, plainly": the answers are built from the city's own
// pricing (delivery fee rule, delivery radius, service fee, small-order fee, minimum order, tip
// suggestions) when the API sends it; the general wording only when it doesn't.
import type { CityPricing } from "@/lib/contract";
import { money, number } from "@/lib/format";
import type { CityPage } from "@/lib/server";

type T = (key: string, vars?: Record<string, string | number>) => string;

export function cityFaq(c: CityPage, p: CityPricing | null, t: T, formatLocale: string): { q: string; a: string }[] {
  const city = c.name;
  if (!p) {
    return (["cost", "tip", "tax"] as const).map((k) => ({ q: t(`city.faq_${k}_q`, { city }), a: t(`city.faq_${k}_a`) }));
  }
  const m = (v: number | string | null | undefined) => money(v, p.currency, formatLocale);
  const dist = (v: number | string) => t(p.distance_unit === "mi" ? "common.mi" : "common.km", { n: number(Number(v), formatLocale) });
  const out: { q: string; a: string }[] = [];

  // What delivery costs: the city's delivery fee rule, then the service and small-order fees.
  const cost: string[] = [];
  const f = p.delivery_fee;
  const unit = p.distance_unit === "mi" ? "mi" : "km";
  if (f?.type === "flat" && f.amount != null) {
    cost.push(t("city.faq_flat", { fee: m(f.amount), city }));
  } else if (f?.type === "distance_slabs" && f.slabs?.length) {
    const slabs = [...f.slabs].sort((a, b) => Number(a.up_to) - Number(b.up_to));
    const parts = slabs.map((b) => t("city.faq_band_upto", { distance: dist(b.up_to), fee: m(b.fee) }));
    const last = slabs[slabs.length - 1]!;
    if (f.beyond_per_unit != null && Number(f.beyond_per_unit) > 0) {
      parts.push(t("city.faq_band_beyond_per", { fee: m(f.beyond_per_unit), unit, distance: dist(last.up_to) }));
    }
    cost.push(t("city.faq_bands", { bands: parts.join("; ") }));
  } else if (f?.type === "free_above" && f.min_subtotal != null && f.otherwise != null) {
    cost.push(t("city.faq_free_above", { min: m(f.min_subtotal), fee: m(f.otherwise) }));
  } else if (p.delivery_from != null) {
    cost.push(t("city.faq_from", { fee: m(p.delivery_from) }));
  }
  if (p.max_distance != null && Number(p.max_distance) > 0) {
    cost.push(t("city.faq_max_distance", { distance: dist(p.max_distance) }));
  }
  const s = p.service_fee;
  const pf = p.platform_fee; // R29 fee model v2: a percentage of the food, at least a minimum
  if (pf && Number(pf.percent) > 0) {
    cost.push(t("city.faq_platform_fee", { percent: number(Number(pf.percent), formatLocale), min: m(pf.min ?? 0) }));
  } else if (s && Number(s.percent) > 0) {
    const percent = number(Number(s.percent), formatLocale);
    const min = s.min != null && Number(s.min) > 0 ? m(s.min) : null;
    const max = s.max != null && Number(s.max) > 0 ? m(s.max) : null;
    cost.push(
      min && max
        ? t("city.faq_service_between", { percent, min, max })
        : min
          ? t("city.faq_service_min", { percent, min })
          : max
            ? t("city.faq_service_max", { percent, max })
            : t("city.faq_service", { percent }),
    );
  } else {
    cost.push(t("city.faq_no_service"));
  }
  if (p.small_order_fee && Number(p.small_order_fee.fee) > 0) {
    cost.push(t("city.faq_small_order", { below: m(p.small_order_fee.below), fee: m(p.small_order_fee.fee) }));
  }
  cost.push(t("city.faq_cost_end"));
  out.push({ q: t("city.faq_cost_q", { city }), a: cost.join(" ") });

  // The minimum order (one for the city, or per area).
  const mins = (p.min_order ?? []).filter((x) => Number(x.min_order) > 0);
  const amounts = [...new Set(mins.map((x) => Number(x.min_order)))];
  out.push({
    q: t("city.faq_min_q"),
    a: !mins.length
      ? t("city.faq_min_none")
      : amounts.length === 1 && (mins.length === 1 || mins.every((x) => !x.zone) || mins.length === c.zones.length)
        ? t("city.faq_min_one", { amount: m(amounts[0]) })
        : t("city.faq_min_zones", { list: mins.map((x) => (x.zone ? t("city.faq_min_zone", { zone: x.zone, amount: m(x.min_order) }) : m(x.min_order))).join("; ") }),
  });

  // Tips: all to the rider; the suggestions shown at checkout.
  const tips = (p.tip_presets?.amounts ?? []).map(Number).filter((n) => n > 0);
  out.push({ q: t("city.faq_tip_q"), a: tips.length ? t("city.faq_tip_presets", { amounts: tips.map((n) => m(n)).join(", ") }) : t("city.faq_tip_a") });

  out.push({ q: t("city.faq_tax_q"), a: t("city.faq_tax_a") });
  return out;
}
