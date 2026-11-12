"use client";
// The browser side: the signed-in session (phone + code, tokens in
// localStorage), the typed API client, and the bag (one restaurant).
import { createApi, unwrap, type CoreSchemas } from "@bhojango/api-client";
import { useSyncExternalStore } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export const urls = {
  core: process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001",
  realtime: process.env.NEXT_PUBLIC_REALTIME_URL ?? "http://localhost:8004",
  worker: process.env.NEXT_PUBLIC_WORKER_URL ?? "http://localhost:8006",
};

export type User = CoreSchemas["UserResponse"];

interface Session {
  access: string | null;
  refreshToken: string | null;
  user: User | null;
  sendCode: (phone: string, country: "IN" | "US") => Promise<void>;
  verify: (phone: string, code: string, country: "IN" | "US") => Promise<void>;
  refresh: () => Promise<string | null>;
  signOut: () => Promise<void>;
}

export const useSession = create<Session>()(persist((set, get) => ({
  access: null,
  refreshToken: null,
  user: null,
  sendCode: async (phone, country) => {
    unwrap(await api.core.POST("/api/v1/auth/send-otp", { body: { phone, country } }));
  },
  verify: async (phone, code, country) => {
    const t = unwrap(await api.core.POST("/api/v1/auth/phone", { body: { phone, otp: code, country } })) as { access_token: string; refresh_token: string };
    set({ access: t.access_token, refreshToken: t.refresh_token });
    set({ user: unwrap(await api.core.GET("/api/v1/users/me")) });
  },
  refresh: async () => {
    const rt = get().refreshToken;
    if (!rt) return null;
    const r = await fetch(`${urls.core}/api/v1/auth/refresh`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ refresh_token: rt }),
    });
    if (!r.ok) return null;
    const t = (await r.json()) as { access_token: string; refresh_token: string };
    set({ access: t.access_token, refreshToken: t.refresh_token });
    return t.access_token;
  },
  signOut: async () => {
    if (get().access) await api.core.POST("/api/v1/auth/logout").catch(() => undefined);
    set({ access: null, refreshToken: null, user: null });
  },
}), { name: "bhojango-session", storage: createJSONStorage(() => localStorage) }));

export const api = createApi({
  coreUrl: urls.core,
  realtimeUrl: urls.realtime,
  workerUrl: urls.worker,
  getAccessToken: () => useSession.getState().access,
  refreshAccessToken: () => useSession.getState().refresh(),
  onSignedOut: () => void useSession.getState().signOut(),
});

export function wsUrl(path: string): string {
  return `${urls.realtime.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(useSession.getState().access ?? "")}`;
}

// ── the bag ──────────────────────────────────────────────────────────────────

export interface Pick {
  group: string;
  option: string;
}

export interface BagLine {
  key: string;
  menuItemId: string;
  name: string;
  unitPrice: number;
  quantity: number;
  picks: Pick[];
  summary: string;
}

interface Bag {
  restaurant: { id: string; name: string; slug: string; city: string; currency: string } | null;
  lines: BagLine[];
  tip: number;
  add: (restaurant: NonNullable<Bag["restaurant"]>, line: Omit<BagLine, "key">) => void;
  setQuantity: (key: string, quantity: number) => void;
  setTip: (tip: number) => void;
  clear: () => void;
}

const keyOf = (id: string, picks: Pick[]) => `${id}|${picks.map((p) => `${p.group}=${p.option}`).sort().join(",")}`;

export const useBag = create<Bag>()(persist((set) => ({
  restaurant: null,
  lines: [],
  tip: 0,
  add: (restaurant, line) => set((s) => {
    const lines = s.restaurant?.id === restaurant.id ? s.lines : [];
    const key = keyOf(line.menuItemId, line.picks);
    const existing = lines.find((l) => l.key === key);
    return {
      restaurant,
      lines: existing ? lines.map((l) => (l.key === key ? { ...l, quantity: l.quantity + line.quantity } : l)) : [...lines, { ...line, key }],
    };
  }),
  setQuantity: (key, quantity) => set((s) => {
    const lines = quantity <= 0 ? s.lines.filter((l) => l.key !== key) : s.lines.map((l) => (l.key === key ? { ...l, quantity } : l));
    return lines.length ? { lines } : { lines, restaurant: null };
  }),
  setTip: (tip) => set({ tip }),
  clear: () => set({ restaurant: null, lines: [], tip: 0 }),
}), { name: "bhojango-bag", storage: createJSONStorage(() => localStorage) }));

export function cartItems(lines: BagLine[]) {
  return lines.map((l) => ({ menu_item_id: l.menuItemId, quantity: l.quantity, options: l.picks }));
}

function onHydrated(cb: () => void) {
  const a = useBag.persist.onFinishHydration(cb);
  const b = useSession.persist.onFinishHydration(cb);
  return () => {
    a();
    b();
  };
}

/** True once the saved session and bag have loaded in the browser (the server renders without them). */
export function useHydrated(): boolean {
  return useSyncExternalStore(onHydrated, () => useBag.persist.hasHydrated() && useSession.persist.hasHydrated(), () => false);
}
