// The website's rules for discovery, kitchens and tracking (apps/web/src/lib/contract.ts,
// components/Cards.tsx), as pure functions so the app shows the same things the
// same way. No React Native here: `node --test test/*.test.ts` runs them.
import type { CoreSchemas } from "@bhojango/api-client";

export type KitchenCard = CoreSchemas["Card"];
export type Offer = CoreSchemas["Offer"];
export type Order = CoreSchemas["OrderResponse"];

type T = (key: string, vars?: Record<string, string | number>) => string;
type Money = (amount: number | string | null | undefined, currency?: string | null, ) => string;

// ── photos ────────────────────────────────────────────────────────────────────

/**
 * A photo URL from the API, ready for <Image>. Absolute URLs pass through;
 * library photos ("/food/<slug>-<width>.webp") are served by the website, so
 * they are resolved against its address (EXPO_PUBLIC_WEB_URL). The library has
 * 400, 800 and 1600 px widths: `width` picks one. No URL, or a relative one with
 * no website to resolve it against: null (the caller shows a text row or an
 * initials tile, never an empty frame).
 */
export function photoUrl(url: string | null | undefined, webBase: string | null | undefined, width: 400 | 800 | 1600 = 800): string | null {
  if (!url) return null;
  const sized = url.replace(/-(400|800|1600)\.webp$/, `-${width}.webp`);
  if (/^https?:\/\//i.test(sized)) return sized;
  if (!sized.startsWith("/") || !webBase) return null;
  return `${webBase.replace(/\/+$/, "")}${sized}`;
}

/**
 * The sign-in screen's photos (R8, as the website's sign-in): the country's hero dish
 * (Markets' hero_photo, a library slug), then the photos of kitchens in its first
 * live city (photo_url, else cover_url), each photo once, at most `n`.
 */
export function signInPhotos(heroSlug: string | null | undefined, kitchens: readonly { photo_url?: string | null; cover_url?: string | null }[], n = 4): string[] {
  const out: string[] = [];
  const add = (u: string | null | undefined) => {
    if (u && !out.includes(u) && out.length < n) out.push(u);
  };
  if (heroSlug && /^[a-z0-9-]+$/.test(heroSlug)) add(`/food/${heroSlug}-800.webp`);
  for (const k of kitchens) add(k.photo_url ?? k.cover_url);
  return out;
}

/** "Royal Paneer Kitchen" -> "RP" (letters only; the initials tile of a kitchen with no photo). */
export function initials(name: string | null | undefined): string {
  return (name ?? "")
    .split(/\s+/)
    .filter((w) => /^\p{L}/u.test(w))
    .slice(0, 2)
    .map((w) => w[0]!.toLocaleUpperCase())
    .join("");
}

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

// ── cuisines: one unique photo each, only cuisines with 2+ kitchens ──────────

export interface CuisineTileData {
  name: string;
  count: number;
  /** The photo as the API sends it (resolve with photoUrl). */
  photo: string;
}

/**
 * The cuisine row. The API sends cuisines with 2+ kitchens, each with a photo
 * of its own (never the same photo twice); with an older API they are worked
 * out from the kitchens. A cuisine with no photo left is left out rather than
 * reusing another's.
 */
export function cuisineTiles(cuisines: readonly Record<string, unknown>[] | null | undefined, kitchens: readonly KitchenCard[] = [],
  used: Set<string> = new Set(), limit = 8): CuisineTileData[] {
  const list = cuisines ?? [];
  const fromApi = list.some((c) => "photo" in c);
  const out: CuisineTileData[] = [];
  for (const c of list) {
    if (out.length >= limit) break;
    const name = String(c.name ?? "");
    if (!name) continue;
    const lc = name.toLocaleLowerCase();
    const own = kitchens.filter((k) => k.cuisine_types.some((x) => x.toLocaleLowerCase() === lc));
    const count = Number(c.count ?? own.length);
    let src: string | null = null;
    if (fromApi) {
      src = typeof c.photo === "string" && c.photo ? c.photo : null;
      if (src && used.has(src)) src = null;
    } else {
      if (own.length < 2) continue;
      src = own.map((k) => k.cover_url).find((u): u is string => !!u && !used.has(u)) ?? null;
    }
    if (!src) continue;
    used.add(src);
    out.push({ name, count, photo: src });
  }
  return out;
}

/** Kitchens of a cuisine (any case), for the cuisine row's filter. */
export function ofCuisine(kitchens: readonly KitchenCard[], cuisine: string | null): KitchenCard[] {
  if (!cuisine) return [...kitchens];
  const lc = cuisine.toLocaleLowerCase();
  return kitchens.filter((k) => k.cuisine_types.some((x) => x.toLocaleLowerCase() === lc));
}

// ── offers: every offer says who pays ────────────────────────────────────────

/** "10% off, up to <money>", "Free delivery", from the offer's own numbers. */
export function offerTitle(o: Offer, t: T, money: Money, currency?: string | null): string {
  const m = (v?: string | null) => money(v ?? 0, currency);
  switch (o.template) {
    case "percent_off":
      return o.max_discount ? t("offers.percent_off_upto", { percent: o.percent ?? "", max: m(o.max_discount) }) : t("offers.percent_off", { percent: o.percent ?? "" });
    case "first_order":
      return o.max_discount ? t("offers.first_order_upto", { percent: o.percent ?? "", max: m(o.max_discount) }) : t("offers.first_order", { percent: o.percent ?? "" });
    case "flat_off":
      return t("offers.flat_off", { amount: m(o.amount) });
    case "free_delivery":
      return t("offers.free_delivery");
    default:
      return o.title;
  }
}

/** A card's badge: "10% off · kitchen pays" / "Free delivery · we pay". */
export function offerBadge(o: Offer, t: T, money: Money, currency?: string | null): string {
  const short = o.template === "percent_off" || o.template === "first_order" ? t("offers.percent_off", { percent: o.percent ?? "" }) : offerTitle(o, t, money, currency);
  return t(o.funded_by === "restaurant" ? "offers.badge_kitchen_pays" : "offers.badge_we_pay", { offer: short });
}

/** Who pays, on an offer card: "Kitchen pays" / "BhojanGo pays". */
export function offerPayer(o: Offer, t: T): string {
  return o.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays");
}

/** "At {kitchen}, orders over {amount}", "On every order". */
export function offerSubtitle(o: Offer, t: T, money: Money, currency?: string | null): string {
  const min = o.min_subtotal && Number(o.min_subtotal) > 0 ? money(o.min_subtotal, currency) : null;
  const kitchen = o.restaurant?.name as string | undefined;
  if (kitchen && min) return t("offers.kitchen_orders_over", { kitchen, amount: min });
  if (kitchen) return t("offers.kitchen_any", { kitchen });
  if (min) return t("offers.orders_over", { amount: min });
  return t("offers.every_order");
}

// ── orders: the active one, the rider, order again ───────────────────────────

const ACTIVE = new Set(["placed", "accepted", "preparing", "almost_ready", "ready", "picked_up"]);

/** The order on its way (or being cooked), newest first as the API lists them. */
export function activeOrder(orders: readonly Order[] | null | undefined): Order | null {
  return (orders ?? []).find((o) => ACTIVE.has(o.status)) ?? null;
}

/** The rider's first name only (never a surname or a phone number). */
export function riderFirstName(o: unknown): string | null {
  const x = o as { rider_first_name?: string | null; rider?: { first_name?: string | null; name?: string | null } | null } | null;
  const name = x?.rider_first_name ?? x?.rider?.first_name ?? x?.rider?.name ?? null;
  return name ? (name.trim().split(/\s+/)[0] ?? null) : null;
}

/** Order again: the latest delivered order from each kitchen, at most `limit`. */
export function orderAgain(orders: readonly Order[] | null | undefined, limit = 3): Order[] {
  const seen = new Set<string>();
  return (orders ?? []).filter((o) => o.status === "delivered" && !seen.has(o.restaurant_id) && !!seen.add(o.restaurant_id)).slice(0, limit);
}

/** Whole minutes from now until `iso` (at least 1), or null. */
export function minutesUntil(iso: string | null | undefined, now = Date.now()): number | null {
  if (!iso) return null;
  const at = Date.parse(iso);
  if (!Number.isFinite(at)) return null;
  return Math.max(1, Math.round((at - now) / 60000));
}

// ── live tracking ────────────────────────────────────────────────────────────

export type Pt = [number, number]; // [lat, lng], as the tracking socket sends them

/** The ETA from realtime's tracking socket (distance_left / distance_unit when the service sends them). */
export interface Eta {
  to_pickup_minutes: number;
  to_customer_minutes: number;
  arrives_at: string;
  distance_left?: number | string | null;
  distance_unit?: string | null;
}

export function kmBetween(a: Pt, b: Pt): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(rad(b[0] - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

/**
 * How far is left: the ETA's own distance_left in its distance_unit, else the
 * straight line from the rider to the next stop in kilometres (unit null: the
 * caller formats it in the country's unit).
 */
export function distanceLeft(eta: Eta | null | undefined, rider: Pt | null, next: Pt | null): { value: number; unit: string | null; km: boolean } | null {
  const v = eta?.distance_left;
  if (v != null && Number.isFinite(Number(v)) && eta?.distance_unit) return { value: Number(v), unit: eta.distance_unit, km: false };
  if (rider && next) return { value: kmBetween(rider, next), unit: null, km: true };
  return null;
}

/** The rider's next stop: the kitchen until the food is picked up, then home. */
export function nextStop(status: string | null | undefined, pickup: Pt | null, dropoff: Pt | null): Pt | null {
  return status === "picked_up" ? dropoff : (pickup ?? dropoff);
}

/** [west, south, east, north] around the points (with a little room), or null. */
export function boundsOf(points: readonly (Pt | null)[], pad = 0.002): [number, number, number, number] | null {
  const pts = points.filter((p): p is Pt => !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]));
  if (!pts.length) return null;
  const lats = pts.map((p) => p[0]);
  const lngs = pts.map((p) => p[1]);
  return [Math.min(...lngs) - pad, Math.min(...lats) - pad, Math.max(...lngs) + pad, Math.max(...lats) + pad];
}

// ── the greeting ──────────────────────────────────────────────────────────────

/** The part of the day (message keys app.home.hello_*, app.home.ask_*). */
export type PartOfDay = "morning" | "afternoon" | "evening" | "night";

/** The part of the day for an hour (0-23) at the delivery address. */
export function partOfDayAt(hour: number): PartOfDay {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  if (hour >= 17 && hour < 22) return "evening";
  return "night";
}

/**
 * The time zone the greeting is in: the delivery address's city (GET /markets/locate),
 * else the current country's (Markets: the address's, the person's choice, ...). null
 * only when neither is known yet; never the phone's zone while one is.
 */
export function greetingZone(cityZone: string | null | undefined, countryZone: string | null | undefined): string | null {
  return cityZone || countryZone || null;
}
