// The rider's state: onboarding, online/offer/busy (live over /ws/rider with a
// poll as a safety net), the active delivery and the week's earnings.
import { api, ApiError, countryForCurrency, findCity, liveSocket, unwrap, useCountry, useI18n, type CoreSchemas } from "@bhojango/mobile-core";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  distance_unit?: string; // the country's unit (Markets)
  trip_km?: number | null;
  /** Task 43: two orders from one kitchen, in drop-off order. rider_pay and tip are then the totals. */
  batch?: BatchStop[] | null;
  batch_minutes?: number | null;
}

export interface BatchStop {
  order_id: string;
  code?: string | null;
  restaurant_name?: string | null;
  dropoff: [number, number] | null;
  drop_area?: string | null;
  rider_pay?: string | null;
  batch_rate?: boolean; // a later drop-off: no base, distance + waiting + the batch bonus (item 2)
  tip?: string | null;
  trip_km?: number | null;
}

export interface RiderNow {
  state: { status: "offline" | "available" | "offered" | "busy"; order_id?: string; batch?: string[] };
  offer: Offer | null;
  location: { lat: number; lng: number } | null;
}

export interface Week {
  currency: string;
  city: string | null;
  /** The rider's city time zone (IANA): delivery times are shown in it, never the phone's. */
  time_zone?: string | null;
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

/**
 * Money, distances, dates and city names for the rider's screens, all by the
 * country (Markets data through useI18n/useCountry). Call it at the top of a component.
 *   const { cash, dist, cityName, unitFor, date, time } = useFormat();
 */
export function useFormat() {
  const { money, distance, date, time } = useI18n();
  const { countries, country } = useCountry();
  return useMemo(() => ({
    /** cash(12.5, order.currency): always two decimals, 12.50 (R12). */
    cash: (v: string | number | null | undefined, currency?: string | null) => money(Number(v ?? 0), currency),
    /** Kilometres in, the country's unit out (or `unit` as the API sends it). */
    dist: (km: number | null | undefined, unit?: string | null) => distance(km, unit),
    /** The distance unit of the country that uses `currency` (an order's), from Markets. */
    unitFor: (currency: string | null | undefined) => countryForCurrency(countries, currency)?.distance_unit ?? null,
    /** A city's name from its Markets code ("XX-RR-CCC"), else the code. */
    cityName: (code: string | null | undefined) => (code ? findCity(countries, code)?.city.name ?? code : null),
    /** The map's centre with no GPS fix (R8): the partner's city (Markets), else the current country's first live city. */
    cityCentre: (code: string | null | undefined): [number, number] | null => {
      const c = findCity(countries, code)?.city ?? country?.regions.flatMap((r) => r.cities).find((x) => x.status === "live") ?? null;
      return c ? [c.lat, c.lng] : null;
    },
    date,
    time,
  }), [money, distance, date, time, countries, country]);
}

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
    // Reopens when it drops, and with a fresh token when realtime closes it at the token's expiry (R22 S10).
    const stopSocket = liveSocket("/ws/rider", () => void refresh());
    void refresh();
    const poll = setInterval(() => void refresh(), 5000);
    return () => {
      clearInterval(poll);
      stopSocket();
    };
  }, [enabled, refresh]);
}

// ── data ─────────────────────────────────────────────────────────────────────

function useLoad<T>(load: () => Promise<T>, key = "") {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** What the last load threw (R9: <LoadError error={failure} onRetry={reload} tone="dark" />); null after a good one. */
  const [failure, setFailure] = useState<unknown>(null);
  /** The HTTP status of the last failed load (403/404: not yours, or gone), else null. */
  const [status, setStatus] = useState<number | null>(null);
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
        setFailure(null);
        setStatus(null);
      }
      return v;
    } catch (e) {
      if (live.current) {
        setError((e as Error).message);
        setFailure(e);
        setStatus(e instanceof ApiError ? e.status : null);
      }
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
  return { data, error, failure, status, reload, setData };
}

export function useOnboarding() {
  return useLoad(async () => unwrap(await api.core.GET("/api/v1/riders/me/onboarding")) as Onboarding);
}

export function useWeek() {
  return useLoad(async () => unwrap(await api.core.GET("/api/v1/finance/earnings/me")) as unknown as Week);
}

/**
 * The order this rider is delivering. Other places move it on too (the kitchen,
 * the demo simulator on QA, the same rider signed in on another phone), so the
 * screen polls it and shows whatever the server says. `gone`: the order isn't
 * this rider's any more (reassigned or cancelled away: 403/404).
 */
export function useOrder(id: string | undefined) {
  const load = useLoad(async () => (id ? (unwrap(await api.core.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } })) as Order) : null), id);
  return { ...load, gone: load.status === 403 || load.status === 404 };
}
