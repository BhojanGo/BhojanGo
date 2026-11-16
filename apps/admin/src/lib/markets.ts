/**
 * Markets API (core_api /api/v1/markets) and the admin scope helpers.
 * Scopes are market codes: "*", "IN", "IN-TG", "IN-TG-HYD" (backend/shared/authz.py).
 */
import { useQuery } from "@tanstack/react-query";

import { adminApi } from "@/lib/api";

export type MarketStatus = "draft" | "soon" | "beta" | "live" | "paused";

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
  payout_provider: PayoutProviderName;
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
  /** "Notify me" sign-ups for this city (website). */
  waitlist: number;
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
  pricing_set: "Delivery fee set",
  payouts_set: "Payout provider set",
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

export interface Demand {
  cities: { city_code: string; city_name: string; country: string; status: MarketStatus; signups: number; with_consent: number; last_at: string | null }[];
  suggested: { text: string; signups: number; last_at: string | null }[];
}

export function useDemand() {
  return useQuery({
    queryKey: ["markets", "demand"],
    queryFn: async () => (await adminApi.get<Demand>("/user/markets/waitlist/demand")).data,
  });
}

/** Language names in their own script, for the country's language list. */
export const LOCALE_NAMES: Record<string, string> = {
  "en-IN": "English",
  "en-US": "English",
  "hi-IN": "हिन्दी",
  "te-IN": "తెలుగు",
  "ta-IN": "தமிழ்",
  "kn-IN": "ಕನ್ನಡ",
  "mr-IN": "मराठी",
  "bn-IN": "বাংলা",
  "es-US": "Español",
};

/** What a new country can choose (backend CountryCreate): the tax regimes and
 * payment gateways the platform already integrates. A country with another tax
 * system picks the closest one; a new regime is a code change. */
export const TAX_REGIMES = [
  { value: "gst", label: "GST (tax invoice)" },
  { value: "us_sales_tax", label: "Sales tax (Stripe Tax, receipt)" },
] as const;
export const PAYMENT_PROVIDERS = ["razorpay", "stripe"] as const;

/** Who pays a country's kitchens and riders (backend countries.payout_provider). The
 * fake moves no money: the API refuses it in production. None: the country can't open. */
export type PayoutProviderName = "stripe_connect" | "razorpay_route" | "fake" | "none";
export const PAYOUT_PROVIDERS: { value: PayoutProviderName; label: string }[] = [
  { value: "stripe_connect", label: "Stripe Connect" },
  { value: "razorpay_route", label: "Razorpay Route" },
  { value: "fake", label: "Fake (test stacks only, never production)" },
  { value: "none", label: "None yet (the country can't open)" },
];
export function payoutLabel(p: string): string {
  return PAYOUT_PROVIDERS.find((x) => x.value === p)?.label ?? p;
}

export interface CountryCreate {
  code: string;
  name: string;
  currency: string;
  locales: string[];
  timezone: string;
  distance_unit: "km" | "mi";
  phone_code: string;
  payment_providers: string[];
  tax_regime: string;
  payout_provider: PayoutProviderName;
}

export interface CountryUpdate {
  name?: string;
  status?: MarketStatus;
  payout_provider?: PayoutProviderName;
  /** A value sets an override, null removes it (back to the default). */
  settings?: Record<string, unknown>;
}

export interface CountryUpdate {
  name?: string;
  status?: MarketStatus;
  /** A value sets an override, null removes it (back to the default). */
  settings?: Record<string, unknown>;
}

export const marketsApi = {
  updateCountry: (code: string, body: CountryUpdate) => adminApi.patch<Country>(`/user/markets/countries/${code}`, body),
  createCountry: (body: CountryCreate) => adminApi.post<Country>("/user/markets/countries", body),
  createRegion: (country: string, body: { code: string; name: string; timezone?: string | null }) =>
    adminApi.post<Region>(`/user/markets/countries/${country}/regions`, body),
  updateRegion: (code: string, body: { name?: string; status?: MarketStatus }) =>
    adminApi.patch<Region>(`/user/markets/regions/${code}`, body),
  createCity: (region: string, body: { code: string; name: string; center_lat: number; center_lng: number; timezone?: string | null }) =>
    adminApi.post<City>(`/user/markets/regions/${region}/cities`, body),
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

/**
 * The city a country-level page opens on (e.g. the price simulator): the first live
 * or beta city of `country` (or of any country), else its first city. From Markets,
 * never a hard-coded code.
 */
export function firstCity(markets: CountrySummary[] | undefined, country?: string | null): string | null {
  const cities = (markets ?? []).filter((c) => !country || country === "ALL" || c.code === country)
    .flatMap((c) => c.regions.flatMap((r) => r.cities));
  return (cities.find((c) => c.status === "live" || c.status === "beta") ?? cities[0])?.code ?? null;
}
