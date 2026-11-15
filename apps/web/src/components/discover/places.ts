// Small helpers over the Markets directory (no names here: everything is data).
import type { DirCity, Directory } from "@/lib/server";

export interface FlatCity extends DirCity {
  country: string; // code
  countryName: string;
  region: string; // name
}

export function flatCities(dir: Directory): FlatCity[] {
  return dir.countries.flatMap((k) =>
    k.regions.flatMap((r) => r.cities.map((c) => ({ ...c, country: k.code, countryName: k.name, region: r.name }))),
  );
}

/** Great-circle distance in km. */
export function km(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/** The first live city of a country (directory order), for examples on the landing page. */
export function firstLiveCity(dir: Directory, country: string | null | undefined): FlatCity | null {
  if (!country) return null;
  return flatCities(dir).find((c) => c.country === country && c.status === "live") ?? null;
}

/** "2 countries · 2 cities live · 3 coming soon" (plural rules per language). */
export function totalsLine(t: (k: string, v?: Record<string, string | number>) => string, totals: Directory["totals"]): string {
  return [
    t("cities.totals_countries", { count: totals.countries ?? 0 }),
    t("cities.totals_live", { count: totals.live ?? 0 }),
    t("cities.totals_soon", { count: totals.soon ?? 0 }),
  ].join(" · ");
}
