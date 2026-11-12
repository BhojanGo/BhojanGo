// Where the food goes: the customer's saved address, or where the phone is.
// Located against the markets API to know the city, zone and whether we deliver.
import { api, unwrap, type CoreSchemas } from "@bhojango/mobile-core";
import * as Location from "expo-location";
import { create } from "zustand";

export type Locate = CoreSchemas["LocateResult"];

export interface DropPoint {
  label: string; // "Home · Madhapur"
  addressId: string | null;
  lat: number;
  lng: number;
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
}

interface WhereState {
  point: DropPoint | null;
  market: Locate | null;
  status: "idle" | "locating" | "ready" | "failed";
  locate: () => Promise<void>;
  setPoint: (p: DropPoint) => Promise<void>;
  goHere: () => Promise<void>;
  saved: () => Promise<DropPoint[]>;
}

function fromAddress(a: CoreSchemas["AddressResponse"]): DropPoint {
  return {
    label: `${a.label} · ${a.street.split(",").slice(-1)[0]?.trim() || a.city}`, addressId: a.id,
    lat: a.lat as number, lng: a.lng as number, street: a.street, city: a.city, state: a.state, zip: a.postal_code, country: a.country,
  };
}

async function here(): Promise<DropPoint> {
  const perm = await Location.requestForegroundPermissionsAsync();
  if (perm.status !== "granted") throw new Error("location");
  const pos = await Location.getCurrentPositionAsync({});
  const geo = (await Location.reverseGeocodeAsync(pos.coords).catch(() => []))[0];
  return {
    label: `Here · ${geo?.city || geo?.district || "current location"}`, addressId: null,
    lat: pos.coords.latitude, lng: pos.coords.longitude, street: geo?.street || geo?.name || "Current location",
    city: geo?.city || "", state: geo?.region || "", zip: geo?.postalCode || "", country: geo?.isoCountryCode || "",
  };
}

async function market(lat: number, lng: number): Promise<Locate> {
  return unwrap(await api.core.GET("/api/v1/markets/locate", { params: { query: { lat, lng } } }));
}

export const useWhere = create<WhereState>()((set, get) => ({
  point: null,
  market: null,
  status: "idle",

  locate: async () => {
    if (get().status === "locating") return;
    set({ status: "locating" });
    try {
      // A saved address first (the one with a map pin), else the phone's location.
      const saved = unwrap(await api.core.GET("/api/v1/me/addresses")) as CoreSchemas["AddressResponse"][];
      const withPin = saved.find((a) => a.lat != null && a.lng != null);
      const point = withPin ? fromAddress(withPin) : await here();
      set({ point, market: await market(point.lat, point.lng), status: "ready" });
    } catch {
      set({ status: "failed" });
    }
  },

  setPoint: async (p) => {
    set({ point: p, market: await market(p.lat, p.lng), status: "ready" });
  },

  goHere: async () => {
    await get().setPoint(await here());
  },

  saved: async () => {
    const all = unwrap(await api.core.GET("/api/v1/me/addresses")) as CoreSchemas["AddressResponse"][];
    return all.filter((a) => a.lat != null && a.lng != null).map(fromAddress);
  },
}));

/** "Good morning", "Good afternoon" or "Good evening" for the local time. */
/** The hour in the delivery city (its own time zone), else the phone's. */
export function localHour(timeZone?: string | null, now = new Date()): number {
  if (timeZone) {
    try {
      return Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone }).format(now)) % 24;
    } catch {
      // no time-zone data on this phone: fall back to its clock
    }
  }
  return now.getHours();
}

/** "Good morning" … "Late night" and what to ask, by the city's local time. */
export function greeting(timeZone?: string | null, now = new Date()): { hello: string; ask: string } {
  const h = localHour(timeZone, now);
  if (h >= 5 && h < 12) return { hello: "Good morning", ask: "What's for breakfast?" };
  if (h >= 12 && h < 17) return { hello: "Good afternoon", ask: "What's for lunch?" };
  if (h >= 17 && h < 22) return { hello: "Good evening", ask: "What's for dinner?" };
  return { hello: "Late night", ask: "Something to keep you going?" };
}
