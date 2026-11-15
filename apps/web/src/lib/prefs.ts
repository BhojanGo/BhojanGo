// Who is looking, from where, in which language (server side). Order of
// evidence for the country (R6, `detectCountry` in @bhojango/i18n): the delivery
// address (cookie, set when the visitor picks one or signs in), then the city they
// chose ("Change city"), then the page's own country, then the IP hint (set in the
// browser from /markets/hint), then the browser's locale. Currency and the language
// list follow the country. Language is the visitor's remembered choice (cookie) if
// the country offers it, else English (`chooseLanguage`).

import { chooseLanguage, createTranslator, detectCountry, formatLocale, languagesFor, type CountrySource, type Messages } from "@bhojango/i18n";
import { cookies, headers } from "next/headers";
import { cache } from "react";

import { flatCities, type FlatCity } from "@/components/discover/places";
import { directory, type DirCountry, type Directory } from "./server";

/** Cookies (a year, path /; the server reads them, so the first render is right). */
export const COOKIE = {
  address: "bg_addr", // the delivery address (Place JSON)
  language: "bg_lang", // "te": the language the visitor picked in the pill
  city: "bg_city", // "US-ID-BOI": the city picked with "Change city"
  hintCountry: "bg_hint", // "IN": the IP hint's country
  hintCity: "bg_hint_city", // the IP hint's city code, when it names one
} as const;

/** The delivery address the visitor picked (an area point or a saved address). */
export interface Place {
  label: string; // "<area>, <city>" or the first line of a saved address
  lat: number;
  lng: number;
  country: string;
  city_code?: string | null;
  city_path?: string | null;
  zone?: string | null;
  address_id?: string | null;
  served?: boolean;
}

export function parsePlace(raw: string | undefined): Place | null {
  if (!raw) return null;
  try {
    const p = JSON.parse(decodeURIComponent(raw)) as Place;
    return typeof p.lat === "number" && typeof p.lng === "number" && p.country ? p : null;
  } catch {
    return null;
  }
}

async function loadMessages(language: string): Promise<Messages> {
  // Static imports per language so the bundler includes them all.
  switch (language) {
    case "hi": return (await import("@bhojango/i18n/messages/hi.json")).default as Messages;
    case "te": return (await import("@bhojango/i18n/messages/te.json")).default as Messages;
    case "ta": return (await import("@bhojango/i18n/messages/ta.json")).default as Messages;
    case "kn": return (await import("@bhojango/i18n/messages/kn.json")).default as Messages;
    case "mr": return (await import("@bhojango/i18n/messages/mr.json")).default as Messages;
    case "bn": return (await import("@bhojango/i18n/messages/bn.json")).default as Messages;
    case "es": return (await import("@bhojango/i18n/messages/es.json")).default as Messages;
    default: return (await import("@bhojango/i18n/messages/en.json")).default as Messages;
  }
}

const countryOfCity = (code: string | null | undefined) => (code ? code.split("-")[0]!.toUpperCase() : null);

export interface Context {
  directory: Directory;
  country: DirCountry | null; // decides currency, kitchens and the language list
  countrySource: CountrySource;
  /** The home page's location line ("<city>, <CC> · Change city"): the visitor's city in that country. */
  city: FlatCity | null;
  place: Place | null;
  language: string;
  languages: string[];
  formatLocale: string;
  messages: Messages;
  fallback: Messages;
  t: ReturnType<typeof createTranslator>;
}

/** Once per request. */
export const getContext = cache(async (): Promise<Context> => {
  const [jar, hdrs, dir] = await Promise.all([cookies(), headers(), directory()]);
  const place = parsePlace(jar.get(COOKIE.address)?.value);
  const chosenCity = jar.get(COOKIE.city)?.value ?? null;
  const hintCity = jar.get(COOKIE.hintCity)?.value ?? null;
  const pathCountry = (hdrs.get("x-bg-path") ?? "").split("/")[1] ?? "";
  const { code, source } = detectCountry(
    {
      address: place?.country,
      chosen: countryOfCity(chosenCity),
      // a city or kitchen page (/{country}/...): its country, before IP or browser hints
      page: /^[a-z]{2}$/.test(pathCountry) ? pathCountry : null,
      ip: jar.get(COOKIE.hintCountry)?.value,
      browser: hdrs.get("accept-language"),
    },
    dir.countries,
  );
  const country = dir.countries.find((c) => c.code === code) ?? null;
  const all = flatCities(dir).filter((c) => c.country === country?.code);
  const city =
    all.find((c) => c.code === place?.city_code) ??
    all.find((c) => c.code === chosenCity) ??
    all.find((c) => c.code === hintCity) ??
    all.find((c) => c.status === "live") ??
    all[0] ??
    null;
  const locales = country?.locales ?? ["en-US"];
  const language = chooseLanguage(jar.get(COOKIE.language)?.value, locales);
  const [messages, fallback] = await Promise.all([loadMessages(language), loadMessages("en")]);
  return {
    directory: dir,
    country,
    countrySource: source,
    city,
    place: place && dir.countries.some((c) => c.code === place.country.toUpperCase()) ? place : null,
    language,
    languages: languagesFor(locales),
    formatLocale: formatLocale(locales),
    messages,
    fallback,
    t: createTranslator(language, messages, fallback),
  };
});
