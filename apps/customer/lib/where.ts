// Where the food goes: the customer's saved address, or where the phone is.
// Located against the markets API to know the city, zone and whether we deliver.
import { api, hourIn, unwrap, type CoreSchemas } from "@bhojango/mobile-core";
import * as Location from "expo-location";
import { create } from "zustand";

import { partOfDayAt, type PartOfDay } from "./contract";

export type { PartOfDay };

export type Locate = CoreSchemas["LocateResult"];

export interface DropPoint {
  label: string; // "Home · <area>" for a saved address; the area (or "") for where the phone is
  addressId: string | null;
  lat: number;
  lng: number;
  street: string;
  city: string;
  state: string;
  zip: string;
  country: string;
  /** Picked as a city on "Change city" (a point inside one of its areas): fine for browsing, not a door to deliver to. */
  browse?: boolean;
}

interface WhereState {
  point: DropPoint | null;
  market: Locate | null;
  status: "idle" | "locating" | "ready" | "failed";
  locate: () => Promise<void>;
  setPoint: (p: DropPoint) => Promise<void>;
  goHere: () => Promise<void>;
  /** "Change city": browse a live city (a point inside one of its open areas, GET /markets/areas). */
  pickCity: (city: { code: string; name: string }, country: string) => Promise<void>;
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
    label: geo?.city || geo?.district || "", addressId: null,
    lat: pos.coords.latitude, lng: pos.coords.longitude, street: geo?.street || geo?.name || "Current location", // sent with the order when the phone has no street
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

  pickCity: async (city, country) => {
    const hits = unwrap(await api.core.GET("/api/v1/markets/areas", { params: { query: { q: city.name, country, limit: 20 } } }));
    const hit = hits.find((a) => a.served && a.city_code === city.code);
    if (!hit) throw new Error("city");
    await get().setPoint({
      label: hit.city_name, addressId: null, lat: hit.lat, lng: hit.lng, street: "", city: hit.city_name, state: "", zip: "",
      country: hit.country, browse: true,
    });
  },

  saved: async () => {
    const all = unwrap(await api.core.GET("/api/v1/me/addresses")) as CoreSchemas["AddressResponse"][];
    return all.filter((a) => a.lat != null && a.lng != null).map(fromAddress);
  },
}));

/**
 * The part of the day at the delivery address, for the greeting: in its city's time
 * zone (GET /markets/locate), else its country's (Markets), never the phone's while
 * either is known (see greetingZone).
 */
export function partOfDay(timeZone?: string | null, now = new Date()): PartOfDay {
  return partOfDayAt(hourIn(timeZone, now));
}
