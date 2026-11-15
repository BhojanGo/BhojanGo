// Who is looking, from where, in which language (server side). Order of
// evidence for the country (WebDataRules.html): the delivery address (cookie,
// set when the visitor picks one or signs in), then the IP hint (set in the
// browser from /markets/hint), then the browser's locale. Language is separate:
// the visitor's choice (cookie), else the browser's, from the country's list.

import { createTranslator, formatLocale, languagesFor, pickLanguage, type Messages } from "@bhojango/i18n";
import { cookies, headers } from "next/headers";
import { cache } from "react";

import { directory, type DirCountry, type Directory } from "./server";

export const COOKIE = { address: "bg_addr", language: "bg_lang", hintCountry: "bg_hint", country: "bg_country" } as const;

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

function countryFromLocale(acceptLanguage: string, dir: Directory): DirCountry | null {
  for (const part of acceptLanguage.split(",")) {
    const region = (part.split(";")[0] ?? "").trim().split("-")[1]?.toUpperCase();
    const hit = region && dir.countries.find((c) => c.code === region);
    if (hit) return hit;
  }
  return null;
}

export interface Context {
  directory: Directory;
  country: DirCountry | null; // decides currency, kitchens and the language list
  countrySource: "address" | "chosen" | "page" | "ip" | "locale" | "none";
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
  const acceptLanguage = hdrs.get("accept-language") ?? "";
  const byCode = (code?: string | null) => (code ? dir.countries.find((c) => c.code === code.toUpperCase()) ?? null : null);
  let country: DirCountry | null = null;
  let countrySource: Context["countrySource"] = "none";
  for (const [source, candidate] of [
    ["address", byCode(place?.country)],
    ["chosen", byCode(jar.get(COOKIE.country)?.value)],
    // a city or kitchen page (/{country}/...): its country, before IP or browser hints
    ["page", byCode((hdrs.get("x-bg-path") ?? "").split("/")[1]?.length === 2 ? (hdrs.get("x-bg-path") ?? "").split("/")[1] : null)],
    ["ip", byCode(jar.get(COOKIE.hintCountry)?.value)],
    ["locale", countryFromLocale(acceptLanguage, dir)],
  ] as const) {
    if (candidate) {
      country = candidate;
      countrySource = source;
      break;
    }
  }
  // Nothing known: the browser's language picks a country that offers it, else the first.
  if (!country && dir.countries.length) {
    const lang = acceptLanguage.split(",")[0]?.split("-")[0]?.trim().toLowerCase();
    country = dir.countries.find((c) => languagesFor(c.locales).includes(lang as never) && lang !== "en") ?? dir.countries[0] ?? null;
  }
  const locales = country?.locales ?? ["en-US"];
  const language = pickLanguage({ chosen: jar.get(COOKIE.language)?.value, acceptLanguage, locales });
  const [messages, fallback] = await Promise.all([loadMessages(language), loadMessages("en")]);
  return {
    directory: dir,
    country,
    countrySource,
    place: place && byCode(place.country) ? place : null,
    language,
    languages: languagesFor(locales),
    formatLocale: formatLocale(locales),
    messages,
    fallback,
    t: createTranslator(language, messages, fallback),
  };
});
