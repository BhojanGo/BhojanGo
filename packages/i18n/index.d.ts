export type Language = "en" | "hi" | "te" | "ta" | "kn" | "mr" | "bn" | "es";
export type Messages = { [key: string]: string | Messages | { one?: string; few?: string; many?: string; other: string } };
export type Translate = (key: string, vars?: Record<string, string | number>) => string;

export declare const LANGUAGES: Record<Language, { name: string; dir: "ltr" | "rtl" }>;
export declare const DEFAULT_LANGUAGE: Language;
export declare function languageOf(locale: string | null | undefined): string;
export declare function languagesFor(locales: string[] | null | undefined): Language[];
export declare function pickLanguage(opts: { chosen?: string | null; acceptLanguage?: string | null; locales?: string[] | null }): Language;
export declare function languageList(locales: string[] | null | undefined): { code: Language; name: string }[];
export declare function chooseLanguage(chosen: string | null | undefined, locales: string[] | null | undefined): Language;
export type CountrySource = "address" | "chosen" | "page" | "ip" | "browser" | "default" | "none";
export declare function detectCountry(
  evidence: { address?: string | null; chosen?: string | null; page?: string | null; ip?: string | null; browser?: string | readonly string[] | null },
  countries: readonly { code: string; locales?: readonly string[] | null }[] | null | undefined,
): { code: string | null; source: CountrySource };
export interface LocationCity {
  code: string; name: string; country: string; status: string;
  /** The state's short code from Markets ("ID", "TG"): the line reads "Boise, ID". */
  region_code?: string | null;
}
export interface LocationEvidence {
  /** The delivery address: its country, its Markets city (if any), whether an open zone serves it. */
  address?: { label?: string | null; country: string; city_code?: string | null; served?: boolean | null } | null;
  /** A Markets city code picked with "Change city". */
  chosen?: string | null;
  /** GET /markets/hint (the IP's place). */
  ip?: { country?: string | null; place?: string | null; region_code?: string | null; city_code?: string | null; served?: boolean | null } | null;
}
export type LocationSource = "address" | "chosen" | "ip" | "none";
export interface ResolvedLocation<C extends LocationCity = LocationCity> {
  source: LocationSource;
  place: string | null;
  code: string | null;
  city: C | null;
  served: boolean;
  deliversHere: boolean;
}
export declare function resolveLocation<C extends LocationCity>(evidence: LocationEvidence, cities: readonly C[] | null | undefined): ResolvedLocation<C>;
export declare function formatLocale(locales: string[] | null | undefined): string;
/** Dates and times in the visitor's language, the country's region, Latin digits ("es", "en-US" -> "es-US-u-nu-latn"). */
export declare function dateLocale(language: string, formatLocale: string): string;
/** "Middle Eastern" -> "cuisine_names.middle_eastern". */
export declare function cuisineKey(name: string): string;
/** A cuisine tag in the language when the catalog knows it, else as written (R27). */
export declare function cuisineName(t: (key: string, vars?: Record<string, string | number>) => string, name: string): string;
/** A fair-bill line's name in the language: the engine's lines by code, known tax lines by name (R27). */
export declare function billLineLabel(t: (key: string, vars?: Record<string, string | number>) => string,
  line: { code: string; label: string }): string;
export declare function createTranslator(language: string, messages: Messages, fallback: Messages): Translate;
export declare function pluralSelector(language: string): (count: number) => string;

/** For the visible text only (tel: links keep the E.164): "+12085550291" -> "+1 208-555-0291",
 * "+919876543210" -> "+91 98765 43210"; rules per country in phone.js. Unknown or invalid input as is. */
/** R38: how a stored number is shown: "+1 (208) 555-0123", "+91 98765 43210" (libphonenumber-js). */
export function formatPhone(e164: string | null | undefined): string;
export interface ParsedPhone { e164: string; valid: boolean; country: string | null }
/** What was typed in ``country`` (a "+" number keeps its own country); null when it can't be read. */
export function parsePhone(input: string | null | undefined, country?: string | null): ParsedPhone | null;
/** E.164 for a valid number, else null. */
export function toE164(input: string | null | undefined, country?: string | null): string | null;
export function isValidPhone(input: string | null | undefined, country?: string | null): boolean;
/** "+1", "+91". */
export function callingCode(country: string | null | undefined): string;
/** The placeholder after the country-code box: "(208) 555-0123", "98765 43210". */
export function phonePlaceholder(country: string | null | undefined): string;
/** A whole example: "+1 (208) 555-0123", "+91 98765 43210". */
export function phoneExample(country: string | null | undefined): string;
export function formatAsYouType(input: string | null | undefined, country?: string | null): string;

/** R27: when a kitchen opens, for "Closed · opens {time}". The time on the city's clock in the country's
 *  format; the weekday (another day only) in the visitor's language. Null for no time. */
export interface OpensOptions { timeZone?: string | null; formatLocale?: string | null; language?: string | null; now?: Date }
export declare function opensWhen(iso: string | null | undefined, options?: OpensOptions): { time: string; day: string | null } | null;
/** "Closed · opens 6:30 am" (keys.today, later today) or "Closed · opens Sat 6:30 am" (keys.day);
 *  defaults common.closed_opens / common.closed_opens_day. */
export declare function opensLabel(t: Translate, iso: string | null | undefined, options?: OpensOptions,
  keys?: { today: string; day: string }): string | null;
/** "08:00" -> "8:00 am" in the country's format. */
export declare function wallClock(hhmm: string | null | undefined, formatLocale?: string | null): string | null;
