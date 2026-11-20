"use client";
// The browser side: the signed-in session, the typed API client, and the bag (one restaurant).
//
// R22 security review (S8): the session lives in httpOnly cookies that core_api sets on its
// own host (bg_web_at, bg_web_rt; backend/shared/session.py). This page never sees a token:
// every call sends the cookies (credentials "include"), and every change says it is the
// website (X-Session: web). The store keeps only who is signed in, for the header and account pages.
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

/**
 * A call to core_api with the session's cookies (never a token in the page). A change says
 * it's the website (X-Session: web), which core_api requires with a cookie (CSRF); a read
 * doesn't, so it needs no CORS preflight.
 */
export function coreFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") headers.set("X-Session", "web");
  return fetch(`${urls.core}${path}`, { ...init, headers, credentials: "include" });
}

interface Session {
  signedIn: boolean;
  user: User | null;
  sendCode: (phone: string, country: string) => Promise<void>;
  verify: (phone: string, code: string, country: string) => Promise<void>;
  /** Renew the session's cookies; false when the session has ended. */
  refresh: () => Promise<boolean>;
  signOut: () => Promise<void>;
  /** After a sign-in answer (its cookies are already set): load who signed in. */
  adopt: (answer?: unknown) => Promise<void>;
}

// Sessions from before R22 kept the tokens in localStorage: remove them (that person signs in again once).
if (typeof window !== "undefined") {
  try {
    window.localStorage.removeItem("bhojango-session");
  } catch {
    // storage blocked: nothing was kept there either
  }
}

let refreshing: Promise<boolean> | null = null;

export const useSession = create<Session>()(persist((set, get) => ({
  signedIn: false,
  user: null,
  sendCode: async (phone, country) => {
    // The page's language (<html lang>): the code's SMS is written in it when the country offers it.
    const language = typeof document === "undefined" ? undefined : document.documentElement.lang || undefined;
    unwrap(await api.core.POST("/api/v1/auth/send-otp", { body: { phone, country, language } }));
  },
  verify: async (phone, code, country) => {
    unwrap(await api.core.POST("/api/v1/auth/phone", { body: { phone, otp: code, country } }));
    await get().adopt();
  },
  // One refresh at a time: a refresh token works once, and using it twice ends the session
  // (the tracking page's two sockets can ask for new tickets together).
  refresh: () => (refreshing ??= (async () => {
    const r = await coreFetch("/api/v1/auth/refresh", { method: "POST" }).catch(() => null);
    if (!r?.ok) return false;
    set({ signedIn: true });
    return true;
  })().finally(() => {
    refreshing = null;
  })),
  adopt: async () => {
    set({ signedIn: true });
    set({ user: unwrap(await api.core.GET("/api/v1/users/me")) });
  },
  signOut: async () => {
    if (get().signedIn) {
      // Ends the session on the server and clears its cookies (also when the access cookie ran out).
      const r = await coreFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => null);
      if (r?.status === 401 && (await get().refresh())) await coreFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => null);
    }
    set({ signedIn: false, user: null });
  },
}), {
  name: "bhojango-session-v2",
  storage: createJSONStorage(() => localStorage),
  partialize: (s) => ({ signedIn: s.signedIn, user: s.user }),
}));

export const api = createApi({
  coreUrl: urls.core,
  realtimeUrl: urls.realtime,
  workerUrl: urls.worker,
  session: "web",
  getAccessToken: () => null,
  refreshAccessToken: async () => ((await useSession.getState().refresh()) ? "cookie" : null),
  onSignedOut: () => void useSession.getState().signOut(),
});

/**
 * The realtime WebSocket's address for ``path``. realtime is on another host and can't see
 * the session's cookies, so this asks core_api for a socket ticket (it expires with the
 * session's access token; the socket then closes with 4401 and liveSocket opens a new one).
 */
export async function wsUrl(path: string): Promise<string> {
  const ticket = () => coreFetch("/api/v1/auth/socket-ticket", { method: "POST" });
  let r = await ticket();
  if (r.status === 401 && (await useSession.getState().refresh())) r = await ticket();
  if (!r.ok) throw new Error(`socket ticket: HTTP ${r.status}`);
  const { ticket: t } = (await r.json()) as { ticket: string };
  return `${urls.realtime.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(t)}`;
}

/**
 * A live socket that opens again when it closes (its ticket expired: 4401, or the network
 * dropped), until the returned stop function is called. A refused socket (4001, 4004, 4403,
 * 4429) isn't reopened.
 */
export function liveSocket(path: string, onMessage: (e: MessageEvent) => void): () => void {
  let stopped = false;
  let ws: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let failures = 0;
  const open = async () => {
    if (stopped) return;
    try {
      ws = new WebSocket(await wsUrl(path));
    } catch {
      failures += 1;
      retry = setTimeout(() => void open(), Math.min(30000, 2000 * failures));
      return;
    }
    if (stopped) {
      ws.close();
      return;
    }
    ws.onopen = () => {
      failures = 0;
    };
    ws.onmessage = onMessage;
    ws.onclose = (e) => {
      if (stopped || [4001, 4004, 4403, 4429].includes(e.code)) return;
      failures += 1;
      retry = setTimeout(() => void open(), e.code === 4401 ? 0 : Math.min(30000, 2000 * failures));
    };
  };
  void open();
  return () => {
    stopped = true;
    if (retry) clearTimeout(retry);
    ws?.close();
  };
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

/**
 * A signed-in call to an endpoint the typed client may not list yet (newer
 * account APIs): the session's cookies, one refresh on 401, JSON in and out.
 */
export async function authed<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const go = () =>
    coreFetch(path, {
      method,
      headers: body !== undefined ? { "content-type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  let r = await go();
  if (r.status === 401) {
    if (!(await useSession.getState().refresh())) {
      await useSession.getState().signOut();
      throw new Error("signed out");
    }
    r = await go();
  }
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    const d = (detail as { detail?: unknown }).detail;
    throw new Error(typeof d === "string" ? d : (d as { message?: string })?.message ?? `HTTP ${r.status}`);
  }
  // 204 No Content (saving a favourite, a default address...) may still say "json": no body to read.
  if (r.status === 204 || r.headers.get("content-length") === "0") return undefined as T;
  const type = r.headers.get("content-type") ?? "";
  return (type.includes("json") ? await r.json() : await r.blob()) as T;
}
