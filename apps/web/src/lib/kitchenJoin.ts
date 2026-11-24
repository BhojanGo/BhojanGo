// "Add your kitchen" (/partner): the page's rules as plain functions, so they are
// tested on their own (test/kitchenJoin.test.ts). Every number comes from
// GET /kitchens/terms (the live commission and payout rules, Markets cities and
// documents); nothing here knows a country.

import { isValidPhone } from "@bhojango/i18n";

export const MIN_PASSWORD = 10;

export interface TermsCity {
  code: string;
  name: string;
  region: string;
  status: "live" | "soon";
  beta: boolean;
  starting_percent?: string | number | null;
}

export interface Terms {
  country: string;
  country_name: string;
  currency: string;
  phone_code: string;
  tax_regime: string;
  commission: {
    percent_min: string | number;
    percent_max: string | number;
    starting_percent?: string | number | null;
    tiers?: { tier: string; percent: string | number }[];
    flat_per_order?: string | number | null;
  } | null;
  payout: { frequency?: "weekly" | "biweekly"; day?: string; hold_days?: number };
  documents: { key: string; title: string; why: string }[];
  cities: TermsCity[];
}

export interface SignUpFields {
  kitchen_name: string;
  city_code: string;
  full_name: string;
  phone: string; // the national number, as typed
  email: string;
  password: string;
  accept_terms: boolean;
}

export type FieldKey = keyof SignUpFields;

/** The full number in E.164 from the country's calling code and what was typed ("98480 21234" -> "+919848021234"). */
export function e164(phoneCode: string, typed: string): string {
  const code = phoneCode.replace(/[^\d]/g, "");
  let digits = typed.replace(/\D/g, "");
  if (digits.startsWith(code) && digits.length > code.length + 7) digits = digits.slice(code.length); // pasted with the code
  digits = digits.replace(/^0+/, ""); // a trunk 0
  return `+${code}${digits}`;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Field -> what's wrong (an i18n key under kitchen_join.errors), in the form's order; empty when it can be sent. */
export function validate(f: SignUpFields, phoneCode: string, cities: { code: string }[]): Partial<Record<FieldKey, string>> {
  const out: Partial<Record<FieldKey, string>> = {};
  if (f.kitchen_name.trim().length < 2) out.kitchen_name = "kitchen_name";
  if (!cities.some((c) => c.code === f.city_code)) out.city_code = "city";
  if (f.full_name.trim().length < 2) out.full_name = "contact_name";
  if (!isValidPhone(e164(phoneCode, f.phone))) out.phone = "phone";  // R38: a real number (libphonenumber-js)
  if (!EMAIL.test(f.email.trim())) out.email = "email";
  if (f.password.length < MIN_PASSWORD) out.password = "password";
  if (!f.accept_terms) out.accept_terms = "consent";
  return out;
}

/** What the API's refusal means for the form: a field to mark, or a message for the whole form. */
export function apiProblem(code: string | undefined): { field?: FieldKey; key: string } {
  switch (code) {
    case "ACCOUNT_EXISTS": return { field: "email", key: "exists" };
    case "PASSWORD": return { field: "password", key: "password" };
    case "PHONE_COUNTRY_MISMATCH": return { field: "phone", key: "phone" };
    case "PHONE_INVALID": return { field: "phone", key: "phone" };
    case "CITY": return { field: "city_code", key: "city" };
    case "TERMS": return { field: "accept_terms", key: "consent" };
    default: return { key: "generic" };
  }
}

const num = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? null : Number(v));

/**
 * The commission line for the page: which message and its numbers, from the live rules.
 * "range" when tiers or cities differ, "one" when every kitchen pays the same, "unknown"
 * when the country has no commission rule live yet. `start` is the visitor's city's
 * starting rate (else the country's).
 */
export function commissionSummary(terms: Pick<Terms, "commission" | "cities"> | null, cityCode?: string | null):
  | { kind: "unknown" }
  | { kind: "one"; percent: number; flat: number | null }
  | { kind: "range"; min: number; max: number; start: number | null; city: string | null; flat: number | null } {
  const c = terms?.commission;
  if (!c) return { kind: "unknown" };
  const min = Number(c.percent_min);
  const max = Number(c.percent_max);
  const flat = num(c.flat_per_order);
  if (min === max) return { kind: "one", percent: min, flat };
  const city = terms?.cities.find((x) => x.code === cityCode) ?? null;
  const start = num(city?.starting_percent) ?? num(c.starting_percent);
  return { kind: "range", min, max, start, city: city?.name ?? null, flat };
}

/** Cities for the form: live ones first (by name), then coming soon. */
export function cityOptions(cities: TermsCity[]): TermsCity[] {
  return [...cities].sort((a, b) => (a.status === b.status ? a.name.localeCompare(b.name) : a.status === "live" ? -1 : 1));
}

/** The city the form starts on: the visitor's own when kitchens can apply there, else none (they choose). */
export function defaultCity(cities: TermsCity[], visitorCity: string | null | undefined): string {
  return cities.some((c) => c.code === visitorCity) ? (visitorCity as string) : "";
}

/**
 * A translated sentence with links in it ("I agree to the {terms} and the {privacy}."):
 * the parts between the placeholders, in order, so each language puts the links where
 * its grammar wants them.
 */
export function splitLinks(text: string, names: string[]): ({ text: string } | { link: string })[] {
  const out: ({ text: string } | { link: string })[] = [];
  const re = new RegExp(`\\{(${names.join("|")})\\}`, "g");
  let last = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > last) out.push({ text: text.slice(last, m.index) });
    out.push({ link: m[1]! });
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

/** Where a signed-in visitor's application stands, for the page's top action. */
export function applicationState(role: string | null | undefined): "visitor" | "customer" | "kitchen" | "delivery" | "other" {
  if (!role) return "visitor";
  if (role === "customer") return "customer";
  if (role === "restaurant_owner") return "kitchen";
  if (role === "driver") return "delivery";
  return "other";
}
