// Countries, languages and formatting for the Expo apps (round 4), pure logic:
// no React, no React Native, so `node --test` covers it (test/locale.test.ts).
//
// The rules (same as the website): a country's languages, currency, locales,
// distance unit and phone code are Markets data (GET /api/v1/markets/directory).
// Money, numbers and dates follow the COUNTRY's first locale (formatLocale), never
// the language: switching to Hindi never changes how a price reads.
// No relative imports here: Node runs this file directly in the tests.
import type { CoreSchemas } from "@bhojango/api-client";

/** A country as Markets publishes it (code, name, currency, locales, distance_unit, phone_code, timezone, ...). */
export type MarketCountry = CoreSchemas["DirCountry"];

/** Where the current country came from (the strongest source wins, in this order). */
export type CountrySource = "address" | "chosen" | "device" | "only" | "none";

/** The region of a locale tag (language-REGION or language_REGION -> REGION); null for a bare language. */
export function regionOf(locale: string | null | undefined): string | null {
  const m = /^[a-z]{2,3}(?:[-_][A-Za-z]{4})?[-_]([A-Za-z]{2})\b/.exec(String(locale ?? ""));
  return m ? m[1]!.toUpperCase() : null;
}

/**
 * The country to use: the delivery address's country when known (the customer app
 * sets it), else the person's stored choice, else the device locale's region when
 * Markets has that country, else the only country when there is just one, else none
 * (show a country choice).
 */
export function resolveCountry(opts: {
  countries: readonly MarketCountry[];
  addressCountry?: string | null;
  chosen?: string | null;
  deviceLocale?: string | null;
}): { country: MarketCountry | null; source: CountrySource } {
  const { countries } = opts;
  const find = (code: string | null | undefined) =>
    code ? countries.find((c) => c.code.toUpperCase() === code.toUpperCase()) ?? null : null;
  const fromAddress = find(opts.addressCountry);
  if (fromAddress) return { country: fromAddress, source: "address" };
  const chosen = find(opts.chosen);
  if (chosen) return { country: chosen, source: "chosen" };
  const device = find(regionOf(opts.deviceLocale));
  if (device) return { country: device, source: "device" };
  if (countries.length === 1) return { country: countries[0]!, source: "only" };
  return { country: null, source: "none" };
}

/** A Markets city by its code ("XX-RR-CCC") with its country, or null (hidden or unknown). */
export function findCity(countries: readonly MarketCountry[], code: string | null | undefined):
    { city: MarketCountry["regions"][number]["cities"][number]; country: MarketCountry } | null {
  if (!code) return null;
  for (const country of countries) {
    for (const region of country.regions) {
      const city = region.cities.find((c) => c.code === code);
      if (city) return { city, country };
    }
  }
  return null;
}

/** The Markets country that uses a currency (its distance unit, locale, ...), or null. */
export function countryForCurrency(countries: readonly MarketCountry[], currency: string | null | undefined): MarketCountry | null {
  return (currency && countries.find((c) => c.currency === currency)) || null;
}

/** Every live city's name, for "We're cooking in ..." (Markets order: live first). */
export function liveCityNames(countries: readonly MarketCountry[]): string[] {
  return countries.flatMap((c) => c.regions.flatMap((r) => r.cities.filter((x) => x.status === "live").map((x) => x.name)));
}

/**
 * The locale to format an amount in `currency`: the current country's when it uses
 * that currency, else the first Markets country that does (an order from another
 * country reads the way it does there), else the current country's, else the device's.
 */
export function localeForCurrency(currency: string | null | undefined, current: MarketCountry | null,
                                  countries: readonly MarketCountry[]): string | undefined {
  if (current && (!currency || current.currency === currency)) return current.locales[0];
  const other = currency ? countries.find((c) => c.currency === currency) : undefined;
  return other?.locales[0] ?? current?.locales[0] ?? undefined;
}

/** The device's locale tag, from Intl (Hermes reads the phone's setting); null when unknown. */
export function deviceLocale(): string | null {
  try {
    return Intl.DateTimeFormat().resolvedOptions().locale || null;
  } catch {
    return null;
  }
}

/**
 * An amount in a currency, grouped and placed the way the locale writes it (Indian
 * lakh grouping, symbol before or after, ...); a minus sign for a discount. `whole`
 * drops ".00" from a whole amount but never rounds real cents away. The symbol and
 * grouping come from Intl for the currency code (Markets data), not from a table.
 */
export function formatMoney(amount: number | string | null | undefined, currency: string, locale?: string,
                            opts?: { whole?: boolean }): string {
  const n = Number(amount ?? 0);
  const abs = Math.abs(Number.isFinite(n) ? n : 0);
  const decimals = opts?.whole && Math.round(abs * 100) % 100 === 0 ? 0 : 2;
  let body: string;
  try {
    body = new Intl.NumberFormat(locale, {
      style: "currency", currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    }).format(abs);
  } catch {
    body = `${currency} ${abs.toFixed(decimals)}`; // an engine without currency data
  }
  return n < 0 ? `−${body}` : body;
}

/** A number in the locale's grouping; at most `digits` decimals. */
export function formatNumber(n: number, locale?: string, digits = 1): string {
  try {
    return new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(n);
  } catch {
    return String(Math.round(n * 10 ** digits) / 10 ** digits);
  }
}

const KM_PER_MILE = 1.609344;

/** A distance in kilometres in the country's unit (Markets distance_unit): {value, unit}. */
// data-ok: the two distance units Markets offers; the conversion lives here and nowhere else.
export function convertDistance(km: number, unit: string | null | undefined): { value: number; unit: "km" | "mi" } {
  return unit === "mi" ? { value: km / KM_PER_MILE, unit: "mi" } : { value: km, unit: "km" }; // data-ok: as above
}

/** A short day and month in the locale's order; options and time zone as Intl.DateTimeFormat takes them. */
export function formatDate(iso: string | number | Date, locale?: string, opts?: Intl.DateTimeFormatOptions): string {
  const d = toDate(iso);
  try {
    return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", ...opts }).format(d);
  } catch {
    return d.toDateString();
  }
}

/** A time on the locale's clock (12 or 24 hours), lower-cased as on the website. */
export function formatTime(iso: string | number | Date, locale?: string, opts?: Intl.DateTimeFormatOptions): string {
  const d = toDate(iso);
  try {
    return new Intl.DateTimeFormat(locale, { hour: "numeric", minute: "2-digit", ...opts }).format(d).toLowerCase();
  } catch {
    return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  }
}

/** A calendar day from the API ("2026-11-14") at noon, so no time zone moves it to another day. */
function toDate(iso: string | number | Date): Date {
  if (typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso)) return new Date(`${iso}T12:00:00`);
  return iso instanceof Date ? iso : new Date(iso);
}

/** The country's phone code (Markets phone_code) + the typed number, digits only, leading zeros dropped; a number typed with "+" is taken as is. */
export function e164(phoneCode: string, typed: string): string {
  const digits = typed.replace(/\D/g, "");
  return typed.trim().startsWith("+") ? `+${digits}` : `${phoneCode}${digits.replace(/^0+/, "")}`;
}
