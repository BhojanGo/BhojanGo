"use client";
// The language and formats in the browser: the same messages the server used,
// so client components read the same words. Setting the language or the
// address writes a cookie (the server reads it) and refreshes the page.

import { chooseLanguage, createTranslator, languageList, LANGUAGES, type Messages } from "@bhojango/i18n";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { date, money, number, time } from "./format";
import type { Place } from "./prefs";

interface I18n {
  language: string;
  languages: string[];
  formatLocale: string;
  /** Dates and times in the visitor's language (R27; prefs.ts). */
  dateLocale: string;
  country: { code: string; name: string; currency: string; timezone: string; distance_unit: string; phone_code: string;
    /** Who operates BhojanGo in the country (R15, Markets "legal": name, address, support contacts...). */
    legal?: Record<string, string> } | null;
  messages: Messages;
  fallback: Messages;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ value, children }: { value: I18n; children: ReactNode }) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("I18nProvider missing");
  return v;
}

/** The visitor's country (Markets), with who operates BhojanGo there (R15). */
export function useCountry() {
  return useI18n().country;
}

export function useT() {
  const { language, messages, fallback } = useI18n();
  return useMemo(() => createTranslator(language, messages, fallback), [language, messages, fallback]);
}

/**
 * Money, numbers and dates in the country's format. Dates and times are in a time
 * zone, never the visitor's device's: `zone(order.time_zone)` for an order (its
 * city's), `zone(kitchen.time_zone)` for a kitchen; plain `date`/`time` use the
 * country's (a label only in a country with several zones).
 */
export function useFormat() {
  const { formatLocale, dateLocale, country } = useI18n();
  return useMemo(() => {
    // R27: dates in the visitor's language ("17 nov" in Spanish); times, money and numbers in the
    // country's format (as @bhojango/i18n hours.js: "Closed · opens Sat 6:30 am").
    const inZone = (tz?: string | null) => ({
      date: (iso: string | Date, opts?: Intl.DateTimeFormatOptions) => date(iso, dateLocale, tz || country?.timezone, opts),
      time: (iso: string | Date) => time(iso, formatLocale, tz || country?.timezone),
    });
    return {
      money: (amount: number | string | null | undefined, currency?: string) =>
        money(amount, currency ?? country?.currency ?? "USD", formatLocale),
      /** R37: the bill, the payment and receipts: to the cent (385.80), so every line adds up to the total. */
      bill: (amount: number | string | null | undefined, currency?: string) =>
        money(amount, currency ?? country?.currency ?? "USD", formatLocale, { exact: true }),
      number: (n: number, digits?: number) => number(n, formatLocale, digits),
      ...inZone(null),
      zone: inZone,
      formatLocale,
      dateLocale,
    };
  }, [formatLocale, dateLocale, country]);
}

export function useLanguage() {
  const { language, languages, country } = useI18n();
  return {
    language,
    languages,
    /** The pill's list: [{code, name in its own script}], in Markets order. */
    list: languageList(languages),
    country,
    name: (l: string) => LANGUAGES[l as keyof typeof LANGUAGES]?.name ?? l,
  };
}

const YEAR = 60 * 60 * 24 * 365;

export function setCookie(name: string, value: string | null) {
  document.cookie = value === null
    ? `${name}=; path=/; max-age=0; samesite=lax`
    : `${name}=${encodeURIComponent(value)}; path=/; max-age=${YEAR}; samesite=lax`;
}

/** Set a preference cookie and re-render the server parts with it. */
export function usePrefs() {
  const router = useRouter();
  return {
    setLanguage: useCallback((lang: string) => {
      setCookie("bg_lang", lang);
      router.refresh();
    }, [router]),
    /**
     * "Change city": remember the city (its country decides currency and languages).
     * An address in another city no longer applies, and a language the new country
     * doesn't offer goes back to English. The caller navigates (home) afterwards.
     */
    setCity: useCallback((city: { code: string; locales: string[] }, current: { language: string; addressCity?: string | null }) => {
      setCookie("bg_city", city.code);
      if (current.addressCity !== city.code) setCookie("bg_addr", null);
      if (chooseLanguage(current.language, city.locales) !== current.language) setCookie("bg_lang", null);
    }, []),
    setPlace: useCallback((p: Place | null) => {
      setCookie("bg_addr", p ? JSON.stringify(p) : null);
      router.refresh();
    }, [router]),
  };
}
