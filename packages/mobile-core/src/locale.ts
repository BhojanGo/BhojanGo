// Countries, languages and formatting for the Expo apps (round 4), pure logic:
// no React, no React Native, so `node --test` covers it (test/locale.test.ts).
//
// The rules (same as the website): a country's languages, currency, locales,
// distance unit and phone code are Markets data (GET /api/v1/markets/directory).
// Money, numbers and dates follow the COUNTRY's first locale (formatLocale), never
// the language: switching to Hindi never changes how a price reads.
// No relative imports here: Node runs this file directly in the tests.
import type { CoreSchemas } from "@bhojango/api-client";
import { detectCountry, languageOf, languagesFor, type CountrySource as I18nCountrySource, type Language } from "@bhojango/i18n";

/** A country as Markets publishes it (code, name, currency, locales, distance_unit, phone_code, timezone, ...). */
export type MarketCountry = CoreSchemas["DirCountry"];

/** Where the current country came from (@bhojango/i18n detectCountry; the apps never use "chosen" or "page"). */
export type CountrySource = I18nCountrySource;

/** The region of a locale tag (language-REGION or language_REGION -> REGION); null for a bare language. */
export function regionOf(locale: string | null | undefined): string | null {
  const m = /^[a-z]{2,3}(?:[-_][A-Za-z]{4})?[-_]([A-Za-z]{2})\b/.exec(String(locale ?? ""));
  return m ? m[1]!.toUpperCase() : null;
}

/**
 * The country to use (there is no country selector), with the website's rules
 * (@bhojango/i18n detectCountry): the delivery address's country (the customer's
 * address; the rider's or partner's account), else the IP hint (GET
 * /markets/hint), else the phone's locale region, else a country offering the
 * phone's (non-English) language, else Markets' first; none until Markets loads.
 */
export function resolveCountry(opts: {
  countries: readonly MarketCountry[];
  addressCountry?: string | null;
  ipCountry?: string | null;
  deviceLocale?: string | null;
}): { country: MarketCountry | null; source: CountrySource } {
  const { countries } = opts;
  const found = detectCountry({ address: opts.addressCountry, page: null, ip: opts.ipCountry, browser: opts.deviceLocale }, countries);
  const country = found.code ? countries.find((c) => c.code === found.code) ?? null : null;
  return country ? { country, source: found.source } : { country: null, source: "none" };
}

/**
 * The partner apps' country (BhojanGo Kitchen, BhojanGo Delivery: R20), whose Markets
 * locales are the languages they offer. Signed in: the account's country (the
 * kitchen's, the delivery partner's) when Markets has it. Otherwise the phone's
 * region when Markets has it, else the first country with a live city, else
 * Markets' first. No IP hint: a partner works in their own country.
 */
export function partnerCountry(opts: {
  countries: readonly MarketCountry[];
  accountCountry?: string | null;
  deviceLocale?: string | null;
}): { country: MarketCountry | null; source: CountrySource } {
  const { countries } = opts;
  const byCode = (code: string | null | undefined) => (code ? countries.find((c) => c.code === code.toUpperCase()) ?? null : null);
  const account = byCode(opts.accountCountry);
  if (account) return { country: account, source: "address" };
  const device = byCode(regionOf(opts.deviceLocale));
  if (device) return { country: device, source: "browser" };
  const first = countries.find((c) => c.live > 0) ?? countries[0] ?? null;
  return first ? { country: first, source: "default" } : { country: null, source: "none" };
}

/**
 * The partner apps' language: the one saved on this phone when the country offers
 * it, else the country's first (Markets order). Until a country is known, the saved one.
 */
