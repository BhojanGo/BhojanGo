// Server-side reads (web v2). Everything about places, kitchens, prices and
// offers comes from core_api: no city, state, country, currency or price is
// typed into a page (docs/design/web/WebDataRules.html; checked by tools/web/check_templates.py in make ci).

import type { CoreSchemas } from "@bhojango/api-client";
import { unstable_noStore as noStore } from "next/cache";

export type Directory = CoreSchemas["Directory"];
export type DirCountry = CoreSchemas["DirCountry"];
export type DirRegion = CoreSchemas["DirRegion"];
export type DirCity = CoreSchemas["DirCity"];
export type CityPage = CoreSchemas["CityPage"];
export type Discover = CoreSchemas["Discover"];
export type KitchenCard = CoreSchemas["Card"];
export type Offer = CoreSchemas["Offer"];
export type Restaurant = CoreSchemas["PublicRestaurant"];
export type MenuItem = CoreSchemas["MenuItemResponse"];
export interface Menu {
  restaurant: Restaurant;
  categories: { id?: string; name: string; description?: string | null; items: MenuItem[] }[];
  uncategorized_items: MenuItem[];
}
export interface BillLine {
  code: string;
  label: string;
  amount: string;
  funded_by?: string | null;
  detail?: Record<string, string> | null;
}
export interface ExampleBill {
  city: string;
  city_name: string;
  currency: string;
  total: string;
  source: "order" | "typical";
  lines: BillLine[];
  /** Who gets the money, from the engine's split (rider = pay + tip); absent on an older API. */
  shares?: Record<"kitchen" | "rider" | "tax" | "us", string>;
  assumptions: Record<string, string>;
}

const CORE = process.env.CORE_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";

async function get<T>(path: string, revalidate = 60): Promise<T | null> {
  try {
    const r = await fetch(`${CORE}/api/v1${path}`, { next: { revalidate } });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return (await r.json()) as T;
  } catch (e) {
    // No backend (e.g. building the image in CI): render per request instead of caching an empty page.
    console.warn("core_api unavailable", (e as Error).message);
    noStore();
    return null;
  }
}

const EMPTY_DIRECTORY: Directory = { countries: [], totals: { countries: 0, live: 0, soon: 0, restaurants: 0 } };

/** Countries -> states -> cities (live and coming soon), from Markets. */
export async function directory(): Promise<Directory> {
  return (await get<Directory>("/markets/directory", 60)) ?? EMPTY_DIRECTORY;
}

export async function cityPage(country: string, slug: string): Promise<CityPage | null> {
  return get<CityPage>(`/markets/cities/${encodeURIComponent(country)}/${encodeURIComponent(slug)}`, 60);
}

/** Kitchens, fees and offers for an address (lat/lng), or a whole city (code). */
export async function discover(where: { lat: number; lng: number } | { city: string }): Promise<Discover | null> {
  const q = "city" in where ? `city=${encodeURIComponent(where.city)}` : `lat=${where.lat}&lng=${where.lng}`;
  return get<Discover>(`/discover?${q}`, 30);
}

export async function restaurant(slug: string): Promise<Restaurant | null> {
  return get<Restaurant>(`/restaurants/by-slug/${encodeURIComponent(slug)}`);
}

export async function menu(id: string): Promise<Menu | null> {
  return get<Menu>(`/restaurants/${id}/menu`, 60);
}

/** A real recent bill for the zone or city (or a typical cart priced by the engine). */
export async function exampleBill(city: string, zone?: string | null): Promise<ExampleBill | null> {
  return get<ExampleBill>(`/pricing/example?city=${encodeURIComponent(city)}${zone ? `&zone=${zone}` : ""}`, 3600);
}

/** Which social sign-ins are configured ({google: {client_id} | null, apple: null}); null on an older API. */
export async function authProviders(): Promise<{ google?: { client_id: string } | null; apple?: { client_id: string } | null } | null> {
  return get("/auth/providers", 300);
}

export const SITE = process.env.NEXT_PUBLIC_APP_URL ?? "https://bhojango.com";
/** Search engines index production only (APP_ENV=production); QA, staging and local are noindex. */
export const INDEXABLE = process.env.APP_ENV === "production";
