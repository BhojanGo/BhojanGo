// The signed-in session and the typed API client for the Expo apps (P17).
// Tokens live in SecureStore; the client adds the access token, refreshes it
// once on a 401 (one refresh shared by concurrent requests) and signs out if
// the refresh token is no longer good.
import { createApi, unwrap, type CoreSchemas } from "@bhojango/api-client";
import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

const env = (k: string, fallback: string) => (process.env as Record<string, string | undefined>)[k] || fallback;

// The emulator reaches the host's services through `adb reverse` (see README).
export const urls = {
  core: env("EXPO_PUBLIC_CORE_URL", "http://localhost:8001"),
  realtime: env("EXPO_PUBLIC_REALTIME_URL", "http://localhost:8004"),
  worker: env("EXPO_PUBLIC_WORKER_URL", "http://localhost:8006"),
};

const ACCESS = "access_token";
const REFRESH = "refresh_token";

export type User = CoreSchemas["UserResponse"];

interface SessionState {
  status: "loading" | "signed-out" | "signed-in";
  accessToken: string | null;
  user: User | null;
  initialize: () => Promise<void>;
  sendCode: (phone: string, country: "IN" | "US") => Promise<void>;
  verifyCode: (phone: string, code: string, country: "IN" | "US") => Promise<void>;
  refresh: () => Promise<string | null>;
  loadUser: () => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
}

export const useSession = create<SessionState>()((set, get) => ({
  status: "loading",
  accessToken: null,
  user: null,

  initialize: async () => {
    const token = await SecureStore.getItemAsync(ACCESS).catch(() => null);
    if (!token) {
      set({ status: "signed-out" });
      return;
    }
    set({ accessToken: token });
    try {
      await get().loadUser();
      set({ status: "signed-in" });
    } catch {
      await get().signOut();
    }
  },

  sendCode: async (phone, country) => {
    unwrap(await api.core.POST("/api/v1/auth/send-otp", { body: { phone, country } }));
  },

  verifyCode: async (phone, code, country) => {
    const tokens = unwrap(await api.core.POST("/api/v1/auth/phone", { body: { phone, otp: code, country } })) as {
      access_token: string;
      refresh_token: string;
    };
    await SecureStore.setItemAsync(ACCESS, tokens.access_token);
    await SecureStore.setItemAsync(REFRESH, tokens.refresh_token);
    set({ accessToken: tokens.access_token });
    await get().loadUser();
    set({ status: "signed-in" });
  },

  refresh: async () => {
    const refreshToken = await SecureStore.getItemAsync(REFRESH).catch(() => null);
    if (!refreshToken) return null;
    const res = await fetch(`${urls.core}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const tokens = (await res.json()) as { access_token: string; refresh_token: string };
    await SecureStore.setItemAsync(ACCESS, tokens.access_token);
    await SecureStore.setItemAsync(REFRESH, tokens.refresh_token);
    set({ accessToken: tokens.access_token });
    return tokens.access_token;
  },

  loadUser: async () => {
    set({ user: unwrap(await api.core.GET("/api/v1/users/me")) });
  },

  signOut: async () => {
    const token = get().accessToken;
    if (token) await api.core.POST("/api/v1/auth/logout").catch(() => undefined);
    await SecureStore.deleteItemAsync(ACCESS).catch(() => undefined);
    await SecureStore.deleteItemAsync(REFRESH).catch(() => undefined);
    set({ status: "signed-out", accessToken: null, user: null });
  },

  deleteAccount: async () => {
    unwrap(await api.core.DELETE("/api/v1/users/me"));
    await get().signOut();
  },
}));

export const api = createApi({
  coreUrl: urls.core,
  realtimeUrl: urls.realtime,
  workerUrl: urls.worker,
  getAccessToken: () => useSession.getState().accessToken,
  refreshAccessToken: () => useSession.getState().refresh(),
  onSignedOut: () => void useSession.getState().signOut(),
});

/** The realtime WebSocket URL for a path (token as a subprotocol-free query for React Native). */
export function wsUrl(path: string): string {
  const token = useSession.getState().accessToken ?? "";
  return `${urls.realtime.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(token)}`;
}
