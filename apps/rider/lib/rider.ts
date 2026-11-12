// The rider's state: onboarding, online/offer/busy (live over /ws/rider with a
// poll as a safety net), the active delivery and the week's earnings.
import { api, money, unwrap, wsUrl, type CoreSchemas } from "@bhojango/mobile-core";
import { useCallback, useEffect, useRef, useState } from "react";
import { create } from "zustand";

export type Onboarding = CoreSchemas["OnboardingOut"];
export type Order = CoreSchemas["OrderResponse"];

export interface Offer {
  order_id: string;
  expires_at: string;
  expires_in: number;
  distance_km: number;
  restaurant_name: string | null;
  pickup: [number, number];
  dropoff: [number, number] | null;
  eta: { to_pickup_minutes: number; to_customer_minutes: number } | null;
  code?: string;
  currency?: string;
  rider_pay?: string | null;
  tip?: string | null;
  items_count?: number;
  bags?: number;
  ready_in_minutes?: number | null;
  drop_area?: string | null;
  distance_unit?: "km" | "mi";
  trip_km?: number | null;
}

export interface RiderNow {
  state: { status: "offline" | "available" | "offered" | "busy"; order_id?: string };
  offer: Offer | null;
  location: { lat: number; lng: number } | null;
}

export interface Week {
  currency: string;
  city: string | null;
  period_start: string;
  period_end: string;
  payout_date: string;
  total: string;
  summary: {
    deliveries: number; tips: string; active_hours: string; hourly_floor: string | null; floor_top_up: string;
    per_active_hour: string | null; total: string; base: string; distance: string; waiting: string;
  };
  days: { date: string; deliveries: number; total: string }[];
  today: { date: string; total: string; lines: WeekLine[] };
}

export interface WeekLine {
  order_id: string; delivered_at: string; base: string; distance: string; waiting: string; tip: string; total: string;
  restaurant_name?: string; drop_area?: string | null;
}

// ── formatting ───────────────────────────────────────────────────────────────

const MI = 1.609344;

export function dist(km: number | null | undefined, unit: "km" | "mi" = "km"): string {
  if (km == null) return "";
  const v = unit === "mi" ? km / MI : km;
  return `${v.toFixed(1)} ${unit}`;
}

export function cash(v: string | number | null | undefined, currency = "USD", decimals = 2): string {
  return money(Number(v ?? 0), currency, { decimals });
}

export const CITY_NAMES: Record<string, string> = { "IN-TG-HYD": "Hyderabad", "US-ID-BOI": "Boise" };

// ── live rider state ─────────────────────────────────────────────────────────

interface LiveStore {
  now: RiderNow | null;
  /** Orders finished on this phone; realtime may still say "busy" for a moment after drop-off. */
  finished: string[];
  finish: (orderId: string) => void;
  set: (n: RiderNow) => void;
  refresh: () => Promise<RiderNow | null>;
}

export const useLive = create<LiveStore>()((set) => ({
  now: null,
  finished: [],
  finish: (orderId) => set((s) => ({ finished: [...s.finished.slice(-20), orderId] })),
  set: (now) => set({ now }),
  refresh: async () => {
    const r = await api.realtime.GET("/api/v1/riders/me").catch(() => null);
    if (!r || r.error) return null;
    const now = r.data as unknown as RiderNow;
    set({ now });
    return now;
  },
}));

/** Keep useLive current: WebSocket offers/withdrawals, plus a poll every 5 s. */
export function useLiveRider(enabled: boolean) {
  const refresh = useLive((s) => s.refresh);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    const connect = () => {
      ws = new WebSocket(wsUrl("/ws/rider"));
      ws.onmessage = () => void refresh();
      ws.onclose = () => {
        if (alive) retry = setTimeout(connect, 3000);
      };
    };
    connect();
    void refresh();
    const poll = setInterval(() => void refresh(), 5000);
    return () => {
      alive = false;
      clearInterval(poll);
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [enabled, refresh]);
}

// ── data ─────────────────────────────────────────────────────────────────────

function useLoad<T>(load: () => Promise<T>, key = "") {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const live = useRef(true);
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });
  const reload = useCallback(async () => {
    try {
      const v = await loader.current();
      if (live.current) {
        setData(v);
        setError(null);
      }
      return v;
    } catch (e) {
      if (live.current) setError((e as Error).message);
      return null;
    }
    // `key` (e.g. the order id) decides when to load again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => {
    live.current = true;
    void reload();
    return () => {
      live.current = false;
    };
  }, [reload]);
  return { data, error, reload, setData };
}

export function useOnboarding() {
  return useLoad(async () => unwrap(await api.core.GET("/api/v1/riders/me/onboarding")) as Onboarding);
}

export function useWeek() {
  return useLoad(async () => unwrap(await api.core.GET("/api/v1/finance/earnings/me")) as unknown as Week);
}

export function useOrder(id: string | undefined) {
  return useLoad(async () => (id ? (unwrap(await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })) as Order) : null), id);
}
