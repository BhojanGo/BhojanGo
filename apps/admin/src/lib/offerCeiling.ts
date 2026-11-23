/**
 * Kitchen offer ceiling (R22 security review, S11): the most a kitchen's own offer may
 * give, the Markets setting `kitchen_offer_ceiling`, set on a country and overridden on a
 * city (country -> state -> city, key by key). Mirrors
 * backend/core_api/modules/markets/service/offer_ceiling.py, which is what the API enforces.
 */
export const CEILING_SETTING = "kitchen_offer_ceiling";
export type CeilingKey = "flat_off" | "max_discount" | "weekly_cap";
export type Ceiling = Partial<Record<CeilingKey, string>>;

export const CEILING_FIELDS: { key: CeilingKey; label: string; note: string }[] = [
  { key: "flat_off", label: "Amount off, per order", note: "The most a flat-amount offer takes off one order" },
  { key: "max_discount", label: "Most a %-off offer can take off one order", note: "A percent-off offer never takes more off one order" },
  { key: "weekly_cap", label: "Weekly cap", note: "The most a restaurant's offers give away in a week, together" },
];

/** What the API uses when no level sets a key (the country's currency). */
export const CEILING_DEFAULTS: Record<string, Ceiling> = {
  INR: { flat_off: "200", max_discount: "200", weekly_cap: "25000" },
  USD: { flat_off: "15", max_discount: "15", weekly_cap: "1500" },
};

const KEYS: CeilingKey[] = ["flat_off", "max_discount", "weekly_cap"];

/** A level's own ceiling (only well-formed keys). */
export function ownCeiling(settings: Record<string, unknown> | null | undefined): Ceiling {
  const v = settings?.[CEILING_SETTING];
  if (!v || typeof v !== "object" || Array.isArray(v)) return {};
  const out: Ceiling = {};
  for (const k of KEYS) {
    const x = (v as Record<string, unknown>)[k];
    if ((typeof x === "string" || typeof x === "number") && Number(x) > 0) out[k] = String(x);
  }
  return out;
}

/** The ceiling that applies given the levels' settings (country first), with where each key comes from. */
export function effectiveCeiling(levels: { name: string; settings: Record<string, unknown> | null | undefined }[], currency: string):
  Partial<Record<CeilingKey, { value: string; source: string }>> {
  const out: Partial<Record<CeilingKey, { value: string; source: string }>> = {};
  const defaults = CEILING_DEFAULTS[currency] ?? {};
  for (const k of KEYS) if (defaults[k]) out[k] = { value: defaults[k] as string, source: "BhojanGo's default" };
  for (const level of levels) {
    const own = ownCeiling(level.settings);
    for (const k of KEYS) if (own[k]) out[k] = { value: own[k] as string, source: level.name };
  }
  return out;
}

/** The setting to save from the form's boxes: empty boxes are left to the level above; none at all resets it (null). */
export function ceilingPatch(form: Ceiling): Ceiling | null | { error: string } {
  const out: Ceiling = {};
  for (const k of KEYS) {
    const raw = (form[k] ?? "").trim();
    if (!raw) continue;
    const n = Number(raw);
    if (!Number.isFinite(n) || n <= 0) return { error: `${CEILING_FIELDS.find((f) => f.key === k)?.label}: enter an amount above 0` };
    out[k] = raw;
  }
  return Object.keys(out).length ? out : null;
}
