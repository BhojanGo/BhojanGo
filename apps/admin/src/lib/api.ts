import axios, { AxiosRequestConfig } from "axios";

import { setApiReachable, unreachable } from "@/lib/connection";

// R22 security review (S8): the console's session is in httpOnly cookies (bg_admin_at,
// bg_admin_rt) that core_api sets through the console's own /api rewrites, so they belong to
// the console's host and no script on the page can read them. Every call says it's the
// console (X-Session: admin); core_api then reads the cookie, and checks that a call that
// changes something came from one of our own pages (Origin), against CSRF.
// See backend/shared/session.py.
export const SESSION_HEADERS = { "X-Session": "admin" } as const;

let onLogout: (() => void) | null = null;

/** Lets the auth store react to a forced sign-out without a circular import. */
export function registerAuthHandlers(handlers: { onLogout: () => void }) {
  onLogout = handlers.onLogout;
}

export const adminApi = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json", ...SESSION_HEADERS },
  withCredentials: true,
  timeout: 30000,
});

let refreshing: Promise<boolean> | null = null;

/** Renew the session's cookies; false when it has ended. */
async function refreshSession(): Promise<boolean> {
  try {
    await axios.post("/api/user/auth/refresh", undefined, { headers: { ...SESSION_HEADERS }, withCredentials: true });
    return true;
  } catch {
    return false;
  }
}

/** Ends the session on the server and clears its cookies. */
export async function endSession(): Promise<void> {
  const out = () => axios.post("/api/user/auth/logout", undefined, { headers: { ...SESSION_HEADERS }, withCredentials: true });
  try {
    await out();
  } catch (err) {
    // The access cookie ran out: renew it once so the server can end the whole session.
    if ((err as { response?: { status?: number } }).response?.status === 401 && (await refreshSession())) await out().catch(() => undefined);
  }
}

adminApi.interceptors.response.use(
  (response) => {
    setApiReachable(true);
    return response;
  },
  async (error) => {
    setApiReachable(!unreachable(error)); // R42: the console's "can't reach BhojanGo" banner
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
    const signingIn = (original?.url ?? "").startsWith("/user/auth/");

    // On 401, try a single refresh + retry before giving up (not for the sign-in steps themselves).
    if (error.response?.status === 401 && original && !original._retry && !signingIn) {
      original._retry = true;
      if (!refreshing) refreshing = refreshSession().finally(() => { refreshing = null; });
      if (await refreshing) return adminApi(original);
    }

    if (error.response?.status === 401 && !signingIn) {
      onLogout?.();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
