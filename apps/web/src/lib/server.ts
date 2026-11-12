// Server-side reads for the search-friendly pages (home, city, restaurant).
// Cached for 5 minutes (ISR): menus and listings don't change by the second.

import type { CoreSchemas } from "@bhojango/api-client";
import { unstable_noStore as noStore } from "next/cache";

export type City = CoreSchemas["PublicCity"];
export type Restaurant = CoreSchemas["RestaurantResponse"];
export type MenuItem = CoreSchemas["MenuItemResponse"];
export interface Menu {
  restaurant: Restaurant;
  categories: { name: string; items: MenuItem[] }[];
  uncategorized_items: MenuItem[];
}

const CORE = process.env.CORE_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";

async function get<T>(path: string, revalidate = 300): Promise<T | null> {
  try {
    const r = await fetch(`${CORE}/api/v1${path}`, { next: { revalidate } });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return (await r.json()) as T;
  } catch (e) {
    // No backend (e.g. building the image in CI): don't let an empty page be cached as the
    // static version. The route renders per request instead; the fetches themselves stay cached.
    console.warn("core_api unavailable", (e as Error).message);
    noStore();
    return null;
  }
}

export async function cities(): Promise<City[]> {
  return (await get<City[]>("/markets/cities")) ?? [];
}

export async function city(slug: string): Promise<City | null> {
  return (await cities()).find((c) => c.slug === slug) ?? null;
}

export async function restaurantsIn(c: City): Promise<Restaurant[]> {
  const r = await get<{ items: Restaurant[] }>(`/restaurants?city=${encodeURIComponent(c.name)}&limit=100`);
  return r?.items ?? [];
}

export async function restaurant(slug: string): Promise<Restaurant | null> {
  return get<Restaurant>(`/restaurants/by-slug/${encodeURIComponent(slug)}`);
}

export async function menu(id: string): Promise<Menu | null> {
  return get<Menu>(`/restaurants/${id}/menu`, 120);
}

export const SITE = process.env.NEXT_PUBLIC_APP_URL ?? "https://bhojango.com";
