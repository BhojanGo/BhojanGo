// Kitchens for the drop point (GET /discover, as the website's personal home)
// and their menus (cached for the session).
import { api, unwrap, type CoreSchemas, type OptionGroup } from "@bhojango/mobile-core";
import { useCallback, useEffect, useState } from "react";
import { create } from "zustand";

import type { KitchenCard } from "./contract";

export type Restaurant = CoreSchemas["PublicRestaurant"];
export type Discover = CoreSchemas["Discover"];
export type MenuItem = Omit<CoreSchemas["MenuItemResponse"], "option_groups"> & { option_groups: OptionGroup[] };
export interface Menu {
  restaurant: Restaurant;
  categories: { name: string; items: MenuItem[] }[];
}

const menus = new Map<string, Menu>();

interface DiscoverState {
  key: string | null;
  data: Discover | null;
  loading: boolean;
  error: boolean;
  load: (at: { lat: number; lng: number }, force?: boolean) => Promise<void>;
}

/** The last /discover answer (home and search share it; the kitchen page reads its card's offer). */
export const useDiscoverStore = create<DiscoverState>()((set, get) => ({
  key: null,
  data: null,
  loading: false,
  error: false,
  load: async ({ lat, lng }, force = false) => {
    const key = `${lat.toFixed(5)},${lng.toFixed(5)}`;
    if (!force && get().key === key && (get().data || get().loading)) return;
    set({ key, loading: true, error: false, ...(get().key === key ? {} : { data: null }) });
    try {
      const d = unwrap(await api.core.GET("/api/v1/discover", { params: { query: { lat, lng } } })) as Discover;
      if (get().key === key) set({ data: d, loading: false });
    } catch {
      if (get().key === key) set({ loading: false, error: true });
    }
  },
}));

/** Kitchens, cuisines and offers for the drop point (null point: nothing yet). */
export function useDiscover(point: { lat: number; lng: number } | null | undefined) {
  const { data, loading, error, load } = useDiscoverStore();
  const lat = point?.lat;
  const lng = point?.lng;
  useEffect(() => {
    if (lat != null && lng != null) void load({ lat, lng });
  }, [lat, lng, load]);
  const reload = useCallback(() => (lat != null && lng != null ? load({ lat, lng }, true) : Promise.resolve()), [lat, lng, load]);
  return { data, kitchens: data?.restaurants ?? [], loading: loading || (!data && !error && lat != null), error, reload };
}

/** The kitchen's card from the last /discover (its offer, distance), if it was on it. */
export function useKitchenCard(id: string | undefined): KitchenCard | null {
  return useDiscoverStore((s) => s.data?.restaurants?.find((k) => k.id === id) ?? null);
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
    // Dishes outside a section go last, under the website's "More" heading (kitchen.more).
    categories: [...m.categories, ...(m.uncategorized_items.length ? [{ name: "", items: m.uncategorized_items }] : [])],
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
