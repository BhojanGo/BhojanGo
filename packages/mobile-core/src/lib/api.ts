import axios from "axios";
import * as SecureStore from "expo-secure-store";

// Fail loud in release builds if the API URL wasn't baked in, instead of silently
// pointing every request at localhost (which never resolves on a real device).
const BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? (__DEV__ ? "http://localhost:8888/api" : "");
if (!BASE_URL) {
  throw new Error("EXPO_PUBLIC_API_URL must be set for production builds");
}

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 15000,
});

api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = await SecureStore.getItemAsync("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");

        const { data } = await axios.post(`${BASE_URL}/user/auth/refresh`, {
          refresh_token: refreshToken,
        });

        await SecureStore.setItemAsync("access_token", data.access_token);
        await SecureStore.setItemAsync("refresh_token", data.refresh_token);

        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        await SecureStore.deleteItemAsync("access_token");
        await SecureStore.deleteItemAsync("refresh_token");
        // Navigation to login handled by auth store listener
      }
    }
    return Promise.reject(error);
  }
);
