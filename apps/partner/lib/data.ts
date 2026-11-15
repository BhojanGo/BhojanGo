// The partner's restaurant and what the tablet shows: today's state, the
// orders board (polled every 4 s), the menu, offers and the application.
import { api, inZone, unwrap, urls, useI18n, type CoreSchemas } from "@bhojango/mobile-core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

export type Order = CoreSchemas["OrderResponse"];
export type Today = CoreSchemas["StateOut"];
export type Offer = CoreSchemas["OfferOut"];
export type Application = CoreSchemas["ApplicationOut"];
export type RatingSummary = CoreSchemas["RatingSummary"];

export type Kitchen = CoreSchemas["MineOut"];

const CHOSEN = "partner_kitchen";

interface KitchenStore {
  kitchens: Kitchen[] | null;
  kitchen: Kitchen | null;
  /** The API's reason the kitchens didn't load; null when they did. */
  error: string | null;
  /** Signed in, but the account has no kitchen (index shows partner.home.no_kitchen). */
  none: boolean;
  load: () => Promise<Kitchen | null>;
  choose: (k: Kitchen) => Promise<void>;
}

/** The kitchen this tablet runs. A partner with several picks one (remembered). */
export const useKitchen = create<KitchenStore>()((set) => ({
  kitchens: null,
  kitchen: null,
  error: null,
  none: false,
  load: async () => {
    try {
      const all = unwrap(await api.core.GET("/api/v1/restaurants/mine"));
      const saved = await SecureStore.getItemAsync(CHOSEN).catch(() => null);
      const k = all.find((x) => x.id === saved) ?? (all.length === 1 ? all[0] : null);
      set({ kitchens: all, kitchen: k ?? null, error: null, none: !all.length });
      return k ?? null;
    } catch (e) {
      set({ error: (e as Error).message });
      return null;
    }
  },
  choose: async (k) => {
    await SecureStore.setItemAsync(CHOSEN, k.id).catch(() => undefined);
    set({ kitchen: k });
  },
}));

/**
 * Money, times and dates for the kitchen's screens, by the country (Markets data
 * through useI18n). Call it at the top of a component.
 *   const { cash, clock, date } = useFormat();
 */
export function useFormat() {
  const { money, time, date } = useI18n();
  return useMemo(() => ({
    /** cash(250, order.currency): whole amounts lose ".00" (decimals 2 always shows cents). No currency: the country's. */
    cash: (v: string | number | null | undefined, currency?: string | null, decimals = 0) =>
      money(Number(v ?? 0), currency, { whole: decimals === 0 }),
    /** "7:05 pm" in the country's clock, in a time zone: the order's (order.time_zone) or the kitchen's city (today.time_zone), never the tablet's. */
    clock: (iso: string | null | undefined, zone?: string | null) => (iso ? time(iso, inZone(zone)) : ""),
    date,
  }), [money, time, date]);
}

export function code(id: string): string {
  return "#" + id.replace(/-/g, "").slice(0, 6).toUpperCase(); // as in messages and the rider app
}

export function useLoad<T>(load: () => Promise<T>, key = "", every = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });
  const reload = useCallback(async () => {
    try {
      const v = await loader.current();
      setData(v);
      setError(null);
      return v;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    void reload();
    if (!every) return;
    const t = setInterval(() => void reload(), every);
    return () => clearInterval(t);
  }, [reload, every]);
  return { data, error, reload, setData };
}

export async function getToday(id: string): Promise<Today> {
  return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/today", { params: { path: { restaurant_id: id } } }));
}

export async function getBoard(id: string): Promise<Order[]> {
  const r = unwrap(await api.core.GET("/api/v1/orders/restaurant/{restaurant_id}", {
    params: { path: { restaurant_id: id }, query: { limit: 100 } },
  }));
  return r.items;
}

export async function move(orderId: string, status: string, prepMinutes?: number): Promise<Order> {
  return unwrap(await api.core.PUT("/api/v1/orders/{order_id}/status", {
    params: { path: { order_id: orderId } },
    body: { status: status as never, ...(prepMinutes ? { prep_minutes: prepMinutes } : {}) },
  }));
}

export async function reject(orderId: string): Promise<Order> {
  return unwrap(await api.core.POST("/api/v1/orders/{order_id}/cancel", {
    params: { path: { order_id: orderId } }, body: { reason: "restaurant_cancelled", note: "Rejected on the tablet" },
  }));
}

/** The kitchen's ratings for the dashboard: "New" until 5, average, count, stars, latest comments. */
export async function getRatingSummary(id: string): Promise<RatingSummary> {
  return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/ratings/summary", { params: { path: { restaurant_id: id } } }));
}

/**
 * A dish photo's address the tablet can load. Absolute URLs (uploaded menu photos on
 * core_api, S3) as they are; the website's photo library paths ("/food/...") need the
 * website's address (EXPO_PUBLIC_WEB_URL), else null (the preview shows a stand-in).
 */
export function imageUri(url: string | null | undefined): string | null {
  if (!url) return null;
  if (/^https?:\/\//.test(url)) return url;
  if (url.startsWith("/api/")) return `${urls.core}${url}`;
  const web = process.env.EXPO_PUBLIC_WEB_URL;
  return web && url.startsWith("/") ? `${web.replace(/\/$/, "")}${url}` : null;
}

/** Minutes until the rider reaches the kitchen (realtime ETA), or null. */
export async function riderEta(orderId: string): Promise<number | null> {
  const r = await api.realtime.GET("/api/v1/delivery/{order_id}/eta", { params: { path: { order_id: orderId } } }).catch(() => null);
  if (!r || r.error) return null;
  return (r.data as { estimated_pickup_minutes?: number | null }).estimated_pickup_minutes ?? null;
}
