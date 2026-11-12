// Restaurants near the drop point and their menus (cached for the session).
import { api, unwrap, type CoreSchemas, type OptionGroup } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";

export type Restaurant = CoreSchemas["RestaurantResponse"];
export type MenuItem = Omit<CoreSchemas["MenuItemResponse"], "option_groups"> & { option_groups: OptionGroup[] };
export interface Menu {
  restaurant: Restaurant;
  categories: { name: string; items: MenuItem[] }[];
}

const menus = new Map<string, Menu>();

/** Distance in km between two points (for "2.1 km" on cards). */
export function km(a: { lat: number; lng: number }, b: { lat: number | null; lng: number | null }): number | null {
  if (b.lat == null || b.lng == null) return null;
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function useRestaurants(city: string | null | undefined) {
  const [state, setState] = useState<{ items: Restaurant[]; loading: boolean; error: string | null }>({ items: [], loading: true, error: null });
  useEffect(() => {
    if (!city) return;
    let live = true;
    api.core
      .GET("/api/v1/restaurants", { params: { query: { city, limit: 50 } } })
      .then((r) => live && setState({ items: (unwrap(r) as { items: Restaurant[] }).items, loading: false, error: null }))
      .catch((e: Error) => live && setState({ items: [], loading: false, error: e.message }));
    return () => {
      live = false;
    };
  }, [city]);
  return state;
}

export async function loadMenu(id: string): Promise<Menu> {
  const cached = menus.get(id);
  if (cached) return cached;
  const m = unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/menu", { params: { path: { restaurant_id: id } } })) as unknown as {
    restaurant: Restaurant;
    categories: { name: string; items: MenuItem[] }[];
    uncategorized_items: MenuItem[];
  };
  const menu: Menu = {
    restaurant: m.restaurant,
    categories: [...m.categories, ...(m.uncategorized_items.length ? [{ name: "More", items: m.uncategorized_items }] : [])],
  };
  menus.set(id, menu);
  return menu;
}

export function useMenu(id: string | undefined) {
  const [menu, setMenu] = useState<Menu | null>(id ? (menus.get(id) ?? null) : null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!id) return;
    loadMenu(id).then(setMenu).catch((e: Error) => setError(e.message));
  }, [id]);
  return { menu, error };
}
