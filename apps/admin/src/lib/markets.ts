/**
 * Markets API (core_api /api/v1/markets) and the admin scope helpers.
 * Scopes are market codes: "*", "IN", "IN-TG", "IN-TG-HYD" (backend/shared/authz.py).
 */
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "@/lib/api";

export type MarketStatus = "draft" | "beta" | "live" | "paused";

export interface Country {
  id: string;
  code: string;
  name: string;
  currency: string;
  locales: string[];
  timezone: string;
  distance_unit: string;
  phone_code: string;
  payment_providers: string[];
  tax_regime: string;
  settings: Record<string, unknown>;
  status: MarketStatus;
}

export interface Region {
  id: string;
  code: string;
  name: string;
  timezone: string | null;
  settings: Record<string, unknown>;
  status: MarketStatus;
}

export interface ServiceHours {
  open: string;
  close: string;
}

export interface City {
  id: string;
  code: string;
  name: string;
  timezone: string | null;
  service_hours: ServiceHours | null;
  center_lat: number;
  center_lng: number;
  settings: Record<string, unknown>;
  status: MarketStatus;
}

export interface CitySummary extends City {
  zone_count: number;
  live_zone_count: number;
  launch_checklist: Record<string, boolean>;
}

export interface RegionSummary extends Region {
  cities: CitySummary[];
}

export interface CountrySummary extends Country {
  regions: RegionSummary[];
}

export interface GeoPolygon {
  type: "Polygon";
  coordinates: [number, number][][]; // [[ [lng, lat], ... ]]
}

export interface Zone {
  id: string;
  city_code: string;
  name: string;
  polygon: GeoPolygon;
  area_km2: number;
  min_order: string | null;
  color: string;
  status: MarketStatus;
  pause_reason: string | null;
  paused_until: string | null;
}

export interface SettingValue {
  key: string;
  value: unknown;
  source: string;
  source_level: "country" | "region" | "city";
}

export interface CityDetail extends CitySummary {
  country: Country;
  region: Region;
  zones: Zone[];
  effective_settings: SettingValue[];
}

export interface AdminMe {
  user_id: string;
  email: string | null;
  full_name: string;
  assignments: { id: string; role: string; scope: string }[];
  permissions: Record<string, string[]>;
}

/** True when `scope` is `target` or contains it ("IN" covers "IN-TG-HYD"). */
export function covers(scope: string, target: string): boolean {
  if (scope === "*") return true;
  if (target === "*") return false;
  return target === scope || target.startsWith(scope + "-");
}

export function can(me: AdminMe | undefined, permission: string, target: string): boolean {
  return (me?.permissions[permission] ?? []).some((s) => covers(s, target));
}

export const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super admin",
  country_manager: "Country manager",
  city_ops: "City ops",
  support_agent: "Support",
  finance: "Finance",
  viewer: "Viewer",
};

export const CHECKLIST_LABELS: Record<string, string> = {
  country_open: "Country open",
  state_open: "State open",
  zones_drawn: "Zones drawn",
  zone_open: "A zone is open",
  service_hours_set: "Service hours set",
};

export function useAdminMe() {
  return useQuery({
    queryKey: ["admin-me"],
    queryFn: async () => (await adminApi.get<AdminMe>("/user/admin/me")).data,
    staleTime: 60_000,
  });
}

export function useMarkets() {
  return useQuery({
    queryKey: ["markets"],
    queryFn: async () => (await adminApi.get<CountrySummary[]>("/user/markets")).data,
  });
}

export function useCity(code: string) {
  return useQuery({
    queryKey: ["markets", "city", code],
    queryFn: async () => (await adminApi.get<CityDetail>(`/user/markets/cities/${code}`)).data,
    enabled: Boolean(code),
  });
}

export const marketsApi = {
  updateCity: (code: string, body: Partial<City> & { status?: MarketStatus }) =>
    adminApi.patch<City>(`/user/markets/cities/${code}`, body),
  createZone: (city: string, body: { name: string; polygon: GeoPolygon; min_order?: string | null; color?: string; status?: MarketStatus }) =>
    adminApi.post<Zone>(`/user/markets/cities/${city}/zones`, body),
  updateZone: (id: string, body: Partial<Pick<Zone, "name" | "polygon" | "min_order" | "color">> & { status?: MarketStatus }) =>
    adminApi.patch<Zone>(`/user/markets/zones/${id}`, body),
  pauseZone: (id: string, reason: string, until?: string | null) =>
    adminApi.post<Zone>(`/user/markets/zones/${id}/pause`, { reason, until: until || null }),
  resumeZone: (id: string) => adminApi.post<Zone>(`/user/markets/zones/${id}/resume`),
};

/** The API's error message, in plain words. */
export function apiError(e: unknown): string {
  const err = e as { response?: { data?: { detail?: unknown } } };
  const d = err.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && "message" in d) return String((d as { message: string }).message);
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  return "Something went wrong. Try again.";
}

export function moneySymbol(currency: string): string {
  return currency === "INR" ? "₹" : currency === "USD" ? "$" : currency + " ";
}

export function tzLabel(tz: string): string {
  return tz;
}
