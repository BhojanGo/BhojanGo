import axios, { AxiosRequestConfig } from "axios";

let accessToken: string | null = null;
let refreshToken: string | null = null;

let onTokensRefreshed: ((access: string, refresh: string | null) => void) | null = null;
let onLogout: (() => void) | null = null;

export function setAdminTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  refreshToken = refresh;
}

/** Lets the auth store persist rotated tokens / react to forced logout without a circular import. */
export function registerAuthHandlers(handlers: {
  onTokensRefreshed: (access: string, refresh: string | null) => void;
  onLogout: () => void;
}) {
  onTokensRefreshed = handlers.onTokensRefreshed;
  onLogout = handlers.onLogout;
}

export const adminApi = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

adminApi.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post(
      "/api/user/auth/refresh",
      { refresh_token: refreshToken },
      { headers: { "Content-Type": "application/json" } }
    );
    accessToken = data.access_token;
    if (data.refresh_token) refreshToken = data.refresh_token;
    onTokensRefreshed?.(accessToken as string, refreshToken);
    return accessToken;
  } catch {
    return null;
  }
}

adminApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;

    // On 401, try a single refresh + retry before giving up.
    if (error.response?.status === 401 && original && !original._retry && refreshToken) {
      original._retry = true;
      if (!refreshing) refreshing = refreshAccessToken();
      const newToken = await refreshing;
      refreshing = null;
      if (newToken) {
        original.headers = { ...(original.headers ?? {}), Authorization: `Bearer ${newToken}` };
        return adminApi(original);
      }
    }

    if (error.response?.status === 401) {
      onLogout?.();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
