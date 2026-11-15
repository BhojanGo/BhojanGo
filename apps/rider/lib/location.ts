// GPS while online. Android runs a foreground service ("You're online"
// notification), so updates keep coming with the screen off or another app on
// top; each fix goes to realtime, which offers nearby orders and shows the
// customer where their rider is. Stops when the rider goes offline.
//
// Only the phone the rider went online on shares its GPS ("tracking here",
// kept in SecureStore). The same rider signed in on a second phone, or the demo
// rider on QA whose position the demo simulator sends, sees the server's state
// without this phone's GPS fighting the other source; "Use this phone's
// location" on the Drive tab takes over deliberately.
import { api, useSession, urls } from "@bhojango/mobile-core";
import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import * as TaskManager from "expo-task-manager";

export const LOCATION_TASK = "bhojango-rider-location";
const TRACKING_HERE = "rider_tracking_here";

let watcher: Location.LocationSubscription | null = null;

/** The words on Android's "you're online" notification, in the rider's language (set by the Drive tab). */
let notice = { title: "BhojanGo", body: "" };
export function setTrackingNotice(title: string, body: string) {
  notice = { title, body };
}

/** Did the rider go online on this phone (so this phone shares its GPS)? */
export async function trackingHere(): Promise<boolean> {
  return (await SecureStore.getItemAsync(TRACKING_HERE).catch(() => null)) === "1";
}

async function send(lat: number, lng: number, extra: { heading?: number | null; speed?: number | null; accuracy?: number | null }) {
  // The task can run before the session store is hydrated (app in the background).
  const token = useSession.getState().accessToken ?? (await SecureStore.getItemAsync("access_token").catch(() => null));
  if (!token) return;
  await fetch(`${urls.realtime}/api/v1/delivery/driver/location`, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${token}` },
    body: JSON.stringify({
      lat, lng,
      heading: extra.heading != null && extra.heading >= 0 ? extra.heading : undefined,
      speed: extra.speed != null && extra.speed >= 0 ? extra.speed : undefined,
      accuracy: extra.accuracy ?? undefined,
    }),
  }).catch(() => undefined);
}

TaskManager.defineTask<{ locations: Location.LocationObject[] }>(LOCATION_TASK, async ({ data, error }) => {
  if (error || !data?.locations?.length) return;
  const l = data.locations.at(-1);
  if (!l) return;
  await send(l.coords.latitude, l.coords.longitude, l.coords);
});

/** Location while the app is open (asked when going online). */
export async function askForLocation(): Promise<boolean> {
  const fg = await Location.requestForegroundPermissionsAsync();
  return fg.status === "granted";
}

export async function hasBackgroundLocation(): Promise<boolean> {
  return (await Location.getBackgroundPermissionsAsync().catch(() => null))?.status === "granted";
}

/** "Allow all the time", asked separately (Android only shows it in Settings), then
 * switch from following in the app to the foreground service. */
export async function askForBackgroundLocation(): Promise<boolean> {
  const bg = await Location.requestBackgroundPermissionsAsync().catch(() => null);
  if (bg?.status !== "granted") return false;
  watcher?.remove();
  watcher = null;
  await startTracking();
  return true;
}

export async function currentFix(): Promise<{ lat: number; lng: number } | null> {
  const pos = (await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null))
    ?? (await Location.getLastKnownPositionAsync().catch(() => null))
    ?? (await firstFix(10000));
  return pos ? { lat: pos.coords.latitude, lng: pos.coords.longitude } : null;
}

/** Right after a cold start the GPS may not have a fix yet: wait briefly for the first one. */
function firstFix(ms: number): Promise<Location.LocationObject | null> {
  return new Promise((resolve) => {
    let sub: Location.LocationSubscription | null = null;
    const done = (v: Location.LocationObject | null) => {
      clearTimeout(timer);
      sub?.remove();
      resolve(v);
    };
    const timer = setTimeout(() => done(null), ms);
    Location.watchPositionAsync({ accuracy: Location.Accuracy.Balanced }, (l) => done(l))
      .then((s) => (sub = s))
      .catch(() => done(null));
  });
}

export async function startTracking(): Promise<void> {
  await SecureStore.setItemAsync(TRACKING_HERE, "1").catch(() => undefined);
  const bg = await Location.getBackgroundPermissionsAsync().catch(() => null);
  if (bg?.status === "granted") {
    if (!(await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK).catch(() => false))) {
      await Location.startLocationUpdatesAsync(LOCATION_TASK, {
        accuracy: Location.Accuracy.High,
        timeInterval: 5000,
        distanceInterval: 10,
        pausesUpdatesAutomatically: false,
        showsBackgroundLocationIndicator: true,
        foregroundService: {
          notificationTitle: notice.title,
          notificationBody: notice.body,
          notificationColor: "#E8A93C",
          killServiceOnDestroy: false,
        },
      });
    }
    return;
  }
  // Only "while using the app": follow the position while the app is open.
  if (!watcher) {
    watcher = await Location.watchPositionAsync({ accuracy: Location.Accuracy.High, timeInterval: 5000, distanceInterval: 10 },
      (l) => void send(l.coords.latitude, l.coords.longitude, l.coords));
  }
}

export async function stopTracking(): Promise<void> {
  await SecureStore.deleteItemAsync(TRACKING_HERE).catch(() => undefined);
  watcher?.remove();
  watcher = null;
  if (await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK).catch(() => false)) {
    await Location.stopLocationUpdatesAsync(LOCATION_TASK);
  }
}

/** One fix now (going online, or a manual refresh). */
export async function sendNow(): Promise<{ lat: number; lng: number } | null> {
  const fix = await currentFix();
  if (fix) await send(fix.lat, fix.lng, {});
  return fix;
}

export { api };
