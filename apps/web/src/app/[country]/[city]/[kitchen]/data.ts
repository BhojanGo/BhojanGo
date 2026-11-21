// Kitchen page helpers (server): the path slug, today's availability, the
// distance from the visitor's address. Everything here is computed from data.

const CORE = process.env.CORE_API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_CORE_URL ?? "http://localhost:8001";

/** "Some City" -> "some-city": lower-case, non-alphanumerics -> "-" (the same rule as the API's city slugs). */
export function slugify(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export interface Availability {
  open_now: boolean;
  reason?: string | null;
  next_open_at?: string | null;
  timezone?: string | null;
  opens_at?: string | null;
  closes_at?: string | null;
  closed_for_now?: boolean; // R17: paused by an admin
  not_taking_orders?: boolean; // R27: open by its hours, but its tablet isn't connected
  back_at?: string | null;
  /** R27: why it's closed (closed, closed_today, outside_delivery_hours, paused, ...); next_open_at is then
   *  when orders can next come in (the kitchen's hours and the city's delivery hours both). */
  reason_code?: string | null;
  closed_note?: string | null;
  open_until?: string | null;
}

export async function availability(id: string): Promise<Availability | null> {
  try {
    const r = await fetch(`${CORE}/api/v1/restaurants/${id}/availability`, { next: { revalidate: 60 } });
    return r.ok ? ((await r.json()) as Availability) : null;
  } catch {
    return null;
  }
}

/** Great-circle distance in km. */
export function km(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

/** "11:00" (the kitchen's local clock) -> "11:00 am" (dateLocale: the visitor's language, the country's clock). */
export function clock(hhmm: string | null | undefined, formatLocale: string): string | null {
  const m = /^(\d{1,2}):(\d{2})/.exec(hhmm ?? "");
  if (!m) return null;
  const d = new Date(Date.UTC(2000, 0, 1, Number(m[1]), Number(m[2])));
  return new Intl.DateTimeFormat(formatLocale, { hour: "numeric", minute: "2-digit", timeZone: "UTC" }).format(d).toLowerCase();
}
