// Deliver with BhojanGo (/deliver): small pure helpers, tested with node --test.
// Everything shown comes from GET /delivery/terms (rules + Markets); these only
// format it. QR codes are drawn here, from a local library (no QR service).
import qrcode from "qrcode-generator";

/** A QR code as one SVG path of 1×1 squares, with a 4-module quiet zone. */
export function qrPath(text: string): { size: number; d: string } {
  const qr = qrcode(0, "M");
  qr.addData(text, "Byte");
  qr.make();
  const n = qr.getModuleCount();
  const parts: string[] = [];
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) if (qr.isDark(r, c)) parts.push(`M${c + 4} ${r + 4}h1v1h-1z`);
  }
  return { size: n + 8, d: parts.join("") };
}

// data-ok: maps the API's distance unit to its Intl unit name, not a hard-coded country
const INTL_UNIT: Record<string, string> = { km: "kilometer", mi: "mile" };

/** "3 km", "2 mi" (or "3 किमी") in the given locale; falls back to "<n> <unit>". */
export function distance(value: number | string, unit: string, locale: string): string {
  const n = Number(value);
  const intl = INTL_UNIT[unit];
  if (!intl) return `${n} ${unit}`;
  return new Intl.NumberFormat(locale, { style: "unit", unit: intl, unitDisplay: "short", maximumFractionDigits: 1 }).format(n);
}

/** The unit's short name alone ("km", "mi"), as Intl writes it after a number. */
export function unitName(unit: string, locale: string): string {
  const intl = INTL_UNIT[unit];
  if (!intl) return unit;
  const parts = new Intl.NumberFormat(locale, { style: "unit", unit: intl, unitDisplay: "short" }).formatToParts(1);
  return parts.find((p) => p.type === "unit")?.value ?? unit;
}

const DAY_INDEX: Record<string, number> = { mon: 0, tue: 1, wed: 2, thu: 3, fri: 4, sat: 5, sun: 6 };

/** "Monday" for "mon", in the page's language. */
export function weekday(day: string, language: string): string {
  const i = DAY_INDEX[day] ?? 0;
  // 2024-01-01 was a Monday; noon UTC is the same day everywhere
  const d = new Date(Date.UTC(2024, 0, 1 + i, 12));
  try {
    return new Intl.DateTimeFormat(language, { weekday: "long", timeZone: "UTC" }).format(d);
  } catch {
    return new Intl.DateTimeFormat("en", { weekday: "long", timeZone: "UTC" }).format(d);
  }
}

/** "motorcycle, scooter or electric scooter" in the page's language. */
export function orList(items: string[], language: string): string {
  try {
    return new Intl.ListFormat(language, { type: "disjunction" }).format(items);
  } catch {
    return items.join(", ");
  }
}

/** "100%" in the given locale. */
export function percent(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(value / 100);
}

export function capitalize(s: string): string {
  return s ? s[0]!.toLocaleUpperCase() + s.slice(1) : s;
}

/** Live cities to offer: the visitor's own city when it is one, else the first. */
export function defaultCity(codes: string[], preferred: (string | null | undefined)[]): string | null {
  for (const p of preferred) if (p && codes.includes(p)) return p;
  return codes[0] ?? null;
}

/** First name for "You're signed up, Kiran". */
export function firstName(full: string | null | undefined): string {
  return (full ?? "").trim().split(/\s+/)[0] ?? "";
}
