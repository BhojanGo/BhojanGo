// The signed-in session and the typed API client for the Expo apps (P17).
// Tokens live in SecureStore; the client adds the access token, refreshes it
// once on a 401 (one refresh shared by concurrent requests) and signs out if
// the refresh token is no longer good.
import { ApiError, createApi, newRequestId, unwrap, type CoreSchemas } from "@bhojango/api-client";
import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

import { appEnv } from "./env";
import { getTimeoutMs, timeoutFetch } from "./load";
import { REFRESH_TIMEOUT_MS, singleFlight } from "./refresh";
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

// R19: steps that need the session to still work, run before sign-out ends it (push.ts
// removes this phone's push token). Each is quiet: a failure never stops the sign-out.
const signOutSteps: (() => Promise<void>)[] = [];
export function beforeSignOut(step: () => Promise<void>): void {
  if (!signOutSteps.includes(step)) signOutSteps.push(step);
}

const refreshOnce = singleFlight(async (signal) => {
  const refreshToken = await SecureStore.getItemAsync(REFRESH).catch(() => null);
  if (!refreshToken) return null;
  const id = newRequestId(); // R28: logged by the API under this id, as every app request is
  const started = Date.now();
  const res = await fetch(`${urls.core}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "content-type": "application/json", "X-Request-ID": id },
    body: JSON.stringify({ refresh_token: refreshToken }),
    ...(signal ? { signal } : {}),
  }).catch((e: unknown) => {
    console.info(`[api] ${id} POST /api/v1/auth/refresh ${e instanceof Error ? `${e.name}: ${e.message}` : String(e)} ${Date.now() - started}ms`);
    throw e;
  });
  if (!res.ok) console.info(`[api] ${id} POST /api/v1/auth/refresh ${res.status} ${Date.now() - started}ms`);
  // Our servers down or busy (a deploy's 502, a 429): an error, so the next request tries again.
  // Only the API refusing the refresh token (401/403/422) ends the session (null: sign out).
  if (res.status >= 500 || res.status === 408 || res.status === 429) throw new Error(`The session refresh failed (${res.status})`);
  if (!res.ok) return null;
  const tokens = (await res.json()) as { access_token: string; refresh_token: string };
  await SecureStore.setItemAsync(ACCESS, tokens.access_token);
  await SecureStore.setItemAsync(REFRESH, tokens.refresh_token);
  useSession.setState({ accessToken: tokens.access_token });
  return tokens.access_token;
}, REFRESH_TIMEOUT_MS);

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

  // One refresh at a time: a refresh token works once, and using it twice ends the session
  // (two sockets closing at their token's expiry together would otherwise both refresh).
  // R27: never longer than REFRESH_TIMEOUT_MS (refresh.ts): a hung refresh used to leave every
  // later request waiting on it forever (the kitchen board froze with no error). A timeout is
  // an error, not a sign-out: the next request refreshes again.
  refresh: () => refreshOnce(),

  loadUser: async () => {
    set({ user: unwrap(await api.core.GET("/api/v1/users/me")) });
  },

  signOut: async () => {
    const token = get().accessToken;
    if (token) {
      for (const step of signOutSteps) await step().catch(() => undefined);
      await api.core.POST("/api/v1/auth/logout").catch(() => undefined);
    }
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
  // R28: a failed request goes to the device log (logcat "ReactNativeJS") with its X-Request-ID, the
  // id the API logs it under. Never the body, the token or the query (only the path).
  onFailure: (f) => console.info(`[api] ${f.id} ${f.method} ${f.path} ${f.status ?? f.error} ${f.ms}ms`),
  // R9: a GET that hangs fails after 8 s, so a screen shows "Can't reach BhojanGo" and Retry (load.ts).
  // R23: a throwaway-stack build may ask for longer (getTimeoutMs; never production or QA).
  // Written out in full so Expo inlines it.
  fetch: timeoutFetch(getTimeoutMs(appEnv(), process.env.EXPO_PUBLIC_TEST_GET_TIMEOUT_MS)),
});

/**
 * A live realtime socket that opens again when it closes, until the returned stop function
 * is called. realtime closes a socket when its token expires (4401, R22 S10): the token is
 * refreshed and the socket reopened at once. A refused socket (4004 not yours, 4403 no longer
 * yours, 4429 too many) isn't reopened; other drops retry with a growing wait.
 *
 * R27 `heartbeatMs` (the kitchen socket): send "ping" that often; a socket that hears nothing
 * (no message, no "pong") for 2.5 heartbeats is treated as dead (a half-open connection never
 * fires onclose) and reopened. `onState` hears when the socket opens and closes.
 */
export function liveSocket(path: string, onMessage: (e: { data?: unknown }) => void,
  options: { heartbeatMs?: number; onState?: (open: boolean) => void } = {}): () => void {
  let stopped = false;
  let ws: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let beat: ReturnType<typeof setInterval> | null = null;
  let failures = 0;
  let heard = 0;
  const { heartbeatMs, onState } = options;
  const quiet = () => {
    if (beat) clearInterval(beat);
    beat = null;
  };
  const open = () => {
    if (stopped) return;
    // R27: the token goes in the Authorization header (React Native's WebSocket takes headers), never
    // in the URL, where uvicorn's access log and any proxy would keep it.
    const socket = new WebSocket(wsUrl(path), null, { headers: wsHeaders() });
    ws = socket;
    socket.onopen = () => {
      failures = 0;
      heard = Date.now();
      onState?.(true);
      if (heartbeatMs) {
        quiet();
        beat = setInterval(() => {
          if (Date.now() - heard > heartbeatMs * 2.5) {
            quiet();
            socket.close(); // dead without a close: onclose reopens it
            return;
          }
          try {
            socket.send("ping");
          } catch {
            // closing already
          }
        }, heartbeatMs);
      }
    };
    socket.onmessage = (e) => {
      heard = Date.now();
      onMessage(e);
    };
    socket.onclose = (e) => {
      if (ws !== socket) return; // an older socket closing late
      quiet();
      onState?.(false);
      const code = e.code ?? 0;
      if (stopped || [4004, 4403, 4429].includes(code)) return;
      failures += 1;
      const again = (wait: number) => {
        if (!stopped) retry = setTimeout(open, wait);
      };
      if (code === 4401 || code === 4001) {
        void useSession.getState().refresh().catch(() => null).then((t) => again(t ? 0 : Math.min(30000, 2000 * failures)));
      } else {
        again(Math.min(30000, 2000 * failures));
      }
    };
  };
  open();
  return () => {
    stopped = true;
    quiet();
    if (retry) clearTimeout(retry);
    ws?.close();
  };
}

/** The realtime WebSocket URL for a path. No token in it (R27): liveSocket sends wsHeaders(). */
export function wsUrl(path: string): string {
  return `${urls.realtime.replace(/^http/, "ws")}${path}`;
}

/** The realtime WebSocket's sign-in: the access token as an Authorization header (realtime reads it first). */
export function wsHeaders(): Record<string, string> {
  const token = useSession.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
