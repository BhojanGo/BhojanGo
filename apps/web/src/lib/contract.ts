// Newer API fields the typed client may not list yet (all additive and
// optional): ratings, per-cuisine photos, a city's pricing, waiting counts,
// tip presets. Every helper falls back gracefully when a field is missing, so
// the site works on an older API too. Safe on the server and in the browser.
import type { Discover, KitchenCard } from "./server";

// ── ratings: "New" until 5 ratings, then "★4.6 (23)" ────────────────────────

export type RatingDisplay = { new: true } | { new: false; stars: number; count: number };

/** The few ratings a kitchen needs before its average is shown. */
export const RATINGS_SHOWN_FROM = 5;

/** The API's rating_display, else the same rule over rating / review_count. */
export function ratingOf(x: { rating_display?: unknown; rating?: number | string | null; review_count?: number | string | null }): RatingDisplay {
  const d = x.rating_display as Partial<{ new: boolean; stars: number; count: number }> | null | undefined;
  if (d && typeof d === "object") {
    if (d.new === false && d.stars != null && d.count != null) return { new: false, stars: Number(d.stars), count: Number(d.count) };
    if (d.new === true) return { new: true };
  }
  const count = Number(x.review_count ?? 0);
  const stars = Number(x.rating ?? 0);
  return count >= RATINGS_SHOWN_FROM && stars > 0 ? { new: false, stars, count } : { new: true };
}

// ── cuisine tiles: one unique photo each, only cuisines with 2+ kitchens ─────

export interface CuisineTileData {
  name: string;
  photo: string;
}

/**
 * The cuisine tiles for a page. With the newer API each cuisine carries its own
 * photo (already filtered to 2+ kitchens and unique); with an older one they
 * are worked out here from the kitchens. Either way a photo appears once per
 * page (`used` holds photos already on it, e.g. the hero) and a cuisine with no
 * photo of its own is left out rather than reusing one.
 */
export function cuisineTiles(d: Pick<Discover, "cuisines" | "restaurants"> | null | undefined, used: Set<string> = new Set(), limit = 8): CuisineTileData[] {
  const list = (d?.cuisines ?? []) as { name?: unknown; count?: unknown; photo?: unknown }[];
  const kitchens: KitchenCard[] = d?.restaurants ?? [];
  const fromApi = list.some((c) => "photo" in c);
  const out: CuisineTileData[] = [];
  for (const c of list) {
    if (out.length >= limit) break;
    const name = String(c.name ?? "");
    if (!name) continue;
    let src: string | null = null;
    if (fromApi) {
      src = typeof c.photo === "string" && c.photo ? c.photo : null;
      if (src && used.has(src)) src = null;
    } else {
      const lc = name.toLocaleLowerCase();
      const own = kitchens.filter((k) => k.cuisine_types.some((x) => x.toLocaleLowerCase() === lc));
      if (own.length < 2) continue;
      src = own.map((k) => k.cover_url).find((u): u is string => !!u && !used.has(u)) ?? null;
    }
    if (!src) continue;
    used.add(src);
    out.push({ name, photo: src });
  }
  return out;
}

// ── a city's pricing (city page FAQ and "from … delivery") ───────────────────

export interface CityPricing {
  currency: string;
  distance_unit: string;
  delivery: { up_to: number | string | null; fee: number | string }[];
  service_fee: { percent: number | string; min?: number | string | null; max?: number | string | null } | null;
  small_order: { below: number | string; fee: number | string } | null;
  min_order: { zone: string | null; amount: number | string }[];
  tip_presets: TipPresets | null;
}

export interface TipPresets {
  amounts: (number | string)[];
  default_index?: number | null;
}

export function pricingOf(c: unknown): CityPricing | null {
  const p = (c as { pricing?: CityPricing | null } | null)?.pricing;
  return p && Array.isArray(p.delivery) ? p : null;
}

/** The lowest delivery fee in a city's bands (null when there are none). */
export function lowestFee(p: CityPricing | null): number | null {
  const fees = (p?.delivery ?? []).map((b) => Number(b.fee)).filter((n) => Number.isFinite(n));
  return fees.length ? Math.min(...fees) : null;
}

/** People waiting for a coming-soon city (0 when unknown). */
export function waitingOf(c: unknown): number {
  const n = Number((c as { waiting?: unknown } | null)?.waiting ?? 0);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** The quote's tip choices, or null (older API, or none set for the city). */
export function tipPresetsOf(q: unknown): TipPresets | null {
  const p = (q as { tip_presets?: TipPresets | null } | null)?.tip_presets;
  return p && Array.isArray(p.amounts) && p.amounts.length ? p : null;
}

// ── orders: rider's first name, PIN, rating ──────────────────────────────────

export interface OrderRating {
  stars: number;
  comment?: string | null;
}

export function riderFirstName(o: unknown): string | null {
  const x = o as { rider_first_name?: string | null; rider?: { first_name?: string | null; name?: string | null } | null } | null;
  const name = x?.rider_first_name ?? x?.rider?.first_name ?? x?.rider?.name ?? null;
  return name ? (name.trim().split(/\s+/)[0] ?? null) : null;
}

export function orderRating(o: unknown): { rated: boolean | null; rating: OrderRating | null } {
  const x = o as { rated?: boolean; rating?: OrderRating | null } | null;
  return { rated: typeof x?.rated === "boolean" ? x.rated : null, rating: x?.rating && x.rating.stars ? x.rating : null };
}
