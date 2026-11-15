"use client";
// The language and formats in the browser: the same messages the server used,
// so client components read the same words. Setting the language or the
// address writes a cookie (the server reads it) and refreshes the page.

import { createTranslator, LANGUAGES, type Messages } from "@bhojango/i18n";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import { date, money, number, time } from "./format";
import type { Place } from "./prefs";

interface I18n {
  language: string;
  languages: string[];
  formatLocale: string;
  country: { code: string; name: string; currency: string; timezone: string; distance_unit: string; phone_code: string } | null;
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

export function useT() {
  const { language, messages, fallback } = useI18n();
  return useMemo(() => createTranslator(language, messages, fallback), [language, messages, fallback]);
}

/** Money, numbers and dates in the country's format. */
export function useFormat() {
  const { formatLocale, country } = useI18n();
  return useMemo(
    () => ({
      money: (amount: number | string | null | undefined, currency?: string, opts?: { whole?: boolean }) =>
        money(amount, currency ?? country?.currency ?? "USD", formatLocale, opts),
      number: (n: number, digits?: number) => number(n, formatLocale, digits),
      date: (iso: string, opts?: Intl.DateTimeFormatOptions) => date(iso, formatLocale, country?.timezone, opts),
      time: (iso: string) => time(iso, formatLocale, country?.timezone),
      formatLocale,
    }),
    [formatLocale, country],
  );
}

export function useLanguage() {
  const { language, languages, country } = useI18n();
  return { language, languages, country, name: (l: string) => LANGUAGES[l as keyof typeof LANGUAGES]?.name ?? l };
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
    setCountry: useCallback((code: string) => {
      setCookie("bg_country", code);
      router.refresh();
    }, [router]),
    setPlace: useCallback((p: Place | null) => {
      setCookie("bg_addr", p ? JSON.stringify(p) : null);
      router.refresh();
    }, [router]),
  };
}