export function partnerLanguage(saved: string | null | undefined, locales: readonly string[] | null | undefined): Language {
  const offered = languagesFor(locales ? [...locales] : saved ? [saved] : null);
  const lang = saved ? languageOf(saved) : "";
  return (offered as string[]).includes(lang) ? (lang as Language) : offered[0]!;
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

const fold = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/**
 * "Change city" (R8): the countries' states and cities whose city or state name
 * contains `q` (accents and case ignored), empty states and countries dropped;
 * everything when `q` is blank.
 */
export function filterCities(countries: readonly MarketCountry[], q: string | null | undefined): MarketCountry[] {
  const needle = fold(String(q ?? "").trim());
  return countries
    .map((k) => ({
      ...k,
      regions: k.regions
        .map((r) => ({ ...r, cities: needle && !fold(r.name).includes(needle) ? r.cities.filter((c) => fold(c.name).includes(needle)) : r.cities }))
        .filter((r) => r.cities.length),
    }))
    .filter((k) => k.regions.length);
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
 * lakh grouping, symbol before or after, ...); a minus sign for a discount. Always two
 * decimals (29.00, 300.00: one money format everywhere, R12). The symbol and
 * grouping come from Intl for the currency code (Markets data), not from a table.
 */
export function formatMoney(amount: number | string | null | undefined, currency: string, locale?: string): string {
  const n = Number(amount ?? 0);
  const abs = Math.abs(Number.isFinite(n) ? n : 0);
  const decimals = 2;
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

/**
 * Intl options for an order's time zone (the API's IANA `time_zone`: the order's
 * city). Every order time (placed, ETA, receipt) is shown in it, never the phone's.
 * Nothing when the zone is unknown.
 *   time(order.placed_at, inZone(order.time_zone))
 */
export function inZone(timeZone: string | null | undefined): Intl.DateTimeFormatOptions {
  return timeZone ? { timeZone } : {};
}

/** A short day and month in the locale's order; options and time zone as Intl.DateTimeFormat takes them. */
export function formatDate(iso: string | number | Date, locale?: string, opts?: Intl.DateTimeFormatOptions): string {
  return format(iso, locale, { day: "numeric", month: "short" }, opts, (d) => d.toDateString());
}

/** A time on the locale's clock (12 or 24 hours), lower-cased as on the website. */
export function formatTime(iso: string | number | Date, locale?: string, opts?: Intl.DateTimeFormatOptions): string {
  return format(iso, locale, { hour: "numeric", minute: "2-digit" }, opts,
    (d) => `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`).toLowerCase();
}

/** The hour (0-23) in a time zone (a city's, Markets data); the phone's clock only when no zone is known. */
export function hourIn(timeZone: string | null | undefined, now: Date = new Date()): number {
  if (timeZone) {
    try {
      // data-ok: parses the hour, so Latin digits whatever the language
      return Number(new Intl.DateTimeFormat("en-US", { hour: "numeric", hourCycle: "h23", timeZone }).format(now)) % 24;
    } catch {
      // an engine without time-zone data: the phone's clock below
    }
  }
  return now.getHours();
}

function format(iso: string | number | Date, locale: string | undefined, base: Intl.DateTimeFormatOptions,
                opts: Intl.DateTimeFormatOptions | undefined, fallback: (d: Date) => string): string {
  const day = isCalendarDay(iso);
  // A calendar day from the API ("2026-11-14") is that day everywhere: noon UTC read in UTC,
  // so no time zone (the phone's or a city's) moves it to the day before or after.
  const d = day ? new Date(`${iso as string}T12:00:00Z`) : iso instanceof Date ? iso : new Date(iso);
  const options = { ...base, ...opts, ...(day ? { timeZone: "UTC" } : {}) };
  try {
    return new Intl.DateTimeFormat(locale, options).format(d);
  } catch {
    try {
      // an unknown zone name: the same format without it rather than nothing
      const { timeZone: _unused, ...rest } = options;
      return new Intl.DateTimeFormat(locale, rest).format(d);
    } catch {
      return fallback(d);
    }
  }
}

function isCalendarDay(iso: string | number | Date): boolean {
  return typeof iso === "string" && /^\d{4}-\d{2}-\d{2}$/.test(iso);
}

/** The country's phone code (Markets phone_code) + the typed number, digits only, leading zeros dropped; a number typed with "+" is taken as is. */
export function e164(phoneCode: string, typed: string): string {
  const digits = typed.replace(/\D/g, "");
  return typed.trim().startsWith("+") ? `+${digits}` : `${phoneCode}${digits.replace(/^0+/, "")}`;
}
