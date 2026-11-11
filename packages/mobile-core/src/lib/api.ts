import axios, { type AxiosInstance } from "axios";
import * as SecureStore from "expo-secure-store";

/**
 * The apps call the backend directly (no gateway, ADR-008):
 *   EXPO_PUBLIC_API_URL       core_api,  e.g. http://192.168.1.20:8001/api/v1
 *   EXPO_PUBLIC_REALTIME_URL  realtime,  e.g. http://192.168.1.20:8004/api/v1
 * On a phone or emulator, "localhost" is the device itself: use your computer's
 * LAN IP (or 10.0.2.2 on the Android emulator). See apps/<app>/.env.example.
 */
function baseUrl(value: string | undefined, devDefault: string, name: string): string {
  // Fail loud in release builds if the URL wasn't baked in, instead of silently
  // pointing every request at localhost (which never resolves on a real device).
  const url = value ?? (__DEV__ ? devDefault : "");
  if (!url) throw new Error(`${name} must be set for production builds`);
  return url.replace(/\/+$/, "");
}

const CORE_API_URL = baseUrl(process.env.EXPO_PUBLIC_API_URL, "http://localhost:8001/api/v1", "EXPO_PUBLIC_API_URL");
const REALTIME_URL = baseUrl(process.env.EXPO_PUBLIC_REALTIME_URL, "http://localhost:8004/api/v1", "EXPO_PUBLIC_REALTIME_URL");

function createClient(baseURL: string): AxiosInstance {
  const client = axios.create({
    baseURL,
    headers: { "Content-Type": "application/json" },
    timeout: 15000,
  });

  client.interceptors.request.use(async (config) => {
    const token = await SecureStore.getItemAsync("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          const refreshToken = await SecureStore.getItemAsync("refresh_token");
          if (!refreshToken) throw new Error("No refresh token");

          // Tokens are always refreshed by core_api (identity).
          const { data } = await axios.post(`${CORE_API_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          await SecureStore.setItemAsync("access_token", data.access_token);
          await SecureStore.setItemAsync("refresh_token", data.refresh_token);

          originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
          return client(originalRequest);
        } catch {
          await SecureStore.deleteItemAsync("access_token");
          await SecureStore.deleteItemAsync("refresh_token");
          // Navigation to login handled by auth store listener
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
}

/** core_api: identity, catalog, orders, payments (paths start at /api/v1). */
export const api = createClient(CORE_API_URL);

/** realtime: rider location, shifts, earnings, ETA (paths start at /api/v1). */
export const realtimeApi = createClient(REALTIME_URL);
