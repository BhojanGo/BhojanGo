// R19: push notifications for every app. After sign-in the app asks once for permission
// (a moment after the first screen, never during sign-in itself), gets this phone's Expo
// push token and registers it with core_api (POST /api/v1/me/devices); the worker then
// pushes order updates to it. Sign-out removes it first, while the session still works.
// Everything here is quiet: denied, no project id yet (a placeholder in config/store.json),
// an emulator without Play services, no network: no token, no error shown.
//
// The app hands in expo-notifications and its EAS project id (each app already depends on
// expo-notifications and expo-constants; this package doesn't, so it needs nothing new).
import * as SecureStore from "expo-secure-store";
import { useEffect } from "react";
import { Platform } from "react-native";

import { easProjectId, pushPlatform } from "./push-config";
import { api, beforeSignOut, useSession } from "./session";

/** The parts of expo-notifications this uses (pass the module: `import * as Notifications`). */
export interface PushModule {
  getPermissionsAsync(): Promise<{ status: string }>;
  requestPermissionsAsync(): Promise<{ status: string }>;
  getExpoPushTokenAsync(options: { projectId: string }): Promise<{ data: string }>;
  setNotificationChannelAsync(id: string, channel: { name: string; importance: number; sound?: string | null }): Promise<unknown>;
  AndroidImportance: { HIGH: number; MAX?: number };
}

/**
 * An extra Android notification channel an app pushes to (R27: the Kitchen app's "new_orders",
 * ringing with its own sound). `sound` is a file the app bundles (expo-notifications plugin
 * "sounds"); `max`: the loudest importance (heads-up). A channel's sound is fixed once made.
 */
export interface PushChannel {
  id: string;
  name: string;
  sound?: string;
  max?: boolean;
}

const TOKEN = "bg.push_token"; // the token this phone registered (to remove on sign-out)
const ASKED = "bg.push_asked"; // asked once on this install: a "no" is never asked again by us
const AFTER_SIGN_IN_MS = 2500;
const SIGN_OUT_WAIT_MS = 3000;

/**
 * Register this phone for push. `projectId`: the app config's extra.eas.projectId (a
 * placeholder skips quietly). `ask`: may show the system permission prompt (once per install).
 * Returns the token, or null when there is none.
 */
export async function registerPush(n: PushModule, projectId: unknown,
  { ask = true, channels = [] }: { ask?: boolean; channels?: PushChannel[] } = {}): Promise<string | null> {
  try {
    const platform = pushPlatform(Platform.OS);
    const id = easProjectId(projectId);
    if (!platform || !id) return null;
    if (platform === "android") {
      // The worker sends with channelId "orders" (shared/providers/push.py): high importance, sound.
      await n.setNotificationChannelAsync("orders", { name: "BhojanGo", importance: n.AndroidImportance.HIGH, sound: "default" });
      for (const c of channels) {
        await n.setNotificationChannelAsync(c.id, {
          name: c.name, importance: (c.max ? n.AndroidImportance.MAX : undefined) ?? n.AndroidImportance.HIGH, sound: c.sound ?? "default",
        });
      }
    }
    let { status } = await n.getPermissionsAsync();
    if (status !== "granted") {
      const asked = await SecureStore.getItemAsync(ASKED).catch(() => null);
      if (!ask || asked) return null;
      await SecureStore.setItemAsync(ASKED, "1").catch(() => undefined);
      status = (await n.requestPermissionsAsync()).status;
      if (status !== "granted") return null;
    }
    const token = (await n.getExpoPushTokenAsync({ projectId: id })).data;
    const r = await api.core.POST("/api/v1/me/devices", { body: { token, platform, provider: "expo" } });
    if (r.error) return null;
    await SecureStore.setItemAsync(TOKEN, token).catch(() => undefined);
    return token;
  } catch {
    return null;
  }
}

/** Stop pushes to this phone for the signed-in person (runs before sign-out ends the session). Quiet. */
export async function unregisterPush(): Promise<void> {
  const token = await SecureStore.getItemAsync(TOKEN).catch(() => null);
  if (!token) return;
  await SecureStore.deleteItemAsync(TOKEN).catch(() => undefined); // first: a refused call can't loop back here
  const removed = api.core.DELETE("/api/v1/me/devices", { params: { query: { token } } }).catch(() => undefined);
  await Promise.race([removed, new Promise<void>((r) => setTimeout(() => r(), SIGN_OUT_WAIT_MS))]); // sign-out never waits long
}

beforeSignOut(unregisterPush);

/**
 * In each app's root layout: registers a moment after sign-in (and on each start, signed in).
 * `usePushRegistration(Notifications, Constants.expoConfig?.extra?.eas?.projectId)`.
 */
export function usePushRegistration(n: PushModule, projectId: unknown, channels?: PushChannel[]): void {
  const status = useSession((s) => s.status);
  const userId = useSession((s) => s.user?.id ?? null);
  const key = JSON.stringify(channels ?? []);
  useEffect(() => {
    if (status !== "signed-in" || !userId) return;
    const timer = setTimeout(() => void registerPush(n, projectId, { channels: JSON.parse(key) as PushChannel[] }), AFTER_SIGN_IN_MS);
    return () => clearTimeout(timer);
  }, [status, userId, n, projectId, key]);
}
