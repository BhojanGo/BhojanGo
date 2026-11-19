// The signed-in session and the typed API client for the Expo apps (P17).
// Tokens live in SecureStore; the client adds the access token, refreshes it
// once on a 401 (one refresh shared by concurrent requests) and signs out if
// the refresh token is no longer good.
import { ApiError, createApi, unwrap, type CoreSchemas } from "@bhojango/api-client";
import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

import { FIRST_LOAD_TIMEOUT_MS, timeoutFetch } from "./load";
import { deviceLocale } from "./locale";

const env = (k: string, fallback: string) => (process.env as Record<string, string | undefined>)[k] || fallback;

// The emulator reaches the host's services through `adb reverse` (see README).
export const urls = {
  core: env("EXPO_PUBLIC_CORE_URL", "http://localhost:8001"),
  realtime: env("EXPO_PUBLIC_REALTIME_URL", "http://localhost:8004"),
  worker: env("EXPO_PUBLIC_WORKER_URL", "http://localhost:8006"),
  /** The website (legal pages, the photo library): R19 Account -> Legal in the Kitchen and Delivery apps. */
  web: env("EXPO_PUBLIC_WEB_URL", "http://localhost:3000"),
};

const ACCESS = "access_token";
const REFRESH = "refresh_token";

export type User = CoreSchemas["UserResponse"];

interface SessionState {
  /** "unreachable": signed in on this phone, but the API didn't answer at start (see `failure`). */
  status: "loading" | "signed-out" | "signed-in" | "unreachable";
  /** Why the start-up check got no answer (LoadError words it); null otherwise. */
  failure: unknown;
  accessToken: string | null;
  user: User | null;
  initialize: () => Promise<void>;
  /** country: the Markets country code of the phone number (useCountry). */
  sendCode: (phone: string, country: string) => Promise<void>;
  verifyCode: (phone: string, code: string, country: string) => Promise<void>;
  refresh: () => Promise<string | null>;
  loadUser: () => Promise<void>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
  /** After applying to ride or with a kitchen: the account's new role comes with new tokens. */
  adopt: (tokens: { access_token: string; refresh_token: string }) => Promise<void>;
}

export const useSession = create<SessionState>()((set, get) => ({
  status: "loading",
  failure: null,
  accessToken: null,
  user: null,

  initialize: async () => {
    const token = await SecureStore.getItemAsync(ACCESS).catch(() => null);
    if (!token) {
      set({ status: "signed-out", failure: null });
      return;
    }
    set({ accessToken: token });
    try {
      await get().loadUser();
      set({ status: "signed-in", failure: null });
    } catch (e) {
      // R9: no answer (offline, our servers down, a request that hung): stay signed in and
      // say so (the root layouts show UnreachableScreen; its Retry calls initialize again).
      // Only the API refusing the account signs this phone out.
      if (!(e instanceof ApiError)) {
        set({ status: "unreachable", failure: e });
        return;
      }
      await get().signOut();
    }
  },

  sendCode: async (phone, country) => {
    // The app's language (the person's choice, else the phone's): the code's SMS is written in it
    // when the country offers it (the API checks; i18n.tsx keeps the choice under this key).
    const chosen = await SecureStore.getItemAsync("bg.language").catch(() => null);
    const language = (chosen || deviceLocale() || "").split("-")[0]?.toLowerCase() || undefined;
    unwrap(await api.core.POST("/api/v1/auth/send-otp", { body: { phone, country, language } }));
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

  adopt: async (tokens) => {
    await SecureStore.setItemAsync(ACCESS, tokens.access_token);
    await SecureStore.setItemAsync(REFRESH, tokens.refresh_token);
    set({ accessToken: tokens.access_token });
    await get().loadUser();
    set({ status: "signed-in" });
  },

  deleteAccount: async () => {
    unwrap(await api.core.DELETE("/api/v1/users/me"));
    await get().signOut();
  },
}));

// ── email sign-in (round 8, D5) ──────────────────────────────────────────────
// The API answers sign-up, "email me a code" and "forgot password" the same whether
// or not the email has an account; the screens say no more than that either.

async function appLanguage(): Promise<string | undefined> {
  const chosen = await SecureStore.getItemAsync("bg.language").catch(() => null);
  const lang = (chosen || deviceLocale() || "").split("-")[0]?.toLowerCase();
  return lang && /^[a-z]{2}$/.test(lang) ? lang : undefined;
}

/** An admin account: its second step happens on the admin console, not in the apps. */
export class AdminAccountError extends Error {}

type SignInAnswer = { access_token: string; refresh_token: string } | { mfa_required: true };

async function adoptAnswer(answer: SignInAnswer): Promise<void> {
  if ("mfa_required" in answer && answer.mfa_required) throw new AdminAccountError("admin");
  await useSession.getState().adopt(answer as { access_token: string; refresh_token: string });
}

export const emailAuth = {
  signIn: async (email: string, password: string) =>
    adoptAnswer(unwrap(await api.core.POST("/api/v1/auth/login", { body: { email, password } })) as SignInAnswer),
  signUp: async (email: string, password: string, country: string) => {
    unwrap(await api.core.POST("/api/v1/auth/email/sign-up", { body: { email, password, country, language: await appLanguage() } }));
  },
  sendCode: async (email: string) => {
    unwrap(await api.core.POST("/api/v1/auth/email/code", { body: { email, language: await appLanguage() } }));
  },
  verify: async (email: string, code: string) =>
    adoptAnswer(unwrap(await api.core.POST("/api/v1/auth/email/verify", { body: { email, code } })) as SignInAnswer),
  forgot: async (email: string) => {
    unwrap(await api.core.POST("/api/v1/auth/password/forgot", { body: { email, language: await appLanguage() } }));
  },
};

export const api = createApi({
  coreUrl: urls.core,
  realtimeUrl: urls.realtime,
  workerUrl: urls.worker,
  getAccessToken: () => useSession.getState().accessToken,
  refreshAccessToken: () => useSession.getState().refresh(),
  onSignedOut: () => void useSession.getState().signOut(),
  // R9: a GET that hangs fails after 8 s, so a screen shows "Can't reach BhojanGo" and Retry (load.ts).
  fetch: timeoutFetch(FIRST_LOAD_TIMEOUT_MS),
});

/** The realtime WebSocket URL for a path (token as a subprotocol-free query for React Native). */
export function wsUrl(path: string): string {
  const token = useSession.getState().accessToken ?? "";
  return `${urls.realtime.replace(/^http/, "ws")}${path}?token=${encodeURIComponent(token)}`;
}
