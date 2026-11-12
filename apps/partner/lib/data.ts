// The partner's restaurant and what the tablet shows: today's state, the
// orders board (polled every 4 s), the menu, offers and the application.
import { api, money, unwrap, useSession, type CoreSchemas } from "@bhojango/mobile-core";
import { useCallback, useEffect, useRef, useState } from "react";
import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

export type Order = CoreSchemas["OrderResponse"];
export type Today = CoreSchemas["StateOut"];
export type Offer = CoreSchemas["OfferOut"];
export type Application = CoreSchemas["ApplicationOut"];

export type Kitchen = CoreSchemas["MineOut"];

const CHOSEN = "partner_kitchen";

interface KitchenStore {
  kitchens: Kitchen[] | null;
  kitchen: Kitchen | null;
  error: string | null;
  load: () => Promise<Kitchen | null>;
  choose: (k: Kitchen) => Promise<void>;
}

/** The kitchen this tablet runs. A partner with several picks one (remembered). */
export const useKitchen = create<KitchenStore>()((set) => ({
  kitchens: null,
  kitchen: null,
  error: null,
  load: async () => {
    try {
      const all = unwrap(await api.core.GET("/api/v1/restaurants/mine"));
      const saved = await SecureStore.getItemAsync(CHOSEN).catch(() => null);
      const k = all.find((x) => x.id === saved) ?? (all.length === 1 ? all[0] : null);
      const me = useSession.getState().user;
      set({ kitchens: all, kitchen: k ?? null, error: all.length ? null : `${me?.full_name ?? "This account"} has no restaurant yet.` });
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

export function cash(v: string | number | null | undefined, currency = "INR", decimals = 0): string {
  return money(Number(v ?? 0), currency, { decimals });
}

export function code(id: string): string {
  return "#" + id.replace(/-/g, "").slice(0, 4).toUpperCase();
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase();
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

/** Minutes until the rider reaches the kitchen (realtime ETA), or null. */
export async function riderEta(orderId: string): Promise<number | null> {
  const r = await api.realtime.GET("/api/v1/delivery/{order_id}/eta", { params: { path: { order_id: orderId } } }).catch(() => null);
  if (!r || r.error) return null;
  return (r.data as { estimated_pickup_minutes?: number | null }).estimated_pickup_minutes ?? null;
}
